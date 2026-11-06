"""Municipal report queue, hotspots, drainage failure flags, and work orders.

Provides:
- Work-order lifecycle (open -> assigned -> in_progress -> resolved)
- Immediate crowd-signal clearance upon work-order resolution
- Drainage failure detection (verified reports when rain < 60% of segment threshold T_seg)
- Combined hotspot ranking
- In-memory resilient fallback when PostgreSQL is offline
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import psycopg
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.database import is_db_available
from app.schemas import MunicipalStatsResponse, WorkOrderCreate, WorkOrderResponse, WorkOrderUpdate
from app.services.reports import _in_memory_reports, _report_counts_cache, review_report, verified_report_counts
from app.services.risk_engine import segment_threshold
from app.services.segments import get_segment, list_segments
from app.services.weather import rain_store

logger = logging.getLogger(__name__)

# In-memory work order store for testing/demo fallback
_in_memory_work_orders: dict[UUID, dict[str, Any]] = {}


def _as_work_order(row: tuple[Any, ...]) -> WorkOrderResponse:
    return WorkOrderResponse(
        id=row[0],
        report_id=row[1],
        segment_id=row[2],
        title=row[3],
        description=row[4],
        priority=row[5],
        status=row[6],
        assigned_to=row[7],
        created_at=row[8],
        updated_at=row[9],
    )


def list_work_orders() -> list[WorkOrderResponse]:
    """Retrieve all maintenance work orders ordered by status and priority."""
    if is_db_available():
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=1) as connection:
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
        except Exception:
            pass

    # In-memory fallback
    orders = sorted(
        _in_memory_work_orders.values(),
        key=lambda x: (
            {"open": 0, "assigned": 1, "in_progress": 2, "resolved": 3}.get(x["status"], 4),
            -x["priority"],
            -x["created_at"].timestamp(),
        ),
    )
    return [
        WorkOrderResponse(
            id=o["id"],
            report_id=o["report_id"],
            segment_id=o["segment_id"],
            title=o["title"],
            description=o["description"],
            priority=o["priority"],
            status=o["status"],
            assigned_to=o["assigned_to"],
            created_at=o["created_at"],
            updated_at=o["updated_at"],
        )
        for o in orders
    ]


def create_work_order(payload: WorkOrderCreate, staff_email: str) -> WorkOrderResponse:
    """Create a municipal work order for hazard remediation."""
    order_id = uuid4()
    now = datetime.now(timezone.utc)
    initial_status = "assigned" if payload.assigned_to else "open"

    if is_db_available():
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=1) as connection:
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
                        (
                            order_id, payload.report_id, payload.segment_id, payload.title,
                            payload.description, payload.priority, initial_status, payload.assigned_to,
                            staff_email, now, now,
                        ),
                    )
                    row = cursor.fetchone()
                connection.commit()
                if row is not None:
                    return _as_work_order(row)
        except Exception:
            pass

    # In-memory fallback
    record = {
        "id": order_id,
        "report_id": payload.report_id,
        "segment_id": payload.segment_id,
        "title": payload.title,
        "description": payload.description,
        "priority": payload.priority,
        "status": initial_status,
        "assigned_to": payload.assigned_to,
        "created_by": staff_email,
        "created_at": now,
        "updated_at": now,
    }
    _in_memory_work_orders[order_id] = record
    return WorkOrderResponse(**record)


def update_work_order(order_id: UUID, payload: WorkOrderUpdate) -> WorkOrderResponse:
    """Update work order status; resolving clears the incident effect from risk scoring."""
    now = datetime.now(timezone.utc)
    updated_row = None

    if is_db_available():
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=1) as connection:
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
                    updated_row = cursor.fetchone()
                    if updated_row is not None and payload.status == "resolved" and updated_row[1] is not None:
                        # Resolving work order marks report resolved, removing crowd signal
                        cursor.execute(
                            "UPDATE citizen_reports SET status = 'resolved', updated_at = %s WHERE id = %s",
                            (now, updated_row[1]),
                        )
                connection.commit()
                if updated_row is not None:
                    return _as_work_order(updated_row)
        except Exception:
            pass

    # In-memory fallback
    if order_id in _in_memory_work_orders:
        rec = _in_memory_work_orders[order_id]
        rec["status"] = payload.status
        if payload.assigned_to is not None:
            rec["assigned_to"] = payload.assigned_to
        rec["updated_at"] = now

        # If resolved, update report status in memory — clear ALL verified reports
        # for this segment (not just the directly linked report_id), so the crowd
        # signal is fully removed from risk scoring even when no report_id is set.
        if payload.status == "resolved":
            seg_id = rec.get("segment_id")
            # Clear linked report (if any)
            if rec["report_id"]:
                try:
                    review_report(rec["report_id"], "resolved", "system-work-order")
                except Exception:
                    pass
            # Clear all remaining verified reports for the same segment
            if seg_id:
                for r in _in_memory_reports.values():
                    if r.get("segment_id") == seg_id and r.get("status") == "verified":
                        r["status"] = "resolved"
            # Bust the report counts cache so next read reflects clearance
            _report_counts_cache["last_checked"] = 0.0

        return WorkOrderResponse(
            id=rec["id"],
            report_id=rec["report_id"],
            segment_id=rec["segment_id"],
            title=rec["title"],
            description=rec["description"],
            priority=rec["priority"],
            status=rec["status"],
            assigned_to=rec["assigned_to"],
            created_at=rec["created_at"],
            updated_at=rec["updated_at"],
        )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work order not found")


def hotspots() -> list[dict[str, Any]]:
    """Return recurring flood hotspots based on verified citizen reports and segment history."""
    if is_db_available():
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=1) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT segment_id, COUNT(*) AS reports, MAX(severity) AS max_severity,
                               MAX(created_at) AS last_reported_at
                        FROM citizen_reports
                        WHERE status IN ('pending', 'verified')
                        GROUP BY segment_id
                        HAVING COUNT(*) >= 1
                        ORDER BY reports DESC, max_severity DESC
                        """
                    )
                    db_results = [
                        {
                            "segment_id": row[0],
                            "report_count": row[1],
                            "max_severity": row[2],
                            "last_reported_at": row[3],
                        }
                        for row in cursor.fetchall()
                    ]
                    if db_results:
                        return db_results
        except Exception:
            pass

    # Built-in fallback combining demo seeds and memory reports
    report_counts = verified_report_counts()
    results: list[dict[str, Any]] = []

    for feat in list_segments()["features"]:
        props = feat["properties"]
        seg_id = props["segment_id"]
        c_count = report_counts.get(seg_id, 0)
        hist_sig = props.get("signals", {}).get("flood_history", 0.0)

        if c_count >= 1 or hist_sig >= 0.50:
            results.append({
                "segment_id": seg_id,
                "name": props["name"],
                "report_count": max(1, c_count),
                "max_severity": 4 if hist_sig >= 0.70 else 3,
                "flood_history_signal": hist_sig,
                "last_reported_at": datetime.now(timezone.utc).isoformat(),
            })

    results.sort(key=lambda x: (x["report_count"], x.get("flood_history_signal", 0)), reverse=True)
    return results


def drain_failure_flags() -> list[dict[str, Any]]:
    """Flag road segments where verified flooding occurs while rainfall is < 60% of segment capacity T_seg."""
    current_rain = rain_store.response().rainfall_mm_hour
    active_counts = verified_report_counts()
    flags: list[dict[str, Any]] = []

    for feat in list_segments()["features"]:
        props = feat["properties"]
        seg_id = props["segment_id"]
        v_count = active_counts.get(seg_id, 0)

        # Compute this segment's specific threshold
        signals = props.get("signals", {})
        t_seg = segment_threshold(signals.get("terrain", 0.0), signals.get("flood_history", 0.0))

        # Check if flooding occurs below 60% of capacity threshold
        # Or if there is an underpass with verified report in light/medium rain
        if (v_count > 0 and current_rain < 0.60 * t_seg) or (props.get("is_underpass") and v_count > 0 and current_rain < 15.0):
            ratio = round(current_rain / t_seg, 2)
            flags.append({
                "segment_id": seg_id,
                "name": props["name"],
                "verified_reports": v_count,
                "rainfall_mm_hour": current_rain,
                "threshold_mm_hr": round(t_seg, 1),
                "capacity_utilization": f"{int(ratio * 100)}%",
                "suspected_cause": "Structural drainage failure: waterlogging occurred well below road capacity threshold.",
                "action_recommended": "Inspect storm culvert for silt buildup, tree debris, or pump failure.",
            })

    return flags


def municipal_stats() -> MunicipalStatsResponse:
    """Return aggregated KPI statistics for the municipal dashboard."""
    now_utc = datetime.now(timezone.utc)
    start_of_today = datetime(now_utc.year, now_utc.month, now_utc.day, tzinfo=timezone.utc)

    if is_db_available():
        try:
            with psycopg.connect(get_settings().database_url, connect_timeout=1) as conn:
                with conn.cursor() as cur:
                    # Open reports (pending + verified)
                    cur.execute("SELECT COUNT(*) FROM citizen_reports WHERE status IN ('pending', 'verified')")
                    open_reps = cur.fetchone()[0]

                    # Pending reports
                    cur.execute("SELECT COUNT(*) FROM citizen_reports WHERE status = 'pending'")
                    pending_reps = cur.fetchone()[0]

                    # Verified today
                    cur.execute(
                        "SELECT COUNT(*) FROM citizen_reports WHERE status = 'verified' AND verified_at >= %s",
                        (start_of_today,),
                    )
                    verif_today = cur.fetchone()[0]

                    # Open work orders
                    cur.execute("SELECT COUNT(*) FROM work_orders WHERE status != 'resolved'")
                    open_wos = cur.fetchone()[0]

                    active_hs = len(hotspots())

                    return MunicipalStatsResponse(
                        open_reports=open_reps,
                        verified_today=verif_today,
                        active_hotspots=active_hs,
                        open_work_orders=open_wos,
                        pending_reports=pending_reps,
                    )
        except Exception:
            pass

    # In-memory fallback
    from app.services.reports import _in_memory_reports

    open_reps = 0
    pending_reps = 0
    verif_today = 0
    for r in _in_memory_reports.values():
        st = r.get("status")
        if st in ("pending", "verified"):
            open_reps += 1
        if st == "pending":
            pending_reps += 1
        if st == "verified":
            v_time = r.get("verified_at") or r.get("created_at")
            if v_time and v_time >= start_of_today:
                verif_today += 1

    open_wos = sum(1 for o in _in_memory_work_orders.values() if o.get("status") != "resolved")
    active_hs = len(hotspots())

    return MunicipalStatsResponse(
        open_reports=open_reps,
        verified_today=verif_today,
        active_hotspots=active_hs,
        open_work_orders=open_wos,
        pending_reports=pending_reps,
    )


async def drainage_failure_detector_task(interval_sec: float = 300.0) -> None:
    """Periodic background worker detecting structural drainage failures every 5 minutes."""
    while True:
        try:
            flags = drain_failure_flags()
            if flags:
                logger.warning(
                    "drainage_failures_detected",
                    count=len(flags),
                    flagged_segments=[f["segment_id"] for f in flags],
                )
        except Exception as exc:
            logger.warning("drainage_failure_detector_error: %s", exc)
        await asyncio.sleep(interval_sec)

