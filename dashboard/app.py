"""
YottaFlex AI Logistics Operations & ML Analytics Dashboard.
Interactive Streamlit web application providing executive KPIs, shipment timelines,
facility queue heatmaps, data quality audits, and operations exception cockpit.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

# Set page configuration
st.set_page_config(
    page_title="YottaFlex AI | Real-Time Shipment Tracking & Delay Intelligence",
    page_icon="🛞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Premium Styling
st.markdown("""
<style>
    /* Professional dashboard background */
    .stApp {
        background: #f3f6fb;
        color: #17243b;
    }

    .block-container {
        max-width: 1500px;
        padding-top: 1.6rem;
        padding-bottom: 3rem;
    }

    /* Dark navigation sidebar */
    [data-testid="stSidebar"] {
        background: #101c32;
    }

    [data-testid="stSidebar"] * {
        color: #e8eef8;
    }

    /* Professional KPI cards */
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e3eaf3;
        border-radius: 14px;
        padding: 18px;
        box-shadow: 0 3px 12px rgba(24, 45, 75, 0.05);
        min-height: 118px;
    }

    [data-testid="stMetricLabel"] {
        color: #64748b;
        font-weight: 600;
    }

    [data-testid="stMetricValue"] {
        color: #17243b;
        font-size: 1.9rem;
        font-weight: 750;
    }

    /* Improved navigation tabs */
    [data-testid="stTabs"] button[role="tab"] {
        border-radius: 9px 9px 0 0;
        padding: 12px 15px;
        font-weight: 600;
    }

    [data-testid="stTabs"] button[aria-selected="true"] {
        color: #0878bd;
        border-bottom: 3px solid #0878bd;
    }

    /* Tables */
    [data-testid="stDataFrame"] {
        border: 1px solid #e3eaf3;
        border-radius: 12px;
        overflow: hidden;
    }

    /* Consistent headings */
    h1, h2, h3, h4 {
        color: #17243b;
        letter-spacing: -0.025em;
    }
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main-header {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
        
        padding: 45px 40px;
        min-height: 150px;
        display: flex;
        align-items: center;
        border-radius: 14px;
        margin-bottom: 24px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }
    
    .metric-card {
        background: #1e293b;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 18px 22px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: #38bdf8;
        transform: translateY(-2px);
    }
    
    .badge-ontime {
        background-color: rgba(16, 185, 129, 0.2);
        color: #10b981;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-delayed {
        background-color: rgba(245, 158, 11, 0.2);
        color: #f59e0b;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-severe {
        background-color: rgba(239, 68, 68, 0.2);
        color: #ef4444;
        padding: 4px 10px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


ROOT = Path(__file__).resolve().parent.parent


@st.cache_resource
def get_db_connection(data_dir: Path) -> sqlite3.Connection:
    sqlite_path = data_dir / "logistics.sqlite"
    if not sqlite_path.exists():
        st.error(f"Database not found at {sqlite_path}. Please generate data first!")
        st.stop()
    conn = sqlite3.connect(sqlite_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def load_query(conn: sqlite3.Connection, query: str, params: tuple = ()) -> pd.DataFrame:
    return pd.read_sql_query(query, conn, params=params)


# Sidebar configuration
st.sidebar.image("https://img.icons8.com/isometric/100/delivery.png", width=64)

st.sidebar.title("YottaFlex AI")
st.sidebar.caption("Shipment Tracking & Predictive ETA Intelligence")

data_source = st.sidebar.radio(
    "Dataset Source",
    ["Starter Scale (500 Shipments)", "Full Scale (50,000 Shipments)"],
    index=1,
)

target_dir = ROOT / "data" / "starter" if "Starter" in data_source else ROOT / "data" / "full"

if not target_dir.exists():
    st.sidebar.warning(f"Dataset path `{target_dir.name}` does not exist yet. Please generate it using `python run.py full`.")
    target_dir = ROOT / "data" / "starter"

conn = get_db_connection(target_dir)

# Header
st.markdown("""
<div class="main-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <p style="
            color: #e8eef8;
            margin: 0;
            font-size: 1.35rem;
            font-weight: 600;
        ">
            Real-Time Shipment Tracking & Delay Intelligence
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

# Navigation tabs
tabs = st.tabs([
    "📊 Executive KPIs",
    "🔍 Shipment Explorer & Timeline",
    "🏭 Facility Queues & Congestion",
    "🛡️ Data Quality & Anomaly Audit",
    "🚨 Operations Exception Cockpit",
    "🤖 ETA Model Evaluation",
    "⏱️ Timestamp Leakage Audit",
])

# TAB 1: EXECUTIVE KPIS
with tabs[0]:
    st.subheader("Network Executive Overview")

    col1, col2, col3, col4, col5 = st.columns(5)
    
    total_shp = load_query(conn, "SELECT COUNT(*) as cnt FROM shipments")["cnt"][0]
    total_events = load_query(conn, "SELECT COUNT(*) as cnt FROM tracking_events")["cnt"][0]
    ontime_cnt = load_query(conn, "SELECT COUNT(*) as cnt FROM shipments WHERE final_delay_label='ON_TIME'")["cnt"][0]
    ontime_pct = round((ontime_cnt / total_shp) * 100, 1) if total_shp > 0 else 0
    severe_cnt = load_query(conn, "SELECT COUNT(*) as cnt FROM shipments WHERE final_delay_label='SEVERELY_DELAYED'")["cnt"][0]
    rerouted_cnt = load_query(conn, "SELECT COUNT(*) as cnt FROM shipments WHERE is_rerouted=1")["cnt"][0]

    with col1:
        st.metric("Total Shipments", f"{total_shp:,}")
    with col2:
        st.metric("Tracking Events", f"{total_events:,}")
    with col3:
        st.metric("On-Time SLA %", f"{ontime_pct}%", delta=f"{ontime_pct - 85.0:.1f}% vs Target")
    with col4:
        st.metric("Severely Delayed", f"{severe_cnt:,}")
    with col5:
        st.metric("Dynamic Reroutes", f"{rerouted_cnt:,}")

    st.markdown("---")
    
    c_left, c_right = st.columns([1, 1])

    with c_left:
        st.markdown("##### Delivery SLA Compliance Distribution")
        sla_df = load_query(conn, """
            SELECT final_delay_label as status, COUNT(*) as count 
            FROM shipments 
            GROUP BY final_delay_label
        """)
        st.bar_chart(sla_df.set_index("status"), color="#0284c7")

    with c_right:
        st.markdown("##### Delay Attribution Decomposition (Hours Attributed)")
        delay_reason_df = load_query(conn, """
            SELECT dr.reason_code, ROUND(SUM(sdr.delay_hours_attributed), 1) as total_hours
            FROM shipment_delay_reasons sdr
            JOIN delay_reasons dr ON sdr.delay_id = dr.delay_id
            GROUP BY dr.reason_code
            ORDER BY total_hours DESC
        """)
        st.bar_chart(delay_reason_df.set_index("reason_code"), color="#f59e0b")

    st.markdown("##### Mode Distribution & Carrier Reliability")
    carrier_df = load_query(conn, """
        SELECT c.mode, c.reliability_tier, COUNT(sl.leg_id) as executed_legs
        FROM shipment_legs sl
        JOIN carriers c ON sl.carrier_id = c.carrier_id
        GROUP BY c.mode, c.reliability_tier
        ORDER BY c.mode, c.reliability_tier
    """)
    st.dataframe(carrier_df, use_container_width=True)

# TAB 2: SHIPMENT EXPLORER & TIMELINE
with tabs[1]:
    st.subheader("Shipment Telematics & Ingestion Lag Explorer")
    
    # Filter selection
    status_filter = st.selectbox("Filter by Status", ["ALL", "ON_TIME", "DELAYED", "SEVERELY_DELAYED"], index=0)
    
    query = "SELECT shipment_id, origin_facility_id, destination_facility_id, service_level_id, final_delay_label, is_rerouted FROM shipments"
    if status_filter != "ALL":
        query += f" WHERE final_delay_label='{status_filter}'"
    query += " LIMIT 100"
    
    sample_shipments = load_query(conn, query)
    
    selected_shp_id = st.selectbox(
        "Select Shipment to Inspect",
        sample_shipments["shipment_id"].tolist(),
        index=0 if len(sample_shipments) > 0 else None,
    )

    if selected_shp_id:
        shp_data = load_query(conn, "SELECT * FROM shipments WHERE shipment_id = ?", (selected_shp_id,)).iloc[0]
        
        info_c1, info_c2, info_c3, info_c4 = st.columns(4)
        with info_c1:
            st.markdown(f"**Origin**: `{shp_data['origin_facility_id']}`")
            st.markdown(f"**Destination**: `{shp_data['destination_facility_id']}`")
        with info_c2:
            st.markdown(f"**Service Level**: `{shp_data['service_level_id']}`")
            st.markdown(f"**Route**: `{shp_data['route_id']}`")
        with info_c3:
            st.markdown(f"**Created At**: `{shp_data['created_at']}`")
            st.markdown(f"**Promised Delivery**: `{shp_data['promised_delivery_at']}`")
        with info_c4:
            st.markdown(f"**Actual Delivery**: `{shp_data['actual_delivery_at'] or 'In Transit'}`")
            badge_class = "badge-ontime" if shp_data["final_delay_label"] == "ON_TIME" else ("badge-delayed" if shp_data["final_delay_label"] == "DELAYED" else "badge-severe")
            st.markdown(f"**Outcome**: <span class='{badge_class}'>{shp_data['final_delay_label']}</span>", unsafe_allow_html=True)

        st.markdown("---")
        
        # Events & Ingestion Lag Table
        st.markdown("##### Telemetry Event Stream (`event_time` vs Database `ingestion_time`)")
        events_df = load_query(conn, """
            SELECT sequence_no, event_type, event_time, ingestion_time, 
                   ROUND((julianday(ingestion_time) - julianday(event_time)) * 24.0 * 60.0, 1) as lag_minutes,
                   source_system, is_duplicate_of
            FROM tracking_events
            WHERE shipment_id = ?
            ORDER BY sequence_no ASC
        """, (selected_shp_id,))
        st.dataframe(events_df, use_container_width=True)

        # Leg hops
        st.markdown("##### Executed Transit Legs")
        legs_df = load_query(conn, """
            SELECT leg_sequence, from_facility_id, to_facility_id, carrier_id,
                   planned_depart_at, planned_arrive_at, actual_depart_at, actual_arrive_at, leg_status
            FROM shipment_legs
            WHERE shipment_id = ?
            ORDER BY leg_sequence ASC
        """, (selected_shp_id,))
        st.dataframe(legs_df, use_container_width=True)

        # ETA Evolution Snapshots
        st.markdown("##### Leakage-Safe ETA Snapshots (Prediction Progression Over Time)")
        eta_df = load_query(conn, """
            SELECT prediction_time, method, predicted_delivery_at, n_events_used, predicted_delay_probability
            FROM eta_estimates
            WHERE shipment_id = ?
            ORDER BY prediction_time ASC
        """, (selected_shp_id,))
        st.dataframe(eta_df, use_container_width=True)

        if not eta_df.empty:
            st.markdown("##### ETA Prediction Progression")
            eta_plot = eta_df.copy()
            eta_plot["prediction_time"] = pd.to_datetime(eta_plot["prediction_time"], errors="coerce")
            eta_plot["predicted_delivery_at"] = pd.to_datetime(eta_plot["predicted_delivery_at"], errors="coerce")
            eta_plot = eta_plot.dropna(subset=["prediction_time", "predicted_delivery_at"])
            if not eta_plot.empty:
                eta_plot["predicted_eta_hours"] = (
                    eta_plot["predicted_delivery_at"] - eta_plot["prediction_time"]
                ).dt.total_seconds() / 3600
                eta_pivot = eta_plot.pivot_table(
                    index="prediction_time", columns="method",
                    values="predicted_eta_hours", aggfunc="mean"
                )
                st.line_chart(eta_pivot)
            else:
                st.info("No valid ETA timestamps are available to plot.")

        if not events_df.empty and "lag_minutes" in events_df.columns:
            st.markdown("##### Event Ingestion Lag (Minutes)")
            lag_plot = events_df[["sequence_no", "lag_minutes"]].copy()
            lag_plot["lag_minutes"] = pd.to_numeric(lag_plot["lag_minutes"], errors="coerce")
            lag_plot = lag_plot.dropna(subset=["lag_minutes"])
            if not lag_plot.empty:
                st.bar_chart(lag_plot.set_index("sequence_no")["lag_minutes"])
            else:
                st.info("No valid ingestion-lag values are available to plot.")

# TAB 3: FACILITY QUEUES & CONGESTION
with tabs[2]:
    st.subheader("Facility Congestion & Queue Monitoring")
    
    facilities_df = load_query(conn, "SELECT facility_id, name, type, region, capacity_per_hour FROM facilities ORDER BY facility_id")
    selected_fac_id = st.selectbox(
        "Select Facility",
        facilities_df["facility_id"].tolist(),
        format_func=lambda x: f"{x} - {facilities_df.loc[facilities_df['facility_id']==x, 'name'].values[0]} ({facilities_df.loc[facilities_df['facility_id']==x, 'type'].values[0]})"
    )

    if selected_fac_id:
        f_info = facilities_df[facilities_df["facility_id"] == selected_fac_id].iloc[0]
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        with f_col1:
            st.metric("Facility Type", f_info["type"])
        with f_col2:
            st.metric("Region", f_info["region"])
        with f_col3:
            st.metric("Hourly Capacity", f"{f_info['capacity_per_hour']} units/hr")
        with f_col4:
            avg_wait = load_query(conn, "SELECT ROUND(AVG(avg_wait_hours), 2) as val FROM facility_queues WHERE facility_id = ?", (selected_fac_id,))["val"][0]
            st.metric("Mean Wait Time", f"{avg_wait or 0.0} hrs")

        st.markdown("---")
        st.markdown("##### Queue Length Over Time")
        queue_timeline = load_query(conn, """
            SELECT snapshot_time, queue_length, avg_wait_hours, throughput_per_hour
            FROM facility_queues
            WHERE facility_id = ?
            ORDER BY snapshot_time ASC
        """, (selected_fac_id,))
        
        if not queue_timeline.empty:
            st.line_chart(queue_timeline.set_index("snapshot_time")[["queue_length", "avg_wait_hours"]])
        else:
            st.info("No periodic queue snapshots found for this facility.")

# TAB 4: DATA QUALITY & ANOMALIES
with tabs[3]:
    st.subheader("Data Quality & Labelled Anomaly Audit")
    st.info("ℹ️ **Ground Truth Governance**: Injected anomalies are isolated to `ground_truth/` and are never exposed to feature extraction or inference pipelines.")

    gt_path = ROOT / "ground_truth" / "ground_truth.csv"
    if gt_path.exists():
        gt_df = pd.read_csv(gt_path)
        
        q1, q2, q3, q4 = st.columns(4)
        with q1:
            st.metric("Total Injected Anomalies", len(gt_df))
        with q2:
            st.metric("Timestamp Confusions", sum(gt_df["issue_type"] == "EVENT_TIME_INGESTION_CONFUSION"))
        with q3:
            st.metric("Impossible Route Orders", sum(gt_df["issue_type"] == "IMPOSSIBLE_ROUTE_ORDER"))
        with q4:
            st.metric("Future Peek ETA Leakages", sum(gt_df["issue_type"] == "ETA_USES_FUTURE_EVENT"))

        st.markdown("---")
        st.markdown("##### Injected Anomaly Audit Log")
        issue_filter = st.selectbox("Filter by Issue Type", ["ALL"] + sorted(gt_df["issue_type"].unique().tolist()))
        
        display_gt = gt_df if issue_filter == "ALL" else gt_df[gt_df["issue_type"] == issue_filter]

        st.markdown("##### Anomaly Distribution")
        anomaly_counts = gt_df["issue_type"].value_counts().rename_axis("issue_type")
        if not anomaly_counts.empty:
            st.bar_chart(anomaly_counts)

        st.markdown("##### Filtered Anomaly Audit Log")
        st.dataframe(display_gt, use_container_width=True)
    else:
        st.warning("No ground_truth.csv file located.")

# TAB 5: OPERATIONS EXCEPTION COCKPIT
with tabs[4]:
    st.subheader("Operations Manager Exception Cockpit")
    st.markdown("Active exception queue prioritizing shipments at severe risk of SLA violation.")

    exception_df = load_query(conn, """
        SELECT s.shipment_id, s.origin_facility_id, s.destination_facility_id, s.service_level_id,
               s.final_delay_label, s.is_rerouted,
               ROUND((julianday(s.actual_delivery_at) - julianday(s.promised_delivery_at)) * 24.0, 1) as delay_hours
        FROM shipments s
        WHERE s.final_delay_label IN ('DELAYED', 'SEVERELY_DELAYED')
        ORDER BY delay_hours DESC
        LIMIT 50
    """)

    if not exception_df.empty:
        severity_counts = exception_df["final_delay_label"].value_counts().reindex(
            ["DELAYED", "SEVERELY_DELAYED"], fill_value=0
        )
        metric_a, metric_b = st.columns(2)
        metric_a.metric("Delayed exceptions", int(severity_counts["DELAYED"]))
        metric_b.metric("Severely delayed exceptions", int(severity_counts["SEVERELY_DELAYED"]))

        st.markdown("##### Exception Severity Distribution")
        st.bar_chart(severity_counts)

        delay_plot = exception_df.dropna(subset=["delay_hours"]).head(15)
        if not delay_plot.empty:
            st.markdown("##### Highest Delay Exceptions (Hours)")
            st.bar_chart(delay_plot.set_index("shipment_id")["delay_hours"])
    else:
        st.success("No delayed or severely delayed shipments were found.")

    st.dataframe(exception_df, use_container_width=True)

# TAB 6: ETA MODEL EVALUATION
with tabs[5]:
    st.subheader("ETA Prediction & Delay Classification Evaluation")

    report_path = ROOT / "docs" / "EVALUATION.md"
    chart_dir = ROOT / "docs" / "img"

    # st.caption(f"Report: {report_path}")
    # st.caption(f"Charts: {chart_dir}")

    # if not report_path.is_file():
    #     st.error("EVALUATION.md was not found.")
    # else:
    #     report_text = report_path.read_text(encoding="utf-8")

    #     st.caption(f"Report characters: {len(report_text)}")

    #     if report_text.strip():
    #         st.markdown(report_text.split(
    #             "## 5. Visualizations", 1
    #         )[0])
    #     else:
    #         st.error("EVALUATION.md is empty.")

    #     st.divider()
    #     st.subheader("Evaluation Charts")

    #     chart_names = [
    #         "eta_mae_by_method.png",
    #         "horizon_error_curve.png",
    #     ]

    #     col1, col2 = st.columns(2)

    #     for col, filename in zip([col1, col2], chart_names):
    #         chart_path = chart_dir / filename

    #         with col:
    #             if chart_path.is_file():
    #                 st.image(
    #                     str(chart_path),
    #                     caption=filename,
    #                     use_container_width=True,
    #                 )
    #             else:
    #                 st.error(f"Chart not found: {chart_path}")
    if report_path.is_file():
        report_text = report_path.read_text(encoding="utf-8")

        if report_text.strip():
            report_for_dashboard = report_text.split(
                "## 5. Visualizations", 1
            )[0].strip()

            st.markdown(report_for_dashboard)
        else:
            st.error("Evaluation report is empty.")

        st.divider()
        st.subheader("Evaluation Charts")

        chart_names = [
            "eta_mae_by_method.png",
            "horizon_error_curve.png",
        ]

        col1, col2 = st.columns(2)

        for col, filename in zip([col1, col2], chart_names):
            chart_path = chart_dir / filename

            with col:
                if chart_path.is_file():
                    st.image(
                        str(chart_path),
                        caption=filename,
                        use_container_width=True,
                    )
                else:
                    st.error(f"Chart not found: {filename}")
    else:
        st.error("EVALUATION.md was not found.")

# TAB 7: TIMESTAMP LEAKAGE AUDIT
with tabs[6]:
    st.subheader("Point-in-Time Timestamp Leakage Audit")
    st.markdown(
        "Inspect one shipment prediction snapshot and compare the physical event time "
        "with the time the event became available to the prediction system."
    )

    st.info(
        "**Leakage-safe rule:** an event is visible to a prediction only when "
        "`ingestion_time <= prediction_time`. An event that happened earlier but "
        "arrived later must be excluded from that prediction."
    )

    audit_shipments = load_query(
        conn,
        """
        SELECT DISTINCT s.shipment_id
        FROM shipments s
        JOIN eta_estimates e ON e.shipment_id = s.shipment_id
        ORDER BY s.shipment_id
        """
    )

    if audit_shipments.empty:
        st.warning("No shipments with ETA prediction snapshots were found.")
    else:
        selected_audit_shipment = st.selectbox(
            "Select shipment for timestamp audit",
            audit_shipments["shipment_id"].tolist(),
            key="timestamp_audit_shipment",
        )

        prediction_df = load_query(
            conn,
            """
            SELECT prediction_time
            FROM eta_estimates
            WHERE shipment_id = ?
            ORDER BY prediction_time
            """,
            (selected_audit_shipment,),
        )

        if prediction_df.empty:
            st.warning("No prediction timestamps are available for this shipment.")
        else:
            selected_prediction_time = st.selectbox(
                "Select prediction timestamp",
                prediction_df["prediction_time"].dropna().astype(str).tolist(),
                key="timestamp_audit_prediction",
            )

            audit_events = load_query(
                conn,
                """
                SELECT
                    event_id,
                    sequence_no,
                    event_type,
                    event_time,
                    ingestion_time,
                    source_system
                FROM tracking_events
                WHERE shipment_id = ?
                ORDER BY sequence_no
                """,
                (selected_audit_shipment,),
            )

            if audit_events.empty:
                st.info("No tracking events were found for this shipment.")
            else:
                prediction_ts = pd.to_datetime(selected_prediction_time, errors="coerce")
                audit_events["event_time_parsed"] = pd.to_datetime(
                    audit_events["event_time"], errors="coerce"
                )
                audit_events["ingestion_time_parsed"] = pd.to_datetime(
                    audit_events["ingestion_time"], errors="coerce"
                )

                audit_events["visible_at_prediction"] = (
                    audit_events["ingestion_time_parsed"].notna()
                    & (audit_events["ingestion_time_parsed"] <= prediction_ts)
                )
                audit_events["event_time_only_would_include"] = (
                    audit_events["event_time_parsed"].notna()
                    & (audit_events["event_time_parsed"] <= prediction_ts)
                )
                audit_events["false_inclusion_if_event_time_only"] = (
                    audit_events["event_time_only_would_include"]
                    & ~audit_events["visible_at_prediction"]
                )

                visible_count = int(audit_events["visible_at_prediction"].sum())
                excluded_count = int((~audit_events["visible_at_prediction"]).sum())
                false_inclusion_count = int(
                    audit_events["false_inclusion_if_event_time_only"].sum()
                )

                metric_a, metric_b, metric_c, metric_d = st.columns(4)
                metric_a.metric("Total shipment events", len(audit_events))
                metric_b.metric("Visible at prediction", visible_count)
                metric_c.metric("Excluded at prediction", excluded_count)
                metric_d.metric("Event-time-only false inclusions", false_inclusion_count)

                st.markdown("#### Event Availability at Prediction Time")
                availability_counts = pd.Series({
                    "Visible": visible_count,
                    "Excluded": excluded_count,
                    "False inclusion if event-time-only": false_inclusion_count,
                }, name="Events")
                st.bar_chart(availability_counts)

                st.markdown("#### Timestamp decision table")
                st.caption(
                    f"Shipment: {selected_audit_shipment} · "
                    f"Prediction time: {selected_prediction_time}"
                )

                display_events = audit_events[
                    [
                        "event_id",
                        "sequence_no",
                        "event_type",
                        "event_time",
                        "ingestion_time",
                        "visible_at_prediction",
                        "false_inclusion_if_event_time_only",
                    ]
                ].copy()
                display_events["decision"] = display_events.apply(
                    lambda row: (
                        "INCLUDE"
                        if row["visible_at_prediction"]
                        else "EXCLUDE — not ingested yet"
                    ),
                    axis=1,
                )
                st.dataframe(display_events, use_container_width=True, hide_index=True)

                st.markdown("#### Leakage interpretation")
                if false_inclusion_count:
                    st.warning(
                        f"An event-time-only filter would incorrectly expose "
                        f"{false_inclusion_count} event(s) to this prediction. "
                        "The ingestion-time cutoff correctly excludes them."
                    )
                else:
                    st.success(
                        "For this selected snapshot, no event-time-only false "
                        "inclusions were found. The ingestion-time rule is still "
                        "required to prevent leakage in other snapshots."
                    )

                st.markdown("#### How to read the audit")
                st.markdown(
                    "- **INCLUDE:** ingestion time is at or before prediction time.\n"
                    "- **EXCLUDE:** ingestion time is after prediction time or is unavailable.\n"
                    "- **False inclusion:** event time is at or before prediction time, "
                    "but ingestion time is after prediction time. A filter based only "
                    "on event time would leak information."
                )

