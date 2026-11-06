CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

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
