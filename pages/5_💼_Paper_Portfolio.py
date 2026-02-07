"""Paper Portfolio.

Read-only view backed by the automated worker (paper_portfolio + paper_trades).
No manual trade buttons; the worker opens/closes trades automatically.
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime
import pandas as pd
import sys
import os
import importlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db.db import get_db
from streamlit_worker import ensure_worker_running

st.set_page_config(page_title="Paper Portfolio", page_icon="💼", layout="wide")

# Ensure background worker is running
ensure_worker_running()


def _has_matplotlib() -> bool:
    """Return True if matplotlib is importable.

    Pandas Styler.background_gradient() requires matplotlib. We treat it as optional
    so the page works in minimal environments.
    """
    try:
        importlib.import_module('matplotlib')
        return True
    except Exception:
        return False


st.title("💼 Paper Portfolio Simulation")
st.caption("Virtual $1,000 portfolio for educational trading simulation")

db = get_db()

portfolio = db.get_portfolio()
all_trades = db.get_all_trades(limit=1000)
open_trades = db.get_open_trades()
portfolio_perf = db.get_portfolio_performance()

starting_equity = float(portfolio['starting_equity']) if portfolio else 1000.0
current_equity = float(portfolio['current_equity']) if portfolio else starting_equity


def _round_money(value: float) -> float:
    """Avoid confusing -0.00 outputs caused by floating rounding."""
    try:
        v = float(value)
    except Exception:
        v = 0.0
    if abs(v) < 0.005:
        return 0.0
    return v


def _fmt_money(value: float) -> str:
    return f"${_round_money(value):.2f}"

# Compute unrealized PnL for open positions using latest DB prices
open_pnl = 0.0
latest_prices = {}

# Pull prices for default watchlist + any currently open-trade assets
watch_assets = {'USD Index', 'Gold', 'Silver', 'Oil', 'Bitcoin'}
watch_assets.update({t.get('asset') for t in open_trades if t.get('asset')})

for asset in sorted(watch_assets):
    row = db.get_latest_price(asset)
    if row:
        try:
            latest_prices[asset] = float(row['price'])
        except Exception:
            pass

for trade in open_trades:
    asset = trade.get('asset')
    entry_price = float(trade.get('entry_price') or 0)
    size_usd = float(trade.get('size_usd') or 0)
    side = trade.get('side')
    current_price = latest_prices.get(asset)

    if not current_price or entry_price <= 0 or size_usd <= 0:
        continue

    if side == 'BUY':
        unrealized = (current_price - entry_price) / entry_price * size_usd
    else:
        unrealized = (entry_price - current_price) / entry_price * size_usd

    open_pnl += unrealized

total_equity = current_equity + open_pnl

# Only guard against negative-zero / rounding artifacts; do not hide real losses
total_equity_disp = _round_money(total_equity)
open_pnl_disp = _round_money(open_pnl)
closed_pnl_disp = _round_money(current_equity - starting_equity)

# Portfolio overview
st.subheader("💰 Portfolio Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    delta_equity = _round_money(total_equity_disp - starting_equity)
    st.metric("Total Equity", _fmt_money(total_equity_disp), f"{delta_equity:+.2f}")

with col2:
    st.metric("Closed P&L", _fmt_money(closed_pnl_disp))

with col3:
    st.metric("Open P&L", _fmt_money(open_pnl_disp))
    st.caption(
        "Small open P&L values (e.g., ±$0.01–$0.05) are normal: they come from mark-to-market using the latest stored price snapshot plus rounding."
    )

with col4:
    return_pct = ((total_equity_disp - starting_equity) / starting_equity * 100) if starting_equity else 0
    st.metric("Return", f"{return_pct:+.2f}%")

st.markdown("---")

# Performance metrics
st.subheader("📈 Performance Metrics")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Trades", portfolio_perf.get('total_trades', 0))

with col2:
    st.metric("Winning Trades", portfolio_perf.get('winning_trades', 0))

with col3:
    st.metric("Losing Trades", portfolio_perf.get('losing_trades', 0))

with col4:
    win_rate = portfolio_perf.get('win_rate', 0)
    st.metric("Win Rate", f"{win_rate:.1f}%")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Avg P&L per Trade", f"${portfolio_perf.get('avg_pnl', 0):.2f}")

with col2:
    st.metric("Largest Win", f"${portfolio_perf.get('max_win', 0):.2f}")

with col3:
    st.metric("Largest Loss", f"${portfolio_perf.get('max_loss', 0):.2f}")

st.markdown("---")

# Equity curve
if all_trades:
    st.subheader("📊 Equity Curve")
    
    df_trades = pd.DataFrame(all_trades)
    df_closed = df_trades[df_trades['status'] == 'closed'].copy()
    
    if not df_closed.empty:
        df_closed['exit_time'] = pd.to_datetime(df_closed['exit_time'])
        df_closed = df_closed.sort_values('exit_time')
        df_closed['pnl'] = pd.to_numeric(df_closed.get('pnl'), errors='coerce').fillna(0.0)
        df_closed['cumulative_pnl'] = df_closed['pnl'].cumsum()
        df_closed['equity'] = starting_equity + df_closed['cumulative_pnl']
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df_closed['exit_time'],
            y=df_closed['equity'],
            mode='lines',
            name='Equity',
            line=dict(color='#D4AF37', width=3),
            fill='tonexty',
            fillcolor='rgba(212, 175, 55, 0.1)'
        ))
        
        fig.add_hline(y=starting_equity, line_dash="dash", line_color="gray",
                  annotation_text=f"Starting Equity (${starting_equity:.0f})")
        
        fig.update_layout(
            title="Portfolio Equity Over Time",
            xaxis_title="Date",
            yaxis_title="Equity ($)",
            paper_bgcolor='#0E1117',
            plot_bgcolor='#1E2130',
            font={'color': '#FAFAFA'},
            height=400,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# Open Positions
st.subheader("📊 Open Positions")

if not open_trades:
    st.info("No open positions currently.")
else:
    for trade in open_trades:
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
            
            asset = trade['asset']
            side = trade.get('side')
            entry_price = float(trade.get('entry_price') or 0)
            size_usd = float(trade.get('size_usd') or 0)

            current_price = latest_prices.get(asset, entry_price)
            
            # Calculate unrealized P&L
            if side == 'BUY':
                unrealized_pnl = (current_price - entry_price) / entry_price * size_usd if entry_price else 0
                pnl_pct = (current_price - entry_price) / entry_price * 100 if entry_price else 0
                badge_color = "🟢"
                label = "BUY"
            else:
                unrealized_pnl = (entry_price - current_price) / entry_price * size_usd if entry_price else 0
                pnl_pct = (entry_price - current_price) / entry_price * 100 if entry_price else 0
                badge_color = "🔴"
                label = "SELL"
            
            with col1:
                st.markdown(f"### {asset}")
                st.caption(f"{badge_color} {label}")
            
            with col2:
                st.metric("Entry", f"${entry_price:.2f}")
            
            with col3:
                st.metric("Current", f"${current_price:.2f}")
            
            with col4:
                st.metric("Size", f"${size_usd:.2f}")
            
            with col5:
                delta_color = "normal" if unrealized_pnl >= 0 else "inverse"
                st.metric("P&L", f"${unrealized_pnl:.2f}", f"{pnl_pct:+.2f}%", delta_color=delta_color)
            
            # Entry time and notes
            entry_time = trade.get('entry_time', '')
            if entry_time:
                try:
                    dt = datetime.fromisoformat(entry_time)
                    st.caption(f"⏰ Opened: {dt.strftime('%Y-%m-%d %H:%M')}")
                except:
                    pass
            
            if trade.get('notes'):
                st.caption(f"📝 {trade['notes']}")
            
            st.caption("Positions are managed automatically by the worker.")
            
            st.markdown("---")

# Trade History
st.subheader("📜 Trade History")

if not all_trades:
    st.info("No trades yet. Trading simulation will appear here.")
else:
    # Display recent trades
    df_trades = pd.DataFrame(all_trades)
    
    # Recent trades table
    display_cols = ['asset', 'side', 'entry_price', 'exit_price', 'size_usd', 'pnl', 'status', 'entry_time']
    display_df = df_trades[display_cols].copy() if all(c in df_trades.columns for c in display_cols) else df_trades.copy()
    
    # Format
    display_df['entry_time'] = pd.to_datetime(display_df['entry_time']).dt.strftime('%Y-%m-%d %H:%M')
    display_df = display_df.sort_values('entry_time', ascending=False).head(20)
    
    # Optional visual styling: gradient requires matplotlib.
    enable_gradient = _has_matplotlib()
    if enable_gradient:
        st.caption("Advanced visual styling enabled")
    else:
        st.caption("Basic table view (matplotlib not installed)")

    try:
        styler = display_df.style.format(
            {
                'entry_price': '${:.2f}',
                'exit_price': '${:.2f}',
                'size_usd': '${:.2f}',
                'pnl': '${:.2f}',
            }
        )

        if enable_gradient:
            # Guard even when matplotlib exists: do not let styling crash the page.
            try:
                styler = styler.background_gradient(
                    subset=['pnl'], cmap='RdYlGn', vmin=-50, vmax=50
                )
            except Exception:
                enable_gradient = False

        # Always show formatted table; gradient is optional visual sugar.
        st.dataframe(styler, use_container_width=True)
    except Exception:
        # Absolute fallback: always render something.
        st.dataframe(display_df, use_container_width=True)

# Risk warning
st.markdown("---")
st.markdown("""
<div style='background-color: #2E1A1A; border: 1px solid #D4AF37; border-radius: 5px; padding: 15px;'>
<strong>⚠️ EDUCATIONAL SIMULATION ONLY</strong><br>
This is a <strong>virtual portfolio with simulated funds</strong>. No real money is at risk.
This simulation is for <strong>learning purposes only</strong> to understand:
<ul>
<li>Position sizing and risk management</li>
<li>Trading psychology and discipline</li>
<li>Performance tracking and evaluation</li>
</ul>
<strong>This is NOT real trading and does NOT constitute investment advice.</strong><br>
Real trading involves significant risk of loss. Always consult licensed professionals before making investment decisions.
</div>
""", unsafe_allow_html=True)
