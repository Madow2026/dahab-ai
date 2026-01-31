import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from db.db import get_db

db = get_db()
print(db.evaluate_due_forecasts_backfill(max_window_hours=6))
