"""
pages/camera_network.py
Camera Network — Add, view, and remove simulated cameras.
"""
import os
import streamlit as st
import pandas as pd
from modules.camera_manager import CameraManager


def render(db):
    st.markdown("<h1>🌐 Camera Network</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#64748b; margin-top:-10px;'>"
        "Manage simulated surveillance cameras. "
        "Each camera maps to a local video file for detection simulation.</p>",
        unsafe_allow_html=True,
    )

    mgr = CameraManager(db)

    tab_list, tab_add = st.tabs(["📋  Camera List", "➕  Add Camera"])

    # ── Camera List ───────────────────────────────────────────────────────────
    with tab_list:
        cameras = mgr.get_cameras()
        if not cameras:
            st.info("No cameras registered yet. Use the **Add Camera** tab.")
        else:
            for cam in cameras:
                status        = cam.get("status", "idle")
                status_colors = {"active": "#22c55e", "idle": "#94a3b8", "error": "#ef4444"}
                sc            = status_colors.get(status, "#94a3b8")

                with st.container():
                    cols = st.columns([0.5, 2, 2, 2, 1.5, 1])
                    cols[0].markdown(
                        f"<div style='font-size:1.6rem; text-align:center;'>📹</div>",
                        unsafe_allow_html=True,
                    )
                    cols[1].markdown(
                        f"**{cam['camera_id']}**<br>"
                        f"<span style='color:#64748b; font-size:0.8rem;'>{cam['name']}</span>",
                        unsafe_allow_html=True,
                    )
                    src = cam.get("source_path", "")
                    cols[2].markdown(
                        f"<span style='color:#94a3b8; font-size:0.8rem;'>"
                        f"{os.path.basename(src)}</span>",
                        unsafe_allow_html=True,
                    )
                    cols[3].markdown(
                        f"<span style='color:#64748b; font-size:0.78rem;'>"
                        f"{cam.get('location','—')}</span>",
                        unsafe_allow_html=True,
                    )
                    cols[4].markdown(
                        f"<span style='color:{sc}; font-weight:600; "
                        f"font-size:0.78rem;'>{status.upper()}</span>",
                        unsafe_allow_html=True,
                    )
                    if cols[5].button("🗑 Remove", key=f"rm_{cam['camera_id']}"):
                        ok, msg = mgr.remove_camera(cam["camera_id"])
                        if ok:
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

                st.markdown(
                    "<hr style='border-color:#1e293b; margin:6px 0;'>",
                    unsafe_allow_html=True,
                )

            # Summary table
            st.markdown("<div class='section-header'>Summary</div>",
                        unsafe_allow_html=True)
            df = pd.DataFrame(cameras)
            show = [c for c in ["camera_id", "name", "location", "status",
                                 "added_at", "last_active"] if c in df.columns]
            st.dataframe(df[show], use_container_width=True)

    # ── Add Camera ────────────────────────────────────────────────────────────
    with tab_add:
        st.markdown("#### Register a Simulated Camera")
        st.markdown(
            "<p style='color:#64748b; font-size:0.85rem;'>"
            "Point a camera entry to a local video file (.mp4, .avi, .mov).<br>"
            "The file must exist on this machine. No physical camera is required.</p>",
            unsafe_allow_html=True,
        )

        with st.form("add_camera_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            cam_id   = col1.text_input("Camera ID *", placeholder="CAM-01",
                                        help="Unique identifier, e.g. CAM-01")
            cam_name = col2.text_input("Display Name", placeholder="North Gate",
                                        help="Human-friendly label")

            source = st.text_input(
                "Video File Path *",
                placeholder=r"C:\videos\patrol.mp4",
                help="Full path to a local .mp4 / .avi / .mov file",
            )
            location = st.text_input("Location / Description",
                                      placeholder="Border checkpoint — North sector")

            submitted = st.form_submit_button("➕ Register Camera",
                                               use_container_width=True)

        if submitted:
            ok, msg = mgr.add_camera(
                cam_id.strip(), cam_name.strip(), source.strip(), location.strip()
            )
            if ok:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)

        # Quick-add demo note
        st.markdown("---")
        st.markdown("#### 💡 Quick Demo")
        st.markdown(
            "If you don't have a video file, download a sample or use "
            "[this free surveillance clip](https://pixabay.com/videos/search/people%20walking/) "
            "and save it locally."
        )

        with st.form("demo_camera_form"):
            st.markdown("**Add a demo camera using an existing file in the project:**")
            demo_files = []
            for d in ["clips", "data", "."]:
                if os.path.isdir(d):
                    for f in os.listdir(d):
                        if f.lower().endswith((".mp4", ".avi", ".mov")):
                            demo_files.append(os.path.join(d, f))
            if demo_files:
                chosen = st.selectbox("Found local video files:", demo_files)
                demo_id   = st.text_input("Camera ID for demo", value="DEMO-01")
                demo_name = st.text_input("Name", value="Demo Camera")
                if st.form_submit_button("Add Demo Camera"):
                    ok, msg = mgr.add_camera(demo_id.strip(), demo_name,
                                             os.path.abspath(chosen), "Demo")
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)
            else:
                st.info("No .mp4 / .avi / .mov files found in project folders. "
                        "Add a video file to the `clips/` directory.")
                st.form_submit_button("(No files found)", disabled=True)
