"""
pages/alert_center.py
Alert Center — view, filter, and export verified alerts with explanations.
"""
import json
import io
import streamlit as st
import pandas as pd


def render(db):
    st.markdown("<h1>🚨 Alert Center</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#64748b; margin-top:-10px;'>"
        "Verified security events with contextual explanations</p>",
        unsafe_allow_html=True,
    )

    # ── Filters sidebar ───────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("---")
        st.markdown("**Alert Filters**")
        alerts_all = db.get_alerts(limit=2000)
        if not alerts_all:
            st.info("No alerts yet.")
            return

        df_all = pd.DataFrame(alerts_all)
        cameras   = sorted(df_all["camera_id"].dropna().unique().tolist()) if "camera_id" in df_all else []
        ev_types  = sorted(df_all["event_type"].dropna().unique().tolist()) if "event_type" in df_all else []
        severities = ["All", "Critical", "High", "Medium", "Low"]

        sel_cams  = st.multiselect("Camera", cameras, default=cameras)
        sel_evts  = st.multiselect("Event Type", ev_types, default=ev_types)
        sel_sev   = st.selectbox("Severity", severities)
        verified_only = st.checkbox("Verified only", value=True)

    # ── Apply filters ─────────────────────────────────────────────────────────
    df = df_all.copy()
    if sel_cams:
        df = df[df["camera_id"].isin(sel_cams)]
    if sel_evts:
        df = df[df["event_type"].isin(sel_evts)]
    if sel_sev != "All" and "severity" in df.columns:
        df = df[df["severity"] == sel_sev]
    if verified_only and "verified" in df.columns:
        df = df[df["verified"] == 1]

    # ── Summary row ───────────────────────────────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Showing", len(df))
    c2.metric("Critical", len(df[df["severity"] == "Critical"]) if "severity" in df.columns else 0)
    c3.metric("High", len(df[df["severity"] == "High"]) if "severity" in df.columns else 0)
    c4.metric("Medium", len(df[df["severity"] == "Medium"]) if "severity" in df.columns else 0)

    st.markdown("<hr style='border-color:#1e3a5f; margin:12px 0;'>", unsafe_allow_html=True)

    if df.empty:
        st.info("No alerts match the selected filters.")
        return

    # ── Alert cards ───────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Alert Feed</div>", unsafe_allow_html=True)

    severity_class = {
        "Critical": "sentinel-alert-critical",
        "High":     "sentinel-alert-high",
        "Medium":   "sentinel-alert-medium",
        "Low":      "sentinel-alert-low",
    }

    for _, row in df.head(50).iterrows():
        sev  = str(row.get("severity", "Low"))
        cls  = severity_class.get(sev, "sentinel-alert-low")
        evt  = row.get("event_type", "UNKNOWN")
        cam  = row.get("camera_id", "?")
        tid  = row.get("track_id", "?")
        obj  = row.get("object_class", "?")
        ts   = str(row.get("timestamp", ""))[:19]
        v_st = row.get("verification_state", "—")
        conf = row.get("confidence", 0.0)
        expl = row.get("explanation", "—")
        msg  = row.get("message", "—")

        with st.expander(f"[{sev}] {evt} — {cam} — {ts}", expanded=False):
            st.markdown(f"""
            <div class='{cls}'>
                <b>{evt}</b> &nbsp;|&nbsp; {cam} &nbsp;|&nbsp;
                Track-{tid} &nbsp;|&nbsp; {obj}<br>
                <span style='font-size:0.78rem;'>
                    Severity: <b>{sev}</b> &nbsp;|&nbsp;
                    State: <b>{v_st}</b> &nbsp;|&nbsp;
                    Confidence: {float(conf):.0%} &nbsp;|&nbsp;
                    {ts}
                </span>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("**Semantic Alert Message:**")
            st.code(msg, language=None)

            st.markdown("**Explanation:**")
            st.markdown(f"> {expl}")

    # ── Export ────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("<div class='section-header'>Export</div>", unsafe_allow_html=True)
    col_csv, col_json = st.columns(2)

    with col_csv:
        csv_buf = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Export CSV",
            data=csv_buf,
            file_name="sentinel_alerts.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col_json:
        json_buf = json.dumps(df.to_dict(orient="records"), indent=2, default=str).encode("utf-8")
        st.download_button(
            "⬇️ Export JSON",
            data=json_buf,
            file_name="sentinel_alerts.json",
            mime="application/json",
            use_container_width=True,
        )

    # ── Full table ────────────────────────────────────────────────────────────
    st.markdown("<div class='section-header'>Full Alert Table</div>",
                unsafe_allow_html=True)
    show = [c for c in ["timestamp", "camera_id", "event_type", "object_class",
                          "severity", "verification_state", "confidence",
                          "verified", "suppression_reason", "zone_name"]
            if c in df.columns]
    st.dataframe(df[show], use_container_width=True)
