"use client";

import { useState } from "react";
import { simulateRain } from "@/lib/api";
import type { RainLevel, RainState } from "@/lib/types";
import { SunIcon, CloudDrizzleIcon, CloudRainIcon, CloudLightningIcon, WavesIcon, AlertTriangleIcon } from "@/components/icons";

const levels: {
  value: RainLevel;
  label: string;
  description: string;
  icon: React.ComponentType<{ className?: string; size?: number }>;
}[] = [
  { value: "none", label: "None", description: "0 mm/h", icon: SunIcon },
  { value: "light", label: "Light", description: "~2 mm/h", icon: CloudDrizzleIcon },
  { value: "medium", label: "Medium", description: "~8 mm/h", icon: CloudRainIcon },
  { value: "heavy", label: "Heavy", description: "~22 mm/h", icon: CloudLightningIcon },
  { value: "extreme", label: "Extreme", description: "~45 mm/h", icon: WavesIcon },
];

const levelIndex: Record<RainLevel, number> = { none: 0, light: 1, medium: 2, heavy: 3, extreme: 4 };
const intensityGradient = "linear-gradient(90deg, #0ea5e9 0%, #f59e0b 40%, #ef4444 70%, #7c2d12 100%)";

type Props = {
  rain: RainState | null;
  onChange: (state: RainState) => void;
};

export function RainControls({ rain, onChange }: Props) {
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function select(level: RainLevel) {
    setIsSaving(true);
    setError(null);
    try {
      onChange(await simulateRain(level));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to change rain level.");
    } finally {
      setIsSaving(false);
    }
  }

  const currentIdx = rain ? levelIndex[rain.level] ?? 0 : 0;

  return (
    <div className="frosted-card p-5 space-y-3.5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-widest text-slate-800">Rainfall Simulation</h2>
          <p className="text-[11px] text-slate-500 mt-0.5">Test road passability under monsoon scenarios</p>
        </div>
        <span className="badge bg-sky-50 text-sky-800 border border-sky-200 px-2.5 py-1 text-xs font-bold">
          {rain ? `${rain.rainfall_mm_hour} mm/h` : "Loading…"}
        </span>
      </div>

      {/* Intensity bar */}
      <div className="space-y-1">
        <div className="relative h-2 w-full overflow-hidden rounded-full bg-slate-100 border border-slate-200/80">
          <div
            className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
            style={{
              width: `${(currentIdx / 4) * 100}%`,
              background: intensityGradient,
            }}
          />
        </div>
      </div>

      {/* Level buttons */}
      <div className="grid grid-cols-5 gap-1.5" role="radiogroup" aria-label="Set simulated rainfall">
        {levels.map((level) => {
          const active = rain?.level === level.value;
          const Icon = level.icon;
          return (
            <button
              key={level.value}
              id={`rain-level-${level.value}`}
              aria-checked={active}
              role="radio"
              type="button"
              disabled={isSaving}
              onClick={() => select(level.value)}
              className={`flex flex-col items-center justify-center gap-1 rounded-xl border p-2 text-center transition-all ${
                active
                  ? "border-sky-500 bg-sky-50 text-sky-950 font-bold shadow-xs ring-2 ring-sky-500/15"
                  : "border-slate-200/80 bg-white/70 text-slate-600 hover:border-slate-300 hover:bg-white"
              }`}
            >
              <Icon size={18} className={active ? "text-sky-700" : "text-slate-500"} />
              <span className="text-[11px] font-bold leading-tight">{level.label}</span>
              <span className="text-[9px] text-slate-400">{level.description}</span>
            </button>
          );
        })}
      </div>

      {/* Forecast & source row */}
      <div className="flex items-center justify-between rounded-xl bg-slate-50/80 border border-slate-200/70 px-3 py-2 text-xs">
        <span className="text-slate-600 font-medium">+30 Min Forecast:</span>
        <span className="font-extrabold text-slate-800">
          {rain?.forecast_30m_mm_hour ?? 0} mm/h
        </span>
      </div>

      {rain?.source && (
        <p className="text-[11px] text-slate-400 text-center">
          Weather data: <span className="font-semibold text-slate-600">{rain.source}</span>
          {rain.is_stale && " (simulated fallback)"}
        </p>
      )}

      {error && (
        <div className="rounded-xl bg-rose-50 border border-rose-200 p-2 text-xs font-semibold text-rose-800 flex items-center gap-1.5">
          <AlertTriangleIcon size={13} className="text-rose-600 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
