"""
Controlled edge case and anomaly injection module with strict ground-truth isolation.
Injected anomalies are recorded exclusively in ground_truth tables, leaving primary
feature tables clean of any giveaway label columns.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple
from eta_data.config import AppConfig
from eta_data.rng import RNGManager


def inject_anomalies(
    cfg: AppConfig,
    shipments: List[Dict[str, Any]],
    legs: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    eta_estimates: List[Dict[str, Any]],
    rng_manager: RNGManager,
) -> List[Dict[str, Any]]:
    """
    Injects 4 required anomalies at controlled rates and returns isolated ground_truth records.
    Primary tables are modified in-place without adding any anomaly label columns.
    """
    rng = rng_manager.get_stream("anomalies_injection")
    ground_truth: List[Dict[str, Any]] = []

    # 1. EVENT_TIME_INGESTION_CONFUSION (~0.6% of events)
    # Swap event_time and ingestion_time so event_time > ingestion_time
    rate_confusion = cfg.anomalies.event_time_ingestion_confusion
    for ev in events:
        if ev["event_type"] != "CREATED" and rng.random() < rate_confusion:
            orig_ev_time = ev["event_time"]
            orig_ing_time = ev["ingestion_time"]
            t_ing = datetime.fromisoformat(orig_ing_time.rstrip("Z"))

            # Force event_time to be strictly after ingestion_time
            corrupted_ev_time = (t_ing + timedelta(minutes=int(rng.integers(15, 120)))).isoformat() + "Z"

            ev["event_time"] = corrupted_ev_time
            ev["ingestion_time"] = orig_ing_time

            ground_truth.append({
                "record_type": "TrackingEvent",
                "record_id": ev["event_id"],
                "issue_type": "EVENT_TIME_INGESTION_CONFUSION",
                "description": "Event timestamp corrupted to occur after database ingestion timestamp",
                "expected_decision": "IMPUTE_EVENT_TIME",
                "injected_field": "event_time",
                "original_value": orig_ev_time,
                "injected_value": corrupted_ev_time,
            })

    # 2. IMPOSSIBLE_ROUTE_ORDER (~0.5% of shipments)
    # Leg arrival timestamp corrupted to precede leg departure
    rate_route_order = cfg.anomalies.impossible_route_order
    legs_by_shipment: Dict[str, List[Dict[str, Any]]] = {}
    for l in legs:
        legs_by_shipment.setdefault(l["shipment_id"], []).append(l)

    for shp_id, shp_legs in legs_by_shipment.items():
        if len(shp_legs) >= 1 and rng.random() < rate_route_order:
            target_leg = shp_legs[int(rng.integers(0, len(shp_legs)))]
            orig_arrive = target_leg["actual_arrive_at"]
            t_dep = datetime.fromisoformat(target_leg["actual_depart_at"].rstrip("Z"))

            # Set arrival 2 hours before departure (negative duration)
            corrupted_arrive = (t_dep - timedelta(hours=2.0)).isoformat() + "Z"
            target_leg["actual_arrive_at"] = corrupted_arrive

            ground_truth.append({
                "record_type": "ShipmentLeg",
                "record_id": target_leg["leg_id"],
                "issue_type": "IMPOSSIBLE_ROUTE_ORDER",
                "description": "Leg actual arrival timestamp precedes actual departure timestamp",
                "expected_decision": "QUARANTINE_RECORD",
                "injected_field": "actual_arrive_at",
                "original_value": orig_arrive,
                "injected_value": corrupted_arrive,
            })

    # 3. ETA_USES_FUTURE_EVENT (~0.5% of ETA estimates)
    # Features cutoff time or n_events_used peeks into the future
    rate_eta_leak = cfg.anomalies.eta_uses_future_event
    for eta in eta_estimates:
        if rng.random() < rate_eta_leak:
            orig_cutoff = eta["features_cutoff_time"]
            t_pred = datetime.fromisoformat(eta["prediction_time"].rstrip("Z"))

            # Set cutoff 6 hours in the future
            future_cutoff = (t_pred + timedelta(hours=6.0)).isoformat() + "Z"
            eta["features_cutoff_time"] = future_cutoff
            eta["n_events_used"] += 3  # Artificially incorporate future scans

            ground_truth.append({
                "record_type": "ETAEstimate",
                "record_id": eta["eta_id"],
                "issue_type": "ETA_USES_FUTURE_EVENT",
                "description": "ETA estimate incorporates tracking events ingested after prediction timestamp",
                "expected_decision": "FLAG_DATA_LEAKAGE",
                "injected_field": "features_cutoff_time",
                "original_value": orig_cutoff,
                "injected_value": future_cutoff,
            })

    # 4. DELIVERED_STILL_IN_TRANSIT (~0.4% of delivered shipments)
    # Shipment has DELIVERED tracking event but current_status left as IN_TRANSIT
    rate_status_mismatch = cfg.anomalies.delivered_still_in_transit
    for shp in shipments:
        if shp["current_status"] == "DELIVERED" and rng.random() < rate_status_mismatch:
            orig_status = shp["current_status"]
            shp["current_status"] = "IN_TRANSIT"

            ground_truth.append({
                "record_type": "Shipment",
                "record_id": shp["shipment_id"],
                "issue_type": "DELIVERED_STILL_IN_TRANSIT",
                "description": "Shipment has terminal DELIVERED event but state machine status remains IN_TRANSIT",
                "expected_decision": "FORCE_STATE_RECONCILIATION",
                "injected_field": "current_status",
                "original_value": orig_status,
                "injected_value": "IN_TRANSIT",
            })

    return ground_truth
