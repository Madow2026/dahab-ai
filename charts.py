"""Plotly chart builders (production-safe).

All functions are defensive against empty/small datasets.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import math
import pandas as pd
import plotly.graph_objects as go


def dual_line_forecast_actual(df: pd.DataFrame, x_col: str, forecast_col: str, actual_col: str, title: str) -> go.Figure:
    fig = go.Figure()

    if df is None or df.empty:
        fig.update_layout(title=title)
        return fig

    if x_col in df.columns and forecast_col in df.columns:
        d1 = df.dropna(subset=[x_col, forecast_col])
        if not d1.empty:
            fig.add_trace(go.Scatter(x=d1[x_col], y=d1[forecast_col], mode="lines+markers", name="Predicted"))

    has_actual = False
    if x_col in df.columns and actual_col in df.columns:
        d2 = df.dropna(subset=[x_col, actual_col])
        if not d2.empty:
            has_actual = True
            fig.add_trace(go.Scatter(x=d2[x_col], y=d2[actual_col], mode="lines+markers", name="Actual"))

    if not has_actual:
        fig.add_annotation(
            text="Awaiting evaluation",
            xref="paper",
            yref="paper",
            x=0.01,
            y=0.99,
            showarrow=False,
        )

    fig.update_layout(
        title=title,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        height=360,
        margin=dict(l=10, r=10, t=40, b=10),
    )
    return fig


def _drawdown_from_equity(equity: pd.Series) -> pd.Series:
    if equity is None or equity.empty:
        return pd.Series(dtype=float)
    peak = equity.cummax()
    dd = (equity / peak - 1.0) * 100.0
    return dd


def performance_triplet(daily_df: pd.DataFrame, date_col: str = "date") -> Dict[str, go.Figure]:
    """Return cumulative growth, daily bar, and drawdown figures.

    Expects columns:
    - predicted_return_pct
    - actual_return_pct
    """
    figs: Dict[str, go.Figure] = {}
    if daily_df is None or daily_df.empty:
        figs["cumulative"] = go.Figure().update_layout(title="Cumulative Growth")
        figs["daily"] = go.Figure().update_layout(title="Daily Gain/Loss")
        figs["drawdown"] = go.Figure().update_layout(title="Drawdown")
        return figs

    df = daily_df.copy()
    if date_col in df.columns:
        df = df.sort_values(date_col)

    # Cumulative curves
    cum_fig = go.Figure()
    for col, name in [("predicted_return_pct", "Predicted"), ("actual_return_pct", "Actual")]:
        if col not in df.columns:
            continue
        r = pd.to_numeric(df[col], errors="coerce").fillna(0.0) / 100.0
        equity = (1.0 + r).cumprod()
        cum = (equity - 1.0) * 100.0
        cum_fig.add_trace(go.Scatter(x=df[date_col], y=cum, mode="lines+markers", name=name))

    cum_fig.update_layout(title="Cumulative Growth Curve", height=320, margin=dict(l=10, r=10, t=40, b=10))
    figs["cumulative"] = cum_fig

    # Daily bars
    daily_fig = go.Figure()
    if "actual_return_pct" in df.columns:
        daily_fig.add_trace(go.Bar(x=df[date_col], y=df["actual_return_pct"], name="Actual"))
    if "predicted_return_pct" in df.columns:
        daily_fig.add_trace(go.Bar(x=df[date_col], y=df["predicted_return_pct"], name="Predicted"))
    daily_fig.update_layout(title="Daily Gain/Loss", barmode="group", height=320, margin=dict(l=10, r=10, t=40, b=10))
    figs["daily"] = daily_fig

    # Drawdown (Actual)
    dd_fig = go.Figure()
    if "actual_return_pct" in df.columns:
        r = pd.to_numeric(df["actual_return_pct"], errors="coerce").fillna(0.0) / 100.0
        equity = (1.0 + r).cumprod()
        dd = _drawdown_from_equity(equity)
        dd_fig.add_trace(go.Scatter(x=df[date_col], y=dd, mode="lines", name="Drawdown"))
    dd_fig.update_layout(title="Drawdown", height=320, margin=dict(l=10, r=10, t=40, b=10))
    figs["drawdown"] = dd_fig

    return figs
