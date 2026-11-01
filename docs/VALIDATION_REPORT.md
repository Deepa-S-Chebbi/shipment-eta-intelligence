# YottaFlex Logistics Synthetic Dataset: Formal Validation Report

**Execution Timestamp**: 2026-11-01T13:33:49.093134+00:00  
**Validation Status**: PASSED (ALL SUITES GREEN)  
**Total Tables Verified**: 19  
**Total Injected Anomalies Audited**: 67  

---

## 1. Summary of Integrity Test Suites

| Suite Name | Category | Status | Violations | Labelled Anomalies Detected | Summary Details |
|---|---|---|---|---|---|
| Primary Key Uniqueness | RELATIONAL_INTEGRITY | PASS | 0 | 0 | Checked 14492 PKs across 19 tables. Duplicates found: 0 |
| Foreign Key Integrity | RELATIONAL_INTEGRITY | PASS | 0 | 0 | Validated 16 FK relationships. Orphan references found: 0 |
| ID Format Patterns | SCHEMA_CONFORMANCE | PASS | 0 | 0 | Validated zero-padded ID regex patterns. Malformed IDs: 0 |
| Enum Domain Constraints | SCHEMA_CONFORMANCE | PASS | 0 | 0 | Validated enum domains across modes, regions, and statuses. Violations: 0 |
| Temporal & Chronological Ordering | TEMPORAL_INTEGRITY | PASS | 0 | 24 | Unlabelled temporal order violations: 0. Labelled anomalies detected: 20 time confusion, 4 route sequence. |
| Delay Reason Arithmetic Reconciliation | MATHEMATICAL_INTEGRITY | PASS | 0 | 0 | Reconciled delay components vs total delay. Discrepancies: 0 |
| State Machine Lifecycle Integrity | STATE_MACHINE | PASS | 0 | 2 | Validated state transitions. Unlabelled state violations: 0. Labelled anomalies detected: 2. |
| Duplicate Tracking Event Pointers | RELATIONAL_INTEGRITY | PASS | 0 | 0 | Validated duplicate scan references. Broken duplicate pointers: 0 |
| Delay Label Rule Consistency | BUSINESS_LOGIC | PASS | 0 | 0 | Independently recomputed SLA labels from timestamps. Mismatches: 0 |
| ETA Prediction-Time Leakage Safety | ML_DATA_LEAKAGE | PASS | 0 | 41 | Unlabelled feature leakage violations: 0. Labelled future-peek anomalies detected: 41. |
| Labelled Anomaly Accounting | DATA_QUALITY_AUDIT | PASS | 0 | 67 | Total injected anomalies in ground truth: 67. All 4 required anomaly classes present: True. |
| Distribution & Sanity Bounds | DISTRIBUTION | PASS | 0 | 0 | Events/shipment: 6.0 (target 5-10). On-time rate: 84.4%. Duplicate rate: 0.3% (10 dups). Delayed: 69 vs Severe: 9. |

---

## 2. Anomaly Detection Accounting (Precision & Recall)

The data validator audits 100% of injected edge cases recorded in `ground_truth/` and verifies that no unlabelled corruption exists in the primary dataset.

| Injected Anomaly Code | Target Table | Injected Count | Detected by Validator | Precision | Recall |
|---|---|---|---|---|---|
| `EVENT_TIME_INGESTION_CONFUSION` | `TrackingEvent` | 20 | 20 | 100.0% | 100.0% |
| `IMPOSSIBLE_ROUTE_ORDER` | `ShipmentLeg` | 4 | 4 | 100.0% | 100.0% |
| `ETA_USES_FUTURE_EVENT` | `ETAEstimate` | 41 | 41 | 100.0% | 100.0% |
| `DELIVERED_STILL_IN_TRANSIT` | `Shipment` | 2 | 2 | 100.0% | 100.0% |

---

## 3. Certification

All relational foreign keys, zero-padded ID regex rules, date orderings, arithmetic reconciliations, and leakage-safe prediction constraints are fully verified and conform strictly to the YottaFlex AI specification.