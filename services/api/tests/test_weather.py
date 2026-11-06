from fastapi.testclient import TestClient

from app.main import app
from app.services.weather import rain_store

client = TestClient(app)


def test_weather_endpoints_and_aliases() -> None:
    res1 = client.get("/v1/rain")
    res2 = client.get("/v1/rainfall")
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["level"] == res2.json()["level"]


def test_custom_rainfall_simulation() -> None:
    # Set custom rainfall value
    res = client.post("/v1/rain/simulate", json={"rainfall_mm_hour": 38.5, "forecast_30m_mm_hour": 52.0})
    assert res.status_code == 200
    data = res.json()
    assert data["rainfall_mm_hour"] == 38.5
    assert data["forecast_30m_mm_hour"] == 52.0
    assert data["level"] == "extreme"

    # Reset
    client.post("/v1/rain/simulate", json={"level": "none"})


def test_storm_playback_lifecycle() -> None:
    # Fetch 3-hour storm playback sequence
    res = client.get("/v1/rain/playback")
    assert res.status_code == 200
    playback = res.json()
    assert "Pune Monsoon Cloudburst" in playback["storm_name"]
    assert len(playback["steps"]) >= 10

    # Step 0 is dry baseline (0 mm/h)
    step0_res = client.post("/v1/rain/playback/0")
    assert step0_res.status_code == 200
    assert step0_res.json()["rainfall_mm_hour"] == 0.0

    # Step 5 is peak storm (60 mm/h)
    step5_res = client.post("/v1/rain/playback/5")
    assert step5_res.status_code == 200
    assert step5_res.json()["rainfall_mm_hour"] == 60.0
    assert step5_res.json()["level"] == "extreme"

    # Travel advice should advise avoid during peak
    advice = client.get("/v1/travel-advice?vehicle=car").json()
    assert advice["verdict"] in ("wait", "avoid")

    # Step 12 is post-storm clear (0 mm/h)
    step12_res = client.post("/v1/rain/playback/12")
    assert step12_res.status_code == 200
    assert step12_res.json()["rainfall_mm_hour"] == 0.0

    # Reset
    client.post("/v1/rain/simulate", json={"level": "none"})


def test_get_travel_advice_endpoint() -> None:
    res = client.get("/v1/travel-advice?vehicle=two_wheeler")
    assert res.status_code == 200
    data = res.json()
    assert data["verdict"] in ("go", "caution", "wait", "avoid")
    assert data["trend"] in ("rising", "falling", "stable")
    assert len(data["reasons"]) >= 2
