/* eslint-disable @typescript-eslint/no-explicit-any */

/**
 * Standard Google Maps raster style configurations for MapLibre GL.
 * Provides crisp Google Maps Street, Satellite Hybrid, and Terrain tiles for Pune navigation.
 */

export type MapLayerStyleKey = "streets" | "satellite" | "terrain";

export const GOOGLE_MAPS_STREETS_STYLE: any = {
  version: 8,
  name: "Google Maps Streets",
  sources: {
    "google-streets-tiles": {
      type: "raster",
      tiles: [
        "https://mt0.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        "https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        "https://mt2.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
        "https://mt3.google.com/vt/lyrs=m&x={x}&y={y}&z={z}",
      ],
      tileSize: 256,
      attribution: "&copy; Google Maps",
      maxzoom: 21,
    },
  },
  layers: [
    {
      id: "google-streets-layer",
      type: "raster",
      source: "google-streets-tiles",
      minzoom: 0,
      maxzoom: 21,
    },
  ],
};

export const GOOGLE_MAPS_SATELLITE_STYLE: any = {
  version: 8,
  name: "Google Maps Satellite Hybrid",
  sources: {
    "google-satellite-tiles": {
      type: "raster",
      tiles: [
        "https://mt0.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        "https://mt2.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        "https://mt3.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
      ],
      tileSize: 256,
      attribution: "&copy; Google Maps Satellite",
      maxzoom: 21,
    },
  },
  layers: [
    {
      id: "google-satellite-layer",
      type: "raster",
      source: "google-satellite-tiles",
      minzoom: 0,
      maxzoom: 21,
    },
  ],
};

export const GOOGLE_MAPS_TERRAIN_STYLE: any = {
  version: 8,
  name: "Google Maps Terrain",
  sources: {
    "google-terrain-tiles": {
      type: "raster",
      tiles: [
        "https://mt0.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
        "https://mt1.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
        "https://mt2.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
        "https://mt3.google.com/vt/lyrs=p&x={x}&y={y}&z={z}",
      ],
      tileSize: 256,
      attribution: "&copy; Google Maps Terrain",
      maxzoom: 21,
    },
  },
  layers: [
    {
      id: "google-terrain-layer",
      type: "raster",
      source: "google-terrain-tiles",
      minzoom: 0,
      maxzoom: 21,
    },
  ],
};

export function getMapStyle(key: MapLayerStyleKey = "streets"): any {
  switch (key) {
    case "satellite":
      return GOOGLE_MAPS_SATELLITE_STYLE;
    case "terrain":
      return GOOGLE_MAPS_TERRAIN_STYLE;
    case "streets":
    default:
      return GOOGLE_MAPS_STREETS_STYLE;
  }
}
