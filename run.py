#!/usr/bin/env python
"""
Cross-platform target runner for YottaFlex AI Synthetic Logistics Project.
Provides standard targets equivalent to Makefile:
  python run.py install
  python run.py starter
  python run.py full
  python run.py validate
  python run.py repro
  python run.py test
  python run.py eval
  python run.py dashboard
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

PYTHON = sys.executable
ROOT = Path(__file__).resolve().parent


def run_cmd(cmd: list[str], env: dict[str, str] | None = None) -> int:
    """Execute a command synchronously with streamed output."""
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    # Ensure src is in PYTHONPATH
    src_dir = str(ROOT / "src")
    if "PYTHONPATH" in full_env:
        full_env["PYTHONPATH"] = f"{src_dir}{os.path.pathsep}{full_env['PYTHONPATH']}"
    else:
        full_env["PYTHONPATH"] = src_dir

    print(f"\n>>> Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT), env=full_env)
    return result.returncode


def target_install() -> int:
    print("Installing core and dashboard dependencies...")
    code = run_cmd([PYTHON, "-m", "pip", "install", "-r", "requirements.txt"])
    if code != 0:
        return code
    return run_cmd([PYTHON, "-m", "pip", "install", "-r", "requirements-dashboard.txt"])


def target_starter() -> int:
    print("Generating starter dataset (scale=0.01)...")
    return run_cmd([
        PYTHON, "scripts/generate.py",
        "--config", "config/starter.yaml",
        "--out", "data/starter",
        "--scale", "0.01",
    ])


def target_full() -> int:
    print("Generating full dataset (scale=1.0)...")
    return run_cmd([
        PYTHON, "scripts/generate.py",
        "--config", "config/default.yaml",
        "--out", "data/full",
        "--scale", "1.0",
    ])


def target_validate(data_dir: str = "data/starter") -> int:
    print(f"Validating dataset in {data_dir}...")
    return run_cmd([PYTHON, "-m", "eta_data.validate", "--data", data_dir])


def target_repro(scale: float = 0.01) -> int:
    print(f"Running reproducibility check (scale={scale})...")
    return run_cmd([PYTHON, "scripts/repro_check.py", "--scale", str(scale)])


def target_test() -> int:
    print("Running pytest test suite...")
    return run_cmd([PYTHON, "-m", "pytest", "tests/", "-v"])


def target_eval(data_dir: str = "data/starter") -> int:
    print(f"Running temporal ETA evaluation and baseline models on {data_dir}...")
    return run_cmd([PYTHON, "-m", "eta_data.evaluate", "--data", data_dir])


def target_dashboard() -> int:
    print("Launching Streamlit dashboard...")
    return run_cmd(["streamlit", "run", "dashboard/app.py"])


def target_clean() -> int:
    print("Cleaning temporary datasets and caches...")
    paths_to_remove = [
        ROOT / "data" / "full",
        ROOT / "data" / "repro_1",
        ROOT / "data" / "repro_2",
        ROOT / ".pytest_cache",
    ]
    for p in paths_to_remove:
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            print(f"Removed {p}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="YottaFlex Logistics Project Target Runner")
    parser.add_argument(
        "target",
        choices=["install", "starter", "full", "validate", "repro", "test", "eval", "dashboard", "clean"],
        nargs="?",
        default="starter",
        help="Target to execute",
    )
    parser.add_argument("--data", default="data/starter", help="Path to data directory for validate/eval")
    parser.add_argument("--scale", type=float, default=0.01, help="Scale factor for repro check")

    args = parser.parse_args()

    targets = {
        "install": target_install,
        "starter": target_starter,
        "full": target_full,
        "validate": lambda: target_validate(args.data),
        "repro": lambda: target_repro(args.scale),
        "test": target_test,
        "eval": lambda: target_eval(args.data),
        "dashboard": target_dashboard,
        "clean": target_clean,
    }

    exit_code = targets[args.target]()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
