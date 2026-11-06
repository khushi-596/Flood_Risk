"""WebSocket notifications when a segment enters high or severe risk."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket

from app.services.reports import verified_report_counts
from app.services.segments import scored_segments
from app.services.weather import rain_store

RISK_RANK = {"low": 0, "moderate": 1, "high": 2, "severe": 3}


class AlertHub:
    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()
        self.previous_bands: dict[str, str] = {}

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
                await self.broadcast(
                    {
                        "type": "risk_alert",
                        "segment_id": segment_id,
                        "road_name": props["name"],
                        "risk_band": band,
                        "risk_score": props["risk_score"],
                        "message": f"{props['name']} has entered {band} flood-risk conditions.",
                    }
                )

    async def monitor(self) -> None:
        while True:
            try:
                await self.check_for_transitions()
            except Exception:
                # A live-alert failure must never take down map, routing, or report requests.
                pass
            await asyncio.sleep(15)


alert_hub = AlertHub()
