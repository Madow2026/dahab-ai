"""
Training Simulator Database Manager
Completely isolated from main app - for educational purposes only
"""

import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import os


class TrainingDatabase:
    """Isolated database for training simulator - NO interaction with main DB"""
    
    def __init__(self, db_path: str = "training_simulator.db"):
        self.db_path = db_path
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialize training tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Training Sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_name TEXT NOT NULL UNIQUE,
                initial_capital REAL NOT NULL,
                current_cash REAL NOT NULL,
                created_at TEXT NOT NULL,
                last_trade_at TEXT,
                is_active INTEGER DEFAULT 1,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_commission_paid REAL DEFAULT 0,
                settings TEXT DEFAULT '{}'
            )
        """)
        
        # Training Trades (complete history)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                asset TEXT NOT NULL,
                action TEXT NOT NULL,
                quantity REAL NOT NULL,
                price REAL NOT NULL,
                commission REAL NOT NULL,
                pnl_realized REAL DEFAULT 0,
                balance_after REAL NOT NULL,
                blocked_reason TEXT,
                notes TEXT,
                FOREIGN KEY (session_id) REFERENCES training_sessions (id)
            )
        """)
        
        # Current Positions (aggregated)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_positions (
                session_id INTEGER NOT NULL,
                asset TEXT NOT NULL,
                quantity REAL NOT NULL,
                avg_entry_price REAL NOT NULL,
                total_cost REAL NOT NULL,
                last_updated TEXT NOT NULL,
                PRIMARY KEY (session_id, asset),
                FOREIGN KEY (session_id) REFERENCES training_sessions (id)
            )
        """)
        
        # AI Recommendations (for educational training)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                asset TEXT NOT NULL,
                action TEXT NOT NULL,
                current_price REAL NOT NULL,
                target_price REAL,
                stop_loss REAL,
                time_horizon_minutes INTEGER,
                confidence REAL NOT NULL,
                reasoning TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                expires_at TEXT,
                evaluated_at TEXT,
                actual_price REAL,
                was_accurate INTEGER,
                accuracy_score REAL,
                FOREIGN KEY (session_id) REFERENCES training_sessions (id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_session ON training_trades(session_id, timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_session ON training_positions(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_recommendations_active ON training_recommendations(session_id, status, expires_at)")
        
        conn.commit()
        conn.close()
    
    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================
    
    def create_session(self, session_name: str, initial_capital: float, 
                      settings: Dict = None) -> int:
        """Create new training session"""
        if settings is None:
            settings = {
                'commission_rate': 0.001,  # 0.1%
                'min_trade_gap_minutes': 5,
                'allow_short_selling': False,
                'max_position_size_percent': 50,  # % of capital
                'cooldown_after_loss_minutes': 0
            }
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO training_sessions 
                (session_name, initial_capital, current_cash, created_at, settings)
                VALUES (?, ?, ?, ?, ?)
            """, (
                session_name,
                initial_capital,
                initial_capital,
                datetime.now().isoformat(),
                json.dumps(settings)
            ))
            
            session_id = cursor.lastrowid
            conn.commit()
            return session_id
            
        except sqlite3.IntegrityError:
            raise ValueError(f"Session '{session_name}' already exists")
        finally:
            conn.close()
    
    def get_all_sessions(self) -> List[Dict]:
        """Get all training sessions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM training_sessions 
            ORDER BY created_at DESC
        """)
        
        sessions = []
        for row in cursor.fetchall():
            session = dict(row)
            session['settings'] = json.loads(session.get('settings', '{}'))
            sessions.append(session)
        
        conn.close()
        return sessions
    
    def get_session(self, session_id: int) -> Optional[Dict]:
        """Get specific session"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM training_sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            session = dict(row)
            session['settings'] = json.loads(session.get('settings', '{}'))
            return session
        return None
    
    def update_session_settings(self, session_id: int, settings: Dict):
        """Update session settings"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE training_sessions 
            SET settings = ?
            WHERE id = ?
        """, (json.dumps(settings), session_id))
        
        conn.commit()
        conn.close()
    
    def delete_session(self, session_id: int):
        """Delete session and all its data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM training_trades WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM training_positions WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM training_sessions WHERE id = ?", (session_id,))
        
        conn.commit()
        conn.close()
    
    # ========================================================================
    # TRADING OPERATIONS
    # ========================================================================
    
    def can_execute_trade(self, session_id: int, asset: str, action: str, 
                         quantity: float, price: float) -> Tuple[bool, str]:
        """Check if trade can be executed according to rules"""
        session = self.get_session(session_id)
        if not session:
            return False, "Session not found"
        
        settings = session['settings']
        current_cash = session['current_cash']
        
        # Check timing rules
        if session['last_trade_at']:
            last_trade = datetime.fromisoformat(session['last_trade_at'])
            min_gap = timedelta(minutes=settings.get('min_trade_gap_minutes', 5))
            if datetime.now() - last_trade < min_gap:
                return False, f"⏰ Wait {settings['min_trade_gap_minutes']} minutes between trades (Trading discipline)"
        
        # Calculate commission
        commission_rate = settings.get('commission_rate', 0.001)
        trade_value = quantity * price
        commission = trade_value * commission_rate
        
        if action.upper() == 'BUY':
            total_cost = trade_value + commission
            
            # Check sufficient funds
            if total_cost > current_cash:
                return False, f"❌ Insufficient funds (need ${total_cost:,.2f}, have ${current_cash:,.2f})"
            
            # Check position size limit
            max_position_pct = settings.get('max_position_size_percent', 50)
            if (total_cost / session['initial_capital']) > (max_position_pct / 100):
                return False, f"⚠️ Position too large (max {max_position_pct}% of initial capital)"
        
        elif action.upper() == 'SELL':
            # Check if position exists
            position = self.get_position(session_id, asset)
            if not position or position['quantity'] < quantity:
                available = position['quantity'] if position else 0
                return False, f"❌ Insufficient {asset} (trying to sell {quantity}, have {available})"
            
            # Check cooldown after loss
            cooldown_minutes = settings.get('cooldown_after_loss_minutes', 0)
            if cooldown_minutes > 0:
                last_loss = self.get_last_losing_trade(session_id)
                if last_loss:
                    loss_time = datetime.fromisoformat(last_loss['timestamp'])
                    cooldown = timedelta(minutes=cooldown_minutes)
                    if datetime.now() - loss_time < cooldown:
                        return False, f"🧊 Cooldown active after loss (wait {cooldown_minutes} min to prevent revenge trading)"
        
        return True, "Trade allowed"
    
    def execute_trade(self, session_id: int, asset: str, action: str, 
                     quantity: float, price: float, notes: str = "") -> Dict:
        """Execute trade and update positions"""
        # Check if trade is allowed
        can_trade, reason = self.can_execute_trade(session_id, asset, action, quantity, price)
        
        if not can_trade:
            # Log blocked trade
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO training_trades 
                (session_id, timestamp, asset, action, quantity, price, 
                 commission, balance_after, blocked_reason, notes)
                VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
            """, (session_id, datetime.now().isoformat(), asset, action, 
                  quantity, price, reason, notes))
            conn.commit()
            conn.close()
            
            return {
                'success': False,
                'reason': reason,
                'blocked': True
            }
        
        session = self.get_session(session_id)
        settings = session['settings']
        commission_rate = settings.get('commission_rate', 0.001)
        
        trade_value = quantity * price
        commission = trade_value * commission_rate
        pnl_realized = 0
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if action.upper() == 'BUY':
            # Decrease cash
            total_cost = trade_value + commission
            new_cash = session['current_cash'] - total_cost
            
            # Update or create position
            position = self.get_position(session_id, asset)
            if position:
                # Add to existing position (weighted average)
                new_quantity = position['quantity'] + quantity
                new_total_cost = position['total_cost'] + trade_value
                new_avg_price = new_total_cost / new_quantity
                
                cursor.execute("""
                    UPDATE training_positions
                    SET quantity = ?, avg_entry_price = ?, total_cost = ?, last_updated = ?
                    WHERE session_id = ? AND asset = ?
                """, (new_quantity, new_avg_price, new_total_cost, 
                      datetime.now().isoformat(), session_id, asset))
            else:
                # Create new position
                cursor.execute("""
                    INSERT INTO training_positions
                    (session_id, asset, quantity, avg_entry_price, total_cost, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, asset, quantity, price, trade_value, 
                      datetime.now().isoformat()))
        
        elif action.upper() == 'SELL':
            # Increase cash (minus commission)
            proceeds = trade_value - commission
            new_cash = session['current_cash'] + proceeds
            
            # Calculate realized P&L
            position = self.get_position(session_id, asset)
            cost_basis = position['avg_entry_price'] * quantity
            pnl_realized = trade_value - cost_basis
            
            # Update position
            new_quantity = position['quantity'] - quantity
            if new_quantity > 0.0001:  # Keep position
                new_total_cost = position['total_cost'] - cost_basis
                cursor.execute("""
                    UPDATE training_positions
                    SET quantity = ?, total_cost = ?, last_updated = ?
                    WHERE session_id = ? AND asset = ?
                """, (new_quantity, new_total_cost, datetime.now().isoformat(), 
                      session_id, asset))
            else:  # Close position
                cursor.execute("""
                    DELETE FROM training_positions
                    WHERE session_id = ? AND asset = ?
                """, (session_id, asset))
        
        # Record trade
        cursor.execute("""
            INSERT INTO training_trades
            (session_id, timestamp, asset, action, quantity, price, 
             commission, pnl_realized, balance_after, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (session_id, datetime.now().isoformat(), asset, action, 
              quantity, price, commission, pnl_realized, new_cash, notes))
        
        # Update session
        cursor.execute("""
            UPDATE training_sessions
            SET current_cash = ?,
                last_trade_at = ?,
                total_trades = total_trades + 1,
                winning_trades = winning_trades + ?,
                losing_trades = losing_trades + ?,
                total_commission_paid = total_commission_paid + ?
            WHERE id = ?
        """, (new_cash, datetime.now().isoformat(),
              1 if pnl_realized > 0 else 0,
              1 if pnl_realized < 0 else 0,
              commission, session_id))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'commission': commission,
            'pnl_realized': pnl_realized,
            'new_balance': new_cash,
            'action': action
        }
    
    # ========================================================================
    # PORTFOLIO QUERIES
    # ========================================================================
    
    def get_position(self, session_id: int, asset: str) -> Optional[Dict]:
        """Get current position for asset"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM training_positions
            WHERE session_id = ? AND asset = ?
        """, (session_id, asset))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_all_positions(self, session_id: int) -> List[Dict]:
        """Get all open positions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM training_positions
            WHERE session_id = ?
            ORDER BY asset
        """, (session_id,))
        
        positions = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return positions
    
    def calculate_unrealized_pnl(self, session_id: int, current_prices: Dict[str, float]) -> float:
        """Calculate total unrealized P&L"""
        positions = self.get_all_positions(session_id)
        total_unrealized = 0
        
        for pos in positions:
            current_price = current_prices.get(pos['asset'], pos['avg_entry_price'])
            market_value = pos['quantity'] * current_price
            unrealized = market_value - pos['total_cost']
            total_unrealized += unrealized
        
        return total_unrealized
    
    def get_trade_history(self, session_id: int, limit: int = 50) -> List[Dict]:
        """Get trade history"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM training_trades
            WHERE session_id = ? AND blocked_reason IS NULL
            ORDER BY timestamp DESC
            LIMIT ?
        """, (session_id, limit))
        
        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return trades
    
    def get_last_losing_trade(self, session_id: int) -> Optional[Dict]:
        """Get most recent losing trade"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM training_trades
            WHERE session_id = ? 
              AND action = 'SELL'
              AND pnl_realized < 0
              AND blocked_reason IS NULL
            ORDER BY timestamp DESC
            LIMIT 1
        """, (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def get_session_statistics(self, session_id: int, current_prices: Dict[str, float]) -> Dict:
        """Get comprehensive session statistics"""
        session = self.get_session(session_id)
        if not session:
            return {}
        
        positions = self.get_all_positions(session_id)
        
        # Calculate portfolio value
        positions_value = sum(
            pos['quantity'] * current_prices.get(pos['asset'], pos['avg_entry_price'])
            for pos in positions
        )
        
        total_equity = session['current_cash'] + positions_value
        total_pnl = total_equity - session['initial_capital']
        total_pnl_pct = (total_pnl / session['initial_capital']) * 100
        
        unrealized_pnl = self.calculate_unrealized_pnl(session_id, current_prices)
        
        # Calculate realized P&L from trades
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SUM(pnl_realized) FROM training_trades
            WHERE session_id = ? AND action = 'SELL' AND blocked_reason IS NULL
        """, (session_id,))
        realized_pnl = cursor.fetchone()[0] or 0
        conn.close()
        
        return {
            'initial_capital': session['initial_capital'],
            'current_cash': session['current_cash'],
            'positions_value': positions_value,
            'total_equity': total_equity,
            'total_pnl': total_pnl,
            'total_pnl_pct': total_pnl_pct,
            'realized_pnl': realized_pnl,
            'unrealized_pnl': unrealized_pnl,
            'total_trades': session['total_trades'],
            'winning_trades': session['winning_trades'],
            'losing_trades': session['losing_trades'],
            'win_rate': (session['winning_trades'] / session['total_trades'] * 100) if session['total_trades'] > 0 else 0,
            'total_commission': session['total_commission_paid'],
            'num_positions': len(positions)
        }
    
    # ========================================================================
    # AI RECOMMENDATIONS FOR TRAINING
    # ========================================================================
    
    def create_recommendation(self, session_id: int, asset: str, action: str,
                            current_price: float, target_price: float,
                            stop_loss: float, time_horizon_minutes: int,
                            confidence: float, reasoning: str) -> int:
        """Create new AI recommendation"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        created_at = datetime.now()
        expires_at = created_at + timedelta(minutes=time_horizon_minutes)
        
        cursor.execute("""
            INSERT INTO training_recommendations
            (session_id, created_at, asset, action, current_price, target_price,
             stop_loss, time_horizon_minutes, confidence, reasoning, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, created_at.isoformat(), asset, action, current_price,
            target_price, stop_loss, time_horizon_minutes, confidence, reasoning,
            expires_at.isoformat()
        ))
        
        rec_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return rec_id
    
    def get_active_recommendations(self, session_id: int) -> List[Dict]:
        """Get active recommendations for session"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM training_recommendations
            WHERE session_id = ? AND status = 'active'
            AND datetime(expires_at) > datetime('now')
            ORDER BY created_at DESC
        """, (session_id,))
        
        recommendations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return recommendations
    
    def get_evaluated_recommendations(self, session_id: int, limit: int = 10) -> List[Dict]:
        """Get recently evaluated recommendations with results"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM training_recommendations
            WHERE session_id = ? AND status = 'evaluated'
            ORDER BY evaluated_at DESC
            LIMIT ?
        """, (session_id, limit))
        
        recommendations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return recommendations
    
    def evaluate_recommendation(self, rec_id: int, actual_price: float) -> Dict:
        """Evaluate recommendation accuracy after time horizon - SMARTER scoring"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get recommendation
        cursor.execute("SELECT * FROM training_recommendations WHERE id = ?", (rec_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {'was_accurate': False, 'accuracy_score': 0}
        
        rec = dict(row)
        
        target_price = rec['target_price']
        current_price = rec['current_price']
        action = rec['action']
        
        # Calculate accuracy with SMARTER scoring
        if action == 'BUY':
            # BUY = expected price UP. Any upward move is partially right
            expected_move = target_price - current_price
            actual_move = actual_price - current_price
            
            if actual_move > 0:  # Price went up (correct direction!)
                was_accurate = True
                # Score based on how much of target was achieved
                if expected_move > 0:
                    accuracy_score = min(100, (actual_move / expected_move) * 100)
                else:
                    accuracy_score = 50
            else:  # Price went down (wrong direction)
                was_accurate = False
                # Partial score if move was very small
                move_pct = abs(actual_move / current_price) * 100
                if move_pct < 0.1:  # Less than 0.1% move = basically neutral
                    accuracy_score = 30
                    was_accurate = True  # Too small to call wrong
                else:
                    accuracy_score = max(0, 20 - move_pct * 10)
        else:  # SELL
            # SELL = expected price DOWN. Any downward move is partially right
            expected_move = current_price - target_price
            actual_move = current_price - actual_price
            
            if actual_move > 0:  # Price went down (correct direction!)
                was_accurate = True
                if expected_move > 0:
                    accuracy_score = min(100, (actual_move / expected_move) * 100)
                else:
                    accuracy_score = 50
            else:  # Price went up (wrong direction)
                was_accurate = False
                move_pct = abs(actual_move / current_price) * 100
                if move_pct < 0.1:  # Basically neutral
                    accuracy_score = 30
                    was_accurate = True
                else:
                    accuracy_score = max(0, 20 - move_pct * 10)
        
        # Update recommendation
        cursor.execute("""
            UPDATE training_recommendations
            SET status = 'evaluated',
                evaluated_at = ?,
                actual_price = ?,
                was_accurate = ?,
                accuracy_score = ?
            WHERE id = ?
        """, (
            datetime.now().isoformat(),
            actual_price,
            1 if was_accurate else 0,
            max(0, accuracy_score),
            rec_id
        ))
        
        conn.commit()
        conn.close()
        
        return {
            'was_accurate': was_accurate,
            'accuracy_score': accuracy_score
        }
    
    def get_recommendation_stats(self, session_id: int) -> Dict:
        """Get recommendation accuracy statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN was_accurate = 1 THEN 1 ELSE 0 END) as accurate,
                AVG(accuracy_score) as avg_score,
                AVG(confidence) as avg_confidence
            FROM training_recommendations
            WHERE session_id = ? AND status = 'evaluated'
        """, (session_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row and row['total'] > 0:
            return {
                'total_evaluated': row['total'],
                'accurate_count': row['accurate'] or 0,
                'accuracy_rate': (row['accurate'] or 0) / row['total'] * 100,
                'avg_accuracy_score': row['avg_score'] or 0,
                'avg_confidence': row['avg_confidence'] or 0
            }
        return {
            'total_evaluated': 0,
            'accurate_count': 0,
            'accuracy_rate': 0,
            'avg_accuracy_score': 0,
            'avg_confidence': 0
        }
    
    def learn_from_results(self, session_id: int) -> Dict:
        """Analyze past recommendations to improve future predictions"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get statistics by asset and action
        cursor.execute("""
            SELECT 
                asset,
                action,
                COUNT(*) as total,
                AVG(CASE WHEN was_accurate = 1 THEN 1.0 ELSE 0.0 END) as success_rate,
                AVG(accuracy_score) as avg_score,
                AVG(confidence) as avg_confidence,
                AVG(CASE WHEN was_accurate = 1 THEN 1.0 ELSE -1.0 END) as direction_bias
            FROM training_recommendations
            WHERE session_id = ? AND status = 'evaluated'
            GROUP BY asset, action
        """, (session_id,))
        
        learning_data = {}
        for row in cursor.fetchall():
            key = f"{row['asset']}_{row['action']}"
            learning_data[key] = {
                'asset': row['asset'],
                'action': row['action'],
                'total': row['total'],
                'success_rate': row['success_rate'] * 100,
                'avg_score': row['avg_score'] or 0,
                'avg_confidence': row['avg_confidence'] or 0,
                'direction_bias': row['direction_bias'] or 0
            }
        
        # Also get overall stats to know what fails
        cursor.execute("""
            SELECT 
                action,
                COUNT(*) as total,
                AVG(CASE WHEN was_accurate = 1 THEN 1.0 ELSE 0.0 END) as success_rate
            FROM training_recommendations
            WHERE session_id = ? AND status = 'evaluated'
            GROUP BY action
        """, (session_id,))
        
        for row in cursor.fetchall():
            learning_data[f'_overall_{row["action"]}'] = {
                'total': row['total'],
                'success_rate': row['success_rate'] * 100
            }
        
        conn.close()
        return learning_data
    
    def _get_learned_direction(self, learning_data: Dict, asset: str) -> Optional[str]:
        """Determine best direction to recommend based on past learning"""
        buy_key = f"{asset}_BUY"
        sell_key = f"{asset}_SELL"
        
        buy_rate = learning_data.get(buy_key, {}).get('success_rate', 50)
        sell_rate = learning_data.get(sell_key, {}).get('success_rate', 50)
        buy_count = learning_data.get(buy_key, {}).get('total', 0)
        sell_count = learning_data.get(sell_key, {}).get('total', 0)
        
        # If we have enough data and one direction clearly fails, avoid it
        if buy_count >= 3 and buy_rate < 20:
            return 'SELL'  # BUY keeps failing, try SELL
        if sell_count >= 3 and sell_rate < 20:
            return 'BUY'  # SELL keeps failing, try BUY
        
        # If one direction clearly succeeds, prefer it
        if buy_count >= 3 and buy_rate > 70:
            return 'BUY'
        if sell_count >= 3 and sell_rate > 70:
            return 'SELL'
        
        return None  # No clear preference yet
    
    def generate_ai_recommendations(self, session_id: int, current_prices: Dict[str, float],
                                   price_history: Dict[str, List[float]], max_recommendations: int = 5) -> List[int]:
        """
        Smart AI recommendations with real learning from past results.
        Analyzes actual price movements and adjusts strategy based on accuracy.
        """
        import math
        recommendations = []
        
        # Learn from past results
        learning_data = self.learn_from_results(session_id)
        
        # Check overall accuracy to adjust strategy
        overall_buy_rate = learning_data.get('_overall_BUY', {}).get('success_rate', 50)
        overall_sell_rate = learning_data.get('_overall_SELL', {}).get('success_rate', 50)
        overall_buy_count = learning_data.get('_overall_BUY', {}).get('total', 0)
        overall_sell_count = learning_data.get('_overall_SELL', {}).get('total', 0)
        
        # Strategy: if all SELL failed, switch to mostly BUY and vice versa
        prefer_buy = False
        prefer_sell = False
        if overall_sell_count >= 3 and overall_sell_rate < 25:
            prefer_buy = True  # SELL keeps failing, lean towards BUY
        if overall_buy_count >= 3 and overall_buy_rate < 25:
            prefer_sell = True  # BUY keeps failing, lean towards SELL
        
        for asset, price in current_prices.items():
            if len(recommendations) >= max_recommendations:
                break
            
            history = price_history.get(asset, [])
            if len(history) < 3:
                continue
            
            # Analyze REAL price movement
            # Short-term trend (last 5 prices)
            short_term = history[-5:] if len(history) >= 5 else history
            short_avg = sum(short_term) / len(short_term)
            short_momentum = (price - short_avg) / short_avg * 100
            
            # Medium-term trend (last 15 prices)
            mid_term = history[-15:] if len(history) >= 15 else history
            mid_avg = sum(mid_term) / len(mid_term)
            mid_momentum = (price - mid_avg) / mid_avg * 100
            
            # Price change rate (acceleration)
            if len(history) >= 3:
                recent_change = (history[-1] - history[-2]) / history[-2] * 100
                prev_change = (history[-2] - history[-3]) / history[-3] * 100
                acceleration = recent_change - prev_change
            else:
                recent_change = 0
                acceleration = 0
            
            # Check if learned direction is available
            learned_dir = self._get_learned_direction(learning_data, asset)
            
            # --- SMART DECISION ENGINE ---
            action = None
            confidence = 50
            reasoning = ""
            target_pct = 0.005  # Default 0.5% target
            time_horizon = 30  # Default 30 min
            
            # Strategy 1: Follow the actual trend (momentum)
            if short_momentum > 0.1:
                # Price is rising
                if prefer_sell and not learned_dir:  # Override only if no asset-specific learning
                    pass  # Skip BUY if overall BUY fails
                else:
                    action = 'BUY'
                    target_pct = min(0.015, abs(short_momentum) * 0.005)
                    confidence = min(80, 55 + abs(short_momentum) * 3)
                    reasoning = f"📈 السعر في ارتفاع ({short_momentum:+.2f}%). الاتجاه يدعم الشراء."
                    if acceleration > 0:
                        confidence += 5
                        reasoning += f" تسارع إيجابي في الحركة."
            
            elif short_momentum < -0.1:
                # Price is falling
                if prefer_buy and not learned_dir:  # Override only if no asset-specific learning
                    pass  # Skip SELL if overall SELL fails
                else:
                    action = 'SELL'
                    target_pct = min(0.015, abs(short_momentum) * 0.005)
                    confidence = min(80, 55 + abs(short_momentum) * 3)
                    reasoning = f"📉 السعر في انخفاض ({short_momentum:+.2f}%). الاتجاه يدعم البيع."
                    if acceleration < 0:
                        confidence += 5
                        reasoning += f" تسارع في الانخفاض."
            
            else:
                # Price is stable - use mean reversion
                if mid_momentum > 0.2:
                    # Was going up, now stable - might continue or reverse
                    action = 'BUY' if not prefer_sell else 'SELL'
                    target_pct = 0.005
                    confidence = 55
                    reasoning = f"📊 استقرار بعد صعود. توقع استئناف الاتجاه الصعودي."
                elif mid_momentum < -0.2:
                    action = 'SELL' if not prefer_buy else 'BUY'
                    target_pct = 0.005
                    confidence = 55
                    reasoning = f"📊 استقرار بعد هبوط. توقع استئناف الاتجاه الهبوطي."
                else:
                    # Truly flat - use time-based alternation for variety
                    minute = datetime.now().minute
                    if minute % 2 == 0:
                        action = 'BUY'
                        reasoning = f"🔄 سوق هادئ. توقع حركة صعودية بسيطة."
                    else:
                        action = 'SELL'
                        reasoning = f"🔄 سوق هادئ. توقع حركة هبوطية بسيطة."
                    target_pct = 0.003
                    confidence = 50
            
            # Override with learned direction if we have strong data
            if learned_dir and action != learned_dir:
                asset_key = f"{asset}_{learned_dir}"
                learned_rate = learning_data.get(asset_key, {}).get('success_rate', 0)
                if learned_rate > 60:  # Only override if learned rate is good
                    action = learned_dir
                    confidence = min(85, confidence + 10)
                    reasoning += f" [🧠 تعلم: {learned_dir} أدق لـ {asset} ({learned_rate:.0f}%)]"
            
            if action is None:
                continue
            
            # Apply learning adjustments to confidence
            learning_key = f"{asset}_{action}"
            if learning_key in learning_data:
                past = learning_data[learning_key]
                if past['total'] >= 2:
                    # Blend base confidence with learned accuracy
                    weight = min(0.5, past['total'] * 0.1)  # More data = more weight (max 50%)
                    confidence = confidence * (1 - weight) + past['success_rate'] * weight
                    reasoning += f" [دقة سابقة: {past['success_rate']:.0f}% من {past['total']} توصية]"
            
            # Calculate target and stop loss
            if action == 'BUY':
                target_price = price * (1 + target_pct)
                stop_loss = price * (1 - target_pct * 0.5)
            else:
                target_price = price * (1 - target_pct)
                stop_loss = price * (1 + target_pct * 0.5)
            
            # Adjust time horizon based on confidence
            if confidence >= 70:
                time_horizon = 45  # Higher confidence, longer horizon
            elif confidence >= 60:
                time_horizon = 30
            else:
                time_horizon = 20  # Lower confidence, shorter horizon
            
            rec_id = self.create_recommendation(
                session_id, asset, action, price, target_price, stop_loss,
                time_horizon_minutes=time_horizon,
                confidence=max(40, min(90, confidence)),
                reasoning=reasoning
            )
            recommendations.append(rec_id)
        
        return recommendations
    
    def auto_evaluate_expired_recommendations(self, session_id: int, current_prices: Dict[str, float]) -> int:
        """Automatically evaluate expired recommendations"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, asset FROM training_recommendations
            WHERE session_id = ? AND status = 'active'
            AND datetime(expires_at) <= datetime('now')
        """, (session_id,))
        
        expired = cursor.fetchall()
        conn.close()
        
        evaluated_count = 0
        for row in expired:
            rec_id = row['id']
            asset = row['asset']
            if asset in current_prices:
                self.evaluate_recommendation(rec_id, current_prices[asset])
                evaluated_count += 1
        
        return evaluated_count


# Singleton
_training_db = None

def get_training_db() -> TrainingDatabase:
    """Get training database instance"""
    global _training_db
    if _training_db is None:
        _training_db = TrainingDatabase()
    return _training_db
