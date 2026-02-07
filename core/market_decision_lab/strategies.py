"""Simple explainable strategy library for Strategy Lab."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class StrategySpec:
    id: str
    name: str
    description_template: str
    param_grid: dict[str, list]
    build_signals: Callable[[pd.DataFrame, dict], tuple[pd.Series, pd.Series]]


def _rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)
    avg_gain = gains.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = losses.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def _ema_trend(df: pd.DataFrame, params: dict) -> tuple[pd.Series, pd.Series]:
    ema = df["close"].ewm(span=int(params["ema_window"]), adjust=False).mean()
    entry = df["close"] > ema
    exit_ = df["close"] < ema
    return entry.fillna(False), exit_.fillna(False)


def _ema_crossover(df: pd.DataFrame, params: dict) -> tuple[pd.Series, pd.Series]:
    fast = df["close"].ewm(span=int(params["fast_ema"]), adjust=False).mean()
    slow = df["close"].ewm(span=int(params["slow_ema"]), adjust=False).mean()
    spread = fast - slow
    entry = (spread > 0) & (spread.shift(1) <= 0)
    exit_ = (spread < 0) & (spread.shift(1) >= 0)
    return entry.fillna(False), exit_.fillna(False)


def _rsi_mean_reversion(df: pd.DataFrame, params: dict) -> tuple[pd.Series, pd.Series]:
    rsi = _rsi(df["close"], window=int(params["rsi_window"]))
    entry = rsi < float(params["entry_rsi"])
    exit_ = rsi > float(params["exit_rsi"])
    return entry.fillna(False), exit_.fillna(False)


def _donchian_breakout(df: pd.DataFrame, params: dict) -> tuple[pd.Series, pd.Series]:
    breakout_n = int(params["breakout_window"])
    exit_n = int(params["exit_window"])
    rolling_high = df["high"].rolling(window=breakout_n, min_periods=breakout_n).max().shift(1)
    rolling_low = df["low"].rolling(window=exit_n, min_periods=exit_n).min().shift(1)
    entry = df["close"] > rolling_high
    exit_ = df["close"] < rolling_low
    return entry.fillna(False), exit_.fillna(False)


STRATEGIES: dict[str, StrategySpec] = {
    "ema_trend": StrategySpec(
        id="ema_trend",
        name="EMA Trend",
        description_template="Long when close is above EMA({ema_window}); exit when close falls below EMA({ema_window}).",
        param_grid={"ema_window": [20, 50, 100]},
        build_signals=_ema_trend,
    ),
    "ema_crossover": StrategySpec(
        id="ema_crossover",
        name="EMA Crossover",
        description_template="Long when EMA({fast_ema}) crosses above EMA({slow_ema}); exit when EMA({fast_ema}) crosses below EMA({slow_ema}).",
        param_grid={"fast_ema": [10, 20], "slow_ema": [50, 100]},
        build_signals=_ema_crossover,
    ),
    "rsi_mean_reversion": StrategySpec(
        id="rsi_mean_reversion",
        name="RSI Mean Reversion",
        description_template="Long when RSI({rsi_window}) is below {entry_rsi}; exit when RSI({rsi_window}) is above {exit_rsi}.",
        param_grid={"rsi_window": [14], "entry_rsi": [25, 30], "exit_rsi": [50, 55]},
        build_signals=_rsi_mean_reversion,
    ),
    "donchian_breakout": StrategySpec(
        id="donchian_breakout",
        name="Donchian Breakout",
        description_template="Long when close breaks above the prior {breakout_window}-bar high; exit when close falls below the prior {exit_window}-bar low.",
        param_grid={"breakout_window": [20, 50], "exit_window": [10, 20]},
        build_signals=_donchian_breakout,
    ),
}


def generate_candidates(max_runs: int = 160) -> list[tuple[str, dict]]:
    """Generate deterministic (strategy_id, params) candidates capped by ``max_runs``."""
    if max_runs < 1:
        return []

    candidates: list[tuple[str, dict]] = []
    for strategy_id, spec in STRATEGIES.items():
        keys = list(spec.param_grid.keys())
        values = [spec.param_grid[key] for key in keys]
        for combo in product(*values):
            params = dict(zip(keys, combo))
            candidates.append((strategy_id, params))
            if len(candidates) >= max_runs:
                return candidates

    return candidates
