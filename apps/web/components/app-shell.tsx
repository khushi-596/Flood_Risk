"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Toaster, toast } from "sonner";
import { useAlerts } from "@/lib/use-alerts";
import { useAppStore, type AlertMessage } from "@/lib/store";
import { useEffect } from "react";

const navItems = [
  { href: "/", label: "Map", icon: MapIcon },
  { href: "/report", label: "Report", icon: ReportIcon },
  { href: "/my-reports", label: "My Reports", icon: ListIcon },
  { href: "/municipal/login", label: "Municipal", icon: ShieldIcon },
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
    <div className="flex min-h-dvh flex-col lg:flex-row">
      {/* Desktop sidebar */}
      <nav
        aria-label="Main navigation"
        className="hidden lg:flex lg:w-[220px] lg:flex-col lg:border-r lg:border-slate-200 lg:bg-white"
      >
        <div className="flex h-16 items-center gap-3 border-b border-slate-100 px-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg" style={{ background: "var(--gradient-hero)" }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2.69l5.66 5.66a8 8 0 1 1-11.31 0z" /></svg>
          </div>
          <div>
            <p className="text-sm font-extrabold text-slate-900">FloodAware</p>
            <p className="text-[10px] font-medium uppercase tracking-widest text-sky-600">Pune</p>
          </div>
        </div>
        <div className="flex flex-1 flex-col gap-1 p-3">
          {navItems.map(({ href, label, icon: Icon }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                id={`nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
                className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold transition-all duration-200 ${
                  active
                    ? "bg-sky-50 text-sky-800 shadow-sm"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                <Icon active={active} />
                {label}
              </Link>
            );
          })}
        </div>
        <div className="border-t border-slate-100 p-4">
          <p className="text-[10px] font-medium text-slate-400">Flood-Aware Route Engine</p>
          <p className="text-[10px] text-slate-300">v1.0.0</p>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 pb-20 lg:pb-0">{children}</main>

      {/* Mobile bottom tab bar */}
      <nav
        aria-label="Mobile navigation"
        className="fixed inset-x-0 bottom-0 z-50 flex items-center justify-around border-t border-slate-200 bg-white/90 backdrop-blur-lg lg:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
      >
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              id={`mobile-nav-${label.toLowerCase().replace(/\s+/g, "-")}`}
              className={`flex flex-col items-center gap-0.5 px-3 py-2.5 text-[11px] font-semibold transition-colors ${
                active ? "text-sky-700" : "text-slate-400"
              }`}
            >
              <Icon active={active} />
              {label}
            </Link>
          );
        })}
      </nav>

      <Toaster
        position="top-right"
        richColors
        toastOptions={{
          style: {
            borderRadius: "var(--radius-lg)",
            fontFamily: "'Inter', sans-serif",
          },
        }}
      />
    </div>
  );
}

/* ─── Icons ────────────────────────────────────────────── */

function MapIcon({ active }: { active: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={active ? "#0369a1" : "#94a3b8"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6" />
      <line x1="8" y1="2" x2="8" y2="18" />
      <line x1="16" y1="6" x2="16" y2="22" />
    </svg>
  );
}

function ReportIcon({ active }: { active: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={active ? "#0369a1" : "#94a3b8"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 9v4" /><path d="M12 17h.01" />
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
    </svg>
  );
}

function ListIcon({ active }: { active: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={active ? "#0369a1" : "#94a3b8"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}

function ShieldIcon({ active }: { active: boolean }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke={active ? "#0369a1" : "#94a3b8"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
