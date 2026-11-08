"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from "recharts";
import { getSegmentExplanation } from "@/lib/api";
import type { SegmentExplanation } from "@/lib/types";
import { AlertTriangleIcon, ShieldCheckIcon } from "@/components/icons";

const signalLabels: Record<string, string> = {
  terrain: "Terrain / Elevation",
  rainfall: "Rainfall Pressure",
  flood_history: "Historical Hotspot",
  drainage: "Drainage Clearance",
  citizen_reports: "Verified Reports",
};

const signalColors: Record<string, string> = {
  terrain: "#6366f1",
  rainfall: "#0ea5e9",
  flood_history: "#f59e0b",
  drainage: "#10b981",
  citizen_reports: "#ec4899",
};

const bandBadge: Record<string, { label: string; className: string }> = {
  low: { label: "Low", className: "bg-emerald-100 text-emerald-800 border-emerald-300" },
  moderate: { label: "Moderate", className: "bg-amber-100 text-amber-800 border-amber-300" },
  high: { label: "High", className: "bg-rose-100 text-rose-800 border-rose-300" },
  severe: { label: "Severe", className: "bg-rose-200 text-rose-950 border-rose-400 font-black" },
};

const confidenceStyles: Record<string, { label: string; className: string }> = {
  HIGH: { label: "Confidence: HIGH", className: "bg-emerald-100 text-emerald-900 border-emerald-300" },
  MEDIUM: { label: "Confidence: MEDIUM", className: "bg-amber-100 text-amber-900 border-amber-300" },
  LOW: { label: "Confidence: LOW", className: "bg-slate-100 text-slate-700 border-slate-300" },
};

type Props = {
  segmentId: string | null;
  onClose: () => void;
};

export function SegmentExplanationPanel({ segmentId, onClose }: Props) {
  const [data, setData] = useState<SegmentExplanation | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!segmentId) {
      setData(null);
      return;
    }
    setLoading(true);
    getSegmentExplanation(segmentId)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [segmentId]);

  if (!segmentId) return null;

  const currentRiskPercent = data ? Math.round(data.risk_score * 100) : 0;
  const staticVulnPercent = data ? Math.round(data.static_vulnerability_score * 100) : 0;
  const currentBandInfo = data ? bandBadge[data.risk_band] ?? bandBadge.low : bandBadge.low;
  const staticBandInfo = data ? bandBadge[data.static_vulnerability_band] ?? bandBadge.low : bandBadge.low;
  const confInfo = data ? confidenceStyles[data.confidence_level] ?? confidenceStyles.MEDIUM : confidenceStyles.MEDIUM;

  return (
    <div className="animate-slide-up">
      <div className="frosted-panel p-5 space-y-4">
        {/* Header with road name */}
        <div className="flex items-start justify-between gap-3 border-b border-slate-200/60 pb-3">
          <div className="min-w-0 flex-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Segment Flood Risk &amp; Vulnerability
            </span>
            {data && (
              <h3 className="text-base font-black text-slate-900 leading-snug truncate mt-0.5">
                {data.name}
              </h3>
            )}
          </div>
          <button
            aria-label="Close explanation panel"
            className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
            id="close-explanation-panel"
            onClick={onClose}
            type="button"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {loading && (
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 py-4">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-sky-600 border-t-transparent" />
            Analyzing road elevation, historical data &amp; precipitation…
          </div>
        )}

        {data && !loading && (
          <div className="space-y-4">
            {/* FEATURE 2: Static Flood Vulnerability vs Current Dynamic Risk */}
            <div className="grid grid-cols-2 gap-2.5">
              {/* Static Vulnerability Card */}
              <div className="rounded-xl border border-slate-200/90 bg-slate-50/90 p-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 block">
                  Static Vulnerability
                </span>
                <div className="mt-1 flex items-baseline gap-1.5">
                  <span className="text-xl font-black text-slate-900">{staticVulnPercent}/100</span>
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${staticBandInfo.className}`}>
                    {staticBandInfo.label}
                  </span>
                </div>
                <p className="mt-1 text-[10px] text-slate-500 leading-tight">
                  Natural terrain, slope &amp; drain clearance (offline baseline).
                </p>
              </div>

              {/* Dynamic Flood Risk Card */}
              <div className="rounded-xl border border-sky-200 bg-sky-50/70 p-3">
                <span className="text-[10px] font-bold uppercase tracking-wider text-sky-800 block">
                  Current Flood Risk
                </span>
                <div className="mt-1 flex items-baseline gap-1.5">
                  <span className="text-xl font-black text-slate-900">{currentRiskPercent}/100</span>
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${currentBandInfo.className}`}>
                    {currentBandInfo.label}
                  </span>
                </div>
                <p className="mt-1 text-[10px] text-sky-900/80 leading-tight">
                  Static vulnerability + live rain intensity + active crowd reports.
                </p>
              </div>
            </div>

            {/* FEATURE 8: Confidence Level & Evidence Narrative */}
            <div className="rounded-xl border border-slate-200/80 bg-white/80 p-3 space-y-1">
              <div className="flex items-center justify-between">
                <span className={`text-[10px] font-black px-2 py-0.5 rounded-full border tracking-wide ${confInfo.className}`}>
                  {confInfo.label}
                </span>
                <span className="text-[11px] font-bold text-slate-700">
                  {Math.round(data.confidence * 100)}% Evidence Index
                </span>
              </div>
              <p className="text-[11px] text-slate-600 leading-snug pt-0.5">
                {data.confidence_evidence}
              </p>
            </div>

            {/* ADDITIONAL FEATURE 2: Drainage Failure Detection Alert */}
            {data.drainage_degradation_flag && (
              <div className="rounded-xl border border-rose-300 bg-rose-50/90 p-3 animate-pulse-subtle">
                <div className="flex items-start gap-2">
                  <AlertTriangleIcon size={16} className="text-rose-600 shrink-0 mt-0.5" />
                  <div>
                    <h4 className="text-xs font-black text-rose-950">
                      🚨 Possible Drainage Degradation Detected
                    </h4>
                    <p className="mt-0.5 text-[11px] text-rose-800 leading-relaxed font-medium">
                      {data.drainage_degradation_message ??
                        "Waterlogging observed despite rainfall being well below historical road design threshold. Siltation or drain blockage suspected."}
                    </p>
                  </div>
                </div>
              </div>
            )}

            {/* FEATURE 7: Physical Risk Factors / Explainability */}
            <div className="space-y-2">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center justify-between">
                <span>Physical Risk Factors</span>
                <span className="text-[10px] font-normal text-slate-400">Ground Truth Attributes</span>
              </h4>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="rounded-xl bg-slate-50/80 border border-slate-200/70 p-2.5">
                  <span className="text-[10px] text-slate-500 font-semibold block">Elevation</span>
                  <span className="font-bold text-slate-800 text-xs mt-0.5 block">
                    {data.metrics?.elevation_label ?? "Moderate (28m ASL)"}
                  </span>
                </div>

                <div className="rounded-xl bg-slate-50/80 border border-slate-200/70 p-2.5">
                  <span className="text-[10px] text-slate-500 font-semibold block">Road Slope</span>
                  <span className="font-bold text-slate-800 text-xs mt-0.5 block">
                    {data.metrics?.slope_label ?? "Low (< 1.5% flat)"}
                  </span>
                </div>

                <div className="rounded-xl bg-slate-50/80 border border-slate-200/70 p-2.5">
                  <span className="text-[10px] text-slate-500 font-semibold block">Distance to Water / Drains</span>
                  <span className="font-bold text-slate-800 text-xs mt-0.5 block">
                    {data.metrics?.distance_to_water_m ?? 120} m
                  </span>
                </div>

                <div className="rounded-xl bg-slate-50/80 border border-slate-200/70 p-2.5">
                  <span className="text-[10px] text-slate-500 font-semibold block">Historical Flood Events</span>
                  <span className="font-bold text-slate-800 text-xs mt-0.5 block">
                    {data.metrics?.historical_flood_incidents ?? 2} documented incidents
                  </span>
                </div>

                <div className="rounded-xl bg-slate-50/80 border border-slate-200/70 p-2.5">
                  <span className="text-[10px] text-slate-500 font-semibold block">Current Rainfall Rate</span>
                  <span className="font-bold text-slate-800 text-xs mt-0.5 block">
                    {data.metrics?.current_rainfall_mm_hr ?? 0} mm/hr
                  </span>
                </div>

                <div className="rounded-xl bg-slate-50/80 border border-slate-200/70 p-2.5">
                  <span className="text-[10px] text-slate-500 font-semibold block">Flood Capacity Threshold (T_seg)</span>
                  <span className="font-bold text-slate-800 text-xs mt-0.5 block">
                    {data.metrics?.historical_flood_threshold_mm_hr ?? 30} mm/hr
                  </span>
                </div>
              </div>
            </div>

            {/* Factor Contributions Chart */}
            <div className="space-y-1.5 pt-1">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                Factor Contributions to Flood Score
              </h4>
              <div className="h-[150px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={Object.entries(data.weighted_contributions).map(([key, value]) => ({
                      name: signalLabels[key] ?? key,
                      value: Math.round(value * 1000) / 10,
                      key,
                    }))}
                    layout="vertical"
                    margin={{ top: 0, right: 16, bottom: 0, left: 100 }}
                  >
                    <XAxis type="number" domain={[0, "auto"]} tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                    <YAxis type="category" dataKey="name" tick={{ fontSize: 10, fill: "#475569", fontWeight: 600 }} axisLine={false} tickLine={false} width={95} />
                    <Tooltip
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      formatter={(val: any) => [`${val}%`, "Impact"]}
                      contentStyle={{
                        borderRadius: "0.75rem",
                        border: "1px solid #e2e8f0",
                        boxShadow: "0 4px 20px rgba(0,0,0,0.06)",
                        fontSize: 12,
                      }}
                    />
                    <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={18}>
                      {Object.keys(data.weighted_contributions).map((key) => (
                        <Cell key={key} fill={signalColors[key] ?? "#94a3b8"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Top Reasons / Insights */}
            {data.reasons && data.reasons.length > 0 && (
              <div className="space-y-1.5 pt-1 border-t border-slate-200/50">
                <h4 className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                  Primary Risk Contributors
                </h4>
                <ul className="space-y-1">
                  {data.reasons.map((reason, i) => (
                    <li key={i} className="flex items-center gap-2 text-xs text-slate-700 bg-slate-50/70 rounded-lg px-2.5 py-1.5 border border-slate-200/50">
                      <span className="h-1.5 w-1.5 rounded-full bg-amber-500 shrink-0" />
                      <span className="capitalize">{reason}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Active Verified Reports */}
            {data.active_verified_reports > 0 && (
              <div className="flex items-center gap-2 rounded-xl bg-purple-50 px-3 py-2 text-xs font-semibold text-purple-900 border border-purple-200">
                <ShieldCheckIcon size={14} className="text-purple-600 shrink-0" />
                <span>{data.active_verified_reports} verified citizen hazard report{data.active_verified_reports > 1 ? "s" : ""} on this segment</span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
