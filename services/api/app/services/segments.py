"""Road-segment retrieval with PostGIS spatial queries and JSON seed fallback."""

import json
import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import psycopg

from app.core.config import get_settings
from app.services.risk_engine import calculate_risk, segment_threshold, rainfall_pressure
from app.services.weather import rainfall_signal

logger = logging.getLogger(__name__)


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
    """Apply current rain and verified-report signals to every road feature."""
    collection = list_segments(bbox)
    if verified_reports is None:
        from app.services.reports import verified_report_counts
        report_counts = verified_report_counts()
    else:
        report_counts = verified_reports
    is_dry_day = rainfall_mm_hour < 1.0

    for feature in collection["features"]:
        properties = feature["properties"]
        signals = dict(properties.get("signals", {}))

        # Per-segment rainfall pressure using T_seg
        t_seg = segment_threshold(
            signals.get("terrain", 0.0),
            signals.get("flood_history", 0.0),
        )
        signals["rainfall"] = rainfall_pressure(rainfall_mm_hour, t_seg)

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
