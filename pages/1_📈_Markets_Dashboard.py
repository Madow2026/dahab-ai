"""
Home / Markets Dashboard
Real-time market overview with key indicators
AUTO-REFRESHING - Read-only display
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timezone
import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.db import get_db
from ui.sidebar import render_sidebar

st.set_page_config(page_title="Markets Dashboard", page_icon="📈", layout="wide")

# Auto-refresh every 30 seconds
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = time.time()

current_time = time.time()
if current_time - st.session_state.last_refresh > 30:
    st.session_state.last_refresh = current_time
    st.rerun()

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #1E2130;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #2E3340;
        margin: 10px 0;
    }
    .positive {
        color: #00FF00;
    }
    .negative {
        color: #FF4444;
    }
    .alert-box {
        background-color: #2E2130;
        border-left: 4px solid #D4AF37;
        padding: 15px;
        margin: 10px 0;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 Markets Dashboard")
st.caption("🔄 Auto-refreshing every 30 seconds | Worker process updates data continuously")

# Get market data from database
db = get_db()

PAGE_KEY = 'dashboard'

if f"_page_new_since_{PAGE_KEY}" not in st.session_state:
    try:
        st.session_state[f"_page_new_since_{PAGE_KEY}"] = int(db.get_page_new_count(PAGE_KEY) or 0)
    except Exception:
        st.session_state[f"_page_new_since_{PAGE_KEY}"] = 0

try:
    db.mark_page_seen(PAGE_KEY)
except Exception:
    pass

render_sidebar(db, current_page_key=PAGE_KEY)

@st.cache_data(ttl=15)  # Cache for 15 seconds only
def fetch_market_data():
    """Fetch latest prices from database with timestamps"""
    assets = ['USD Index', 'Gold', 'Silver', 'Oil', 'Bitcoin']
    market_data = {}
    
    for asset in assets:
        latest = db.get_latest_price(asset)
        change_data = db.get_price_change(asset)
        if latest:
            # Calculate age of data
            try:
                ts = datetime.fromisoformat(latest['timestamp'])
                now_dt = datetime.now(ts.tzinfo) if getattr(ts, 'tzinfo', None) else datetime.now()
                age_seconds = (now_dt - ts).total_seconds()
                is_stale = age_seconds > 300  # 5 minutes
            except:
                is_stale = True
            
            market_data[asset] = {
                'price': latest['price'],
                'timestamp': latest.get('timestamp'),
                'change': change_data.get('change'),
                'change_percent': change_data.get('change_percent'),
                'prev_timestamp': change_data.get('prev_timestamp'),
                'is_stale': is_stale
            }
        else:
            market_data[asset] = {
                'price': None,
                'timestamp': None,
                'change': None,
                'change_percent': None,
                'prev_timestamp': None,
                'is_stale': False
            }
    
    return market_data

try:
    with st.spinner("Loading market data..."):
        market_data = fetch_market_data()
    
    last_updated = None
    try:
        last_updated = db.get_page_last_updated(PAGE_KEY)
    except Exception:
        last_updated = None
    new_since = int(st.session_state.get(f"_page_new_since_{PAGE_KEY}", 0) or 0)

    # Display time + per-page indicators
    if last_updated:
        st.caption(f"Last updated: {last_updated} | New since last visit: {new_since}")
    else:
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | New since last visit: {new_since}")
    
    # Main metrics
    st.subheader("💹 Live Market Prices")
    
    # Show warning if any data is stale
    stale_count = sum(1 for d in market_data.values() if d.get('is_stale'))
    if stale_count > 0:
        st.warning(f"⚠️ {stale_count} asset(s) showing stale data (>5 min old). Worker may be delayed.")
    
    cols = st.columns(5)

    def _fmt_price(asset: str, price: float) -> str:
        if price is None:
            return "N/A"
        if asset == 'Bitcoin':
            return f"${price:,.0f}"
        if asset == 'USD Index':
            return f"{price:,.4f}"
        return f"${price:,.2f}"

    def _fmt_delta(asset: str, change: float, change_pct: float) -> str:
        if change is None or change_pct is None:
            return "—"
        if asset == 'USD Index':
            return f"{change:+.4f} ({change_pct:+.2f}%)"
        if asset == 'Bitcoin':
            return f"{change:+.0f} ({change_pct:+.2f}%)"
        return f"{change:+.2f} ({change_pct:+.2f}%)"
    
    for idx, (asset, data) in enumerate(market_data.items()):
        with cols[idx]:
            if data.get('price') is not None:
                change = data.get('change')
                change_pct = data.get('change_percent')
                
                # Color based on direction
                if change is None or change_pct is None:
                    delta_text = "—"
                    delta_color = "off"
                else:
                    delta_text = _fmt_delta(asset, float(change), float(change_pct))
                    delta_color = "normal" if change >= 0 else "inverse"
                
                # Add stale indicator
                label = asset
                if data.get('is_stale'):
                    label = f"⚠️ {asset}"
                
                st.metric(
                    label=label,
                    value=_fmt_price(asset, float(data['price'])),
                    delta=delta_text,
                    delta_color=delta_color
                )
            else:
                st.metric(label=asset, value="N/A", delta="--")
    
    st.markdown("---")
    
    # Market sentiment indicator
    st.subheader("📊 Market Sentiment Overview")
    
    assets = ['USD Index', 'Gold', 'Silver', 'Oil', 'Bitcoin']

    # Deterministic scoring (priority): latest forecast direction per asset.
    # Fallback: price delta direction from last two DB snapshots.
    signals = {}
    for asset in assets:
        signal = 0
        try:
            f = db.get_latest_forecast_for_asset(asset)
        except Exception:
            f = None

        direction = str((f or {}).get('direction') or '').upper()
        if direction == 'UP':
            signal = 1
        elif direction == 'DOWN':
            signal = -1
        elif direction == 'NEUTRAL':
            signal = 0
        else:
            # fallback to price deltas
            try:
                ch = market_data.get(asset, {}).get('change')
                if ch is not None:
                    ch = float(ch)
                    if ch > 0:
                        signal = 1
                    elif ch < 0:
                        signal = -1
            except Exception:
                signal = 0

        signals[asset] = signal

    up_assets = sum(1 for s in signals.values() if s == 1)
    down_assets = sum(1 for s in signals.values() if s == -1)

    # Normalize to 0..100 with midpoint 50.
    sentiment_score = 50.0 + 50.0 * (sum(signals.values()) / max(1, len(assets)))
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # Sentiment gauge
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=sentiment_score,
            title={'text': "Market Sentiment", 'font': {'color': '#FAFAFA'}},
            gauge={
                'axis': {'range': [0, 100], 'tickcolor': '#FAFAFA'},
                'bar': {'color': '#D4AF37'},
                'bgcolor': '#1E2130',
                'borderwidth': 2,
                'bordercolor': '#2E3340',
                'steps': [
                    {'range': [0, 33], 'color': '#FF4444'},
                    {'range': [33, 66], 'color': '#FFA500'},
                    {'range': [66, 100], 'color': '#00FF00'}
                ],
                'threshold': {
                    'line': {'color': "white", 'width': 4},
                    'thickness': 0.75,
                    'value': sentiment_score
                }
            }
        ))
        
        fig.update_layout(
            paper_bgcolor='#0E1117',
            plot_bgcolor='#0E1117',
            font={'color': '#FAFAFA'},
            height=300
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.metric("Assets Up", up_assets, f"{sentiment_score:.0f}%")
        st.metric("Assets Down", down_assets)
    
    with col3:
        # Market regime
        if sentiment_score > 66:
            regime = "🟢 Risk-On"
            regime_desc = "Bullish sentiment"
        elif sentiment_score < 33:
            regime = "🔴 Risk-Off"
            regime_desc = "Bearish sentiment"
        else:
            regime = "🟡 Mixed"
            regime_desc = "Neutral sentiment"
        
        st.markdown(f"### {regime}")
        st.write(regime_desc)
    
    st.markdown("---")
    
    # High-impact alerts
    st.subheader("⚠️ Recent High-Impact News")
    
    recent_news = db.get_recent_news(limit=5)
    
    if recent_news:
        for news_item in recent_news:
            impact_level = str(news_item.get('impact_level') or '').upper()
            if impact_level in ['HIGH', 'CRITICAL']:
                st.markdown(f"""
                <div class="alert-box">
                    <strong>{news_item.get('title_en')}</strong><br>
                    <small>Source: {news_item.get('source')} | Impact: {news_item.get('impact_level')}</small><br>
                    <small>Confidence: {news_item.get('confidence', 0):.0f}% | Category: {news_item.get('category', 'N/A')}</small>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("No recent high-impact news. Worker is collecting data...")
    
    st.markdown("---")
    
    # Quick stats
    st.subheader("📈 Platform Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Get stats from database
    all_forecasts = db.get_active_forecasts(limit=1000)
    accuracy_stats = db.get_forecast_accuracy()
    portfolio = db.get_portfolio()
    
    with col1:
        news_count = len(db.get_recent_news(limit=1000))
        st.metric("Total News Items", news_count)
    
    with col2:
        active_forecasts = len([f for f in all_forecasts if f.get('status') == 'active'])
        st.metric("Active Forecasts", active_forecasts)
    
    with col3:
        total_evaluated = sum(stat['total'] for stat in accuracy_stats.values())
        st.metric("Evaluated Forecasts", total_evaluated)
    
    with col4:
        if accuracy_stats:
            avg_accuracy = sum(stat['accuracy'] for stat in accuracy_stats.values()) / len(accuracy_stats)
            st.metric("Avg Accuracy", f"{avg_accuracy:.1f}%")
        else:
            st.metric("Avg Accuracy", "N/A")
    
    st.markdown("---")
    
    # System Status Diagnostics
    st.subheader("🔍 System Status")

    worker_status = db.get_worker_status() or {}
    forecast_counts = db.get_forecast_counts()
    trade_counts = db.get_trade_counts()
    latest_error = db.get_latest_error_log()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Worker Heartbeat:**")
        hb = worker_status.get('last_heartbeat_at') or worker_status.get('last_heartbeat')
        if hb:
            try:
                hb_dt = datetime.fromisoformat(hb)
                now_dt = datetime.now(hb_dt.tzinfo) if getattr(hb_dt, 'tzinfo', None) else datetime.now()
                age = (now_dt - hb_dt).total_seconds()
                if age < 30:
                    st.success(f"✅ Healthy ({age:.0f}s ago)")
                elif age < 120:
                    st.warning(f"⚠️ Delayed ({age:.0f}s ago)")
                else:
                    st.error(f"❌ Stalled ({age/60:.0f}m ago)")
            except Exception:
                st.info("⚪ Unknown")
        else:
            st.info("⚪ No heartbeat yet")

        st.markdown("**Counts:**")
        st.write(f"News: {db.get_news_count()}")
        st.write(
            f"Forecasts: {forecast_counts['total']} total / {forecast_counts['active']} active / {forecast_counts['evaluated']} evaluated"
        )
        st.write(
            f"Trades: {trade_counts['total']} total / {trade_counts['open']} open / {trade_counts['closed']} closed"
        )

        st.markdown("**Last Successful Cycle:**")
        last_ok = worker_status.get('last_successful_cycle_at')
        if last_ok:
            try:
                dt = datetime.fromisoformat(last_ok)
                st.write(dt.strftime('%Y-%m-%d %H:%M:%S'))
            except Exception:
                st.write(str(last_ok))
        else:
            st.write("—")

    with col2:
        st.markdown("**Latest Prices (timestamps):**")
        for asset in ['USD Index', 'Gold', 'Silver', 'Oil', 'Bitcoin']:
            ts = market_data.get(asset, {}).get('timestamp')
            if ts:
                try:
                    dt = datetime.fromisoformat(ts)
                    st.write(f"{asset}: {dt.strftime('%H:%M:%S')}")
                except Exception:
                    st.write(f"{asset}: {ts}")
            else:
                st.write(f"{asset}: Unavailable")

    with col3:
        st.markdown("**Latest Error:**")
        if latest_error:
            st.error(
                f"[{latest_error.get('timestamp')}] {latest_error.get('module')}: {latest_error.get('message')}"
            )
        else:
            if not worker_status.get('last_error'):
                st.success("System Healthy")
            else:
                st.warning("Worker reported an error state, but no recent log entry was found.")

        # If we appear stalled, offer an actionable hint
        hb = worker_status.get('last_heartbeat')
        if hb:
            try:
                hb_dt = datetime.fromisoformat(hb)
                now_dt = datetime.now(hb_dt.tzinfo) if getattr(hb_dt, 'tzinfo', None) else datetime.now()
                age = (now_dt - hb_dt).total_seconds()
                if age >= 300 and (latest_error or worker_status.get('last_error')):
                    st.caption(
                        "Suggestion: restart the worker and review the latest error. "
                        "If it repeats, open System Logs for details."
                    )
            except Exception:
                pass

        last_err_state = worker_status.get('last_error')
        if last_err_state:
            with st.expander("Worker last_error (full)"):
                st.code(str(last_err_state))

except Exception as e:
    st.error("Dashboard failed to load. The system may still be initializing.")
    st.info("Try again in a few seconds.")
    with st.expander("Details"):
        st.write(str(e))

# Disclaimer
st.markdown("---")
st.markdown("""
<div style='background-color: #2E1A1A; border: 1px solid #D4AF37; border-radius: 5px; padding: 15px; margin: 20px 0;'>
<strong>⚠️ Disclaimer</strong><br>
This platform is intended for <strong>educational and analytical purposes only</strong>. 
It does not constitute financial advice, investment recommendations, or solicitation to buy or sell any asset.
</div>
""", unsafe_allow_html=True)
