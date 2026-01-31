"""
Automated Worker Process
Runs continuously to automate the entire news→forecast→trade→evaluate pipeline
"""

import time
import signal
import sys
import traceback
from datetime import datetime
from typing import Dict
import argparse
import os
import socket
import threading


class _SingleInstanceLock:
    """Cross-process lock to prevent multiple workers.

    Uses an OS-level file lock on Windows via msvcrt.
    """

    def __init__(self, lock_path: str):
        self.lock_path = lock_path
        self._fh = None

    def acquire(self) -> bool:
        try:
            # Keep file handle open for the lifetime of the process.
            self._fh = open(self.lock_path, 'a+', encoding='utf-8')
            self._fh.seek(0)

            if os.name == 'nt':
                import msvcrt

                try:
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    return False
            else:
                import fcntl

                try:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    return False

            # Write basic metadata (best-effort)
            try:
                self._fh.truncate(0)
                self._fh.write(f"pid={os.getpid()} started_at={datetime.now().isoformat()}\n")
                self._fh.flush()
            except Exception:
                pass

            return True
        except Exception:
            return False

    def release(self) -> None:
        try:
            if not self._fh:
                return
            if os.name == 'nt':
                import msvcrt

                try:
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                except Exception:
                    pass
            else:
                import fcntl

                try:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
        finally:
            try:
                self._fh.close()
            except Exception:
                pass
            self._fh = None

import config

from config import (
    NEWS_POLL_INTERVAL,
    PRICE_POLL_INTERVAL,
    FORECAST_EVAL_INTERVAL,
    TRADE_CHECK_INTERVAL,
    WORKER_CYCLE_INTERVAL
)
from db.db import get_db
from engine.news_ingestion import get_news_ingestion
from engine.translator import get_translator
from engine.market_data import get_market_data
from engine.impact_engine import get_impact_engine
from engine.forecaster import get_forecaster
from engine.trader import get_auto_trader
from engine.evaluator import get_evaluator


class WorkerProcess:
    """Automated worker that runs the entire pipeline"""
    
    def __init__(self):
        self.running = True
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
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._shutdown_handler)
        signal.signal(signal.SIGTERM, self._shutdown_handler)

        # Independent heartbeat thread
        self._hb_stop = threading.Event()
        self._hb_thread: threading.Thread | None = None

        # Single instance lock
        lock_path = os.path.join(os.path.dirname(__file__), 'worker.lock')
        self._instance_lock = _SingleInstanceLock(lock_path)
    
    def _shutdown_handler(self, signum, frame):
        """Handle graceful shutdown"""
        print("\n🛑 Shutdown signal received. Cleaning up...")
        self.db.log('INFO', 'Worker', 'Shutdown signal received')
        self.running = False
        try:
            self._hb_stop.set()
        except Exception:
            pass
        try:
            self._instance_lock.release()
        except Exception:
            pass
        sys.exit(0)

    def _start_heartbeat_thread(self) -> None:
        if self._hb_thread and self._hb_thread.is_alive():
            return

        def _loop():
            # Update heartbeat every 10 seconds regardless of cycle progress.
            while not self._hb_stop.is_set():
                try:
                    self.db.update_worker_heartbeat()
                except Exception:
                    pass
                # Sleep in small increments so shutdown is responsive.
                self._hb_stop.wait(10)

        self._hb_thread = threading.Thread(target=_loop, name='worker-heartbeat', daemon=True)
        self._hb_thread.start()

    def _run_step(self, name: str, fn, max_seconds: float) -> None:
        """Run a pipeline step with a hard time budget.

        If it errors or times out, log and continue.
        """
        result = {'error': None}

        def _target():
            try:
                fn()
            except Exception:
                result['error'] = traceback.format_exc()

        t = threading.Thread(target=_target, name=f'step-{name}', daemon=True)
        t.start()
        t.join(timeout=max_seconds)

        if t.is_alive():
            msg = f"Step timeout: {name} exceeded {max_seconds:.0f}s (skipping)"
            print(f"   ⚠️ {msg}")
            try:
                self.db.log('WARNING', 'Worker', msg)
            except Exception:
                pass
            return

        if result['error']:
            msg = f"Step error: {name}"
            print(f"   ❌ {msg}")
            try:
                self.db.log('ERROR', 'Worker', f"{msg}: {result['error']}")
            except Exception:
                pass
            try:
                self.db.update_worker_last_error(result['error'])
            except Exception:
                pass
    
    def run(self, cycles: int | None = None):
        """Main worker loop.

        If cycles is provided, runs that many cycles then exits.
        """
        cycle_count = 0

        # Global network timeout safety net (covers deep_translator/yfinance internals too)
        try:
            socket.setdefaulttimeout(15)
        except Exception:
            pass

        # Single instance lock
        if not self._instance_lock.acquire():
            print("❌ Another worker instance is already running. Exiting.")
            try:
                self.db.log('WARNING', 'Worker', 'Another worker instance detected; exiting')
            except Exception:
                pass
            return

        # Start independent heartbeat
        self._start_heartbeat_thread()

        # Now safe to announce startup
        try:
            self.db.log('INFO', 'Worker', 'Worker process started')
        except Exception:
            pass
        print("🚀 DAHAB AI Worker Process Started")
        print("=" * 60)
        print("📊 Automated Pipeline Active:")
        print("   • News Collection → Translation → Impact Analysis")
        print("   • Forecast Generation → Auto Paper Trading")
        print("   • Trade Management → Evaluation")
        print("=" * 60)
        print("\nPress Ctrl+C to stop\n")
        
        while self.running:
            try:
                cycle_count += 1
                cycle_start = time.time()

                # Heartbeat at cycle start (helps UI show "alive" even if later stages fail)
                try:
                    self.db.update_worker_heartbeat()
                except Exception:
                    pass
                
                print(f"\n{'='*60}")
                print(f"🔄 Cycle #{cycle_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'='*60}")
                
                # Watchdog wrapper per step: never allow a single stage to stall the whole worker.
                self._run_step('news', self._process_news, max_seconds=45)
                self._run_step('prices', self._update_prices, max_seconds=45)
                self._run_step('forecast_eval', self._evaluate_forecasts, max_seconds=60)
                self._run_step('forecasts', self._generate_forecasts, max_seconds=30)
                self._run_step('trade_eval', self._evaluate_trades, max_seconds=25)
                self._run_step('trade_monitor', self._monitor_open_trades, max_seconds=20)
                self._run_step('risk_limits', self._check_risk_limits, max_seconds=10)
                
                cycle_duration = time.time() - cycle_start
                sleep_time = max(WORKER_CYCLE_INTERVAL - cycle_duration, 0)

                # Heartbeat at cycle end with duration
                try:
                    self.db.update_worker_heartbeat(cycle_duration)
                except Exception:
                    pass

                # Track last successful cycle separately (diagnostic KPI)
                try:
                    self.db.update_worker_success(cycle_duration)
                except Exception:
                    pass
                
                print(f"\n✅ Cycle complete in {cycle_duration:.1f}s. Sleeping {sleep_time:.0f}s...")
                if cycles is not None and cycle_count >= cycles:
                    self.db.log('INFO', 'Worker', f'Exiting after {cycles} cycles (requested)')
                    break

                time.sleep(sleep_time)
                
            except Exception as e:
                print(f"❌ Error in worker cycle: {e}")
                err = traceback.format_exc()
                self.db.log('ERROR', 'Worker', f'Cycle error: {err}')
                try:
                    self.db.update_worker_last_error(err)
                except Exception:
                    pass
                time.sleep(10)  # Brief pause on error
                continue

        # Cleanup
        try:
            self._hb_stop.set()
        except Exception:
            pass
        try:
            self._instance_lock.release()
        except Exception:
            pass
    
    def _process_news(self):
        """Fetch, translate, and analyze news"""
        now = time.time()
        
        if now - self.last_news_fetch < NEWS_POLL_INTERVAL:
            return
        
        print("\n📰 Processing News...")
        
        try:
            # Fetch news (ingestion layer dedups against DB best-effort)
            news_items = self.news_ingestion.fetch_all_news()
            
            if not news_items:
                print("   No new economic news found")
                self.last_news_fetch = now
                return
            
            print(f"   Found {len(news_items)} new articles")
            
            # Process each news item
            inserted_count = 0
            analyzed_count = 0
            skipped_duplicates = 0
            item_errors = 0

            # Keep this step bounded so it never times out the worker.
            # Insert is cheap; translation/analysis can be slower.
            step_started = time.time()
            time_budget_seconds = 35  # must stay below _run_step('news', ..., 45)
            max_analyzed_per_cycle = 8

            for news in news_items:
                try:
                    # Save to database
                    news_id = self.db.insert_news(news)

                    # Duplicate URL or insert rejected
                    if not news_id:
                        skipped_duplicates += 1
                        continue

                    inserted_count += 1

                    # If we're running out of time, skip heavy work.
                    if (time.time() - step_started) > time_budget_seconds or analyzed_count >= max_analyzed_per_cycle:
                        continue
                    
                    # Translate
                    translated = self.translator.translate_news(news)
                    self.db.update_news_translation(
                        news_id, 
                        translated['title_ar'], 
                        translated['body_ar']
                    )
                    
                    # Analyze impact
                    impact = self.impact_engine.analyze_news(news)

                    # Guarantee at least one affected asset
                    affected_assets = impact.get('affected_assets') or []
                    if not affected_assets:
                        affected_assets = ['USD Index']
                        impact['affected_assets'] = affected_assets
                        impact['confidence'] = min(float(impact.get('confidence', 35.0)), 35.0)
                    
                    # Update with analysis
                    self.db.update_news_analysis(
                        news_id,
                        impact['category'],
                        impact['sentiment'],
                        impact['impact_level'],
                        impact['confidence'],
                        impact.get('affected_assets')
                    )

                    analyzed_count += 1
                    
                except Exception as e:
                    print(f"   Error processing news: {e}")
                    self.db.log('ERROR', 'Worker', f'News item processing error: {traceback.format_exc()}')
                    item_errors += 1
                    continue
            
            remaining = max(0, len(news_items) - inserted_count - skipped_duplicates)
            print(
                f"   ✅ Inserted {inserted_count} | analyzed {analyzed_count} | skipped_duplicates {skipped_duplicates} | errors {item_errors}"
            )
            if remaining > 0:
                print(f"   ⏱️ Deferred {remaining} items (time budget); will continue next cycle")
            try:
                self.db.log(
                    'INFO',
                    'Worker',
                    f'News ingest: inserted={inserted_count} analyzed={analyzed_count} skipped_duplicates={skipped_duplicates} errors={item_errors}',
                )
            except Exception:
                pass
            
        except Exception as e:
            print(f"   ❌ News processing error: {e}")
            self.db.log('ERROR', 'Worker', f'News processing error: {e}')
        
        self.last_news_fetch = now
    
    def _update_prices(self):
        """Update market prices"""
        now = time.time()
        
        if now - self.last_price_fetch < PRICE_POLL_INTERVAL:
            return
        
        print("\n💹 Updating Market Prices...")
        
        try:
            prices = self.market_data.fetch_all_prices()
            
            if prices:
                print(f"   ✅ Updated {len(prices)} asset prices")
            else:
                print("   ⚠️ No prices updated")
            
        except Exception as e:
            print(f"   ❌ Price update error: {e}")
            self.db.log('ERROR', 'Worker', f'Price update error: {e}')
        
        self.last_price_fetch = now
    
    def _generate_forecasts(self):
        """Generate forecasts for unprocessed analyzed news"""
        now = time.time()
        
        # No rate limiting needed - run every cycle
        
        print("\n🎯 Generating Forecasts...")
        
        try:
            # Get unprocessed news with impact analysis
            unprocessed = self.db.get_unprocessed_news()
            
            if not unprocessed:
                print("   No news pending forecast generation")
                self.last_forecast_gen = now
                return
            
            print(f"   Found {len(unprocessed)} analyzed news items")
            
            # Get current prices for forecasting
            current_prices_data = {}
            for asset in ['USD Index', 'Gold', 'Silver', 'Oil', 'Bitcoin']:
                price_row = self.db.get_latest_price(asset)
                if price_row:
                    # Forecaster expects dict-like price_data, but can also accept float.
                    current_prices_data[asset] = {'price': price_row['price'], 'timestamp': price_row.get('timestamp')}
            
            forecast_count = 0
            for news_item in unprocessed:
                try:
                    # Backfill analysis if missing (older rows may have NULL analysis fields)
                    if not news_item.get('category') or not news_item.get('sentiment') or not news_item.get('impact_level') or news_item.get('confidence') is None:
                        try:
                            impact = self.impact_engine.analyze_news(news_item)
                            affected_assets = impact.get('affected_assets') or []
                            if not affected_assets:
                                affected_assets = ['USD Index']
                                impact['affected_assets'] = affected_assets
                                impact['confidence'] = min(float(impact.get('confidence', 35.0)), 35.0)

                            self.db.update_news_analysis(
                                news_item['id'],
                                impact.get('category') or 'general',
                                impact.get('sentiment') or 'neutral',
                                (impact.get('impact_level') or 'LOW'),
                                float(impact.get('confidence', 50.0) or 50.0),
                                impact.get('affected_assets'),
                            )

                            # Keep in-memory dict consistent for this cycle
                            news_item['category'] = impact.get('category') or 'general'
                            news_item['sentiment'] = impact.get('sentiment') or 'neutral'
                            news_item['impact_level'] = impact.get('impact_level') or 'LOW'
                            news_item['confidence'] = float(impact.get('confidence', 50.0) or 50.0)
                            news_item['affected_assets'] = impact.get('affected_assets')
                        except Exception:
                            # Don't block forecasting; fall back to defaults below
                            pass

                    # Create analysis dict from news_item
                    affected_assets_str = news_item.get('affected_assets', '')
                    
                    # Handle both string and list formats
                    if isinstance(affected_assets_str, str):
                        affected_assets_list = [a.strip() for a in affected_assets_str.split(',') if a.strip()]
                    else:
                        affected_assets_list = affected_assets_str if isinstance(affected_assets_str, list) else []
                    
                    analysis = {
                        'category': news_item.get('category') or 'general',
                        'sentiment': news_item.get('sentiment') or 'neutral',
                        'impact_level': (news_item.get('impact_level') or 'LOW').upper(),
                        'confidence': float(news_item.get('confidence', 50.0) or 50.0),
                        'affected_assets': affected_assets_list
                    }

                    # Normalize legacy asset names
                    analysis['affected_assets'] = [
                        ('USD Index' if a.strip() == 'USD' else a.strip())
                        for a in analysis.get('affected_assets', [])
                        if str(a).strip()
                    ]

                    # Never allow "skip due to low impact"; always forecast at least one asset.
                    if not analysis['affected_assets']:
                        analysis['affected_assets'] = ['USD Index']
                        analysis['confidence'] = min(analysis['confidence'], 35.0)
                    
                    # Generate forecasts
                    forecasts = self.forecaster.generate_forecasts(news_item, analysis, current_prices_data)

                    inserted_any = False
                    for forecast in forecasts or []:
                        self.db.insert_forecast(forecast)
                        forecast_count += 1
                        inserted_any = True

                    # Mark as processed only after at least one successful insert
                    if inserted_any:
                        self.db.mark_news_processed(news_item['id'])
                    else:
                        self.db.log('WARNING', 'Worker', f"No forecasts inserted for news_id={news_item.get('id')}")
                    
                except Exception as e:
                    print(f"   Error generating forecast: {e}")
                    self.db.log('ERROR', 'Worker', f'Forecast generation error for news_id={news_item.get("id")}: {traceback.format_exc()}')
                    continue
            
            print(f"   ✅ Generated {forecast_count} forecasts")
            self.db.log('INFO', 'Worker', f'Generated {forecast_count} forecasts')
            
        except Exception as e:
            print(f"   ❌ Forecast generation error: {e}")
            self.db.log('ERROR', 'Worker', f'Forecast generation error: {e}')
    
    def _evaluate_trades(self):
        """Evaluate forecasts for trading opportunities"""
        now = time.time()
        
        if now - self.last_trade_check < TRADE_CHECK_INTERVAL:
            return
        
        print("\n💼 Evaluating Trading Opportunities...")
        
        try:
            # Get recent unevaluated forecasts
            recent_forecasts = self.db.get_recent_forecasts_for_trading()
            
            if not recent_forecasts:
                print("   No forecasts to evaluate")
                self.last_trade_eval = now
                return
            
            print(f"   Evaluating {len(recent_forecasts)} forecasts")
            
            # Get current prices
            current_prices = {}
            for asset in ['USD Index', 'Gold', 'Silver', 'Oil', 'Bitcoin']:
                price_row = self.db.get_latest_price(asset)
                if price_row:
                    current_prices[asset] = price_row['price']
            
            trades_executed = 0
            skip_reasons = {
                'no_price': 0,
                'below_confidence': 0,
                'neutral_direction': 0,
                'hourly_limit': 0,
                'open_trades_limit': 0,
                'paused': 0,
                'other': 0,
            }
            for forecast in recent_forecasts:
                try:
                    asset = forecast.get('asset')
                    current_price = current_prices.get(asset)
                    
                    if not current_price:
                        skip_reasons['no_price'] += 1
                        continue

                    # Lightweight skip-reason tracking (mirrors AutoTrader guardrails)
                    try:
                        portfolio = self.db.get_portfolio()
                        if portfolio and portfolio.get('is_trading_paused'):
                            skip_reasons['paused'] += 1
                            continue
                        if float(forecast.get('confidence') or 0) < float(config.MIN_CONFIDENCE_FOR_TRADE):
                            skip_reasons['below_confidence'] += 1
                            continue
                        if str(forecast.get('direction') or '').upper() == 'NEUTRAL':
                            skip_reasons['neutral_direction'] += 1
                            continue
                        if len(self.db.get_open_trades_for_asset(asset)) >= config.MAX_OPEN_TRADES_PER_ASSET:
                            skip_reasons['open_trades_limit'] += 1
                            continue
                        if not self.trader._check_hourly_limit():
                            skip_reasons['hourly_limit'] += 1
                            continue
                    except Exception:
                        skip_reasons['other'] += 1
                    
                    trade = self.trader.evaluate_forecast_for_trading(forecast, current_price)
                    
                    if trade:
                        self.trader.execute_trade(trade)
                        trades_executed += 1
                        print(
                            f"   📈 Executed: {trade['asset']} {forecast.get('direction')} @ {trade['entry_price']:.4f}"
                        )
                    
                except Exception as e:
                    print(f"   Error evaluating trade: {e}")
                    continue
            
            if trades_executed > 0:
                print(f"   ✅ Executed {trades_executed} trades")
                self.db.log('INFO', 'Worker', f'Executed {trades_executed} trades')
            else:
                print("   No trades met guardrail criteria")
                try:
                    self.db.log(
                        'INFO',
                        'Worker',
                        "Trade skips: "
                        + ", ".join([f"{k}={v}" for k, v in skip_reasons.items() if v]),
                    )
                except Exception:
                    pass
            
        except Exception as e:
            print(f"   ❌ Trade evaluation error: {e}")
            self.db.log('ERROR', 'Worker', f'Trade evaluation error: {e}')
        
        self.last_trade_check = now
    
    def _monitor_open_trades(self):
        """Check and close open trades if SL/TP hit"""
        print("\n🔍 Monitoring Open Trades...")
        
        try:
            open_trades = self.db.get_open_trades()
            if not open_trades:
                print("   No open trades")
                return

            assets = sorted({t.get('asset') for t in open_trades if t.get('asset')})

            # Get current prices for just the assets we actually need
            current_prices = {}
            for asset in assets:
                price_row = self.db.get_latest_price(asset)
                if price_row:
                    current_prices[asset] = {
                        'price': price_row['price'],
                        'timestamp': price_row.get('timestamp'),
                    }

            closed_trades = self.trader.check_open_trades(current_prices)
            
            if closed_trades:
                print(f"   ✅ Closed {closed_trades} positions")
                self.db.log('INFO', 'Worker', f'Closed {closed_trades} positions')
            else:
                print("   All positions within limits")
            
        except Exception as e:
            print(f"   ❌ Trade monitoring error: {e}")
            self.db.log('ERROR', 'Worker', f'Trade monitoring error: {e}')
    
    def _evaluate_forecasts(self):
        """Evaluate matured forecasts"""
        print("\n📊 Evaluating Matured Forecasts...")
        
        try:
            evaluated = self.evaluator.evaluate_due_forecasts()
            
            if evaluated > 0:
                print(f"   ✅ Evaluated {evaluated} forecasts")
                self.db.log('INFO', 'Worker', f'Evaluated {evaluated} forecasts')
            else:
                print("   No forecasts due for evaluation")
            
        except Exception as e:
            print(f"   ❌ Forecast evaluation error: {e}")
            self.db.log('ERROR', 'Worker', f'Forecast evaluation error: {traceback.format_exc()}')

        self.last_forecast_eval = time.time()
    
    def _check_risk_limits(self):
        """Check if daily loss limit exceeded"""
        try:
            portfolio = self.db.get_portfolio_status()
            
            if not portfolio:
                return
            
            if portfolio.get('is_trading_paused') or portfolio.get('trading_paused'):
                print("\n⚠️ Trading paused due to daily loss limit")
            
        except Exception as e:
            print(f"   ❌ Risk check error: {e}")
            self.db.log('ERROR', 'Worker', f'Risk check error: {traceback.format_exc()}')


def main():
    """Entry point"""
    parser = argparse.ArgumentParser(description='DAHAB AI worker process')
    parser.add_argument('--cycles', type=int, default=None, help='Run N cycles then exit (for testing)')
    parser.add_argument('--once', action='store_true', help='Run exactly one cycle then exit')
    args = parser.parse_args()

    worker = WorkerProcess()
    if args.once and args.cycles is None:
        worker.run(cycles=1)
    else:
        worker.run(cycles=args.cycles)


if __name__ == "__main__":
    main()
