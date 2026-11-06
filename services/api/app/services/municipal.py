"""Municipal report queue, hotspots, drainage flags, and work-order workflow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import psycopg
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.schemas import WorkOrderCreate, WorkOrderResponse, WorkOrderUpdate


def _as_work_order(row: tuple[Any, ...]) -> WorkOrderResponse:
    return WorkOrderResponse(
        id=row[0], report_id=row[1], segment_id=row[2], title=row[3], description=row[4],
        priority=row[5], status=row[6], assigned_to=row[7], created_at=row[8], updated_at=row[9],
    )


def list_work_orders() -> list[WorkOrderResponse]:
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, report_id, segment_id, title, description, priority, status,
                           assigned_to, created_at, updated_at
                    FROM work_orders
                    ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'assigned' THEN 1 WHEN 'in_progress' THEN 2 ELSE 3 END,
                             priority DESC, created_at DESC
                    """
                )
                return [_as_work_order(row) for row in cursor.fetchall()]
    except psycopg.Error as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Municipal storage is unavailable.") from error


def create_work_order(payload: WorkOrderCreate, staff_email: str) -> WorkOrderResponse:
    order_id = uuid4()
    now = datetime.now(timezone.utc)
    initial_status = "assigned" if payload.assigned_to else "open"
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO work_orders (
                        id, report_id, segment_id, title, description, priority, status,
                        assigned_to, created_by, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, report_id, segment_id, title, description, priority, status,
                              assigned_to, created_at, updated_at
                    """,
                    (order_id, payload.report_id, payload.segment_id, payload.title, payload.description,
                     payload.priority, initial_status, payload.assigned_to, staff_email, now, now),
                )
                row = cursor.fetchone()
            connection.commit()
    except psycopg.Error as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Municipal storage is unavailable.") from error
    return _as_work_order(row)


def update_work_order(order_id: UUID, payload: WorkOrderUpdate) -> WorkOrderResponse:
    now = datetime.now(timezone.utc)
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE work_orders
                    SET status = %s, assigned_to = COALESCE(%s, assigned_to), updated_at = %s
                    WHERE id = %s
                    RETURNING id, report_id, segment_id, title, description, priority, status,
                              assigned_to, created_at, updated_at
                    """,
                    (payload.status, payload.assigned_to, now, order_id),
                )
                row = cursor.fetchone()
                if row is not None and payload.status == "resolved" and row[1] is not None:
                    cursor.execute(
                        "UPDATE citizen_reports SET status = 'resolved', updated_at = %s WHERE id = %s",
                        (now, row[1]),
                    )
            connection.commit()
    except psycopg.Error as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Municipal storage is unavailable.") from error
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")
    return _as_work_order(row)


def hotspots() -> list[dict[str, Any]]:
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT segment_id, COUNT(*) AS reports, MAX(severity) AS max_severity,
                           MAX(created_at) AS last_reported_at
                    FROM citizen_reports
                    WHERE status IN ('pending', 'verified')
                    GROUP BY segment_id
                    HAVING COUNT(*) >= 2
                    ORDER BY reports DESC, max_severity DESC
                    """
                )
                return [
                    {"segment_id": row[0], "report_count": row[1], "max_severity": row[2], "last_reported_at": row[3]}
                    for row in cursor.fetchall()
                ]
    except psycopg.Error as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Municipal storage is unavailable.") from error


def drain_failure_flags(low_rainfall: bool) -> list[dict[str, Any]]:
    """Flag verified drainage incidents during light rain for inspection."""
    if not low_rainfall:
        return []
    try:
        with psycopg.connect(get_settings().database_url, connect_timeout=2) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT segment_id, COUNT(*) AS reports, MAX(created_at) AS last_reported_at
                    FROM citizen_reports
                    WHERE status = 'verified' AND report_type IN ('waterlogging', 'flood', 'blocked_drain')
                    GROUP BY segment_id
                    ORDER BY reports DESC
                    """
                )
                return [
                    {"segment_id": row[0], "verified_reports": row[1], "last_reported_at": row[2],
                     "reason": "Verified flooding during light rainfall can indicate a drainage failure."}
                    for row in cursor.fetchall()
                ]
    except psycopg.Error as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Municipal storage is unavailable.") from error
