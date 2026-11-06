"""Crowd-report persistence, rate controls, and verification rules."""

from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import psycopg
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.schemas import CrowdReportCreate, CrowdReportReceipt, CrowdReportSummary

VERIFIABLE_TYPES = {"waterlogging", "flood", "blocked_drain"}
RATE_WINDOW = timedelta(minutes=30)
MAX_REPORTS_PER_WINDOW = 5
_report_attempts: dict[str, deque[datetime]] = defaultdict(deque)


def _as_summary(row: tuple[Any, ...]) -> CrowdReportSummary:
    return CrowdReportSummary(
        id=row[0],
        segment_id=row[1],
        report_type=row[2],
        severity=row[3],
        longitude=row[4],
        latitude=row[5],
        description=row[6],
        status=row[7],
        created_at=row[8],
        verified_at=row[9],
    )


def _distance_m(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    earth_radius_m = 6_371_000
    lat_delta = math.radians(lat_b - lat_a)
    lon_delta = math.radians(lon_b - lon_a)
    a = math.sin(lat_delta / 2) ** 2 + math.cos(math.radians(lat_a)) * math.cos(math.radians(lat_b)) * math.sin(lon_delta / 2) ** 2
    return 2 * earth_radius_m * math.asin(math.sqrt(a))


def _check_rate_limit(fingerprint: str | None, now: datetime) -> None:
    """Small process-local safety net; deploy behind a shared Redis limiter."""
    if not fingerprint:
        return
    attempts = _report_attempts[fingerprint]
    while attempts and now - attempts[0] > RATE_WINDOW:
        attempts.popleft()
    if len(attempts) >= MAX_REPORTS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reports from this device. Try again in a few minutes.",
        )
    attempts.append(now)


def _verify_cluster(connection: psycopg.Connection, report: CrowdReportCreate, report_id: UUID, now: datetime) -> bool:
    if report.report_type not in VERIFIABLE_TYPES or not report.reporter_fingerprint:
        return False
    cutoff = now - RATE_WINDOW
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, latitude, longitude, reporter_fingerprint
            FROM citizen_reports
            WHERE report_type = %s
              AND created_at >= %s
              AND status IN ('pending', 'verified')
            """,
            (report.report_type, cutoff),
        )
        nearby_rows = [
            row
            for row in cursor.fetchall()
            if row[3] and _distance_m(report.latitude, report.longitude, row[1], row[2]) <= 150
        ]
        unique_devices = {row[3] for row in nearby_rows}
        if len(unique_devices) < 3:
            return False
        cluster_ids = [row[0] for row in nearby_rows]
        cursor.execute(
            """
            UPDATE citizen_reports
            SET status = 'verified', verified_at = COALESCE(verified_at, %s), updated_at = %s
            WHERE id = ANY(%s)
            """,
            (now, now, cluster_ids),
        )
    return report_id in cluster_ids


def create_report(report: CrowdReportCreate, segment_id: str, distance_m: float) -> CrowdReportReceipt:
    """Persist a report and auto-verify a 3-device / 150m / 30m incident cluster."""
    report_id: UUID = uuid4()
    created_at = datetime.now(timezone.utc)
    _check_rate_limit(report.reporter_fingerprint, created_at)
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO citizen_reports (
                        id, segment_id, report_type, severity, longitude, latitude,
                        description, photo_path, reporter_fingerprint, status, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s)
                    """,
                    (
                        report_id, segment_id, report.report_type, report.severity,
                        report.longitude, report.latitude, report.description, report.photo_path,
                        report.reporter_fingerprint, created_at, created_at,
                    ),
                )
            verified = _verify_cluster(connection, report, report_id, created_at)
            connection.commit()
    except psycopg.Error as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Report storage is temporarily unavailable; please retry.",
        ) from error

    return CrowdReportReceipt(
        id=report_id,
        status="verified" if verified else "pending",
        segment_id=segment_id,
        nearest_segment_distance_m=distance_m,
        created_at=created_at,
        message=(
            "Report verified by nearby independent reports and added to risk scoring."
            if verified else "Report received. It will affect risk scoring once verified."
        ),
    )


def verified_report_counts() -> dict[str, int]:
    """Return active crowd signal per segment; a database outage cannot hide map data."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT segment_id, COUNT(*)
                    FROM citizen_reports
                    WHERE status = 'verified' AND created_at >= %s
                    GROUP BY segment_id
                    """,
                    (cutoff,),
                )
                return {row[0]: row[1] for row in cursor.fetchall()}
    except psycopg.Error:
        return {}


def list_reports(limit: int = 100, reporter_fingerprint: str | None = None) -> list[CrowdReportSummary]:
    query = """
        SELECT id, segment_id, report_type, severity, longitude, latitude, description,
               status, created_at, verified_at
        FROM citizen_reports
    """
    params: list[Any] = []
    if reporter_fingerprint:
        query += " WHERE reporter_fingerprint = %s"
        params.append(reporter_fingerprint)
    query += " ORDER BY created_at DESC LIMIT %s"
    params.append(limit)
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                return [_as_summary(row) for row in cursor.fetchall()]
    except psycopg.Error as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Report storage is unavailable.") from error


def review_report(report_id: UUID, decision: str, reviewer: str) -> CrowdReportSummary:
    now = datetime.now(timezone.utc)
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE citizen_reports
                    SET status = %s, verified_at = CASE WHEN %s = 'verified' THEN %s ELSE verified_at END,
                        reviewed_by = %s, updated_at = %s
                    WHERE id = %s
                    RETURNING id, segment_id, report_type, severity, longitude, latitude, description,
                              status, created_at, verified_at
                    """,
                    (decision, decision, now, reviewer, now, report_id),
                )
                row = cursor.fetchone()
            connection.commit()
    except psycopg.Error as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Report storage is unavailable.") from error
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return _as_summary(row)
