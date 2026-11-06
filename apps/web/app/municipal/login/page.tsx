"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { loginMunicipal } from "@/lib/api";
import { useAppStore } from "@/lib/store";

export default function MunicipalLoginPage() {
  const router = useRouter();
  const setMunicipalToken = useAppStore((s) => s.setMunicipalToken) as (t: string | null) => void;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  function fillCredentials(fillEmail: string, fillPass: string) {
    setEmail(fillEmail);
    setPassword(fillPass);
    toast.info(`Filled credentials for ${fillEmail}`);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || !password) {
      toast.error("Please enter both email and password.");
      return;
    }
    setLoading(true);
    try {
      const result = await loginMunicipal(email, password);
      setMunicipalToken(result.access_token);
      toast.success("Logged in successfully as Municipal Staff!");
      router.push("/municipal");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Invalid credentials.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-[85vh] items-center justify-center px-4 py-8">
      <div className="relative w-full max-w-md">
        {/* Background glow */}
        <div className="absolute -inset-4 -z-10 rounded-3xl opacity-30 blur-3xl" style={{ background: "var(--gradient-hero)" }} />

        <div className="glass-card p-8 animate-scale-in">
          {/* Logo */}
          <div className="flex flex-col items-center">
            <div
              className="flex h-14 w-14 items-center justify-center rounded-2xl shadow-lg"
              style={{ background: "var(--gradient-hero)" }}
            >
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <h1 className="mt-4 text-xl font-extrabold text-slate-900">Municipal Staff Portal</h1>
            <p className="mt-1 text-center text-sm text-slate-500">
              PMC &amp; Disaster Management Operational Dashboard
            </p>
          </div>

          <div className="mt-5 rounded-xl border border-sky-200 bg-sky-50/70 p-3 text-xs text-sky-800">
            <div className="flex items-center gap-1.5 font-semibold">
              <span>🔒</span> Pre-Configured Staff Accounts
            </div>
            <p className="mt-1 text-slate-600">
              Municipal employee accounts are pre-seeded in the database to prevent public unauthorized access. No manual registration needed.
            </p>
          </div>

          <form className="mt-6 space-y-4" onSubmit={handleSubmit}>
            <div>
              <label htmlFor="login-email" className="mb-1.5 block text-sm font-semibold text-slate-700">
                Email Address
              </label>
              <input
                autoComplete="email"
                className="input-field"
                id="login-email"
                onChange={(e) => setEmail(e.target.value)}
                placeholder="staff@pune.gov.in"
                type="email"
                value={email}
              />
            </div>
            <div>
              <label htmlFor="login-password" className="mb-1.5 block text-sm font-semibold text-slate-700">
                Password
              </label>
              <input
                autoComplete="current-password"
                className="input-field"
                id="login-password"
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter your password"
                type="password"
                value={password}
              />
            </div>
            <button
              className="btn-primary mt-2 w-full py-3 text-base font-semibold"
              disabled={loading}
              id="municipal-login-btn"
              type="submit"
            >
              {loading ? <span className="animate-pulse-subtle">Signing In…</span> : "Sign In to Portal"}
            </button>
          </form>

          {/* 1-Click Quick Fill Buttons */}
          <div className="mt-6 border-t border-slate-200/80 pt-4">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">
              Quick 1-Click Demo Login
            </p>
            <div className="flex flex-col gap-2">
              <button
                type="button"
                onClick={() => fillCredentials("staff@pune.gov.in", "change-before-deployment")}
                className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:bg-sky-50 hover:text-sky-900"
              >
                <span>⚡ Fill <b>staff@pune.gov.in</b></span>
                <span className="text-[11px] text-slate-400">Default Staff</span>
              </button>
              <button
                type="button"
                onClick={() => fillCredentials("khushidudhalkar@gmail.com", "change-before-deployment")}
                className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 shadow-sm transition hover:border-sky-300 hover:bg-sky-50 hover:text-sky-900"
              >
                <span>⚡ Fill <b>khushidudhalkar@gmail.com</b></span>
                <span className="text-[11px] text-slate-400">Admin Staff</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
