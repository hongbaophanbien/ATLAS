
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import pandas as pd

CALL_LABELS = {"BUY CALL", "WATCH CALL"}
PUT_LABELS = {"BUY PUT", "WATCH PUT"}

def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default

def normalize_bias(value: Any) -> str:
    text = str(value or "").strip().upper()
    if "BEAR" in text:
        return "BEARISH"
    if "BULL" in text:
        return "BULLISH"
    return "NEUTRAL"

def build_decision(row: pd.Series) -> str:
    trade_score = _num(row.get("Trade Score"))
    call_score = _num(row.get("Call Score"))
    put_score = _num(row.get("Put Score"))
    pullback = _num(row.get("Pullback Risk"))
    selloff = _num(row.get("Sell-off Risk"))
    bias = normalize_bias(row.get("Overnight Bias"))
    day_pct = _num(row.get("1D %"))

    bullish_score = max(call_score, trade_score + (6 if bias == "BULLISH" else 0) + max(day_pct, 0))
    bearish_score = max(put_score, trade_score + (6 if bias == "BEARISH" else 0) + max(-day_pct, 0))

    call_blocked = pullback >= 45 or selloff >= 55
    put_blocked = selloff <= 12 and bias == "BULLISH"

    if bullish_score >= 82 and bullish_score >= bearish_score + 4 and not call_blocked:
        return "BUY CALL"
    if bearish_score >= 82 and bearish_score >= bullish_score + 4 and not put_blocked:
        return "BUY PUT"
    if bullish_score >= 70 and bullish_score >= bearish_score and not call_blocked:
        return "WATCH CALL"
    if bearish_score >= 70 and bearish_score > bullish_score and not put_blocked:
        return "WATCH PUT"
    return "WAIT"

def apply_decisions(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    out["Decision"] = out.apply(build_decision, axis=1)
    return out

def fill_option_signals(options: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    if options is None or options.empty:
        return pd.DataFrame()
    out = options.copy()
    decision_map = {}
    if decisions is not None and not decisions.empty and "Ticker" in decisions.columns:
        for _, row in decisions.iterrows():
            decision_map[str(row["Ticker"]).upper()] = str(row.get("Decision", "WAIT"))

    def signal_for(row: pd.Series) -> str:
        ticker = str(row.get("Ticker", "")).upper()
        current = str(row.get("Signal", "") or "").strip().upper()
        return current or decision_map.get(ticker, "WAIT")

    out["Signal"] = out.apply(signal_for, axis=1)

    if "Delta" in out.columns:
        for idx, row in out.iterrows():
            sig = str(row.get("Signal", "")).upper()
            delta = _num(row.get("Delta"))
            if sig in CALL_LABELS:
                out.at[idx, "Delta"] = abs(delta)
            elif sig in PUT_LABELS:
                out.at[idx, "Delta"] = -abs(delta)
    return out

@dataclass(frozen=True)
class SnapshotHealth:
    age_seconds: float
    label: str
    message: str

def snapshot_health(updated_at: Any) -> SnapshotHealth:
    if not updated_at:
        return SnapshotHealth(float("inf"), "NO DATA", "Chưa có snapshot.")
    ts = pd.to_datetime(updated_at, utc=True, errors="coerce")
    if pd.isna(ts):
        return SnapshotHealth(float("inf"), "INVALID", "Timestamp snapshot không hợp lệ.")
    age = max(0.0, (datetime.now(timezone.utc) - ts.to_pydatetime()).total_seconds())
    if age <= 90:
        return SnapshotHealth(age, "FRESH", f"Cập nhật {int(age)} giây trước.")
    if age <= 300:
        return SnapshotHealth(age, "WARNING", f"Cập nhật {int(age // 60)} phút trước.")
    return SnapshotHealth(age, "DELAYED", f"Snapshot cũ {age / 60:.1f} phút.")

def format_snapshot_age(updated_at: Any) -> str:
    health = snapshot_health(updated_at)
    if health.age_seconds == float("inf"):
        return health.message
    if health.age_seconds < 60:
        return f"{int(health.age_seconds)}s ago"
    return f"{health.age_seconds / 60:.1f} min old"

def compact_numbers(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    out = frame.copy()
    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            out[col] = out[col].round(2)
    return out
