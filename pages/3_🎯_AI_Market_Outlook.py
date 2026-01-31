"""
AI Market Outlook
Probabilistic forecasts and scenario analysis
AUTO-REFRESHING - Worker generates forecasts automatically
"""

import streamlit as st
from datetime import datetime, timedelta
import math
import sys
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.db import get_db

st.set_page_config(page_title="AI Market Outlook", page_icon="🎯", layout="wide")

# Auto-refresh every 30 seconds
if 'last_refresh_forecasts' not in st.session_state:
    st.session_state.last_refresh_forecasts = time.time()

current_time = time.time()
if current_time - st.session_state.last_refresh_forecasts > 30:
    st.session_state.last_refresh_forecasts = current_time
    st.rerun()

st.title("🎯 AI Market Outlook")
st.caption("🔄 Auto-refreshing every 30 seconds | Worker automatically generates probabilistic forecasts")

# Get database
db = get_db()


ASSETS: List[str] = ["Gold", "Silver", "Oil", "USD Index", "Bitcoin"]


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).strip())
    except Exception:
        return None


def _fmt_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return "Unknown"
    return dt.strftime("%Y-%m-%d %H:%M")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _direction_meta(direction: str) -> Tuple[str, str, str]:
    d = str(direction or "").upper()
    if d == "UP":
        return ("▲", "UP", "rgba(120, 210, 185, 0.95)")
    if d == "DOWN":
        return ("▼", "DOWN", "rgba(230, 160, 160, 0.95)")
    return ("•", "NEUTRAL", "rgba(150, 160, 175, 0.95)")


def _get_price_history(asset: str, hours: int = 72, limit: int = 800) -> pd.DataFrame:
    """DB-only price history for charting. Returns a DF with ['ts','price'] sorted ascending."""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        cursor.execute(
            """
            SELECT timestamp, price
            FROM prices
            WHERE asset = ? AND timestamp IS NOT NULL AND price IS NOT NULL
              AND datetime(timestamp) >= datetime(?)
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (asset, since, int(limit)),
        )
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            return pd.DataFrame(columns=["ts", "price"])
        df = pd.DataFrame(rows, columns=["ts", "price"])
        df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df = df.dropna(subset=["ts", "price"]).sort_values("ts")
        return df
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return pd.DataFrame(columns=["ts", "price"])


def _get_latest_forecast_for_asset(asset: str) -> Optional[Dict]:
    """DB-only. Prefer latest active forecast; fallback to latest evaluated."""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM forecasts
            WHERE asset = ?
            ORDER BY
              CASE WHEN status = 'active' THEN 0 ELSE 1 END,
              datetime(COALESCE(created_at, forecast_time, due_at)) DESC
            LIMIT 1
            """,
            (asset,),
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return None


def _project_forecast_endpoint(forecast: Dict) -> Tuple[Optional[datetime], Optional[float], str]:
    """Return (due_dt, projected_price, method).

    Uses DB fields if present; otherwise uses a conservative confidence-scaled heuristic by horizon.
    """
    created_dt = _parse_dt(forecast.get("created_at") or forecast.get("forecast_time"))
    due_dt = _parse_dt(forecast.get("due_at"))
    price0 = _safe_float(forecast.get("price_at_forecast"), default=math.nan)
    if not created_dt:
        created_dt = due_dt

    direction = str(forecast.get("direction") or "").upper()
    conf = _safe_float(forecast.get("confidence"), 0.0) / 100.0

    # If a target magnitude exists in DB, prefer it.
    pct = forecast.get("price_change_percent")
    if pct is not None and str(pct) != "":
        pct_f = _safe_float(pct, default=0.0) / 100.0
        if direction == "DOWN":
            pct_f = -abs(pct_f)
        elif direction == "UP":
            pct_f = abs(pct_f)
        else:
            pct_f = 0.0
        if not math.isnan(price0) and due_dt:
            return (due_dt, price0 * (1.0 + pct_f), "db_price_change_percent")

    horizon = int(_safe_float(forecast.get("horizon_minutes"), 0))
    base_by_horizon = {
        15: 0.0010,   # 0.10%
        60: 0.0025,   # 0.25%
        240: 0.0060,  # 0.60%
        1440: 0.0150  # 1.50%
    }
    base = base_by_horizon.get(horizon, 0.0040)
    pct_f = base * max(0.10, min(1.0, conf))
    if direction == "DOWN":
        pct_f = -abs(pct_f)
    elif direction == "UP":
        pct_f = abs(pct_f)
    else:
        pct_f = 0.0

    if not math.isnan(price0) and due_dt:
        return (due_dt, price0 * (1.0 + pct_f), "heuristic")
    return (due_dt, None, "insufficient")


def _make_price_outlook_chart(asset: str) -> Optional[go.Figure]:
    history = _get_price_history(asset, hours=120, limit=1000)
    if history.shape[0] < 2:
        return None

    forecast = _get_latest_forecast_for_asset(asset)
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=history["ts"],
            y=history["price"],
            mode="lines",
            name="Actual",
            line=dict(color="rgba(180, 190, 205, 0.95)", width=2),
            hovertemplate="%{x|%Y-%m-%d %H:%M}<br>Price: %{y:.4f}<extra>Actual</extra>",
        )
    )

    if forecast:
        created_dt = _parse_dt(forecast.get("created_at") or forecast.get("forecast_time"))
        if not created_dt:
            # Ensure timestamp is always visible somewhere, but skip plotting if missing
            created_dt = history["ts"].iloc[-1].to_pydatetime()

        price0 = forecast.get("price_at_forecast")
        if price0 is None or str(price0) == "":
            # fallback to last historical price
            price0 = float(history["price"].iloc[-1])
        else:
            price0 = _safe_float(price0, float(history["price"].iloc[-1]))

        due_dt, price1, method = _project_forecast_endpoint(forecast)
        if due_dt and price1 is not None:
            fig.add_trace(
                go.Scatter(
                    x=[created_dt, due_dt],
                    y=[price0, price1],
                    mode="lines+markers",
                    name="Forecast",
                    line=dict(color="rgba(212, 175, 55, 0.95)", width=2, dash="dash"),
                    marker=dict(size=7, color="rgba(212, 175, 55, 0.95)"),
                    hovertemplate=(
                        "%{x|%Y-%m-%d %H:%M}<br>Price: %{y:.4f}"
                        f"<extra>Forecast ({method})</extra>"
                    ),
                )
            )

    fig.update_layout(
        height=320,
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="#0E1117",
        plot_bgcolor="#0E1117",
        font=dict(color="#E6E6E6"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        hovermode="x unified",
    )
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.06)",
        zeroline=False,
    )
    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(255,255,255,0.06)",
        zeroline=False,
    )
    return fig


st.markdown(
    """
<style>
  .forecast-row {
    border: 1px solid rgba(255,255,255,0.07);
    background: rgba(255,255,255,0.02);
    border-radius: 10px;
    padding: 12px 14px;
    margin: 10px 0;
  }
  .forecast-row:hover {
    border-color: rgba(212,175,55,0.35);
  }
  .forecast-row-top {
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap: 12px;
  }
  .forecast-left {
    display:flex;
    flex-wrap:wrap;
    gap: 10px;
    align-items:center;
  }
  .asset-pill {
    font-weight: 700;
    letter-spacing: 0.2px;
  }
  .dir-pill {
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    border: 1px solid rgba(255,255,255,0.10);
    background: rgba(255,255,255,0.03);
  }
  .meta-pill {
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 12px;
    border: 1px solid rgba(255,255,255,0.08);
    color: rgba(220,225,235,0.92);
    background: rgba(255,255,255,0.02);
  }
  .forecast-right {
    font-size: 12px;
    color: rgba(210,215,225,0.75);
    text-align:right;
    white-space:nowrap;
  }
  .subtle {
    color: rgba(210,215,225,0.72);
  }
</style>
    """,
    unsafe_allow_html=True,
)

# Sidebar filters
st.sidebar.subheader("🔍 Filters")

asset_filter = st.sidebar.selectbox(
    "Asset",
    ["All", "USD Index", "Gold", "Silver", "Oil", "Bitcoin"]
)

status_filter = st.sidebar.selectbox(
    "Status",
    ["Active", "Evaluated"]
)

risk_filter = st.sidebar.selectbox(
    "Risk Level",
    ["All", "LOW", "MEDIUM", "HIGH"]
)

direction_filter = st.sidebar.selectbox(
    "Direction",
    ["All", "UP", "DOWN", "NEUTRAL"]
)

# Main content
st.subheader("📊 Forecasts Dashboard")

st.subheader("AI Price Forecasts – Visual Outlook")
st.caption("Historical prices and the latest forecast per asset (DB-only).")

grid_cols = st.columns(2)
for i, asset in enumerate(ASSETS):
    with grid_cols[i % 2]:
        st.markdown(f"### {asset}")
        fig = _make_price_outlook_chart(asset)
        if fig is None:
            st.info("Not enough data yet – collecting prices")
        else:
            st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# Get forecasts based on status
if status_filter == "Active":
    forecasts = db.get_active_forecasts(limit=100)
else:
    # Get evaluated forecasts
    forecasts = []
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM forecasts
        WHERE status = 'evaluated'
        ORDER BY COALESCE(evaluated_at, evaluation_time) DESC
        LIMIT 100
    """)
    forecasts = [dict(row) for row in cursor.fetchall()]
    conn.close()

# Apply filters
if asset_filter != "All":
    forecasts = [f for f in forecasts if f.get('asset') == asset_filter]

if risk_filter != "All":
    forecasts = [f for f in forecasts if f.get('risk_level') == risk_filter]

if direction_filter != "All":
    forecasts = [f for f in forecasts if f.get('direction') == direction_filter]

# Display count
st.caption(f"Showing {len(forecasts)} forecasts | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if not forecasts:
    st.info("📭 No forecasts found matching filters. Worker is continuously generating forecasts...")
else:
    # Stats row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        up_count = len([f for f in forecasts if f.get('direction') == 'UP'])
        st.metric("Bullish Forecasts", up_count)
    
    with col2:
        down_count = len([f for f in forecasts if f.get('direction') == 'DOWN'])
        st.metric("Bearish Forecasts", down_count)
    
    with col3:
        avg_confidence = sum(f.get('confidence', 0) for f in forecasts) / len(forecasts)
        st.metric("Avg Confidence", f"{avg_confidence:.1f}%")
    
    with col4:
        if status_filter == "Evaluated":
            hits = len([f for f in forecasts if f.get('evaluation_result') == 'hit'])
            accuracy = (hits / len(forecasts) * 100) if forecasts else 0
            st.metric("Accuracy", f"{accuracy:.1f}%")
        else:
            st.metric("Status", "Active")
    
    st.markdown("---")
    
    # Display forecasts
    for forecast in forecasts[:50]:  # Show top 50
        asset = str(forecast.get("asset") or "N/A")
        direction = str(forecast.get("direction") or "NEUTRAL").upper()
        icon, dir_label, dir_color = _direction_meta(direction)
        confidence = _safe_float(forecast.get("confidence"), 0.0)
        risk = str(forecast.get("risk_level") or "N/A").upper()
        horizon = int(_safe_float(forecast.get("horizon_minutes"), 0))

        created_dt = _parse_dt(forecast.get("created_at") or forecast.get("forecast_time"))
        due_dt = _parse_dt(forecast.get("due_at"))
        created_text = _fmt_dt(created_dt)
        due_text = _fmt_dt(due_dt) if due_dt else "—"

        status = str(forecast.get("status") or "").lower()
        status_text = "Active" if status == "active" else "Evaluated" if status == "evaluated" else (status.title() or "Unknown")

        st.markdown(
            f"""
    <div class="forecast-row">
      <div class="forecast-row-top">
        <div class="forecast-left">
          <span class="asset-pill">{asset}</span>
          <span class="dir-pill" style="color:{dir_color}">{icon} {dir_label}</span>
          <span class="meta-pill">{confidence:.0f}%</span>
          <span class="meta-pill">{risk}</span>
          <span class="meta-pill">{horizon}m</span>
          <span class="meta-pill">{status_text}</span>
        </div>
        <div class="forecast-right">
          <div><span class="subtle">Created</span> {created_text}</div>
          <div><span class="subtle">Due</span> {due_text}</div>
        </div>
      </div>
    </div>
            """.strip(),
            unsafe_allow_html=True,
        )

        with st.expander("Details", expanded=False):
            col1, col2 = st.columns([2, 1])
            with col1:
                reasoning = forecast.get("reasoning")
                if reasoning:
                    st.markdown("**Reasoning**")
                    st.write(str(reasoning))
                if forecast.get("scenario_base") or forecast.get("scenario_alt"):
                    st.markdown("**Scenarios**")
                    c1, c2 = st.columns(2)
                    with c1:
                        if forecast.get("scenario_base"):
                            st.markdown("Base")
                            st.write(str(forecast.get("scenario_base")))
                    with c2:
                        if forecast.get("scenario_alt"):
                            st.markdown("Alternative")
                            st.write(str(forecast.get("scenario_alt")))
            with col2:
                price0 = forecast.get("price_at_forecast")
                if price0 is not None and str(price0) != "":
                    st.metric("Price at Forecast", f"{_safe_float(price0):.4f}")
                if status == "evaluated":
                    result = str(forecast.get("evaluation_result") or "").lower()
                    if result == "hit":
                        st.success("HIT")
                    elif result == "miss":
                        st.error("MISS")
                    else:
                        st.info("Evaluated")
                    if forecast.get("actual_direction"):
                        st.caption(f"Actual: {forecast.get('actual_direction')}")
                    if forecast.get("actual_return") is not None:
                        st.metric("Actual Return", f"{_safe_float(forecast.get('actual_return')):+.2f}%")
    
    if len(forecasts) > 50:
        st.info(f"Showing top 50 of {len(forecasts)} forecasts.")

# Disclaimer
st.markdown("---")
st.markdown("""
<div style='background-color: #2E1A1A; border: 1px solid #D4AF37; border-radius: 5px; padding: 15px;'>
<strong>⚠️ Disclaimer</strong><br>
Forecasts are probabilistic and automated. Maximum confidence is capped at 85% by design.
This platform does not constitute financial advice or trading recommendations.
</div>
""", unsafe_allow_html=True)
