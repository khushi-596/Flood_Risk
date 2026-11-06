export type RiskBand = "low" | "moderate" | "high" | "severe";

export type SegmentProperties = {
  segment_id: string;
  name: string;
  risk_score: number;
  confidence: number;
  risk_band: RiskBand;
  reasons: string[];
  signals: Record<string, number>;
  active_verified_reports: number;
};

export type RoadFeature = GeoJSON.Feature<GeoJSON.LineString, SegmentProperties>;
export type RoadCollection = GeoJSON.FeatureCollection<GeoJSON.LineString, SegmentProperties>;

export type MapPoint = {
  longitude: number;
  latitude: number;
  label: string;
};

export type RainLevel = "none" | "light" | "medium" | "heavy" | "extreme";
export type VehicleType = "two_wheeler" | "car" | "bus" | "truck";

export type RainState = {
  level: RainLevel;
  rainfall_mm_hour: number;
  forecast_30m_mm_hour: number;
  source: "simulated" | "live" | "cached";
  is_stale: boolean;
  updated_at: string;
};

export type RouteOption = {
  id: "fast" | "safe" | "balanced";
  label: string;
  geometry: GeoJSON.LineString;
  distance_m: number;
  duration_min: number;
  average_risk: number;
  highest_risk: number;
  risky_segment_count: number;
  segment_ids: string[];
  recommendation: string;
};

export type RouteComparison = {
  vehicle: VehicleType;
  rain: RainState;
  routes: RouteOption[];
};

export type SegmentExplanation = {
  segment_id: string;
  name: string;
  risk_score: number;
  confidence: number;
  risk_band: string;
  signals: Record<string, number>;
  weighted_contributions: Record<string, number>;
  reasons: string[];
  active_verified_reports: number;
};

export type TravelAdvice = {
  verdict: "go" | "caution" | "wait" | "avoid";
  vehicle: VehicleType;
  risk_now: number;
  risk_in_30m: number;
  trend: "rising" | "stable" | "falling";
  reasons: string[];
  updated_at: string;
};

export type CrowdReport = {
  id: string;
  segment_id: string;
  report_type: "waterlogging" | "flood" | "pothole" | "blocked_drain" | "other";
  severity: number;
  longitude: number;
  latitude: number;
  description?: string | null;
  status: "pending" | "verified" | "rejected" | "resolved";
  created_at: string;
  verified_at?: string | null;
};

export type WorkOrder = {
  id: string;
  report_id?: string | null;
  segment_id: string;
  title: string;
  description?: string | null;
  priority: number;
  status: "open" | "assigned" | "in_progress" | "resolved";
  assigned_to?: string | null;
  created_at: string;
  updated_at: string;
};
