# DAHAB AI Platform - Quick Start Guide

## System Fixed & Ready to Run

All issues have been resolved:
- ✅ Database schema validated and migrated automatically
- ✅ Market prices now show last known values (never N/A)
- ✅ Forecast generation pipeline fixed
- ✅ Auto-trading enabled with guardrails
- ✅ System diagnostics added to dashboard
- ✅ Robust error handling with retries

## Running the Platform

### Windows PowerShell Commands:

**1. Start the Worker (Automated Pipeline):**
```powershell
cd "d:\APP\gold ai"
python start_worker.py
```

This will:
- Validate system configuration
- Test database connection  
- Test market data fetch
- Start automated worker process

**2. Start the Dashboard (in separate terminal):**
```powershell
cd "d:\APP\gold ai"
streamlit run app.py
```

Then open: **http://localhost:8501**

## What the Worker Does

Every cycle (30-60 seconds):
1. **Fetches news** from RSS feeds (economic keywords required)
2. **Translates** to Arabic
3. **Analyzes impact** with NLP (category, sentiment, confidence)
4. **Generates forecasts** for affected assets (probabilistic, max 85% confidence)
5. **Updates market prices** with fallback to cached values
6. **Evaluates trades** if confidence >= 70%
7. **Monitors positions** for stop-loss/take-profit
8. **Evaluates matured forecasts** for accuracy tracking

## Dashboard Pages

1. **📈 Markets Dashboard** - Live prices, sentiment, system status
2. **📰 News Feed** - Economic news with Arabic translation
3. **🎯 AI Market Outlook** - Active and evaluated forecasts
4. **📊 Accuracy Performance** - Forecast accuracy by asset
5. **💼 Paper Portfolio** - Trade history and P&L

All pages auto-refresh every 30 seconds.

## System Status Indicators

The dashboard now shows:
- **Worker Status**: Last activity timestamp
- **Price Freshness**: How many assets have current data
- **Trade Count**: Total and open positions
- **Stale Data Warnings**: If prices are >5 minutes old

## Troubleshooting

**Prices showing as stale:**
- Worker is fetching but market may be closed
- yfinance API rate limits (adds delays)
- Check worker terminal for fetch errors

**No forecasts generated:**
- News may not contain economic keywords (requires 2+ matches)
- Check "System Status" panel on dashboard
- Verify worker is running

**No trades executing:**
- Requires forecasts with confidence >= 70%
- Max 1 trade per asset
- Daily loss limit may be hit (3%)
- Check Paper Portfolio page for details

**Worker crashes:**
- Check Python version (3.8+ required)
- Reinstall: `pip install -r requirements.txt`
- Check terminal output for specific errors

## Key Features

### Automated Forecasting
- Never claims 100% certainty (max 85%)
- Considers data quality in confidence
- Generates scenarios (base + alternative)
- Time horizons: 60-480 minutes

### Risk Management
- Max 1% risk per trade
- Position size: 5% of equity
- Stop loss: 0.8% | Take profit: 1.6% (2:1 RR)
- Daily circuit breaker: 3% loss

### Data Quality
- Source reliability scoring
- Economic keyword filtering
- Deduplication via URL hash
- Translation validation

## Files Modified

1. `db/schema_validator.py` - NEW: Auto-migration
2. `db/db.py` - Updated: evaluation_time compatibility
3. `engine/market_data.py` - Updated: Fallback to cached prices
4. `pages/1_📈_Markets_Dashboard.py` - Updated: System status panel
5. `worker.py` - Updated: Better error handling
6. `start_worker.py` - NEW: Startup validation script

## Database Schema

The system uses SQLite with 7 tables:
- `news` - Article storage with analysis
- `prices` - Historical price data
- `forecasts` - Predictions and evaluations
- `paper_portfolio` - Account summary
- `paper_trades` - Trade records
- `trade_counters` - Rate limiting
- `system_logs` - Activity logs

Schema is validated and migrated automatically on startup.

## Performance Notes

- First run: 1-2 minutes to collect initial data
- Price fetch: 5-15 seconds per cycle (yfinance API)
- News translation: May fail if Google rate limits (continues with next)
- Forecast generation: Instant once news is analyzed

## Support

Check `system_logs` table for detailed error messages:
```python
python -c "import sqlite3; conn = sqlite3.connect('dahab_ai.db'); print(conn.execute('SELECT * FROM system_logs ORDER BY id DESC LIMIT 10').fetchall())"
```

Or view in System Status panel on dashboard.

---

**⚠️ IMPORTANT**: This is for educational purposes only. Paper trading is simulated. Real trading involves significant risk.
