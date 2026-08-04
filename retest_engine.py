from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from core import atr, ema, ensure_ohlcv, safe_float


def analyze_retest(daily: pd.DataFrame, row: dict) -> dict[str, Any]:
    data = ensure_ohlcv(daily)
    if len(data) < 22:
        return {}

    price = safe_float(data["Close"].iloc[-1])
    atr_now = max(safe_float(atr(data, 14).iloc[-1], price * 0.025), 0.01)
    e9 = safe_float(ema(data["Close"], 9).iloc[-1], price)
    e21 = safe_float(ema(data["Close"], 21).iloc[-1], price)
    low5 = safe_float(data["Low"].tail(5).min(), price)
    high5 = safe_float(data["High"].tail(5).max(), price)
    pullback = safe_float(row.get("Pullback Risk"), 50.0)
    mtf = safe_float(row.get("MTF Score"), 50.0)
    money_in = safe_float(row.get("Money In"), 50.0)

    support_near = max(min(e9, price), min(low5 + 0.25 * atr_now, price))
    support_deep = min(e21, support_near - 0.55 * atr_now)
    resistance = max(high5, price + 0.75 * atr_now)

    continuation = 25 + max(0, mtf - 50) * 0.34 + max(0, money_in - 50) * 0.18
    shallow = 32 + max(0, pullback - 45) * 0.26 + max(0, mtf - 50) * 0.12
    deep = 18 + max(0, pullback - 60) * 0.35
    breakdown = 10 + max(0, 45 - mtf) * 0.40

    raw = np.array([continuation, shallow, deep, breakdown], dtype=float)
    raw = np.clip(raw, 3, None)
    probs = raw / raw.sum() * 100.0

    if price > e9 + 1.25 * atr_now:
        state = "EXTENDED — KHÔNG CHASE"
    elif abs(price - e9) <= 0.45 * atr_now:
        state = "GẦN RETEST EMA9"
    elif abs(price - e21) <= 0.55 * atr_now:
        state = "GẦN RETEST EMA21"
    else:
        state = "CHỜ XÁC NHẬN"

    return {
        "State": state,
        "Retest Zone Low": round(min(support_deep, support_near), 2),
        "Retest Zone High": round(max(support_deep, support_near), 2),
        "Breakout Trigger": round(resistance, 2),
        "Continuation %": round(float(probs[0]), 1),
        "Shallow Retest %": round(float(probs[1]), 1),
        "Deep Retest %": round(float(probs[2]), 1),
        "Breakdown %": round(float(probs[3]), 1),
    }
