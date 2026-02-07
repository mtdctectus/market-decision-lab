"""Decision layer for scenario scoring and final recommendation."""

from __future__ import annotations

from . import config


def evaluate_run(metrics: dict) -> dict:
    reasons = []
    ann = metrics["Annualized Return %"]
    dd = metrics["Max Drawdown %"]
    trades = metrics["Number of Trades"]

    is_red = ann < config.RET_MIN or dd > config.DD_MAX or trades < config.MIN_TRADES
    is_green = ann >= config.RET_GOOD and dd <= config.DD_WARN and trades >= config.MIN_TRADES

    if is_red:
        status, color = "RED", "🔴"
        if ann < config.RET_MIN:
            reasons.append("Return below minimum threshold.")
        if dd > config.DD_MAX:
            reasons.append("Drawdown exceeds max risk limit.")
        if trades < config.MIN_TRADES:
            reasons.append("Not enough trades for confidence.")
        recommendation = "NO: Conditions are not supportive under this setup."
    elif is_green:
        status, color = "GREEN", "🟢"
        reasons.append("Return, drawdown, and trade count meet quality targets.")
        recommendation = "INVEST: Setup looks reasonable under tested conditions."
    else:
        status, color = "YELLOW", "🟡"
        reasons.append("Mixed results: some targets met, but risk/reliability is moderate.")
        recommendation = "CAUTION: Consider parameter or timeframe adjustments."

    return {
        "status": status,
        "color": color,
        "reasons": reasons,
        "recommendation": recommendation,
    }


def final_decision(scenarios_dict: dict) -> dict:
    statuses = {k: v["decision"]["status"] for k, v in scenarios_dict.items()}

    all_red = all(status == "RED" for status in statuses.values())
    green_candidates = [k for k, status in statuses.items() if status == "GREEN"]

    ranked = sorted(
        scenarios_dict.items(),
        key=lambda kv: (
            kv[1]["metrics"]["Annualized Return %"],
            -kv[1]["metrics"]["Max Drawdown %"],
            kv[1]["metrics"]["Expectancy %"],
        ),
        reverse=True,
    )
    recommended = ranked[0][0]

    if all_red:
        return {
            "label": "NO",
            "text": "All scenarios are high-risk or underperforming.",
            "recommended": recommended,
        }

    if green_candidates and statuses[recommended] != "RED":
        if recommended not in green_candidates:
            recommended = green_candidates[0]
        return {
            "label": "INVEST",
            "text": "At least one scenario is robust with acceptable risk.",
            "recommended": recommended,
        }

    return {
        "label": "CAUTION",
        "text": "No fully robust setup; proceed only with risk controls.",
        "recommended": recommended,
    }
