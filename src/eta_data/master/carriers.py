"""Deterministic Carrier master data generator."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List
from eta_data.config import AppConfig
from eta_data.ids import build_carrier_id
from eta_data.rng import RNGManager

CARRIER_NAMES = [
    ("Apex Freight Systems", "ROAD", "TIER_1", 72.0),
    ("SwiftRoad Logistics", "ROAD", "TIER_2", 68.0),
    ("Vanguard Trucking", "ROAD", "TIER_2", 65.0),
    ("Titan Haulage", "ROAD", "TIER_3", 60.0),
    ("Pinnacle Ground", "ROAD", "TIER_1", 75.0),
    ("IronRail Express", "RAIL", "TIER_1", 55.0),
    ("TransContinental Rail", "RAIL", "TIER_2", 48.0),
    ("MetroRail Cargo", "RAIL", "TIER_3", 42.0),
    ("AeroSpeed Air Cargo", "AIR", "TIER_1", 520.0),
    ("SkyFreight Express", "AIR", "TIER_2", 480.0),
    ("Oceanic Freight Lines", "SEA", "TIER_2", 28.0),
    ("Pacific Marine Transit", "SEA", "TIER_3", 24.0),
]


def generate_carriers(cfg: AppConfig, rng_manager: RNGManager) -> List[Dict[str, Any]]:
    """Generates deterministic Carrier master data."""
    start_dt = datetime.fromisoformat(cfg.simulation.start_date.rstrip("Z"))
    end_dt = start_dt + timedelta(days=cfg.simulation.duration_days + 30)

    num_carriers = min(len(CARRIER_NAMES), cfg.targets.num_carriers)
    carriers: List[Dict[str, Any]] = []

    for idx in range(num_carriers):
        name, mode, tier, speed = CARRIER_NAMES[idx]
        carrier = {
            "carrier_id": build_carrier_id(idx + 1),
            "name": name,
            "mode": mode,
            "reliability_tier": tier,
            "base_speed_kmh": float(speed),
            "effective_from": start_dt.isoformat() + "Z",
            "effective_to": end_dt.isoformat() + "Z",
        }
        carriers.append(carrier)

    return carriers
