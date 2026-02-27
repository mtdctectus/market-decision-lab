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
from mdl.logging_helpers import extract_scenario_metrics
from mdl.log_store import CsvLogStore, sanitize_meta, to_json_str, utc_now_iso
from mdl.storage import init_db, load_runs, load_trades, save_candles, save_run, save_trades

from ui_guards import can_run_compare, can_run_strategy_lab, validate_timeframe_for_exchange

ASSETS = ["BTC", "ETH", "SOL", "ADA", "AVAX", "LINK", "DOT", "MATIC", "LTC", "BCH"]

TIMEFRAME_DAY_LIMITS = {"1h": 41, "4h": 166, "1d": 3650}
COMPARE_MAX_DAYS = 41
LAB_MAX_RUNS = 200

st.set_page_config(page_title="Market Decision Lab", layout="wide")
print("Startup OK")
st.caption("Startup OK")
st.title("📊 Market Decision Lab")
st.caption("Research-only decision support. No live trading. No financial advice.")

init_db()

log_dir = Path(os.getenv("MDL_LOG_DIR", "app/data/logs"))
if not log_dir.is_absolute():
    log_dir = ROOT / log_dir
LOG_STORE = CsvLogStore(str(log_dir))
OFFLINE_MODE = os.getenv("MDL_OFFLINE", "0") == "1"
OFFLINE_FIXTURE_DIR = ROOT / "src" / "mdl" / "fixtures"


# ── UI helpers ──────────────────────────────────────────────────────────────

DECISION_STYLES = {
    "INVEST": {"emoji": "🟢", "color": "#1a7a1a", "bg": "#e6f4e6"},
    "CAUTION": {"emoji": "🟡", "color": "#7a6a00", "bg": "#fdf8e1"},
    "NO":     {"emoji": "🔴", "color": "#7a1a1a", "bg": "#fde8e8"},
    "GREEN":  {"emoji": "🟢", "color": "#1a7a1a", "bg": "#e6f4e6"},
    "YELLOW": {"emoji": "🟡", "color": "#7a6a00", "bg": "#fdf8e1"},
    "RED":    {"emoji": "🔴", "color": "#7a1a1a", "bg": "#fde8e8"},
}


def render_decision_badge(label: str, text: str = "") -> None:
    """Render a big coloured decision badge."""
    style = DECISION_STYLES.get(label.upper(), {"emoji": "⚪", "color": "#555", "bg": "#f0f0f0"})
    display = text or label
    st.markdown(
        f"""
        <div style="
            background:{style['bg']};
            border-left:6px solid {style['color']};
            border-radius:8px;
            padding:16px 20px;
            margin-bottom:12px;
        ">
            <span style="font-size:2rem;">{style['emoji']}</span>
            <span style="font-size:1.4rem; font-weight:700; color:{style['color']}; margin-left:10px;">
                {display}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_scenario_card(key: str, sc: dict, is_recommended: bool = False) -> None:
    """Render a scenario card with metrics and colour coding."""
    d = sc["decision"]
    m = sc["metrics"]
    style = DECISION_STYLES.get(d["status"].upper(), DECISION_STYLES["RED"])
    border = "3px solid gold" if is_recommended else f"2px solid {style['color']}"

    ann = m.get("Annualized Return %", 0)
    dd = m.get("Max Drawdown %", 0)
    tpw = m.get("Trades Per Week", 0)
    exp = m.get("Expectancy %", 0)

    recommended_badge = "⭐ Recommended" if is_recommended else ""

    st.markdown(
        f"""
        <div style="
            background:{style['bg']};
            border:{border};
            border-radius:10px;
            padding:14px 16px;
            height:100%;
        ">
            <div style="font-size:1.1rem; font-weight:700; color:{style['color']};">
                {style['emoji']} Scenario {key}: {d['status']}
                {'<span style="color:gold; margin-left:8px;">⭐</span>' if is_recommended else ''}
            </div>
            <div style="font-size:0.8rem; color:#888; margin-bottom:8px;">{recommended_badge}</div>
            <table style="width:100%; font-size:0.9rem;">
                <tr><td>📈 Ann. Return</td><td style="font-weight:600; text-align:right;">{ann:.2f}%</td></tr>
                <tr><td>📉 Max Drawdown</td><td style="font-weight:600; text-align:right;">{dd:.2f}%</td></tr>
                <tr><td>🔄 Trades/Week</td><td style="font-weight:600; text-align:right;">{tpw:.2f}</td></tr>
                <tr><td>💡 Expectancy</td><td style="font-weight:600; text-align:right;">{exp:.2f}%</td></tr>
            </table>
            <div style="font-size:0.8rem; color:{style['color']}; margin-top:8px; font-style:italic;">
                {d['recommendation']}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_comparison_table(scenarios: dict) -> None:
    """Render a summary comparison table for all scenarios."""
    rows = []
    for key in ["A", "B", "C"]:
        sc = scenarios[key]
        m = sc["metrics"]
        d = sc["decision"]
        style = DECISION_STYLES.get(d["status"].upper(), DECISION_STYLES["RED"])
        rows.append({
            "Scenario": f"{style['emoji']} {key}",
            "Status": d["status"],
            "Ann. Return %": round(m.get("Annualized Return %", 0), 2),
            "Max Drawdown %": round(m.get("Max Drawdown %", 0), 2),
            "Trades/Week": round(m.get("Trades Per Week", 0), 2),
            "Expectancy %": round(m.get("Expectancy %", 0), 2),
            "# Trades": int(m.get("Number of Trades", 0)),
            "Score": round(sc["decision"].get("score", 0), 3),
        })
    df = pd.DataFrame(rows).set_index("Scenario")
    st.dataframe(df, use_container_width=True)


# ── Cached helpers ───────────────────────────────────────────────────────────

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
    if OFFLINE_MODE:
        return _offline_markets(exchange_name)

    import ccxt

    exchange_obj = getattr(ccxt, exchange_name)({"enableRateLimit": True})
    return exchange_obj.load_markets()


def _cached_ohlcv(
    exchange_name: str,
    symbol: str,
    timeframe: str,
    days: int,
    *,
    use_cache: bool = True,
    max_retries: int = 1,
    backoff_s: int = 1,
) -> pd.DataFrame:
    if OFFLINE_MODE:
        return _offline_ohlcv(timeframe, days)

    return fetch_ohlcv(
        exchange_name,
        symbol,
        timeframe,
        days,
        use_cache=use_cache,
        max_retries=max_retries,
        backoff_s=backoff_s,
    )


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
    ohlcv_df = _cached_ohlcv(exchange_name, symbol, timeframe, days, use_cache=True, max_retries=1, backoff_s=1)
    return run_strategy_lab(ohlcv_df, objective=objective, max_runs=max_runs, top_n=top_n)


def fmt_pct(value: float) -> str:
    return f"{value:.2f}%"


def load_runs_for_export(db_path: Path) -> tuple[pd.DataFrame, str | None]:
    if not db_path.exists():
        return pd.DataFrame(), f"Database not found at `{db_path}`."

    try:
        with sqlite3.connect(db_path) as conn:
            runs = pd.read_sql_query("SELECT * FROM runs ORDER BY run_ts DESC", conn)
    except sqlite3.Error as exc:
        return pd.DataFrame(), f"Could not load runs for export: {exc}."

    return runs, None


def save_single_run(exchange_name, symbol, tf, days_value, params, metrics, decision, trades_df):
    run_id = str(uuid.uuid4())
    run_ts = datetime.now(timezone.utc).isoformat()
    save_run(run_id, run_ts, exchange_name, symbol, tf, int(days_value), params, metrics, decision)
    save_trades(run_id, trades_df)


def render_error(message: str, exc: Exception, *, show_debug: bool = False):
    st.error(message)
    st.caption(f"Debug: {exc}")
    if show_debug:
        with st.expander("Details"):
            st.exception(exc)


def is_retryable_exchange_error(exc: Exception) -> bool:
    try:
        import ccxt
    except Exception:
        return False

    return isinstance(
        exc,
        (
            ccxt.DDoSProtection,
            ccxt.RateLimitExceeded,
            ccxt.RequestTimeout,
            ccxt.NetworkError,
            ccxt.ExchangeNotAvailable,
        ),
    )


def render_fetch_error(exc: Exception, *, show_debug: bool = False):
    if is_retryable_exchange_error(exc):
        st.error(
            "Could not complete the request because the exchange is rate-limiting or the network timed out. "
            "Try reducing Days, running again shortly, or switching exchange."
        )
        st.caption(f"Debug: {exc}")
        if show_debug:
            with st.expander("Details"):
                st.exception(exc)
        return

    render_error("Run failed. Please verify inputs and try again.", exc, show_debug=show_debug)


def render_inputs_summary(exchange_name, symbol, timeframes, days, scenarios_count):
    st.caption(
        f"Inputs summary: exchange={exchange_name}, symbol={symbol}, timeframe(s)={timeframes}, days={days}, scenarios={scenarios_count}"
    )


def decision_to_status(decision: dict) -> str:
    status = str(decision.get("status", "")).upper()
    if status == "GREEN":
        return "ok"
    if status == "YELLOW":
        return "warn"
    return "fail"


def append_event(run_id, level, stage, message, duration_ms=None, meta=None):
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


def append_error(run_id, exc, context):
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


# ── Run logic ────────────────────────────────────────────────────────────────

def run_quick_check(inputs, run_id, data_opts):
    append_event(run_id, "INFO", "run.started", "Quick check started", meta=inputs)
    markets = _cached_markets(inputs["exchange"])
    symbol = select_symbol(inputs["exchange"], inputs["asset"], markets)

    fetch_start = time.perf_counter()
    ohlcv_df = _cached_ohlcv(
        inputs["exchange"], symbol, inputs["timeframe"], int(inputs["days"]),
        use_cache=bool(data_opts["use_cache"]),
        max_retries=int(data_opts["max_retries"]),
        backoff_s=int(data_opts["backoff_s"]),
    )
    fetch_duration = int((time.perf_counter() - fetch_start) * 1000)
    append_event(run_id, "INFO", "data.fetch_ohlcv", "Fetched OHLCV candles", duration_ms=fetch_duration)
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

    save_single_run(inputs["exchange"], symbol, inputs["timeframe"], int(inputs["days"]),
                    params_obj.__dict__, metrics, decision, tr_df)

    return {
        "symbol": symbol,
        "backtest_df": bt_df,
        "trades_df": tr_df,
        "metrics": metrics,
        "decision": decision,
        "inputs": inputs.copy(),
    }


def run_compare_check(inputs, run_id, data_opts):
    append_event(run_id, "INFO", "run.started", "Scenario compare started", meta=inputs)
    markets = _cached_markets(inputs["exchange"])
    symbol = select_symbol(inputs["exchange"], inputs["asset"], markets)

    compare_start = time.perf_counter()
    scenarios = run_scenarios(
        inputs["exchange"], symbol, int(inputs["days"]),
        initial_cash=10000,
        base_params={
            "entry_mode": inputs["entry_mode"],
            "sl_mult": inputs["sl_mult"],
            "tp_mult": inputs["tp_mult"],
            "fee_per_side": inputs["fee"],
            "slippage_per_side": inputs["slippage"],
        },
        ohlcv_fetcher=lambda ex, sym, tf, dd: _cached_ohlcv(
            ex, sym, tf, dd,
            use_cache=bool(data_opts["use_cache"]),
            max_retries=int(data_opts["max_retries"]),
            backoff_s=int(data_opts["backoff_s"]),
        ),
    )
    compare_duration = int((time.perf_counter() - compare_start) * 1000)
    append_event(run_id, "INFO", "data.fetch_ohlcv", "Scenario backtests completed", duration_ms=compare_duration)

    final = final_decision({k: scenarios[k] for k in ["A", "B", "C"]})

    for key in ["A", "B", "C"]:
        sc = scenarios[key]
        save_single_run(inputs["exchange"], symbol, sc["params"]["timeframe"], int(inputs["days"]),
                        sc["params"], sc["metrics"], sc["decision"], sc["trades_df"])

    return {"symbol": symbol, "scenarios": scenarios, "final": final, "inputs": inputs.copy()}


# ── Main app ─────────────────────────────────────────────────────────────────

def run_app() -> None:
    if "quick_result" not in st.session_state:
        st.session_state.quick_result = None
    if "compare_result" not in st.session_state:
        st.session_state.compare_result = None
    if "strategy_lab_result" not in st.session_state:
        st.session_state.strategy_lab_result = None

    def reset_session_results() -> None:
        keys_to_clear = ["quick_result", "compare_result", "strategy_lab_result", "runs_csv_export"]
        keys_to_clear.extend(
            key for key in st.session_state.keys()
            if key.startswith("run_") or key.endswith("_error") or key.endswith("_lock")
        )
        for key in set(keys_to_clear):
            st.session_state.pop(key, None)

    submitted_quick = False
    submitted_compare = False
    submitted_lab = False

    with st.sidebar:
        st.header("⚙️ Controls")
        st.subheader("Quick / Compare")
        exchange = st.selectbox("Exchange", ["kraken", "coinbase"], index=0)
        asset = st.selectbox("Asset", ASSETS, index=0)
        timeframe = st.selectbox("Timeframe", ["1h", "4h", "1d"], index=1)
        quick_days_max = TIMEFRAME_DAY_LIMITS.get(timeframe, 365)
        days = st.number_input("Days", min_value=7, max_value=quick_days_max, value=min(30, quick_days_max), step=1)
        st.caption(f"Quick Check day limit for {timeframe}: {quick_days_max} (exchange API limit is 1000 candles).")
        st.caption(f"Compare mode is capped at {COMPARE_MAX_DAYS} days because it includes 1h candles.")

        with st.expander("Backtest settings", expanded=False):
            ema_window = st.selectbox("EMA window", [20, 50], index=0)
            signal_mode = st.selectbox("Signal mode", ["strict", "relaxed"], index=0)
            entry_mode = st.selectbox("Entry mode", ["next_open", "signal_close"], index=0)
            sl_mult = st.number_input("SL ATR multiple", min_value=0.5, max_value=5.0, value=1.5, step=0.1)
            tp_mult = st.number_input("TP ATR multiple", min_value=0.5, max_value=10.0, value=2.5, step=0.1)
            fee = st.number_input("Fee per side", min_value=0.0, max_value=0.01, value=0.0006, step=0.0001, format="%.4f")
            slippage = st.number_input("Slippage per side", min_value=0.0, max_value=0.01, value=0.0002, step=0.0001, format="%.4f")

        st.subheader("🧪 Strategy Lab (Auto)")
        objective = st.selectbox("Objective", list(OBJECTIVES.keys()), index=0)
        max_runs = st.slider("Max strategy runs", min_value=10, max_value=LAB_MAX_RUNS, value=60, step=10)
        top_n = st.slider("Top strategies to display", min_value=3, max_value=20, value=10, step=1)

        with st.expander("Advanced", expanded=False):
            use_cached_data = st.checkbox("Use cached data when available", value=True)
            show_debug_details = st.checkbox("Show debug details", value=False)
            max_retries = st.selectbox("Max retries", [0, 1, 2, 3], index=1)
            retry_backoff = st.selectbox("Retry backoff (seconds)", [0, 1, 2, 5], index=1)
            if st.button("♻ Reset session", use_container_width=True):
                reset_session_results()
                st.rerun()

        st.divider()
        st.subheader("▶ Actions")
        submitted_quick = st.button("▶ Run Quick Check", use_container_width=True, type="primary")
        submitted_compare = st.button("▶▶ Run A/B/C Compare", use_container_width=True)
        submitted_lab = st.button("🧪 Run Strategy Lab (Auto)", use_container_width=True)

        st.divider()
        st.subheader("📥 Export")
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
        "exchange": exchange, "asset": asset, "timeframe": timeframe, "days": int(days),
        "ema_window": ema_window, "signal_mode": signal_mode, "entry_mode": entry_mode,
        "sl_mult": float(sl_mult), "tp_mult": float(tp_mult),
        "fee": float(fee), "slippage": float(slippage),
    }

    lab_inputs = {
        "exchange": exchange, "asset": asset, "timeframe": timeframe, "days": int(days),
        "objective": objective, "max_runs": int(max_runs), "top_n": int(top_n),
    }

    data_opts = {
        "use_cache": bool(use_cached_data), "show_debug": bool(show_debug_details),
        "max_retries": int(max_retries), "backoff_s": int(retry_backoff),
    }

    timeframe_ok, timeframe_msg = validate_timeframe_for_exchange(inputs["exchange"], inputs["timeframe"])
    compare_ok, compare_msg = can_run_compare(inputs)
    strategy_ok, strategy_msg = can_run_strategy_lab(dict(st.session_state))

    if not timeframe_ok:
        st.sidebar.caption(f"Quick Check: {timeframe_msg}")
    if not compare_ok:
        st.sidebar.caption(f"A/B/C Compare: {compare_msg}")
    if not strategy_ok:
        st.sidebar.caption(f"Strategy Lab: {strategy_msg}")

    # ── Run handlers ──────────────────────────────────────────────────────────

    if submitted_quick:
        if not timeframe_ok:
            st.info(timeframe_msg)
        else:
            run_id = str(uuid.uuid4())
            run_started = time.perf_counter()
            rate_limit_hits = 0
            append_event(run_id, "INFO", "ui.submit", "User submitted quick check", meta=inputs)
            try:
                with st.spinner("⏳ Computing..."):
                    st.session_state.quick_result = run_quick_check(inputs, run_id, data_opts)
                latency_ms = int((time.perf_counter() - run_started) * 1000)
                quick_result = st.session_state.quick_result
                LOG_STORE.append_run({
                    "run_id": run_id, "run_ts": utc_now_iso(),
                    "exchange": inputs["exchange"], "symbol": quick_result["symbol"],
                    "timeframe": inputs["timeframe"], "days": int(inputs["days"]),
                    "status": decision_to_status(quick_result["decision"]),
                    "latency_ms": latency_ms, "rate_limit_hits": rate_limit_hits,
                    "params_json": to_json_str(sanitize_meta(inputs)),
                    "metrics_json": to_json_str(quick_result["metrics"]),
                    "decision_json": to_json_str(quick_result["decision"]),
                })
            except Exception as exc:
                if is_retryable_exchange_error(exc):
                    rate_limit_hits += 1
                append_error(run_id, exc, {"stage": "data.fetch_ohlcv", **inputs})
                latency_ms = int((time.perf_counter() - run_started) * 1000)
                LOG_STORE.append_run({
                    "run_id": run_id, "run_ts": utc_now_iso(),
                    "exchange": inputs["exchange"], "symbol": inputs["asset"],
                    "timeframe": inputs["timeframe"], "days": int(inputs["days"]),
                    "status": "fail", "latency_ms": latency_ms, "rate_limit_hits": rate_limit_hits,
                    "params_json": to_json_str(sanitize_meta(inputs)),
                    "metrics_json": to_json_str({}), "decision_json": to_json_str({}),
                })
                render_fetch_error(exc, show_debug=bool(data_opts["show_debug"]))

    if submitted_compare:
        if not compare_ok:
            st.info(compare_msg)
        else:
            run_id = str(uuid.uuid4())
            run_started = time.perf_counter()
            rate_limit_hits = 0
            append_event(run_id, "INFO", "ui.submit", "User submitted scenario compare", meta=inputs)
            try:
                with st.spinner("⏳ Running A/B/C scenarios..."):
                    st.session_state.compare_result = run_compare_check(inputs, run_id, data_opts)
                latency_ms = int((time.perf_counter() - run_started) * 1000)
                compare_result = st.session_state.compare_result
                final_decision_payload = compare_result["final"]
                final_status = "ok" if final_decision_payload.get("label") == "INVEST" else "warn"
                if final_decision_payload.get("label") == "NO":
                    final_status = "fail"
                LOG_STORE.append_run({
                    "run_id": run_id, "run_ts": utc_now_iso(),
                    "exchange": inputs["exchange"], "symbol": compare_result["symbol"],
                    "timeframe": inputs["timeframe"], "days": int(inputs["days"]),
                    "status": final_status, "latency_ms": latency_ms, "rate_limit_hits": rate_limit_hits,
                    "params_json": to_json_str(sanitize_meta(inputs)),
                    "metrics_json": to_json_str(extract_scenario_metrics(compare_result["scenarios"])),
                    "decision_json": to_json_str(final_decision_payload),
                })
            except Exception as exc:
                if is_retryable_exchange_error(exc):
                    rate_limit_hits += 1
                append_error(run_id, exc, {"stage": "data.fetch_ohlcv", **inputs})
                latency_ms = int((time.perf_counter() - run_started) * 1000)
                LOG_STORE.append_run({
                    "run_id": run_id, "run_ts": utc_now_iso(),
                    "exchange": inputs["exchange"], "symbol": inputs["asset"],
                    "timeframe": inputs["timeframe"], "days": int(inputs["days"]),
                    "status": "fail", "latency_ms": latency_ms, "rate_limit_hits": rate_limit_hits,
                    "params_json": to_json_str(sanitize_meta(inputs)),
                    "metrics_json": to_json_str({}), "decision_json": to_json_str({}),
                })
                render_fetch_error(exc, show_debug=bool(data_opts["show_debug"]))

    if submitted_lab:
        if not strategy_ok:
            st.info(strategy_msg)
        else:
            run_id = str(uuid.uuid4())
            append_event(run_id, "INFO", "ui.submit", "User submitted strategy lab", meta=lab_inputs)
            try:
                with st.spinner("🧪 Running auto strategy search..."):
                    markets = _cached_markets(lab_inputs["exchange"])
                    symbol = select_symbol(lab_inputs["exchange"], lab_inputs["asset"], markets)
                    results_df, details = _cached_strategy_lab(
                        lab_inputs["exchange"], symbol, lab_inputs["timeframe"],
                        int(lab_inputs["days"]), lab_inputs["objective"],
                        int(lab_inputs["max_runs"]), int(lab_inputs["top_n"]),
                    )
                    st.session_state.strategy_lab_result = {
                        "symbol": symbol, "results_df": results_df,
                        "details": details, "inputs": lab_inputs,
                    }
            except Exception as exc:
                append_error(run_id, exc, {"stage": "strategy_lab", **lab_inputs})
                render_error("Strategy Lab failed. Please verify inputs and try again.", exc, show_debug=bool(data_opts["show_debug"]))

    # ── Tabs ──────────────────────────────────────────────────────────────────

    quick_tab, compare_tab, strategy_tab, history_tab = st.tabs(["⚡ Quick", "📊 Compare", "🧪 Strategy Lab", "📜 History"])

    with quick_tab:
        quick_result = st.session_state.quick_result
        if quick_result is None:
            st.info("Configure inputs in the sidebar and press **Run Quick Check**.")
        else:
            render_inputs_summary(
                quick_result["inputs"]["exchange"], quick_result["symbol"],
                quick_result["inputs"]["timeframe"], int(quick_result["inputs"]["days"]), 1,
            )
            decision = quick_result["decision"]
            metrics = quick_result["metrics"]

            with st.container(border=True):
                st.subheader("Decision Summary")
                render_decision_badge(decision["color"], decision["recommendation"])
                for reason in decision["reasons"]:
                    st.write(f"• {reason}")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("📈 Ann. Return", fmt_pct(metrics["Annualized Return %"]))
            m2.metric("📉 Max Drawdown", fmt_pct(metrics["Max Drawdown %"]))
            m3.metric("🔄 Trades", f"{metrics['Number of Trades']}")
            m4.metric("💡 Expectancy", fmt_pct(metrics["Expectancy %"]))

            st.subheader("Equity Curve")
            st.line_chart(quick_result["backtest_df"].set_index("ts")["equity"])
            st.subheader("Trades")
            st.dataframe(quick_result["trades_df"], use_container_width=True)

    with compare_tab:
        compare_result = st.session_state.compare_result
        if compare_result is None:
            st.info("Configure inputs in the sidebar and press **Run A/B/C Compare**.")
        else:
            render_inputs_summary(
                compare_result["inputs"]["exchange"], compare_result["symbol"],
                "1h, 4h, 1d", int(compare_result["inputs"]["days"]), 3,
            )
            final = compare_result["final"]
            scenarios = compare_result["scenarios"]

            with st.container(border=True):
                st.subheader("Final Decision")
                render_decision_badge(final["label"], final["text"])
                st.write(f"**Recommended scenario:** {final['recommended']}")
                st.caption(final["reason"])

            st.subheader("Scenario Comparison")
            render_comparison_table(scenarios)

            cards = st.columns(3)
            for idx, key in enumerate(["A", "B", "C"]):
                with cards[idx]:
                    render_scenario_card(key, scenarios[key], is_recommended=(key == final["recommended"]))

            st.subheader("Inspect Scenario")
            chosen = st.selectbox("Select scenario", ["A", "B", "C"], index=0, key="compare_inspect_scenario")
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

            st.subheader("🏆 Top Strategy Candidates")
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
            c1.metric("📈 Return", fmt_pct(selected["metrics"]["total_return_pct"]))
            c2.metric("📉 Max Drawdown", fmt_pct(selected["metrics"]["max_drawdown_pct"]))
            c3.metric("📐 Sharpe", f"{selected['metrics']['sharpe']:.2f}")
            c4.metric("🎯 Win Rate", fmt_pct(selected["metrics"]["win_rate"]))

            st.line_chart(selected["backtest_df"].set_index("ts")["equity"])
            st.dataframe(selected["trades_df"], use_container_width=True)

    with history_tab:
        st.subheader("📜 History")
        runs = load_runs(limit=50)
        if runs.empty:
            st.info("No runs stored yet.")
        else:
            view_runs = runs[["run_ts", "exchange", "symbol", "timeframe", "days", "run_id"]].copy()
            st.dataframe(view_runs, use_container_width=True)
            run_id_sel = st.selectbox("Load trades for run", view_runs["run_id"].tolist(), key="history_run_id")
            if run_id_sel:
                trades = load_trades(run_id_sel)
                st.dataframe(trades, use_container_width=True)
                matching_runs = runs.loc[runs["run_id"] == run_id_sel]
                if not matching_runs.empty:
                    selected_run = matching_runs.iloc[0]
                    st.json({
                        "params": json.loads(selected_run["params_json"]),
                        "metrics": json.loads(selected_run["metrics_json"]),
                        "decision": json.loads(selected_run["decision_json"]),
                    })
                else:
                    st.warning(f"Run {run_id_sel} not found in loaded history.")


try:
    run_app()
except Exception as exc:
    print("Startup failure in app construction:", exc)
    traceback.print_exc()
    raise
