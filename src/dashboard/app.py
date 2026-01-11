import streamlit as st
import pandas as pd
import psycopg2
import time
import plotly.express as px
import os

# Configuration
POSTGRES_HOST = os.environ.get('POSTGRES_HOST', 'postgres')
POSTGRES_DB = os.environ.get('POSTGRES_DB', 'fraud_detection')
POSTGRES_USER = os.environ.get('POSTGRES_USER', 'admin')
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD', 'password')

from sqlalchemy import create_engine

def get_engine():
    return create_engine(f'postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{POSTGRES_DB}')

def get_connection():
    return psycopg2.connect(
        host=POSTGRES_HOST,
        database=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )

st.set_page_config(
    page_title="Fraud Guard Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for dark theme and styling
st.markdown("""
    <style>
    .big-font {
        font_size:30px !important;
        font-weight: bold;
    }
    .metric-card {
        background-color: #1E1E1E;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #333;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ Real-Time Fraud Detection System")

@st.cache_data(ttl=5)
def load_data():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            query = "SELECT * FROM fraud_alerts ORDER BY timestamp DESC LIMIT 100"
            df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        return pd.DataFrame()

def update_feedback(alert_id, feedback_value):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE fraud_alerts SET feedback = %s WHERE alert_id = %s", (feedback_value, int(alert_id)))
        conn.commit()
        conn.close()
        # No toast here as it might disrupt the loop flow or behave oddly in auto-refresh
    except Exception as e:
        st.error(f"Error updating feedback: {e}")

# Layout
col1, col2 = st.columns([2, 1])

# Placeholder container for auto-refresh
placeholder = st.empty()

while True:
    data = load_data()
    
    with placeholder.container():
        # Top Metrics
        m1, m2, m3 = st.columns(3)
        if not data.empty:
            total_fraud = len(data)
            high_value_count = len(data[data['reason'] == 'High Value Transaction'])
            impossible_travel_count = len(data[data['reason'] == 'Impossible Travel'])
            
            m1.metric("🚨 Total Fraud Detected", total_fraud, delta_color="inverse")
            m2.metric("💸 High Value Alerts", high_value_count)
            m3.metric("✈️ Impossible Travel", impossible_travel_count)
        else:
            m1.metric("🚨 Total Fraud Detected", 0)
            m2.metric("💸 High Value Alerts", 0)
            m3.metric("✈️ Impossible Travel", 0)

        st.divider()

        # Split view: Table & Map
        row1_col1, row1_col2 = st.columns([1, 1])
        
        with row1_col1:
            st.subheader("Recent Alerts")
            if not data.empty:
                # Add actions using expanders
                # Note: modifying database inside a potential rerun loop can be tricky in Streamlit.
                # Ideally we use callbacks, but for this simple auto-refresh loop, buttons work if clicked before refresh.
                for index, row in data.iterrows():
                    # Unique key for each expander
                    with st.expander(f"{row['timestamp'].strftime('%H:%M:%S')} - {row['reason']} (User {row['user_id']})"):
                        st.write(f"**Details:** {row['details']}")
                        current_fb = row['feedback'] if 'feedback' in row and row['feedback'] else 'None'
                        st.write(f"**Current Feedback:** {current_fb}")
                        
                        c1, c2 = st.columns(2)
                        with c1:
                            if st.button("✅ True Fraud", key=f"tf_{row['alert_id']}"):
                                update_feedback(row['alert_id'], "True Fraud")
                                st.rerun()
                        with c2:
                            if st.button("❌ False Positive", key=f"fp_{row['alert_id']}"):
                                update_feedback(row['alert_id'], "False Positive")
                                st.rerun()
            else:
                st.info("Waiting for alerts...")

        with row1_col2:
            st.subheader("Global Fraud Heatmap")
            if not data.empty and 'lat' in data.columns and 'lon' in data.columns:
                 # Check if we have valid coordinates (not null)
                 map_data = data.dropna(subset=['lat', 'lon'])
                 if not map_data.empty:
                     st.map(map_data, latitude='lat', longitude='lon')
                 else:
                     st.info("No location data available for current alerts.")
            else:
                 st.info("Waiting for data...")

    time.sleep(2) # Refresh rate
