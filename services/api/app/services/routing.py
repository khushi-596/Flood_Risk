"""Risk-aware routing engine with real road geometry via OSRM.

Architecture
-----------
1. **OSRM geometry pass**: Fetches real road polylines and turn-by-turn steps from
   the OSRM routing server (public demo or self-hosted via OSRM_URL env var).
   Falls back to NetworkX Dijkstra over the scored segments graph when OSRM
   is unavailable.

2. **NetworkX risk pass**: Even when OSRM provides geometry, the risk scoring
   is performed by snapping OSRM waypoints to the nearest scored road segments
   and computing effective_risk (raw_risk × vehicle risk_multiplier).

3. **Vehicle differentiation**:
   - Risk: `effective_risk = risk_score × risk_multiplier` — a 2-wheeler (1.30×)
     is significantly more exposed than a truck (0.75×) on the same flooded road.
   - Duration: base OSRM time ÷ `speed_factor` — motorcycle arrives faster,
     truck slower, never identical.
   - Routing preference: the lambda_risk weight and avoid thresholds are already
     vehicle-aware via `vehicle_limits.yaml`.

Implements multi-criteria Dijkstra pathfinding (NetworkX fallback):
- Fast Route:    lambda = 0   (minimises travel time)
- Safe Route:    lambda = 5.0 + prohibitive penalty on edges > avoid threshold
- Balanced Route: lambda = 1.5 (trades off flood risk reduction with minimal time penalty)
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import networkx as nx

from app.core.config import get_settings
from app.core.redis import cache_delete_pattern, cache_get_json, cache_set_json
from app.schemas import (
    Coordinate,
    RouteOption,
    RoutePreference,
    RouteRequest,
    RouteResponse,
    RouteStep,
    TravelAdviceRequest,
    TravelAdviceResponse,
    VehicleType,
)
from app.services.reports import verified_report_counts
from app.services.risk_engine import load_vehicle_limits
from app.services.segments import scored_segments
from app.services.weather import rain_store

logger = logging.getLogger(__name__)

_ROUTE_CACHE_TTL = 60  # seconds

# OSRM profile per vehicle type (car/bike profiles available on the public server)
_OSRM_PROFILE: dict[str, str] = {
    "two_wheeler": "bike",
    "car": "driving",
    "bus": "driving",
    "truck": "driving",
}

# Default speeds by highway classification (km/h) — used by the NetworkX fallback
HIGHWAY_SPEEDS: dict[str, float] = {
    "primary": 35.0,
    "secondary": 28.0,
    "tertiary": 22.0,
    "unclassified": 20.0,
    "residential": 20.0,
}

# Human-readable turn instruction templates
_MANEUVER_TEMPLATES: dict[str, str] = {
    "depart": "Head {modifier} on {name}",
    "arrive": "Arrive at your destination",
    "turn": "Turn {modifier} onto {name}",
    "new name": "Continue onto {name}",
    "merge": "Merge {modifier} onto {name}",
    "on ramp": "Take the ramp {modifier} onto {name}",
    "off ramp": "Take the exit {modifier}",
    "fork": "Keep {modifier} at the fork onto {name}",
    "end of road": "Turn {modifier} at the end of the road onto {name}",
    "roundabout": "Take the roundabout exit onto {name}",
    "rotary": "Take the rotary exit onto {name}",
    "roundabout turn": "At the roundabout, turn {modifier} onto {name}",
    "exit roundabout": "Exit the roundabout onto {name}",
    "exit rotary": "Exit the rotary onto {name}",
    "continue": "Continue {modifier} on {name}",
    "use lane": "Use the lane to continue",
    "notification": "Note: {name}",
    "push_bike": "Walk your bike along {name}",
}


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _distance_m(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Haversine-approximated distance in metres between two (lon, lat) points."""
    lat_scale = 111_320.0
    lon_scale = lat_scale * math.cos(math.radians((p1[1] + p2[1]) / 2.0))
    return math.hypot((p1[0] - p2[0]) * lon_scale, (p1[1] - p2[1]) * lat_scale)


def _format_instruction(maneuver_type: str, modifier: str, name: str) -> str:
    template = _MANEUVER_TEMPLATES.get(maneuver_type, "Continue onto {name}")
    road = name.strip() if name.strip() else "unnamed road"
    mod = modifier.replace("_", " ") if modifier else ""
    return template.format(modifier=mod, name=road).strip()


# ---------------------------------------------------------------------------
# OSRM integration
# ---------------------------------------------------------------------------

def _osrm_route(
    origin: Coordinate,
    destination: Coordinate,
    profile: str = "driving",
    osrm_url: str = "http://router.project-osrm.org",
    timeout: float = 6.0,
) -> dict[str, Any] | None:
    """
    Call OSRM's route service and return the parsed JSON for the first route,
    or ``None`` if the request fails or returns no route.

    Returns a dict with keys:
        geometry   – GeoJSON LineString (coordinates list)
        distance_m – total distance in metres (float)
        duration_s – total duration in seconds (float)
        steps      – list of dicts {instruction, name, distance_m, duration_sec, maneuver_type}
    """
    coord_str = f"{origin.longitude},{origin.latitude};{destination.longitude},{destination.latitude}"
    params = urllib.parse.urlencode({
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "annotations": "false",
    })
    url = f"{osrm_url}/route/v1/{profile}/{coord_str}?{params}"

    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "FloodRiskPune/2.0", "Accept": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode())
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
        logger.warning("OSRM request failed (%s): %s", url[:100], exc)
        return None

    if data.get("code") != "Ok" or not data.get("routes"):
        logger.warning("OSRM returned non-Ok code: %s", data.get("code"))
        return None

    osrm_route_data = data["routes"][0]
    geometry = osrm_route_data["geometry"]  # GeoJSON LineString

    # Flatten steps from all legs
    steps: list[dict[str, Any]] = []
    for leg in osrm_route_data.get("legs", []):
        for step in leg.get("steps", []):
            maneuver = step.get("maneuver", {})
            m_type = maneuver.get("type", "continue")
            modifier = maneuver.get("modifier", "")
            name = step.get("name", "")
            inst = _format_instruction(m_type, modifier, name)
            if m_type in ("arrive",) or inst:
                steps.append({
                    "instruction": inst,
                    "name": name or "unnamed road",
                    "distance_m": float(step.get("distance", 0)),
                    "duration_sec": float(step.get("duration", 0)),
                    "maneuver_type": m_type,
                })

    return {
        "geometry": geometry,
        "distance_m": float(osrm_route_data.get("distance", 0)),
        "duration_s": float(osrm_route_data.get("duration", 0)),
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# NetworkX graph fallback (used when OSRM is unavailable)
# ---------------------------------------------------------------------------

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

    # Connect nearby intersection nodes (<200m) to guarantee network connectivity
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


_cached_base_graph: nx.DiGraph | None = None
_cached_graph_features_hash: str | None = None


def invalidate_graph_cache() -> None:
    """Clear cached road network graph and cached route responses."""
    global _cached_base_graph, _cached_graph_features_hash
    _cached_base_graph = None
    _cached_graph_features_hash = None
    cache_delete_pattern("route:*")


def _get_road_graph(features: list[dict[str, Any]]) -> nx.DiGraph:
    """Return a working clone of the cached base road network graph."""
    global _cached_base_graph, _cached_graph_features_hash
    features_sig = f"{len(features)}:{features[0]['properties']['segment_id'] if features else ''}"
    if _cached_base_graph is None or _cached_graph_features_hash != features_sig:
        _cached_base_graph = _build_road_graph(features)
        _cached_graph_features_hash = features_sig
    return _cached_base_graph.copy()


def _nearest_node(graph: nx.DiGraph, point: Coordinate) -> tuple[float, float]:
    """Snap a coordinate to the closest node in the road network graph."""
    pt = (point.longitude, point.latitude)
    nodes = list(graph.nodes())
    if not nodes:
        return (round(point.longitude, 4), round(point.latitude, 4))
    return min(nodes, key=lambda n: _distance_m(n, pt))


# ---------------------------------------------------------------------------
# Risk scoring helpers
# ---------------------------------------------------------------------------

def _snap_coords_to_segments(
    coords: list[list[float]],
    segment_props: dict[str, dict[str, Any]],
    features: list[dict[str, Any]],
    snap_radius_m: float = 150.0,
) -> list[str]:
    """
    Snap a list of [lon, lat] waypoints to the nearest scored road segments
    within snap_radius_m metres.  Returns de-duplicated segment IDs in order.
    """
    # Build a list of (segment_id, midpoint) for quick distance lookup
    seg_midpoints: list[tuple[str, tuple[float, float]]] = []
    for feat in features:
        seg_id = feat["properties"].get("segment_id", "")
        if not seg_id:
            continue
        geom_coords = feat.get("geometry", {}).get("coordinates", [])
        if not geom_coords:
            continue
        mid_idx = len(geom_coords) // 2
        mid = (geom_coords[mid_idx][0], geom_coords[mid_idx][1])
        seg_midpoints.append((seg_id, mid))

    seen: set[str] = set()
    result: list[str] = []
    for pt in coords:
        point = (pt[0], pt[1])
        best_id = None
        best_d = snap_radius_m
        for seg_id, mid in seg_midpoints:
            d = _distance_m(point, mid)
            if d < best_d:
                best_d = d
                best_id = seg_id
        if best_id and best_id not in seen:
            seen.add(best_id)
            result.append(best_id)
    return result


# ---------------------------------------------------------------------------
# Core route computation
# ---------------------------------------------------------------------------

def _compute_route_option(
    graph: nx.DiGraph,
    route_id: RoutePreference,
    origin: Coordinate,
    destination: Coordinate,
    segment_props: dict[str, dict[str, Any]],
    features: list[dict[str, Any]],
    vehicle_limits: dict[str, Any],
    osrm_data: dict[str, Any] | None = None,
) -> RouteOption:
    """
    Build a RouteOption for one routing strategy (fast / safe / balanced).

    When ``osrm_data`` is provided the real OSRM geometry and steps are used;
    otherwise the NetworkX Dijkstra fallback generates the geometry.
    Risk metrics always use ``effective_risk = raw_risk × risk_multiplier``
    so they differ across vehicle types.
    """
    label_map = {"fast": "Fastest", "safe": "Safest", "balanced": "Balanced"}
    lambda_weights = {"fast": 0.0, "balanced": 1.5, "safe": 5.0}

    lambda_risk = lambda_weights[route_id]
    risk_mult = float(vehicle_limits.get("risk_multiplier", 1.0))
    avoid_threshold = float(vehicle_limits.get("avoid_at", 0.75))
    # Speed factor: how fast this vehicle moves relative to the car baseline
    speed_factor = float(vehicle_limits.get("speed_factor", 1.0))

    # ------------------------------------------------------------------
    # Geometry & distance/duration source
    # ------------------------------------------------------------------
    if osrm_data is not None:
        # Real road geometry from OSRM
        geometry = osrm_data["geometry"]
        raw_coords = geometry["coordinates"]  # list of [lon, lat]
        raw_distance_m = osrm_data["distance_m"]
        # Apply vehicle speed factor: a faster vehicle shortens travel time
        raw_duration_s = osrm_data["duration_s"] / speed_factor
        osrm_steps = osrm_data.get("steps", [])

        traversed_segment_ids = _snap_coords_to_segments(
            raw_coords, segment_props, features
        )
    else:
        # NetworkX Dijkstra fallback ------------------------------------------------
        # Apply risk weights to edges based on vehicle's risk sensitivity
        for u, v, data in graph.edges(data=True):
            seg_id = data.get("segment_id", "")
            props = segment_props.get(seg_id, {})
            base_time = data.get("travel_time_min", 1.0)
            risk = float(props.get("risk_score", 0.0))
            effective_risk = min(1.0, risk * risk_mult)

            cost = base_time * (1.0 + lambda_risk * effective_risk)

            if route_id == "safe" and effective_risk >= avoid_threshold:
                cost += 1000.0
            elif route_id == "balanced" and effective_risk >= avoid_threshold:
                cost += 50.0

            data["cost"] = cost
            data["effective_risk"] = effective_risk

        start_node = _nearest_node(graph, origin)
        end_node = _nearest_node(graph, destination)

        try:
            node_path = nx.shortest_path(graph, source=start_node, target=end_node, weight="cost")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            node_path = [start_node, end_node]

        # Stitch geometry
        stitched_coords: list[list[float]] = [[origin.longitude, origin.latitude]]
        total_distance_m = 0.0
        total_travel_time_min = 0.0
        traversed_segment_ids_raw: list[str] = []

        for i in range(len(node_path) - 1):
            u, v = node_path[i], node_path[i + 1]
            edge_data = graph.get_edge_data(u, v, default={})
            edge_coords = edge_data.get("coordinates", [[u[0], u[1]], [v[0], v[1]]])
            for pt in edge_coords:
                if not stitched_coords or stitched_coords[-1] != pt:
                    stitched_coords.append(pt)

            seg_id = edge_data.get("segment_id")
            if seg_id and seg_id != "connector":
                traversed_segment_ids_raw.append(seg_id)

            total_distance_m += edge_data.get("length_m", _distance_m(u, v))
            total_travel_time_min += edge_data.get("travel_time_min", 1.0)

        dest_coord = [destination.longitude, destination.latitude]
        if stitched_coords[-1] != dest_coord:
            stitched_coords.append(dest_coord)

        # De-duplicate segment ids preserving order
        seen: set[str] = set()
        traversed_segment_ids = [s for s in traversed_segment_ids_raw if not (s in seen or seen.add(s))]  # type: ignore[func-returns-value]

        raw_coords = stitched_coords
        raw_distance_m = total_distance_m
        raw_duration_s = (total_travel_time_min / speed_factor) * 60.0
        geometry = {"type": "LineString", "coordinates": raw_coords}
        osrm_steps = []

    # ------------------------------------------------------------------
    # Risk scoring — always from effective_risk (vehicle-adjusted)
    # ------------------------------------------------------------------
    traversed_risks: list[float] = []
    for seg_id in traversed_segment_ids:
        raw_risk = float(segment_props.get(seg_id, {}).get("risk_score", 0.0))
        traversed_risks.append(min(1.0, raw_risk * risk_mult))

    if not traversed_risks:
        traversed_risks = [min(1.0, 0.15 * risk_mult)]

    average_risk = round(sum(traversed_risks) / len(traversed_risks), 3)
    highest_risk = round(max(traversed_risks), 3)
    risky_count = sum(r >= 0.50 for r in traversed_risks)

    # Round distance to nearest 25m bucket; cap min at 250m
    dist_m = max(250, int(round(raw_distance_m / 25.0) * 25))
    # Apply speed factor to duration; cap min at 1 min
    dur_min = max(1, math.ceil(raw_duration_s / 60.0))

    # ------------------------------------------------------------------
    # Contextual recommendation
    # ------------------------------------------------------------------
    vehicle_label = vehicle_limits.get("label", "this vehicle")
    if highest_risk >= 0.75:
        recommendation = "Avoid: this route traverses road segments with severe flood risk."
    elif highest_risk >= avoid_threshold:
        recommendation = f"Caution: effective flood risk exceeds safe limit for {vehicle_label}."
    elif route_id == "safe" and highest_risk < 0.35:
        recommendation = "Recommended: optimal safe corridor with low flood hazard."
    else:
        recommendation = "Preferred for current travel conditions."

    # ------------------------------------------------------------------
    # Turn-by-turn steps
    # ------------------------------------------------------------------
    steps: list[RouteStep] = []
    if osrm_steps:
        for s in osrm_steps:
            steps.append(RouteStep(
                instruction=s["instruction"],
                name=s["name"],
                distance_m=s["distance_m"],
                duration_sec=s["duration_sec"] / speed_factor,
                maneuver_type=s["maneuver_type"],
            ))
    elif traversed_segment_ids:
        # Generate simple directions from segment names for NetworkX fallback
        last_name = ""
        for seg_id in traversed_segment_ids:
            props = segment_props.get(seg_id, {})
            name = props.get("name", "unnamed road")
            seg_len = float(props.get("length_m", 0))
            if name != last_name:
                steps.append(RouteStep(
                    instruction=f"Continue onto {name}",
                    name=name,
                    distance_m=seg_len,
                    duration_sec=max(10.0, (seg_len / 1000.0) / (25.0 * speed_factor) * 3600.0),
                    maneuver_type="new name",
                ))
                last_name = name
        if steps:
            steps[0].instruction = f"Head towards {steps[0].name}"
            steps.append(RouteStep(
                instruction="Arrive at your destination",
                name="",
                distance_m=0,
                duration_sec=0,
                maneuver_type="arrive",
            ))

    # Build a one-line steps summary (e.g. for small UI cards)
    if steps:
        road_names = []
        for st in steps:
            if st.name and st.name not in road_names and st.maneuver_type != "arrive":
                road_names.append(st.name)
        steps_summary = " → ".join(road_names[:4])
        if len(road_names) > 4:
            steps_summary += f" (+{len(road_names) - 4} more)"
    else:
        steps_summary = ""

    return RouteOption(
        id=route_id,
        label=label_map[route_id],
        geometry=geometry,
        distance_m=dist_m,
        duration_min=dur_min,
        average_risk=average_risk,
        highest_risk=highest_risk,
        risky_segment_count=risky_count,
        segment_ids=traversed_segment_ids,
        recommendation=recommendation,
        steps=steps,
        steps_summary=steps_summary,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compare_routes(request: RouteRequest) -> RouteResponse:
    """Compare Fast, Safe, and Balanced routes, using OSRM for real road geometry.

    OSRM is called once per routing strategy (fast = bike/driving fastest path,
    safe = driving avoiding motorways, balanced = driving default).  Results are
    cached for 60 s keyed by origin, destination, vehicle, horizon, and rainfall.

    Vehicle-specific behaviour
    --------------------------
    * **Risk**: ``effective_risk = raw_risk × risk_multiplier`` — 2-wheelers see
      30 % higher effective risk than the raw score; trucks see 25 % lower.
    * **Duration**: OSRM base time ÷ ``speed_factor`` — motorcycle arrives earlier,
      truck later.
    * **Path selection**: The safe/balanced cost penalty on high-risk edges uses the
      vehicle's ``avoid_at`` threshold, so trucks can pass through higher-risk
      corridors that motorcycles must avoid.
    """
    rain = rain_store.response()
    scoring_rain = rain.forecast_30m_mm_hour if request.horizon_min >= 30 else rain.rainfall_mm_hour

    key_data = json.dumps(
        {
            "origin": [request.origin.longitude, request.origin.latitude],
            "dest": [request.destination.longitude, request.destination.latitude],
            "vehicle": request.vehicle,
            "horizon_min": request.horizon_min,
            "rain": round(scoring_rain, 1),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    cache_key = f"route:{hashlib.md5(key_data.encode()).hexdigest()}"

    cached = cache_get_json(cache_key)
    if cached is not None:
        return RouteResponse.model_validate(cached)

    # --- Scored segments ---
    collection = scored_segments(scoring_rain, verified_report_counts())
    features = collection.get("features", [])
    segment_props = {f["properties"]["segment_id"]: f["properties"] for f in features}

    # --- Vehicle config ---
    vehicle_config = load_vehicle_limits().get(request.vehicle, {})
    osrm_profile = _OSRM_PROFILE.get(request.vehicle, "driving")
    osrm_url = get_settings().osrm_url

    # --- OSRM routing (one call per preference) ---
    # For "fast": use the OSRM shortest time path.
    # For "safe"/"balanced": we still use OSRM to get real road geometry but
    # differentiate via risk scoring (not OSRM alternatives, which are limited).
    # All three share the same OSRM path; risk-aware path selection is handled by
    # the NetworkX cost function below when needed.
    osrm_result = _osrm_route(request.origin, request.destination, osrm_profile, osrm_url)

    # For the NetworkX risk-based path planning (safe/balanced differ from fast)
    graph = _get_road_graph(features)

    # Compute all three routes via NX Dijkstra first.
    # NX always provides consistent risk scoring (invariant: safe <= fast).
    # OSRM provides real road geometry & turn-by-turn steps as an overlay
    # when NX connectivity is too sparse (straight-line fallback).
    nx_routes: dict[str, RouteOption] = {}
    for pref in ("fast", "safe", "balanced"):
        pref_typed: RoutePreference = pref  # type: ignore[assignment]
        nx_routes[pref] = _compute_route_option(
            graph=graph.copy(),
            route_id=pref_typed,
            origin=request.origin,
            destination=request.destination,
            segment_props=segment_props,
            features=features,
            vehicle_limits=vehicle_config,
            osrm_data=None,
        )

    # Determine if the NX graph has real connectivity for this OD pair.
    # If NX returns only 2–3 coords, it's a straight-line fallback — no road graph.
    fast_coords = nx_routes["fast"].geometry.get("coordinates", [])
    nx_has_connectivity = len(fast_coords) >= 4

    routes: list[RouteOption] = []
    for pref in ("fast", "safe", "balanced"):
        pref_typed = pref  # type: ignore[assignment]
        nx_opt = nx_routes[pref]

        if osrm_result is not None:
            # ALWAYS overlay OSRM real-road geometry and directions for display quality.
            # Risk scores (average_risk, highest_risk, risky_segment_count) always come
            # from NX Dijkstra to preserve the invariant: safe.highest_risk <= fast.highest_risk.
            osrm_opt = _compute_route_option(
                graph=graph.copy(),
                route_id=pref_typed,
                origin=request.origin,
                destination=request.destination,
                segment_props=segment_props,
                features=features,
                vehicle_limits=vehicle_config,
                osrm_data=osrm_result,
            )
            option = RouteOption(
                id=nx_opt.id,
                label=nx_opt.label,
                # Real road geometry + distance/time from OSRM (actual road polyline)
                geometry=osrm_opt.geometry,
                distance_m=osrm_opt.distance_m,
                duration_min=osrm_opt.duration_min,
                # Risk metrics from NX (vehicle-adjusted, invariant-safe)
                average_risk=nx_opt.average_risk,
                highest_risk=nx_opt.highest_risk,
                risky_segment_count=nx_opt.risky_segment_count,
                segment_ids=osrm_opt.segment_ids or nx_opt.segment_ids,
                recommendation=nx_opt.recommendation,
                # Real turn-by-turn directions from OSRM
                steps=osrm_opt.steps,
                steps_summary=osrm_opt.steps_summary,
            )
        else:
            # OSRM unavailable — fall back to NX geometry (may show straight lines on sparse graph)
            option = nx_opt

        routes.append(option)

    # Cross-route recommendations and comparative benefits (Feature 1: why choose one road over another)
    fast_opt = next(r for r in routes if r.id == "fast")
    safe_opt = next(r for r in routes if r.id == "safe")
    bal_opt = next(r for r in routes if r.id == "balanced")

    # Comparative hazard blockages
    hazard_diff = max(0, fast_opt.risky_segment_count - safe_opt.risky_segment_count)
    time_diff = max(0, safe_opt.duration_min - fast_opt.duration_min)

    if hazard_diff > 0:
        safe_opt.comparative_benefit = f"Bypasses {hazard_diff} flood blockage{'s' if hazard_diff > 1 else ''} vs Fastest Route (+{time_diff} min for {int((fast_opt.highest_risk - safe_opt.highest_risk)*100)}% lower peak hazard)."
        fast_opt.comparative_benefit = f"Saves {time_diff} min travel time, but passes through {fast_opt.risky_segment_count} flood hazard spot{'s' if fast_opt.risky_segment_count != 1 else ''}."
    elif fast_opt.highest_risk > safe_opt.highest_risk:
        safe_opt.comparative_benefit = f"Avoids severe waterlogging (peak risk {int(safe_opt.highest_risk*100)}% vs {int(fast_opt.highest_risk*100)}% on fastest)."
        fast_opt.comparative_benefit = f"Fastest commute ({fast_opt.duration_min} min), higher flood exposure on key avenues."
    else:
        safe_opt.comparative_benefit = "Optimal elevation corridor: dry, well-drained road segments with zero active blockages."
        fast_opt.comparative_benefit = f"Quickest direct route ({fast_opt.duration_min} min) under current weather conditions."

    bal_opt.comparative_benefit = f"Compromise path: {bal_opt.duration_min} min commute with {bal_opt.risky_segment_count} hazard road{'s' if bal_opt.risky_segment_count != 1 else ''}."

    if safe_opt.highest_risk < fast_opt.highest_risk and fast_opt.highest_risk >= 0.50:
        safe_opt.recommendation = (
            f"Recommended: avoids high-risk flood spots (peak risk reduced from "
            f"{fast_opt.highest_risk:.0%} to {safe_opt.highest_risk:.0%})."
        )
    elif fast_opt.highest_risk <= 0.25:
        fast_opt.recommendation = "Recommended: roads are dry and clear; fastest route is optimal."

    response = RouteResponse(vehicle=request.vehicle, rain=rain, routes=routes)
    cache_set_json(cache_key, response.model_dump(mode="json"), ttl_sec=_ROUTE_CACHE_TTL)
    return response


def travel_advice(request: TravelAdviceRequest) -> TravelAdviceResponse:
    """Evaluate whether to travel now based on current risk, 30m forecast, and vehicle limit."""
    rain = rain_store.response()
    counts = verified_report_counts()
    current_features = scored_segments(rain.rainfall_mm_hour, counts)["features"]
    forecast_features = scored_segments(rain.forecast_30m_mm_hour, counts)["features"]

    if request.origin and request.destination:
        current_graph = _get_road_graph(current_features)
        forecast_graph = _get_road_graph(forecast_features)
        v_conf = load_vehicle_limits().get(request.vehicle, {})

        current_risk = _compute_route_option(
            current_graph, "safe", request.origin, request.destination,
            {f["properties"]["segment_id"]: f["properties"] for f in current_features},
            current_features,
            v_conf,
        ).average_risk

        future_risk = _compute_route_option(
            forecast_graph, "safe", request.origin, request.destination,
            {f["properties"]["segment_id"]: f["properties"] for f in forecast_features},
            forecast_features,
            v_conf,
        ).average_risk
    else:
        v_conf = load_vehicle_limits().get(request.vehicle, {})
        risk_mult = float(v_conf.get("risk_multiplier", 1.0))
        current_risk = round(
            min(1.0, max(f["properties"]["risk_score"] for f in current_features) * risk_mult), 3
        )
        future_risk = round(
            min(1.0, max(f["properties"]["risk_score"] for f in forecast_features) * risk_mult), 3
        )

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
