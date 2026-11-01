# YottaFlex Logistics Data Dictionary

This document details every table and field in the YottaFlex synthetic logistics dataset, specifying data types, nullability, allowed values, units, uniqueness constraints, and explicit validation rules.

---

## 1. Master Data Tables

### 1.1 `Carrier`
Represents logistics transportation providers operating across modes and reliability tiers.
- **File**: `carriers.csv`

| Column | Type | Nullable | Units / Allowed Values | Uniqueness | Validation Rule |
|---|---|---|---|---|---|
| `carrier_id` | STRING | No | Regex `^CAR-\d{3}$` | Primary Key | Zero-padded 3-digit ID |
| `name` | STRING | No | e.g. "Apex Freight", "SwiftRoad" | Unique | Non-empty string |
| `mode` | STRING | No | `ROAD`, `RAIL`, `AIR`, `SEA` | No | Member of allowed modes |
| `reliability_tier` | STRING | No | `TIER_1`, `TIER_2`, `TIER_3` | No | Reliability performance tier |
| `base_speed_kmh` | FLOAT | No | km/h (20.0 to 900.0) | No | Positive float |
| `effective_from` | TIMESTAMP | No | ISO-8601 UTC | No | <= `effective_to` |
| `effective_to` | TIMESTAMP | No | ISO-8601 UTC | No | >= `effective_from` |

### 1.2 `Facility`
Hubs, sorting depots, warehouses, and freight ports.
- **File**: `facilities.csv`

| Column | Type | Nullable | Units / Allowed Values | Uniqueness | Validation Rule |
|---|---|---|---|---|---|
| `facility_id` | STRING | No | Regex `^FAC-\d{3}$` | Primary Key | Zero-padded 3-digit ID |
| `name` | STRING | No | e.g. "North Metro Hub" | Unique | Non-empty string |
| `type` | STRING | No | `HUB`, `DEPOT`, `WAREHOUSE`, `PORT` | No | Member of facility types |
| `region` | STRING | No | `North`, `South`, `East`, `West` | No | Member of regions |
| `latitude` | FLOAT | No | Coordinate $[0.0, 1000.0]$ | No | Within grid bounds |
| `longitude` | FLOAT | No | Coordinate $[0.0, 1000.0]$ | No | Within grid bounds |
| `capacity_per_hour`| INTEGER | No | Parcels / containers per hour | No | Value $> 0$ |
| `timezone` | STRING | No | e.g. `UTC`, `America/New_York` | No | Valid timezone identifier |

### 1.3 `ServiceLevel`
Contractual delivery SLAs with targets, grace periods, and severity thresholds.
- **File**: `service_levels.csv`

| Column | Type | Nullable | Units / Allowed Values | Uniqueness | Validation Rule |
|---|---|---|---|---|---|
| `service_level_id` | STRING | No | Regex `^SL-[A-Z]+-\d+H$` | Primary Key | e.g. `SL-EXP-24H` |
| `name` | STRING | No | Service tier name | Unique | Non-empty string |
| `target_hours` | INTEGER | No | Hours (e.g. 24, 48, 72, 120) | No | Value $> 0$ |
| `grace_hours` | FLOAT | No | Hours allowed before marked delayed | No | Value $\ge 0$ |
| `severely_delayed_hours` | FLOAT | No | Hours delay threshold for severe | No | $> \text{grace\_hours}$ |
| `effective_from` | TIMESTAMP | No | ISO-8601 UTC | No | <= `effective_to` |
| `effective_to` | TIMESTAMP | No | ISO-8601 UTC | No | >= `effective_from` |

### 1.4 `Route` & `RouteLegTemplate`
Standard route networks connecting origin to destination with 1 to 4 ordered hops.
- **Files**: `routes.csv`, `route_leg_templates.csv`

| Table | Column | Type | Nullable | Units / Allowed Values | Uniqueness | Validation Rule |
|---|---|---|---|---|---|---|
| `Route` | `route_id` | STRING | No | Regex `^RTE-\d{4}$` | Primary Key | Zero-padded 4-digit ID |
| `Route` | `origin_facility_id` | STRING | No | FK $\to$ `Facility.facility_id` | No | Valid origin facility |
| `Route` | `destination_facility_id`| STRING | No | FK $\to$ `Facility.facility_id` | No | $\ne \text{origin\_facility\_id}$ |
| `Route` | `total_planned_hours` | FLOAT | No | Hours | No | Value $> 0$ |
| `Route` | `version` | INTEGER | No | Integer version counter | No | Value $\ge 1$ |
| `Route` | `effective_from` | TIMESTAMP | No | ISO-8601 UTC | No | <= `effective_to` |
| `Route` | `effective_to` | TIMESTAMP | No | ISO-8601 UTC | No | >= `effective_from` |
| `RouteLegTemplate` | `template_id` | STRING | No | Regex `^RLT-\d{6}$` | Primary Key | Sequential ID |
| `RouteLegTemplate` | `route_id` | STRING | No | FK $\to$ `Route.route_id` | No | Valid parent route |
| `RouteLegTemplate` | `leg_sequence` | INTEGER | No | 1, 2, 3, 4 | No | Consecutive 1..N |
| `RouteLegTemplate` | `from_facility_id` | STRING | No | FK $\to$ `Facility.facility_id` | No | Valid start hub |
| `RouteLegTemplate` | `to_facility_id` | STRING | No | FK $\to$ `Facility.facility_id` | No | Valid end hub |
| `RouteLegTemplate` | `carrier_id` | STRING | No | FK $\to$ `Carrier.carrier_id` | No | Valid carrier |
| `RouteLegTemplate` | `planned_duration_hours`| FLOAT | No | Hours | No | Value $> 0$ |

### 1.5 `CarrierCalendar` & `FacilityCalendar`
Operational working hours, shifts, and holiday closures.
- **Files**: `carrier_calendars.csv`, `facility_calendars.csv`

| Table | Column | Type | Nullable | Units / Allowed Values | Validation Rule |
|---|---|---|---|---|---|
| `*Calendar` | `calendar_id` | STRING | No | Regex `^CAL-\d{6}$` | Primary Key |
| `CarrierCalendar` | `carrier_id` | STRING | No | FK $\to$ `Carrier.carrier_id` | Valid carrier |
| `FacilityCalendar`| `facility_id`| STRING | No | FK $\to$ `Facility.facility_id` | Valid facility |
| `*Calendar` | `day_of_week` | INTEGER | No | 0 (Mon) to 6 (Sun) | $0 \le d \le 6$ |
| `*Calendar` | `open_time` | STRING | No | `HH:MM:SS` | 24-hr time string |
| `*Calendar` | `close_time` | STRING | No | `HH:MM:SS` | 24-hr time string |
| `*Calendar` | `is_holiday` | BOOLEAN | No | `True`, `False` | Boolean |
| `*Calendar` | `effective_from` | TIMESTAMP | No | ISO-8601 UTC | Valid timestamp |
| `*Calendar` | `effective_to` | TIMESTAMP | No | ISO-8601 UTC | Valid timestamp |

---

## 2. Transactional & Disruption Tables

### 2.1 `WeatherEvent` & Disruption Windows
Atmospheric disturbances and facility maintenance outages.
- **File**: `weather_events.csv`

| Column | Type | Nullable | Units / Allowed Values | Uniqueness | Validation Rule |
|---|---|---|---|---|---|
| `weather_event_id` | STRING | No | Regex `^WX-\d{4}$` | Primary Key | Exactly 1,000 full scale |
| `window_type` | STRING | No | `WEATHER`, `FACILITY` | No | Split: 650 Weather, 350 Facility |
| `type` | STRING | No | `RAIN`, `STORM`, `FOG`, `HEAT`, `SNOW`, `MAINTENANCE` | No | Valid disturbance type |
| `severity` | INTEGER | No | 1 to 5 | No | Severity scale 1 (mild) to 5 (severe) |
| `start_time` | TIMESTAMP | No | ISO-8601 UTC | No | <= `end_time` |
| `end_time` | TIMESTAMP | No | ISO-8601 UTC | No | >= `start_time` |
| `region` | STRING | No | `North`, `South`, `East`, `West` | No | Valid region |
| `speed_multiplier` | FLOAT | No | Multiplier (1.02 to 1.85) | No | Value $\ge 1.0$ |

### 2.2 Bridge Tables: `WeatherEventFacility` & `WeatherEventLeg`
- **Files**: `weather_event_facilities.csv`, `weather_event_legs.csv`

| Table | Column | Type | Nullable | Validation Rule |
|---|---|---|---|---|
| `WeatherEventFacility` | `bridge_id` | STRING | No | PK `^WEF-\d{6}$` |
| `WeatherEventFacility` | `weather_event_id` | STRING | No | FK $\to$ `WeatherEvent.weather_event_id` |
| `WeatherEventFacility` | `facility_id` | STRING | No | FK $\to$ `Facility.facility_id` |
| `WeatherEventFacility` | `impact_start` | TIMESTAMP | No | Timestamp overlap start |
| `WeatherEventFacility` | `impact_end` | TIMESTAMP | No | Timestamp overlap end |
| `WeatherEventLeg` | `bridge_id` | STRING | No | PK `^WEL-\d{6}$` |
| `WeatherEventLeg` | `weather_event_id` | STRING | No | FK $\to$ `WeatherEvent.weather_event_id` |
| `WeatherEventLeg` | `leg_id` | STRING | No | FK $\to$ `ShipmentLeg.leg_id` |
| `WeatherEventLeg` | `impact_multiplier` | FLOAT | No | Computed transit multiplier $\ge 1.0$ |

### 2.3 `FacilityQueue`
Hourly queue snapshots across facilities.
- **File**: `facility_queues.csv`

| Column | Type | Nullable | Units / Allowed Values | Validation Rule |
|---|---|---|---|---|
| `queue_id` | STRING | No | Regex `^FQ-\d{6}$` | Primary Key |
| `facility_id` | STRING | No | FK $\to$ `Facility.facility_id` | Valid facility |
| `snapshot_time` | TIMESTAMP | No | ISO-8601 UTC | Valid timestamp |
| `queue_length` | INTEGER | No | Waiting vehicles / containers | $\ge 0$ |
| `avg_wait_hours` | FLOAT | No | Hours waiting | $\ge 0.0$ |
| `throughput_per_hour` | FLOAT | No | Units processed / hr | $> 0.0$ |

---

## 3. Shipments, Legs & Tracking Events

### 3.1 `Shipment`
Top-level shipment entity.
- **File**: `shipments.csv`

| Column | Type | Nullable | Units / Allowed Values | Uniqueness | Validation Rule |
|---|---|---|---|---|---|
| `shipment_id` | STRING | No | Regex `^SHP-2026-\d{6}$` | Primary Key | Zero-padded 6-digit ID |
| `supplier_id` | STRING | No | Regex `^SUP-\d{3}$` | No | e.g. `SUP-014` |
| `origin_facility_id` | STRING | No | FK $\to$ `Facility.facility_id` | No | Valid facility |
| `destination_facility_id`| STRING | No | FK $\to$ `Facility.facility_id` | No | Valid facility |
| `service_level_id` | STRING | No | FK $\to$ `ServiceLevel.service_level_id`| No | Valid service level |
| `route_id` | STRING | No | FK $\to$ `Route.route_id` | No | Valid route |
| `created_at` | TIMESTAMP | No | ISO-8601 UTC | No | <= `promised_delivery_at` |
| `promised_delivery_at` | TIMESTAMP | No | ISO-8601 UTC | No | `created_at` + SLA hours |
| `actual_delivery_at` | TIMESTAMP | Yes | ISO-8601 UTC | No | Null if cancelled/lost; matches DELIVERED event |
| `current_status` | STRING | No | `CREATED`, `IN_TRANSIT`, `DELIVERED`, `CANCELLED` | No | Derived from state history |
| `final_delay_label` | STRING | No | `ON_TIME`, `DELAYED`, `SEVERELY_DELAYED`, `CANCELLED` | No | Derived from delay rules |
| `is_rerouted` | BOOLEAN | No | `True`, `False` | No | True if RouteChange occurred |

### 3.2 `ShipmentLeg`
Leg hop execution.
- **File**: `shipment_legs.csv`

| Column | Type | Nullable | Units / Allowed Values | Uniqueness | Validation Rule |
|---|---|---|---|---|---|
| `leg_id` | STRING | No | Regex `^LEG-SHP-2026-\d{6}-\d{2}$` | Primary Key | Formatted with shipment ID + leg sequence |
| `shipment_id` | STRING | No | FK $\to$ `Shipment.shipment_id` | No | Valid shipment |
| `leg_sequence` | INTEGER | No | 1, 2, 3, 4 | No | Strictly consecutive |
| `from_facility_id` | STRING | No | FK $\to$ `Facility.facility_id` | No | Valid origin hub |
| `to_facility_id` | STRING | No | FK $\to$ `Facility.facility_id` | No | Valid destination hub |
| `carrier_id` | STRING | No | FK $\to$ `Carrier.carrier_id` | No | Valid carrier |
| `planned_depart_at` | TIMESTAMP | No | ISO-8601 UTC | No | <= `planned_arrive_at` |
| `planned_arrive_at` | TIMESTAMP | No | ISO-8601 UTC | No | >= `planned_depart_at` |
| `actual_depart_at` | TIMESTAMP | Yes | ISO-8601 UTC | No | Null if cancelled |
| `actual_arrive_at` | TIMESTAMP | Yes | ISO-8601 UTC | No | Null if in-progress/cancelled |
| `leg_status` | STRING | No | `PLANNED`, `IN_TRANSIT`, `COMPLETED`, `SUPERSEDED` | No | Leg state |

### 3.3 `TrackingEvent`
Event stream with physical vs system ingestion timestamps.
- **File**: `tracking_events.csv`

| Column | Type | Nullable | Units / Allowed Values | Uniqueness | Validation Rule |
|---|---|---|---|---|---|
| `event_id` | STRING | No | Regex `^EVT-SHP-2026-\d{6}-\d{6}$` | Primary Key | Per-shipment zero-padded sequence |
| `shipment_id` | STRING | No | FK $\to$ `Shipment.shipment_id` | No | Valid shipment |
| `leg_id` | STRING | Yes | FK $\to$ `ShipmentLeg.leg_id` | No | Optional on creation events |
| `facility_id` | STRING | Yes | FK $\to$ `Facility.facility_id` | No | Populated at depot/hub scans |
| `event_type` | STRING | No | `CREATED`, `PICKED_UP`, `DEPARTED`, `IN_TRANSIT_SCAN`, `ARRIVED`, `DELAY_SCAN`, `ROUTE_CHANGED`, `OUT_FOR_DELIVERY`, `DELIVERED`, `CANCELLED` | No | Member of allowed event types |
| `event_time` | TIMESTAMP | No | ISO-8601 UTC | No | Physical occurrence time |
| `ingestion_time` | TIMESTAMP | No | ISO-8601 UTC | No | Visible in database; $\ge \text{event\_time}$ (unless anomaly) |
| `source_system` | STRING | No | `MOBILE_SCANNER`, `PORTAL`, `EDI_214`, `GPS_TELEMATICS` | No | Telemetry origin |
| `is_duplicate_of` | STRING | Yes | FK $\to$ `TrackingEvent.event_id` | No | Self-referencing duplicate pointer |
| `sequence_no` | INTEGER | No | 1, 2, 3... | No | Strictly monotonic per shipment |

---

## 4. Derived & Operational Analytics Tables

### 4.1 `DelayReason` & `ShipmentDelayReason`
Taxonomy and exact arithmetic decomposition.
- **Files**: `delay_reasons.csv`, `shipment_delay_reasons.csv`

| Table | Column | Type | Nullable | Allowed Values | Validation Rule |
|---|---|---|---|---|---|
| `DelayReason` | `delay_id` | STRING | No | Regex `^DLY-2026-\d{6}$` | Primary Key |
| `DelayReason` | `reason_code` | STRING | No | `WEATHER`, `FACILITY_QUEUE`, `CARRIER_DELAY`, `ROUTE_CHANGE`, `CALENDAR_CLOSURE`, `LATE_PICKUP` | Standard delay taxonomy |
| `DelayReason` | `description` | STRING | No | Human readable text | Non-empty |
| `DelayReason` | `severity` | INTEGER | No | 1 to 5 | Severity scale |
| `ShipmentDelayReason` | `attribution_id` | STRING | No | Regex `^SDR-\d{8}$` | Primary Key |
| `ShipmentDelayReason` | `shipment_id` | STRING | No | FK $\to$ `Shipment.shipment_id` | Valid shipment |
| `ShipmentDelayReason` | `leg_id` | STRING | Yes | FK $\to$ `ShipmentLeg.leg_id` | Optional leg attribution |
| `ShipmentDelayReason` | `delay_id` | STRING | No | FK $\to$ `DelayReason.delay_id` | Valid delay category |
| `ShipmentDelayReason` | `delay_hours_attributed`| FLOAT | No | Hours $\ge 0.0$ | Sum over shipment == positive delay |

### 4.2 `ShipmentStatusHistory` & `RouteChange`
Append-only lifecycle auditing.
- **Files**: `shipment_status_history.csv`, `route_changes.csv`

| Table | Column | Type | Nullable | Validation Rule |
|---|---|---|---|---|
| `ShipmentStatusHistory` | `history_id` | STRING | No | PK `^SSH-\d{8}$` |
| `ShipmentStatusHistory` | `shipment_id` | STRING | No | FK $\to$ `Shipment.shipment_id` |
| `ShipmentStatusHistory` | `status` | STRING | No | Valid status lifecycle value |
| `ShipmentStatusHistory` | `transition_time` | TIMESTAMP | No | Monotonic timestamp |
| `ShipmentStatusHistory` | `trigger_event_id` | STRING | Yes | FK $\to$ `TrackingEvent.event_id` |
| `RouteChange` | `change_id` | STRING | No | PK `^RTC-\d{6}$` |
| `RouteChange` | `shipment_id` | STRING | No | FK $\to$ `Shipment.shipment_id` |
| `RouteChange` | `old_route_id` | STRING | No | FK $\to$ `Route.route_id` |
| `RouteChange` | `new_route_id` | STRING | No | FK $\to$ `Route.route_id` |
| `RouteChange` | `reason` | STRING | No | e.g. `SEVERE_WEATHER_DETOUR`, `FACILITY_CONGESTION` |
| `RouteChange` | `effective_time` | TIMESTAMP | No | Time reroute was enacted |

### 4.3 `ETAEstimate`
Leakage-safe point-in-time ETA snapshots.
- **File**: `eta_estimates.csv`

| Column | Type | Nullable | Units / Allowed Values | Validation Rule |
|---|---|---|---|---|
| `eta_id` | STRING | No | Regex `^ETA-SHP-2026-\d{6}-\d{8}T\d{4}$` | Primary Key format `ETA-<shipment-id>-<timestamp>` |
| `shipment_id` | STRING | No | FK $\to$ `Shipment.shipment_id` | Valid shipment |
| `prediction_time` | TIMESTAMP | No | ISO-8601 UTC | Timestamp when inference was executed |
| `predicted_delivery_at`| TIMESTAMP | No | ISO-8601 UTC | Estimated arrival time |
| `method` | STRING | No | `PLAN_BASED`, `PROGRESS_BASED`, `CONTEXT_AWARE`, `ML_GRADIENT_BOOST` | Method taxonomy |
| `features_cutoff_time` | TIMESTAMP | No | ISO-8601 UTC | Must be $\le \text{prediction\_time}$ (leakage check) |
| `n_events_used` | INTEGER | No | Count of events known at inference | Only counts events with $\text{ingestion\_time} \le \text{prediction\_time}$ |
| `predicted_delay_probability`| FLOAT| No | $[0.0, 1.0]$ | Calibrated delay risk probability |

---

## 5. Ground Truth & Anomaly Tracking Table (Isolated)
- **Files**: `ground_truth/ground_truth.csv`, `ground_truth/ground_truth.json`
- **Notice**: Never merged into feature or input tables.

| Column | Type | Description |
|---|---|---|
| `record_type` | STRING | Entity type where anomaly was injected (e.g. `TrackingEvent`, `ShipmentLeg`, `ETAEstimate`, `Shipment`) |
| `record_id` | STRING | Primary key of the corrupted record |
| `issue_type` | STRING | Anomaly label: `EVENT_TIME_INGESTION_CONFUSION`, `IMPOSSIBLE_ROUTE_ORDER`, `ETA_USES_FUTURE_EVENT`, `DELIVERED_STILL_IN_TRANSIT` |
| `description` | STRING | Technical explanation of the injected condition |
| `expected_decision` | STRING | Recommended action by validator/cleanser (`REJECT`, `QUARANTINE`, `IMPUTE_INGESTION_TIME`) |
| `injected_field` | STRING | Name of corrupted attribute |
| `original_value` | STRING | Uncorrupted ground-truth value |
| `injected_value` | STRING | Corrupted value present in published dataset |
