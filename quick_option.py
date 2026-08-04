from __future__ import annotations

import math
from datetime import date, datetime

import numpy as np
import pandas as pd
import yfinance as yf


def _cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _greeks(spot: float, strike: float, days: int, iv: float, side: str, rate: float = 0.045):
    if min(spot, strike, days, iv) <= 0:
        return np.nan, np.nan
    t = days / 365.0
    sigma = max(iv, 0.01)
    d1 = (math.log(spot / strike) + (rate + sigma * sigma / 2.0) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    if side == "CALL":
        delta = _cdf(d1)
        theta_y = -(spot * _pdf(d1) * sigma) / (2 * math.sqrt(t)) - rate * strike * math.exp(-rate*t) * _cdf(d2)
    else:
        delta = _cdf(d1) - 1
        theta_y = -(spot * _pdf(d1) * sigma) / (2 * math.sqrt(t)) + rate * strike * math.exp(-rate*t) * _cdf(-d2)
    return delta, theta_y / 365.0


def dte_range(horizon: str):
    return {
        "Day trade": (7, 21),
        "Ngày mai": (14, 35),
        "Swing 3–5 ngày": (21, 55),
        "Swing 1–2 tuần": (35, 90),
    }.get(horizon, (21, 55))


def _expirations(symbol: str, horizon: str):
    low, high = dte_range(horizon)
    today = date.today()
    result = []
    try:
        expirations = yf.Ticker(symbol).options
    except Exception:
        return []
    for exp in expirations:
        try:
            dte = (datetime.strptime(exp, "%Y-%m-%d").date() - today).days
        except Exception:
            continue
        if low <= dte <= high:
            result.append((dte, exp))
    if not result:
        for exp in expirations:
            try:
                dte = (datetime.strptime(exp, "%Y-%m-%d").date() - today).days
            except Exception:
                continue
            if dte > 0:
                result.append((abs(dte-low), exp))
    return [x[1] for x in sorted(result)[:3]]


def _normalize_signal(value: str) -> str:
    text = str(value or "").strip().upper()
    if "CALL" in text:
        return "CALL"
    if "PUT" in text:
        return "PUT"
    return ""

def best_contract(symbol: str, signal: str, spot: float, horizon: str, budget: float, er_date=None, lotto_mode=False) -> dict:
    signal = _normalize_signal(signal)
    if signal not in {"CALL", "PUT"}:
        return {}
    rows = []
    today = date.today()
    ticker = yf.Ticker(symbol)

    for expiration in _expirations(symbol, horizon):
        if er_date and not lotto_mode:
            try:
                if datetime.strptime(expiration, '%Y-%m-%d').date() >= datetime.strptime(er_date, '%Y-%m-%d').date():
                    continue
            except Exception:
                pass
        try:
            chain = ticker.option_chain(expiration)
            frame = chain.calls if signal == "CALL" else chain.puts
            dte = (datetime.strptime(expiration, "%Y-%m-%d").date() - today).days
        except Exception:
            continue

        for _, r in frame.iterrows():
            strike = float(r.get("strike", np.nan))
            bid = float(r.get("bid", np.nan))
            ask = float(r.get("ask", np.nan))
            last = float(r.get("lastPrice", np.nan))
            iv = float(r.get("impliedVolatility", np.nan))
            volume = float(r.get("volume", 0) or 0)
            oi = float(r.get("openInterest", 0) or 0)

            if not np.isfinite(strike):
                continue
            mid = (bid + ask)/2 if np.isfinite(bid) and np.isfinite(ask) and ask > 0 else last
            if not np.isfinite(mid) or mid <= 0:
                continue
            premium = mid * 100
            if premium > budget:
                continue

            delta, theta = _greeks(spot, strike, dte, iv, signal)
            abs_delta = abs(delta) if np.isfinite(delta) else 0
            spread = ((ask-bid)/mid*100) if mid > 0 and np.isfinite(ask) and np.isfinite(bid) else 99

            # Calls must be at/above spot; puts must be at/below spot.
            # Allow a very small ATM tolerance to avoid losing the closest liquid strike.
            if signal == "CALL" and strike < spot * 0.997:
                continue
            if signal == "PUT" and strike > spot * 1.003:
                continue

            # User preference: liquid ATM-to-slightly-OTM contracts, not ITM.
            target_delta = 0.50
            score = (
                max(0, 100 - abs(abs_delta-target_delta)*180) * 0.38
                + min(100, math.log10(max(volume+oi,1))*30) * 0.30
                + max(0, 100-spread*3) * 0.20
                + max(0, 100-abs(abs(theta)-0.20)*180) * 0.12
            )

            if oi < 50 or spread > 22:
                continue

            rows.append({
                "Ticker": symbol,
                "Signal": signal,
                "Expiration": expiration,
                "Stock Price": spot,
                "Strike": strike,
                "Bid": bid,
                "Ask": ask,
                "Premium": premium,
                "Delta": delta,
                "Theta/day": theta if np.isfinite(theta) else np.nan,
                "IV": iv*100 if np.isfinite(iv) else np.nan,
                "Volume": volume,
                "OI": oi,
                "Spread": spread,
                "Contract Score": score,
            })

    if not rows:
        return {}

    best = max(rows, key=lambda x: x["Contract Score"])
    best["Contract Score"] = round(best["Contract Score"], 1)
    return best


def shortlist_contracts(signals: pd.DataFrame, horizon: str, budget: float, limit: int = 5, lotto_mode: bool = False) -> pd.DataFrame:
    output = []
    if signals is None or signals.empty:
        return pd.DataFrame()
    for _, row in signals.head(limit).iterrows():
        contract = best_contract(
            str(row["Ticker"]),
            _normalize_signal(
                row.get("Signal", row.get("Decision", row.get("Action", "")))
            ),
            float(row["Price"]),
            horizon,
            budget,
            er_date=row.get('ER Date'),
            lotto_mode=lotto_mode,
        )
        if contract:
            confidence_value = row.get("Confidence", row.get("Opportunity Score", row.get("Trade Score", 0.0)))
            contract["Stock Confidence"] = float(confidence_value or 0.0)
            contract["Stock Price"] = float(row["Price"])
            output.append(contract)
    return pd.DataFrame(output)
