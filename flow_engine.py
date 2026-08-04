from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd

from core import (
    analyze_symbol,
    atr,
    cmf,
    ema,
    ensure_ohlcv,
    mfi,
    obv,
    rolling_slope,
    safe_float,
)


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def money_flow_metrics(daily: pd.DataFrame, hourly: pd.DataFrame | None = None) -> dict:
    data = ensure_ohlcv(daily)
    intra = ensure_ohlcv(hourly) if hourly is not None else pd.DataFrame()
    if len(data) < 30:
        return {}

    close = data["Close"]
    volume = data["Volume"].fillna(0.0)
    direction = np.sign(close.diff()).fillna(0.0)

    cmf20 = safe_float(cmf(data, 20).iloc[-1], 0.0)
    mfi14 = safe_float(mfi(data, 14).iloc[-1], 50.0)
    obv_series = obv(data)
    obv_slope = rolling_slope(obv_series, 20)
    price_slope = rolling_slope(close, 20)

    up_volume = float(volume[direction > 0].tail(20).sum())
    down_volume = float(volume[direction < 0].tail(20).sum())
    total_directional = up_volume + down_volume
    up_share = up_volume / total_directional * 100.0 if total_directional > 0 else 50.0

    dollar_volume = close * volume
    signed_dollar = dollar_volume * direction
    net_dollar_proxy = float(signed_dollar.tail(10).sum())
    gross_dollar = float(dollar_volume.tail(10).sum())
    net_dollar_pct = net_dollar_proxy / gross_dollar * 100.0 if gross_dollar > 0 else 0.0

    closes_above_mid = (
        (close - data["Low"]) / (data["High"] - data["Low"]).replace(0, np.nan)
    ).tail(10).mean()
    closes_above_mid = safe_float(closes_above_mid, 0.5)

    accumulation_days = int(
        ((close.pct_change() > 0.005) & (volume > volume.rolling(20).mean())).tail(20).sum()
    )
    distribution_days = int(
        ((close.pct_change() < -0.005) & (volume > volume.rolling(20).mean())).tail(20).sum()
    )

    intraday_flow = 50.0
    vwap_position = np.nan
    if not intra.empty and len(intra) >= 10:
        typical = (intra["High"] + intra["Low"] + intra["Close"]) / 3.0
        cumulative_volume = intra["Volume"].cumsum().replace(0, np.nan)
        vwap = (typical * intra["Volume"]).cumsum() / cumulative_volume
        last_close = safe_float(intra["Close"].iloc[-1])
        last_vwap = safe_float(vwap.iloc[-1], last_close)
        vwap_position = (last_close / last_vwap - 1.0) * 100.0 if last_vwap else 0.0

        intraday_dir = np.sign(intra["Close"].diff()).fillna(0.0)
        intraday_vol = intra["Volume"].fillna(0.0)
        buy_vol = float(intraday_vol[intraday_dir > 0].tail(30).sum())
        sell_vol = float(intraday_vol[intraday_dir < 0].tail(30).sum())
        active = buy_vol + sell_vol
        intraday_flow = buy_vol / active * 100.0 if active > 0 else 50.0

    money_in = (
        clamp((cmf20 + 0.25) / 0.50 * 100.0) * 0.18
        + clamp(mfi14) * 0.14
        + clamp(50.0 + obv_slope * 8.0) * 0.14
        + clamp(up_share) * 0.14
        + clamp(50.0 + net_dollar_pct * 5.0) * 0.12
        + clamp(closes_above_mid * 100.0) * 0.10
        + clamp(50.0 + (accumulation_days - distribution_days) * 6.0) * 0.08
        + clamp(intraday_flow) * 0.10
    )

    divergence_penalty = 0.0
    if price_slope > 0 and obv_slope < 0:
        divergence_penalty += 12.0
    if cmf20 < 0 and close.pct_change(5).iloc[-1] > 0:
        divergence_penalty += 8.0

    money_in = clamp(money_in - divergence_penalty)
    money_out = clamp(100.0 - money_in + max(0.0, divergence_penalty * 0.5))
    net_flow = money_in - money_out

    if money_in >= 68 and distribution_days <= accumulation_days:
        status = "Strong Accumulation"
    elif money_in >= 58:
        status = "Accumulation"
    elif money_out >= 70:
        status = "Heavy Distribution"
    elif money_out >= 58:
        status = "Distribution"
    elif price_slope > 0 and obv_slope < 0:
        status = "Bearish Divergence"
    else:
        status = "Neutral"

    selloff_risk = clamp(
        money_out * 0.45
        + max(0.0, distribution_days - accumulation_days) * 6.0
        + (12.0 if price_slope > 0 and obv_slope < 0 else 0.0)
        + max(0.0, -cmf20) * 40.0
        + max(0.0, -safe_float(vwap_position, 0.0)) * 4.0
    )

    return {
        "Money In": round(money_in, 1),
        "Money Out": round(money_out, 1),
        "Net Flow": round(net_flow, 1),
        "Flow Status": status,
        "Sell-off Risk": round(selloff_risk, 1),
        "CMF20": round(cmf20, 3),
        "MFI14": round(mfi14, 1),
        "OBV Slope": round(obv_slope, 3),
        "Up Volume %": round(up_share, 1),
        "Net Dollar Proxy %": round(net_dollar_pct, 2),
        "Accumulation Days": accumulation_days,
        "Distribution Days": distribution_days,
        "VWAP Position %": round(vwap_position, 2) if math.isfinite(safe_float(vwap_position, np.nan)) else np.nan,
    }


def rank_candidate(base: dict, flow: dict) -> dict:
    if not base or not flow:
        return {}

    mtf = safe_float(base.get("MTF Score"), 50.0)
    trade = safe_float(base.get("Trade Score"), 50.0)
    pullback = safe_float(base.get("Pullback Risk"), 50.0)
    reversal = safe_float(base.get("Reversal Score"), 50.0)
    sector = safe_float(base.get("Sector Flow"), 50.0)
    rsi = safe_float(base.get("RSI14"), 50.0)
    money_in = safe_float(flow.get("Money In"), 50.0)
    money_out = safe_float(flow.get("Money Out"), 50.0)
    selloff = safe_float(flow.get("Sell-off Risk"), 50.0)

    call_score = clamp(
        trade * 0.24 + mtf * 0.22 + money_in * 0.24 + sector * 0.12
        + reversal * 0.08 + (100.0 - pullback) * 0.10
    )
    if rsi > 75:
        call_score -= min(15.0, (rsi - 75.0) * 1.2)

    put_score = clamp(
        money_out * 0.28 + selloff * 0.24 + (100.0 - mtf) * 0.20
        + (100.0 - trade) * 0.12 + (100.0 - sector) * 0.10
        + pullback * 0.06
    )
    if rsi < 28:
        put_score -= min(12.0, (28.0 - rsi) * 1.0)

    edge = max(call_score, put_score)
    if call_score >= 62 and call_score - put_score >= 8:
        category = "CALL"
        action = "Canh call sau trigger"
    elif put_score >= 62 and put_score - call_score >= 8:
        category = "PUT"
        action = "Canh put sau breakdown/retest"
    elif edge >= 52:
        category = "WAIT"
        action = "Chờ xác nhận"
    else:
        category = "NO TRADE"
        action = "Đứng ngoài"

    return {
        "Call Score": round(clamp(call_score), 1),
        "Put Score": round(clamp(put_score), 1),
        "Category": category,
        "Action": action,
    }


def market_pulse(rows: pd.DataFrame) -> dict:
    if rows is None or rows.empty:
        return {}

    call_count = int((rows["Category"] == "CALL").sum())
    put_count = int((rows["Category"] == "PUT").sum())
    money_in = safe_float(rows["Money In"].mean(), 50.0)
    money_out = safe_float(rows["Money Out"].mean(), 50.0)
    mtf = safe_float(rows["MTF Score"].mean(), 50.0)
    breadth = float((rows["1D %"] > 0).mean() * 100.0) if "1D %" in rows else 50.0

    pulse_score = clamp(
        money_in * 0.30 + mtf * 0.30 + breadth * 0.25
        + clamp(50.0 + (call_count - put_count) * 4.0) * 0.15
    )

    if pulse_score >= 62:
        regime = "Bullish"
    elif pulse_score <= 40:
        regime = "Bearish"
    else:
        regime = "Choppy / Mixed"

    risk = clamp(
        rows["Sell-off Risk"].mean() * 0.55
        + rows["Pullback Risk"].mean() * 0.30
        + (100.0 - breadth) * 0.15
    )
    return {
        "Market Pulse": round(pulse_score, 1),
        "Regime": regime,
        "Risk Level": round(risk, 1),
        "Breadth Up %": round(breadth, 1),
        "Average Money In": round(money_in, 1),
        "Average Money Out": round(money_out, 1),
        "Call Candidates": call_count,
        "Put Candidates": put_count,
    }


def flow_alert(previous: dict | None, current: dict) -> str:
    if not previous or not current:
        return ""
    old_net = safe_float(previous.get("Net Flow"), 0.0)
    new_net = safe_float(current.get("Net Flow"), 0.0)
    old_status = previous.get("Flow Status", "")
    new_status = current.get("Flow Status", "")

    if old_net >= 10 and new_net <= -10:
        return "FLOW REVERSAL: Money In → Money Out"
    if old_net <= -10 and new_net >= 10:
        return "FLOW REVERSAL: Money Out → Money In"
    if old_status != new_status:
        return f"Flow status changed: {old_status} → {new_status}"
    return ""
