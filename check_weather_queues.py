import pandas as pd

BASE = "data/full/"

# Load data
weather = pd.read_csv(BASE + "weather_events.csv")
weather_legs = pd.read_csv(BASE + "weather_event_legs.csv")
queues = pd.read_csv(BASE + "facility_queues.csv")
facilities = pd.read_csv(BASE + "facilities.csv")

# 1. Weather event distribution
print("\n===== WEATHER EVENT DISTRIBUTION =====")
print(
    weather.groupby(["type", "severity"])
    .agg(
        event_count=("weather_event_id", "count"),
        avg_multiplier=("speed_multiplier", "mean"),
        max_multiplier=("speed_multiplier", "max")
    )
    .round(2)
    .to_string()
)

# 2. Number of shipment legs affected by each weather type
print("\n===== WEATHER IMPACT ON SHIPMENT LEGS =====")
weather_impact = weather_legs.merge(
    weather[["weather_event_id", "type", "severity"]],
    on="weather_event_id",
    how="left"
)

print(
    weather_impact.groupby("type")
    .agg(
        affected_legs=("leg_id", "nunique"),
        impact_records=("leg_id", "count"),
        avg_multiplier=("impact_multiplier", "mean"),
        max_multiplier=("impact_multiplier", "max")
    )
    .round(2)
    .to_string()
)

# 3. Facility queue statistics
print("\n===== QUEUE WAITING BY FACILITY TYPE =====")
queue_data = queues.merge(
    facilities[["facility_id", "type"]],
    on="facility_id",
    how="left"
)

print(
    queue_data.groupby("type")["avg_wait_hours"]
    .agg(["count", "mean", "median", "max"])
    .round(2)
    .to_string()
)

# 4. Overall queue statistics
print("\n===== OVERALL QUEUE STATISTICS =====")
print(
    queue_data["avg_wait_hours"]
    .describe(percentiles=[0.50, 0.90, 0.95])
    .round(2)
)

print("\n===== DIAGNOSTIC COMPLETED =====")