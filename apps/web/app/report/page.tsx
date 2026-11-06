"use client";

import { useState } from "react";
import Map, { Marker, NavigationControl } from "react-map-gl/maplibre";
import { toast } from "sonner";
import { submitReport } from "@/lib/api";
import { useAppStore } from "@/lib/store";

const reportTypes = [
  { value: "waterlogging", label: "Waterlogging", emoji: "💧", desc: "Standing water on road" },
  { value: "flood", label: "Flood", emoji: "🌊", desc: "Road submerged" },
  { value: "pothole", label: "Pothole", emoji: "🕳️", desc: "Damaged road surface" },
  { value: "blocked_drain", label: "Blocked Drain", emoji: "🚧", desc: "Drain clogged/overflowing" },
  { value: "other", label: "Other", emoji: "📋", desc: "Other flood hazard" },
] as const;

const severityLabels = ["", "Minor", "Low", "Moderate", "High", "Severe"];
const severityColors = ["", "#10b981", "#22d3ee", "#f59e0b", "#f97316", "#ef4444"];

export default function ReportPage() {
  const fingerprint = useAppStore((s) => s.fingerprint) as string;
  const [type, setType] = useState<string>("waterlogging");
  const [severity, setSeverity] = useState(3);
  const [location, setLocation] = useState<{ lng: number; lat: number } | null>(null);
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!location) {
      toast.error("Please tap the map to mark the flood location.");
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
      toast.success(result.message);
      setSubmitted(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to submit report.");
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <main className="flex min-h-[80vh] items-center justify-center px-4">
        <div className="card mx-auto max-w-md p-8 text-center animate-scale-in">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-50 text-3xl">
            ✅
          </div>
          <h2 className="mt-4 text-xl font-extrabold text-slate-900">Report Submitted!</h2>
          <p className="mt-2 text-sm text-slate-600">
            Your report is pending verification. When 3 independent reports confirm the same area,
            it becomes verified and affects road risk scores.
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
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
      {/* Header */}
      <div className="mb-6">
        <p className="section-title">Citizen Reporting</p>
        <h1 className="page-title mt-1">Report a Flood Hazard</h1>
        <p className="mt-1 text-sm text-slate-500">
          Help make Pune&apos;s roads safer. Your anonymous report will be verified by nearby independent reports.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Report type */}
        <fieldset>
          <legend className="mb-3 text-sm font-bold text-slate-700">What did you observe?</legend>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
            {reportTypes.map((rt) => (
              <button
                key={rt.value}
                type="button"
                id={`report-type-${rt.value}`}
                aria-pressed={type === rt.value}
                onClick={() => setType(rt.value)}
                className={`card-interactive flex flex-col items-center gap-1.5 rounded-xl border p-3 text-center transition-all duration-200 ${
                  type === rt.value
                    ? "border-sky-300 bg-sky-50 shadow-md ring-2 ring-sky-200"
                    : "border-slate-200 bg-white hover:border-sky-200"
                }`}
              >
                <span className="text-2xl">{rt.emoji}</span>
                <span className="text-xs font-bold text-slate-800">{rt.label}</span>
                <span className="text-[10px] text-slate-500">{rt.desc}</span>
              </button>
            ))}
          </div>
        </fieldset>

        {/* Severity */}
        <fieldset>
          <legend className="mb-3 text-sm font-bold text-slate-700">Severity level</legend>
          <div className="flex items-center gap-3">
            <div className="flex flex-1 gap-1.5">
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
            <span className="w-20 text-right text-sm font-bold" style={{ color: severityColors[severity] }}>
              {severityLabels[severity]}
            </span>
          </div>
        </fieldset>

        {/* Map location */}
        <fieldset>
          <legend className="mb-3 text-sm font-bold text-slate-700">
            Tap the map to mark the location
          </legend>
          <div className="h-[280px] overflow-hidden rounded-2xl border border-slate-200 shadow-sm">
            <Map
              initialViewState={{ longitude: 73.865, latitude: 18.523, zoom: 12.4 }}
              mapStyle={process.env.NEXT_PUBLIC_MAP_STYLE_URL ?? "https://demotiles.maplibre.org/style.json"}
              onClick={(e) => setLocation({ lng: e.lngLat.lng, lat: e.lngLat.lat })}
              style={{ height: "100%", width: "100%" }}
            >
              <NavigationControl position="bottom-right" />
              {location && (
                <Marker anchor="bottom" latitude={location.lat} longitude={location.lng}>
                  <div className="animate-scale-in flex h-8 w-8 items-center justify-center rounded-full bg-rose-600 text-sm font-bold text-white shadow-lg ring-2 ring-white">
                    📍
                  </div>
                </Marker>
              )}
            </Map>
          </div>
          {location && (
            <p className="mt-2 text-xs text-slate-500">
              📍 {location.lat.toFixed(5)}, {location.lng.toFixed(5)}
            </p>
          )}
        </fieldset>

        {/* Description */}
        <div>
          <label htmlFor="report-description" className="mb-2 block text-sm font-bold text-slate-700">
            Description (optional)
          </label>
          <textarea
            id="report-description"
            className="input-field min-h-[80px] resize-y"
            maxLength={500}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe the situation — e.g., 'knee-deep water near the bus stop'"
            value={description}
          />
          <p className="mt-1 text-right text-[11px] text-slate-400">{description.length}/500</p>
        </div>

        {/* Submit */}
        <button
          className="btn-primary w-full py-3 text-base"
          disabled={submitting || !location}
          id="submit-report-btn"
          type="submit"
        >
          {submitting ? (
            <span className="animate-pulse-subtle">Submitting Report…</span>
          ) : (
            "Submit Flood Report"
          )}
        </button>
      </form>
    </main>
  );
}
