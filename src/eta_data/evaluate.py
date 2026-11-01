"""
Evaluation engine for shipment ETA prediction and delay classification.

Compares:
- PLAN_BASED, PROGRESS_BASED, and CONTEXT_AWARE heuristic baselines
- A gradient-boosting model using point-in-time, leakage-safe features
- A deliberately leaky comparison model that uses event_time instead of ingestion_time

The ML train/test split is shipment-grouped and chronological by each shipment's
first prediction timestamp. All snapshots belonging to one shipment stay in
the same partition.
"""

from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.utils.class_weight import compute_sample_weight


def parse_dt(value: str) -> datetime:
    """Parse project timestamps such as 2026-03-19T22:37:07.536948Z."""
    return datetime.fromisoformat(str(value).rstrip("Z"))


def load_csv(path: Path) -> List[Dict[str, Any]]:
    """Load a CSV file. Return an empty list if it does not exist."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def build_metrics(
    y_true: np.ndarray,
    y_pred_prob: np.ndarray,
    errors: np.ndarray | None = None,
    threshold: float = 0.5,
) -> Dict[str, float]:
    """Calculate classification metrics and optional regression-error metrics."""
    y_pred = (y_pred_prob >= threshold).astype(int)

    if len(set(y_true.tolist())) > 1:
        roc_auc = float(roc_auc_score(y_true, y_pred_prob))
        pr_auc = float(average_precision_score(y_true, y_pred_prob))
    else:
        roc_auc = 0.5
        pr_auc = float(np.mean(y_true)) if len(y_true) else 0.0

    result = {
        "f1": round(float(f1_score(y_true, y_pred, zero_division=0)), 3),
        "precision": round(float(precision_score(y_true, y_pred, zero_division=0)), 3),
        "recall": round(float(recall_score(y_true, y_pred, zero_division=0)), 3),
        "roc_auc": round(roc_auc, 3),
        "pr_auc": round(pr_auc, 3),
    }

    if errors is not None and len(errors):
        abs_errors = np.abs(errors)
        result.update({
            "mae": round(float(np.mean(abs_errors)), 2),
            "p90": round(float(np.percentile(abs_errors, 90)), 2),
            "bias": round(float(np.mean(errors)), 2),
            "rmse": round(float(math.sqrt(np.mean(np.square(errors)))), 2),
        })

    return result


def classification_distribution(y: np.ndarray) -> Dict[str, Any]:
    """Return binary class counts and percentages."""
    total = len(y)
    positives = int(np.sum(y))
    negatives = total - positives
    return {
        "total": total,
        "on_time": negatives,
        "delayed": positives,
        "on_time_pct": round(100.0 * negatives / total, 2) if total else 0.0,
        "delayed_pct": round(100.0 * positives / total, 2) if total else 0.0,
    }


def threshold_metrics(
    y_true: np.ndarray,
    probabilities: np.ndarray,
    thresholds: List[float],
) -> List[Dict[str, float]]:
    """Calculate precision, recall and F1 for candidate thresholds."""
    rows = []
    for threshold in thresholds:
        predicted = (probabilities >= threshold).astype(int)
        rows.append({
            "threshold": float(threshold),
            "precision": float(precision_score(y_true, predicted, zero_division=0)),
            "recall": float(recall_score(y_true, predicted, zero_division=0)),
            "f1": float(f1_score(y_true, predicted, zero_division=0)),
        })
    return rows


def evaluate_eta_models(
    data_dir: Path,
    output_docs_dir: Path,
) -> Dict[str, Any]:
    print("=" * 70)
    print(f"EVALUATING ETA PREDICTION BASELINES & ML MODELS [{data_dir}]")
    print("=" * 70)

    shipments = load_csv(data_dir / "shipments.csv")
    eta_estimates = load_csv(data_dir / "eta_estimates.csv")
    events = load_csv(data_dir / "tracking_events.csv")
    route_changes = load_csv(data_dir / "route_changes.csv")
    service_levels = {
        row["service_level_id"]: row
        for row in load_csv(data_dir / "service_levels.csv")
    }

    img_dir = output_docs_dir / "img"
    img_dir.mkdir(parents=True, exist_ok=True)

    # Build shipment lookup and final-outcome targets.
    actual_delivery_map: Dict[str, datetime] = {}
    is_delayed_map: Dict[str, int] = {}
    shipment_obj_map: Dict[str, Dict[str, Any]] = {}

    for shipment in shipments:
        shipment_id = shipment["shipment_id"]
        shipment_obj_map[shipment_id] = shipment

        if not shipment.get("actual_delivery_at"):
            continue

        actual_delivery = parse_dt(shipment["actual_delivery_at"])
        promised_delivery = parse_dt(shipment["promised_delivery_at"])
        service_level = service_levels.get(shipment["service_level_id"], {})
        grace_hours = float(service_level.get("grace_hours", 2.0))

        actual_delivery_map[shipment_id] = actual_delivery
        delay_hours = (
            actual_delivery - promised_delivery
        ).total_seconds() / 3600.0
        is_delayed_map[shipment_id] = int(delay_hours > grace_hours)

    # Group tracking events by shipment.
    events_by_shp: Dict[str, List[Dict[str, Any]]] = {}
    for event in events:
        events_by_shp.setdefault(event["shipment_id"], []).append(event)

    # Group recorded route changes by shipment.
    # effective_time is used as the point-in-time cutoff because the supplied
    # route_changes.csv does not contain a separate ingestion timestamp.
    route_changes_by_shp: Dict[str, List[datetime]] = {}
    for change in route_changes:
        effective_time = parse_dt(change["effective_time"])
        route_changes_by_shp.setdefault(
            change["shipment_id"], []
        ).append(effective_time)

    for change_times in route_changes_by_shp.values():
        change_times.sort()

    # Build ETA snapshot records and their ground-truth targets.
    records: List[Dict[str, Any]] = []

    for eta in eta_estimates:
        shipment_id = eta["shipment_id"]
        if shipment_id not in actual_delivery_map:
            continue

        prediction_time = parse_dt(eta["prediction_time"])
        estimated_delivery = parse_dt(eta["predicted_delivery_at"])
        actual_delivery = actual_delivery_map[shipment_id]

        actual_remaining_hours = max(
            0.0,
            (actual_delivery - prediction_time).total_seconds() / 3600.0,
        )
        predicted_remaining_hours = max(
            0.0,
            (estimated_delivery - prediction_time).total_seconds() / 3600.0,
        )
        error_hours = predicted_remaining_hours - actual_remaining_hours

        shipment = shipment_obj_map[shipment_id]
        promised_delivery = parse_dt(shipment["promised_delivery_at"])
        horizon_hours = (
            promised_delivery - prediction_time
        ).total_seconds() / 3600.0

        # Do not use the shipment's final is_rerouted flag: it can describe
        # a reroute that happened after this ETA prediction.
        route_changed_by_prediction = any(
            change_time <= prediction_time
            for change_time in route_changes_by_shp.get(shipment_id, [])
        )

        records.append({
            "eta_id": eta["eta_id"],
            "shipment_id": shipment_id,
            "prediction_time": prediction_time,
            "method": eta["method"],
            "features_cutoff_time": eta.get("features_cutoff_time", ""),
            "n_events_used": int(eta.get("n_events_used", 0)),
            "pred_delay_prob": float(eta["predicted_delay_probability"]),
            "actual_remaining": actual_remaining_hours,
            "predicted_remaining": predicted_remaining_hours,
            "error_hours": error_hours,
            "abs_error_hours": abs(error_hours),
            "actual_delayed": is_delayed_map[shipment_id],
            "horizon_hours": horizon_hours,
            "route_changed_by_prediction": route_changed_by_prediction,
            "service_level_id": shipment["service_level_id"],
        })

    if not records:
        raise ValueError(
            f"No completed-shipment ETA snapshots found in {data_dir}"
        )

    # Shipment-grouped chronological split. Every snapshot from a shipment
    # remains entirely in either train or test.
    records.sort(key=lambda row: row["prediction_time"])
    n_total = len(records)

    first_prediction_by_shp: Dict[str, datetime] = {}
    for row in records:
        shipment_id = row["shipment_id"]
        prediction_time = row["prediction_time"]

        if (
            shipment_id not in first_prediction_by_shp
            or prediction_time < first_prediction_by_shp[shipment_id]
        ):
            first_prediction_by_shp[shipment_id] = prediction_time

    ordered_shipment_ids = sorted(
        first_prediction_by_shp,
        key=lambda shipment_id: first_prediction_by_shp[shipment_id],
    )

    split_idx = int(len(ordered_shipment_ids) * 0.70)
    train_shipment_ids = set(ordered_shipment_ids[:split_idx])
    test_shipment_ids = set(ordered_shipment_ids[split_idx:])

    train_records = [
        row for row in records
        if row["shipment_id"] in train_shipment_ids
    ]
    test_records = [
        row for row in records
        if row["shipment_id"] in test_shipment_ids
    ]

    assert train_shipment_ids.isdisjoint(test_shipment_ids)
    if not train_records or not test_records:
        raise ValueError(
            "The shipment-grouped split produced an empty train or test set."
        )

    # Split the training cohort again, by shipment and chronology, for threshold
    # selection. The final test cohort remains untouched during model selection.
    train_first_prediction: Dict[str, datetime] = {}
    for row in train_records:
        sid = row["shipment_id"]
        current = row["prediction_time"]
        if sid not in train_first_prediction or current < train_first_prediction[sid]:
            train_first_prediction[sid] = current

    ordered_inner_ids = sorted(
        train_first_prediction,
        key=lambda sid: train_first_prediction[sid],
    )
    inner_split_idx = int(len(ordered_inner_ids) * 0.80)
    fit_shipment_ids = set(ordered_inner_ids[:inner_split_idx])
    validation_shipment_ids = set(ordered_inner_ids[inner_split_idx:])
    fit_records = [r for r in train_records if r["shipment_id"] in fit_shipment_ids]
    validation_records = [
        r for r in train_records if r["shipment_id"] in validation_shipment_ids
    ]
    assert fit_shipment_ids.isdisjoint(validation_shipment_ids)
    assert validation_shipment_ids.isdisjoint(test_shipment_ids)
    if not fit_records or not validation_records:
        raise ValueError("Could not create non-empty shipment-grouped fit/validation sets.")

    print(f"Total Prediction Snapshots: {n_total}")
    print(
        f"Shipment-Grouped Split: "
        f"Train={len(train_records)} snapshots "
        f"({len(train_shipment_ids)} shipments), "
        f"Test={len(test_records)} snapshots "
        f"({len(test_shipment_ids)} shipments)"
    )

    # Feature extraction. Both models use the same point-in-time reroute
    # feature. Their only intended difference is event visibility:
    # safe = ingestion_time; leaky = event_time.
    def extract_features(
        recs: List[Dict[str, Any]],
        timestamp_field: str,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        features = []
        targets_reg = []
        targets_clf = []

        for row in recs:
            shipment_id = row["shipment_id"]
            prediction_time = row["prediction_time"]
            shipment_events = events_by_shp.get(shipment_id, [])

            visible_events = [
                event
                for event in shipment_events
                if parse_dt(event[timestamp_field]) <= prediction_time
            ]

            has_delay_scan = int(any(
                event["event_type"] == "DELAY_SCAN"
                for event in visible_events
            ))
            has_arrived = int(any(
                event["event_type"] in ("ARRIVED", "DELIVERED")
                for event in visible_events
            ))

            features.append([
                max(0.0, row["horizon_hours"]),
                len(visible_events),
                int(row["route_changed_by_prediction"]),
                has_delay_scan,
                has_arrived,
            ])
            targets_reg.append(row["actual_remaining"])
            targets_clf.append(row["actual_delayed"])

        return (
            np.asarray(features, dtype=float),
            np.asarray(targets_reg, dtype=float),
            np.asarray(targets_clf, dtype=int),
        )

    # 1. Leakage-safe features: events are usable only after ingestion.
    X_train_safe, y_train_reg, y_train_clf = extract_features(
        train_records, "ingestion_time"
    )
    X_test_safe, y_test_reg, y_test_clf = extract_features(
        test_records, "ingestion_time"
    )

    gb_reg_safe = HistGradientBoostingRegressor(
        random_state=20261022,
        max_iter=60,
    )
    gb_reg_safe.fit(X_train_safe, y_train_reg)
    safe_pred_remaining = gb_reg_safe.predict(X_test_safe)

    # Tune the classification threshold on the validation shipment cohort.
    X_fit_safe, _, y_fit_clf = extract_features(fit_records, "ingestion_time")
    X_validation_safe, _, y_validation_clf = extract_features(
        validation_records, "ingestion_time"
    )
    candidate_thresholds = [round(float(x), 2) for x in np.arange(0.10, 0.91, 0.05)]

    # A. Unweighted classifier: tune its threshold on validation data.
    unweighted_validation_model = HistGradientBoostingClassifier(
        random_state=20261022, max_iter=60
    )
    unweighted_validation_model.fit(X_fit_safe, y_fit_clf)
    unweighted_validation_probabilities = (
        unweighted_validation_model.predict_proba(X_validation_safe)[:, 1]
    )
    validation_threshold_results = threshold_metrics(
        y_validation_clf, unweighted_validation_probabilities, candidate_thresholds
    )
    best_threshold_row = max(
        validation_threshold_results,
        key=lambda row: (row["f1"], row["precision"], row["threshold"]),
    )
    selected_threshold = best_threshold_row["threshold"]

    # B. Class-balanced classifier: use inverse-frequency sample weights and
    # independently tune its threshold on the same validation cohort.
    fit_sample_weights = compute_sample_weight(
        class_weight="balanced", y=y_fit_clf
    )
    balanced_validation_model = HistGradientBoostingClassifier(
        random_state=20261022, max_iter=60
    )
    balanced_validation_model.fit(
        X_fit_safe, y_fit_clf, sample_weight=fit_sample_weights
    )
    balanced_validation_probabilities = (
        balanced_validation_model.predict_proba(X_validation_safe)[:, 1]
    )
    balanced_validation_threshold_results = threshold_metrics(
        y_validation_clf,
        balanced_validation_probabilities,
        candidate_thresholds,
    )
    best_balanced_threshold_row = max(
        balanced_validation_threshold_results,
        key=lambda row: (row["f1"], row["precision"], row["threshold"]),
    )
    balanced_selected_threshold = best_balanced_threshold_row["threshold"]

    # Refit both classifiers on all training shipments. Do not tune on test.
    gb_clf_safe = HistGradientBoostingClassifier(
        random_state=20261022, max_iter=60
    )
    gb_clf_safe.fit(X_train_safe, y_train_clf)
    safe_pred_probability = gb_clf_safe.predict_proba(X_test_safe)[:, 1]

    train_sample_weights = compute_sample_weight(
        class_weight="balanced", y=y_train_clf
    )
    gb_clf_balanced = HistGradientBoostingClassifier(
        random_state=20261022, max_iter=60
    )
    gb_clf_balanced.fit(
        X_train_safe, y_train_clf, sample_weight=train_sample_weights
    )
    balanced_pred_probability = (
        gb_clf_balanced.predict_proba(X_test_safe)[:, 1]
    )

    train_distribution = classification_distribution(y_train_clf)
    validation_distribution = classification_distribution(y_validation_clf)
    test_distribution = classification_distribution(y_test_clf)
    print("Binary target: DELAYED + SEVERELY_DELAYED = positive")
    for label, distribution in [
        ("Fit", classification_distribution(y_fit_clf)),
        ("Validation", validation_distribution),
        ("Train", train_distribution),
        ("Test", test_distribution),
    ]:
        print(
            f"  {label:<10} total={distribution['total']:<5} "
            f"delayed={distribution['delayed']:<5} "
            f"on_time={distribution['on_time']:<5} "
            f"delayed_pct={distribution['delayed_pct']}%"
        )
    print(
        f"Selected validation threshold: {selected_threshold:.2f} "
        f"(F1={best_threshold_row['f1']:.3f}, "
        f"precision={best_threshold_row['precision']:.3f}, "
        f"recall={best_threshold_row['recall']:.3f})"
    )

    # 2. Deliberately leaky comparison: uses physical event_time.
    X_train_leaky, _, _ = extract_features(train_records, "event_time")
    X_test_leaky, _, _ = extract_features(test_records, "event_time")

    gb_reg_leaky = HistGradientBoostingRegressor(
        random_state=20261022,
        max_iter=60,
    )
    gb_reg_leaky.fit(X_train_leaky, y_train_reg)
    leaky_pred_remaining = gb_reg_leaky.predict(X_test_leaky)

    gb_clf_leaky = HistGradientBoostingClassifier(
        random_state=20261022,
        max_iter=60,
    )
    gb_clf_leaky.fit(X_train_leaky, y_train_clf)
    leaky_pred_probability = gb_clf_leaky.predict_proba(X_test_leaky)[:, 1]

    # Evaluate heuristic baselines on the same test shipment cohort.
    eval_results: Dict[str, Dict[str, float]] = {}
    methods = ["PLAN_BASED", "PROGRESS_BASED", "CONTEXT_AWARE"]

    for method in methods:
        subset = [
            row for row in test_records
            if row["method"] == method
        ]
        if not subset:
            continue

        errors = np.asarray(
            [row["error_hours"] for row in subset],
            dtype=float,
        )
        y_true = np.asarray(
            [row["actual_delayed"] for row in subset],
            dtype=int,
        )
        probabilities = np.asarray(
            [row["pred_delay_prob"] for row in subset],
            dtype=float,
        )

        eval_results[method] = build_metrics(
            y_true,
            probabilities,
            errors,
        )

    # Evaluate safe ML model.
    safe_errors = safe_pred_remaining - y_test_reg
    safe_metrics = build_metrics(
        y_test_clf,
        safe_pred_probability,
        safe_errors,
        threshold=selected_threshold,
    )
    eval_results["ML_GRADIENT_BOOST"] = safe_metrics

    balanced_metrics = build_metrics(
        y_test_clf,
        balanced_pred_probability,
        threshold=balanced_selected_threshold,
    )

    # Evaluate deliberately leaky model.
    leaky_errors = leaky_pred_remaining - y_test_reg
    leaky_metrics = build_metrics(
        y_test_clf,
        leaky_pred_probability,
        leaky_errors,
    )
    eval_results["LEAKAGE_TRAP_EVENT_TIME"] = leaky_metrics

    model_keys = [
        "PLAN_BASED",
        "PROGRESS_BASED",
        "CONTEXT_AWARE",
        "ML_GRADIENT_BOOST",
        "LEAKAGE_TRAP_EVENT_TIME",
    ]
    missing_models = [key for key in model_keys if key not in eval_results]
    if missing_models:
        raise ValueError(
            "Evaluation could not calculate results for: "
            + ", ".join(missing_models)
        )

    # Chart 1: MAE comparison.
    model_labels = [
        "Plan-Based",
        "Progress-Based",
        "Context-Aware",
        "GBoost (Safe)",
        "Leakage Trap (Leaky)",
    ]
    maes = [eval_results[key]["mae"] for key in model_keys]

    fig, ax = plt.subplots(figsize=(8.5, 5))
    colors = ["#94a3b8", "#38bdf8", "#0284c7", "#10b981", "#ef4444"]
    bars = ax.bar(
        model_labels,
        maes,
        color=colors,
        edgecolor="#1e293b",
        linewidth=1.2,
    )
    ax.set_ylabel("Mean Absolute Error (Hours)", fontsize=11, fontweight="bold")
    ax.set_title(
        "ETA Prediction MAE Across Models & The Leakage Trap",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    for bar, value in zip(bars, maes):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.15,
            f"{value}h",
            ha="center",
            va="bottom",
            fontweight="bold",
        )

    plt.xticks(rotation=15, ha="right", fontsize=9.5)
    plt.tight_layout()
    chart1_path = img_dir / "eta_mae_by_method.png"
    plt.savefig(chart1_path, dpi=200)
    plt.close()

    # Chart 2: heuristic baseline MAE by prediction horizon.
    horizon_bins = [
        (0.0, 8.0, "T-6h Arrival"),
        (8.0, 16.0, "T-12h Approach"),
        (16.0, 30.0, "T-24h Dispatch"),
        (30.0, 100.0, "T-48h+ Early"),
    ]
    bin_labels = [item[2] for item in horizon_bins]

    horizon_curves: Dict[str, List[float]] = {
        "PLAN_BASED": [],
        "PROGRESS_BASED": [],
        "CONTEXT_AWARE": [],
    }

    for low, high, _ in horizon_bins:
        for method in horizon_curves:
            errors = [
                row["abs_error_hours"]
                for row in test_records
                if row["method"] == method
                and low <= row["horizon_hours"] < high
            ]
            fallback = eval_results[method]["mae"]
            horizon_curves[method].append(
                float(np.mean(errors)) if errors else fallback
            )

    fig, ax = plt.subplots(figsize=(8.5, 5))
    x_indices = np.arange(len(bin_labels))
    ax.plot(
        x_indices,
        horizon_curves["PLAN_BASED"],
        marker="o",
        label="Plan-Based",
        color="#94a3b8",
        linewidth=2,
    )
    ax.plot(
        x_indices,
        horizon_curves["PROGRESS_BASED"],
        marker="s",
        label="Progress-Based",
        color="#38bdf8",
        linewidth=2,
    )
    ax.plot(
        x_indices,
        horizon_curves["CONTEXT_AWARE"],
        marker="^",
        label="Context-Aware",
        color="#0284c7",
        linewidth=2.5,
    )
    ax.set_xticks(x_indices)
    ax.set_xticklabels(bin_labels, fontsize=9.5)
    ax.set_xlabel(
        "Operational Prediction Horizon Before Promised Delivery",
        fontsize=11,
        fontweight="bold",
    )
    ax.set_ylabel("Actual Test MAE (Hours)", fontsize=11, fontweight="bold")
    ax.set_title(
        "Real Horizon Error Curve Across Prediction Checkpoints",
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.legend(frameon=True)
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    chart2_path = img_dir / "horizon_error_curve.png"
    plt.savefig(chart2_path, dpi=200)
    plt.close()

    # Generate docs/EVALUATION.md from the metrics calculated above.
    eval_doc = output_docs_dir / "EVALUATION.md"
    doc_lines = [
        "# Model Evaluation: ETA Prediction & Delay Classification",
        "",
        (
            "This evaluation uses a **shipment-grouped chronological split**. "
            "All snapshots from a shipment are kept in one partition, and "
            "shipment cohorts are ordered by their first prediction timestamp."
        ),
        "",
        "The route-change feature is point-in-time: a recorded route change is "
        "included only when its `effective_time` is at or before the prediction "
        "timestamp. The route-change CSV does not provide a separate ingestion "
        "timestamp, so this evaluation assumes the change is available at its "
        "effective time.",
        "",
        "---",
        "",
        "## 1. Primary Benchmark Results",
        "",
        "| Model / Baseline | MAE (h) | P90 Error (h) | Bias (h) | Delay F1 | Precision | Recall | ROC-AUC |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for key in model_keys:
        result = eval_results[key]
        name = key.replace("_", " ").title()
        if key == "LEAKAGE_TRAP_EVENT_TIME":
            name = "Leakage Trap (`event_time` peek)"
        doc_lines.append(
            f"| {name} | {result['mae']} | {result['p90']} | "
            f"{result['bias']} | {result['f1']} | "
            f"{result['precision']} | {result['recall']} | "
            f"{result['roc_auc']} |"
        )

    doc_lines.extend([
        "",
        "---",
        "",
        "## 2. Key Findings",
        "",
        "### Baseline and ML Performance",
        (
            f"- Plan-Based MAE: **{eval_results['PLAN_BASED']['mae']}h**."
        ),
        (
            f"- Progress-Based MAE: **{eval_results['PROGRESS_BASED']['mae']}h**."
        ),
        (
            f"- Context-Aware MAE: **{eval_results['CONTEXT_AWARE']['mae']}h**, "
            f"Delay ROC-AUC: **{eval_results['CONTEXT_AWARE']['roc_auc']}**."
        ),
        (
            f"- Leakage-safe Gradient Boosting MAE: "
            f"**{eval_results['ML_GRADIENT_BOOST']['mae']}h**, "
            f"ROC-AUC: **{eval_results['ML_GRADIENT_BOOST']['roc_auc']}**."
        ),
        "",
        "### Event-Time Leakage Comparison",
        (
            "- Physical events can occur before they are ingested into the "
            "system. A prediction made before ingestion must not use that event."
        ),
        (
            "- The safe model filters events using "
            "`ingestion_time <= prediction_time`."
        ),
        (
            "- The deliberately leaky comparison filters events using "
            "`event_time <= prediction_time`, which can expose events that "
            "were not yet available to the prediction system."
        ),
        (
            f"- Leakage-trap MAE: "
            f"**{eval_results['LEAKAGE_TRAP_EVENT_TIME']['mae']}h**, "
            f"ROC-AUC: **{eval_results['LEAKAGE_TRAP_EVENT_TIME']['roc_auc']}**. "
            "The measured difference is dataset-dependent; leakage does not "
            "guarantee a particular metric improvement."
        ),
        "",
        "---",
        "",
        "## 3. Classification Threshold Tuning",
        "",
        f"- Threshold selected on validation data: **{selected_threshold:.2f}**.",
        (
            f"- Validation F1: **{best_threshold_row['f1']:.3f}**, "
            f"precision: **{best_threshold_row['precision']:.3f}**, "
            f"recall: **{best_threshold_row['recall']:.3f}**."
        ),
        "- The final test shipment cohort was not used to select the threshold.",
        "",
        "| Threshold | Validation Precision | Validation Recall | Validation F1 |",
        "|---:|---:|---:|---:|",
        *[
            f"| {row['threshold']:.2f} | {row['precision']:.3f} | "
            f"{row['recall']:.3f} | {row['f1']:.3f} |"
            for row in validation_threshold_results
        ],
        "",
        "## 4. Class-Weighting Experiment",
        "",
        (
            "The unweighted and class-balanced classifiers use identical "
            "shipment-grouped fit, validation, and test partitions. Each "
            "classifier selects its own threshold using validation F1. "
            "Inverse-frequency sample weights are applied only during fitting; "
            "the final test cohort is not used for model or threshold selection."
        ),
        "",
        "| Classifier | Validation threshold | Validation F1 | Test precision | Test recall | Test F1 | Test PR-AUC | Test ROC-AUC |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        (
            f"| Unweighted | {selected_threshold:.2f} | "
            f"{best_threshold_row['f1']:.3f} | {safe_metrics['precision']:.3f} | "
            f"{safe_metrics['recall']:.3f} | {safe_metrics['f1']:.3f} | "
            f"{safe_metrics['pr_auc']:.3f} | {safe_metrics['roc_auc']:.3f} |"
        ),
        (
            f"| Class-balanced | {balanced_selected_threshold:.2f} | "
            f"{best_balanced_threshold_row['f1']:.3f} | "
            f"{balanced_metrics['precision']:.3f} | "
            f"{balanced_metrics['recall']:.3f} | "
            f"{balanced_metrics['f1']:.3f} | "
            f"{balanced_metrics['pr_auc']:.3f} | "
            f"{balanced_metrics['roc_auc']:.3f} |"
        ),
        "",
        "## 5. Visualizations",
        "",
        f"![ETA MAE Comparison](img/{chart1_path.name})",
        "",
        f"![Horizon Error Curve](img/{chart2_path.name})",
    ])

    with eval_doc.open("w", newline="\n", encoding="utf-8") as file:
        file.write("\n".join(doc_lines))

    print("\nVALIDATION THRESHOLD SWEEP")
    print("threshold | precision | recall | f1")
    for row in validation_threshold_results:
        print(
            f"{row['threshold']:.2f}      | {row['precision']:.3f}     | "
            f"{row['recall']:.3f}  | {row['f1']:.3f}"
        )
    print(f"Selected validation threshold: {selected_threshold:.2f}")

    print("\nCLASS-WEIGHTING EXPERIMENT")
    print("Classifier     | Val threshold | Val F1 | Test precision | Test recall | Test F1 | PR-AUC | ROC-AUC")
    print(
        f"Unweighted     | {selected_threshold:>13.2f} | "
        f"{best_threshold_row['f1']:.3f}  | {safe_metrics['precision']:.3f}          | "
        f"{safe_metrics['recall']:.3f}       | {safe_metrics['f1']:.3f}  | "
        f"{safe_metrics['pr_auc']:.3f}  | {safe_metrics['roc_auc']:.3f}"
    )
    print(
        f"Class-balanced | {balanced_selected_threshold:>13.2f} | "
        f"{best_balanced_threshold_row['f1']:.3f}  | "
        f"{balanced_metrics['precision']:.3f}          | "
        f"{balanced_metrics['recall']:.3f}       | "
        f"{balanced_metrics['f1']:.3f}  | "
        f"{balanced_metrics['pr_auc']:.3f}  | "
        f"{balanced_metrics['roc_auc']:.3f}"
    )

    print("\n" + "=" * 70)
    print("EVALUATION METRICS TABLE")
    print("=" * 70)
    for key, result in eval_results.items():
        print(
            f"{key:<25} MAE: {result['mae']:<5}h | "
            f"P90: {result['p90']:<5}h | "
            f"F1: {result['f1']:<5} | AUC: {result['roc_auc']}"
        )
    print("=" * 70)
    print(f"Evaluation report written to: {eval_doc}")
    print(f"Charts saved to: {img_dir}")

    return eval_results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare ETA prediction models with and without class weighting"
    )
    parser.add_argument(
        "--data",
        default="data/starter",
        help="Path to dataset directory",
    )
    parser.add_argument(
        "--docs",
        default="docs",
        help="Path to documentation output directory",
    )
    args = parser.parse_args()

    data_dir = Path(args.data).resolve()
    docs_dir = Path(args.docs).resolve()

    evaluate_eta_models(data_dir, docs_dir)


if __name__ == "__main__":
    main()
