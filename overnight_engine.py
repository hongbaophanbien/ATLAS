from __future__ import annotations

from datetime import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

NEW_YORK = ZoneInfo("America/New_York")


def _number(value, default=np.nan):
    try:
        value = float(value)
        return value if np.isfinite(value) else default
    except Exception:
        return default


def _ny_index(frame: pd.DataFrame) -> pd.DatetimeIndex:
    idx = pd.DatetimeIndex(frame.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    return idx.tz_convert(NEW_YORK)


def overnight_metrics(daily: pd.DataFrame, extended: pd.DataFrame) -> dict:
    """Build an extended-hours proxy from Yahoo 5-minute pre/post-market data.

    This is not a complete 24-hour Robinhood overnight tape. Yahoo generally
    covers pre-market and after-hours (approximately 04:00-20:00 ET).
    Missing data is reported as unavailable rather than converted to zero.
    """
    result = {
        "Extended Price": np.nan,
        "Overnight %": np.nan,
        "Premarket %": np.nan,
        "After Hours %": np.nan,
        "Overnight Bias": "DATA UNAVAILABLE",
        "Overnight Session": "NONE",
        "Overnight Confirm": "UNAVAILABLE",
        "Gap Risk": "UNKNOWN",
        "Overnight Updated": "—",
        "Overnight Source": "Yahoo extended-hours proxy (04:00-20:00 ET)",
    }

    if daily is None or daily.empty or extended is None or extended.empty:
        return result

    previous_close = _number(daily["Close"].dropna().iloc[-1])
    if not np.isfinite(previous_close) or previous_close <= 0:
        return result

    frame = extended.copy().dropna(subset=["Close"])
    if frame.empty:
        return result

    ny_idx = _ny_index(frame)
    frame.index = ny_idx
    times = pd.Series(ny_idx.time, index=frame.index)

    pre_mask = times.map(lambda t: time(4, 0) <= t < time(9, 30))
    regular_mask = times.map(lambda t: time(9, 30) <= t < time(16, 0))
    after_mask = times.map(lambda t: time(16, 0) <= t <= time(20, 0))
    extended_mask = pre_mask | after_mask

    non_regular = frame.loc[extended_mask]
    if non_regular.empty:
        return result

    latest_ts = non_regular.index[-1]
    latest_price = _number(non_regular["Close"].iloc[-1])
    if not np.isfinite(latest_price) or latest_price <= 0:
        return result

    pct = (latest_price / previous_close - 1.0) * 100.0
    latest_time = latest_ts.time()
    if time(4, 0) <= latest_time < time(9, 30):
        session = "PREMARKET"
    elif time(16, 0) <= latest_time <= time(20, 0):
        session = "AFTER HOURS"
    else:
        session = "EXTENDED"

    pre = frame.loc[pre_mask]
    after = frame.loc[after_mask]
    pre_pct = np.nan
    after_pct = np.nan
    if not pre.empty:
        pre_price = _number(pre["Close"].iloc[-1])
        if np.isfinite(pre_price):
            pre_pct = (pre_price / previous_close - 1.0) * 100.0
    if not after.empty:
        after_price = _number(after["Close"].iloc[-1])
        if np.isfinite(after_price):
            after_pct = (after_price / previous_close - 1.0) * 100.0

    if pct >= 1.5:
        bias = "STRONG BULLISH"
    elif pct >= 0.45:
        bias = "BULLISH"
    elif pct <= -1.5:
        bias = "STRONG BEARISH"
    elif pct <= -0.45:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    abs_gap = abs(pct)
    if abs_gap >= 3.0:
        gap_risk = "EXTREME — DO NOT CHASE"
    elif abs_gap >= 2.0:
        gap_risk = "HIGH — WAIT RETEST"
    elif abs_gap >= 1.0:
        gap_risk = "MEDIUM"
    else:
        gap_risk = "LOW"

    result.update({
        "Extended Price": round(latest_price, 2),
        "Overnight %": round(pct, 2),
        "Premarket %": round(pre_pct, 2) if np.isfinite(pre_pct) else np.nan,
        "After Hours %": round(after_pct, 2) if np.isfinite(after_pct) else np.nan,
        "Overnight Bias": bias,
        "Overnight Session": session,
        "Gap Risk": gap_risk,
        "Overnight Updated": latest_ts.strftime("%Y-%m-%d %I:%M %p ET"),
    })
    return result


def apply_overnight_adjustment(record: dict) -> dict:
    """Apply a bounded score adjustment; overnight never decides alone."""
    output = dict(record or {})
    pct = _number(output.get("Overnight %"))
    if not np.isfinite(pct):
        output["Overnight Confirm"] = "UNAVAILABLE"
        return output

    call_score = _number(output.get("Call Score"), 50.0)
    put_score = _number(output.get("Put Score"), 50.0)
    trade_score = _number(output.get("Trade Score"), 50.0)
    action = str(output.get("Action", output.get("Signal", ""))).upper()

    # Maximum score influence is deliberately small (8 points).
    influence = min(8.0, abs(pct) * 3.0)
    if pct > 0:
        call_score += influence
        put_score -= influence * 0.65
    elif pct < 0:
        put_score += influence
        call_score -= influence * 0.65

    if "CALL" in action:
        if pct >= 0.45:
            confirm = "CONFIRMED"
            trade_score += min(5.0, abs(pct) * 1.5)
        elif pct <= -0.45:
            confirm = "CONFLICT"
            trade_score -= min(8.0, abs(pct) * 2.0)
        else:
            confirm = "NEUTRAL"
    elif "PUT" in action:
        if pct <= -0.45:
            confirm = "CONFIRMED"
            trade_score += min(5.0, abs(pct) * 1.5)
        elif pct >= 0.45:
            confirm = "CONFLICT"
            trade_score -= min(8.0, abs(pct) * 2.0)
        else:
            confirm = "NEUTRAL"
    else:
        confirm = "NEUTRAL"

    output["Call Score"] = round(max(0.0, min(100.0, call_score)), 1)
    output["Put Score"] = round(max(0.0, min(100.0, put_score)), 1)
    output["Trade Score"] = round(max(0.0, min(100.0, trade_score)), 1)
    output["Overnight Confirm"] = confirm
    return output
