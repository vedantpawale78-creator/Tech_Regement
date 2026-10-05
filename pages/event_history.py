"""
pages/event_history.py
Event History — full timeline with search and detailed stats.
"""
import streamlit as st
import pandas as pd
import plotly.express as px


def render(db):
    st.markdown("<h1>📋 Event History</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#64748b; margin-top:-10px;'>"
        "Complete audit trail of all detected events</p>",
        unsafe_allow_html=True,
    )

    alerts = db.get_alerts(limit=2000)
    if not alerts:
        st.info("No events recorded yet. Start a detection session to populate this view.")
        return

    df = pd.DataFrame(alerts)
    if "timestamp" in df.columns:
        df["ts"] = pd.to_datetime(df["timestamp"], errors="coerce")

    # ── Filters ───────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    cameras  = sorted(df["camera_id"].dropna().unique()) if "camera_id" in df.columns else []
    ev_types = sorted(df["event_type"].dropna().unique()) if "event_type" in df.columns else []

    sel_cam  = col1.multiselect("Camera", cameras, default=cameras, key="eh_cam")
    sel_evt  = col2.multiselect("Event Type", ev_types, default=ev_types, key="eh_evt")
    show_all = col3.checkbox("Include suppressed events", value=True, key="eh_all")

    filtered = df.copy()
    if sel_cam:
        filtered = filtered[filtered["camera_id"].isin(sel_cam)]
    if sel_evt:
        filtered = filtered[filtered["event_type"].isin(sel_evt)]
    if not show_all and "verified" in filtered.columns:
        filtered = filtered[filtered["verified"] == 1]

    st.markdown(
        f"<p style='color:#64748b; font-size:0.85rem;'>"
        f"Showing {len(filtered)} of {len(df)} total events</p>",
        unsafe_allow_html=True,
    )

    # ── Timeline ──────────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Event Timeline</div>",
                unsafe_allow_html=True)
    if "ts" in filtered.columns and not filtered["ts"].isna().all():
        try:
            tdf = filtered.set_index("ts").resample("10min").size().reset_index()
            tdf.columns = ["Time", "Events"]
            fig = px.bar(tdf, x="Time", y="Events",
                         color_discrete_sequence=["#38bdf8"])
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#94a3b8",
                xaxis=dict(showgrid=False, color="#64748b"),
                yaxis=dict(showgrid=True, gridcolor="#1e293b", color="#64748b"),
                margin=dict(t=10, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            pass

    # ── Per-camera breakdown ──────────────────────────────────────────────────
    if "camera_id" in filtered.columns and len(cameras) > 1:
        st.markdown("<div class='section-header'>Per-Camera Event Count</div>",
                    unsafe_allow_html=True)
        cam_counts = filtered.groupby("camera_id").size().reset_index(name="Count")
        fig2 = px.bar(cam_counts, x="camera_id", y="Count",
                      color="Count", color_continuous_scale="Blues")
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#94a3b8",
            xaxis=dict(showgrid=False, color="#64748b"),
            yaxis=dict(showgrid=True, gridcolor="#1e293b", color="#64748b"),
            margin=dict(t=10, b=20),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Full table ────────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Full Event Log</div>",
                unsafe_allow_html=True)
    show = [c for c in ["timestamp", "camera_id", "event_type", "object_class",
                          "track_id", "severity", "verification_state",
                          "confidence", "duration", "zone_name",
                          "verified", "suppression_reason"]
            if c in filtered.columns]
    st.dataframe(filtered[show].sort_values("timestamp", ascending=False)
                 if "timestamp" in filtered.columns else filtered[show],
                 use_container_width=True)

    # ── Export ────────────────────────────────────────────────────────────────
    csv = filtered.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Export Event Log (CSV)", csv,
                       "event_history.csv", "text/csv")
