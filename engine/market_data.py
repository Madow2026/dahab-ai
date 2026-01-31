"""
Market Data Module
Fetches and stores market prices with fallbacks
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, Optional
import config
import time
import requests
import concurrent.futures

class MarketData:
    def __init__(self):
        self.price_cache = {}
        self.cache_timestamp = {}
        from db.db import get_db
        self.db = get_db()
    
    def fetch_all_prices(self) -> Dict[str, Dict]:
        """Fetch current prices for all assets with retries and fallbacks"""
        prices = {}
        
        for asset_name, asset_config in config.ASSETS.items():
            try:
                # Try primary method (yfinance)
                price_data = self._fetch_price_yfinance(asset_name, asset_config['symbol'])

                # USD Index fallback symbol
                if (not price_data or not price_data.get('price')) and asset_name == 'USD Index':
                    price_data = self._fetch_price_yfinance(asset_name, '^DXY')
                
                if price_data and price_data['price']:
                    prices[asset_name] = price_data
                    # Store in database
                    self.db.insert_price(asset_name, price_data['price'])
                else:
                    # Fallback to last known price from DB
                    last_known = self.db.get_latest_price(asset_name)
                    if last_known:
                        prices[asset_name] = {
                            'price': last_known['price'],
                            'change': 0,
                            'change_percent': 0,
                            'timestamp': last_known['timestamp'],
                            'stale': True
                        }
                    else:
                        prices[asset_name] = {'price': None, 'error': True}
                
                time.sleep(0.5)  # Rate limiting
                
            except Exception as e:
                print(f"Error fetching {asset_name}: {e}")
                # Always try to get last known price
                last_known = self.db.get_latest_price(asset_name)
                if last_known:
                    prices[asset_name] = {
                        'price': last_known['price'],
                        'timestamp': last_known['timestamp'],
                        'stale': True
                    }
        
        return prices
    
    def _fetch_price_yfinance(self, asset_name: str, symbol: str, timeout=10) -> Optional[Dict]:
        """Fetch price for single asset using yfinance with timeout"""
        try:
            ticker = yf.Ticker(symbol)

            # yfinance has no reliable per-call timeout; enforce a hard budget.
            def _load_history():
                return ticker.history(period='1d', interval='5m')

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(_load_history)
                hist = fut.result(timeout=float(timeout))
            
            if hist.empty:
                print(f"  No data for {symbol}")
                return None
            
            current_price = float(hist['Close'].iloc[-1])
            
            # Get previous close for change calculation
            try:
                if len(hist) > 1:
                    previous_close = float(hist['Close'].iloc[-2])
                else:
                    previous_close = current_price
            except:
                previous_close = current_price
            
            # NOTE: Keep full precision in DB to avoid UI deltas rounding to 0.00.
            # UI will format to the appropriate number of decimals per asset.
            change = current_price - previous_close
            change_percent = (change / previous_close * 100) if previous_close else 0
            
            price_data = {
                'price': float(current_price),
                'change': float(change),
                'change_percent': float(change_percent),
                'timestamp': datetime.now().isoformat(),
                'previous_close': float(previous_close),
                'error': False,
                'stale': False
            }
            
            # Update cache
            self.price_cache[asset_name] = price_data
            self.cache_timestamp[asset_name] = datetime.now()
            
            return price_data
            
        except Exception as e:
            print(f"yfinance error for {symbol}: {e}")
            return None
    
    def get_cached_price(self, asset_name: str) -> Optional[Dict]:
        """Get cached price if available and recent"""
        if asset_name not in self.price_cache:
            return None
        
        cache_time = self.cache_timestamp.get(asset_name)
        if not cache_time:
            return None
        
        # Check if cache is still valid (< 5 minutes old)
        if datetime.now() - cache_time > timedelta(minutes=5):
            return None
        
        return self.price_cache[asset_name]
    
    def get_price_at_time(self, asset_name: str, target_time: datetime) -> Optional[float]:
        """Get historical price at specific time"""
        if asset_name not in config.ASSETS:
            return None
        
        symbol = config.ASSETS[asset_name]['symbol']
        
        try:
            ticker = yf.Ticker(symbol)
            
            # Get data around target time
            start_time = target_time - timedelta(hours=2)
            end_time = target_time + timedelta(hours=2)
            
            hist = ticker.history(start=start_time, end=end_time, interval='1m')
            
            if hist.empty:
                # Fallback to daily data
                hist = ticker.history(start=target_time.date(), end=target_time.date() + timedelta(days=1))
            
            if not hist.empty:
                # Get closest price
                closest_idx = hist.index.get_indexer([target_time], method='nearest')[0]
                price = float(hist['Close'].iloc[closest_idx])
                return round(price, 2)
            
            return None
            
        except Exception as e:
            print(f"Error getting historical price for {asset_name}: {e}")
            return None


# Singleton
_market_data = None

def get_market_data() -> MarketData:
    """Get market data instance"""
    global _market_data
    if _market_data is None:
        _market_data = MarketData()
    return _market_data
