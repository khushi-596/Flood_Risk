from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check() -> None:
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_demo_map_returns_risk_segments() -> None:
    # On a dry day with 0 mm/h, all segments are guarded by dry-gate cap at <= 0.25 (low)
    response = client.get("/v1/map/segments")
    payload = response.json()
    assert response.status_code == 200
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) >= 5
    for item in payload["features"]:
        assert item["properties"]["risk_band"] == "low"
        assert item["properties"]["risk_score"] <= 0.25

    # Under simulated heavy rain, vulnerable segments should transition to high/severe
    client.post("/v1/rain/simulate", json={"level": "heavy"})
    wet_response = client.get("/v1/map/segments")
    wet_payload = wet_response.json()
    wet_bands = {item["properties"]["risk_band"] for item in wet_payload["features"]}
    assert "high" in wet_bands or "severe" in wet_bands

    # Reset simulator back to none
    client.post("/v1/rain/simulate", json={"level": "none"})


def test_known_segment_is_returned() -> None:
    response = client.get("/v1/segments/pune-demo-003")
    assert response.status_code == 200
    assert response.json()["properties"]["name"] == "Pune Station Underpass"


def test_segment_explanation_and_aliases() -> None:
    response = client.get("/v1/segments/pune-demo-003/explain")
    assert response.status_code == 200
    data = response.json()
    assert data["segment_id"] == "pune-demo-003"
    assert "weighted_contributions" in data
    assert "reasons" in data

