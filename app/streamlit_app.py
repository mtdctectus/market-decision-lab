from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "core"
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from market_decision_lab.backtest import BacktestParams, run_backtest
from market_decision_lab.data import fetch_ohlcv, select_symbol
from market_decision_lab.decision import evaluate_run, final_decision
from market_decision_lab.metrics import summarize_metrics
from market_decision_lab.scenarios import run_scenarios
from market_decision_lab.storage import init_db, load_runs, load_trades, save_candles, save_run, save_trades

ASSETS = ["BTC", "ETH", "SOL", "ADA", "AVAX", "LINK", "DOT", "MATIC", "LTC", "BCH"]

st.set_page_config(page_title="Market Decision Lab", layout="wide")
st.title("Market Decision Lab")
st.caption("Research-only decision support. No live trading. No financial advice.")

init_db()


def fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def save_single_run(exchange_name: str, symbol: str, tf: str, days_value: int, params: dict, metrics: dict, decision: dict, trades_df: pd.DataFrame):
    run_id = str(uuid.uuid4())
    run_ts = datetime.now(timezone.utc).isoformat()
    save_run(run_id, run_ts, exchange_name, symbol, tf, int(days_value), params, metrics, decision)
    save_trades(run_id, trades_df)


def render_error(message: str, exc: Exception):
    st.error(message)
    with st.expander("Details"):
        st.exception(exc)


def run_quick_check(inputs: dict):
    import ccxt

    exchange_obj = getattr(ccxt, inputs["exchange"])(
        {
            "enableRateLimit": True,
        }
    )
    markets = exchange_obj.load_markets()
    symbol = select_symbol(inputs["exchange"], inputs["asset"], markets)

    ohlcv_df = fetch_ohlcv(inputs["exchange"], symbol, inputs["timeframe"], int(inputs["days"]))
    save_candles(inputs["exchange"], symbol, inputs["timeframe"], ohlcv_df)

    params_obj = BacktestParams(
        ema_window=inputs["ema_window"],
        signal_mode=inputs["signal_mode"],
        entry_mode=inputs["entry_mode"],
        sl_mult=float(inputs["sl_mult"]),
        tp_mult=float(inputs["tp_mult"]),
        fee_per_side=float(inputs["fee"]),
        slippage_per_side=float(inputs["slippage"]),
    )

    bt_df, tr_df = run_backtest(ohlcv_df, params_obj)
    metrics = summarize_metrics(bt_df, tr_df, params_obj.initial_cash, int(inputs["days"]))
    decision = evaluate_run(metrics)

    save_single_run(
        inputs["exchange"],
        symbol,
        inputs["timeframe"],
        int(inputs["days"]),
        params_obj.__dict__,
        metrics,
        decision,
        tr_df,
    )

    return {
        "symbol": symbol,
        "backtest_df": bt_df,
        "trades_df": tr_df,
        "metrics": metrics,
        "decision": decision,
    }


def run_compare_check(inputs: dict):
    import ccxt

    exchange_obj = getattr(ccxt, inputs["exchange"])(
        {
            "enableRateLimit": True,
        }
    )
    markets = exchange_obj.load_markets()
    symbol = select_symbol(inputs["exchange"], inputs["asset"], markets)

    scenarios = run_scenarios(
        inputs["exchange"],
        symbol,
        int(inputs["days"]),
        initial_cash=10000,
        base_params={
            "entry_mode": inputs["entry_mode"],
            "sl_mult": inputs["sl_mult"],
            "tp_mult": inputs["tp_mult"],
            "fee_per_side": inputs["fee"],
            "slippage_per_side": inputs["slippage"],
        },
    )

    final = final_decision({k: scenarios[k] for k in ["A", "B", "C"]})

    for key in ["A", "B", "C"]:
        sc = scenarios[key]
        save_single_run(
            inputs["exchange"],
            symbol,
            sc["params"]["timeframe"],
            int(inputs["days"]),
            sc["params"],
            sc["metrics"],
            sc["decision"],
            sc["trades_df"],
        )

    return {
        "symbol": symbol,
        "scenarios": scenarios,
        "final": final,
    }


if "quick_result" not in st.session_state:
    st.session_state.quick_result = None
if "compare_result" not in st.session_state:
    st.session_state.compare_result = None

with st.sidebar:
    st.header("Controls")
    with st.form("controls_form"):
        exchange = st.selectbox("Exchange", ["kraken", "coinbase"], index=0)
        asset = st.selectbox("Asset", ASSETS, index=0)
        timeframe = st.selectbox("Timeframe", ["1h", "4h", "1d"], index=1)
        days = st.number_input("Days", min_value=7, max_value=365, value=30, step=1)

        with st.expander("Advanced", expanded=False):
            ema_window = st.selectbox("EMA window", [20, 50], index=0)
            signal_mode = st.selectbox("Signal mode", ["strict", "relaxed"], index=0)
            entry_mode = st.selectbox("Entry mode", ["next_open", "signal_close"], index=0)
            sl_mult = st.number_input("SL ATR multiple", min_value=0.5, max_value=5.0, value=1.5, step=0.1)
            tp_mult = st.number_input("TP ATR multiple", min_value=0.5, max_value=10.0, value=2.5, step=0.1)
            fee = st.number_input("Fee per side", min_value=0.0, max_value=0.01, value=0.0006, step=0.0001, format="%.4f")
            slippage = st.number_input(
                "Slippage per side",
                min_value=0.0,
                max_value=0.01,
                value=0.0002,
                step=0.0001,
                format="%.4f",
            )

        submitted_quick = st.form_submit_button("Run Quick Check", use_container_width=True)
        submitted_compare = st.form_submit_button("Run A/B/C Compare", use_container_width=True)

inputs = {
    "exchange": exchange,
    "asset": asset,
    "timeframe": timeframe,
    "days": int(days),
    "ema_window": ema_window,
    "signal_mode": signal_mode,
    "entry_mode": entry_mode,
    "sl_mult": float(sl_mult),
    "tp_mult": float(tp_mult),
    "fee": float(fee),
    "slippage": float(slippage),
}

if submitted_quick:
    try:
        with st.spinner("Computing…"):
            st.session_state.quick_result = run_quick_check(inputs)
    except Exception as exc:
        render_error("Quick check failed. Please verify inputs and try again.", exc)

if submitted_compare:
    try:
        with st.spinner("Computing…"):
            st.session_state.compare_result = run_compare_check(inputs)
    except Exception as exc:
        render_error("Scenario compare failed. Please verify inputs and try again.", exc)

quick_tab, compare_tab, history_tab = st.tabs(["Quick", "Compare", "History"])

with quick_tab:
    quick_result = st.session_state.quick_result
    if quick_result is None:
        st.info("Configure inputs in the sidebar and press **Run Quick Check**.")
    else:
        decision = quick_result["decision"]
        metrics = quick_result["metrics"]
        with st.container(border=True):
            st.subheader("Decision Summary")
            st.markdown(f"### {decision['color']} {decision['recommendation']}")
            st.write("; ".join(decision["reasons"]))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Annualized Return", fmt_pct(metrics["Annualized Return %"]))
        m2.metric("Max Drawdown", fmt_pct(metrics["Max Drawdown %"]))
        m3.metric("Trades", f"{metrics['Number of Trades']}")
        m4.metric("Expectancy", fmt_pct(metrics["Expectancy %"]))

        st.line_chart(quick_result["backtest_df"].set_index("ts")["equity"])
        st.dataframe(quick_result["trades_df"], use_container_width=True)

with compare_tab:
    compare_result = st.session_state.compare_result
    if compare_result is None:
        st.info("Configure inputs in the sidebar and press **Run A/B/C Compare**.")
    else:
        final = compare_result["final"]
        scenarios = compare_result["scenarios"]

        with st.container(border=True):
            st.subheader("Decision Summary")
            st.markdown(f"### {final['label']}")
            st.write(f"Recommended scenario: **{final['recommended']}**")
            st.write(final["text"])

        cards = st.columns(3)
        for idx, key in enumerate(["A", "B", "C"]):
            sc = scenarios[key]
            d = sc["decision"]
            with cards[idx]:
                with st.container(border=True):
                    st.markdown(f"#### Scenario {key}: {d['color']} {d['status']}")
                    st.write(f"Annualized Return: {fmt_pct(sc['metrics']['Annualized Return %'])}")
                    st.write(f"Max Drawdown: {fmt_pct(sc['metrics']['Max Drawdown %'])}")
                    st.write(f"Trades/Week: {sc['metrics']['Trades Per Week']:.2f}")
                    st.caption(d["recommendation"])

        chosen = st.selectbox("Inspect scenario", ["A", "B", "C"], index=0, key="compare_inspect_scenario")
        inspect = scenarios[chosen]
        st.line_chart(inspect["backtest_df"].set_index("ts")["equity"])
        st.dataframe(inspect["trades_df"], use_container_width=True)

with history_tab:
    st.subheader("History")
    runs = load_runs(limit=50)
    if runs.empty:
        st.info("No runs stored yet.")
    else:
        view_runs = runs[["run_ts", "exchange", "symbol", "timeframe", "days", "run_id"]].copy()
        st.dataframe(view_runs, use_container_width=True)
        run_id = st.selectbox("Load trades for run", view_runs["run_id"].tolist(), key="history_run_id")
        if run_id:
            trades = load_trades(run_id)
            st.dataframe(trades, use_container_width=True)
            selected = runs.loc[runs["run_id"] == run_id].iloc[0]
            st.json(
                {
                    "params": json.loads(selected["params_json"]),
                    "metrics": json.loads(selected["metrics_json"]),
                    "decision": json.loads(selected["decision_json"]),
                }
            )
