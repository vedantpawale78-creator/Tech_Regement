"""
pages/bandwidth_analytics.py
Bandwidth Analytics — Phase 7 simulation.

Demonstrates why compact semantic alerts are better than raw video
transmission for constrained communication links (mountain, cave, satellite).
"""
import time
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from modules.bandwidth_simulator import BandwidthSimulator
from config.settings import BANDWIDTH_PRESETS, VIDEO_BYTES_PER_SECOND_720P


def render(db):
    st.markdown("<h1>📡 Bandwidth Analytics</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#64748b; margin-top:-10px;'>"
        "Simulated network transmission comparison: Raw video vs. Semantic alerts</p>",
        unsafe_allow_html=True,
    )

    st.info(
        "ℹ️ This is a **simulated** analysis. No real network I/O is performed. "
        "All calculations use: `Transmission time = payload_bytes × 8 / bandwidth_bps`"
    )

    # ── Network Condition Selector ────────────────────────────────────────────
    st.markdown("<div class='section-header'>Network Configuration</div>",
                unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    condition  = col1.selectbox("Network Condition", list(BANDWIDTH_PRESETS.keys()),
                                 index=2, key="bw_condition")
    resolution = col2.selectbox("Video Resolution", ["480p", "720p", "1080p"],
                                 index=1, key="bw_resolution")
    duration   = col3.slider("Equivalent Video Duration (sec)", 10, 3600, 60,
                              key="bw_duration")

    bw_bps = BANDWIDTH_PRESETS[condition]
    bw_display = (
        f"{bw_bps:,} bps" if bw_bps > 0
        else ("500–2,000 bps (variable)" if bw_bps == -1 else "DISCONNECTED")
    )

    st.markdown(
        f"<div style='background:#0f1f35; border:1px solid #1e3a5f; "
        f"border-radius:8px; padding:12px 16px; color:#38bdf8;'>"
        f"Selected: <b>{condition}</b> — Effective bandwidth: <b>{bw_display}</b>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ── Load alert data ───────────────────────────────────────────────────────
    alerts = db.get_alerts(limit=500)
    num_alerts = len(alerts)

    # ── Payload Comparison ────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Payload Size Comparison</div>",
                unsafe_allow_html=True)

    bps_lookup = {"720p": VIDEO_BYTES_PER_SECOND_720P,
                  "1080p": VIDEO_BYTES_PER_SECOND_720P * 2,
                  "480p": VIDEO_BYTES_PER_SECOND_720P // 2}
    video_bytes    = bps_lookup.get(resolution, VIDEO_BYTES_PER_SECOND_720P) * duration
    semantic_bytes = max(num_alerts, 1) * 250  # 250 bytes per alert text

    reduction_pct  = ((video_bytes - semantic_bytes) / video_bytes * 100
                       if video_bytes > 0 else 0)

    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Video Payload", f"{video_bytes/1024:.1f} KB",
               help=f"Compressed {resolution} H.264 estimate for {duration}s")
    mc2.metric("Semantic Alert Payload", f"{semantic_bytes/1024:.2f} KB",
               help=f"{num_alerts} alerts × 250 bytes each")
    mc3.metric("Estimated Reduction", f"{reduction_pct:.1f}%",
               delta=None,
               help="(video_bytes - semantic_bytes) / video_bytes × 100")

    # Bar chart comparison
    fig_bar = go.Figure(data=[
        go.Bar(name="Raw Video", x=["Payload Size (KB)"],
               y=[video_bytes / 1024],
               marker_color="#ef4444", width=0.3),
        go.Bar(name="Semantic Alerts", x=["Payload Size (KB)"],
               y=[semantic_bytes / 1024],
               marker_color="#22c55e", width=0.3),
    ])
    fig_bar.update_layout(
        barmode="group",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#94a3b8",
        xaxis=dict(showgrid=False, color="#64748b"),
        yaxis=dict(showgrid=True, gridcolor="#1e293b", color="#64748b",
                   title="Size (KB)"),
        legend=dict(font=dict(color="#94a3b8")),
        margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # ── Transmission Time ─────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Estimated Transmission Time</div>",
                unsafe_allow_html=True)

    effective_bw = bw_bps if bw_bps > 0 else 1000  # use 1kbps for display if unstable

    if bw_bps == 0:
        st.error("⛔ DISCONNECTED MODE — No transmission possible. Alerts are queued.")
        video_tx_time   = float("inf")
        semantic_tx_time = float("inf")
    else:
        video_tx_time    = (video_bytes * 8) / effective_bw
        semantic_tx_time = (semantic_bytes * 8) / effective_bw

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"""
        <div style='background:rgba(239,68,68,0.1); border:1px solid #ef4444;
                    border-radius:8px; padding:14px 16px;'>
            <div style='color:#ef4444; font-size:0.75rem; text-transform:uppercase;
                        letter-spacing:0.08em;'>Raw Video Transmission</div>
            <div style='font-size:2rem; font-weight:700; color:#fca5a5; margin-top:4px;'>
                {_format_time(video_tx_time)}
            </div>
            <div style='color:#64748b; font-size:0.78rem; margin-top:6px;'>
                Payload: {video_bytes/1024:.1f} KB |
                Bandwidth: {bw_display}
            </div>
            <div style='color:#475569; font-size:0.72rem; margin-top:4px;'>
                Formula: {video_bytes:.0f} bytes × 8 ÷ {effective_bw:,} bps
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col_b:
        st.markdown(f"""
        <div style='background:rgba(34,197,94,0.1); border:1px solid #22c55e;
                    border-radius:8px; padding:14px 16px;'>
            <div style='color:#22c55e; font-size:0.75rem; text-transform:uppercase;
                        letter-spacing:0.08em;'>Semantic Alert Transmission</div>
            <div style='font-size:2rem; font-weight:700; color:#86efac; margin-top:4px;'>
                {_format_time(semantic_tx_time)}
            </div>
            <div style='color:#64748b; font-size:0.78rem; margin-top:6px;'>
                Payload: {semantic_bytes/1024:.2f} KB |
                Bandwidth: {bw_display}
            </div>
            <div style='color:#475569; font-size:0.72rem; margin-top:4px;'>
                Formula: {semantic_bytes:.0f} bytes × 8 ÷ {effective_bw:,} bps
            </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Multi-bandwidth comparison chart ──────────────────────────────────────
    st.markdown("<div class='section-header'>Transmission Time Across Bandwidths</div>",
                unsafe_allow_html=True)

    bw_rows = []
    for name, bps in BANDWIDTH_PRESETS.items():
        if bps <= 0:
            continue
        vid_t = (video_bytes * 8) / bps
        sem_t = (semantic_bytes * 8) / bps
        bw_rows.append({"Bandwidth": name, "Type": "Raw Video",     "Time (sec)": vid_t})
        bw_rows.append({"Bandwidth": name, "Type": "Semantic Alert","Time (sec)": sem_t})

    if bw_rows:
        bw_df = pd.DataFrame(bw_rows)
        fig_bw = px.bar(
            bw_df, x="Bandwidth", y="Time (sec)", color="Type", barmode="group",
            color_discrete_map={"Raw Video": "#ef4444", "Semantic Alert": "#22c55e"},
        )
        fig_bw.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#94a3b8",
            xaxis=dict(showgrid=False, color="#64748b"),
            yaxis=dict(showgrid=True, gridcolor="#1e293b", color="#64748b",
                       title="Transmission Time (seconds)"),
            legend=dict(font=dict(color="#94a3b8")),
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig_bw, use_container_width=True)

    # ── Disconnected mode queue simulation ────────────────────────────────────
    st.markdown("<div class='section-header'>Disconnected Mode Simulator</div>",
                unsafe_allow_html=True)

    with st.expander("🔌 Simulate Disconnection / Reconnection", expanded=False):
        st.markdown(
            "When the link is **Disconnected**, semantic alerts are queued locally. "
            "When the link is restored, queued alerts are transmitted first."
        )
        if "bw_queue" not in st.session_state:
            st.session_state.bw_queue = []
        if "bw_delivered" not in st.session_state:
            st.session_state.bw_delivered = []

        col_q1, col_q2, col_q3 = st.columns(3)
        if col_q1.button("📥 Queue 5 Alerts (Disconnected)"):
            sim = BandwidthSimulator(db, session_id="sim_manual")
            sim.set_condition("Disconnected")
            for i in range(5):
                fake_alert = {
                    "camera_id": "CAM-01",
                    "event_type": "ZONE_ENTRY",
                    "object_class": "person",
                    "track_id": i + 100,
                    "severity": "High",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "alert_payload_bytes": 250,
                    "message": f"QUEUED ALERT {i+1}",
                }
                sim.queue_alert(fake_alert)
                st.session_state.bw_queue.append(fake_alert)
            st.success(f"5 alerts queued. Queue size: {len(st.session_state.bw_queue)}")

        if col_q2.button("📡 Reconnect & Deliver Queue"):
            if st.session_state.bw_queue:
                sim = BandwidthSimulator(db, session_id="sim_manual")
                sim.set_condition("10 kbps")
                delivered = []
                for alert in st.session_state.bw_queue:
                    rec = sim.simulate_semantic_alert(alert)
                    delivered.append(rec)
                st.session_state.bw_delivered = delivered
                count = len(delivered)
                st.session_state.bw_queue = []
                st.success(f"Delivered {count} queued alerts over 10 kbps link.")
            else:
                st.info("Queue is empty.")

        if col_q3.button("🗑 Clear"):
            st.session_state.bw_queue = []
            st.session_state.bw_delivered = []

        st.markdown(f"**Queue size:** {len(st.session_state.bw_queue)} alerts pending")

        if st.session_state.bw_delivered:
            df_del = pd.DataFrame(st.session_state.bw_delivered)
            st.dataframe(df_del[["timestamp", "payload_type", "payload_bytes",
                                  "transmission_time_sec", "network_condition"]]
                         if "timestamp" in df_del.columns else df_del,
                         use_container_width=True)

    # ── Historical log ────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Transmission Log</div>",
                unsafe_allow_html=True)
    bw_log = db.get_bandwidth_log(limit=200)
    if bw_log:
        df_log = pd.DataFrame(bw_log)
        show   = [c for c in ["timestamp", "payload_type", "payload_bytes",
                               "transmission_time_sec", "network_condition",
                               "queued", "delivered"] if c in df_log.columns]
        st.dataframe(df_log[show], use_container_width=True)
    else:
        st.info("No transmission records yet. "
                "Run a detection session and alerts will be logged here.")


def _format_time(seconds: float) -> str:
    if seconds == float("inf"):
        return "∞ (disconnected)"
    if seconds < 1:
        return f"{seconds*1000:.0f} ms"
    if seconds < 60:
        return f"{seconds:.1f} sec"
    return f"{seconds/60:.1f} min"
