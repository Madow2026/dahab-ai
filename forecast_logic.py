"""Forecast normalization helpers.

This module is intentionally small and dependency-free.
It provides backward-compatible field normalization so the rest of the system
can rely on a consistent schema without resetting or rewriting historical data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def iso_utc_z(dt: datetime) -> str:
    """Return ISO-8601 timestamp in UTC with a trailing 'Z'."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    dt = dt.replace(microsecond=0)
    return dt.isoformat().replace("+00:00", "Z")


def parse_iso_dt(value: Any) -> Optional[datetime]:
    if value is None or str(value).strip() == "":
        return None
    try:
        s = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt
    except Exception:
        return None


def horizon_hours_from_minutes(horizon_minutes: Any) -> Optional[float]:
    try:
        hm = float(horizon_minutes)
        if hm <= 0:
            return None
        return hm / 60.0
    except Exception:
        return None


def normalize_forecast_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow-normalized forecast dict.

    Adds friendly aliases required by some analytics/reporting layers:
    - predicted_direction: direction
    - horizon_hours: horizon_minutes / 60
    - forecast_timestamp: created_at (or forecast_time)
    - evaluation_timestamp: evaluated_at (or evaluation_time)

    Does not mutate the input.
    """
    r = dict(record or {})

    r.setdefault("predicted_direction", r.get("direction"))
    r.setdefault("horizon_hours", horizon_hours_from_minutes(r.get("horizon_minutes")))
    r.setdefault("forecast_timestamp", r.get("created_at") or r.get("forecast_time"))
    r.setdefault("evaluation_timestamp", r.get("evaluated_at") or r.get("evaluation_time"))

    # actual_price is allowed to be NULL until evaluated
    if "actual_price" not in r:
        r["actual_price"] = r.get("price_at_evaluation")

    return r
