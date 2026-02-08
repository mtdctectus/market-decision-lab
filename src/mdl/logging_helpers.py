from __future__ import annotations

from typing import Any

SCENARIO_KEYS = ("A", "B", "C")


def extract_scenario_metrics(scenarios: dict[str, Any]) -> dict[str, Any]:
    """Return metrics only for scenario keys A/B/C when present."""
    filtered: dict[str, Any] = {}
    for key in SCENARIO_KEYS:
        value = scenarios.get(key)
        if isinstance(value, dict) and isinstance(value.get("metrics"), dict):
            filtered[key] = value["metrics"]
    return filtered
