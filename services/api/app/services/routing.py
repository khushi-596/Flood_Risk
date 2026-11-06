"""Risk-aware NetworkX graph routing engine.

Implements multi-criteria Dijkstra pathfinding:
- Fast Route: lambda = 0 (minimizes travel time)
- Safe Route: lambda = 5.0 + prohibitive penalty on edges exceeding vehicle avoid threshold
- Balanced Route: lambda = 1.5 (trades off flood risk reduction with minimal time penalty)
"""

from __future__ import annotations

import math
from typing import Any

import networkx as nx

from app.schemas import (
    Coordinate,
    RouteOption,
    RoutePreference,
    RouteRequest,
    RouteResponse,
    TravelAdviceRequest,
    TravelAdviceResponse,
    VehicleType,
)
from app.services.reports import verified_report_counts
from app.services.risk_engine import load_vehicle_limits
from app.services.segments import scored_segments
from app.services.weather import rain_store

# Default speeds by highway classification (km/h)
HIGHWAY_SPEEDS: dict[str, float] = {
    "primary": 35.0,
    "secondary": 28.0,
    "tertiary": 22.0,
    "unclassified": 20.0,
    "residential": 20.0,
}


def _distance_m(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Distance in meters between two (lon, lat) points."""
    lat_scale = 111_320.0
    lon_scale = lat_scale * math.cos(math.radians((p1[1] + p2[1]) / 2.0))
    return math.hypot((p1[0] - p2[0]) * lon_scale, (p1[1] - p2[1]) * lat_scale)


def _build_road_graph(features: list[dict[str, Any]]) -> nx.DiGraph:
    """Construct an interconnected NetworkX DiGraph from segment features."""
    graph = nx.DiGraph()

    for feat in features:
        props = feat.get("properties", {})
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if len(coords) < 2:
            continue

        seg_id = props.get("segment_id", "")
        name = props.get("name", "Unnamed road")
        highway = props.get("highway", "unclassified")
        length_m = float(props.get("length_m", 0))
        speed_kmph = HIGHWAY_SPEEDS.get(highway, 25.0)

        if length_m <= 0:
            length_m = sum(_distance_m(coords[i], coords[i + 1]) for i in range(len(coords) - 1))

        travel_time_min = max(0.1, (length_m / 1000.0) / speed_kmph * 60.0)

        # Nodes are represented by (lon, lat) rounded to 4 decimals (~11m precision)
        start_node = (round(coords[0][0], 4), round(coords[0][1], 4))
        end_node = (round(coords[-1][0], 4), round(coords[-1][1], 4))

        # Add bidirectional edges
        graph.add_node(start_node, lon=coords[0][0], lat=coords[0][1])
        graph.add_node(end_node, lon=coords[-1][0], lat=coords[-1][1])

        graph.add_edge(
            start_node,
            end_node,
            segment_id=seg_id,
            name=name,
            length_m=length_m,
            travel_time_min=travel_time_min,
            coordinates=coords,
        )
        graph.add_edge(
            end_node,
            start_node,
            segment_id=seg_id,
            name=name,
            length_m=length_m,
            travel_time_min=travel_time_min,
            coordinates=list(reversed(coords)),
        )

    # Connect nearby intersection nodes (< 200m) to guarantee network connectivity
    nodes = list(graph.nodes())
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            n1, n2 = nodes[i], nodes[j]
            d = _distance_m(n1, n2)
            if 0 < d < 200.0:
                if not graph.has_edge(n1, n2):
                    t = (d / 1000.0) / 25.0 * 60.0
                    graph.add_edge(
                        n1, n2,
                        segment_id="connector",
                        name="Intersection Connector",
                        length_m=d,
                        travel_time_min=t,
                        coordinates=[[n1[0], n1[1]], [n2[0], n2[1]]],
                    )
                if not graph.has_edge(n2, n1):
                    t = (d / 1000.0) / 25.0 * 60.0
                    graph.add_edge(
                        n2, n1,
                        segment_id="connector",
                        name="Intersection Connector",
                        length_m=d,
                        travel_time_min=t,
                        coordinates=[[n2[0], n2[1]], [n1[0], n1[1]]],
                    )

    return graph


def _nearest_node(graph: nx.DiGraph, point: Coordinate) -> tuple[float, float]:
    """Snap a coordinate to the closest node in the road network graph."""
    pt = (point.longitude, point.latitude)
    nodes = list(graph.nodes())
    if not nodes:
        return (round(point.longitude, 4), round(point.latitude, 4))
    return min(nodes, key=lambda n: _distance_m(n, pt))


def _compute_route_option(
    graph: nx.DiGraph,
    route_id: RoutePreference,
    origin: Coordinate,
    destination: Coordinate,
    segment_props: dict[str, dict[str, Any]],
    vehicle_limits: dict[str, Any],
) -> RouteOption:
    """Run Dijkstra pathfinding on the risk-weighted graph."""
    label_map = {"fast": "Fastest", "safe": "Safest", "balanced": "Balanced"}
    lambda_weights = {"fast": 0.0, "balanced": 1.5, "safe": 5.0}

    lambda_risk = lambda_weights[route_id]
    risk_mult = float(vehicle_limits.get("risk_multiplier", 1.0))
    avoid_threshold = float(vehicle_limits.get("avoid_at", 0.75))

    # Weight edges dynamically based on live risk
    for u, v, data in graph.edges(data=True):
        seg_id = data.get("segment_id", "")
        props = segment_props.get(seg_id, {})
        base_time = data.get("travel_time_min", 1.0)
        risk = float(props.get("risk_score", 0.0))
        effective_risk = min(1.0, risk * risk_mult)

        # Cost formula: time * (1 + lambda * risk)
        cost = base_time * (1.0 + lambda_risk * effective_risk)

        # Penalize edges exceeding avoid threshold
        if route_id == "safe" and effective_risk >= avoid_threshold:
            cost += 1000.0  # Prohibitive avoid penalty
        elif route_id == "balanced" and effective_risk >= avoid_threshold:
            cost += 50.0

        data["cost"] = cost
        data["effective_risk"] = effective_risk

    start_node = _nearest_node(graph, origin)
    end_node = _nearest_node(graph, destination)

    # Pathfinding
    try:
        node_path = nx.shortest_path(graph, source=start_node, target=end_node, weight="cost")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        # Fallback to direct path between start and end
        node_path = [start_node, end_node]

    # Stitch geometry and collect traversed segments
    stitched_coords: list[list[float]] = [[origin.longitude, origin.latitude]]
    total_distance_m = 0.0
    total_travel_time_min = 0.0
    traversed_segment_ids: list[str] = []
    traversed_risks: list[float] = []

    for i in range(len(node_path) - 1):
        u, v = node_path[i], node_path[i + 1]
        edge_data = graph.get_edge_data(u, v, default={})
        edge_coords = edge_data.get("coordinates", [[u[0], u[1]], [v[0], v[1]]])

        for pt in edge_coords:
            if not stitched_coords or stitched_coords[-1] != pt:
                stitched_coords.append(pt)

        seg_id = edge_data.get("segment_id")
        if seg_id and seg_id != "connector":
            traversed_segment_ids.append(seg_id)
            props = segment_props.get(seg_id, {})
            traversed_risks.append(float(props.get("risk_score", 0.0)))

        total_distance_m += edge_data.get("length_m", _distance_m(u, v))
        total_travel_time_min += edge_data.get("travel_time_min", 1.0)

    # Append destination coordinate
    dest_coord = [destination.longitude, destination.latitude]
    if stitched_coords[-1] != dest_coord:
        stitched_coords.append(dest_coord)

    # Deduplicate segment ids preserving order
    seen = set()
    unique_seg_ids = [s for s in traversed_segment_ids if not (s in seen or seen.add(s))]

    if not traversed_risks:
        # Fallback if no named segments were traversed
        traversed_risks = [0.15]

    average_risk = round(sum(traversed_risks) / len(traversed_risks), 3)
    highest_risk = round(max(traversed_risks), 3)
    risky_count = sum(r >= 0.50 for r in traversed_risks)

    dist_m = max(250, int(round(total_distance_m / 25.0) * 25))
    dur_min = max(2, math.ceil(total_travel_time_min))

    # Contextual recommendation
    if highest_risk >= 0.75:
        recommendation = "Avoid: this route traverses road segments with severe flood risk."
    elif highest_risk >= avoid_threshold:
        recommendation = f"Caution: exceeds safe limit for {vehicle_limits.get('label', 'this vehicle')}."
    elif route_id == "safe" and highest_risk < 0.35:
        recommendation = "Recommended: optimal safe corridor with low flood hazard."
    else:
        recommendation = "Preferred for current travel conditions."

    return RouteOption(
        id=route_id,
        label=label_map[route_id],
        geometry={"type": "LineString", "coordinates": stitched_coords},
        distance_m=dist_m,
        duration_min=dur_min,
        average_risk=average_risk,
        highest_risk=highest_risk,
        risky_segment_count=risky_count,
        segment_ids=unique_seg_ids,
        recommendation=recommendation,
    )


def compare_routes(request: RouteRequest) -> RouteResponse:
    """Compare Fast, Safe, and Balanced routes over the risk-weighted graph."""
    rain = rain_store.response()
    collection = scored_segments(rain.rainfall_mm_hour, verified_report_counts())
    features = collection.get("features", [])

    # Map segment_id -> properties
    segment_props = {f["properties"]["segment_id"]: f["properties"] for f in features}

    # Build road network graph
    graph = _build_road_graph(features)

    # Vehicle limits
    vehicle_config = load_vehicle_limits().get(request.vehicle, {})

    routes: list[RouteOption] = []
    for pref in ("fast", "safe", "balanced"):
        option = _compute_route_option(
            graph=graph,
            route_id=pref,  # type: ignore[arg-type]
            origin=request.origin,
            destination=request.destination,
            segment_props=segment_props,
            vehicle_limits=vehicle_config,
        )
        routes.append(option)

    # Final recommendation comparison: recommend Safe when it reduces risk meaningfully
    fast_opt = next(r for r in routes if r.id == "fast")
    safe_opt = next(r for r in routes if r.id == "safe")

    if safe_opt.highest_risk < fast_opt.highest_risk and fast_opt.highest_risk >= 0.50:
        safe_opt.recommendation = (
            f"Recommended: avoids high-risk flood spots (peak risk reduced from "
            f"{fast_opt.highest_risk} to {safe_opt.highest_risk})."
        )
    elif fast_opt.highest_risk <= 0.25:
        fast_opt.recommendation = "Recommended: roads are dry and clear; fastest route is optimal."

    return RouteResponse(vehicle=request.vehicle, rain=rain, routes=routes)


def travel_advice(request: TravelAdviceRequest) -> TravelAdviceResponse:
    """Evaluate whether to travel now based on current risk, 30m forecast, and vehicle limit."""
    rain = rain_store.response()
    counts = verified_report_counts()
    current_features = scored_segments(rain.rainfall_mm_hour, counts)["features"]
    forecast_features = scored_segments(rain.forecast_30m_mm_hour, counts)["features"]

    if request.origin and request.destination:
        current_graph = _build_road_graph(current_features)
        forecast_graph = _build_road_graph(forecast_features)
        v_conf = load_vehicle_limits().get(request.vehicle, {})

        current_risk = _compute_route_option(
            current_graph, "safe", request.origin, request.destination,
            {f["properties"]["segment_id"]: f["properties"] for f in current_features},
            v_conf,
        ).average_risk

        future_risk = _compute_route_option(
            forecast_graph, "safe", request.origin, request.destination,
            {f["properties"]["segment_id"]: f["properties"] for f in forecast_features},
            v_conf,
        ).average_risk
    else:
        current_risk = round(max(f["properties"]["risk_score"] for f in current_features), 3)
        future_risk = round(max(f["properties"]["risk_score"] for f in forecast_features), 3)

    thresholds = load_vehicle_limits()[request.vehicle]

    if future_risk >= thresholds["avoid_at"]:
        verdict = "avoid"
    elif future_risk >= thresholds["wait_at"]:
        verdict = "wait"
    elif future_risk >= thresholds["caution_at"]:
        verdict = "caution"
    else:
        verdict = "go"

    trend = (
        "rising"
        if future_risk > current_risk + 0.03
        else "falling"
        if future_risk < current_risk - 0.03
        else "stable"
    )

    reasons = [
        f"{request.vehicle.replace('_', ' ').capitalize()} safety threshold applied.",
        f"Rain is {trend}: {rain.rainfall_mm_hour:.1f} to {rain.forecast_30m_mm_hour:.1f} mm/h over next 30 min.",
    ]
    if rain.is_stale:
        reasons.append("Live weather is unavailable; using cached observations.")

    return TravelAdviceResponse(
        verdict=verdict,
        vehicle=request.vehicle,
        risk_now=current_risk,
        risk_in_30m=future_risk,
        trend=trend,
        reasons=reasons,
        updated_at=rain.updated_at,
    )
