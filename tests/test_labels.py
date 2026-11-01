"""Unit tests for delay labels, boundary conditions, and exact arithmetic reconciliation."""

from datetime import datetime, timedelta
import pytest
from eta_data.ids import validate_id
from eta_data.labels import (
    compute_delay_labels_and_reasons,
    generate_delay_reason_taxonomy,
)


def test_delay_reason_taxonomy():
    tax = generate_delay_reason_taxonomy()
    assert len(tax) == 6
    codes = {r["reason_code"] for r in tax}
    assert codes == {"WEATHER", "FACILITY_QUEUE", "CARRIER_DELAY", "ROUTE_CHANGE", "CALENDAR_CLOSURE", "LATE_PICKUP"}
    for r in tax:
        assert validate_id("delay", r["delay_id"])


def test_boundary_label_rules():
    """Verifies exact grace hour and severe delay threshold boundaries."""
    service_levels = [
        {
            "service_level_id": "SL-TEST-24H",
            "name": "Test SLA",
            "target_hours": 24,
            "grace_hours": 2.0,
            "severely_delayed_hours": 6.0,
        }
    ]
    reasons = generate_delay_reason_taxonomy()

    # 1. Exact boundary: delay_hours == 2.0 (grace_hours) -> MUST BE ON_TIME
    shipment_on_time = {
        "shipment_id": "SHP-2026-000001",
        "service_level_id": "SL-TEST-24H",
        "created_at": "2026-03-01T10:00:00Z",
        "promised_delivery_at": "2026-03-02T10:00:00Z",
        "actual_delivery_at": None,
        "current_status": "DELIVERED",
        "final_delay_label": None,
        "origin_facility_id": "FAC-001",
        "destination_facility_id": "FAC-002",
        "is_rerouted": False,
    }
    event_on_time = {
        "shipment_id": "SHP-2026-000001",
        "event_type": "DELIVERED",
        "event_time": "2026-03-02T12:00:00Z",  # Exactly +2.0 hours
    }

    compute_delay_labels_and_reasons(
        [shipment_on_time], [], [event_on_time], service_levels, reasons
    )
    assert shipment_on_time["final_delay_label"] == "ON_TIME"

    # 2. Exact boundary: delay_hours == 6.0 (severely_delayed_hours) -> MUST BE DELAYED
    shipment_delayed = {
        "shipment_id": "SHP-2026-000002",
        "service_level_id": "SL-TEST-24H",
        "created_at": "2026-03-01T10:00:00Z",
        "promised_delivery_at": "2026-03-02T10:00:00Z",
        "actual_delivery_at": None,
        "current_status": "DELIVERED",
        "final_delay_label": None,
        "origin_facility_id": "FAC-001",
        "destination_facility_id": "FAC-002",
        "is_rerouted": False,
    }
    event_delayed = {
        "shipment_id": "SHP-2026-000002",
        "event_type": "DELIVERED",
        "event_time": "2026-03-02T16:00:00Z",  # Exactly +6.0 hours
    }

    compute_delay_labels_and_reasons(
        [shipment_delayed], [], [event_delayed], service_levels, reasons
    )
    assert shipment_delayed["final_delay_label"] == "DELAYED"

    # 3. Beyond threshold: delay_hours == 6.1 -> SEVERELY_DELAYED
    shipment_severe = {
        "shipment_id": "SHP-2026-000003",
        "service_level_id": "SL-TEST-24H",
        "created_at": "2026-03-01T10:00:00Z",
        "promised_delivery_at": "2026-03-02T10:00:00Z",
        "actual_delivery_at": None,
        "current_status": "DELIVERED",
        "final_delay_label": None,
        "origin_facility_id": "FAC-001",
        "destination_facility_id": "FAC-002",
        "is_rerouted": False,
    }
    event_severe = {
        "shipment_id": "SHP-2026-000003",
        "event_type": "DELIVERED",
        "event_time": "2026-03-02T16:06:00Z",  # +6.1 hours
    }

    compute_delay_labels_and_reasons(
        [shipment_severe], [], [event_severe], service_levels, reasons
    )
    assert shipment_severe["final_delay_label"] == "SEVERELY_DELAYED"


def test_delay_reason_reconciliation():
    """Verifies that attributed hours sum to total positive delay."""
    service_levels = [
        {
            "service_level_id": "SL-TEST-24H",
            "name": "Test SLA",
            "target_hours": 24,
            "grace_hours": 2.0,
            "severely_delayed_hours": 6.0,
        }
    ]
    reasons = generate_delay_reason_taxonomy()

    shipment = {
        "shipment_id": "SHP-2026-000010",
        "service_level_id": "SL-TEST-24H",
        "created_at": "2026-03-01T10:00:00Z",
        "promised_delivery_at": "2026-03-02T10:00:00Z",
        "actual_delivery_at": None,
        "current_status": "DELIVERED",
        "final_delay_label": None,
        "origin_facility_id": "FAC-001",
        "destination_facility_id": "FAC-002",
        "is_rerouted": True,
    }
    # Delivered 10 hours late: total_delay = 10.0 hours
    del_event = {
        "shipment_id": "SHP-2026-000010",
        "event_type": "DELIVERED",
        "event_time": "2026-03-02T20:00:00Z",
    }
    leg = {
        "leg_id": "LEG-SHP-2026-000010-01",
        "shipment_id": "SHP-2026-000010",
        "from_facility_id": "FAC-001",
        "to_facility_id": "FAC-002",
        "planned_depart_at": "2026-03-01T11:00:00Z",
        "planned_arrive_at": "2026-03-02T05:00:00Z",
        "actual_depart_at": "2026-03-01T12:00:00Z",
        "actual_arrive_at": "2026-03-02T18:00:00Z",
    }

    _, attributions = compute_delay_labels_and_reasons(
        [shipment], [leg], [del_event], service_levels, reasons
    )

    assert len(attributions) > 0
    attributed_sum = sum(a["delay_hours_attributed"] for a in attributions)
    total_expected_delay = 10.0
    assert abs(attributed_sum - total_expected_delay) < 1e-3
