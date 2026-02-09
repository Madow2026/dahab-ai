"""
🎓 Manual Trading Training Simulator
Educational paper trading environment for learning trading rules and discipline
COMPLETELY ISOLATED from AI forecasts and automated trading
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from engine.training_db import get_training_db
from db.db import get_db

st.set_page_config(
    page_title="Trading Training Simulator", 
    page_icon="🎓", 
    layout="wide"
)

# Professional dark theme CSS
st.markdown("""
<style>
    /* Main styling */
    .main {
        background-color: #0e1117;
    }
    
    /* Training card */
    .training-card {
        background: linear-gradient(135deg, #1a1d24 0%, #252932 100%);
        border-radius: 15px;
        padding: 25px;
        border: 1px solid #2a2e37;
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.4);
        margin-bottom: 20px;
    }
    
    /* Educational tip box */
    .tip-box {
        background: linear-gradient(135deg, #1e3a5f 0%, #2a5298 100%);
        border-left: 4px solid #4a90e2;
        border-radius: 8px;
        padding: 15px;
        margin: 15px 0;
        color: #e0e0e0;
    }
    
    .tip-box strong {
        color: #ffd700;
    }
    
    /* Rule violations */
    .violation-box {
        background: linear-gradient(135deg, #5f1e1e 0%, #982a2a 100%);
        border-left: 4px solid #e74c3c;
        border-radius: 8px;
        padding: 15px;
        margin: 15px 0;
        color: #ffcccc;
    }
    
    /* Success box */
    .success-box {
        background: linear-gradient(135deg, #1e5f1e 0%, #2a982a 100%);
        border-left: 4px solid #00d4aa;
        border-radius: 8px;
        padding: 15px;
        margin: 15px 0;
        color: #ccffcc;
    }
    
    /* Metric cards */
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 700;
    }
    
    /* Buttons */
    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        padding: 12px 28px;
        transition: all 0.3s;
    }
    
    /* Buy button */
    .buy-button {
        background: linear-gradient(90deg, #00d4aa 0%, #00a896 100%);
    }
    
    /* Sell button */
    .sell-button {
        background: linear-gradient(90deg, #e74c3c 0%, #c0392b 100%);
    }
    
    /* Tables */
    .dataframe {
        background-color: #1a1d24;
        border-radius: 8px;
        font-size: 0.9rem;
    }
    
    /* Headers */
    h1 {
        color: #ffd700;
        font-weight: 700;
    }
    
    h2, h3 {
        color: #4a90e2;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Initialize
training_db = get_training_db()
main_db = get_db()  # Only for reading current prices

# Session state
if 'current_training_session' not in st.session_state:
    st.session_state.current_training_session = None
if 'show_settings' not in st.session_state:
    st.session_state.show_settings = False
if 'last_trade_message' not in st.session_state:
    st.session_state.last_trade_message = None


def get_current_prices() -> dict:
    """Fetch current prices from main DB (READ-ONLY)"""
    prices = {}
    assets = ['Gold', 'Silver', 'Oil', 'Bitcoin', 'USD Index']
    
    for asset in assets:
        try:
            price_data = main_db.get_latest_price(asset)
            if price_data and price_data.get('price'):
                prices[asset] = float(price_data['price'])
            else:
                # Fallback demo prices
                fallback = {
                    'Gold': 2050.00,
                    'Silver': 24.50,
                    'Oil': 75.00,
                    'Bitcoin': 45000.00,
                    'USD Index': 103.50
                }
                prices[asset] = fallback.get(asset, 100.0)
        except:
            # Fallback if main DB unavailable
            fallback = {
                'Gold': 2050.00,
                'Silver': 24.50,
                'Oil': 75.00,
                'Bitcoin': 45000.00,
                'USD Index': 103.50
            }
            prices[asset] = fallback.get(asset, 100.0)
    
    return prices


def render_header():
    """Render page header"""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.title("🎓 Trading Training Simulator")
        st.caption("Learn trading discipline and risk management in a safe environment")
    
    with col2:
        st.markdown("### 📚 Training Mode")
        st.caption("*Paper money only*")


def render_educational_intro():
    """Display educational introduction"""
    st.markdown("""
    <div class="tip-box">
        <strong>🎯 Learning Objectives:</strong><br>
        • Master trading discipline and timing rules<br>
        • Understand how commissions affect profitability<br>
        • Practice risk management with position sizing<br>
        • Experience the psychology of winning and losing trades<br>
        • Learn that <em>timing discipline > prediction ability</em>
    </div>
    """, unsafe_allow_html=True)


def render_session_manager():
    """Render session selection/creation"""
    st.subheader("📂 Training Session")
    
    sessions = training_db.get_all_sessions()
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if sessions:
            session_options = {s['session_name']: s['id'] for s in sessions}
            selected_name = st.selectbox(
                "Select Session",
                options=list(session_options.keys()),
                key='session_selector'
            )
            
            if st.button("📊 Load Session"):
                st.session_state.current_training_session = session_options[selected_name]
                st.rerun()
        else:
            st.info("👉 Create your first training session to start learning!")
    
    with col2:
        if st.button("➕ New Session"):
            st.session_state.show_create = True
    
    with col3:
        if st.session_state.current_training_session:
            if st.button("⚙️ Settings"):
                st.session_state.show_settings = not st.session_state.show_settings
    
    # Create new session dialog
    if st.session_state.get('show_create', False):
        with st.expander("➕ Create New Training Session", expanded=True):
            new_name = st.text_input("Session Name", placeholder="e.g., Gold Trading Practice")
            new_capital = st.number_input("Initial Capital ($)", min_value=100, value=5000, step=500)
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("Create", type="primary"):
                    if new_name:
                        try:
                            session_id = training_db.create_session(new_name, new_capital)
                            st.session_state.current_training_session = session_id
                            st.session_state.show_create = False
                            st.success(f"✅ Session '{new_name}' created!")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
                    else:
                        st.warning("Please enter a session name")
            
            with col_b:
                if st.button("Cancel"):
                    st.session_state.show_create = False
                    st.rerun()


def render_settings_panel(session_id: int):
    """Render trading rules settings"""
    if not st.session_state.show_settings:
        return
    
    with st.expander("⚙️ Trading Rules & Settings", expanded=True):
        session = training_db.get_session(session_id)
        settings = session['settings']
        
        st.markdown("### 📋 Adjust Your Training Rules")
        
        col1, col2 = st.columns(2)
        
        with col1:
            commission = st.slider(
                "Commission Rate (%)",
                min_value=0.0,
                max_value=1.0,
                value=settings.get('commission_rate', 0.001) * 100,
                step=0.01,
                help="Realistic commissions teach cost awareness"
            )
            
            min_gap = st.slider(
                "Minimum Time Between Trades (minutes)",
                min_value=0,
                max_value=60,
                value=settings.get('min_trade_gap_minutes', 5),
                step=5,
                help="Prevents overtrading and emotional decisions"
            )
            
            max_position = st.slider(
                "Max Position Size (% of capital)",
                min_value=10,
                max_value=100,
                value=settings.get('max_position_size_percent', 50),
                step=5,
                help="Risk management through position sizing"
            )
        
        with col2:
            cooldown = st.slider(
                "Cooldown After Loss (minutes)",
                min_value=0,
                max_value=60,
                value=settings.get('cooldown_after_loss_minutes', 0),
                step=5,
                help="Prevents revenge trading after losses"
            )
            
            allow_short = st.checkbox(
                "Allow Short Selling",
                value=settings.get('allow_short_selling', False),
                help="Advanced: sell assets you don't own"
            )
        
        if st.button("💾 Save Settings", type="primary"):
            new_settings = {
                'commission_rate': commission / 100,
                'min_trade_gap_minutes': min_gap,
                'max_position_size_percent': max_position,
                'cooldown_after_loss_minutes': cooldown,
                'allow_short_selling': allow_short
            }
            training_db.update_session_settings(session_id, new_settings)
            st.success("✅ Settings updated!")
            st.session_state.show_settings = False
            st.rerun()


def render_portfolio_metrics(session_id: int, current_prices: dict):
    """Render portfolio metrics cards"""
    stats = training_db.get_session_statistics(session_id, current_prices)
    
    st.markdown("### 💼 Portfolio Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "💵 Cash Balance",
            f"${stats['current_cash']:,.2f}",
            help="Available for new trades"
        )
    
    with col2:
        st.metric(
            "💰 Total Equity",
            f"${stats['total_equity']:,.2f}",
            delta=f"{stats['total_pnl_pct']:+.2f}%",
            help="Cash + Positions Value"
        )
    
    with col3:
        pnl_color = "normal" if stats['total_pnl'] >= 0 else "inverse"
        st.metric(
            "📊 Total P&L",
            f"${stats['total_pnl']:+,.2f}",
            delta=f"Realized: ${stats['realized_pnl']:+,.2f}",
            delta_color=pnl_color,
            help="Realized + Unrealized profit/loss"
        )
    
    with col4:
        win_rate_color = "normal" if stats['win_rate'] >= 50 else "inverse"
        st.metric(
            "🎯 Win Rate",
            f"{stats['win_rate']:.1f}%",
            delta=f"{stats['winning_trades']}/{stats['total_trades']} trades",
            delta_color=win_rate_color,
            help="Percentage of profitable trades"
        )
    
    # Additional stats
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        st.metric("📍 Open Positions", stats['num_positions'])
    
    with col6:
        st.metric("📈 Unrealized P&L", f"${stats['unrealized_pnl']:+,.2f}")
    
    with col7:
        st.metric("💸 Commission Paid", f"${stats['total_commission']:.2f}")
    
    with col8:
        st.metric("📦 Trades Executed", stats['total_trades'])


def render_trading_interface(session_id: int, current_prices: dict):
    """Render manual trading controls"""
    st.markdown("### 🎮 Trading Controls")
    
    session = training_db.get_session(session_id)
    settings = session['settings']
    
    col_info, col_trade = st.columns([1, 2])
    
    with col_info:
        st.markdown("#### 📋 Current Rules")
        st.markdown(f"""
        - **Commission:** {settings['commission_rate']*100:.2f}%
        - **Min Time Gap:** {settings['min_trade_gap_minutes']} min
        - **Max Position:** {settings['max_position_size_percent']}%
        - **Cooldown After Loss:** {settings['cooldown_after_loss_minutes']} min
        """)
        
        if session['last_trade_at']:
            last_trade = datetime.fromisoformat(session['last_trade_at'])
            time_since = datetime.now() - last_trade
            min_gap = timedelta(minutes=settings['min_trade_gap_minutes'])
            
            if time_since < min_gap:
                remaining = (min_gap - time_since).total_seconds() / 60
                st.warning(f"⏰ Wait {remaining:.1f} more minutes")
            else:
                st.success("✅ Ready to trade")
    
    with col_trade:
        # Asset selection
        tradable_assets = ['Gold', 'Silver', 'Oil', 'Bitcoin']
        selected_asset = st.selectbox("Asset", tradable_assets)
        
        current_price = current_prices.get(selected_asset, 0)
        st.info(f"💵 Current Price: **${current_price:,.2f}**")
        
        # Show current position
        position = training_db.get_position(session_id, selected_asset)
        if position:
            market_value = position['quantity'] * current_price
            unrealized = market_value - position['total_cost']
            unrealized_pct = (unrealized / position['total_cost']) * 100
            
            st.markdown(f"""
            **Current Position:**
            - Quantity: {position['quantity']:.4f} units
            - Avg Entry: ${position['avg_entry_price']:,.2f}
            - Unrealized P&L: ${unrealized:+,.2f} ({unrealized_pct:+.2f}%)
            """)
        else:
            st.info("No position in this asset")
        
        # Trading inputs
        col_qty, col_btn = st.columns([2, 1])
        
        with col_qty:
            if selected_asset == 'Bitcoin':
                default_qty = 0.01
                step = 0.001
                fmt = "%.4f"
            elif selected_asset in ['Gold', 'Silver']:
                default_qty = 1.0
                step = 0.1
                fmt = "%.2f"
            else:
                default_qty = 1.0
                step = 1.0
                fmt = "%.1f"
            
            quantity = st.number_input(
                "Quantity",
                min_value=step,
                value=default_qty,
                step=step,
                format=fmt
            )
        
        # Calculate trade value
        trade_value = quantity * current_price
        commission = trade_value * settings['commission_rate']
        total_cost = trade_value + commission
        
        st.caption(f"Trade Value: ${trade_value:,.2f} | Commission: ${commission:.2f} | Total: ${total_cost:,.2f}")
        
        # Buy/Sell buttons
        col_buy, col_sell = st.columns(2)
        
        with col_buy:
            if st.button("🟢 BUY", type="primary", use_container_width=True):
                result = training_db.execute_trade(
                    session_id, selected_asset, 'BUY', quantity, current_price
                )
                
                if result['success']:
                    st.session_state.last_trade_message = {
                        'type': 'success',
                        'message': f"""
                        ✅ **BUY Executed Successfully!**
                        
                        {quantity:.4f} {selected_asset} @ ${current_price:,.2f}
                        
                        Commission: ${result['commission']:.2f}
                        
                        New Balance: ${result['new_balance']:,.2f}
                        """
                    }
                else:
                    st.session_state.last_trade_message = {
                        'type': 'error',
                        'message': f"❌ **Trade Blocked**\n\n{result['reason']}"
                    }
                
                st.rerun()
        
        with col_sell:
            if st.button("🔴 SELL", type="secondary", use_container_width=True):
                result = training_db.execute_trade(
                    session_id, selected_asset, 'SELL', quantity, current_price
                )
                
                if result['success']:
                    pnl_emoji = "🎉" if result['pnl_realized'] > 0 else "😔"
                    st.session_state.last_trade_message = {
                        'type': 'success' if result['pnl_realized'] >= 0 else 'warning',
                        'message': f"""
                        {pnl_emoji} **SELL Executed!**
                        
                        {quantity:.4f} {selected_asset} @ ${current_price:,.2f}
                        
                        Realized P&L: ${result['pnl_realized']:+,.2f}
                        
                        Commission: ${result['commission']:.2f}
                        
                        New Balance: ${result['new_balance']:,.2f}
                        """
                    }
                else:
                    st.session_state.last_trade_message = {
                        'type': 'error',
                        'message': f"❌ **Trade Blocked**\n\n{result['reason']}"
                    }
                
                st.rerun()
    
    # Display last trade result
    if st.session_state.last_trade_message:
        msg = st.session_state.last_trade_message
        if msg['type'] == 'success':
            st.success(msg['message'])
        elif msg['type'] == 'error':
            st.error(msg['message'])
        elif msg['type'] == 'warning':
            st.warning(msg['message'])
        
        # Clear after showing
        if st.button("Clear Message"):
            st.session_state.last_trade_message = None
            st.rerun()


def render_positions_table(session_id: int, current_prices: dict):
    """Render open positions"""
    st.markdown("### 📊 Open Positions")
    
    positions = training_db.get_all_positions(session_id)
    
    if not positions:
        st.info("No open positions. Buy assets to start trading!")
        return
    
    # Build display table
    position_data = []
    for pos in positions:
        current_price = current_prices.get(pos['asset'], pos['avg_entry_price'])
        market_value = pos['quantity'] * current_price
        cost = pos['total_cost']
        unrealized = market_value - cost
        unrealized_pct = (unrealized / cost) * 100
        
        position_data.append({
            'Asset': pos['asset'],
            'Quantity': f"{pos['quantity']:.4f}",
            'Avg Entry': f"${pos['avg_entry_price']:,.2f}",
            'Current Price': f"${current_price:,.2f}",
            'Market Value': f"${market_value:,.2f}",
            'Cost Basis': f"${cost:,.2f}",
            'Unrealized P&L': f"${unrealized:+,.2f}",
            'Unrealized %': f"{unrealized_pct:+.2f}%"
        })
    
    df = pd.DataFrame(position_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_trade_history(session_id: int):
    """Render trade history table"""
    st.markdown("### 📜 Trade History")
    
    trades = training_db.get_trade_history(session_id, limit=30)
    
    if not trades:
        st.info("No trades yet. Start trading to see your history!")
        return
    
    trade_data = []
    for trade in trades:
        trade_data.append({
            'Time': datetime.fromisoformat(trade['timestamp']).strftime('%Y-%m-%d %H:%M'),
            'Asset': trade['asset'],
            'Action': trade['action'],
            'Quantity': f"{trade['quantity']:.4f}",
            'Price': f"${trade['price']:,.2f}",
            'Commission': f"${trade['commission']:.2f}",
            'Realized P&L': f"${trade['pnl_realized']:+,.2f}" if trade['action'] == 'SELL' else '-',
            'Balance After': f"${trade['balance_after']:,.2f}"
        })
    
    df = pd.DataFrame(trade_data)
    st.dataframe(df, use_container_width=True, hide_index=True)


def render_educational_tips():
    """Display educational tips and insights"""
    st.markdown("### 🎓 Trading Lessons")
    
    tips = [
        {
            'title': 'Commission Awareness',
            'content': 'Every trade costs money. Two round trips (buy→sell→buy→sell) means 4 commissions. Trade less, profit more!'
        },
        {
            'title': 'Timing Discipline',
            'content': 'The time gap rule prevents emotional overtrading. Professional traders wait for setups, not chase every move.'
        },
        {
            'title': 'Position Sizing',
            'content': 'Never risk your entire capital on one trade. The max position rule protects you from catastrophic losses.'
        },
        {
            'title': 'Loss Cooldown',
            'content': 'After a loss, emotions run high. The cooldown prevents "revenge trading" - forcing yourself to be rational.'
        },
        {
            'title': 'Win Rate ≠ Profitability',
            'content': 'You can be right 70% of the time and still lose money if your losses are bigger than your wins. Risk:Reward matters!'
        }
    ]
    
    for tip in tips:
        with st.expander(f"💡 {tip['title']}"):
            st.markdown(tip['content'])


def main():
    """Main application"""
    render_header()
    
    # Check if user has selected a session
    if not st.session_state.current_training_session:
        render_educational_intro()
        render_session_manager()
        
        st.markdown("---")
        
        # Show demo of what's available
        st.markdown("### 🎯 What You'll Learn")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            **📊 Trading Mechanics**
            - Buy and sell assets
            - Manage positions
            - Track profit/loss
            """)
        
        with col2:
            st.markdown("""
            **⚖️ Risk Management**
            - Position sizing
            - Commission impact
            - Capital preservation
            """)
        
        with col3:
            st.markdown("""
            **🧠 Trading Psychology**
            - Timing discipline
            - Emotional control
            - Loss management
            """)
        
        st.markdown("---")
        render_educational_tips()
        
        return
    
    # Main trading interface
    session_id = st.session_state.current_training_session
    
    # Session info bar
    session = training_db.get_session(session_id)
    col_name, col_reset = st.columns([4, 1])
    
    with col_name:
        st.info(f"📂 **Active Session:** {session['session_name']}")
    
    with col_reset:
        if st.button("🔄 Change Session"):
            st.session_state.current_training_session = None
            st.rerun()
    
    # Get current prices
    current_prices = get_current_prices()
    
    # Settings panel
    render_settings_panel(session_id)
    
    st.markdown("---")
    
    # Portfolio metrics
    render_portfolio_metrics(session_id, current_prices)
    
    st.markdown("---")
    
    # Trading interface and positions
    col_trade, col_positions = st.columns([1, 1])
    
    with col_trade:
        render_trading_interface(session_id, current_prices)
    
    with col_positions:
        render_positions_table(session_id, current_prices)
    
    st.markdown("---")
    
    # Trade history
    render_trade_history(session_id)
    
    st.markdown("---")
    
    # Educational tips
    render_educational_tips()
    
    # Footer
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px; margin-top: 30px;'>
        <p><strong>🎓 Training Mode</strong> | Paper money only | For educational purposes</p>
        <p>Master these skills before risking real capital</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
