#!/usr/bin/env python
"""
CLI entry point for YottaFlex AI Synthetic Logistics Data Generation.
Coordinates end-to-end pipeline execution from master data to export and validation.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure src is on sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "src"))

from eta_data.anomalies import inject_anomalies
from eta_data.calendars import generate_carrier_calendars, generate_facility_calendars
from eta_data.config import load_config
from eta_data.eta import generate_all_eta_snapshots
from eta_data.export import export_dataset
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
from eta_data.validate import validate_data_directory


def run_pipeline(
    config_path: str,
    out_dir_str: str,
    scale_override: float | None = None,
    ground_truth_dir_str: str = "ground_truth",
    run_validation: bool = True,
) -> int:
    t_start = time.time()
    cfg = load_config(config_path, scale_override=scale_override)
    scale = cfg.project.scale
    out_dir = Path(out_dir_str).resolve()
    gt_dir = Path(ground_truth_dir_str).resolve()

    print("=" * 70)
    print("YOTTAFLEX AI LOGISTICS SYNTHETIC DATA GENERATOR")
    print(f"Master Seed:     {cfg.project.seed}")
    print(f"Scale:           {scale}")
    print(f"Target Shipments:{cfg.targets.num_shipments}")
    print(f"Target Events:   {cfg.targets.target_events}")
    print(f"Output Directory:{out_dir}")
    print("=" * 70)

    rng = RNGManager(cfg.project.seed)

    print("\n[1/7] Generating Master Data & Calendars...")
    facilities = generate_facilities(cfg, rng)
    carriers = generate_carriers(cfg, rng)
    routes, templates = generate_routes(cfg, facilities, carriers, rng)
    service_levels = generate_service_levels(cfg)
    delay_reasons = generate_delay_reason_taxonomy()

    sim_start = cfg.simulation.start_date
    sim_end = "2026-06-30T00:00:00Z"
    fac_cals = generate_facility_calendars(facilities, sim_start, sim_end)
    car_cals = generate_carrier_calendars(carriers, sim_start, sim_end)
    print(f"  Generated {len(facilities)} facilities, {len(carriers)} carriers, {len(routes)} routes.")

    print("\n[2/7] Generating Disruption Windows & Facility Queues...")
    disruptions, wef_bridges = generate_disruption_windows(cfg, facilities, rng)
    queues = generate_facility_queues(cfg, facilities, disruptions, rng, snapshot_interval_hours=24)
    print(f"  Generated {len(disruptions)} disruption windows (Weather: {cfg.targets.disruption_split.weather}, Facility: {cfg.targets.disruption_split.facility}).")

    print("\n[3/7] Generating Shipments & Executing Causal Simulation...")
    shipments = generate_shipments(cfg, routes, service_levels, rng)
    engine = SimulationEngine(
        cfg,
        facilities,
        carriers,
        routes,
        templates,
        disruptions,
        rng,
        facility_bridges=wef_bridges,
    )
    legs, route_changes = engine.simulate(shipments)
    wel_bridges = build_weather_leg_bridges(
        disruptions, legs, facilities, wef_bridges
    )    
    print(f"  Simulated {len(shipments)} shipments, {len(legs)} legs, {len(route_changes)} dynamic reroutes.")

    print("\n[4/7] Emitting Tracking Events with Ingestion Lag & Calibration...")
    events, status_history = generate_tracking_events(cfg, shipments, legs, route_changes, rng)
    print(f"  Emitted exactly {len(events)} tracking events (target: {cfg.targets.target_events}).")

    print("\n[5/7] Computing Delay Labels & Additive Reconciliation...")
    shipments, delay_attributions = compute_delay_labels_and_reasons(
        shipments, legs, events, service_levels, delay_reasons
    )
    print(f"  Calculated SLA labels and {len(delay_attributions)} reconciled delay reason attributions.")

    print("\n[6/7] Computing Leakage-Safe Point-in-Time ETA Snapshots...")
    eta_estimates = generate_all_eta_snapshots(
        shipments, legs, events, disruptions, facilities, service_levels
    )
    print(f"  Generated {len(eta_estimates)} leakage-safe point-in-time ETA snapshots.")

    print("\n[7/7] Injecting Labelled Anomalies & Exporting Datasets...")
    ground_truth = inject_anomalies(cfg, shipments, legs, events, eta_estimates, rng)
    print(f"  Injected {len(ground_truth)} labelled anomalies (isolated to ground_truth/).")

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

    manifest = export_dataset(
        tables=tables,
        ground_truth=ground_truth,
        out_dir=out_dir,
        ground_truth_dir=gt_dir,
        metadata={
            "version": cfg.project.version,
            "seed": cfg.project.seed,
            "scale": scale,
            "command": " ".join(sys.argv),
        },
    )
    print(f"  Successfully exported {len(manifest['files'])} files to {out_dir} and {gt_dir}.")

    elapsed = time.time() - t_start
    print(f"\nGeneration completed in {elapsed:.2f} seconds.")

    if run_validation:
        print("\nRunning Automated Validation Suite...")
        valid = validate_data_directory(out_dir, gt_dir)
        if not valid:
            print("ERROR: Validation failed!")
            return 1

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic logistics dataset")
    parser.add_argument("--config", default="config/default.yaml", help="Path to YAML configuration")
    parser.add_argument("--out", default="data/full", help="Output directory for generated dataset")
    parser.add_argument("--scale", type=float, default=None, help="Scale multiplier override")
    parser.add_argument("--ground-truth", default="ground_truth", help="Ground truth output directory")
    parser.add_argument("--no-validate", action="store_true", help="Skip post-generation validation")

    args = parser.parse_args()

    exit_code = run_pipeline(
        config_path=args.config,
        out_dir_str=args.out,
        scale_override=args.scale,
        ground_truth_dir_str=args.ground_truth,
        run_validation=not args.no_validate,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
