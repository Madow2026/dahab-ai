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
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_session ON training_trades(session_id, timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_positions_session ON training_positions(session_id)")
        
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


# Singleton
_training_db = None

def get_training_db() -> TrainingDatabase:
    """Get training database instance"""
    global _training_db
    if _training_db is None:
        _training_db = TrainingDatabase()
    return _training_db
