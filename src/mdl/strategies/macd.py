"""MACD-based strategy signal generators."""

from __future__ import annotations

import pandas as pd


def _macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute MACD line, signal line, and histogram."""
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def macd_crossover(df: pd.DataFrame, params: dict) -> tuple[pd.Series, pd.Series]:
    """Long when MACD line crosses above signal line; exit on bearish cross.

    Params:
        fast_period   - fast EMA period (default 12)
        slow_period   - slow EMA period (default 26)
        signal_period - signal EMA period (default 9)
    """
    macd_line, signal_line, _ = _macd(
        df["close"],
        fast=int(params["fast_period"]),
        slow=int(params["slow_period"]),
        signal=int(params["signal_period"]),
    )
    spread = macd_line - signal_line
    entry = (spread > 0) & (spread.shift(1) <= 0)
    exit_ = (spread < 0) & (spread.shift(1) >= 0)
    return entry.fillna(False), exit_.fillna(False)


def macd_histogram_reversal(df: pd.DataFrame, params: dict) -> tuple[pd.Series, pd.Series]:
    """Long when MACD histogram turns from negative to positive (momentum shift);
    exit when histogram turns from positive to negative.

    More sensitive than crossover — catches earlier entries.

    Params:
        fast_period   - fast EMA period (default 12)
        slow_period   - slow EMA period (default 26)
        signal_period - signal EMA period (default 9)
    """
    _, _, histogram = _macd(
        df["close"],
        fast=int(params["fast_period"]),
        slow=int(params["slow_period"]),
        signal=int(params["signal_period"]),
    )
    entry = (histogram > 0) & (histogram.shift(1) <= 0)
    exit_ = (histogram < 0) & (histogram.shift(1) >= 0)
    return entry.fillna(False), exit_.fillna(False)
