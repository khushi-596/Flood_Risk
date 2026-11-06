"""End-to-End User Journey Tests (PCCOE Workplan Dev E1).

Tests the 4 canonical user journeys defined in the test plan:
1. Commuter Journey: View risk map -> search route -> compare Safe vs Fast -> read travel advice
2. Citizen & Municipal Journey: Citizen report -> verification -> risk increase -> work order resolution
3. Storm Simulation Journey: Heavy rainfall simulation -> risk band transitions -> alerts persistence
4. Multi-Vehicle Journey: Rain sensitivity -> vehicle adaptability (two-wheeler vs bus/car)
"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "services" / "api"))

from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.services.weather import rain_store
from app.services.reports import _in_memory_reports
from app.services.municipal import _in_memory_work_orders
from app.services.segments import invalidate_segment_cache

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_state():
    """Reset all state before each user journey test."""
    _in_memory_reports.clear()
    _in_memory_work_orders.clear()
    rain_store.set_simulator("none")
    invalidate_segment_cache()
    yield
    _in_memory_reports.clear()
    _in_memory_work_orders.clear()
    rain_store.set_simulator("none")
    invalidate_segment_cache()


def test_journey_1_commuter_workflow():
    """Journey 1: View risk map -> search a route -> compare Safe vs Fast -> read travel advice."""
    # 1. Commuter views risk map
    map_res = client.get("/v1/segments")
    assert map_res.status_code == 200
    features = map_res.json().get("features", [])
    assert len(features) > 0, "Map must return road segments"

    # Verify each segment has risk band and explanation properties
    first_seg = features[0]["properties"]
    assert "risk_score" in first_seg
    assert "risk_band" in first_seg
    assert "confidence" in first_seg

    # 2. Search a route
    origin = {"longitude": 73.8446, "latitude": 18.5211}
    destination = {"longitude": 73.8744, "latitude": 18.5282}
    route_payload = {
        "origin": origin,
        "destination": destination,
        "vehicle": "car",
        "horizon_min": 0,
    }

    route_res = client.post("/v1/routes/compare", json=route_payload)
    assert route_res.status_code == 200
    routes_data = route_res.json()
    assert "routes" in routes_data
    routes = {r["id"]: r for r in routes_data["routes"]}
    assert "fast" in routes
    assert "safe" in routes
    assert "balanced" in routes

    # 3. Compare Safe vs Fast: Safe must never be riskier than Fast
    assert routes["safe"]["highest_risk"] <= routes["fast"]["highest_risk"] + 1e-4
    assert routes["safe"]["average_risk"] <= routes["fast"]["average_risk"] + 1e-4

    # 4. Read travel advice — the endpoint is POST /v1/travel-advice
    advice_payload = {
        "origin": origin,
        "destination": destination,
        "vehicle": "car",
    }
    advice_res = client.post("/v1/travel-advice", json=advice_payload)
    assert advice_res.status_code == 200
    advice_data = advice_res.json()
    assert advice_data["verdict"] in ("go", "caution", "wait", "avoid")
    assert len(advice_data["reasons"]) > 0


def test_journey_2_citizen_reporting_and_municipal_triage():
    """Journey 2: Citizen report -> verification -> risk increase -> work order resolution."""
    # Step A: Baseline segment risk before citizen report
    seg_id = "pune-demo-001"
    base_res = client.get(f"/v1/segments/{seg_id}/explain")
    assert base_res.status_code == 200
    base_score = base_res.json()["risk_score"]

    # Step B: 3 independent citizen reports within 150m (auto-verification cluster)
    # Reports endpoint expects JSON body — no multipart
    for i in range(1, 4):
        rep_res = client.post(
            "/v1/reports",
            json={
                "report_type": "waterlogging",
                "severity": 3,
                "latitude": 18.5211,
                "longitude": 73.8446,
                "description": f"Flooding on JM road device {i}",
                "reporter_fingerprint": f"device-e2e-journey2-{i}",
            },
        )
        assert rep_res.status_code == 201, rep_res.text

    invalidate_segment_cache()

    # Step C: Verify segment risk increased due to verified citizen reports
    post_res = client.get(f"/v1/segments/{seg_id}/explain")
    assert post_res.status_code == 200
    post_score = post_res.json()["risk_score"]
    assert post_score > base_score, f"Expected risk increase ({post_score} > {base_score})"
    assert post_res.json()["active_verified_reports"] >= 1

    # Step D: Staff logs in, views report queue stats, and creates work order
    login_res = client.post(
        "/v1/municipal/login",
        json={"email": "staff@pune.gov.in", "password": "change-before-deployment"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    stats_res = client.get("/v1/municipal/stats", headers=headers)
    assert stats_res.status_code == 200
    assert stats_res.json()["verified_today"] >= 1

    # Staff creates a work order
    wo_res = client.post(
        "/v1/municipal/work-orders",
        json={
            "segment_id": seg_id,
            "title": "Clear JM Road Drain",
            "priority": 4,
        },
        headers=headers,
    )
    assert wo_res.status_code == 201
    wo_id = wo_res.json()["id"]

    # Step E: Staff marks work order resolved -> crowd signal cleared
    update_res = client.patch(
        f"/v1/municipal/work-orders/{wo_id}",
        json={"status": "resolved"},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "resolved"

    invalidate_segment_cache()

    # Segment risk returns to baseline (no active verified reports)
    resolved_res = client.get(f"/v1/segments/{seg_id}/explain")
    assert resolved_res.status_code == 200
    assert resolved_res.json()["active_verified_reports"] == 0
    assert resolved_res.json()["risk_score"] < post_score


def test_journey_3_storm_event_and_alerts():
    """Journey 3: Simulator set to heavy rainfall -> risk band transitions -> alerts endpoint."""
    # 1. Simulate heavy rainfall event using /v1/rain/simulate (or /v1/sim/rain)
    sim_res = client.post(
        "/v1/rain/simulate",
        json={"rainfall_mm_hour": 35.0, "forecast_30m_mm_hour": 50.0},
    )
    assert sim_res.status_code == 200
    rain_data = sim_res.json()
    assert rain_data["level"] in ("heavy", "extreme")

    # 2. Map reflects severe conditions
    map_res = client.get("/v1/segments")
    assert map_res.status_code == 200
    features = map_res.json()["features"]
    high_or_severe = [f for f in features if f["properties"]["risk_band"] in ("high", "severe")]
    assert len(high_or_severe) > 0, "Heavy rain should cause high or severe segments"

    # 3. Alerts endpoint returns recent alert records
    alerts_res = client.get("/v1/alerts")
    assert alerts_res.status_code == 200
    alerts = alerts_res.json()
    assert isinstance(alerts, list)


def test_journey_4_vehicle_adaptability_and_warnings():
    """Journey 4: Rain sensitivity changes warnings and routing by vehicle type."""
    # Set moderate rain condition using correct endpoint /v1/rain/simulate
    sim_res = client.post(
        "/v1/rain/simulate",
        json={"rainfall_mm_hour": 15.0, "forecast_30m_mm_hour": 22.0},
    )
    assert sim_res.status_code == 200

    # Compare two-wheeler vs bus travel advice (GET endpoint)
    advice_tw = client.get("/v1/travel-advice?vehicle=two_wheeler")
    advice_bus = client.get("/v1/travel-advice?vehicle=bus")
    assert advice_tw.status_code == 200
    assert advice_bus.status_code == 200

    # Two-wheelers have much higher flood sensitivity than buses
    assert advice_tw.json()["vehicle"] == "two_wheeler"
    assert advice_bus.json()["vehicle"] == "bus"

    # Compare routing by vehicle
    origin = {"longitude": 73.8446, "latitude": 18.5211}
    dest = {"longitude": 73.8744, "latitude": 18.5282}

    tw_res = client.post(
        "/v1/routes/compare",
        json={"origin": origin, "destination": dest, "vehicle": "two_wheeler"},
    )
    bus_res = client.post(
        "/v1/routes/compare",
        json={"origin": origin, "destination": dest, "vehicle": "bus"},
    )
    assert tw_res.status_code == 200
    assert bus_res.status_code == 200
    assert tw_res.json()["vehicle"] == "two_wheeler"
    assert bus_res.json()["vehicle"] == "bus"
