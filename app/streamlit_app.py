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

with st.sidebar:
    st.header("Controls")
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
        slippage = st.number_input("Slippage per side", min_value=0.0, max_value=0.01, value=0.0002, step=0.0001, format="%.4f")

col1, col2 = st.columns(2)
run_quick = col1.button("Run Quick Check", use_container_width=True)
run_compare = col2.button("Run A/B/C Compare", use_container_width=True)


def save_single_run(symbol: str, tf: str, params: dict, metrics: dict, decision: dict, trades_df: pd.DataFrame):
    run_id = str(uuid.uuid4())
    run_ts = datetime.now(timezone.utc).isoformat()
    save_run(run_id, run_ts, exchange, symbol, tf, int(days), params, metrics, decision)
    save_trades(run_id, trades_df)


if run_quick:
    try:
        import ccxt

        exchange_obj = getattr(ccxt, exchange)({"enableRateLimit": True})
        markets = exchange_obj.load_markets()
        symbol = select_symbol(exchange, asset, markets)

        ohlcv_df = fetch_ohlcv(exchange, symbol, timeframe, int(days))
        save_candles(exchange, symbol, timeframe, ohlcv_df)

        params_obj = BacktestParams(
            ema_window=ema_window,
            signal_mode=signal_mode,
            entry_mode=entry_mode,
            sl_mult=float(sl_mult),
            tp_mult=float(tp_mult),
            fee_per_side=float(fee),
            slippage_per_side=float(slippage),
        )
        bt_df, tr_df = run_backtest(ohlcv_df, params_obj)
        metrics = summarize_metrics(bt_df, tr_df, params_obj.initial_cash, int(days))
        decision = evaluate_run(metrics)

        save_single_run(symbol, timeframe, params_obj.__dict__, metrics, decision, tr_df)

        top = st.container(border=True)
        top.subheader("Decision Summary")
        top.markdown(f"### {decision['color']} {decision['recommendation']}")
        top.write("; ".join(decision["reasons"]))

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Annualized Return %", f"{metrics['Annualized Return %']:.2f}")
        m2.metric("Max Drawdown %", f"{metrics['Max Drawdown %']:.2f}")
        m3.metric("Trades", f"{metrics['Number of Trades']}")
        m4.metric("Expectancy %", f"{metrics['Expectancy %']:.2f}")

        st.line_chart(bt_df.set_index("ts")["equity"])
        st.dataframe(tr_df, use_container_width=True)

    except Exception as exc:
        st.error(f"Quick check failed: {exc}")


if run_compare:
    try:
        import ccxt

        exchange_obj = getattr(ccxt, exchange)({"enableRateLimit": True})
        markets = exchange_obj.load_markets()
        symbol = select_symbol(exchange, asset, markets)

        scenarios = run_scenarios(
            exchange,
            symbol,
            int(days),
            initial_cash=10000,
            base_params={
                "entry_mode": entry_mode,
                "sl_mult": sl_mult,
                "tp_mult": tp_mult,
                "fee_per_side": fee,
                "slippage_per_side": slippage,
            },
        )

        final = final_decision({k: scenarios[k] for k in ["A", "B", "C"]})
        summary = st.container(border=True)
        summary.subheader("Decision Summary")
        summary.markdown(f"### {final['label']}")
        summary.write(f"Recommended scenario: **{final['recommended']}**")
        summary.write(final["text"])

        cards = st.columns(3)
        for idx, key in enumerate(["A", "B", "C"]):
            sc = scenarios[key]
            d = sc["decision"]
            with cards[idx]:
                st.container(border=True)
                st.markdown(f"#### Scenario {key}: {d['color']} {d['status']}")
                st.write(f"Annualized Return %: {sc['metrics']['Annualized Return %']:.2f}")
                st.write(f"Max Drawdown %: {sc['metrics']['Max Drawdown %']:.2f}")
                st.write(f"Trades/Week: {sc['metrics']['Trades Per Week']:.2f}")
                st.caption(d["recommendation"])

        chosen = st.selectbox("Inspect scenario", ["A", "B", "C"], index=0)
        inspect = scenarios[chosen]
        st.line_chart(inspect["backtest_df"].set_index("ts")["equity"])
        st.dataframe(inspect["trades_df"], use_container_width=True)

        for key in ["A", "B", "C"]:
            sc = scenarios[key]
            save_single_run(symbol, sc["params"]["timeframe"], sc["params"], sc["metrics"], sc["decision"], sc["trades_df"])

    except Exception as exc:
        st.error(f"Scenario compare failed: {exc}")

st.subheader("History")
runs = load_runs(limit=50)
if runs.empty:
    st.info("No runs stored yet.")
else:
    view_runs = runs[["run_ts", "exchange", "symbol", "timeframe", "days", "run_id"]].copy()
    st.dataframe(view_runs, use_container_width=True)
    run_id = st.selectbox("Load trades for run", view_runs["run_id"].tolist())
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
