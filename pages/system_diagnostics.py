"""
pages/system_diagnostics.py
System Diagnostics — health check, performance metrics, DB info.
"""
import os
import sys
import sqlite3
import streamlit as st
import pandas as pd
import plotly.express as px

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from config.settings import DEFAULT_DB_PATH, DEFAULT_MODEL_PATH


def render(db):
    st.markdown("<h1>🔧 System Diagnostics</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#64748b; margin-top:-10px;'>"
        "Hardware, software, and database health checks</p>",
        unsafe_allow_html=True,
    )

    tab_sys, tab_db, tab_perf = st.tabs(
        ["🖥️  System Status", "🗄️  Database", "📈  Performance Metrics"]
    )

    # ── System Status ─────────────────────────────────────────────────────────
    with tab_sys:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("<div class='section-header'>Environment</div>",
                        unsafe_allow_html=True)
            checks = {
                "Python Version":  sys.version.split()[0],
                "OS":              sys.platform,
                "Model File":      "✅ Found" if os.path.isfile(DEFAULT_MODEL_PATH)
                                   else "❌ Not found",
                "Database File":   "✅ Found" if os.path.isfile(DEFAULT_DB_PATH)
                                   else "⚠️ Will be created on first run",
            }
            for k, v in checks.items():
                color = "#22c55e" if "✅" in str(v) else (
                    "#ef4444" if "❌" in str(v) else "#94a3b8"
                )
                st.markdown(
                    f"<div style='display:flex; justify-content:space-between; "
                    f"padding:6px 0; border-bottom:1px solid #1e293b;'>"
                    f"<span style='color:#64748b;'>{k}</span>"
                    f"<span style='color:{color}; font-weight:600;'>{v}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            # Package versions
            st.markdown("<br><div class='section-header'>Key Dependencies</div>",
                        unsafe_allow_html=True)
            packages = ["ultralytics", "cv2", "streamlit", "pandas",
                        "plotly", "numpy", "PIL", "psutil"]
            for pkg in packages:
                try:
                    mod = __import__(pkg if pkg != "PIL" else "PIL")
                    ver = getattr(mod, "__version__", "installed")
                    st.markdown(
                        f"<div style='display:flex; justify-content:space-between; "
                        f"padding:5px 0; border-bottom:1px solid #1e293b;'>"
                        f"<span style='color:#64748b;'>{pkg}</span>"
                        f"<span style='color:#22c55e;'>{ver}</span></div>",
                        unsafe_allow_html=True,
                    )
                except ImportError:
                    st.markdown(
                        f"<div style='display:flex; justify-content:space-between; "
                        f"padding:5px 0; border-bottom:1px solid #1e293b;'>"
                        f"<span style='color:#64748b;'>{pkg}</span>"
                        f"<span style='color:#ef4444;'>Not installed</span></div>",
                        unsafe_allow_html=True,
                    )

        with col2:
            st.markdown("<div class='section-header'>Resource Usage</div>",
                        unsafe_allow_html=True)
            if HAS_PSUTIL:
                cpu    = psutil.cpu_percent(interval=0.5)
                mem    = psutil.virtual_memory()
                disk   = psutil.disk_usage(os.path.abspath("."))

                st.metric("CPU Usage", f"{cpu:.1f}%")
                st.metric("RAM Usage",
                           f"{mem.used/1024**3:.1f} GB / {mem.total/1024**3:.1f} GB",
                           f"{mem.percent:.0f}%")
                st.metric("Disk (project drive)",
                           f"{disk.used/1024**3:.1f} GB used / {disk.total/1024**3:.1f} GB total",
                           f"{disk.percent:.0f}%")

                # CPU gauge
                fig = px.pie(
                    values=[cpu, 100 - cpu],
                    names=["Used", "Free"],
                    color_discrete_sequence=["#38bdf8", "#1e293b"],
                    hole=0.7,
                )
                fig.update_traces(textinfo="none")
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    margin=dict(t=0, b=0, l=0, r=0),
                    annotations=[dict(text=f"{cpu:.0f}%\nCPU",
                                      x=0.5, y=0.5, font_size=18,
                                      font_color="#38bdf8",
                                      showarrow=False)],
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Install `psutil` to see resource usage: `pip install psutil`")

    # ── Database ──────────────────────────────────────────────────────────────
    with tab_db:
        st.markdown("<div class='section-header'>Database File</div>",
                    unsafe_allow_html=True)
        if os.path.isfile(DEFAULT_DB_PATH):
            size_kb = os.path.getsize(DEFAULT_DB_PATH) / 1024
            st.markdown(
                f"**Path:** `{DEFAULT_DB_PATH}`<br>"
                f"**Size:** {size_kb:.1f} KB",
                unsafe_allow_html=True,
            )
        else:
            st.info(f"Database not yet created at: `{DEFAULT_DB_PATH}`")

        st.markdown("<div class='section-header'>Table Row Counts</div>",
                    unsafe_allow_html=True)
        try:
            with sqlite3.connect(DEFAULT_DB_PATH) as conn:
                cur = conn.cursor()
                cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [r[0] for r in cur.fetchall()]
                for tbl in tables:
                    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                    count = cur.fetchone()[0]
                    st.markdown(
                        f"<div style='display:flex; justify-content:space-between; "
                        f"padding:6px 0; border-bottom:1px solid #1e293b;'>"
                        f"<span style='color:#64748b;'>{tbl}</span>"
                        f"<span style='color:#38bdf8; font-weight:600;'>{count} rows</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
        except Exception as e:
            st.warning(f"Cannot read database: {e}")

    # ── Performance Metrics ───────────────────────────────────────────────────
    with tab_perf:
        metrics = db.get_metrics(limit=500)
        if not metrics:
            st.info("No performance metrics yet. Start a detection session to populate.")
        else:
            df = pd.DataFrame(metrics)
            cameras = sorted(df["camera_id"].dropna().unique()) if "camera_id" in df.columns else []
            if cameras:
                sel = st.selectbox("Camera", ["All"] + list(cameras))
                if sel != "All":
                    df = df[df["camera_id"] == sel]

            col1, col2, col3 = st.columns(3)
            if "fps" in df.columns:
                col1.metric("Avg FPS", f"{df['fps'].mean():.1f}")
            if "processing_latency_ms" in df.columns:
                col2.metric("Avg Latency", f"{df['processing_latency_ms'].mean():.1f} ms")
            if "detected_objects" in df.columns:
                col3.metric("Total Objects Detected",
                            int(df["detected_objects"].sum()))

            if "processing_latency_ms" in df.columns and "timestamp" in df.columns:
                fig = px.line(df.sort_values("timestamp"),
                              x="timestamp", y="processing_latency_ms",
                              title="Processing Latency Over Time",
                              color_discrete_sequence=["#38bdf8"])
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#94a3b8",
                    xaxis=dict(showgrid=False, color="#64748b"),
                    yaxis=dict(showgrid=True, gridcolor="#1e293b", color="#64748b"),
                    margin=dict(t=30, b=20),
                )
                st.plotly_chart(fig, use_container_width=True)
