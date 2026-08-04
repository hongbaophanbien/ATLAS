from __future__ import annotations

import math
from datetime import date, datetime
from typing import Iterable

import numpy as np
import pandas as pd
import yfinance as yf

from quick_option import _greeks


def _safe(value, default=0.0) -> float:
    try:
        value = float(value)
        return value if math.isfinite(value) else float(default)
    except Exception:
        return float(default)


def _clamp(value, low=0.0, high=100.0) -> float:
    return max(low, min(high, float(value)))


def _fmt_contract(symbol: str, expiry: str, strike: float, side: str) -> str:
    return f"{symbol} {expiry} {strike:g}{'C' if side == 'CALL' else 'P'}"


def _chart_bias(row: pd.Series) -> str:
    call_score = _safe(row.get("Call Score"), 50.0)
    put_score = _safe(row.get("Put Score"), 50.0)
    mtf = _safe(row.get("MTF Score"), 50.0)
    money_in = _safe(row.get("Money In"), 50.0)
    money_out = _safe(row.get("Money Out"), 50.0)
    overnight_pct = _safe(row.get("Overnight %"), 0.0)

    if call_score >= 62 and call_score >= put_score + 8 and mtf >= 55 and money_in >= money_out and overnight_pct > -1.0:
        return "BULLISH"
    if put_score >= 62 and put_score >= call_score + 8 and mtf <= 48 and money_out >= money_in and overnight_pct < 1.0:
        return "BEARISH"
    return "MIXED"


def _technical_alignment(side: str, bias: str) -> tuple[str, float]:
    if side == "CALL" and bias == "BULLISH":
        return "ALIGNED", 25.0
    if side == "PUT" and bias == "BEARISH":
        return "ALIGNED", 25.0
    if bias == "MIXED":
        return "UNCONFIRMED", 10.0
    return "CONFLICT / HEDGE RISK", 0.0


def _interpretation(side: str, alignment: str, vol_oi: float, spread: float) -> str:
    if alignment == "ALIGNED":
        if vol_oi >= 1.0 and spread <= 12:
            return f"{side} activity mạnh, đồng thuận chart — chờ trigger"
        return f"{side} activity đồng thuận chart nhưng chưa đủ bất thường"
    if alignment == "CONFLICT / HEDGE RISK":
        return "Flow ngược chart — có thể hedge/closing/spread; không follow mù"
    return "Chart chưa xác nhận — chỉ đưa vào watch"


def _trigger_text(row: pd.Series, side: str) -> str:
    price = _safe(row.get("Price"), 0.0)
    if side == "CALL":
        trigger = _safe(
            row.get("Buy Zone High",
            row.get("Entry High",
            row.get("Chase Limit", price))),
            price,
        )
        return f"CALL khi giá giữ/vượt ${trigger:.2f}"
    stop = _safe(row.get("Stop"), price)
    trigger = _safe(row.get("Buy Zone Low", row.get("Entry Low", stop)), stop)
    return f"PUT khi giá mất/retest dưới ${trigger:.2f}"


def _invalidation_text(row: pd.Series, side: str) -> str:
    price = _safe(row.get("Price"), 0.0)
    stop = _safe(row.get("Stop"), price)
    if side == "CALL":
        return f"Hủy CALL nếu mất ${stop:.2f}"
    invalid = _safe(row.get("Buy Zone High", row.get("Chase Limit", price)), price)
    return f"Hủy PUT nếu reclaim ${invalid:.2f}"


def _expirations(ticker: yf.Ticker, min_dte: int = 7, max_dte: int = 120, limit: int = 3):
    today = date.today()
    found = []
    try:
        expirations = ticker.options
    except Exception:
        return []

    for expiry in expirations:
        try:
            dte = (datetime.strptime(expiry, "%Y-%m-%d").date() - today).days
        except Exception:
            continue
        if min_dte <= dte <= max_dte:
            found.append((dte, expiry))

    return [expiry for _, expiry in sorted(found)[:limit]]


def scan_symbol_flow(
    row: pd.Series,
    max_expirations: int = 3,
    contracts_per_side: int = 2,
) -> list[dict]:
    symbol = str(row.get("Ticker", "")).strip().upper()
    spot = _safe(row.get("Price"), 0.0)
    if not symbol or spot <= 0:
        return []

    bias = _chart_bias(row)
    ticker = yf.Ticker(symbol)
    output: list[dict] = []
    today = date.today()

    for expiry in _expirations(ticker, limit=max_expirations):
        try:
            chain = ticker.option_chain(expiry)
            dte = (datetime.strptime(expiry, "%Y-%m-%d").date() - today).days
        except Exception:
            continue

        for side, frame in (("CALL", chain.calls), ("PUT", chain.puts)):
            candidates = []

            for _, contract in frame.iterrows():
                strike = _safe(contract.get("strike"), np.nan)
                bid = _safe(contract.get("bid"), np.nan)
                ask = _safe(contract.get("ask"), np.nan)
                last = _safe(contract.get("lastPrice"), np.nan)
                volume = _safe(contract.get("volume"), 0.0)
                oi = _safe(contract.get("openInterest"), 0.0)
                iv = _safe(contract.get("impliedVolatility"), 0.0)

                if not math.isfinite(strike) or strike <= 0 or volume <= 0:
                    continue

                if math.isfinite(bid) and math.isfinite(ask) and ask > 0:
                    mid = (bid + ask) / 2.0
                else:
                    mid = last

                if not math.isfinite(mid) or mid <= 0:
                    continue

                spread = ((ask - bid) / mid * 100.0) if (
                    math.isfinite(ask) and math.isfinite(bid) and ask >= bid
                ) else 99.0

                # Volume * midpoint is only a notional proxy. It is not exact
                # executed premium because trades may have occurred at many prices.
                premium_proxy = volume * mid * 100.0
                vol_oi = volume / max(oi, 1.0)
                moneyness = (strike / spot - 1.0) * 100.0
                delta, _theta = _greeks(spot, strike, max(dte, 1), max(iv, 0.01), side)
                abs_delta = abs(_safe(delta, 0.0))

                alignment, alignment_points = _technical_alignment(side, bias)

                premium_points = _clamp(
                    (math.log10(max(premium_proxy, 1.0)) - 3.5) / 3.0 * 25.0,
                    0.0,
                    25.0,
                )
                activity_points = _clamp(vol_oi * 14.0, 0.0, 25.0)
                liquidity_points = _clamp(math.log10(max(oi + volume, 1.0)) * 5.0, 0.0, 15.0)
                spread_points = _clamp(15.0 - spread * 0.8, 0.0, 15.0)
                delta_points = _clamp(10.0 - abs(abs_delta - 0.45) * 20.0, 0.0, 10.0)

                flow_score = _clamp(
                    premium_points
                    + activity_points
                    + liquidity_points
                    + spread_points
                    + delta_points
                    + alignment_points
                )

                # Hard filters remove illiquid far-tail contracts.
                if spread > 35 or oi < 10:
                    continue
                if abs(moneyness) > 35 and abs_delta < 0.12:
                    continue
                if premium_proxy < 25_000:
                    continue

                candidates.append({
                    "Ticker": symbol,
                    "Side": side,
                    "Contract": _fmt_contract(symbol, expiry, strike, side),
                    "Expiration": expiry,
                    "DTE": dte,
                    "Strike": round(strike, 2),
                    "Spot": round(spot, 2),
                    "Moneyness %": round(moneyness, 1),
                    "Volume": int(volume),
                    "OI": int(oi),
                    "Vol/OI": round(vol_oi, 2),
                    "Bid": round(bid, 2) if math.isfinite(bid) else np.nan,
                    "Ask": round(ask, 2) if math.isfinite(ask) else np.nan,
                    "Mid": round(mid, 2),
                    "Spread %": round(spread, 1),
                    "Premium Proxy": round(premium_proxy, 0),
                    "IV %": round(iv * 100.0, 1),
                    "Delta": round(delta, 2) if math.isfinite(_safe(delta, np.nan)) else np.nan,
                    "Execution": "UNKNOWN — no trade tape",
                    "Chart Bias": bias,
                    "Overnight %": row.get("Overnight %", np.nan),
                    "Overnight Bias": row.get("Overnight Bias", "DATA UNAVAILABLE"),
                    "Gap Risk": row.get("Gap Risk", "UNKNOWN"),
                    "Overnight Confirm": row.get("Overnight Confirm", "UNAVAILABLE"),
                    "Alignment": alignment,
                    "Flow Score": round(flow_score, 1),
                    "Interpretation": _interpretation(side, alignment, vol_oi, spread),
                    "Trigger": _trigger_text(row, side),
                    "Invalidation": _invalidation_text(row, side),
                    "Source": "Yahoo option-chain snapshot + ATLAS chart logic",
                })

            candidates.sort(
                key=lambda item: (
                    item["Flow Score"],
                    item["Premium Proxy"],
                    item["Vol/OI"],
                ),
                reverse=True,
            )
            output.extend(candidates[:contracts_per_side])

    return output


def build_flow_radar(
    scan: pd.DataFrame,
    opportunity_frame: pd.DataFrame | None = None,
    max_symbols: int = 12,
) -> pd.DataFrame:
    if scan is None or scan.empty:
        return pd.DataFrame()

    source = opportunity_frame if opportunity_frame is not None and not opportunity_frame.empty else scan
    preferred = []

    for _, row in source.iterrows():
        ticker = str(row.get("Ticker", "")).strip().upper()
        if ticker and ticker not in preferred:
            preferred.append(ticker)
        if len(preferred) >= max_symbols:
            break

    lookup = scan.set_index("Ticker", drop=False)
    rows: list[dict] = []

    for ticker in preferred:
        if ticker not in lookup.index:
            continue
        row = lookup.loc[ticker]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]
        try:
            rows.extend(scan_symbol_flow(row))
        except Exception:
            continue

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    return (
        result.sort_values(
            ["Flow Score", "Premium Proxy", "Vol/OI"],
            ascending=[False, False, False],
        )
        .drop_duplicates(subset=["Contract"])
        .reset_index(drop=True)
    )
