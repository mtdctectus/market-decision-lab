#!/usr/bin/env python3
"""Lightweight local sanity checks for Market Decision Lab."""

from __future__ import annotations

import compileall
import importlib
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = ROOT / "src"
APP_PATH = ROOT / "app"

for path in (ROOT, SRC_PATH, APP_PATH):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

MODULES = [
    "pandas",
    "streamlit",
    "mdl.backtest.engine",
    "mdl.backtest.metrics",
    "mdl.data.ohlcv",
    "mdl.decision",
    "mdl.scenarios",
    "mdl.storage",
    "mdl.log_store",
    "mdl.strategies",
    "mdl.lab.strategy_lab",
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
