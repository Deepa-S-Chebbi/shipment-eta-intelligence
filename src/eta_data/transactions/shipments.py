"""Deterministic Shipment generator with realistic pickup seasonality."""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, List
from eta_data.config import AppConfig
from eta_data.ids import build_shipment_id
from eta_data.rng import RNGManager


def generate_shipments(
    cfg: AppConfig,
    routes: List[Dict[str, Any]],
    service_levels: List[Dict[str, Any]],
    rng_manager: RNGManager,
) -> List[Dict[str, Any]]:
    """
    Generates core Shipment rows with service level selection, route assignment,
    and business-hour creation seasonality.
    """
    rng = rng_manager.get_stream("shipment_generation")
    start_dt = datetime.fromisoformat(cfg.simulation.start_date.rstrip("Z"))
    duration_days = cfg.simulation.duration_days
    num_shipments = cfg.targets.num_shipments

    sl_by_id = {sl["service_level_id"]: sl for sl in service_levels}

    shipments: List[Dict[str, Any]] = []

    for idx in range(num_shipments):
        shp_id = build_shipment_id(idx + 1)
        supplier_id = f"SUP-{int(rng.integers(1, 51)):03d}"

        # Route assignment
        route = rng.choice(routes)
        planned_hrs = float(route.get("total_planned_hours", 24.0))

        # Select compatible service level based on route planned transit duration
        # Calibrated matching: 1-hop routes (<=25h) to 24H, 2-hop (<=50h) to 48H,
        # 3-hop (<=75h) to 72H, and 4-hop (>75h) to 120H.
        if planned_hrs <= 25.0 and "SL-EXP-24H" in sl_by_id:
            chosen_sl_id = "SL-EXP-24H"
        elif planned_hrs <= 50.0 and "SL-EXP-48H" in sl_by_id:
            chosen_sl_id = "SL-EXP-48H"
        elif planned_hrs <= 75.0 and "SL-STD-72H" in sl_by_id:
            chosen_sl_id = "SL-STD-72H"
        elif "SL-FRT-120H" in sl_by_id:
            chosen_sl_id = "SL-FRT-120H"
        else:
            chosen_sl_id = service_levels[0]["service_level_id"]

        sl = sl_by_id.get(chosen_sl_id, service_levels[0])

        # Realistic creation time: business hours (08:00 - 18:00) with weekday skew (85% Mon-Fri, 15% Sat-Sun)
        day_offset = int(rng.integers(0, max(1, duration_days - 7)))
        dow = (start_dt + timedelta(days=day_offset)).weekday()
        if dow in (5, 6) and rng.random() < 0.75:
            # Re-roll weekend creation to Monday/Tuesday for realistic B2B freight seasonality
            day_offset = min(duration_days - 8, day_offset + (2 if dow == 5 else 1))

        # Hour drawn from beta distribution peaked around 10:00 - 15:00
        hour_frac = rng.beta(2.5, 2.0)
        hour = int(8 + hour_frac * 10)  # 08:00 to 18:00
        minute = int(rng.integers(0, 60))
        second = int(rng.integers(0, 60))

        created_dt = start_dt + timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)
        target_hours = int(sl["target_hours"])
        promised_dt = created_dt + timedelta(hours=target_hours)

        shp_row = {
            "shipment_id": shp_id,
            "supplier_id": supplier_id,
            "origin_facility_id": route["origin_facility_id"],
            "destination_facility_id": route["destination_facility_id"],
            "service_level_id": sl["service_level_id"],
            "route_id": route["route_id"],
            "created_at": created_dt.isoformat() + "Z",
            "promised_delivery_at": promised_dt.isoformat() + "Z",
            "actual_delivery_at": None,  # Derived during simulation
            "current_status": "CREATED",
            "final_delay_label": "ON_TIME",  # Derived during labeling
            "is_rerouted": False,
        }
        shipments.append(shp_row)

    return shipments
