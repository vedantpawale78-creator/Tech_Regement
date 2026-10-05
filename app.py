"""
app.py — Semantic Sentinel Command Center
Main Streamlit entry point.

Run with:
    streamlit run app.py
"""
import os
import sys

# Ensure project root is on the path so sub-packages resolve correctly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st

# ── Page configuration (must be first Streamlit call) ─────────────────────────
st.set_page_config(
    page_title="Semantic Sentinel — Command Center",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ─── Font ─────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ─── Background ────────────────────────────────────────── */
.stApp {
    background-color: #0a0e1a;
    color: #e2e8f0;
}

/* ─── Sidebar ───────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #111827 100%);
    border-right: 1px solid #1e3a5f;
}
[data-testid="stSidebar"] .stRadio label {
    color: #94a3b8 !important;
    font-size: 0.85rem;
}

/* ─── Metric cards ──────────────────────────────────────── */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #0f1f35 0%, #1a2744 100%);
    border: 1px solid #1e3a5f;
    border-radius: 10px;
    padding: 14px 18px;
}
[data-testid="stMetricValue"] {
    font-size: 1.8rem !important;
    font-weight: 700 !important;
    color: #38bdf8 !important;
}
[data-testid="stMetricLabel"] {
    color: #64748b !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
}

/* ─── Headers ───────────────────────────────────────────── */
h1 { color: #38bdf8 !important; font-weight: 700 !important; }
h2 { color: #7dd3fc !important; font-weight: 600 !important; }
h3 { color: #bae6fd !important; font-weight: 500 !important; }

/* ─── Buttons ───────────────────────────────────────────── */
.stButton > button {
    background: linear-gradient(135deg, #0369a1, #0ea5e9);
    color: #fff !important;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    transition: opacity 0.2s;
}
.stButton > button:hover {
    opacity: 0.85;
}

/* ─── Inputs ────────────────────────────────────────────── */
.stTextInput input, .stSelectbox select, .stNumberInput input {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    color: #e2e8f0 !important;
    border-radius: 6px !important;
}

/* ─── Dataframe ─────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    background: #0f1f35;
}

/* ─── Alert boxes ───────────────────────────────────────── */
.sentinel-alert-critical {
    background: rgba(239, 68, 68, 0.15);
    border-left: 4px solid #ef4444;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
    color: #fca5a5;
}
.sentinel-alert-high {
    background: rgba(249, 115, 22, 0.15);
    border-left: 4px solid #f97316;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
    color: #fdba74;
}
.sentinel-alert-medium {
    background: rgba(234, 179, 8, 0.12);
    border-left: 4px solid #eab308;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
    color: #fde047;
}
.sentinel-alert-low {
    background: rgba(148, 163, 184, 0.1);
    border-left: 4px solid #94a3b8;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
    color: #cbd5e1;
}
.sentinel-status-ok {
    color: #22c55e;
    font-weight: 600;
}
.sentinel-status-warn {
    color: #eab308;
    font-weight: 600;
}
.sentinel-status-err {
    color: #ef4444;
    font-weight: 600;
}

/* ─── Section divider ───────────────────────────────────── */
.section-header {
    border-bottom: 1px solid #1e3a5f;
    padding-bottom: 6px;
    margin-bottom: 16px;
    color: #38bdf8;
    font-weight: 600;
    font-size: 1.1rem;
    letter-spacing: 0.04em;
}

/* ─── Code / monospace ──────────────────────────────────── */
.stCodeBlock, code {
    background: #0d1117 !important;
    border: 1px solid #1e3a5f !important;
    border-radius: 6px !important;
    color: #38bdf8 !important;
}

/* ─── Progress bar ──────────────────────────────────────── */
.stProgress > div > div > div {
    background: linear-gradient(90deg, #0369a1, #38bdf8) !important;
}

/* ─── Tabs ──────────────────────────────────────────────── */
.stTabs [data-baseweb="tab"] {
    background: #0f1f35;
    color: #94a3b8;
    border-radius: 6px 6px 0 0;
}
.stTabs [aria-selected="true"] {
    background: #0369a1 !important;
    color: #fff !important;
}
</style>
""", unsafe_allow_html=True)

# ── Database singleton ────────────────────────────────────────────────────────
from database.database import Database
from config.settings import DEFAULT_DB_PATH

@st.cache_resource
def get_db() -> Database:
    return Database(DEFAULT_DB_PATH)

# ── Sidebar navigation ────────────────────────────────────────────────────────
PAGES = {
    "🏠  Overview":            "overview",
    "📹  Live Surveillance":   "live_surveillance",
    "🌐  Camera Network":      "camera_network",
    "🚨  Alert Center":        "alert_center",
    "📋  Event History":       "event_history",
    "📡  Bandwidth Analytics": "bandwidth_analytics",
    "🔧  System Diagnostics":  "system_diagnostics",
    "⚙️  Settings":            "settings_page",
}

with st.sidebar:
    st.markdown("""
    <div style='text-align:center; padding: 20px 0 10px 0;'>
        <div style='font-size:2.2rem;'>🛡️</div>
        <div style='color:#38bdf8; font-weight:700; font-size:1.1rem;
                    letter-spacing:0.08em; text-transform:uppercase;
                    margin-top:4px;'>Semantic Sentinel</div>
        <div style='color:#475569; font-size:0.72rem; margin-top:2px;'>
            Offline AI Surveillance v2.0
        </div>
    </div>
    <hr style='border-color:#1e3a5f; margin:8px 0 16px 0;'/>
    """, unsafe_allow_html=True)

    page_key = st.radio(
        "Navigation",
        list(PAGES.keys()),
        label_visibility="collapsed",
    )

    st.markdown("""
    <hr style='border-color:#1e3a5f; margin:16px 0 8px 0;'/>
    <div style='color:#334155; font-size:0.68rem; text-align:center;'>
        ⚠️ Simulated system only.<br>No real hardware required.
    </div>
    """, unsafe_allow_html=True)

# ── Page routing ──────────────────────────────────────────────────────────────
db = get_db()
page_module = PAGES[page_key]

if page_module == "overview":
    from pages.overview import render
    render(db)
elif page_module == "live_surveillance":
    from pages.live_surveillance import render
    render(db)
elif page_module == "camera_network":
    from pages.camera_network import render
    render(db)
elif page_module == "alert_center":
    from pages.alert_center import render
    render(db)
elif page_module == "event_history":
    from pages.event_history import render
    render(db)
elif page_module == "bandwidth_analytics":
    from pages.bandwidth_analytics import render
    render(db)
elif page_module == "system_diagnostics":
    from pages.system_diagnostics import render
    render(db)
elif page_module == "settings_page":
    from pages.settings_page import render
    render(db)
