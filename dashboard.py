import streamlit as st
import pandas as pd
import sqlite3
import os
from config_loader import load_config
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="Semantic Sentinel — Defence Command Center",
    layout="wide",
    page_icon="🛡️",
    initial_sidebar_state="expanded"
)

# ── DARK TACTICAL EDGE-AI DEFENCE COMMAND CENTER THEME ─────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

/* Main App & Background */
.stApp {
    background-color: #0a0e14 !important;
    color: #e2e8f0 !important;
    font-family: 'Inter', -apple-system, sans-serif !important;
}

/* Subtle military/tactical grid pattern */
.stApp::before {
    content: "";
    position: fixed;
    top: 0; left: 0; width: 100%; height: 100%;
    background-image: 
        linear-gradient(rgba(30, 41, 59, 0.12) 1px, transparent 1px),
        linear-gradient(90deg, rgba(30, 41, 59, 0.12) 1px, transparent 1px);
    background-size: 36px 36px;
    pointer-events: none;
    z-index: 0;
}

/* Clean Streamlit Header & Chrome */
header[data-testid="stHeader"] {
    background: transparent !important;
}
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 2.5rem !important;
}

/* Sidebar Styling */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #090d14 0%, #0d1219 100%) !important;
    border-right: 1px solid #1a2333 !important;
}
.sidebar-header {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.8rem;
    font-weight: 700;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding-bottom: 0.5rem;
    margin-bottom: 0.8rem;
    border-bottom: 1px solid #1a2333;
}

/* Tactical Command Center Header */
.tactical-header {
    background: linear-gradient(180deg, #111827 0%, #0d131f 100%);
    border: 1px solid #1e293b;
    border-left: 4px solid #38bdf8;
    border-radius: 8px;
    padding: 1.1rem 1.4rem;
    margin-bottom: 1.4rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
}
.tactical-title-box h1 {
    font-size: 1.7rem !important;
    font-weight: 800 !important;
    letter-spacing: 0.08em !important;
    color: #f8fafc !important;
    margin: 0 !important;
    padding: 0 !important;
    display: flex;
    align-items: center;
    gap: 0.6rem;
}
.tactical-title-box .subtitle {
    font-size: 0.74rem;
    color: #64748b;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 0.25rem;
}
.tactical-status-bar {
    display: inline-flex;
    align-items: center;
    gap: 0.75rem;
    background: #090d14;
    border: 1px solid #1e293b;
    border-radius: 6px;
    padding: 0.45rem 0.85rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.74rem;
}
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    color: #22c55e;
    font-weight: 600;
}
.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: #22c55e;
    box-shadow: 0 0 8px rgba(34, 197, 94, 0.7);
    display: inline-block;
}
.status-divider {
    color: #334155;
}
.status-meta {
    color: #94a3b8;
}
:root {
    --primary-color: #38bdf8;
    --background-color: #0a0e14;
    --secondary-background-color: #111827;
    --text-color: #e2e8f0;
}

.status-meta strong {
    color: #38bdf8;
}

/* Metric Cards */
div[data-testid="stMetric"], [data-testid="metric-container"] {
    background: linear-gradient(180deg, #111827 0%, #0d131f 100%) !important;
    border: 1px solid #1e293b !important;
    border-radius: 8px !important;
    padding: 1rem 1.25rem !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3) !important;
    transition: transform 0.15s ease, border-color 0.15s ease !important;
}
div[data-testid="stMetric"]:hover, [data-testid="metric-container"]:hover {
    border-color: #38bdf8 !important;
    transform: translateY(-1px);
}
[data-testid="stMetricLabel"] {
    color: #94a3b8 !important;
    font-size: 0.72rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
}
[data-testid="stMetricValue"] {
    color: #f8fafc !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 2.1rem !important;
    font-weight: 700 !important;
}

/* Section Headers */
.section-hdr {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.82rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #94a3b8;
    margin-top: 1.2rem;
    margin-bottom: 0.8rem;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid #1a2333;
}
.hdr-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    display: inline-block;
}
.hdr-dot.cyan  { background: #38bdf8; box-shadow: 0 0 6px rgba(56, 189, 248, 0.6); }
.hdr-dot.green { background: #22c55e; box-shadow: 0 0 6px rgba(34, 197, 94, 0.6); }
.hdr-dot.red   { background: #ef4444; box-shadow: 0 0 6px rgba(239, 68, 68, 0.6); }
.hdr-dot.blue  { background: #0284c7; box-shadow: 0 0 6px rgba(2, 132, 199, 0.6); }

/* Bandwidth Analysis Callout Panel */
.bandwidth-panel {
    background: linear-gradient(180deg, #111827 0%, #0d131f 100%);
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
    margin-bottom: 0.85rem;
}
.bw-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #090d14;
    border: 1px solid #1a2333;
    border-radius: 6px;
    padding: 0.6rem 0.85rem;
    font-size: 0.8rem;
}
.bw-row .bw-label {
    color: #94a3b8;
    font-weight: 600;
    font-size: 0.72rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
}
.bw-row .bw-val {
    font-family: 'JetBrains Mono', monospace;
    font-weight: 700;
    color: #f8fafc;
}
.bw-row .bw-val.cyan { color: #38bdf8; }
.bw-row.highlight {
    background: rgba(34, 197, 94, 0.08);
    border-color: rgba(34, 197, 94, 0.35);
}
.bw-row.highlight .bw-label {
    color: #86efac;
}
.bw-row.highlight .bw-val.green {
    color: #22c55e;
    font-size: 1.05rem;
}

/* Dataframe styling */
[data-testid="stDataFrame"] {
    background: #090d14 !important;
    border: 1px solid #1e293b !important;
    border-radius: 8px !important;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3) !important;
}

/* MultiSelect and Radio Controls */
div[data-baseweb="select"] > div {
    background-color: #0d131f !important;
    border: 1px solid #1e293b !important;
    color: #e2e8f0 !important;
}
div[data-baseweb="select"] input {
    color: #e2e8f0 !important;
}
div[data-baseweb="select"] svg {
    fill: #94a3b8 !important;
}
[data-baseweb="tag"] {
    background-color: #1e293b !important;
    border: 1px solid #334155 !important;
}
[data-baseweb="tag"] span {
    color: #38bdf8 !important;
}
[data-baseweb="popover"], [data-baseweb="menu"], ul[role="listbox"] {
    background-color: #0d131f !important;
    border: 1px solid #1e293b !important;
}
li[data-baseweb="menu-item"], li[role="option"] {
    background-color: #0d131f !important;
    color: #e2e8f0 !important;
}
li[data-baseweb="menu-item"]:hover, li[role="option"]:hover, [aria-selected="true"] {
    background-color: #1e293b !important;
    color: #38bdf8 !important;
}
div[data-testid="stRadio"] label {
    color: #cbd5e1 !important;
    font-size: 0.82rem !important;
}

/* Progress bar styling */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #0284c7 0%, #22c55e 100%) !important;
}
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_db_connection(db_path):
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return conn

def load_data():
    config = load_config()
    db_path = config.get('database', {}).get('path', 'data/sentinel.db')
    if not os.path.exists(db_path):
        return pd.DataFrame(), pd.DataFrame()
        
    conn = get_db_connection(db_path)
    
    try:
        alerts_df = pd.read_sql_query("SELECT * FROM alerts ORDER BY timestamp DESC", conn)
        metrics_df = pd.read_sql_query("SELECT * FROM system_metrics ORDER BY timestamp DESC LIMIT 1000", conn)
    except Exception as e:
        st.error(f"Database error: {e}")
        return pd.DataFrame(), pd.DataFrame()
        
    return alerts_df, metrics_df

def main():
    alerts_df, metrics_df = load_data()
    
    # ── TACTICAL HEADER ────────────────────────────────────────────────────────
    cam_count = len(alerts_df['camera_id'].unique()) if (not alerts_df.empty and 'camera_id' in alerts_df.columns) else 1
    node_id = "N1"
    st.markdown(f"""
    <div class="tactical-header">
        <div class="tactical-title-box">
            <h1>🛡️ SEMANTIC SENTINEL</h1>
            <div class="subtitle">EDGE-AI DEFENCE SURVEILLANCE &amp; SEMANTIC ALERT SYSTEM</div>
        </div>
        <div class="tactical-status-bar">
            <span class="status-pill"><span class="status-dot"></span> SYSTEM STATUS: ONLINE</span>
            <span class="status-divider">|</span>
            <span class="status-meta">NODE: <strong>{node_id}</strong></span>
            <span class="status-divider">|</span>
            <span class="status-meta">CAMERAS: <strong>{cam_count}</strong></span>
            <span class="status-divider">|</span>
            <span class="status-meta">MODE: <strong>EDGE AI</strong></span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if alerts_df.empty:
        st.info("No alerts yet. Run the detector or simulator.")
        return
        
    # ── SIDEBAR FILTERS ────────────────────────────────────────────────────────
    st.sidebar.markdown("""
    <div class="sidebar-header">
        <span class="hdr-dot cyan"></span> TACTICAL FILTERS
    </div>
    """, unsafe_allow_html=True)
    selected_camera = st.sidebar.multiselect("Camera ID", options=alerts_df['camera_id'].unique(), default=alerts_df['camera_id'].unique())
    selected_event = st.sidebar.multiselect("Event Type", options=alerts_df['event_type'].unique(), default=alerts_df['event_type'].unique())
    selected_status = st.sidebar.radio("Verification Status", options=["All", "Verified", "Suppressed"])
    
    filtered_df = alerts_df[alerts_df['camera_id'].isin(selected_camera) & alerts_df['event_type'].isin(selected_event)]
    if selected_status == "Verified":
        filtered_df = filtered_df[filtered_df['verified'] == 1]
    elif selected_status == "Suppressed":
        filtered_df = filtered_df[filtered_df['verified'] == 0]
        
    # ── METRIC CARDS ───────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    total_alerts = len(alerts_df)
    verified = len(alerts_df[alerts_df['verified'] == 1])
    suppressed = total_alerts - verified
    fence = len(alerts_df[alerts_df['event_type'] == 'FENCE_CROSSING'])
    loiter = len(alerts_df[alerts_df['event_type'] == 'LOITERING'])
    abandon = len(alerts_df[alerts_df['event_type'] == 'ABANDONED_OBJECT'])
    
    col1.metric("Total Events", total_alerts)
    col2.metric("Verified Alerts", verified)
    col3.metric("Suppressed", suppressed)
    col4.metric("Fence Crossings", fence)
    
    # ── SPLIT ROW: EVENT BREAKDOWN & BANDWIDTH ANALYSIS ─────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown('<div class="section-hdr"><span class="hdr-dot cyan"></span> EVENT BREAKDOWN</div>', unsafe_allow_html=True)
        if not filtered_df.empty:
            color_palette = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#38bdf8', '#8b5cf6', '#64748b']
            fig = px.pie(filtered_df, names='event_type', title=None, hole=0.45, color_discrete_sequence=color_palette)
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family='Inter', color='#cbd5e1', size=12),
                margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=-0.22,
                    xanchor="center",
                    x=0.5,
                    font=dict(size=11, color='#94a3b8')
                ),
                showlegend=True
            )
            fig.update_traces(
                textposition='inside',
                textinfo='percent',
                marker=dict(line=dict(color='#0a0e14', width=2))
            )
            st.plotly_chart(fig, use_container_width=True)
            
    with col_r:
        st.markdown('<div class="section-hdr"><span class="hdr-dot green"></span> BANDWIDTH / SEMANTIC ALERT ANALYSIS</div>', unsafe_allow_html=True)
        # Estimate semantic size vs raw video (assume 1 min video vs semantic JSON)
        raw_size_mb = 15.0 # Estimate 1 min 1080p
        semantic_size_kb = len(filtered_df) * 0.25 # ~250 bytes per alert
        reduction = 100.0 if raw_size_mb == 0 else ((raw_size_mb * 1024 - semantic_size_kb) / (raw_size_mb * 1024)) * 100
        
        st.markdown(f"""
        <div class="bandwidth-panel">
            <div class="bw-row">
                <span class="bw-label">RAW VIDEO DATA (1 MIN EST.)</span>
                <span class="bw-val">{raw_size_mb:.2f} MB</span>
            </div>
            <div class="bw-row">
                <span class="bw-label">SEMANTIC ALERT DATA</span>
                <span class="bw-val cyan">{semantic_size_kb:.2f} KB</span>
            </div>
            <div class="bw-row highlight">
                <span class="bw-label">BANDWIDTH REDUCTION</span>
                <span class="bw-val green">{reduction:.4f}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.progress(min(1.0, semantic_size_kb / (raw_size_mb * 1024 + 0.001)))
    
    # ── RECENT ALERTS TIMELINE ─────────────────────────────────────────────────
    st.markdown('<div class="section-hdr"><span class="hdr-dot red"></span> RECENT ALERTS (TIMELINE)</div>', unsafe_allow_html=True)
    
    if not filtered_df.empty:
        if 'duration' in filtered_df.columns:
            filtered_df['Duration'] = filtered_df.apply(
                lambda row: f"{row['duration']:.1f} sec" if pd.notnull(row['duration']) and row['duration'] > 0 else "N/A", 
                axis=1
            )
        else:
            filtered_df['Duration'] = "N/A"
            
        cols_to_show = ['timestamp', 'camera_id', 'event_type', 'object_class', 'confidence', 'severity', 'verified', 'suppression_reason', 'message', 'Duration']
        # only select columns that exist in the dataframe to avoid errors
        cols_to_show = [c for c in cols_to_show if c in filtered_df.columns]
        
        # Style severity: HIGH/CRITICAL in red, MEDIUM in amber, LOW in green/neutral
        def highlight_severity(val):
            v = str(val).upper()
            if "CRITICAL" in v or "HIGH" in v:
                return "color: #ef4444; font-weight: 700;"
            elif "MEDIUM" in v:
                return "color: #f59e0b; font-weight: 600;"
            elif "LOW" in v:
                return "color: #22c55e;"
            return ""

        df_display = filtered_df[cols_to_show].head(50)
        try:
            styled_df = df_display.style.set_properties(**{
                'background-color': '#0d131f',
                'color': '#cbd5e1',
                'border-color': '#1e293b'
            }).set_table_styles([
                {'selector': 'th', 'props': [('background-color', '#111827'), ('color', '#94a3b8'), ('font-weight', '700'), ('border-color', '#1e293b')]},
                {'selector': 'th.col_heading', 'props': [('background-color', '#111827'), ('color', '#94a3b8')]},
                {'selector': 'th.row_heading', 'props': [('background-color', '#111827'), ('color', '#64748b')]}
            ])
            if 'severity' in df_display.columns:
                if hasattr(styled_df, 'map'):
                    styled_df = styled_df.map(highlight_severity, subset=['severity'])
                else:
                    styled_df = styled_df.applymap(highlight_severity, subset=['severity'])
            st.dataframe(styled_df, use_container_width=True)
        except Exception:
            st.dataframe(df_display, use_container_width=True)
    else:
        st.info("No alerts match the current filters.")
    
    # ── PERFORMANCE METRICS ────────────────────────────────────────────────────
    if not metrics_df.empty:
        st.markdown('<div class="section-hdr"><span class="hdr-dot blue"></span> PERFORMANCE METRICS</div>', unsafe_allow_html=True)
        fig2 = px.line(metrics_df, x='timestamp', y='fps', title=None)
        fig2.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(family='Inter', color='#cbd5e1', size=12),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis=dict(gridcolor='rgba(255,255,255,0.06)', zerolinecolor='rgba(255,255,255,0.06)'),
            yaxis=dict(gridcolor='rgba(255,255,255,0.06)', zerolinecolor='rgba(255,255,255,0.06)')
        )
        fig2.update_traces(line=dict(color='#38bdf8', width=2))
        st.plotly_chart(fig2, use_container_width=True)

if __name__ == '__main__':
    main()
