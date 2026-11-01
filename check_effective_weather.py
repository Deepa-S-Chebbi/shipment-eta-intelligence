
import pandas as pd

BASE = "data/full/"

legs = pd.read_csv(BASE + "shipment_legs.csv")
facilities = pd.read_csv(BASE + "facilities.csv")
weather = pd.read_csv(BASE + "weather_events.csv")
weather = weather[
    weather["window_type"] == "WEATHER"
].copy()
# Parse timestamps
for col in [
    "actual_depart_at",
    "planned_depart_at",
    "planned_arrive_at"
]:
    legs[col] = pd.to_datetime(
        legs[col], format="ISO8601", utc=True
    )

for col in ["start_time", "end_time"]:
    weather[col] = pd.to_datetime(
        weather[col], format="ISO8601", utc=True
    )

# Get destination region for each leg
legs = legs.merge(
    facilities[["facility_id", "region"]],
    left_on="to_facility_id",
    right_on="facility_id",
    how="left"
)

legs["planned_hours"] = (
    legs["planned_arrive_at"] -
    legs["planned_depart_at"]
).dt.total_seconds() / 3600

# Group weather events by region
weather_by_region = {
    region: group.to_dict("records")
    for region, group in weather.groupby("region")
}

effective_multipliers = []

for leg in legs.itertuples():
    planned_hours = leg.planned_hours
    depart = leg.actual_depart_at
    arrive = depart + pd.Timedelta(hours=planned_hours)

    max_mult = 1.0

    for event in weather_by_region.get(leg.region, []):
        overlap_start = max(depart, event["start_time"])
        overlap_end = min(arrive, event["end_time"])

        if overlap_start < overlap_end:
            overlap_hours = (
                overlap_end - overlap_start
            ).total_seconds() / 3600

            weight = min(
                1.0,
                overlap_hours / max(1.0, planned_hours)
            )

            effective = 1.0 + (
                float(event["speed_multiplier"]) - 1.0
            ) * weight

            max_mult = max(max_mult, effective)

    effective_multipliers.append(min(1.28, max_mult))

legs["effective_weather_multiplier"] = effective_multipliers

print("\n===== EFFECTIVE WEATHER MULTIPLIER =====")
print(
    legs["effective_weather_multiplier"]
    .describe(percentiles=[0.5, 0.75, 0.90, 0.95])
    .round(3)
)

print("\n===== WEATHER CAP FREQUENCY =====")
print(
    "At 1.28 cap:",
    round(
        (legs["effective_weather_multiplier"] >= 1.28).mean() * 100,
        2
    ),
    "%"
)

print("\n===== MULTIPLIER DISTRIBUTION =====")
print(
    pd.cut(
        legs["effective_weather_multiplier"],
        bins=[0.99, 1.05, 1.10, 1.15, 1.20, 1.28],
        include_lowest=True
    ).value_counts().sort_index()
)

print("\n===== COMPLETED =====")
