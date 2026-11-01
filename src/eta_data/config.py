"""Configuration loading and validation module."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml


@dataclass
class ProjectConfig:
    name: str = "yottaflex-eta-delay-data"
    version: str = "1.0.0"
    seed: int = 20261022
    scale: float = 1.0


@dataclass
class SimulationConfig:
    start_date: str = "2026-03-01T00:00:00Z"
    duration_days: int = 90
    grid_size_km: float = 1000.0


@dataclass
class DisruptionSplit:
    weather: int = 650
    facility: int = 350


@dataclass
class TargetsConfig:
    num_shipments: int = 50000
    target_events: int = 300000
    num_facilities: int = 100
    num_disruption_windows: int = 1000
    disruption_split: DisruptionSplit = field(default_factory=DisruptionSplit)
    num_carriers: int = 12
    num_routes: int = 120


@dataclass
class ServiceLevelItem:
    id: str
    name: str
    target_hours: int
    grace_hours: float
    severely_delayed_hours: float
    weight: float


@dataclass
class AnomaliesConfig:
    event_time_ingestion_confusion: float = 0.006
    impossible_route_order: float = 0.005
    eta_uses_future_event: float = 0.005
    delivered_still_in_transit: float = 0.004


@dataclass
class PathsConfig:
    starter_dir: str = "data/starter"
    full_dir: str = "data/full"
    ground_truth_dir: str = "ground_truth"
    docs_dir: str = "docs"


@dataclass
class AppConfig:
    project: ProjectConfig = field(default_factory=ProjectConfig)
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    targets: TargetsConfig = field(default_factory=TargetsConfig)
    master_data: Dict[str, Any] = field(default_factory=dict)
    weather_types: Dict[str, Any] = field(default_factory=dict)
    ingestion_lag: Dict[str, Any] = field(default_factory=dict)
    anomalies: AnomaliesConfig = field(default_factory=AnomaliesConfig)
    eta_snapshots: Dict[str, Any] = field(default_factory=dict)
    paths: PathsConfig = field(default_factory=PathsConfig)

    def apply_scale(self, scale: float) -> None:
        """Deterministically apply scale override."""
        self.project.scale = scale
        if scale == 1.0:
            return

        # Deterministic integer scaling with sane lower bounds
        self.targets.num_shipments = max(20, int(round(50000 * scale)))
        self.targets.target_events = max(100, int(round(300000 * scale)))
        self.targets.num_facilities = max(10, min(100, int(round(100 * (scale ** 0.5)))))
        total_disruptions = max(4, int(round(1000 * scale)))
        self.targets.num_disruption_windows = total_disruptions
        weather_w = int(round(total_disruptions * 0.65))
        facility_w = total_disruptions - weather_w
        self.targets.disruption_split.weather = weather_w
        self.targets.disruption_split.facility = facility_w
        self.targets.num_routes = max(15, min(120, int(round(120 * (scale ** 0.5)))))


def find_repo_root() -> Path:
    """Find repository root by looking for requirements.txt or pyproject.toml."""
    current = Path(__file__).resolve().parent
    for p in [current, current.parent, current.parent.parent]:
        if (p / "requirements.txt").exists() or (p / "config").exists():
            return p
    return Path.cwd()


def load_config(config_path: Optional[str] = None, scale_override: Optional[float] = None) -> AppConfig:
    """Load configuration from YAML file and optionally override scale."""
    repo_root = find_repo_root()
    if config_path is None:
        target_path = repo_root / "config" / "default.yaml"
    else:
        target_path = Path(config_path)
        if not target_path.is_absolute():
            target_path = repo_root / target_path

    if not target_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    proj = ProjectConfig(**data.get("project", {}))
    sim = SimulationConfig(**data.get("simulation", {}))

    targets_data = data.get("targets", {})
    disrupt_data = targets_data.get("disruption_split", {})
    disrupt = DisruptionSplit(**disrupt_data) if disrupt_data else DisruptionSplit()
    targets_args = {k: v for k, v in targets_data.items() if k != "disruption_split"}
    targets = TargetsConfig(disruption_split=disrupt, **targets_args)

    anomalies = AnomaliesConfig(**data.get("anomalies", {}))
    paths = PathsConfig(**data.get("paths", {}))

    cfg = AppConfig(
        project=proj,
        simulation=sim,
        targets=targets,
        master_data=data.get("master_data", {}),
        weather_types=data.get("weather_types", {}),
        ingestion_lag=data.get("ingestion_lag", {}),
        anomalies=anomalies,
        eta_snapshots=data.get("eta_snapshots", {}),
        paths=paths,
    )

    if scale_override is not None:
        cfg.apply_scale(scale_override)

    return cfg
