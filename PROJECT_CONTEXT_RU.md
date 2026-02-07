# Market Decision Lab — project context

Copy this into the start of a new chat so the assistant immediately understands the project.

## Goal
A research Streamlit app that:
- pulls market OHLCV data through **ccxt**;
- runs strategy backtests;
- computes metrics (return, drawdown, trade frequency, expectancy);
- produces a verdict **INVEST / CAUTION / NO** with reasons;
- stores run history in SQLite.

## Stack
- Python 3.11+
- Streamlit UI: `app/streamlit_app.py`
- Core logic: `core/market_decision_lab/*`
- Data/history: `data/app.db` (created automatically)
- Dependencies: root `requirements.txt`

## How the UI works
There are 3 tabs:
- **Quick**: single run with selected parameters
- **Compare**: mini parameter/timeframe sweep and scenario A/B/C selection
- **History**: run and trade history

Colors:
- 🟢 GREEN: strong metrics with acceptable risk
- 🟡 YELLOW: mixed profile
- 🔴 RED: fails minimum thresholds (return/drawdown/trade count)

## What is already done
- Repository is structured as a monorepo: `app/`, `core/`, `data/`.
- UI caching is added for markets and OHLCV (fewer repeated requests and lower rate-limit risk).
- SQLite path is fixed relative to repository root, so DB is always in `data/app.db` regardless of current working directory.

## What to do next
- Keep Streamlit Cloud deployment stable.
- As needed: add a "Refresh data" button and reuse candle cache from SQLite.
- Improve UX: hints, more charts, and result export.

## Assistant working mode
- Be practical: if something is broken, find the cause and provide a ready fix.
- Keep complexity low: Streamlit Cloud first.
- For any change: provide a short explanation and exact files/diff.
