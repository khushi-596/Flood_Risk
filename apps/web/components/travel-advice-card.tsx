"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from "recharts";
import { getTravelAdvice } from "@/lib/api";
import type { MapPoint, TravelAdvice, VehicleType } from "@/lib/types";
import { ShieldCheckIcon, AlertTriangleIcon, ClockIcon, BanIcon } from "@/components/icons";

const verdictConfig: Record<
  TravelAdvice["verdict"],
  { bg: string; text: string; border: string; label: string; icon: React.ComponentType<{ className?: string; size?: number }> }
> = {
  go: { bg: "bg-emerald-50/80", text: "text-emerald-800", border: "border-emerald-200", label: "Safe to Travel", icon: ShieldCheckIcon },
  caution: { bg: "bg-amber-50/80", text: "text-amber-800", border: "border-amber-200", label: "Travel with Caution", icon: AlertTriangleIcon },
  wait: { bg: "bg-orange-50/80", text: "text-orange-800", border: "border-orange-200", label: "Wait Recommended", icon: ClockIcon },
  avoid: { bg: "bg-rose-50/80", text: "text-rose-800", border: "border-rose-200", label: "Avoid Commuting", icon: BanIcon },
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
      <div className="frosted-card p-5 animate-fade-in">
        <h2 className="text-xs font-bold uppercase tracking-widest text-slate-700">Travel Advice</h2>
        <p className="mt-2 text-xs text-slate-400 animate-pulse">
          Calculating travel conditions…
        </p>
      </div>
    );
  }

  if (!advice) {
    return (
      <div className="frosted-card p-5 animate-fade-in">
        <h2 className="text-xs font-bold uppercase tracking-widest text-slate-700">Travel Advice</h2>
        <p className="mt-2 text-xs text-slate-500">
          Real-time commute recommendations will appear here.
        </p>
      </div>
    );
  }

  const config = verdictConfig[advice.verdict];
  const Icon = config.icon;
  const chartData = [
    { name: "Current", value: Math.round(advice.risk_now * 100), color: "#0ea5e9" },
    { name: "+30 Min", value: Math.round(advice.risk_in_30m * 100), color: advice.trend === "rising" ? "#ef4444" : advice.trend === "falling" ? "#10b981" : "#f59e0b" },
  ];

  return (
    <div className={`frosted-card p-5 transition-all border ${config.bg} ${config.border}`}>
      {/* Header */}
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-widest text-slate-800">Travel Advice</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">Real-time commute decision</p>
        </div>
        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${config.text} bg-white shadow-xs border ${config.border}`}>
          <Icon size={14} />
          <span>{config.label}</span>
        </span>
      </div>

      {/* Risk chart */}
      <div className="mt-3.5 h-[90px]">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
            <XAxis
              dataKey="name"
              tick={{ fontSize: 11, fill: "#475569", fontWeight: 700 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 10, fill: "#94a3b8" }}
              axisLine={false}
              tickLine={false}
              width={26}
            />
            <Bar dataKey="value" radius={[6, 6, 0, 0]} maxBarSize={44}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Stats row */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        <div className="rounded-xl bg-white/90 border border-slate-200/60 p-2 text-center shadow-xs">
          <p className="text-[10px] font-bold uppercase text-slate-500">Current</p>
          <p className="text-base font-black text-slate-900">{Math.round(advice.risk_now * 100)}%</p>
        </div>
        <div className="rounded-xl bg-white/90 border border-slate-200/60 p-2 text-center shadow-xs">
          <p className="text-[10px] font-bold uppercase text-slate-500">+30 min</p>
          <p className="text-base font-black text-slate-900">{Math.round(advice.risk_in_30m * 100)}%</p>
        </div>
        <div className="rounded-xl bg-white/90 border border-slate-200/60 p-2 text-center shadow-xs">
          <p className="text-[10px] font-bold uppercase text-slate-500">Trend</p>
          <p className="text-base font-black text-slate-900 capitalize">
            {advice.trend}
          </p>
        </div>
      </div>

      {/* Reasons */}
      {advice.reasons.length > 0 && (
        <ul className="mt-3 space-y-1 pt-2 border-t border-slate-200/50">
          {advice.reasons.map((reason, i) => (
            <li key={i} className="flex items-start gap-1.5 text-xs text-slate-700 leading-normal">
              <span className="text-sky-600 font-bold">•</span>
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
