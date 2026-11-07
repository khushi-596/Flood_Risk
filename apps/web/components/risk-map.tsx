"use client";

import { useMemo, useRef, useState } from "react";
import Map, { Layer, Marker, NavigationControl, Popup, Source, type MapLayerMouseEvent } from "react-map-gl/maplibre";

import { useAppStore } from "@/lib/store";
import type { MapPoint, RoadCollection, RoadFeature, RouteOption, SegmentProperties } from "@/lib/types";
import { CrosshairIcon } from "@/components/icons";
import { getMapStyle, type MapLayerStyleKey } from "@/lib/map-styles";

type Props = {
  roads: RoadCollection;
  origin: MapPoint | null;
  destination: MapPoint | null;
  routes: RouteOption[];
  onPointSelect: (point: MapPoint) => void;
  onSegmentSelect: (segmentId: string) => void;
};

/* eslint-disable @typescript-eslint/no-explicit-any */
const riskLineLayer: any = {
  id: "risk-segments",
  type: "line",
  paint: {
    "line-color": [
      "match",
      ["get", "risk_band"],
      "low", "#2563eb",
      "moderate", "#d97706",
      "high", "#9333ea",
      "severe", "#be123c",
      "#64748b",
    ],
    "line-width": ["interpolate", ["linear"], ["zoom"], 11, 4.5, 15, 9.5],
    "line-opacity": 0.92,
  },
};
/* eslint-enable @typescript-eslint/no-explicit-any */

const routeStyles: Record<string, { color: string; width: number; dash: number[] }> = {
  fast: { color: "#e11d48", width: 5.5, dash: [1, 0] },
  safe: { color: "#047857", width: 7.5, dash: [1, 0] },
  balanced: { color: "#0284c7", width: 5.5, dash: [2, 1.5] },
};

function isRoadFeature(feature: unknown): feature is RoadFeature {
  return Boolean(
    feature &&
      typeof feature === "object" &&
      "properties" in feature &&
      (feature as RoadFeature).properties?.segment_id
  );
}

const bandLabel: Record<string, string> = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  severe: "Severe",
};

export function RiskMap({ roads, origin, destination, routes, onPointSelect, onSegmentSelect }: Props) {
  const [selectedRoad, setSelectedRoad] = useState<SegmentProperties | null>(null);
  const [popupPoint, setPopupPoint] = useState<MapPoint | null>(null);
  const [mapStyleKey, setMapStyleKey] = useState<MapLayerStyleKey>("streets");
  const mapRef = useRef<any>(null);
  const initialViewState = useMemo(() => ({ longitude: 73.8567, latitude: 18.5204, zoom: 12.5 }), []);

  const selectedRouteId = useAppStore((s) => s.selectedRouteId) as string | null;
  const selectionMode = useAppStore((s) => s.selectionMode) as "origin" | "destination";
  const setSelectionMode = useAppStore((s) => s.setSelectionMode) as (m: "origin" | "destination") => void;

  function handleClick(event: MapLayerMouseEvent) {
    const point = { longitude: event.lngLat.lng, latitude: event.lngLat.lat, label: "Map Pin" };
    const feature = event.features?.[0];
    if (isRoadFeature(feature)) {
      setSelectedRoad(feature.properties);
      setPopupPoint(point);
      onSegmentSelect(feature.properties.segment_id);
    }
    onPointSelect(point);
  }

  function handleResetView() {
    if (mapRef.current) {
      mapRef.current.flyTo({ center: [73.8567, 18.5204], zoom: 12.5, duration: 1000 });
    }
  }

  return (
    <div className="relative h-[66vh] min-h-[500px] overflow-hidden rounded-3xl border border-slate-200/90 bg-slate-100 shadow-elevated">
      {/* Top Floating Map Controls Pill */}
      <div className="absolute left-3 top-3 z-10 flex flex-wrap items-center gap-2">
        <div className="glass-card flex items-center gap-1.5 px-3 py-1.5 shadow-sm text-xs font-semibold text-slate-800">
          <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Click map sets:</span>
          <button
            type="button"
            onClick={() => setSelectionMode("origin")}
            className={`rounded-lg px-2 py-0.5 text-[11px] font-bold transition ${
              selectionMode === "origin"
                ? "bg-emerald-600 text-white shadow-xs"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            Start (A)
          </button>
          <button
            type="button"
            onClick={() => setSelectionMode("destination")}
            className={`rounded-lg px-2 py-0.5 text-[11px] font-bold transition ${
              selectionMode === "destination"
                ? "bg-rose-600 text-white shadow-xs"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            End (B)
          </button>
        </div>

        <button
          type="button"
          onClick={handleResetView}
          title="Reset map view to Pune center"
          className="glass-card flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:text-sky-900 transition shadow-sm hover:shadow"
        >
          <CrosshairIcon size={14} className="text-slate-600" />
          <span className="hidden sm:inline">Center Pune</span>
        </button>
      </div>

      {/* Top Right Floating Map Style Switcher (Google Maps Style Switcher) */}
      <div className="absolute right-3 top-3 z-10 hidden sm:flex items-center gap-1 glass-card p-1 shadow-sm">
        <button
          type="button"
          onClick={() => setMapStyleKey("streets")}
          className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition ${
            mapStyleKey === "streets"
              ? "bg-slate-900 text-white shadow-xs"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Google Map
        </button>
        <button
          type="button"
          onClick={() => setMapStyleKey("satellite")}
          className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition ${
            mapStyleKey === "satellite"
              ? "bg-slate-900 text-white shadow-xs"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Satellite
        </button>
        <button
          type="button"
          onClick={() => setMapStyleKey("terrain")}
          className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition ${
            mapStyleKey === "terrain"
              ? "bg-slate-900 text-white shadow-xs"
              : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Terrain
        </button>
      </div>

      <Map
        ref={mapRef}
        initialViewState={initialViewState}
        interactiveLayerIds={[riskLineLayer.id]}
        mapStyle={getMapStyle(mapStyleKey)}
        onClick={handleClick}
        style={{ height: "100%", width: "100%" }}
      >
        <NavigationControl position="bottom-right" />

        {/* Road segments layer */}
        <Source data={roads} id="roads" type="geojson">
          <Layer {...riskLineLayer} />
        </Source>

        {/* Route lines */}
        {routes.map((route) => {
          const style = routeStyles[route.id] ?? routeStyles.fast;
          const isSelected = selectedRouteId === route.id;
          return (
            <Source data={route.geometry} id={`route-${route.id}`} key={route.id} type="geojson">
              <Layer
                id={`route-line-${route.id}`}
                type="line"
                paint={{
                  "line-color": style.color,
                  "line-width": isSelected ? style.width + 3 : style.width,
                  "line-opacity": isSelected ? 1 : 0.72,
                  "line-dasharray": style.dash,
                }}
              />
            </Source>
          );
        })}

        {/* Origin marker (A) */}
        {origin && (
          <Marker anchor="bottom" latitude={origin.latitude} longitude={origin.longitude}>
            <div className="animate-scale-in flex flex-col items-center">
              <span className="rounded-md bg-emerald-950/90 backdrop-blur-xs px-2 py-0.5 text-[10px] font-bold text-white shadow-md border border-emerald-400/40">
                A: {origin.label ? origin.label.slice(0, 16) : "Start"}
              </span>
              <div className="relative flex h-8 w-8 items-center justify-center rounded-full bg-emerald-600 text-xs font-black text-white shadow-xl ring-2 ring-white">
                A
                <span className="absolute -inset-1 rounded-full bg-emerald-400 opacity-40 animate-ping -z-10" />
              </div>
            </div>
          </Marker>
        )}

        {/* Destination marker (B) */}
        {destination && (
          <Marker anchor="bottom" latitude={destination.latitude} longitude={destination.longitude}>
            <div className="animate-scale-in flex flex-col items-center">
              <span className="rounded-md bg-rose-950/90 backdrop-blur-xs px-2 py-0.5 text-[10px] font-bold text-white shadow-md border border-rose-400/40">
                B: {destination.label ? destination.label.slice(0, 16) : "Dest"}
              </span>
              <div className="relative flex h-8 w-8 items-center justify-center rounded-full bg-rose-600 text-xs font-black text-white shadow-xl ring-2 ring-white">
                B
                <span className="absolute -inset-1 rounded-full bg-rose-400 opacity-40 animate-ping -z-10" />
              </div>
            </div>
          </Marker>
        )}

        {/* Segment popup */}
        {selectedRoad && popupPoint && (
          <Popup
            anchor="bottom"
            closeButton
            onClose={() => setSelectedRoad(null)}
            longitude={popupPoint.longitude}
            latitude={popupPoint.latitude}
          >
            <div className="min-w-[210px] p-0.5">
              <p className="text-sm font-extrabold text-slate-900 leading-tight">{selectedRoad.name}</p>
              <div className="mt-2 flex items-center justify-between gap-2">
                <span
                  className={`badge ${
                    selectedRoad.risk_band === "low"
                      ? "badge-low"
                      : selectedRoad.risk_band === "moderate"
                      ? "badge-moderate"
                      : selectedRoad.risk_band === "high"
                      ? "badge-high"
                      : "badge-severe"
                  }`}
                >
                  {bandLabel[selectedRoad.risk_band] ?? selectedRoad.risk_band}
                </span>
                <span className="text-xs font-black text-slate-800">
                  {Math.round(selectedRoad.risk_score * 100)}% Risk
                </span>
              </div>
              <p className="mt-2 text-[11px] text-slate-500 font-medium">
                Click road segment to see factor contributions in details panel
              </p>
            </div>
          </Popup>
        )}
      </Map>
    </div>
  );
}
