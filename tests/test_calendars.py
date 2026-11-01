"""Unit tests for calendar logic, shifts, and holiday forward-seekers."""

from datetime import datetime, timezone
import pytest
from eta_data.calendars import (
    DEFAULT_HOLIDAYS,
    get_next_open_time,
    is_timestamp_within_open_hours,
)


def test_hub_24_7_operations():
    """HUB is 24/7 and never closes on weekends or standard days."""
    # Sunday at midnight
    dt_sun = datetime(2026, 3, 8, 2, 30, 0, tzinfo=timezone.utc)
    assert is_timestamp_within_open_hours("HUB", dt_sun)
    next_t = get_next_open_time("HUB", dt_sun)
    assert next_t == dt_sun


def test_warehouse_weekend_closure():
    """WAREHOUSE is open Mon-Fri 07:00-19:00, closed on Saturday and Sunday."""
    # Saturday 14:00
    dt_sat = datetime(2026, 3, 7, 14, 0, 0, tzinfo=timezone.utc)
    assert not is_timestamp_within_open_hours("WAREHOUSE", dt_sat)

    # Next open time should be Monday morning at 07:00:00
    next_t = get_next_open_time("WAREHOUSE", dt_sat)
    assert next_t.weekday() == 0  # Monday
    assert next_t.hour == 7
    assert next_t.minute == 0


def test_depot_overnight_closure():
    """DEPOT closes at 22:00, reopens at 06:00."""
    # Wednesday at 23:30
    dt_night = datetime(2026, 3, 4, 23, 30, 0, tzinfo=timezone.utc)
    assert not is_timestamp_within_open_hours("DEPOT", dt_night)

    next_t = get_next_open_time("DEPOT", dt_night)
    assert next_t.day == 5  # Thursday
    assert next_t.hour == 6
    assert next_t.minute == 0


def test_holiday_closure():
    """Non-24/7 facilities observe national holidays."""
    # 2026-05-01 is a Friday and an official holiday
    dt_holiday = datetime(2026, 5, 1, 10, 0, 0, tzinfo=timezone.utc)
    assert "2026-05-01" in DEFAULT_HOLIDAYS
    assert not is_timestamp_within_open_hours("DEPOT", dt_holiday)

    next_t = get_next_open_time("DEPOT", dt_holiday)
    # Reopens Saturday 2026-05-02 at 06:00
    assert next_t.day == 2
    assert next_t.hour == 6
