# Dahab AI — Architecture V2 (Stability + Decoupling)

This document describes the production-safe architecture changes for:
- Database stability and retention
- Decoupled subsystems (recommendations, evaluation, portfolio, training)
- Continuous multi-horizon recommendations + append-only history
- Statistical self-calibration (no retraining)

## 1) System Separation (Decoupled)

```mermaid
flowchart LR
  subgraph Ingestion[News Ingestion]
    RSS[Scrapers/RSS] --> N1[Normalize + Dedupe]
    N1 --> NDB[(news)]
    N1 --> NImp[Importance Classifier]
    NImp --> NDB
  end

  subgraph Reco[Recommendation Engine]
    NDB --> R1[Select analyzed/unprocessed news]
    PDB[(prices)] --> R2[Get latest prices]
    R1 --> R2
    R2 --> R3[Generate multi-horizon forecasts]
    CDB[(calibration_stats)] --> R4[Apply confidence weight]
    R3 --> R4
    R4 --> FDB[(forecasts)]
  end

  subgraph Eval[Forecast Evaluation Engine]
    FDB --> E1[Find due active forecasts]
    PDB --> E2[Fetch realized price near due_at]
    E1 --> E2
    E2 --> E3[Score + store metrics]
    E3 --> FDB
    E3 --> HDB[(recommendation_history)]
    E3 --> CDB
  end

  subgraph Port[Portfolio Engine (Optional Consumer)]
    FDB --> T1[Trade decision rules]
    T1 --> TDB[(paper_trades)]
    TDB --> PS[(paper_portfolio)]
  end

  subgraph Train[Training Simulator (Isolated)]
    TS[(training_simulator.db)]
  end

  %% Explicit non-dependencies
  Port -. does not gate .-> Reco
  Train -. no coupling .-> Reco
  Train -. no coupling .-> Eval
```

Key invariants:
- Recommendation generation does **not** depend on portfolio/trades.
- Evaluation does **not** depend on portfolio/trades.
- Training simulator is isolated (separate DB).

## 2) Database Stability Rules

### Stable DB path
- The canonical DB path is resolved from `dahab-ai/config.py`:
  - `DAHAB_DB_PATH` env var overrides everything.
  - Else DB lives under `dahab-ai/data/dahab_ai.db`.
- This eliminates “relative path” database resets when worker/UI run from different working directories.

### Non-destructive schema
- Migrations are additive only.
- No `DROP TABLE`, no destructive rebuild.

### Survival across restarts
- Streamlit restarts only reconnect to the same absolute SQLite file.
- SQLite WAL + busy timeout are enabled at connection time.

### Deletion detection
- Triggers log any `DELETE` on `news` or `forecasts` into `system_logs` (does not block; purely diagnostic).
- Startup integrity checks log if `news` rowcount drops sharply.

## 3) Revised Schema (Core Tables)

### `news`
- Stores all collected news.
- New additive columns:
  - `importance_score REAL`
  - `importance_level TEXT`

### `news_archive` (optional)
- Manual archive destination (copy-only). Never auto-populated.

### `prices`
- Time series snapshots.

### `forecasts` (recommendations)
- Each row is a recommendation for one asset and one horizon.
- Important fields (subset):
  - `news_id`, `asset`, `direction`, `confidence`, `risk_level`
  - `horizon_minutes`, `horizon_key` (`12h`, `24h`, `3d`, `7d`)
  - `created_at`, `due_at`
  - `price_at_forecast`, `predicted_price`
  - `reasoning`, `reasoning_tags`
  - `news_category`, `news_sentiment`, `impact_level`
  - `recommendation_group_id` (ties multi-horizon rows together)
  - lifecycle: `status` in `{active, evaluated, expired}`
  - evaluation: `actual_price`, `actual_time`, `evaluation_result`, `direction_correct`, `pred_abs_error`, `pred_pct_error`, `evaluated_at`

### `recommendation_history` (append-only)
- One row per `forecast_id` at evaluation time (unique constraint).
- Never deleted.
- Contains exactly the “history table” fields needed for long-term research:
  - asset, direction, entry price, horizon, predicted/actual price, accuracy %, confidence, tags, timestamps.

### `calibration_stats`
- Rolling segment accuracy and confidence weight:
  - keyed by `(asset, horizon_minutes, news_category, news_sentiment)`
  - stores `n_total`, `n_hit`, `rolling_accuracy`, `weight_multiplier`.

### Operational tables
- `system_logs`, `worker_status`, `db_meta`, `user_page_state`, `paper_trades`, `paper_portfolio`, `trade_counters`.

## 4) Recommendation Lifecycle

- **Active**: created and waiting for due time.
- **Evaluated**: due time passed and a realized price snapshot was found; metrics stored; row updated.
- **Expired**: due time passed but evaluation cannot be performed (e.g., missing prices long after due time). Row is retained.

No automatic deletion occurs in any lifecycle phase.

## 5) Self-Calibration (Statistical, No Retraining)

Mechanism:
1. Each evaluated forecast produces a binary outcome `hit ∈ {0,1}`.
2. For each segment `(asset, horizon, category, sentiment)` update:
   - `rolling_accuracy` via EWMA:
     - `rolling := (1-α) * rolling + α * (100*hit)` with α = 0.05
3. Convert rolling accuracy into a bounded confidence weight multiplier:
   - `weight = 0.75 + 0.5*(rolling_accuracy/100)` → bounded to `[0.6, 1.4]`
4. At recommendation generation time, scale confidence by `weight` and re-clip to global bounds.

This continuously self-calibrates signal strength without retraining models.

## 6) Safe Retention Policy

- Keep all `news`, `forecasts`, `recommendation_history`, and `calibration_stats` indefinitely.
- Optional archival is copy-only (`news_archive`).
- Backups are append-only; no automatic deletion of old backups.

## 7) Implementation Checklist (Practical)

1. Confirm environment DB location:
   - set `DAHAB_DB_PATH` explicitly in production (recommended).
2. Run worker once to apply additive migrations.
3. Confirm Streamlit UI and worker point to the same DB:
   - check `config.DATABASE_PATH` printed by diagnostics.
4. Verify multi-horizon generation rate:
   - each qualifying news event now yields 4 horizons per asset.
5. Verify evaluation updates history + calibration:
   - `recommendation_history` rows appear after due time.
   - `calibration_stats` begins populating as evaluations accumulate.
