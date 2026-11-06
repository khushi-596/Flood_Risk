"""SlowAPI rate-limiter singleton.

A single Limiter instance is created here and re-used throughout the app.
Default limits are defined per-endpoint via the @limiter.limit() decorator.

Default key function: client IP address (extracted from X-Forwarded-For when
running behind a proxy, falls back to request.client.host).

Limits applied (per IP):
  Public read endpoints      (segments, rain, travel-advice)  → 120/minute
  Expensive compute (routes) → 30/minute
  Citizen report submission  → 20/minute
  Municipal writes           → 60/minute
  Rain simulation (staff)    → 30/minute

When Redis is available the limiter uses it as the backend storage so limits
are shared across multiple workers.  When Redis is offline it falls back
transparently to in-memory storage within the current process.
"""

from __future__ import annotations

import os

from slowapi import Limiter
from slowapi.util import get_remote_address


def _make_limiter() -> Limiter:
    """Build a SlowAPI Limiter, using Redis storage when available."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        # Attempt to use Redis as the shared rate-limit store
        import redis as _redis

        client = _redis.Redis.from_url(redis_url, socket_connect_timeout=0.5, socket_timeout=0.5)
        client.ping()
        storage_uri = redis_url
    except Exception:
        # Redis not available — use in-memory (single-process only)
        storage_uri = "memory://"

    return Limiter(
        key_func=get_remote_address,
        storage_uri=storage_uri,
        default_limits=["200/minute"],
        headers_enabled=False,
    )


limiter = _make_limiter()
