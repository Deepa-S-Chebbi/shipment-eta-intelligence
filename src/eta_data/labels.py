"""
Rule-based delay labeling and exact arithmetic delay reason decomposition.
Reconciles carrier, weather, queue, calendar, and reroute components so that
the sum of attributed delay hours equals total positive delay exactly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple
from eta_data.ids import (
    build_delay_attribution_id,
    build_delay_id,
)

STANDARD_DELAY_REASONS = [
    ("WEATHER", "Severe weather hazard or meteorological disturbance along route", 4),
    ("FACILITY_QUEUE", "Terminal dock congestion, gate dwell, and facility queue delay", 3),
    ("CARRIER_DELAY", "Carrier operational transit slowdown below scheduled speed", 3),
    ("ROUTE_CHANGE", "Detour mileage and handling penalty resulting from dynamic reroute", 3),
    ("CALENDAR_CLOSURE", "Operating schedule hold during night, weekend, or holiday closure", 2),
    ("LATE_PICKUP", "Dispatch preparation delay at origin facility prior to departure", 2),
]


def generate_delay_reason_taxonomy() -> List[Dict[str, Any]]:
    """Generates standard DelayReason master taxonomy rows."""
    reasons: List[Dict[str, Any]] = []
    for seq, (code, desc, sev) in enumerate(STANDARD_DELAY_REASONS, start=1):
        reasons.append({
            "delay_id": build_delay_id(seq),
            "reason_code": code,
            "description": desc,
            "severity": sev,
        })
    return reasons


def compute_delay_labels_and_reasons(
    shipments: List[Dict[str, Any]],
    legs: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    service_levels: List[Dict[str, Any]],
    delay_reasons: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Computes final delay labels for all shipments and generates ShipmentDelayReason
    reconciliation rows for delayed shipments.
    """
    sl_map = {sl["service_level_id"]: sl for sl in service_levels}
    reason_map = {r["reason_code"]: r["delay_id"] for r in delay_reasons}

    # Group legs by shipment_id
    legs_by_shipment: Dict[str, List[Dict[str, Any]]] = {}
    for l in legs:
        legs_by_shipment.setdefault(l["shipment_id"], []).append(l)

    # Group terminal events by shipment_id
    delivered_events: Dict[str, Dict[str, Any]] = {}
    for e in events:
        if e["event_type"] == "DELIVERED":
            delivered_events[e["shipment_id"]] = e

    all_attributions: List[Dict[str, Any]] = []
    sdr_seq = 1

    for shp in shipments:
        shp_id = shp["shipment_id"]
        sl = sl_map[shp["service_level_id"]]
        grace_hours = float(sl["grace_hours"])
        severe_hours = float(sl["severely_delayed_hours"])

        # Determine actual delivery from DELIVERED event
        del_evt = delivered_events.get(shp_id)
        if not del_evt:
            shp["final_delay_label"] = "CANCELLED"
            continue

        actual_del_dt = datetime.fromisoformat(del_evt["event_time"].rstrip("Z"))
        promised_dt = datetime.fromisoformat(shp["promised_delivery_at"].rstrip("Z"))
        created_dt = datetime.fromisoformat(shp["created_at"].rstrip("Z"))

        # Keep shipment delivery in sync with event
        shp["actual_delivery_at"] = del_evt["event_time"]

        total_delay_hours = (actual_del_dt - promised_dt).total_seconds() / 3600.0

        # Exact boundary logic
        if total_delay_hours <= grace_hours:
            shp["final_delay_label"] = "ON_TIME"
        elif total_delay_hours <= severe_hours:
            shp["final_delay_label"] = "DELAYED"
        else:
            shp["final_delay_label"] = "SEVERELY_DELAYED"

        # Arithmetic delay attribution decomposition if positive delay
        if total_delay_hours > 0:
            shp_legs = legs_by_shipment.get(shp_id, [])

            # Compute raw breakdown estimates
            raw_weather = 0.0
            raw_carrier = 0.0
            raw_queue = 0.0
            raw_calendar = 0.0
            raw_reroute = 4.0 if shp.get("is_rerouted") else 0.0

            # First leg pickup delay
            if shp_legs:
                l1_dep = datetime.fromisoformat(shp_legs[0]["actual_depart_at"].rstrip("Z"))
                raw_late_pickup = max(0.0, (l1_dep - created_dt).total_seconds() / 3600.0 - 2.0)
            else:
                raw_late_pickup = 0.0

            for leg in shp_legs:
                p_dep = datetime.fromisoformat(leg["planned_depart_at"].rstrip("Z"))
                p_arr = datetime.fromisoformat(leg["planned_arrive_at"].rstrip("Z"))
                a_dep = datetime.fromisoformat(leg["actual_depart_at"].rstrip("Z"))
                a_arr = datetime.fromisoformat(leg["actual_arrive_at"].rstrip("Z"))

                p_dur = (p_arr - p_dep).total_seconds() / 3600.0
                a_dur = (a_arr - a_dep).total_seconds() / 3600.0

                diff = max(0.0, a_dur - p_dur)
                # Split leg excess into weather vs carrier noise
                raw_weather += diff * 0.60
                raw_carrier += diff * 0.40

                # Intermediate dwell/queue wait
                wait_hours = max(0.0, (a_dep - p_dep).total_seconds() / 3600.0)
                raw_queue += wait_hours * 0.70
                raw_calendar += wait_hours * 0.30

            components = [
                ("WEATHER", raw_weather),
                ("FACILITY_QUEUE", raw_queue),
                ("CARRIER_DELAY", raw_carrier),
                ("ROUTE_CHANGE", raw_reroute),
                ("CALENDAR_CLOSURE", raw_calendar),
                ("LATE_PICKUP", raw_late_pickup),
            ]

            sum_raw = sum(val for _, val in components)
            if sum_raw <= 0:
                # Fallback purely to carrier delay
                attributed_map = {"CARRIER_DELAY": total_delay_hours}
            else:
                attributed_map = {
                    code: total_delay_hours * (val / sum_raw)
                    for code, val in components
                    if val > 0
                }

            # Arithmetic exact reconciliation: ensure sum(attributed) == total_delay_hours
            if attributed_map:
                diff = total_delay_hours - sum(attributed_map.values())
                # Add tiny float diff to the primary largest contributor
                top_code = max(attributed_map, key=attributed_map.get)
                attributed_map[top_code] += diff

                for code, hours in attributed_map.items():
                    if hours > 1e-4:
                        attr_row = {
                            "attribution_id": build_delay_attribution_id(sdr_seq),
                            "shipment_id": shp_id,
                            "leg_id": shp_legs[0]["leg_id"] if shp_legs else None,
                            "delay_id": reason_map[code],
                            "delay_hours_attributed": round(hours, 4),
                        }
                        all_attributions.append(attr_row)
                        sdr_seq += 1

    return shipments, all_attributions
