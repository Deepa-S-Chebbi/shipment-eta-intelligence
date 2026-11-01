"""
Facility queue snapshot generator modeling periodic congestion, throughput, and wait times.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple
from eta_data.config import AppConfig
from eta_data.ids import build_facility_queue_id
from eta_data.rng import RNGManager


def generate_facility_queues(
    cfg: AppConfig,
    facilities: List[Dict[str, Any]],
    disruptions: List[Dict[str, Any]],
    rng_manager: RNGManager,
    snapshot_interval_hours: int = 12,
) -> List[Dict[str, Any]]:
    """
    Generates periodic facility queue snapshots capturing diurnal cycles,
    weekend slowdowns, and disruption-induced congestion.
    """
    rng = rng_manager.get_stream("facility_queues")
    start_dt = datetime.fromisoformat(cfg.simulation.start_date.rstrip("Z"))
    total_hours = cfg.simulation.duration_days * 24

    # Build facility disruption lookup: facility_id -> list of (start, end, severity)
    disrupt_lookup: Dict[str, List[Tuple[datetime, datetime, int]]] = {}
    for d in disruptions:
        if d["window_type"] == "FACILITY":
            d_start = datetime.fromisoformat(d["start_time"].rstrip("Z"))
            d_end = datetime.fromisoformat(d["end_time"].rstrip("Z"))
            # For each facility matching region or targeted
            for f in facilities:
                if f["region"] == d["region"]:
                    disrupt_lookup.setdefault(f["facility_id"], []).append(
                        (d_start, d_end, d["severity"])
                    )

    queue_records: List[Dict[str, Any]] = []
    fq_seq = 1

    # Time steps across the simulation
    num_steps = total_hours // snapshot_interval_hours

    for step in range(num_steps):
        snap_dt = start_dt + timedelta(hours=step * snapshot_interval_hours)
        hour = snap_dt.hour
        dow = snap_dt.weekday()

        # Diurnal rush factor: peaks at 09:00-11:00 and 16:00-18:00
        diurnal_factor = 1.0 + 0.35 * math.sin((hour - 4) * math.pi / 12)
        # Weekend factor
        weekend_factor = 0.60 if dow >= 5 else 1.0

        for fac in facilities:
            fac_id = fac["facility_id"]
            base_capacity = float(fac["capacity_per_hour"])

            # Check if active disruption applies
            severity_boost = 1.0
            if fac_id in disrupt_lookup:
                for d_start, d_end, sev in disrupt_lookup[fac_id]:
                    if d_start <= snap_dt <= d_end:
                        severity_boost += 0.25 * sev

            # Target queue length modeled as Poisson / Negative Binomial
            mean_queue = (base_capacity * 0.40) * diurnal_factor * weekend_factor * severity_boost
            queue_len = int(max(0, rng.poisson(mean_queue)))

            # Throughput
            throughput = max(10.0, base_capacity * float(rng.uniform(0.85, 1.15)) / severity_boost)
            # Wait time = queue_length / throughput + baseline handling
            wait_hours = round(queue_len / throughput + float(rng.uniform(0.1, 0.4)), 2)

            q_row = {
                "queue_id": build_facility_queue_id(fq_seq),
                "facility_id": fac_id,
                "snapshot_time": snap_dt.isoformat() + "Z",
                "queue_length": queue_len,
                "avg_wait_hours": wait_hours,
                "throughput_per_hour": round(throughput, 1),
            }
            queue_records.append(q_row)
            fq_seq += 1

    return queue_records
