"""Unit tests for Shipment generation and SimulationEngine."""

from datetime import datetime
from eta_data.config import load_config
from eta_data.ids import validate_id
from eta_data.master.carriers import generate_carriers
from eta_data.master.facilities import generate_facilities
from eta_data.master.routes import generate_routes
from eta_data.master.service_levels import generate_service_levels
from eta_data.rng import RNGManager
from eta_data.transactions.disruptions import generate_disruption_windows
from eta_data.transactions.shipments import generate_shipments
from eta_data.transactions.simulation import SimulationEngine


def test_shipments_and_simulation():
    # Use starter scale for quick testing
    cfg = load_config(scale_override=0.01)
    rng = RNGManager(cfg.project.seed)

    facilities = generate_facilities(cfg, rng)
    carriers = generate_carriers(cfg, rng)
    routes, templates = generate_routes(cfg, facilities, carriers, rng)
    service_levels = generate_service_levels(cfg)
    disruptions, wef_bridges = generate_disruption_windows(
            cfg, facilities, rng
    )
    shipments = generate_shipments(cfg, routes, service_levels, rng)
    assert len(shipments) == cfg.targets.num_shipments

    for s in shipments:
        assert validate_id("shipment", s["shipment_id"])
        assert s["origin_facility_id"] != s["destination_facility_id"]
        assert s["current_status"] == "CREATED"
        t_create = datetime.fromisoformat(s["created_at"].rstrip("Z"))
        t_prom = datetime.fromisoformat(s["promised_delivery_at"].rstrip("Z"))
        assert t_prom > t_create

    # Run simulation
    engine = SimulationEngine(
        cfg=cfg,
        facilities=facilities,
        carriers=carriers,
        routes=routes,
        templates=templates,
        disruptions=disruptions,
        rng_manager=rng,
    )

    legs, route_changes = engine.simulate(shipments)
    assert len(legs) >= len(shipments)

    for leg in legs:
        assert validate_id("leg", leg["leg_id"])
        dep = datetime.fromisoformat(leg["actual_depart_at"].rstrip("Z"))
        arr = datetime.fromisoformat(leg["actual_arrive_at"].rstrip("Z"))
        # Actual transit must be strictly positive
        assert arr > dep

    # Test shipment final state
    for s in shipments:
        assert s["current_status"] == "DELIVERED"
        assert s["actual_delivery_at"] is not None
        t_del = datetime.fromisoformat(s["actual_delivery_at"].rstrip("Z"))
        t_create = datetime.fromisoformat(s["created_at"].rstrip("Z"))
        assert t_del > t_create
