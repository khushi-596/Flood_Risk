"use client";

import { useState } from "react";
import Map, { Marker, NavigationControl } from "react-map-gl/maplibre";
import { toast } from "sonner";
import { submitReport } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { PlaceSearch } from "@/components/place-search";
import type { MapPoint } from "@/lib/types";

const reportTypes = [
  { value: "waterlogging", label: "Waterlogging", emoji: "💧", desc: "Standing water on road" },
  { value: "flood", label: "Flood", emoji: "🌊", desc: "Road submerged / impassable" },
  { value: "pothole", label: "Pothole", emoji: "🕳️", desc: "Damaged / sunken road surface" },
  { value: "blocked_drain", label: "Blocked Drain", emoji: "🚧", desc: "Drain clogged or overflowing" },
  { value: "other", label: "Other", emoji: "📋", desc: "Other flood or safety hazard" },
] as const;

const severityLabels = ["", "Minor (10cm)", "Low (20cm)", "Moderate (knee-deep)", "High (waist-deep)", "Severe (impassable)"];
const severityColors = ["", "#10b981", "#22d3ee", "#f59e0b", "#f97316", "#ef4444"];

const quickLocations = [
  { name: "Pune Station", lat: 18.5284, lng: 73.8739, emoji: "🏢" },
  { name: "Shivajinagar", lat: 18.5314, lng: 73.8446, emoji: "🏙️" },
  { name: "Deccan / FC Rd", lat: 18.5186, lng: 73.8415, emoji: "🌳" },
  { name: "Kothrud", lat: 18.5074, lng: 73.8077, emoji: "🏡" },
  { name: "Hinjawadi IT Park", lat: 18.5913, lng: 73.7389, emoji: "💻" },
  { name: "Viman Nagar", lat: 18.5679, lng: 73.9143, emoji: "✈️" },
  { name: "Hadapsar", lat: 18.5089, lng: 73.9260, emoji: "🏭" },
  { name: "Baner", lat: 18.5590, lng: 73.7868, emoji: "🛣️" },
  { name: "Katraj", lat: 18.4480, lng: 73.8580, emoji: "⛰️" },
  { name: "Pimpri", lat: 18.6298, lng: 73.7997, emoji: "🏭" },
];

export default function ReportPage() {
  const fingerprint = useAppStore((s) => s.fingerprint) as string;
  const [type, setType] = useState<string>("waterlogging");
  const [severity, setSeverity] = useState(3);
  const [location, setLocation] = useState<{ lng: number; lat: number; label?: string } | null>(null);
  const [viewState, setViewState] = useState({ longitude: 73.8567, latitude: 18.5204, zoom: 12.5 });
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [lastReceipt, setLastReceipt] = useState<{ id: string; status: string; segment_id: string; message: string } | null>(null);

  const defaultMapStyle =
    process.env.NEXT_PUBLIC_MAP_STYLE_URL || "https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json";

  function handlePlaceSelect(point: MapPoint) {
    setLocation({ lng: point.longitude, lat: point.latitude, label: point.label });
    setViewState({ longitude: point.longitude, latitude: point.latitude, zoom: 15 });
    toast.info(`Location pinned: ${point.label}`);
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
        toast.success("Location pinned to your current GPS position!");
      },
      (err) => {
        toast.error(`Unable to retrieve GPS location: ${err.message}`);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!location) {
      toast.error("Please pin the flood location on the map or search your area.");
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
      toast.success(result.message || "Report submitted successfully!");
      setSubmitted(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to submit report.");
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted && lastReceipt) {
    return (
      <main className="flex min-h-[80vh] items-center justify-center px-4">
        <div className="card mx-auto max-w-md p-8 text-center animate-scale-in">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 text-3xl">
            ✅
          </div>
          <h2 className="mt-4 text-xl font-extrabold text-slate-900">Flood Hazard Reported!</h2>
          <p className="mt-2 text-sm text-slate-600">
            {lastReceipt.message}
          </p>
          <div className="mt-4 rounded-xl bg-slate-50 p-3 text-left text-xs space-y-1">
            <p><span className="font-semibold text-slate-700">Snapped Segment:</span> <code className="bg-white px-1.5 py-0.5 rounded border border-slate-200">{lastReceipt.segment_id}</code></p>
            <p><span className="font-semibold text-slate-700">Status:</span> <span className="badge badge-status-pending">{lastReceipt.status}</span></p>
          </div>
          <p className="mt-3 text-xs text-slate-500">
            When 3 independent reports verify this spot or municipal staff confirms it, it increases the road hazard score to protect commuters.
          </p>
          <div className="mt-6 flex gap-3">
            <button className="btn-primary flex-1" onClick={() => setSubmitted(false)} type="button">
              Submit Another
            </button>
            <a className="btn-secondary flex-1" href="/my-reports">
              View My Reports
            </a>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
      {/* Header */}
      <div className="mb-6">
        <p className="section-title">Pune Citizen Reporting Portal</p>
        <h1 className="page-title mt-1">Report a Flood Hazard</h1>
        <p className="mt-1 text-sm text-slate-600">
          Help keep Pune safe during heavy rain. Anyone can submit a report without registration — reports snap to the nearest road across Greater Pune.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* 1. Report type */}
        <fieldset className="card p-4 sm:p-5">
          <legend className="mb-3 text-sm font-bold text-slate-800">1. What type of hazard did you observe?</legend>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
            {reportTypes.map((rt) => (
              <button
                key={rt.value}
                type="button"
                id={`report-type-${rt.value}`}
                aria-pressed={type === rt.value}
                onClick={() => setType(rt.value)}
                className={`flex flex-col items-center rounded-xl border p-3 text-center transition-all duration-200 ${
                  type === rt.value
                    ? "border-sky-500 bg-sky-50/80 text-sky-950 shadow-sm ring-2 ring-sky-500/20"
                    : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50"
                }`}
              >
                <span className="text-2xl">{rt.emoji}</span>
                <span className="mt-1.5 text-xs font-bold">{rt.label}</span>
                <span className="mt-0.5 text-[10px] text-slate-500">{rt.desc}</span>
              </button>
            ))}
          </div>
        </fieldset>

        {/* 2. Severity */}
        <fieldset className="card p-4 sm:p-5">
          <legend className="mb-3 text-sm font-bold text-slate-800">2. Water depth / Hazard severity</legend>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex flex-1 gap-1.5" role="group" aria-label="Severity rating 1 to 5">
              {[1, 2, 3, 4, 5].map((level) => (
                <button
                  key={level}
                  type="button"
                  id={`severity-${level}`}
                  aria-label={`Severity ${level}: ${severityLabels[level]}`}
                  onClick={() => setSeverity(level)}
                  className={`flex h-11 flex-1 items-center justify-center rounded-xl border text-sm font-bold transition-all duration-200 ${
                    severity >= level
                      ? "text-white shadow-sm"
                      : "border-slate-200 bg-white text-slate-400 hover:border-slate-300"
                  }`}
                  style={severity >= level ? { backgroundColor: severityColors[level], borderColor: severityColors[level] } : {}}
                >
                  {level}
                </button>
              ))}
            </div>
            <div className="rounded-xl bg-slate-50 px-3 py-2 text-right">
              <span className="text-xs font-semibold text-slate-500">Rating: </span>
              <span className="text-sm font-bold" style={{ color: severityColors[severity] }}>
                {severityLabels[severity]}
              </span>
            </div>
          </div>
        </fieldset>

        {/* 3. Location Picker */}
        <fieldset className="card p-4 sm:p-5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <legend className="text-sm font-bold text-slate-800">3. Where is this hazard located?</legend>
              <p className="text-xs text-slate-500">Search any Pune locality, click a quick button, or tap directly on the map.</p>
            </div>
            <button
              type="button"
              onClick={handleUseCurrentLocation}
              className="flex items-center gap-1.5 rounded-lg border border-sky-300 bg-sky-50 px-3 py-1.5 text-xs font-bold text-sky-800 hover:bg-sky-100 transition shadow-sm"
            >
              <span>📍</span> Use My Current Location
            </button>
          </div>

          {/* Place Search on Report Page */}
          <div className="pt-1">
            <PlaceSearch
              onPlaceSelect={handlePlaceSelect}
              placeholder="Type any Pune area (e.g. Hinjawadi, Kothrud, Baner, Swargate, Viman Nagar)…"
            />
          </div>

          {/* Quick Pune Area Chips */}
          <div>
            <p className="text-[11px] font-semibold text-slate-500 mb-1.5">Quick Locations across Pune:</p>
            <div className="flex flex-wrap gap-1.5">
              {quickLocations.map((loc) => (
                <button
                  key={loc.name}
                  type="button"
                  onClick={() => {
                    setLocation({ lng: loc.lng, lat: loc.lat, label: loc.name });
                    setViewState({ longitude: loc.lng, latitude: loc.lat, zoom: 14.5 });
                    toast.info(`Pinned: ${loc.name}`);
                  }}
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold border transition ${
                    location?.label === loc.name
                      ? "bg-sky-700 text-white border-sky-700 shadow-sm"
                      : "bg-slate-100 hover:bg-slate-200 text-slate-700 border-slate-200"
                  }`}
                >
                  <span className="mr-1">{loc.emoji}</span>
                  {loc.name}
                </button>
              ))}
            </div>
          </div>

          {/* Interactive Map */}
          <div className="relative h-[340px] overflow-hidden rounded-2xl border border-slate-300 shadow-sm mt-2">
            <Map
              longitude={viewState.longitude}
              latitude={viewState.latitude}
              zoom={viewState.zoom}
              onMove={(e) => setViewState(e.viewState)}
              mapStyle={defaultMapStyle}
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
                  <div className="animate-scale-in flex flex-col items-center">
                    <span className="rounded-md bg-slate-900/90 px-2 py-0.5 text-[10px] font-bold text-white shadow">
                      {location.label ? location.label.split(",")[0] : "Hazard Pin"}
                    </span>
                    <div className="h-9 w-9 flex items-center justify-center rounded-full bg-rose-600 text-base font-bold text-white shadow-xl ring-2 ring-white">
                      📍
                    </div>
                  </div>
                </Marker>
              )}
            </Map>
          </div>

          {/* Selected coordinates badge */}
          {location ? (
            <div className="flex items-center justify-between rounded-xl bg-emerald-50 border border-emerald-200 p-2.5 text-xs text-emerald-900">
              <div className="flex items-center gap-2">
                <span className="text-base">📌</span>
                <div>
                  <span className="font-bold">{location.label || "Map Location"}</span>
                  <span className="text-emerald-700 ml-2">
                    ({location.lat.toFixed(5)}, {location.lng.toFixed(5)})
                  </span>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setLocation(null)}
                className="text-[11px] font-bold text-emerald-800 hover:text-emerald-950 underline"
              >
                Clear
              </button>
            </div>
          ) : (
            <p className="text-xs text-slate-400 italic">
              Tap anywhere on the map above or pick a quick location to place the pin.
            </p>
          )}
        </fieldset>

        {/* 4. Description */}
        <fieldset className="card p-4 sm:p-5">
          <label htmlFor="report-desc" className="mb-2 block text-sm font-bold text-slate-800">
            4. Details / Landmark description (optional)
          </label>
          <textarea
            id="report-desc"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            maxLength={500}
            placeholder="e.g. Water 1 foot deep near the bus stop, drain blocked with tree debris…"
            className="input-field resize-none text-xs"
          />
          <div className="mt-1 text-right text-[10px] text-slate-400">{description.length}/500</div>
        </fieldset>

        {/* Submit button */}
        <button
          type="submit"
          disabled={submitting || !location}
          className="btn-primary w-full py-3.5 text-sm font-bold shadow-md hover:shadow-lg transition disabled:opacity-50"
        >
          {submitting ? "Submitting Report…" : "Submit Flood Report 🚀"}
        </button>
      </form>
    </main>
  );
}
