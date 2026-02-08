from __future__ import annotations

from typing import Any

COMPARE_DAY_CAP_1H = 41


def validate_timeframe_for_exchange(exchange: str, timeframe: str) -> tuple[bool, str | None]:
    """Validate exchange/timeframe combinations exposed in the UI."""
    if exchange == "coinbase" and timeframe == "4h":
        return False, "Coinbase does not support 4h candles in this app. Choose 1h or 1d."
    return True, None


def can_run_compare(inputs: dict[str, Any]) -> tuple[bool, str | None]:
    """Validate compare-specific limits before starting a run."""
    days = int(inputs.get("days", 0))
    if days > COMPARE_DAY_CAP_1H:
        return False, f"Compare supports up to {COMPARE_DAY_CAP_1H} days because it includes 1h candles."
    return True, None


def can_run_strategy_lab(state: dict[str, Any]) -> tuple[bool, str | None]:
    """Require existing run context before strategy lab can be launched."""
    has_quick = state.get("quick_result") is not None
    has_compare = state.get("compare_result") is not None
    if not (has_quick or has_compare):
        return False, "Run Quick Check or A/B/C Compare first to provide data context for Strategy Lab."
    return True, None
