"use client";

import { useEffect, useState } from "react";
import Map, { Marker, NavigationControl } from "react-map-gl/maplibre";
import { toast } from "sonner";
import { submitReport, getMyReports } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { PlaceSearch } from "@/components/place-search";
import type { CrowdReport, MapPoint } from "@/lib/types";
import {
  WaterDropIcon,
  WavesIcon,
  PotholeIcon,
  HazardDrainIcon,
  ClipboardIcon,
  CrosshairIcon,
  ShieldCheckIcon,
  AlertTriangleIcon,
} from "@/components/icons";
import { GOOGLE_MAPS_STREETS_STYLE } from "@/lib/map-styles";

type ReportTypeKey = "waterlogging" | "flood" | "pothole" | "blocked_drain" | "other";

const reportTypes: {
  value: ReportTypeKey;
  label: string;
  desc: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
}[] = [
  { value: "waterlogging", label: "Waterlogging", desc: "Standing water on road", icon: WaterDropIcon },
  { value: "flood", label: "Submerged Road", desc: "Road submerged / impassable", icon: WavesIcon },
  { value: "pothole", label: "Pothole Hazard", desc: "Damaged / sunken road surface", icon: PotholeIcon },
  { value: "blocked_drain", label: "Blocked Drainage", desc: "Drain clogged or overflowing", icon: HazardDrainIcon },
  { value: "other", label: "Other Hazard", desc: "Other flood or safety concern", icon: ClipboardIcon },
];

const severityLabels = ["", "Minor (~10cm)", "Low (~20cm)", "Moderate (Knee-deep)", "High (Waist-deep)", "Severe (Impassable)"];
const severityColors = ["", "#10b981", "#0ea5e9", "#f59e0b", "#f97316", "#ef4444"];

const quickLocations = [
  { name: "Pune Station", lat: 18.5284, lng: 73.8739 },
  { name: "Shivajinagar", lat: 18.5314, lng: 73.8446 },
  { name: "Deccan / FC Rd", lat: 18.5186, lng: 73.8415 },
  { name: "Kothrud", lat: 18.5074, lng: 73.8077 },
  { name: "Hinjawadi IT Park", lat: 18.5913, lng: 73.7389 },
  { name: "Viman Nagar", lat: 18.5679, lng: 73.9143 },
  { name: "Hadapsar", lat: 18.5089, lng: 73.9260 },
  { name: "Baner", lat: 18.5590, lng: 73.7868 },
  { name: "Katraj", lat: 18.4480, lng: 73.8580 },
  { name: "Pimpri", lat: 18.6298, lng: 73.7997 },
];

const statusBadgeStyles: Record<string, string> = {
  pending: "bg-slate-100 text-slate-700 border border-slate-200",
  verified: "bg-emerald-50 text-emerald-800 border border-emerald-200",
  rejected: "bg-rose-50 text-rose-800 border border-rose-200",
  resolved: "bg-sky-50 text-sky-800 border border-sky-200",
};

export default function ReportPage() {
  const fingerprint = useAppStore((s) => s.fingerprint) as string;

  // Tab State: "submit" or "history"
  const [activeTab, setActiveTab] = useState<"submit" | "history">("submit");

  // Form State
  const [type, setType] = useState<ReportTypeKey>("waterlogging");
  const [severity, setSeverity] = useState(3);
  const [location, setLocation] = useState<{ lng: number; lat: number; label?: string } | null>(null);
  const [viewState, setViewState] = useState({ longitude: 73.8567, latitude: 18.5204, zoom: 12.5 });
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [lastReceipt, setLastReceipt] = useState<{ id: string; status: string; segment_id: string; message: string } | null>(null);

  // History State
  const [myReports, setMyReports] = useState<CrowdReport[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);


  // Check URL params for tab on load
  useEffect(() => {
    if (typeof window !== "undefined") {
      const urlParams = new URLSearchParams(window.location.search);
      if (urlParams.get("tab") === "history") {
        setActiveTab("history");
      }
    }
  }, []);

  // Fetch reports when switching to history or fingerprint ready
  useEffect(() => {
    if (!fingerprint || fingerprint === "ssr-placeholder") return;
    setLoadingHistory(true);
    getMyReports(fingerprint)
      .then(setMyReports)
      .catch(() => {})
      .finally(() => setLoadingHistory(false));
  }, [fingerprint, activeTab]);

  function handlePlaceSelect(point: MapPoint) {
    setLocation({ lng: point.longitude, lat: point.latitude, label: point.label });
    setViewState({ longitude: point.longitude, latitude: point.latitude, zoom: 15 });
    toast.success(`Location set: ${point.label}`);
  }

  function handleUseCurrentLocation() {
    if (!navigator.geolocation) {
      toast.error("Geolocation is not supported by your browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lng = pos.coords.longitude;
        const lat = pos.coords.latitude;
        setLocation({ lng, lat, label: "Current GPS Location" });
        setViewState({ longitude: lng, latitude: lat, zoom: 15.5 });
        toast.success("Location pinned to your current GPS position");
      },
      (err) => {
        toast.error(`Unable to retrieve GPS: ${err.message}`);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!location) {
      toast.error("Please pin the hazard location on the map or search your area.");
      return;
    }
    setSubmitting(true);
    try {
      const result = await submitReport({
        report_type: type,
        severity,
        longitude: location.lng,
        latitude: location.lat,
        description: description || undefined,
        reporter_fingerprint: fingerprint,
      });
      setLastReceipt(result);
      toast.success(result.message || "Hazard report submitted successfully");
      setSubmitted(true);
      // Refresh history list
      getMyReports(fingerprint).then(setMyReports).catch(() => {});
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to submit hazard report.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6 space-y-6">
      {/* Luxury Aquatic Blue Glassmorphism Header */}
      <div className="luxury-glass-blue water-droplets-pattern rounded-3xl p-6 sm:p-7 text-white border border-sky-400/20 shadow-xl flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1.5">
          <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-sky-300">
            Citizen Flood Portal
          </p>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white drop-shadow-sm">
            Hazard Reports &amp; Activity
          </h1>
          <p className="text-xs text-sky-100/80 max-w-xl leading-relaxed">
            Crowdsourced flood data verified by citizens and municipal staff. Verified reports immediately calibrate road safety scores.
          </p>
        </div>

        {/* Tab Switcher */}
        <div className="flex items-center rounded-2xl bg-white/10 p-1 border border-white/15 backdrop-blur-md self-start sm:self-auto">
          <button
            type="button"
            onClick={() => setActiveTab("submit")}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
              activeTab === "submit"
                ? "bg-white text-slate-900 shadow-md"
                : "text-sky-100/80 hover:text-white hover:bg-white/10"
            }`}
          >
            <AlertTriangleIcon size={14} className={activeTab === "submit" ? "text-amber-600" : "text-sky-300"} />
            <span>Submit Report</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("history")}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 text-xs font-bold transition-all ${
              activeTab === "history"
                ? "bg-white text-slate-900 shadow-md"
                : "text-sky-100/80 hover:text-white hover:bg-white/10"
            }`}
          >
            <ClipboardIcon size={14} className={activeTab === "history" ? "text-sky-600" : "text-sky-300"} />
            <span>My Reports &amp; History</span>
            {myReports.length > 0 && (
              <span className="ml-1 rounded-full bg-cyan-400 text-slate-900 text-[10px] font-black px-1.5 py-0.2">
                {myReports.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* TAB 1: SUBMIT HAZARD REPORT */}
      {activeTab === "submit" && (
        <>
          {submitted && lastReceipt ? (
            <div className="frosted-panel p-8 text-center animate-scale-in max-w-lg mx-auto space-y-4">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600 border border-emerald-200">
                <ShieldCheckIcon size={28} />
              </div>
              <div>
                <h2 className="text-lg font-black text-slate-900">Hazard Report Received</h2>
                <p className="text-xs text-slate-600 mt-1">{lastReceipt.message}</p>
              </div>

              <div className="rounded-xl bg-slate-50 border border-slate-200/70 p-3 text-left text-xs space-y-1.5">
                <div className="flex justify-between">
                  <span className="font-semibold text-slate-500">Snapped Segment:</span>
                  <code className="bg-white px-2 py-0.5 rounded border border-slate-200 font-mono text-slate-800">
                    {lastReceipt.segment_id}
                  </code>
                </div>
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-slate-500">Status:</span>
                  <span className={`badge ${statusBadgeStyles[lastReceipt.status] ?? "badge-status-pending"}`}>
                    {lastReceipt.status}
                  </span>
                </div>
              </div>

              <p className="text-[11px] text-slate-400 leading-relaxed">
                When 3 independent reports corroborate this location or municipal staff approves it, it elevates the road hazard score to protect commuters.
              </p>

              <div className="flex gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setSubmitted(false)}
                  className="btn-secondary flex-1 py-2 text-xs"
                >
                  Submit Another Report
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("history")}
                  className="btn-primary flex-1 py-2 text-xs"
                >
                  View My Reports
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* 1. Hazard Type */}
              <div className="frosted-card p-5">
                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-3">
                  1. Observed Hazard Type
                </h2>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
                  {reportTypes.map((rt) => {
                    const Icon = rt.icon;
                    const isSelected = type === rt.value;
                    return (
                      <button
                        key={rt.value}
                        type="button"
                        id={`report-type-${rt.value}`}
                        onClick={() => setType(rt.value)}
                        className={`flex flex-col items-center justify-center rounded-xl p-3 border text-center transition-all ${
                          isSelected
                            ? "border-sky-500 bg-sky-50 text-sky-950 font-bold shadow-xs ring-2 ring-sky-500/15"
                            : "border-slate-200/90 bg-white/80 hover:bg-white text-slate-600 hover:border-slate-300"
                        }`}
                      >
                        <Icon size={22} className={isSelected ? "text-sky-700" : "text-slate-500"} />
                        <span className="mt-1.5 text-xs font-bold">{rt.label}</span>
                        <span className="text-[10px] text-slate-400 mt-0.5">{rt.desc}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* 2. Water Depth Severity */}
              <div className="frosted-card p-5">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                    2. Water Depth / Hazard Severity
                  </h2>
                  <span className="text-xs font-bold" style={{ color: severityColors[severity] }}>
                    Level {severity}: {severityLabels[severity]}
                  </span>
                </div>
                <div className="flex gap-2">
                  {[1, 2, 3, 4, 5].map((lvl) => (
                    <button
                      key={lvl}
                      type="button"
                      onClick={() => setSeverity(lvl)}
                      className={`h-10 flex-1 rounded-xl text-xs font-black transition-all border ${
                        severity >= lvl
                          ? "text-white shadow-xs"
                          : "border-slate-200 bg-white/70 text-slate-400 hover:border-slate-300"
                      }`}
                      style={severity >= lvl ? { backgroundColor: severityColors[lvl], borderColor: severityColors[lvl] } : {}}
                    >
                      {lvl}
                    </button>
                  ))}
                </div>
              </div>

              {/* 3. Location Picker */}
              <div className="frosted-card p-5 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="text-xs font-bold uppercase tracking-wider text-slate-700">
                      3. Hazard Location
                    </h2>
                    <p className="text-[11px] text-slate-500">
                      Search any Pune area, choose a quick location, or tap directly on the map.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleUseCurrentLocation}
                    className="flex items-center gap-1.5 rounded-xl border border-sky-300 bg-sky-50 px-3 py-1.5 text-xs font-bold text-sky-800 hover:bg-sky-100 transition shadow-xs"
                  >
                    <CrosshairIcon size={14} className="text-sky-700" />
                    <span>My Current GPS</span>
                  </button>
                </div>

                <PlaceSearch
                  onPlaceSelect={handlePlaceSelect}
                  placeholder="Search Pune locality (e.g. Hinjawadi, Kothrud, Baner, Swargate)…"
                />

                {/* Quick Locations */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {quickLocations.map((loc) => (
                    <button
                      key={loc.name}
                      type="button"
                      onClick={() => {
                        setLocation({ lng: loc.lng, lat: loc.lat, label: loc.name });
                        setViewState({ longitude: loc.lng, latitude: loc.lat, zoom: 14.5 });
                        toast.info(`Pinned: ${loc.name}`);
                      }}
                      className={`rounded-full px-2.5 py-0.5 text-[11px] font-semibold border transition ${
                        location?.label === loc.name
                          ? "bg-slate-900 text-white border-slate-900 shadow-xs"
                          : "bg-white/80 hover:bg-slate-100 text-slate-600 border-slate-200/80"
                      }`}
                    >
                      {loc.name}
                    </button>
                  ))}
                </div>

                {/* Interactive Mini Map (Google Maps Visual) */}
                <div className="relative h-[300px] sm:h-[340px] overflow-hidden rounded-2xl border border-slate-300/80 shadow-sm">
                  <Map
                    key="report-submit-map"
                    longitude={viewState.longitude}
                    latitude={viewState.latitude}
                    zoom={viewState.zoom}
                    onMove={(e) => setViewState(e.viewState)}
                    mapStyle={GOOGLE_MAPS_STREETS_STYLE}
                    onClick={(e) => {
                      setLocation({
                        lng: e.lngLat.lng,
                        lat: e.lngLat.lat,
                        label: `Custom Pin (${e.lngLat.lat.toFixed(4)}, ${e.lngLat.lng.toFixed(4)})`,
                      });
                    }}
                    style={{ height: "100%", width: "100%" }}
                  >
                    <NavigationControl position="bottom-right" />
                    {location && (
                      <Marker anchor="bottom" latitude={location.lat} longitude={location.lng}>
                        <div className="flex flex-col items-center">
                          <span className="rounded bg-slate-900/90 text-white text-[10px] font-bold px-2 py-0.5 shadow-sm">
                            {location.label ? location.label.split(",")[0] : "Hazard"}
                          </span>
                          <div className="h-7 w-7 rounded-full bg-rose-600 text-white flex items-center justify-center font-bold text-xs shadow-lg ring-2 ring-white">
                            !
                          </div>
                        </div>
                      </Marker>
                    )}
                  </Map>
                  <div className="absolute top-3 left-3 z-10 glass-card px-3 py-1 text-[11px] font-bold text-slate-800 shadow-sm flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-rose-500 animate-pulse" />
                    <span>Click or drag map to place hazard pin</span>
                  </div>
                </div>

                {location ? (
                  <div className="flex items-center justify-between rounded-xl bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-900">
                    <span className="font-semibold">
                      Selected: {location.label || "Map Pin"} ({location.lat.toFixed(4)}, {location.lng.toFixed(4)})
                    </span>
                    <button
                      type="button"
                      onClick={() => setLocation(null)}
                      className="text-emerald-700 hover:text-emerald-950 font-bold underline text-[11px]"
                    >
                      Clear
                    </button>
                  </div>
                ) : (
                  <p className="text-[11px] text-slate-400 italic">
                    Tap anywhere on the map above or pick a quick location to position the hazard pin.
                  </p>
                )}
              </div>

              {/* 4. Description */}
              <div className="frosted-card p-5">
                <label htmlFor="report-desc" className="text-xs font-bold uppercase tracking-wider text-slate-700 mb-2 block">
                  4. Details / Landmark Notes (Optional)
                </label>
                <textarea
                  id="report-desc"
                  rows={2}
                  maxLength={500}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="e.g. Water 1 foot deep near the bus stop, drain blocked with tree debris…"
                  className="input-field text-xs resize-none"
                />
                <div className="text-right text-[10px] text-slate-400 mt-1">{description.length}/500</div>
              </div>

              {/* Submit Button */}
              <button
                type="submit"
                disabled={submitting || !location}
                className="btn-primary w-full py-3 text-sm font-bold shadow-md hover:shadow-lg transition disabled:opacity-50"
              >
                {submitting ? "Submitting Report…" : "Submit Hazard Report"}
              </button>
            </form>
          )}
        </>
      )}

      {/* TAB 2: MY REPORTS & HISTORY (Merged) */}
      {activeTab === "history" && (
        <div className="space-y-4">
          {loadingHistory && (
            <div className="flex items-center gap-2 py-10 justify-center text-xs text-slate-500">
              <span className="animate-spin h-4 w-4 border-2 border-sky-600 border-t-transparent rounded-full" />
              <span>Loading your report history…</span>
            </div>
          )}

          {!loadingHistory && (
            <>
              {/* Interactive Citizen Records Google Map */}
              <div className="relative h-[320px] sm:h-[360px] overflow-hidden rounded-3xl border border-slate-300/80 shadow-md">
                <Map
                  key="citizen-history-map"
                  initialViewState={{
                    longitude: myReports[0]?.longitude || 73.8567,
                    latitude: myReports[0]?.latitude || 18.5204,
                    zoom: myReports.length > 0 ? 12.8 : 12,
                  }}
                  mapStyle={GOOGLE_MAPS_STREETS_STYLE}
                  style={{ height: "100%", width: "100%" }}
                >
                  <NavigationControl position="bottom-right" />
                  {myReports.map((rep) => (
                    <Marker
                      key={rep.id}
                      anchor="bottom"
                      latitude={rep.latitude}
                      longitude={rep.longitude}
                      onClick={(e) => {
                        e.originalEvent.stopPropagation();
                        setSelectedReportId(rep.id);
                        const el = document.getElementById(`report-${rep.id}`);
                        el?.scrollIntoView({ behavior: "smooth", block: "center" });
                      }}
                    >
                      <div className="flex flex-col items-center cursor-pointer group">
                        <span className="rounded bg-slate-900/90 text-white text-[10px] font-bold px-2 py-0.5 shadow-sm whitespace-nowrap">
                          {rep.report_type.replace("_", " ")}
                        </span>
                        <div
                          className={`h-7 w-7 rounded-full text-white flex items-center justify-center font-bold text-xs shadow-lg ring-2 ring-white transform transition ${
                            selectedReportId === rep.id ? "scale-125 ring-sky-400" : "group-hover:scale-110"
                          }`}
                          style={{ backgroundColor: severityColors[rep.severity] || "#ef4444" }}
                        >
                          {rep.severity}
                        </div>
                      </div>
                    </Marker>
                  ))}
                </Map>

                {/* Map Floating Header Overlay */}
                <div className="absolute top-3 left-3 z-10 glass-card px-3.5 py-1.5 text-xs font-bold text-slate-800 shadow-sm flex items-center gap-2">
                  <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                  <span>Citizen Records Map</span>
                  <span className="rounded-full bg-sky-100 text-sky-800 text-[10px] px-2 py-0.5 font-black">
                    {myReports.length} {myReports.length === 1 ? "Record" : "Records"}
                  </span>
                </div>
              </div>

              {myReports.length === 0 ? (
                <div className="frosted-panel p-10 text-center space-y-3">
                  <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
                    <ClipboardIcon size={24} />
                  </div>
                  <h3 className="text-sm font-bold text-slate-700">No Submitted Reports Yet</h3>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto">
                    Reports you submit from this device will be tracked here and plotted on the map above so you can monitor verification by municipal staff.
                  </p>
                  <button
                    type="button"
                    onClick={() => setActiveTab("submit")}
                    className="btn-primary text-xs px-4 py-2 mt-2"
                  >
                    Submit a Hazard Report
                  </button>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs text-slate-500 px-1">
                    <span>{myReports.length} hazard report{myReports.length > 1 ? "s" : ""} on record</span>
                    <span>Click any pin to highlight report</span>
                  </div>

                  {myReports.map((report) => (
                    <article
                      key={report.id}
                      className={`frosted-card p-4 transition space-y-2.5 ${
                        selectedReportId === report.id ? "ring-2 ring-sky-500 bg-sky-50/50" : ""
                      }`}
                      id={`report-${report.id}`}
                      onClick={() => setSelectedReportId(report.id)}
                    >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-slate-700">
                        {report.report_type === "waterlogging" ? (
                          <WaterDropIcon size={18} />
                        ) : report.report_type === "flood" ? (
                          <WavesIcon size={18} />
                        ) : report.report_type === "pothole" ? (
                          <PotholeIcon size={18} />
                        ) : report.report_type === "blocked_drain" ? (
                          <HazardDrainIcon size={18} />
                        ) : (
                          <ClipboardIcon size={18} />
                        )}
                      </div>
                      <div>
                        <h4 className="text-xs font-bold capitalize text-slate-900">
                          {report.report_type.replace("_", " ")}
                        </h4>
                        <p className="text-[11px] text-slate-500">
                          Road Segment: <code className="bg-slate-100 px-1 rounded font-mono">{report.segment_id}</code>
                        </p>
                      </div>
                    </div>

                    <span className={`badge ${statusBadgeStyles[report.status] ?? "badge-status-pending"}`}>
                      {report.status}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
                    <div className="flex items-center gap-1">
                      <span className="text-[11px] text-slate-400">Severity:</span>
                      <div className="flex gap-0.5">
                        {[1, 2, 3, 4, 5].map((lvl) => (
                          <span
                            key={lvl}
                            className="h-2 w-2 rounded-full"
                            style={{ backgroundColor: report.severity >= lvl ? severityColors[lvl] : "#e2e8f0" }}
                          />
                        ))}
                      </div>
                      <span className="font-bold text-[11px]" style={{ color: severityColors[report.severity] }}>
                        {report.severity}/5
                      </span>
                    </div>

                    <span className="text-[11px] text-slate-400">
                      Coordinates: {report.latitude.toFixed(4)}, {report.longitude.toFixed(4)}
                    </span>
                  </div>

                  {report.description && (
                    <p className="rounded-xl bg-slate-50/90 border border-slate-200/60 p-2.5 text-xs text-slate-700 leading-relaxed">
                      {report.description}
                    </p>
                  )}

                  <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1 border-t border-slate-100">
                    <span>Submitted: {new Date(report.created_at).toLocaleString()}</span>
                    {report.verified_at && (
                      <span className="text-emerald-700 font-bold">
                        Verified: {new Date(report.verified_at).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </>
      )}
        </div>
      )}
    </main>
  );
}
