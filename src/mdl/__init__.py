"""Market Decision Lab internal engine package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .decision import evaluate_run, final_decision

try:
    __version__ = version("market-decision-lab")
except PackageNotFoundError:
    # Fallback for editable/local source execution without installed package metadata.
    __version__ = "0.1.0"

__all__ = ["__version__", "evaluate_run", "final_decision"]
