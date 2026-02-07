"""EMA-based strategy signal generators."""

from __future__ import annotations

import pandas as pd


def ema_trend(df: pd.DataFrame, params: dict) -> tuple[pd.Series, pd.Series]:
    ema = df["close"].ewm(span=int(params["ema_window"]), adjust=False).mean()
    entry = df["close"] > ema
    exit_ = df["close"] < ema
    return entry.fillna(False), exit_.fillna(False)


def ema_crossover(df: pd.DataFrame, params: dict) -> tuple[pd.Series, pd.Series]:
    fast = df["close"].ewm(span=int(params["fast_ema"]), adjust=False).mean()
    slow = df["close"].ewm(span=int(params["slow_ema"]), adjust=False).mean()
    spread = fast - slow
    entry = (spread > 0) & (spread.shift(1) <= 0)
    exit_ = (spread < 0) & (spread.shift(1) >= 0)
    return entry.fillna(False), exit_.fillna(False)
