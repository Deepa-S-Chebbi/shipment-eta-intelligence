"""Unit tests for ID generators and regex patterns."""

import pytest
from eta_data.ids import (
    build_shipment_id,
    build_leg_id,
    build_event_id,
    build_eta_id,
    build_delay_id,
    build_carrier_id,
    build_facility_id,
    build_service_level_id,
    build_route_id,
    build_route_leg_template_id,
    build_weather_event_id,
    build_facility_queue_id,
    validate_id,
    ID_PATTERNS,
)


def test_shipment_id():
    shp_id = build_shipment_id(1)
    assert shp_id == "SHP-2026-000001"
    assert validate_id("shipment", shp_id)

    shp_id_large = build_shipment_id(50000)
    assert shp_id_large == "SHP-2026-050000"
    assert validate_id("shipment", shp_id_large)

    with pytest.raises(ValueError):
        build_shipment_id(0)


def test_leg_id():
    shp_id = "SHP-2026-000001"
    leg_id = build_leg_id(shp_id, 1)
    assert leg_id == "LEG-SHP-2026-000001-01"
    assert validate_id("leg", leg_id)

    leg_id_4 = build_leg_id(shp_id, 4)
    assert leg_id_4 == "LEG-SHP-2026-000001-04"
    assert validate_id("leg", leg_id_4)

    with pytest.raises(ValueError):
        build_leg_id("INVALID", 1)
    with pytest.raises(ValueError):
        build_leg_id(shp_id, 0)


def test_event_id():
    shp_id = "SHP-2026-000001"
    evt_id = build_event_id(shp_id, 1)
    assert evt_id == "EVT-SHP-2026-000001-000001"
    assert validate_id("event", evt_id)

    evt_id_seq = build_event_id(shp_id, 12)
    assert evt_id_seq == "EVT-SHP-2026-000001-000012"
    assert validate_id("event", evt_id_seq)


def test_eta_id():
    shp_id = "SHP-2026-000001"
    eta_id = build_eta_id(shp_id, "2026-03-11T10:00:00Z")
    assert eta_id == "ETA-SHP-2026-000001-20260311T1000"
    assert validate_id("eta", eta_id)


def test_delay_id():
    dly_id = build_delay_id(1)
    assert dly_id == "DLY-2026-000001"
    assert validate_id("delay", dly_id)


def test_master_data_ids():
    car = build_carrier_id(1)
    assert car == "CAR-001"
    assert validate_id("carrier", car)

    fac = build_facility_id(1)
    assert fac == "FAC-001"
    assert validate_id("facility", fac)

    sl = build_service_level_id("EXPRESS", 48)
    assert sl == "SL-EXPRESS-48H"
    assert validate_id("service_level", sl)

    rte = build_route_id(1)
    assert rte == "RTE-0001"
    assert validate_id("route", rte)

    rlt = build_route_leg_template_id(1)
    assert rlt == "RLT-000001"
    assert validate_id("route_leg_template", rlt)

    wx = build_weather_event_id(1)
    assert wx == "WX-0001"
    assert validate_id("weather_event", wx)

    fq = build_facility_queue_id(1)
    assert fq == "FQ-000001"
    assert validate_id("facility_queue", fq)
