# Real-Time Shipment Tracking & Delay Intelligence

An end-to-end synthetic logistics data platform for shipment tracking, multi-leg route simulation, ETA prediction, delay detection, disruption analysis, and data quality validation.

Built to simulate real-world logistics operations by combining carrier events, route plans, weather disruptions, facility queues, and shipment lifecycle information to estimate delivery times and identify potential delays.

## 1. Project Overview

Logistics operations depend on accurate shipment tracking and timely delivery predictions. However, carrier events may arrive late, routes may change, and weather or facility disruptions can affect delivery schedules.

This project simulates an end-to-end logistics workflow that:

- Generates synthetic shipment and logistics master data.
- Simulates multi-leg shipment journeys.
- Generates tracking events with event time and ingestion time.
- Models weather and facility disruptions.
- Calculates actual delivery outcomes and delay labels.
- Generates point-in-time ETA prediction snapshots.
- Detects data anomalies and temporal leakage.
- Evaluates ETA and delay-prediction approaches.
- Exports validated datasets into CSV, JSON, SQL, and SQLite formats.

**Project details**

- Domain: Logistics, Supply Chain, ETA Prediction
- Data provenance: 100% synthetic
- Programming language: Python
- Database: SQLite
- Machine Learning: scikit-learn
- Visualization: Streamlit, Matplotlib
- Testing: pytest

## 2. Full-Scale Synthetic Data Generation

The generator supports starter and full-scale configurations using a fixed random seed.

### Full-scale generation results

| Entity / Output | Generated records |
|---|---:|
| Shipments | 50,000 |
| Tracking events | 300,000 |
| Facilities | 100 |
| Disruption windows | 1,000 |
| Shipment legs | 92,291 |
| ETA snapshots | 750,123 |
| Ground-truth anomalies | 5,737 |
| Delay reason attributions | 162,858 |
| Exported files | 23 |

**Generation configuration**

- Master seed: `20261022`
- Full-scale multiplier: `1.0`
- Starter configuration: `config/starter.yaml`
- Full-scale configuration: `config/default.yaml`

The generator uses deterministic random-number streams to maintain reproducible outputs.

### Reproducibility verification

The full-scale generator was executed twice independently using the same master seed and scale.

Verification results:

- 50,000 shipments generated in each run.
- 300,000 tracking events generated in each run.
- 100 facilities generated in each run.
- 1,000 disruption windows generated in each run.
- All 23 exported files had matching row counts and SHA-256 checksums.
- CSV, JSON, SQLite, and SQL outputs were compared.

**Result: 100% bit-for-bit identical across both full-scale runs.**

See [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md) for the generated verification report.

## 3. Key Features

### Synthetic Logistics Data Generation

- Generates shipments, shipment legs, carriers, facilities, routes, and tracking events.
- Supports configurable starter and full-scale datasets.
- Uses deterministic identifiers and seeded random-number generation.
- Models carrier and facility operating calendars.
- Generates weather and facility disruption windows.
- Exports relational datasets into CSV, JSON, SQL, and SQLite.

### Multi-Leg Shipment Simulation

- Simulates multi-hop shipment journeys.
- Models carrier travel-time variation.
- Supports dynamic route changes and rerouting.
- Models facility waiting times and operating-hour constraints.
- Tracks shipment lifecycle transitions.
- Calculates actual delivery outcomes.

### Point-in-Time ETA Prediction

- Generates ETA snapshots at defined prediction times.
- Separates event time from ingestion time.
- Restricts tracking information to events available at prediction time.
- Incorporates route progress, weather disruptions, facility queues, and operational context.
- Evaluates ETA prediction accuracy using historical simulation outcomes.

### Delay Detection and Attribution

- Derives delivery delay labels from actual delivery outcomes and service-level rules.
- Identifies contributing delay reasons.
- Reconciles delay attribution against calculated delivery delays.
- Supports delay classification and operational analysis.

### Data Quality and Anomaly Detection

Includes four required anomaly categories:

1. Event ingestion time confused with event time.
2. Impossible route order.
3. ETA using future event data.
4. Delivered shipment still marked in transit.

Anomaly labels are maintained separately in the ground-truth outputs rather than being silently mixed into ordinary model input features.

## 4. Data Model and Database Design

The project models the logistics workflow through related entities.

Core entities include:

- Shipment
- ShipmentLeg
- Carrier
- Route
- TrackingEvent
- Facility
- FacilityQueue
- WeatherEvent
- ServiceLevel
- ETAEstimate
- DelayReason

Additional relationship and history tables support:

- Shipment delay reason attribution.
- Shipment status history.
- Carrier and facility calendars.
- Weather-event-to-facility relationships.
- Weather-event-to-shipment-leg relationships.
- Route changes and route-leg templates.

The relational model uses primary keys, foreign keys, and defined entity relationships to maintain referential integrity.

Documentation:

- [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md)
- [`docs/ER_DIAGRAM.md`](docs/ER_DIAGRAM.md)
- [`docs/BUSINESS_RULES.md`](docs/BUSINESS_RULES.md)
- [`docs/ASSUMPTIONS.md`](docs/ASSUMPTIONS.md)

## 5. Temporal Data Integrity and Leakage Prevention

A tracking event has two important timestamps:

- `event_time`: When the physical shipment event occurred.
- `ingestion_time`: When the event became available to the system.

For example:

- A shipment is scanned at 10:00.
- The scan reaches the database at 13:00.
- An ETA prediction generated at 11:00 must not use that scan.

The project enforces the point-in-time availability rule:

```python
event.ingestion_time <= prediction_time
```

This prevents future information from entering prediction features.

The project also includes a deliberately leaky event-time comparison to demonstrate the impact of incorrect temporal feature construction.

## 6. ETA and Delay Prediction Evaluation

The starter evaluation compares multiple prediction approaches:

- Plan-based prediction.
- Progress-based prediction.
- Context-aware prediction.
- Machine-learning Gradient Boosting.
- An intentionally leaky event-time comparison.

The evaluation uses shipment-grouped train/test splitting to prevent snapshots from the same shipment from appearing in both training and testing partitions.

### Latest documented starter evaluation

The evaluation covers 7,215 prediction snapshots.

| Model | MAE (hours) | P90 Error (hours) | Delay F1 | ROC-AUC |
|---|---:|---:|---:|---:|
| Plan-based | 4.92 | 11.1 | 0.000 | 0.554 |
| Progress-based | 5.40 | 18.2 | 0.312 | 0.650 |
| Context-aware | 5.34 | 18.2 | 0.312 | 0.667 |
| ML Gradient Boost | **4.31** | **8.56** | 0.295 | 0.605 |
| Leakage trap using event time | 4.28 | 8.62 | 0.233 | 0.626 |

The ML Gradient Boost model achieved the lowest MAE among the leakage-safe approaches in this evaluation.

The event-time leakage result is included for comparison only and is not considered a valid production prediction approach.

### Class imbalance experiment

| Metric | Unweighted | Class-balanced |
|---|---:|---:|
| Validation threshold | 0.20 | 0.40 |
| Validation F1 | 0.265 | 0.255 |
| Test precision | 0.298 | 0.193 |
| Test recall | 0.291 | **0.732** |
| Test F1 | 0.295 | **0.305** |
| Test PR-AUC | 0.303 | **0.306** |
| Test ROC-AUC | 0.605 | **0.611** |

Class weighting improved recall and F1 slightly while increasing false-positive delay alerts.

The appropriate operating point depends on the business cost of missed delays versus unnecessary alerts.

Full evaluation details and charts:

- [`docs/EVALUATION.md`](docs/EVALUATION.md)
- [`docs/img/`](docs/img/)

## 7. Validation and Testing

The project includes automated validation and testing for data quality and consistency.

Validation areas include:

- Primary-key uniqueness.
- Foreign-key integrity.
- Allowed enumeration values.
- Date and timestamp ordering.
- Duplicate event checks.
- Shipment lifecycle transitions.
- Delay-label consistency.
- Temporal leakage prevention.
- Anomaly isolation.
- Data reconciliation.

The previously documented test run completed with:

```text
25 passed
```

The project also includes 12 validation suites.

Run validation:

```powershell
python run.py validate
```

Run automated tests:

```powershell
python run.py test
```

Validation documentation:

[`docs/VALIDATION_REPORT.md`](docs/VALIDATION_REPORT.md)

## 8. Project Structure

```text
shipment-eta-delay-simulator/
│
├── config/
│   ├── default.yaml
│   └── starter.yaml
│
├── data/
│   ├── starter/
│   └── full/
│
├── dashboard/
│   └── app.py
│
├── docs/
│   ├── ASSUMPTIONS.md
│   ├── BUSINESS_RULES.md
│   ├── DATA_DICTIONARY.md
│   ├── DESIGN_DECISIONS.md
│   ├── EVALUATION.md
│   ├── ER_DIAGRAM.md
│   ├── REPRODUCIBILITY.md
│   └── VALIDATION_REPORT.md
│
├── ground_truth/
│
├── scripts/
│   ├── generate.py
│   └── repro_check.py
│
├── src/
│   └── eta_data/
│       ├── master/
│       ├── transactions/
│       ├── anomalies.py
│       ├── eta.py
│       ├── evaluate.py
│       ├── export.py
│       ├── labels.py
│       └── validate.py
│
├── tests/
├── requirements.txt
├── run.py
└── README.md
```

Generated datasets are created locally and do not need to be committed in full to GitHub.


## 9. Installation and Setup

### Requirements

- Python 3.11 or later
- Git
- Windows, macOS, or Linux

### Clone the repository

```powershell
git clone https://github.com/srinivas377/shipment-eta-delay-simulator.git

cd shipment-eta-delay-simulator
```

### Create a virtual environment

```powershell
python -m venv venv
```

Activate it on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```powershell
python run.py install
```

## 10. Running the Project

### Generate starter dataset

```powershell
python run.py starter
```

### Generate full-scale dataset

```powershell
python run.py full
```

### Run validation

```powershell
python run.py validate
```

### Run automated tests

```powershell
python run.py test
```

### Run reproducibility verification

```powershell
python run.py repro
```

### Run full-scale reproducibility verification

```powershell
python scripts/repro_check.py --scale 1.0
```

### Run ETA and delay evaluation

```powershell
$env:PYTHONPATH = "src"
python run.py eval
```

### Launch the Streamlit dashboard

```powershell
python run.py dashboard
```

## 11. Dashboard and Visualization

The Streamlit dashboard provides an interface for exploring shipment and logistics simulation outputs.

It supports operational analysis through shipment information, tracking events, ETA estimates, delay information, and generated visualizations.

The dashboard helps users understand shipment progress, identify potential delays, and inspect logistics data.

## 📸 Dashboard Preview

The YottaFlex AI Logistics Dashboard provides an interactive interface for monitoring shipment performance, tracking delays, inspecting facility congestion, and evaluating ETA predictions.

### 1. Executive Dashboard
![Executive Dashboard](docs/images/dashboard-overview.png)

### 2. Shipment Explorer & Timeline
![Shipment Explorer](docs/images/shipment-explorer.png)

### 3. Facility Queues & Congestion
![Facility Queues](docs/images/facility-queues.png)

### 4. Data Quality & Anomaly Audit
![Anomaly Audit](docs/images/anomaly-audit.png)

### 5. Operations Exception Cockpit
![Operations Cockpit](docs/images/operations-cockpit.png)

### 6. ETA Model Evaluation
![ETA Model Evaluation](docs/images/eta-model-evaluation.png)

### 7. Timestamp Leakage Audit
![Timestamp Leakage Audit](docs/images/timestamp-leakage-audit.png)

## 12. Data Provenance and Licensing

All generated shipment and logistics records are synthetic.

The project does not require real customer shipment information or confidential carrier records.

The repository includes an MIT license. Review third-party dependency licenses and notices before redistribution.

## 13. Limitations and Future Improvements

The project uses synthetic data and simulated logistics assumptions. Its results do not establish real-world production performance.

Potential improvements include:

- Integration with real road-network routing.
- More detailed weather-impact modelling.
- Carrier capacity and driver-hour constraints.
- External logistics datasets where licensing permits.
- Better delay probability calibration.
- Business-cost-based alert threshold optimization.
- Monitoring model performance across seasonal and operational changes.

## 14. AI Usage and Attribution

AI tools assisted parts of the development process.

See [`docs/AI_USAGE.md`](docs/AI_USAGE.md) for the AI usage disclosure and prompt history.

All project contributions and disclosures should accurately reflect the work performed and reviewed by the developer.

## 15. Documentation

| Document | Description |
|---|---|
| [Business Rules](docs/BUSINESS_RULES.md) | Logistics business logic |
| [Data Dictionary](docs/DATA_DICTIONARY.md) | Entity and field definitions |
| [ER Diagram](docs/ER_DIAGRAM.md) | Database relationships |
| [Assumptions](docs/ASSUMPTIONS.md) | Simulation assumptions |
| [Design Decisions](docs/DESIGN_DECISIONS.md) | Technical decisions |
| [Validation Report](docs/VALIDATION_REPORT.md) | Data quality validation |
| [Reproducibility Report](docs/REPRODUCIBILITY.md) | SHA-256 reproducibility evidence |
| [Evaluation Report](docs/EVALUATION.md) | ETA and delay model evaluation |
| [AI Usage](docs/AI_USAGE.md) | AI usage disclosure |

---


**Project:** Real-Time Shipment Tracking & Delay Intelligence

**Assessment:** YottaFlex.ai – Associate AI Forward Deployed Engineer – Round 2 Code Challenge