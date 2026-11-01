"""Unit tests for anomaly injection, ground truth records, and non-leakage."""

from eta_data.anomalies import inject_anomalies
from eta_data.config import load_config
from eta_data.eta import generate_all_eta_snapshots
from eta_data.master.carriers import generate_carriers
from eta_data.master.facilities import generate_facilities
from eta_data.master.routes import generate_routes
from eta_data.master.service_levels import generate_service_levels
from eta_data.rng import RNGManager
from eta_data.transactions.disruptions import generate_disruption_windows
from eta_data.transactions.events import generate_tracking_events
from eta_data.transactions.shipments import generate_shipments
from eta_data.transactions.simulation import SimulationEngine


def test_anomaly_injection_and_non_leakage():
    cfg = load_config(scale_override=0.02)
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
    eta_estimates = generate_all_eta_snapshots(
        shipments=shipments,
        legs=legs,
        events=events,
        disruptions=disruptions,
        facilities=facilities,
        service_levels=service_levels,
    )

    # Inject anomalies
    ground_truth = inject_anomalies(
        cfg=cfg,
        shipments=shipments,
        legs=legs,
        events=events,
        eta_estimates=eta_estimates,
        rng_manager=rng,
    )

    # 1. Ground truth table verification
    assert len(ground_truth) > 0
    issue_types = {gt["issue_type"] for gt in ground_truth}
    assert "EVENT_TIME_INGESTION_CONFUSION" in issue_types
    assert "IMPOSSIBLE_ROUTE_ORDER" in issue_types
    assert "ETA_USES_FUTURE_EVENT" in issue_types
    assert "DELIVERED_STILL_IN_TRANSIT" in issue_types

    # 2. Strict non-leakage test: Primary tables must NOT contain ground-truth columns
    forbidden_cols = {"issue_type", "is_anomaly", "injected_field", "ground_truth", "expected_decision"}

    for s in shipments:
        assert forbidden_cols.isdisjoint(s.keys())
    for l in legs:
        assert forbidden_cols.isdisjoint(l.keys())
    for e in events:
        assert forbidden_cols.isdisjoint(e.keys())
    for eta in eta_estimates:
        assert forbidden_cols.isdisjoint(eta.keys())
