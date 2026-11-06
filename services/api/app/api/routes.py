import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile, status

from app.core.limiter import limiter
from app.core.logging import get_logger
from app.schemas import (
    CrowdReportCreate,
    CrowdReportReceipt,
    CrowdReportSummary,
    LoginRequest,
    RainSimulationRequest,
    RainStateResponse,
    ReportReviewRequest,
    RouteRequest,
    RouteResponse,
    TokenResponse,
    TravelAdviceRequest,
    TravelAdviceResponse,
    WorkOrderCreate,
    WorkOrderResponse,
    WorkOrderUpdate,
)
from app.services.auth import login, require_staff
from app.services.municipal import create_work_order, drain_failure_flags, hotspots, list_work_orders, update_work_order
from app.services.reports import create_report, list_reports, review_report, save_report_photo, verified_report_counts
from app.services.risk_engine import weighted_contributions
from app.services.routing import compare_routes, travel_advice
from app.services.segments import nearest_segment, scored_segments
from app.services.weather import rain_store

logger = get_logger(__name__)
router = APIRouter()


def _parse_bbox(bbox_str: str | None) -> tuple[float, float, float, float] | None:
    if not bbox_str:
        return None
    try:
        parts = [float(p.strip()) for p in bbox_str.split(",")]
        if len(parts) == 4:
            return (parts[0], parts[1], parts[2], parts[3])
    except (ValueError, IndexError):
        pass
    return None


def _current_segments(
    bbox: tuple[float, float, float, float] | None = None,
    horizon_min: int = 0,
) -> dict:
    rain = rain_store.response()
    rain_val = rain.forecast_30m_mm_hour if horizon_min >= 30 else rain.rainfall_mm_hour
    return scored_segments(rain_val, verified_report_counts(), bbox=bbox)


def _segment_or_404(segment_id: str) -> dict:
    for feature in _current_segments()["features"]:
        if feature["properties"]["segment_id"] == segment_id:
            return feature
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")


@router.get("/health", tags=["health"])
@limiter.limit("120/minute")
def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "stage": "day-3", "service": "flood-risk-api"}


@router.get("/map/segments", tags=["map"])
@router.get("/segments", tags=["map"])
@limiter.limit("120/minute")
def map_segments(
    request: Request,
    bbox: str | None = Query(default=None, description="min_lon,min_lat,max_lon,max_lat"),
    horizon_min: int = Query(default=0, ge=0, le=60, description="Forecast horizon in minutes (0 or 30)"),
) -> dict:
    """Return current risk-scored GeoJSON. Rain, horizon, and verified reports alter the scores."""
    bbox_parsed = _parse_bbox(bbox)
    return _current_segments(bbox=bbox_parsed, horizon_min=horizon_min)


@router.get("/segments/{segment_id}", tags=["map"])
@limiter.limit("120/minute")
def segment_detail(request: Request, segment_id: str) -> dict:
    return _segment_or_404(segment_id)


@router.get("/segments/{segment_id}/explanation", tags=["map"])
@router.get("/segments/{segment_id}/explain", tags=["map"])
@limiter.limit("120/minute")
def segment_explanation(request: Request, segment_id: str) -> dict:
    feature = _segment_or_404(segment_id)
    props = feature["properties"]
    return {
        "segment_id": segment_id,
        "name": props["name"],
        "risk_score": props["risk_score"],
        "confidence": props["confidence"],
        "risk_band": props["risk_band"],
        "signals": props["signals"],
        "weighted_contributions": weighted_contributions(props["signals"]),
        "reasons": props["reasons"],
        "active_verified_reports": props["active_verified_reports"],
    }


@router.get("/rain", response_model=RainStateResponse, tags=["rain"])
@router.get("/rainfall", response_model=RainStateResponse, tags=["rain"])
@limiter.limit("120/minute")
def rain_state(request: Request) -> RainStateResponse:
    return rain_store.response()


@router.post("/rain/simulate", response_model=RainStateResponse, tags=["rain"])
@router.post("/sim/rain", response_model=RainStateResponse, tags=["rain"])
@limiter.limit("30/minute")
def set_rain_simulator(request: Request, payload: RainSimulationRequest) -> RainStateResponse:
    logger.info("rain_simulator_invoked", level=payload.level, mm_hour=payload.rainfall_mm_hour)
    if payload.rainfall_mm_hour is not None:
        return rain_store.set_custom(payload.rainfall_mm_hour, payload.forecast_30m_mm_hour)
    if payload.level is not None:
        return rain_store.set_simulator(payload.level)
    return rain_store.set_simulator("none")


@router.get("/rain/playback", tags=["rain"])
@limiter.limit("60/minute")
def get_storm_playback(request: Request):
    return rain_store.get_playback_series()


@router.post("/rain/playback/{step_index}", response_model=RainStateResponse, tags=["rain"])
@limiter.limit("30/minute")
def set_storm_playback_step(request: Request, step_index: int) -> RainStateResponse:
    try:
        return rain_store.set_playback_step(step_index)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/rain/refresh", response_model=RainStateResponse, tags=["rain"])
@limiter.limit("10/minute")
async def refresh_live_rain(request: Request, _: str = Depends(require_staff)) -> RainStateResponse:
    return await rain_store.refresh_from_open_meteo()


@router.post("/routes/compare", response_model=RouteResponse, tags=["routing"])
@router.post("/route", response_model=RouteResponse, tags=["routing"])
@limiter.limit("30/minute")
def route_comparison(request: Request, payload: RouteRequest) -> RouteResponse:
    logger.info("route_compared", vehicle=payload.vehicle)
    return compare_routes(payload)


@router.post("/travel-advice", response_model=TravelAdviceResponse, tags=["routing"])
@limiter.limit("60/minute")
def should_i_travel(request: Request, payload: TravelAdviceRequest) -> TravelAdviceResponse:
    return travel_advice(payload)


@router.get("/travel-advice", response_model=TravelAdviceResponse, tags=["routing"])
@limiter.limit("60/minute")
def get_travel_advice(request: Request, vehicle: str = "car") -> TravelAdviceResponse:
    return travel_advice(TravelAdviceRequest(vehicle=vehicle))  # type: ignore[arg-type]


@router.post(
    "/reports",
    response_model=CrowdReportReceipt,
    status_code=status.HTTP_201_CREATED,
    tags=["crowdsourcing"],
)
@limiter.limit("30/minute")
def submit_report(request: Request, report: CrowdReportCreate) -> CrowdReportReceipt:
    match = nearest_segment(longitude=report.longitude, latitude=report.latitude)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No road segment is available in the current demo zone.",
        )
    logger.info("report_submitted", segment_id=match.segment_id, severity=report.severity)
    return create_report(report=report, segment_id=match.segment_id, distance_m=match.distance_m)


@router.post("/reports/photo", tags=["crowdsourcing"])
@limiter.limit("20/minute")
async def upload_report_photo(request: Request, file: UploadFile = File(...)) -> dict[str, str]:
    """Upload and validate hazard photo (max 3 MB, JPEG/PNG/WebP)."""
    photo_path = await save_report_photo(file)
    return {"photo_path": photo_path}


@router.get("/reports", response_model=list[CrowdReportSummary], tags=["crowdsourcing"])
@limiter.limit("60/minute")
def my_reports(request: Request, reporter_fingerprint: str = Query(min_length=8, max_length=128)) -> list[CrowdReportSummary]:
    return list_reports(limit=100, reporter_fingerprint=reporter_fingerprint)


@router.post("/reports/{report_id}/verify", response_model=CrowdReportSummary, tags=["municipal"])
@limiter.limit("60/minute")
def verify_report_direct(request: Request, report_id: UUID, staff_email: str = Depends(require_staff)) -> CrowdReportSummary:
    logger.info("report_verified", report_id=str(report_id), reviewer=staff_email)
    return review_report(report_id, "verified", staff_email)


@router.post("/reports/{report_id}/reject", response_model=CrowdReportSummary, tags=["municipal"])
@limiter.limit("60/minute")
def reject_report_direct(request: Request, report_id: UUID, staff_email: str = Depends(require_staff)) -> CrowdReportSummary:
    logger.info("report_rejected", report_id=str(report_id), reviewer=staff_email)
    return review_report(report_id, "rejected", staff_email)


@router.post("/municipal/login", response_model=TokenResponse, tags=["municipal"])
@limiter.limit("20/minute")
def municipal_login(request: Request, payload: LoginRequest) -> TokenResponse:
    logger.info("municipal_login_attempt", email=payload.email)
    return login(payload)


@router.get("/municipal/reports", response_model=list[CrowdReportSummary], tags=["municipal"])
@limiter.limit("60/minute")
def municipal_reports(request: Request, _: str = Depends(require_staff)) -> list[CrowdReportSummary]:
    return list_reports()


@router.post("/municipal/reports/{report_id}/review", response_model=CrowdReportSummary, tags=["municipal"])
@limiter.limit("60/minute")
def municipal_report_review(
    request: Request, report_id: UUID, payload: ReportReviewRequest, staff_email: str = Depends(require_staff)
) -> CrowdReportSummary:
    return review_report(report_id, payload.decision, staff_email)


@router.get("/municipal/hotspots", tags=["municipal"])
@limiter.limit("60/minute")
def municipal_hotspots(request: Request, _: str = Depends(require_staff)) -> list[dict]:
    return hotspots()


@router.get("/municipal/drain-failure-flags", tags=["municipal"])
@router.get("/municipal/drainage-flags", tags=["municipal"])
@limiter.limit("60/minute")
def municipal_drain_flags(request: Request, _: str = Depends(require_staff)) -> list[dict]:
    return drain_failure_flags()


@router.get("/municipal/work-orders", response_model=list[WorkOrderResponse], tags=["municipal"])
@limiter.limit("60/minute")
def municipal_work_orders(request: Request, _: str = Depends(require_staff)) -> list[WorkOrderResponse]:
    return list_work_orders()


@router.post("/municipal/work-orders", response_model=WorkOrderResponse, status_code=status.HTTP_201_CREATED, tags=["municipal"])
@limiter.limit("60/minute")
def municipal_create_work_order(
    request: Request, payload: WorkOrderCreate, staff_email: str = Depends(require_staff)
) -> WorkOrderResponse:
    logger.info("work_order_created", segment_id=payload.segment_id, priority=payload.priority)
    return create_work_order(payload, staff_email)


@router.patch("/municipal/work-orders/{order_id}", response_model=WorkOrderResponse, tags=["municipal"])
@limiter.limit("60/minute")
def municipal_update_work_order(
    request: Request, order_id: UUID, payload: WorkOrderUpdate, _: str = Depends(require_staff)
) -> WorkOrderResponse:
    return update_work_order(order_id, payload)


@router.get("/municipal/reports.csv", tags=["municipal"])
@limiter.limit("20/minute")
def export_reports_csv(request: Request, _: str = Depends(require_staff)) -> Response:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["id", "segment_id", "type", "severity", "status", "latitude", "longitude", "created_at"])
    for report in list_reports(limit=10_000):
        writer.writerow([report.id, report.segment_id, report.report_type, report.severity, report.status, report.latitude, report.longitude, report.created_at.isoformat()])
    return Response(
        content=stream.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=flood-risk-reports.csv"},
    )
