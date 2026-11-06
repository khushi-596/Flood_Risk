"""Rainfall state with a simulator-first, stale-safe live weather fallback."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone

import httpx

from app.schemas import RainLevel, RainStateResponse

RAIN_PROFILES: dict[RainLevel, tuple[float, float]] = {
    "none": (0.0, 0.0),
    "light": (2.0, 3.0),
    "medium": (8.0, 11.0),
    "heavy": (22.0, 30.0),
    "extreme": (45.0, 58.0),
}


def rainfall_signal(mm_hour: float) -> float:
    """Map 0-45+ mm/h to the model's normalised rainfall feature."""
    return round(max(0.0, min(1.0, mm_hour / 45.0)), 3)


def _level_for(mm_hour: float) -> RainLevel:
    if mm_hour < 1:
        return "none"
    if mm_hour < 5:
        return "light"
    if mm_hour < 15:
        return "medium"
    if mm_hour < 35:
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


class RainStateStore:
    """In-process state for demo reliability; Redis persistence is a deployment swap-in."""

    def __init__(self) -> None:
        self._state = _RainState(
            level="none",
            rainfall_mm_hour=0.0,
            forecast_30m_mm_hour=0.0,
            source="cached",
            is_stale=False,
            updated_at=datetime.now(timezone.utc),
        )
        self._simulated = False

    def response(self) -> RainStateResponse:
        state = self._state
        return RainStateResponse(
            level=state.level,
            rainfall_mm_hour=state.rainfall_mm_hour,
            forecast_30m_mm_hour=state.forecast_30m_mm_hour,
            source=state.source,  # type: ignore[arg-type]
            is_stale=state.is_stale,
            updated_at=state.updated_at,
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
        )
        self._simulated = True
        return self.response()

    async def refresh_from_open_meteo(self) -> RainStateResponse:
        """Refresh Pune weather unless a presenter explicitly enabled simulator mode."""
        if self._simulated:
            return self.response()
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(
                    "https://api.open-meteo.com/v1/forecast",
                    params={
                        "latitude": 18.5204,
                        "longitude": 73.8567,
                        "current": "precipitation",
                        "minutely_15": "precipitation",
                        "forecast_days": 1,
                    },
                )
                response.raise_for_status()
                payload = response.json()
            current = float(payload["current"].get("precipitation", 0.0))
            forecast_values = payload.get("minutely_15", {}).get("precipitation", [])[:2]
            forecast = max([current, *(float(value) for value in forecast_values)], default=current)
            self._state = _RainState(
                level=_level_for(current),
                rainfall_mm_hour=current,
                forecast_30m_mm_hour=forecast,
                source="live",
                is_stale=False,
                updated_at=datetime.now(timezone.utc),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            self._state = replace(self._state, source="cached", is_stale=True, updated_at=datetime.now(timezone.utc))
        return self.response()


rain_store = RainStateStore()
