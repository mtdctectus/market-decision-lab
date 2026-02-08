"""Market data fetching utilities via ccxt."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from pathlib import Path

import pandas as pd

TIMEFRAME_TO_MINUTES: dict[str, int] = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
CACHE_TTL_SECONDS = 30 * 60
CACHE_ROOT = Path(".cache") / "ohlcv"


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


def fetch_ohlcv(
    exchange_name: str,
    symbol: str,
    timeframe: str,
    days: int,
    *,
    use_cache: bool = True,
    max_retries: int = 5,
    backoff_s: int = 1,
) -> pd.DataFrame:
    """Fetch OHLCV candles for a symbol and timeframe covering `days`."""
    import ccxt  # Lazy import to avoid blocking Streamlit startup.

    if timeframe not in TIMEFRAME_TO_MINUTES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")

    exchange = _get_exchange(exchange_name)

    candles_needed = max(50, math.ceil(days * 1440 / TIMEFRAME_TO_MINUTES[timeframe]))
    limit = min(1000, candles_needed + 20)
    since = exchange.milliseconds() - (candles_needed + 20) * TIMEFRAME_TO_MINUTES[timeframe] * 60 * 1000

    cache_path = _cache_path(exchange_name, symbol, timeframe, days)
    if use_cache:
        cached_df = _read_cache(cache_path, CACHE_TTL_SECONDS)
        if cached_df is not None:
            return cached_df

    raw = fetch_with_retries(
        lambda: exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=limit),
        max_retries=max_retries,
        backoff_s=backoff_s,
        is_retryable_exception=lambda exc: isinstance(
            exc,
            (
                ccxt.DDoSProtection,
                ccxt.RateLimitExceeded,
                ccxt.RequestTimeout,
                ccxt.NetworkError,
                ccxt.ExchangeNotAvailable,
            ),
        ),
    )
    if not raw:
        raise ValueError("No OHLCV data returned")

    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    numeric_cols = ["open", "high", "low", "close", "volume"]
    df[numeric_cols] = df[numeric_cols].astype(float)
    df = df.drop_duplicates(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    _write_cache(cache_path, df)
    return df


def fetch_with_retries(
    fn: Callable[[], list],
    max_retries: int,
    backoff_s: int,
    is_retryable_exception: Callable[[Exception], bool],
) -> list:
    """Run `fn` with retry/backoff for retryable exceptions only."""
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            if not is_retryable_exception(exc) or attempt == max_retries:
                raise
            time.sleep(backoff_s * (attempt + 1))


def _cache_path(exchange_name: str, symbol: str, timeframe: str, days: int) -> Path:
    normalized_symbol = symbol.replace("/", "-")
    return CACHE_ROOT / exchange_name.lower() / normalized_symbol / timeframe / f"{int(days)}.parquet"


def _read_cache(path: Path, ttl_seconds: int) -> pd.DataFrame | None:
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > ttl_seconds:
        return None
    try:
        df = pd.read_parquet(path)
    except Exception:
        return None

    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
    return df


def _write_cache(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(path, index=False)
    except Exception:
        return
