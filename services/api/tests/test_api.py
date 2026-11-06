from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_demo_map_returns_risk_segments() -> None:
    response = client.get("/v1/map/segments")
    payload = response.json()
    assert response.status_code == 200
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) >= 5
    assert {item["properties"]["risk_band"] for item in payload["features"]} >= {"low", "high"}


def test_known_segment_is_returned() -> None:
    response = client.get("/v1/segments/pune-demo-003")
    assert response.status_code == 200
    assert response.json()["properties"]["name"] == "Pune Station Underpass"
