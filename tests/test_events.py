"""Unit tests for tracking event generation, exact calibration, and status history."""

from datetime import datetime
from eta_data.config import load_config
from eta_data.ids import validate_id
from eta_data.master.carriers import generate_carriers
from eta_data.master.facilities import generate_facilities
from eta_data.master.routes import generate_routes
from eta_data.master.service_levels import generate_service_levels
from eta_data.rng import RNGManager
from eta_data.transactions.disruptions import generate_disruption_windows
from eta_data.transactions.events import generate_tracking_events
from eta_data.transactions.shipments import generate_shipments
from eta_data.transactions.simulation import SimulationEngine


def test_events_generation_and_exact_calibration():
    # Use starter scale
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

    events, status_history = generate_tracking_events(
        cfg=cfg,
        shipments=shipments,
        legs=legs,
        route_changes=route_changes,
        rng_manager=rng,
    )

    # EXACT EVENT COUNT CALIBRATION CHECK
    assert len(events) == cfg.targets.target_events

    # Event fields and monotonic sequences
    events_by_shp = {}
    for ev in events:
        assert validate_id("event", ev["event_id"])
        events_by_shp.setdefault(ev["shipment_id"], []).append(ev)

        # Ingestion lag must be positive
        t_ev = datetime.fromisoformat(ev["event_time"].rstrip("Z"))
        t_ing = datetime.fromisoformat(ev["ingestion_time"].rstrip("Z"))
        assert t_ing >= t_ev

    for shp_id, ev_list in events_by_shp.items():
        seqs = [e["sequence_no"] for e in ev_list]
        assert seqs == list(range(1, len(ev_list) + 1))

    # Verify ShipmentStatusHistory
    assert len(status_history) > 0
    for ssh in status_history:
        assert validate_id("shipment_status_history", ssh["history_id"])
        assert ssh["status"] in ("CREATED", "IN_TRANSIT", "DELIVERED")
