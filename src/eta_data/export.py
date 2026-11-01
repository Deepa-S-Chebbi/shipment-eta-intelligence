"""
Data export engine: CSV, JSON, SQL DDL/seed script, ready SQLite DB, and SHA-256 manifest.
Ensures stable sort order and deterministic formatting across all file outputs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TABLE_SORT_KEYS: Dict[str, List[str]] = {
    "carriers": ["carrier_id"],
    "facilities": ["facility_id"],
    "service_levels": ["service_level_id"],
    "routes": ["route_id"],
    "route_leg_templates": ["route_id", "leg_sequence"],
    "carrier_calendars": ["carrier_id", "day_of_week"],
    "facility_calendars": ["facility_id", "day_of_week"],
    "weather_events": ["weather_event_id"],
    "weather_event_facilities": ["weather_event_id", "facility_id"],
    "weather_event_legs": ["weather_event_id", "leg_id"],
    "facility_queues": ["facility_id", "snapshot_time"],
    "shipments": ["shipment_id"],
    "shipment_legs": ["shipment_id", "leg_sequence"],
    "tracking_events": ["shipment_id", "sequence_no"],
    "delay_reasons": ["delay_id"],
    "shipment_delay_reasons": ["shipment_id", "attribution_id"],
    "shipment_status_history": ["shipment_id", "transition_time"],
    "route_changes": ["shipment_id", "effective_time"],
    "eta_estimates": ["shipment_id", "prediction_time", "method"],
}

SQL_SCHEMA_DDL = """
-- SQLite DDL for YottaFlex AI Synthetic Logistics Database
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS carriers (
    carrier_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mode TEXT NOT NULL,
    reliability_tier TEXT NOT NULL,
    base_speed_kmh REAL NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS facilities (
    facility_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    region TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    capacity_per_hour INTEGER NOT NULL,
    timezone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS service_levels (
    service_level_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    target_hours INTEGER NOT NULL,
    grace_hours REAL NOT NULL,
    severely_delayed_hours REAL NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS routes (
    route_id TEXT PRIMARY KEY,
    origin_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    destination_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    total_planned_hours REAL NOT NULL,
    version INTEGER NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS route_leg_templates (
    template_id TEXT PRIMARY KEY,
    route_id TEXT NOT NULL REFERENCES routes(route_id),
    leg_sequence INTEGER NOT NULL,
    from_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    to_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    carrier_id TEXT NOT NULL REFERENCES carriers(carrier_id),
    planned_duration_hours REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS carrier_calendars (
    calendar_id TEXT PRIMARY KEY,
    carrier_id TEXT NOT NULL REFERENCES carriers(carrier_id),
    day_of_week INTEGER NOT NULL,
    open_time TEXT NOT NULL,
    close_time TEXT NOT NULL,
    is_holiday INTEGER NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS facility_calendars (
    calendar_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    day_of_week INTEGER NOT NULL,
    open_time TEXT NOT NULL,
    close_time TEXT NOT NULL,
    is_holiday INTEGER NOT NULL,
    effective_from TEXT NOT NULL,
    effective_to TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weather_events (
    weather_event_id TEXT PRIMARY KEY,
    window_type TEXT NOT NULL,
    type TEXT NOT NULL,
    severity INTEGER NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    region TEXT NOT NULL,
    speed_multiplier REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS weather_event_facilities (
    bridge_id TEXT PRIMARY KEY,
    weather_event_id TEXT NOT NULL REFERENCES weather_events(weather_event_id),
    facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    impact_start TEXT NOT NULL,
    impact_end TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weather_event_legs (
    bridge_id TEXT PRIMARY KEY,
    weather_event_id TEXT NOT NULL REFERENCES weather_events(weather_event_id),
    leg_id TEXT NOT NULL,
    impact_multiplier REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS facility_queues (
    queue_id TEXT PRIMARY KEY,
    facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    snapshot_time TEXT NOT NULL,
    queue_length INTEGER NOT NULL,
    avg_wait_hours REAL NOT NULL,
    throughput_per_hour REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id TEXT PRIMARY KEY,
    supplier_id TEXT NOT NULL,
    origin_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    destination_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    service_level_id TEXT NOT NULL REFERENCES service_levels(service_level_id),
    route_id TEXT NOT NULL REFERENCES routes(route_id),
    created_at TEXT NOT NULL,
    promised_delivery_at TEXT NOT NULL,
    actual_delivery_at TEXT,
    current_status TEXT NOT NULL,
    final_delay_label TEXT NOT NULL,
    is_rerouted INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS shipment_legs (
    leg_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipments(shipment_id),
    leg_sequence INTEGER NOT NULL,
    from_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    to_facility_id TEXT NOT NULL REFERENCES facilities(facility_id),
    carrier_id TEXT NOT NULL REFERENCES carriers(carrier_id),
    planned_depart_at TEXT NOT NULL,
    planned_arrive_at TEXT NOT NULL,
    actual_depart_at TEXT,
    actual_arrive_at TEXT,
    leg_status TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tracking_events (
    event_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipments(shipment_id),
    leg_id TEXT,
    facility_id TEXT,
    event_type TEXT NOT NULL,
    event_time TEXT NOT NULL,
    ingestion_time TEXT NOT NULL,
    source_system TEXT NOT NULL,
    is_duplicate_of TEXT,
    sequence_no INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS delay_reasons (
    delay_id TEXT PRIMARY KEY,
    reason_code TEXT NOT NULL,
    description TEXT NOT NULL,
    severity INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS shipment_delay_reasons (
    attribution_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipments(shipment_id),
    leg_id TEXT,
    delay_id TEXT NOT NULL REFERENCES delay_reasons(delay_id),
    delay_hours_attributed REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS shipment_status_history (
    history_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipments(shipment_id),
    status TEXT NOT NULL,
    transition_time TEXT NOT NULL,
    trigger_event_id TEXT
);

CREATE TABLE IF NOT EXISTS route_changes (
    change_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipments(shipment_id),
    old_route_id TEXT NOT NULL REFERENCES routes(route_id),
    new_route_id TEXT NOT NULL REFERENCES routes(route_id),
    reason TEXT NOT NULL,
    effective_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eta_estimates (
    eta_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL REFERENCES shipments(shipment_id),
    prediction_time TEXT NOT NULL,
    predicted_delivery_at TEXT NOT NULL,
    method TEXT NOT NULL,
    features_cutoff_time TEXT NOT NULL,
    n_events_used INTEGER NOT NULL,
    predicted_delay_probability REAL NOT NULL
);
"""


def _compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def export_dataset(
    tables: Dict[str, List[Dict[str, Any]]],
    ground_truth: List[Dict[str, Any]],
    out_dir: Path,
    ground_truth_dir: Path,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Exports all CSVs, JSON, SQL seed, SQLite database, and manifest.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    ground_truth_dir.mkdir(parents=True, exist_ok=True)

    manifest_files: List[Dict[str, Any]] = []

    # 1. Export CSVs with stable sorting
    for table_name, rows in tables.items():
        if not rows:
            continue

        sort_keys = TABLE_SORT_KEYS.get(table_name, list(rows[0].keys()))
        sorted_rows = sorted(rows, key=lambda r: tuple(str(r.get(k, "")) for k in sort_keys))

        csv_path = out_dir / f"{table_name}.csv"
        fieldnames = list(sorted_rows[0].keys())

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            for r in sorted_rows:
                # Format booleans cleanly as 1/0 or True/False
                row_copy = {}
                for k, v in r.items():
                    if isinstance(v, bool):
                        row_copy[k] = "True" if v else "False"
                    elif v is None:
                        row_copy[k] = ""
                    else:
                        row_copy[k] = v
                writer.writerow(row_copy)

        sha = _compute_sha256(csv_path)
        manifest_files.append({
            "name": f"{table_name}.csv",
            "path": f"{out_dir.name}/{table_name}.csv",
            "row_count": len(sorted_rows),
            "bytes": csv_path.stat().st_size,
            "sha256": sha,
        })

    # 2. Export Ground Truth
    gt_sorted = sorted(ground_truth, key=lambda x: (x.get("record_type", ""), x.get("record_id", "")))
    gt_csv_path = ground_truth_dir / "ground_truth.csv"
    gt_json_path = ground_truth_dir / "ground_truth.json"
    gt_dataset_csv_path = ground_truth_dir / f"ground_truth_{out_dir.name}.csv"
    gt_dataset_json_path = ground_truth_dir / f"ground_truth_{out_dir.name}.json"

    if gt_sorted:
        gt_fields = list(gt_sorted[0].keys())
        with open(gt_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=gt_fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(gt_sorted)

        with open(gt_json_path, "w", newline="\n", encoding="utf-8") as f:
            json.dump(gt_sorted, f, indent=2)

        # Write dataset-specific copies to prevent cross-scale overwrite collisions
        shutil.copy2(gt_csv_path, gt_dataset_csv_path)
        shutil.copy2(gt_json_path, gt_dataset_json_path)

        manifest_files.append({
            "name": "ground_truth.csv",
            "path": f"{ground_truth_dir.name}/ground_truth.csv",
            "row_count": len(gt_sorted),
            "bytes": gt_csv_path.stat().st_size,
            "sha256": _compute_sha256(gt_csv_path),
        })
        manifest_files.append({
            "name": "ground_truth.json",
            "path": f"{ground_truth_dir.name}/ground_truth.json",
            "row_count": len(gt_sorted),
            "bytes": gt_json_path.stat().st_size,
            "sha256": _compute_sha256(gt_json_path),
        })

    # 3. Export SQL Seed Script and SQLite DB
    sql_path = out_dir / "seed.sql"
    sqlite_path = out_dir / "logistics.sqlite"

    with open(sql_path, "w", newline="\n", encoding="utf-8") as f:
        f.write(SQL_SCHEMA_DDL)
        f.write("\nBEGIN TRANSACTION;\n")

        for tbl, rows in tables.items():
            if not rows:
                continue
            cols = list(rows[0].keys())
            cols_str = ", ".join(cols)
            for r in rows:
                vals = []
                for c in cols:
                    v = r.get(c)
                    if v is None or v == "":
                        vals.append("NULL")
                    elif isinstance(v, bool):
                        vals.append("1" if v else "0")
                    elif isinstance(v, (int, float)):
                        vals.append(str(v))
                    else:
                        clean_str = str(v).replace("'", "''")
                        vals.append(f"'{clean_str}'")
                vals_str = ", ".join(vals)
                f.write(f"INSERT INTO {tbl} ({cols_str}) VALUES ({vals_str});\n")

        f.write("COMMIT;\n")

    manifest_files.append({
        "name": "seed.sql",
        "path": f"{out_dir.name}/seed.sql",
        "row_count": sum(len(r) for r in tables.values()),
        "bytes": sql_path.stat().st_size,
        "sha256": _compute_sha256(sql_path),
    })

    # Populate SQLite database directly
    if sqlite_path.exists():
        sqlite_path.unlink()
    conn = sqlite3.connect(sqlite_path)
    with open(sql_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

    manifest_files.append({
        "name": "logistics.sqlite",
        "path": f"{out_dir.name}/logistics.sqlite",
        "row_count": sum(len(r) for r in tables.values()),
        "bytes": sqlite_path.stat().st_size,
        "sha256": _compute_sha256(sqlite_path),
    })

    # 4. Generate manifest.json
    manifest = {
        "generator_version": metadata.get("version", "1.0.0"),
        "master_seed": metadata.get("seed", 20261022),
        "scale": metadata.get("scale", 1.0),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_command": metadata.get("command", ""),
        "total_files": len(manifest_files),
        "files": manifest_files,
    }

    manifest_path = out_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return manifest
