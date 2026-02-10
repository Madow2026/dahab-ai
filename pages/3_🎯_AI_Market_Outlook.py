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
from streamlit_worker import ensure_worker_running

st.set_page_config(page_title="AI Market Outlook", page_icon="🎯", layout="wide")

# Ensure background worker is running
ensure_worker_running()

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
    ["All", "Active", "Evaluated"]
)

risk_filter = st.sidebar.selectbox(
    "Risk Level",
    ["All", "LOW", "MEDIUM", "HIGH"]
)

direction_filter = st.sidebar.selectbox(
    "Direction",
    ["All", "UP", "DOWN", "NEUTRAL"]
)

time_range_filter = st.sidebar.selectbox(
    "Time Range",
    ["All Time", "Last 24 Hours", "Last 7 Days", "Last 30 Days", "Last 90 Days"]
)

# Map time range filter to days
_DAYS_MAP = {
    "All Time": None,
    "Last 24 Hours": 1,
    "Last 7 Days": 7,
    "Last 30 Days": 30,
    "Last 90 Days": 90,
}
days_filter = _DAYS_MAP.get(time_range_filter)

# ========================================================================
# OVERALL SUMMARY (all-time stats)
# ========================================================================
st.subheader("📊 Recommendations Summary")

try:
    summary_stats = db.get_forecasts_summary_stats()
except Exception:
    summary_stats = {}

col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
with col_s1:
    st.metric("Total Recommendations", summary_stats.get('total', 0))
with col_s2:
    st.metric("Active", summary_stats.get('active', 0))
with col_s3:
    st.metric("Evaluated", summary_stats.get('evaluated', 0))
with col_s4:
    hits = summary_stats.get('hits', 0) or 0
    misses = summary_stats.get('misses', 0) or 0
    total_eval = hits + misses
    acc = (hits / total_eval * 100) if total_eval > 0 else 0
    st.metric("Overall Accuracy", f"{acc:.1f}%", f"{hits}/{total_eval}")
with col_s5:
    avg_conf = summary_stats.get('avg_confidence', 0) or 0
    st.metric("Avg Confidence", f"{avg_conf:.1f}%")

# Worker status indicator
worker_alive = db.is_worker_alive(max_stale_seconds=120)
if worker_alive:
    st.success("🟢 Worker is running — recommendations are being generated continuously (even when this page is closed)")
else:
    st.warning("🟡 Worker starting up... Recommendations will resume shortly")

st.markdown("---")

# ========================================================================
# VISUAL OUTLOOK CHARTS
# ========================================================================
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

# ========================================================================
# ALL RECOMMENDATIONS HISTORY
# ========================================================================
st.subheader("📋 All Recommendations (Past & Current)")
st.caption("All recommendations are stored permanently. They continue to be generated and evaluated even when the website is closed.")

# Fetch all forecasts using unified query with filters
_status_arg = None
if status_filter == "Active":
    _status_arg = "active"
elif status_filter == "Evaluated":
    _status_arg = "evaluated"

forecasts = db.get_all_forecasts_history(
    limit=1000,
    asset=asset_filter if asset_filter != "All" else None,
    status=_status_arg,
    direction=direction_filter if direction_filter != "All" else None,
    risk_level=risk_filter if risk_filter != "All" else None,
    days=days_filter,
)

# Display count
st.caption(f"Showing {len(forecasts)} recommendations | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if not forecasts:
    st.info("📭 No recommendations found matching filters. Worker is continuously generating forecasts...")
else:
    # Stats row
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        up_count = len([f for f in forecasts if f.get('direction') == 'UP'])
        st.metric("▲ Bullish", up_count)
    
    with col2:
        down_count = len([f for f in forecasts if f.get('direction') == 'DOWN'])
        st.metric("▼ Bearish", down_count)
    
    with col3:
        avg_confidence = sum(f.get('confidence', 0) for f in forecasts) / len(forecasts)
        st.metric("Avg Confidence", f"{avg_confidence:.1f}%")

    with col4:
        evaluated_in_view = [f for f in forecasts if f.get('status') == 'evaluated']
        hits_in_view = len([f for f in evaluated_in_view if f.get('evaluation_result') == 'hit'])
        total_eval_in_view = len(evaluated_in_view)
        accuracy_in_view = (hits_in_view / total_eval_in_view * 100) if total_eval_in_view > 0 else 0
        st.metric("Accuracy (filtered)", f"{accuracy_in_view:.1f}%", f"{hits_in_view}/{total_eval_in_view}")

    with col5:
        active_in_view = len([f for f in forecasts if f.get('status') == 'active'])
        st.metric("⏳ Pending", active_in_view)
    
    st.markdown("---")

    # Pagination
    ITEMS_PER_PAGE = 50
    total_pages = max(1, (len(forecasts) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    
    if total_pages > 1:
        page_num = st.number_input("Page", min_value=1, max_value=total_pages, value=1, step=1)
    else:
        page_num = 1
    
    start_idx = (page_num - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(forecasts))
    page_forecasts = forecasts[start_idx:end_idx]
    
    if total_pages > 1:
        st.caption(f"Page {page_num}/{total_pages} — showing {start_idx+1}-{end_idx} of {len(forecasts)}")
    
    # Display forecasts
    for forecast in page_forecasts:
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
        eval_result = str(forecast.get("evaluation_result") or "").lower()

        # Enhanced status display with evaluation result
        if status == "evaluated":
            if eval_result == "hit":
                status_html = '<span style="color:#78D2B9;font-weight:700">✅ HIT</span>'
            elif eval_result == "miss":
                status_html = '<span style="color:#E6A0A0;font-weight:700">❌ MISS</span>'
            else:
                status_html = '<span style="color:#96A0AF">Evaluated</span>'
        elif status == "active":
            # Check if overdue
            if due_dt and due_dt < datetime.now():
                status_html = '<span style="color:#E6C860">⏰ Overdue</span>'
            else:
                status_html = '<span style="color:#60B0E6">⏳ Active</span>'
        else:
            status_html = f'<span style="color:#96A0AF">{status.title() or "Unknown"}</span>'

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
          {status_html}
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
                    if eval_result == "hit":
                        st.success("✅ HIT — Direction correct")
                    elif eval_result == "miss":
                        st.error("❌ MISS — Direction incorrect")
                    else:
                        st.info("Evaluated")
                    if forecast.get("actual_direction"):
                        st.caption(f"Predicted: {direction} → Actual: {forecast.get('actual_direction')}")
                    if forecast.get("actual_return") is not None:
                        st.metric("Actual Return", f"{_safe_float(forecast.get('actual_return')):+.2f}%")
                    actual_price = forecast.get("actual_price") or forecast.get("price_at_evaluation")
                    if actual_price is not None and str(actual_price) != "":
                        st.metric("Actual Price", f"{_safe_float(actual_price):.4f}")
                elif status == "active":
                    if due_dt:
                        remaining = due_dt - datetime.now()
                        if remaining.total_seconds() > 0:
                            hours = int(remaining.total_seconds() // 3600)
                            mins = int((remaining.total_seconds() % 3600) // 60)
                            st.info(f"⏳ Due in {hours}h {mins}m")
                        else:
                            st.warning("⏰ Overdue — awaiting evaluation")
    
    if total_pages > 1:
        st.caption(f"Page {page_num} of {total_pages} — {len(forecasts)} total recommendations")

# Disclaimer
st.markdown("---")
st.markdown("""
<div style='background-color: #2E1A1A; border: 1px solid #D4AF37; border-radius: 5px; padding: 15px;'>
<strong>⚠️ Disclaimer</strong><br>
Forecasts are probabilistic and automated. Maximum confidence is capped at 85% by design.
This platform does not constitute financial advice or trading recommendations.
</div>
""", unsafe_allow_html=True)
