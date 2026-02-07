"""Market data fetching utilities via ccxt."""

from __future__ import annotations

import math
import random
import time

import pandas as pd

TIMEFRAME_TO_MINUTES: dict[str, int] = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


_EXCHANGE_CACHE: dict[str, "ccxt.Exchange"] = {}


def _get_exchange(exchange_name: str) -> "ccxt.Exchange":
    import ccxt  # Lazy import to avoid blocking Streamlit startup.

    normalized_name = exchange_name.lower()
    cached = _EXCHANGE_CACHE.get(normalized_name)
    if cached is not None:
        return cached

    exchange_cls = getattr(ccxt, normalized_name, None)
    if exchange_cls is None:
        raise ValueError(f"Unsupported exchange: {exchange_name}")

    exchange = exchange_cls(
        {
            "enableRateLimit": True,
            "timeout": 30000,
            "options": {"adjustForTimeDifference": True},
        }
    )
    _EXCHANGE_CACHE[normalized_name] = exchange
    return exchange


def select_symbol(exchange_name: str, asset: str, markets: dict) -> str:
    """Resolve symbol by exchange rules and availability."""
    asset = asset.upper()
    exchange_name = exchange_name.lower()

    if exchange_name == "coinbase":
        symbol = f"{asset}/USD"
        if symbol not in markets:
            raise ValueError(f"Symbol {symbol} not available on Coinbase")
        return symbol

    if exchange_name == "kraken":
        preferred = f"{asset}/USDT"
        fallback = f"{asset}/USD"
        if preferred in markets:
            return preferred
        if fallback in markets:
            return fallback
        raise ValueError(f"Neither {preferred} nor {fallback} available on Kraken")

    raise ValueError("Only Kraken and Coinbase are supported")


def fetch_ohlcv(exchange_name: str, symbol: str, timeframe: str, days: int) -> pd.DataFrame:
    """Fetch OHLCV candles for a symbol and timeframe covering `days`."""
    import ccxt  # Lazy import to avoid blocking Streamlit startup.

    if timeframe not in TIMEFRAME_TO_MINUTES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    exchange = _get_exchange(exchange_name)
    retry_errors = (
        ccxt.DDoSProtection,
        ccxt.RateLimitExceeded,
        ccxt.NetworkError,
        ccxt.ExchangeNotAvailable,
    )
    max_attempts = 6

    def _with_retry(func, *args, **kwargs):
        base_delay_seconds = max(float(getattr(exchange, "rateLimit", 0) or 0) / 1000.0, 0.1)
        for attempt in range(1, max_attempts + 1):
            try:
                return func(*args, **kwargs)
            except retry_errors:
                if attempt == max_attempts:
                    raise
                exponential = base_delay_seconds * (2 ** (attempt - 1))
                jitter = random.uniform(0, base_delay_seconds)
                time.sleep(max(base_delay_seconds, exponential + jitter))

    candles_needed = max(50, math.ceil(days * 1440 / TIMEFRAME_TO_MINUTES[timeframe]))
    limit = min(1000, candles_needed + 20)
    since = exchange.milliseconds() - (candles_needed + 20) * TIMEFRAME_TO_MINUTES[timeframe] * 60 * 1000

    raw = _with_retry(exchange.fetch_ohlcv, symbol, timeframe=timeframe, since=since, limit=limit)
    if not raw:
        raise ValueError("No OHLCV data returned")

    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    numeric_cols = ["open", "high", "low", "close", "volume"]
    df[numeric_cols] = df[numeric_cols].astype(float)
    df = df.drop_duplicates(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    return df
