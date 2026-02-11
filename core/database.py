"""
Database Manager for Dahab AI
Handles SQLite operations for news, forecasts, and portfolio
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import os

import config

class DatabaseManager:
    def __init__(self, db_path: str = None):
        self.db_path = os.path.abspath(db_path or config.DATABASE_PATH)
        self.init_database()
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
        except Exception:
            pass
        return conn
    
    def init_database(self):
        """Initialize database schema"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # News table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                title_ar TEXT,
                content TEXT,
                content_ar TEXT,
                source TEXT,
                url TEXT,
                published_date TEXT,
                collected_date TEXT NOT NULL,
                news_type TEXT,
                affected_assets TEXT,
                impact_nature TEXT,
                impact_strength TEXT,
                is_analyzed BOOLEAN DEFAULT 0
            )
        """)
        
        # Forecasts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                news_id INTEGER,
                asset TEXT NOT NULL,
                forecast_time TEXT NOT NULL,
                expected_direction TEXT NOT NULL,
                confidence_level REAL NOT NULL,
                time_horizon_minutes INTEGER NOT NULL,
                risk_level TEXT NOT NULL,
                key_reasons TEXT,
                price_at_forecast REAL,
                evaluation_time TEXT,
                actual_direction TEXT,
                price_at_evaluation REAL,
                is_accurate BOOLEAN,
                price_change_percent REAL,
                FOREIGN KEY (news_id) REFERENCES news (id)
            )
        """)
        
        # Portfolio trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_id INTEGER,
                asset TEXT NOT NULL,
                trade_type TEXT NOT NULL,
                entry_price REAL NOT NULL,
                entry_time TEXT NOT NULL,
                position_size REAL NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                exit_price REAL,
                exit_time TEXT,
                profit_loss REAL,
                status TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (forecast_id) REFERENCES forecasts (id)
            )
        """)
        
        # Portfolio summary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL UNIQUE,
                total_equity REAL NOT NULL,
                total_trades INTEGER NOT NULL,
                winning_trades INTEGER NOT NULL,
                losing_trades INTEGER NOT NULL,
                total_profit_loss REAL NOT NULL,
                max_drawdown REAL
            )
        """)
        
        conn.commit()
        conn.close()
    
    # News operations
    def insert_news(self, news_data: Dict) -> int:
        """Insert news item and return ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO news (
                title, title_ar, content, content_ar, source, url, 
                published_date, collected_date, news_type, 
                affected_assets, impact_nature, impact_strength
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            news_data.get('title'),
            news_data.get('title_ar'),
            news_data.get('content'),
            news_data.get('content_ar'),
            news_data.get('source'),
            news_data.get('url'),
            news_data.get('published_date'),
            news_data.get('collected_date', datetime.now().isoformat()),
            news_data.get('news_type'),
            json.dumps(news_data.get('affected_assets', [])),
            news_data.get('impact_nature'),
            news_data.get('impact_strength')
        ))
        
        news_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return news_id
    
    def get_recent_news(self, limit: int = 50, asset_filter: Optional[str] = None) -> List[Dict]:
        """Get recent news items"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = "SELECT * FROM news"
        params = []
        
        if asset_filter:
            query += " WHERE affected_assets LIKE ?"
            params.append(f"%{asset_filter}%")
        
        query += " ORDER BY collected_date DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        columns = [description[0] for description in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        # Parse JSON fields
        for item in results:
            if item.get('affected_assets'):
                try:
                    item['affected_assets'] = json.loads(item['affected_assets'])
                except:
                    item['affected_assets'] = []
        
        conn.close()
        return results
    
    def mark_news_analyzed(self, news_id: int):
        """Mark news as analyzed"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE news SET is_analyzed = 1 WHERE id = ?", (news_id,))
        conn.commit()
        conn.close()
    
    # Forecast operations
    def insert_forecast(self, forecast_data: Dict) -> int:
        """Insert forecast and return ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO forecasts (
                news_id, asset, forecast_time, expected_direction, 
                confidence_level, time_horizon_minutes, risk_level, 
                key_reasons, price_at_forecast
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            forecast_data.get('news_id'),
            forecast_data.get('asset'),
            forecast_data.get('forecast_time', datetime.now().isoformat()),
            forecast_data.get('expected_direction'),
            forecast_data.get('confidence_level'),
            forecast_data.get('time_horizon_minutes'),
            forecast_data.get('risk_level'),
            forecast_data.get('key_reasons'),
            forecast_data.get('price_at_forecast')
        ))
        
        forecast_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return forecast_id
    
    def get_pending_forecasts(self) -> List[Dict]:
        """Get forecasts waiting for evaluation"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM forecasts 
            WHERE evaluation_time IS NULL 
            AND datetime(forecast_time, '+' || time_horizon_minutes || ' minutes') < datetime('now')
            ORDER BY forecast_time DESC
        """)
        
        columns = [description[0] for description in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def update_forecast_evaluation(self, forecast_id: int, evaluation_data: Dict):
        """Update forecast with actual outcome"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE forecasts SET
                evaluation_time = ?,
                actual_direction = ?,
                price_at_evaluation = ?,
                is_accurate = ?,
                price_change_percent = ?
            WHERE id = ?
        """, (
            evaluation_data.get('evaluation_time', datetime.now().isoformat()),
            evaluation_data.get('actual_direction'),
            evaluation_data.get('price_at_evaluation'),
            evaluation_data.get('is_accurate'),
            evaluation_data.get('price_change_percent'),
            forecast_id
        ))
        
        conn.commit()
        conn.close()
    
    def get_forecast_accuracy_stats(self, days: int = 7) -> Dict:
        """Get forecast accuracy statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_forecasts,
                SUM(CASE WHEN is_accurate = 1 THEN 1 ELSE 0 END) as accurate_forecasts,
                AVG(confidence_level) as avg_confidence,
                asset
            FROM forecasts
            WHERE evaluation_time IS NOT NULL
            AND datetime(forecast_time) > datetime('now', '-' || ? || ' days')
            GROUP BY asset
        """, (days,))
        
        results = cursor.fetchall()
        conn.close()
        
        stats = {}
        for row in results:
            asset = row[3]
            stats[asset] = {
                'total': row[0],
                'accurate': row[1],
                'accuracy_rate': (row[1] / row[0] * 100) if row[0] > 0 else 0,
                'avg_confidence': row[2]
            }
        
        return stats
    
    def get_all_evaluated_forecasts(self) -> List[Dict]:
        """Get all evaluated forecasts for performance tracking"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM forecasts 
            WHERE evaluation_time IS NOT NULL
            ORDER BY forecast_time DESC
        """)
        
        columns = [description[0] for description in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results
    
    # Portfolio operations
    def insert_trade(self, trade_data: Dict) -> int:
        """Insert portfolio trade"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO portfolio_trades (
                forecast_id, asset, trade_type, entry_price, entry_time,
                position_size, stop_loss, take_profit, status, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_data.get('forecast_id'),
            trade_data.get('asset'),
            trade_data.get('trade_type'),
            trade_data.get('entry_price'),
            trade_data.get('entry_time', datetime.now().isoformat()),
            trade_data.get('position_size'),
            trade_data.get('stop_loss'),
            trade_data.get('take_profit'),
            trade_data.get('status', 'OPEN'),
            trade_data.get('notes')
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return trade_id
    
    def close_trade(self, trade_id: int, exit_price: float, exit_time: str = None):
        """Close a trade and calculate P&L"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get trade details
        cursor.execute("SELECT * FROM portfolio_trades WHERE id = ?", (trade_id,))
        trade = cursor.fetchone()
        
        if not trade:
            conn.close()
            return
        
        entry_price = trade[4]
        position_size = trade[6]
        trade_type = trade[3]
        
        # Calculate P&L
        if trade_type == 'LONG':
            profit_loss = (exit_price - entry_price) / entry_price * position_size
        else:  # SHORT
            profit_loss = (entry_price - exit_price) / entry_price * position_size
        
        cursor.execute("""
            UPDATE portfolio_trades SET
                exit_price = ?,
                exit_time = ?,
                profit_loss = ?,
                status = 'CLOSED'
            WHERE id = ?
        """, (
            exit_price,
            exit_time or datetime.now().isoformat(),
            profit_loss,
            trade_id
        ))
        
        conn.commit()
        conn.close()
    
    def get_open_trades(self) -> List[Dict]:
        """Get all open trades"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM portfolio_trades WHERE status = 'OPEN' ORDER BY entry_time DESC")
        columns = [description[0] for description in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_all_trades(self) -> List[Dict]:
        """Get all trades"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM portfolio_trades ORDER BY entry_time DESC")
        columns = [description[0] for description in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_portfolio_performance(self) -> Dict:
        """Calculate portfolio performance metrics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(profit_loss) as total_pnl,
                AVG(profit_loss) as avg_pnl,
                MAX(profit_loss) as max_win,
                MIN(profit_loss) as max_loss
            FROM portfolio_trades
            WHERE status = 'CLOSED'
        """)
        
        result = cursor.fetchone()
        conn.close()
        
        if not result or result[0] == 0:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_pnl': 0,
                'max_win': 0,
                'max_loss': 0
            }
        
        return {
            'total_trades': result[0],
            'winning_trades': result[1] or 0,
            'losing_trades': result[2] or 0,
            'win_rate': ((result[1] or 0) / result[0] * 100) if result[0] > 0 else 0,
            'total_pnl': result[3] or 0,
            'avg_pnl': result[4] or 0,
            'max_win': result[5] or 0,
            'max_loss': result[6] or 0
        }

# Singleton instance
_db_instance = None

def get_db() -> DatabaseManager:
    """Get database manager instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
