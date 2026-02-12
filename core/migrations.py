"""SQLite additive migrations for DAHAB AI.

Hard requirements:
- Never delete existing DB data.
- Only use safe, additive migrations (ALTER TABLE ADD COLUMN, CREATE TABLE IF NOT EXISTS).
- Provide compatibility between legacy schema (core/*) and automated schema (db/*).

This module is dependency-free so it can run very early in startup.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Iterable, Tuple


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,)
    )
    return cur.fetchone() is not None


def _get_columns(conn: sqlite3.Connection, table: str) -> Dict[str, str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1]: row[2] for row in cur.fetchall()}


def _add_column(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    cur = conn.cursor()
    cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _ensure_columns(
    conn: sqlite3.Connection, table: str, required: Iterable[Tuple[str, str]]
) -> None:
    if not _table_exists(conn, table):
        return

    existing = _get_columns(conn, table)
    for name, col_type in required:
        if name in existing:
            continue
        _add_column(conn, table, name, col_type)


def migrate_database(db_path: str) -> None:
    """Run all migrations. Safe to run multiple times."""

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")

        # ------------------------------------------------------------------
        # Worker status table (heartbeat + last error)
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS worker_status (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_heartbeat TEXT,
                last_heartbeat_at TEXT,
                last_cycle_seconds REAL,
                last_successful_cycle_at TEXT,
                last_error TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO worker_status (id, last_heartbeat) VALUES (1, NULL)"
        )

        # Ensure additive column exists on older DBs
        _ensure_columns(
            conn,
            "worker_status",
            [
                ("last_successful_cycle_at", "TEXT"),
                ("last_heartbeat_at", "TEXT"),
            ],
        )

        # Backfill last_heartbeat_at from last_heartbeat if needed
        try:
            conn.execute(
                """
                UPDATE worker_status
                SET last_heartbeat_at = last_heartbeat
                WHERE (last_heartbeat_at IS NULL OR last_heartbeat_at = '')
                  AND last_heartbeat IS NOT NULL
                """
            )
        except Exception:
            pass

        # ------------------------------------------------------------------
        # Per-page last-seen state (for NEW badges)
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_page_state (
                page_key TEXT PRIMARY KEY,
                last_seen_at TEXT,
                last_seen_id INTEGER
            )
            """
        )

        # ------------------------------------------------------------------
        # System logs (needed for safety triggers; created in db.init too)
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS system_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                module TEXT NOT NULL,
                message TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON system_logs(timestamp DESC)")

        # ------------------------------------------------------------------
        # DB meta (integrity + runtime state)
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS db_meta (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
            """
        )

        # ------------------------------------------------------------------
        # Recommendation history (append-only, never deleted)
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recommendation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_id INTEGER UNIQUE,
                news_id INTEGER,
                asset TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL,
                horizon_minutes INTEGER,
                horizon_key TEXT,
                predicted_price REAL,
                confidence REAL,
                reasoning_tags TEXT,
                created_at TEXT,
                due_at TEXT,
                actual_price REAL,
                actual_time TEXT,
                accuracy_pct REAL,
                abs_error REAL,
                pct_error REAL,
                evaluation_result TEXT,
                evaluated_at TEXT,
                FOREIGN KEY (forecast_id) REFERENCES forecasts (id)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rechist_asset_due ON recommendation_history(asset, due_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rechist_eval ON recommendation_history(evaluated_at)")

        # ------------------------------------------------------------------
        # Evaluation summary (aggregated metrics, append-only)
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluation_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                computed_at TEXT NOT NULL,
                window_days INTEGER NOT NULL,
                asset TEXT NOT NULL,
                horizon_minutes INTEGER,
                horizon_key TEXT,
                n_total INTEGER NOT NULL,
                n_hit INTEGER NOT NULL,
                directional_accuracy REAL,
                mae REAL,
                mape REAL,
                avg_confidence REAL,
                calibration_score REAL,
                weighted_overall_accuracy REAL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_evalsum_computed ON evaluation_summary(computed_at DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_evalsum_asset_h ON evaluation_summary(asset, horizon_minutes)")

        # ------------------------------------------------------------------
        # Optional news archival table (manual use only; never auto-delete news)
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_archive (
                id INTEGER PRIMARY KEY,
                source TEXT,
                url TEXT,
                title_en TEXT,
                body_en TEXT,
                title_ar TEXT,
                body_ar TEXT,
                published_at TEXT,
                fetched_at TEXT,
                category TEXT,
                sentiment TEXT,
                impact_level TEXT,
                confidence REAL,
                affected_assets TEXT,
                source_reliability REAL,
                archived_at TEXT NOT NULL,
                archive_reason TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_news_archive_archived_at ON news_archive(archived_at)")

        # ------------------------------------------------------------------
        # Calibration stats (rolling accuracy -> confidence weighting)
        # ------------------------------------------------------------------
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS calibration_stats (
                asset TEXT NOT NULL,
                horizon_minutes INTEGER NOT NULL,
                news_category TEXT,
                news_sentiment TEXT,
                n_total INTEGER NOT NULL DEFAULT 0,
                n_hit INTEGER NOT NULL DEFAULT 0,
                rolling_accuracy REAL,
                weight_multiplier REAL,
                updated_at TEXT,
                PRIMARY KEY (asset, horizon_minutes, news_category, news_sentiment)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_calib_asset_h ON calibration_stats(asset, horizon_minutes)")

        # ------------------------------------------------------------------
        # Safety triggers: log accidental deletions (never auto-delete data)
        # ------------------------------------------------------------------
        # Note: triggers only log; they do not block operations.
        try:
            if _table_exists(conn, 'news'):
                conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS trg_news_delete
                    AFTER DELETE ON news
                    BEGIN
                        INSERT INTO system_logs (timestamp, level, module, message)
                        VALUES (datetime('now'), 'ERROR', 'DB', 'DELETE on news detected: id=' || OLD.id || ' source=' || COALESCE(OLD.source,'') || ' url=' || COALESCE(OLD.url,''));
                    END;
                    """
                )
            if _table_exists(conn, 'forecasts'):
                conn.execute(
                    """
                    CREATE TRIGGER IF NOT EXISTS trg_forecasts_delete
                    AFTER DELETE ON forecasts
                    BEGIN
                        INSERT INTO system_logs (timestamp, level, module, message)
                        VALUES (datetime('now'), 'ERROR', 'DB', 'DELETE on forecasts detected: id=' || OLD.id || ' asset=' || COALESCE(OLD.asset,''));
                    END;
                    """
                )
        except Exception:
            pass

        # ------------------------------------------------------------------
        # Forecasts compatibility columns
        # ------------------------------------------------------------------
        if _table_exists(conn, "forecasts"):
            required_forecast_cols = [
                # Canonical (new)
                ("news_id", "INTEGER"),
                ("asset", "TEXT"),
                ("direction", "TEXT"),
                ("confidence", "REAL"),
                ("risk_level", "TEXT"),
                ("horizon_minutes", "INTEGER"),
                ("created_at", "TEXT"),
                ("due_at", "TEXT"),
                ("status", "TEXT"),
                ("evaluation_result", "TEXT"),
                ("actual_return", "REAL"),
                ("evaluated_at", "TEXT"),

                # Evaluation enrichment (direction-only forecasts still benefit from realized move/error stats)
                ("actual_price", "REAL"),
                ("actual_time", "TEXT"),
                ("direction_correct", "INTEGER"),
                ("abs_error", "REAL"),
                ("pct_error", "REAL"),
                ("evaluation_quality", "TEXT"),

                # Compatibility (legacy / UI)
                ("forecast_time", "TEXT"),
                ("evaluation_time", "TEXT"),
                ("expected_direction", "TEXT"),
                ("confidence_level", "REAL"),
                ("price_change_percent", "REAL"),
                ("is_accurate", "INTEGER"),

                # Multi-horizon recommendation extensions (additive)
                ("horizon_key", "TEXT"),
                ("predicted_price", "REAL"),
                ("reasoning_tags", "TEXT"),
                ("news_category", "TEXT"),
                ("news_sentiment", "TEXT"),
                ("impact_level", "TEXT"),
                ("recommendation_group_id", "TEXT"),
                ("pred_abs_error", "REAL"),
                ("pred_pct_error", "REAL"),
                ("expired_at", "TEXT"),
            ]
            _ensure_columns(conn, "forecasts", required_forecast_cols)

        # ------------------------------------------------------------------
        # News importance classification (event-driven recommendation triggers)
        # ------------------------------------------------------------------
        if _table_exists(conn, 'news'):
            _ensure_columns(
                conn,
                'news',
                [
                    ('importance_score', 'REAL'),
                    ('importance_level', 'TEXT'),
                ],
            )

            cols = _get_columns(conn, "forecasts")

            # created_at <-> forecast_time sync
            if "created_at" in cols and "forecast_time" in cols:
                conn.execute(
                    """
                    UPDATE forecasts
                    SET forecast_time = created_at
                    WHERE (forecast_time IS NULL OR forecast_time = '')
                      AND created_at IS NOT NULL
                    """
                )
                conn.execute(
                    """
                    UPDATE forecasts
                    SET created_at = forecast_time
                    WHERE (created_at IS NULL OR created_at = '')
                      AND forecast_time IS NOT NULL
                    """
                )

            # evaluated_at <-> evaluation_time sync
            if "evaluated_at" in cols and "evaluation_time" in cols:
                conn.execute(
                    """
                    UPDATE forecasts
                    SET evaluation_time = evaluated_at
                    WHERE (evaluation_time IS NULL OR evaluation_time = '')
                      AND evaluated_at IS NOT NULL
                    """
                )
                conn.execute(
                    """
                    UPDATE forecasts
                    SET evaluated_at = evaluation_time
                    WHERE (evaluated_at IS NULL OR evaluated_at = '')
                      AND evaluation_time IS NOT NULL
                    """
                )

            # Backfill due_at when missing (created_at + horizon_minutes)
            if "due_at" in cols and "created_at" in cols and "horizon_minutes" in cols:
                # Compute in Python per-row to avoid SQLite datetime format issues.
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT id, created_at, horizon_minutes
                    FROM forecasts
                    WHERE (due_at IS NULL OR due_at = '')
                      AND created_at IS NOT NULL
                      AND horizon_minutes IS NOT NULL
                    """
                )
                rows = cur.fetchall()
                for row in rows:
                    try:
                        created = datetime.fromisoformat(row[1])
                        due = created + timedelta(minutes=int(row[2]))
                        conn.execute(
                            "UPDATE forecasts SET due_at = ? WHERE id = ?",
                            (due.isoformat(), row[0]),
                        )
                    except Exception:
                        continue

            # Normalize direction from expected_direction when missing
            if "direction" in cols and "expected_direction" in cols:
                conn.execute(
                    """
                    UPDATE forecasts
                    SET direction = CASE
                        WHEN UPPER(TRIM(expected_direction)) LIKE 'UP%' THEN 'UP'
                        WHEN UPPER(TRIM(expected_direction)) LIKE 'DOWN%' THEN 'DOWN'
                        WHEN UPPER(TRIM(expected_direction)) LIKE 'NEUTRAL%' THEN 'NEUTRAL'
                        ELSE UPPER(TRIM(expected_direction))
                    END
                    WHERE (direction IS NULL OR direction = '')
                      AND expected_direction IS NOT NULL
                    """
                )

            # Confidence from confidence_level when missing
            if "confidence" in cols and "confidence_level" in cols:
                conn.execute(
                    """
                    UPDATE forecasts
                    SET confidence = confidence_level
                    WHERE confidence IS NULL
                      AND confidence_level IS NOT NULL
                    """
                )

            # Backfill actual_return from legacy price_change_percent
            if "actual_return" in cols and "price_change_percent" in cols:
                conn.execute(
                    """
                    UPDATE forecasts
                    SET actual_return = price_change_percent
                    WHERE actual_return IS NULL
                      AND price_change_percent IS NOT NULL
                    """
                )

            # Backfill evaluation_result from legacy is_accurate
            if "evaluation_result" in cols and "is_accurate" in cols:
                conn.execute(
                    """
                    UPDATE forecasts
                    SET evaluation_result = CASE
                        WHEN is_accurate = 1 THEN 'hit'
                        WHEN is_accurate = 0 THEN 'miss'
                        ELSE evaluation_result
                    END
                    WHERE evaluation_result IS NULL
                      AND is_accurate IS NOT NULL
                    """
                )

            # Ensure status is set when evaluated
            if "status" in cols:
                if "evaluated_at" in cols:
                    conn.execute(
                        """
                        UPDATE forecasts
                        SET status = 'evaluated'
                        WHERE (status IS NULL OR status = '')
                          AND evaluated_at IS NOT NULL
                        """
                    )
                elif "evaluation_time" in cols:
                    conn.execute(
                        """
                        UPDATE forecasts
                        SET status = 'evaluated'
                        WHERE (status IS NULL OR status = '')
                          AND evaluation_time IS NOT NULL
                        """
                    )

        # ------------------------------------------------------------------
        # Asset naming unification: USD -> USD Index
        # ------------------------------------------------------------------
        for table in ("prices", "forecasts", "paper_trades"):
            if _table_exists(conn, table):
                tcols = _get_columns(conn, table)
                if "asset" in tcols:
                    conn.execute(
                        f"UPDATE {table} SET asset = 'USD Index' WHERE asset = 'USD'"
                    )

        conn.commit()
    finally:
        conn.close()
