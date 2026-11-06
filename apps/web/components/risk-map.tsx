"use client";

import { useMemo, useState } from "react";
import Map, { Layer, Marker, NavigationControl, Popup, Source, type MapLayerMouseEvent } from "react-map-gl/maplibre";

import type { MapPoint, RoadCollection, RoadFeature, RouteOption, SegmentProperties } from "@/lib/types";

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
    "line-width": ["interpolate", ["linear"], ["zoom"], 11, 4, 15, 9],
    "line-opacity": 0.92,
  },
};
/* eslint-enable @typescript-eslint/no-explicit-any */

const routeStyles: Record<string, { color: string; width: number; dash: number[] }> = {
  fast: { color: "#e11d48", width: 5, dash: [1, 0] },
  safe: { color: "#047857", width: 7, dash: [1, 0] },
  balanced: { color: "#0369a1", width: 5, dash: [2, 1.5] },
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
  const initialViewState = useMemo(() => ({ longitude: 73.865, latitude: 18.523, zoom: 12.4 }), []);

  function handleClick(event: MapLayerMouseEvent) {
    const point = { longitude: event.lngLat.lng, latitude: event.lngLat.lat, label: "Map pin" };
    const feature = event.features?.[0];
    if (isRoadFeature(feature)) {
      setSelectedRoad(feature.properties);
      setPopupPoint(point);
      onSegmentSelect(feature.properties.segment_id);
    }
    onPointSelect(point);
  }

  return (
    <div className="h-[62vh] min-h-[460px] overflow-hidden rounded-2xl border border-slate-200 bg-slate-100 shadow-sm">
      <Map
        initialViewState={initialViewState}
        interactiveLayerIds={[riskLineLayer.id]}
        mapStyle={process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://demotiles.maplibre.org/style.json"}
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
          return (
            <Source data={route.geometry} id={`route-${route.id}`} key={route.id} type="geojson">
              <Layer
                id={`route-line-${route.id}`}
                type="line"
                paint={{
                  "line-color": style.color,
                  "line-width": style.width,
                  "line-opacity": 0.88,
                  "line-dasharray": style.dash,
                }}
              />
            </Source>
          );
        })}

        {/* Origin marker */}
        {origin && (
          <Marker anchor="bottom" latitude={origin.latitude} longitude={origin.longitude}>
            <div className="animate-scale-in flex h-8 w-8 items-center justify-center rounded-full bg-emerald-600 text-xs font-black text-white shadow-lg ring-2 ring-white">
              A
            </div>
          </Marker>
        )}

        {/* Destination marker */}
        {destination && (
          <Marker anchor="bottom" latitude={destination.latitude} longitude={destination.longitude}>
            <div className="animate-scale-in flex h-8 w-8 items-center justify-center rounded-full bg-rose-600 text-xs font-black text-white shadow-lg ring-2 ring-white">
              B
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
            <div className="min-w-[200px]">
              <p className="text-sm font-extrabold text-slate-900">{selectedRoad.name}</p>
              <div className="mt-1.5 flex items-center gap-2">
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
                <span className="text-xs font-bold text-slate-600">
                  {Math.round(selectedRoad.risk_score * 100)}% risk
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-500">
                Click the segment to see full explanation →
              </p>
            </div>
          </Popup>
        )}
      </Map>
    </div>
  );
}
