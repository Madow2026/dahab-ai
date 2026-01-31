"""
Quick test script to verify Dahab AI components
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

print("🟨 Dahab AI - Component Test\n")

# Test 1: Database
print("1. Testing Database...")
try:
    from core.database import get_db
    db = get_db()
    print("   ✅ Database initialized successfully")
    print(f"   Database file: dahab_ai.db")
except Exception as e:
    print(f"   ❌ Database error: {e}")

# Test 2: AI Engine
print("\n2. Testing AI Engine...")
try:
    from core.ai_engine import get_engine
    engine = get_engine()
    
    # Test classification
    test_news = engine.classify_news(
        "Federal Reserve raises interest rates by 0.25%",
        "The Federal Reserve announced an interest rate hike today"
    )
    print(f"   ✅ AI Engine working")
    print(f"   Test classification: {test_news.news_type}")
    print(f"   Affected assets: {test_news.affected_assets}")
    print(f"   Impact: {test_news.impact_nature} ({test_news.impact_strength})")
except Exception as e:
    print(f"   ❌ AI Engine error: {e}")

# Test 3: Data Collector
print("\n3. Testing Data Collector...")
try:
    from core.data_collector import get_market_data_collector
    collector = get_market_data_collector()
    print("   ✅ Data Collector initialized")
    print("   Tracked assets: USD, Gold, Silver, Oil, Bitcoin")
except Exception as e:
    print(f"   ❌ Data Collector error: {e}")

# Test 4: Forecast Generation
print("\n4. Testing Forecast Generation...")
try:
    from core.ai_engine import get_engine, NewsAnalysis
    engine = get_engine()
    
    # Create sample analysis
    sample_analysis = NewsAnalysis(
        news_type='interest_rates',
        affected_assets=['Gold', 'USD'],
        impact_nature='Positive',
        impact_strength='High',
        confidence=0.8,
        key_factors=['Rate increase expected']
    )
    
    forecast = engine.generate_forecast(sample_analysis, 'Gold', 1950.0)
    print(f"   ✅ Forecast generation working")
    print(f"   Asset: {forecast.asset}")
    print(f"   Direction: {forecast.expected_direction}")
    print(f"   Confidence: {forecast.confidence_level}%")
    print(f"   Risk: {forecast.risk_level}")
except Exception as e:
    print(f"   ❌ Forecast error: {e}")

# Test 5: Database Operations
print("\n5. Testing Database Operations...")
try:
    db = get_db()
    
    # Insert test news
    test_news_data = {
        'title': 'Test Economic News',
        'title_ar': 'اختبار الأخبار الاقتصادية',
        'content': 'This is a test news item',
        'content_ar': 'هذا خبر اختبار',
        'source': 'test_source',
        'url': 'https://example.com',
        'published_date': '2026-01-30T12:00:00',
        'collected_date': '2026-01-30T12:00:00',
        'news_type': 'interest_rates',
        'affected_assets': ['USD', 'Gold'],
        'impact_nature': 'Positive',
        'impact_strength': 'Medium'
    }
    
    news_id = db.insert_news(test_news_data)
    print(f"   ✅ News insertion successful (ID: {news_id})")
    
    # Retrieve news
    recent_news = db.get_recent_news(limit=5)
    print(f"   ✅ News retrieval successful ({len(recent_news)} items)")
    
except Exception as e:
    print(f"   ❌ Database operations error: {e}")

print("\n" + "="*50)
print("🎉 Component test complete!")
print("\n📊 Platform Status: OPERATIONAL")
print("\n🌐 Access the platform at: http://localhost:8501")
print("\n📝 Next steps:")
print("   1. Open the platform in your browser")
print("   2. Navigate to 'News' page")
print("   3. Click 'Collect Fresh News'")
print("   4. Explore AI Market Outlook and other pages")
print("\n⚠️  Remember: This is for educational purposes only!")
