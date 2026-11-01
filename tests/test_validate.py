"""Unit tests for ValidationSuite in-memory execution."""

from eta_data.anomalies import inject_anomalies
from eta_data.calendars import generate_carrier_calendars, generate_facility_calendars
from eta_data.config import load_config
from eta_data.eta import generate_all_eta_snapshots
from eta_data.labels import compute_delay_labels_and_reasons, generate_delay_reason_taxonomy
from eta_data.master.carriers import generate_carriers
from eta_data.master.facilities import generate_facilities
from eta_data.master.routes import generate_routes
from eta_data.master.service_levels import generate_service_levels
from eta_data.rng import RNGManager
from eta_data.transactions.disruptions import build_weather_leg_bridges, generate_disruption_windows
from eta_data.transactions.events import generate_tracking_events
from eta_data.transactions.queues import generate_facility_queues
from eta_data.transactions.shipments import generate_shipments
from eta_data.transactions.simulation import SimulationEngine
from eta_data.validate import ValidationSuite


def test_validation_suite_passes():
    cfg = load_config(scale_override=0.01)
    rng = RNGManager(cfg.project.seed)

    # Master data
    facilities = generate_facilities(cfg, rng)
    carriers = generate_carriers(cfg, rng)
    routes, templates = generate_routes(cfg, facilities, carriers, rng)
    service_levels = generate_service_levels(cfg)
    delay_reasons = generate_delay_reason_taxonomy()

    # Calendars
    fac_cals = generate_facility_calendars(facilities, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z")
    car_cals = generate_carrier_calendars(carriers, "2026-03-01T00:00:00Z", "2026-06-01T00:00:00Z")

    # Disruptions & Queues
    disruptions, wef_bridges = generate_disruption_windows(cfg, facilities, rng)
    queues = generate_facility_queues(cfg, facilities, disruptions, rng, snapshot_interval_hours=24)

    # Transactions & Simulation
    shipments = generate_shipments(cfg, routes, service_levels, rng)
    engine = SimulationEngine(cfg, facilities, carriers, routes, templates, disruptions, rng, wef_bridges)
    legs, route_changes = engine.simulate(shipments)

    wel_bridges = build_weather_leg_bridges(disruptions, legs, facilities, wef_bridges)
    events, status_history = generate_tracking_events(cfg, shipments, legs, route_changes, rng)

    # Labels
    shipments, delay_attributions = compute_delay_labels_and_reasons(
        shipments, legs, events, service_levels, delay_reasons
    )

    # ETA
    eta_estimates = generate_all_eta_snapshots(
        shipments, legs, events, disruptions, facilities, service_levels
    )

    # Injected Anomalies
    ground_truth = inject_anomalies(cfg, shipments, legs, events, eta_estimates, rng)

    tables = {
        "carriers": carriers,
        "facilities": facilities,
        "service_levels": service_levels,
        "routes": routes,
        "route_leg_templates": templates,
        "carrier_calendars": car_cals,
        "facility_calendars": fac_cals,
        "weather_events": disruptions,
        "weather_event_facilities": wef_bridges,
        "weather_event_legs": wel_bridges,
        "facility_queues": queues,
        "shipments": shipments,
        "shipment_legs": legs,
        "tracking_events": events,
        "delay_reasons": delay_reasons,
        "shipment_delay_reasons": delay_attributions,
        "shipment_status_history": status_history,
        "route_changes": route_changes,
        "eta_estimates": eta_estimates,
    }

    suite = ValidationSuite(tables=tables, ground_truth=ground_truth)
    all_passed = suite.run_all()

    assert all_passed is True
    assert len(suite.results) == 12
    for res in suite.results:
        assert res["passed"] is True
        assert res["violations_count"] == 0
