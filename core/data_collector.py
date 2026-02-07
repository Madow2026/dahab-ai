"""
Data Collection Module
Handles news feeds and market data from free sources
"""

import requests
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import time
from deep_translator import GoogleTranslator

class NewsCollector:
    """Collect economic news from RSS feeds"""
    
    # Free RSS feeds for economic news
    FEEDS = {
        'reuters_business': 'https://www.reutersagency.com/feed/?taxonomy=best-topics&post_type=best',
        'investing_economy': 'https://www.investing.com/rss/news_14.rss',
        'forex_live': 'https://www.forexlive.com/feed/news',
        'marketwatch': 'https://www.marketwatch.com/rss/topstories',
    }
    
    def __init__(self):
        self.translator = GoogleTranslator(source='en', target='ar')
    
    def collect_news(self, max_items: int = 20) -> List[Dict]:
        """Collect news from all feeds"""
        all_news = []
        
        for source_name, feed_url in self.FEEDS.items():
            try:
                news_items = self._parse_feed(feed_url, source_name, max_items // len(self.FEEDS))
                all_news.extend(news_items)
                time.sleep(0.5)  # Rate limiting
            except Exception as e:
                print(f"Error collecting from {source_name}: {e}")
                continue
        
        # Sort by date
        all_news.sort(key=lambda x: x.get('published_date', ''), reverse=True)
        return all_news[:max_items]
    
    def _parse_feed(self, feed_url: str, source_name: str, max_items: int) -> List[Dict]:
        """Parse RSS feed"""
        feed = feedparser.parse(feed_url)
        news_items = []
        
        for entry in feed.entries[:max_items]:
            try:
                # Extract data
                title = entry.get('title', '')
                content = entry.get('summary', entry.get('description', ''))
                url = entry.get('link', '')
                
                # Parse date
                published_date = None
                if hasattr(entry, 'published_parsed'):
                    published_date = datetime(*entry.published_parsed[:6]).isoformat()
                elif hasattr(entry, 'updated_parsed'):
                    published_date = datetime(*entry.updated_parsed[:6]).isoformat()
                
                # Filter economic news (basic filtering)
                if not self._is_economic_news(title, content):
                    continue
                
                # Translate to Arabic
                title_ar = self._safe_translate(title)
                content_ar = self._safe_translate(content[:500]) if content else ""  # Limit content for translation
                
                news_items.append({
                    'title': title,
                    'title_ar': title_ar,
                    'content': content,
                    'content_ar': content_ar,
                    'source': source_name,
                    'url': url,
                    'published_date': published_date,
                    'collected_date': datetime.now().isoformat()
                })
                
            except Exception as e:
                print(f"Error parsing entry: {e}")
                continue
        
        return news_items
    
    def _is_economic_news(self, title: str, content: str) -> bool:
        """Check if news is economic/financial including political events affecting markets"""
        text = (title + " " + content).lower()
        
        economic_keywords = [
            # Core economic terms
            'economy', 'economic', 'fed', 'federal reserve', 'interest rate',
            'inflation', 'gdp', 'employment', 'unemployment', 'jobs',
            'central bank', 'ecb', 'monetary', 'fiscal',
            'gold', 'silver', 'oil', 'dollar', 'usd', 'forex',
            'bitcoin', 'crypto', 'market', 'stock', 'trade',
            'treasury', 'bond', 'yield',
            # Political and geopolitical terms affecting markets
            'election', 'politics', 'political', 'government', 'sanction',
            'tariff', 'war', 'conflict', 'tension', 'crisis', 'opec',
            'regulation', 'tax', 'budget', 'deficit', 'china', 'russia',
            'ukraine', 'middle east', 'iran', 'geopolitical', 'treaty',
            'diplomacy', 'energy policy', 'trade war', 'embargo'
        ]
        
        return any(keyword in text for keyword in economic_keywords)
    
    def _safe_translate(self, text: str) -> str:
        """Safely translate text to Arabic with error handling"""
        if not text or len(text.strip()) == 0:
            return ""
        
        try:
            # Limit text length for translation API
            text_to_translate = text[:500] if len(text) > 500 else text
            translated = self.translator.translate(text_to_translate)
            return translated
        except Exception as e:
            print(f"Translation error: {e}")
            return text  # Return original if translation fails

class MarketDataCollector:
    """Collect market price data from free APIs"""
    
    # Asset symbols for different APIs
    SYMBOLS = {
        'Gold': 'GC=F',  # Gold Futures
        'Silver': 'SI=F',  # Silver Futures
        'Oil': 'CL=F',  # Crude Oil WTI Futures
        'USD': 'DX-Y.NYB',  # US Dollar Index
        'Bitcoin': 'BTC-USD'  # Bitcoin
    }
    
    def __init__(self):
        pass
    
    def get_current_prices(self) -> Dict[str, Dict]:
        """Get current prices for all tracked assets"""
        prices = {}
        
        for asset, symbol in self.SYMBOLS.items():
            try:
                price_data = self._fetch_yahoo_finance(symbol)
                if price_data:
                    prices[asset] = price_data
                time.sleep(0.3)  # Rate limiting
            except Exception as e:
                print(f"Error fetching {asset}: {e}")
                prices[asset] = {
                    'price': None,
                    'change': 0,
                    'change_percent': 0,
                    'timestamp': datetime.now().isoformat()
                }
        
        return prices
    
    def _fetch_yahoo_finance(self, symbol: str) -> Optional[Dict]:
        """Fetch data from Yahoo Finance (free, no API key needed)"""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='1d', interval='1m')
            
            if data.empty:
                return None
            
            current_price = data['Close'].iloc[-1]
            previous_close = ticker.info.get('previousClose', current_price)
            
            change = current_price - previous_close
            change_percent = (change / previous_close * 100) if previous_close else 0
            
            return {
                'price': round(float(current_price), 2),
                'change': round(float(change), 2),
                'change_percent': round(float(change_percent), 2),
                'timestamp': datetime.now().isoformat(),
                'previous_close': round(float(previous_close), 2)
            }
        
        except Exception as e:
            print(f"Yahoo Finance error for {symbol}: {e}")
            return None
    
    def get_price_at_time(self, asset: str, target_time: datetime) -> Optional[float]:
        """Get historical price at specific time (best effort)"""
        symbol = self.SYMBOLS.get(asset)
        if not symbol:
            return None
        
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            
            # Get data around target time
            start_time = target_time - timedelta(hours=1)
            end_time = target_time + timedelta(hours=1)
            
            data = ticker.history(start=start_time, end=end_time, interval='1m')
            
            if data.empty:
                # Fallback to daily data
                data = ticker.history(start=target_time.date(), end=target_time.date() + timedelta(days=1))
            
            if not data.empty:
                # Get closest price
                closest_idx = data.index.get_indexer([target_time], method='nearest')[0]
                price = data['Close'].iloc[closest_idx]
                return round(float(price), 2)
            
            return None
        
        except Exception as e:
            print(f"Error getting historical price: {e}")
            return None

# Singleton instances
_news_collector = None
_market_data_collector = None

def get_news_collector() -> NewsCollector:
    """Get news collector instance"""
    global _news_collector
    if _news_collector is None:
        _news_collector = NewsCollector()
    return _news_collector

def get_market_data_collector() -> MarketDataCollector:
    """Get market data collector instance"""
    global _market_data_collector
    if _market_data_collector is None:
        _market_data_collector = MarketDataCollector()
    return _market_data_collector
