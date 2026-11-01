"""Unit tests for ETA snapshot leakage safety."""

from datetime import datetime
from eta_data.config import load_config
from eta_data.eta import generate_all_eta_snapshots
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


def test_eta_leakage_safety():
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
    events, _ = generate_tracking_events(
        cfg=cfg,
        shipments=shipments,
        legs=legs,
        route_changes=route_changes,
        rng_manager=rng,
    )

    snapshots = generate_all_eta_snapshots(
        shipments=shipments,
        legs=legs,
        events=events,
        disruptions=disruptions,
        facilities=facilities,
        service_levels=service_levels,
    )

    assert len(snapshots) > 0

    events_by_shp = {}
    for e in events:
        events_by_shp.setdefault(e["shipment_id"], []).append(e)

    for snap in snapshots:
        t_pred = datetime.fromisoformat(snap["prediction_time"].rstrip("Z"))
        t_cutoff = datetime.fromisoformat(snap["features_cutoff_time"].rstrip("Z"))

        # Cutoff must not exceed prediction time
        assert t_cutoff <= t_pred

        # Verify n_events_used matches only events ingested by prediction time
        shp_events = events_by_shp.get(snap["shipment_id"], [])
        truly_visible = [
            e for e in shp_events
            if datetime.fromisoformat(e["ingestion_time"].rstrip("Z")) <= t_pred
        ]
        assert snap["n_events_used"] == len(truly_visible)

        # Verify probability bounds
        prob = snap["predicted_delay_probability"]
        assert 0.0 <= prob <= 1.0
