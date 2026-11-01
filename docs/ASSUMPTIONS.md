# YottaFlex AI Logistics Synthetic Data: Assumptions Log

This document records all domain, simulation, and engineering assumptions made across the project lifecycle.

---

### 1. Temporal & Clock Assumptions
- **UTC Uniformity**: All simulation dates and event timestamps are strictly represented in UTC ISO-8601 format (`YYYY-MM-DDTHH:MM:SSZ`).
- **Fixed Epoch**: The simulation starts at `2026-03-01T00:00:00Z` and runs for 90 days. No call to non-deterministic system clocks (`datetime.now()`) is permitted.
- **Microsecond Truncation**: Timestamps are resolved to whole seconds for tracking events and minute boundaries for scheduled departure/arrival plans.

### 2. Physical & Spatial Modeling
- **Synthetic 2D Logistics Plane**: Facilities exist within a continuous normalized coordinate space $[0, 1000] \times [0, 1000]$ (representing a 1,000 km $\times$ 1,000 km territory).
- **Regions**: The territory is partitioned into 4 quadrants: `North` ($y \ge 500, x < 500$), `South` ($y < 500, x < 500$), `East` ($y \ge 500, x \ge 500$), and `West` ($y < 500, x \ge 500$).
- **Haversine / Euclidean Routing Factor**: Road distances incorporate an average circuity tortuosity multiplier of $1.25 \times \text{Euclidean distance}$. Rail incorporates $1.15$, Air is $1.02$, Sea connects designated coastal/port hubs.

### 3. Calendars & Facility Operations
- **Facility Types & Shifts**:
  - `HUB`: 24/7 continuous operations (3 shifts, no weekend shutdown).
  - `DEPOT`: Monday to Saturday, 06:00 to 22:00 local time.
  - `WAREHOUSE`: Monday to Friday, 07:00 to 19:00 local time.
  - `PORT`: 24/7 continuous customs & container operations.
- **Holidays**: National holiday shutdowns occur on fixed calendar dates during the 90-day window (e.g., Spring Logistics Holiday on Day 25, Regional Labor Day on Day 62).

### 4. Telemetry & Ingestion Simulation
- **Multi-Source Ingestion Lag**: Scanners and telematics upload events with latency drawn from a 3-tier mixture distribution:
  1. Cellular / live scanners (82%): 5–30 min.
  2. Batch dock reconciliation (15%): 1–6 hours.
  3. Remote dead-zone sync / hardware restart (3%): 12–48+ hours.
- **Near-Duplicate Events**: Scanners occasionally retry upload after transient failure, generating near-duplicate tracking events with identical `event_time` and slightly altered `ingestion_time` or duplicate flags.

### 5. Causal Rules vs Random Noise
- **No Independent Random Choices for Derived State**:
  - `actual_delivery_at` is derived solely from the timestamp of the terminal `DELIVERED` event.
  - `delay_hours = actual_delivery_at - promised_delivery_at`.
  - Service level classification (`ON_TIME`, `DELAYED`, `SEVERELY_DELAYED`) is computed solely by threshold lookup against `ServiceLevel`.
  - `ShipmentDelayReason` additive breakdown sums to total positive delay (within $10^{-6}$ hours).

### 6. Isolation of Ground Truth
- Injected anomalies (e.g., timestamp confusion, impossible sequence, ETA future-event usage) are recorded exclusively in `ground_truth/ground_truth.csv` and `ground_truth/ground_truth.json`.
- The input transactional datasets (`shipments.csv`, `legs.csv`, `events.csv`, `eta_estimates.csv`) contain zero metadata columns revealing anomaly presence.
