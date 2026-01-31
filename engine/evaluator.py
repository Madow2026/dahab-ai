"""
Forecast Evaluator
Evaluates forecast accuracy against actual results
"""

from typing import Dict
from db.db import get_db

class Evaluator:
    """Evaluates forecasts against actual outcomes"""
    
    def __init__(self):
        self.db = get_db()
    
    def evaluate_due_forecasts(self) -> int:
        """
        Evaluate all forecasts that are due
        Returns count of evaluated forecasts
        """
        try:
            result = self.db.evaluate_due_forecasts_backfill(max_window_hours=6)
            evaluated_count = int(result.get('evaluated') or 0)
            if evaluated_count:
                self.db.log('INFO', 'Evaluator', f"Evaluated due forecasts: {result}")
            return evaluated_count
        except Exception as e:
            try:
                self.db.log('ERROR', 'Evaluator', f"Evaluation loop failed: {e}")
            except Exception:
                pass
            return 0


# Singleton
_evaluator = None

def get_evaluator() -> Evaluator:
    """Get evaluator instance"""
    global _evaluator
    if _evaluator is None:
        _evaluator = Evaluator()
    return _evaluator
