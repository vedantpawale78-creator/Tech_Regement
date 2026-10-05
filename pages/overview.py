"""
pages/overview.py — System Overview Dashboard
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta


def render(db):
    st.markdown("<h1>🏠 System Overview</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#64748b; margin-top:-10px;'>Real-time summary of all simulated surveillance activity</p>",
        unsafe_allow_html=True,
    )

    # ── Key metrics ───────────────────────────────────────────────────────────
    stats = db.get_summary_stats()

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📷 Cameras", stats["total_cameras"])
    c2.metric("⚠️ Total Alerts", stats["total_alerts"])
    c3.metric("✅ Verified", stats["verified_alerts"])
    c4.metric("🔴 Critical / High", stats["critical_alerts"])
    c5.metric("⚡ Avg Latency", f"{stats['avg_latency_ms']:.1f} ms"
              if stats["avg_latency_ms"] else "—")

    st.markdown("<hr style='border-color:#1e3a5f; margin:16px 0;'>", unsafe_allow_html=True)

    # ── Camera status strip ───────────────────────────────────────────────────
    cameras = db.get_cameras()
    if cameras:
        st.markdown("<div class='section-header'>Camera Status</div>", unsafe_allow_html=True)
        cols = st.columns(min(len(cameras), 6))
        status_color = {
            "active":   "#22c55e",
            "idle":     "#94a3b8",
            "error":    "#ef4444",
            "removed":  "#374151",
        }
        for i, cam in enumerate(cameras):
            sc = status_color.get(cam.get("status", "idle"), "#94a3b8")
            cols[i % 6].markdown(f"""
            <div style='background:#0f1f35; border:1px solid #1e3a5f;
                        border-radius:8px; padding:10px 12px; text-align:center;
                        border-top: 3px solid {sc};'>
                <div style='font-size:1.4rem;'>📹</div>
                <div style='color:#e2e8f0; font-weight:600; font-size:0.85rem;'>
                    {cam["camera_id"]}</div>
                <div style='color:#64748b; font-size:0.72rem;'>{cam["name"]}</div>
                <div style='color:{sc}; font-size:0.7rem; font-weight:600;
                            margin-top:4px; text-transform:uppercase;'>
                    {cam.get("status","idle")}</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No cameras registered. Go to **Camera Network** to add simulated cameras.")

    st.markdown("<hr style='border-color:#1e3a5f; margin:16px 0;'>", unsafe_allow_html=True)

    # ── Charts row ────────────────────────────────────────────────────────────
    alerts = db.get_alerts(limit=500)
    if not alerts:
        st.info("No events recorded yet. Run a live detection session or the demo simulator.")
        return

    df = pd.DataFrame(alerts)

    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("<div class='section-header'>Alert Type Distribution</div>",
                    unsafe_allow_html=True)
        if "event_type" in df.columns:
            type_counts = df["event_type"].value_counts().reset_index()
            type_counts.columns = ["Event Type", "Count"]
            fig = px.pie(
                type_counts, names="Event Type", values="Count",
                color_discrete_sequence=["#38bdf8", "#f97316", "#22c55e", "#a78bfa"],
                hole=0.45,
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#94a3b8",
                legend=dict(font=dict(color="#94a3b8")),
                margin=dict(t=20, b=20, l=20, r=20),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("<div class='section-header'>Severity Breakdown</div>",
                    unsafe_allow_html=True)
        if "severity" in df.columns:
            sev_counts = df["severity"].value_counts().reset_index()
            sev_counts.columns = ["Severity", "Count"]
            color_map = {
                "Critical": "#ef4444", "High": "#f97316",
                "Medium": "#eab308",   "Low": "#94a3b8",
            }
            colors = [color_map.get(s, "#64748b") for s in sev_counts["Severity"]]
            fig2 = go.Figure(go.Bar(
                x=sev_counts["Severity"],
                y=sev_counts["Count"],
                marker_color=colors,
                text=sev_counts["Count"],
                textposition="outside",
                textfont=dict(color="#94a3b8"),
            ))
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#94a3b8",
                xaxis=dict(showgrid=False, color="#64748b"),
                yaxis=dict(showgrid=True, gridcolor="#1e293b", color="#64748b"),
                margin=dict(t=20, b=20, l=10, r=10),
            )
            st.plotly_chart(fig2, use_container_width=True)

    # ── Timeline chart ────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Detection Activity Timeline</div>",
                unsafe_allow_html=True)
    if "timestamp" in df.columns:
        try:
            df["ts"] = pd.to_datetime(df["timestamp"])
            df_time = df.set_index("ts").resample("5min").size().reset_index()
            df_time.columns = ["Time", "Events"]
            fig3 = px.area(
                df_time, x="Time", y="Events",
                color_discrete_sequence=["#38bdf8"],
                line_shape="spline",
            )
            fig3.update_traces(fill="tozeroy", fillcolor="rgba(56,189,248,0.12)")
            fig3.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#94a3b8",
                xaxis=dict(showgrid=False, color="#64748b"),
                yaxis=dict(showgrid=True, gridcolor="#1e293b", color="#64748b"),
                margin=dict(t=10, b=20, l=10, r=10),
            )
            st.plotly_chart(fig3, use_container_width=True)
        except Exception:
            pass

    # ── Recent events table ───────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Recent Events</div>", unsafe_allow_html=True)
    show_cols = [c for c in ["timestamp", "camera_id", "event_type", "object_class",
                              "severity", "verification_state", "verified"] if c in df.columns]
    st.dataframe(df[show_cols].head(15), use_container_width=True)
