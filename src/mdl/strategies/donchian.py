"""Donchian breakout strategy signal generators."""

from __future__ import annotations

import pandas as pd


def donchian_breakout(df: pd.DataFrame, params: dict) -> tuple[pd.Series, pd.Series]:
    breakout_n = int(params["breakout_window"])
    exit_n = int(params["exit_window"])
    rolling_high = df["high"].rolling(window=breakout_n, min_periods=breakout_n).max().shift(1)
    rolling_low = df["low"].rolling(window=exit_n, min_periods=exit_n).min().shift(1)
    entry = df["close"] > rolling_high
    exit_ = df["close"] < rolling_low
    return entry.fillna(False), exit_.fillna(False)
