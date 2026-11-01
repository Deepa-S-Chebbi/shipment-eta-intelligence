"""Generate weather/facility disruption windows and relational bridge tables.

Weather-event type weights and duration multipliers are read from
``config/default.yaml`` through ``AppConfig.weather_types``. Facility outage
multipliers remain severity-based because the configuration currently defines
weather-specific ranges only.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from eta_data.config import AppConfig
from eta_data.ids import (
    build_weather_event_id,
    build_weather_facility_bridge_id,
    build_weather_leg_bridge_id,
)
from eta_data.rng import RNGManager

FACILITY_OUTAGE_TYPES = [
    "MAINTENANCE",
    "POWER_OUTAGE",
    "LABOR_SHORTAGE",
    "EQUIPMENT_FAILURE",
]
FACILITY_OUTAGE_PROBS = [0.40, 0.25, 0.20, 0.15]

# Retained for facility outages. Weather events use the per-type settings in YAML.
SPEED_MULTIPLIERS_BY_SEVERITY = {
    1: (1.05, 1.15),
    2: (1.15, 1.30),
    3: (1.30, 1.50),
    4: (1.50, 1.75),
    5: (1.75, 2.10),
}


def _get_weather_configuration(
    cfg: AppConfig,
) -> Tuple[List[str], List[float], Dict[str, Dict[str, Any]]]:
    """Validate and normalize weather settings loaded from the YAML config."""
    weather_config = cfg.weather_types
    if not weather_config:
        raise ValueError(
            "No weather_types configured. Add weather types with weight, "
            "min_speed_mult, and max_speed_mult to config/default.yaml."
        )

    weather_types = list(weather_config.keys())
    weights: List[float] = []

    for weather_type in weather_types:
        settings = weather_config[weather_type]
        required = ("weight", "min_speed_mult", "max_speed_mult")
        missing = [key for key in required if key not in settings]
        if missing:
            raise ValueError(
                f"Weather type {weather_type!r} is missing settings: {', '.join(missing)}"
            )

        weight = float(settings["weight"])
        min_multiplier = float(settings["min_speed_mult"])
        max_multiplier = float(settings["max_speed_mult"])

        if weight < 0:
            raise ValueError(f"Weather type {weather_type!r} has a negative weight.")
        if min_multiplier <= 0 or max_multiplier < min_multiplier:
            raise ValueError(
                f"Invalid multiplier range for weather type {weather_type!r}: "
                f"{min_multiplier} to {max_multiplier}."
            )
        weights.append(weight)

    weight_total = sum(weights)
    if weight_total <= 0:
        raise ValueError("Weather type weights must add up to a positive value.")

    # NumPy's choice() expects probabilities to sum to 1.
    probabilities = [weight / weight_total for weight in weights]
    return weather_types, probabilities, weather_config


def generate_disruption_windows(
    cfg: AppConfig,
    facilities: List[Dict[str, Any]],
    rng_manager: RNGManager,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Generate the configured disruption windows and facility bridge rows."""
    if not facilities:
        raise ValueError("Cannot generate disruption windows without facilities.")

    rng_wx = rng_manager.get_stream("disruptions_weather")
    rng_fac = rng_manager.get_stream("disruptions_facility")

    weather_types, weather_probs, weather_config = _get_weather_configuration(cfg)

    start_dt = datetime.fromisoformat(cfg.simulation.start_date.rstrip("Z"))
    duration_days = int(cfg.simulation.duration_days)
    sim_seconds = duration_days * 24 * 3600
    if duration_days <= 0:
        raise ValueError("simulation.duration_days must be greater than zero.")

    target_total = int(cfg.targets.num_disruption_windows)
    weather_target = int(cfg.targets.disruption_split.weather)
    facility_target = int(cfg.targets.disruption_split.facility)

    # Preserve the configured total if the split is inconsistent.
    if weather_target + facility_target != target_total:
        weather_target = int(round(target_total * 0.65))
        facility_target = target_total - weather_target

    facilities_by_region: Dict[str, List[Dict[str, Any]]] = {}
    for facility in facilities:
        facilities_by_region.setdefault(facility["region"], []).append(facility)

    regions = ["North", "South", "East", "West"]
    disruptions: List[Dict[str, Any]] = []
    facility_bridges: List[Dict[str, Any]] = []

    wx_seq = 1
    wef_seq = 1

    # 1. Weather disruption windows.
    for _ in range(weather_target):
        wx_id = build_weather_event_id(wx_seq)
        weather_type = str(rng_wx.choice(weather_types, p=weather_probs))
        severity = int(rng_wx.integers(1, 6))
        region = str(rng_wx.choice(regions))

        # Weather-event duration: 4 to 48 hours.
        duration_hours = float(rng_wx.uniform(4.0, 48.0))
        latest_offset = max(1.0, sim_seconds - duration_hours * 3600)
        offset_seconds = float(rng_wx.uniform(0.0, latest_offset))
        event_start = start_dt + timedelta(seconds=offset_seconds)
        event_end = event_start + timedelta(hours=duration_hours)

        weather_settings = weather_config[weather_type]
        multiplier_low = float(weather_settings["min_speed_mult"])
        multiplier_high = float(weather_settings["max_speed_mult"])
        speed_multiplier = float(
            rng_wx.uniform(multiplier_low, multiplier_high)
        )

        disruptions.append(
            {
                "weather_event_id": wx_id,
                "window_type": "WEATHER",
                "type": weather_type,
                "severity": severity,
                "start_time": event_start.isoformat() + "Z",
                "end_time": event_end.isoformat() + "Z",
                "region": region,
                "speed_multiplier": round(speed_multiplier, 3),
            }
        )

        # Attach the weather event to 20%-50% of facilities in its region.
        candidate_facilities = facilities_by_region.get(region, facilities)
        impact_fraction = float(rng_wx.uniform(0.20, 0.50))
        impacted_count = max(
            1, int(round(len(candidate_facilities) * impact_fraction))
        )
        impacted_count = min(impacted_count, len(candidate_facilities))
        impacted_facilities = rng_wx.choice(
            candidate_facilities, size=impacted_count, replace=False
        )

        for facility in impacted_facilities:
            facility_bridges.append(
                {
                    "bridge_id": build_weather_facility_bridge_id(wef_seq),
                    "weather_event_id": wx_id,
                    "facility_id": facility["facility_id"],
                    "impact_start": event_start.isoformat() + "Z",
                    "impact_end": event_end.isoformat() + "Z",
                }
            )
            wef_seq += 1

        wx_seq += 1

    # 2. Facility outage/disruption windows.
    for _ in range(facility_target):
        wx_id = build_weather_event_id(wx_seq)
        facility_type = str(
            rng_fac.choice(FACILITY_OUTAGE_TYPES, p=FACILITY_OUTAGE_PROBS)
        )
        severity = int(rng_fac.integers(1, 6))

        # Facility outage duration: 2 to 24 hours.
        duration_hours = float(rng_fac.uniform(2.0, 24.0))
        latest_offset = max(1.0, sim_seconds - duration_hours * 3600)
        offset_seconds = float(rng_fac.uniform(0.0, latest_offset))
        event_start = start_dt + timedelta(seconds=offset_seconds)
        event_end = event_start + timedelta(hours=duration_hours)

        facility = rng_fac.choice(facilities)
        region = facility["region"]

        multiplier_low, multiplier_high = SPEED_MULTIPLIERS_BY_SEVERITY[severity]
        speed_multiplier = float(
            rng_fac.uniform(multiplier_low, multiplier_high)
        )

        disruptions.append(
            {
                "weather_event_id": wx_id,
                "window_type": "FACILITY",
                "type": facility_type,
                "severity": severity,
                "start_time": event_start.isoformat() + "Z",
                "end_time": event_end.isoformat() + "Z",
                "region": region,
                "speed_multiplier": round(speed_multiplier, 3),
            }
        )

        facility_bridges.append(
            {
                "bridge_id": build_weather_facility_bridge_id(wef_seq),
                "weather_event_id": wx_id,
                "facility_id": facility["facility_id"],
                "impact_start": event_start.isoformat() + "Z",
                "impact_end": event_end.isoformat() + "Z",
            }
        )
        wef_seq += 1
        wx_seq += 1

    return disruptions, facility_bridges


def build_weather_leg_bridges(
    disruptions: List[Dict[str, Any]],
    legs: List[Dict[str, Any]],
    facilities: List[Dict[str, Any]],
    facility_bridges: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Link legs to weather events affecting their destination facility."""

    weather_events = {
        d["weather_event_id"]: d
        for d in disruptions
        if d["window_type"] == "WEATHER"
    }

    facility_impacts = {}
    for bridge in facility_bridges:
        event_id = bridge["weather_event_id"]
        facility_impacts.setdefault(event_id, []).append(bridge)

    bridges = []
    bridge_seq = 1

    for leg in legs:
        depart_value = leg.get("actual_depart_at")
        arrive_value = leg.get("actual_arrive_at")

        if not depart_value or not arrive_value:
            continue

        leg_depart = datetime.fromisoformat(depart_value.rstrip("Z"))
        leg_arrive = datetime.fromisoformat(arrive_value.rstrip("Z"))
        destination_id = leg["to_facility_id"]

        for event_id, disruption in weather_events.items():
            for facility_bridge in facility_impacts.get(event_id, []):
                if facility_bridge["facility_id"] != destination_id:
                    continue

                impact_start = datetime.fromisoformat(
                    facility_bridge["impact_start"].rstrip("Z")
                )
                impact_end = datetime.fromisoformat(
                    facility_bridge["impact_end"].rstrip("Z")
                )

                overlap_start = max(
                    leg_depart,
                    datetime.fromisoformat(
                        disruption["start_time"].rstrip("Z")
                    ),
                    impact_start,
                )
                overlap_end = min(
                    leg_arrive,
                    datetime.fromisoformat(
                        disruption["end_time"].rstrip("Z")
                    ),
                    impact_end,
                )

                if overlap_start >= overlap_end:
                    continue

                bridges.append(
                    {
                        "bridge_id": build_weather_leg_bridge_id(bridge_seq),
                        "weather_event_id": event_id,
                        "leg_id": leg["leg_id"],
                        "impact_multiplier": disruption["speed_multiplier"],
                    }
                )
                bridge_seq += 1

    return bridges
