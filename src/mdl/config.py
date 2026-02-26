"""Global thresholds and defaults for decision logic."""

RET_MIN = 0
RET_GOOD = 8
DD_WARN = 20
DD_MAX = 25
MIN_TRADES = 12
TPW_TARGET = 2
TPW_TOL = 1

# Decision score weights used in _decision_score()
W_RET = 1.0   # weight for annualized return contribution (higher = better)
W_DD = 0.8    # weight for max drawdown penalty (higher = penalises risk more)
W_TPW = 0.1   # weight for trades-per-week deviation penalty
W_EXP = 0.2   # weight for per-trade expectancy contribution
