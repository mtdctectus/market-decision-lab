# Market Decision Lab

Market Decision Lab is a Streamlit decision-support application for evaluating whether market conditions are reasonable for a strategy hypothesis.

> This application is for research and education only.
> It does not execute live trades and is not financial advice.

## Features
- Pulls OHLCV market data through `ccxt`.
- Runs a long-only EMA + ATR backtest.
- Includes an **Auto Strategy Lab** that generates multiple explainable strategy candidates, backtests them, and ranks them by objective.
- Computes performance and risk metrics.
- Produces a decision label: **INVEST**, **CAUTION**, or **NO**.
- Stores run and trade history in SQLite at `data/app.db`.
- Collects production-friendly CSV logs for run audits and diagnostics.

## Repository structure
- `app/` contains Streamlit UI code only.
- `src/mdl/` contains the reusable research/decision engine package consumed by the UI and tools.
- `app/streamlit_app.py` - Streamlit entrypoint.
- `app/pages/Logs.py` - Streamlit page for downloading log CSVs and ZIP bundles.
- `src/mdl/` - Internal engine package (data loaders, strategies, backtest engines, metrics, decision logic, and persistence).
- `data/` - SQLite database directory created at runtime.
- `app/data/logs/` - Default CSV log directory.
- `tools/export_data.py` - Script to export runs and trades data to CSV files.
- `requirements.txt` - Python dependencies.

## Requirements
- Python 3.10+

## Run locally
```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

## Strategy Lab (Auto)
The Strategy Lab searches through a compact library of simple long-only strategies and parameter combinations, then ranks candidates by your selected objective:
- **Sharpe**
- **Return**
- **Min Drawdown**
- **Win Rate**

Included strategy families:
- EMA Trend
- EMA Crossover
- RSI Mean Reversion
- Donchian Breakout

For each candidate, the app shows:
- Human-readable strategy explanation text
- Key metrics (return, drawdown, Sharpe, win rate, trade count)
- Equity curve and trade table for inspection

The search is intentionally capped (Streamlit Cloud friendly) to avoid long runtimes.

## Local sanity check
```bash
python tools/smoke_check.py
```

## Log collection and export
The app writes audit-friendly CSV logs to `app/data/logs` by default (override with `MDL_LOG_DIR`).

Collected files:
- `runs.csv` with run-level records (status, latency, rate-limit hits, params, metrics, decision).
- `events.csv` with stage-level lifecycle events (for example UI submit, data fetch, and decision evaluation).
- `errors.csv` with exception summaries and trimmed tracebacks.
- `app_health.csv` is reserved for optional health metrics.

How to download logs:
1. Open the **Logs** page in the Streamlit app.
2. Use download buttons for `runs.csv`, `events.csv`, and `errors.csv`.
3. Use the ZIP button to download all existing log files as one archive.

Privacy notes:
- Sensitive metadata keys are removed before writing logs (for example API keys, tokens, authorization headers, cookies, and IP fields).
- Very long string values are truncated before persistence.
- Do not add secrets to user input fields.

## Export data
To export the runs and trades data from the SQLite database to CSV files:
```bash
python tools/export_data.py
```

This will create two files:
- `runs.csv` - All backtest runs ordered by timestamp (most recent first)
- `trades.csv` - All trades from all runs ordered chronologically by exit time

Alternatively, you can use a one-liner (note: the script version is recommended as it includes a database existence check and uses explicit column lists for better maintainability):
```bash
python -c "
import sqlite3, pandas as pd
from pathlib import Path

db = Path('data/app.db')
conn = sqlite3.connect(db)

runs = pd.read_sql_query('select * from runs order by run_ts desc', conn)
trades = pd.read_sql_query('select * from trades order by exit_ts asc', conn)

runs.to_csv('runs.csv', index=False)
trades.to_csv('trades.csv', index=False)

conn.close()

print(f'Exported: {len(runs)} runs and {len(trades)} trades')
"
```

## Security audit
This repository includes an automated security audit workflow that runs `pip-audit` to check for known vulnerabilities in Python dependencies. The workflow runs on:
- Push to main branch
- Pull requests to main branch
- Manual workflow dispatch

To run the security audit locally:
```bash
pip install pip-audit
pip-audit -r requirements.txt --desc on
```

The audit will fail if any known vulnerabilities are found, ensuring that security issues are caught early.

## Streamlit Cloud deployment
1. Push this repository to GitHub.
2. Create a new Streamlit Cloud app from this repository.
3. Set the main file path to `app/streamlit_app.py`.
4. Deploy.
