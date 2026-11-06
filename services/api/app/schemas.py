from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


ReportType = Literal["waterlogging", "flood", "pothole", "blocked_drain", "other"]
ReportStatus = Literal["pending", "verified", "rejected", "resolved"]
RainLevel = Literal["none", "light", "medium", "heavy", "extreme"]
VehicleType = Literal["two_wheeler", "car", "bus", "truck"]
RoutePreference = Literal["fast", "safe", "balanced"]
WorkOrderStatus = Literal["open", "assigned", "in_progress", "resolved"]


class CrowdReportCreate(BaseModel):
    report_type: ReportType
    severity: int = Field(ge=1, le=5, description="1 is minor and 5 is severe")
    longitude: float = Field(ge=73.80, le=73.93, description="Longitude in the Pune demo zone")
    latitude: float = Field(ge=18.48, le=18.60, description="Latitude in the Pune demo zone")
    description: str | None = Field(default=None, max_length=500)
    photo_path: str | None = Field(
        default=None,
        max_length=500,
        description="Temporary Day 1 path; upload validation arrives on Day 3.",
    )
    reporter_fingerprint: str | None = Field(
        default=None,
        max_length=128,
        description="Anonymous device hash used by the Day 2 verification rule.",
    )


class CrowdReportReceipt(BaseModel):
    id: UUID
    status: Literal["pending", "verified"]
    segment_id: str
    nearest_segment_distance_m: float
    created_at: datetime
    message: str


class CrowdReportSummary(BaseModel):
    id: UUID
    segment_id: str
    report_type: ReportType
    severity: int
    longitude: float
    latitude: float
    description: str | None
    status: ReportStatus
    created_at: datetime
    verified_at: datetime | None = None


class RainSimulationRequest(BaseModel):
    level: RainLevel


class RainStateResponse(BaseModel):
    level: RainLevel
    rainfall_mm_hour: float
    forecast_30m_mm_hour: float
    source: Literal["simulated", "live", "cached"]
    is_stale: bool
    updated_at: datetime


class Coordinate(BaseModel):
    longitude: float = Field(ge=73.80, le=73.93)
    latitude: float = Field(ge=18.48, le=18.60)


class RouteRequest(BaseModel):
    origin: Coordinate
    destination: Coordinate
    vehicle: VehicleType = "car"


class RouteOption(BaseModel):
    id: RoutePreference
    label: str
    geometry: dict
    distance_m: int
    duration_min: int
    average_risk: float
    highest_risk: float
    risky_segment_count: int
    segment_ids: list[str]
    recommendation: str


class RouteResponse(BaseModel):
    vehicle: VehicleType
    rain: RainStateResponse
    routes: list[RouteOption]


class SegmentExplanation(BaseModel):
    segment_id: str
    name: str
    risk_score: float
    confidence: float
    risk_band: str
    signals: dict[str, float]
    weighted_contributions: dict[str, float]
    reasons: list[str]
    active_verified_reports: int


class TravelAdviceRequest(BaseModel):
    vehicle: VehicleType = "car"
    origin: Coordinate | None = None
    destination: Coordinate | None = None


class TravelAdviceResponse(BaseModel):
    verdict: Literal["go", "caution", "wait", "avoid"]
    vehicle: VehicleType
    risk_now: float
    risk_in_30m: float
    trend: Literal["falling", "stable", "rising"]
    reasons: list[str]
    updated_at: datetime


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class ReportReviewRequest(BaseModel):
    decision: Literal["verified", "rejected"]


class WorkOrderCreate(BaseModel):
    report_id: UUID | None = None
    segment_id: str = Field(min_length=3, max_length=80)
    title: str = Field(min_length=3, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    priority: int = Field(default=3, ge=1, le=5)
    assigned_to: str | None = Field(default=None, max_length=120)


class WorkOrderUpdate(BaseModel):
    status: WorkOrderStatus
    assigned_to: str | None = Field(default=None, max_length=120)


class WorkOrderResponse(BaseModel):
    id: UUID
    report_id: UUID | None
    segment_id: str
    title: str
    description: str | None
    priority: int
    status: WorkOrderStatus
    assigned_to: str | None
    created_at: datetime
    updated_at: datetime
