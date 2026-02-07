"""Explainable strategy library for Strategy Lab."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable

import pandas as pd

from .donchian import donchian_breakout
from .ema import ema_crossover, ema_trend
from .rsi import rsi_mean_reversion


@dataclass(frozen=True)
class StrategySpec:
    id: str
    name: str
    description_template: str
    param_grid: dict[str, list]
    build_signals: Callable[[pd.DataFrame, dict], tuple[pd.Series, pd.Series]]


STRATEGIES: dict[str, StrategySpec] = {
    "ema_trend": StrategySpec(
        id="ema_trend",
        name="EMA Trend",
        description_template="Long when close is above EMA({ema_window}); exit when close falls below EMA({ema_window}).",
        param_grid={"ema_window": [20, 50, 100]},
        build_signals=ema_trend,
    ),
    "ema_crossover": StrategySpec(
        id="ema_crossover",
        name="EMA Crossover",
        description_template="Long on fast EMA({fast_ema}) crossing above slow EMA({slow_ema}); exit on bearish cross.",
        param_grid={"fast_ema": [10, 20], "slow_ema": [50, 100]},
        build_signals=ema_crossover,
    ),
    "rsi_mean_reversion": StrategySpec(
        id="rsi_mean_reversion",
        name="RSI Mean Reversion",
        description_template="Long when RSI({rsi_window}) < {entry_rsi}; exit when RSI > {exit_rsi}.",
        param_grid={"rsi_window": [14], "entry_rsi": [25, 30], "exit_rsi": [55, 60]},
        build_signals=rsi_mean_reversion,
    ),
    "donchian_breakout": StrategySpec(
        id="donchian_breakout",
        name="Donchian Breakout",
        description_template="Long when close breaks above {breakout_window}-bar high; exit below {exit_window}-bar low.",
        param_grid={"breakout_window": [20, 55], "exit_window": [10, 20]},
        build_signals=donchian_breakout,
    ),
}


def generate_candidates(max_runs: int) -> list[tuple[str, dict]]:
    """Generate deterministic strategy candidate tuples (strategy_id, params)."""
    candidates: list[tuple[str, dict]] = []
    for strategy_id, spec in STRATEGIES.items():
        keys = list(spec.param_grid.keys())
        values = [spec.param_grid[k] for k in keys]
        for combo in product(*values):
            candidates.append((strategy_id, dict(zip(keys, combo))))
    return candidates[:max_runs]


__all__ = ["StrategySpec", "STRATEGIES", "generate_candidates"]
