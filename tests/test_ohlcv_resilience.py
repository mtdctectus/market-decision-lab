from __future__ import annotations

from mdl.data.ohlcv import fetch_with_retries, _cache_path


def test_fetch_with_retries_retries_then_succeeds() -> None:
    attempts = {"count": 0}

    def flaky() -> list:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise TimeoutError("temporary")
        return [1]

    out = fetch_with_retries(
        flaky,
        max_retries=3,
        backoff_s=0,
        is_retryable_exception=lambda exc: isinstance(exc, TimeoutError),
    )

    assert out == [1]
    assert attempts["count"] == 3


def test_fetch_with_retries_raises_on_non_retryable() -> None:
    def bad() -> list:
        raise ValueError("invalid")

    try:
        fetch_with_retries(
            bad,
            max_retries=3,
            backoff_s=0,
            is_retryable_exception=lambda exc: isinstance(exc, TimeoutError),
        )
    except ValueError as exc:
        assert str(exc) == "invalid"
    else:
        raise AssertionError("Expected ValueError")


def test_cache_path_layout() -> None:
    path = _cache_path("kraken", "BTC/USDT", "1h", 30)
    assert str(path).endswith(".cache/ohlcv/kraken/BTC-USDT/1h/30.parquet")
