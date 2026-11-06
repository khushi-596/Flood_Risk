"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from "recharts";
import { getTravelAdvice } from "@/lib/api";
import type { MapPoint, TravelAdvice, VehicleType } from "@/lib/types";

const verdictConfig: Record<
  TravelAdvice["verdict"],
  { bg: string; text: string; border: string; emoji: string; label: string }
> = {
  go: { bg: "bg-emerald-50", text: "text-emerald-800", border: "border-emerald-200", emoji: "✅", label: "Safe to Go" },
  caution: { bg: "bg-amber-50", text: "text-amber-800", border: "border-amber-200", emoji: "⚠️", label: "Use Caution" },
  wait: { bg: "bg-orange-50", text: "text-orange-800", border: "border-orange-200", emoji: "⏳", label: "Wait" },
  avoid: { bg: "bg-rose-50", text: "text-rose-800", border: "border-rose-200", emoji: "🚫", label: "Avoid Travel" },
};

const trendIcon: Record<TravelAdvice["trend"], string> = {
  rising: "↗",
  stable: "→",
  falling: "↘",
};

type Props = {
  vehicle: VehicleType;
  origin: MapPoint | null;
  destination: MapPoint | null;
  refreshKey: number;
};

export function TravelAdviceCard({ vehicle, origin, destination, refreshKey }: Props) {
  const [advice, setAdvice] = useState<TravelAdvice | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    getTravelAdvice(vehicle, origin, destination)
      .then(setAdvice)
      .catch(() => setAdvice(null))
      .finally(() => setLoading(false));
  }, [vehicle, origin, destination, refreshKey]);

  if (loading && !advice) {
    return (
      <div className="card p-5 animate-fade-in">
        <h2 className="section-title">Should I Travel Now?</h2>
        <p className="mt-3 text-sm text-slate-400 animate-pulse-subtle">
          Calculating travel advice…
        </p>
      </div>
    );
  }

  if (!advice) {
    return (
      <div className="card p-5 animate-fade-in">
        <h2 className="section-title">Should I Travel Now?</h2>
        <p className="mt-3 text-sm text-slate-500">
          Travel advice will appear when the API is running.
        </p>
      </div>
    );
  }

  const config = verdictConfig[advice.verdict];
  const chartData = [
    { name: "Now", value: Math.round(advice.risk_now * 100), color: "#0ea5e9" },
    { name: "+30 min", value: Math.round(advice.risk_in_30m * 100), color: advice.trend === "rising" ? "#ef4444" : advice.trend === "falling" ? "#10b981" : "#f59e0b" },
  ];

  return (
    <div className={`animate-fade-in rounded-2xl border p-5 shadow-sm transition-all ${config.bg} ${config.border}`}>
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <h2 className="section-title">Should I Travel Now?</h2>
        <span className={`badge ${config.text} ${config.bg} border ${config.border}`}>
          {config.emoji} {config.label}
        </span>
      </div>

      {/* Risk chart */}
      <div className="mt-4 h-[100px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
            <XAxis
              dataKey="name"
              tick={{ fontSize: 12, fill: "#475569", fontWeight: 600 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 10, fill: "#94a3b8" }}
              axisLine={false}
              tickLine={false}
              width={30}
            />
            <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={48}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Stats row */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        <div className="rounded-xl bg-white/70 p-2.5 text-center">
          <p className="text-[10px] font-semibold uppercase text-slate-500">Now</p>
          <p className="text-lg font-black text-slate-900">{Math.round(advice.risk_now * 100)}%</p>
        </div>
        <div className="rounded-xl bg-white/70 p-2.5 text-center">
          <p className="text-[10px] font-semibold uppercase text-slate-500">+30 min</p>
          <p className="text-lg font-black text-slate-900">{Math.round(advice.risk_in_30m * 100)}%</p>
        </div>
        <div className="rounded-xl bg-white/70 p-2.5 text-center">
          <p className="text-[10px] font-semibold uppercase text-slate-500">Trend</p>
          <p className="text-lg font-black text-slate-900">
            {trendIcon[advice.trend]} {advice.trend}
          </p>
        </div>
      </div>

      {/* Reasons */}
      {advice.reasons.length > 0 && (
        <ul className="mt-3 space-y-1">
          {advice.reasons.map((reason, i) => (
            <li key={i} className="text-xs leading-relaxed text-slate-600">
              • {reason}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
