"""Scenario sweep and selection logic."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict
from itertools import product
from typing import Any

from .backtest import BacktestParams, run_backtest
from .config import DD_MAX, TPW_TARGET
from .data import fetch_ohlcv
from .decision import evaluate_run
from .metrics import summarize_metrics


def _stability_score(metrics: dict) -> float:
    dd_decimal = metrics["Max Drawdown %"] / 100.0
    return 1 / (1 + dd_decimal + abs(metrics["Trades Per Week"] - TPW_TARGET))


def _select_best(candidates: list[dict], key: Callable[[dict], Any], reverse: bool = True) -> dict:
    """Helper to safely select best candidate from a list."""
    if not candidates:
        raise ValueError("Cannot select from empty candidates list")
    return sorted(candidates, key=key, reverse=reverse)[0]


def run_scenarios(
    exchange: str,
    symbol: str,
    days: int,
    initial_cash: float,
    base_params: dict | None = None,
    ohlcv_fetcher: Callable[[str, str, str, int], Any] = fetch_ohlcv,
) -> dict:
    """Run scenario sweep with injectable OHLCV fetcher to support UI-level caching."""
    base_params = base_params or {}
    candidates = []
    timeframe_data = {timeframe: ohlcv_fetcher(exchange, symbol, timeframe, days) for timeframe in ["1h", "4h", "1d"]}

    for timeframe, ema_window, signal_mode in product(["1h", "4h", "1d"], [20, 50], ["strict", "relaxed"]):
        ohlcv_df = timeframe_data[timeframe]
        params = BacktestParams(
            ema_window=ema_window,
            signal_mode=signal_mode,
            entry_mode=base_params.get("entry_mode", "next_open"),
            sl_mult=float(base_params.get("sl_mult", 1.5)),
            tp_mult=float(base_params.get("tp_mult", 2.5)),
            fee_per_side=float(base_params.get("fee_per_side", 0.0006)),
            slippage_per_side=float(base_params.get("slippage_per_side", 0.0002)),
            initial_cash=float(initial_cash),
        )

        bt_df, tr_df = run_backtest(ohlcv_df, params)
        metrics = summarize_metrics(bt_df, tr_df, initial_cash=initial_cash, test_days=days)
        decision = evaluate_run(metrics)
        candidates.append(
            {
                "params": {**asdict(params), "timeframe": timeframe},
                "backtest_df": bt_df,
                "trades_df": tr_df,
                "metrics": metrics,
                "decision": decision,
                "risk_exceeded": metrics["Max Drawdown %"] > DD_MAX,
            }
        )

    if not candidates:
        raise ValueError("No scenarios generated - check data availability")

    def sig(c: dict) -> tuple:
        p = c.get("params", {})
        return (p.get("timeframe"), p.get("ema_window"), p.get("signal_mode"))

    used = set()

    # Scenario A: Best expectancy with balanced risk
    # Find first unused scenario, fallback to best if all used
    unused_a = [c for c in candidates if sig(c) not in used]
    if unused_a:
        scenario_a = _select_best(
            unused_a,
            key=lambda c: (
                c["metrics"]["Expectancy %"],
                -c["metrics"]["Max Drawdown %"],
                -abs(c["metrics"]["Trades Per Week"] - TPW_TARGET),
            ),
        )
    else:
        scenario_a = _select_best(
            candidates,
            key=lambda c: (
                c["metrics"]["Expectancy %"],
                -c["metrics"]["Max Drawdown %"],
                -abs(c["metrics"]["Trades Per Week"] - TPW_TARGET),
            ),
        )
    used.add(sig(scenario_a))

    # Scenario B: Best return within risk limits
    b_eligible = [c for c in candidates if c["metrics"]["Max Drawdown %"] <= DD_MAX and sig(c) not in used]
    if b_eligible:
        scenario_b = _select_best(b_eligible, key=lambda c: c["metrics"]["Annualized Return %"])
    else:
        b_candidates = [c for c in candidates if sig(c) not in used]
        if b_candidates:
            scenario_b = _select_best(b_candidates, key=lambda c: c["metrics"]["Annualized Return %"])
        else:
            # Fallback: reuse a scenario if all are used
            scenario_b = _select_best(candidates, key=lambda c: c["metrics"]["Annualized Return %"])
        scenario_b["risk_exceeded"] = True
    used.add(sig(scenario_b))

    # Scenario C: Most stable/consistent
    c_options = [c for c in candidates if sig(c) not in used]
    if c_options:
        scenario_c = _select_best(c_options, key=lambda c: _stability_score(c["metrics"]))
    else:
        # Fallback: reuse a scenario if all are used
        scenario_c = _select_best(candidates, key=lambda c: _stability_score(c["metrics"]))
    used.add(sig(scenario_c))

    return {"A": scenario_a, "B": scenario_b, "C": scenario_c, "all_candidates": candidates}
