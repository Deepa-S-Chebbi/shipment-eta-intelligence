
import pandas as pd

BASE = "data/full/"

# Load data
legs = pd.read_csv(BASE + "shipment_legs.csv")
facilities = pd.read_csv(BASE + "facilities.csv")
carriers = pd.read_csv(BASE + "carriers.csv")

# Convert timestamps safely
date_cols = [
    "planned_depart_at",
    "planned_arrive_at",
    "actual_depart_at",
    "actual_arrive_at"
]

for col in date_cols:
    legs[col] = pd.to_datetime(
        legs[col],
        format="ISO8601",
        utc=True,
        errors="coerce"
    )

# Calculate transit durations
legs["planned_hours"] = (
    legs["planned_arrive_at"] -
    legs["planned_depart_at"]
).dt.total_seconds() / 3600

legs["actual_hours"] = (
    legs["actual_arrive_at"] -
    legs["actual_depart_at"]
).dt.total_seconds() / 3600

legs["extra_hours"] = (
    legs["actual_hours"] -
    legs["planned_hours"]
)

# ===================================
# 1. DELAY BY CARRIER
# ===================================

print("\n===== TRANSIT DELAY BY CARRIER =====")

carrier_analysis = legs.merge(
    carriers[["carrier_id", "reliability_tier", "mode"]],
    on="carrier_id",
    how="left"
)

print(
    carrier_analysis.groupby(
        ["carrier_id", "reliability_tier", "mode"]
    )["extra_hours"]
    .agg(["count", "mean", "median", "max"])
    .round(2)
    .to_string()
)

# ===================================
# 2. DELAY BY LEG SEQUENCE
# ===================================

print("\n===== TRANSIT DELAY BY LEG SEQUENCE =====")

print(
    legs.groupby("leg_sequence")[
        ["planned_hours", "actual_hours", "extra_hours"]
    ]
    .median()
    .round(2)
    .to_string()
)

# ===================================
# 3. FACILITY WAITING ANALYSIS
# ===================================

legs = legs.sort_values(
    ["shipment_id", "leg_sequence"]
)

legs["next_departure"] = (
    legs.groupby("shipment_id")["actual_depart_at"]
    .shift(-1)
)

legs["waiting_hours"] = (
    legs["next_departure"] -
    legs["actual_arrive_at"]
).dt.total_seconds() / 3600

facility_analysis = legs.merge(
    facilities[["facility_id", "type"]],
    left_on="to_facility_id",
    right_on="facility_id",
    how="left"
)

print("\n===== WAITING BY FACILITY TYPE =====")

print(
    facility_analysis.groupby("type")["waiting_hours"]
    .agg(["count", "mean", "median", "max"])
    .round(2)
    .to_string()
)

print("\n===== DIAGNOSTIC COMPLETED =====")
