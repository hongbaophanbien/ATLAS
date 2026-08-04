from __future__ import annotations
import math
from typing import Any
import numpy as np
import pandas as pd
from core import atr, ema, ensure_ohlcv, safe_float

HORIZON = {
    "Day trade": {"lookback": 20, "tp1_atr": 1.10, "tp2_atr": 1.65, "stretch_atr": 2.20},
    "Ngày mai": {"lookback": 30, "tp1_atr": 1.40, "tp2_atr": 2.00, "stretch_atr": 2.80},
    "Swing 3–5 ngày": {"lookback": 60, "tp1_atr": 1.95, "tp2_atr": 2.75, "stretch_atr": 3.70},
    "Swing 1–2 tuần": {"lookback": 100, "tp1_atr": 2.70, "tp2_atr": 3.70, "stretch_atr": 4.80},
}

def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))

def mtf_map(mtf: pd.DataFrame) -> dict[str, float]:
    result = {}
    if mtf is None or mtf.empty:
        return result
    for _, row in mtf.iterrows():
        result[str(row.get("timeframe", ""))] = safe_float(row.get("trend_score"), 50.0)
    return result

def structural_levels(daily: pd.DataFrame, horizon: str) -> dict[str, float]:
    data = ensure_ohlcv(daily)
    if len(data) < 22:
        return {}
    cfg = HORIZON.get(horizon, HORIZON["Ngày mai"])
    price = safe_float(data["Close"].iloc[-1])
    atr_now = max(safe_float(atr(data, 14).iloc[-1], price * 0.025), 0.01)
    e9 = safe_float(ema(data["Close"], 9).iloc[-1], price)
    e21 = safe_float(ema(data["Close"], 21).iloc[-1], price)
    recent = data.tail(min(cfg["lookback"], len(data)))

    highs = [
        safe_float(data["High"].iloc[-2], np.nan),
        safe_float(data["High"].tail(5).max(), np.nan),
        safe_float(data["High"].tail(10).max(), np.nan),
        safe_float(recent["High"].max(), np.nan),
    ]
    lows = [
        safe_float(data["Low"].iloc[-2], np.nan),
        safe_float(data["Low"].tail(5).min(), np.nan),
        safe_float(data["Low"].tail(10).min(), np.nan),
        e9, e21,
    ]
    resistances = sorted(set(
        v for v in highs if math.isfinite(v) and v > price + 0.05 * atr_now
    ))
    supports = sorted(set(
        (v for v in lows if math.isfinite(v) and v < price - 0.03 * atr_now)
    ), reverse=True)

    r1 = resistances[0] if resistances else price + cfg["tp1_atr"] * atr_now
    r2 = resistances[1] if len(resistances) > 1 else max(r1 + 0.55 * atr_now, price + cfg["tp2_atr"] * atr_now)
    s1 = supports[0] if supports else min(e9, price - 0.40 * atr_now)
    s2 = supports[1] if len(supports) > 1 else min(e21, s1 - 0.60 * atr_now)
    stretch = max(r2 + 0.65 * atr_now, price + cfg["stretch_atr"] * atr_now)

    return {
        "ATR": atr_now, "EMA9": e9, "EMA21": e21,
        "Resistance 1": r1, "Resistance 2": r2,
        "Support 1": s1, "Support 2": s2, "Stretch": stretch,
    }

def calculate_trend_score(row: dict, mtf: pd.DataFrame) -> float:
    tf = mtf_map(mtf)
    common = safe_float(row.get("MTF Score"), 50.0)
    return clamp(
        tf.get("2H", common) * 0.22
        + tf.get("4H", common) * 0.29
        + tf.get("1D", common) * 0.28
        + tf.get("1W", 50.0) * 0.08
        + safe_float(row.get("Smart Money Score"), 50.0) * 0.08
        + safe_float(row.get("Sector Flow"), 50.0) * 0.05
    )

def calculate_entry_score(price: float, levels: dict, row: dict, trend: float):
    atr_now = max(safe_float(levels.get("ATR"), price * 0.025), 0.01)
    e9 = safe_float(levels.get("EMA9"), price)
    e21 = safe_float(levels.get("EMA21"), price)
    r1 = safe_float(levels.get("Resistance 1"), price + atr_now)
    s1 = safe_float(levels.get("Support 1"), price - atr_now)
    pullback = safe_float(row.get("Pullback Risk"), 50)
    rsi = safe_float(row.get("RSI14"), 50)
    extension = safe_float(row.get("Extension ATR"), (price - e21) / atr_now)
    money_in = safe_float(row.get("Money In"), safe_float(row.get("Smart Money Score"), 50))
    selloff = safe_float(row.get("Sell-off Risk"), 50)

    d9 = abs(price - e9) / atr_now
    d21 = abs(price - e21) / atr_now
    room_r = (r1 - price) / atr_now
    room_s = (price - s1) / atr_now
    score = 55.0
    reasons = []

    score += 8 if trend >= 65 else -10 if trend <= 42 else 0
    if d9 <= 0.45:
        score += 17; reasons.append("gần EMA9")
    elif d9 <= 0.90:
        score += 7
    else:
        score -= min(19, (d9 - 0.9) * 10); reasons.append("cách EMA9")

    if d21 <= 0.75:
        score += 9; reasons.append("gần EMA21")
    elif d21 > 2.0:
        score -= 8

    if room_r < 0.40:
        score -= 25; reasons.append("sát kháng cự")
    elif room_r < 0.90:
        score -= 12; reasons.append("upside gần thấp")
    elif room_r >= 1.35:
        score += 8

    if room_s <= 0.55:
        score += 9
    elif room_s > 2.2:
        score -= 7

    score -= max(0, pullback - 55) * 0.40
    score -= max(0, abs(extension) - 1.5) * 8
    score -= max(0, rsi - 70) * 1.1
    score -= max(0, selloff - 60) * 0.28
    score += max(0, money_in - 55) * 0.18
    score = clamp(score)

    label = (
        "ĐẸP — chờ trigger" if score >= 80 else
        "TỐT — vào có điều kiện" if score >= 65 else
        "TRUNG BÌNH — chờ retest" if score >= 48 else
        "MUỘN — không chase" if score >= 30 else
        "XẤU — đứng ngoài"
    )
    return round(score, 1), label, reasons

def scenario_probabilities(row: dict, trend: float, entry: float, price: float, levels: dict):
    pullback = safe_float(row.get("Pullback Risk"), 50)
    rsi = safe_float(row.get("RSI14"), 50)
    money_in = safe_float(row.get("Money In"), safe_float(row.get("Smart Money Score"), 50))
    money_out = safe_float(row.get("Money Out"), 100 - money_in)
    selloff = safe_float(row.get("Sell-off Risk"), 50)
    atr_now = max(safe_float(levels.get("ATR"), price * 0.025), 0.01)
    room = (safe_float(levels.get("Resistance 1"), price + atr_now) - price) / atr_now

    raw = np.array([
        20 + max(0, trend - 50)*0.40 + max(0, money_in - 50)*0.18 + max(0, entry - 55)*0.08 + max(0, room)*4 - max(0, pullback - 55)*0.24 - max(0, rsi - 68)*0.65,
        30 + max(0, trend - 50)*0.18 + max(0, pullback - 45)*0.20 + max(0, rsi - 60)*0.42 + max(0, 0.8-room)*10,
        15 + max(0, pullback - 60)*0.30 + max(0, selloff - 50)*0.20 + max(0, money_out-money_in)*0.18,
        8 + max(0, 48-trend)*0.45 + max(0, selloff-55)*0.28 + max(0, money_out-money_in)*0.22,
    ], dtype=float)
    raw = np.clip(raw, 3, None)
    p = raw / raw.sum() * 100
    return {
        "Continuation": round(float(p[0]),1),
        "Shallow Retest": round(float(p[1]),1),
        "Deep Retest": round(float(p[2]),1),
        "Breakdown": round(float(p[3]),1),
    }

def analyze_brain(daily: pd.DataFrame, row: dict, mtf: pd.DataFrame, horizon: str) -> dict[str, Any]:
    data = ensure_ohlcv(daily)
    if data.empty or not row:
        return {}
    price = safe_float(data["Close"].iloc[-1])
    levels = structural_levels(data, horizon)
    trend = calculate_trend_score(row, mtf)
    entry, label, reasons = calculate_entry_score(price, levels, row, trend)
    scenarios = scenario_probabilities(row, trend, entry, price, levels)
    if entry >= 70:
        decision = "CANH MUA — chỉ sau trigger"
    elif trend >= 62 and entry < 48:
        decision = "BULLISH NHƯNG KHÔNG MUA ĐUỔI"
    elif trend <= 42:
        decision = "BEARISH / ƯU TIÊN ĐỨNG NGOÀI"
    else:
        decision = "CHỜ RETEST HOẶC BREAKOUT XÁC NHẬN"
    return {
        "Trend Score": round(trend,1), "Entry Score": entry,
        "Entry Label": label, "Decision": decision,
        "Scenarios": scenarios, "Levels": levels, "Entry Reasons": reasons,
    }
