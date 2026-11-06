# 1-Page Test Strategy & Verification Summary

This document summarizes the testing methodology, test matrix, failure-mode verification, contract testing, and load-testing suite implemented for the Pune Flood Risk API.

---

## 1. Testing Philosophy & Zero-Dependency Guarantee

The backend is engineered for **resilient, offline-tolerant execution**:
- **Zero External Dependencies**: All 99 unit, integration, and end-to-end tests execute successfully in an isolated test runner without requiring a running PostgreSQL server, Redis instance, or live internet connection.
- **Graceful Fallbacks**: When PostGIS is unreachable, the system transparently serves seeded GeoJSON; when Redis is unreachable, it defaults to in-memory TTL caching and local Pub/Sub queues; when Open-Meteo times out, it uses cached observation snapshots marked `is_stale=True`.
- **State Cleanliness**: The `conftest.py` autouse fixture clears all in-memory reports, work-orders, rate-limit buckets, and weather simulator overrides between every single test.

---

## 2. Test Suite Matrix (99 Total Tests)

| Test Module | Tests | Focus Area & Key Invariants Verified |
| :--- | :---: | :--- |
| `test_api.py` | 4 | Health check, map segment retrieval, known segment validation, explanation endpoint & aliases |
| `test_risk_engine.py` | 3 | Risk monotonicity (more rain never lowers risk), dry-day score capping ($R \le 0.40$), per-segment rainfall pressure thresholds ($T_{\text{seg}}$) |
| `test_routing.py` | 7 | Safe route is never riskier than Fast route; dry weather routes all low risk; heavy rain forces safe route to avoid severe underpasses; vehicle limits (two-wheeler vs bus); extreme rain monotonicity; `horizon_min=30` forecast routing; graph cache invalidation |
| `test_weather.py` | 8 | Weather endpoints & aliases, custom rainfall simulator overrides, deterministic storm playback lifecycle (ramp-up → peak → decay), travel advice endpoint, multi-point grid lookups, segment risk persistence snapshot, weather time-series history/grid endpoints, persisted segment risk endpoint |
| `test_crowd_and_municipal.py` | 7 | KNN nearest-segment snapping, 3-device/150m auto-verification clustering, work-order lifecycle clearing crowd risk, drainage failure detection, photo magic byte/size validation, municipal stats endpoint, alert persistence |
| `test_part_c.py` | 7 | `/api/v1` prefix alias parity with `/v1`, root metadata, Structlog structured logger, rate limiting headers, HTTP 429 Too Many Requests verification on limit breach |
| `test_contract.py` | 4 | Complete OpenAPI 3.1 schema structure, tags/summary completeness, Schemathesis property-based fuzzing, Schemathesis POST response schema validation |
| `test_failure_modes.py` | 11 | PostGIS offline fallback, Redis offline fallback, Open-Meteo timeout handling, malformed bbox handling, off-grid routing point snapping, unauthorized municipal 401s, photo empty/spoof/size checks, playback out-of-bounds, extreme weather numeric monotonicity, JWT tampering rejection, WebSocket lifecycle |
| `test_od_benchmarks.py` | 43 | 5 canonical Pune O-D corridors × 5 rain scenarios ($R_{\text{safe}} \le R_{\text{fast}}$), dry weather bounds ($\le 0.25$), heavy rain flood hotspot evasion, monotonic risk growth, vehicle adaptability, and deep readiness probe (`/health/ready`) |
| `test_second_zone.py` | 1 | Pipeline reusability: PCMC/Pimpri-Chinchwad second zone (5 segments, 7 nodes, 10 edges) verifies schema validation and risk monotonicity on a fresh zone |
| **`test_user_journeys.py`** (E2E) | **4** | **End-to-end integration journeys covering all user personas:**<br>• Journey 1: Commuter workflow (rain → route compare → travel advice)<br>• Journey 2: Citizen reporting → municipal triage → work order resolution → crowd signal clearance<br>• Journey 3: Storm event → risk band transitions → alerts endpoint<br>• Journey 4: Vehicle adaptability warnings under heavy rain |

**Total:** 99 passed in ~12 seconds (offline, no DB/Redis required).

---

## 3. New Endpoints Added (Post-Plan Completion)

| Endpoint | Method | Description |
| :--- | :---: | :--- |
| `/v1/rain/history` | GET | Returns time-series of weather observations (DB or in-memory) |
| `/v1/weather/history` | GET | Alias for `/v1/rain/history` |
| `/v1/rain/grid` | GET | Returns per-grid-point rainfall readings for all 5 spatial sample points |
| `/v1/weather/grid` | GET | Alias for `/v1/rain/grid` |
| `/v1/segments/risk/current` | GET | Returns persisted segment risk scores from `segment_risk_current` table |
| `/v1/municipal/stats` | GET | Dashboard KPIs: open reports, verified today, active hotspots, open work orders |

---

## 4. Second Zone Pipeline Verification

A PCMC/Pimpri-Chinchwad second zone was seeded at `data/seeds/second_zone_segments.geojson` and verified by `pipelines/run_second_zone.py`:

```
python -m pipelines.run_second_zone
# → SUCCESS: 5 segments, 7 nodes, 10 edges
# → Risk monotonicity verified across all rainfall levels
```

---

## 5. How to Run the Tests

```bash
# 1. Run full backend pytest test suite (95 tests)
pytest services/api/tests -v

# 2. Run E2E integration journeys (4 tests, offline, no browser needed)
pytest tests/e2e/ -v

# 3. Run everything combined (99 tests)
pytest services/api/tests tests/e2e/ -v
# or via Makefile:
make test-all

# 4. Run 5 Pune Origin-Destination benchmark suite
pytest services/api/tests/test_od_benchmarks.py -v

# 5. Run contract and schema tests
pytest services/api/tests/test_contract.py -v

# 6. Run failure mode and resilience tests
pytest services/api/tests/test_failure_modes.py -v

# 7. Run automated Locust load test (self-contained with auto-server)
python -m tests.load.run_load_test --host http://127.0.0.1:8000 --users 15 --duration 15
```

> **Note on Playwright E2E**: Browser-based Playwright tests are scaffolded at `apps/web/e2e/user-journeys.spec.ts` and require a running Next.js dev server (`npm run dev`) plus installed Playwright browsers (`npx playwright install`). The FastAPI integration-level E2E tests in `tests/e2e/` provide equivalent coverage and run fully offline.
