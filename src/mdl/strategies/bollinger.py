"""Bollinger Bands-based strategy signal generators."""

from __future__ import annotations

import pandas as pd


def _bollinger_bands(
    series: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Compute Bollinger Bands: middle (SMA), upper, lower."""
    middle = series.rolling(window=window).mean()
    std = series.rolling(window=window).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return middle, upper, lower


def bollinger_mean_reversion(df: pd.DataFrame, params: dict) -> tuple[pd.Series, pd.Series]:
    """Mean reversion: long when price touches lower band, exit at middle band.

    Classic counter-trend strategy — works well in ranging markets.

    Params:
        bb_window  - rolling window for SMA and std (default 20)
        bb_std     - number of standard deviations for bands (default 2.0)
    """
    middle, upper, lower = _bollinger_bands(
        df["close"],
        window=int(params["bb_window"]),
        num_std=float(params["bb_std"]),
    )
    entry = df["close"] <= lower
    exit_ = df["close"] >= middle
    return entry.fillna(False), exit_.fillna(False)


def bollinger_breakout(df: pd.DataFrame, params: dict) -> tuple[pd.Series, pd.Series]:
    """Breakout: long when price closes above upper band (momentum squeeze release);
    exit when price falls back below middle band.

    Works well in trending markets after periods of low volatility.

    Params:
        bb_window  - rolling window for SMA and std (default 20)
        bb_std     - number of standard deviations for bands (default 2.0)
    """
    middle, upper, lower = _bollinger_bands(
        df["close"],
        window=int(params["bb_window"]),
        num_std=float(params["bb_std"]),
    )
    entry = df["close"] > upper
    exit_ = df["close"] < middle
    return entry.fillna(False), exit_.fillna(False)
