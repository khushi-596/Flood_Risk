"""Resilient Redis cache and Pub/Sub manager with seamless offline fallback.

Provides:
- Distributed caching for segment risk GeoJSON and Dijkstra routing computations
- Shared simulation override state across worker processes
- Redis Pub/Sub for real-time WebSocket alert broadcasting
- Non-blocking availability check with sub-second offline detection and in-memory fallback
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Cached availability state
_redis_status = {"available": False, "last_checked": 0.0, "client": None}
_in_memory_cache: dict[str, tuple[float, str]] = {}
_local_subscribers: set[asyncio.Queue] = set()


def is_redis_available() -> bool:
    """Check if Redis server is reachable with a 15-second TTL status cache."""
    now = time.monotonic()
    if now - _redis_status["last_checked"] < 15.0:
        return bool(_redis_status["available"])

    _redis_status["last_checked"] = now
    try:
        import redis

        client = redis.Redis.from_url(
            get_settings().redis_url,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            decode_responses=True,
        )
        if client.ping():
            _redis_status["available"] = True
            _redis_status["client"] = client
            return True
    except Exception:
        pass

    _redis_status["available"] = False
    _redis_status["client"] = None
    return False


def get_sync_client():
    if is_redis_available():
        return _redis_status["client"]
    return None


def cache_get_json(key: str) -> Any | None:
    """Retrieve JSON value from Redis or local in-memory fallback."""
    if is_redis_available():
        try:
            client = get_sync_client()
            if client:
                val = client.get(key)
                if val:
                    return json.loads(val)
        except Exception as exc:
            logger.debug(f"Redis get failed for {key}: {exc}")

    # Fallback to in-memory cache
    now = time.monotonic()
    if key in _in_memory_cache:
        expire_at, data_str = _in_memory_cache[key]
        if now < expire_at:
            return json.loads(data_str)
        else:
            del _in_memory_cache[key]
    return None


def cache_set_json(key: str, value: Any, ttl_sec: int = 60) -> None:
    """Store JSON value in Redis or in-memory fallback with TTL."""
    payload = json.dumps(value)
    if is_redis_available():
        try:
            client = get_sync_client()
            if client:
                client.set(key, payload, ex=ttl_sec)
                return
        except Exception as exc:
            logger.debug(f"Redis set failed for {key}: {exc}")

    # Fallback
    expire_at = time.monotonic() + ttl_sec
    _in_memory_cache[key] = (expire_at, payload)


def cache_delete_pattern(pattern: str) -> None:
    """Invalidate all keys matching a pattern."""
    if is_redis_available():
        try:
            client = get_sync_client()
            if client:
                keys = client.keys(pattern)
                if keys:
                    client.delete(*keys)
        except Exception as exc:
            logger.debug(f"Redis delete_pattern failed for {pattern}: {exc}")

    # In-memory wildcard purge
    prefix = pattern.replace("*", "")
    to_delete = [k for k in _in_memory_cache if k.startswith(prefix)]
    for k in to_delete:
        _in_memory_cache.pop(k, None)


async def publish_alert_event(channel: str, message: dict[str, Any]) -> None:
    """Publish an alert message via Redis Pub/Sub or local queue fallback."""
    payload = json.dumps(message)
    published = False

    if is_redis_available():
        try:
            client = get_sync_client()
            if client:
                client.publish(channel, payload)
                published = True
        except Exception as exc:
            logger.debug(f"Redis publish failed: {exc}")

    # Also notify any local WebSocket subscriber queues
    for q in list(_local_subscribers):
        try:
            q.put_nowait(message)
        except Exception:
            pass


def register_local_subscriber(queue: asyncio.Queue) -> None:
    _local_subscribers.add(queue)


def unregister_local_subscriber(queue: asyncio.Queue) -> None:
    _local_subscribers.discard(queue)
