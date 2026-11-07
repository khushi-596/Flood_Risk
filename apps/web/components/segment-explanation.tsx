"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from "recharts";
import { getSegmentExplanation } from "@/lib/api";
import type { SegmentExplanation } from "@/lib/types";

const signalLabels: Record<string, string> = {
  terrain: "Terrain",
  rainfall: "Rainfall",
  flood_history: "Flood History",
  drainage: "Drainage",
  citizen_reports: "Citizen Reports",
};

const signalColors: Record<string, string> = {
  terrain: "#6366f1",
  rainfall: "#0ea5e9",
  flood_history: "#f59e0b",
  drainage: "#10b981",
  citizen_reports: "#ec4899",
};

const bandBadge: Record<string, string> = {
  low: "badge badge-low",
  moderate: "badge badge-moderate",
  high: "badge badge-high",
  severe: "badge badge-severe",
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

  return (
    <div className="animate-slide-up">
      <div className="card p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <p className="section-title">Road Risk Explanation</p>
            {data && (
              <h3 className="mt-1 truncate text-lg font-extrabold text-slate-900">
                {data.name}
              </h3>
            )}
          </div>
          <button
            aria-label="Close explanation panel"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
            id="close-explanation-panel"
            onClick={onClose}
            type="button"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </div>

        {loading && (
          <div className="mt-4 flex items-center gap-2 text-sm text-slate-500">
            <span className="animate-pulse-subtle">●</span> Loading explanation…
          </div>
        )}

        {data && !loading && (
          <div className="mt-4 space-y-5">
            {/* Score + Confidence row */}
            <div className="flex flex-wrap gap-3">
              <div className="flex-1 rounded-xl bg-slate-50 p-3">
                <p className="text-xs font-medium text-slate-500">Risk Score</p>
                <p className="mt-1 text-2xl font-black text-slate-900">
                  {Math.round(data.risk_score * 100)}%
                </p>
                <span className={`mt-1 ${bandBadge[data.risk_band] ?? "badge"}`}>
                  {data.risk_band}
                </span>
              </div>
              <div className="flex-1 rounded-xl bg-slate-50 p-3">
                <p className="text-xs font-medium text-slate-500">Confidence</p>
                <p className="mt-1 text-2xl font-black text-slate-900">
                  {Math.round(data.confidence * 100)}%
                </p>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-200">
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${data.confidence * 100}%`,
                      background: "var(--gradient-hero)",
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Weighted contributions chart */}
            <div>
              <h4 className="mb-2 text-xs font-bold uppercase tracking-widest text-slate-500">
                Factor Contributions
              </h4>
              <div className="h-[180px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={Object.entries(data.weighted_contributions).map(
                      ([key, value]) => ({
                        name: signalLabels[key] ?? key,
                        value: Math.round(value * 1000) / 10,
                        key,
                      })
                    )}
                    layout="vertical"
                    margin={{ top: 0, right: 16, bottom: 0, left: 80 }}
                  >
                    <XAxis
                      type="number"
                      domain={[0, "auto"]}
                      tick={{ fontSize: 11, fill: "#94a3b8" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      type="category"
                      dataKey="name"
                      tick={{ fontSize: 12, fill: "#475569", fontWeight: 600 }}
                      axisLine={false}
                      tickLine={false}
                      width={78}
                    />
                    <Tooltip
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      formatter={(val: any) => [`${val}%`, "Contribution"]}
                      contentStyle={{
                        borderRadius: "0.75rem",
                        border: "1px solid #e2e8f0",
                        boxShadow: "0 4px 24px rgba(0,0,0,0.08)",
                        fontFamily: "'Inter', sans-serif",
                        fontSize: 13,
                      }}
                    />
                    <Bar dataKey="value" radius={[0, 6, 6, 0]} maxBarSize={24}>
                      {Object.keys(data.weighted_contributions).map((key) => (
                        <Cell key={key} fill={signalColors[key] ?? "#94a3b8"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Raw signals */}
            <div>
              <h4 className="mb-2 text-xs font-bold uppercase tracking-widest text-slate-500">
                Raw Signal Values
              </h4>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                {Object.entries(data.signals).map(([key, value]) => (
                  <div key={key} className="rounded-lg bg-slate-50 p-2.5">
                    <p className="text-[11px] font-semibold text-slate-500">
                      {signalLabels[key] ?? key}
                    </p>
                    <div className="mt-1 flex items-center gap-2">
                      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-slate-200">
                        <div
                          className="h-full rounded-full transition-all duration-500"
                          style={{
                            width: `${Math.min(100, value * 100)}%`,
                            backgroundColor: signalColors[key] ?? "#94a3b8",
                          }}
                        />
                      </div>
                      <span className="text-xs font-bold text-slate-700">
                        {(value * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Reasons */}
            <div>
              <h4 className="mb-2 text-xs font-bold uppercase tracking-widest text-slate-500">
                Top Contributing Factors
              </h4>
              <ul className="space-y-1.5">
                {data.reasons.map((reason, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 rounded-xl bg-slate-50 border border-slate-200/60 px-3 py-2 text-xs text-slate-700"
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-amber-500 mt-1.5 shrink-0" />
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Active reports */}
            {data.active_verified_reports > 0 && (
              <div className="flex items-center gap-2 rounded-xl bg-purple-50 px-4 py-3 text-sm font-semibold text-purple-800">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 0 0-3-3.87" /><path d="M16 3.13a4 4 0 0 1 0 7.75" /></svg>
                {data.active_verified_reports} verified citizen report{data.active_verified_reports > 1 ? "s" : ""} active
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
