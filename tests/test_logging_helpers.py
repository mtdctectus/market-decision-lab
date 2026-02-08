from mdl.logging_helpers import extract_scenario_metrics


def test_extract_scenario_metrics_filters_non_scenarios() -> None:
    scenarios = {
        "A": {"metrics": {"Annualized Return %": 1.2}},
        "B": {"metrics": {"Annualized Return %": 2.3}},
        "C": {"metrics": {"Annualized Return %": 3.4}},
        "all_candidates": ["x", "y"],
        "meta": {"count": 3},
    }

    metrics = extract_scenario_metrics(scenarios)

    assert metrics == {
        "A": {"Annualized Return %": 1.2},
        "B": {"Annualized Return %": 2.3},
        "C": {"Annualized Return %": 3.4},
    }
