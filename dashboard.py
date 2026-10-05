import streamlit as st
import pandas as pd
import sqlite3
import os
from config_loader import load_config
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Semantic Sentinel", layout="wide", page_icon="🛡️")

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
    st.title("🛡️ Semantic Sentinel")
    st.subheader("Offline Edge-AI Surveillance Dashboard")
    
    alerts_df, metrics_df = load_data()
    
    if alerts_df.empty:
        st.info("No alerts yet. Run the detector or simulator.")
        return
        
    # Sidebar Filters
    st.sidebar.header("Filters")
    selected_camera = st.sidebar.multiselect("Camera ID", options=alerts_df['camera_id'].unique(), default=alerts_df['camera_id'].unique())
    selected_event = st.sidebar.multiselect("Event Type", options=alerts_df['event_type'].unique(), default=alerts_df['event_type'].unique())
    selected_status = st.sidebar.radio("Status", options=["All", "Verified", "Suppressed"])
    
    filtered_df = alerts_df[alerts_df['camera_id'].isin(selected_camera) & alerts_df['event_type'].isin(selected_event)]
    if selected_status == "Verified":
        filtered_df = filtered_df[filtered_df['verified'] == 1]
    elif selected_status == "Suppressed":
        filtered_df = filtered_df[filtered_df['verified'] == 0]
        
    # Metrics
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
    
    st.markdown("---")
    
    col_l, col_r = st.columns(2)
    with col_l:
        st.subheader("Event Breakdown")
        if not filtered_df.empty:
            fig = px.pie(filtered_df, names='event_type', title="Alert Types", hole=0.3)
            st.plotly_chart(fig, use_container_width=True)
            
    with col_r:
        st.subheader("Bandwidth / Semantic Alert Analysis")
        # Estimate semantic size vs raw video (assume 1 min video vs semantic JSON)
        raw_size_mb = 15.0 # Estimate 1 min 1080p
        semantic_size_kb = len(filtered_df) * 0.25 # ~250 bytes per alert
        reduction = 100.0 if raw_size_mb == 0 else ((raw_size_mb * 1024 - semantic_size_kb) / (raw_size_mb * 1024)) * 100
        
        st.write(f"**Raw Video Data (1 min est.):** {raw_size_mb:.2f} MB")
        st.write(f"**Semantic Alert Data:** {semantic_size_kb:.2f} KB")
        st.write(f"**Bandwidth Reduction:** {reduction:.4f}%")
        st.progress(min(1.0, semantic_size_kb / (raw_size_mb * 1024 + 0.001)))
    
    st.subheader("Recent Alerts (Timeline)")
    
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
        
        st.dataframe(filtered_df[cols_to_show].head(50), use_container_width=True)
    else:
        st.info("No alerts match the current filters.")
    
    if not metrics_df.empty:
        st.subheader("Performance Metrics")
        fig2 = px.line(metrics_df, x='timestamp', y='fps', title='System FPS')
        st.plotly_chart(fig2, use_container_width=True)

if __name__ == '__main__':
    main()
