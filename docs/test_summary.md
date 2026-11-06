# 1-Page Test Strategy & Verification Summary

This document summarizes the testing methodology, test matrix, failure-mode verification, contract testing, and load-testing suite implemented for the Pune Flood Risk API.

---

## 1. Testing Philosophy & Zero-Dependency Guarantee

The backend is engineered for **resilient, offline-tolerant execution**:
- **Zero External Dependencies**: All 37 unit and integration tests execute successfully in an isolated test runner without requiring a running PostgreSQL server, Redis instance, or live internet connection.
- **Graceful Fallbacks**: When PostGIS is unreachable, the system transparently serves seeded GeoJSON; when Redis is unreachable, it defaults to in-memory TTL caching and local Pub/Sub queues; when Open-Meteo times out, it uses cached observation snapshots marked `is_stale=True`.
- **State Cleanliness**: The `conftest.py` autouse fixture clears all in-memory reports, work-orders, rate-limit buckets, and weather simulator overrides between every single test.

---

## 2. Test Suite Matrix (86 Total Tests)

| Test Module | Tests | Focus Area & Key Invariants Verified |
| :--- | :---: | :--- |
| `test_api.py` | 4 | Health check, map segment retrieval, known segment validation, explanation endpoint & aliases |
| `test_risk_engine.py` | 3 | Risk monotonicity (more rain never lowers risk), dry-day score capping ($R \le 0.40$), per-segment rainfall pressure thresholds ($T_{\text{seg}}$) |
| `test_routing.py` | 5 | Safe route is never riskier than Fast route; dry weather routes all low risk; heavy rain forces safe route to avoid severe underpasses; vehicle limits (two-wheeler vs bus); extreme rain monotonicity |
| `test_weather.py` | 4 | Weather endpoints & aliases, custom rainfall simulator overrides, deterministic storm playback lifecycle (ramp-up $\to$ peak $\to$ decay), travel advice endpoint |
| `test_crowd_and_municipal.py` | 5 | KNN nearest-segment snapping, 3-device/150m auto-verification clustering, work-order lifecycle clearing crowd risk, drainage failure detection, photo magic byte/size validation |
| `test_part_c.py` | 7 | `/api/v1` prefix alias parity with `/v1`, root metadata, Structlog structured logger, rate limiting headers, HTTP 429 Too Many Requests verification on limit breach |
| `test_contract.py` | 4 | Complete OpenAPI 3.1 schema structure, tags/summary completeness, Schemathesis property-based fuzzing, Schemathesis POST response schema validation |
| `test_failure_modes.py` | 11 | PostGIS offline fallback, Redis offline fallback, Open-Meteo timeout handling, malformed bbox handling, off-grid routing point snapping, unauthorized municipal 401s, photo empty/spoof/size checks, playback out-of-bounds, extreme weather numeric monotonicity, JWT tampering rejection, WebSocket lifecycle |
| `test_od_benchmarks.py` | 43 | 5 canonical Pune O-D corridors $\times$ 5 rain scenarios ($R_{\text{safe}} \le R_{\text{fast}}$), dry weather bounds ($\le 0.25$), heavy rain flood hotspot evasion, monotonic risk growth, vehicle adaptability, and deep readiness probe (`/health/ready`) |

**Total:** 86 passed in ~15 seconds.

---

## 3. Load Testing Architecture (Locust)

The system includes a production-grade load testing suite defined in `tests/load/locustfile.py` simulating 4 concurrent personas:

1. **MapViewerUser (Weight 50)**: High-frequency queries to `/v1/segments`, `/v1/rain`, `/v1/health`, and segment explanations. Validates cache hit rates and sub-50ms latency.
2. **CommuterUser (Weight 30)**: Requests risk-weighted Dijkstra route comparisons (`POST /v1/routes/compare`) across car, two-wheeler, and auto profiles, alongside travel advice queries.
3. **CitizenReporterUser (Weight 15)**: Generates spatial reports with pseudonymous device fingerprints, triggering spatial snapping and clustering logic.
4. **MunicipalStaffUser (Weight 5)**: Authenticated triage workflow—logs in with JWT, monitors pending queues, inspects hotspot flags, and updates work orders.

---

## 4. How to Run the Tests

```bash
# 1. Run full backend pytest test suite (86 tests)
pytest services/api/tests -v

# 2. Run 5 Pune Origin-Destination benchmark suite
pytest services/api/tests/test_od_benchmarks.py -v

# 3. Run contract and schema tests
pytest services/api/tests/test_contract.py -v

# 4. Run failure mode and resilience tests
pytest services/api/tests/test_failure_modes.py -v

# 5. Run automated Locust load test (self-contained with auto-server)
python -m tests.load.run_load_test --host http://127.0.0.1:8000 --users 15 --duration 15
```
