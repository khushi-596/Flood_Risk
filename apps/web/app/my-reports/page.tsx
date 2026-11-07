"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function MyReportsPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/report?tab=history");
  }, [router]);

  return (
    <div className="flex min-h-[50vh] items-center justify-center p-6 text-xs text-slate-400">
      <span className="animate-pulse">Redirecting to Citizen Reports Portal…</span>
    </div>
  );
}
