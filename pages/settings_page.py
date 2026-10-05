"""
pages/settings_page.py
Settings — configure thresholds, add demo data, manage zones.
"""
import time
import streamlit as st
import json
from config.settings import (
    DEFAULT_CONFIDENCE, MIN_TRACK_AGE, COOLDOWN_SECONDS,
    LOITER_SECONDS, ABANDONED_SECONDS,
)


def render(db):
    st.markdown("<h1>⚙️ Settings</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#64748b; margin-top:-10px;'>"
        "Configure detection thresholds, manage zones, and run demo simulator</p>",
        unsafe_allow_html=True,
    )

    tab_thresh, tab_zones, tab_demo = st.tabs(
        ["🎛️  Thresholds", "🗺️  Zone Editor", "🧪  Demo Simulator"]
    )

    # ── Thresholds ────────────────────────────────────────────────────────────
    with tab_thresh:
        st.markdown(
            "<p style='color:#64748b; font-size:0.85rem;'>"
            "These values are used by the Event Engine and Contextual Verifier. "
            "Changes apply to new detection sessions only.</p>",
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Detection**")
            conf  = st.slider("Confidence Threshold", 0.10, 0.95, DEFAULT_CONFIDENCE, 0.05)
            track = st.number_input("Min Track Age (frames)", 1, 30, MIN_TRACK_AGE)
            cd    = st.number_input("Cooldown Between Alerts (sec)", 1, 60, COOLDOWN_SECONDS)

        with c2:
            st.markdown("**Rule Thresholds**")
            loiter  = st.number_input("Loitering Threshold (sec)", 3, 120, LOITER_SECONDS)
            abandon = st.number_input("Abandoned Object Threshold (sec)", 3, 300, ABANDONED_SECONDS)
            aband_d = st.number_input("Abandoned: Person Proximity (px)", 50, 500, 150)

        if st.button("💾 Save to config.yaml", use_container_width=True):
            import yaml, os
            cfg_path = "config.yaml"
            try:
                with open(cfg_path) as f:
                    cfg = yaml.safe_load(f) or {}
                cfg.setdefault("model", {})["confidence"] = conf
                cfg.setdefault("verification", {}).update({
                    "min_track_age": track,
                    "cooldown_seconds": cd,
                })
                cfg.setdefault("rules", {}).update({
                    "loiter_seconds": loiter,
                    "abandoned_seconds": abandon,
                    "abandoned_person_distance_pixels": aband_d,
                })
                with open(cfg_path, "w") as f:
                    yaml.safe_dump(cfg, f, default_flow_style=False)
                st.success("Settings saved to config.yaml ✅")
            except Exception as e:
                st.error(f"Failed to save: {e}")

    # ── Zone Editor ───────────────────────────────────────────────────────────
    with tab_zones:
        cameras = db.get_cameras()
        if not cameras:
            st.warning("Register a camera in **Camera Network** first.")
        else:
            cam_opts = {f"{c['camera_id']} — {c['name']}": c["camera_id"]
                        for c in cameras}
            sel_cam_label = st.selectbox("Select Camera for Zone", list(cam_opts.keys()))
            sel_cam_id    = cam_opts[sel_cam_label]

            # Show existing zones
            zones = db.get_zones(camera_id=sel_cam_id)
            if zones:
                st.markdown(f"**Existing zones for {sel_cam_id}:**")
                for z in zones:
                    cols = st.columns([3, 1, 1])
                    cols[0].markdown(
                        f"`{z['zone_name']}` — {z['zone_type']} — "
                        f"{len(z['polygon'])} vertices"
                    )
                    cols[1].code(
                        json.dumps(z["polygon"][:2], indent=None), language=None
                    )
                    if cols[2].button("🗑 Delete", key=f"del_zone_{z['id']}"):
                        db.delete_zone(z["id"])
                        st.success(f"Zone '{z['zone_name']}' deleted.")
                        st.rerun()
            else:
                st.info(f"No zones configured for {sel_cam_id}.")

            st.markdown("---")
            st.markdown("#### Add New Zone (manual polygon entry)")
            st.markdown(
                "<p style='color:#64748b; font-size:0.82rem;'>"
                "Enter polygon vertices as comma-separated x,y pairs (one per line).</p>",
                unsafe_allow_html=True,
            )

            with st.form("add_zone_form"):
                zone_name = st.text_input("Zone Name", placeholder="Restricted Area 1")
                zone_type = st.selectbox("Zone Type", ["restricted", "warning", "safe"])
                pts_raw   = st.text_area(
                    "Polygon Points (x,y per line)",
                    placeholder="100,150\n400,150\n400,350\n100,350",
                    height=120,
                )
                submitted = st.form_submit_button("➕ Add Zone", use_container_width=True)

            if submitted:
                try:
                    polygon = []
                    for line in pts_raw.strip().splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        parts = line.replace(";", ",").split(",")
                        x, y  = int(parts[0].strip()), int(parts[1].strip())
                        polygon.append([x, y])

                    if len(polygon) < 3:
                        st.error("A zone needs at least 3 points.")
                    elif not zone_name.strip():
                        st.error("Zone name is required.")
                    else:
                        zid = db.add_zone(sel_cam_id, zone_name.strip(),
                                          polygon, zone_type)
                        st.success(f"Zone '{zone_name}' added with ID {zid}.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Invalid polygon data: {e}")

    # ── Demo Simulator ────────────────────────────────────────────────────────
    with tab_demo:
        st.markdown(
            "Run the built-in scenario simulator to populate the database with "
            "synthetic events. **These are not real detections** — they are scripted "
            "scenarios for testing and demonstration purposes.",
        )

        col1, col2 = st.columns(2)
        n_events = col1.slider("Number of Events to Generate", 5, 100, 20)
        cam_opt  = col2.selectbox(
            "Target Camera",
            ["CAM-SIM-01"] + [c["camera_id"] for c in db.get_cameras()],
        )

        if st.button("🧪 Run Demo Simulation", use_container_width=True):
            _run_demo_simulation(db, cam_opt, n_events)

        st.markdown("---")
        st.markdown("#### Legacy Demo Simulator")
        st.markdown(
            "Run the original `demo_simulator.py` script (3 events, fixed scenarios)."
        )
        if st.button("Run Legacy Simulator"):
            import subprocess
            result = subprocess.run(
                ["python", "demo_simulator.py"],
                capture_output=True, text=True, cwd="."
            )
            if result.returncode == 0:
                st.success("Legacy simulator completed.")
                st.code(result.stdout)
            else:
                st.error("Simulator failed.")
                st.code(result.stderr)


def _run_demo_simulation(db, camera_id: str, n_events: int):
    """Generate synthetic alert records for demonstration."""
    import random
    from datetime import datetime, timedelta
    from core.semantic_alerts import SemanticAlertEngine

    alert_eng = SemanticAlertEngine(database=db, camera_id=camera_id)

    event_types = ["ZONE_ENTRY", "LOITERING", "ABANDONED_OBJECT", "ZONE_ENTRY"]
    severities  = ["Low", "Medium", "High", "Critical"]
    objects     = ["person", "person", "person", "backpack"]

    progress = st.progress(0)
    generated = 0

    base_time = datetime.now() - timedelta(minutes=n_events * 2)

    for i in range(n_events):
        et     = random.choice(event_types)
        sev    = random.choice(severities)
        obj    = "backpack" if et == "ABANDONED_OBJECT" else "person"
        tid    = random.randint(1, 50)
        conf   = round(random.uniform(0.45, 0.95), 2)
        ts     = (base_time + timedelta(minutes=i * 2 +
                   random.randint(0, 90))).isoformat()
        dur    = round(random.uniform(5, 45), 1) if et != "ZONE_ENTRY" else 0.0
        v_state = random.choice(["Verified", "Verified", "Under Verification"])
        verified = v_state == "Verified"
        expl   = (
            f"Demo scenario {i+1}: {et} detected for Track-{tid} ({obj}). "
            f"Confidence: {conf:.0%}. Duration: {dur}s. "
            f"[SYNTHETIC — not a real detection]"
        )
        msg = (
            f"{camera_id} | {et} | {obj} | Track-{tid} | {sev} | "
            f"{ts[:19]} | Verification: {v_state}"
        )

        db.insert_alert({
            "timestamp":          ts,
            "camera_id":          camera_id,
            "event_type":         et,
            "track_id":           tid,
            "object_class":       obj,
            "direction":          "ENTER" if et == "ZONE_ENTRY" else None,
            "confidence":         conf,
            "severity":           sev,
            "message":            msg,
            "verified":           verified,
            "suppression_reason": None if verified else "DEMO_UNCONFIRMED",
            "duration":           dur,
            "explanation":        expl,
            "verification_state": v_state,
            "zone_name":          "Demo Zone",
            "alert_payload_bytes": len(msg.encode()),
        })
        generated += 1
        progress.progress(generated / n_events)
        time.sleep(0.02)

    st.success(f"✅ Generated {generated} synthetic demo events for **{camera_id}**.")
    st.info("Refresh the **Overview** and **Alert Center** pages to see the data.")
