from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
CORE_PATH = ROOT / "core"
if str(CORE_PATH) not in sys.path:
    sys.path.insert(0, str(CORE_PATH))

from market_decision_lab.log_store import CsvLogStore

st.set_page_config(page_title="Logs", layout="wide")
st.title("Logs")
st.caption("Download run logs and diagnostics collected by the app.")

log_dir = Path(os.getenv("MDL_LOG_DIR", "app/data/logs"))
if not log_dir.is_absolute():
    log_dir = ROOT / log_dir

store = CsvLogStore(str(log_dir))

runs_df = store.read_csv("runs")

total_runs = int(len(runs_df))
failures_24h = 0
last_run = "N/A"
p95_latency = "N/A"

if not runs_df.empty and "run_ts" in runs_df.columns:
    now_utc = pd.Timestamp.utcnow().tz_convert("UTC")
    failures_24h = int(((runs_df["status"] == "fail") & (runs_df["run_ts"] >= (now_utc - pd.Timedelta(hours=24)))).sum())
    valid_run_ts = runs_df["run_ts"].dropna()
    if not valid_run_ts.empty:
        last_run = valid_run_ts.max().strftime("%Y-%m-%d %H:%M:%S UTC")

if not runs_df.empty and "latency_ms" in runs_df.columns:
    valid_latency = pd.to_numeric(runs_df["latency_ms"], errors="coerce").dropna()
    if not valid_latency.empty:
        p95_latency = f"{int(valid_latency.quantile(0.95))} ms"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total runs", total_runs)
c2.metric("Failures (last 24h)", failures_24h)
c3.metric("Last run", last_run)
c4.metric("P95 latency", p95_latency)

st.divider()


def get_csv_bytes(name: str) -> bytes | None:
    file_path = store.files[name]
    if not file_path.exists():
        return None
    return file_path.read_bytes()


for csv_name in ["runs", "events", "errors"]:
    payload = get_csv_bytes(csv_name)
    if payload is None:
        st.info(f"{csv_name}.csv is not available yet.")
    st.download_button(
        f"Download {csv_name}.csv",
        data=payload or b"",
        file_name=f"{csv_name}.csv",
        mime="text/csv",
        disabled=payload is None,
        use_container_width=True,
    )

bundle = store.bundle_zip()
if not bundle:
    st.info("No log files available yet for a ZIP export.")

st.download_button(
    "Download logs bundle (.zip)",
    data=bundle,
    file_name="logs_bundle.zip",
    mime="application/zip",
    disabled=not bool(bundle),
    use_container_width=True,
)
