"""
Streamlit-Compatible Background Worker
Runs worker tasks in background threads compatible with Streamlit Cloud
"""

import threading
import time
import traceback
from datetime import datetime
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
                
                # Evaluate forecasts
                self._safe_run('Forecast Eval', self._evaluate_forecasts)
                
                # Generate forecasts
                self._safe_run('Forecasts', self._generate_forecasts)
                
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
            # Get recent unprocessed news
            recent_news = self.db.get_unprocessed_news(limit=10)

            if not recent_news:
                return

            # Best-effort current prices (cached or last known from DB)
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

            for news_item in recent_news:
                inserted = 0
                try:
                    # Build analysis from stored fields
                    affected_assets = news_item.get('affected_assets') or []
                    if isinstance(affected_assets, str):
                        affected_assets = [a.strip() for a in affected_assets.split(',') if a.strip()]
                    elif not isinstance(affected_assets, list):
                        affected_assets = []

                    analysis = {
                        'category': (news_item.get('category') or 'general'),
                        'sentiment': (news_item.get('sentiment') or 'neutral'),
                        'impact_level': (news_item.get('impact_level') or 'LOW'),
                        'confidence': float(news_item.get('confidence') or 50.0),
                        'affected_assets': affected_assets,
                    }

                    forecasts = self.forecaster.generate_forecasts(news_item, analysis, current_prices)
                    for forecast in forecasts or []:
                        try:
                            self.db.insert_forecast(forecast)
                            inserted += 1
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
                    # Mark news processed to prevent infinite reprocessing loops
                    try:
                        self.db.mark_news_processed(news_item['id'])
                    except Exception:
                        pass
                    
        except Exception as e:
            print(f"Forecast generation error: {e}")
    
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


def ensure_worker_running():
    """Ensure background worker is running (call from Streamlit pages)"""
    worker = get_streamlit_worker()
    if not worker.running:
        worker.start()
