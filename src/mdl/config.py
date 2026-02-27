"""Global thresholds and defaults for decision logic."""

RET_MIN = 0
RET_GOOD = 8
DD_WARN = 20
DD_MAX = 25
MIN_TRADES = 12
TPW_TARGET = 2
TPW_TOL = 1

# Sharpe Ratio thresholds
SHARPE_GOOD = 1.0   # >= this is GREEN territory
SHARPE_MIN = 0.3    # < this is a RED flag

# Win Rate thresholds
WIN_RATE_GOOD = 50.0  # >= 50% win rate is healthy
WIN_RATE_MIN = 35.0   # < 35% win rate is a RED flag

# Decision score weights used in _decision_score()
W_RET = 1.0     # weight for annualized return contribution
W_DD = 0.8      # weight for max drawdown penalty
W_TPW = 0.1     # weight for trades-per-week deviation penalty
W_EXP = 0.2     # weight for per-trade expectancy contribution
W_SHARPE = 0.5  # weight for Sharpe Ratio contribution
W_WR = 0.3      # weight for Win Rate contribution
