from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


COLUMNS = [
    "Timestamp", "Ticker", "Direction", "Instrument", "Entry", "Exit",
    "Quantity", "Expiration", "Strike", "Plan Entry Low", "Plan Entry High",
    "Plan Stop", "Plan TP1", "Plan TP2", "Reason", "Notes",
]


def empty_journal() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def load_journal(path: str | Path) -> pd.DataFrame:
    file_path = Path(path)
    if not file_path.exists():
        return empty_journal()
    try:
        data = pd.read_csv(file_path)
    except Exception:
        return empty_journal()
    for column in COLUMNS:
        if column not in data.columns:
            data[column] = np.nan
    return data[COLUMNS]


def save_journal(path: str | Path, df: pd.DataFrame) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def add_trade(path: str | Path, trade: dict) -> pd.DataFrame:
    data = load_journal(path)
    row = {column: trade.get(column, np.nan) for column in COLUMNS}
    row["Timestamp"] = trade.get("Timestamp") or datetime.now().isoformat(timespec="seconds")
    data = pd.concat([data, pd.DataFrame([row])], ignore_index=True)
    save_journal(path, data)
    return data


def journal_stats(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "Trades": 0, "Closed": 0, "Win Rate": np.nan,
            "Net P/L": 0.0, "Avg P/L": np.nan,
        }

    data = df.copy()
    entry = pd.to_numeric(data["Entry"], errors="coerce")
    exit_ = pd.to_numeric(data["Exit"], errors="coerce")
    quantity = pd.to_numeric(data["Quantity"], errors="coerce").fillna(1.0)
    direction = data["Direction"].astype(str).str.upper()
    instrument = data["Instrument"].astype(str).str.upper()
    multiplier = np.where(instrument.str.contains("OPTION|CALL|PUT"), 100.0, 1.0)
    sign = np.where(direction.str.contains("PUT|SHORT"), -1.0, 1.0)
    pnl = (exit_ - entry) * quantity * multiplier * sign
    closed = pnl.notna()
    closed_pnl = pnl[closed]

    return {
        "Trades": int(len(data)),
        "Closed": int(closed.sum()),
        "Win Rate": float((closed_pnl > 0).mean() * 100.0) if len(closed_pnl) else np.nan,
        "Net P/L": float(closed_pnl.sum()) if len(closed_pnl) else 0.0,
        "Avg P/L": float(closed_pnl.mean()) if len(closed_pnl) else np.nan,
    }
