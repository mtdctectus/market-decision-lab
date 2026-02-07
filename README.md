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
- `requirements.txt` - Python dependencies.

## Requirements
- Python 3.10+

## Run locally
```bash
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

## Streamlit Cloud deployment
1. Push this repository to GitHub.
2. Create a new Streamlit Cloud app from this repository.
3. Set the main file path to `app/streamlit_app.py`.
4. Deploy.
