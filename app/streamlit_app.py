from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import json
import os
import sqlite3
import time
import traceback
import uuid
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from mdl.backtest.engine import BacktestParams, run_backtest
from mdl.data.ohlcv import TIMEFRAME_TO_MINUTES, fetch_ohlcv, select_symbol
from mdl.decision import evaluate_run, final_decision
from mdl.backtest.metrics import summarize_metrics
from mdl.scenarios import run_scenarios
from mdl.lab.strategy_lab import OBJECTIVES, run_strategy_lab
from mdl.log_store import CsvLogStore, sanitize_meta, to_json_str, utc_now_iso
from mdl.storage import init_db, load_runs, load_trades, save_candles, save_run, save_trades

ASSETS = ["BTC", "ETH", "SOL", "ADA", "AVAX", "LINK", "DOT", "MATIC", "LTC", "BCH"]

TIMEFRAME_DAY_LIMITS = {"1h": 41, "4h": 166, "1d": 3650}
COMPARE_MAX_DAYS = 41
LAB_MAX_RUNS = 200

st.set_page_config(page_title="Market Decision Lab", layout="wide")
print("Startup OK")
st.caption("Startup OK")
st.title("Market Decision Lab")
st.caption("Research-only decision support. No live trading. No financial advice.")

init_db()

log_dir = Path(os.getenv("MDL_LOG_DIR", "app/data/logs"))
if not log_dir.is_absolute():
    log_dir = ROOT / log_dir
LOG_STORE = CsvLogStore(str(log_dir))
OFFLINE_MODE = os.getenv("MDL_OFFLINE", "0") == "1"
OFFLINE_FIXTURE_DIR = ROOT / "src" / "mdl" / "fixtures"


@st.cache_data(ttl=60 * 10, show_spinner=False)
def _offline_markets(exchange_name: str) -> dict:
    pairs = [f"{asset}/USD" for asset in ASSETS] + [f"{asset}/USDT" for asset in ASSETS]
    return {pair: {"symbol": pair, "exchange": exchange_name} for pair in pairs}


@st.cache_data(ttl=60 * 10, show_spinner=False)
def _offline_ohlcv(timeframe: str, days: int) -> pd.DataFrame:
    fixture_path = OFFLINE_FIXTURE_DIR / f"ohlcv_{timeframe}.csv"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Offline fixture not found: {fixture_path}")

    df = pd.read_csv(fixture_path)
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    candles_needed = max(50, int(days * 1440 / TIMEFRAME_TO_MINUTES[timeframe]))
    return df.tail(candles_needed).reset_index(drop=True)


@st.cache_data(ttl=60 * 10, show_spinner=False)
def _cached_markets(exchange_name: str) -> dict:
    """Cache exchange markets to speed up repeated runs in Streamlit."""
    if OFFLINE_MODE:
        return _offline_markets(exchange_name)

    import ccxt

    exchange_obj = getattr(ccxt, exchange_name)(
        {
            "enableRateLimit": True,
        }
    )
    return exchange_obj.load_markets()


@st.cache_data(ttl=60 * 10, show_spinner=False)
def _cached_ohlcv(exchange_name: str, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
    """Cache OHLCV pulls to reduce API calls and rate-limit risk."""
    if OFFLINE_MODE:
        return _offline_ohlcv(timeframe, days)

    return fetch_ohlcv(exchange_name, symbol, timeframe, days)


@st.cache_data(ttl=60 * 10, show_spinner=False)
def _cached_strategy_lab(
    exchange_name: str,
    symbol: str,
    timeframe: str,
    days: int,
    objective: str,
    max_runs: int,
    top_n: int,
) -> tuple[pd.DataFrame, dict]:
    ohlcv_df = _cached_ohlcv(exchange_name, symbol, timeframe, days)
    return run_strategy_lab(ohlcv_df, objective=objective, max_runs=max_runs, top_n=top_n)


def fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def load_runs_for_export(db_path: Path) -> tuple[pd.DataFrame, str | None]:
    """Load all runs for CSV export, returning a warning message when unavailable."""
    if not db_path.exists():
        return pd.DataFrame(), f"Database not found at `{db_path}`."

    try:
        with sqlite3.connect(db_path) as conn:
            runs = pd.read_sql_query("SELECT * FROM runs ORDER BY run_ts DESC", conn)
    except sqlite3.Error as exc:
        return pd.DataFrame(), f"Could not load runs for export: {exc}."

    return runs, None


def save_single_run(exchange_name: str, symbol: str, tf: str, days_value: int, params: dict, metrics: dict, decision: dict, trades_df: pd.DataFrame):
    run_id = str(uuid.uuid4())
    run_ts = datetime.now(timezone.utc).isoformat()
    save_run(run_id, run_ts, exchange_name, symbol, tf, int(days_value), params, metrics, decision)
    save_trades(run_id, trades_df)


def render_error(message: str, exc: Exception):
    st.error(message)
    with st.expander("Details"):
        st.exception(exc)


def decision_to_status(decision: dict) -> str:
    status = str(decision.get("status", "")).upper()
    if status == "GREEN":
        return "ok"
    if status == "YELLOW":
        return "warn"
    return "fail"


def append_event(run_id: str, level: str, stage: str, message: str, duration_ms: int | None = None, meta: dict | None = None):
    LOG_STORE.append_event(
        {
            "event_ts": utc_now_iso(),
            "run_id": run_id,
            "level": level,
            "stage": stage,
            "message": message,
            "duration_ms": duration_ms,
            "meta_json": to_json_str(sanitize_meta(meta or {})),
        }
    )


def append_error(run_id: str, exc: Exception, context: dict):
    tb = traceback.format_exc()
    lines = tb.splitlines()
    short_tb = "\n".join(lines[-30:])[-4000:]
    LOG_STORE.append_error(
        {
            "error_ts": utc_now_iso(),
            "run_id": run_id,
            "exc_type": type(exc).__name__,
            "exc_message": str(exc),
            "traceback_short": short_tb,
            "context_json": to_json_str(sanitize_meta(context)),
        }
    )


def run_quick_check(inputs: dict, run_id: str):
    append_event(run_id, "INFO", "run.started", "Quick check started", meta=inputs)
    append_event(run_id, "INFO", "data.load_markets", "Loading exchange markets", meta={"exchange": inputs["exchange"]})
    markets = _cached_markets(inputs["exchange"])
    symbol = select_symbol(inputs["exchange"], inputs["asset"], markets)

    append_event(run_id, "INFO", "data.fetch_ohlcv", "Fetching OHLCV candles", meta={"exchange": inputs["exchange"], "symbol": symbol, "timeframe": inputs["timeframe"], "days": int(inputs["days"])})
    fetch_start = time.perf_counter()
    ohlcv_df = _cached_ohlcv(inputs["exchange"], symbol, inputs["timeframe"], int(inputs["days"]))
    fetch_duration = int((time.perf_counter() - fetch_start) * 1000)
    append_event(
        run_id,
        "INFO",
        "data.fetch_ohlcv",
        "Fetched OHLCV candles",
        duration_ms=fetch_duration,
        meta={"exchange": inputs["exchange"], "symbol": symbol, "timeframe": inputs["timeframe"], "days": int(inputs["days"])} ,
    )
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
    append_event(run_id, "INFO", "decision.evaluate", "Evaluating decision")
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


def run_compare_check(inputs: dict, run_id: str):
    append_event(run_id, "INFO", "run.started", "Scenario compare started", meta=inputs)
    append_event(run_id, "INFO", "data.load_markets", "Loading exchange markets", meta={"exchange": inputs["exchange"]})
    markets = _cached_markets(inputs["exchange"])
    symbol = select_symbol(inputs["exchange"], inputs["asset"], markets)

    append_event(run_id, "INFO", "data.fetch_ohlcv", "Starting scenario data and backtests", meta={"exchange": inputs["exchange"], "symbol": symbol, "days": int(inputs["days"])})
    compare_start = time.perf_counter()
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
        ohlcv_fetcher=_cached_ohlcv,
    )
    compare_duration = int((time.perf_counter() - compare_start) * 1000)
    append_event(
        run_id,
        "INFO",
        "data.fetch_ohlcv",
        "Scenario data and backtests completed",
        duration_ms=compare_duration,
        meta={"exchange": inputs["exchange"], "symbol": symbol, "days": int(inputs["days"])},
    )

    append_event(run_id, "INFO", "decision.evaluate", "Building final scenario decision")
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


def run_app() -> None:
    if "quick_result" not in st.session_state:
        st.session_state.quick_result = None
    if "compare_result" not in st.session_state:
        st.session_state.compare_result = None
    if "strategy_lab_result" not in st.session_state:
        st.session_state.strategy_lab_result = None

    with st.sidebar:
        st.header("Controls")
        mode = st.selectbox("Mode", ["Quick Check", "A/B/C Compare", "Strategy Lab (Auto)"], index=0)
        with st.form("controls_form"):
            st.subheader("Quick / Compare")
            exchange = st.selectbox("Exchange", ["kraken", "coinbase"], index=0)
            asset = st.selectbox("Asset", ASSETS, index=0)
            timeframe = st.selectbox("Timeframe", ["1h", "4h", "1d"], index=1)
            quick_days_max = TIMEFRAME_DAY_LIMITS.get(timeframe, 365)
            days = st.number_input("Days", min_value=7, max_value=quick_days_max, value=min(30, quick_days_max), step=1)
            st.caption(f"Quick Check day limit for {timeframe}: {quick_days_max} (exchange API limit is 1000 candles).")
            st.caption(f"Compare mode is capped at {COMPARE_MAX_DAYS} days because it includes 1h candles (1000-candle API limit).")

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

            submitted_quick = st.form_submit_button("Run Quick Check", use_container_width=True, disabled=mode != "Quick Check")
            submitted_compare = st.form_submit_button("Run A/B/C Compare", use_container_width=True, disabled=mode != "A/B/C Compare")

        st.divider()
        st.subheader("Strategy Lab (Auto)")
        objective = st.selectbox("Objective", list(OBJECTIVES.keys()), index=0)
        max_runs = st.slider("Max strategy runs", min_value=10, max_value=LAB_MAX_RUNS, value=60, step=10)
        top_n = st.slider("Top strategies to display", min_value=3, max_value=20, value=10, step=1)
        submitted_lab = st.button("Run Strategy Lab", use_container_width=True, disabled=mode != "Strategy Lab (Auto)")

        st.divider()
        st.subheader("Export")
        if st.button("Export runs.csv", use_container_width=True):
            export_df, export_warning = load_runs_for_export(ROOT / "data" / "app.db")
            if export_warning:
                st.warning(export_warning)
                st.session_state.pop("runs_csv_export", None)
            elif export_df.empty:
                st.warning("No runs available to export.")
                st.session_state.pop("runs_csv_export", None)
            else:
                st.session_state.runs_csv_export = export_df.to_csv(index=False).encode("utf-8")

        if "runs_csv_export" in st.session_state:
            st.download_button(
                "Download runs.csv",
                data=st.session_state.runs_csv_export,
                file_name="runs.csv",
                mime="text/csv",
                use_container_width=True,
            )

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

    lab_inputs = {
        "exchange": exchange,
        "asset": asset,
        "timeframe": timeframe,
        "days": int(days),
        "objective": objective,
        "max_runs": int(max_runs),
        "top_n": int(top_n),
    }

    if submitted_quick:
        run_id = str(uuid.uuid4())
        run_started = time.perf_counter()
        rate_limit_hits = 0
        append_event(run_id, "INFO", "ui.submit", "User submitted quick check", meta=inputs)
        try:
            with st.spinner("Computing..."):
                st.session_state.quick_result = run_quick_check(inputs, run_id)
            latency_ms = int((time.perf_counter() - run_started) * 1000)
            quick_result = st.session_state.quick_result
            LOG_STORE.append_run(
                {
                    "run_id": run_id,
                    "run_ts": utc_now_iso(),
                    "exchange": inputs["exchange"],
                    "symbol": quick_result["symbol"],
                    "timeframe": inputs["timeframe"],
                    "days": int(inputs["days"]),
                    "status": decision_to_status(quick_result["decision"]),
                    "latency_ms": latency_ms,
                    "rate_limit_hits": rate_limit_hits,
                    "params_json": to_json_str(sanitize_meta(inputs)),
                    "metrics_json": to_json_str(quick_result["metrics"]),
                    "decision_json": to_json_str(quick_result["decision"]),
                }
            )
        except Exception as exc:
            if "Too many requests" in str(exc) or "DDoSProtection" in str(exc):
                rate_limit_hits += 1
            append_error(
                run_id,
                exc,
                {
                    "stage": "data.fetch_ohlcv",
                    "exchange": inputs["exchange"],
                    "symbol": inputs["asset"],
                    "timeframe": inputs["timeframe"],
                    "days": int(inputs["days"]),
                },
            )
            latency_ms = int((time.perf_counter() - run_started) * 1000)
            LOG_STORE.append_run(
                {
                    "run_id": run_id,
                    "run_ts": utc_now_iso(),
                    "exchange": inputs["exchange"],
                    "symbol": inputs["asset"],
                    "timeframe": inputs["timeframe"],
                    "days": int(inputs["days"]),
                    "status": "fail",
                    "latency_ms": latency_ms,
                    "rate_limit_hits": rate_limit_hits,
                    "params_json": to_json_str(sanitize_meta(inputs)),
                    "metrics_json": to_json_str({}),
                    "decision_json": to_json_str({}),
                }
            )
            render_error("Quick check failed. Please verify inputs and try again.", exc)

    if submitted_compare:
        if int(inputs["days"]) > COMPARE_MAX_DAYS:
            st.warning(f"Compare supports up to {COMPARE_MAX_DAYS} days to stay within exchange candle limits.")
        else:
            run_id = str(uuid.uuid4())
            run_started = time.perf_counter()
            rate_limit_hits = 0
            append_event(run_id, "INFO", "ui.submit", "User submitted scenario compare", meta=inputs)
            try:
                with st.spinner("Computing..."):
                    st.session_state.compare_result = run_compare_check(inputs, run_id)

                latency_ms = int((time.perf_counter() - run_started) * 1000)
                compare_result = st.session_state.compare_result
                final_decision_payload = compare_result["final"]
                final_status = "ok" if final_decision_payload.get("label") == "INVEST" else "warn"
                if final_decision_payload.get("label") == "NO":
                    final_status = "fail"
                LOG_STORE.append_run(
                    {
                        "run_id": run_id,
                        "run_ts": utc_now_iso(),
                        "exchange": inputs["exchange"],
                        "symbol": compare_result["symbol"],
                        "timeframe": inputs["timeframe"],
                        "days": int(inputs["days"]),
                        "status": final_status,
                        "latency_ms": latency_ms,
                        "rate_limit_hits": rate_limit_hits,
                        "params_json": to_json_str(sanitize_meta(inputs)),
                        "metrics_json": to_json_str({key: value["metrics"] for key, value in compare_result["scenarios"].items()}),
                        "decision_json": to_json_str(final_decision_payload),
                    }
                )
            except Exception as exc:
                if "Too many requests" in str(exc) or "DDoSProtection" in str(exc):
                    rate_limit_hits += 1
                append_error(
                    run_id,
                    exc,
                    {
                        "stage": "data.fetch_ohlcv",
                        "exchange": inputs["exchange"],
                        "symbol": inputs["asset"],
                        "timeframe": inputs["timeframe"],
                        "days": int(inputs["days"]),
                    },
                )
                latency_ms = int((time.perf_counter() - run_started) * 1000)
                LOG_STORE.append_run(
                    {
                        "run_id": run_id,
                        "run_ts": utc_now_iso(),
                        "exchange": inputs["exchange"],
                        "symbol": inputs["asset"],
                        "timeframe": inputs["timeframe"],
                        "days": int(inputs["days"]),
                        "status": "fail",
                        "latency_ms": latency_ms,
                        "rate_limit_hits": rate_limit_hits,
                        "params_json": to_json_str(sanitize_meta(inputs)),
                        "metrics_json": to_json_str({}),
                        "decision_json": to_json_str({}),
                    }
                )
                render_error("Scenario compare failed. Please verify inputs and try again.", exc)

    if submitted_lab:
        run_id = str(uuid.uuid4())
        append_event(run_id, "INFO", "ui.submit", "User submitted strategy lab", meta=lab_inputs)
        try:
            with st.spinner("Running auto strategy search..."):
                markets = _cached_markets(lab_inputs["exchange"])
                symbol = select_symbol(lab_inputs["exchange"], lab_inputs["asset"], markets)
                results_df, details = _cached_strategy_lab(
                    lab_inputs["exchange"],
                    symbol,
                    lab_inputs["timeframe"],
                    int(lab_inputs["days"]),
                    lab_inputs["objective"],
                    int(lab_inputs["max_runs"]),
                    int(lab_inputs["top_n"]),
                )
                st.session_state.strategy_lab_result = {
                    "symbol": symbol,
                    "results_df": results_df,
                    "details": details,
                    "inputs": lab_inputs,
                }
        except Exception as exc:
            append_error(run_id, exc, {"stage": "strategy_lab", **lab_inputs})
            render_error("Strategy Lab failed. Please verify inputs and try again.", exc)

    quick_tab, compare_tab, strategy_tab, history_tab = st.tabs(["Quick", "Compare", "Strategy Lab", "History"])

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

    with strategy_tab:
        st.caption("Research-only decision support. No live trading. No financial advice.")
        strategy_lab_result = st.session_state.strategy_lab_result
        if strategy_lab_result is None:
            st.info("Set Strategy Lab inputs in the sidebar and click **Run Strategy Lab**.")
        else:
            results_df = strategy_lab_result["results_df"]
            details = strategy_lab_result["details"]
            top_df = results_df.copy()

            st.subheader("Top Strategy Candidates")
            st.dataframe(
                top_df[["candidate_id", "strategy_name", "total_return_pct", "max_drawdown_pct", "sharpe", "win_rate", "n_trades", "params"]],
                use_container_width=True,
            )

            candidate_options = top_df["candidate_id"].tolist()
            selected_candidate = st.selectbox("Select strategy", candidate_options, key="strategy_lab_select")
            selected = details[selected_candidate]

            st.markdown("### Strategy Explanation")
            st.write(selected["description"])

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Return", fmt_pct(selected["metrics"]["total_return_pct"]))
            c2.metric("Max Drawdown", fmt_pct(selected["metrics"]["max_drawdown_pct"]))
            c3.metric("Sharpe", f"{selected['metrics']['sharpe']:.2f}")
            c4.metric("Win Rate", fmt_pct(selected["metrics"]["win_rate"]))

            st.line_chart(selected["backtest_df"].set_index("ts")["equity"])
            st.dataframe(selected["trades_df"], use_container_width=True)

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
                # Check if run_id exists in dataframe before accessing
                matching_runs = runs.loc[runs["run_id"] == run_id]
                if not matching_runs.empty:
                    selected = matching_runs.iloc[0]
                    st.json(
                        {
                            "params": json.loads(selected["params_json"]),
                            "metrics": json.loads(selected["metrics_json"]),
                            "decision": json.loads(selected["decision_json"]),
                        }
                    )
                else:
                    st.warning(f"Run {run_id} not found in loaded history.")


try:
    run_app()
except Exception as exc:
    print("Startup failure in app construction:", exc)
    traceback.print_exc()
    raise
