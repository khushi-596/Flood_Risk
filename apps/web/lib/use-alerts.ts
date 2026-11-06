"use client";

import { useEffect, useRef } from "react";
import { useAppStore, type AlertMessage } from "@/lib/store";

const WS_URL =
  (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1")
    .replace(/^http/, "ws")
    .replace(/\/v1$/, "") + "/v1/ws/alerts";

export function useAlerts() {
  const addAlert = useAppStore((s) => s.addAlert);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      try {
        const ws = new WebSocket(WS_URL);
        wsRef.current = ws;

        ws.onmessage = (event: MessageEvent) => {
          try {
            const data = JSON.parse(event.data as string) as Partial<AlertMessage>;
            if (data.type === "risk_alert" && data.message) {
              addAlert({
                id: `alert-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                type: "risk_alert",
                segment_id: data.segment_id,
                road_name: data.road_name,
                risk_band: data.risk_band,
                risk_score: data.risk_score,
                message: data.message,
                timestamp: Date.now(),
              });
            }
          } catch {
            /* ignore malformed */
          }
        };

        ws.onclose = () => {
          if (!cancelled) {
            reconnectTimer.current = setTimeout(connect, 5000);
          }
        };

        ws.onerror = () => {
          ws.close();
        };
      } catch {
        if (!cancelled) {
          reconnectTimer.current = setTimeout(connect, 5000);
        }
      }
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [addAlert]);
}
