from app.schemas import Coordinate, RouteRequest, TravelAdviceRequest
from app.services.routing import compare_routes, travel_advice
from app.services.weather import rain_store


def test_safe_route_is_not_riskier_than_fast_route() -> None:
    rain_store.set_simulator("heavy")
    result = compare_routes(
        RouteRequest(
            origin=Coordinate(longitude=73.8446, latitude=18.5211),
            destination=Coordinate(longitude=73.8744, latitude=18.5282),
            vehicle="car",
        )
    )
    risks = {route.id: route.average_risk for route in result.routes}
    assert risks["safe"] <= risks["fast"]
    rain_store.set_simulator("none")


def test_dry_weather_all_routes_are_low_risk() -> None:
    rain_store.set_simulator("none")
    result = compare_routes(
        RouteRequest(
            origin=Coordinate(longitude=73.8446, latitude=18.5211),
            destination=Coordinate(longitude=73.8744, latitude=18.5282),
            vehicle="car",
        )
    )
    for route in result.routes:
        assert route.average_risk <= 0.25
        assert route.highest_risk <= 0.25
        assert len(route.geometry["coordinates"]) >= 2
        assert route.distance_m > 0
        assert route.duration_min > 0


def test_heavy_rain_safe_route_avoids_severe_underpass() -> None:
    rain_store.set_simulator("heavy")
    result = compare_routes(
        RouteRequest(
            origin=Coordinate(longitude=73.8556, latitude=18.5259),  # Shivajinagar
            destination=Coordinate(longitude=73.8744, latitude=18.5282),  # Pune Station
            vehicle="car",
        )
    )
    routes_by_id = {r.id: r for r in result.routes}
    fast = routes_by_id["fast"]
    safe = routes_by_id["safe"]

    # Fast route goes directly through the underpass hotspot (pune-demo-003)
    assert "pune-demo-003" in fast.segment_ids
    # Safe route detours and avoids the severe underpass
    assert "pune-demo-003" not in safe.segment_ids
    assert safe.highest_risk < fast.highest_risk
    rain_store.set_simulator("none")


def test_vehicle_profile_differences() -> None:
    rain_store.set_simulator("medium")
    two_wheeler = travel_advice(TravelAdviceRequest(vehicle="two_wheeler"))
    truck = travel_advice(TravelAdviceRequest(vehicle="truck"))

    # Two-wheelers have a lower tolerance and should receive a more restrictive or equal verdict
    severity_order = {"go": 0, "caution": 1, "wait": 2, "avoid": 3}
    assert severity_order[two_wheeler.verdict] >= severity_order[truck.verdict]
    rain_store.set_simulator("none")


def test_extreme_rain_does_not_lower_travel_risk() -> None:
    rain_store.set_simulator("light")
    light = travel_advice(TravelAdviceRequest(vehicle="two_wheeler"))
    rain_store.set_simulator("extreme")
    extreme = travel_advice(TravelAdviceRequest(vehicle="two_wheeler"))
    assert extreme.risk_now >= light.risk_now
    rain_store.set_simulator("none")

