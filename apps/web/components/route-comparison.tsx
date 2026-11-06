"use client";

import { useState } from "react";
import { compareRoutes } from "@/lib/api";
import type { MapPoint, RouteComparison, RouteOption, VehicleType } from "@/lib/types";

const vehicles: { value: VehicleType; label: string; icon: string }[] = [
  { value: "two_wheeler", label: "Two-wheeler", icon: "🏍️" },
  { value: "car", label: "Car", icon: "🚗" },
  { value: "bus", label: "Bus", icon: "🚌" },
  { value: "truck", label: "Truck", icon: "🚛" },
];

const routeStyle: Record<RouteOption["id"], { bg: string; border: string; accent: string; dot: string }> = {
  fast: { bg: "bg-rose-50", border: "border-rose-200", accent: "text-rose-700", dot: "bg-rose-500" },
  safe: { bg: "bg-emerald-50", border: "border-emerald-200", accent: "text-emerald-700", dot: "bg-emerald-500" },
  balanced: { bg: "bg-sky-50", border: "border-sky-200", accent: "text-sky-700", dot: "bg-sky-500" },
};

type Props = {
  origin: MapPoint | null;
  destination: MapPoint | null;
  vehicle: VehicleType;
  onVehicleChange: (vehicle: VehicleType) => void;
  result: RouteComparison | null;
  onResult: (result: RouteComparison) => void;
};

export function RouteComparison({ origin, destination, vehicle, onVehicleChange, result, onResult }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function findRoutes() {
    if (!origin || !destination) {
      setError("Select both A (start) and B (destination) on the map.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      onResult(await compareRoutes(origin, destination, vehicle));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not compare routes.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card p-5 animate-fade-in">
      <div className="flex items-center justify-between gap-3">
        <h2 className="section-title">Compare Routes</h2>
      </div>

      {/* Vehicle picker */}
      <div className="mt-3 grid grid-cols-4 gap-1.5" role="radiogroup" aria-label="Select vehicle type">
        {vehicles.map((v) => (
          <button
            aria-checked={vehicle === v.value}
            className={`flex flex-col items-center gap-1 rounded-xl border px-2 py-2.5 text-xs font-semibold transition-all duration-200 ${
              vehicle === v.value
                ? "border-sky-300 bg-sky-50 text-sky-800 shadow-sm"
                : "border-slate-200 bg-white text-slate-600 hover:border-sky-200 hover:bg-sky-50/50"
            }`}
            id={`vehicle-${v.value}`}
            key={v.value}
            onClick={() => onVehicleChange(v.value)}
            role="radio"
            type="button"
          >
            <span className="text-lg">{v.icon}</span>
            <span className="leading-none">{v.label}</span>
          </button>
        ))}
      </div>

      {/* Origin/Destination status */}
      <div className="mt-3 space-y-1.5">
        <div className="flex items-center gap-2 text-xs">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-600 text-[10px] font-bold text-white">A</span>
          <span className={origin ? "font-medium text-slate-700" : "text-slate-400"}>
            {origin ? origin.label : "Click map to set start"}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-rose-600 text-[10px] font-bold text-white">B</span>
          <span className={destination ? "font-medium text-slate-700" : "text-slate-400"}>
            {destination ? destination.label : "Click map to set destination"}
          </span>
        </div>
      </div>

      <button
        className="btn-primary mt-4 w-full"
        disabled={loading || !origin || !destination}
        id="compare-routes-btn"
        onClick={findRoutes}
        type="button"
      >
        {loading ? (
          <span className="animate-pulse-subtle">Comparing…</span>
        ) : (
          "Compare Fast, Safe & Balanced"
        )}
      </button>

      {error && <p className="mt-2 text-xs font-medium text-rose-700">{error}</p>}

      {result && (
        <div className="mt-4 space-y-2.5 animate-slide-up">
          {result.routes.map((route) => {
            const style = routeStyle[route.id] ?? routeStyle.fast;
            return (
              <article
                className={`rounded-xl border p-3.5 transition-all duration-200 ${style.bg} ${style.border}`}
                key={route.id}
                id={`route-card-${route.id}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
                    <h3 className={`text-sm font-extrabold ${style.accent}`}>
                      {route.label}
                    </h3>
                  </div>
                  <span className={`text-lg font-black ${style.accent}`}>
                    {Math.round(route.average_risk * 100)}%
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
                  <span>{(route.distance_m / 1000).toFixed(1)} km</span>
                  <span>{route.duration_min} min</span>
                  <span>{route.risky_segment_count} risky road{route.risky_segment_count !== 1 ? "s" : ""}</span>
                </div>
                <p className="mt-2 text-xs leading-relaxed text-slate-500">{route.recommendation}</p>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
