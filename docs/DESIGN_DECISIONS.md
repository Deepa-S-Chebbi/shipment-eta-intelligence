# Key Design Decisions & Architectural Trade-offs

This document documents each fundamental design decision made in the YottaFlex AI logistics synthetic data engine, detailing the rationale, alternatives evaluated, and trade-offs incurred.

---

### Decision 1: SeedSequence Spawning vs Global RNG Seed
- **Decision**: Partition the master seed `20261022` using `numpy.random.SeedSequence(seed).spawn(N)` into dedicated child generators for each entity domain (`master_facilities`, `master_carriers`, `simulation_transit`, etc.).
- **Alternatives Considered**: Using a single global NumPy random generator (`np.random.default_rng(20261022)`).
- **Trade-off Analysis**:
  - *Global RNG*: If an engineer adds one extra facility or tweaks a carrier attribute, all subsequent random draws across the entire simulation (shipment times, event timestamps) shift completely, breaking downstream reproducibility.
  - *Spawned Streams*: Domain streams are completely decoupled. Modifying the carrier generator does NOT change the random draws for facilities or weather events.

---

### Decision 2: Ingestion-Time vs Event-Time Cutoffs (Leakage Prevention)
- **Decision**: All machine learning feature stores and ETA snapshots filter available telemetry using `event.ingestion_time <= prediction_time`.
- **Alternatives Considered**: Filtering using `event.event_time <= prediction_time`.
- **Trade-off Analysis**:
  - *Event-Time Filtering*: Models appear artificially accurate during training (low MAE) because they use scans that occurred prior to prediction time, ignoring that due to cellular dead zones or dock upload delays, those scans were NOT yet in the database. When deployed live, model performance collapses.
  - *Ingestion-Time Filtering*: Accurately reflects real-world operational latency, preventing feature leakage and providing reliable production telemetry evaluations.

---

### Decision 3: Deterministic Event Calibration vs Unbounded Generation
- **Decision**: Use a two-phase generation process: emit core physical lifecycle events, then deterministically calibrate to exactly 300,000 events (or $300,000 \times \text{scale}$) using round-robin waypoint scans and duplicate retries.
- **Alternatives Considered**: Allowing event counts to float freely based on random leg generation.
- **Trade-off Analysis**:
  - *Unbounded*: Generates variable event counts (~285,000 to ~315,000), violating hard project benchmarks.
  - *Calibrated*: Guarantees exact integer counts required by recruitment specifications while keeping event distributions physically and operationally realistic.

---

### Decision 4: Isolated Ground Truth vs In-Table Anomaly Flags
- **Decision**: All anomaly labels (`issue_type`, `injected_field`, `original_value`) reside exclusively in `ground_truth/ground_truth.csv` and `ground_truth/ground_truth.json`. Primary tables (`shipments.csv`, `tracking_events.csv`, etc.) contain zero anomaly metadata columns.
- **Alternatives Considered**: Adding an `is_anomaly` or `issue_type` column directly to `tracking_events.csv`.
- **Trade-off Analysis**:
  - *In-Table Flag*: Creates catastrophic label leakage for downstream ML models.
  - *Isolated Ground Truth*: Primary tables reflect raw real-world dirty data. Validation and audit systems join against ground truth only during quality evaluation.

---

### Decision 5: Exact Additive Delay Reconciliation
- **Decision**: Every delayed shipment decomposes its positive delay into mutually exclusive components (`WEATHER`, `FACILITY_QUEUE`, `CARRIER_DELAY`, `ROUTE_CHANGE`, `CALENDAR_CLOSURE`, `LATE_PICKUP`) that sum to total delay within $10^{-6}$ hours.
- **Alternatives Considered**: Independent heuristic delay tags without mathematical reconciliation.
- **Trade-off Analysis**:
  - *Independent Tags*: Can sum to more than 100% or less than 100% of actual observed delay, failing financial audit reconciliation.
  - *Reconciled Components*: Provides clean, audit-grade accounting for operations managers and customer SLA dispute resolution.
