"""
Centralized deterministic ID builders and validators.
Enforces immutable, zero-padded, strict format strings across all tables.
No string-hacking permitted anywhere else in the codebase.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Dict


# Exact Regex Patterns for ID Validation
ID_PATTERNS: Dict[str, re.Pattern[str]] = {
    "shipment": re.compile(r"^SHP-\d{4}-\d{6}$"),
    "leg": re.compile(r"^LEG-SHP-\d{4}-\d{6}-\d{2}$"),
    "event": re.compile(r"^EVT-SHP-\d{4}-\d{6}-\d{6}$"),
    "eta": re.compile(r"^ETA-SHP-\d{4}-\d{6}-\d{8}T\d{4}$"),
    "delay": re.compile(r"^DLY-\d{4}-\d{6}$"),
    "carrier": re.compile(r"^CAR-\d{3}$"),
    "facility": re.compile(r"^FAC-\d{3}$"),
    "service_level": re.compile(r"^SL-[A-Z]+-\d+H$"),
    "route": re.compile(r"^RTE-\d{4}$"),
    "route_leg_template": re.compile(r"^RLT-\d{6}$"),
    "weather_event": re.compile(r"^WX-\d{4}$"),
    "facility_queue": re.compile(r"^FQ-\d{6}$"),
    "weather_event_facility": re.compile(r"^WEF-\d{6}$"),
    "weather_event_leg": re.compile(r"^WEL-\d{6}$"),
    "shipment_delay_reason": re.compile(r"^SDR-\d{8}$"),
    "shipment_status_history": re.compile(r"^SSH-\d{8}$"),
    "route_change": re.compile(r"^RTC-\d{6}$"),
    "calendar": re.compile(r"^CAL-\d{6}$"),
}


def build_shipment_id(seq: int, year: int = 2026) -> str:
    """e.g. SHP-2026-000001"""
    if seq < 1:
        raise ValueError(f"Sequence number must be >= 1, got {seq}")
    return f"SHP-{year}-{seq:06d}"


def build_leg_id(shipment_id: str, leg_seq: int) -> str:
    """e.g. LEG-SHP-2026-000001-01"""
    if not ID_PATTERNS["shipment"].match(shipment_id):
        raise ValueError(f"Invalid shipment_id format: {shipment_id}")
    if leg_seq < 1 or leg_seq > 99:
        raise ValueError(f"Leg sequence must be between 1 and 99, got {leg_seq}")
    return f"LEG-{shipment_id}-{leg_seq:02d}"


def build_event_id(shipment_id: str, event_seq: int) -> str:
    """e.g. EVT-SHP-2026-000001-000001"""
    if not ID_PATTERNS["shipment"].match(shipment_id):
        raise ValueError(f"Invalid shipment_id format: {shipment_id}")
    if event_seq < 1:
        raise ValueError(f"Event sequence must be >= 1, got {event_seq}")
    return f"EVT-{shipment_id}-{event_seq:06d}"


def format_compact_utc(dt_or_str: datetime | str) -> str:
    """Formats datetime or ISO string to compact UTC format: YYYYMMDDTHHMM"""
    if isinstance(dt_or_str, str):
        # Parse ISO string like '2026-03-11T10:00:00Z'
        clean = dt_or_str.rstrip("Z")
        dt = datetime.fromisoformat(clean)
    else:
        dt = dt_or_str
    return dt.strftime("%Y%m%dT%H%M")


def build_eta_id(shipment_id: str, timestamp_str: str) -> str:
    """e.g. ETA-SHP-2026-000001-20260311T1000"""
    if not ID_PATTERNS["shipment"].match(shipment_id):
        raise ValueError(f"Invalid shipment_id format: {shipment_id}")
    compact_ts = format_compact_utc(timestamp_str)
    return f"ETA-{shipment_id}-{compact_ts}"


def build_delay_id(seq: int, year: int = 2026) -> str:
    """e.g. DLY-2026-000001"""
    if seq < 1:
        raise ValueError(f"Sequence number must be >= 1, got {seq}")
    return f"DLY-{year}-{seq:06d}"


def build_carrier_id(seq: int) -> str:
    """e.g. CAR-001"""
    if seq < 1 or seq > 999:
        raise ValueError(f"Carrier sequence must be 1..999, got {seq}")
    return f"CAR-{seq:03d}"


def build_facility_id(seq: int) -> str:
    """e.g. FAC-001"""
    if seq < 1 or seq > 999:
        raise ValueError(f"Facility sequence must be 1..999, got {seq}")
    return f"FAC-{seq:03d}"


def build_service_level_id(tier_code: str, hours: int) -> str:
    """e.g. SL-EXP-24H"""
    return f"SL-{tier_code.upper()}-{hours}H"


def build_route_id(seq: int) -> str:
    """e.g. RTE-0001"""
    if seq < 1 or seq > 9999:
        raise ValueError(f"Route sequence must be 1..9999, got {seq}")
    return f"RTE-{seq:04d}"


def build_route_leg_template_id(seq: int) -> str:
    """e.g. RLT-000001"""
    if seq < 1:
        raise ValueError(f"Template sequence must be >= 1, got {seq}")
    return f"RLT-{seq:06d}"


def build_weather_event_id(seq: int) -> str:
    """e.g. WX-0001"""
    if seq < 1 or seq > 9999:
        raise ValueError(f"Weather event sequence must be 1..9999, got {seq}")
    return f"WX-{seq:04d}"


def build_facility_queue_id(seq: int) -> str:
    """e.g. FQ-000001"""
    if seq < 1:
        raise ValueError(f"Queue sequence must be >= 1, got {seq}")
    return f"FQ-{seq:06d}"


def build_weather_facility_bridge_id(seq: int) -> str:
    """e.g. WEF-000001"""
    return f"WEF-{seq:06d}"


def build_weather_leg_bridge_id(seq: int) -> str:
    """e.g. WEL-000001"""
    return f"WEL-{seq:06d}"


def build_delay_attribution_id(seq: int) -> str:
    """e.g. SDR-00000001"""
    return f"SDR-{seq:08d}"


def build_status_history_id(seq: int) -> str:
    """e.g. SSH-00000001"""
    return f"SSH-{seq:08d}"


def build_route_change_id(seq: int) -> str:
    """e.g. RTC-000001"""
    return f"RTC-{seq:06d}"


def build_calendar_id(seq: int) -> str:
    """e.g. CAL-000001"""
    return f"CAL-{seq:06d}"


def validate_id(entity_type: str, id_str: str) -> bool:
    """Validates that id_str conforms exactly to the defined regex pattern for entity_type."""
    pattern = ID_PATTERNS.get(entity_type.lower())
    if not pattern:
        raise KeyError(f"No regex pattern defined for entity type: {entity_type}")
    return bool(pattern.match(id_str))
