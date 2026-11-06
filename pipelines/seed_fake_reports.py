"""Seed generator for realistic crowdsourced flood and hazard reports.

Generates realistic citizen reports with:
- Spatially clustered reports around known Pune flood hotspots to test auto-verification
- Distinct device fingerprints
- Hazard classifications: waterlogging, blocked_drain, flood, pothole
- Plausible timestamps spanning the last 2-4 hours
- Direct insertion into PostgreSQL or export to JSON

Usage:
    python -m pipelines.seed_fake_reports
    python -m pipelines.seed_fake_reports --count 60 --export data/seeds/fake_reports.json
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REPORT_TYPES = ["waterlogging", "blocked_drain", "flood", "pothole"]

SAMPLE_DESCRIPTIONS = {
    "waterlogging": [
        "Water level reached above knee height, slow traffic.",
        "Underpass completely submerged, cars turning back.",
        "Severe water accumulation near junction, two-wheelers slipping.",
        "Water stagnating for past 45 minutes, half foot deep.",
        "Road partially inundated on left lane, causing bottleneck.",
    ],
    "blocked_drain": [
        "Stormwater drain choked with plastic and construction debris.",
        "Manhole overflowing with muddy water onto pedestrian path.",
        "Drain grate blocked by fallen leaves, water spilling into lane.",
        "Culvert entrance clogged, storm water backing up on road.",
    ],
    "flood": [
        "River backwater entering main approach road.",
        "Nallah overflowing into residential street, strong current.",
        "Flash flood conditions near bridge ramp after cloudburst.",
    ],
    "pothole": [
        "Large submerged pothole hidden under water, hazard for bikes.",
        "Deep crater formed after water receded near intersection.",
        "Road surface eroded with multiple open trenches.",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate realistic citizen hazard reports.")
    parser.add_argument("--count", type=int, default=50, help="Number of reports to generate.")
    parser.add_argument(
        "--hotspots-csv",
        type=Path,
        default=PROJECT_ROOT / "data" / "known_flood_locations.csv",
        help="Path to CSV of known hotspots.",
    )
    parser.add_argument(
        "--database-url",
        default="postgresql://flood:flood@localhost:5432/flood_risk",
        help="PostgreSQL connection string.",
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=PROJECT_ROOT / "data" / "seeds" / "fake_reports.json",
        help="Path to export generated reports as JSON.",
    )
    parser.add_argument(
        "--insert-db",
        action="store_true",
        help="Attempt direct insertion into PostgreSQL if available.",
    )
    return parser.parse_args()


def load_hotspots(csv_path: Path) -> list[dict]:
    hotspots = []
    if csv_path.exists():
        with csv_path.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                hotspots.append({
                    "name": row.get("name", "Unknown"),
                    "lat": float(row["latitude"]),
                    "lon": float(row["longitude"]),
                    "severity": int(row.get("severity", 3)),
                })
    return hotspots


def generate_reports(count: int, hotspots: list[dict]) -> list[dict]:
    reports = []
    now = datetime.now(timezone.utc)

    # 1. First create 3 intentional auto-verification clusters (3+ reports within 100m and 20 mins)
    cluster_hotspots = random.sample(hotspots, min(3, len(hotspots)))
    for hs in cluster_hotspots:
        cluster_time = now - timedelta(minutes=random.randint(5, 25))
        for dev_idx in range(1, 4):
            # slight jitter within 50m (~0.00045 degrees)
            lat = hs["lat"] + random.uniform(-0.0003, 0.0003)
            lon = hs["lon"] + random.uniform(-0.0003, 0.0003)
            reports.append({
                "id": str(uuid4()),
                "segment_id": "pune-demo-003" if "Underpass" in hs["name"] else "pune-demo-001",
                "report_type": "waterlogging",
                "severity": min(5, max(1, hs["severity"] + random.randint(-1, 1))),
                "latitude": round(lat, 5),
                "longitude": round(lon, 5),
                "description": random.choice(SAMPLE_DESCRIPTIONS["waterlogging"]),
                "photo_path": None,
                "reporter_fingerprint": f"device-cluster-{hs['name'][:6].lower()}-{dev_idx:02d}",
                "status": "pending",
                "created_at": (cluster_time + timedelta(minutes=random.randint(0, 8))).isoformat(),
            })

    # 2. Fill the remainder with diverse reports across the study zone
    devices = [f"device-citizen-{i:03d}" for i in range(1, count + 1)]
    remaining = count - len(reports)

    for i in range(remaining):
        hs = random.choice(hotspots) if hotspots else {"lat": 18.5204, "lon": 73.8567, "severity": 3}
        # scatter within 300m of a hotspot or street
        lat = hs["lat"] + random.uniform(-0.002, 0.002)
        lon = hs["lon"] + random.uniform(-0.002, 0.002)
        rtype = random.choices(REPORT_TYPES, weights=[0.45, 0.30, 0.15, 0.10])[0]
        desc = random.choice(SAMPLE_DESCRIPTIONS[rtype])
        t_delta = timedelta(minutes=random.randint(2, 240))

        reports.append({
            "id": str(uuid4()),
            "segment_id": "pune-demo-002",
            "report_type": rtype,
            "severity": min(5, max(1, hs["severity"] + random.randint(-1, 1))),
            "latitude": round(lat, 5),
            "longitude": round(lon, 5),
            "description": desc,
            "photo_path": None,
            "reporter_fingerprint": random.choice(devices),
            "status": "pending",
            "created_at": (now - t_delta).isoformat(),
        })

    return reports


def main() -> None:
    args = parse_args()
    hotspots = load_hotspots(args.hotspots_csv)
    print(f"Loaded {len(hotspots)} hotspots from {args.hotspots_csv}")

    reports = generate_reports(args.count, hotspots)
    print(f"Generated {len(reports)} realistic citizen hazard reports.")

    # Export to JSON
    args.export.parent.mkdir(parents=True, exist_ok=True)
    args.export.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    print(f"Saved reports to {args.export}")

    if args.insert_db:
        try:
            with psycopg.connect(args.database_url, connect_timeout=2) as conn:
                with conn.cursor() as cur:
                    for r in reports:
                        cur.execute(
                            """
                            INSERT INTO citizen_reports (
                                id, segment_id, report_type, severity, longitude, latitude,
                                description, reporter_fingerprint, status, created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (id) DO NOTHING
                            """,
                            (
                                r["id"], r["segment_id"], r["report_type"], r["severity"],
                                r["longitude"], r["latitude"], r["description"],
                                r["reporter_fingerprint"], r["status"], r["created_at"], r["created_at"]
                            )
                        )
                conn.commit()
            print(f"Successfully inserted {len(reports)} reports into PostgreSQL.")
        except Exception as e:
            print(f"Database insertion skipped or failed: {e}")


if __name__ == "__main__":
    main()
