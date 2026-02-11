"""
Configuration for Dahab AI Platform
All adjustable parameters for automated operation
"""

# ============================================================================
# AUTOMATION INTERVALS
# ============================================================================

# How often to check for new news (seconds)
NEWS_POLL_INTERVAL = 60

# How often to update market prices (seconds)
PRICE_POLL_INTERVAL = 30

# How often to evaluate forecasts (seconds)
FORECAST_EVAL_INTERVAL = 60

# How often to check trade exits (seconds)
TRADE_CHECK_INTERVAL = 30

# Main worker cycle interval (seconds)
WORKER_CYCLE_INTERVAL = 30

# ============================================================================
# PAPER TRADING PARAMETERS
# ============================================================================

# Starting capital
INITIAL_EQUITY = 1000.0

# Risk management
MAX_RISK_PER_TRADE = 0.01  # 1% of equity per trade
MIN_CONFIDENCE_FOR_TRADE = 50.0  # Only trade forecasts >= 50% confidence
MIN_IMPACT_LEVEL = "MEDIUM"  # Minimum impact level (LOW/MEDIUM/HIGH)

# Position limits
MAX_OPEN_TRADES_PER_ASSET = 1
MAX_TRADES_PER_HOUR = 2

# Daily circuit breaker
DAILY_MAX_LOSS_PERCENT = 3.0  # Pause trading if daily loss > 3%

# Stop loss and take profit
DEFAULT_STOP_LOSS_PERCENT = 0.8  # 0.8% stop loss
DEFAULT_TAKE_PROFIT_PERCENT = 1.6  # 1.6% take profit (2:1 RR)

# Time-based exit
FORCE_EXIT_AT_HORIZON = True  # Close trade at forecast horizon even if SL/TP not hit

# ============================================================================
# FORECASTING PARAMETERS
# ============================================================================

# Confidence caps (following Dahab AI principles)
MAX_CONFIDENCE_ALLOWED = 85.0  # Never exceed 85%
MIN_CONFIDENCE_ALLOWED = 25.0

# Default forecast horizons by news category (minutes)
FORECAST_HORIZONS = {
    'interest_rates': 240,  # 4 hours
    'inflation': 240,
    'employment': 240,
    'gdp': 1440,  # 1 day
    'energy': 60,  # 1 hour
    'geopolitics': 240,
    'crypto': 15,  # 15 minutes (fast-moving)
    'general': 15,  # 15 minutes (short-term)
}

# Structured recommendation horizons (required research baseline)
# These are used by the multi-horizon recommendation engine.
ENABLE_MULTI_HORIZON_RECOMMENDATIONS = True
RECOMMENDATION_HORIZONS = {
    '12h': 12 * 60,
    '24h': 24 * 60,
    '3d': 3 * 24 * 60,
    '7d': 7 * 24 * 60,
}

# Event-driven recommendation threshold.
# If an analyzed news item has impact confidence below this threshold,
# the worker may still store the news but treat recommendations as low priority.
RECOMMENDATION_IMPACT_THRESHOLD = 55.0

# Impact strength thresholds
HIGH_IMPACT_CONFIDENCE_BOOST = 10.0
LOW_IMPACT_CONFIDENCE_PENALTY = 10.0

# ============================================================================
# DATA QUALITY RULES
# ============================================================================

# Weak source confidence penalty
WEAK_SOURCE_PENALTY = 15.0

# Ambiguous news confidence penalty
AMBIGUOUS_NEWS_PENALTY = 10.0

# Minimum words for quality analysis
MIN_NEWS_CONTENT_LENGTH = 50

# ============================================================================
# NEWS SOURCES
# ============================================================================

# RSS feeds with reliability scores
NEWS_SOURCES = {
    # Financial News - High Reliability
    'marketwatch': {
        'url': 'https://www.marketwatch.com/rss/topstories',
        'reliability': 0.85
    },
    'marketwatch_economy': {
        'url': 'https://www.marketwatch.com/rss/economicrpt',
        'reliability': 0.85
    },
    'forex_live': {
        'url': 'https://www.forexlive.com/feed/news',
        'reliability': 0.75
    },
    'investing_economy': {
        'url': 'https://www.investing.com/rss/news_14.rss',
        'reliability': 0.8
    },
    'investing_commodities': {
        'url': 'https://www.investing.com/rss/commodities',
        'reliability': 0.8
    },
    'investing_forex': {
        'url': 'https://www.investing.com/rss/forex',
        'reliability': 0.8
    },
    'investing_crypto': {
        'url': 'https://www.investing.com/rss/news_301.rss',
        'reliability': 0.75
    },
    
    # Business & Economic News
    'cnbc_economy': {
        'url': 'https://www.cnbc.com/id/20910258/device/rss/rss.html',
        'reliability': 0.85
    },
    'cnbc_markets': {
        'url': 'https://www.cnbc.com/id/10000664/device/rss/rss.html',
        'reliability': 0.85
    },
    'cnbc_world': {
        'url': 'https://www.cnbc.com/id/100727362/device/rss/rss.html',
        'reliability': 0.85
    },
    'yahoo_finance': {
        'url': 'https://finance.yahoo.com/news/rssindex',
        'reliability': 0.8
    },
    'seekingalpha': {
        'url': 'https://seekingalpha.com/feed.xml',
        'reliability': 0.75
    },
    
    # Central Banks & Policy
    'fed_news': {
        'url': 'https://www.federalreserve.gov/feeds/press_all.xml',
        'reliability': 0.95
    },
    
    # Commodities & Forex Specialized
    'kitco_gold': {
        'url': 'https://www.kitco.com/rss/KitcoNews.xml',
        'reliability': 0.8
    },
    'fxstreet': {
        'url': 'https://www.fxstreet.com/feeds/news',
        'reliability': 0.75
    },
    'dailyfx': {
        'url': 'https://www.dailyfx.com/feeds/market-news',
        'reliability': 0.75
    },
    
    # Crypto Economic News
    'coindesk': {
        'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
        'reliability': 0.8
    },
    'cointelegraph': {
        'url': 'https://cointelegraph.com/rss',
        'reliability': 0.75
    },
    
    # Energy Markets
    'oilprice': {
        'url': 'https://oilprice.com/rss/main',
        'reliability': 0.75
    },
    
    # International Economic News
    'ft_world': {
        'url': 'https://www.ft.com/world?format=rss',
        'reliability': 0.9
    },
    'ft_markets': {
        'url': 'https://www.ft.com/markets?format=rss',
        'reliability': 0.9
    },
    'economist': {
        'url': 'https://www.economist.com/finance-and-economics/rss.xml',
        'reliability': 0.9
    },
    'bloomberg_markets': {
        'url': 'https://feeds.bloomberg.com/markets/news.rss',
        'reliability': 0.9
    },
    'bloomberg_economics': {
        'url': 'https://feeds.bloomberg.com/economics/news.rss',
        'reliability': 0.9
    },
    
    # Political & Geopolitical News Affecting Markets
    'reuters_world': {
        'url': 'https://www.reutersagency.com/feed/?taxonomy=best-regions&post_type=best',
        'reliability': 0.9
    },
    'reuters_politics': {
        'url': 'https://www.reuters.com/rssfeed/worldNews',
        'reliability': 0.9
    },
    'ap_politics': {
        'url': 'https://apnews.com/hub/politics/feed',
        'reliability': 0.85
    },
    'bbc_world': {
        'url': 'http://feeds.bbci.co.uk/news/world/rss.xml',
        'reliability': 0.9
    },
    'politico': {
        'url': 'https://www.politico.com/rss/politics08.xml',
        'reliability': 0.8
    },
    'aljazeera_economy': {
        'url': 'https://www.aljazeera.com/xml/rss/all.xml',
        'reliability': 0.8
    },
    'cnbc_politics': {
        'url': 'https://www.cnbc.com/id/10000113/device/rss/rss.html',
        'reliability': 0.85
    }
}

# Minimum keyword matches required to treat an RSS item as economic/financial.
# Set to 1 to be more inclusive; raise to 2+ for stricter filtering.
NEWS_MIN_KEYWORD_MATCHES = 1

# ============================================================================
# MARKET DATA
# ============================================================================

# Asset symbols (Yahoo Finance format)
ASSETS = {
    'USD Index': {'symbol': 'DX-Y.NYB', 'name': 'US Dollar Index'},
    'Gold': {'symbol': 'GC=F', 'name': 'Gold Futures'},
    'Silver': {'symbol': 'SI=F', 'name': 'Silver Futures'},
    'Oil': {'symbol': 'CL=F', 'name': 'Crude Oil WTI'},
    'Bitcoin': {'symbol': 'BTC-USD', 'name': 'Bitcoin'}
}

# Price data timeout
PRICE_FETCH_TIMEOUT = 10  # seconds

# ============================================================================
# TRANSLATION
# ============================================================================

# Translation settings
TRANSLATION_ENABLED = True
TRANSLATION_SOURCE_LANG = 'en'
TRANSLATION_TARGET_LANG = 'ar'
TRANSLATION_MAX_LENGTH = 500  # Max chars to translate per text

import os

# ============================================================================
# DATABASE / RUNTIME PATHS
# ============================================================================

# Resolve runtime paths relative to this package so DB location does not depend
# on the process working directory (worker vs Streamlit vs scripts).
DAHAB_AI_ROOT = os.path.dirname(os.path.abspath(__file__))
DAHAB_AI_DATA_DIR = os.getenv("DAHAB_DATA_DIR", os.path.join(DAHAB_AI_ROOT, "data"))
try:
    os.makedirs(DAHAB_AI_DATA_DIR, exist_ok=True)
except Exception:
    # If the directory can't be created (e.g., permissions), fall back to root.
    DAHAB_AI_DATA_DIR = DAHAB_AI_ROOT

# Allow explicit override for deployments.
DATABASE_PATH = os.path.abspath(
    os.getenv("DAHAB_DB_PATH", os.path.join(DAHAB_AI_DATA_DIR, "dahab_ai.db"))
)

# ============================================================================
# UI SETTINGS
# ============================================================================

# Streamlit auto-refresh interval (seconds)
UI_REFRESH_INTERVAL = 30

# Number of items to display
MAX_NEWS_DISPLAY = 50
MAX_FORECASTS_DISPLAY = 20
MAX_TRADES_DISPLAY = 30

# ============================================================================
# LOGGING
# ============================================================================

LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR
LOG_TO_FILE = True
LOG_FILE_PATH = os.path.abspath(
    os.getenv("DAHAB_LOG_PATH", os.path.join(DAHAB_AI_DATA_DIR, "dahab_ai.log"))
)

# ============================================================================
# DISCLAIMERS
# ============================================================================

DISCLAIMER_TEXT = """
⚠️ **DISCLAIMER**  
This platform is for **educational and analytical purposes only**.  
It does **not constitute financial advice** or investment recommendations.  
All forecasts are **probabilistic** (not guaranteed).  
The paper portfolio is a **simulated environment** for learning only.  
Past performance does not guarantee future results.
"""

DISCLAIMER_SHORT = "Educational only. Not financial advice. Forecasts are probabilistic. Portfolio is simulated."

#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+###########
# WORKER SETTINGS
# (Keep WORKER_CYCLE_INTERVAL defined once, above)
#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+#+###########

# Graceful shutdown timeout
WORKER_SHUTDOWN_TIMEOUT = 10  # seconds

# Network request timeout
NETWORK_TIMEOUT = 10  # seconds

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# ============================================================================
# PERFORMANCE TRACKING
# ============================================================================

# Accuracy calculation window (days)
ACCURACY_WINDOW_DAYS = 7

# Minimum forecasts for source reliability calculation
MIN_FORECASTS_FOR_RELIABILITY = 10
