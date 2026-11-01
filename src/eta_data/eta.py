"""
Leakage-safe point-in-time ETA snapshot prediction engine.
Filters available signals strictly using ingestion_time <= prediction_time,
preventing any future telemetry leakage into feature sets.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Set, Tuple
from eta_data.ids import build_eta_id, format_compact_utc


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-15.0, min(15.0, x))))


def generate_eta_snapshots_for_shipment(
    shp: Dict[str, Any],
    legs: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    disruptions: List[Dict[str, Any]],
    facilities: Dict[str, Dict[str, Any]],
    service_levels: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Generates multiple point-in-time ETA snapshots across a shipment's lifecycle.
    Guarantees that at prediction_time T, only events with ingestion_time <= T are visible.
    """
    shp_id = shp["shipment_id"]
    t_create = datetime.fromisoformat(shp["created_at"].rstrip("Z"))
    t_promised = datetime.fromisoformat(shp["promised_delivery_at"].rstrip("Z"))
    sl = service_levels[shp["service_level_id"]]
    grace_hours = float(sl["grace_hours"])

    # Determine delivery time if completed
    t_delivered = None
    for e in events:
        if e["event_type"] == "DELIVERED":
            t_delivered = datetime.fromisoformat(e["event_time"].rstrip("Z"))
            break

    # Candidate prediction times
    prediction_times: List[datetime] = [t_create]

    # Fixed horizon checkpoints before promised delivery: T-24h, T-12h, T-6h
    for h in [24, 12, 6]:
        t_checkpoint = t_promised - timedelta(hours=h)
        if t_checkpoint > t_create and (t_delivered is None or t_checkpoint < t_delivered):
            prediction_times.append(t_checkpoint)

    # Checkpoint after first visible scan
    for e in events:
        if e["event_type"] in ("PICKED_UP", "ARRIVED"):
            t_ingest = datetime.fromisoformat(e["ingestion_time"].rstrip("Z"))
            if t_delivered is None or t_ingest < t_delivered:
                prediction_times.append(t_ingest)

    # Deduplicate and sort chronologically by compact minute representation
    deduped_prediction_times: List[datetime] = []
    seen_compact: Set[str] = set()
    for dt in sorted(prediction_times):
        compact = format_compact_utc(dt)
        if compact not in seen_compact:
            seen_compact.add(compact)
            deduped_prediction_times.append(dt)
    prediction_times = deduped_prediction_times

    # Planned delivery from final scheduled leg arrival
    final_leg = legs[-1] if legs else None
    if final_leg and final_leg.get("planned_arrive_at"):
        planned_arrival_dt = datetime.fromisoformat(final_leg["planned_arrive_at"].rstrip("Z"))
    else:
        planned_arrival_dt = t_promised

    snapshots: List[Dict[str, Any]] = []

    for pred_dt in prediction_times:
        pred_time_str = pred_dt.isoformat() + "Z"

        # STRICT LEAKAGE FILTER: Only events with ingestion_time <= pred_dt
        visible_events = [
            e for e in events
            if datetime.fromisoformat(e["ingestion_time"].rstrip("Z")) <= pred_dt
        ]
        n_events = len(visible_events)

        # Baseline 1: PLAN_BASED (Static route schedule)
        pred_plan_delivery = planned_arrival_dt
        plan_delay_hours = (planned_arrival_dt - t_promised).total_seconds() / 3600.0
        plan_delay_prob = _sigmoid((plan_delay_hours - grace_hours) * 0.7)

        snapshots.append({
            "eta_id": build_eta_id(shp_id, pred_time_str) + "-PLAN",
            "shipment_id": shp_id,
            "prediction_time": pred_time_str,
            "predicted_delivery_at": pred_plan_delivery.isoformat() + "Z",
            "method": "PLAN_BASED",
            "features_cutoff_time": pred_time_str,
            "n_events_used": n_events,
            "predicted_delay_probability": round(plan_delay_prob, 3),
        })

        # Baseline 2: PROGRESS_BASED (Observes delays from ingested scans)
        current_delay_hours = 0.0
        if visible_events:
            last_ev = max(visible_events, key=lambda x: datetime.fromisoformat(x["event_time"].rstrip("Z")))
            t_ev = datetime.fromisoformat(last_ev["event_time"].rstrip("Z"))
            # If last event is delayed compared to planned departure/arrival
            if last_ev["leg_id"]:
                leg_match = next((l for l in legs if l["leg_id"] == last_ev["leg_id"]), None)
                if leg_match:
                    p_dep = datetime.fromisoformat(leg_match["planned_depart_at"].rstrip("Z"))
                    if t_ev > p_dep:
                        current_delay_hours = (t_ev - p_dep).total_seconds() / 3600.0

        pred_prog_delivery = planned_arrival_dt + timedelta(hours=current_delay_hours)
        prog_delay_hours = (pred_prog_delivery - t_promised).total_seconds() / 3600.0
        prog_delay_prob = _sigmoid((prog_delay_hours - grace_hours) * 0.8)

        snapshots.append({
            "eta_id": build_eta_id(shp_id, pred_time_str) + "-PROG",
            "shipment_id": shp_id,
            "prediction_time": pred_time_str,
            "predicted_delivery_at": pred_prog_delivery.isoformat() + "Z",
            "method": "PROGRESS_BASED",
            "features_cutoff_time": pred_time_str,
            "n_events_used": n_events,
            "predicted_delay_probability": round(prog_delay_prob, 3),
        })

        # Baseline 3: CONTEXT_AWARE (Progress + Active Weather / Facility Queues)
        # Evaluates disruptions active AT OR BEFORE pred_dt
        context_extra_hours = current_delay_hours
        for d in disruptions:
            d_start = datetime.fromisoformat(d["start_time"].rstrip("Z"))
            d_end = datetime.fromisoformat(d["end_time"].rstrip("Z"))
            # Disruption must be active around prediction window
            if d_start <= pred_dt <= d_end:
                sev = int(d["severity"])
                context_extra_hours += sev * 0.6

        pred_ctx_delivery = planned_arrival_dt + timedelta(hours=context_extra_hours)
        ctx_delay_hours = (pred_ctx_delivery - t_promised).total_seconds() / 3600.0
        ctx_delay_prob = _sigmoid((ctx_delay_hours - grace_hours) * 0.9)

        snapshots.append({
            "eta_id": build_eta_id(shp_id, pred_time_str),
            "shipment_id": shp_id,
            "prediction_time": pred_time_str,
            "predicted_delivery_at": pred_ctx_delivery.isoformat() + "Z",
            "method": "CONTEXT_AWARE",
            "features_cutoff_time": pred_time_str,
            "n_events_used": n_events,
            "predicted_delay_probability": round(ctx_delay_prob, 3),
        })

    return snapshots


def generate_all_eta_snapshots(
    shipments: List[Dict[str, Any]],
    legs: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
    disruptions: List[Dict[str, Any]],
    facilities: List[Dict[str, Any]],
    service_levels: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Generates all leakage-safe ETA snapshots for the dataset."""
    fac_map = {f["facility_id"]: f for f in facilities}
    sl_map = {sl["service_level_id"]: sl for sl in service_levels}

    legs_by_shp: Dict[str, List[Dict[str, Any]]] = {}
    for l in legs:
        legs_by_shp.setdefault(l["shipment_id"], []).append(l)

    events_by_shp: Dict[str, List[Dict[str, Any]]] = {}
    for e in events:
        events_by_shp.setdefault(e["shipment_id"], []).append(e)

    all_snapshots: List[Dict[str, Any]] = []

    for shp in shipments:
        s_id = shp["shipment_id"]
        shp_legs = legs_by_shp.get(s_id, [])
        shp_events = events_by_shp.get(s_id, [])

        snaps = generate_eta_snapshots_for_shipment(
            shp=shp,
            legs=shp_legs,
            events=shp_events,
            disruptions=disruptions,
            facilities=fac_map,
            service_levels=sl_map,
        )
        all_snapshots.extend(snaps)

    return all_snapshots
