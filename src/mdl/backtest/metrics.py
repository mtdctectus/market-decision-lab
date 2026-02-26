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


def walk_forward_score(ohlcv_df: pd.DataFrame, params, initial_cash: float) -> dict:
    """Split OHLCV data 70/30, backtest each portion, and assess out-of-sample robustness.

    Args:
        ohlcv_df: Full OHLCV DataFrame with a ``ts`` column.
        params: ``BacktestParams`` instance used for both backtest runs.
        initial_cash: Starting capital for both backtest runs.

    Returns:
        Dict with keys:
            ``in_sample``     – metrics dict for the first 70 % of data.
            ``out_of_sample`` – metrics dict for the remaining 30 % of data.
            ``is_robust``     – True when the out-of-sample run is profitable
                                and its drawdown does not exceed 1.5× the
                                in-sample drawdown.
    """
    from mdl.backtest.engine import run_backtest  # local import avoids circular dependency

    if ohlcv_df.empty:
        raise ValueError("ohlcv_df is empty; cannot run walk-forward split.")

    n = len(ohlcv_df)
    split = max(1, int(n * 0.7))

    in_df = ohlcv_df.iloc[:split].reset_index(drop=True)
    out_df = ohlcv_df.iloc[split:].reset_index(drop=True)

    def _days(df: pd.DataFrame) -> int:
        if "ts" in df.columns and len(df) >= 2:
            delta = pd.to_datetime(df["ts"].iloc[-1]) - pd.to_datetime(df["ts"].iloc[0])
            return max(1, int(delta.total_seconds() / 86400))
        return max(1, len(df))

    in_bt, in_tr = run_backtest(in_df, params)
    out_bt, out_tr = run_backtest(out_df, params)

    in_metrics = summarize_metrics(in_bt, in_tr, initial_cash=initial_cash, test_days=_days(in_df))
    out_metrics = summarize_metrics(out_bt, out_tr, initial_cash=initial_cash, test_days=_days(out_df))

    in_dd = in_metrics["Max Drawdown %"]
    out_dd = out_metrics["Max Drawdown %"]
    is_robust = (
        out_metrics["Annualized Return %"] > 0
        and out_dd <= max(in_dd * 1.5, 1.0)  # allow slight degradation but not runaway drawdown
    )

    return {
        "in_sample": in_metrics,
        "out_of_sample": out_metrics,
        "is_robust": is_robust,
    }
