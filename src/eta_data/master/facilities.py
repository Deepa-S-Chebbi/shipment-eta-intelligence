"""Deterministic Facility master data generator."""

from __future__ import annotations

from typing import Any, Dict, List
import numpy as np
from eta_data.config import AppConfig
from eta_data.ids import build_facility_id
from eta_data.rng import RNGManager

FACILITY_TYPE_SPECS = {
    "HUB": {"base_cap": 400, "dwell_hours": 1.5},
    "DEPOT": {"base_cap": 120, "dwell_hours": 2.5},
    "WAREHOUSE": {"base_cap": 80, "dwell_hours": 4.0},
    "PORT": {"base_cap": 250, "dwell_hours": 8.0},
}


def _get_region_for_coords(x: float, y: float) -> str:
    if y >= 500.0 and x < 500.0:
        return "North"
    elif y < 500.0 and x < 500.0:
        return "South"
    elif y >= 500.0 and x >= 500.0:
        return "East"
    else:
        return "West"


def generate_facilities(cfg: AppConfig, rng_manager: RNGManager) -> List[Dict[str, Any]]:
    """Generates deterministic Facility master data with coordinates, regions, and capacities."""
    rng = rng_manager.get_stream("master_facilities")
    num_facilities = cfg.targets.num_facilities
    grid_size = cfg.simulation.grid_size_km

    facilities: List[Dict[str, Any]] = []

    # Target distribution of types: 20% HUB, 45% DEPOT, 25% WAREHOUSE, 10% PORT
    type_choices = ["HUB", "DEPOT", "WAREHOUSE", "PORT"]
    type_probs = [0.20, 0.45, 0.25, 0.10]

    for idx in range(num_facilities):
        fac_id = build_facility_id(idx + 1)
        # Ensure first few facilities guarantee at least 2 HUBs and 1 PORT
        if idx < 2:
            fac_type = "HUB"
        elif idx == 2:
            fac_type = "PORT"
        else:
            fac_type = str(rng.choice(type_choices, p=type_probs))

        # Position assignment
        if fac_type == "PORT":
            # Ports sit along boundaries (coastal boundaries)
            edge = rng.choice(["left", "right", "bottom", "top"])
            if edge == "left":
                x = float(rng.uniform(10.0, 60.0))
                y = float(rng.uniform(100.0, 900.0))
            elif edge == "right":
                x = float(rng.uniform(940.0, 990.0))
                y = float(rng.uniform(100.0, 900.0))
            elif edge == "bottom":
                x = float(rng.uniform(100.0, 900.0))
                y = float(rng.uniform(10.0, 60.0))
            else:
                x = float(rng.uniform(100.0, 900.0))
                y = float(rng.uniform(940.0, 990.0))
        elif fac_type == "HUB":
            # Hubs cluster near major quadrant centroids
            quadrant_x = rng.choice([250.0, 750.0])
            quadrant_y = rng.choice([250.0, 750.0])
            x = float(np.clip(rng.normal(quadrant_x, 60.0), 50.0, grid_size - 50.0))
            y = float(np.clip(rng.normal(quadrant_y, 60.0), 50.0, grid_size - 50.0))
        else:
            # Depots and warehouses uniformly spread across territory
            x = float(rng.uniform(50.0, grid_size - 50.0))
            y = float(rng.uniform(50.0, grid_size - 50.0))

        region = _get_region_for_coords(x, y)
        base_cap = FACILITY_TYPE_SPECS[fac_type]["base_cap"]
        cap_variation = float(rng.uniform(0.85, 1.15))
        capacity = int(round(base_cap * cap_variation))

        name = f"{region} {fac_type.capitalize()} #{idx + 1:03d}"

        fac = {
            "facility_id": fac_id,
            "name": name,
            "type": fac_type,
            "region": region,
            "latitude": round(y, 2),
            "longitude": round(x, 2),
            "capacity_per_hour": capacity,
            "timezone": "UTC",
        }
        facilities.append(fac)

    return facilities
