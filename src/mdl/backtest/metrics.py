"""Performance metric summary functions."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def summarize_metrics(backtest_df: pd.DataFrame, trades_df: pd.DataFrame, initial_cash: float, test_days: int) -> dict:
    """Generate standardized performance metrics dict."""
    final_equity = float(backtest_df["equity"].iloc[-1]) if not backtest_df.empty else float(initial_cash)
    total_return_decimal = (final_equity / initial_cash) - 1
    annualized_return = ((1 + total_return_decimal) ** (365 / max(1, test_days)) - 1) * 100

    if backtest_df.empty:
        max_drawdown = 0.0
    else:
        rolling_peak = backtest_df["equity"].cummax()
        drawdown = (backtest_df["equity"] - rolling_peak) / rolling_peak.replace(0, np.nan)
        max_drawdown = abs(float(drawdown.min() * 100)) if not drawdown.isna().all() else 0.0

    trade_count = int(len(trades_df))
    trades_per_week = trade_count / max(1, (test_days / 7))

    if trade_count > 0:
        win_rate = float((trades_df["pnl"] > 0).mean() * 100)
        expectancy = float(trades_df["pnl_pct"].mean())
        profits = float(trades_df.loc[trades_df["pnl"] > 0, "pnl"].sum())
        losses = float(trades_df.loc[trades_df["pnl"] < 0, "pnl"].sum())
    else:
        win_rate = 0.0
        expectancy = 0.0
        profits = 0.0
        losses = 0.0

    if losses == 0 and profits > 0:
        profit_factor = math.inf
    elif losses == 0:
        profit_factor = 0.0
    else:
        profit_factor = profits / abs(losses)

    return {
        "Total Return %": float(total_return_decimal * 100),
        "Annualized Return %": float(annualized_return),
        "Final Equity": float(final_equity),
        "Max Drawdown %": float(max_drawdown),
        "Number of Trades": trade_count,
        "Trades Per Week": float(trades_per_week),
        "Win Rate %": float(win_rate),
        "Expectancy %": float(expectancy),
        "Profit Factor": float(profit_factor) if math.isfinite(profit_factor) else math.inf,
        "Test Days": int(test_days),
    }
