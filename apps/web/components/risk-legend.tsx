const legend = [
  { band: "Low", score: "0.00 – 0.34", colour: "#2563eb", description: "Safe in most conditions" },
  { band: "Moderate", score: "0.35 – 0.59", colour: "#d97706", description: "Use caution, especially two-wheelers" },
  { band: "High", score: "0.60 – 0.79", colour: "#9333ea", description: "Avoid unless necessary" },
  { band: "Severe", score: "0.80 – 1.00", colour: "#be123c", description: "Road likely impassable" },
];

export function RiskLegend() {
  return (
    <div className="card p-5 animate-fade-in" aria-label="Flood risk legend">
      <h2 className="section-title">Road Flood Risk</h2>
      <p className="mt-1 text-xs leading-5 text-slate-500">
        Risk level and score are both shown so colour is never the only signal.
      </p>
      <ul className="mt-3 space-y-2.5">
        {legend.map((item) => (
          <li className="flex items-start gap-3" key={item.band}>
            <span
              aria-hidden
              className="mt-1 h-3 w-10 shrink-0 rounded-full"
              style={{ backgroundColor: item.colour }}
            />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-bold text-slate-800">{item.band}</span>
                <span className="text-xs font-medium text-slate-400">{item.score}</span>
              </div>
              <p className="text-xs text-slate-500">{item.description}</p>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
