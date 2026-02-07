from __future__ import annotations

from mdl import evaluate_run, final_decision


def test_evaluate_run_returns_expected_shape() -> None:
    metrics = {
        "Annualized Return %": 20.0,
        "Max Drawdown %": 10.0,
        "Number of Trades": 25,
        "Trades Per Week": 2.0,
        "Expectancy %": 0.8,
    }
    decision = evaluate_run(metrics)
    assert set(["status", "color", "reasons", "recommendation", "score"]).issubset(decision)


def test_final_decision_prefers_green_scenario() -> None:
    scenarios = {
        "A": {"metrics": {"Annualized Return %": 10.0, "Max Drawdown %": 20.0}, "decision": {"status": "YELLOW", "score": 1.0}},
        "B": {"metrics": {"Annualized Return %": 25.0, "Max Drawdown %": 10.0}, "decision": {"status": "GREEN", "score": 2.0}},
        "C": {"metrics": {"Annualized Return %": 5.0, "Max Drawdown %": 25.0}, "decision": {"status": "RED", "score": -1.0}},
    }

    decision = final_decision(scenarios)

    assert decision["label"] == "INVEST"
    assert decision["recommended"] == "B"
