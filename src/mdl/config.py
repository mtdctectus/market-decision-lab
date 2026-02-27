"""Global thresholds and defaults for decision logic."""

# ── Return thresholds ──────────────────────────────────────────────────────────
RET_MIN = -5       # below this → hard RED (small negatives tolerable)
RET_GOOD = 15      # >= this → GREEN (8% is passive index; active trading needs more)

# ── Drawdown thresholds ────────────────────────────────────────────────────────
DD_WARN = 15       # above this → YELLOW (was 20 — too lenient)
DD_MAX = 20        # above this → hard RED (was 25 — too lenient)

# ── Trade count ────────────────────────────────────────────────────────────────
MIN_TRADES = 12    # fewer trades → statistically unreliable
TPW_TARGET = 2     # target trades per week
TPW_TOL = 1        # acceptable deviation

# ── Sharpe Ratio ───────────────────────────────────────────────────────────────
SHARPE_GOOD = 1.0  # >= 1.0 → GREEN (industry standard)
SHARPE_MIN = 0.5   # < 0.5 → hard RED (was 0.3 — too lenient, barely above noise)

# ── Win Rate ───────────────────────────────────────────────────────────────────
WIN_RATE_GOOD = 50.0  # >= 50% → GREEN
WIN_RATE_MIN = 38.0   # < 38% → hard RED (was 35% — raised)

# ── Calmar Ratio (Ann Return % / Max Drawdown %) ──────────────────────────────
CALMAR_GOOD = 0.75   # strong risk-adjusted return relative to worst drawdown
CALMAR_MIN = 0.25    # below this → hard RED

# ── Profit Factor (Gross Profit / Gross Loss) ─────────────────────────────────
PROFIT_FACTOR_GOOD = 1.5   # earns 1.50 for every 1.00 lost — solid edge
PROFIT_FACTOR_MIN = 1.1    # < 1.1 → hard RED (barely above breakeven)

# ── Confidence score threshold ────────────────────────────────────────────────
# GREEN scenario with normalised score below this gets downgraded to CAUTION
SCORE_CONFIDENCE_MIN = 0.8

# ── Decision score weights ────────────────────────────────────────────────────
W_SHARPE = 0.8   # primary quality signal (raised from 0.5)
W_RET = 0.6      # raw return matters but misleads without risk context (was 1.0)
W_DD = 1.0       # drawdown penalty — protect capital first (was 0.8)
W_TPW = 0.1      # trades-per-week deviation
W_EXP = 0.3      # per-trade expectancy (raised from 0.2)
W_WR = 0.25      # win rate (lowered slightly — high WR with tiny wins is misleading)
W_CALMAR = 0.4   # Calmar Ratio (new)
W_PF = 0.3       # Profit Factor (new)
