"""Road-segment retrieval with PostGIS spatial queries and JSON seed fallback."""

import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import psycopg

from app.core.config import get_settings
from app.core.redis import cache_delete_pattern, cache_get_json, cache_set_json
from app.services.risk_engine import calculate_risk, segment_threshold, rainfall_pressure
from app.services.weather import rainfall_signal

logger = logging.getLogger(__name__)

_SEGMENT_CACHE_TTL = 30  # seconds


def invalidate_segment_cache() -> None:
    """Purge all cached segment results, routes, and road network graph clone (call after mutations)."""
    cache_delete_pattern("segments:*")
    cache_delete_pattern("route:*")
    try:
        from app.services.routing import invalidate_graph_cache
        invalidate_graph_cache()
    except Exception:
        pass


@dataclass(frozen=True)
class SegmentMatch:
    segment_id: str
    distance_m: float


# ---------------------------------------------------------------------------
# JSON seed fallback (used when PostGIS has no rows in the segments table)
# ---------------------------------------------------------------------------

@lru_cache
def _load_seed_collection() -> dict[str, Any]:
    path: Path = get_settings().data_dir / "seeds" / "demo_segments.geojson"
    if not path.exists():
        raise FileNotFoundError(f"Demo segment data was not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_segments() -> dict[str, Any]:
    """Return a deep copy so routes cannot mutate process-wide cached seed data."""
    return json.loads(json.dumps(_load_seed_collection()))


# ---------------------------------------------------------------------------
# PostGIS segment loading
# ---------------------------------------------------------------------------

import time

_db_status_cache: dict[str, Any] = {"count": 0, "last_checked": 0.0, "reachable": False}


from app.core.database import is_db_available

def _db_segment_count() -> int:
    """Quick check whether the segments table has data, with a 15-second TTL cache."""
    if not is_db_available():
        return 0

    now = time.monotonic()
    if now - _db_status_cache["last_checked"] < 15.0:
        return _db_status_cache["count"]

    _db_status_cache["last_checked"] = now
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=1) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM segments")
                row = cur.fetchone()
                count = row[0] if row else 0
                _db_status_cache["count"] = count
                _db_status_cache["reachable"] = True
                return count
    except Exception:
        _db_status_cache["count"] = 0
        _db_status_cache["reachable"] = False
        return 0



def _load_db_segments(bbox: tuple[float, float, float, float] | None = None) -> dict[str, Any]:
    """Load segments from PostGIS as a GeoJSON FeatureCollection."""
    query = """
        SELECT seg_id, name, highway, length_m, is_underpass,
               signal_terrain, signal_flood_history, signal_drainage,
               threshold_mm_hr,
               ST_AsGeoJSON(geom)::json AS geometry
        FROM segments
    """
    params: list[Any] = []
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        query += """
            WHERE ST_Intersects(
                geom,
                ST_MakeEnvelope(%s, %s, %s, %s, 4326)
            )
        """
        params.extend([min_lon, min_lat, max_lon, max_lat])
    query += " ORDER BY seg_id"

    features: list[dict[str, Any]] = []
    with psycopg.connect(get_settings().database_url, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            for row in cur.fetchall():
                features.append({
                    "type": "Feature",
                    "properties": {
                        "segment_id": row[0],
                        "name": row[1],
                        "highway": row[2],
                        "length_m": row[3],
                        "is_underpass": row[4],
                        "signals": {
                            "terrain": row[5],
                            "flood_history": row[6],
                            "drainage": row[7],
                        },
                        "threshold_mm_hr": row[8],
                    },
                    "geometry": row[9],
                })
    return {"type": "FeatureCollection", "name": "pune_segments", "features": features}


# ---------------------------------------------------------------------------
# Unified public API
# ---------------------------------------------------------------------------

def _use_db() -> bool:
    """Decide whether to query PostGIS or fall back to the JSON seed."""
    if not is_db_available():
        return False
    try:
        return _db_segment_count() > 0
    except Exception:
        return False


def list_segments(bbox: tuple[float, float, float, float] | None = None) -> dict[str, Any]:
    """Return raw segment GeoJSON (no risk scoring applied yet)."""
    if _use_db():
        try:
            return _load_db_segments(bbox)
        except Exception as exc:
            logger.warning("PostGIS segment load failed, falling back to seed: %s", exc)
    return _seed_segments()


def scored_segments(
    rainfall_mm_hour: float,
    verified_reports: dict[str, int] | None = None,
    bbox: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    """Apply current rain and verified-report signals to every road feature.

    Results are cached for 30 s keyed by rainfall, bbox, and report-count fingerprint
    so repeated calls within the same polling cycle skip recomputation.
    """
    if verified_reports is None:
        from app.services.reports import verified_report_counts
        report_counts = verified_report_counts()
    else:
        report_counts = verified_reports

    # Build a stable, short cache key
    report_hash = hashlib.md5(
        json.dumps(sorted(report_counts.items()), separators=(",", ":")).encode()
    ).hexdigest()[:8]
    bbox_str = f"{bbox[0]:.4f},{bbox[1]:.4f},{bbox[2]:.4f},{bbox[3]:.4f}" if bbox else "none"
    cache_key = f"segments:{rainfall_mm_hour:.1f}:{bbox_str}:{report_hash}"

    cached = cache_get_json(cache_key)
    if cached is not None:
        return cached

    collection = list_segments(bbox)
    is_dry_day = rainfall_mm_hour < 1.0

    from app.services.weather import rain_store
    rain_resp = rain_store.response()
    is_live_or_forecast = (
        abs(rainfall_mm_hour - rain_resp.rainfall_mm_hour) < 0.05
        or abs(rainfall_mm_hour - rain_resp.forecast_30m_mm_hour) < 0.05
    )
    is_forecast = (
        abs(rainfall_mm_hour - rain_resp.forecast_30m_mm_hour) < 0.05
        and abs(rainfall_mm_hour - rain_resp.rainfall_mm_hour) >= 0.05
    )

    for feature in collection["features"]:
        properties = feature["properties"]
        signals = dict(properties.get("signals", {}))

        # Check if segment has geometry for nearest-station spatial rainfall
        seg_rain = rainfall_mm_hour
        if is_live_or_forecast:
            geom_coords = feature.get("geometry", {}).get("coordinates", [])
            if geom_coords:
                mid = geom_coords[len(geom_coords) // 2]
                seg_rain = rain_store.get_rainfall_for_location(
                    latitude=mid[1], longitude=mid[0], use_forecast=is_forecast
                )

        # Per-segment rainfall pressure using T_seg
        t_seg = segment_threshold(
            signals.get("terrain", 0.0),
            signals.get("flood_history", 0.0),
        )
        signals["rainfall"] = rainfall_pressure(seg_rain, t_seg)

        active_reports = report_counts.get(properties["segment_id"], 0)
        signals["citizen_reports"] = min(1.0, active_reports / 3)

        result = calculate_risk(signals, is_dry_day=is_dry_day)
        properties.update(
            {
                "risk_score": result.score,
                "confidence": result.confidence,
                "risk_band": result.band,
                "reasons": result.reasons,
                "signals": signals,
                "active_verified_reports": active_reports,
            }
        )

    cache_set_json(cache_key, collection, ttl_sec=_SEGMENT_CACHE_TTL)
    return collection


def get_segment(segment_id: str) -> dict[str, Any] | None:
    """Fetch a single segment by ID."""
    if _use_db():
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT seg_id, name, highway, length_m, is_underpass,
                               signal_terrain, signal_flood_history, signal_drainage,
                               threshold_mm_hr,
                               ST_AsGeoJSON(geom)::json AS geometry
                        FROM segments WHERE seg_id = %s
                        """,
                        (segment_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        return {
                            "type": "Feature",
                            "properties": {
                                "segment_id": row[0],
                                "name": row[1],
                                "highway": row[2],
                                "length_m": row[3],
                                "is_underpass": row[4],
                                "signals": {
                                    "terrain": row[5],
                                    "flood_history": row[6],
                                    "drainage": row[7],
                                },
                                "threshold_mm_hr": row[8],
                            },
                            "geometry": row[9],
                        }
        except Exception as exc:
            logger.warning("PostGIS get_segment failed, falling back to seed: %s", exc)

    # Seed fallback
    for feature in _load_seed_collection()["features"]:
        if feature["properties"]["segment_id"] == segment_id:
            return feature
    return None


# ---------------------------------------------------------------------------
# Nearest-segment snapping (PostGIS KNN with seed fallback)
# ---------------------------------------------------------------------------

def nearest_segment(longitude: float, latitude: float) -> SegmentMatch | None:
    """Find the closest road segment to a point using PostGIS KNN or Euclidean fallback."""
    if _use_db():
        try:
            return _nearest_segment_postgis(longitude, latitude)
        except Exception as exc:
            logger.warning("PostGIS KNN snap failed, falling back to seed: %s", exc)
    return _nearest_segment_seed(longitude, latitude)


def _nearest_segment_postgis(longitude: float, latitude: float) -> SegmentMatch | None:
    """Sub-millisecond nearest-neighbor lookup using PostGIS GIST index."""
    with psycopg.connect(get_settings().database_url, connect_timeout=2) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT seg_id,
                       ST_Distance(
                           geom::geography,
                           ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                       ) AS distance_m
                FROM segments
                ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
                LIMIT 1
                """,
                (longitude, latitude, longitude, latitude),
            )
            row = cur.fetchone()
            if row:
                return SegmentMatch(segment_id=row[0], distance_m=round(row[1], 1))
    return None


def _distance_to_line_m(
    longitude: float, latitude: float, coordinates: list[list[float]]
) -> float:
    """Approximate point-to-line distance in metres for the small Pune demo area."""
    latitude_scale = 111_320.0
    longitude_scale = latitude_scale * math.cos(math.radians(latitude))
    px, py = longitude * longitude_scale, latitude * latitude_scale
    nearest = float("inf")

    for start, end in zip(coordinates, coordinates[1:]):
        ax, ay = start[0] * longitude_scale, start[1] * latitude_scale
        bx, by = end[0] * longitude_scale, end[1] * latitude_scale
        dx, dy = bx - ax, by - ay
        denominator = dx * dx + dy * dy
        ratio = 0.0 if denominator == 0 else ((px - ax) * dx + (py - ay) * dy) / denominator
        ratio = max(0.0, min(1.0, ratio))
        cx, cy = ax + ratio * dx, ay + ratio * dy
        nearest = min(nearest, math.hypot(px - cx, py - cy))
    return nearest


def _nearest_segment_seed(longitude: float, latitude: float) -> SegmentMatch | None:
    """Seed-based fallback: iterate over all demo segments."""
    closest: SegmentMatch | None = None
    for feature in _load_seed_collection()["features"]:
        geometry = feature.get("geometry", {})
        if geometry.get("type") != "LineString":
            continue
        distance_m = _distance_to_line_m(longitude, latitude, geometry["coordinates"])
        candidate = SegmentMatch(feature["properties"]["segment_id"], round(distance_m, 1))
        if closest is None or candidate.distance_m < closest.distance_m:
            closest = candidate
    return closest


# ---------------------------------------------------------------------------
# Background segment risk persistence to segment_risk_current
# ---------------------------------------------------------------------------

_in_memory_segment_risk: dict[str, dict[str, Any]] = {}


def persist_segment_risk_snapshot() -> int:
    """Score all segments against current rain and 30-min forecast, then upsert to DB.

    Upserts into segment_risk_current:
        seg_id, risk_now, risk_30, risk_band, confidence, factors (jsonb), updated_at
    Returns the number of segments persisted.
    """
    from app.services.reports import verified_report_counts
    from app.services.weather import rain_store

    rain = rain_store.response()
    rain_now = rain.rainfall_mm_hour
    rain_30 = rain.forecast_30m_mm_hour
    report_counts = verified_report_counts()

    collection_now = scored_segments(rain_now, report_counts)
    collection_30 = scored_segments(rain_30, report_counts)

    scores_30 = {
        f["properties"]["segment_id"]: f["properties"]["risk_score"]
        for f in collection_30.get("features", [])
    }

    now_utc = datetime.now(timezone.utc)
    records: list[tuple[str, float, float, str, float, str, datetime]] = []

    for feature in collection_now.get("features", []):
        props = feature["properties"]
        seg_id = str(props["segment_id"])
        risk_now = float(props["risk_score"])
        risk_30 = float(scores_30.get(seg_id, risk_now))
        risk_band = str(props["risk_band"])
        confidence = float(props["confidence"])

        factors = dict(props.get("signals", {}))
        factors["reasons"] = props.get("reasons", [])

        # In-memory fallback store
        _in_memory_segment_risk[seg_id] = {
            "seg_id": seg_id,
            "risk_now": risk_now,
            "risk_30": risk_30,
            "risk_band": risk_band,
            "confidence": confidence,
            "factors": factors,
            "updated_at": now_utc,
        }

        records.append((
            seg_id,
            risk_now,
            risk_30,
            risk_band,
            confidence,
            json.dumps(factors),
            now_utc,
        ))

    # Persist to PostgreSQL if available and PostGIS segments exist
    if _use_db() and records:
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    cur.executemany(
                        """
                        INSERT INTO segment_risk_current (
                            seg_id, risk_now, risk_30, risk_band, confidence, factors, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
                        ON CONFLICT (seg_id) DO UPDATE SET
                            risk_now = EXCLUDED.risk_now,
                            risk_30 = EXCLUDED.risk_30,
                            risk_band = EXCLUDED.risk_band,
                            confidence = EXCLUDED.confidence,
                            factors = EXCLUDED.factors,
                            updated_at = EXCLUDED.updated_at
                        """,
                        records,
                    )
                conn.commit()
        except Exception as exc:
            logger.debug("Failed to upsert segment risk to database: %s", exc)

    return len(records)


async def persist_segment_risk(interval_sec: float = 60.0) -> None:
    """Periodic background asyncio task persisting risk scores to segment_risk_current every 60s."""
    while True:
        try:
            persist_segment_risk_snapshot()
        except Exception as exc:
            logger.warning("Segment risk persistence error: %s", exc)
        await asyncio.sleep(interval_sec)


def get_persisted_segment_risk(segment_id: str | None = None) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Read risk scores from segment_risk_current table with in-memory fallback."""
    if _use_db():
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=1) as conn:
                with conn.cursor() as cur:
                    if segment_id:
                        cur.execute(
                            """
                            SELECT seg_id, risk_now, risk_30, risk_band, confidence, factors, updated_at
                            FROM segment_risk_current WHERE seg_id = %s
                            """,
                            (segment_id,),
                        )
                        row = cur.fetchone()
                        if row:
                            return {
                                "seg_id": row[0],
                                "risk_now": float(row[1]),
                                "risk_30": float(row[2]),
                                "risk_band": row[3],
                                "confidence": float(row[4]),
                                "factors": row[5] if isinstance(row[5], dict) else json.loads(row[5]),
                                "updated_at": row[6].isoformat() if hasattr(row[6], "isoformat") else str(row[6]),
                            }
                    else:
                        cur.execute(
                            """
                            SELECT seg_id, risk_now, risk_30, risk_band, confidence, factors, updated_at
                            FROM segment_risk_current ORDER BY seg_id
                            """
                        )
                        rows = cur.fetchall()
                        if rows:
                            return [
                                {
                                    "seg_id": r[0],
                                    "risk_now": float(r[1]),
                                    "risk_30": float(r[2]),
                                    "risk_band": r[3],
                                    "confidence": float(r[4]),
                                    "factors": r[5] if isinstance(r[5], dict) else json.loads(r[5]),
                                    "updated_at": r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6]),
                                }
                                for r in rows
                            ]
        except Exception as exc:
            logger.debug("Failed to fetch persisted segment risk: %s", exc)

    # In-memory fallback
    if segment_id:
        return _in_memory_segment_risk.get(segment_id)
    return list(_in_memory_segment_risk.values())

