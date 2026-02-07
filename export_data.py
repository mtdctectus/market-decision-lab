#!/usr/bin/env python3
"""Export runs and trades from SQLite database to CSV files."""

import sqlite3
import pandas as pd
from pathlib import Path

# Database path
db = Path('data/app.db')

# Check if database exists
if not db.exists():
    print(f"Database not found at {db}")
    print("Please run the Streamlit app first to generate the database.")
    exit(1)

# Connect to database
conn = sqlite3.connect(db)

# Export runs table (most recent first) and trades table (chronological order by exit time)
runs = pd.read_sql_query(
    'SELECT run_id, run_ts, exchange, symbol, timeframe, days, params_json, metrics_json, decision_json '
    'FROM runs ORDER BY run_ts DESC',
    conn
)
trades = pd.read_sql_query(
    'SELECT run_id, entry_ts, exit_ts, entry, exit, pnl, pnl_pct, reason, sl, tp '
    'FROM trades ORDER BY exit_ts ASC',
    conn
)

# Save to CSV files
runs.to_csv('runs.csv', index=False)
trades.to_csv('trades.csv', index=False)

# Close connection
conn.close()

# Print summary
print(f'Exported: {len(runs)} runs and {len(trades)} trades')
