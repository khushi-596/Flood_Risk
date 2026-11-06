"""Second Zone Reusability Pipeline & Verification (Section C4 of PCCOE Workplan).

Demonstrates that the data extraction, segmentation, risk calculation engine,
and pathfinding pipelines are completely zone-agnostic and work seamlessly
for a second study zone (PCMC / Pimpri-Chinchwad).

Usage:
    python -m pipelines.run_second_zone
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "services" / "api"))

from app.services.risk_engine import calculate_risk, segment_threshold, rainfall_pressure
from app.services.routing import _build_road_graph


def run_second_zone_pipeline() -> dict[str, int | float | str]:
    seed_path = PROJECT_ROOT / "data" / "seeds" / "second_zone_segments.geojson"
    if not seed_path.exists():
        raise FileNotFoundError(f"Second zone seed not found: {seed_path}")

    data = json.loads(seed_path.read_text(encoding="utf-8"))
    features = data.get("features", [])
    print(f"[Zone 2: {data.get('name')}] Loaded {len(features)} road segments.")

    # 1. Pipeline Feature Validation
    for f in features:
        props = f["properties"]
        geom = f["geometry"]
        assert "segment_id" in props, "Segment missing segment_id"
        assert "name" in props, "Segment missing name"
        assert "signals" in props, "Segment missing signals"
        assert geom["type"] == "LineString", "Invalid geometry type"
        assert len(geom["coordinates"]) >= 2, "LineString needs at least 2 points"

    print("[Zone 2] Schema & GeoJSON validation passed.")

    # 2. Risk Monotonicity & Scoring Across Rain Scenarios
    scenarios = [
        ("dry", 0.0, True),
        ("moderate", 15.0, False),
        ("heavy", 30.0, False),
        ("extreme", 55.0, False),
    ]

    for f in features:
        props = f["properties"]
        sig = dict(props["signals"])
        t_seg = segment_threshold(sig.get("terrain", 0.0), sig.get("flood_history", 0.0))

        prev_score = -1.0
        for name, rain, is_dry in scenarios:
            sig["rainfall"] = rainfall_pressure(rain, t_seg)
            sig["citizen_reports"] = 0.0
            res = calculate_risk(sig, is_dry_day=is_dry)
            assert res.score >= prev_score - 1e-4, f"Monotonicity violation on {props['segment_id']} for {name}"
            prev_score = res.score

    print("[Zone 2] Risk monotonicity verified across all rainfall levels.")

    # 3. Pathfinding / Network Graph Construction on Second Zone
    graph = _build_road_graph(features)
    assert len(graph.nodes) >= 4, "Graph has insufficient nodes"
    assert len(graph.edges) >= 4, "Graph has insufficient edges"
    print(f"[Zone 2] Network graph built successfully: {len(graph.nodes)} nodes, {len(graph.edges)} edges.")

    print(f"=== Second Zone Pipeline Verification: SUCCESS ({len(features)} segments) ===")
    return {
        "zone_name": data.get("name", "pcmc"),
        "segment_count": len(features),
        "graph_nodes": len(graph.nodes),
        "graph_edges": len(graph.edges),
    }


if __name__ == "__main__":
    run_second_zone_pipeline()
