"""Scenario sweep and selection logic."""

from __future__ import annotations

from dataclasses import asdict
from itertools import product

from .backtest import BacktestParams, run_backtest
from .config import DD_MAX, TPW_TARGET
from .data import fetch_ohlcv
from .decision import evaluate_run
from .metrics import summarize_metrics


def _stability_score(metrics: dict) -> float:
    dd_decimal = metrics["Max Drawdown %"] / 100.0
    return 1 / (1 + dd_decimal + abs(metrics["Trades Per Week"] - TPW_TARGET))


def run_scenarios(exchange: str, symbol: str, days: int, initial_cash: float, base_params: dict | None = None) -> dict:
    base_params = base_params or {}
    candidates = []

    for timeframe, ema_window, signal_mode in product(["1h", "4h", "1d"], [20, 50], ["strict", "relaxed"]):
        ohlcv_df = fetch_ohlcv(exchange, symbol, timeframe, days)
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

    used_ids = set()

    sorted_a = sorted(
        candidates,
        key=lambda c: (
            c["metrics"]["Expectancy %"],
            -c["metrics"]["Max Drawdown %"],
            -abs(c["metrics"]["Trades Per Week"] - TPW_TARGET),
        ),
        reverse=True,
    )
    scenario_a = next(c for c in sorted_a if id(c) not in used_ids)
    used_ids.add(id(scenario_a))

    b_eligible = [c for c in candidates if c["metrics"]["Max Drawdown %"] <= DD_MAX and id(c) not in used_ids]
    if b_eligible:
        scenario_b = sorted(b_eligible, key=lambda c: c["metrics"]["Annualized Return %"], reverse=True)[0]
    else:
        scenario_b = sorted(
            [c for c in candidates if id(c) not in used_ids],
            key=lambda c: c["metrics"]["Annualized Return %"],
            reverse=True,
        )[0]
        scenario_b["risk_exceeded"] = True
    used_ids.add(id(scenario_b))

    c_options = [c for c in candidates if id(c) not in used_ids]
    scenario_c = sorted(c_options, key=lambda c: _stability_score(c["metrics"]), reverse=True)[0]

    return {"A": scenario_a, "B": scenario_b, "C": scenario_c, "all_candidates": candidates}
