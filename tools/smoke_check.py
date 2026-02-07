#!/usr/bin/env python3
"""Lightweight local sanity checks for Market Decision Lab."""

from __future__ import annotations

import compileall
import importlib
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_PATH = ROOT / "core"
APP_PATH = ROOT / "app"

for path in (ROOT, CORE_PATH, APP_PATH):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

MODULES = [
    "pandas",
    "streamlit",
    "market_decision_lab.backtest",
    "market_decision_lab.data",
    "market_decision_lab.decision",
    "market_decision_lab.metrics",
    "market_decision_lab.scenarios",
    "market_decision_lab.storage",
    "market_decision_lab.log_store",
    "market_decision_lab.strategy_backtest",
    "market_decision_lab.strategies",
    "market_decision_lab.strategy_lab",
]


def _module_version(name: str) -> str:
    root_name = name.split(".")[0]
    module = importlib.import_module(root_name)
    return getattr(module, "__version__", "unknown")


def main() -> int:
    print(f"Python: {platform.python_version()}")
    for module_name in MODULES:
        importlib.import_module(module_name)
    print(f"pandas: {_module_version('pandas')}")
    print(f"streamlit: {_module_version('streamlit')}")

    ok = compileall.compile_dir(str(ROOT), quiet=1)
    if not ok:
        print("compileall failed")
        return 1

    print("smoke check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
