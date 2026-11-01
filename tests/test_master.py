"""Unit tests for master data generation: carriers, facilities, service levels, routes."""

from eta_data.config import load_config
from eta_data.ids import validate_id
from eta_data.master.carriers import generate_carriers
from eta_data.master.facilities import generate_facilities
from eta_data.master.routes import generate_routes
from eta_data.master.service_levels import generate_service_levels
from eta_data.rng import RNGManager


def test_master_data_generation():
    cfg = load_config()
    rng = RNGManager(cfg.project.seed)

    carriers = generate_carriers(cfg, rng)
    assert len(carriers) == cfg.targets.num_carriers
    for c in carriers:
        assert validate_id("carrier", c["carrier_id"])
        assert c["mode"] in ["ROAD", "RAIL", "AIR", "SEA"]
        assert c["reliability_tier"] in ["TIER_1", "TIER_2", "TIER_3"]
        assert c["base_speed_kmh"] > 0

    facilities = generate_facilities(cfg, rng)
    assert len(facilities) == cfg.targets.num_facilities
    for f in facilities:
        assert validate_id("facility", f["facility_id"])
        assert 0.0 <= f["latitude"] <= 1000.0
        assert 0.0 <= f["longitude"] <= 1000.0
        assert f["type"] in ["HUB", "DEPOT", "WAREHOUSE", "PORT"]
        assert f["region"] in ["North", "South", "East", "West"]
        assert f["capacity_per_hour"] > 0

    service_levels = generate_service_levels(cfg)
    assert len(service_levels) >= 4
    for sl in service_levels:
        assert validate_id("service_level", sl["service_level_id"])
        assert sl["target_hours"] > 0
        assert sl["grace_hours"] >= 0
        assert sl["severely_delayed_hours"] > sl["grace_hours"]

    routes, templates = generate_routes(cfg, facilities, carriers, rng)
    assert len(routes) == cfg.targets.num_routes
    for r in routes:
        assert validate_id("route", r["route_id"])
        assert r["total_planned_hours"] > 0

    # Ensure templates link to routes and have 1..N sequence
    templates_by_route = {}
    for t in templates:
        assert validate_id("route_leg_template", t["template_id"])
        templates_by_route.setdefault(t["route_id"], []).append(t)

    for r_id, t_list in templates_by_route.items():
        seqs = [t["leg_sequence"] for t in t_list]
        assert seqs == list(range(1, len(t_list) + 1))
