"""Unit and pipeline integration tests for the Second Study Zone (PCMC).

Verifies Section C4 of the PCCOE Workplan:
    "Second zone test: Run make data for another small zone to verify reusability
     and lack of hardcoded city assumptions."
"""

from __future__ import annotations

import json
from pathlib import Path

from app.services.risk_engine import calculate_risk, rainfall_pressure, segment_threshold
from app.services.routing import _build_road_graph

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_second_zone_reusability() -> None:
    seed_path = PROJECT_ROOT / "data" / "seeds" / "second_zone_segments.geojson"
    assert seed_path.exists(), f"Seed missing at {seed_path}"

    data = json.loads(seed_path.read_text(encoding="utf-8"))
    features = data.get("features", [])
    assert len(features) >= 5, "Expected at least 5 segments in the second zone"

    # Test scoring engine on second zone segments
    for feat in features:
        props = feat["properties"]
        sig = dict(props["signals"])
        t_seg = segment_threshold(sig.get("terrain", 0.0), sig.get("flood_history", 0.0))

        # Dry test
        sig["rainfall"] = rainfall_pressure(0.0, t_seg)
        sig["citizen_reports"] = 0.0
        dry_res = calculate_risk(sig, is_dry_day=True)
        assert dry_res.score <= 0.40, f"Dry score exceeded on {props['segment_id']}"

        # Extreme rain test
        sig["rainfall"] = rainfall_pressure(60.0, t_seg)
        wet_res = calculate_risk(sig, is_dry_day=False)
        assert wet_res.score > dry_res.score, f"Monotonicity failed on {props['segment_id']}"

    # Test graph construction on second zone geometry
    graph = _build_road_graph(features)
    assert len(graph.nodes) >= 4
    assert len(graph.edges) >= 4
