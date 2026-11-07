"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Toaster, toast } from "sonner";
import { useAlerts } from "@/lib/use-alerts";
import { useAppStore, type AlertMessage } from "@/lib/store";
import { useEffect } from "react";

const navItems = [
  { href: "/", label: "Map Navigation", icon: MapIcon },
  { href: "/report", label: "Citizen Reports", icon: ReportIcon },
  { href: "/municipal/login", label: "Municipal Portal", icon: ShieldIcon },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const alerts = useAppStore((s) => s.alerts) as AlertMessage[];

  useAlerts();

  /* Show toast when a new alert arrives */
  useEffect(() => {
    const latest = alerts[0];
    if (latest && latest.type === "risk_alert") {
      toast.warning(latest.message, {
        id: latest.id,
        description: `${latest.road_name ?? "Road"} — ${latest.risk_band} risk`,
        duration: 8000,
      });
    }
  }, [alerts]);

  return (
    <div className="flex min-h-dvh flex-col lg:flex-row bg-slate-50/50">
      {/* Luxury Aquatic Desktop Sidebar */}
      <nav
        aria-label="Main navigation"
        className="hidden lg:flex lg:w-[240px] lg:flex-col luxury-glass-sidebar water-droplets-pattern text-white z-20"
      >
        <div className="flex h-18 items-center gap-3 border-b border-sky-400/15 px-5 py-4">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-xl shadow-lg border border-sky-300/30 transition transform hover:scale-105"
            style={{ background: "linear-gradient(135deg, #0284c7 0%, #0369a1 100%)" }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" />
            </svg>
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <p className="text-base font-black tracking-tight text-white">FloodAware</p>
              <span className="rounded bg-sky-400/20 border border-sky-300/30 text-sky-200 text-[10px] font-black px-1.5 py-0.2">PUNE</span>
            </div>
            <p className="text-[10px] font-medium text-sky-200/70">Safe Route Navigation</p>
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-1.5 p-3.5">
          <p className="px-3 pt-2 pb-1 text-[10px] font-bold uppercase tracking-widest text-sky-300/60">
            Navigation
          </p>
          {navItems.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                id={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
                className={`group flex items-center justify-between rounded-xl px-3.5 py-2.5 text-sm font-bold transition-all duration-200 ${
                  active
                    ? "bg-sky-500/20 text-white border border-sky-400/40 shadow-xs shadow-sky-950/40"
                    : "text-sky-100/70 hover:bg-white/10 hover:text-white"
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon active={active} />
                  <span>{label}</span>
                </div>
                {active && <span className="h-2 w-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#38bdf8]" />}
              </Link>
            );
          })}
        </div>

        {/* Status footer in sidebar */}
        <div className="border-t border-sky-400/15 p-4 space-y-2">
          <div className="flex items-center gap-2.5 rounded-xl bg-white/5 border border-sky-400/15 p-2.5">
            <span className="flex h-2 w-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#38bdf8]" />
            <div className="min-w-0 flex-1">
              <p className="text-[11px] font-bold text-white tracking-wide">Monsoon Risk System</p>
              <p className="text-[10px] text-sky-200/70 font-medium">Real-Time Routing Online</p>
            </div>
          </div>
          <p className="text-[10px] text-center text-sky-300/40">Pune Municipal Monsoon Edition</p>
        </div>
      </nav>

      {/* Main content */}
      <div className="flex-1 pb-24 lg:pb-0 min-w-0">{children}</div>

      {/* Mobile bottom tab bar */}
      <nav
        aria-label="Mobile navigation"
        className="fixed inset-x-0 bottom-0 z-50 flex items-center justify-around border-t border-sky-400/20 bg-[#07162c]/95 backdrop-blur-xl lg:hidden shadow-xl"
        style={{ paddingBottom: "env(safe-area-inset-bottom, 8px)" }}
      >
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              id={`mobile-nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
              className={`flex flex-col items-center gap-1 py-2 px-3 text-[11px] font-bold transition-all relative ${
                active ? "text-cyan-400" : "text-sky-200/60 hover:text-white"
              }`}
            >
              <div className={`p-1 rounded-xl transition ${active ? "bg-sky-500/20" : ""}`}>
                <Icon active={active} />
              </div>
              <span className="leading-none">{label}</span>
              {active && <span className="absolute bottom-1 h-1 w-6 rounded-full bg-cyan-400" />}
            </Link>
          );
        })}
      </nav>

      <Toaster
        position="top-right"
        richColors
        toastOptions={{
          style: {
            borderRadius: "var(--radius-xl)",
            fontFamily: "'Inter', sans-serif",
            boxShadow: "var(--shadow-elevated)",
          },
        }}
      />
    </div>
  );
}

/* ─── Icons ────────────────────────────────────────────── */

function MapIcon({ active }: { active: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={active ? "#38bdf8" : "#93c5fd99"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" />
      <line x1="16" y1="6" x2="16" y2="22" />
    </svg>
  );
}

function ReportIcon({ active }: { active: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={active ? "#38bdf8" : "#93c5fd99"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 9v4" /><path d="M12 17h.01" />
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
    </svg>
  );
}

function ListIcon({ active }: { active: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={active ? "#38bdf8" : "#93c5fd99"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}

function ShieldIcon({ active }: { active: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={active ? "#38bdf8" : "#93c5fd99"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
