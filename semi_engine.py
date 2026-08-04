from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from core import safe_float


SEMI_UNIVERSE = [
    "SMH", "SOXX",
    "NVDA", "AMD", "AVGO", "TSM",
    "MU", "MRVL", "ARM", "INTC", "SNDK",
    "AMAT", "LRCX", "KLAC", "ASML",
    "QCOM", "ALAB", "DELL", "WDC", "GLW",
]


def _clamp(value: float, low: float = 5.0, high: float = 90.0) -> float:
    return max(low, min(high, float(value)))


def _probabilities(row: pd.Series | dict) -> tuple[float, float, float]:
    call_score = safe_float(row.get("Call Score"), 50)
    put_score = safe_float(row.get("Put Score"), 50)
    money_in = safe_float(row.get("Money In"), 50)
    money_out = safe_float(row.get("Money Out"), 50)
    net_flow = safe_float(row.get("Net Flow"), 0)
    mtf = safe_float(row.get("MTF Score"), 50)
    pullback = safe_float(row.get("Pullback Risk"), 50)
    selloff = safe_float(row.get("Sell-off Risk"), 50)
    rsi = safe_float(row.get("RSI14"), 50)

    call_raw = (
        call_score * 0.34
        + money_in * 0.22
        + mtf * 0.20
        + _clamp(50 + net_flow * 1.2) * 0.12
        + (100 - pullback) * 0.12
    )
    put_raw = (
        put_score * 0.34
        + money_out * 0.22
        + (100 - mtf) * 0.20
        + _clamp(50 - net_flow * 1.2) * 0.12
        + selloff * 0.12
    )

    if rsi >= 72:
        call_raw -= (rsi - 72) * 1.5
    if rsi <= 28:
        put_raw -= (28 - rsi) * 1.5

    call_raw = max(call_raw, 1)
    put_raw = max(put_raw, 1)

    # Reserve probability for "WAIT"; this prevents forced opposite trades.
    directional_edge = abs(call_raw - put_raw)
    wait_raw = max(18.0, 52.0 - directional_edge * 0.9)

    total = call_raw + put_raw + wait_raw
    return (
        round(call_raw / total * 100, 1),
        round(put_raw / total * 100, 1),
        round(wait_raw / total * 100, 1),
    )


def _decision(
    row: pd.Series | dict,
    call_probability: float,
    put_probability: float,
    wait_probability: float,
) -> tuple[str, str]:
    call_score = safe_float(row.get("Call Score"), 50)
    put_score = safe_float(row.get("Put Score"), 50)
    money_in = safe_float(row.get("Money In"), 50)
    money_out = safe_float(row.get("Money Out"), 50)
    net_flow = safe_float(row.get("Net Flow"), 0)
    mtf = safe_float(row.get("MTF Score"), 50)
    pullback = safe_float(row.get("Pullback Risk"), 50)
    selloff = safe_float(row.get("Sell-off Risk"), 50)

    call_confirmed = all([
        call_probability >= 52,
        call_score >= 66,
        mtf >= 56,
        money_in > money_out,
        net_flow >= 4,
        pullback <= 65,
    ])
    put_confirmed = all([
        put_probability >= 52,
        put_score >= 64,
        mtf <= 48,
        money_out > money_in,
        net_flow <= -4,
        selloff >= 55,
    ])

    if call_confirmed:
        return "CALL", "Trend + Money In + đa khung cùng xác nhận."
    if put_confirmed:
        return "PUT", "Money Out + sell-off risk + đa khung cùng xác nhận."

    if call_probability > put_probability:
        return "WAIT CALL", "Bias nghiêng CALL nhưng còn thiếu trigger hoặc entry chưa đẹp."
    if put_probability > call_probability:
        return "WAIT PUT", "Bias nghiêng PUT nhưng chưa có breakdown xác nhận."
    return "WAIT", "Hai hướng còn cân bằng; không ép giao dịch."


def build_semi_dashboard(scan: pd.DataFrame) -> pd.DataFrame:
    if scan is None or scan.empty:
        return pd.DataFrame()

    frame = scan[scan["Ticker"].isin(SEMI_UNIVERSE)].copy()
    if frame.empty:
        return frame

    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        call_prob, put_prob, wait_prob = _probabilities(row)
        decision, reason = _decision(row, call_prob, put_prob, wait_prob)

        price = safe_float(row.get("Price"), np.nan)
        entry_low = safe_float(row.get("Entry Low"), price)
        entry_high = safe_float(row.get("Entry High"), price)
        stop = safe_float(row.get("Stop"), np.nan)
        tp1 = safe_float(row.get("TP1"), np.nan)
        tp2 = safe_float(row.get("TP2"), np.nan)

        rows.append({
            "Ticker": row.get("Ticker"),
            "Decision": decision,
            "CALL %": call_prob,
            "PUT %": put_prob,
            "WAIT %": wait_prob,
            "Price": price,
            "Money In": safe_float(row.get("Money In"), 50),
            "Money Out": safe_float(row.get("Money Out"), 50),
            "Net Flow": safe_float(row.get("Net Flow"), 0),
            "MTF Score": safe_float(row.get("MTF Score"), 50),
            "Pullback Risk": safe_float(row.get("Pullback Risk"), 50),
            "Sell-off Risk": safe_float(row.get("Sell-off Risk"), 50),
            "Call Score": safe_float(row.get("Call Score"), 50),
            "Put Score": safe_float(row.get("Put Score"), 50),
            "Entry Low": entry_low,
            "Entry High": entry_high,
            "Stop": stop,
            "TP1": tp1,
            "TP2": tp2,
            "Reason": reason,
        })

    result = pd.DataFrame(rows)
    priority = {
        "CALL": 0,
        "PUT": 0,
        "WAIT CALL": 1,
        "WAIT PUT": 1,
        "WAIT": 2,
    }
    result["_priority"] = result["Decision"].map(priority).fillna(3)
    result["_edge"] = (result["CALL %"] - result["PUT %"]).abs()
    result = result.sort_values(
        ["_priority", "_edge", "Net Flow"],
        ascending=[True, False, False],
    ).drop(columns=["_priority", "_edge"]).reset_index(drop=True)
    return result


def semi_market_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame is None or frame.empty:
        return {
            "bias": "NO DATA",
            "call_count": 0,
            "put_count": 0,
            "wait_count": 0,
            "leader": "N/A",
            "weakest": "N/A",
        }

    call_count = int(frame["Decision"].eq("CALL").sum())
    put_count = int(frame["Decision"].eq("PUT").sum())
    wait_count = len(frame) - call_count - put_count

    mean_call = float(frame["CALL %"].mean())
    mean_put = float(frame["PUT %"].mean())
    if mean_call >= mean_put + 7:
        bias = "SEMI BULLISH"
    elif mean_put >= mean_call + 7:
        bias = "SEMI BEARISH"
    else:
        bias = "SEMI MIXED / WAIT"

    leader = frame.sort_values(
        ["CALL %", "Net Flow"], ascending=False
    ).iloc[0]["Ticker"]
    weakest = frame.sort_values(
        ["PUT %", "Net Flow"], ascending=[False, True]
    ).iloc[0]["Ticker"]

    return {
        "bias": bias,
        "call_count": call_count,
        "put_count": put_count,
        "wait_count": wait_count,
        "leader": leader,
        "weakest": weakest,
    }
