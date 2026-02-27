"""Decision layer for scenario scoring and final recommendation.

Product-oriented decision logic:
- converts metrics into GREEN / YELLOW / RED
- generates explicit human-readable reasons
- produces a single final decision: INVEST / CAUTION / NO
"""

from __future__ import annotations

from mdl import config


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
    sharpe = _num(metrics, "Sharpe Ratio")
    win_rate = _num(metrics, "Win Rate %")

    ann_s = ann / max(config.RET_GOOD, 1e-9)
    dd_s = dd / max(config.DD_MAX, 1e-9)
    tpw_pen = abs(tpw - config.TPW_TARGET) / max(config.TPW_TARGET, 1e-9)
    exp_s = exp / 1.0
    sharpe_s = sharpe / max(config.SHARPE_GOOD, 1e-9)
    wr_s = win_rate / max(config.WIN_RATE_GOOD, 1e-9)

    return (
        config.W_RET * ann_s
        - config.W_DD * dd_s
        - config.W_TPW * tpw_pen
        + config.W_EXP * exp_s
        + config.W_SHARPE * sharpe_s
        + config.W_WR * wr_s
    )


def evaluate_run(metrics: dict) -> dict:
    reasons = []
    ann = _num(metrics, "Annualized Return %")
    dd = _num(metrics, "Max Drawdown %")
    trades = int(_num(metrics, "Number of Trades"))
    tpw = _num(metrics, "Trades Per Week")
    sharpe = _num(metrics, "Sharpe Ratio")
    win_rate = _num(metrics, "Win Rate %")

    # Hard RED conditions
    is_red = (
        ann < config.RET_MIN
        or dd > config.DD_MAX
        or trades < config.MIN_TRADES
        or sharpe < config.SHARPE_MIN
        or win_rate < config.WIN_RATE_MIN
    )

    # Full GREEN conditions
    is_green = (
        ann >= config.RET_GOOD
        and dd <= config.DD_WARN
        and trades >= config.MIN_TRADES
        and sharpe >= config.SHARPE_GOOD
        and win_rate >= config.WIN_RATE_GOOD
    )

    if is_red:
        status, color = "RED", "RED"
        if ann < config.RET_MIN:
            reasons.append(f"Annualized return {ann:.2f}% is below minimum {config.RET_MIN:.2f}%.")
        if dd > config.DD_MAX:
            reasons.append(f"Max drawdown {dd:.2f}% exceeds risk limit {config.DD_MAX:.2f}%.")
        if trades < config.MIN_TRADES:
            reasons.append(f"Only {trades} trades (min {config.MIN_TRADES}) — low confidence.")
        if sharpe < config.SHARPE_MIN:
            reasons.append(f"Sharpe Ratio {sharpe:.2f} is below minimum {config.SHARPE_MIN:.2f} — poor risk-adjusted return.")
        if win_rate < config.WIN_RATE_MIN:
            reasons.append(f"Win Rate {win_rate:.1f}% is below minimum {config.WIN_RATE_MIN:.1f}%.")
        recommendation = "NO - conditions are not supportive under this setup."

    elif is_green:
        status, color = "GREEN", "GREEN"
        reasons.append(
            f"Return >= {config.RET_GOOD:.0f}%, drawdown <= {config.DD_WARN:.0f}%, "
            f"Sharpe {sharpe:.2f} >= {config.SHARPE_GOOD:.1f}, Win Rate {win_rate:.1f}% >= {config.WIN_RATE_GOOD:.0f}%."
        )
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
        if sharpe < config.SHARPE_GOOD:
            reasons.append(f"Sharpe Ratio {sharpe:.2f} is below target {config.SHARPE_GOOD:.1f}.")
        if win_rate < config.WIN_RATE_GOOD:
            reasons.append(f"Win Rate {win_rate:.1f}% is below target {config.WIN_RATE_GOOD:.0f}%.")
        if not reasons:
            reasons.append("Mixed return/risk profile.")
        recommendation = "CAUTION - consider parameter changes or reduced position size."

    return {
        "status": status,
        "color": color,
        "reasons": reasons,
        "recommendation": recommendation,
        "score": _decision_score(metrics),
        "sharpe": sharpe,
        "win_rate": win_rate,
    }


def final_decision(scenarios_dict: dict) -> dict:
    if not scenarios_dict:
        return {
            "label": "NO",
            "text": "NO - no scenarios provided.",
            "recommended": None,
            "reason": "Empty scenarios input; nothing to evaluate.",
        }

    statuses = {k: v["decision"]["status"] for k, v in scenarios_dict.items()}
    all_red = all(s == "RED" for s in statuses.values())

    # Pick best GREEN by score (not hardcoded B > A > C priority)
    green_scenarios = [(k, v) for k, v in scenarios_dict.items() if statuses.get(k) == "GREEN"]
    if green_scenarios:
        recommended = sorted(
            green_scenarios,
            key=lambda kv: kv[1]["decision"]["score"],
            reverse=True,
        )[0][0]
    else:
        yellow = [(k, v) for k, v in scenarios_dict.items() if statuses.get(k) == "YELLOW"]
        if yellow:
            recommended = sorted(yellow, key=lambda kv: kv[1]["decision"]["score"], reverse=True)[0][0]
        else:
            recommended = sorted(
                scenarios_dict.items(),
                key=lambda kv: kv[1]["decision"]["score"],
                reverse=True,
            )[0][0]

    if all_red:
        return {
            "label": "NO",
            "text": "NO - all scenarios are high-risk or underperforming.",
            "recommended": recommended,
            "reason": "Every scenario breached a hard risk limit (return, drawdown, Sharpe, or Win Rate).",
        }

    rec_decision = scenarios_dict[recommended]["decision"]
    if any(s == "GREEN" for s in statuses.values()) and statuses.get(recommended) != "RED":
        sharpe = rec_decision.get("sharpe", 0)
        wr = rec_decision.get("win_rate", 0)
        return {
            "label": "INVEST",
            "text": "INVEST - at least one scenario is robust with acceptable risk.",
            "recommended": recommended,
            "reason": (
                f"Scenario {recommended} passed all thresholds "
                f"(Sharpe {sharpe:.2f}, Win Rate {wr:.1f}%)."
            ),
        }

    return {
        "label": "CAUTION",
        "text": "CAUTION - no fully robust setup; proceed only with risk controls.",
        "recommended": recommended,
        "reason": f"Scenario {recommended} has the best score but did not reach GREEN status.",
    }
