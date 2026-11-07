"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  getMunicipalReports,
  getWorkOrders,
  reviewMunicipalReport,
  createWorkOrder,
  updateWorkOrder,
  apiBaseUrl,
} from "@/lib/api";
import { useAppStore } from "@/lib/store";
import type { CrowdReport, WorkOrder } from "@/lib/types";
import {
  ClipboardIcon,
  WaterDropIcon,
  WavesIcon,
  PotholeIcon,
  HazardDrainIcon,
  DownloadIcon,
  CheckIcon,
  CloseIcon,
  PlusIcon,
} from "@/components/icons";

type Tab = "reports" | "work-orders" | "hotspots";

const statusBadge: Record<string, string> = {
  pending: "badge-status-pending",
  verified: "badge-status-verified",
  rejected: "badge-status-rejected",
  resolved: "badge-status-resolved",
  open: "bg-amber-100 text-amber-800",
  assigned: "bg-blue-100 text-blue-800",
  in_progress: "bg-purple-100 text-purple-800",
};

const severityColors = ["", "#10b981", "#22d3ee", "#f59e0b", "#f97316", "#ef4444"];

function getReportIcon(type: string) {
  switch (type) {
    case "waterlogging":
      return <WaterDropIcon className="w-5 h-5 text-sky-600" />;
    case "flood":
      return <WavesIcon className="w-5 h-5 text-blue-600" />;
    case "pothole":
      return <PotholeIcon className="w-5 h-5 text-amber-600" />;
    case "blocked_drain":
      return <HazardDrainIcon className="w-5 h-5 text-rose-600" />;
    default:
      return <ClipboardIcon className="w-5 h-5 text-slate-600" />;
  }
}


export default function MunicipalDashboardPage() {
  const router = useRouter();
  const token = useAppStore((s) => s.municipalToken) as string | null;
  const setMunicipalToken = useAppStore((s) => s.setMunicipalToken) as (t: string | null) => void;
  const [tab, setTab] = useState<Tab>("reports");
  const [reports, setReports] = useState<CrowdReport[]>([]);
  const [workOrders, setWorkOrders] = useState<WorkOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState<string | null>(null);

  // Work order creation state
  const [showWoForm, setShowWoForm] = useState(false);
  const [woSegment, setWoSegment] = useState("");
  const [woTitle, setWoTitle] = useState("");
  const [woPriority, setWoPriority] = useState(3);

  const loadData = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    try {
      const [reps, orders] = await Promise.all([
        getMunicipalReports(token),
        getWorkOrders(token),
      ]);
      setReports(reps);
      setWorkOrders(orders);
    } catch {
      toast.error("Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (!token) {
      router.push("/municipal/login");
      return;
    }
    loadData();
  }, [token, router, loadData]);

  async function handleReview(reportId: string, decision: "verified" | "rejected") {
    if (!token) return;
    setReviewing(reportId);
    try {
      const updated = await reviewMunicipalReport(token, reportId, decision);
      setReports((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      toast.success(`Report ${decision}.`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Review failed.");
    } finally {
      setReviewing(null);
    }
  }

  async function handleCreateWo(e: React.FormEvent) {
    e.preventDefault();
    if (!token || !woSegment || !woTitle) return;
    try {
      const order = await createWorkOrder(token, { segment_id: woSegment, title: woTitle, priority: woPriority });
      setWorkOrders((prev) => [order, ...prev]);
      toast.success("Work order created.");
      setShowWoForm(false);
      setWoSegment("");
      setWoTitle("");
      setWoPriority(3);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to create work order.");
    }
  }

  async function handleUpdateWoStatus(orderId: string, newStatus: WorkOrder["status"]) {
    if (!token) return;
    try {
      const updated = await updateWorkOrder(token, orderId, newStatus);
      setWorkOrders((prev) => prev.map((wo) => (wo.id === updated.id ? updated : wo)));
      toast.success(`Work order → ${newStatus.replace("_", " ")}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed.");
    }
  }

  async function handleCsvExport() {
    if (!token) return;
    try {
      const response = await fetch(`${apiBaseUrl}/municipal/reports.csv`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error("Export failed.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "flood-risk-reports.csv";
      a.click();
      URL.revokeObjectURL(url);
      toast.success("CSV downloaded.");
    } catch {
      toast.error("Failed to export CSV.");
    }
  }

  function logout() {
    setMunicipalToken(null);
    router.push("/municipal/login");
  }

  if (!token) return null;

  const tabs: { key: Tab; label: string; count?: number }[] = [
    { key: "reports", label: "Report Queue", count: reports.filter((r) => r.status === "pending").length },
    { key: "work-orders", label: "Work Orders", count: workOrders.filter((wo) => wo.status !== "resolved").length },
    { key: "hotspots", label: "Flood Hotspots" },
  ];

  // Compute hotspots from reports
  const hotspotMap = new Map<string, { segment_id: string; count: number; maxSeverity: number; latest: string }>();
  reports.filter((r) => r.status === "pending" || r.status === "verified").forEach((r) => {
    const existing = hotspotMap.get(r.segment_id);
    if (existing) {
      existing.count++;
      existing.maxSeverity = Math.max(existing.maxSeverity, r.severity);
      if (r.created_at > existing.latest) existing.latest = r.created_at;
    } else {
      hotspotMap.set(r.segment_id, { segment_id: r.segment_id, count: 1, maxSeverity: r.severity, latest: r.created_at });
    }
  });
  const hotspots = Array.from(hotspotMap.values()).filter((h) => h.count >= 2).sort((a, b) => b.count - a.count);

  const nextStatus: Record<string, WorkOrder["status"]> = {
    open: "assigned", assigned: "in_progress", in_progress: "resolved",
  };

  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6">
      {/* Luxury Aquatic Blue Glassmorphism Header */}
      <div className="luxury-glass-blue water-droplets-pattern rounded-3xl p-6 sm:p-7 text-white border border-sky-400/20 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.25em] text-sky-300">
            Municipal Control Center
          </p>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white mt-1">
            Flood Risk &amp; Hazard Management
          </h1>
          <p className="text-xs text-sky-100/80 mt-1 max-w-xl">
            Live queue of citizen reports, severity verification, and road maintenance work order dispatch.
          </p>
        </div>
        <div className="flex gap-2.5">
          <button className="luxury-glass-pill text-xs flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-white font-bold" id="csv-export-btn" onClick={handleCsvExport} type="button">
            <DownloadIcon className="w-3.5 h-3.5 text-sky-300" />
            <span>Export CSV</span>
          </button>
          <button className="rounded-xl bg-white/10 border border-white/20 text-xs px-3.5 py-2 text-white font-bold hover:bg-white/20 transition" id="municipal-logout-btn" onClick={logout} type="button">
            Logout
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="mt-5 flex gap-1 rounded-xl bg-slate-100 p-1" role="tablist" aria-label="Dashboard tabs">
        {tabs.map((t) => (
          <button
            aria-selected={tab === t.key}
            className={`flex items-center gap-2 rounded-lg px-4 py-2.5 text-sm font-semibold transition-all duration-200 ${
              tab === t.key
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
            id={`tab-${t.key}`}
            key={t.key}
            onClick={() => setTab(t.key)}
            role="tab"
            type="button"
          >
            {t.label}
            {t.count !== undefined && t.count > 0 && (
              <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-rose-100 px-1.5 text-[10px] font-bold text-rose-700">
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {loading && (
        <div className="py-16 text-center text-sm text-slate-500 animate-pulse-subtle">
          Loading dashboard data…
        </div>
      )}

      {/* ─── Reports Tab ─── */}
      {!loading && tab === "reports" && (
        <div className="mt-5 space-y-2 animate-fade-in">
          {reports.length === 0 && (
            <div className="card p-10 text-center text-slate-500">No reports yet.</div>
          )}
          {reports.map((report) => (
            <article key={report.id} className="card p-4" id={`municipal-report-${report.id}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100">
                    {getReportIcon(report.report_type)}
                  </span>
                  <div>
                    <h3 className="text-sm font-bold capitalize text-slate-900">
                      {report.report_type.replace("_", " ")}
                    </h3>
                    <p className="text-xs text-slate-500">
                      {report.segment_id} · {new Date(report.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex gap-0.5">
                    {[1, 2, 3, 4, 5].map((level) => (
                      <span
                        key={level}
                        className="h-2.5 w-2.5 rounded-full"
                        style={{
                          backgroundColor: report.severity >= level ? severityColors[level] : "#e2e8f0",
                        }}
                      />
                    ))}
                  </div>
                  <span className={`badge ${statusBadge[report.status] ?? ""}`}>
                    {report.status}
                  </span>
                </div>
              </div>
              {report.description && (
                <p className="mt-2 text-xs text-slate-600 pl-[52px]">{report.description}</p>
              )}
              {report.status === "pending" && (
                <div className="mt-3 flex gap-2 pl-[52px]">
                  <button
                    className="btn-safe py-1.5 text-xs flex items-center gap-1.5"
                    disabled={reviewing === report.id}
                    id={`verify-report-${report.id}`}
                    onClick={() => handleReview(report.id, "verified")}
                    type="button"
                  >
                    <CheckIcon className="w-3.5 h-3.5" />
                    <span>Verify</span>
                  </button>
                  <button
                    className="btn-danger py-1.5 text-xs flex items-center gap-1.5"
                    disabled={reviewing === report.id}
                    id={`reject-report-${report.id}`}
                    onClick={() => handleReview(report.id, "rejected")}
                    type="button"
                  >
                    <CloseIcon className="w-3.5 h-3.5" />
                    <span>Reject</span>
                  </button>
                </div>
              )}
            </article>
          ))}
        </div>
      )}

      {/* ─── Work Orders Tab ─── */}
      {!loading && tab === "work-orders" && (
        <div className="mt-5 animate-fade-in">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-700">
              {workOrders.length} work order{workOrders.length !== 1 ? "s" : ""}
            </h2>
            <button
              className="btn-primary py-1.5 text-xs flex items-center gap-1.5"
              id="create-work-order-btn"
              onClick={() => setShowWoForm(!showWoForm)}
              type="button"
            >
              <PlusIcon className="w-3.5 h-3.5" />
              <span>Create Work Order</span>
            </button>
          </div>

          {/* Create form */}
          {showWoForm && (
            <form className="card mb-4 p-4 space-y-3 animate-slide-down" onSubmit={handleCreateWo}>
              <div className="grid gap-3 sm:grid-cols-3">
                <div>
                  <label htmlFor="wo-segment" className="mb-1 block text-xs font-semibold text-slate-600">
                    Segment ID
                  </label>
                  <input
                    className="input-field py-2 text-xs"
                    id="wo-segment"
                    onChange={(e) => setWoSegment(e.target.value)}
                    placeholder="e.g. pune-demo-003"
                    required
                    value={woSegment}
                  />
                </div>
                <div>
                  <label htmlFor="wo-title" className="mb-1 block text-xs font-semibold text-slate-600">
                    Title
                  </label>
                  <input
                    className="input-field py-2 text-xs"
                    id="wo-title"
                    onChange={(e) => setWoTitle(e.target.value)}
                    placeholder="Clear blocked drain"
                    required
                    value={woTitle}
                  />
                </div>
                <div>
                  <label htmlFor="wo-priority" className="mb-1 block text-xs font-semibold text-slate-600">
                    Priority (1-5)
                  </label>
                  <select
                    className="input-field py-2 text-xs"
                    id="wo-priority"
                    onChange={(e) => setWoPriority(Number(e.target.value))}
                    value={woPriority}
                  >
                    {[1, 2, 3, 4, 5].map((p) => (
                      <option key={p} value={p}>
                        {p} — {["", "Low", "Below Average", "Normal", "High", "Critical"][p]}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="flex gap-2">
                <button className="btn-primary py-1.5 text-xs" type="submit">
                  Create
                </button>
                <button className="btn-secondary py-1.5 text-xs" onClick={() => setShowWoForm(false)} type="button">
                  Cancel
                </button>
              </div>
            </form>
          )}

          {/* Kanban-style columns on desktop, list on mobile */}
          <div className="grid gap-4 lg:grid-cols-4">
            {(["open", "assigned", "in_progress", "resolved"] as const).map((status) => {
              const items = workOrders.filter((wo) => wo.status === status);
              return (
                <div key={status}>
                  <div className="mb-2 flex items-center gap-2">
                    <span className={`badge ${statusBadge[status] ?? "badge-status-resolved"}`}>
                      {status.replace("_", " ")}
                    </span>
                    <span className="text-xs font-bold text-slate-400">{items.length}</span>
                  </div>
                  <div className="space-y-2">
                    {items.map((wo) => (
                      <div key={wo.id} className="card p-3" id={`work-order-${wo.id}`}>
                        <h4 className="text-xs font-bold text-slate-800">{wo.title}</h4>
                        <p className="mt-1 text-[11px] text-slate-500">{wo.segment_id}</p>
                        <div className="mt-1.5 flex items-center justify-between">
                          <div className="flex gap-0.5">
                            {[1, 2, 3, 4, 5].map((p) => (
                              <span
                                key={p}
                                className="h-1.5 w-3 rounded-sm"
                                style={{
                                  backgroundColor: wo.priority >= p ? severityColors[p] : "#e2e8f0",
                                }}
                              />
                            ))}
                          </div>
                          {nextStatus[wo.status] && (
                            <button
                              className="text-[10px] font-bold text-sky-700 hover:text-sky-900"
                              onClick={() => handleUpdateWoStatus(wo.id, nextStatus[wo.status])}
                              type="button"
                            >
                              → {nextStatus[wo.status].replace("_", " ")}
                            </button>
                          )}
                        </div>
                        {wo.assigned_to && (
                          <p className="mt-1 text-[10px] text-slate-400">Assigned: {wo.assigned_to}</p>
                        )}
                      </div>
                    ))}
                    {items.length === 0 && (
                      <p className="rounded-lg bg-slate-50 p-3 text-center text-[11px] text-slate-400">
                        No {status.replace("_", " ")} orders
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ─── Hotspots Tab ─── */}
      {!loading && tab === "hotspots" && (
        <div className="mt-5 space-y-2 animate-fade-in">
          {hotspots.length === 0 && (
            <div className="card p-10 text-center text-slate-500">
              No flood hotspots detected yet. Hotspots appear when segments receive 2+ active reports.
            </div>
          )}
          {hotspots.map((spot) => (
            <article key={spot.segment_id} className="card p-4" id={`hotspot-${spot.segment_id}`}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-bold text-slate-900">{spot.segment_id}</h3>
                  <p className="text-xs text-slate-500">
                    Last report: {new Date(spot.latest).toLocaleString()}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-center">
                    <p className="text-xl font-black text-rose-700">{spot.count}</p>
                    <p className="text-[10px] font-semibold text-slate-500">reports</p>
                  </div>
                  <div className="text-center">
                    <p className="text-xl font-black" style={{ color: severityColors[spot.maxSeverity] }}>
                      {spot.maxSeverity}/5
                    </p>
                    <p className="text-[10px] font-semibold text-slate-500">max severity</p>
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}
