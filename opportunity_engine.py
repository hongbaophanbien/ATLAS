from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from core import safe_float


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def grade(score: float) -> str:
    if score >= 90:
        return "A+"
    if score >= 82:
        return "A"
    if score >= 74:
        return "B+"
    if score >= 68:
        return "B"
    return "SKIP"


def opportunity_score(row: pd.Series | dict) -> dict[str, Any]:
    call_score = safe_float(row.get("Call Score"), 50.0)
    put_score = safe_float(row.get("Put Score"), 50.0)
    money_in = safe_float(row.get("Money In"), 50.0)
    money_out = safe_float(row.get("Money Out"), 50.0)
    net_flow = safe_float(row.get("Net Flow"), 0.0)
    mtf = safe_float(row.get("MTF Score"), 50.0)
    trade = safe_float(row.get("Trade Score"), 50.0)
    pullback = safe_float(row.get("Pullback Risk"), 50.0)
    selloff = safe_float(row.get("Sell-off Risk"), 50.0)
    rsi = safe_float(row.get("RSI14"), 50.0)
    sector = safe_float(row.get("Sector Flow"), 50.0)

    if call_score >= put_score:
        signal = "CALL"
        directional = call_score
        flow = money_in
        trend_quality = mtf
        risk_quality = 100.0 - pullback
        edge = call_score - put_score
        reasons = []
        if money_in >= 65:
            reasons.append("Money In mạnh")
        if mtf >= 65:
            reasons.append("đa khung bullish")
        if sector >= 60:
            reasons.append("sector hỗ trợ")
        if pullback <= 50:
            reasons.append("entry chưa quá nóng")
    else:
        signal = "PUT"
        directional = put_score
        flow = money_out
        trend_quality = 100.0 - mtf
        risk_quality = selloff
        edge = put_score - call_score
        reasons = []
        if money_out >= 65:
            reasons.append("Money Out mạnh")
        if mtf <= 40:
            reasons.append("đa khung bearish")
        if sector <= 42:
            reasons.append("sector yếu")
        if selloff >= 65:
            reasons.append("sell-off risk cao")

    score = (
        directional * 0.30
        + flow * 0.21
        + trend_quality * 0.18
        + trade * 0.11
        + risk_quality * 0.10
        + clamp(50 + edge * 2.0) * 0.07
        + clamp(50 + abs(net_flow) * 1.5) * 0.03
    )

    if signal == "CALL":
        score -= max(0.0, rsi - 72.0) * 1.4
        score -= max(0.0, pullback - 62.0) * 0.45
    else:
        score -= max(0.0, 28.0 - rsi) * 1.3
        score -= max(0.0, 58.0 - selloff) * 0.30

    score = clamp(score)
    conviction = grade(score)

    call_confirmed = all([
        signal == "CALL",
        score >= 72,
        edge >= 8,
        mtf >= 58,
        money_in >= 58,
        money_in > money_out,
        net_flow >= 5,
        pullback <= 65,
        selloff <= 58,
    ])
    put_confirmed = all([
        signal == "PUT",
        score >= 72,
        edge >= 8,
        mtf <= 48,
        money_out >= 58,
        money_out > money_in,
        net_flow <= -5,
        selloff >= 58,
        rsi >= 25,
    ])

    if call_confirmed:
        action = "BUY CALL"
    elif put_confirmed:
        action = "BUY PUT"
    else:
        action = "SKIP"

    return {
        "Signal": signal,
        "Action": action,
        "Opportunity Score": round(score, 1),
        "Conviction": conviction,
        "Edge": round(edge, 1),
        "Reasons": ", ".join(reasons) if reasons else "tín hiệu chưa đủ đồng thuận",
    }


def rank_opportunities(scan: pd.DataFrame) -> pd.DataFrame:
    if scan is None or scan.empty:
        return pd.DataFrame()

    rows = []
    for _, row in scan.iterrows():
        result = opportunity_score(row)
        record = row.to_dict()
        record.update(result)
        rows.append(record)

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame

    frame = frame[
        (frame["Action"] != "SKIP")
        & (frame["Opportunity Score"] >= 68)
    ].copy()

    if frame.empty:
        return frame

    return frame.sort_values(
        ["Opportunity Score", "Trade Score", "Net Flow"],
        ascending=False,
    ).reset_index(drop=True)
