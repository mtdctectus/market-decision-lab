import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "app" / "ui_guards.py"
SPEC = importlib.util.spec_from_file_location("ui_guards", MODULE_PATH)
ui_guards = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(ui_guards)


validate_timeframe_for_exchange = ui_guards.validate_timeframe_for_exchange
can_run_compare = ui_guards.can_run_compare
can_run_strategy_lab = ui_guards.can_run_strategy_lab


def test_validate_timeframe_for_exchange_blocks_coinbase_4h() -> None:
    ok, msg = validate_timeframe_for_exchange("coinbase", "4h")

    assert ok is False
    assert msg is not None


def test_can_run_compare_blocks_days_over_cap() -> None:
    ok, msg = can_run_compare({"days": 42})

    assert ok is False
    assert "41" in (msg or "")


def test_can_run_strategy_lab_blocks_without_prior_results() -> None:
    ok, msg = can_run_strategy_lab({"quick_result": None, "compare_result": None})

    assert ok is False
    assert msg is not None
