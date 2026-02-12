"""Evaluation metrics engine.

Computes per-horizon and overall accuracy metrics from evaluated forecasts and
persists aggregated results into the additive `evaluation_summary` table.

Data safety:
- Never deletes or overwrites forecast history.
- Uses INSERTs into a dedicated summary table.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

import math

from forecast_logic import normalize_forecast_record


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None or str(x) == "":
            return None
        return float(x)
    except Exception:
        return None


def _safe_int(x: Any) -> Optional[int]:
    try:
        if x is None or str(x) == "":
            return None
        return int(float(x))
    except Exception:
        return None


def _sql_dt_expr(column: str) -> str:
    # Mirrors Database._sql_dt_expr
    return f"datetime(replace(substr({column},1,19),'T',' '))"


@dataclass(frozen=True)
class HorizonMetrics:
    asset: str
    horizon_minutes: Optional[int]
    horizon_key: Optional[str]
    window_days: int
    n_total: int
    n_hit: int
    directional_accuracy: Optional[float]
    mae: Optional[float]
    mape: Optional[float]
    avg_confidence: Optional[float]
    calibration_score: Optional[float]


def fetch_evaluated_forecasts(
    db,
    window_days: int = 60,
    asset: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch evaluated forecasts from forecasts table, robust to ISO timestamps."""
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(forecasts)")
    cols = {r[1] for r in cur.fetchall()}

    evaluated_col = "evaluated_at" if "evaluated_at" in cols else ("evaluation_time" if "evaluation_time" in cols else None)
    created_col = "created_at" if "created_at" in cols else ("forecast_time" if "forecast_time" in cols else None)
    if not evaluated_col or not created_col:
        conn.close()
        return []

    conditions = [f"{evaluated_col} IS NOT NULL", f"{evaluated_col} != ''"]
    params: List[Any] = []

    if asset and asset != "All":
        conditions.append("asset = ?")
        params.append(asset)

    if window_days and int(window_days) > 0:
        conditions.append(f"{_sql_dt_expr(evaluated_col)} >= datetime('now', ?)")
        params.append(f"-{int(window_days)} days")

    where = " AND ".join(conditions)
    cur.execute(
        f"""
        SELECT *
        FROM forecasts
        WHERE {where}
        ORDER BY {_sql_dt_expr(evaluated_col)} DESC, id DESC
        LIMIT 5000
        """,
        tuple(params),
    )
    rows = [normalize_forecast_record(dict(r)) for r in cur.fetchall()]
    conn.close()
    return rows


def _compute_calibration_score(confidence_pct: List[float], hits: List[int]) -> Optional[float]:
    """Return a 0..100 calibration score (higher is better)."""
    if not confidence_pct or not hits or len(confidence_pct) != len(hits):
        return None
    diffs = []
    for c, y in zip(confidence_pct, hits):
        try:
            p = max(0.0, min(float(c) / 100.0, 1.0))
            diffs.append(abs(p - float(y)))
        except Exception:
            continue
    if not diffs:
        return None
    return round(100.0 * (1.0 - (sum(diffs) / float(len(diffs)))), 3)


def compute_metrics(rows: Iterable[Dict[str, Any]], window_days: int, asset_label: str, horizon_minutes: Optional[int] = None, horizon_key: Optional[str] = None) -> HorizonMetrics:
    hits: List[int] = []
    abs_errors: List[float] = []
    pct_errors: List[float] = []
    confs: List[float] = []

    n_total = 0
    n_hit = 0

    for r in rows:
        n_total += 1

        # Hit/miss
        hit = None
        if r.get("direction_correct") is not None:
            hit = 1 if int(float(r.get("direction_correct") or 0)) == 1 else 0
        elif r.get("evaluation_result") is not None:
            hit = 1 if str(r.get("evaluation_result") or "").lower() == "hit" else 0
        else:
            hit = 0

        n_hit += int(hit)
        hits.append(int(hit))

        c = _safe_float(r.get("confidence"))
        if c is not None:
            confs.append(c)

        # Prefer predicted-price error metrics
        pe = _safe_float(r.get("pred_abs_error"))
        pp = _safe_float(r.get("pred_pct_error"))
        if pe is None:
            pe = _safe_float(r.get("abs_error"))
        if pp is None:
            pp = _safe_float(r.get("pct_error"))

        if pe is not None and not math.isnan(pe):
            abs_errors.append(pe)
        if pp is not None and not math.isnan(pp):
            pct_errors.append(pp)

    directional_accuracy = round((n_hit / n_total) * 100.0, 3) if n_total else None
    mae = round(sum(abs_errors) / len(abs_errors), 6) if abs_errors else None
    mape = round(sum(pct_errors) / len(pct_errors), 6) if pct_errors else None
    avg_conf = round(sum(confs) / len(confs), 3) if confs else None
    calib = _compute_calibration_score(confs, hits)

    return HorizonMetrics(
        asset=asset_label,
        horizon_minutes=horizon_minutes,
        horizon_key=horizon_key,
        window_days=int(window_days),
        n_total=int(n_total),
        n_hit=int(n_hit),
        directional_accuracy=directional_accuracy,
        mae=mae,
        mape=mape,
        avg_confidence=avg_conf,
        calibration_score=calib,
    )


def persist_summary(db, metrics: List[HorizonMetrics], weighted_overall: Dict[str, Any]) -> None:
    conn = db.get_connection()
    cur = conn.cursor()
    computed_at = _utc_now_iso()

    for m in metrics:
        cur.execute(
            """
            INSERT INTO evaluation_summary (
                computed_at, window_days, asset,
                horizon_minutes, horizon_key,
                n_total, n_hit,
                directional_accuracy, mae, mape,
                avg_confidence, calibration_score,
                weighted_overall_accuracy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                computed_at,
                int(m.window_days),
                m.asset,
                m.horizon_minutes,
                m.horizon_key,
                int(m.n_total),
                int(m.n_hit),
                m.directional_accuracy,
                m.mae,
                m.mape,
                m.avg_confidence,
                m.calibration_score,
                weighted_overall.get("accuracy"),
            ),
        )

    conn.commit()
    conn.close()

    try:
        db.log("INFO", "EvalSummary", f"Stored evaluation summary rows={len(metrics)} window_days={metrics[0].window_days if metrics else 'n/a'}")
    except Exception:
        pass


def compute_and_store_evaluation_summary(
    db,
    window_days: int = 60,
    assets: Optional[List[str]] = None,
    horizons: Optional[List[Tuple[str, int]]] = None,
) -> List[HorizonMetrics]:
    """Compute metrics per (asset,horizon) + weighted overall accuracy and persist to DB."""

    if horizons is None:
        horizons = [("15m", 15), ("60m", 60), ("6h", 360), ("12h", 720), ("48h", 2880), ("72h", 4320)]

    if assets is None:
        assets = ["Gold", "Silver", "Oil", "Bitcoin", "USD Index"]

    all_metrics: List[HorizonMetrics] = []

    # Weighted overall across horizons for ALL assets combined
    weighted_total = 0
    weighted_hits = 0

    for asset in assets:
        rows_asset = fetch_evaluated_forecasts(db, window_days=window_days, asset=asset)
        if not rows_asset:
            continue

        for hk, hm in horizons:
            rows_h = [r for r in rows_asset if _safe_int(r.get("horizon_minutes")) == int(hm)]
            if not rows_h:
                continue
            m = compute_metrics(rows_h, window_days=window_days, asset_label=asset, horizon_minutes=int(hm), horizon_key=hk)
            all_metrics.append(m)
            weighted_total += m.n_total
            weighted_hits += m.n_hit

    weighted_overall_acc = (weighted_hits / weighted_total * 100.0) if weighted_total else None

    persist_summary(
        db,
        all_metrics,
        weighted_overall={"accuracy": weighted_overall_acc, "n_total": weighted_total},
    )

    return all_metrics
