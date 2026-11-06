# Crowd-Sourced Flood Reporting Specification

This document defines the architecture, ingestion pipeline, verification logic, municipal escalation, and abuse mitigation for crowd-sourced flood reports in the Pune Flood Risk Management System.

---

## 1. Overview & Objectives

Citizen hazard reporting acts as a real-time, ground-truth observation signal ($s_{\text{crowd}}$) that complements physical models, historical flood hotspots, and precipitation forecasts.

Key objectives:
- Enable low-friction hazard reporting from citizens via mobile web/app.
- Automatically snap GPS coordinates to Pune's road network using PostGIS spatial indexes (or Euclidean fallback).
- Filter noise, duplicates, and trolling using a 3-device spatio-temporal clustering algorithm and dry-day guardrails.
- Seamlessly transition verified reports into municipal maintenance work orders.

---

## 2. Report Data Schema & Lifecycle

### 2.1 Schema Definition

| Field | Type | Validation / Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | UUID | Auto-generated v4 | Unique report identifier |
| `segment_id` | String | Foreign key to `segments.seg_id` | Matched road segment ID |
| `report_type` | String | `waterlogging`, `blocked_drain`, `manhole_overflow` | Category of the hazard |
| `severity` | Integer | $1 \le \text{severity} \le 5$ | Citizen-assessed intensity (1=puddle, 5=impassable) |
| `longitude` | Float | $73.70 \le \text{lon} \le 74.05$ | WGS84 longitude |
| `latitude` | Float | $18.40 \le \text{lat} \le 18.65$ | WGS84 latitude |
| `description` | String | Max 500 chars, optional | Contextual notes |
| `photo_path` | String | Validated file path, optional | Path to stored image |
| `reporter_fingerprint` | String | Min 8 chars, max 128 chars | Pseudonymous client device fingerprint |
| `status` | Enum | `pending`, `verified`, `rejected`, `resolved` | Operational lifecycle status |
| `verified_at` | Timestamp | Nullable UTC timestamp | Time when verified |
| `reviewed_by` | String | Staff email or `system:cluster` | Reviewing agent |
| `created_at` | Timestamp | UTC timestamp | Submission timestamp |
| `updated_at` | Timestamp | UTC timestamp | Last state modification |

### 2.2 Lifecycle State Diagram

```
                 [Citizen Submission]
                          │
                          ▼
                     ( pending )
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
[3-Device Cluster Auto-Verify]   [Municipal Staff Action]
            │                           │
            ▼                           ▼
      ( verified )                ( rejected )
            │
    [Work Order Resolution]
            │
            ▼
      ( resolved )
```

- **`pending`**: Newly submitted report. Stored and queried, but does not yet influence the model's high-risk bands unless verified.
- **`verified`**: Confirmed hazard. Increments the segment's verified report count and scales the risk engine's crowd factor ($s_{\text{crowd}} = \min(1.0, \text{verified\_count} / 3)$).
- **`rejected`**: False alarm, spam, or outdated report rejected by staff. Zero weight in risk scoring.
- **`resolved`**: Associated field work order completed (e.g., culvert unblocked, water drained). Automatically removes risk contribution.

---

## 3. Spatial Snapping & Clustering Rules

### 3.1 Nearest-Segment Snapping
Every report submitted with `(latitude, longitude)` is snapped to the nearest road segment in Pune:
- **Primary (Online)**: PostGIS KNN distance query using `ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography)` with GiST spatial indexing.
- **Fallback (Offline)**: Seed-based Euclidean point-to-linestring distance calculation.
- **Constraint**: If distance to the nearest segment exceeds 150 meters, the report is rejected with HTTP 422 (`"No road segment is available in the current demo zone"`).

### 3.2 3-Device Auto-Verification Rule
To prevent single-device trolling while ensuring rapid response during flash floods:
1. When a report is submitted, the system queries existing reports within **150 metres** submitted within the past **30 minutes**.
2. If at least **3 distinct device fingerprints** (`reporter_fingerprint`) have reported hazards within this window:
   - All reports in the cluster are updated to `status = 'verified'`.
   - `reviewed_by` is recorded as `'system:cluster'`.
   - The road segment's risk score is immediately updated and cached across Redis.

---

## 4. Media Ingestion & Validation

Citizen-uploaded photos provide verifiable evidence for municipal dispatch. The `/v1/reports/photo` endpoint enforces strict validation:
1. **File Size Limit**: Strictly capped at **3.0 MB** (3,145,728 bytes). Excess payload returns HTTP 413.
2. **MIME & Extension Whitelist**:
   - `image/jpeg` (`.jpg`, `.jpeg`)
   - `image/png` (`.png`)
   - `image/webp` (`.webp`)
3. **Magic Byte Verification**: Headers are verified (`\xFF\xD8\xFF` for JPEG, `\x89PNG\r\n\x1a\n` for PNG, `RIFF...WEBP` for WebP). Spoofed content types are rejected with HTTP 415.
4. **Storage Isolation**: Files are renamed with UUIDs (`{uuid4}.ext`) and saved to an isolated upload volume (`uploads/`) with no executable permissions.

---

## 5. Anti-Abuse & Guardrails

### 5.1 Rate Limiting
- **IP-Level**: 30 requests/minute on `POST /v1/reports` via SlowAPI.
- **Device-Level**: Max 5 submissions per `reporter_fingerprint` per rolling hour.
- **Photo Uploads**: 20 requests/minute per IP on `POST /v1/reports/photo`.

### 5.2 Dry-Day Guardrails
During sunny or dry conditions ($\text{rainfall} < 1.0\text{ mm/h}$), malicious or erroneous crowd reports must not trigger unwarranted city-wide flood panics:
- The risk engine caps total segment risk at **$0.40$ (Moderate)** if no heavy rain has been observed and reports are unverified by municipal staff.
- This prevents a lone user from making an arterial road appear "Severe" (red) on a clear day.

---

## 6. Municipal Work Order & Drainage Detection

### 6.1 Work Order Generation
Municipal staff inspect reports via `/v1/municipal/reports` and dispatch field crews:
- Staff can create work orders (`POST /v1/municipal/work-orders`) linked to report IDs.
- Work order priorities: 1 (Routine) to 5 (Emergency/Life Hazard).
- Updating work order status to `resolved` automatically cascades to resolve linked citizen reports and clears the crowd risk factor on the segment.

### 6.2 Drainage Failure Detection
The system automatically correlates crowd reports with infrastructure properties:
- **Condition**: A segment has low historical risk ($s_{\text{hist}} \le 0.40$), low slope ($< 1.5\%$), but receives active verified waterlogging reports during moderate rain ($8\text{--}15\text{ mm/h}$).
- **Flag**: The segment is flagged under `/v1/municipal/drain-failure-flags` indicating a blocked culvert or collapsed stormwater drain rather than pure topographical flooding.

---

## 7. API Reference

| Method | Endpoint | Auth | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/v1/reports` | None (Public) | Submit hazard report (snaps to segment) |
| `POST` | `/v1/reports/photo` | None (Public) | Upload hazard photo (max 3MB) |
| `GET` | `/v1/reports` | None (Public) | Fetch my reports by `reporter_fingerprint` |
| `POST` | `/v1/reports/{id}/verify` | Bearer Token (Staff) | Verify report directly |
| `POST` | `/v1/reports/{id}/reject` | Bearer Token (Staff) | Reject report |
| `POST` | `/v1/municipal/reports/{id}/review` | Bearer Token (Staff) | Review report (`verified` / `rejected`) |
| `GET` | `/v1/municipal/reports` | Bearer Token (Staff) | List all reports for municipal triage |
| `GET` | `/v1/municipal/reports.csv` | Bearer Token (Staff) | Export reports as CSV |
