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
runs = pd.read_sql_query('select * from runs order by run_ts desc', conn)
trades = pd.read_sql_query('select * from trades order by exit_ts asc', conn)

# Save to CSV files
runs.to_csv('runs.csv', index=False)
trades.to_csv('trades.csv', index=False)

# Close connection
conn.close()

# Print summary
print(f'Exported: {len(runs)} runs and {len(trades)} trades')
