CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS segments (
  seg_id TEXT PRIMARY KEY,
  osm_way_id TEXT,
  name TEXT NOT NULL DEFAULT 'Unnamed road',
  highway TEXT NOT NULL DEFAULT 'unclassified',
  geom GEOMETRY(LineString, 4326) NOT NULL,
  length_m DOUBLE PRECISION NOT NULL DEFAULT 0,
  is_underpass BOOLEAN NOT NULL DEFAULT FALSE,
  elev_mean DOUBLE PRECISION,
  slope DOUBLE PRECISION,
  depression_idx DOUBLE PRECISION,
  drain_dist_m DOUBLE PRECISION,
  signal_terrain DOUBLE PRECISION NOT NULL DEFAULT 0,
  signal_flood_history DOUBLE PRECISION NOT NULL DEFAULT 0,
  signal_drainage DOUBLE PRECISION NOT NULL DEFAULT 0,
  threshold_mm_hr DOUBLE PRECISION NOT NULL DEFAULT 30.0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS segments_geom_gist_idx ON segments USING GIST (geom);
CREATE INDEX IF NOT EXISTS segments_highway_idx ON segments (highway);

CREATE TABLE IF NOT EXISTS hotspots_hist (
  id SERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  geom GEOMETRY(Point, 4326) NOT NULL,
  severity SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5),
  source TEXT NOT NULL DEFAULT 'manual',
  threshold_mm_hr DOUBLE PRECISION,
  confidence DOUBLE PRECISION DEFAULT 0.5,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS hotspots_hist_geom_gist_idx ON hotspots_hist USING GIST (geom);

CREATE TABLE IF NOT EXISTS segment_risk_current (
  seg_id TEXT PRIMARY KEY REFERENCES segments(seg_id) ON DELETE CASCADE,
  risk_now DOUBLE PRECISION NOT NULL DEFAULT 0,
  risk_30 DOUBLE PRECISION NOT NULL DEFAULT 0,
  risk_band TEXT NOT NULL DEFAULT 'low',
  confidence DOUBLE PRECISION NOT NULL DEFAULT 0.55,
  factors JSONB NOT NULL DEFAULT '{}',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS citizen_reports (
  id UUID PRIMARY KEY,
  segment_id TEXT NOT NULL,
  report_type TEXT NOT NULL,
  severity SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 5),
  longitude DOUBLE PRECISION NOT NULL,
  latitude DOUBLE PRECISION NOT NULL,
  description TEXT,
  photo_path TEXT,
  reporter_fingerprint TEXT,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'verified', 'rejected', 'resolved')),
  verified_at TIMESTAMPTZ,
  reviewed_by TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS citizen_reports_segment_created_idx
  ON citizen_reports (segment_id, created_at DESC);
CREATE INDEX IF NOT EXISTS citizen_reports_status_idx
  ON citizen_reports (status);
CREATE INDEX IF NOT EXISTS citizen_reports_location_time_idx
  ON citizen_reports (latitude, longitude, created_at DESC);

CREATE TABLE IF NOT EXISTS work_orders (
  id UUID PRIMARY KEY,
  report_id UUID REFERENCES citizen_reports(id) ON DELETE SET NULL,
  segment_id TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT,
  priority SMALLINT NOT NULL CHECK (priority BETWEEN 1 AND 5),
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'assigned', 'in_progress', 'resolved')),
  assigned_to TEXT,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS work_orders_status_idx ON work_orders (status, priority DESC);
CREATE INDEX IF NOT EXISTS work_orders_segment_idx ON work_orders (segment_id);

CREATE TABLE IF NOT EXISTS weather_observations (
  id BIGSERIAL PRIMARY KEY,
  observed_at TIMESTAMPTZ NOT NULL,
  rainfall_mm_hour DOUBLE PRECISION NOT NULL,
  forecast_30m_mm_hour DOUBLE PRECISION NOT NULL,
  source TEXT NOT NULL,
  is_stale BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS weather_observations_time_idx ON weather_observations (observed_at DESC);
