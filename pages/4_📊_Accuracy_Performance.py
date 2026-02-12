"""Accuracy & Performance Page.

Read-only dashboard backed by the automated DB schema (db/db.py).
Crash-proof: handles missing columns and empty datasets.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pandas as pd
import sys
import os

import config

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.db import get_db
from ui.sidebar import render_sidebar
from streamlit_worker import ensure_worker_running

from evaluation_engine import compute_and_store_evaluation_summary, fetch_evaluated_forecasts
from charts import performance_triplet

st.set_page_config(page_title="Accuracy & Performance", page_icon="📊", layout="wide")

# Ensure background worker is running
ensure_worker_running()

st.title("📊 Accuracy & Performance Tracking")
st.caption("Forecast vs Reality - Continuous self-evaluation")

db = get_db()

PAGE_KEY = 'accuracy'

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

last_updated = None
try:
    last_updated = db.get_page_last_updated(PAGE_KEY)
except Exception:
    last_updated = None
new_since = int(st.session_state.get(f"_page_new_since_{PAGE_KEY}", 0) or 0)

st.caption(f"Last updated: {last_updated or '—'} | New since last visit: {new_since}")

st.markdown("---")
st.subheader("🧮 Evaluation Summary (Production Metrics)")

window_days = st.selectbox("Window (days)", [14, 30, 60, 90], index=2)
if st.button("Compute & store evaluation summary", type="secondary"):
    with st.spinner("Computing metrics..."):
        try:
            _ = compute_and_store_evaluation_summary(db, window_days=int(window_days))
            st.success("Evaluation summary stored.")
        except Exception as e:
            st.error("Failed to compute/store summary.")
            try:
                db.log('ERROR', 'UI', f"Eval summary failed: {e}")
            except Exception:
                pass

try:
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT computed_at, window_days, asset, horizon_key, horizon_minutes,
               n_total, n_hit, directional_accuracy, mae, mape, avg_confidence,
               calibration_score, weighted_overall_accuracy
        FROM evaluation_summary
        ORDER BY datetime(replace(substr(computed_at,1,19),'T',' ')) DESC, id DESC
        LIMIT 200
        """
    )
    sum_rows = cur.fetchall() or []
    conn.close()
except Exception:
    try:
        conn.close()
    except Exception:
        pass
    sum_rows = []

if sum_rows:
    sdf = pd.DataFrame(
        sum_rows,
        columns=[
            'computed_at', 'window_days', 'asset', 'horizon_key', 'horizon_minutes',
            'n_total', 'n_hit', 'directional_accuracy', 'mae', 'mape', 'avg_confidence',
            'calibration_score', 'weighted_overall_accuracy'
        ],
    )
    st.dataframe(sdf, use_container_width=True, hide_index=True)
else:
    st.info("No evaluation summary rows yet. Click 'Compute & store evaluation summary'.")

col_eval_btn, _ = st.columns([1, 3])
with col_eval_btn:
    if st.button("Run evaluation now", type="primary"):
        with st.spinner("Evaluating due forecasts..."):
            try:
                result = db.evaluate_due_forecasts_backfill(max_window_hours=6)
                st.success(f"Evaluation complete: {result}")
            except Exception as e:
                st.error("Evaluation failed (see logs).")
                try:
                    db.log('ERROR', 'UI', f"Manual evaluation failed: {e}")
                except Exception:
                    pass
        st.rerun()


def _safe_pending_forecast_counts():
    """Return pending (active) forecast counts by horizon_minutes.

    Crash-proof: returns empty dict on any error.
    """
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT horizon_minutes, COUNT(*) as c
            FROM forecasts
            WHERE status = 'active'
            GROUP BY horizon_minutes
            """
        )
        rows = cursor.fetchall()
        conn.close()

        counts = {}
        for row in rows:
            try:
                horizon = int(row[0]) if row[0] is not None else 0
            except Exception:
                horizon = 0
            try:
                count = int(row[1])
            except Exception:
                count = 0
            counts[horizon] = counts.get(horizon, 0) + count
        return counts
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return {}


def _safe_overdue_pending_count():
    """Count active forecasts whose due_at is in the past but not evaluated yet."""
    try:
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM forecasts
            WHERE status = 'active'
              AND due_at IS NOT NULL
                            AND datetime(replace(substr(due_at,1,19),'T',' ')) <= datetime('now')
            """
        )
        n = int(cursor.fetchone()[0])
        conn.close()
        return n
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return 0


def _bucket_horizon_minutes(horizon_minutes: int) -> str:
    # Standard UI buckets requested
    if horizon_minutes == 15:
        return '15m'
    if horizon_minutes == 60:
        return '60m'
    if horizon_minutes == 360:
        return '6h'
    if horizon_minutes == 720:
        return '12h'
    if horizon_minutes == 2880:
        return '48h'
    if horizon_minutes == 4320:
        return '72h'
    return 'Other'


# Pending forecasts section (always shown)
st.subheader("⏳ Forecasts Pending Evaluation")
pending_counts_raw = _safe_pending_forecast_counts()
pending_total = sum(pending_counts_raw.values())
pending_overdue = _safe_overdue_pending_count() if pending_total else 0

bucketed = {'15m': 0, '60m': 0, '6h': 0, '12h': 0, '48h': 0, '72h': 0, 'Other': 0}
for horizon, count in pending_counts_raw.items():
    label = _bucket_horizon_minutes(horizon)
    bucketed[label] = bucketed.get(label, 0) + int(count or 0)

col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
with col1:
    st.metric("Pending (Total)", pending_total)
with col2:
    st.metric("15m", bucketed.get('15m', 0))
with col3:
    st.metric("60m", bucketed.get('60m', 0))
with col4:
    st.metric("6h", bucketed.get('6h', 0))
with col5:
    st.metric("12h", bucketed.get('12h', 0))
with col6:
    st.metric("48h", bucketed.get('48h', 0))
with col7:
    st.metric("72h", bucketed.get('72h', 0))

if pending_total == 0:
    st.info("No pending forecasts right now.")
else:
    if bucketed.get('Other', 0):
        st.caption(f"Other horizons pending: {bucketed.get('Other', 0)}")
    if pending_overdue:
        st.warning(
            f"Overdue (should be evaluated): {pending_overdue}. "
            "If this persists, the evaluator may be delayed; check Worker logs/System Status."
        )

st.markdown("---")

# Growth / decline performance (daily aggregation)
st.subheader("📉 Growth / Decline Performance")
st.caption("Aggregates evaluated forecasts into daily predicted vs actual performance, with cumulative and drawdown charts.")

asset_filter = st.selectbox("Asset", ["All", "Gold", "Silver", "Oil", "Bitcoin", "USD Index"], index=0)
_hlist = list((getattr(config, 'RECOMMENDATION_HORIZONS', None) or {}).keys())
if not _hlist:
    _hlist = ["15m", "60m", "6h", "12h", "48h", "72h"]
horizon_filter = st.selectbox("Horizon", ["All"] + _hlist, index=0)

eval_rows = fetch_evaluated_forecasts(db, window_days=int(window_days), asset=None if asset_filter == 'All' else asset_filter)
if not eval_rows:
    st.info("No evaluated forecasts available for the selected window.")
else:
    edf = pd.DataFrame(eval_rows)
    edf['evaluated_at'] = pd.to_datetime(edf.get('evaluated_at', edf.get('evaluation_time')), errors='coerce', utc=True)
    edf = edf.dropna(subset=['evaluated_at']).copy()

    # Filters
    if asset_filter != 'All' and 'asset' in edf.columns:
        edf = edf[edf['asset'] == asset_filter]

    if horizon_filter != 'All' and 'horizon_minutes' in edf.columns:
        hm_map = {'15m': 15, '60m': 60, '6h': 360, '12h': 720, '48h': 2880, '72h': 4320}
        hm = hm_map.get(horizon_filter)
        if hm is not None:
            edf = edf[pd.to_numeric(edf['horizon_minutes'], errors='coerce').fillna(-1).astype(int) == int(hm)]

    if edf.empty:
        st.info("No evaluated forecasts match the selected filters.")
    else:
        # Compute predicted/actual returns vs entry (price_at_forecast)
        entry = pd.to_numeric(edf.get('price_at_forecast'), errors='coerce')
        pred = pd.to_numeric(edf.get('predicted_price'), errors='coerce')
        actual = pd.to_numeric(edf.get('actual_price', edf.get('price_at_evaluation')), errors='coerce')

        edf['predicted_return_pct'] = ((pred - entry) / entry) * 100.0
        edf['actual_return_pct'] = ((actual - entry) / entry) * 100.0
        edf['date'] = edf['evaluated_at'].dt.date

        daily = edf.groupby('date', as_index=False).agg(
            predicted_return_pct=('predicted_return_pct', 'mean'),
            actual_return_pct=('actual_return_pct', 'mean'),
            n=('id', 'count') if 'id' in edf.columns else ('date', 'count'),
        )

        figs = performance_triplet(daily, date_col='date')
        st.plotly_chart(figs['cumulative'], use_container_width=True)
        st.plotly_chart(figs['daily'], use_container_width=True)
        st.plotly_chart(figs['drawdown'], use_container_width=True)

# Get all evaluated forecasts (dynamic column detection in DB layer)
evaluated_forecasts = db.get_all_evaluated_forecasts(limit=1000)

if not evaluated_forecasts:
    st.subheader("✅ Evaluated Forecasts")
    st.warning("📭 No evaluated forecasts yet. Generate forecasts and wait for evaluation periods to complete.")
    st.info(
        """
**How it works:**
1. System generates forecasts from economic news
2. Forecasts include time horizons (15min, 1hr, 4hr, 1day)
3. After time horizon passes, system evaluates actual vs expected
4. Results are tracked here for transparency and improvement
        """.strip()
    )
else:
    # Convert to DataFrame
    df = pd.DataFrame(evaluated_forecasts)

    # Determine time columns dynamically
    forecast_time_col = 'created_at' if 'created_at' in df.columns else ('forecast_time' if 'forecast_time' in df.columns else None)
    evaluation_time_col = 'evaluation_time' if 'evaluation_time' in df.columns else ('evaluated_at' if 'evaluated_at' in df.columns else None)

    if forecast_time_col is None or evaluation_time_col is None:
        st.warning("Forecast evaluation columns are not available yet. Worker will populate them once forecasts mature.")
        st.stop()

    df['forecast_time'] = pd.to_datetime(df[forecast_time_col], errors='coerce')
    df['evaluation_time'] = pd.to_datetime(df[evaluation_time_col], errors='coerce')

    # Normalize result
    if 'direction_correct' in df.columns:
        df['is_hit'] = pd.to_numeric(df['direction_correct'], errors='coerce').fillna(0).astype(int).eq(1)
    elif 'evaluation_result' in df.columns:
        df['is_hit'] = df['evaluation_result'].astype(str).str.lower().eq('hit')
    else:
        df['is_hit'] = False

    if 'confidence' in df.columns:
        df['confidence_pct'] = pd.to_numeric(df['confidence'], errors='coerce')
    else:
        df['confidence_pct'] = 0.0

    # Error metrics (direction-only forecasts): realized move vs entry snapshot
    if 'abs_error' in df.columns:
        df['abs_error_val'] = pd.to_numeric(df['abs_error'], errors='coerce')
    else:
        # Fallback: compute from price_at_forecast and evaluation price if present
        p0 = pd.to_numeric(df.get('price_at_forecast'), errors='coerce')
        p1 = pd.to_numeric(df.get('actual_price', df.get('price_at_evaluation')), errors='coerce')
        df['abs_error_val'] = (p1 - p0).abs()

    if 'pct_error' in df.columns:
        df['pct_error_val'] = pd.to_numeric(df['pct_error'], errors='coerce')
    else:
        p0 = pd.to_numeric(df.get('price_at_forecast'), errors='coerce')
        df['pct_error_val'] = (df['abs_error_val'] / p0) * 100.0
    
    # Overall statistics
    st.subheader("📈 Overall Performance")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_forecasts = len(df)
    accurate_forecasts = int(df['is_hit'].sum())
    accuracy_rate = (accurate_forecasts / total_forecasts * 100) if total_forecasts > 0 else 0
    avg_confidence = float(df['confidence_pct'].mean()) if total_forecasts > 0 else 0
    avg_abs_error = float(df['abs_error_val'].dropna().mean()) if total_forecasts > 0 else 0.0
    avg_pct_error = float(df['pct_error_val'].dropna().mean()) if total_forecasts > 0 else 0.0
    
    with col1:
        st.metric("Total Evaluated", total_forecasts)
    
    with col2:
        st.metric("Accurate Forecasts", accurate_forecasts, f"{accuracy_rate:.1f}%")
    
    with col3:
        st.metric("Inaccurate Forecasts", total_forecasts - accurate_forecasts)
    
    with col4:
        st.metric("Avg Confidence", f"{avg_confidence:.1f}%")

    col5, col6 = st.columns(2)
    with col5:
        st.metric("Avg Abs Error", f"{avg_abs_error:.4f}")
    with col6:
        st.metric("Avg % Error", f"{avg_pct_error:.2f}%")
    
    st.markdown("---")
    
    # Accuracy by Asset
    st.subheader("🎯 Accuracy by Asset")
    
    asset_stats = df.groupby('asset').agg({
        'is_hit': ['sum', 'count'],
        'confidence_pct': 'mean'
    }).reset_index()
    
    asset_stats.columns = ['asset', 'accurate', 'total', 'avg_confidence']
    asset_stats['accuracy_rate'] = (asset_stats['accurate'] / asset_stats['total'] * 100)
    
    # Bar chart
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=asset_stats['asset'],
        y=asset_stats['accuracy_rate'],
        text=asset_stats['accuracy_rate'].round(1).astype(str) + '%',
        textposition='auto',
        marker_color='#D4AF37',
        name='Accuracy Rate'
    ))
    
    fig.update_layout(
        title="Forecast Accuracy by Asset",
        xaxis_title="Asset",
        yaxis_title="Accuracy Rate (%)",
        yaxis=dict(range=[0, 100]),
        paper_bgcolor='#0E1117',
        plot_bgcolor='#1E2130',
        font={'color': '#FAFAFA'},
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Display table
    st.dataframe(
        asset_stats[['asset', 'total', 'accurate', 'accuracy_rate', 'avg_confidence']].style.format({
            'accuracy_rate': '{:.1f}%',
            'avg_confidence': '{:.1f}%'
        }),
        use_container_width=True
    )

    st.markdown("---")

    # Accuracy by Horizon (requested multi-horizon set)
    if 'horizon_minutes' in df.columns:
        st.subheader("⏱️ Accuracy by Horizon")
        df['horizon_label'] = df['horizon_minutes'].apply(lambda x: _bucket_horizon_minutes(int(x) if pd.notna(x) else 0))

        horizon_order = ['15m', '60m', '6h', '12h', '48h', '72h', 'Other']
        horizon_stats = df.groupby('horizon_label', observed=True).agg(
            accurate=('is_hit', 'sum'),
            total=('is_hit', 'count'),
            avg_pct_error=('pct_error_val', 'mean'),
            avg_abs_error=('abs_error_val', 'mean'),
        ).reset_index()
        horizon_stats['accuracy_rate'] = (horizon_stats['accurate'] / horizon_stats['total'] * 100.0).round(3)
        horizon_stats['horizon_label'] = pd.Categorical(horizon_stats['horizon_label'], categories=horizon_order, ordered=True)
        horizon_stats = horizon_stats.sort_values('horizon_label')

        st.dataframe(
            horizon_stats.style.format(
                {
                    'accuracy_rate': '{:.1f}%',
                    'avg_pct_error': '{:.2f}%',
                    'avg_abs_error': '{:.4f}',
                }
            ),
            use_container_width=True,
        )

    st.markdown("---")

    # Growth / decline rate chart (Gold)
    st.subheader("📈 Gold Rise/Fall Rate (Daily)")
    st.caption("Daily percentage change based on last available Gold price each day.")

    days = 30
    try:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT asset, price, timestamp
            FROM prices
            WHERE asset = 'Gold'
              AND timestamp IS NOT NULL AND timestamp != ''
              AND datetime(replace(substr(timestamp,1,19),'T',' ')) >= datetime('now', ?)
            ORDER BY datetime(replace(substr(timestamp,1,19),'T',' ')) ASC
            """,
            (f'-{int(days)} days',),
        )
        price_rows = cur.fetchall() or []
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        price_rows = []

    if not price_rows:
        st.info("No Gold price history found yet.")
    else:
        pdf = pd.DataFrame(price_rows, columns=['asset', 'price', 'timestamp'])
        pdf['timestamp'] = pd.to_datetime(pdf['timestamp'], errors='coerce', utc=True)
        pdf = pdf.dropna(subset=['timestamp', 'price']).copy()
        pdf['price'] = pd.to_numeric(pdf['price'], errors='coerce')
        pdf = pdf.dropna(subset=['price']).copy()
        pdf['date'] = pdf['timestamp'].dt.date

        # Last price per day (close proxy)
        daily = pdf.sort_values('timestamp').groupby('date').tail(1).sort_values('date')
        daily['daily_pct_change'] = daily['price'].pct_change() * 100.0

        fig_ret = go.Figure()
        fig_ret.add_trace(
            go.Bar(
                x=daily['date'],
                y=daily['daily_pct_change'],
                name='Daily % Change',
            )
        )
        fig_ret.update_layout(
            title='Gold Daily Rise/Fall Rate',
            xaxis_title='Date',
            yaxis_title='Change (%)',
            paper_bgcolor='#0E1117',
            plot_bgcolor='#1E2130',
            font={'color': '#FAFAFA'},
            height=360,
            hovermode='x unified',
        )
        st.plotly_chart(fig_ret, use_container_width=True)

    # Evaluated forecasts table
    st.subheader("✅ Evaluated Forecasts")
    cols = [c for c in [
        'id',
        'asset',
        'direction',
        'actual_direction',
        'is_hit',
        'horizon_minutes',
        forecast_time_col,
        evaluation_time_col,
        'actual_time',
        'evaluation_quality',
        'price_at_forecast',
        'actual_price',
        'price_at_evaluation',
        'actual_return',
        'abs_error_val',
        'pct_error_val',
    ] if c and c in df.columns]

    table_df = df[cols].copy() if cols else df.copy()
    # Friendly names
    if 'is_hit' in table_df.columns:
        table_df['is_hit'] = table_df['is_hit'].astype(bool)

    st.dataframe(table_df.head(200), use_container_width=True)
    
    st.markdown("---")
    
    # Accuracy over time
    st.subheader("📅 Accuracy Trend Over Time")
    
    # Group by date
    df['forecast_date'] = df['forecast_time'].dt.date
    time_stats = df.groupby('forecast_date').agg({
        'is_hit': lambda x: (x.sum() / len(x) * 100) if len(x) > 0 else 0,
        'id': 'count'
    }).reset_index()
    
    time_stats.columns = ['date', 'accuracy_rate', 'forecast_count']
    
    # Line chart
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=time_stats['date'],
        y=time_stats['accuracy_rate'],
        mode='lines+markers',
        name='Accuracy Rate',
        line=dict(color='#D4AF37', width=3),
        marker=dict(size=8)
    ))
    
    fig.add_hline(y=50, line_dash="dash", line_color="gray", 
                  annotation_text="50% Baseline", annotation_position="right")
    
    fig.update_layout(
        title="Forecast Accuracy Over Time",
        xaxis_title="Date",
        yaxis_title="Accuracy Rate (%)",
        yaxis=dict(range=[0, 100]),
        paper_bgcolor='#0E1117',
        plot_bgcolor='#1E2130',
        font={'color': '#FAFAFA'},
        height=400,
        hovermode='x unified'
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Confidence calibration
    st.subheader("🎲 Confidence Calibration")
    st.caption("How well do our confidence levels match actual accuracy?")
    
    # Bin by confidence (automated schema uses confidence_pct)
    df['confidence_bin'] = pd.cut(
        df['confidence_pct'],
        bins=[0, 40, 50, 60, 70, 80, 100],
        labels=['0-40%', '40-50%', '50-60%', '60-70%', '70-80%', '80-100%']
    )

    calibration = df.groupby('confidence_bin', observed=True).agg({
        'is_hit': lambda x: (x.sum() / len(x) * 100) if len(x) > 0 else 0,
        'id': 'count'
    }).reset_index()
    
    calibration.columns = ['confidence_range', 'actual_accuracy', 'count']
    
    # Create comparison chart
    fig = go.Figure()
    
    # Expected line (perfect calibration) — match present bins exactly
    midpoint_map = {
        '0-40%': 20,
        '40-50%': 45,
        '50-60%': 55,
        '60-70%': 65,
        '70-80%': 75,
        '80-100%': 90,
    }
    expected = [midpoint_map.get(str(x), None) for x in calibration['confidence_range']]

    # Marker sizes reflect sample sizes (tiny bins are noisy)
    sizes = []
    for c in calibration['count']:
        try:
            n = int(c)
        except Exception:
            n = 0
        sizes.append(max(8, min(18, 6 + n)))
    fig.add_trace(go.Scatter(
        x=calibration['confidence_range'],
        y=expected,
        mode='lines',
        name='Perfect Calibration',
        line=dict(color='gray', dash='dash')
    ))
    
    # Actual accuracy
    fig.add_trace(go.Scatter(
        x=calibration['confidence_range'],
        y=calibration['actual_accuracy'],
        mode='lines+markers',
        name='Actual Accuracy',
        line=dict(color='#D4AF37', width=3),
        marker=dict(size=sizes)
    ))
    
    fig.update_layout(
        title="Confidence Calibration (Expected vs Actual)",
        xaxis_title="Confidence Range",
        yaxis_title="Accuracy (%)",
        yaxis=dict(range=[0, 100]),
        paper_bgcolor='#0E1117',
        plot_bgcolor='#1E2130',
        font={'color': '#FAFAFA'},
        height=400
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("📖 What does this mean?"):
        st.write("""
        **Perfect Calibration**: When we say 60% confidence, we should be right 60% of the time.
        
        - **Above the line**: We're more accurate than our confidence suggests (good, but we could be more confident)
        - **Below the line**: We're less accurate than our confidence suggests (need to be more cautious)
        - **On the line**: Perfect calibration - our confidence matches reality
        
        This helps us continuously improve our forecasting system.
        """)
    
    st.markdown("---")
    
    # Best and worst performing categories
    st.subheader("🏆 Best & Worst Performing Categories")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### ✅ Best Assets")
        best = asset_stats.nlargest(3, 'accuracy_rate')[['asset', 'accuracy_rate', 'total']]
        for idx, row in best.iterrows():
            st.success(f"**{row['asset']}**: {row['accuracy_rate']:.1f}% ({int(row['total'])} forecasts)")
    
    with col2:
        st.markdown("#### ⚠️ Needs Improvement")
        worst = asset_stats.nsmallest(3, 'accuracy_rate')[['asset', 'accuracy_rate', 'total']]
        for idx, row in worst.iterrows():
            st.warning(f"**{row['asset']}**: {row['accuracy_rate']:.1f}% ({int(row['total'])} forecasts)")
    
    st.markdown("---")
    
    # Recent forecasts detail
    st.subheader("📋 Recent Forecast Results")
    
    # Get last 10 evaluated
    recent = df.nlargest(10, 'evaluation_time')
    
    for idx, forecast in recent.iterrows():
        with st.expander(f"{forecast['asset']} - {forecast['forecast_time'].strftime('%Y-%m-%d %H:%M')}"):
            col_a, col_b, col_c = st.columns(3)
            
            with col_a:
                expected = forecast.get('direction', 'N/A')
                actual = forecast.get('actual_direction', 'N/A')
                st.write("**Expected:**", expected)
                st.write("**Actual:**", actual)
                is_hit = bool(forecast.get('is_hit'))
                result = "✅ HIT" if is_hit else "❌ MISS"
                (st.success if is_hit else st.error)(result)
            
            with col_b:
                st.write("**Confidence:**", f"{float(forecast.get('confidence_pct') or 0):.1f}%")
                st.write("**Risk Level:**", forecast.get('risk_level', 'N/A'))
                st.write("**Time Horizon:**", f"{int(forecast.get('horizon_minutes') or 0)} min")
            
            with col_c:
                actual_return = forecast.get('actual_return')
                if actual_return is not None:
                    st.write("**Actual Return:**", f"{float(actual_return):+.2f}%")
                st.write("**Forecast Price:**", f"${float(forecast.get('price_at_forecast') or 0):.2f}")
                st.write("**Actual Price:**", f"${float(forecast.get('price_at_evaluation') or 0):.2f}")
            
            reasoning = forecast.get('reasoning')
            if reasoning:
                st.caption(f"Reasoning: {reasoning}")

# Disclaimer
st.markdown("---")
st.markdown("""
<div style='background-color: #2E1A1A; border: 1px solid #D4AF37; border-radius: 5px; padding: 15px;'>
<strong>⚠️ Transparency Commitment</strong><br>
This page demonstrates our commitment to <strong>honest evaluation</strong>. We track every forecast and measure actual outcomes. 
No cherry-picking, no hiding failures. This data helps us improve and helps you understand the probabilistic nature of forecasting.
<strong>Past performance does not guarantee future results.</strong>
</div>
""", unsafe_allow_html=True)
