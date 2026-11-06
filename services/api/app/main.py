import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.services.alerts import alert_hub
from app.services.weather import rain_store, weather_poller_task


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Keep live rainfall best-effort and emit risk-band transitions without blocking requests."""
    await rain_store.refresh_from_open_meteo()
    alert_task = asyncio.create_task(alert_hub.monitor())
    weather_task = asyncio.create_task(weather_poller_task())
    try:
        yield
    finally:
        alert_task.cancel()
        weather_task.cancel()
        with suppress(asyncio.CancelledError):
            await alert_task
            await weather_task



settings = get_settings()
app = FastAPI(
    title="Flood-Aware Route & Road Risk API",
    version="0.1.0",
    description=(
        "Day 1 API: Pune demo risk segments and nearest-road crowd reports. "
        "The risk model is explainable and versioned in the repository."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/v1")


@app.websocket("/v1/ws/alerts")
@app.websocket("/ws/alerts")
async def risk_alerts(websocket: WebSocket) -> None:
    await alert_hub.connect(websocket)
    try:
        while True:
            # The client need not poll; this read only keeps the connection alive.
            await websocket.receive_text()
    except WebSocketDisconnect:
        alert_hub.disconnect(websocket)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {"service": "flood-risk-api", "docs": "/docs", "api_prefix": "/v1"}
