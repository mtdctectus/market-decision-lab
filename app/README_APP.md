# App notes

This Streamlit app is the UI layer for Market Decision Lab.

## What it does
- Lets you select exchange, asset, timeframe, and test horizon.
- Runs either:
  - **Run Quick Check** (single backtest)
  - **Run A/B/C Compare** (parameter and timeframe mini-sweep)
- Shows decision status cards and historical saved runs.

## Runtime assumptions
- Designed to run directly on Streamlit Cloud.
- Uses root-level `requirements.txt`.
- Persists run history in `data/app.db` (SQLite).
