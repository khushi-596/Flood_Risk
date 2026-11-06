"use client";

import { useCallback, useEffect, useState } from "react";

import { PlaceSearch } from "@/components/place-search";
import { RainControls } from "@/components/rain-controls";
import { RiskLegend } from "@/components/risk-legend";
import { RiskMap } from "@/components/risk-map";
import { RouteComparison } from "@/components/route-comparison";
import { SegmentExplanationPanel } from "@/components/segment-explanation";
import { TravelAdviceCard } from "@/components/travel-advice-card";
import { getRainState, getRoadSegments } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { MapPoint, RainState, RoadCollection, RouteComparison as RouteComparisonType, VehicleType } from "@/lib/types";

export default function HomePage() {
  const [roads, setRoads] = useState<RoadCollection | null>(null);
  const [error, setError] = useState<string | null>(null);

  const origin = useAppStore((s) => s.origin) as MapPoint | null;
  const destination = useAppStore((s) => s.destination) as MapPoint | null;
  const selectionMode = useAppStore((s) => s.selectionMode) as "origin" | "destination";
  const handlePointSelect = useAppStore((s) => s.handlePointSelect) as (p: MapPoint) => void;
  const vehicle = useAppStore((s) => s.vehicle) as VehicleType;
  const setVehicle = useAppStore((s) => s.setVehicle) as (v: VehicleType) => void;
  const rain = useAppStore((s) => s.rain) as RainState | null;
  const setRain = useAppStore((s) => s.setRain) as (r: RainState) => void;
  const refreshKey = useAppStore((s) => s.refreshKey) as number;
  const triggerRefresh = useAppStore((s) => s.triggerRefresh) as () => void;
  const routeResult = useAppStore((s) => s.routeResult) as RouteComparisonType | null;
  const setRouteResult = useAppStore((s) => s.setRouteResult) as (r: RouteComparisonType | null) => void;
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
    <main className="min-h-screen">
      {/* Hero header */}
      <header className="relative overflow-hidden" style={{ background: "var(--gradient-hero)" }}>
        <div className="absolute inset-0 opacity-10">
          <div className="absolute -right-20 -top-20 h-64 w-64 rounded-full bg-white/20 blur-3xl" />
          <div className="absolute -bottom-10 left-1/4 h-48 w-48 rounded-full bg-sky-300/30 blur-3xl" />
        </div>
        <div className="relative mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-5 sm:px-6">
          <div>
            <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-sky-200">
              Pune Flood-Aware Navigation
            </p>
            <h1 className="mt-1 text-xl font-extrabold text-white sm:text-2xl">
              FloodAware Route &amp; Risk Engine
            </h1>
            <p className="mt-1 max-w-xl text-sm text-sky-100/80">
              Roads scored by terrain, drainage, rainfall, flood history &amp; citizen reports.
              Choose a safer road — not only a faster one.
            </p>
          </div>
          <div className="hidden items-center gap-2 sm:flex">
            <span className="rounded-full bg-white/15 px-3 py-1.5 text-xs font-bold text-white backdrop-blur">
              {selectionMode === "origin" ? "📍 Set Start (A)" : "📍 Set Destination (B)"}
            </span>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl px-4 py-5 sm:px-6">
        {/* Map + search */}
        <div className="relative">
          <div className="absolute left-3 right-3 top-3 z-10 sm:left-5 sm:right-auto">
            <PlaceSearch onPlaceSelect={handlePointSelect} />
          </div>
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
              className="flex h-[62vh] min-h-[460px] items-center justify-center rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm"
              role="status"
            >
              <div>
                <div className="mx-auto h-10 w-10 animate-pulse-subtle rounded-full bg-sky-100 p-2.5">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#0369a1" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" /></svg>
                </div>
                <p className="mt-3 text-sm font-medium text-slate-600">
                  {error ?? "Loading Pune road-risk segments…"}
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Controls grid */}
        <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_340px]">
          {/* Left column */}
          <div className="space-y-5">
            <RouteComparison
              origin={origin}
              destination={destination}
              vehicle={vehicle}
              onVehicleChange={setVehicle}
              result={routeResult}
              onResult={setRouteResult}
            />

            {selectedSegmentId && (
              <SegmentExplanationPanel
                segmentId={selectedSegmentId}
                onClose={() => setSelectedSegmentId(null)}
              />
            )}
          </div>

          {/* Right column */}
          <div className="space-y-5">
            <TravelAdviceCard
              vehicle={vehicle}
              origin={origin}
              destination={destination}
              refreshKey={refreshKey}
            />
            <RainControls rain={rain} onChange={handleRainChange} />
            <RiskLegend />
          </div>
        </div>
      </section>
    </main>
  );
}
