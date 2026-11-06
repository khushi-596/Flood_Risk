"use client";

import { useEffect, useState } from "react";
import { getMyReports } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { CrowdReport } from "@/lib/types";

const statusBadge: Record<string, string> = {
  pending: "badge-status-pending",
  verified: "badge-status-verified",
  rejected: "badge-status-rejected",
  resolved: "badge-status-resolved",
};

const typeEmoji: Record<string, string> = {
  waterlogging: "💧",
  flood: "🌊",
  pothole: "🕳️",
  blocked_drain: "🚧",
  other: "📋",
};

const severityColors = ["", "#10b981", "#22d3ee", "#f59e0b", "#f97316", "#ef4444"];

export default function MyReportsPage() {
  const fingerprint = useAppStore((s) => s.fingerprint) as string;
  const [reports, setReports] = useState<CrowdReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!fingerprint || fingerprint === "ssr-placeholder") return;
    setLoading(true);
    getMyReports(fingerprint)
      .then(setReports)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load reports."))
      .finally(() => setLoading(false));
  }, [fingerprint]);

  return (
    <main className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
      <div className="mb-6">
        <p className="section-title">Your Reports</p>
        <h1 className="page-title mt-1">My Flood Reports</h1>
        <p className="mt-1 text-sm text-slate-500">
          Track the status of your submitted reports. Verified reports affect road risk scores.
        </p>
      </div>

      {loading && (
        <div className="flex items-center gap-3 py-12 text-sm text-slate-500">
          <span className="animate-pulse-subtle text-lg">●</span>
          Loading your reports…
        </div>
      )}

      {error && (
        <div className="card p-6 text-center">
          <p className="text-sm font-medium text-rose-700">{error}</p>
        </div>
      )}

      {!loading && !error && reports.length === 0 && (
        <div className="card p-10 text-center animate-fade-in">
          <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 text-3xl">
            📭
          </div>
          <h2 className="mt-4 text-lg font-bold text-slate-700">No reports yet</h2>
          <p className="mt-2 text-sm text-slate-500">
            You haven&apos;t submitted any flood reports yet. Help make Pune safer!
          </p>
          <a className="btn-primary mt-5 inline-flex" href="/report">
            Submit a Report
          </a>
        </div>
      )}

      {!loading && reports.length > 0 && (
        <div className="space-y-3">
          {reports.map((report, index) => (
            <article
              key={report.id}
              className="card p-4 animate-slide-up"
              style={{ animationDelay: `${index * 50}ms` }}
              id={`report-${report.id}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-xl">
                    {typeEmoji[report.report_type] ?? "📋"}
                  </span>
                  <div>
                    <h3 className="text-sm font-bold capitalize text-slate-900">
                      {report.report_type.replace("_", " ")}
                    </h3>
                    <p className="text-xs text-slate-500">
                      Segment: {report.segment_id}
                    </p>
                  </div>
                </div>
                <span className={`badge ${statusBadge[report.status] ?? ""}`}>
                  {report.status}
                </span>
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-3">
                {/* Severity dots */}
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-medium text-slate-500">Severity:</span>
                  <div className="flex gap-0.5">
                    {[1, 2, 3, 4, 5].map((level) => (
                      <span
                        key={level}
                        className="h-3 w-3 rounded-full transition-all"
                        style={{
                          backgroundColor: report.severity >= level ? severityColors[level] : "#e2e8f0",
                        }}
                      />
                    ))}
                  </div>
                  <span className="text-xs font-bold" style={{ color: severityColors[report.severity] }}>
                    {report.severity}/5
                  </span>
                </div>

                {/* Location */}
                <span className="text-xs text-slate-400">
                  📍 {report.latitude.toFixed(4)}, {report.longitude.toFixed(4)}
                </span>
              </div>

              {report.description && (
                <p className="mt-2 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">
                  {report.description}
                </p>
              )}

              <div className="mt-2 flex items-center gap-3 text-[11px] text-slate-400">
                <span>Submitted: {new Date(report.created_at).toLocaleString()}</span>
                {report.verified_at && (
                  <span className="text-emerald-600">
                    ✓ Verified: {new Date(report.verified_at).toLocaleString()}
                  </span>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
