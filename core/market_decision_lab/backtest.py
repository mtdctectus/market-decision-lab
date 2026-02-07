"""Backtesting engine for EMA + ATR long-only strategy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np
import pandas as pd


@dataclass
class BacktestParams:
    ema_window: int = 20
    signal_mode: str = "strict"
    entry_mode: str = "next_open"
    sl_mult: float = 1.5
    tp_mult: float = 2.5
    fee_per_side: float = 0.0006
    slippage_per_side: float = 0.0002
    initial_cash: float = 10000.0
    cooldown_candles: int = 2


def _atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.rolling(window=window, min_periods=window).mean()


def _entry_signal(df: pd.DataFrame, idx: int, mode: str) -> bool:
    if mode == "strict":
        if idx < 1:
            return False
        return bool((df.loc[idx, "close"] > df.loc[idx, "ema"]) and (df.loc[idx - 1, "close"] > df.loc[idx - 1, "ema"]))
    return bool(df.loc[idx, "close"] > df.loc[idx, "ema"])


def _exit_signal(df: pd.DataFrame, idx: int, mode: str) -> bool:
    if mode == "strict":
        if idx < 1:
            return False
        return bool((df.loc[idx, "close"] < df.loc[idx, "ema"]) and (df.loc[idx - 1, "close"] < df.loc[idx - 1, "ema"]))
    return bool(df.loc[idx, "close"] < df.loc[idx, "ema"])


def run_backtest(ohlcv_df: pd.DataFrame, params: BacktestParams | None = None) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Run the EMA+ATR strategy and return backtest and trade DataFrames."""
    if params is None:
        params = BacktestParams()

    if ohlcv_df.empty:
        raise ValueError("Input OHLCV data is empty")

    df = ohlcv_df.copy().reset_index(drop=True)
    df["ema"] = df["close"].ewm(span=params.ema_window, adjust=False).mean()
    df["atr"] = _atr(df, 14)

    cash = params.initial_cash
    units = 0.0
    in_position = False
    cooldown = 0

    entry_price_raw = np.nan
    entry_price_cost = np.nan
    entry_ts = None
    sl = np.nan
    tp = np.nan

    trades: List[dict] = []
    states: List[dict] = []

    for i, row in df.iterrows():
        ts = row["ts"]
        open_p, high_p, low_p, close_p, atr = row["open"], row["high"], row["low"], row["close"], row["atr"]
        action = "HOLD"

        if in_position:
            exit_price_raw = None
            reason = None

            if low_p <= sl and high_p >= tp:
                exit_price_raw = sl
                reason = "stop_loss"
            elif low_p <= sl:
                exit_price_raw = sl
                reason = "stop_loss"
            elif high_p >= tp:
                exit_price_raw = tp
                reason = "take_profit"
            elif _exit_signal(df, i, params.signal_mode):
                exit_price_raw = close_p
                reason = "signal_exit"

            if exit_price_raw is not None:
                effective_exit = exit_price_raw * (1 - params.slippage_per_side)
                gross = units * effective_exit
                fee = gross * params.fee_per_side
                cash = gross - fee

                pnl_pct = ((effective_exit - entry_price_cost) / entry_price_cost) * 100
                trades.append(
                    {
                        "entry_ts": entry_ts,
                        "exit_ts": ts,
                        "entry": round(float(entry_price_raw), 8),
                        "exit": round(float(exit_price_raw), 8),
                        "pnl": float(units * (effective_exit - entry_price_cost)),
                        "pnl_pct": float(pnl_pct),
                        "reason": reason,
                        "sl": float(sl),
                        "tp": float(tp),
                    }
                )

                units = 0.0
                in_position = False
                cooldown = params.cooldown_candles
                action = f"EXIT:{reason}"

        if (not in_position) and (cooldown <= 0) and not np.isnan(atr):
            if _entry_signal(df, i, params.signal_mode):
                # Check bounds for next_open mode to avoid accessing beyond dataframe
                if params.entry_mode == "next_open":
                    if i + 1 < len(df):
                        signal_idx = i + 1
                        fill_raw = float(df.loc[signal_idx, "open"])
                        fill_ts = df.loc[signal_idx, "ts"]
                    else:
                        # If we're at the last candle, use current close instead of next open
                        fill_raw = float(close_p)
                        fill_ts = ts
                else:
                    fill_raw = float(close_p)
                    fill_ts = ts

                fill_cost = fill_raw * (1 + params.slippage_per_side)
                trade_value = cash
                fee = trade_value * params.fee_per_side
                spendable = trade_value - fee
                if spendable > 0:
                    units = spendable / fill_cost
                    cash = 0.0
                    in_position = True
                    entry_price_raw = fill_raw
                    entry_price_cost = fill_cost
                    entry_ts = fill_ts
                    sl = entry_price_raw - params.sl_mult * atr
                    tp = entry_price_raw + params.tp_mult * atr
                    action = "ENTRY"

        if cooldown > 0 and not in_position:
            cooldown -= 1

        mark_price = close_p * (1 - params.slippage_per_side) if in_position else close_p
        equity = cash + units * mark_price
        states.append(
            {
                "ts": ts,
                "close": close_p,
                "ema": row["ema"],
                "atr": atr,
                "equity": equity,
                "position": 1 if in_position else 0,
                "action": action,
                "sl": sl if in_position else np.nan,
                "tp": tp if in_position else np.nan,
            }
        )

    if in_position:
        last = df.iloc[-1]
        effective_exit = float(last["close"]) * (1 - params.slippage_per_side)
        gross = units * effective_exit
        fee = gross * params.fee_per_side
        cash = gross - fee
        pnl_pct = ((effective_exit - entry_price_cost) / entry_price_cost) * 100
        trades.append(
            {
                "entry_ts": entry_ts,
                "exit_ts": last["ts"],
                "entry": round(float(entry_price_raw), 8),
                "exit": round(float(last["close"]), 8),
                "pnl": float(units * (effective_exit - entry_price_cost)),
                "pnl_pct": float(pnl_pct),
                "reason": "end_of_test",
                "sl": float(sl),
                "tp": float(tp),
            }
        )
        states[-1]["equity"] = cash

    backtest_df = pd.DataFrame(states)
    trades_df = pd.DataFrame(
        trades,
        columns=["entry_ts", "exit_ts", "entry", "exit", "pnl", "pnl_pct", "reason", "sl", "tp"],
    )
    return backtest_df, trades_df
