"""Database connectivity and health check caching.

Provides a cached connectivity check so services do not hang on connection
timeouts when running without PostgreSQL (e.g. unit tests or demo mode).
"""

from __future__ import annotations

import time
import psycopg

from app.core.config import get_settings

_db_status = {"reachable": False, "last_checked": 0.0}


def is_db_available() -> bool:
    """Check if PostgreSQL is reachable, caching result for 30s to prevent timeout stalls."""
    now = time.monotonic()
    if now - _db_status["last_checked"] < 30.0:
        return _db_status["reachable"]

    _db_status["last_checked"] = now
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=1) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                _db_status["reachable"] = True
                return True
    except Exception:
        _db_status["reachable"] = False
        return False


def reset_db_status_cache() -> None:
    """Force re-checking database availability on next call."""
    _db_status["last_checked"] = 0.0
