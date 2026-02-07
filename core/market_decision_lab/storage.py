"""SQLite persistence layer."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/app.db")


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS candles (
              exchange TEXT,
              symbol TEXT,
              timeframe TEXT,
              ts TEXT,
              open REAL,
              high REAL,
              low REAL,
              close REAL,
              volume REAL,
              UNIQUE(exchange, symbol, timeframe, ts)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
              run_id TEXT PRIMARY KEY,
              run_ts TEXT,
              exchange TEXT,
              symbol TEXT,
              timeframe TEXT,
              days INTEGER,
              params_json TEXT,
              metrics_json TEXT,
              decision_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
              run_id TEXT,
              entry_ts TEXT,
              exit_ts TEXT,
              entry REAL,
              exit REAL,
              pnl REAL,
              pnl_pct REAL,
              reason TEXT,
              sl REAL,
              tp REAL
            )
            """
        )


def save_candles(exchange: str, symbol: str, timeframe: str, candles_df: pd.DataFrame) -> None:
    if candles_df.empty:
        return
    frame = candles_df.copy()
    frame["ts"] = frame["ts"].astype(str)
    frame["exchange"] = exchange
    frame["symbol"] = symbol
    frame["timeframe"] = timeframe
    frame = frame[["exchange", "symbol", "timeframe", "ts", "open", "high", "low", "close", "volume"]]

    with _conn() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO candles(exchange, symbol, timeframe, ts, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            frame.to_records(index=False).tolist(),
        )


def load_candles(exchange: str, symbol: str, timeframe: str) -> pd.DataFrame:
    with _conn() as conn:
        df = pd.read_sql_query(
            """
            SELECT ts, open, high, low, close, volume
            FROM candles
            WHERE exchange=? AND symbol=? AND timeframe=?
            ORDER BY ts ASC
            """,
            conn,
            params=(exchange, symbol, timeframe),
        )
    if not df.empty:
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def save_run(run_id: str, run_ts: str, exchange: str, symbol: str, timeframe: str, days: int, params: dict, metrics: dict, decision: dict) -> None:
    with _conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO runs(run_id, run_ts, exchange, symbol, timeframe, days, params_json, metrics_json, decision_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, run_ts, exchange, symbol, timeframe, days, json.dumps(params), json.dumps(metrics), json.dumps(decision)),
        )


def save_trades(run_id: str, trades_df: pd.DataFrame) -> None:
    if trades_df.empty:
        return
    frame = trades_df.copy()
    frame["entry_ts"] = frame["entry_ts"].astype(str)
    frame["exit_ts"] = frame["exit_ts"].astype(str)
    frame.insert(0, "run_id", run_id)

    with _conn() as conn:
        conn.executemany(
            """
            INSERT INTO trades(run_id, entry_ts, exit_ts, entry, exit, pnl, pnl_pct, reason, sl, tp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            frame[["run_id", "entry_ts", "exit_ts", "entry", "exit", "pnl", "pnl_pct", "reason", "sl", "tp"]]
            .to_records(index=False)
            .tolist(),
        )


def load_runs(limit: int = 50) -> pd.DataFrame:
    with _conn() as conn:
        runs = pd.read_sql_query(
            """
            SELECT run_id, run_ts, exchange, symbol, timeframe, days, params_json, metrics_json, decision_json
            FROM runs
            ORDER BY run_ts DESC
            LIMIT ?
            """,
            conn,
            params=(limit,),
        )
    return runs


def load_trades(run_id: str) -> pd.DataFrame:
    with _conn() as conn:
        trades = pd.read_sql_query(
            """
            SELECT entry_ts, exit_ts, entry, exit, pnl, pnl_pct, reason, sl, tp
            FROM trades
            WHERE run_id=?
            ORDER BY exit_ts ASC
            """,
            conn,
            params=(run_id,),
        )
    return trades
