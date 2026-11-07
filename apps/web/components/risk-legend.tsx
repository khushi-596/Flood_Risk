const legend = [
  { band: "Low", score: "0.00 – 0.34", colour: "#2563eb", description: "Safe under ordinary conditions" },
  { band: "Moderate", score: "0.35 – 0.59", colour: "#d97706", description: "Caution advised for two-wheelers" },
  { band: "High", score: "0.60 – 0.79", colour: "#9333ea", description: "Avoid travel unless necessary" },
  { band: "Severe", score: "0.80 – 1.00", colour: "#be123c", description: "Road impassable or deeply submerged" },
];

export function RiskLegend() {
  return (
    <div className="frosted-card p-5 space-y-3" aria-label="Flood risk legend">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-bold uppercase tracking-widest text-slate-800">Risk Assessment Scale</h2>
        <span className="text-[10px] text-slate-400 font-medium">Pune Risk Engine</span>
      </div>
      <p className="text-xs text-slate-500 leading-normal">
        Road hazard scores derived continuously from terrain elevation, rainfall rate, drainage, and verified citizen reports.
      </p>
      <div className="space-y-2 pt-0.5">
        {legend.map((item) => (
          <div
            className="flex items-center gap-3 rounded-xl bg-slate-50/80 border border-slate-200/60 p-2.5 transition hover:bg-slate-50"
            key={item.band}
          >
            <span
              aria-hidden
              className="h-2.5 w-6 shrink-0 rounded-full"
              style={{ backgroundColor: item.colour }}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-bold text-slate-900">{item.band} Risk</span>
                <span className="text-[11px] font-semibold text-slate-400">{item.score}</span>
              </div>
              <p className="text-[11px] text-slate-500 leading-tight mt-0.5">{item.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
