"""Unit tests for disruption windows, queues, and bridge tables."""

from eta_data.config import load_config
from eta_data.ids import validate_id
from eta_data.master.facilities import generate_facilities
from eta_data.rng import RNGManager
from eta_data.transactions.disruptions import generate_disruption_windows
from eta_data.transactions.queues import generate_facility_queues


def test_disruption_windows_count_and_split():
    cfg = load_config()
    rng = RNGManager(cfg.project.seed)
    facilities = generate_facilities(cfg, rng)

    disruptions, wef_bridges = generate_disruption_windows(cfg, facilities, rng)

    # Exactly 1,000 disruption windows at full scale
    assert len(disruptions) == cfg.targets.num_disruption_windows

    # Verify exact split
    weather_count = sum(1 for d in disruptions if d["window_type"] == "WEATHER")
    facility_count = sum(1 for d in disruptions if d["window_type"] == "FACILITY")

    assert weather_count == cfg.targets.disruption_split.weather
    assert facility_count == cfg.targets.disruption_split.facility
    assert weather_count + facility_count == cfg.targets.num_disruption_windows

    # Verify ID format and ranges
    for d in disruptions:
        assert validate_id("weather_event", d["weather_event_id"])
        assert 1 <= d["severity"] <= 5
        if d["window_type"] == "WEATHER":
            settings = cfg.weather_types[d["type"]]
            assert settings["min_speed_mult"] <= d["speed_multiplier"]
            assert d["speed_multiplier"] <= settings["max_speed_mult"]
        else:
            assert d["speed_multiplier"] >= 1.05

    # Verify bridge table
    assert len(wef_bridges) > 0
    fac_ids = {f["facility_id"] for f in facilities}
    wx_ids = {d["weather_event_id"] for d in disruptions}
    for b in wef_bridges:
        assert validate_id("weather_event_facility", b["bridge_id"])
        assert b["facility_id"] in fac_ids
        assert b["weather_event_id"] in wx_ids


def test_facility_queues():
    cfg = load_config()
    rng = RNGManager(cfg.project.seed)
    facilities = generate_facilities(cfg, rng)
    disruptions, _ = generate_disruption_windows(cfg, facilities, rng)

    queues = generate_facility_queues(cfg, facilities, disruptions, rng, snapshot_interval_hours=24)
    assert len(queues) > 0
    fac_ids = {f["facility_id"] for f in facilities}

    for q in queues:
        assert validate_id("facility_queue", q["queue_id"])
        assert q["facility_id"] in fac_ids
        assert q["queue_length"] >= 0
        assert q["avg_wait_hours"] >= 0.0
        assert q["throughput_per_hour"] > 0.0
