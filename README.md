# Market Decision Lab

Market Decision Lab is a Streamlit decision-support application for evaluating whether market conditions are reasonable for a strategy hypothesis.

> This application is for research and education only.
> It does not execute live trades and is not financial advice.

## Features
- Pulls OHLCV market data through `ccxt`.
- Runs a long-only EMA + ATR backtest.
- Computes performance and risk metrics.
- Produces a decision label: **INVEST**, **CAUTION**, or **NO**.
- Stores run and trade history in SQLite at `data/app.db`.

## Repository structure
- `app/streamlit_app.py` - Streamlit entrypoint.
- `core/market_decision_lab/` - Core backtest, data, metrics, decision, scenario, and storage logic.
- `data/` - SQLite database directory created at runtime.
- `export_data.py` - Script to export runs and trades data to CSV files.
- `requirements.txt` - Python dependencies.

## Requirements
- Python 3.10+

## Run locally
```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

## Export data
To export the runs and trades data from the SQLite database to CSV files:
```bash
python export_data.py
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

## Streamlit Cloud deployment
1. Push this repository to GitHub.
2. Create a new Streamlit Cloud app from this repository.
3. Set the main file path to `app/streamlit_app.py`.
4. Deploy.
