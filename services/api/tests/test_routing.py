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


def test_extreme_rain_does_not_lower_travel_risk() -> None:
    rain_store.set_simulator("light")
    light = travel_advice(TravelAdviceRequest(vehicle="two_wheeler"))
    rain_store.set_simulator("extreme")
    extreme = travel_advice(TravelAdviceRequest(vehicle="two_wheeler"))
    assert extreme.risk_now >= light.risk_now
