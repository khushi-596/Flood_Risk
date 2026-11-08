import type {
  CrowdReport,
  MapPoint,
  RainLevel,
  RainState,
  RoadCollection,
  RouteComparison,
  SegmentExplanation,
  TravelAdvice,
  VehicleType,
  WorkOrder,
  EmergencyFacility,
} from "@/lib/types";

export const apiBaseUrl =
  typeof window !== "undefined"
    ? "/api/backend"
    : (process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/v1");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    /* eslint-disable @typescript-eslint/no-explicit-any */
    const body = (await response.json().catch(() => null)) as { detail?: any } | null;
    let message = `Request failed (${response.status}).`;
    if (typeof body?.detail === "string") {
      message = body.detail;
    } else if (Array.isArray(body?.detail)) {
      message = body.detail
        .map((e: any) => {
          if (typeof e === "string") return e;
          if (e?.msg) {
            const loc = Array.isArray(e.loc) ? e.loc[e.loc.length - 1] : "";
            return loc ? `${loc}: ${e.msg}` : e.msg;
          }
          return JSON.stringify(e);
        })
        .join("; ");
    }
    /* eslint-enable @typescript-eslint/no-explicit-any */
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export function getRoadSegments(signal?: AbortSignal): Promise<RoadCollection> {
  return request<RoadCollection>("/map/segments", { signal, cache: "no-store" });
}

export function getRainState(): Promise<RainState> {
  return request<RainState>("/rain", { cache: "no-store" });
}

export function simulateRain(level: RainLevel): Promise<RainState> {
  return request<RainState>("/rain/simulate", { method: "POST", body: JSON.stringify({ level }) });
}

export function getSegmentExplanation(segmentId: string): Promise<SegmentExplanation> {
  return request<SegmentExplanation>(`/segments/${encodeURIComponent(segmentId)}/explanation`, { cache: "no-store" });
}

export async function compareRoutes(origin: MapPoint, destination: MapPoint, vehicle: VehicleType): Promise<RouteComparison> {
  const result = await request<RouteComparison>("/routes/compare", {
    method: "POST",
    body: JSON.stringify({ origin, destination, vehicle }),
  });

  // Client-side safety: ensure every route follows actual road coordinates (never straight line)
  const hasStraightLine = result.routes.some((r) => (r.geometry?.coordinates?.length ?? 0) < 4);
  if (hasStraightLine) {
    try {
      const profile = vehicle === "two_wheeler" ? "driving" : "driving";
      const osrmUrl = `https://router.project-osrm.org/route/v1/${profile}/${origin.longitude},${origin.latitude};${destination.longitude},${destination.latitude}?overview=full&geometries=geojson&steps=true`;
      const res = await fetch(osrmUrl);
      if (res.ok) {
        /* eslint-disable @typescript-eslint/no-explicit-any */
        const osrmData = (await res.json()) as any;
        if (osrmData.routes && osrmData.routes[0]) {
          const roadGeom = osrmData.routes[0].geometry;
          const roadDist = Math.round(osrmData.routes[0].distance);
          const roadDur = Math.max(1, Math.round(osrmData.routes[0].duration / 60));
          const steps: any[] = [];
          for (const leg of osrmData.routes[0].legs || []) {
            for (const st of leg.steps || []) {
              const mType = st.maneuver?.type || "turn";
              const modifier = st.maneuver?.modifier || "";
              const name = st.name || "road";
              let instruction = `${mType} onto ${name}`;
              if (mType === "depart") instruction = `Head toward ${name}`;
              else if (mType === "arrive") instruction = "Arrive at destination";
              else if (modifier) instruction = `Turn ${modifier} onto ${name}`;
              steps.push({
                instruction,
                name,
                distance_m: Math.round(st.distance),
                duration_sec: Math.round(st.duration),
                maneuver_type: mType,
              });
            }
          }
          for (const route of result.routes) {
            if ((route.geometry?.coordinates?.length ?? 0) < 4) {
              route.geometry = roadGeom;
              route.distance_m = roadDist;
              route.duration_min = roadDur;
              if (!route.steps || route.steps.length === 0) {
                route.steps = steps;
              }
            }
          }
        }
        /* eslint-enable @typescript-eslint/no-explicit-any */
      }
    } catch (e) {
      console.warn("Client OSRM fallback error:", e);
    }
  }

  return result;
}

export function getTravelAdvice(vehicle: VehicleType, origin?: MapPoint | null, destination?: MapPoint | null): Promise<TravelAdvice> {
  return request<TravelAdvice>("/travel-advice", {
    method: "POST",
    body: JSON.stringify({ vehicle, origin: origin ?? null, destination: destination ?? null }),
  });
}

export function submitReport(payload: {
  report_type: string;
  severity: number;
  longitude: number;
  latitude: number;
  description?: string;
  reporter_fingerprint: string;
}): Promise<{ id: string; status: string; segment_id: string; message: string }> {
  return request("/reports", { method: "POST", body: JSON.stringify(payload) });
}

export function getMyReports(fingerprint: string): Promise<CrowdReport[]> {
  return request<CrowdReport[]>(`/reports?reporter_fingerprint=${encodeURIComponent(fingerprint)}`, { cache: "no-store" });
}

export function loginMunicipal(email: string, password: string): Promise<{ access_token: string }> {
  return request("/municipal/login", { method: "POST", body: JSON.stringify({ email, password }) });
}

function auth(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export function getMunicipalReports(token: string): Promise<CrowdReport[]> {
  return request<CrowdReport[]>("/municipal/reports", { headers: auth(token), cache: "no-store" });
}

export function reviewMunicipalReport(token: string, reportId: string, decision: "verified" | "rejected"): Promise<CrowdReport> {
  return request<CrowdReport>(`/municipal/reports/${reportId}/review`, { method: "POST", headers: auth(token), body: JSON.stringify({ decision }) });
}

export function getWorkOrders(token: string): Promise<WorkOrder[]> {
  return request<WorkOrder[]>("/municipal/work-orders", { headers: auth(token), cache: "no-store" });
}

export function createWorkOrder(token: string, payload: { segment_id: string; title: string; priority: number; report_id?: string }): Promise<WorkOrder> {
  return request<WorkOrder>("/municipal/work-orders", { method: "POST", headers: auth(token), body: JSON.stringify(payload) });
}

export function updateWorkOrder(token: string, id: string, status: WorkOrder["status"]): Promise<WorkOrder> {
  return request<WorkOrder>(`/municipal/work-orders/${id}`, { method: "PATCH", headers: auth(token), body: JSON.stringify({ status }) });
}

export async function getEmergencyFacilities(type?: "hospital" | "shelter"): Promise<EmergencyFacility[]> {
  const query = type ? `?facility_type=${type}` : "";
  try {
    return await request<EmergencyFacility[]>(`/emergency/facilities${query}`, { cache: "no-store" });
  } catch {
    const res = await fetch("/emergency_facilities.json");
    const data = (await res.json()) as EmergencyFacility[];
    if (type) return data.filter((f) => f.type === type);
    return data;
  }
}

