"""Decision layer for scenario scoring and final recommendation.

Product-oriented decision logic:
- converts metrics into GREEN / YELLOW / RED
- computes Calmar Ratio and reads Profit Factor
- generates explicit human-readable reasons
- produces a single final decision: INVEST / CAUTION / NO
- attaches confidence level: HIGH / MEDIUM / LOW
"""

from __future__ import annotations

from mdl import config


def _num(metrics: dict, key: str, default: float = 0.0) -> float:
    try:
        v = metrics.get(key, default)
        return float(v) if v is not None else float(default)
    except Exception:
        return float(default)


def _calmar(ann: float, dd: float) -> float:
    """Calmar Ratio = Ann Return % / Max Drawdown %."""
    return ann / max(dd, 1e-9)


def _decision_score(metrics: dict) -> float:
    """Composite score: higher = better. Used to rank scenarios."""
    ann = _num(metrics, "Annualized Return %")
    dd = _num(metrics, "Max Drawdown %")
    tpw = _num(metrics, "Trades Per Week")
    exp = _num(metrics, "Expectancy %")
    sharpe = _num(metrics, "Sharpe Ratio")
    win_rate = _num(metrics, "Win Rate %")
    profit_factor = _num(metrics, "Profit Factor", default=1.0)
    calmar = _calmar(ann, dd)

    ann_s = ann / max(config.RET_GOOD, 1e-9)
    dd_s = dd / max(config.DD_MAX, 1e-9)
    tpw_pen = abs(tpw - config.TPW_TARGET) / max(config.TPW_TARGET, 1e-9)
    exp_s = exp / 1.0
    sharpe_s = sharpe / max(config.SHARPE_GOOD, 1e-9)
    wr_s = win_rate / max(config.WIN_RATE_GOOD, 1e-9)
    calmar_s = calmar / max(config.CALMAR_GOOD, 1e-9)
    pf_s = (profit_factor - 1.0) / max(config.PROFIT_FACTOR_GOOD - 1.0, 1e-9)

    return (
        config.W_SHARPE * sharpe_s
        + config.W_RET * ann_s
        - config.W_DD * dd_s
        - config.W_TPW * tpw_pen
        + config.W_EXP * exp_s
        + config.W_WR * wr_s
        + config.W_CALMAR * calmar_s
        + config.W_PF * pf_s
    )


def _confidence(score: float, status: str) -> str:
    """Translate score + status into a human-readable confidence level."""
    if status == "RED":
        return "LOW"
    if status == "GREEN":
        return "HIGH" if score >= config.SCORE_CONFIDENCE_MIN * 1.2 else "MEDIUM"
    # YELLOW
    if score >= config.SCORE_CONFIDENCE_MIN:
        return "MEDIUM"
    return "LOW"


def evaluate_run(metrics: dict) -> dict:
    reasons = []
    ann = _num(metrics, "Annualized Return %")
    dd = _num(metrics, "Max Drawdown %")
    trades = int(_num(metrics, "Number of Trades"))
    tpw = _num(metrics, "Trades Per Week")
    sharpe = _num(metrics, "Sharpe Ratio")
    win_rate = _num(metrics, "Win Rate %")
    profit_factor = _num(metrics, "Profit Factor", default=1.0)
    has_pf = "Profit Factor" in metrics
    calmar = _calmar(ann, dd)

    # ── Hard RED conditions ────────────────────────────────────────────────────
    red_flags = []
    if ann < config.RET_MIN:
        red_flags.append(f"Return {ann:.1f}% < minimum {config.RET_MIN:.0f}%.")
    if dd > config.DD_MAX:
        red_flags.append(f"Drawdown {dd:.1f}% exceeds hard limit {config.DD_MAX:.0f}%.")
    if trades < config.MIN_TRADES:
        red_flags.append(f"Only {trades} trades (min {config.MIN_TRADES}) — unreliable stats.")
    if sharpe < config.SHARPE_MIN:
        red_flags.append(f"Sharpe {sharpe:.2f} < {config.SHARPE_MIN:.1f} — poor risk-adjusted return.")
    if win_rate < config.WIN_RATE_MIN:
        red_flags.append(f"Win Rate {win_rate:.1f}% < {config.WIN_RATE_MIN:.0f}%.")
    if calmar < config.CALMAR_MIN:
        red_flags.append(
            f"Calmar Ratio {calmar:.2f} < {config.CALMAR_MIN:.2f} — gains don't justify drawdown."
        )
    if has_pf and profit_factor < config.PROFIT_FACTOR_MIN:
        red_flags.append(
            f"Profit Factor {profit_factor:.2f} < {config.PROFIT_FACTOR_MIN:.1f} — edge too thin."
        )

    is_red = bool(red_flags)

    # ── Full GREEN conditions ──────────────────────────────────────────────────
    is_green = (
        ann >= config.RET_GOOD
        and dd <= config.DD_WARN
        and trades >= config.MIN_TRADES
        and sharpe >= config.SHARPE_GOOD
        and win_rate >= config.WIN_RATE_GOOD
        and calmar >= config.CALMAR_GOOD
        and (not has_pf or profit_factor >= config.PROFIT_FACTOR_GOOD)
    )

    score = _decision_score(metrics)

    if is_red:
        status = "RED"
        reasons = red_flags
        recommendation = "NO — one or more hard risk limits breached."

    elif is_green:
        status = "GREEN"
        reasons.append(
            f"Return {ann:.1f}% ✓  Drawdown {dd:.1f}% ✓  "
            f"Sharpe {sharpe:.2f} ✓  Win Rate {win_rate:.1f}% ✓  "
            f"Calmar {calmar:.2f} ✓"
        )
        if has_pf:
            reasons.append(f"Profit Factor {profit_factor:.2f} ✓")
        if abs(tpw - config.TPW_TARGET) > config.TPW_TOL:
            reasons.append(
                f"Trade frequency {tpw:.2f}/week deviates from target {config.TPW_TARGET:.0f}/week."
            )
        recommendation = "INVEST — setup passes all quality and risk thresholds."

    else:
        status = "YELLOW"
        if ann < config.RET_GOOD:
            reasons.append(f"Return {ann:.1f}% below target {config.RET_GOOD:.0f}%.")
        if dd > config.DD_WARN:
            reasons.append(f"Drawdown {dd:.1f}% above comfort zone {config.DD_WARN:.0f}%.")
        if sharpe < config.SHARPE_GOOD:
            reasons.append(f"Sharpe {sharpe:.2f} below target {config.SHARPE_GOOD:.1f}.")
        if win_rate < config.WIN_RATE_GOOD:
            reasons.append(f"Win Rate {win_rate:.1f}% below target {config.WIN_RATE_GOOD:.0f}%.")
        if calmar < config.CALMAR_GOOD:
            reasons.append(f"Calmar {calmar:.2f} below target {config.CALMAR_GOOD:.2f}.")
        if has_pf and profit_factor < config.PROFIT_FACTOR_GOOD:
            reasons.append(f"Profit Factor {profit_factor:.2f} below target {config.PROFIT_FACTOR_GOOD:.1f}.")
        if abs(tpw - config.TPW_TARGET) > config.TPW_TOL:
            reasons.append(f"Trades/week {tpw:.2f} far from target {config.TPW_TARGET:.0f}.")
        if not reasons:
            reasons.append("Mixed return/risk profile — does not fully meet GREEN criteria.")
        recommendation = "CAUTION — consider parameter changes or reduced position size."

    confidence = _confidence(score, status)

    return {
        "status": status,
        "color": status,
        "reasons": reasons,
        "recommendation": recommendation,
        "score": score,
        "confidence": confidence,
        "sharpe": sharpe,
        "win_rate": win_rate,
        "calmar": calmar,
        "profit_factor": profit_factor if has_pf else None,
    }


def final_decision(scenarios_dict: dict) -> dict:
    """Aggregate scenario decisions into a single INVEST / CAUTION / NO label.

    Logic:
    1. All RED → NO
    2. Has GREEN with sufficient confidence → INVEST (best GREEN by score)
    3. Has GREEN but borderline confidence → CAUTION
    4. Only YELLOW → CAUTION (best YELLOW by score)
    5. Fallback → best overall score
    """
    if not scenarios_dict:
        return {
            "label": "NO",
            "text": "NO — no scenarios provided.",
            "recommended": None,
            "reason": "Empty scenarios input; nothing to evaluate.",
            "confidence": "LOW",
        }

    statuses = {k: v["decision"]["status"] for k, v in scenarios_dict.items()}
    scores = {k: v["decision"]["score"] for k, v in scenarios_dict.items()}
    all_red = all(s == "RED" for s in statuses.values())

    def best_by_score(items):
        return sorted(items, key=lambda k: scores[k], reverse=True)[0]

    green_keys = [k for k, s in statuses.items() if s == "GREEN"]
    yellow_keys = [k for k, s in statuses.items() if s == "YELLOW"]

    if all_red:
        recommended = best_by_score(list(statuses.keys()))
        return {
            "label": "NO",
            "text": "NO — all scenarios breach one or more hard risk limits.",
            "recommended": recommended,
            "reason": "Every scenario failed at least one hard threshold (return, drawdown, Sharpe, Calmar, or Profit Factor).",
            "confidence": "LOW",
        }

    if green_keys:
        recommended = best_by_score(green_keys)
        rec = scenarios_dict[recommended]["decision"]
        sharpe = rec.get("sharpe", 0)
        wr = rec.get("win_rate", 0)
        calmar = rec.get("calmar", 0)
        score = rec["score"]
        confidence = rec.get("confidence", "MEDIUM")

        # Borderline GREEN → downgrade to CAUTION
        if score < config.SCORE_CONFIDENCE_MIN:
            return {
                "label": "CAUTION",
                "text": "CAUTION — scenario is GREEN but confidence is borderline.",
                "recommended": recommended,
                "reason": (
                    f"Scenario {recommended} passed all thresholds but score {score:.2f} "
                    f"is below confidence minimum {config.SCORE_CONFIDENCE_MIN:.2f}."
                ),
                "confidence": "MEDIUM",
            }

        return {
            "label": "INVEST",
            "text": "INVEST — at least one scenario is robust with acceptable risk.",
            "recommended": recommended,
            "reason": (
                f"Scenario {recommended}: Sharpe {sharpe:.2f}, "
                f"Win Rate {wr:.1f}%, Calmar {calmar:.2f}."
            ),
            "confidence": confidence,
        }

    # Only YELLOW scenarios remain
    recommended = best_by_score(yellow_keys)
    return {
        "label": "CAUTION",
        "text": "CAUTION — no fully robust setup; proceed only with strict risk controls.",
        "recommended": recommended,
        "reason": (
            f"Scenario {recommended} has the best score ({scores[recommended]:.2f}) "
            "but did not reach GREEN status on all criteria."
        ),
        "confidence": "LOW",
    }
