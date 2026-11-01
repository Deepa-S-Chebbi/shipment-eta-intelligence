
import pandas as pd

BASE = "data/full/"

# ==========================================
# 1. LOAD DATA
# ==========================================

print("Loading shipment and shipment-leg data...")

shipments = pd.read_csv(BASE + "shipments.csv")
legs = pd.read_csv(BASE + "shipment_legs.csv")

# ==========================================
# 2. CONVERT TIMESTAMPS
# ==========================================

shipment_dates = [
    "created_at",
    "promised_delivery_at",
    "actual_delivery_at"
]

leg_dates = [
    "planned_depart_at",
    "planned_arrive_at",
    "actual_depart_at",
    "actual_arrive_at"
]

for col in shipment_dates:
    shipments[col] = pd.to_datetime(
        shipments[col],
        format="ISO8601",
        utc=True,
        errors="coerce"
    )

for col in leg_dates:
    legs[col] = pd.to_datetime(
        legs[col],
        format="ISO8601",
        utc=True,
        errors="coerce"
    )

# ==========================================
# 3. CALCULATE SHIPMENT DELAYS
# ==========================================

shipments["delay_hours"] = (
    shipments["actual_delivery_at"]
    - shipments["promised_delivery_at"]
).dt.total_seconds() / 3600

print("\n========== SHIPMENT COUNTS ==========")

print(
    shipments["final_delay_label"]
    .value_counts(dropna=False)
)

print("\n========== ON-TIME PERCENTAGE ==========")

print(
    shipments["final_delay_label"]
    .eq("ON_TIME")
    .mean() * 100
)

print("\n========== DELAY STATISTICS ==========")

print(
    shipments["delay_hours"].describe(
        percentiles=[0.25, 0.50, 0.75, 0.90, 0.95]
    )
)

# ==========================================
# 4. DELAY BY SERVICE LEVEL
# ==========================================

print("\n========== DELAY BY SERVICE LEVEL ==========")

service_stats = shipments.groupby(
    "service_level_id"
)["delay_hours"].agg(
    ["count", "mean", "median", "min", "max"]
)

print(service_stats.round(2).to_string())

# ==========================================
# 5. CALCULATE PICKUP DELAY
# ==========================================

legs = legs.sort_values(
    ["shipment_id", "leg_sequence"]
)

first_leg = legs.groupby("shipment_id").first()

last_leg = legs.groupby("shipment_id").last()

shipment_index = shipments.set_index("shipment_id")

pickup_hours = (
    first_leg["actual_depart_at"]
    - shipment_index["created_at"]
).dt.total_seconds() / 3600

# ==========================================
# 6. CALCULATE TRANSIT TIME
# ==========================================

legs["planned_transit"] = (
    legs["planned_arrive_at"]
    - legs["planned_depart_at"]
).dt.total_seconds() / 3600

legs["actual_transit"] = (
    legs["actual_arrive_at"]
    - legs["actual_depart_at"]
).dt.total_seconds() / 3600

legs["transit_excess"] = (
    legs["actual_transit"]
    - legs["planned_transit"]
)

transit_hours = legs.groupby(
    "shipment_id"
)["actual_transit"].sum(min_count=1)

transit_excess = legs.groupby(
    "shipment_id"
)["transit_excess"].sum(min_count=1)

# ==========================================
# 7. CALCULATE FACILITY WAITING TIME
# ==========================================

legs["next_departure"] = legs.groupby(
    "shipment_id"
)["actual_depart_at"].shift(-1)

legs["dwell_hours"] = (
    legs["next_departure"]
    - legs["actual_arrive_at"]
).dt.total_seconds() / 3600

dwell_hours = legs.groupby(
    "shipment_id"
)["dwell_hours"].sum(min_count=1)

# ==========================================
# 8. COMBINE DIAGNOSTIC RESULTS
# ==========================================

diagnostics = shipments.set_index(
    "shipment_id"
).copy()

diagnostics["pickup_hours"] = pickup_hours
diagnostics["transit_hours"] = transit_hours
diagnostics["transit_excess_hours"] = transit_excess
diagnostics["intermediate_dwell_hours"] = dwell_hours

print("\n========== DELAY CONTRIBUTION DIAGNOSTICS ==========")

columns = [
    "delay_hours",
    "pickup_hours",
    "transit_hours",
    "transit_excess_hours",
    "intermediate_dwell_hours"
]

print(
    diagnostics.groupby("service_level_id")[columns]
    .median()
    .round(2)
    .to_string()
)

# ==========================================
# 9. WORST 10 SHIPMENTS
# ==========================================

print("\n========== WORST 10 SHIPMENTS ==========")

worst = diagnostics.sort_values(
    "delay_hours",
    ascending=False
)

print(
    worst[
        [
            "service_level_id",
            "delay_hours",
            "pickup_hours",
            "transit_excess_hours",
            "intermediate_dwell_hours"
        ]
    ].head(10).round(2).to_string()
)

# ==========================================
# 10. DATA QUALITY CHECK
# ==========================================

print("\n========== DATA QUALITY CHECK ==========")

print("Shipments:", len(shipments))
print("Shipment legs:", len(legs))

print(
    "Missing actual delivery timestamps:",
    shipments["actual_delivery_at"].isna().sum()
)

print(
    "Missing actual arrival timestamps:",
    legs["actual_arrive_at"].isna().sum()
)

print(
    "Missing actual departure timestamps:",
    legs["actual_depart_at"].isna().sum()
)

print("\nDiagnostic completed.")
