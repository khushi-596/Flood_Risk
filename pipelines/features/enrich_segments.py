"""Attach Day 1 terrain and drainage features to extracted road segments.

The calculations use a local elevation raster and drainage layer. They are CPU-only;
the resulting signals are inputs to the transparent baseline risk engine.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich road segments with terrain and drainage features.")
    parser.add_argument("--segments", required=True, type=Path)
    parser.add_argument("--dem", required=True, type=Path, help="Elevation raster, ideally in metres.")
    parser.add_argument("--drains", required=True, type=Path, help="Drain, stream, or waterway layer.")
    parser.add_argument("--output", type=Path, default=Path("data/processed/segments_with_features.geojson"))
    return parser.parse_args()


def min_max(values: np.ndarray, invert: bool = False) -> np.ndarray:
    finite = np.isfinite(values)
    if not finite.any():
        return np.zeros(len(values))
    low, high = np.nanpercentile(values[finite], (5, 95))
    if high <= low:
        scaled = np.zeros(len(values))
    else:
        scaled = np.clip((values - low) / (high - low), 0, 1)
    scaled[~finite] = 0
    return 1 - scaled if invert else scaled


def main() -> None:
    args = parse_args()
    segments = gpd.read_file(args.segments)
    drains = gpd.read_file(args.drains)
    if segments.empty:
        raise ValueError("The segment layer is empty.")

    with rasterio.open(args.dem) as dataset:
        target_crs = dataset.crs
        sampling = segments.to_crs(target_crs)
        centroids = sampling.geometry.centroid
        start_points = sampling.geometry.interpolate(0, normalized=True)
        end_points = sampling.geometry.interpolate(1, normalized=True)

        def sample(points: gpd.GeoSeries) -> np.ndarray:
            values = np.array([item[0] for item in dataset.sample([(point.x, point.y) for point in points])])
            values = values.astype(float)
            if dataset.nodata is not None:
                values[np.isclose(values, dataset.nodata)] = np.nan
            return values

        elevation = sample(centroids)
        endpoint_difference = np.abs(sample(start_points) - sample(end_points))

    metric_segments = segments.to_crs(3857)
    metric_drains = drains.to_crs(3857)
    nearest = gpd.sjoin_nearest(
        metric_segments[["segment_id", "geometry"]], metric_drains[["geometry"]], how="left", distance_col="distance_to_drain_m"
    )
    nearest = nearest.drop_duplicates(subset="segment_id").set_index("segment_id")
    segments = segments.set_index("segment_id")
    segments["elevation_m"] = elevation
    segments["slope_proxy_m"] = endpoint_difference
    segments["distance_to_drain_m"] = nearest["distance_to_drain_m"]
    segments["low_elevation_signal"] = min_max(elevation, invert=True)
    # Standing water is more likely where roads are flatter; this is a proxy pending DEM-grade calculation.
    segments["flatness_signal"] = min_max(endpoint_difference, invert=True)
    segments["drainage_proximity_signal"] = min_max(segments["distance_to_drain_m"].to_numpy(), invert=True)
    segments = segments.reset_index()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    segments.to_file(args.output, driver="GeoJSON")
    print(f"Wrote enriched features for {len(segments):,} segments to {args.output}")


if __name__ == "__main__":
    main()
