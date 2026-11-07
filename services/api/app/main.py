"""FastAPI application factory for the Flood-Aware Route & Road Risk API.

Startup sequence (lifespan):
  1. configure_logging() — structlog JSON/console renderer
  2. rain_store.refresh_from_open_meteo() — prime live rainfall
  3. alert_hub.monitor() background task
  4. weather_poller_task() background task

Routing:
  /v1/...        — primary versioned prefix (existing)
  /api/v1/...    — alias prefix added in Part C for spec compliance

Rate limiting:
  SlowAPI middleware installed; per-endpoint limits applied in routes.py.
  429 responses are JSON with Retry-After header.
"""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.logging import configure_logging, get_logger
from app.services.alerts import alert_hub
from app.services.municipal import drainage_failure_detector_task
from app.services.segments import persist_segment_risk
from app.services.weather import rain_store, weather_poller_task

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Startup: configure logging, prime weather, launch background tasks."""
    settings = get_settings()
    configure_logging(settings.app_env)
    logger.info("flood_risk_api_starting", env=settings.app_env)

    with suppress(Exception):
        await asyncio.wait_for(rain_store.refresh_from_open_meteo(), timeout=2.5)
    alert_task = asyncio.create_task(alert_hub.monitor())
    weather_task = asyncio.create_task(weather_poller_task())
    risk_task = asyncio.create_task(persist_segment_risk())
    drain_task = asyncio.create_task(drainage_failure_detector_task())

    logger.info("flood_risk_api_ready")
    try:
        yield
    finally:
        alert_task.cancel()
        weather_task.cancel()
        risk_task.cancel()
        drain_task.cancel()
        with suppress(asyncio.CancelledError):
            await alert_task
            await weather_task
            await risk_task
            await drain_task
        logger.info("flood_risk_api_shutdown")


settings = get_settings()
app = FastAPI(
    title="Flood-Aware Route & Road Risk API",
    version="0.1.0",
    description=(
        "Pune flood-risk API: real-time segment scoring, risk-aware routing, "
        "crowd reports, municipal work-orders, and WebSocket alerts. "
        "The risk model is explainable and versioned in the repository."
    ),
    lifespan=lifespan,
)

# ── Rate limiting ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ───────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=r"^https://.*\.onrender\.com$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
# Primary versioned prefix
app.include_router(api_router, prefix="/v1")
# /api/v1/... alias — spec-compliant second mount (Part C requirement)
app.include_router(api_router, prefix="/api/v1", include_in_schema=False)


# ── WebSocket ─────────────────────────────────────────────────────────────────
@app.websocket("/v1/ws/alerts")
@app.websocket("/api/v1/ws/alerts")
@app.websocket("/ws/alerts")
async def risk_alerts(websocket: WebSocket) -> None:
    await alert_hub.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        alert_hub.disconnect(websocket)



# ── Root ──────────────────────────────────────────────────────────────────────
@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    return {
        "service": "flood-risk-api",
        "docs": "/docs",
        "primary_prefix": "/v1",
        "alias_prefix": "/api/v1",
    }
