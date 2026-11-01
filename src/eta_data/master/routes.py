"""Deterministic Route and RouteLegTemplate master data generator."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple
from eta_data.config import AppConfig
from eta_data.ids import build_route_id, build_route_leg_template_id
from eta_data.rng import RNGManager

# Mode circuity factors (tortuosity)
CIRCUITY_FACTORS = {
    "ROAD": 1.25,
    "RAIL": 1.15,
    "AIR": 1.02,
    "SEA": 1.30,
}


def _calculate_distance(fac_a: Dict[str, Any], fac_b: Dict[str, Any], mode: str) -> float:
    """Euclidean distance scaled by mode circuity factor."""
    dx = float(fac_b["longitude"]) - float(fac_a["longitude"])
    dy = float(fac_b["latitude"]) - float(fac_a["latitude"])
    euclidean = math.sqrt(dx * dx + dy * dy)
    factor = CIRCUITY_FACTORS.get(mode, 1.20)
    return max(15.0, euclidean * factor)


def generate_routes(
    cfg: AppConfig,
    facilities: List[Dict[str, Any]],
    carriers: List[Dict[str, Any]],
    rng_manager: RNGManager,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generates Routes and RouteLegTemplates connecting facilities across 1 to 4 hops."""
    rng = rng_manager.get_stream("master_routes")
    start_dt = datetime.fromisoformat(cfg.simulation.start_date.rstrip("Z"))
    end_dt = start_dt + timedelta(days=cfg.simulation.duration_days + 30)

    num_routes = cfg.targets.num_routes
    fac_by_id = {f["facility_id"]: f for f in facilities}
    hubs = [f for f in facilities if f["type"] == "HUB"]
    if not hubs:
        hubs = facilities[:2]

    carriers_by_mode: Dict[str, List[Dict[str, Any]]] = {}
    for c in carriers:
        carriers_by_mode.setdefault(c["mode"], []).append(c)

    routes: List[Dict[str, Any]] = []
    templates: List[Dict[str, Any]] = []

    # Distribution of leg counts: 1 leg: 35%, 2 legs: 40%, 3 legs: 20%, 4 legs: 5%
    leg_counts = [1, 2, 3, 4]
    leg_probs = [0.35, 0.40, 0.20, 0.05]

    template_seq = 1

    for r_idx in range(num_routes):
        route_id = build_route_id(r_idx + 1)

        # Pick distinct origin and destination
        orig_fac = rng.choice(facilities)
        dest_candidates = [f for f in facilities if f["facility_id"] != orig_fac["facility_id"]]
        dest_fac = rng.choice(dest_candidates)

        n_legs = int(rng.choice(leg_counts, p=leg_probs))

        # Build path of facilities
        path = [orig_fac]
        if n_legs == 1:
            path.append(dest_fac)
        elif n_legs == 2:
            # Origin -> Hub -> Destination
            intermediate_hubs = [h for h in hubs if h["facility_id"] not in (orig_fac["facility_id"], dest_fac["facility_id"])]
            mid_hub = rng.choice(intermediate_hubs) if intermediate_hubs else hubs[0]
            path.extend([mid_hub, dest_fac])
        elif n_legs == 3:
            # Origin -> Hub1 -> Hub2 -> Destination
            intermediate_hubs = [h for h in hubs if h["facility_id"] not in (orig_fac["facility_id"], dest_fac["facility_id"])]
            if len(intermediate_hubs) >= 2:
                chosen_hubs = list(rng.choice(intermediate_hubs, size=2, replace=False))
            else:
                chosen_hubs = [hubs[0], hubs[min(1, len(hubs)-1)]]
            path.extend([chosen_hubs[0], chosen_hubs[1], dest_fac])
        else: # 4 legs
            intermediate = [f for f in facilities if f["facility_id"] not in (orig_fac["facility_id"], dest_fac["facility_id"])]
            chosen = list(rng.choice(intermediate, size=3, replace=False)) if len(intermediate) >= 3 else [hubs[0], hubs[0], hubs[0]]
            path.extend([chosen[0], chosen[1], chosen[2], dest_fac])

        # Generate leg templates for this route
        # Calibrated end-to-end planned timetable targets:
        # 1-hop: ~20.0h (24h Express SLA -> 4.0h operational buffer)
        # 2-hop: ~41.5h (48h Express SLA -> 6.5h operational buffer)
        # 3-hop: ~62.5h (72h Standard SLA -> 9.5h operational buffer)
        # 4-hop: ~105.0h (120h Freight SLA -> 15.0h operational buffer)
        target_total = {1: 20.0, 2: 41.5, 3: 62.5, 4: 105.0}[n_legs]
        leg_base = target_total / n_legs

        total_planned_hours = 0.0
        for leg_seq in range(1, len(path)):
            f_from = path[leg_seq - 1]
            f_to = path[leg_seq]

            # Choose mode: Long distances (> 500km) between HUBs can use AIR/RAIL, otherwise ROAD
            dist_approx = math.hypot(f_to["longitude"] - f_from["longitude"], f_to["latitude"] - f_from["latitude"])
            if dist_approx > 600.0 and "AIR" in carriers_by_mode and rng.random() < 0.40:
                mode = "AIR"
            elif dist_approx > 350.0 and "RAIL" in carriers_by_mode and rng.random() < 0.35:
                mode = "RAIL"
            elif f_from["type"] == "PORT" and f_to["type"] == "PORT" and "SEA" in carriers_by_mode:
                mode = "SEA"
            else:
                mode = "ROAD"

            candidate_carriers = carriers_by_mode.get(mode, carriers)
            carrier = rng.choice(candidate_carriers)

            p_leg = round(leg_base + float(rng.uniform(-0.4, 0.4)), 2)
            total_planned_hours += p_leg

            t_row = {
                "template_id": build_route_leg_template_id(template_seq),
                "route_id": route_id,
                "leg_sequence": leg_seq,
                "from_facility_id": f_from["facility_id"],
                "to_facility_id": f_to["facility_id"],
                "carrier_id": carrier["carrier_id"],
                "planned_duration_hours": p_leg,
            }
            templates.append(t_row)
            template_seq += 1

        route_row = {
            "route_id": route_id,
            "origin_facility_id": orig_fac["facility_id"],
            "destination_facility_id": dest_fac["facility_id"],
            "total_planned_hours": round(total_planned_hours, 2),
            "version": 1,
            "effective_from": start_dt.isoformat() + "Z",
            "effective_to": end_dt.isoformat() + "Z",
        }
        routes.append(route_row)

    return routes, templates
