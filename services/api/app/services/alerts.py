"""WebSocket notifications when a segment enters high or severe risk.

Alert delivery architecture:
- check_for_transitions() detects risk-band escalations and calls publish_alert_event()
- publish_alert_event() (core/redis.py) publishes to Redis Pub/Sub channel AND
  puts the message directly into every registered local asyncio.Queue
- _redis_subscriber() subscribes to the Redis channel and re-broadcasts messages
  that arrive from other worker processes (cross-process fan-out)
- When Redis is offline, local queues alone provide in-process delivery
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

from app.core.redis import (
    is_redis_available,
    publish_alert_event,
    register_local_subscriber,
    unregister_local_subscriber,
)
from app.services.reports import verified_report_counts
from app.services.segments import scored_segments
from app.services.weather import rain_store

logger = logging.getLogger(__name__)

RISK_RANK = {"low": 0, "moderate": 1, "high": 2, "severe": 3}
ALERT_CHANNEL = "flood:risk:alerts"


class AlertHub:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()
        self.previous_bands: dict[str, str] = {}
        self._local_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        register_local_subscriber(self._local_queue)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections.add(websocket)
        await websocket.send_json({"type": "connected", "message": "Flood-risk alerts connected."})

    def disconnect(self, websocket: WebSocket) -> None:
        self.connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for socket in list(self.connections):
            try:
                await socket.send_json(message)
            except Exception:
                self.disconnect(socket)

    async def check_for_transitions(self) -> None:
        rain = rain_store.response()
        collection = scored_segments(rain.rainfall_mm_hour, verified_report_counts())
        for feature in collection["features"]:
            props = feature["properties"]
            segment_id, band = props["segment_id"], props["risk_band"]
            previous = self.previous_bands.get(segment_id, band)
            self.previous_bands[segment_id] = band
            if RISK_RANK[band] >= 2 and RISK_RANK[band] > RISK_RANK[previous]:
                alert = {
                    "type": "risk_alert",
                    "segment_id": segment_id,
                    "road_name": props["name"],
                    "risk_band": band,
                    "risk_score": props["risk_score"],
                    "message": f"{props['name']} has entered {band} flood-risk conditions.",
                }
                # Publish to Redis Pub/Sub (and local queue fallback) so all workers broadcast
                await publish_alert_event(ALERT_CHANNEL, alert)

    async def _redis_subscriber(self) -> None:
        """Subscribe to the Redis Pub/Sub alert channel and fan-out to local WebSocket clients.

        This coroutine handles messages published by OTHER worker processes.
        Messages from THIS process arrive via the local queue registered in __init__.
        """
        while True:
            if not is_redis_available():
                await asyncio.sleep(5)
                continue
            try:
                import redis.asyncio as aioredis  # type: ignore[import-untyped]
                from app.core.config import get_settings

                async with aioredis.from_url(
                    get_settings().redis_url,
                    socket_connect_timeout=0.5,
                    socket_timeout=0.5,
                    decode_responses=True,
                ) as client:
                    pubsub = client.pubsub()
                    await pubsub.subscribe(ALERT_CHANNEL)
                    async for raw in pubsub.listen():
                        if raw["type"] != "message":
                            continue
                        try:
                            msg = json.loads(raw["data"])
                            await self.broadcast(msg)
                        except Exception:
                            pass
            except Exception as exc:
                logger.debug("Redis subscriber error: %s — retrying in 5 s", exc)
                await asyncio.sleep(5)

    async def _local_queue_drainer(self) -> None:
        """Drain the local alert queue and broadcast to WebSocket clients.

        This handles messages from THIS process regardless of Redis availability.
        """
        while True:
            try:
                msg = await asyncio.wait_for(self._local_queue.get(), timeout=1.0)
                await self.broadcast(msg)
            except asyncio.TimeoutError:
                pass
            except Exception as exc:
                logger.debug("Local queue drainer error: %s", exc)

    async def monitor(self) -> None:
        """Main background task: poll segments, subscribe to Redis, and drain local queue."""
        asyncio.ensure_future(self._local_queue_drainer())
        asyncio.ensure_future(self._redis_subscriber())
        while True:
            try:
                await self.check_for_transitions()
            except Exception:
                # A live-alert failure must never take down map, routing, or report requests.
                pass
            await asyncio.sleep(15)


alert_hub = AlertHub()
