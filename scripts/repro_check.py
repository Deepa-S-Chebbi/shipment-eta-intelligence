#!/usr/bin/env python
"""
Two-run reproducibility check script.
Executes the generator pipeline twice into separate directories from the same master seed,
and verifies 100% bit-for-bit SHA-256 and row-count identity across all exported files.
Generates docs/REPRODUCIBILITY.md.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(root_dir / "src"))

from scripts.generate import run_pipeline


def run_reproducibility_check(scale: float = 0.01) -> bool:
    print("=" * 70)
    print("YOTTAFLEX REPRODUCIBILITY VERIFICATION")
    print(f"Master Seed: 20261022 | Scale: {scale}")
    print("=" * 70)

    repro1_dir = root_dir / "data" / "repro_1"
    repro2_dir = root_dir / "data" / "repro_2"
    gt1_dir = root_dir / "data" / "gt_repro_1"
    gt2_dir = root_dir / "data" / "gt_repro_2"

    for p in [repro1_dir, repro2_dir, gt1_dir, gt2_dir]:
        if p.exists():
            shutil.rmtree(p)

    print("\n>>> Executing Run 1...")
    t0 = time.time()
    code1 = run_pipeline(
        config_path="config/starter.yaml",
        out_dir_str=str(repro1_dir),
        scale_override=scale,
        ground_truth_dir_str=str(gt1_dir),
        run_validation=False,
    )
    t_run1 = time.time() - t0
    if code1 != 0:
        print("Run 1 failed!")
        return False

    print("\n>>> Executing Run 2 (Independent Execution from Same Seed)...")
    t0 = time.time()
    code2 = run_pipeline(
        config_path="config/starter.yaml",
        out_dir_str=str(repro2_dir),
        scale_override=scale,
        ground_truth_dir_str=str(gt2_dir),
        run_validation=False,
    )
    t_run2 = time.time() - t0
    if code2 != 0:
        print("Run 2 failed!")
        return False

    # Compare manifests
    with open(repro1_dir / "manifest.json", "r", encoding="utf-8") as f:
        m1 = json.load(f)
    with open(repro2_dir / "manifest.json", "r", encoding="utf-8") as f:
        m2 = json.load(f)

    files1 = {f["name"]: f for f in m1["files"]}
    files2 = {f["name"]: f for f in m2["files"]}

    all_file_names = sorted(list(set(files1.keys()) | set(files2.keys())))

    comparisons = []
    all_match = True

    for fname in all_file_names:
        f1 = files1.get(fname)
        f2 = files2.get(fname)

        if not f1 or not f2:
            comparisons.append({
                "name": fname,
                "rows_1": f1["row_count"] if f1 else None,
                "rows_2": f2["row_count"] if f2 else None,
                "sha1": f1["sha256"] if f1 else None,
                "sha256_match": False,
                "status": "MISSING_IN_ONE_RUN",
            })
            all_match = False
            continue

        rows_match = f1["row_count"] == f2["row_count"]
        # Compare sha256
        sha_match = f1["sha256"] == f2["sha256"]

        if not (rows_match and sha_match):
            all_match = False

        comparisons.append({
            "name": fname,
            "rows_1": f1["row_count"],
            "rows_2": f2["row_count"],
            "sha1": f1["sha256"],
            "sha2": f2["sha256"],
            "sha256_match": sha_match,
            "status": "IDENTICAL" if (rows_match and sha_match) else "MISMATCH",
        })

    # Generate docs/REPRODUCIBILITY.md
    docs_dir = root_dir / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    repro_doc = docs_dir / "REPRODUCIBILITY.md"

    doc_lines = [
        "# Reproducibility Verification Report",
        "",
        f"**Audit Timestamp**: {datetime.now(timezone.utc).isoformat()}  ",
        f"**Master Seed**: `20261022`  ",
        f"**Scale**: `{scale}`  ",
        f"**Run 1 Execution Time**: {t_run1:.2f}s  ",
        f"**Run 2 Execution Time**: {t_run2:.2f}s  ",
        f"**Overall Status**: {'BIT-FOR-BIT IDENTICAL (100% REPRODUCIBLE)' if all_match else 'FAILED'}  ",
        "",
        "---",
        "",
        "## Dual-Run Bitwise Comparison",
        "",
        "| File Name | Run 1 Rows | Run 2 Rows | SHA-256 Checksum (Run 1) | SHA-256 Match | Verification Status |",
        "|---|---|---|---|---|---|",
    ]

    for c in comparisons:
        match_str = "MATCH" if c["sha256_match"] else "**MISMATCH**"
        doc_lines.append(
            f"| `{c['name']}` | {c['rows_1']} | {c['rows_2']} | `{c['sha1'][:16]}...` | {match_str} | {c['status']} |"
        )

    doc_lines.extend([
        "",
        "---",
        "",
        "## Technical Safeguards for Determinism",
        "",
        "1. **Independent RNG Streams**: Master seed `20261022` is partitioned using `numpy.random.SeedSequence.spawn`, ensuring modifications to one entity generator never shuffle the random trajectory of others.",
        "2. **Zero System-Clock Dependencies**: No non-deterministic `datetime.now()` calls exist in generation logic. Timestamps derive from a static epoch (`2026-03-01T00:00:00Z`).",
        "3. **Stable Sorting**: Tables are explicitly sorted across composite primary keys prior to export, preventing unordered dictionary/set nondeterminism across runs or platforms.",
        "4. **No Python hash() Iteration**: Set lookups avoid Python's randomized hash seed (`PYTHONHASHSEED`).",
    ])

    with open(repro_doc, "w", encoding="utf-8") as f:
        f.write("\n".join(doc_lines))

    # Print summary table
    print("\n" + "=" * 70)
    print("REPRODUCIBILITY RESULTS TABLE")
    print("=" * 70)
    for c in comparisons:
        st = "[MATCH]" if c["sha256_match"] else "[FAIL]"
        print(f"{st:<8} {c['name']:<28} Rows: {c['rows_1']:<6} SHA: {c['sha1'][:12]}...")
    print("=" * 70)
    print(f"Overall Result: {'100% BIT-FOR-BIT IDENTICAL' if all_match else 'VERIFICATION FAILED'}")
    print(f"Report written to: {repro_doc}")

    # Clean up test directories
    for p in [repro1_dir, repro2_dir, gt1_dir, gt2_dir]:
        shutil.rmtree(p, ignore_errors=True)

    return all_match


def main() -> None:
    parser = argparse.ArgumentParser(description="Reproducibility check")
    parser.add_argument("--scale", type=float, default=0.01, help="Scale for reproducibility check")
    args = parser.parse_args()

    success = run_reproducibility_check(args.scale)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
