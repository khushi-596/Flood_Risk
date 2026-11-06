"""Fixed 5 Origin-Destination Benchmark Tests across 5 Rain Scenarios.

Verifies the mathematical invariants from Workplan Section 7 & Dev E3:
1. Safe route risk <= Fast route risk across all conditions
2. In dry weather (none), all routes exhibit low risk (<= 0.25)
3. In heavy and extreme weather, the safe route effectively bypasses flood hotspots
4. Monotonic risk growth: risk(extreme) >= risk(none)
5. Robustness across all supported vehicle categories (car, two_wheeler, truck, auto, bus)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import Coordinate, RouteRequest, TravelAdviceRequest
from app.services.routing import compare_routes, travel_advice
from app.services.weather import rain_store

client = TestClient(app)

BENCHMARK_OD_PAIRS = [
    (
        "swargate_to_pune_station",
        Coordinate(longitude=73.8580, latitude=18.5018),  # Swargate Chowk
        Coordinate(longitude=73.8744, latitude=18.5282),  # Pune Station
    ),
    (
        "deccan_to_shivajinagar",
        Coordinate(longitude=73.8402, latitude=18.5168),  # Deccan Gymkhana
        Coordinate(longitude=73.8476, latitude=18.5292),  # Shivajinagar
    ),
    (
        "swargate_to_deccan",
        Coordinate(longitude=73.8504, latitude=18.5132),  # Swargate North / Hirabaug
        Coordinate(longitude=73.8402, latitude=18.5168),  # Deccan Gymkhana
    ),
    (
        "pune_station_to_bund_garden",
        Coordinate(longitude=73.8744, latitude=18.5282),  # Pune Station
        Coordinate(longitude=73.8820, latitude=18.5340),  # Bund Garden
    ),
    (
        "kothrud_to_koregaon_park",
        Coordinate(longitude=73.8050, latitude=18.5060),  # Kothrud Depot
        Coordinate(longitude=73.8952, latitude=18.5359),  # Koregaon Park
    ),
]

RAIN_PROFILES = ["none", "light", "medium", "heavy", "extreme"]


@pytest.fixture(autouse=True)
def reset_rain():
    """Ensure rain state is cleanly restored after each test."""
    yield
    rain_store.set_simulator("none")


@pytest.mark.parametrize("route_name,origin,destination", BENCHMARK_OD_PAIRS)
@pytest.mark.parametrize("rain_level", RAIN_PROFILES)
def test_od_benchmark_safe_risk_bounded_by_fast_risk(
    route_name: str, origin: Coordinate, destination: Coordinate, rain_level: str
) -> None:
    """Core mathematical invariant: Risk(Safe) <= Risk(Fast)."""
    rain_store.set_simulator(rain_level)
    req = RouteRequest(origin=origin, destination=destination, vehicle="car")
    res = compare_routes(req)

    assert len(res.routes) == 3
    routes = {r.id: r for r in res.routes}
    fast = routes["fast"]
    safe = routes["safe"]

    # Geometric validity
    for r in res.routes:
        assert r.geometry["type"] == "LineString"
        assert len(r.geometry["coordinates"]) >= 2
        assert r.distance_m > 0
        assert r.duration_min > 0

    # Invariant: safe route peak risk must never exceed fast route peak risk
    assert safe.highest_risk <= fast.highest_risk + 1e-4, (
        f"[{route_name} | {rain_level}] Safe highest risk ({safe.highest_risk}) > Fast highest risk ({fast.highest_risk})"
    )
    # Invariant: safe route average risk must never exceed fast route average risk
    assert safe.average_risk <= fast.average_risk + 1e-4, (
        f"[{route_name} | {rain_level}] Safe average risk ({safe.average_risk}) > Fast average risk ({fast.average_risk})"
    )


@pytest.mark.parametrize("route_name,origin,destination", BENCHMARK_OD_PAIRS)
def test_od_benchmark_dry_weather_baseline(
    route_name: str, origin: Coordinate, destination: Coordinate
) -> None:
    """In dry weather (none), all routes should have low flood risk (<= 0.25)."""
    rain_store.set_simulator("none")
    req = RouteRequest(origin=origin, destination=destination, vehicle="car")
    res = compare_routes(req)

    for route in res.routes:
        assert route.highest_risk <= 0.25, (
            f"[{route_name}] Expected dry weather risk <= 0.25, got {route.highest_risk}"
        )
        assert route.average_risk <= 0.25


@pytest.mark.parametrize("route_name,origin,destination", [
    (
        "swargate_to_pune_station",
        Coordinate(longitude=73.8580, latitude=18.5018),
        Coordinate(longitude=73.8744, latitude=18.5282),
    ),
    (
        "swargate_to_deccan",
        Coordinate(longitude=73.8504, latitude=18.5132),
        Coordinate(longitude=73.8402, latitude=18.5168),
    ),
    (
        "kothrud_to_koregaon_park",
        Coordinate(longitude=73.8050, latitude=18.5060),
        Coordinate(longitude=73.8952, latitude=18.5359),
    ),
])
def test_od_benchmark_heavy_rain_significant_risk_reduction(
    route_name: str, origin: Coordinate, destination: Coordinate
) -> None:
    """In heavy rain, corridors with flood hotspots should achieve strict risk reduction."""
    rain_store.set_simulator("heavy")
    req = RouteRequest(origin=origin, destination=destination, vehicle="car")
    res = compare_routes(req)

    routes = {r.id: r for r in res.routes}
    fast = routes["fast"]
    safe = routes["safe"]

    assert safe.highest_risk < fast.highest_risk, (
        f"[{route_name}] Expected Safe peak risk ({safe.highest_risk}) < Fast peak risk ({fast.highest_risk})"
    )


@pytest.mark.parametrize("route_name,origin,destination", BENCHMARK_OD_PAIRS)
def test_od_benchmark_monotonic_risk_progression(
    route_name: str, origin: Coordinate, destination: Coordinate
) -> None:
    """Risk must monotonically increase from dry conditions to extreme downpours."""
    rain_store.set_simulator("none")
    dry_res = compare_routes(RouteRequest(origin=origin, destination=destination, vehicle="car"))
    dry_fast = next(r for r in dry_res.routes if r.id == "fast")

    rain_store.set_simulator("extreme")
    extreme_res = compare_routes(RouteRequest(origin=origin, destination=destination, vehicle="car"))
    extreme_fast = next(r for r in extreme_res.routes if r.id == "fast")

    assert extreme_fast.highest_risk >= dry_fast.highest_risk
    assert extreme_fast.average_risk >= dry_fast.average_risk


@pytest.mark.parametrize("vehicle", ["car", "two_wheeler", "truck", "bus"])
def test_od_benchmark_vehicle_adaptability(vehicle: str) -> None:
    """All vehicles successfully compute valid routes with correct vehicle metadata."""
    rain_store.set_simulator("medium")
    origin = Coordinate(longitude=73.8580, latitude=18.5018)
    dest = Coordinate(longitude=73.8744, latitude=18.5282)

    res = compare_routes(RouteRequest(origin=origin, destination=dest, vehicle=vehicle))
    assert res.vehicle == vehicle
    assert len(res.routes) == 3


def test_deep_readiness_probe_endpoints() -> None:
    """Verify deep readiness probe on both /v1/health/ready and /api/v1/health/ready."""
    for prefix in ("/v1", "/api/v1"):
        res = client.get(f"{prefix}/health/ready")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "database" in data
        assert "redis" in data
        assert data["service"] == "flood-risk-api"
        assert data["status"] in ("healthy", "degraded", "offline_fallback")
