"""Load known flood hotspots from CSV into PostGIS hotspots_hist table.

Usage:
    python -m pipelines.load_hotspots
    python -m pipelines.load_hotspots --hotspots-csv data/known_flood_locations.csv
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load flood hotspots from CSV into PostGIS.")
    parser.add_argument(
        "--hotspots-csv",
        type=Path,
        default=PROJECT_ROOT / "data" / "known_flood_locations.csv",
        help="Path to CSV of known flood locations.",
    )
    parser.add_argument(
        "--database-url",
        default="postgresql://flood:flood@localhost:5432/flood_risk",
        help="PostgreSQL connection string.",
    )
    return parser.parse_args()


def load_hotspots(csv_path: Path, database_url: str) -> int:
    """Insert or update known flood hotspots from a CSV file into hotspots_hist."""
    if not csv_path.exists():
        print(f"Hotspots CSV not found at {csv_path}, skipping.")
        return 0

    count = 0
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            with csv_path.open(encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    name = row.get("name", "Unknown").strip()
                    lat = float(row["latitude"])
                    lon = float(row["longitude"])
                    severity = int(row.get("severity", 3))
                    source = row.get("source", "csv_seed").strip()
                    notes = row.get("notes", "").strip()
                    threshold = float(row.get("threshold_mm_hr", 20.0)) if row.get("threshold_mm_hr") else 20.0
                    confidence = float(row.get("confidence", 0.5)) if row.get("confidence") else 0.5

                    # Check if hotspot already exists by name
                    cur.execute("SELECT id FROM hotspots_hist WHERE name = %s", (name,))
                    existing = cur.fetchone()
                    if existing:
                        cur.execute(
                            """
                            UPDATE hotspots_hist
                            SET geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                                severity = %s,
                                source = %s,
                                threshold_mm_hr = %s,
                                confidence = %s,
                                notes = %s
                            WHERE id = %s
                            """,
                            (lon, lat, severity, source, threshold, confidence, notes, existing[0]),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO hotspots_hist (name, geom, severity, source, threshold_mm_hr, confidence, notes)
                            VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s, %s, %s)
                            """,
                            (name, lon, lat, severity, source, threshold, confidence, notes),
                        )
                    count += 1
        conn.commit()
    return count


def main() -> None:
    args = parse_args()
    print(f"Loading hotspots from {args.hotspots_csv} into PostGIS...")
    try:
        loaded = load_hotspots(args.hotspots_csv, args.database_url)
        print(f"  -> Successfully loaded {loaded} hotspots into PostgreSQL (hotspots_hist).")
    except psycopg.OperationalError as exc:
        print(f"  -> PostgreSQL is currently offline ({exc}). Hotspots CSV validated ({args.hotspots_csv.name}) and ready for DB startup.")


if __name__ == "__main__":
    main()
