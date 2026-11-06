import io
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.services.reports import _in_memory_reports, _report_attempts
from app.services.segments import scored_segments
from app.services.weather import rain_store

client = TestClient(app)


def _get_staff_token() -> str:
    res = client.post("/v1/municipal/login", json={"email": "staff@pune.gov.in", "password": "change-before-deployment"})
    assert res.status_code == 200
    return res.json()["access_token"]


def test_report_submission_and_snapping() -> None:
    res = client.post(
        "/v1/reports",
        json={
            "report_type": "waterlogging",
            "severity": 4,
            "longitude": 73.8448,
            "latitude": 18.5212,
            "description": "Severe waterlogging near JM Road Deccan bus stop",
            "reporter_fingerprint": f"device-{uuid4().hex[:8]}",
        },
    )
    assert res.status_code == 201
    receipt = res.json()
    assert receipt["status"] == "pending"
    assert "pune-demo" in receipt["segment_id"]
    assert receipt["nearest_segment_distance_m"] < 100.0


def test_3_device_auto_verification_cluster() -> None:
    # 3 distinct devices reporting at the same spot within 150m
    lat, lon = 18.5285, 73.8740  # Near Pune Station
    dev1 = f"device-test-1-{uuid4().hex[:6]}"
    dev2 = f"device-test-2-{uuid4().hex[:6]}"
    dev3 = f"device-test-3-{uuid4().hex[:6]}"

    r1 = client.post("/v1/reports", json={"report_type": "waterlogging", "severity": 4, "longitude": lon, "latitude": lat, "reporter_fingerprint": dev1})
    assert r1.status_code == 201
    assert r1.json()["status"] == "pending"

    r2 = client.post("/v1/reports", json={"report_type": "waterlogging", "severity": 4, "longitude": lon + 0.0003, "latitude": lat + 0.0002, "reporter_fingerprint": dev2})
    assert r2.status_code == 201
    assert r2.json()["status"] == "pending"

    # 3rd independent device triggers cluster auto-verification
    r3 = client.post("/v1/reports", json={"report_type": "waterlogging", "severity": 5, "longitude": lon + 0.0001, "latitude": lat + 0.0001, "reporter_fingerprint": dev3})
    assert r3.status_code == 201
    assert r3.json()["status"] == "verified"

    # Verified report count should be >= 1 for that segment
    seg_id = r3.json()["segment_id"]
    coll = scored_segments(rainfall_mm_hour=0.0)
    feat = next(f for f in coll["features"] if f["properties"]["segment_id"] == seg_id)
    assert feat["properties"]["active_verified_reports"] >= 1


def test_work_order_lifecycle_clears_crowd_risk() -> None:
    token = _get_staff_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Submit a verified report
    dev_a = f"dev-wo-1-{uuid4().hex[:6]}"
    dev_b = f"dev-wo-2-{uuid4().hex[:6]}"
    dev_c = f"dev-wo-3-{uuid4().hex[:6]}"
    lat, lon = 18.5200, 73.8490

    for dev in (dev_a, dev_b):
        client.post("/v1/reports", json={"report_type": "waterlogging", "severity": 4, "longitude": lon, "latitude": lat, "reporter_fingerprint": dev})
    last_rep = client.post("/v1/reports", json={"report_type": "waterlogging", "severity": 4, "longitude": lon, "latitude": lat, "reporter_fingerprint": dev_c}).json()
    assert last_rep["status"] == "verified"

    seg_id = last_rep["segment_id"]

    # Create work order
    wo_res = client.post(
        "/v1/municipal/work-orders",
        json={
            "report_id": last_rep["id"],
            "segment_id": seg_id,
            "title": "Clear blocked culvert and drain excess water",
            "priority": 5,
            "assigned_to": "Ward Officer Shinde",
        },
        headers=headers,
    )
    assert wo_res.status_code == 201
    wo_id = wo_res.json()["id"]
    assert wo_res.json()["status"] == "assigned"

    # Resolve work order
    res_update = client.patch(
        f"/v1/municipal/work-orders/{wo_id}",
        json={"status": "resolved"},
        headers=headers,
    )
    assert res_update.status_code == 200
    assert res_update.json()["status"] == "resolved"


def test_drainage_failure_detection() -> None:
    token = _get_staff_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Ensure dry simulator
    rain_store.set_simulator("none")

    # Submit 3 verified reports on a segment during dry/low rain
    lat, lon = 18.5292, 73.8476  # Shivajinagar
    for i in range(3):
        client.post(
            "/v1/reports",
            json={
                "report_type": "waterlogging",
                "severity": 4,
                "longitude": lon,
                "latitude": lat,
                "reporter_fingerprint": f"drain-dev-{i}-{uuid4().hex[:6]}",
            },
        )

    # Check drainage failure flags
    flags = client.get("/v1/municipal/drain-failure-flags", headers=headers).json()
    assert len(flags) >= 1
    flag = flags[0]
    assert "Structural drainage failure" in flag["suspected_cause"]
    assert "Inspect storm culvert" in flag["action_recommended"]


def test_photo_upload_validation() -> None:
    # 1. Reject invalid MIME type
    bad_file = io.BytesIO(b"<html>not an image</html>")
    res_bad = client.post("/v1/reports/photo", files={"file": ("test.html", bad_file, "text/html")})
    assert res_bad.status_code == 415

    # 2. Reject oversized file (> 3MB)
    large_bytes = b"0" * (3 * 1024 * 1024 + 1024)
    res_large = client.post("/v1/reports/photo", files={"file": ("huge.png", io.BytesIO(large_bytes), "image/png")})
    assert res_large.status_code == 413

    # 3. Accept valid PNG <= 3MB
    valid_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (b"0" * 1000)
    res_valid = client.post("/v1/reports/photo", files={"file": ("valid.png", io.BytesIO(valid_bytes), "image/png")})
    assert res_valid.status_code == 200
    assert res_valid.json()["photo_path"].startswith("/uploads/")
