"""Decision layer for scenario scoring and final recommendation.

Product-oriented decision logic:
- converts metrics into GREEN / YELLOW / RED
- generates explicit human-readable reasons
- produces a single final decision: INVEST / CAUTION / NO
"""

from __future__ import annotations

from . import config


def _num(metrics: dict, key: str, default: float = 0.0) -> float:
    try:
        v = metrics.get(key, default)
        return float(v) if v is not None else float(default)
    except Exception:
        return float(default)


def _decision_score(metrics: dict) -> float:
    ann = _num(metrics, "Annualized Return %")
    dd = _num(metrics, "Max Drawdown %")
    tpw = _num(metrics, "Trades Per Week")
    exp = _num(metrics, "Expectancy %")

    ann_s = ann / max(config.RET_GOOD, 1e-9)
    dd_s = dd / max(config.DD_MAX, 1e-9)
    tpw_pen = abs(tpw - config.TPW_TARGET) / max(config.TPW_TARGET, 1e-9)
    exp_s = exp / 1.0

    return (1.0 * ann_s) - (0.8 * dd_s) - (0.1 * tpw_pen) + (0.2 * exp_s)


def evaluate_run(metrics: dict) -> dict:
    reasons = []
    ann = _num(metrics, "Annualized Return %")
    dd = _num(metrics, "Max Drawdown %")
    trades = int(_num(metrics, "Number of Trades"))
    tpw = _num(metrics, "Trades Per Week")

    is_red = ann < config.RET_MIN or dd > config.DD_MAX or trades < config.MIN_TRADES
    is_green = ann >= config.RET_GOOD and dd <= config.DD_WARN and trades >= config.MIN_TRADES

    if is_red:
        status, color = "RED", "RED"
        if ann < config.RET_MIN:
            reasons.append(f"Annualized return {ann:.2f}% is below minimum {config.RET_MIN:.2f}%.")
        if dd > config.DD_MAX:
            reasons.append(f"Max drawdown {dd:.2f}% exceeds risk limit {config.DD_MAX:.2f}%.")
        if trades < config.MIN_TRADES:
            reasons.append(f"Only {trades} trades (min {config.MIN_TRADES}) -> low confidence.")
        recommendation = "NO - conditions are not supportive under this setup."
    elif is_green:
        status, color = "GREEN", "GREEN"
        reasons.append(f"Return >= {config.RET_GOOD:.0f}% annualized and drawdown <= {config.DD_WARN:.0f}%.")
        if abs(tpw - config.TPW_TARGET) > config.TPW_TOL:
            reasons.append(f"Trade frequency {tpw:.2f}/week deviates from target {config.TPW_TARGET:.0f}/week.")
        recommendation = "INVEST - setup looks reasonable under tested conditions."
    else:
        status, color = "YELLOW", "YELLOW"
        if ann < config.RET_GOOD:
            reasons.append(f"Annualized return {ann:.2f}% is below target {config.RET_GOOD:.2f}%.")
        if dd > config.DD_WARN:
            reasons.append(f"Drawdown {dd:.2f}% is above comfort zone {config.DD_WARN:.2f}%.")
        if trades < config.MIN_TRADES:
            reasons.append(f"Trade count {trades} is below minimum {config.MIN_TRADES}.")
        if abs(tpw - config.TPW_TARGET) > config.TPW_TOL:
            reasons.append(f"Trades/week {tpw:.2f} is far from target {config.TPW_TARGET:.0f}.")
        if not reasons:
            reasons.append("Mixed return/risk profile.")
        recommendation = "CAUTION - consider parameter changes or reduced position size."

    return {
        "status": status,
        "color": color,
        "reasons": reasons,
        "recommendation": recommendation,
        "score": _decision_score(metrics),
    }


def final_decision(scenarios_dict: dict) -> dict:
    statuses = {k: v["decision"]["status"] for k, v in scenarios_dict.items()}
    all_red = all(s == "RED" for s in statuses.values())

    if statuses.get("B") == "GREEN":
        recommended = "B"
    elif statuses.get("A") == "GREEN":
        recommended = "A"
    elif statuses.get("C") == "GREEN":
        recommended = "C"
    else:
        yellow = [(k, v) for k, v in scenarios_dict.items() if statuses.get(k) == "YELLOW"]
        if yellow:
            recommended = sorted(yellow, key=lambda kv: kv[1]["decision"]["score"], reverse=True)[0][0]
        else:
            recommended = sorted(
                scenarios_dict.items(),
                key=lambda kv: (_num(kv[1]["metrics"], "Annualized Return %"), -_num(kv[1]["metrics"], "Max Drawdown %")),
                reverse=True,
            )[0][0]

    if all_red:
        return {"label": "NO", "text": "NO - all scenarios are high-risk or underperforming.", "recommended": recommended}

    if any(s == "GREEN" for s in statuses.values()) and statuses.get(recommended) != "RED":
        return {"label": "INVEST", "text": "INVEST - at least one scenario is robust with acceptable risk.", "recommended": recommended}

    return {"label": "CAUTION", "text": "CAUTION - no fully robust setup; proceed only with risk controls.", "recommended": recommended}
