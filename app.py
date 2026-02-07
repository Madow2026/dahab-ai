"""
DAHAB AI - Economic News & Market Analysis Platform
Main Entry Point
"""

import streamlit as st
from streamlit_worker import ensure_worker_running

# Page configuration
st.set_page_config(
    page_title="Dahab AI - Market Analysis",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Start background worker automatically
ensure_worker_running()

# Custom CSS for professional dark theme
st.markdown("""
<style>
    .main {
        background-color: #0E1117;
    }
    .stMetric {
        background-color: #1E2130;
        padding: 15px;
        border-radius: 5px;
        border: 1px solid #2E3340;
    }
    .stMetric label {
        color: #FAFAFA !important;
        font-weight: 600;
    }
    h1, h2, h3 {
        color: #D4AF37 !important;
        font-weight: 700;
    }
    .disclaimer-box {
        background-color: #2E1A1A;
        border: 1px solid #D4AF37;
        border-radius: 5px;
        padding: 15px;
        margin: 20px 0;
        color: #FAFAFA;
        font-size: 0.9em;
    }
</style>
""", unsafe_allow_html=True)

# Main welcome page
st.title("📊 Dahab AI - Economic News & Market Analysis Platform")

st.markdown("""
### Professional-Grade Financial Intelligence System

**Dahab AI** is a specialized platform for:
- 📰 Real-time economic news analysis
- 📈 Probabilistic market forecasting
- 🎯 Performance tracking and evaluation
- 💼 Educational portfolio simulation

Navigate using the sidebar to explore different sections.
""")

# Key features
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### 🌍 Multi-Source Analysis")
    st.write("Aggregates and analyzes economic news from global sources with Arabic translation support.")

with col2:
    st.markdown("#### 🎲 Probabilistic Forecasts")
    st.write("Risk-aware predictions with confidence levels - never guarantees, always probabilities.")

with col3:
    st.markdown("#### 📊 Performance Tracking")
    st.write("Continuous evaluation of forecast accuracy vs actual market outcomes.")

st.markdown("---")

# Mandatory disclaimer
st.markdown("""
<div class="disclaimer-box">
<strong>⚠️ Disclaimer</strong><br>
This platform is intended for <strong>educational and analytical purposes only</strong>. 
It does not constitute financial advice, investment recommendations, or solicitation to buy or sell any asset. 
All forecasts are probabilistic in nature, and the displayed portfolio is a simulated environment for learning purposes only.
</div>
""", unsafe_allow_html=True)

st.markdown("---")
st.markdown("*Version 1.0 | January 2026*")
