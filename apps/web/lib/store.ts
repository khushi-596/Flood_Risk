"use client";

import { create } from "zustand";
import type {
  MapPoint,
  RainState,
  RouteComparison,
  SegmentExplanation,
  TravelAdvice,
  VehicleType,
} from "@/lib/types";

export type AlertMessage = {
  id: string;
  type: "risk_alert" | "connected";
  segment_id?: string;
  road_name?: string;
  risk_band?: string;
  risk_score?: number;
  message: string;
  timestamp: number;
};

type AppState = {
  /* Map selection */
  origin: MapPoint | null;
  destination: MapPoint | null;
  selectionMode: "origin" | "destination";
  setOrigin: (p: MapPoint | null) => void;
  setDestination: (p: MapPoint | null) => void;
  setSelectionMode: (m: "origin" | "destination") => void;
  handlePointSelect: (p: MapPoint) => void;
  swapOriginDestination: () => void;
  clearOrigin: () => void;
  clearDestination: () => void;

  /* Route selection */
  selectedRouteId: string | null;
  setSelectedRouteId: (id: string | null) => void;

  /* Vehicle */
  vehicle: VehicleType;
  setVehicle: (v: VehicleType) => void;

  /* Rain */
  rain: RainState | null;
  setRain: (r: RainState) => void;
  refreshKey: number;
  triggerRefresh: () => void;

  /* Route comparison */
  routeResult: RouteComparison | null;
  setRouteResult: (r: RouteComparison | null) => void;

  /* Segment explanation */
  selectedSegmentId: string | null;
  segmentExplanation: SegmentExplanation | null;
  setSelectedSegmentId: (id: string | null) => void;
  setSegmentExplanation: (e: SegmentExplanation | null) => void;

  /* Travel advice */
  travelAdvice: TravelAdvice | null;
  setTravelAdvice: (a: TravelAdvice | null) => void;

  /* Alerts */
  alerts: AlertMessage[];
  addAlert: (a: AlertMessage) => void;
  dismissAlert: (id: string) => void;

  /* Municipal auth */
  municipalToken: string | null;
  setMunicipalToken: (t: string | null) => void;

  /* Reporter fingerprint */
  fingerprint: string;
};

function generateFingerprint(): string {
  if (typeof window === "undefined") return "ssr-placeholder";
  const stored = localStorage.getItem("flood-reporter-fp");
  if (stored) return stored;
  const fp = `fp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  localStorage.setItem("flood-reporter-fp", fp);
  return fp;
}

export const useAppStore = create<AppState>()((set, get) => ({
  origin: null,
  destination: null,
  selectionMode: "origin" as const,
  setOrigin: (p: MapPoint | null) => set({ origin: p }),
  setDestination: (p: MapPoint | null) => set({ destination: p }),
  setSelectionMode: (m: "origin" | "destination") => set({ selectionMode: m }),
  handlePointSelect: (p: MapPoint) => {
    const mode = get().selectionMode;
    if (mode === "origin") {
      set({ origin: p, selectionMode: "destination" });
    } else {
      set({ destination: p, selectionMode: "origin" });
    }
  },
  swapOriginDestination: () => {
    const { origin, destination } = get();
    set({ origin: destination, destination: origin, routeResult: null });
  },
  clearOrigin: () => set({ origin: null, routeResult: null, selectionMode: "origin" }),
  clearDestination: () => set({ destination: null, routeResult: null, selectionMode: "destination" }),

  selectedRouteId: null,
  setSelectedRouteId: (id: string | null) => set({ selectedRouteId: id }),

  vehicle: "car" as VehicleType,
  setVehicle: (v: VehicleType) => set({ vehicle: v }),

  rain: null,
  setRain: (r: RainState) => set({ rain: r }),
  refreshKey: 0,
  triggerRefresh: () => set((s: AppState) => ({ refreshKey: s.refreshKey + 1 })),

  routeResult: null,
  setRouteResult: (r: RouteComparison | null) => set({ routeResult: r }),

  selectedSegmentId: null,
  segmentExplanation: null,
  setSelectedSegmentId: (id: string | null) => set({ selectedSegmentId: id }),
  setSegmentExplanation: (e: SegmentExplanation | null) => set({ segmentExplanation: e }),

  travelAdvice: null,
  setTravelAdvice: (a: TravelAdvice | null) => set({ travelAdvice: a }),

  alerts: [],
  addAlert: (a: AlertMessage) =>
    set((s: AppState) => ({ alerts: [a, ...s.alerts].slice(0, 20) })),
  dismissAlert: (id: string) =>
    set((s: AppState) => ({ alerts: s.alerts.filter((x: AlertMessage) => x.id !== id) })),

  municipalToken: null,
  setMunicipalToken: (t: string | null) => set({ municipalToken: t }),

  fingerprint: generateFingerprint(),
}));
