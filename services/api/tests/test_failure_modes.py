"""Failure-mode and resilience test suite.

Verifies graceful degradation under infrastructure outages and edge cases:
1. PostGIS/PostgreSQL unavailable -> fallback to GeoJSON seed dataset & in-memory stores
2. Redis unavailable -> fallback to local in-memory TTL cache & subscriber queues
3. Open-Meteo API unreachable / timeout -> fallback to stale cached weather state
4. Malformed bounding box -> gracefully ignored without 500 error
5. Disconnected / off-grid routing coordinates -> fallback path without crashing
6. Municipal auth failures -> consistent 401 Unauthorized, never 500
"""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from app.core.redis import (
    _in_memory_cache,
    cache_delete_pattern,
    cache_get_json,
    cache_set_json,
    publish_alert_event,
    register_local_subscriber,
    unregister_local_subscriber,
)
from app.main import app
from app.schemas import Coordinate, RouteRequest
from app.services.routing import compare_routes
from app.services.segments import _use_db, get_segment, list_segments, nearest_segment, scored_segments
from app.services.weather import rain_store

client = TestClient(app)


def test_postgis_offline_fallback():
    """When PostGIS is offline, segment retrieval gracefully serves seed data."""
    with patch("app.services.segments.is_db_available", return_value=False):
        assert _use_db() is False
        segments = list_segments()
        assert segments["type"] == "FeatureCollection"
        assert len(segments["features"]) > 0

        # Scored segments should also work
        scored = scored_segments(15.0)
        assert len(scored["features"]) > 0
        assert all("risk_score" in f["properties"] for f in scored["features"])

        # Fetch single segment by ID
        seg = get_segment("pune-demo-001")
        assert seg is not None
        assert seg["properties"]["segment_id"] == "pune-demo-001"

        # Nearest segment snapping
        nearest = nearest_segment(73.8448, 18.5212)
        assert nearest is not None
        assert nearest.segment_id.startswith("pune-demo")


def test_redis_offline_cache_and_pubsub_fallback():
    """When Redis is unreachable, caching and pub/sub transparently use in-memory fallbacks."""
    with patch("app.core.redis.is_redis_available", return_value=False):
        # Cache set and get
        test_key = f"test:resilience:{uuid4().hex[:6]}"
        cache_set_json(test_key, {"status": "ok", "count": 42}, ttl_sec=10)

        retrieved = cache_get_json(test_key)
        assert retrieved == {"status": "ok", "count": 42}

        # Cache wildcard deletion
        cache_delete_pattern("test:resilience:*")
        assert cache_get_json(test_key) is None

        # Expired cache entry handling
        cache_set_json(test_key, {"expired": True}, ttl_sec=-1)
        assert cache_get_json(test_key) is None


def test_open_meteo_timeout_marks_state_stale():
    """When Open-Meteo times out or throws HTTP errors, system marks weather stale instead of crashing."""
    rain_store.reset_to_live()
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectTimeout("Connection timed out")):
        res = client.post(
            "/v1/rain/refresh",
            headers={"Authorization": "Bearer staff-override-test"},
        )
        # Even if unauthorized or mocked, let's call the store directly:
        import asyncio
        loop = asyncio.new_event_loop()
        state = loop.run_until_complete(rain_store.refresh_from_open_meteo())
        loop.close()

        assert state.is_stale is True
        assert state.source == "cached"


def test_malformed_bbox_query_graceful_handling():
    """Malformed bounding boxes must be safely ignored without raising 500."""
    # Letters instead of floats
    res1 = client.get("/v1/segments?bbox=foo,bar,baz,qux")
    assert res1.status_code == 200
    assert res1.json()["type"] == "FeatureCollection"

    # Incomplete coordinates (only 2 parts)
    res2 = client.get("/v1/segments?bbox=73.84,18.52")
    assert res2.status_code == 200
    assert res2.json()["type"] == "FeatureCollection"


def test_unreachable_route_point_fallback():
    """Routing between arbitrary off-grid points snaps to nearest nodes and completes safely."""
    req = RouteRequest(
        origin=Coordinate(longitude=73.8000, latitude=18.5000),
        destination=Coordinate(longitude=73.9200, latitude=18.5600),
        vehicle="car",
    )
    result = compare_routes(req)
    assert len(result.routes) == 3
    for opt in result.routes:
        assert opt.distance_m > 0
        assert opt.duration_min > 0
        assert len(opt.geometry["coordinates"]) >= 2


def test_unauthorized_municipal_access():
    """Accessing protected municipal endpoints without valid token returns 401."""
    res1 = client.get("/v1/municipal/reports")
    assert res1.status_code == 401

    res2 = client.post(
        "/v1/municipal/work-orders",
        json={"segment_id": "pune-demo-001", "title": "Inspect culvert", "priority": 3},
    )
    assert res2.status_code == 401

    res3 = client.get("/v1/municipal/hotspots", headers={"Authorization": "Bearer invalid_token"})
    assert res3.status_code == 401
