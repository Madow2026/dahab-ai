"""
Auto Paper Trading Engine
Makes simulated trading decisions based on forecasts
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import config
from db.db import get_db

class AutoTrader:
    """Automated paper trading with strict guardrails"""
    
    def __init__(self):
        self.db = get_db()
    
    def evaluate_forecast_for_trading(self, forecast: Dict, current_price: float) -> Optional[Dict]:
        """
        Evaluate if forecast should trigger a trade
        Returns trade dict or None if guardrails prevent trade
        """
        try:
            # Check if trading is paused (daily loss limit)
            portfolio = self.db.get_portfolio()
            if not portfolio:
                print("⚠️ Trader: No portfolio found")
                return None
            if portfolio.get('is_trading_paused'):
                print("⚠️ Trader: Trading paused")
                return None
            
            # Guardrail 1: Confidence threshold
            confidence = forecast.get('confidence', 0)
            if confidence < config.MIN_CONFIDENCE_FOR_TRADE:
                return None
            
            # Guardrail 2: Direction must not be NEUTRAL
            direction = forecast.get('direction', 'NEUTRAL')
            if direction == 'NEUTRAL':
                return None
            
            # Guardrail 3: Must have valid current price
            if not current_price or current_price <= 0:
                return None
            
            # Guardrail 4: Max open trades per asset
            try:
                open_trades = self.db.get_open_trades_for_asset(forecast['asset'])
                if len(open_trades) >= config.MAX_OPEN_TRADES_PER_ASSET:
                    return None
            except Exception:
                pass  # Don't block trading if check fails
            
            # Guardrail 5: Max trades per hour
            try:
                if not self._check_hourly_limit():
                    return None
            except Exception:
                pass  # Don't block trading if check fails
            
            # Calculate position size based on risk
            position_size = self._calculate_position_size(portfolio)
            
            if position_size <= 0:
                return None
        except Exception as e:
            print(f"⚠️ Trader guardrail error: {e}")
            return None
        
        # Calculate stop loss and take profit
        sl_price, tp_price = self._calculate_sl_tp(
            current_price, direction
        )
        
        # Create trade
        trade = {
            'forecast_id': forecast.get('id'),
            'news_id': forecast.get('news_id'),
            'asset': forecast['asset'],
            'side': 'BUY' if direction == 'UP' else 'SELL',
            'size_usd': position_size,
            'entry_price': current_price,
            'entry_time': datetime.now().isoformat(),
            'stop_loss': sl_price,
            'take_profit': tp_price,
            'reason': f"Auto-trade: {forecast.get('reasoning', 'forecast-based')}",
            'confidence': confidence,
            'risk_level': forecast.get('risk_level', 'MEDIUM')
        }
        
        return trade
    
    def _check_hourly_limit(self) -> bool:
        """Check if hourly trade limit is not exceeded"""
        counter = self.db.get_trade_counter()
        
        if not counter:
            return True
        
        # Check if hour has reset
        hour_reset_time = datetime.fromisoformat(counter['hour_reset_time'])
        if datetime.now() - hour_reset_time > timedelta(hours=1):
            # Reset counter
            self.db.reset_trade_counter()
            return True
        
        # Check limit
        return counter['trades_this_hour'] < config.MAX_TRADES_PER_HOUR
    
    def _calculate_position_size(self, portfolio: Dict) -> float:
        """Calculate position size based on risk management"""
        if not portfolio:
            return 0.0
        
        current_equity = portfolio['current_equity']
        
        # Max risk per trade
        max_risk_amount = current_equity * config.MAX_RISK_PER_TRADE
        
        # Position size (simplified - using max risk)
        # In reality: position_size = max_risk / (entry - stop_loss)
        # Here we use a fixed percentage of equity
        position_size = current_equity * 0.05  # 5% of equity per trade
        
        # Cap at 10% of equity
        position_size = min(position_size, current_equity * 0.10)
        
        return round(position_size, 2)
    
    def _calculate_sl_tp(self, entry_price: float, direction: str) -> tuple:
        """Calculate stop loss and take profit prices"""
        if direction == 'UP':  # BUY
            sl_price = entry_price * (1 - config.DEFAULT_STOP_LOSS_PERCENT / 100)
            tp_price = entry_price * (1 + config.DEFAULT_TAKE_PROFIT_PERCENT / 100)
        else:  # SELL (short)
            sl_price = entry_price * (1 + config.DEFAULT_STOP_LOSS_PERCENT / 100)
            tp_price = entry_price * (1 - config.DEFAULT_TAKE_PROFIT_PERCENT / 100)
        
        return round(sl_price, 2), round(tp_price, 2)
    
    def check_open_trades(self, current_prices: Optional[Dict] = None) -> List[int]:
        """
        Check all open trades for exit conditions
        Returns list of closed trade IDs
        """
        closed_trade_ids = []
        open_trades = self.db.get_open_trades()

        # Allow callers to omit prices; fall back to latest DB prices.
        if current_prices is None:
            current_prices = {}
            try:
                assets = {t.get('asset') for t in open_trades if t.get('asset')}
                for asset in assets:
                    row = self.db.get_latest_price(asset)
                    if row:
                        current_prices[asset] = {
                            'price': row['price'],
                            'timestamp': row.get('timestamp'),
                        }
            except Exception:
                # If fallback fails, proceed with an empty dict (no closes).
                current_prices = {}
        
        for trade in open_trades:
            asset = trade['asset']
            current_price_data = current_prices.get(asset)

            # Accept either {price: ...} dicts or raw float prices
            if current_price_data is None:
                continue

            if isinstance(current_price_data, dict):
                if current_price_data.get('error'):
                    continue
                current_price = current_price_data.get('price')
            else:
                current_price = current_price_data

            if not current_price or current_price <= 0:
                continue
            
            should_close, reason = self._check_exit_conditions(trade, current_price)
            
            if should_close:
                pnl = self.db.close_trade(trade['id'], current_price, reason)
                closed_trade_ids.append(trade['id'])
                
                # Update portfolio equity
                portfolio = self.db.get_portfolio()
                new_equity = portfolio['current_equity'] + pnl
                new_daily_pnl = portfolio['daily_pnl'] + pnl
                
                self.db.update_portfolio_equity(new_equity, new_daily_pnl)
                
                # Check daily loss limit
                self._check_daily_loss_limit(portfolio, new_daily_pnl)
        
        return closed_trade_ids
    
    def _check_exit_conditions(self, trade: Dict, current_price: float) -> tuple:
        """Check if trade should be closed"""
        entry_price = trade['entry_price']
        stop_loss = trade['stop_loss']
        take_profit = trade['take_profit']
        side = trade['side']
        
        # Check stop loss
        if side == 'BUY':
            if current_price <= stop_loss:
                return True, "Stop loss hit"
            if current_price >= take_profit:
                return True, "Take profit hit"
        else:  # SELL
            if current_price >= stop_loss:
                return True, "Stop loss hit"
            if current_price <= take_profit:
                return True, "Take profit hit"
        
        # Check time-based exit (if enabled)
        if config.FORCE_EXIT_AT_HORIZON:
            forecast_id = trade.get('forecast_id')
            if forecast_id:
                forecast = self.db.get_forecast_by_id(int(forecast_id))
                due_at = (forecast or {}).get('due_at')
                if due_at:
                    try:
                        due_time = datetime.fromisoformat(due_at)
                        if datetime.now() >= due_time:
                            return True, "Time-based exit (forecast due_at reached)"
                    except Exception:
                        pass

            # Fallback: entry time + 4 hours
            try:
                entry_time = datetime.fromisoformat(trade['entry_time'])
                if datetime.now() - entry_time > timedelta(hours=4):
                    return True, "Time-based exit (fallback 4h)"
            except Exception:
                pass
        
        return False, ""
    
    def _check_daily_loss_limit(self, portfolio: Dict, daily_pnl: float):
        """Check if daily loss limit is hit"""
        if daily_pnl < 0:
            loss_percent = abs(daily_pnl) / portfolio['starting_equity'] * 100
            
            if loss_percent >= config.DAILY_MAX_LOSS_PERCENT:
                self.db.pause_trading()
                self.db.log('WARNING', 'AutoTrader', 
                          f'Daily loss limit hit: {loss_percent:.2f}%. Trading paused until reset.')
    
    def execute_trade(self, trade: Dict) -> int:
        """Execute trade and update counters"""
        trade_id = self.db.insert_trade(trade)
        
        # Increment hourly counter
        self.db.increment_trade_counter()
        
        # Log trade
        self.db.log('INFO', 'AutoTrader', 
                   f"Executed {trade['side']} trade on {trade['asset']} at {trade['entry_price']}")
        
        return trade_id


# Singleton
_auto_trader = None

def get_auto_trader() -> AutoTrader:
    """Get auto trader instance"""
    global _auto_trader
    if _auto_trader is None:
        _auto_trader = AutoTrader()
    return _auto_trader
