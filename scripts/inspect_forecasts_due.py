import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from db.db import get_db

db = get_db()
conn = db.get_connection()
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM forecasts')
print('forecasts_total:', cur.fetchone()[0])

cur.execute('SELECT MIN(due_at), MAX(due_at) FROM forecasts')
print('due_min_max:', cur.fetchone())

cur.execute("SELECT COUNT(*) FROM forecasts WHERE status='active' AND due_at IS NOT NULL AND due_at != ''")
print('active_with_due:', cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM forecasts WHERE status='active' AND due_at IS NOT NULL AND due_at != '' AND datetime(replace(substr(due_at,1,19),'T',' ')) <= datetime('now')")
print('active_due_now:', cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM forecasts WHERE status='active' AND due_at IS NOT NULL AND due_at != '' AND datetime(replace(substr(due_at,1,19),'T',' ')) <= datetime('now','+12 hours')")
print('active_due_within_12h:', cur.fetchone()[0])

# show a few soonest due
cur.execute(
    """
    SELECT id, asset, created_at, due_at, status, evaluated_at, evaluation_time
    FROM forecasts
    ORDER BY datetime(replace(substr(due_at,1,19),'T',' ')) ASC
    LIMIT 10
    """
)
rows = cur.fetchall()
print('soonest_due_rows:')
for r in rows:
    print(dict(r))

conn.close()
