import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from db.db import get_db

db = get_db()
conn = db.get_connection()
cur = conn.cursor()

def count(sql: str, params=()):
    cur.execute(sql, params)
    return int(cur.fetchone()[0])

news = count('SELECT COUNT(*) FROM news')
forecasts = count('SELECT COUNT(*) FROM forecasts')
prices = count('SELECT COUNT(*) FROM prices')
trades = count('SELECT COUNT(*) FROM paper_trades')

cur.execute('SELECT last_error, last_successful_cycle_at, last_heartbeat_at FROM worker_status WHERE id = 1')
ws = cur.fetchone()
last_error = ws[0] if ws else None
last_success = ws[1] if ws else None
last_hb = ws[2] if ws else None

# Evaluation sanity: if any forecasts are due, at least one should be evaluated after a worker --once.
due = count("SELECT COUNT(*) FROM forecasts WHERE due_at IS NOT NULL AND due_at != '' AND status = 'active' AND datetime(replace(substr(due_at,1,19),'T',' ')) <= datetime('now')")
evaluated = count("SELECT COUNT(*) FROM forecasts WHERE evaluated_at IS NOT NULL AND evaluated_at != ''")

print('news:', news)
print('forecasts:', forecasts)
print('prices:', prices)
print('paper_trades:', trades)
print('worker_status.last_successful_cycle_at:', last_success)
print('worker_status.last_heartbeat_at:', last_hb)
print('worker_status.last_error:', (last_error[:180] + '...') if isinstance(last_error, str) and len(last_error) > 180 else last_error)
print('due_active_forecasts_now:', due)
print('evaluated_forecasts:', evaluated)

if due > 0 and evaluated == 0:
    raise SystemExit('SANITY_FAIL: due forecasts exist but evaluated_forecasts is still 0')

conn.close()
print('SANITY_OK')
