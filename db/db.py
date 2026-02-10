"""
Enhanced Database Manager for Automated Dahab AI
"""

import sqlite3
import json
import shutil
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
import config
import os


_SCHEMA_SUMMARY_LOGGED = False
_BACKUP_DONE = False

class Database:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DATABASE_PATH
        self._auto_backup()
        self.init_database()
        self._run_schema_validation()

    def _auto_backup(self):
        """Create a daily backup of the database to prevent data loss."""
        global _BACKUP_DONE
        if _BACKUP_DONE:
            return
        _BACKUP_DONE = True

        try:
            if not os.path.exists(self.db_path):
                return
            db_size = os.path.getsize(self.db_path)
            if db_size < 50000:  # Skip backup for nearly-empty DBs (< 50KB)
                return

            backup_dir = os.path.join(os.path.dirname(os.path.abspath(self.db_path)), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            today = datetime.now().strftime("%Y-%m-%d")
            backup_path = os.path.join(backup_dir, f"dahab_ai_{today}.db")

            if not os.path.exists(backup_path):
                shutil.copy2(self.db_path, backup_path)
                print(f"💾 Daily backup created: {backup_path}")

            # Keep only last 7 backups
            backups = sorted([
                f for f in os.listdir(backup_dir)
                if f.startswith("dahab_ai_") and f.endswith(".db")
            ])
            while len(backups) > 7:
                old = backups.pop(0)
                try:
                    os.remove(os.path.join(backup_dir, old))
                except Exception:
                    pass
        except Exception as e:
            print(f"Warning: Auto-backup failed: {e}")
    
    def _run_schema_validation(self):
        """Run schema validation and migration on startup"""
        try:
            from core.migrations import migrate_database
            if os.path.exists(self.db_path):
                migrate_database(self.db_path)

            # Log a short schema summary once per process (helps diagnose production DB state)
            self._log_schema_summary_once()
        except Exception as e:
            try:
                self.log('WARNING', 'Database', f'Schema migration skipped: {e}')
            except Exception:
                print(f"Warning: Schema validation skipped: {e}")

    def _log_schema_summary_once(self) -> None:
        global _SCHEMA_SUMMARY_LOGGED
        if _SCHEMA_SUMMARY_LOGGED:
            return

        try:
            conn = self.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [r[0] for r in cur.fetchall()]

            def cols(table: str) -> List[str]:
                cur.execute(f"PRAGMA table_info({table})")
                return [row[1] for row in cur.fetchall()]

            summary_parts = [
                f"tables={len(tables)}",
                f"has_news={'news' in tables}",
                f"has_prices={'prices' in tables}",
                f"has_forecasts={'forecasts' in tables}",
                f"has_paper_trades={'paper_trades' in tables}",
            ]

            if 'news' in tables:
                news_cols = cols('news')
                summary_parts.append(f"news.cols={','.join(news_cols[:8])}{'...' if len(news_cols)>8 else ''}")
                summary_parts.append(f"news.affected_assets_col={'affected_assets' in news_cols}")

            if 'forecasts' in tables:
                fcols = cols('forecasts')
                summary_parts.append(f"forecasts.cols={','.join(fcols[:10])}{'...' if len(fcols)>10 else ''}")
                summary_parts.append(f"forecasts.has_evaluation_time={'evaluation_time' in fcols}")
                summary_parts.append(f"forecasts.has_evaluated_at={'evaluated_at' in fcols}")

            if 'paper_trades' in tables:
                tcols = cols('paper_trades')
                summary_parts.append(f"paper_trades.cols={','.join(tcols[:10])}{'...' if len(tcols)>10 else ''}")

            conn.close()

            # Note: legacy core/database.py exists but UI/worker should use this module.
            self.log('INFO', 'Database', "Schema summary: " + " | ".join(summary_parts))
            _SCHEMA_SUMMARY_LOGGED = True
        except Exception:
            # Avoid breaking startup; summary is diagnostic only.
            return
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn

    @staticmethod
    def _utc_now_iso() -> str:
        """UTC ISO timestamp (seconds precision) for consistent sorting/comparisons."""
        try:
            return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        except Exception:
            return datetime.now().replace(microsecond=0).isoformat()
    
    def init_database(self):
        """Initialize all tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # News table with enhanced fields
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                url TEXT UNIQUE,
                url_hash TEXT,
                title_en TEXT NOT NULL,
                body_en TEXT,
                title_ar TEXT,
                body_ar TEXT,
                published_at TEXT,
                fetched_at TEXT NOT NULL,
                category TEXT,
                sentiment TEXT,
                impact_level TEXT,
                confidence REAL,
                affected_assets TEXT,
                processed INTEGER DEFAULT 0,
                source_reliability REAL DEFAULT 0.8
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_processed ON news(processed)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_url_hash ON news(url_hash)")
        
        # Prices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                asset TEXT NOT NULL,
                price REAL NOT NULL,
                timestamp TEXT NOT NULL,
                source TEXT DEFAULT 'yahoo_finance'
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_prices_asset_time ON prices(asset, timestamp DESC)")
        
        # Forecasts table with enhanced fields
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS forecasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                news_id INTEGER,
                asset TEXT NOT NULL,
                direction TEXT NOT NULL,
                confidence REAL NOT NULL,
                risk_level TEXT NOT NULL,
                horizon_minutes INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                due_at TEXT NOT NULL,
                reasoning TEXT,
                scenario_base TEXT,
                scenario_alt TEXT,
                price_at_forecast REAL,
                status TEXT DEFAULT 'active',
                evaluation_result TEXT,
                actual_direction TEXT,
                price_at_evaluation REAL,
                actual_price REAL,
                actual_time TEXT,
                direction_correct INTEGER,
                abs_error REAL,
                pct_error REAL,
                evaluation_quality TEXT,
                actual_return REAL,
                evaluated_at TEXT,
                FOREIGN KEY (news_id) REFERENCES news (id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_forecasts_status ON forecasts(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_forecasts_due ON forecasts(due_at)")
        
        # Paper portfolio summary (single row)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_portfolio (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                starting_equity REAL NOT NULL,
                current_equity REAL NOT NULL,
                updated_at TEXT NOT NULL,
                daily_pnl REAL DEFAULT 0,
                daily_reset_date TEXT,
                is_trading_paused INTEGER DEFAULT 0
            )
        """)
        
        # Initialize portfolio if not exists
        cursor.execute("""
            INSERT OR IGNORE INTO paper_portfolio (id, starting_equity, current_equity, updated_at, daily_reset_date)
            VALUES (1, ?, ?, ?, ?)
        """, (config.INITIAL_EQUITY, config.INITIAL_EQUITY, datetime.now().isoformat(), datetime.now().date().isoformat()))
        
        # Paper trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_id INTEGER,
                news_id INTEGER,
                asset TEXT NOT NULL,
                side TEXT NOT NULL,
                size_usd REAL NOT NULL,
                entry_price REAL NOT NULL,
                entry_time TEXT NOT NULL,
                stop_loss REAL,
                take_profit REAL,
                exit_price REAL,
                exit_time TEXT,
                status TEXT DEFAULT 'open',
                pnl REAL,
                pnl_pct REAL,
                reason TEXT,
                confidence REAL,
                risk_level TEXT,
                FOREIGN KEY (forecast_id) REFERENCES forecasts (id),
                FOREIGN KEY (news_id) REFERENCES news (id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_status ON paper_trades(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_asset ON paper_trades(asset, status)")
        
        # System logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                module TEXT NOT NULL,
                message TEXT NOT NULL
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON system_logs(timestamp DESC)")

        # Worker status table (single row)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS worker_status (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_heartbeat TEXT,
                last_heartbeat_at TEXT,
                last_cycle_seconds REAL,
                last_error TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("INSERT OR IGNORE INTO worker_status (id, last_heartbeat) VALUES (1, NULL)")

        # Per-page last-seen state (for NEW badges)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_page_state (
                page_key TEXT PRIMARY KEY,
                last_seen_at TEXT,
                last_seen_id INTEGER
            )
            """
        )
        
        # Trade counters (for rate limiting)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trade_counters (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                trades_this_hour INTEGER DEFAULT 0,
                hour_reset_time TEXT
            )
        """)
        
        cursor.execute("""
            INSERT OR IGNORE INTO trade_counters (id, trades_this_hour, hour_reset_time)
            VALUES (1, 0, ?)
        """, (datetime.now().isoformat(),))
        
        conn.commit()
        conn.close()

    # ========================================================================
    # WORKER STATUS
    # ========================================================================

    def update_worker_heartbeat(self, cycle_seconds: float = None):
        """Update worker heartbeat for UI diagnostics.

        This is called both:
        - periodically by a dedicated heartbeat thread (cycle_seconds=None)
        - at cycle boundaries to record duration (cycle_seconds set)

        Must never clobber cycle timing when used as a periodic heartbeat.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        now = self._utc_now_iso()

        # Prefer storing periodic heartbeat into last_heartbeat_at (new) while
        # still updating last_heartbeat for backward compatibility.
        if cycle_seconds is None:
            try:
                cursor.execute(
                    """
                    UPDATE worker_status
                    SET last_heartbeat = ?, last_heartbeat_at = ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (now, now, now),
                )
            except Exception:
                cursor.execute(
                    """
                    UPDATE worker_status
                    SET last_heartbeat = ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (now, now),
                )
        else:
            try:
                cursor.execute(
                    """
                    UPDATE worker_status
                    SET last_heartbeat = ?, last_heartbeat_at = ?, last_cycle_seconds = ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (now, now, cycle_seconds, now),
                )
            except Exception:
                cursor.execute(
                    """
                    UPDATE worker_status
                    SET last_heartbeat = ?, last_cycle_seconds = ?, updated_at = ?
                    WHERE id = 1
                    """,
                    (now, cycle_seconds, now),
                )
        conn.commit()
        conn.close()

    def update_worker_success(self, cycle_seconds: float = None):
        """Record last successful cycle timestamp (separate from heartbeat)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        # Column may not exist on older DBs; migrations should add it, but keep safe.
        try:
            cursor.execute(
                """
                UPDATE worker_status
                SET last_successful_cycle_at = ?, last_cycle_seconds = ?, updated_at = ?
                WHERE id = 1
                """,
                (self._utc_now_iso(), cycle_seconds, self._utc_now_iso()),
            )
        except Exception:
            # Fallback: update updated_at only
            cursor.execute(
                """
                UPDATE worker_status
                SET last_cycle_seconds = ?, updated_at = ?
                WHERE id = 1
                """,
                (cycle_seconds, self._utc_now_iso()),
            )
        conn.commit()
        conn.close()

    def update_worker_last_error(self, error_message: str):
        """Store last worker error for UI diagnostics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE worker_status
            SET last_error = ?, updated_at = ?
            WHERE id = 1
            """,
            (error_message, self._utc_now_iso()),
        )
        conn.commit()
        conn.close()

    def get_worker_status(self) -> Optional[Dict]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM worker_status WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # ========================================================================
    # NEWS DEDUP HELPERS
    # ========================================================================

    def has_news_url(self, url: str) -> bool:
        """Return True if a news row already exists for the given URL."""
        if not url or not str(url).strip():
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM news WHERE url = ? LIMIT 1", (str(url).strip(),))
        row = cursor.fetchone()
        conn.close()
        return bool(row)

    def has_news_url_hash(self, url_hash: str, source: str | None = None) -> bool:
        """Return True if a news row already exists for the given url_hash.

        Optionally scope by source for extra safety.
        """
        if not url_hash or not str(url_hash).strip():
            return False
        conn = self.get_connection()
        cursor = conn.cursor()
        if source:
            cursor.execute(
                "SELECT 1 FROM news WHERE url_hash = ? AND source = ? LIMIT 1",
                (str(url_hash).strip(), str(source).strip()),
            )
        else:
            cursor.execute("SELECT 1 FROM news WHERE url_hash = ? LIMIT 1", (str(url_hash).strip(),))
        row = cursor.fetchone()
        conn.close()
        return bool(row)
    
    # ========================================================================
    # NEWS OPERATIONS
    # ========================================================================
    
    def insert_news(self, news_data: Dict) -> Optional[int]:
        """Insert news item, return ID or None if duplicate"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO news (
                    source, url, url_hash, title_en, body_en, title_ar, body_ar,
                    published_at, fetched_at, category, sentiment, impact_level,
                    confidence, affected_assets, source_reliability
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                news_data.get('source'),
                news_data.get('url'),
                news_data.get('url_hash'),
                news_data.get('title_en'),
                news_data.get('body_en'),
                news_data.get('title_ar'),
                news_data.get('body_ar'),
                news_data.get('published_at'),
                news_data.get('fetched_at', self._utc_now_iso()),
                news_data.get('category'),
                news_data.get('sentiment'),
                news_data.get('impact_level'),
                news_data.get('confidence'),
                json.dumps(news_data.get('affected_assets', [])),
                news_data.get('source_reliability', 0.8)
            ))
            
            news_id = cursor.lastrowid
            conn.commit()
            return news_id
            
        except sqlite3.IntegrityError:
            # Duplicate URL
            return None
        finally:
            conn.close()
    
    def get_unprocessed_news(self, limit: int = 100) -> List[Dict]:
        """Get news items not yet processed for forecasting"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM news 
            WHERE processed = 0 
            ORDER BY fetched_at DESC 
            LIMIT ?
        """, (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Parse JSON fields
        for item in results:
            if item.get('affected_assets'):
                try:
                    item['affected_assets'] = json.loads(item['affected_assets'])
                except Exception:
                    # Legacy: comma-separated string
                    raw = str(item.get('affected_assets') or '')
                    item['affected_assets'] = [a.strip() for a in raw.split(',') if a.strip()]
        
        return results
    
    def update_news_translation(self, news_id: int, title_ar: str, body_ar: str):
        """Update news translation"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE news SET title_ar = ?, body_ar = ? WHERE id = ?
        """, (title_ar, body_ar, news_id))
        conn.commit()
        conn.close()
    
    def update_news_analysis(self, news_id: int, category: str, sentiment: str, 
                            impact_level: str, confidence: float, affected_assets: str):
        """Update news with analysis results"""
        # Store affected_assets as JSON array for consistent downstream parsing
        if isinstance(affected_assets, list):
            affected_assets_json = json.dumps(affected_assets)
        else:
            raw = str(affected_assets or '')
            affected_assets_json = json.dumps([a.strip() for a in raw.split(',') if a.strip()])

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE news 
            SET category = ?, sentiment = ?, impact_level = ?, 
                confidence = ?, affected_assets = ?
            WHERE id = ?
        """, (category, sentiment, impact_level, confidence, affected_assets_json, news_id))
        conn.commit()
        conn.close()
    
    def mark_news_processed(self, news_id: int):
        """Mark news as processed"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE news SET processed = 1 WHERE id = ?", (news_id,))
        conn.commit()
        conn.close()
    
    def get_recent_news(self, limit: int = 50, hours: int = 24) -> List[Dict]:
        """Get recent news items"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM news 
            WHERE datetime(fetched_at) > datetime('now', '-' || ? || ' hours')
            ORDER BY fetched_at DESC 
            LIMIT ?
        """, (hours, limit))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        for item in results:
            if item.get('affected_assets'):
                try:
                    item['affected_assets'] = json.loads(item['affected_assets'])
                except Exception:
                    raw = str(item.get('affected_assets') or '')
                    item['affected_assets'] = [a.strip() for a in raw.split(',') if a.strip()]
        
        return results

    def get_recent_news_count(self, hours: int = 24) -> int:
        """Count recent news items (used for sidebar badges/UI)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT COUNT(*) FROM news
                WHERE datetime(fetched_at) > datetime('now', '-' || ? || ' hours')
                """,
                (hours,),
            )
            return int(cursor.fetchone()[0])
        finally:
            conn.close()
    
    # ========================================================================
    # PRICE OPERATIONS
    # ========================================================================
    
    def insert_price(self, asset: str, price: float, source: str = 'yahoo_finance'):
        """Insert price data"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO prices (asset, price, timestamp, source)
            VALUES (?, ?, ?, ?)
        """, (asset, float(price), self._utc_now_iso(), source))
        
        conn.commit()
        conn.close()
    
    def get_latest_price(self, asset: str) -> Optional[Dict]:
        """Get latest price for asset"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT * FROM prices
            WHERE asset = ?
            ORDER BY datetime(timestamp) DESC, id DESC
            LIMIT 1
            """,
            (asset,),
        )
        
        row = cursor.fetchone()
        conn.close()

        # Compatibility: older DBs might have stored USD as 'USD'
        if not row and asset == 'USD Index':
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM prices
                WHERE asset = 'USD'
                ORDER BY datetime(timestamp) DESC, id DESC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            conn.close()

        return dict(row) if row else None

    def get_last_two_prices(self, asset: str) -> List[Dict]:
        """Return up to two most recent price rows for an asset."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM prices
            WHERE asset = ?
            ORDER BY datetime(timestamp) DESC, id DESC
            LIMIT 2
            """,
            (asset,),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        # Compatibility: older DBs might have stored USD as 'USD'
        if not rows and asset == 'USD Index':
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM prices
                WHERE asset = 'USD'
                ORDER BY datetime(timestamp) DESC, id DESC
                LIMIT 2
                """
            )
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
        return rows

    def get_price_change(self, asset: str) -> Dict[str, Any]:
        """Compute price change vs previous DB snapshot.

        Returns:
            {
              latest_price, latest_timestamp,
              prev_price, prev_timestamp,
              change, change_percent
            }
        """
        rows = self.get_last_two_prices(asset)
        latest = rows[0] if len(rows) >= 1 else None
        prev = rows[1] if len(rows) >= 2 else None

        latest_price = float(latest['price']) if latest and latest.get('price') is not None else None
        prev_price = float(prev['price']) if prev and prev.get('price') is not None else None

        change = None
        change_percent = None
        if latest_price is not None and prev_price not in (None, 0.0):
            change = latest_price - prev_price
            change_percent = (change / prev_price) * 100

        return {
            'latest_price': latest_price,
            'latest_timestamp': (latest or {}).get('timestamp'),
            'prev_price': prev_price,
            'prev_timestamp': (prev or {}).get('timestamp'),
            'change': change,
            'change_percent': change_percent,
        }

    # ========================================================================
    # USER PAGE STATE (NEW BADGES)
    # ========================================================================

    def get_user_page_state(self, page_key: str) -> Dict[str, Any]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT page_key, last_seen_at, last_seen_id FROM user_page_state WHERE page_key = ?",
                (page_key,),
            )
            row = cursor.fetchone()
            return dict(row) if row else {"page_key": page_key, "last_seen_at": None, "last_seen_id": None}
        finally:
            conn.close()

    def upsert_user_page_state(self, page_key: str, last_seen_at: Optional[str], last_seen_id: Optional[int]) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO user_page_state (page_key, last_seen_at, last_seen_id)
                VALUES (?, ?, ?)
                ON CONFLICT(page_key) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    last_seen_id = excluded.last_seen_id
                """,
                (page_key, last_seen_at, last_seen_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _table_max_id(self, table: str, id_col: str = 'id', where_sql: str = '', params: tuple = ()) -> Optional[int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            sql = f"SELECT MAX({id_col}) FROM {table} {where_sql}".strip()
            cursor.execute(sql, params)
            v = cursor.fetchone()[0]
            return int(v) if v is not None else None
        except Exception:
            return None
        finally:
            conn.close()

    def _table_max_ts(self, table: str, ts_col: str, where_sql: str = '', params: tuple = ()) -> Optional[str]:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            sql = f"SELECT {ts_col} FROM {table} {where_sql} ORDER BY datetime({ts_col}) DESC LIMIT 1".strip()
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return str(row[0]) if row and row[0] else None
        except Exception:
            return None
        finally:
            conn.close()

    def _count_new_by_id_or_time(
        self,
        table: str,
        id_col: str,
        ts_col: str,
        last_seen_id: Optional[int],
        last_seen_at: Optional[str],
        where_sql: str = '',
        params: tuple = (),
    ) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cond = ""
            args = list(params)
            if last_seen_id is not None:
                cond = f"{id_col} > ?"
                args.append(int(last_seen_id))
            elif last_seen_at:
                cond = f"datetime({ts_col}) > datetime(?)"
                args.append(str(last_seen_at))
            else:
                # First visit: treat as 0 new.
                return 0

            where = "WHERE " + cond
            if where_sql:
                # where_sql expected to start with WHERE ...
                if where_sql.strip().upper().startswith('WHERE'):
                    where = where_sql + " AND " + cond
                else:
                    where = "WHERE " + where_sql + " AND " + cond

            cursor.execute(f"SELECT COUNT(*) FROM {table} {where}", tuple(args))
            return int(cursor.fetchone()[0])
        except Exception:
            return 0
        finally:
            conn.close()

    def get_page_new_count(self, page_key: str) -> int:
        state = self.get_user_page_state(page_key)
        last_seen_at = state.get('last_seen_at')
        last_seen_id = state.get('last_seen_id')

        if page_key == 'news':
            return self._count_new_by_id_or_time('news', 'id', 'fetched_at', last_seen_id, last_seen_at)
        if page_key == 'outlook':
            return self._count_new_by_id_or_time('forecasts', 'id', 'created_at', last_seen_id, last_seen_at)
        if page_key == 'portfolio':
            return self._count_new_by_id_or_time('paper_trades', 'id', 'entry_time', last_seen_id, last_seen_at)
        if page_key == 'accuracy':
            # Evaluations happen after creation; use evaluated_at/evaluation_time timestamps.
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA table_info(forecasts)")
                cols = {row[1] for row in cursor.fetchall()}
                ts = 'evaluated_at' if 'evaluated_at' in cols else ('evaluation_time' if 'evaluation_time' in cols else None)
            finally:
                conn.close()
            if not ts:
                return 0
            return self._count_new_by_id_or_time('forecasts', 'id', ts, None, last_seen_at, where_sql=f"WHERE {ts} IS NOT NULL")
        if page_key == 'dashboard':
            # Dashboard badge summarizes NEW items across core tables.
            return (
                self.get_page_new_count('news')
                + self.get_page_new_count('outlook')
                + self.get_page_new_count('accuracy')
                + self.get_page_new_count('portfolio')
            )
        return 0

    def get_page_last_updated(self, page_key: str) -> Optional[str]:
        if page_key == 'news':
            return self._table_max_ts('news', 'fetched_at')
        if page_key == 'outlook':
            return self._table_max_ts('forecasts', 'created_at')
        if page_key == 'portfolio':
            # Prefer portfolio.updated_at; fallback to latest trade
            try:
                p = self.get_portfolio()
                if p and p.get('updated_at'):
                    return str(p.get('updated_at'))
            except Exception:
                pass
            return self._table_max_ts('paper_trades', 'entry_time')
        if page_key == 'accuracy':
            # Prefer evaluated_at/evaluation_time
            conn = self.get_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("PRAGMA table_info(forecasts)")
                cols = {row[1] for row in cursor.fetchall()}
                ts = 'evaluated_at' if 'evaluated_at' in cols else ('evaluation_time' if 'evaluation_time' in cols else None)
            finally:
                conn.close()
            if not ts:
                return None
            return self._table_max_ts('forecasts', ts, where_sql=f"WHERE {ts} IS NOT NULL")
        if page_key == 'dashboard':
            # Most recent across key sources
            candidates = [
                self.get_page_last_updated('news'),
                self.get_page_last_updated('outlook'),
                self.get_page_last_updated('accuracy'),
                self.get_page_last_updated('portfolio'),
            ]
            candidates = [c for c in candidates if c]
            return max(candidates) if candidates else None
        return None

    def mark_page_seen(self, page_key: str) -> None:
        now = self._utc_now_iso()

        if page_key == 'news':
            latest_id = self._table_max_id('news')
            self.upsert_user_page_state(page_key, now, latest_id)
            return
        if page_key == 'outlook':
            latest_id = self._table_max_id('forecasts')
            self.upsert_user_page_state(page_key, now, latest_id)
            return
        if page_key == 'portfolio':
            latest_id = self._table_max_id('paper_trades')
            self.upsert_user_page_state(page_key, now, latest_id)
            return
        if page_key == 'accuracy':
            # Use timestamp only (evaluations don't change ids)
            self.upsert_user_page_state(page_key, now, None)
            return
        if page_key == 'dashboard':
            self.upsert_user_page_state(page_key, now, None)
            return

    def get_sidebar_badges(self) -> Dict[str, int]:
        """Return per-page NEW counts suitable for sidebar badges."""
        out: Dict[str, int] = {}
        for key in ('dashboard', 'news', 'outlook', 'accuracy', 'portfolio'):
            try:
                out[key] = int(self.get_page_new_count(key) or 0)
            except Exception:
                out[key] = 0
        return out

    def get_latest_forecast_for_asset(self, asset: str) -> Optional[Dict[str, Any]]:
        """Return latest forecast for asset (prefer active, fallback evaluated)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT *
                FROM forecasts
                WHERE asset = ?
                ORDER BY
                  CASE WHEN status = 'active' THEN 0 ELSE 1 END,
                  datetime(COALESCE(created_at, forecast_time, due_at)) DESC,
                  id DESC
                LIMIT 1
                """,
                (asset,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_price_at_or_after(self, asset: str, target_time_iso: str) -> Optional[float]:
        """Get the first price at-or-after target time; fallback to latest price."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT price FROM prices
            WHERE asset = ?
              AND datetime(timestamp) >= datetime(?)
            ORDER BY datetime(timestamp) ASC
            LIMIT 1
            """,
            (asset, target_time_iso),
        )
        row = cursor.fetchone()
        conn.close()

        if row and row[0] is not None:
            return float(row[0])

        latest = self.get_latest_price(asset)
        if latest and latest.get('price') is not None:
            return float(latest['price'])
        return None

    def _sql_dt_expr(self, column: str) -> str:
        """Return a SQLite expression that parses common ISO timestamps.

        Handles values like:
        - 2026-01-31T12:34:56
        - 2026-01-31T12:34:56+00:00
        - 2026-01-31T12:34:56Z

        SQLite's datetime() is picky; we normalize to 'YYYY-MM-DD HH:MM:SS'.
        """
        return f"datetime(replace(substr({column},1,19),'T',' '))"

    def _sql_dt_param(self) -> str:
        return "datetime(replace(substr(?,1,19),'T',' '))"

    def get_price_for_evaluation(self, asset: str, due_at_iso: str, max_window_hours: int = 6) -> Optional[Dict[str, Any]]:
        """Return the best available price snapshot for evaluating a forecast.

        Priority:
        1) first snapshot at/after due_at within max_window_hours => quality='exact'
        2) first snapshot at/after due_at (even if late) => quality='approx'
        3) latest snapshot => quality='approx'
        """
        if not asset or not due_at_iso:
            return None

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            ts_expr = self._sql_dt_expr('timestamp')
            due_expr = self._sql_dt_param()

            # 1) within window
            try:
                cursor.execute(
                    f"""
                    SELECT price, timestamp
                    FROM prices
                    WHERE asset = ?
                      AND {ts_expr} >= {due_expr}
                      AND {ts_expr} <= datetime({due_expr}, '+{int(max_window_hours)} hours')
                    ORDER BY {ts_expr} ASC, id ASC
                    LIMIT 1
                    """,
                    (asset, due_at_iso, due_at_iso, due_at_iso),
                )
                row = cursor.fetchone()
                if row and row[0] is not None:
                    return {
                        'price': float(row[0]),
                        'timestamp': str(row[1]) if row[1] else None,
                        'quality': 'exact',
                    }
            except Exception:
                pass

            # 2) any time after due
            try:
                cursor.execute(
                    f"""
                    SELECT price, timestamp
                    FROM prices
                    WHERE asset = ?
                      AND {ts_expr} >= {due_expr}
                    ORDER BY {ts_expr} ASC, id ASC
                    LIMIT 1
                    """,
                    (asset, due_at_iso),
                )
                row = cursor.fetchone()
                if row and row[0] is not None:
                    return {
                        'price': float(row[0]),
                        'timestamp': str(row[1]) if row[1] else None,
                        'quality': 'approx',
                    }
            except Exception:
                pass
        finally:
            conn.close()

        # 3) latest snapshot (approx)
        latest = self.get_latest_price(asset)
        if latest and latest.get('price') is not None:
            return {
                'price': float(latest['price']),
                'timestamp': latest.get('timestamp'),
                'quality': 'approx',
            }
        return None
    
    def get_price_at_time(self, asset: str, target_time: str) -> Optional[float]:
        """Get price closest to target time"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT price FROM prices
            WHERE asset = ?
            AND ABS(julianday(timestamp) - julianday(?)) = (
                SELECT MIN(ABS(julianday(timestamp) - julianday(?)))
                FROM prices WHERE asset = ?
            )
            LIMIT 1
        """, (asset, target_time, target_time, asset))
        
        row = cursor.fetchone()
        conn.close()
        
        return row[0] if row else None
    
    # ========================================================================
    # FORECAST OPERATIONS
    # ========================================================================
    
    def insert_forecast(self, forecast_data: Dict) -> int:
        """Insert forecast"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO forecasts (
                news_id, asset, direction, confidence, risk_level,
                horizon_minutes, created_at, due_at, reasoning,
                scenario_base, scenario_alt, price_at_forecast
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            forecast_data.get('news_id'),
            forecast_data['asset'],
            forecast_data['direction'],
            forecast_data['confidence'],
            forecast_data['risk_level'],
            forecast_data['horizon_minutes'],
            forecast_data['created_at'],
            forecast_data['due_at'],
            forecast_data.get('reasoning'),
            forecast_data.get('scenario_base'),
            forecast_data.get('scenario_alt'),
            forecast_data.get('price_at_forecast')
        ))
        
        forecast_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return forecast_id
    
    def get_forecasts_due(self) -> List[Dict]:
        """Get forecasts that need evaluation"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            try:
                cursor.execute("PRAGMA table_info(forecasts)")
                cols = {row[1] for row in cursor.fetchall()}
            except Exception:
                cols = set()

            evaluated_col = None
            if 'evaluated_at' in cols:
                evaluated_col = 'evaluated_at'
            elif 'evaluation_time' in cols:
                evaluated_col = 'evaluation_time'

            due_expr = self._sql_dt_expr('due_at')
            where_eval = ""
            if evaluated_col:
                where_eval = f"AND ({evaluated_col} IS NULL OR {evaluated_col} = '')"

            cursor.execute(
                f"""
                SELECT *
                FROM forecasts
                WHERE status = 'active'
                  {where_eval}
                  AND due_at IS NOT NULL AND due_at != ''
                  AND {due_expr} <= datetime('now')
                ORDER BY {due_expr} ASC, id ASC
                """
            )
            results = [dict(row) for row in cursor.fetchall()]
            return results
        finally:
            conn.close()

    def get_forecast_by_id(self, forecast_id: int) -> Optional[Dict]:
        """Fetch a single forecast row by id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM forecasts WHERE id = ?", (forecast_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def update_forecast_evaluation(self, forecast_id: int, eval_data: Dict):
        """Update forecast with evaluation results"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Columns may not exist on older DBs; keep a conservative fallback.
        try:
            cursor.execute("PRAGMA table_info(forecasts)")
            cols = {row[1] for row in cursor.fetchall()}
        except Exception:
            cols = set()

        evaluated_at = eval_data.get('evaluated_at') or self._utc_now_iso()
        actual_price = eval_data.get('actual_price')
        if actual_price is None:
            actual_price = eval_data.get('price_at_evaluation')

        sets = [
            "status = 'evaluated'",
            "evaluation_result = ?",
            "actual_direction = ?",
            "price_at_evaluation = ?",
            "actual_return = ?",
            "evaluated_at = ?",
        ]
        args = [
            eval_data.get('evaluation_result'),
            eval_data.get('actual_direction'),
            eval_data.get('price_at_evaluation'),
            eval_data.get('actual_return'),
            evaluated_at,
        ]

        if 'evaluation_time' in cols:
            sets.append("evaluation_time = ?")
            args.append(evaluated_at)

        if 'actual_price' in cols:
            sets.append("actual_price = ?")
            args.append(actual_price)

        if 'actual_time' in cols:
            sets.append("actual_time = ?")
            args.append(eval_data.get('actual_time'))

        if 'direction_correct' in cols:
            sets.append("direction_correct = ?")
            args.append(1 if eval_data.get('direction_correct') else 0)

        if 'abs_error' in cols:
            sets.append("abs_error = ?")
            args.append(eval_data.get('abs_error'))

        if 'pct_error' in cols:
            sets.append("pct_error = ?")
            args.append(eval_data.get('pct_error'))

        if 'evaluation_quality' in cols:
            sets.append("evaluation_quality = ?")
            args.append(eval_data.get('evaluation_quality'))

        sets.append("updated_at = ?") if 'updated_at' in cols else None
        if 'updated_at' in cols:
            args.append(self._utc_now_iso())

        sql = "UPDATE forecasts SET " + ", ".join(sets) + " WHERE id = ?"
        args.append(int(forecast_id))
        cursor.execute(sql, tuple(args))
        
        conn.commit()
        conn.close()

    def evaluate_due_forecasts_backfill(self, max_window_hours: int = 6, limit: int = 5000) -> Dict[str, Any]:
        """Evaluate all due forecasts (idempotent) and backfill late evaluations.

        Returns diagnostic counts.
        """
        due = self.get_forecasts_due()
        if limit and len(due) > int(limit):
            due = due[: int(limit)]

        evaluated = 0
        skipped = 0
        errors = 0

        for f in due:
            try:
                forecast_id = int(f.get('id'))
                asset = f.get('asset')
                due_at = f.get('due_at')
                expected = str(f.get('direction') or '').upper()

                price0 = f.get('price_at_forecast')
                if price0 is None or str(price0) == '':
                    skipped += 1
                    continue
                price0 = float(price0)
                if price0 <= 0:
                    skipped += 1
                    continue

                snap = self.get_price_for_evaluation(asset, str(due_at), max_window_hours=max_window_hours)
                if not snap or snap.get('price') is None:
                    skipped += 1
                    continue

                actual_price = float(snap['price'])
                actual_time = snap.get('timestamp')
                quality = snap.get('quality') or 'approx'

                pct_move = ((actual_price - price0) / price0) * 100.0
                if pct_move > 0.1:
                    actual_direction = 'UP'
                elif pct_move < -0.1:
                    actual_direction = 'DOWN'
                else:
                    actual_direction = 'NEUTRAL'

                # Determine direction correctness (direction-only forecasts)
                if expected == actual_direction:
                    hit = True
                elif expected == 'NEUTRAL' and abs(pct_move) < 0.5:
                    hit = True
                else:
                    hit = False

                abs_error = abs(actual_price - price0)
                pct_error = (abs_error / price0) * 100.0

                eval_data = {
                    'evaluation_result': 'hit' if hit else 'miss',
                    'actual_direction': actual_direction,
                    'price_at_evaluation': actual_price,
                    'actual_price': actual_price,
                    'actual_time': actual_time,
                    'direction_correct': hit,
                    'abs_error': abs_error,
                    'pct_error': pct_error,
                    'evaluation_quality': quality,
                    'actual_return': pct_move,
                    'evaluated_at': self._utc_now_iso(),
                }

                self.update_forecast_evaluation(forecast_id, eval_data)
                evaluated += 1
            except Exception as e:
                errors += 1
                try:
                    self.log('ERROR', 'Evaluator', f"Forecast eval error id={f.get('id')}: {e}")
                except Exception:
                    pass
                continue

        return {
            'due_found': len(due),
            'evaluated': evaluated,
            'skipped': skipped,
            'errors': errors,
        }
    
    def evaluate_due_forecasts(self, max_window_hours: int = 6) -> int:
        """Evaluate due forecasts and return count (worker-friendly wrapper).
        
        This is the simplified interface called by the worker.
        Returns the number of forecasts evaluated.
        """
        result = self.evaluate_due_forecasts_backfill(
            max_window_hours=max_window_hours, 
            limit=500  # Process more in each cycle for faster catch-up
        )
        return result.get('evaluated', 0)
    
    def get_active_forecasts(self, limit: int = 100) -> List[Dict]:
        """Get active forecasts"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM forecasts
            WHERE status = 'active'
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_all_evaluated_forecasts(self, limit: int = 500) -> List[Dict]:
        """Return evaluated forecasts with dynamic column detection.

        Crash-proof behavior:
        - If no evaluated timestamp columns exist, returns empty list.
        - Uses created_at/forecast_time ordering depending on what exists.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(forecasts)")
        cols = {row[1] for row in cursor.fetchall()}

        # Determine evaluated timestamp column
        evaluated_col = None
        if 'evaluation_time' in cols:
            evaluated_col = 'evaluation_time'
        elif 'evaluated_at' in cols:
            evaluated_col = 'evaluated_at'
        else:
            conn.close()
            return []

        # Determine forecast time column
        order_col = 'created_at' if 'created_at' in cols else ('forecast_time' if 'forecast_time' in cols else None)
        if not order_col:
            conn.close()
            return []

        cursor.execute(
            f"""
            SELECT * FROM forecasts
            WHERE {evaluated_col} IS NOT NULL
            ORDER BY datetime({order_col}) DESC
            LIMIT ?
            """,
            (limit,),
        )

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_forecast_counts(self) -> Dict[str, int]:
        """Get total/active/evaluated forecast counts."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as c FROM forecasts")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) as c FROM forecasts WHERE status = 'active'")
        active = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) as c FROM forecasts WHERE status = 'evaluated'")
        evaluated = cursor.fetchone()[0]
        conn.close()
        return {'total': total, 'active': active, 'evaluated': evaluated}

    def get_trade_counts(self) -> Dict[str, int]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM paper_trades")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE status = 'open'")
        open_trades = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM paper_trades WHERE status = 'closed'")
        closed_trades = cursor.fetchone()[0]
        conn.close()
        return {'total': total, 'open': open_trades, 'closed': closed_trades}

    def get_news_count(self) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM news")
        count = cursor.fetchone()[0]
        conn.close()
        return count

    def get_latest_error_log(self) -> Optional[Dict]:
        """Return the latest error log entry, if it's still relevant.

        If the system has successfully completed a worker cycle AFTER the most recent
        error, return None so callers can treat the system as recovered.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM system_logs
            WHERE level IN ('ERROR', 'CRITICAL')
            ORDER BY timestamp DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return None

        latest_error = dict(row)

        # If worker_status indicates a successful cycle after this error, suppress it.
        try:
            cursor.execute("SELECT last_successful_cycle_at FROM worker_status WHERE id = 1")
            ws = cursor.fetchone()
            last_ok = (ws[0] if ws else None)
            err_ts = latest_error.get('timestamp')

            if last_ok and err_ts:
                try:
                    ok_dt = datetime.fromisoformat(str(last_ok).replace('Z', '+00:00'))
                    err_dt = datetime.fromisoformat(str(err_ts).replace('Z', '+00:00'))

                    # Compare using epoch seconds to handle naive vs timezone-aware values.
                    local_tz = datetime.now().astimezone().tzinfo
                    if ok_dt.tzinfo is None:
                        ok_dt = ok_dt.replace(tzinfo=local_tz)
                    if err_dt.tzinfo is None:
                        err_dt = err_dt.replace(tzinfo=local_tz)

                    if ok_dt.timestamp() >= err_dt.timestamp():
                        conn.close()
                        return None
                except Exception:
                    pass
        except Exception:
            pass

        conn.close()
        return latest_error
    
    # ========================================================================
    # PAPER PORTFOLIO OPERATIONS
    # ========================================================================
    
    def get_portfolio(self) -> Dict:
        """Get portfolio summary"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM paper_portfolio WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def update_portfolio_equity(self, new_equity: float, daily_pnl: float = None):
        """Update portfolio equity"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if daily_pnl is not None:
            cursor.execute("""
                UPDATE paper_portfolio 
                SET current_equity = ?, daily_pnl = ?, updated_at = ?
                WHERE id = 1
            """, (new_equity, daily_pnl, datetime.now().isoformat()))
        else:
            cursor.execute("""
                UPDATE paper_portfolio 
                SET current_equity = ?, updated_at = ?
                WHERE id = 1
            """, (new_equity, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def reset_daily_pnl(self):
        """Reset daily P&L counter"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE paper_portfolio 
            SET daily_pnl = 0, daily_reset_date = ?, is_trading_paused = 0
            WHERE id = 1
        """, (datetime.now().date().isoformat(),))
        
        conn.commit()
        conn.close()
    
    def pause_trading(self):
        """Pause trading (daily loss limit hit)"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("UPDATE paper_portfolio SET is_trading_paused = 1 WHERE id = 1")
        conn.commit()
        conn.close()
    
    # ========================================================================
    # TRADE OPERATIONS
    # ========================================================================
    
    def insert_trade(self, trade_data: Dict) -> int:
        """Insert new trade"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO paper_trades (
                forecast_id, news_id, asset, side, size_usd,
                entry_price, entry_time, stop_loss, take_profit,
                reason, confidence, risk_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_data.get('forecast_id'),
            trade_data.get('news_id'),
            trade_data['asset'],
            trade_data['side'],
            trade_data['size_usd'],
            trade_data['entry_price'],
            trade_data['entry_time'],
            trade_data.get('stop_loss'),
            trade_data.get('take_profit'),
            trade_data.get('reason'),
            trade_data.get('confidence'),
            trade_data.get('risk_level')
        ))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return trade_id
    
    def close_trade(self, trade_id: int, exit_price: float, reason: str = ""):
        """Close trade and calculate P&L"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get trade details
        cursor.execute("SELECT * FROM paper_trades WHERE id = ?", (trade_id,))
        trade = dict(cursor.fetchone())
        
        entry_price = trade['entry_price']
        size_usd = trade['size_usd']
        side = trade['side']
        
        # Calculate P&L
        if side == 'BUY':
            pnl = (exit_price - entry_price) / entry_price * size_usd
        else:  # SELL (short)
            pnl = (entry_price - exit_price) / entry_price * size_usd
        
        pnl_pct = (pnl / size_usd) * 100
        
        cursor.execute("""
            UPDATE paper_trades SET
                exit_price = ?,
                exit_time = ?,
                status = 'closed',
                pnl = ?,
                pnl_pct = ?,
                reason = reason || ' | ' || ?
            WHERE id = ?
        """, (exit_price, datetime.now().isoformat(), pnl, pnl_pct, reason, trade_id))
        
        conn.commit()
        conn.close()
        
        return pnl
    
    def get_open_trades(self) -> List[Dict]:
        """Get all open trades"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM paper_trades
            WHERE status = 'open'
            ORDER BY entry_time DESC
        """)
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_open_trades_for_asset(self, asset: str) -> List[Dict]:
        """Get open trades for specific asset"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM paper_trades
            WHERE status = 'open' AND asset = ?
        """, (asset,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_trades_by_forecast_id(self, forecast_id: int) -> List[Dict]:
        """Get all trades associated with a forecast"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM paper_trades
            WHERE forecast_id = ?
        """, (forecast_id,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def insert_paper_trade(self, trade_data: Dict) -> int:
        """Alias for insert_trade() - for clarity in auto-trading context"""
        return self.insert_trade(trade_data)
    
    def get_open_paper_trades(self) -> List[Dict]:
        """Alias for get_open_trades() - for clarity in worker context"""
        return self.get_open_trades()
    
    def get_all_trades(self, limit: int = 100) -> List[Dict]:
        """Get all trades"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM paper_trades
            ORDER BY entry_time DESC
            LIMIT ?
        """, (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    # ========================================================================
    # TRADE COUNTERS (Rate Limiting)
    # ========================================================================
    
    def get_trade_counter(self) -> Dict:
        """Get trade counter"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM trade_counters WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def increment_trade_counter(self):
        """Increment trade counter"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE trade_counters 
            SET trades_this_hour = trades_this_hour + 1
            WHERE id = 1
        """)
        
        conn.commit()
        conn.close()
    
    def reset_trade_counter(self):
        """Reset hourly trade counter"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE trade_counters 
            SET trades_this_hour = 0, hour_reset_time = ?
            WHERE id = 1
        """, (datetime.now().isoformat(),))
        
        conn.commit()
        conn.close()
    
    # ========================================================================
    # SYSTEM LOGS
    # ========================================================================
    
    def log(self, level: str, module: str, message: str):
        """Insert system log"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO system_logs (timestamp, level, module, message)
            VALUES (?, ?, ?, ?)
        """, (self._utc_now_iso(), level, module, message))
        
        conn.commit()
        conn.close()
    
    def get_recent_logs(self, limit: int = 100) -> List[Dict]:
        """Get recent logs"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM system_logs
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    # ========================================================================
    # ANALYTICS
    # ========================================================================
    
    def get_forecast_accuracy(self, days: int = 7) -> Dict:
        """Get forecast accuracy statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN evaluation_result = 'hit' THEN 1 ELSE 0 END) as hits,
                AVG(confidence) as avg_confidence,
                asset
            FROM forecasts
            WHERE status = 'evaluated'
            AND datetime(created_at) > datetime('now', '-' || ? || ' days')
            GROUP BY asset
        """, (days,))
        
        results = {}
        for row in cursor.fetchall():
            row_dict = dict(row)
            asset = row_dict['asset']
            total = row_dict['total']
            hits = row_dict['hits']
            
            results[asset] = {
                'total': total,
                'hits': hits,
                'accuracy': (hits / total * 100) if total > 0 else 0,
                'avg_confidence': row_dict['avg_confidence']
            }
        
        conn.close()
        return results
    
    def get_portfolio_performance(self) -> Dict:
        """Get portfolio performance metrics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                MAX(pnl) as max_win,
                MIN(pnl) as max_loss
            FROM paper_trades
            WHERE status = 'closed'
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if not row or row[0] == 0:
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
        
        row_dict = dict(row)
        total = row_dict['total_trades']
        wins = row_dict['winning_trades'] or 0
        
        return {
            'total_trades': total,
            'winning_trades': wins,
            'losing_trades': row_dict['losing_trades'] or 0,
            'win_rate': (wins / total * 100) if total > 0 else 0,
            'total_pnl': row_dict['total_pnl'] or 0,
            'avg_pnl': row_dict['avg_pnl'] or 0,
            'max_win': row_dict['max_win'] or 0,
            'max_loss': row_dict['max_loss'] or 0
        }
    
    def get_recent_forecasts_for_trading(self, limit: int = 50) -> List[Dict]:
        """Get recent unevaluated forecasts for trading evaluation"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT f.*, n.source_reliability
            FROM forecasts f
            LEFT JOIN news n ON f.news_id = n.id
            WHERE f.status = 'active'
            AND f.id NOT IN (
                SELECT DISTINCT forecast_id 
                FROM paper_trades 
                WHERE forecast_id IS NOT NULL
            )
            ORDER BY f.created_at DESC
            LIMIT ?
        """, (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def get_portfolio_status(self) -> Optional[Dict]:
        """Get current portfolio status"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                current_equity,
                daily_pnl,
                is_trading_paused as trading_paused,
                daily_reset_date
            FROM paper_portfolio
            WHERE id = 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None

    # ========================================================================
    # ALL FORECASTS HISTORY (Persistent Recommendations)
    # ========================================================================

    def get_all_forecasts_history(self, limit: int = 1000, asset: str = None,
                                   status: str = None, direction: str = None,
                                   risk_level: str = None, days: int = None) -> List[Dict]:
        """Get all forecasts (active + evaluated) with optional filters.

        Returns all recommendations history for display when app reopens.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        conditions = []
        params = []

        if asset and asset != "All":
            conditions.append("asset = ?")
            params.append(asset)

        if status and status.lower() == "active":
            conditions.append("status = 'active'")
        elif status and status.lower() == "evaluated":
            conditions.append("status = 'evaluated'")
        # else: no status filter => show all

        if direction and direction != "All":
            conditions.append("direction = ?")
            params.append(direction.upper())

        if risk_level and risk_level != "All":
            conditions.append("risk_level = ?")
            params.append(risk_level.upper())

        if days and days > 0:
            conditions.append(f"datetime(COALESCE(created_at, due_at)) > datetime('now', '-{int(days)} days')")

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        cursor.execute(f"""
            SELECT * FROM forecasts
            {where}
            ORDER BY datetime(COALESCE(created_at, due_at)) DESC
            LIMIT ?
        """, (*params, limit))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_forecasts_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for all forecasts."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN status = 'evaluated' THEN 1 ELSE 0 END) as evaluated,
                    SUM(CASE WHEN evaluation_result = 'hit' THEN 1 ELSE 0 END) as hits,
                    SUM(CASE WHEN evaluation_result = 'miss' THEN 1 ELSE 0 END) as misses,
                    AVG(confidence) as avg_confidence,
                    MIN(datetime(COALESCE(created_at, due_at))) as first_forecast,
                    MAX(datetime(COALESCE(created_at, due_at))) as last_forecast
                FROM forecasts
            """)
            row = cursor.fetchone()
            if not row:
                return {}
            result = dict(row)
            total_eval = (result.get('hits') or 0) + (result.get('misses') or 0)
            result['accuracy_rate'] = ((result.get('hits') or 0) / total_eval * 100) if total_eval > 0 else 0
            return result
        finally:
            conn.close()

    def is_worker_alive(self, max_stale_seconds: int = 120) -> bool:
        """Check if worker process is alive via DB heartbeat."""
        try:
            status = self.get_worker_status()
            if not status:
                return False
            heartbeat = status.get('last_heartbeat') or status.get('last_heartbeat_at')
            if not heartbeat:
                return False
            hb_str = str(heartbeat).replace('Z', '+00:00')
            try:
                hb_dt = datetime.fromisoformat(hb_str)
            except Exception:
                return False
            if hb_dt.tzinfo:
                now = datetime.now(timezone.utc)
            else:
                now = datetime.now()
            diff = (now - hb_dt).total_seconds()
            return diff < max_stale_seconds
        except Exception:
            return False


# Singleton
_db_instance = None

def get_db() -> Database:
    """Get database instance"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
