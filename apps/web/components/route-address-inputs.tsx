"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { compareRoutes } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { MapPoint, RouteComparison as RouteComparisonType, VehicleType } from "@/lib/types";
import {
  MotorcycleIcon,
  CarIcon,
  BusIcon,
  TruckIcon,
  NavigationIcon,
  CrosshairIcon,
  SwapIcon,
  CloseIcon,
  ShieldCheckIcon,
  AlertTriangleIcon,
} from "@/components/icons";

export const PUNE_PRESETS: { label: string; area: string; latitude: number; longitude: number }[] = [
  { label: "Pune Railway Station", area: "Station / Camp", latitude: 18.5284, longitude: 73.8739 },
  { label: "Shivajinagar", area: "Central Pune", latitude: 18.5314, longitude: 73.8446 },
  { label: "Hinjawadi IT Park", area: "Phase 1 / Tech Hub", latitude: 18.5913, longitude: 73.7389 },
  { label: "Kothrud", area: "Paud Rd / Chandani Chowk", latitude: 18.5074, longitude: 73.8077 },
  { label: "Swargate", area: "Swargate Bus Stand", latitude: 18.5018, longitude: 73.8586 },
  { label: "Viman Nagar", area: "Phoenix Mall / Airport Rd", latitude: 18.5679, longitude: 73.9143 },
  { label: "Baner", area: "High Street / Balewadi", latitude: 18.559, longitude: 73.7868 },
  { label: "Hadapsar", area: "Magarpatta / Solapur Rd", latitude: 18.5089, longitude: 73.926 },
  { label: "Deccan Gymkhana", area: "FC Road / JM Road", latitude: 18.5186, longitude: 73.8415 },
  { label: "Aundh", area: "Parihar Chowk", latitude: 18.5602, longitude: 73.8062 },
  { label: "Kalyani Nagar", area: "East Pune", latitude: 18.5482, longitude: 73.9035 },
  { label: "Pimpri Chinchwad", area: "PCMC Hub", latitude: 18.6298, longitude: 73.7997 },
];

const vehicleOptions: { value: VehicleType; label: string; clearance: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { value: "two_wheeler", label: "Two-Wheeler", clearance: "15cm clearance", icon: MotorcycleIcon },
  { value: "car", label: "Car", clearance: "30cm clearance", icon: CarIcon },
  { value: "bus", label: "Bus", clearance: "60cm clearance", icon: BusIcon },
  { value: "truck", label: "Truck", clearance: "80cm clearance", icon: TruckIcon },
];

type NominatimResult = {
  display_name: string;
  lat: string;
  lon: string;
};

export function RouteAddressInputs() {
  const origin = useAppStore((s) => s.origin) as MapPoint | null;
  const destination = useAppStore((s) => s.destination) as MapPoint | null;
  const selectionMode = useAppStore((s) => s.selectionMode) as "origin" | "destination";
  const setOrigin = useAppStore((s) => s.setOrigin) as (p: MapPoint | null) => void;
  const setDestination = useAppStore((s) => s.setDestination) as (p: MapPoint | null) => void;
  const setSelectionMode = useAppStore((s) => s.setSelectionMode) as (m: "origin" | "destination") => void;
  const swapOriginDestination = useAppStore((s) => s.swapOriginDestination) as () => void;
  const clearOrigin = useAppStore((s) => s.clearOrigin) as () => void;
  const clearDestination = useAppStore((s) => s.clearDestination) as () => void;
  const vehicle = useAppStore((s) => s.vehicle) as VehicleType;
  const setVehicle = useAppStore((s) => s.setVehicle) as (v: VehicleType) => void;
  const routeResult = useAppStore((s) => s.routeResult) as RouteComparisonType | null;
  const setRouteResult = useAppStore((s) => s.setRouteResult) as (r: RouteComparisonType | null) => void;
  const selectedRouteId = useAppStore((s) => s.selectedRouteId) as string | null;
  const setSelectedRouteId = useAppStore((s) => s.setSelectedRouteId) as (id: string | null) => void;

  const [sourceQuery, setSourceQuery] = useState("");
  const [destQuery, setDestQuery] = useState("");
  const [sourceResults, setSourceResults] = useState<MapPoint[]>([]);
  const [destResults, setDestResults] = useState<MapPoint[]>([]);
  const [isSearchingSource, setIsSearchingSource] = useState(false);
  const [isSearchingDest, setIsSearchingDest] = useState(false);
  const [sourceFocused, setSourceFocused] = useState(false);
  const [destFocused, setDestFocused] = useState(false);
  const [locatingGps, setLocatingGps] = useState(false);
  const [calculatingRoute, setCalculatingRoute] = useState(false);
  const [routeError, setRouteError] = useState<string | null>(null);

  const sourceDropdownRef = useRef<HTMLDivElement>(null);
  const destDropdownRef = useRef<HTMLDivElement>(null);

  // Sync input text when store points change
  useEffect(() => {
    setSourceQuery(origin?.label ?? "");
  }, [origin]);

  useEffect(() => {
    setDestQuery(destination?.label ?? "");
  }, [destination]);

  // Click outside listener for dropdowns
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (sourceDropdownRef.current && !sourceDropdownRef.current.contains(e.target as Node)) {
        setSourceFocused(false);
      }
      if (destDropdownRef.current && !destDropdownRef.current.contains(e.target as Node)) {
        setDestFocused(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Search Pune geocoder
  async function searchPune(query: string): Promise<MapPoint[]> {
    const trimmed = query.trim().toLowerCase();
    if (trimmed.length < 2) return [];

    const localMatches: MapPoint[] = PUNE_PRESETS.filter(
      (p) => p.label.toLowerCase().includes(trimmed) || p.area.toLowerCase().includes(trimmed)
    ).map((p) => ({
      label: p.label,
      latitude: p.latitude,
      longitude: p.longitude,
    }));

    try {
      const url = new URL("https://nominatim.openstreetmap.org/search");
      url.search = new URLSearchParams({
        q: `${trimmed}, Pune, Maharashtra, India`,
        format: "jsonv2",
        limit: "5",
        viewbox: "73.50,18.85,74.20,18.25",
        bounded: "0",
      }).toString();

      const res = await fetch(url.toString(), {
        headers: { Accept: "application/json", "User-Agent": "FloodRiskPune/1.0" },
      });

      if (res.ok) {
        const places = (await res.json()) as NominatimResult[];
        const onlineMatches: MapPoint[] = places.map((p) => ({
          label: p.display_name.split(",")[0],
          latitude: Number(p.lat),
          longitude: Number(p.lon),
        }));

        const combined = [...localMatches];
        for (const item of onlineMatches) {
          if (!combined.some((c) => Math.abs(c.latitude - item.latitude) < 0.005 && Math.abs(c.longitude - item.longitude) < 0.005)) {
            combined.push(item);
          }
        }
        return combined.slice(0, 6);
      }
    } catch {
      // Fallback to local matches
    }

    return localMatches.slice(0, 6);
  }

  // Handle Source Search debounce
  useEffect(() => {
    if (!sourceFocused) return;
    if (sourceQuery.trim().length < 2) {
      setSourceResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearchingSource(true);
      const res = await searchPune(sourceQuery);
      setSourceResults(res);
      setIsSearchingSource(false);
    }, 250);
    return () => clearTimeout(timer);
  }, [sourceQuery, sourceFocused]);

  // Handle Dest Search debounce
  useEffect(() => {
    if (!destFocused) return;
    if (destQuery.trim().length < 2) {
      setDestResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearchingDest(true);
      const res = await searchPune(destQuery);
      setDestResults(res);
      setIsSearchingDest(false);
    }, 250);
    return () => clearTimeout(timer);
  }, [destQuery, destFocused]);

  function handleSelectSource(point: MapPoint) {
    setOrigin(point);
    setSourceQuery(point.label);
    setSourceResults([]);
    setSourceFocused(false);
    setSelectionMode("destination");
    setRouteError(null);
  }

  function handleSelectDest(point: MapPoint) {
    setDestination(point);
    setDestQuery(point.label);
    setDestResults([]);
    setDestFocused(false);
    setSelectionMode("origin");
    setRouteError(null);
  }

  function handleGpsClick() {
    if (!navigator.geolocation) {
      toast.error("Geolocation is not supported by your browser.");
      return;
    }
    setLocatingGps(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const point: MapPoint = {
          label: "Current Location",
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
        };
        setOrigin(point);
        setSourceQuery(point.label);
        setSelectionMode("destination");
        setLocatingGps(false);
        setRouteError(null);
        toast.success("Starting location set to current GPS coordinates");
      },
      (err) => {
        setLocatingGps(false);
        toast.error(`Unable to retrieve GPS: ${err.message}`);
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }

  function handlePresetClick(preset: typeof PUNE_PRESETS[0]) {
    const point: MapPoint = {
      label: preset.label,
      latitude: preset.latitude,
      longitude: preset.longitude,
    };
    if (selectionMode === "origin" || !origin) {
      handleSelectSource(point);
    } else {
      handleSelectDest(point);
    }
  }

  async function handleFindSafeRoute() {
    if (!origin || !destination) {
      setRouteError("Please enter both starting point and destination.");
      return;
    }
    setCalculatingRoute(true);
    setRouteError(null);
    try {
      const res = await compareRoutes(origin, destination, vehicle);
      setRouteResult(res);
      const safe = res.routes.find((r) => r.id === "safe") ?? res.routes[0];
      if (safe) setSelectedRouteId(safe.id);
      toast.success("Routes calculated successfully");
    } catch (err) {
      setRouteError(err instanceof Error ? err.message : "Unable to calculate routes. Check backend connection.");
    } finally {
      setCalculatingRoute(false);
    }
  }

  return (
    <div className="frosted-panel p-5 relative transition-all space-y-4">
      {/* Header bar */}
      <div className="flex items-center justify-between gap-3 pb-1 border-b border-slate-200/50">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-widest text-slate-800">
            Route Planning Console
          </h2>
          <p className="text-[11px] text-slate-500 mt-0.5">
            Enter route endpoints and vehicle type
          </p>
        </div>

        {/* Map Click Selector Pill */}
        <div className="flex items-center gap-1 rounded-full bg-slate-100/80 p-0.5 text-[11px] font-semibold text-slate-600 border border-slate-200/70">
          <span className="px-2 text-slate-400 hidden sm:inline text-[10px]">Map Click:</span>
          <button
            type="button"
            onClick={() => setSelectionMode("origin")}
            className={`rounded-full px-2.5 py-0.5 transition-all text-[11px] ${
              selectionMode === "origin"
                ? "bg-emerald-600 text-white shadow-xs font-bold"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            Start (A)
          </button>
          <button
            type="button"
            onClick={() => setSelectionMode("destination")}
            className={`rounded-full px-2.5 py-0.5 transition-all text-[11px] ${
              selectionMode === "destination"
                ? "bg-rose-600 text-white shadow-xs font-bold"
                : "text-slate-600 hover:text-slate-900"
            }`}
          >
            End (B)
          </button>
        </div>
      </div>

      {/* DUAL INPUTS */}
      <div className="space-y-2">
        {/* Source Input (A) */}
        <div className="relative" ref={sourceDropdownRef}>
          <div
            className={`flex items-center gap-2.5 rounded-xl border bg-white/90 px-3 py-2.5 transition-all ${
              sourceFocused || selectionMode === "origin"
                ? "border-emerald-500 ring-2 ring-emerald-500/15 shadow-xs"
                : "border-slate-200/90 hover:border-slate-300"
            }`}
          >
            <span
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-emerald-600 text-[11px] font-black text-white shadow-xs"
              title="Starting Point"
            >
              A
            </span>

            <div className="flex-1 min-w-0">
              <input
                id="source-address-input"
                type="text"
                autoComplete="off"
                className="w-full bg-transparent text-sm text-slate-900 placeholder:text-slate-400 outline-none font-medium"
                placeholder="Enter starting point in Pune (e.g. Swargate, Kothrud)…"
                value={sourceQuery}
                onFocus={() => {
                  setSourceFocused(true);
                  setSelectionMode("origin");
                }}
                onChange={(e) => setSourceQuery(e.target.value)}
              />
            </div>

            {/* GPS Button */}
            <button
              type="button"
              onClick={handleGpsClick}
              disabled={locatingGps}
              title="Use current GPS location"
              className="flex items-center gap-1 rounded-lg bg-slate-100 hover:bg-slate-200/80 px-2 py-1 text-[11px] font-semibold text-slate-700 transition"
            >
              <CrosshairIcon size={13} className={locatingGps ? "animate-spin text-sky-600" : "text-slate-600"} />
              <span className="hidden sm:inline">{locatingGps ? "Locating…" : "My GPS"}</span>
            </button>

            {/* Clear Source Button */}
            {origin && (
              <button
                type="button"
                onClick={() => {
                  clearOrigin();
                  setSourceQuery("");
                }}
                title="Clear start location"
                className="h-6 w-6 rounded-full flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
              >
                <CloseIcon size={13} />
              </button>
            )}
          </div>

          {/* Source Autocomplete Dropdown */}
          {sourceFocused && sourceResults.length > 0 && (
            <div className="absolute left-0 right-0 top-full mt-1 z-30 max-h-56 overflow-y-auto rounded-xl border border-slate-200 bg-white/95 backdrop-blur-xl p-1.5 shadow-xl animate-slide-down">
              <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Pune Localities
              </div>
              {sourceResults.map((place, idx) => (
                <button
                  key={`${place.latitude}-${place.longitude}-${idx}`}
                  type="button"
                  onMouseDown={() => handleSelectSource(place)}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs transition hover:bg-emerald-50 hover:text-emerald-950"
                >
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-emerald-100 text-[10px] text-emerald-800 font-bold">
                    A
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-slate-900 truncate">{place.label}</p>
                    <p className="truncate text-[10px] text-slate-400">
                      Pune, Maharashtra ({place.latitude.toFixed(3)}, {place.longitude.toFixed(3)})
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}

          {isSearchingSource && sourceFocused && (
            <div className="absolute right-24 top-3 text-[11px] text-slate-400 animate-pulse">
              Searching…
            </div>
          )}
        </div>

        {/* SWAP BUTTON */}
        <div className="flex justify-center -my-1 relative z-10">
          <button
            type="button"
            onClick={swapOriginDestination}
            title="Swap Starting Point and Destination"
            aria-label="Swap Starting Point and Destination"
            className="flex h-6 w-6 items-center justify-center rounded-full border border-slate-200/90 bg-white shadow-xs text-slate-500 hover:text-sky-700 hover:border-sky-300 hover:bg-sky-50 transition transform hover:rotate-180 duration-300"
          >
            <SwapIcon size={12} />
          </button>
        </div>

        {/* Destination Input (B) */}
        <div className="relative" ref={destDropdownRef}>
          <div
            className={`flex items-center gap-2.5 rounded-xl border bg-white/90 px-3 py-2.5 transition-all ${
              destFocused || selectionMode === "destination"
                ? "border-rose-500 ring-2 ring-rose-500/15 shadow-xs"
                : "border-slate-200/90 hover:border-slate-300"
            }`}
          >
            <span
              className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-rose-600 text-[11px] font-black text-white shadow-xs"
              title="Destination"
            >
              B
            </span>

            <div className="flex-1 min-w-0">
              <input
                id="destination-address-input"
                type="text"
                autoComplete="off"
                className="w-full bg-transparent text-sm text-slate-900 placeholder:text-slate-400 outline-none font-medium"
                placeholder="Enter destination in Pune (e.g. Hinjawadi IT Park, Airport)…"
                value={destQuery}
                onFocus={() => {
                  setDestFocused(true);
                  setSelectionMode("destination");
                }}
                onChange={(e) => setDestQuery(e.target.value)}
              />
            </div>

            {/* Clear Destination Button */}
            {destination && (
              <button
                type="button"
                onClick={() => {
                  clearDestination();
                  setDestQuery("");
                }}
                title="Clear destination"
                className="h-6 w-6 rounded-full flex items-center justify-center text-slate-400 hover:bg-slate-100 hover:text-slate-700 transition"
              >
                <CloseIcon size={13} />
              </button>
            )}
          </div>

          {/* Destination Autocomplete Dropdown */}
          {destFocused && destResults.length > 0 && (
            <div className="absolute left-0 right-0 top-full mt-1 z-30 max-h-56 overflow-y-auto rounded-xl border border-slate-200 bg-white/95 backdrop-blur-xl p-1.5 shadow-xl animate-slide-down">
              <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Pune Localities
              </div>
              {destResults.map((place, idx) => (
                <button
                  key={`${place.latitude}-${place.longitude}-${idx}`}
                  type="button"
                  onMouseDown={() => handleSelectDest(place)}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs transition hover:bg-rose-50 hover:text-rose-950"
                >
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-rose-100 text-[10px] text-rose-800 font-bold">
                    B
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-slate-900 truncate">{place.label}</p>
                    <p className="truncate text-[10px] text-slate-400">
                      Pune, Maharashtra ({place.latitude.toFixed(3)}, {place.longitude.toFixed(3)})
                    </p>
                  </div>
                </button>
              ))}
            </div>
          )}

          {isSearchingDest && destFocused && (
            <div className="absolute right-10 top-3 text-[11px] text-slate-400 animate-pulse">
              Searching…
            </div>
          )}
        </div>
      </div>

      {/* VEHICLE SELECTOR (Integrated) */}
      <div className="space-y-1.5 pt-1">
        <label className="text-[11px] font-bold uppercase tracking-wider text-slate-500 block">
          Vehicle Type
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {vehicleOptions.map((opt) => {
            const Icon = opt.icon;
            const isSelected = vehicle === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => setVehicle(opt.value)}
                className={`flex flex-col items-center justify-center rounded-xl p-2.5 border transition-all ${
                  isSelected
                    ? "border-sky-500 bg-sky-50/90 text-sky-950 shadow-xs ring-2 ring-sky-500/15"
                    : "border-slate-200/90 bg-white/70 hover:bg-white text-slate-600 hover:border-slate-300"
                }`}
              >
                <Icon className={`w-5 h-5 ${isSelected ? "text-sky-700" : "text-slate-500"}`} />
                <span className="mt-1 text-xs font-bold leading-tight">{opt.label}</span>
                <span className="text-[9px] text-slate-400">{opt.clearance}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* COMMON SEARCH BUTTON */}
      <div>
        <button
          type="button"
          onClick={handleFindSafeRoute}
          disabled={calculatingRoute || !origin || !destination}
          className="btn-primary w-full py-3 text-sm font-bold shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2"
        >
          {calculatingRoute ? (
            <>
              <svg className="animate-spin h-4 w-4 text-white" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span>Analyzing Flood Risk &amp; Terrain…</span>
            </>
          ) : (
            <>
              <NavigationIcon size={16} />
              <span>Find Safe Route</span>
            </>
          )}
        </button>

        {(!origin || !destination) && (
          <p className="text-center text-[11px] text-slate-400 mt-1.5">
            Set both start and destination points to calculate routes
          </p>
        )}

        {routeError && (
          <div className="mt-2 rounded-xl bg-rose-50 border border-rose-200/80 p-2.5 text-xs text-rose-800 flex items-start gap-2">
            <AlertTriangleIcon size={14} className="mt-0.5 shrink-0 text-rose-600" />
            <span>{routeError}</span>
          </div>
        )}
      </div>

      {/* QUICK PRESET CHIPS */}
      <div className="pt-2 border-t border-slate-200/50">
        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
          Quick Pune Locations
        </p>
        <div className="flex flex-wrap gap-1.5 max-h-20 overflow-y-auto pr-0.5">
          {PUNE_PRESETS.slice(0, 8).map((preset) => {
            const isOrigin = origin?.label === preset.label;
            const isDest = destination?.label === preset.label;
            return (
              <button
                key={preset.label}
                type="button"
                onClick={() => handlePresetClick(preset)}
                className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold border transition ${
                  isOrigin
                    ? "bg-emerald-600 text-white border-emerald-600"
                    : isDest
                    ? "bg-rose-600 text-white border-rose-600"
                    : "bg-white/80 hover:bg-slate-100 text-slate-600 border-slate-200/80 hover:text-slate-900"
                }`}
              >
                {preset.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* ROUTE COMPARISON RESULTS (Rendered directly inside console to eliminate negative space) */}
      {routeResult && (
        <div className="pt-3 border-t border-slate-200/60 space-y-2.5 animate-slide-up">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              Computed Routes ({routeResult.routes.length})
            </h3>
            <span className="text-[10px] text-slate-400">Tap to highlight on map</span>
          </div>

          <div className="space-y-2">
            {routeResult.routes.map((route) => {
              const isSafe = route.id === "safe";
              const isFast = route.id === "fast";
              const isSelected = selectedRouteId === route.id;
              const riskPercent = Math.round(route.average_risk * 100);

              const theme = isSafe
                ? {
                    bg: "bg-emerald-50/70 hover:bg-emerald-50",
                    border: "border-emerald-200",
                    accent: "text-emerald-950",
                    badge: "bg-emerald-100 text-emerald-800 border-emerald-200",
                    label: "Safest Route",
                    bar: "bg-emerald-500",
                  }
                : isFast
                ? {
                    bg: "bg-rose-50/70 hover:bg-rose-50",
                    border: "border-rose-200",
                    accent: "text-rose-950",
                    badge: "bg-rose-100 text-rose-800 border-rose-200",
                    label: "Fastest Route",
                    bar: "bg-rose-500",
                  }
                : {
                    bg: "bg-sky-50/70 hover:bg-sky-50",
                    border: "border-sky-200",
                    accent: "text-sky-950",
                    badge: "bg-sky-100 text-sky-800 border-sky-200",
                    label: "Balanced Route",
                    bar: "bg-sky-500",
                  };

              return (
                <div
                  key={route.id}
                  onClick={() => setSelectedRouteId(route.id)}
                  className={`cursor-pointer rounded-xl border p-3 transition-all ${theme.bg} ${theme.border} ${
                    isSelected ? "ring-2 ring-sky-500 shadow-sm" : ""
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      {isSafe && <ShieldCheckIcon size={14} className="text-emerald-700" />}
                      {isFast && <AlertTriangleIcon size={14} className="text-rose-700" />}
                      <span className={`text-xs font-bold ${theme.accent}`}>{route.label}</span>
                      <span className={`text-[10px] font-bold px-1.5 py-0.2 rounded border ${theme.badge}`}>
                        {theme.label}
                      </span>
                    </div>
                    <span className={`text-sm font-black ${theme.accent}`}>{riskPercent}% Risk</span>
                  </div>

                  {/* Risk Progress Bar */}
                  <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200/80">
                    <div className={`h-full rounded-full ${theme.bar}`} style={{ width: `${Math.max(4, riskPercent)}%` }} />
                  </div>

                  {/* Metrics */}
                  <div className="mt-2 flex items-center justify-between text-[11px] text-slate-600">
                    <span>{(route.distance_m / 1000).toFixed(1)} km • {route.duration_min} min</span>
                    <span className="font-semibold text-slate-700">
                      {route.risky_segment_count === 0 ? "0 hazard roads" : `${route.risky_segment_count} hazard roads`}
                    </span>
                  </div>

                  <p className="mt-1.5 text-[11px] text-slate-600 bg-white/70 rounded-lg p-2 border border-slate-200/50 leading-relaxed">
                    {route.recommendation}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
