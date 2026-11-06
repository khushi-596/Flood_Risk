"use client";

import { useState } from "react";
import { simulateRain } from "@/lib/api";
import type { RainLevel, RainState } from "@/lib/types";

const levels: { value: RainLevel; label: string; emoji: string; description: string }[] = [
  { value: "none", label: "None", emoji: "☀️", description: "0 mm/h" },
  { value: "light", label: "Light", emoji: "🌦️", description: "~2 mm/h" },
  { value: "medium", label: "Medium", emoji: "🌧️", description: "~8 mm/h" },
  { value: "heavy", label: "Heavy", emoji: "⛈️", description: "~22 mm/h" },
  { value: "extreme", label: "Extreme", emoji: "🌊", description: "~45 mm/h" },
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
    <div className="card p-5 animate-fade-in">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="section-title">Rain Simulator</h2>
        <span className="text-xs font-semibold text-slate-500">
          {rain ? `${rain.rainfall_mm_hour} mm/h` : "Loading…"}
        </span>
      </div>

      {/* Intensity bar */}
      <div className="mt-3">
        <div className="relative h-2 w-full overflow-hidden rounded-full bg-slate-200">
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
      <div className="mt-3 grid grid-cols-5 gap-1.5" role="radiogroup" aria-label="Set simulated rainfall">
        {levels.map((level) => {
          const active = rain?.level === level.value;
          return (
            <button
              aria-checked={active}
              className={`flex flex-col items-center gap-0.5 rounded-xl border px-1 py-2 text-center transition-all duration-200 ${
                active
                  ? "border-sky-300 bg-sky-50 text-sky-800 shadow-sm"
                  : "border-transparent bg-slate-50 text-slate-600 hover:border-slate-200 hover:bg-white"
              }`}
              disabled={isSaving}
              id={`rain-level-${level.value}`}
              key={level.value}
              onClick={() => select(level.value)}
              role="radio"
              type="button"
            >
              <span className="text-lg leading-none">{level.emoji}</span>
              <span className="text-[11px] font-bold leading-tight">{level.label}</span>
            </button>
          );
        })}
      </div>

      {/* Forecast */}
      <div className="mt-3 flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
        <span className="text-xs text-slate-500">+30 min forecast</span>
        <span className="text-xs font-bold text-slate-700">
          {rain?.forecast_30m_mm_hour ?? 0} mm/h
        </span>
      </div>

      {rain?.source && (
        <p className="mt-2 text-[11px] text-slate-400">
          Source: <span className="font-semibold">{rain.source}</span>
          {rain.is_stale && " (stale — live weather unavailable)"}
        </p>
      )}

      {error && <p className="mt-2 text-xs font-medium text-rose-700">{error}</p>}
    </div>
  );
}
