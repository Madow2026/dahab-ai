"""
Streamlit-Compatible Background Worker
Runs worker tasks in background threads compatible with Streamlit Cloud
"""

import threading
import time
import traceback
import os
import subprocess
import sys
from datetime import datetime, timezone
import json
import socket

from db.db import get_db
from engine.news_ingestion import get_news_ingestion
from engine.translator import get_translator
from engine.market_data import get_market_data
from engine.impact_engine import get_impact_engine
from engine.forecaster import get_forecaster
from engine.trader import get_auto_trader
from engine.evaluator import get_evaluator
import config


class StreamlitWorker:
    """Background worker compatible with Streamlit Cloud"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.running = False
        self.thread = None
        
        # Components
        self.db = get_db()
        self.news_ingestion = get_news_ingestion()
        self.translator = get_translator()
        self.market_data = get_market_data()
        self.impact_engine = get_impact_engine()
        self.forecaster = get_forecaster()
        self.trader = get_auto_trader()
        self.evaluator = get_evaluator()
        
        # Timestamps for rate limiting
        self.last_news_fetch = 0
        self.last_price_fetch = 0
        self.last_forecast_eval = 0
        self.last_trade_check = 0
        
        # Set global network timeout
        try:
            socket.setdefaulttimeout(15)
        except Exception:
            pass
    
    def start(self):
        """Start background worker thread"""
        with self._lock:
            if self.running:
                return
            
            self.running = True
            self.thread = threading.Thread(target=self._worker_loop, daemon=True, name="streamlit-worker")
            self.thread.start()
            print("✅ Streamlit Worker started")
    
    def stop(self):
        """Stop background worker"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def _worker_loop(self):
        """Main worker loop running in background"""
        cycle_count = 0
        
        while self.running:
            try:
                cycle_count += 1
                cycle_start = time.time()
                
                # Update heartbeat
                try:
                    self.db.update_worker_heartbeat()
                except Exception:
                    pass
                
                # Process news
                self._safe_run('News', self._process_news)
                
                # Update prices
                self._safe_run('Prices', self._update_prices)
                
                # Generate forecasts FIRST
                self._safe_run('Forecasts', self._generate_forecasts)
                
                # Execute auto-trades BEFORE evaluation (so forecasts are still 'active')
                self._safe_run('Auto Trading', self._execute_auto_trades)
                
                # Evaluate forecasts AFTER trading has had a chance
                self._safe_run('Forecast Eval', self._evaluate_forecasts)
                
                # Evaluate trades
                self._safe_run('Trade Eval', self._evaluate_trades)
                
                # Monitor trades
                self._safe_run('Trade Monitor', self._monitor_open_trades)
                
                # Check risk limits
                self._safe_run('Risk Limits', self._check_risk_limits)
                
                # Update heartbeat with cycle duration
                cycle_duration = time.time() - cycle_start
                try:
                    self.db.update_worker_heartbeat(cycle_duration)
                    self.db.update_worker_success(cycle_duration)
                except Exception:
                    pass
                
                # Sleep until next cycle
                sleep_time = max(config.WORKER_CYCLE_INTERVAL - cycle_duration, 0)
                time.sleep(sleep_time)
                
            except Exception as e:
                print(f"❌ Worker cycle error: {e}")
                try:
                    self.db.log('ERROR', 'StreamlitWorker', f'Cycle error: {traceback.format_exc()}')
                    self.db.update_worker_last_error(traceback.format_exc())
                except Exception:
                    pass
                time.sleep(5)
    
    def _safe_run(self, name: str, func):
        """Safely run a function with error handling"""
        try:
            func()
        except Exception as e:
            print(f"⚠️ {name} error: {e}")
            try:
                self.db.log('WARNING', 'StreamlitWorker', f'{name} error: {str(e)}')
            except Exception:
                pass
    
    def _process_news(self):
        """Fetch and process news"""
        now = time.time()
        if now - self.last_news_fetch < config.NEWS_POLL_INTERVAL:
            return
        
        self.last_news_fetch = now
        
        # Fetch news
        news_items = self.news_ingestion.fetch_all_news()
        
        if not news_items:
            return
        
        print(f"📰 Fetched {len(news_items)} news items")
        
        # Process each news item
        for item in news_items:
            try:
                # Translate
                translated = self.translator.translate_news({
                    'title_en': item['title_en'],
                    'body_en': item['body_en']
                })
                title_ar = translated['title_ar']
                body_ar = translated['body_ar']
                
                # Impact analysis
                impact_analysis = self.impact_engine.analyze_news({
                    'title_en': item['title_en'],
                    'body_en': item['body_en']
                })
                
                # Store in database
                self.db.insert_news({
                    'source': item['source'],
                    'url': item['url'],
                    'url_hash': item['url_hash'],
                    'title_en': item['title_en'],
                    'title_ar': title_ar,
                    'body_en': item['body_en'],
                    'body_ar': body_ar,
                    'published_at': item.get('published_at'),
                    'fetched_at': item['fetched_at'],
                    'source_reliability': item['source_reliability'],
                    'category': impact_analysis['category'],
                    'affected_assets': impact_analysis.get('affected_assets', []),
                    'sentiment': impact_analysis['sentiment'],
                    'impact_level': impact_analysis['impact_level'],
                    'impact_analysis': str(impact_analysis)
                })
                
            except Exception as e:
                print(f"Error processing news: {e}")
                continue
    
    def _update_prices(self):
        """Update market prices"""
        now = time.time()
        if now - self.last_price_fetch < config.PRICE_POLL_INTERVAL:
            return
        
        self.last_price_fetch = now
        
        try:
            prices = self.market_data.fetch_all_prices()
        except Exception as e:
            print(f"Price update error: {e}")
    
    def _evaluate_forecasts(self):
        """Evaluate due forecasts"""
        now = time.time()
        if now - self.last_forecast_eval < config.FORECAST_EVAL_INTERVAL:
            return
        
        self.last_forecast_eval = now
        
        try:
            evaluated_count = self.db.evaluate_due_forecasts()
            if evaluated_count > 0:
                print(f"✅ Evaluated {evaluated_count} forecasts")
        except Exception as e:
            print(f"Forecast evaluation error: {e}")
    
    def _generate_forecasts(self):
        """Generate forecasts from recent news"""
        try:
            # Best-effort current prices (cached or last known from DB)
            # Build this first so we can create baseline forecasts even when there is no news.
            current_prices = {}
            try:
                for asset_name in config.ASSETS.keys():
                    price_data = None
                    try:
                        price_data = self.market_data.get_cached_price(asset_name)
                    except Exception:
                        price_data = None

                    if not price_data:
                        try:
                            last_known = self.db.get_latest_price(asset_name)
                            if last_known and last_known.get('price') is not None:
                                price_data = {
                                    'price': float(last_known.get('price')),
                                    'timestamp': last_known.get('timestamp'),
                                    'stale': True,
                                }
                        except Exception:
                            price_data = None

                    if price_data:
                        current_prices[asset_name] = price_data
            except Exception:
                current_prices = {}

            # Ensure Gold continuously gets forecasts for every configured horizon.
            # News mapping may not always produce long horizons; this baseline path guarantees coverage.
            try:
                if getattr(config, 'ENABLE_MULTI_HORIZON_RECOMMENDATIONS', False) and getattr(config, 'RECOMMENDATION_HORIZONS', None):
                    asset = 'Gold'
                    price_data = current_prices.get(asset)
                    if not price_data:
                        try:
                            last_known = self.db.get_latest_price(asset)
                            if last_known and last_known.get('price') is not None:
                                price_data = {'price': float(last_known.get('price')), 'timestamp': last_known.get('timestamp'), 'stale': True}
                                current_prices[asset] = price_data
                        except Exception:
                            price_data = None

                    if price_data and price_data.get('price') is not None:
                        expected = [(str(k), int(v)) for k, v in (config.RECOMMENDATION_HORIZONS or {}).items()]

                        # Create recurring baselines per horizon.
                        # Rule:
                        # - If no forecast exists for a horizon => create one
                        # - If the latest forecast is due (due_at <= now) => create a new one (restart that horizon)
                        # - Cooldown prevents duplicates across fast worker cycles
                        dt_expr = "datetime(replace(substr(COALESCE(created_at, due_at),1,19),'T',' '))"

                        def _parse_iso_dt(value):
                            if not value:
                                return None
                            try:
                                s = str(value).strip().replace('Z', '+00:00')
                                dt = datetime.fromisoformat(s)
                                if dt.tzinfo is None:
                                    dt = dt.replace(tzinfo=timezone.utc)
                                return dt
                            except Exception:
                                return None

                        conn = self.db.get_connection()
                        cur = conn.cursor()
                        inserted = 0

                        for hk, hm in expected:
                            try:
                                # Cooldown: short horizons can restart quickly; long ones slower.
                                if int(hm) <= 60:
                                    cooldown_min = 2
                                elif int(hm) <= 12 * 60:
                                    cooldown_min = 10
                                else:
                                    cooldown_min = 30

                                # Look at the latest forecast for this horizon.
                                cur.execute(
                                    f"""
                                    SELECT created_at, due_at, status
                                    FROM forecasts
                                    WHERE asset = ?
                                      AND (COALESCE(horizon_key,'') = ? OR COALESCE(horizon_minutes,0) = ?)
                                    ORDER BY {dt_expr} DESC, id DESC
                                    LIMIT 1
                                    """,
                                    (asset, hk, int(hm)),
                                )
                                row = cur.fetchone()
                                now_dt = datetime.now(timezone.utc)

                                if row:
                                    created_dt = _parse_iso_dt(row[0])
                                    due_dt = _parse_iso_dt(row[1])
                                    status = str(row[2] or '').lower()

                                    # If we are still before due time, we keep the current cycle running.
                                    if due_dt is not None and due_dt > now_dt:
                                        continue

                                    # If due time passed but we just created something recently, avoid duplicates.
                                    if created_dt is not None:
                                        age_sec = (now_dt - created_dt).total_seconds()
                                        if age_sec < float(cooldown_min) * 60.0:
                                            continue

                                    # If due is missing (shouldn't happen), still allow periodic refresh.
                                    # Also if it's evaluated/expired/active-but-due, we restart.
                                    _ = status  # (kept for readability)

                                synthetic_news = {
                                    'id': None,
                                    'fetched_at': datetime.utcnow().isoformat(),
                                    'published_at': None,
                                    'title_en': 'Baseline Gold Forecast',
                                }
                                analysis = {
                                    'category': 'general',
                                    'sentiment': 'neutral',
                                    'impact_level': 'LOW',
                                    'confidence': 35.0,
                                    'affected_assets': [asset],
                                }

                                # Direction hint so baseline predictions don't stay NEUTRAL (which yields predicted ~= current).
                                try:
                                    ch = None
                                    if isinstance(price_data, dict):
                                        ch = price_data.get('change')
                                        if ch is None and price_data.get('previous_close') is not None and price_data.get('price') is not None:
                                            ch = float(price_data.get('price')) - float(price_data.get('previous_close'))
                                    if ch is not None:
                                        ch = float(ch)
                                        if ch > 0:
                                            analysis['direction_hint'] = 'UP'
                                            analysis['sentiment'] = 'positive'
                                        elif ch < 0:
                                            analysis['direction_hint'] = 'DOWN'
                                            analysis['sentiment'] = 'negative'
                                except Exception:
                                    pass

                                # Generate all horizons then keep only the requested one.
                                forecasts = self.forecaster.generate_forecasts(synthetic_news, analysis, {asset: price_data})
                                for f in forecasts or []:
                                    f_hk = str(f.get('horizon_key') or '').strip()
                                    if str(f.get('asset') or '') != asset:
                                        continue
                                    if f_hk != hk:
                                        continue
                                    try:
                                        # Tag baseline to keep auditability.
                                        try:
                                            tags = {}
                                            rt = f.get('reasoning_tags')
                                            if rt:
                                                tags = json.loads(rt) if isinstance(rt, str) else (rt or {})
                                            if isinstance(tags, dict):
                                                tags['baseline'] = True
                                                tags['baseline_restart'] = True
                                                tags['baseline_cooldown_min'] = int(cooldown_min)
                                                f['reasoning_tags'] = json.dumps(tags, ensure_ascii=False)
                                        except Exception:
                                            pass

                                        f['reasoning'] = f.get('reasoning') or 'Baseline forecast (no specific news)'
                                        self.db.insert_forecast(f)
                                        inserted += 1
                                    except Exception:
                                        pass
                                    break
                            except Exception:
                                continue

                        try:
                            conn.close()
                        except Exception:
                            pass

                        if inserted:
                            print(f"🟡 Baseline: inserted {inserted} recurring Gold forecasts")
            except Exception:
                pass

            # Primary: unprocessed news
            recent_news = self.db.get_unprocessed_news(limit=10) or []

            # Backfill mode: also consider recent news to fill missing horizons
            try:
                backfill_news = self.db.get_recent_news(limit=20) or []
            except Exception:
                backfill_news = []

            # Deduplicate by id while preserving unprocessed priority
            by_id = {}
            for n in recent_news:
                if n and n.get('id') is not None:
                    by_id[n['id']] = n
            for n in backfill_news:
                if n and n.get('id') is not None and n['id'] not in by_id:
                    by_id[n['id']] = n

            news_batch = list(by_id.values())
            if not news_batch:
                return

            # Read existing forecasts per news_id once (to avoid duplicates)
            def _existing_keys_for_news(news_id: int):
                try:
                    conn = self.db.get_connection()
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT asset, COALESCE(horizon_key, ''), COALESCE(horizon_minutes, 0) FROM forecasts WHERE news_id = ?",
                        (news_id,),
                    )
                    rows = cur.fetchall()
                    conn.close()
                    keys = set()
                    for r in rows or []:
                        asset = (r[0] or '').strip()
                        hk = (r[1] or '').strip()
                        hm = int(r[2] or 0)
                        keys.add((asset, hk if hk else str(hm)))
                    return keys
                except Exception:
                    try:
                        conn.close()
                    except Exception:
                        pass
                    return set()

            for news_item in news_batch:
                inserted = 0
                try:
                    # Build analysis from stored fields
                    affected_assets = news_item.get('affected_assets') or []
                    if isinstance(affected_assets, str):
                        affected_assets = [a.strip() for a in affected_assets.split(',') if a.strip()]
                    elif not isinstance(affected_assets, list):
                        affected_assets = []

                    # Normalize and ensure Gold is included for macro categories that typically affect Gold.
                    affected_assets = [str(a).strip() for a in affected_assets if str(a).strip()]
                    category = (news_item.get('category') or 'general')
                    gold_relevant = {
                        'interest_rates',
                        'inflation',
                        'employment',
                        'gdp',
                        'geopolitics',
                        'general',
                    }
                    if (category in gold_relevant) and ('Gold' not in affected_assets):
                        affected_assets.append('Gold')

                    # If still empty, default to Gold (keeps dashboard horizons continuously populated).
                    if not affected_assets:
                        affected_assets = ['Gold']

                    analysis = {
                        'category': category,
                        'sentiment': (news_item.get('sentiment') or 'neutral'),
                        'impact_level': (news_item.get('impact_level') or 'LOW'),
                        'confidence': float(news_item.get('confidence') or 50.0),
                        'affected_assets': affected_assets,
                    }

                    # Keep baseline-level confidence when we had to infer assets.
                    try:
                        if news_item.get('affected_assets') in (None, '', []):
                            analysis['confidence'] = min(float(analysis.get('confidence') or 35.0), 35.0)
                    except Exception:
                        pass

                    forecasts = self.forecaster.generate_forecasts(news_item, analysis, current_prices)

                    existing = _existing_keys_for_news(int(news_item.get('id') or 0))
                    for forecast in forecasts or []:
                        try:
                            # Skip if this horizon already exists for this news+asset
                            asset = str(forecast.get('asset') or '').strip()
                            hk = str(forecast.get('horizon_key') or '').strip()
                            hm = str(int(forecast.get('horizon_minutes') or 0))
                            k = (asset, hk if hk else hm)
                            if k in existing:
                                continue

                            self.db.insert_forecast(forecast)
                            inserted += 1
                            existing.add(k)
                        except Exception as e:
                            print(f"Error inserting forecast: {e}")
                            continue

                    if inserted:
                        try:
                            a = forecasts[0].get('asset') if forecasts else ''
                            d = forecasts[0].get('direction') if forecasts else ''
                            print(f"🎯 Generated {inserted} forecasts (e.g., {a} {d})")
                        except Exception:
                            print(f"🎯 Generated {inserted} forecasts")

                except Exception as e:
                    print(f"Error generating forecasts: {e}")
                finally:
                    # Mark news processed only if it was originally unprocessed.
                    if news_item.get('id') in [n.get('id') for n in recent_news]:
                        try:
                            self.db.mark_news_processed(news_item['id'])
                        except Exception:
                            pass
                    
        except Exception as e:
            print(f"Forecast generation error: {e}")
    
    def _execute_auto_trades(self):
        """Execute auto-trades based on recent forecasts"""
        try:
            # Reset daily trading pause if new day
            try:
                portfolio = self.db.get_portfolio()
                if portfolio:
                    from datetime import date
                    reset_date = portfolio.get('daily_reset_date', '')
                    if reset_date != date.today().isoformat():
                        self.db.reset_daily_pnl()
                        print('📅 Daily P&L reset - trading unpaused')
                    elif portfolio.get('is_trading_paused'):
                        print('⏸️ Trading paused (daily loss limit). Will reset tomorrow.')
                        return
            except Exception as e:
                print(f'Portfolio check error: {e}')
            
            # Get recent active forecasts (not yet traded)
            recent_forecasts = self.db.get_active_forecasts(limit=50)
            
            if not recent_forecasts:
                print('📭 No active forecasts for auto-trading')
                return
            
            print(f'📊 Found {len(recent_forecasts)} active forecasts for trading')
            
            # Get current prices
            current_prices = {}
            try:
                prices = self.market_data.fetch_all_prices()
                for asset, price_data in prices.items():
                    if price_data and price_data.get('price'):
                        current_prices[asset] = price_data['price']
            except Exception:
                # Fallback to cached or last known prices
                for forecast in recent_forecasts:
                    asset = forecast.get('asset')
                    if asset and asset not in current_prices:
                        try:
                            cached = self.market_data.get_cached_price(asset)
                            if cached and cached.get('price'):
                                current_prices[asset] = cached['price']
                            else:
                                last = self.db.get_latest_price(asset)
                                if last and last.get('price'):
                                    current_prices[asset] = float(last['price'])
                        except Exception:
                            pass
            
            trades_executed = 0
            skipped_reasons = {}
            
            for forecast in recent_forecasts:
                try:
                    asset = forecast.get('asset')
                    if not asset:
                        skipped_reasons['no_asset'] = skipped_reasons.get('no_asset', 0) + 1
                        continue
                    
                    if asset not in current_prices:
                        # Try DB fallback
                        try:
                            db_price = self.db.get_latest_price(asset)
                            if db_price and db_price.get('price'):
                                current_prices[asset] = float(db_price['price'])
                            else:
                                skipped_reasons['no_price'] = skipped_reasons.get('no_price', 0) + 1
                                continue
                        except Exception:
                            skipped_reasons['no_price'] = skipped_reasons.get('no_price', 0) + 1
                            continue
                    
                    current_price = current_prices[asset]
                    
                    # Check if already have a trade for this forecast
                    try:
                        trades = self.db.get_trades_by_forecast_id(forecast['id'])
                        if trades:
                            skipped_reasons['already_traded'] = skipped_reasons.get('already_traded', 0) + 1
                            continue
                    except Exception:
                        pass  # If method fails, proceed (don't block trading)
                    
                    # Check forecast fields
                    confidence = forecast.get('confidence', 0)
                    direction = forecast.get('direction', 'NEUTRAL')
                    
                    if direction == 'NEUTRAL':
                        skipped_reasons['neutral'] = skipped_reasons.get('neutral', 0) + 1
                        continue
                    
                    if confidence < config.MIN_CONFIDENCE_FOR_TRADE:
                        skipped_reasons['low_confidence'] = skipped_reasons.get('low_confidence', 0) + 1
                        continue
                    
                    # Evaluate if should trade
                    trade = self.trader.evaluate_forecast_for_trading(forecast, current_price)
                    
                    if trade:
                        # Execute trade
                        try:
                            trade_id = self.db.insert_paper_trade(trade)
                            if trade_id:
                                # Increment trade counter
                                try:
                                    self.db.increment_trade_counter()
                                except Exception:
                                    pass
                                trades_executed += 1
                                print(f"🎯 Auto-trade executed: {trade['asset']} {trade['side']} @ ${current_price:.2f} (conf: {confidence:.0f}%)")
                        except Exception as e:
                            print(f"Trade insert error: {e}")
                    else:
                        skipped_reasons['guardrails'] = skipped_reasons.get('guardrails', 0) + 1
                
                except Exception as e:
                    print(f"Error evaluating forecast {forecast.get('id')}: {e}")
                    continue
            
            if trades_executed > 0:
                print(f"✅ Executed {trades_executed} auto-trades")
            else:
                print(f"⚠️ 0 trades executed. Skipped: {skipped_reasons}")
        
        except Exception as e:
            print(f"Auto-trading error: {e}")
    
    def _evaluate_trades(self):
        """Evaluate closed trades"""
        try:
            # This would be implemented if needed
            pass
        except Exception as e:
            print(f"Trade evaluation error: {e}")
    
    def _monitor_open_trades(self):
        """Monitor and manage open trades"""
        now = time.time()
        if now - self.last_trade_check < config.TRADE_CHECK_INTERVAL:
            return
        
        self.last_trade_check = now
        
        try:
            # Get open trades from DB
            open_trades = self.db.get_open_paper_trades()
            
            for trade in open_trades:
                try:
                    # Check if should close based on SL/TP
                    self.trader.check_trade_exit(trade)
                except Exception as e:
                    print(f"Error checking trade {trade.get('id')}: {e}")
        except Exception as e:
            print(f"Trade monitoring error: {e}")
    
    def _check_risk_limits(self):
        """Check risk limits"""
        try:
            # Circuit breaker check
            portfolio = self.db.get_paper_portfolio()
            if portfolio:
                daily_pnl_percent = portfolio.get('daily_pnl_percent', 0)
                if daily_pnl_percent <= -config.DAILY_MAX_LOSS_PERCENT:
                    print(f"⚠️ Circuit breaker triggered: {daily_pnl_percent:.2f}% daily loss")
        except Exception as e:
            print(f"Risk check error: {e}")


# Singleton instance
_worker = None

def get_streamlit_worker() -> StreamlitWorker:
    """Get singleton worker instance"""
    global _worker
    if _worker is None:
        _worker = StreamlitWorker()
    return _worker


def _start_external_worker() -> bool:
    """Start worker.py as a fully detached background process.

    This allows the worker to keep running even when Streamlit is closed,
    ensuring continuous recommendation generation and evaluation.
    """
    worker_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'worker.py')
    if not os.path.exists(worker_script):
        return False

    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'worker_output.log')

    try:
        if os.name == 'nt':
            # Windows: fully detached process that survives parent exit
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            fh = open(log_file, 'a', encoding='utf-8')
            subprocess.Popen(
                [sys.executable, worker_script],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
                stdout=fh,
                stderr=subprocess.STDOUT,
            )
        else:
            # Unix: start_new_session detaches from parent
            fh = open(log_file, 'a', encoding='utf-8')
            subprocess.Popen(
                [sys.executable, worker_script],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                start_new_session=True,
                stdout=fh,
                stderr=subprocess.STDOUT,
            )
        print("🚀 External worker process launched (persistent)")
        return True
    except Exception as e:
        print(f"⚠️ Failed to start external worker: {e}")
        return False


def ensure_worker_running():
    """Ensure background worker is running (call from Streamlit pages).

    Strategy:
    1. Check if an external worker.py process is already alive (via DB heartbeat)
    2. If not, start worker.py as a detached background process
    3. Fallback to in-process StreamlitWorker thread

    The external worker keeps running even when Streamlit is closed,
    so recommendations continue to be generated and evaluated 24/7.
    """
    db = get_db()

    # 1. Check if external worker is already running
    if db.is_worker_alive(max_stale_seconds=120):
        return  # External worker is handling everything

    # 2. Try to start external worker process (persistent)
    if _start_external_worker():
        # Give it a moment to start and write first heartbeat
        time.sleep(3)
        if db.is_worker_alive(max_stale_seconds=120):
            return  # External worker started successfully

    # 3. Fallback: in-process worker thread
    worker = get_streamlit_worker()
    if not worker.running:
        worker.start()
