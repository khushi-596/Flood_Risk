# Flood-Aware Route & Road Risk Engine

An explainable flood-risk navigation prototype for Pune. It scores individual road
segments using terrain, rainfall, drainage, historic flooding, and verified citizen
reports, then exposes the result to a map-first web app.

## Features

### Map & Navigation
- Interactive risk-coloured road map of Pune demo zone
- Route comparison: Fast, Safe, and Balanced routes with risk metrics
- Vehicle type support: two-wheeler, car, bus, truck — each with different safety thresholds
- Place search via Nominatim for Pune locations

### Risk Intelligence
- Explainable 5-signal risk model: terrain, rainfall, flood history, drainage, citizen reports
- "Should I Travel Now?" travel advice with 30-minute risk forecast
- Rain simulator with 5 levels (none → extreme) for demo scenarios
- Segment explanation panel with weighted contribution charts
- Real-time WebSocket alerts when roads enter high/severe risk

### Citizen Reporting
- Flood hazard report form with type, severity, and map location
- Auto-verification when 3 independent devices report within 150m / 30 minutes
- "My Reports" page to track report status
- Rate limiting (5 reports / 30 min per device)

### Municipal Dashboard
- Staff JWT authentication
- Report queue with verify/reject actions
- Kanban work order board (Open → Assigned → In Progress → Resolved)
- Flood hotspot detection (segments with 2+ active reports)
- Drain failure flags (flooding during light rain)
- CSV export of all reports

## Run locally

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Open `http://localhost:3000`. The interactive API contract is at
   `http://localhost:8000/docs`.

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

### Demo credentials

- **Municipal staff login**: `staff@pune.gov.in` / `change-before-deployment`

## Structure

```text
apps/web/                 Next.js map application
  app/                    Pages (map, report, my-reports, municipal)
  components/             UI components (risk-map, route-comparison, etc.)
  lib/                    API client, types, Zustand store, WebSocket hook
services/api/             FastAPI service and API tests
  app/services/           Risk engine, routing, weather, reports, municipal, alerts
data/seeds/               Small deterministic demo dataset
models/risk_engine/       Versioned explainable risk-model settings
pipelines/                CPU GIS preparation scripts
infra/                    Database initialization
```

## Tech Stack

### Frontend
- Next.js 15 (App Router), React 19, TypeScript 5.7
- MapLibre GL + react-map-gl for mapping
- Tailwind CSS 3 for styling
- Zustand for state management
- Recharts for data visualization
- Sonner for toast notifications

### Backend
- FastAPI with Uvicorn
- PostgreSQL 16 + PostGIS 3.4
- Redis 7
- PyJWT for authentication
- Open-Meteo for live weather data

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /v1/map/segments | Risk-scored road GeoJSON |
| GET | /v1/segments/{id}/explanation | Detailed risk breakdown |
| POST | /v1/routes/compare | Fast/Safe/Balanced route comparison |
| POST | /v1/travel-advice | Should I travel now? verdict |
| GET/POST | /v1/rain | Rain state & simulator |
| POST | /v1/reports | Submit citizen flood report |
| GET | /v1/reports | Get citizen's own reports |
| POST | /v1/municipal/login | Staff authentication |
| GET | /v1/municipal/reports | Report queue |
| POST | /v1/municipal/reports/{id}/review | Verify/reject report |
| GET/POST | /v1/municipal/work-orders | Work order management |
| WS | /v1/ws/alerts | Real-time risk alerts |
