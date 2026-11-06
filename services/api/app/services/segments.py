import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.risk_engine import calculate_risk
from app.services.weather import rainfall_signal


@dataclass(frozen=True)
class SegmentMatch:
    segment_id: str
    distance_m: float


@lru_cache
def _load_collection() -> dict[str, Any]:
    path: Path = get_settings().data_dir / "seeds" / "demo_segments.geojson"
    if not path.exists():
        raise FileNotFoundError(f"Demo segment data was not found at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_segments() -> dict[str, Any]:
    """Return a copy so routes cannot mutate process-wide cached seed data."""
    return json.loads(json.dumps(_load_collection()))


def scored_segments(
    rainfall_mm_hour: float, verified_reports: dict[str, int] | None = None
) -> dict[str, Any]:
    """Apply current rain and verified-report signals to every road feature."""
    collection = list_segments()
    report_counts = verified_reports or {}
    is_dry_day = rainfall_mm_hour < 1.0
    for feature in collection["features"]:
        properties = feature["properties"]
        signals = dict(properties.get("signals", {}))
        signals["rainfall"] = rainfall_signal(rainfall_mm_hour)
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
    for feature in _load_collection()["features"]:
        if feature["properties"]["segment_id"] == segment_id:
            return feature
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


def nearest_segment(longitude: float, latitude: float) -> SegmentMatch | None:
    closest: SegmentMatch | None = None
    for feature in _load_collection()["features"]:
        geometry = feature.get("geometry", {})
        if geometry.get("type") != "LineString":
            continue
        distance_m = _distance_to_line_m(longitude, latitude, geometry["coordinates"])
        candidate = SegmentMatch(feature["properties"]["segment_id"], round(distance_m, 1))
        if closest is None or candidate.distance_m < closest.distance_m:
            closest = candidate
    return closest
