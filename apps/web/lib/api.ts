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
} from "@/lib/types";

export const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail ?? `Request failed (${response.status}).`);
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

export function compareRoutes(origin: MapPoint, destination: MapPoint, vehicle: VehicleType): Promise<RouteComparison> {
  return request<RouteComparison>("/routes/compare", {
    method: "POST",
    body: JSON.stringify({ origin, destination, vehicle }),
  });
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
