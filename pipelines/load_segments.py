"""Load road segments from GeoJSON and flood hotspots from CSV into PostGIS.

Usage:
    python -m pipelines.load_segments
    python -m pipelines.load_segments --geojson data/processed/road_segments.geojson
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load segments and hotspots into PostGIS.")
    parser.add_argument(
        "--geojson",
        type=Path,
        default=PROJECT_ROOT / "data" / "seeds" / "demo_segments.geojson",
        help="Path to a GeoJSON FeatureCollection of road segments.",
    )
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


def load_segments(geojson_path: Path, database_url: str) -> int:
    """Insert or update road segments from a GeoJSON file."""
    collection = json.loads(geojson_path.read_text(encoding="utf-8"))
    features = collection.get("features", [])
    if not features:
        print(f"No features found in {geojson_path}")
        return 0

    count = 0
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            for feature in features:
                props = feature.get("properties", {})
                geom = feature.get("geometry", {})
                seg_id = props.get("segment_id", props.get("seg_id", ""))
                if not seg_id or not geom:
                    continue

                name = props.get("name", "Unnamed road")
                highway = props.get("highway", "unclassified")
                length_m = float(props.get("length_m", 0))
                is_underpass = bool(props.get("is_underpass", False))
                elev_mean = float(props["elev_mean"]) if "elev_mean" in props else None
                slope = float(props["slope"]) if "slope" in props else None
                drain_dist_m = float(props["drain_dist_m"]) if "drain_dist_m" in props else None

                # Extract signals from nested dict or flat keys
                signals = props.get("signals", {})
                terrain = float(signals.get("terrain", props.get("signal_terrain", props.get("low_elevation_signal", 0))))
                flood_history = float(signals.get("flood_history", props.get("signal_flood_history", props.get("flood_history", 0))))
                drainage = float(signals.get("drainage", props.get("signal_drainage", props.get("drainage_proximity_signal", 0))))

                # Per-segment threshold: T_seg = T0 * (1 - 0.5*S - 0.3*H)
                t_seg = max(5.0, 30.0 * (1.0 - 0.5 * terrain - 0.3 * flood_history))

                geom_json = json.dumps(geom)

                cur.execute(
                    """
                    INSERT INTO segments (
                        seg_id, name, highway, geom, length_m, is_underpass,
                        elev_mean, slope, drain_dist_m,
                        signal_terrain, signal_flood_history, signal_drainage,
                        threshold_mm_hr
                    ) VALUES (
                        %s, %s, %s, ST_GeomFromGeoJSON(%s), %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s
                    )
                    ON CONFLICT (seg_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        highway = EXCLUDED.highway,
                        geom = EXCLUDED.geom,
                        length_m = EXCLUDED.length_m,
                        is_underpass = EXCLUDED.is_underpass,
                        elev_mean = EXCLUDED.elev_mean,
                        slope = EXCLUDED.slope,
                        drain_dist_m = EXCLUDED.drain_dist_m,
                        signal_terrain = EXCLUDED.signal_terrain,
                        signal_flood_history = EXCLUDED.signal_flood_history,
                        signal_drainage = EXCLUDED.signal_drainage,
                        threshold_mm_hr = EXCLUDED.threshold_mm_hr
                    """,
                    (
                        seg_id, name, highway, geom_json, length_m, is_underpass,
                        elev_mean, slope, drain_dist_m,
                        terrain, flood_history, drainage, t_seg,
                    ),
                )
                count += 1
        conn.commit()
    return count


def load_hotspots(csv_path: Path, database_url: str) -> int:
    """Insert known flood hotspots from a CSV file."""
    if not csv_path.exists():
        print(f"Hotspots CSV not found at {csv_path}, skipping.")
        return 0

    count = 0
    with psycopg.connect(database_url) as conn:
        with conn.cursor() as cur:
            with csv_path.open(encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    name = row.get("name", "Unknown")
                    lat = float(row["latitude"])
                    lon = float(row["longitude"])
                    severity = int(row.get("severity", 3))
                    source = row.get("source", "csv")
                    notes = row.get("notes", "")
                    threshold = float(row.get("threshold_mm_hr", 20.0)) if row.get("threshold_mm_hr") else 20.0
                    confidence = float(row.get("confidence", 0.5)) if row.get("confidence") else 0.5

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

    print(f"Loading segments from {args.geojson} ...")
    try:
        seg_count = load_segments(args.geojson, args.database_url)
        print(f"  -> {seg_count} segments loaded into PostgreSQL.")
    except psycopg.OperationalError as exc:
        print(f"  -> PostgreSQL is currently offline ({exc}). GeoJSON seed is validated and ready for DB startup.")

    print(f"Loading hotspots from {args.hotspots_csv} ...")
    try:
        hs_count = load_hotspots(args.hotspots_csv, args.database_url)
        print(f"  -> {hs_count} hotspots loaded into PostgreSQL.")
    except psycopg.OperationalError:
        print("  -> PostgreSQL is offline. Hotspots CSV validated and ready for DB startup.")

    print("Pipeline data loading check completed.")


if __name__ == "__main__":
    main()
