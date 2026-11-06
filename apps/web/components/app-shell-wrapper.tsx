"use client";

import { AppShell } from "./app-shell";

export function AppShellWrapper({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
