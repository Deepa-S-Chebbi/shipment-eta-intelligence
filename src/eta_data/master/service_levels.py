"""Deterministic ServiceLevel master data generator."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List
from eta_data.config import AppConfig


def generate_service_levels(cfg: AppConfig) -> List[Dict[str, Any]]:
    """Generates standard ServiceLevel master data with SLA targets and thresholds."""
    start_dt = datetime.fromisoformat(cfg.simulation.start_date.rstrip("Z"))
    end_dt = start_dt + timedelta(days=cfg.simulation.duration_days + 30)

    service_levels_cfg = cfg.master_data.get("service_levels", [])
    result: List[Dict[str, Any]] = []

    for sl in service_levels_cfg:
        item = {
            "service_level_id": sl["id"],
            "name": sl["name"],
            "target_hours": int(sl["target_hours"]),
            "grace_hours": float(sl["grace_hours"]),
            "severely_delayed_hours": float(sl["severely_delayed_hours"]),
            "effective_from": start_dt.isoformat() + "Z",
            "effective_to": end_dt.isoformat() + "Z",
        }
        result.append(item)

    return result
