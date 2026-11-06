import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

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
from app.services.reports import create_report, list_reports, review_report, verified_report_counts
from app.services.risk_engine import weighted_contributions
from app.services.routing import compare_routes, travel_advice
from app.services.segments import nearest_segment, scored_segments
from app.services.weather import rain_store

router = APIRouter()


def _current_segments() -> dict:
    rain = rain_store.response()
    return scored_segments(rain.rainfall_mm_hour, verified_report_counts())


def _segment_or_404(segment_id: str) -> dict:
    for feature in _current_segments()["features"]:
        if feature["properties"]["segment_id"] == segment_id:
            return feature
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found")


@router.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "stage": "day-3", "service": "flood-risk-api"}


@router.get("/map/segments", tags=["map"])
def map_segments() -> dict:
    """Return current risk-scored GeoJSON. Rain and verified reports alter the scores."""
    return _current_segments()


@router.get("/segments/{segment_id}", tags=["map"])
def segment_detail(segment_id: str) -> dict:
    return _segment_or_404(segment_id)


@router.get("/segments/{segment_id}/explanation", tags=["map"])
def segment_explanation(segment_id: str) -> dict:
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
def rain_state() -> RainStateResponse:
    return rain_store.response()


@router.post("/rain/simulate", response_model=RainStateResponse, tags=["rain"])
def set_rain_simulator(payload: RainSimulationRequest) -> RainStateResponse:
    return rain_store.set_simulator(payload.level)


@router.post("/rain/refresh", response_model=RainStateResponse, tags=["rain"])
async def refresh_live_rain(_: str = Depends(require_staff)) -> RainStateResponse:
    return await rain_store.refresh_from_open_meteo()


@router.post("/routes/compare", response_model=RouteResponse, tags=["routing"])
def route_comparison(payload: RouteRequest) -> RouteResponse:
    return compare_routes(payload)


@router.post("/travel-advice", response_model=TravelAdviceResponse, tags=["routing"])
def should_i_travel(payload: TravelAdviceRequest) -> TravelAdviceResponse:
    return travel_advice(payload)


@router.post(
    "/reports",
    response_model=CrowdReportReceipt,
    status_code=status.HTTP_201_CREATED,
    tags=["crowdsourcing"],
)
def submit_report(report: CrowdReportCreate) -> CrowdReportReceipt:
    match = nearest_segment(longitude=report.longitude, latitude=report.latitude)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No road segment is available in the current demo zone.",
        )
    return create_report(report=report, segment_id=match.segment_id, distance_m=match.distance_m)


@router.get("/reports", response_model=list[CrowdReportSummary], tags=["crowdsourcing"])
def my_reports(reporter_fingerprint: str = Query(min_length=8, max_length=128)) -> list[CrowdReportSummary]:
    return list_reports(limit=100, reporter_fingerprint=reporter_fingerprint)


@router.post("/municipal/login", response_model=TokenResponse, tags=["municipal"])
def municipal_login(payload: LoginRequest) -> TokenResponse:
    return login(payload)


@router.get("/municipal/reports", response_model=list[CrowdReportSummary], tags=["municipal"])
def municipal_reports(_: str = Depends(require_staff)) -> list[CrowdReportSummary]:
    return list_reports()


@router.post("/municipal/reports/{report_id}/review", response_model=CrowdReportSummary, tags=["municipal"])
def municipal_report_review(
    report_id: UUID, payload: ReportReviewRequest, staff_email: str = Depends(require_staff)
) -> CrowdReportSummary:
    return review_report(report_id, payload.decision, staff_email)


@router.get("/municipal/hotspots", tags=["municipal"])
def municipal_hotspots(_: str = Depends(require_staff)) -> list[dict]:
    return hotspots()


@router.get("/municipal/drain-failure-flags", tags=["municipal"])
def municipal_drain_flags(_: str = Depends(require_staff)) -> list[dict]:
    return drain_failure_flags(low_rainfall=rain_store.response().rainfall_mm_hour < 5)


@router.get("/municipal/work-orders", response_model=list[WorkOrderResponse], tags=["municipal"])
def municipal_work_orders(_: str = Depends(require_staff)) -> list[WorkOrderResponse]:
    return list_work_orders()


@router.post("/municipal/work-orders", response_model=WorkOrderResponse, status_code=status.HTTP_201_CREATED, tags=["municipal"])
def municipal_create_work_order(
    payload: WorkOrderCreate, staff_email: str = Depends(require_staff)
) -> WorkOrderResponse:
    return create_work_order(payload, staff_email)


@router.patch("/municipal/work-orders/{order_id}", response_model=WorkOrderResponse, tags=["municipal"])
def municipal_update_work_order(
    order_id: UUID, payload: WorkOrderUpdate, _: str = Depends(require_staff)
) -> WorkOrderResponse:
    return update_work_order(order_id, payload)


@router.get("/municipal/reports.csv", tags=["municipal"])
def export_reports_csv(_: str = Depends(require_staff)) -> Response:
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(["id", "segment_id", "type", "severity", "status", "latitude", "longitude", "created_at"])
    for report in list_reports(limit=10_000):
        writer.writerow([report.id, report.segment_id, report.report_type, report.severity, report.status, report.latitude, report.longitude, report.created_at.isoformat()])
    return Response(
        content=stream.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=flood-risk-reports.csv"},
    )
