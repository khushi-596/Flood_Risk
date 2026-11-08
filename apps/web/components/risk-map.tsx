"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Map, { Layer, Marker, NavigationControl, Popup, Source, type MapLayerMouseEvent } from "react-map-gl/maplibre";
import { toast } from "sonner";

import { useAppStore } from "@/lib/store";
import { compareRoutes, getEmergencyFacilities } from "@/lib/api";
import type { EmergencyFacility, MapPoint, RoadCollection, RoadFeature, RouteOption, SegmentProperties, VehicleType } from "@/lib/types";
import { CrosshairIcon, HospitalIcon, ShelterIcon, PhoneIcon, NavigationIcon } from "@/components/icons";
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
      "low", "#10b981",       // Green -> Low Risk
      "moderate", "#f59e0b",  // Yellow/Orange -> Moderate Risk
      "high", "#ef4444",      // Red -> High Risk
      "severe", "#b91c1c",    // Dark Crimson -> Severe / Impassable
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

function calcDistanceKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const R = 6371; // km
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c * 10) / 10;
}

export function RiskMap({ roads, origin, destination, routes, onPointSelect, onSegmentSelect }: Props) {
  const [selectedRoad, setSelectedRoad] = useState<SegmentProperties | null>(null);
  const [popupPoint, setPopupPoint] = useState<MapPoint | null>(null);
  const [mapStyleKey, setMapStyleKey] = useState<MapLayerStyleKey>("streets");
  const [showRoads, setShowRoads] = useState(true);
  const [showFacilities, setShowFacilities] = useState(true);
  const [facilityFilter, setFacilityFilter] = useState<"all" | "hospital" | "shelter">("all");
  const [facilities, setFacilities] = useState<EmergencyFacility[]>([]);
  const [selectedFacility, setSelectedFacility] = useState<EmergencyFacility | null>(null);
  const [cursor, setCursor] = useState<string>("auto");
  const [showDirections, setShowDirections] = useState(false);

  const mapRef = useRef<any>(null);
  const initialViewState = useMemo(() => ({ longitude: 73.8567, latitude: 18.5204, zoom: 12.5 }), []);

  const selectedRouteId = useAppStore((s) => s.selectedRouteId) as string | null;
  const selectionMode = useAppStore((s) => s.selectionMode) as "origin" | "destination";
  const setSelectionMode = useAppStore((s) => s.setSelectionMode) as (m: "origin" | "destination") => void;
  const setOrigin = useAppStore((s) => s.setOrigin) as (p: MapPoint | null) => void;
  const setDestination = useAppStore((s) => s.setDestination) as (p: MapPoint | null) => void;
  const setRouteResult = useAppStore((s) => s.setRouteResult) as (r: any) => void;
  const setSelectedRouteId = useAppStore((s) => s.setSelectedRouteId) as (id: string | null) => void;
  const vehicle = useAppStore((s) => s.vehicle) as VehicleType;

  // Load emergency facilities on mount
  useEffect(() => {
    getEmergencyFacilities()
      .then(setFacilities)
      .catch(() => {});
  }, []);

  // Auto-fit map to route bounds whenever routes change or selected route changes
  useEffect(() => {
    if (!mapRef.current || routes.length === 0) return;
    const activeRoute = routes.find((r) => r.id === selectedRouteId) ?? routes[0];
    if (!activeRoute) return;
    const coords = activeRoute.geometry?.coordinates ?? [];
    if (coords.length < 2) return;

    let minLng = Infinity, maxLng = -Infinity, minLat = Infinity, maxLat = -Infinity;
    for (const [lng, lat] of coords) {
      if (lng < minLng) minLng = lng;
      if (lng > maxLng) maxLng = lng;
      if (lat < minLat) minLat = lat;
      if (lat > maxLat) maxLat = lat;
    }
    // Pad slightly so markers at A/B don't get clipped
    const padLng = Math.max(0.004, (maxLng - minLng) * 0.25);
    const padLat = Math.max(0.004, (maxLat - minLat) * 0.30);
    mapRef.current.fitBounds(
      [[minLng - padLng, minLat - padLat], [maxLng + padLng, maxLat + padLat]],
      { duration: 900, padding: 60 }
    );

    // Auto-open directions panel when routes first arrive
    if (activeRoute.steps && activeRoute.steps.length > 0) {
      setShowDirections(true);
    }
  }, [routes, selectedRouteId]);

  const filteredFacilities = useMemo(() => {
    if (!showFacilities) return [];
    if (facilityFilter === "all") return facilities;
    return facilities.filter((f) => f.type === facilityFilter);
  }, [facilities, showFacilities, facilityFilter]);

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

  function handleLocateGps() {
    if (!navigator.geolocation) {
      toast.error("Geolocation is not supported by your browser");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const pt: MapPoint = {
          label: "My GPS Location",
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
        };
        setOrigin(pt);
        if (mapRef.current) {
          mapRef.current.flyTo({ center: [pt.longitude, pt.latitude], zoom: 14.5, duration: 1200 });
        }
        toast.success("Start point (A) snapped to current GPS");
      },
      (err) => toast.error(`GPS Error: ${err.message}`),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }

  function handleFlyToFacility(fac: EmergencyFacility) {
    setSelectedFacility(fac);
    if (mapRef.current) {
      mapRef.current.flyTo({ center: [fac.longitude, fac.latitude], zoom: 14.8, duration: 900 });
    }
  }

  async function handleNavigateToFacility(fac: EmergencyFacility) {
    const destPoint: MapPoint = {
      label: fac.name,
      latitude: fac.latitude,
      longitude: fac.longitude,
    };
    setDestination(destPoint);
    setSelectedFacility(null);

    if (origin) {
      toast.info(`Calculating safe route to ${fac.name}…`);
      try {
        const res = await compareRoutes(origin, destPoint, vehicle);
        setRouteResult(res);
        const safe = res.routes.find((r) => r.id === "safe") ?? res.routes[0];
        if (safe) setSelectedRouteId(safe.id);
        toast.success(`Safe corridor route planned to ${fac.name}!`);
      } catch (err) {
        toast.error("Destination set. Click 'Find Safe Route' to compute path.");
      }
    } else {
      setSelectionMode("origin");
      toast.success(`Destination set to ${fac.name}. Now select your starting point!`);
    }
  }

  return (
    <div className="relative h-[68vh] min-h-[520px] overflow-hidden rounded-3xl border border-slate-200/90 bg-slate-100 shadow-elevated">
      {/* Top Floating Map Controls Pill */}
      <div className="absolute left-3 top-3 z-10 flex flex-wrap items-center gap-2 max-w-[calc(100%-180px)]">
        {/* Selection Mode Pill */}
        <div className="glass-card flex items-center gap-1.5 px-3 py-1.5 shadow-sm text-xs font-semibold text-slate-800">
          <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="hidden sm:inline">Click sets:</span>
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

        {/* Emergency Layer Filter Pill (Feature A6) */}
        <div className="glass-card flex items-center gap-1 p-1 shadow-sm text-xs font-semibold">
          <button
            type="button"
            onClick={() => setShowFacilities(!showFacilities)}
            title="Toggle Emergency Havens & Hospitals layer"
            className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[11px] font-bold transition ${
              showFacilities ? "bg-rose-600 text-white shadow-xs" : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            <HospitalIcon size={12} className={showFacilities ? "text-white" : "text-rose-600"} />
            <span>Emergency POIs</span>
          </button>

          {showFacilities && (
            <div className="flex items-center gap-0.5 pl-1 border-l border-slate-200/80">
              <button
                type="button"
                onClick={() => setFacilityFilter("all")}
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold transition ${
                  facilityFilter === "all" ? "bg-slate-900 text-white" : "text-slate-500 hover:text-slate-900"
                }`}
              >
                All ({facilities.length})
              </button>
              <button
                type="button"
                onClick={() => setFacilityFilter("hospital")}
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold transition ${
                  facilityFilter === "hospital" ? "bg-rose-700 text-white" : "text-slate-500 hover:text-rose-700"
                }`}
              >
                🏥 Hosp
              </button>
              <button
                type="button"
                onClick={() => setFacilityFilter("shelter")}
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold transition ${
                  facilityFilter === "shelter" ? "bg-emerald-700 text-white" : "text-slate-500 hover:text-emerald-700"
                }`}
              >
                🏛️ Havens
              </button>
            </div>
          )}
        </div>

        {/* Locate GPS Button */}
        <button
          type="button"
          onClick={handleLocateGps}
          title="Snap to current GPS coordinates"
          className="glass-card flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:text-emerald-800 transition shadow-sm hover:shadow"
        >
          <CrosshairIcon size={13} className="text-emerald-600" />
          <span className="hidden md:inline">My GPS</span>
        </button>

        {/* Center Pune Button */}
        <button
          type="button"
          onClick={handleResetView}
          title="Reset map view to Pune center"
          className="glass-card flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold text-slate-700 hover:text-sky-900 transition shadow-sm hover:shadow"
        >
          <span className="hidden md:inline">Center Pune</span>
        </button>
      </div>

      {/* Top Right Floating Map Style Switcher + Directions toggle */}
      <div className="absolute right-3 top-3 z-10 hidden sm:flex items-center gap-1 glass-card p-1 shadow-sm">
        <button
          type="button"
          onClick={() => setMapStyleKey("streets")}
          className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition ${
            mapStyleKey === "streets" ? "bg-slate-900 text-white shadow-xs" : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Google Map
        </button>
        <button
          type="button"
          onClick={() => setMapStyleKey("satellite")}
          className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition ${
            mapStyleKey === "satellite" ? "bg-slate-900 text-white shadow-xs" : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Satellite
        </button>
        <button
          type="button"
          onClick={() => setMapStyleKey("terrain")}
          className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition ${
            mapStyleKey === "terrain" ? "bg-slate-900 text-white shadow-xs" : "text-slate-600 hover:text-slate-900"
          }`}
        >
          Terrain
        </button>
        {routes.length > 0 && (
          <>
            <div className="w-px h-4 bg-slate-300 mx-0.5" />
            <button
              type="button"
              onClick={() => setShowDirections((v) => !v)}
              title="Toggle turn-by-turn directions panel"
              className={`rounded-lg px-2.5 py-1 text-[11px] font-bold transition flex items-center gap-1 ${
                showDirections ? "bg-sky-700 text-white shadow-xs" : "text-slate-600 hover:text-sky-800"
              }`}
            >
              🗺 Directions
            </button>
          </>
        )}
      </div>

      {/* Floating Directions Panel (overlaid on map) */}
      {showDirections && (() => {
        const activeRoute = routes.find((r) => r.id === selectedRouteId);
        if (!activeRoute || !activeRoute.steps || activeRoute.steps.length === 0) return null;
        const style = routeStyles[activeRoute.id] ?? routeStyles.fast;
        const maneuverIcon: Record<string, string> = {
          depart: "🚦",
          arrive: "🏁",
          turn: "↩",
          "new name": "➡",
          continue: "⬆",
          roundabout: "🔄",
          fork: "⤴",
          merge: "⤵",
        };
        return (
          <div className="absolute right-3 top-14 z-10 w-[230px] max-h-[55vh] flex flex-col overflow-hidden rounded-2xl border border-slate-200/90 bg-white/97 backdrop-blur-xl shadow-elevated">
            {/* Panel header */}
            <div
              className="flex items-center justify-between gap-2 px-3 py-2.5 cursor-pointer select-none shrink-0"
              style={{ background: style.color + "15", borderBottom: `2px solid ${style.color}30` }}
              onClick={() => setShowDirections(false)}
            >
              <div>
                <p className="text-[9px] font-black uppercase tracking-wider" style={{ color: style.color }}>
                  {activeRoute.label}
                </p>
                <p className="text-[11px] font-bold text-slate-700 mt-0.5">
                  {(activeRoute.distance_m / 1000).toFixed(1)} km · {activeRoute.duration_min} min
                </p>
              </div>
              <span className="text-[10px] text-slate-400 shrink-0">✕ Close</span>
            </div>
            {/* Steps list */}
            <ol className="overflow-y-auto divide-y divide-slate-100 flex-1">
              {activeRoute.steps.map((step, idx) => (
                <li key={idx} className="flex items-start gap-2.5 px-3 py-2 hover:bg-slate-50/80 transition">
                  <span
                    className="mt-0.5 shrink-0 flex h-5 w-5 items-center justify-center rounded-full text-[11px]"
                    style={{
                      background: step.maneuver_type === "arrive" ? "#dcfce7" : step.maneuver_type === "depart" ? "#fef9c3" : "#f1f5f9",
                    }}
                  >
                    {maneuverIcon[step.maneuver_type] ?? "→"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[11px] font-semibold text-slate-800 leading-snug">{step.instruction}</p>
                    {step.distance_m > 0 && (
                      <p className="text-[9px] text-slate-400 mt-0.5">
                        {step.distance_m < 1000
                          ? `${Math.round(step.distance_m)} m`
                          : `${(step.distance_m / 1000).toFixed(1)} km`}
                        {step.duration_sec > 0 && ` · ~${Math.ceil(step.duration_sec / 60)} min`}
                      </p>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </div>
        );
      })()}

      {/* Bottom Floating Quick Havens Bar (Interactive Access) */}
      {showFacilities && facilities.length > 0 && (
        <div className="absolute left-3 bottom-3 z-10 hidden md:flex items-center gap-1.5 glass-card px-2.5 py-1.5 shadow-md max-w-[70%] overflow-x-auto">
          <span className="text-[10px] font-black uppercase tracking-wider text-rose-700 shrink-0">
            Emergency Havens:
          </span>
          <div className="flex items-center gap-1.5">
            {facilities.slice(0, 4).map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => handleFlyToFacility(f)}
                className="rounded-lg bg-white/80 hover:bg-white px-2 py-0.5 text-[10px] font-bold text-slate-700 border border-slate-200/80 hover:border-slate-300 transition shrink-0 flex items-center gap-1"
              >
                <span>{f.type === "hospital" ? "🏥" : "🏛️"}</span>
                <span className="truncate max-w-[120px]">{f.name.split(" ")[0]}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <Map
        ref={mapRef}
        initialViewState={initialViewState}
        interactiveLayerIds={showRoads ? [riskLineLayer.id] : []}
        mapStyle={getMapStyle(mapStyleKey)}
        onClick={handleClick}
        cursor={cursor}
        onMouseEnter={() => setCursor("pointer")}
        onMouseLeave={() => setCursor("auto")}
        style={{ height: "100%", width: "100%" }}
      >
        <NavigationControl position="bottom-right" />

        {/* Road segments layer */}
        {showRoads && (
          <Source data={roads} id="roads" type="geojson">
            <Layer {...riskLineLayer} />
          </Source>
        )}

        {/* Route lines */}
        {routes.map((route) => {
          const style = routeStyles[route.id] ?? routeStyles.fast;
          const isSelected = selectedRouteId === route.id;
          return (
            <Source data={route.geometry} id={`route-${route.id}`} key={route.id} type="geojson">
              {/* Background casing for selected route (white border glow) */}
              {isSelected && (
                <Layer
                  id={`route-casing-${route.id}`}
                  type="line"
                  layout={{ "line-cap": "round", "line-join": "round" }}
                  paint={{
                    "line-color": "#ffffff",
                    "line-width": style.width + 7,
                    "line-opacity": 0.65,
                    "line-blur": 2,
                  }}
                />
              )}
              <Layer
                id={`route-line-${route.id}`}
                type="line"
                layout={{ "line-cap": "round", "line-join": "round" }}
                paint={{
                  "line-color": style.color,
                  "line-width": isSelected ? style.width + 3 : style.width,
                  "line-opacity": isSelected ? 1 : 0.5,
                  "line-dasharray": style.dash,
                }}
              />
            </Source>
          );
        })}

        {/* Turn-by-turn maneuver arrow markers for selected route */}
        {(() => {
          const activeRoute = routes.find((r) => r.id === selectedRouteId);
          if (!activeRoute || !activeRoute.steps || activeRoute.steps.length === 0) return null;
          const coords = activeRoute.geometry?.coordinates ?? [];
          if (coords.length < 2) return null;

          // Map steps to coordinate positions: step i corresponds roughly to coord[i * stride]
          const stride = Math.max(1, Math.floor(coords.length / (activeRoute.steps.length + 1)));
          const maneuverEmoji: Record<string, string> = {
            depart: "🚦",
            arrive: "🏁",
            turn: "↩",
            "new name": "→",
            continue: "↑",
            roundabout: "🔄",
            fork: "⤴",
            merge: "⤵",
          };

          return activeRoute.steps.map((step, idx) => {
            if (step.maneuver_type === "depart" || step.maneuver_type === "arrive") return null;
            const coordIdx = Math.min(idx * stride, coords.length - 1);
            const [lng, lat] = coords[coordIdx];
            const emoji = maneuverEmoji[step.maneuver_type] ?? "→";
            return (
              <Marker key={`turn-${idx}`} latitude={lat} longitude={lng} anchor="center">
                <div
                  title={step.instruction}
                  className="flex items-center justify-center h-5 w-5 rounded-full bg-white border-2 border-slate-500 shadow-lg text-[9px] font-black cursor-default"
                >
                  {emoji}
                </div>
              </Marker>
            );
          });
        })()}

        {/* EMERGENCY SAFE SHELTERS & HOSPITALS MARKERS (Feature A6) */}
        {filteredFacilities.map((fac) => {
          const isHospital = fac.type === "hospital";
          const distKm = origin ? calcDistanceKm(origin.latitude, origin.longitude, fac.latitude, fac.longitude) : null;

          return (
            <Marker
              key={fac.id}
              anchor="bottom"
              latitude={fac.latitude}
              longitude={fac.longitude}
              onClick={(e) => {
                e.originalEvent.stopPropagation();
                setSelectedFacility(fac);
              }}
            >
              <div
                className="group cursor-pointer flex flex-col items-center transition-transform hover:scale-110"
                title={`${fac.name} (${isHospital ? "Hospital" : "Safe Shelter"})`}
              >
                <div
                  className={`flex h-7 w-7 items-center justify-center rounded-full text-white shadow-lg border-2 border-white transition-all ${
                    isHospital ? "bg-rose-600 group-hover:bg-rose-700" : "bg-emerald-600 group-hover:bg-emerald-700"
                  }`}
                >
                  {isHospital ? <HospitalIcon size={14} /> : <ShelterIcon size={14} />}
                </div>
                <span
                  className={`mt-0.5 rounded px-1.5 py-0.2 text-[9px] font-bold text-white shadow-xs border whitespace-nowrap ${
                    isHospital ? "bg-rose-950/85 border-rose-400/40" : "bg-emerald-950/85 border-emerald-400/40"
                  }`}
                >
                  {fac.name.split(" ")[0]} {distKm ? `• ${distKm}km` : ""}
                </span>
              </div>
            </Marker>
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

        {/* Road segment popup */}
        {selectedRoad && popupPoint && (
          <Popup
            anchor="bottom"
            closeButton
            onClose={() => setSelectedRoad(null)}
            longitude={popupPoint.longitude}
            latitude={popupPoint.latitude}
          >
            <div className="min-w-[210px] p-0.5 space-y-1.5">
              <p className="text-sm font-extrabold text-slate-900 leading-tight">{selectedRoad.name}</p>
              <div className="flex items-center justify-between gap-2">
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
                  {bandLabel[selectedRoad.risk_band] ?? selectedRoad.risk_band} Risk
                </span>
                <span className="text-xs font-black text-slate-800">
                  {Math.round(selectedRoad.risk_score * 100)}%
                </span>
              </div>
              <p className="text-[11px] text-slate-500 font-medium leading-tight">
                Click road segment to see static vulnerability &amp; physical ground factors in details panel
              </p>
            </div>
          </Popup>
        )}

        {/* EMERGENCY FACILITY POPUP (Feature A6) */}
        {selectedFacility && (
          <Popup
            anchor="bottom"
            closeButton
            onClose={() => setSelectedFacility(null)}
            longitude={selectedFacility.longitude}
            latitude={selectedFacility.latitude}
          >
            <div className="min-w-[260px] max-w-[320px] p-1 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span
                    className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-black uppercase tracking-wider ${
                      selectedFacility.type === "hospital"
                        ? "bg-rose-100 text-rose-900 border border-rose-300"
                        : "bg-emerald-100 text-emerald-900 border border-emerald-300"
                    }`}
                  >
                    {selectedFacility.type === "hospital" ? "🏥 24/7 Emergency Hospital" : "🏛️ Flood Evacuation Haven"}
                  </span>
                  <h4 className="text-sm font-black text-slate-900 leading-tight mt-1">
                    {selectedFacility.name}
                  </h4>
                </div>
              </div>

              <p className="text-[11px] text-slate-500 leading-tight">
                📍 {selectedFacility.address} ({selectedFacility.area})
              </p>

              <div className="rounded-lg bg-slate-50 p-2 text-[10px] space-y-1 border border-slate-200/60">
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 font-medium">Safe Elevation:</span>
                  <span className="font-bold text-emerald-800">
                    🛡️ {selectedFacility.elevation_masl}m ASL (High Ground)
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500 font-medium">Capacity:</span>
                  <span className="font-bold text-slate-800">{selectedFacility.capacity}</span>
                </div>
                {origin && (
                  <div className="flex items-center justify-between border-t border-slate-200/50 pt-0.5">
                    <span className="text-slate-500 font-medium">Distance from Start:</span>
                    <span className="font-bold text-sky-700">
                      {calcDistanceKm(origin.latitude, origin.longitude, selectedFacility.latitude, selectedFacility.longitude)} km away
                    </span>
                  </div>
                )}
              </div>

              {/* Services tags */}
              <div className="flex flex-wrap gap-1">
                {selectedFacility.services.slice(0, 3).map((s) => (
                  <span key={s} className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] font-semibold text-slate-700">
                    ✓ {s}
                  </span>
                ))}
              </div>

              {/* Action Buttons */}
              <div className="grid grid-cols-2 gap-1.5 pt-1 border-t border-slate-200/60">
                <a
                  href={`tel:${selectedFacility.phone.replace(/[^0-9+]/g, "")}`}
                  className="flex items-center justify-center gap-1 rounded-lg bg-slate-100 hover:bg-slate-200/80 px-2 py-1.5 text-[10px] font-bold text-slate-800 transition"
                >
                  <PhoneIcon size={11} className="text-slate-600" />
                  <span>Call Emergency</span>
                </a>

                <button
                  type="button"
                  onClick={() => handleNavigateToFacility(selectedFacility)}
                  className="flex items-center justify-center gap-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 px-2 py-1.5 text-[10px] font-black text-white shadow-xs transition"
                >
                  <NavigationIcon size={11} />
                  <span>Navigate Here</span>
                </button>
              </div>
            </div>
          </Popup>
        )}
      </Map>
    </div>
  );
}
