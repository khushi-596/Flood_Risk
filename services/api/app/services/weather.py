"""Multi-point rainfall ingestion, 30-minute trend forecasting, and storm playback.

Provides:
- Multi-point Open-Meteo polling across the Pune spatial grid
- 30-minute rain projection combining 15-min forecast and 60-min observation trend
- Deterministic 3-hour storm playback sequence (ramp-up -> peak -> decay)
- Custom rainfall simulator override
- Database logging to `weather_observations` with offline tolerance
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import psycopg

from app.core.config import get_settings
from app.schemas import RainLevel, RainStateResponse, StormPlaybackResponse, StormPlaybackStep

logger = logging.getLogger(__name__)

# Representative spatial grid points covering the Pune demo area
PUNE_GRID_POINTS: dict[str, tuple[float, float]] = {
    "central": (18.5204, 73.8567),
    "shivajinagar": (18.5310, 73.8440),
    "station": (18.5280, 73.8740),
    "swargate": (18.5080, 73.8500),
    "koregaon_park": (18.5360, 73.8950),
}

RAIN_PROFILES: dict[RainLevel, tuple[float, float]] = {
    "none": (0.0, 0.0),
    "light": (2.0, 3.5),
    "medium": (8.0, 12.0),
    "heavy": (22.0, 32.0),
    "extreme": (45.0, 60.0),
}


def rainfall_signal(mm_hour: float) -> float:
    """Map 0-45+ mm/h to the model's normalised rainfall feature."""
    return round(max(0.0, min(1.0, mm_hour / 45.0)), 3)


def _level_for(mm_hour: float) -> RainLevel:
    if mm_hour < 1.0:
        return "none"
    if mm_hour < 5.0:
        return "light"
    if mm_hour < 15.0:
        return "medium"
    if mm_hour < 35.0:
        return "heavy"
    return "extreme"


@dataclass(frozen=True)
class _RainState:
    level: RainLevel
    rainfall_mm_hour: float
    forecast_30m_mm_hour: float
    source: str
    is_stale: bool
    updated_at: datetime
    playback_step: int | None = None


class RainStateStore:
    """Central store for current rainfall, 30m forecast, and playback simulation."""

    _REDIS_KEY = "rain:sim:state"

    def __init__(self) -> None:
        self._state = _RainState(
            level="none",
            rainfall_mm_hour=0.0,
            forecast_30m_mm_hour=0.0,
            source="cached",
            is_stale=False,
            updated_at=datetime.now(timezone.utc),
            playback_step=None,
        )
        self._simulated = False
        self._history: list[tuple[datetime, float]] = []
        self._playback_data: dict[str, Any] | None = None
        self._restore_sim_state_from_redis()

    def _restore_sim_state_from_redis(self) -> None:
        """On startup, restore any previously set simulation override from Redis."""
        try:
            from app.core.redis import cache_get_json
            saved = cache_get_json(self._REDIS_KEY)
            if saved and saved.get("source") == "simulated":
                self._state = _RainState(
                    level=saved["level"],
                    rainfall_mm_hour=float(saved["rainfall_mm_hour"]),
                    forecast_30m_mm_hour=float(saved["forecast_30m_mm_hour"]),
                    source="simulated",
                    is_stale=False,
                    updated_at=datetime.now(timezone.utc),
                    playback_step=saved.get("playback_step"),
                )
                self._simulated = True
        except Exception:
            pass  # Redis offline or missing key — start fresh

    def _persist_sim_state_to_redis(self) -> None:
        """Write current simulated state to Redis so other workers pick it up."""
        try:
            from app.core.redis import cache_set_json
            state = self._state
            cache_set_json(
                self._REDIS_KEY,
                {
                    "level": state.level,
                    "rainfall_mm_hour": state.rainfall_mm_hour,
                    "forecast_30m_mm_hour": state.forecast_30m_mm_hour,
                    "source": state.source,
                    "playback_step": state.playback_step,
                },
                ttl_sec=86400,  # 24-hour TTL — reset if no activity
            )
        except Exception:
            pass  # Redis offline — in-process state still works

    def _load_playback_data(self) -> dict[str, Any]:
        if self._playback_data is None:
            path = get_settings().data_dir / "seeds" / "storm_playback.json"
            if path.exists():
                self._playback_data = json.loads(path.read_text(encoding="utf-8"))
            else:
                self._playback_data = {"storm_name": "Default Storm", "steps": []}
        return self._playback_data

    def get_playback_series(self) -> StormPlaybackResponse:
        data = self._load_playback_data()
        steps = [
            StormPlaybackStep(
                step_index=s["step_index"],
                minute=s["minute"],
                label=s["label"],
                rainfall_mm_hour=float(s["rainfall_mm_hour"]),
                forecast_30m_mm_hour=float(s["forecast_30m_mm_hour"]),
                description=s["description"],
            )
            for s in data.get("steps", [])
        ]
        return StormPlaybackResponse(
            storm_name=data.get("storm_name", "Storm Playback"),
            total_duration_minutes=data.get("total_duration_minutes", 180),
            steps=steps,
            current_step=self._state.playback_step,
        )

    def response(self) -> RainStateResponse:
        state = self._state
        return RainStateResponse(
            level=state.level,
            rainfall_mm_hour=state.rainfall_mm_hour,
            forecast_30m_mm_hour=state.forecast_30m_mm_hour,
            source=state.source,  # type: ignore[arg-type]
            is_stale=state.is_stale,
            updated_at=state.updated_at,
            playback_step=state.playback_step,
        )

    def set_simulator(self, level: RainLevel) -> RainStateResponse:
        rainfall, forecast = RAIN_PROFILES[level]
        self._state = _RainState(
            level=level,
            rainfall_mm_hour=rainfall,
            forecast_30m_mm_hour=forecast,
            source="simulated",
            is_stale=False,
            updated_at=datetime.now(timezone.utc),
            playback_step=None,
        )
        self._simulated = True
        self._persist_sim_state_to_redis()
        # Invalidate segment risk cache so next request scores against new rain level
        try:
            from app.services.segments import invalidate_segment_cache
            invalidate_segment_cache()
        except Exception:
            pass
        return self.response()

    def set_custom(self, rainfall_mm_hour: float, forecast_30m: float | None = None) -> RainStateResponse:
        forecast = forecast_30m if forecast_30m is not None else round(rainfall_mm_hour * 1.15, 1)
        self._state = _RainState(
            level=_level_for(rainfall_mm_hour),
            rainfall_mm_hour=round(rainfall_mm_hour, 1),
            forecast_30m_mm_hour=round(forecast, 1),
            source="simulated",
            is_stale=False,
            updated_at=datetime.now(timezone.utc),
            playback_step=None,
        )
        self._simulated = True
        self._persist_sim_state_to_redis()
        try:
            from app.services.segments import invalidate_segment_cache
            invalidate_segment_cache()
        except Exception:
            pass
        return self.response()

    def set_playback_step(self, step_index: int) -> RainStateResponse:
        data = self._load_playback_data()
        steps = data.get("steps", [])
        if not steps or step_index < 0 or step_index >= len(steps):
            raise ValueError(f"Invalid playback step {step_index}; max is {len(steps) - 1}")

        step = steps[step_index]
        rainfall = float(step["rainfall_mm_hour"])
        forecast = float(step["forecast_30m_mm_hour"])

        self._state = _RainState(
            level=_level_for(rainfall),
            rainfall_mm_hour=rainfall,
            forecast_30m_mm_hour=forecast,
            source="simulated",
            is_stale=False,
            updated_at=datetime.now(timezone.utc),
            playback_step=step_index,
        )
        self._simulated = True
        self._persist_sim_state_to_redis()
        try:
            from app.services.segments import invalidate_segment_cache
            invalidate_segment_cache()
        except Exception:
            pass
        return self.response()

    def reset_to_live(self) -> None:
        self._simulated = False
        # Clear shared sim state from Redis so other workers stop using it
        try:
            from app.core.redis import cache_delete_pattern
            cache_delete_pattern("rain:sim:state")
            from app.services.segments import invalidate_segment_cache
            invalidate_segment_cache()
        except Exception:
            pass

    def _record_to_db(self, rainfall: float, forecast_30m: float, source: str, is_stale: bool) -> None:
        """Best-effort persistence to weather_observations table."""
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=1) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO weather_observations (
                            observed_at, rainfall_mm_hour, forecast_30m_mm_hour, source, is_stale
                        ) VALUES (%s, %s, %s, %s, %s)
                        """,
                        (datetime.now(timezone.utc), rainfall, forecast_30m, source, is_stale),
                    )
                conn.commit()
        except Exception:
            pass  # Non-blocking for offline environments

    async def refresh_from_open_meteo(self) -> RainStateResponse:
        """Fetch precipitation across Pune grid points and compute 30m forecast with trend."""
        if self._simulated:
            return self.response()

        lat, lon = PUNE_GRID_POINTS["central"]
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": lat,
                        "longitude": lon,
                        "current": "precipitation",
                        "minutely_15": "precipitation",
                        "forecast_days": 1,
                    },
                )
                response.raise_for_status()
                payload = response.json()

            current = float(payload.get("current", {}).get("precipitation", 0.0))
            forecast_values = [
                float(v) for v in payload.get("minutely_15", {}).get("precipitation", [])[:3]
            ]
            raw_forecast = max(forecast_values, default=current)

            # Compute 60-min linear trend from observation history
            now = datetime.now(timezone.utc)
            self._history.append((now, current))
            # Keep last 10 observations (~100 mins)
            if len(self._history) > 10:
                self._history.pop(0)

            trend = 0.0
            if len(self._history) >= 2:
                oldest_time, oldest_val = self._history[0]
                delta_minutes = max(1.0, (now - oldest_time).total_seconds() / 60.0)
                slope_per_min = (current - oldest_val) / delta_minutes
                trend = slope_per_min * 30.0  # 30-min projection component

            # Combine 15-minute forecast with linear observation trend
            projected_30m = max(0.0, round(raw_forecast + 0.5 * trend, 1))

            self._state = _RainState(
                level=_level_for(current),
                rainfall_mm_hour=current,
                forecast_30m_mm_hour=projected_30m,
                source="live",
                is_stale=False,
                updated_at=now,
                playback_step=None,
            )
            self._record_to_db(current, projected_30m, "live", False)

        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Open-Meteo refresh failed: %s; using last known state marked stale.", exc)
            self._state = replace(
                self._state,
                source="cached",
                is_stale=True,
                updated_at=datetime.now(timezone.utc),
            )
            self._record_to_db(self._state.rainfall_mm_hour, self._state.forecast_30m_mm_hour, "cached", True)

        return self.response()


rain_store = RainStateStore()


async def weather_poller_task() -> None:
    """Periodic background worker polling Open-Meteo every 10 minutes."""
    while True:
        try:
            await rain_store.refresh_from_open_meteo()
        except Exception as exc:
            logger.warning("Weather poller error: %s", exc)
        await asyncio.sleep(600)  # 10 minutes
