"""Deterministic Day 2 route comparison over the current segment risk layer."""

from __future__ import annotations

import math
from typing import Any

from app.schemas import Coordinate, RouteOption, RouteRequest, RouteResponse, TravelAdviceRequest, TravelAdviceResponse
from app.services.reports import verified_report_counts
from app.services.risk_engine import load_vehicle_limits
from app.services.segments import scored_segments
from app.services.weather import rain_store


def _distance_m(a: Coordinate, b: Coordinate) -> float:
    latitude_scale = 111_320.0
    longitude_scale = latitude_scale * math.cos(math.radians((a.latitude + b.latitude) / 2))
    return math.hypot((a.longitude - b.longitude) * longitude_scale, (a.latitude - b.latitude) * latitude_scale)


def _route_geometry(origin: Coordinate, destination: Coordinate, route_id: str) -> dict[str, Any]:
    midpoint_lon = (origin.longitude + destination.longitude) / 2
    midpoint_lat = (origin.latitude + destination.latitude) / 2
    offset = {"fast": (0.0, 0.0), "balanced": (-0.006, 0.003), "safe": (-0.013, 0.007)}[route_id]
    if route_id == "fast":
        coordinates = [[origin.longitude, origin.latitude], [destination.longitude, destination.latitude]]
    else:
        coordinates = [
            [origin.longitude, origin.latitude],
            [midpoint_lon + offset[0], midpoint_lat + offset[1]],
            [destination.longitude, destination.latitude],
        ]
    return {"type": "LineString", "coordinates": coordinates}


def _route_option(
    route_id: str,
    origin: Coordinate,
    destination: Coordinate,
    ranked_segments: list[dict[str, Any]],
) -> RouteOption:
    if route_id == "fast":
        chosen = sorted(ranked_segments, key=lambda item: item["properties"]["risk_score"], reverse=True)[:3]
        multiplier, speed_kmph, label = 1.0, 28, "Fastest"
    elif route_id == "safe":
        chosen = sorted(ranked_segments, key=lambda item: item["properties"]["risk_score"])[:3]
        multiplier, speed_kmph, label = 1.28, 23, "Safest"
    else:
        ordered = sorted(ranked_segments, key=lambda item: item["properties"]["risk_score"])
        chosen = [ordered[0], ordered[2], ordered[1]]
        multiplier, speed_kmph, label = 1.12, 25, "Balanced"
    risks = [item["properties"]["risk_score"] for item in chosen]
    base_distance = _distance_m(origin, destination)
    distance = max(450, round(base_distance * multiplier / 25) * 25)
    duration = max(2, math.ceil((distance / 1000) / speed_kmph * 60))
    average_risk = round(sum(risks) / len(risks), 3)
    highest_risk = round(max(risks), 3)
    risky_count = sum(risk >= 0.6 for risk in risks)
    recommendation = (
        "Avoid if possible; this route crosses severe flood-risk road segments."
        if highest_risk >= 0.8
        else "Use with caution and check the highlighted road explanations."
        if highest_risk >= 0.6
        else "Preferred for current conditions."
    )
    return RouteOption(
        id=route_id, label=label, geometry=_route_geometry(origin, destination, route_id),
        distance_m=distance, duration_min=duration, average_risk=average_risk, highest_risk=highest_risk,
        risky_segment_count=risky_count,
        segment_ids=[item["properties"]["segment_id"] for item in chosen], recommendation=recommendation,
    )


def compare_routes(request: RouteRequest) -> RouteResponse:
    rain = rain_store.response()
    collection = scored_segments(rain.rainfall_mm_hour, verified_report_counts())
    routes = [
        _route_option(route_id, request.origin, request.destination, collection["features"])
        for route_id in ("fast", "safe", "balanced")
    ]
    return RouteResponse(vehicle=request.vehicle, rain=rain, routes=routes)


def travel_advice(request: TravelAdviceRequest) -> TravelAdviceResponse:
    rain = rain_store.response()
    counts = verified_report_counts()
    current = scored_segments(rain.rainfall_mm_hour, counts)["features"]
    forecast = scored_segments(rain.forecast_30m_mm_hour, counts)["features"]
    if request.origin and request.destination:
        current_risk = _route_option("safe", request.origin, request.destination, current).average_risk
        future_risk = _route_option("safe", request.origin, request.destination, forecast).average_risk
    else:
        current_risk = round(max(item["properties"]["risk_score"] for item in current), 3)
        future_risk = round(max(item["properties"]["risk_score"] for item in forecast), 3)
    thresholds = load_vehicle_limits()[request.vehicle]
    if future_risk >= thresholds["avoid_at"]:
        verdict = "avoid"
    elif future_risk >= thresholds["wait_at"]:
        verdict = "wait"
    elif future_risk >= thresholds["caution_at"]:
        verdict = "caution"
    else:
        verdict = "go"
    trend = "rising" if future_risk > current_risk + 0.03 else "falling" if future_risk < current_risk - 0.03 else "stable"
    reasons = [
        f"{request.vehicle.replace('_', ' ')} safety limit applied.",
        f"Rain is {trend}: {rain.rainfall_mm_hour:.1f} to {rain.forecast_30m_mm_hour:.1f} mm/h over the next 30 minutes.",
    ]
    if rain.is_stale:
        reasons.append("Live weather is unavailable; the last known rainfall value is being used.")
    return TravelAdviceResponse(
        verdict=verdict, vehicle=request.vehicle, risk_now=current_risk, risk_in_30m=future_risk,
        trend=trend, reasons=reasons, updated_at=rain.updated_at,
    )
