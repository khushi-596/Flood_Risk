# Implementation roadmap

## Day 1 - foundation and map (implemented)

1. Start the Compose stack, API health route, automatic OpenAPI docs, and web shell.
2. Serve a fixed Pune demo zone from `data/seeds/demo_segments.geojson`; do not
   couple the demo to an external data API.
3. Render road segments by risk band, include a legend, and provide map/search point
   selection.
4. Accept a crowd report and attach it to the nearest line segment.
5. Keep the risk formula and all weights under version control.
6. Run the Day 1 checks in `services/api/tests` and manually send one report via
   `/docs` before presenting.

## Day 2 - live risk, safe routes, and verification

1. Replace demo-only road features with outputs of `pipelines/`; load them into
   PostGIS and add spatial indexes.
2. Implement a `RiskEngine` service that reads the versioned YAML configuration and
   exposes score, confidence, and top factors for every segment.
3. Add an Open-Meteo worker with Redis last-known-good caching and an explicit stale
   data flag. Add a simulator override endpoint for a reliable demo.
4. Build Fast, Safe, and Balanced network routes. The Safe cost should penalise
   flood risk and each response should report distance, duration, mean/highest risk,
   risky-segment count, and recommendation.
5. Introduce rate limiting plus the 3 reporters / 150 m / 30 minute verification
   rule. Only verified reports affect the crowd signal.
6. Build report form, segment explanation sheet, rain controls, route comparison,
   and staff report queue.
7. Acceptance test: under heavy simulated rain, the Safe route is never riskier
   than the Fast route; three independent reports make the same segment more risky.

## Day 3 - forecast, municipal workflow, resilience

1. Calculate a 30-minute risk projection from forecast rainfall and the last-hour
   trend. Add vehicle thresholds and a Go/Caution/Wait/Avoid travel verdict.
2. Publish risk-band transitions over WebSocket and display high/severe alerts.
3. Add municipal hotspots, drainage-failure flags, report review, work-order states,
   CSV export, and citizen report-status lookup.
4. Add API cache keys, database indexes, file validation, role expiry, service
   degradation handling, and observability.
5. Run end-to-end, failure, and responsive-accessibility tests; freeze features two
   hours before submission and fix only verified defects.

## GPU decision gate

The planned Day 1-3 system is fully CPU-capable. Ask for a Colab GPU only if the
team elects to train a model with labelled images, satellite rasters, or a neural
forecast model. First create a CPU baseline and data-split evaluation; place the
trained artifact and its metadata under `models/artifacts/` as documented.
