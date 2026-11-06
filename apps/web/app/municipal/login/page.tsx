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
    <div className="flex min-h-[85vh] items-center justify-center px-4 py-8">
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
              Sign in to manage flood reports &amp; work orders
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
              {loading ? <span className="animate-pulse-subtle">Signing In…</span> : "Sign In"}
            </button>
          </form>

          <div className="mt-6 rounded-xl bg-slate-50 border border-slate-200/60 p-3 text-center">
            <p className="text-xs text-slate-500">
              Authorized municipal accounts only. Public registration is restricted for security.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
