"""
Disruption window generator (Weather and Facility events) and relational bridge tables.
Hits exactly the configured number of disruption windows (e.g. 1,000 at full scale)
with a documented split between WEATHER and FACILITY outage windows.
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

WEATHER_TYPES = ["RAIN", "STORM", "FOG", "HEAT", "SNOW"]
WEATHER_PROBS = [0.35, 0.25, 0.15, 0.10, 0.15]

FACILITY_OUTAGE_TYPES = ["MAINTENANCE", "POWER_OUTAGE", "LABOR_SHORTAGE", "EQUIPMENT_FAILURE"]
FACILITY_OUTAGE_PROBS = [0.40, 0.25, 0.20, 0.15]

SPEED_MULTIPLIERS_BY_SEVERITY = {
    1: (1.05, 1.15),
    2: (1.15, 1.30),
    3: (1.30, 1.50),
    4: (1.50, 1.75),
    5: (1.75, 2.10),
}


def generate_disruption_windows(
    cfg: AppConfig,
    facilities: List[Dict[str, Any]],
    rng_manager: RNGManager,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Generates exactly cfg.targets.num_disruption_windows disruption events
    and populates the WeatherEventFacility N:M bridge table.
    """
    rng_wx = rng_manager.get_stream("disruptions_weather")
    rng_fac = rng_manager.get_stream("disruptions_facility")

    start_dt = datetime.fromisoformat(cfg.simulation.start_date.rstrip("Z"))
    duration_days = cfg.simulation.duration_days
    sim_seconds = duration_days * 24 * 3600

    target_total = cfg.targets.num_disruption_windows
    weather_target = cfg.targets.disruption_split.weather
    facility_target = cfg.targets.disruption_split.facility

    # Sanity check: sum must equal total
    if weather_target + facility_target != target_total:
        weather_target = int(round(target_total * 0.65))
        facility_target = target_total - weather_target

    facilities_by_region: Dict[str, List[Dict[str, Any]]] = {}
    for f in facilities:
        facilities_by_region.setdefault(f["region"], []).append(f)

    regions = ["North", "South", "East", "West"]
    disruptions: List[Dict[str, Any]] = []
    facility_bridges: List[Dict[str, Any]] = []

    wx_seq = 1
    wef_seq = 1

    # 1. Weather disruption windows
    for _ in range(weather_target):
        wx_id = build_weather_event_id(wx_seq)
        w_type = str(rng_wx.choice(WEATHER_TYPES, p=WEATHER_PROBS))
        severity = int(rng_wx.integers(1, 6))
        region = str(rng_wx.choice(regions))

        # Event duration between 4 and 48 hours
        duration_hours = float(rng_wx.uniform(4.0, 48.0))
        offset_seconds = float(rng_wx.uniform(0.0, max(1.0, sim_seconds - duration_hours * 3600)))
        event_start = start_dt + timedelta(seconds=offset_seconds)
        event_end = event_start + timedelta(hours=duration_hours)

        mult_low, mult_high = SPEED_MULTIPLIERS_BY_SEVERITY[severity]
        speed_mult = float(rng_wx.uniform(mult_low, mult_high))

        event_row = {
            "weather_event_id": wx_id,
            "window_type": "WEATHER",
            "type": w_type,
            "severity": severity,
            "start_time": event_start.isoformat() + "Z",
            "end_time": event_end.isoformat() + "Z",
            "region": region,
            "speed_multiplier": round(speed_mult, 3),
        }
        disruptions.append(event_row)

        # Bridge: attach to 20% to 50% of facilities in the affected region
        candidate_facs = facilities_by_region.get(region, facilities)
        n_impacted = max(1, int(round(len(candidate_facs) * rng_wx.uniform(0.20, 0.50))))
        impacted_facs = list(rng_wx.choice(candidate_facs, size=min(n_impacted, len(candidate_facs)), replace=False))

        for fac in impacted_facs:
            bridge_row = {
                "bridge_id": build_weather_facility_bridge_id(wef_seq),
                "weather_event_id": wx_id,
                "facility_id": fac["facility_id"],
                "impact_start": event_start.isoformat() + "Z",
                "impact_end": event_end.isoformat() + "Z",
            }
            facility_bridges.append(bridge_row)
            wef_seq += 1

        wx_seq += 1

    # 2. Facility outage / disruption windows
    for _ in range(facility_target):
        wx_id = build_weather_event_id(wx_seq)
        f_type = str(rng_fac.choice(FACILITY_OUTAGE_TYPES, p=FACILITY_OUTAGE_PROBS))
        severity = int(rng_fac.integers(1, 6))

        # Outage duration between 2 and 24 hours
        duration_hours = float(rng_fac.uniform(2.0, 24.0))
        offset_seconds = float(rng_fac.uniform(0.0, max(1.0, sim_seconds - duration_hours * 3600)))
        event_start = start_dt + timedelta(seconds=offset_seconds)
        event_end = event_start + timedelta(hours=duration_hours)

        # Pick specific facility
        fac = rng_fac.choice(facilities)
        region = fac["region"]

        mult_low, mult_high = SPEED_MULTIPLIERS_BY_SEVERITY[severity]
        # Facility outages introduce terminal handling slowdown
        speed_mult = float(rng_fac.uniform(mult_low, mult_high))

        event_row = {
            "weather_event_id": wx_id,
            "window_type": "FACILITY",
            "type": f_type,
            "severity": severity,
            "start_time": event_start.isoformat() + "Z",
            "end_time": event_end.isoformat() + "Z",
            "region": region,
            "speed_multiplier": round(speed_mult, 3),
        }
        disruptions.append(event_row)

        bridge_row = {
            "bridge_id": build_weather_facility_bridge_id(wef_seq),
            "weather_event_id": wx_id,
            "facility_id": fac["facility_id"],
            "impact_start": event_start.isoformat() + "Z",
            "impact_end": event_end.isoformat() + "Z",
        }
        facility_bridges.append(bridge_row)
        wef_seq += 1
        wx_seq += 1

    return disruptions, facility_bridges


def build_weather_leg_bridges(
    disruptions: List[Dict[str, Any]],
    legs: List[Dict[str, Any]],
    facilities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Builds the WeatherEventLeg N:M bridge table linking transit legs to overlapping weather events.
    """
    fac_map = {f["facility_id"]: f for f in facilities}
    wel_bridges: List[Dict[str, Any]] = []
    wel_seq = 1

    # Pre-parse disruption intervals
    parsed_disruptions = []
    for d in disruptions:
        if d["window_type"] == "WEATHER":
            t_start = datetime.fromisoformat(d["start_time"].rstrip("Z"))
            t_end = datetime.fromisoformat(d["end_time"].rstrip("Z"))
            parsed_disruptions.append((d, t_start, t_end))

    for leg in legs:
        if not leg.get("actual_depart_at") or not leg.get("actual_arrive_at"):
            continue

        l_dep = datetime.fromisoformat(leg["actual_depart_at"].rstrip("Z"))
        l_arr = datetime.fromisoformat(leg["actual_arrive_at"].rstrip("Z"))

        from_fac = fac_map.get(leg["from_facility_id"])
        to_fac = fac_map.get(leg["to_facility_id"])
        leg_regions = {from_fac["region"] if from_fac else "North", to_fac["region"] if to_fac else "North"}

        for d, d_start, d_end in parsed_disruptions:
            if d["region"] in leg_regions:
                # Check interval overlap
                overlap_start = max(l_dep, d_start)
                overlap_end = min(l_arr, d_end)
                if overlap_start < overlap_end:
                    wel_row = {
                        "bridge_id": build_weather_leg_bridge_id(wel_seq),
                        "weather_event_id": d["weather_event_id"],
                        "leg_id": leg["leg_id"],
                        "impact_multiplier": d["speed_multiplier"],
                    }
                    wel_bridges.append(wel_row)
                    wel_seq += 1

    return wel_bridges
