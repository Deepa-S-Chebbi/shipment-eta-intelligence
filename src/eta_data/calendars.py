"""
Facility and Carrier calendar schedules, shift logic, holiday cutoffs, and operating windows.
Supports deterministic calendar row generation and forward-seeking next-open calculations.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Set, Tuple
from eta_data.ids import build_calendar_id

# Known fixed holiday dates during the 2026 simulation epoch (March - May 2026)
DEFAULT_HOLIDAYS: Set[str] = {
    "2026-03-25",  # Spring Operational Recess
    "2026-04-12",  # Regional Logistics Holiday
    "2026-05-01",  # International Workers Day
    "2026-05-25",  # Memorial Logistics Day
}

FACILITY_SCHEDULE_RULES: Dict[str, Dict[str, Any]] = {
    "HUB": {
        "open_days": {0, 1, 2, 3, 4, 5, 6},  # Mon-Sun (24/7)
        "open_time": time(0, 0, 0),
        "close_time": time(23, 59, 59),
        "observes_holidays": False,
    },
    "PORT": {
        "open_days": {0, 1, 2, 3, 4, 5, 6},  # Mon-Sun (24/7)
        "open_time": time(0, 0, 0),
        "close_time": time(23, 59, 59),
        "observes_holidays": False,
    },
    "DEPOT": {
        "open_days": {0, 1, 2, 3, 4, 5},  # Mon-Sat
        "open_time": time(6, 0, 0),
        "close_time": time(22, 0, 0),
        "observes_holidays": True,
    },
    "WAREHOUSE": {
        "open_days": {0, 1, 2, 3, 4},  # Mon-Fri
        "open_time": time(7, 0, 0),
        "close_time": time(19, 0, 0),
        "observes_holidays": True,
    },
}


def is_timestamp_within_open_hours(
    fac_type: str,
    dt: datetime,
    holidays: Set[str] | None = None,
) -> bool:
    """Checks whether the facility is operating at the given datetime."""
    if holidays is None:
        holidays = DEFAULT_HOLIDAYS

    rule = FACILITY_SCHEDULE_RULES.get(fac_type, FACILITY_SCHEDULE_RULES["DEPOT"])
    date_str = dt.strftime("%Y-%m-%d")

    # Check holiday closure
    if rule["observes_holidays"] and holidays and date_str in holidays:
        return False

    # Check day of week (0 = Monday, 6 = Sunday)
    if dt.weekday() not in rule["open_days"]:
        return False

    # Check operating hours
    current_time = dt.time()
    return rule["open_time"] <= current_time <= rule["close_time"]


def get_next_open_time(
    fac_type: str,
    dt: datetime,
    holidays: Set[str] | None = None,
) -> datetime:
    """
    Finds the earliest subsequent operating timestamp for the facility.
    If the facility is currently open, returns dt unchanged.
    """
    if holidays is None:
        holidays = DEFAULT_HOLIDAYS

    rule = FACILITY_SCHEDULE_RULES.get(fac_type, FACILITY_SCHEDULE_RULES["DEPOT"])

    # If already open, no delay needed
    if is_timestamp_within_open_hours(fac_type, dt, holidays):
        return dt

    # Search forward day by day
    cursor = dt
    for _ in range(14):  # Look up to 14 days ahead
        date_str = cursor.strftime("%Y-%m-%d")
        is_holiday = rule["observes_holidays"] and (date_str in holidays)
        is_workday = (cursor.weekday() in rule["open_days"]) and not is_holiday

        if is_workday:
            open_dt = datetime.combine(cursor.date(), rule["open_time"], tzinfo=dt.tzinfo)
            close_dt = datetime.combine(cursor.date(), rule["close_time"], tzinfo=dt.tzinfo)

            if cursor < open_dt:
                return open_dt
            elif cursor <= close_dt:
                return cursor

        # Move to next day at 00:00:00
        next_day = cursor.date() + timedelta(days=1)
        cursor = datetime.combine(next_day, time(0, 0, 0), tzinfo=dt.tzinfo)

    # Fallback to current time if loop exhaust
    return dt


def generate_facility_calendars(
    facilities: List[Dict[str, Any]],
    start_date_str: str,
    end_date_str: str,
    holidays: Set[str] | None = None,
) -> List[Dict[str, Any]]:
    """Generates relational FacilityCalendar rows conforming to the schema."""
    if holidays is None:
        holidays = DEFAULT_HOLIDAYS

    calendar_rows: List[Dict[str, Any]] = []
    cal_seq = 1

    for fac in facilities:
        fac_id = fac["facility_id"]
        fac_type = fac["type"]
        rule = FACILITY_SCHEDULE_RULES.get(fac_type, FACILITY_SCHEDULE_RULES["DEPOT"])

        for dow in range(7):
            is_workday = dow in rule["open_days"]
            row = {
                "calendar_id": build_calendar_id(cal_seq),
                "facility_id": fac_id,
                "day_of_week": dow,
                "open_time": rule["open_time"].strftime("%H:%M:%S") if is_workday else "00:00:00",
                "close_time": rule["close_time"].strftime("%H:%M:%S") if is_workday else "00:00:00",
                "is_holiday": False,
                "effective_from": start_date_str,
                "effective_to": end_date_str,
            }
            calendar_rows.append(row)
            cal_seq += 1

    return calendar_rows


def generate_carrier_calendars(
    carriers: List[Dict[str, Any]],
    start_date_str: str,
    end_date_str: str,
) -> List[Dict[str, Any]]:
    """Generates relational CarrierCalendar rows conforming to the schema."""
    calendar_rows: List[Dict[str, Any]] = []
    cal_seq = 1

    for car in carriers:
        car_id = car["carrier_id"]
        mode = car["mode"]

        # ROAD / RAIL usually operate 6 days (Mon-Sat 05:00-23:00); AIR / SEA 24/7
        is_always_open = mode in {"AIR", "SEA"}
        open_days = {0, 1, 2, 3, 4, 5, 6} if is_always_open else {0, 1, 2, 3, 4, 5}
        open_t = "00:00:00" if is_always_open else "05:00:00"
        close_t = "23:59:59" if is_always_open else "23:00:00"

        for dow in range(7):
            is_open = dow in open_days
            row = {
                "calendar_id": build_calendar_id(cal_seq),
                "carrier_id": car_id,
                "day_of_week": dow,
                "open_time": open_t if is_open else "00:00:00",
                "close_time": close_t if is_open else "00:00:00",
                "is_holiday": False,
                "effective_from": start_date_str,
                "effective_to": end_date_str,
            }
            calendar_rows.append(row)
            cal_seq += 1

    return calendar_rows
