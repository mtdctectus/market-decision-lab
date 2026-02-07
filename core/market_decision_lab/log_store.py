from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "key",
    "secret",
    "token",
    "authorization",
    "auth",
    "cookie",
    "cookies",
    "set-cookie",
    "ip",
    "x-forwarded-for",
}

RUN_FIELDS = [
    "run_id",
    "run_ts",
    "exchange",
    "symbol",
    "timeframe",
    "days",
    "status",
    "latency_ms",
    "rate_limit_hits",
    "params_json",
    "metrics_json",
    "decision_json",
]

EVENT_FIELDS = [
    "event_ts",
    "run_id",
    "level",
    "stage",
    "message",
    "duration_ms",
    "meta_json",
]

ERROR_FIELDS = [
    "error_ts",
    "run_id",
    "exc_type",
    "exc_message",
    "traceback_short",
    "context_json",
]

APP_HEALTH_FIELDS = ["event_ts", "key", "value", "meta_json"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sanitize_meta(meta: dict) -> dict:
    sanitized: dict = {}
    for key, value in (meta or {}).items():
        key_lower = str(key).lower()
        if key_lower in SENSITIVE_KEYS:
            continue

        if isinstance(value, dict):
            sanitized[key] = sanitize_meta(value)
            continue

        if isinstance(value, list):
            sanitized[key] = [sanitize_meta(v) if isinstance(v, dict) else _truncate_value(v) for v in value]
            continue

        sanitized[key] = _truncate_value(value)

    return sanitized


def _truncate_value(value):
    if isinstance(value, str) and len(value) > 200:
        return f"{value[:20]}..."
    return value


class CsvLogStore:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.files = {
            "runs": self.base_dir / "runs.csv",
            "events": self.base_dir / "events.csv",
            "errors": self.base_dir / "errors.csv",
            "app_health": self.base_dir / "app_health.csv",
        }

    def append_run(self, row: dict) -> None:
        self._append("runs", RUN_FIELDS, row)

    def append_event(self, row: dict) -> None:
        self._append("events", EVENT_FIELDS, row)

    def append_error(self, row: dict) -> None:
        self._append("errors", ERROR_FIELDS, row)

    def read_csv(self, name: str) -> pd.DataFrame:
        file_path = self.files.get(name)
        if not file_path or not file_path.exists():
            return pd.DataFrame()

        df = pd.read_csv(file_path)
        if "Unnamed: 0" in df.columns:
            df = df.drop(columns=["Unnamed: 0"])
        if name == "runs" and "run_ts" in df.columns:
            df["run_ts"] = pd.to_datetime(df["run_ts"], utc=True, errors="coerce")
        return df

    def bundle_zip(self) -> bytes:
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            for file_path in self.files.values():
                if file_path.exists():
                    zip_file.write(file_path, arcname=file_path.name)
        buffer.seek(0)
        return buffer.read()

    def _append(self, name: str, fields: list[str], row: dict) -> None:
        file_path = self.files[name]
        payload = {field: row.get(field) for field in fields}
        file_exists = file_path.exists()

        with file_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            if not file_exists:
                writer.writeheader()
            writer.writerow(payload)


def to_json_str(payload: dict | list | None) -> str:
    safe_payload = payload if payload is not None else {}
    return json.dumps(safe_payload, ensure_ascii=False, default=str)
