"""Crowd-report persistence, rate controls, clustering verification, and photo storage.

Provides:
- 3-device / 150m / 30min auto-verification clustering
- Local photo upload with strict 3MB size limit and MIME validation
- Time-decayed crowd signal (waterlogging reports expire after 4 hours)
- In-memory resilient fallback when PostgreSQL is offline
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import psycopg
from fastapi import HTTPException, UploadFile, status

from app.core.config import get_settings
from app.core.database import is_db_available
from app.schemas import CrowdReportCreate, CrowdReportReceipt, CrowdReportSummary

logger = logging.getLogger(__name__)

VERIFIABLE_TYPES = {"waterlogging", "flood", "blocked_drain"}
RATE_WINDOW = timedelta(minutes=30)
MAX_REPORTS_PER_WINDOW = 5
MAX_PHOTO_BYTES = 3 * 1024 * 1024  # 3 MB
ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}

_report_attempts: dict[str, deque[datetime]] = defaultdict(deque)

# In-memory store fallback when PostgreSQL is offline
_in_memory_reports: dict[UUID, dict[str, Any]] = {}
_report_counts_cache: dict[str, Any] = {"counts": {}, "last_checked": 0.0}


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
    a = (
        math.sin(lat_delta / 2) ** 2
        + math.cos(math.radians(lat_a)) * math.cos(math.radians(lat_b)) * math.sin(lon_delta / 2) ** 2
    )
    return 2 * earth_radius_m * math.asin(math.sqrt(a))


def _check_rate_limit(fingerprint: str | None, now: datetime) -> None:
    """Device rate limiter: max 5 reports per 30 minutes."""
    if not fingerprint:
        return
    attempts = _report_attempts[fingerprint]
    while attempts and now - attempts[0] > RATE_WINDOW:
        attempts.popleft()
    if len(attempts) >= MAX_REPORTS_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reports from this device. Please wait a few minutes before reporting again.",
        )
    attempts.append(now)


def _verify_cluster_db(connection: psycopg.Connection, report: CrowdReportCreate, report_id: UUID, now: datetime) -> bool:
    """Auto-verify in DB when >= 3 distinct devices report within 150m and 30 minutes."""
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


def _verify_cluster_memory(report: CrowdReportCreate, report_id: UUID, now: datetime) -> bool:
    """In-memory cluster verification fallback."""
    if report.report_type not in VERIFIABLE_TYPES or not report.reporter_fingerprint:
        return False
    cutoff = now - RATE_WINDOW
    nearby = [
        r for r in _in_memory_reports.values()
        if r["report_type"] == report.report_type
        and r["created_at"] >= cutoff
        and r["status"] in ("pending", "verified")
        and r.get("reporter_fingerprint")
        and _distance_m(report.latitude, report.longitude, r["latitude"], r["longitude"]) <= 150
    ]
    unique_devices = {r["reporter_fingerprint"] for r in nearby}
    if len(unique_devices) >= 3:
        for r in nearby:
            r["status"] = "verified"
            if not r["verified_at"]:
                r["verified_at"] = now
        return True
    return False


def create_report(report: CrowdReportCreate, segment_id: str, distance_m: float) -> CrowdReportReceipt:
    """Persist a report and evaluate cluster verification."""
    report_id: UUID = uuid4()
    created_at = datetime.now(timezone.utc)
    _check_rate_limit(report.reporter_fingerprint, created_at)
    verified = False

    # Try PostgreSQL first
    db_success = False
    if is_db_available():
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=1) as connection:
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
                verified = _verify_cluster_db(connection, report, report_id, created_at)
                connection.commit()
                db_success = True
        except Exception:
            db_success = False

    # Fallback to in-memory store
    if not db_success:
        _in_memory_reports[report_id] = {
            "id": report_id,
            "segment_id": segment_id,
            "report_type": report.report_type,
            "severity": report.severity,
            "longitude": report.longitude,
            "latitude": report.latitude,
            "description": report.description,
            "photo_path": report.photo_path,
            "reporter_fingerprint": report.reporter_fingerprint,
            "status": "pending",
            "created_at": created_at,
            "verified_at": None,
        }
        verified = _verify_cluster_memory(report, report_id, created_at)

    # Invalidate cache
    _report_counts_cache["last_checked"] = 0.0

    return CrowdReportReceipt(
        id=report_id,
        status="verified" if verified else "pending",
        segment_id=segment_id,
        nearest_segment_distance_m=distance_m,
        created_at=created_at,
        message=(
            "Report auto-verified by nearby independent reports and applied to live risk scoring."
            if verified else "Report received. It will affect risk scoring once verified by independent reports or staff."
        ),
    )


def verified_report_counts() -> dict[str, int]:
    """Return active crowd signals per segment with 4-hour time decay for waterlogging."""
    now_mono = time.monotonic()
    if now_mono - _report_counts_cache["last_checked"] < 5.0:
        return _report_counts_cache["counts"]

    _report_counts_cache["last_checked"] = now_mono
    cutoff = datetime.now(timezone.utc) - timedelta(hours=4)

    # Try DB
    if is_db_available():
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=1) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT segment_id, COUNT(*)
                        FROM citizen_reports
                        WHERE status = 'verified' AND (
                            report_type = 'pothole' OR created_at >= %s
                        )
                        GROUP BY segment_id
                        """,
                        (cutoff,),
                    )
                    counts = {row[0]: row[1] for row in cursor.fetchall()}
                    _report_counts_cache["counts"] = counts
                    return counts
        except Exception:
            pass

    # In-memory fallback
    counts: dict[str, int] = defaultdict(int)
    for r in _in_memory_reports.values():
        if r["status"] == "verified":
            if r["report_type"] == "pothole" or r["created_at"] >= cutoff:
                counts[r["segment_id"]] += 1

    result = dict(counts)
    _report_counts_cache["counts"] = result
    return result


def list_reports(limit: int = 100, reporter_fingerprint: str | None = None) -> list[CrowdReportSummary]:
    """List citizen reports from DB or in-memory fallback."""
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

    if is_db_available():
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=1) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, params)
                    return [_as_summary(row) for row in cursor.fetchall()]
        except Exception:
            pass

    # In-memory fallback
    results: list[CrowdReportSummary] = []
    for r in sorted(_in_memory_reports.values(), key=lambda x: x["created_at"], reverse=True):
        if reporter_fingerprint and r.get("reporter_fingerprint") != reporter_fingerprint:
            continue
        results.append(
            CrowdReportSummary(
                id=r["id"],
                segment_id=r["segment_id"],
                report_type=r["report_type"],
                severity=r["severity"],
                longitude=r["longitude"],
                latitude=r["latitude"],
                description=r["description"],
                status=r["status"],
                created_at=r["created_at"],
                verified_at=r["verified_at"],
            )
        )
        if len(results) >= limit:
            break
    return results


def review_report(report_id: UUID, decision: str, reviewer: str) -> CrowdReportSummary:
    """Verify or reject a report (municipal staff review)."""
    now = datetime.now(timezone.utc)
    if is_db_available():
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=1) as connection:
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
                if row is not None:
                    _report_counts_cache["last_checked"] = 0.0
                    return _as_summary(row)
        except Exception:
            pass

    # In-memory fallback
    if report_id in _in_memory_reports:
        r = _in_memory_reports[report_id]
        r["status"] = decision
        if decision == "verified" and not r["verified_at"]:
            r["verified_at"] = now
        _report_counts_cache["last_checked"] = 0.0
        return CrowdReportSummary(
            id=r["id"],
            segment_id=r["segment_id"],
            report_type=r["report_type"],
            severity=r["severity"],
            longitude=r["longitude"],
            latitude=r["latitude"],
            description=r["description"],
            status=r["status"],
            created_at=r["created_at"],
            verified_at=r["verified_at"],
        )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")


async def save_report_photo(upload_file: UploadFile) -> str:
    """Validate photo format and size (max 3 MB) and save locally."""
    content_type = upload_file.content_type or ""
    if content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{content_type}'. Allowed types: JPEG, PNG, WebP.",
        )

    content = await upload_file.read()
    if not content or len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded photo file is empty.",
        )
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Photo exceeds 3 MB limit (received {len(content) / (1024 * 1024):.1f} MB).",
        )

    # Magic byte signature validation
    is_jpeg = content.startswith(b"\xFF\xD8\xFF")
    is_png = content.startswith(b"\x89PNG\r\n\x1a\n")
    is_webp = len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP"
    if not (is_jpeg or is_png or is_webp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image format: file contents do not match image header signatures.",
        )

    ext = ".jpg" if "jpeg" in content_type else ".png" if "png" in content_type else ".webp"
    filename = f"report-{uuid4().hex[:12]}{ext}"
    upload_dir = get_settings().upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest_path = upload_dir / filename
    dest_path.write_bytes(content)

    return f"/uploads/{filename}"
