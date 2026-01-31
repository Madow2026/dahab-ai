"""
System Diagnostic Script
Comprehensive health check for Dahab AI platform
Run this to identify issues before making changes
"""

import sqlite3
import sys
import os
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def main():
    db_path = r"d:\APP\gold ai\dahab_ai.db"
    
    if not os.path.exists(db_path):
        print(f"❌ Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    print("="*80)
    print("🔍 DAHAB AI SYSTEM DIAGNOSTIC")
    print("="*80)
    
    # 1. NEWS STATUS
    print("\n📰 NEWS STATUS:")
    cur.execute("SELECT COUNT(*) FROM news")
    news_total = cur.fetchone()[0]
    print(f"  Total news items: {news_total}")
    
    cur.execute("SELECT MAX(fetched_at) FROM news")
    latest_fetch = cur.fetchone()[0]
    print(f"  Latest fetched: {latest_fetch}")
    
    cur.execute("SELECT source, COUNT(*) FROM news GROUP BY source ORDER BY COUNT(*) DESC LIMIT 10")
    print("  By source:")
    for src, cnt in cur.fetchall():
        print(f"    {src}: {cnt}")
    
    # 2. PRICES STATUS
    print("\n💹 MARKET PRICES STATUS:")
    assets = ['USD Index', 'Gold', 'Silver', 'Oil', 'Bitcoin']
    for asset in assets:
        cur.execute("""
            SELECT price, timestamp 
            FROM prices 
            WHERE asset = ? 
            ORDER BY timestamp DESC 
            LIMIT 2
        """, (asset,))
        rows = cur.fetchall()
        
        if len(rows) >= 2:
            latest_price, latest_ts = rows[0]
            prev_price, prev_ts = rows[1]
            delta = latest_price - prev_price
            pct = (delta / prev_price * 100) if prev_price != 0 else 0
            
            try:
                ts_dt = datetime.fromisoformat(latest_ts.replace('Z', '+00:00'))
                age = (datetime.now(ts_dt.tzinfo) - ts_dt).total_seconds()
                stale = "⚠️ STALE" if age > 300 else "✅ Fresh"
            except:
                stale = "?"
            
            print(f"  {asset}: ${latest_price:,.2f} ({delta:+.2f} / {pct:+.2f}%) {stale}")
        elif len(rows) == 1:
            print(f"  {asset}: ${rows[0][0]:,.2f} (only 1 snapshot, no delta)")
        else:
            print(f"  {asset}: ❌ NO DATA")
    
    # 3. WORKER STATUS
    print("\n⚙️ WORKER STATUS:")
    try:
        cur.execute("SELECT * FROM worker_status WHERE id = 1")
        worker = cur.fetchone()
        if worker:
            cols = [desc[0] for desc in cur.description]
            worker_dict = dict(zip(cols, worker))
            print(f"  Last heartbeat: {worker_dict.get('last_heartbeat', 'N/A')}")
            print(f"  Last success: {worker_dict.get('last_successful_cycle_at', 'N/A')}")
            print(f"  Last error: {worker_dict.get('last_error', 'None')[:100] if worker_dict.get('last_error') else 'None'}")
        else:
            print("  ❌ No worker status found")
    except Exception as e:
        print(f"  ❌ Error reading worker_status: {e}")
    
    # 4. FORECASTS STATUS
    print("\n🎯 FORECASTS STATUS:")
    cur.execute("SELECT COUNT(*) FROM forecasts")
    print(f"  Total forecasts: {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(*) FROM forecasts WHERE status = 'active'")
    print(f"  Active forecasts: {cur.fetchone()[0]}")
    
    cur.execute("""
        SELECT COUNT(*) FROM forecasts 
        WHERE status = 'active' 
        AND due_at IS NOT NULL 
        AND datetime(replace(substr(due_at,1,19),'T',' ')) <= datetime('now')
    """)
    print(f"  Due now (ready to evaluate): {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(*) FROM forecasts WHERE evaluated_at IS NOT NULL")
    print(f"  Evaluated: {cur.fetchone()[0]}")
    
    # 5. PAPER TRADING STATUS
    print("\n💼 PAPER TRADING STATUS:")
    cur.execute("SELECT COUNT(*) FROM paper_trades")
    print(f"  Total trades: {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(*) FROM paper_trades WHERE status = 'open'")
    print(f"  Open trades: {cur.fetchone()[0]}")
    
    cur.execute("SELECT COUNT(*) FROM paper_trades WHERE status = 'closed'")
    print(f"  Closed trades: {cur.fetchone()[0]}")
    
    try:
        cur.execute("SELECT equity FROM paper_portfolio WHERE id = 1")
        equity = cur.fetchone()
        if equity:
            print(f"  Current equity: ${equity[0]:,.2f}")
    except:
        pass
    
    # 6. SYSTEM HEALTH SUMMARY
    print("\n🏥 SYSTEM HEALTH SUMMARY:")
    
    issues = []
    
    if news_total < 10:
        issues.append("⚠️ Very few news items (< 10)")
    
    if latest_fetch:
        try:
            fetch_dt = datetime.fromisoformat(latest_fetch.replace('Z', '+00:00'))
            age_hours = (datetime.now(fetch_dt.tzinfo) - fetch_dt).total_seconds() / 3600
            if age_hours > 1:
                issues.append(f"⚠️ News hasn't been fetched in {age_hours:.1f} hours")
        except:
            pass
    
    if not issues:
        print("  ✅ No critical issues detected")
    else:
        for issue in issues:
            print(f"  {issue}")
    
    print("\n" + "="*80)
    print("Diagnostic complete. Review output above.")
    print("="*80)
    
    conn.close()

if __name__ == "__main__":
    main()
