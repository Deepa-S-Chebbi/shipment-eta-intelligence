import tempfile
import json
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))

from scripts.generate import run_pipeline
from eta_data.config import load_config


def test_in_process_dual_generation_reproducibility():
    """Generates dataset twice from scratch and verifies matching SHA-256 checksums."""
    with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
        dir1 = Path(tmp1) / "out1"
        gt1 = Path(tmp1) / "gt1"
        dir2 = Path(tmp2) / "out2"
        gt2 = Path(tmp2) / "gt2"

        # Run 1
        res1 = run_pipeline(
            config_path="config/starter.yaml",
            out_dir_str=str(dir1),
            scale_override=0.01,
            ground_truth_dir_str=str(gt1),
            run_validation=False,
        )
        assert res1 == 0

        # Run 2
        res2 = run_pipeline(
            config_path="config/starter.yaml",
            out_dir_str=str(dir2),
            scale_override=0.01,
            ground_truth_dir_str=str(gt2),
            run_validation=False,
        )
        assert res2 == 0

        # Compare manifest files
        with open(dir1 / "manifest.json", "r", encoding="utf-8") as f:
            m1 = json.load(f)
        with open(dir2 / "manifest.json", "r", encoding="utf-8") as f:
            m2 = json.load(f)

        files1 = {f["name"]: f for f in m1["files"]}
        files2 = {f["name"]: f for f in m2["files"]}

        assert set(files1.keys()) == set(files2.keys())

        for name in files1:
            f1 = files1[name]
            f2 = files2[name]
            assert f1["row_count"] == f2["row_count"], f"Row count mismatch in {name}"
            assert f1["sha256"] == f2["sha256"], f"SHA256 mismatch in {name}"
