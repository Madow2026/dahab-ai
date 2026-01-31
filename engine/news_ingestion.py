"""
News Ingestion Module
Fetches news from RSS feeds with deduplication
"""

import feedparser
import hashlib
import requests
from datetime import datetime
from typing import List, Dict
import config
import time

from db.db import get_db

class NewsIngestion:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Dahab-AI/1.0'})
        self.db = get_db()
    
    def fetch_all_news(self) -> List[Dict]:
        """Fetch news from all configured sources"""
        all_news = []
        
        for source_name, source_config in config.NEWS_SOURCES.items():
            try:
                news_items = self._fetch_from_source(source_name, source_config)
                all_news.extend(news_items)
                time.sleep(1)  # Rate limiting
            except Exception as e:
                print(f"Error fetching from {source_name}: {e}")
                continue
        
        return all_news
    
    def _fetch_from_source(self, source_name: str, source_config: Dict) -> List[Dict]:
        """Fetch news from single RSS feed"""
        url = source_config['url']
        reliability = source_config['reliability']
        
        try:
            # Hard time-bounded RSS fetch (never rely on feedparser doing network I/O)
            try:
                resp = self.session.get(url, timeout=(5, 15))
                resp.raise_for_status()
                feed = feedparser.parse(resp.content)
            except Exception as e:
                print(f"Error fetching RSS bytes from {source_name}: {e}")
                return []
            
            if not feed.entries:
                return []
            
            news_items = []
            
            for entry in feed.entries[:30]:  # Limit per source (more room for unseen items)
                try:
                    title = entry.get('title', '').strip()
                    body = entry.get('summary', entry.get('description', '')).strip()
                    url = (entry.get('link') or entry.get('id') or '').strip()
                    
                    if not title or len(title) < 10:
                        continue
                    
                    # Filter economic news
                    if not self._is_economic_news(title, body):
                        continue
                    
                    # Parse date
                    published_at = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        try:
                            published_at = datetime(*entry.published_parsed[:6]).isoformat()
                        except:
                            pass
                    
                    # Create a stable hash for deduplication.
                    # Prefer URL/id when present; fall back to title.
                    dedup_key = (url or title).strip().lower()
                    url_hash = hashlib.md5(dedup_key.encode()).hexdigest()

                    # Ensure URL is always non-empty because DB enforces UNIQUE(url).
                    if not url:
                        url = f"{source_name}:{url_hash}"

                    # DB-level dedup: only return items we haven't already stored.
                    try:
                        if self.db.has_news_url(url) or self.db.has_news_url_hash(url_hash, source=source_name):
                            continue
                    except Exception:
                        # If DB check fails, still return the item; DB UNIQUE(url) will protect.
                        pass
                    
                    news_items.append({
                        'source': source_name,
                        'url': url,
                        'url_hash': url_hash,
                        'title_en': title,
                        'body_en': body,
                        'published_at': published_at,
                        'fetched_at': datetime.now().isoformat(),
                        'source_reliability': reliability
                    })
                    
                except Exception as e:
                    print(f"Error parsing entry from {source_name}: {e}")
                    continue
            
            return news_items
            
        except Exception as e:
            print(f"Error fetching RSS from {source_name}: {e}")
            return []
    
    def _is_economic_news(self, title: str, body: str) -> bool:
        """Check if news is economic/financial"""
        text = (title + " " + body).lower()
        
        # Extended economic keywords
        economic_keywords = [
            'economy', 'economic', 'fed', 'federal reserve', 'interest rate',
            'inflation', 'gdp', 'employment', 'unemployment', 'jobs', 'payroll',
            'central bank', 'ecb', 'monetary', 'fiscal', 'policy',
            'gold', 'silver', 'oil', 'dollar', 'usd', 'forex', 'currency',
            'bitcoin', 'crypto', 'cryptocurrency', 'market', 'stock', 'trade',
            'treasury', 'bond', 'yield', 'price', 'recession', 'growth',
            'manufacturing', 'retail sales', 'consumer', 'producer',
            'housing', 'construction', 'data', 'report', 'survey'
        ]
        
        # Count keyword matches
        matches = sum(1 for keyword in economic_keywords if keyword in text)
        
        # Require at least N keyword matches (configurable)
        required = int(getattr(config, 'NEWS_MIN_KEYWORD_MATCHES', 2) or 2)
        return matches >= max(1, required)


# Singleton
_news_ingestion = None

def get_news_ingestion() -> NewsIngestion:
    """Get news ingestion instance"""
    global _news_ingestion
    if _news_ingestion is None:
        _news_ingestion = NewsIngestion()
    return _news_ingestion


def fetch_news() -> List[Dict]:
    """Convenience function to fetch news"""
    ingestion = get_news_ingestion()
    return ingestion.fetch_all_news()
