"""RSI-based strategy signal generators."""

from __future__ import annotations

import pandas as pd


def _rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)
    avg_gain = gains.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = losses.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def rsi_mean_reversion(df: pd.DataFrame, params: dict) -> tuple[pd.Series, pd.Series]:
    rsi = _rsi(df["close"], window=int(params["rsi_window"]))
    entry = rsi < float(params["entry_rsi"])
    exit_ = rsi > float(params["exit_rsi"])
    return entry.fillna(False), exit_.fillna(False)
