"""Auto Strategy Lab orchestration and ranking."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from mdl.backtest.engine import BacktestParams, run_backtest_signals
from mdl.strategies import STRATEGIES, generate_candidates

OBJECTIVES = {
    "Sharpe": ("sharpe", False),
    "Return": ("total_return_pct", False),
    "Min Drawdown": ("max_drawdown_pct", True),
    "Win Rate": ("win_rate", False),
}


def _compute_strategy_metrics(backtest_df: pd.DataFrame, trades_df: pd.DataFrame, initial_cash: float) -> dict:
    final_equity = float(backtest_df["equity"].iloc[-1]) if not backtest_df.empty else float(initial_cash)
    total_return_pct = float(((final_equity / initial_cash) - 1) * 100)

    if backtest_df.empty:
        max_drawdown_pct = 0.0
        sharpe = 0.0
    else:
        rolling_peak = backtest_df["equity"].cummax()
        drawdown = (backtest_df["equity"] - rolling_peak) / rolling_peak.replace(0, np.nan)
        max_drawdown_pct = abs(float(drawdown.min() * 100)) if not drawdown.isna().all() else 0.0

        equity_ret = backtest_df["equity"].pct_change().dropna()
        std = float(equity_ret.std()) if not equity_ret.empty else 0.0
        sharpe = 0.0 if std == 0.0 else float((equity_ret.mean() / std) * math.sqrt(252))

    n_trades = int(len(trades_df))
    win_rate = float((trades_df["pnl"] > 0).mean() * 100) if n_trades else 0.0

    return {
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": max_drawdown_pct,
        "sharpe": sharpe,
        "win_rate": win_rate,
        "n_trades": n_trades,
    }


def run_strategy_lab(
    ohlcv_df: pd.DataFrame,
    objective: str,
    max_runs: int,
    top_n: int,
) -> tuple[pd.DataFrame, dict[str, dict]]:
    """Run strategy candidates, rank by objective, and return top results with details."""
    if ohlcv_df.empty:
        raise ValueError("Input OHLCV data is empty")
    if objective not in OBJECTIVES:
        raise ValueError(f"Unsupported objective: {objective}. Valid options are {list(OBJECTIVES.keys())}")
    if max_runs < 1:
        raise ValueError("max_runs must be >= 1")
    if top_n < 1:
        raise ValueError("top_n must be >= 1")

    params = BacktestParams()
    rows: list[dict] = []
    details: dict[str, dict] = {}

    for idx, (strategy_id, strategy_params) in enumerate(generate_candidates(max_runs=max_runs)):
        spec = STRATEGIES[strategy_id]
        entry_signal, exit_signal = spec.build_signals(ohlcv_df, strategy_params)
        backtest_df, trades_df = run_backtest_signals(ohlcv_df, entry_signal, exit_signal, params)
        metrics = _compute_strategy_metrics(backtest_df, trades_df, params.initial_cash)

        candidate_id = f"{strategy_id}__{idx}"
        description = spec.description_template.format(**strategy_params)
        rows.append(
            {
                "candidate_id": candidate_id,
                "strategy_id": strategy_id,
                "strategy_name": spec.name,
                "params": strategy_params,
                "description": description,
                **metrics,
            }
        )
        details[candidate_id] = {
            "strategy_id": strategy_id,
            "strategy_name": spec.name,
            "params": strategy_params,
            "description": description,
            "backtest_df": backtest_df,
            "trades_df": trades_df,
            "metrics": metrics,
        }

    results_df = pd.DataFrame(rows)
    sort_key, ascending = OBJECTIVES[objective]
    ranked_df = results_df.sort_values(by=[sort_key, "total_return_pct"], ascending=[ascending, False]).reset_index(drop=True)
    top_df = ranked_df.head(top_n).reset_index(drop=True)
    top_ids = set(top_df["candidate_id"].tolist())
    top_details = {candidate_id: payload for candidate_id, payload in details.items() if candidate_id in top_ids}
    return top_df, top_details
