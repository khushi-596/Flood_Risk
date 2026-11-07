"use client";

import { useCallback, useEffect, useState } from "react";

import { RainControls } from "@/components/rain-controls";
import { RiskLegend } from "@/components/risk-legend";
import { RiskMap } from "@/components/risk-map";
import { RouteAddressInputs } from "@/components/route-address-inputs";
import { SegmentExplanationPanel } from "@/components/segment-explanation";
import { TravelAdviceCard } from "@/components/travel-advice-card";
import { getRainState, getRoadSegments } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { WaterDropIcon, MapPinIcon } from "@/components/icons";
import type { MapPoint, RainState, RoadCollection, RouteComparison as RouteComparisonType, VehicleType } from "@/lib/types";

export default function HomePage() {
  const [roads, setRoads] = useState<RoadCollection | null>(null);
  const [error, setError] = useState<string | null>(null);

  const origin = useAppStore((s) => s.origin) as MapPoint | null;
  const destination = useAppStore((s) => s.destination) as MapPoint | null;
  const selectionMode = useAppStore((s) => s.selectionMode) as "origin" | "destination";
  const handlePointSelect = useAppStore((s) => s.handlePointSelect) as (p: MapPoint) => void;
  const vehicle = useAppStore((s) => s.vehicle) as VehicleType;
  const rain = useAppStore((s) => s.rain) as RainState | null;
  const setRain = useAppStore((s) => s.setRain) as (r: RainState) => void;
  const refreshKey = useAppStore((s) => s.refreshKey) as number;
  const triggerRefresh = useAppStore((s) => s.triggerRefresh) as () => void;
  const routeResult = useAppStore((s) => s.routeResult) as RouteComparisonType | null;
  const selectedSegmentId = useAppStore((s) => s.selectedSegmentId) as string | null;
  const setSelectedSegmentId = useAppStore((s) => s.setSelectedSegmentId) as (id: string | null) => void;

  /* Load road segments */
  const loadRoads = useCallback(() => {
    const controller = new AbortController();
    getRoadSegments(controller.signal)
      .then(setRoads)
      .catch((reason: unknown) => {
        if (reason instanceof Error && reason.name !== "AbortError") setError(reason.message);
      });
    return () => controller.abort();
  }, []);

  useEffect(loadRoads, [loadRoads]);

  /* Re-fetch segments whenever rain changes */
  useEffect(() => {
    if (refreshKey === 0) return;
    const controller = new AbortController();
    getRoadSegments(controller.signal).then(setRoads).catch(() => {});
    return () => controller.abort();
  }, [refreshKey]);

  /* Fetch initial rain state */
  useEffect(() => {
    getRainState().then(setRain).catch(() => {});
  }, [setRain]);

  function handleRainChange(newRain: RainState | null) {
    if (newRain) {
      setRain(newRain);
      triggerRefresh();
    }
  }

  function onSegmentSelect(segmentId: string) {
    setSelectedSegmentId(segmentId);
  }

  return (
    <main className="min-h-screen bg-slate-50/70 pb-12">
      {/* Luxury Aquatic Blue Glassmorphism Header */}
      <header className="relative overflow-hidden luxury-glass-blue water-droplets-pattern text-white">
        <div className="relative mx-auto flex max-w-7xl flex-col gap-5 px-5 py-6 sm:px-6 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1.5">
            <p className="text-[10px] uppercase font-bold tracking-[0.25em] text-sky-300">
              Metropolitan Flood Risk &amp; Autonomous Transit
            </p>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white drop-shadow-sm">
              FloodAware <span className="font-light text-sky-200">Pune</span>
            </h1>
            <p className="max-w-2xl text-xs text-sky-100/80 leading-relaxed font-normal">
              Continuous road elevation, precipitation rate, and crowdsourced hazard monitoring across Greater Pune.
            </p>
          </div>

          {/* Quick status pills */}
          <div className="flex flex-wrap items-center gap-2.5 text-xs">
            <div className="luxury-glass-pill flex items-center gap-2.5 px-4 py-2.5 rounded-2xl text-white">
              <WaterDropIcon size={16} className="text-sky-300" />
              <div>
                <p className="text-[10px] uppercase font-bold tracking-wider text-sky-300/80">Precipitation</p>
                <p className="text-xs font-black text-white">
                  {rain ? `${rain.rainfall_mm_hour} mm/h` : "0 mm/h"}
                </p>
              </div>
            </div>

            <div className="luxury-glass-pill flex items-center gap-2.5 px-4 py-2.5 rounded-2xl text-white">
              <MapPinIcon size={16} className="text-sky-300" />
              <div>
                <p className="text-[10px] uppercase font-bold tracking-wider text-sky-300/80">Map Click Mode</p>
                <p className="text-xs font-black text-white">
                  {selectionMode === "origin" ? "Start Point (A)" : "Destination (B)"}
                </p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Cohesive Cockpit (Zero Negative Space) */}
      <section className="mx-auto max-w-7xl px-4 py-5 sm:px-6">
        <div className="grid gap-5 lg:grid-cols-[430px_1fr] items-start">
          {/* Left Column: Unified Route Console & Segment Details */}
          <div className="space-y-4">
            <RouteAddressInputs />

            {selectedSegmentId && (
              <SegmentExplanationPanel
                segmentId={selectedSegmentId}
                onClose={() => setSelectedSegmentId(null)}
              />
            )}
          </div>

          {/* Right Column: Interactive Map + Intelligence Grid */}
          <div className="space-y-4 min-w-0">
            {/* Map Container */}
            <div className="relative">
              {roads ? (
                <RiskMap
                  roads={roads}
                  origin={origin}
                  destination={destination}
                  routes={routeResult?.routes ?? []}
                  onPointSelect={handlePointSelect}
                  onSegmentSelect={onSegmentSelect}
                />
              ) : (
                <div
                  className="flex h-[58vh] min-h-[460px] items-center justify-center rounded-3xl border border-slate-200 bg-white/80 backdrop-blur-xl p-6 text-center shadow-card"
                  role="status"
                >
                  <div className="space-y-3">
                    <div className="mx-auto h-10 w-10 animate-pulse rounded-2xl bg-sky-100 flex items-center justify-center">
                      <span className="h-4 w-4 border-2 border-sky-700 border-t-transparent rounded-full animate-spin" />
                    </div>
                    <div>
                      <p className="text-sm font-bold text-slate-800">
                        {error ?? "Loading Pune flood risk road grid…"}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        Analyzing 400+ road segments with live elevation &amp; rainfall scores
                      </p>
                    </div>
                    {error && (
                      <button
                        onClick={() => {
                          setError(null);
                          loadRoads();
                        }}
                        type="button"
                        className="btn-primary text-xs px-4 py-2 shadow-sm"
                      >
                        Retry Connection
                      </button>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Intelligence Grid: Symmetrical 3-card frosted row under map */}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <TravelAdviceCard
                vehicle={vehicle}
                origin={origin}
                destination={destination}
                refreshKey={refreshKey}
              />
              <RainControls rain={rain} onChange={handleRainChange} />
              <div className="sm:col-span-2 lg:col-span-1">
                <RiskLegend />
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
