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


def test_multipoint_grid_and_location_lookup() -> None:
    """Verify multi-point spatial weather grid stations and nearest location lookups."""
    # Set simulated rain
    rain_store.set_custom(rainfall_mm_hour=25.0, forecast_30m=35.0)

    # Grid readings dictionary
    readings = rain_store.get_grid_readings()
    assert len(readings) == 5
    assert "central" in readings
    assert "swargate" in readings
    assert "shivajinagar" in readings
    assert "koregaon_park" in readings
    assert "station" in readings

    # Swargate coordinate lookup
    rain_swargate = rain_store.get_rainfall_for_location(18.5080, 73.8500)
    assert rain_swargate == 25.0

    forecast_swargate = rain_store.get_rainfall_for_location(18.5080, 73.8500, use_forecast=True)
    assert forecast_swargate == 35.0

    # Reset
    rain_store.set_simulator("none")


def test_segment_risk_persistence_snapshot() -> None:
    """Verify segment risk snapshot computation and in-memory persistence."""
    from app.services.segments import _in_memory_segment_risk, persist_segment_risk_snapshot

    # Take snapshot
    count = persist_segment_risk_snapshot()
    assert count > 0
    assert len(_in_memory_segment_risk) == count

    # Validate snapshot structure
    sample_key = next(iter(_in_memory_segment_risk))
    sample = _in_memory_segment_risk[sample_key]
    assert "seg_id" in sample
    assert "risk_now" in sample
    assert "risk_30" in sample
    assert "risk_band" in sample
    assert "confidence" in sample
    assert "factors" in sample
    assert "updated_at" in sample


def test_weather_history_and_grid_endpoints() -> None:
    """Verify weather history and spatial grid API endpoints."""
    # Test grid endpoint
    res_grid = client.get("/v1/weather/grid")
    assert res_grid.status_code == 200
    grid = res_grid.json()
    assert "central" in grid
    assert "swargate" in grid

    # Test history endpoint
    res_hist = client.get("/v1/weather/history?limit=10")
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert isinstance(history, list)
    assert len(history) >= 1
    obs = history[0]
    assert "observed_at" in obs
    assert "rainfall_mm_hour" in obs
    assert "forecast_30m_mm_hour" in obs
    assert "source" in obs


def test_persisted_segment_risk_endpoint() -> None:
    """Verify retrieval of persisted segment risk scores."""
    from app.services.segments import persist_segment_risk_snapshot
    persist_segment_risk_snapshot()

    # Query all
    res = client.get("/v1/segments/risk/current")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    assert len(items) > 0

    first_id = items[0]["seg_id"]
    res_single = client.get(f"/v1/segments/risk/current?segment_id={first_id}")
    assert res_single.status_code == 200
    single = res_single.json()
    assert single["seg_id"] == first_id
    assert "risk_now" in single
    assert "risk_30" in single

