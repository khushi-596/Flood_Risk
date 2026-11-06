"""Locust load testing suite for Pune Flood Risk API.

Simulates 4 realistic concurrent user personas:
1. MapViewerUser (weight=50): Public dashboard viewers querying road segments, rain, and explanations
2. CommuterUser (weight=30): Travelers requesting risk-weighted route comparisons and travel advice
3. CitizenReporterUser (weight=15): Citizens submitting localized waterlogging hazard reports
4. MunicipalStaffUser (weight=5): City operators monitoring reports, work orders, and drain failures

Usage:
    locust -f tests/load/locustfile.py --host http://localhost:8000
    locust -f tests/load/locustfile.py --host http://localhost:8000 --headless -u 20 -r 5 --run-time 30s
"""

import random
from uuid import uuid4

from locust import HttpUser, between, task


class MapViewerUser(HttpUser):
    """Browses real-time risk map and checks weather."""
    weight = 50
    wait_time = between(1, 3)

    @task(3)
    def view_segments(self):
        self.client.get("/v1/segments", name="GET /v1/segments")

    @task(2)
    def view_rain(self):
        self.client.get("/v1/rain", name="GET /v1/rain")

    @task(1)
    def view_segment_explanation(self):
        # Demo segment ID
        self.client.get(
            "/v1/segments/pune-demo-001/explanation",
            name="GET /v1/segments/{id}/explanation",
        )

    @task(1)
    def view_health(self):
        self.client.get("/v1/health", name="GET /v1/health")


class CommuterUser(HttpUser):
    """Queries safe vs fast routes and asks for travel advice."""
    weight = 30
    wait_time = between(2, 5)

    @task(2)
    def compare_routes(self):
        payload = {
            "origin": {"longitude": 73.8448, "latitude": 18.5212},
            "destination": {"longitude": 73.8740, "latitude": 18.5285},
            "vehicle": random.choice(["car", "two_wheeler", "auto"]),
        }
        self.client.post("/v1/routes/compare", json=payload, name="POST /v1/routes/compare")

    @task(2)
    def check_travel_advice(self):
        v = random.choice(["car", "two_wheeler", "auto"])
        self.client.get(f"/v1/travel-advice?vehicle={v}", name="GET /v1/travel-advice")


class CitizenReporterUser(HttpUser):
    """Submits hazard reports from the field."""
    weight = 15
    wait_time = between(3, 8)

    def on_start(self):
        self.fingerprint = f"device-{uuid4().hex[:8]}"

    @task(2)
    def submit_report(self):
        payload = {
            "report_type": random.choice(["waterlogging", "blocked_drain", "manhole_overflow"]),
            "severity": random.randint(2, 5),
            "longitude": 73.8567 + random.uniform(-0.02, 0.02),
            "latitude": 18.5204 + random.uniform(-0.02, 0.02),
            "description": "Localized water accumulation on street",
            "reporter_fingerprint": self.fingerprint,
        }
        self.client.post("/v1/reports", json=payload, name="POST /v1/reports")

    @task(1)
    def view_my_reports(self):
        self.client.get(
            f"/v1/reports?reporter_fingerprint={self.fingerprint}",
            name="GET /v1/reports?fingerprint",
        )


class MunicipalStaffUser(HttpUser):
    """Staff triage workflow: login, inspect hotspots, review reports, create work orders."""
    weight = 5
    wait_time = between(3, 6)

    def on_start(self):
        res = self.client.post(
            "/v1/municipal/login",
            json={"email": "staff@pune.gov.in", "password": "change-before-deployment"},
            name="POST /v1/municipal/login",
        )
        if res.status_code == 200:
            token = res.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            self.headers = {}

    @task(2)
    def view_reports(self):
        self.client.get("/v1/municipal/reports", headers=self.headers, name="GET /v1/municipal/reports")

    @task(1)
    def view_hotspots(self):
        self.client.get("/v1/municipal/hotspots", headers=self.headers, name="GET /v1/municipal/hotspots")

    @task(1)
    def view_drain_flags(self):
        self.client.get(
            "/v1/municipal/drain-failure-flags",
            headers=self.headers,
            name="GET /v1/municipal/drain-failure-flags",
        )

    @task(1)
    def view_work_orders(self):
        self.client.get("/v1/municipal/work-orders", headers=self.headers, name="GET /v1/municipal/work-orders")
