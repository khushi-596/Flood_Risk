"""Tests for Part C: Rate Limiting, Structlog Structured Logging, and /api/v1 Prefix Alias."""

from fastapi.testclient import TestClient

from app.core.limiter import limiter
from app.core.logging import get_logger
from app.main import app

client = TestClient(app)


def test_api_v1_prefix_alias_health():
    """Verify that /api/v1 prefix functions identically to /v1."""
    res_v1 = client.get("/v1/health")
    assert res_v1.status_code == 200

    res_api_v1 = client.get("/api/v1/health")
    assert res_api_v1.status_code == 200
    assert res_api_v1.json() == res_v1.json()


def test_api_v1_prefix_alias_segments():
    """Verify that /api/v1/segments returns valid GeoJSON matching /v1/segments."""
    res_v1 = client.get("/v1/segments")
    res_api_v1 = client.get("/api/v1/segments")

    assert res_v1.status_code == 200
    assert res_api_v1.status_code == 200
    assert res_api_v1.json()["type"] == "FeatureCollection"
    assert len(res_api_v1.json()["features"]) == len(res_v1.json()["features"])


def test_api_v1_prefix_alias_rain():
    """Verify that /api/v1/rain returns identical rain state."""
    res_v1 = client.get("/v1/rain")
    res_api_v1 = client.get("/api/v1/rain")

    assert res_v1.status_code == 200
    assert res_api_v1.status_code == 200
    assert res_api_v1.json()["rainfall_mm_hour"] == res_v1.json()["rainfall_mm_hour"]


def test_root_endpoint_metadata():
    """Root / should report both primary (/v1) and alias (/api/v1) prefixes."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["primary_prefix"] == "/v1"
    assert data["alias_prefix"] == "/api/v1"


def test_structured_logger():
    """Test that structlog logger works without error."""
    logger = get_logger("test_part_c")
    # Should not raise exception
    logger.info("test_event", foo="bar", answer=42)


def test_rate_limiting_headers_or_behavior():
    """Verify rate limiter is wired and active on the app."""
    assert app.state.limiter is not None
    # Make request to /v1/health
    res = client.get("/v1/health")
    assert res.status_code == 200


def test_rate_limit_exceeded_returns_429():
    """Verify that exceeding rate limits returns 429 Too Many Requests."""
    try:
        # /municipal/login limit is 20/minute
        responses = [
            client.post("/v1/municipal/login", json={"email": "bad@email.com", "password": "wrong_password"})
            for _ in range(25)
        ]
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes
        idx = status_codes.index(429)
        assert "Rate limit exceeded" in responses[idx].json().get("error", "")
    finally:
        # Reset storage so other tests aren't blocked
        limiter.reset()
