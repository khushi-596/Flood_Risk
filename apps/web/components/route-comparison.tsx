"use client";

import { useState } from "react";
import { compareRoutes } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { MapPoint, RouteComparison as RouteComparisonType, RouteOption, VehicleType } from "@/lib/types";
import { MotorcycleIcon, CarIcon, BusIcon, TruckIcon, ShieldCheckIcon, AlertTriangleIcon, NavigationIcon } from "@/components/icons";

const vehicles: { value: VehicleType; label: string; icon: React.ComponentType<{ className?: string; size?: number }>; clearance: string }[] = [
  { value: "two_wheeler", label: "2-Wheeler", icon: MotorcycleIcon, clearance: "15cm limit" },
  { value: "car", label: "Car", icon: CarIcon, clearance: "30cm limit" },
  { value: "bus", label: "Bus", icon: BusIcon, clearance: "60cm limit" },
  { value: "truck", label: "Truck", icon: TruckIcon, clearance: "80cm limit" },
];

type Props = {
  origin: MapPoint | null;
  destination: MapPoint | null;
  vehicle: VehicleType;
  onVehicleChange: (vehicle: VehicleType) => void;
  result: RouteComparisonType | null;
  onResult: (result: RouteComparisonType) => void;
};

export function RouteComparison({
  origin,
  destination,
  vehicle,
  onVehicleChange,
  result,
  onResult,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedRouteId = useAppStore((s) => s.selectedRouteId) as string | null;
  const setSelectedRouteId = useAppStore((s) => s.setSelectedRouteId) as (id: string | null) => void;

  async function findRoutes() {
    if (!origin || !destination) {
      setError("Please set both starting point and destination.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await compareRoutes(origin, destination, vehicle);
      onResult(res);
      const safeRoute = res.routes.find((r) => r.id === "safe") ?? res.routes[0];
      if (safeRoute) setSelectedRouteId(safeRoute.id);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not compare routes.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="frosted-card p-5 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-widest text-slate-800">Vehicle Selection</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">Choose transport type to calibrate flood clearance</p>
        </div>
      </div>

      {/* Vehicle picker */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2" role="radiogroup" aria-label="Select vehicle type">
        {vehicles.map((v) => {
          const isSelected = vehicle === v.value;
          const Icon = v.icon;
          return (
            <button
              key={v.value}
              id={`vehicle-${v.value}`}
              aria-checked={isSelected}
              role="radio"
              type="button"
              onClick={() => onVehicleChange(v.value)}
              className={`flex flex-col items-center justify-center rounded-xl border p-2.5 text-center transition-all ${
                isSelected
                  ? "border-sky-500 bg-sky-50 text-sky-950 font-bold shadow-xs ring-2 ring-sky-500/15"
                  : "border-slate-200/90 bg-white/70 text-slate-600 hover:border-slate-300 hover:bg-white"
              }`}
            >
              <Icon size={20} className={isSelected ? "text-sky-700" : "text-slate-500"} />
              <span className="mt-1 text-xs font-bold">{v.label}</span>
              <span className="text-[10px] text-slate-400">{v.clearance}</span>
            </button>
          );
        })}
      </div>

      {/* Calculate Button */}
      <button
        id="compare-routes-btn"
        type="button"
        disabled={loading || !origin || !destination}
        onClick={findRoutes}
        className="btn-primary w-full py-2.5 text-xs font-bold shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2"
      >
        {loading ? (
          <span>Analyzing Flood Risk…</span>
        ) : (
          <>
            <NavigationIcon size={14} />
            <span>Compare Safe, Balanced &amp; Fast Routes</span>
          </>
        )}
      </button>

      {error && (
        <div className="rounded-xl bg-rose-50 border border-rose-200/80 p-2.5 text-xs text-rose-800 flex items-center gap-1.5">
          <AlertTriangleIcon size={14} className="text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Route Results */}
      {result && (
        <div className="space-y-2.5 pt-2 border-t border-slate-200/60 animate-slide-up">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">
              Computed Routes ({result.routes.length})
            </h3>
            <span className="text-[10px] text-slate-400">Tap to highlight on map</span>
          </div>

          <div className="space-y-2">
            {result.routes.map((route) => {
              const isSafe = route.id === "safe";
              const isFast = route.id === "fast";
              const isSelected = selectedRouteId === route.id;
              const riskPercent = Math.round(route.average_risk * 100);

              return (
                <article
                  key={route.id}
                  id={`route-card-${route.id}`}
                  onClick={() => setSelectedRouteId(route.id)}
                  className={`cursor-pointer rounded-xl border p-3.5 transition-all ${
                    isSafe ? "bg-emerald-50/70 border-emerald-200" : isFast ? "bg-rose-50/70 border-rose-200" : "bg-sky-50/70 border-sky-200"
                  } ${isSelected ? "ring-2 ring-sky-500 shadow-md" : ""}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      {isSafe && <ShieldCheckIcon size={14} className="text-emerald-700" />}
                      {isFast && <AlertTriangleIcon size={14} className="text-rose-700" />}
                      <h4 className="text-xs font-bold text-slate-900">{route.label}</h4>
                      <span className={`text-[10px] font-bold px-1.5 py-0.2 rounded border ${
                        isSafe ? "bg-emerald-100 text-emerald-800 border-emerald-200" : isFast ? "bg-rose-100 text-rose-800 border-rose-200" : "bg-sky-100 text-sky-800 border-sky-200"
                      }`}>
                        {isSafe ? "Safest Route" : isFast ? "Fastest Route" : "Balanced"}
                      </span>
                    </div>

                    <span className="text-xs font-black text-slate-900">{riskPercent}% Risk</span>
                  </div>

                  <div className="mt-2 flex items-center justify-between text-xs text-slate-600">
                    <span>{(route.distance_m / 1000).toFixed(1)} km • {route.duration_min} min</span>
                    <span className="font-semibold text-slate-700">
                      {route.risky_segment_count === 0 ? "0 hazard roads" : `${route.risky_segment_count} hazard roads`}
                    </span>
                  </div>

                  <p className="mt-2 text-xs leading-relaxed text-slate-600 bg-white/70 rounded-lg p-2 border border-slate-200/50">
                    {route.recommendation}
                  </p>
                </article>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
