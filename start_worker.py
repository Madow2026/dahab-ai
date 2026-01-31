"""
DAHAB AI Platform Startup Script
Validates system and starts worker
"""

import sys
import os

print("=" * 70)
print("🚀 DAHAB AI Platform - Startup Sequence")
print("=" * 70)

# Step 1: Validate Python version
print("\n1️⃣ Checking Python version...")
if sys.version_info < (3, 8):
    print("❌ Python 3.8+ required")
    sys.exit(1)
print(f"✅ Python {sys.version.split()[0]}")

# Step 2: Check database exists
print("\n2️⃣ Checking database...")
if not os.path.exists("dahab_ai.db"):
    print("⚠️ Database not found. Will be created on first run.")
else:
    print("✅ Database file exists")

# Step 3: Validate configuration
print("\n3️⃣ Validating configuration...")
try:
    import config
    print(f"✅ Initial equity: ${config.INITIAL_EQUITY}")
    print(f"✅ Risk per trade: {config.MAX_RISK_PER_TRADE * 100}%")
    print(f"✅ Assets: {len(config.ASSETS)}")
except Exception as e:
    print(f"❌ Config error: {e}")
    sys.exit(1)

# Step 4: Test database connection
print("\n4️⃣ Testing database connection...")
try:
    from db.db import get_db
    db = get_db()
    print("✅ Database initialized successfully")
    
    # Check portfolio
    portfolio = db.get_portfolio()
    if portfolio:
        print(f"✅ Portfolio equity: ${portfolio['current_equity']:.2f}")
    else:
        print("⚠️ Portfolio not initialized (will be created)")
        
except Exception as e:
    print(f"❌ Database error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 5: Test market data
print("\n5️⃣ Testing market data fetch...")
try:
    from engine.market_data import get_market_data
    market = get_market_data()
    print("✅ Market data module loaded")
    
    print("\n   Testing price fetch (this may take 10-15 seconds)...")
    prices = market.fetch_all_prices()
    
    success_count = sum(1 for p in prices.values() if p.get('price'))
    print(f"   ✅ Fetched {success_count}/{len(prices)} asset prices")
    
    for asset, data in prices.items():
        if data.get('price'):
            print(f"     • {asset}: ${data['price']:.2f}")
        else:
            print(f"     • {asset}: ❌ Failed (will use cached)")
            
except Exception as e:
    print(f"❌ Market data error: {e}")
    import traceback
    traceback.print_exc()
    print("⚠️ Continuing anyway - worker will retry")

# Step 6: Test news ingestion
print("\n6️⃣ Testing news ingestion...")
try:
    from engine.news_ingestion import get_news_ingestion
    news_ing = get_news_ingestion()
    print("✅ News ingestion module loaded")
except Exception as e:
    print(f"❌ News ingestion error: {e}")
    sys.exit(1)

# Step 7: Load all engine modules
print("\n7️⃣ Loading engine modules...")
try:
    from engine.translator import get_translator
    from engine.impact_engine import get_impact_engine
    from engine.forecaster import get_forecaster
    from engine.trader import get_auto_trader
    from engine.evaluator import get_evaluator
    print("✅ All engine modules loaded")
except Exception as e:
    print(f"❌ Engine module error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("✅ System validation complete! Starting worker...")
print("=" * 70)
print()

# Import and run worker
try:
    from worker import WorkerProcess
    worker = WorkerProcess()
    worker.run()
except KeyboardInterrupt:
    print("\n\n🛑 Shutdown requested by user")
    sys.exit(0)
except Exception as e:
    print(f"\n❌ Worker error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
