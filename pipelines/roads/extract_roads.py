"""Download and split OpenStreetMap roads into 100-300 m analysis segments.

This is a CPU-only preprocessing task. Keep the source graph in data/raw and commit
only a tiny, licensable demo seed; generated city-wide files are intentionally ignored.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from uuid import uuid4

import geopandas as gpd
import osmnx as ox
from shapely.geometry import LineString
from shapely.ops import substring


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract segmented drivable roads from OpenStreetMap.")
    parser.add_argument("--place", required=True, help='Example: "Pune, Maharashtra, India"')
    parser.add_argument("--output", type=Path, default=Path("data/processed/road_segments.geojson"))
    parser.add_argument("--segment-length-m", type=float, default=200, choices=range(100, 301))
    parser.add_argument("--network-type", default="drive", choices=("drive", "drive_service", "all"))
    return parser.parse_args()


def split_line(line: LineString, segment_length_m: float) -> list[LineString]:
    if line.is_empty or line.length == 0:
        return []
    positions = list(range(0, int(line.length), int(segment_length_m)))
    return [
        piece
        for start in positions
        if (piece := substring(line, start, min(start + segment_length_m, line.length))).length > 0
    ]


def main() -> None:
    args = parse_args()
    print(f"Downloading {args.network_type} roads for {args.place!r}…")
    graph = ox.graph_from_place(args.place, network_type=args.network_type, simplify=True)
    _, edges = ox.graph_to_gdfs(graph, nodes=True, edges=True, fill_edge_geometry=True)
    projected = ox.project_gdf(edges.reset_index())

    records: list[dict] = []
    for _, edge in projected.iterrows():
        geometry = edge.geometry
        lines = list(geometry.geoms) if geometry.geom_type == "MultiLineString" else [geometry]
        for line in lines:
            for index, piece in enumerate(split_line(line, args.segment_length_m)):
                records.append(
                    {
                        "segment_id": f"osm-{uuid4().hex[:12]}",
                        "osm_u": str(edge.get("u", "")),
                        "osm_v": str(edge.get("v", "")),
                        "osm_key": int(edge.get("key", 0)),
                        "name": edge.get("name") if isinstance(edge.get("name"), str) else "Unnamed road",
                        "highway": str(edge.get("highway", "unknown")),
                        "length_m": round(piece.length, 1),
                        "part_index": index,
                        "geometry": piece,
                    }
                )

    segments = gpd.GeoDataFrame(records, crs=projected.crs).to_crs(4326)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    segments.to_file(args.output, driver="GeoJSON")
    print(f"Wrote {len(segments):,} road segments to {args.output}")


if __name__ == "__main__":
    main()
