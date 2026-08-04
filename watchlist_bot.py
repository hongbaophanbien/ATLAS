from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from core import safe_float


CALL_MIN_SCORE = 68.0
PUT_MIN_SCORE = 68.0
MIN_EDGE = 10.0


def _event(kind: str, ticker: str, title: str, detail: str) -> dict:
    return {
        "kind": kind,
        "ticker": ticker,
        "title": title,
        "detail": detail,
        "time": datetime.now().strftime("%H:%M"),
    }


def _confidence(
    primary_score: float,
    opposing_score: float,
    flow_score: float,
    trend_score: float,
    risk_quality: float,
) -> float:
    edge = max(0.0, primary_score - opposing_score)
    value = (
        primary_score * 0.38
        + flow_score * 0.23
        + trend_score * 0.18
        + risk_quality * 0.13
        + min(100.0, 50.0 + edge * 2.0) * 0.08
    )
    return round(max(0.0, min(100.0, value)), 1)


def build_signal_tables(scan: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Return only high-confidence CALL and PUT candidates.

    Ambiguous, extended, conflicting, and weak signals are intentionally hidden.
    A ticker can appear in at most one table.
    """
    call_rows: list[dict] = []
    put_rows: list[dict] = []

    if scan is None or scan.empty:
        return pd.DataFrame(), pd.DataFrame()

    for _, row in scan.iterrows():
        ticker = str(row.get("Ticker", "")).strip().upper()
        if not ticker:
            continue

        price = safe_float(row.get("Price"), np.nan)
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
        category = str(row.get("Category", "")).upper()

        buy_low = safe_float(row.get("Buy Zone Low"), np.nan)
        buy_high = safe_float(row.get("Buy Zone High"), np.nan)
        chase = safe_float(row.get("Chase Limit"), np.nan)
        stop = safe_float(row.get("Stop"), np.nan)
        tp1 = safe_float(row.get("Sell Zone 1"), np.nan)
        tp2 = safe_float(row.get("Sell Zone 2"), np.nan)

        call_edge = call_score - put_score
        put_edge = put_score - call_score

        call_gate = all([
            call_score >= CALL_MIN_SCORE,
            call_edge >= MIN_EDGE,
            money_in >= 62.0,
            net_flow >= 8.0,
            mtf >= 58.0,
            trade >= 58.0,
            pullback <= 66.0,
            selloff <= 58.0,
            rsi <= 74.0,
            category in {"CALL", "WAIT", ""},
        ])

        put_gate = all([
            put_score >= PUT_MIN_SCORE,
            put_edge >= MIN_EDGE,
            money_out >= 62.0,
            net_flow <= -8.0,
            mtf <= 46.0,
            selloff >= 62.0,
            rsi >= 26.0,
            category in {"PUT", "WAIT", ""},
        ])

        if call_gate and put_gate:
            if call_edge > put_edge:
                put_gate = False
            else:
                call_gate = False

        if call_gate:
            confidence = _confidence(
                call_score,
                put_score,
                money_in,
                mtf,
                100.0 - pullback,
            )
            reasons = []
            if money_in >= 72:
                reasons.append("Money In mạnh")
            if mtf >= 68:
                reasons.append("đa khung bullish")
            if net_flow >= 20:
                reasons.append("Net Flow cao")
            if pullback <= 48:
                reasons.append("entry chưa quá nóng")
            if not reasons:
                reasons.append("tín hiệu đồng thuận")

            call_rows.append({
                "Ticker": ticker,
                "Price": price,
                "Signal": "CALL",
                "Confidence": confidence,
                "Call Score": round(call_score, 1),
                "Money In": round(money_in, 1),
                "Net Flow": round(net_flow, 1),
                "Trend": round(mtf, 1),
                "Pullback Risk": round(pullback, 1),
                "Entry Low": buy_low,
                "Entry High": buy_high,
                "Do Not Chase": chase,
                "Stop": stop,
                "TP1": tp1,
                "TP2": tp2,
                "Reason": ", ".join(reasons),
            })

        elif put_gate:
            confidence = _confidence(
                put_score,
                call_score,
                money_out,
                100.0 - mtf,
                selloff,
            )
            reasons = []
            if money_out >= 72:
                reasons.append("Money Out mạnh")
            if mtf <= 35:
                reasons.append("đa khung bearish")
            if net_flow <= -20:
                reasons.append("Net Flow âm mạnh")
            if selloff >= 75:
                reasons.append("sell-off risk cao")
            if not reasons:
                reasons.append("tín hiệu đồng thuận")

            put_rows.append({
                "Ticker": ticker,
                "Price": price,
                "Signal": "PUT",
                "Confidence": confidence,
                "Put Score": round(put_score, 1),
                "Money Out": round(money_out, 1),
                "Net Flow": round(net_flow, 1),
                "Trend": round(mtf, 1),
                "Sell-off Risk": round(selloff, 1),
                "Breakdown Level": buy_low,
                "Invalidation": buy_high,
                "Stop": stop,
                "TP1": tp1,
                "TP2": tp2,
                "Reason": ", ".join(reasons),
            })

    call_df = pd.DataFrame(call_rows)
    put_df = pd.DataFrame(put_rows)

    if not call_df.empty:
        call_df = call_df.sort_values(
            ["Confidence", "Call Score", "Net Flow"],
            ascending=False,
        ).reset_index(drop=True)

    if not put_df.empty:
        put_df = put_df.sort_values(
            ["Confidence", "Put Score", "Net Flow"],
            ascending=[False, False, True],
        ).reset_index(drop=True)

    return call_df, put_df



def _missing_call_conditions(row: pd.Series) -> list[str]:
    missing = []
    call_score = safe_float(row.get("Call Score"), 50)
    put_score = safe_float(row.get("Put Score"), 50)
    money_in = safe_float(row.get("Money In"), 50)
    net_flow = safe_float(row.get("Net Flow"), 0)
    mtf = safe_float(row.get("MTF Score"), 50)
    pullback = safe_float(row.get("Pullback Risk"), 50)
    selloff = safe_float(row.get("Sell-off Risk"), 50)
    if call_score < 68: missing.append("Call Score < 68")
    if call_score - put_score < 8: missing.append("CALL chưa vượt PUT 8 điểm")
    if money_in < 58: missing.append("Money In < 58")
    if net_flow < 5: missing.append("Net Flow chưa dương rõ")
    if mtf < 55: missing.append("MTF chưa bullish")
    if pullback > 68: missing.append("Pullback risk quá cao")
    if selloff > 60: missing.append("Sell-off risk còn cao")
    return missing


def _missing_put_conditions(row: pd.Series) -> list[str]:
    missing = []
    call_score = safe_float(row.get("Call Score"), 50)
    put_score = safe_float(row.get("Put Score"), 50)
    money_out = safe_float(row.get("Money Out"), 50)
    net_flow = safe_float(row.get("Net Flow"), 0)
    mtf = safe_float(row.get("MTF Score"), 50)
    selloff = safe_float(row.get("Sell-off Risk"), 50)
    rsi = safe_float(row.get("RSI14"), 50)
    if put_score < 65: missing.append("Put Score < 65")
    if put_score - call_score < 7: missing.append("PUT chưa vượt CALL 7 điểm")
    if money_out < 58: missing.append("Money Out < 58")
    if net_flow > -5: missing.append("Net Flow chưa âm rõ")
    if mtf > 52: missing.append("MTF chưa bearish")
    if selloff < 55: missing.append("Sell-off risk < 55")
    if rsi < 25: missing.append("Đã quá bán, PUT dễ muộn")
    return missing


def build_signal_watch(scan: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Near-miss candidates. These are WATCH, not trade recommendations."""
    if scan is None or scan.empty:
        return pd.DataFrame(), pd.DataFrame()

    call_rows, put_rows = [], []
    for _, row in scan.iterrows():
        ticker = str(row.get("Ticker", "")).upper()
        if not ticker:
            continue

        call_score = safe_float(row.get("Call Score"), 50)
        put_score = safe_float(row.get("Put Score"), 50)
        money_in = safe_float(row.get("Money In"), 50)
        money_out = safe_float(row.get("Money Out"), 50)
        net_flow = safe_float(row.get("Net Flow"), 0)
        mtf = safe_float(row.get("MTF Score"), 50)
        selloff = safe_float(row.get("Sell-off Risk"), 50)

        call_missing = _missing_call_conditions(row)
        put_missing = _missing_put_conditions(row)

        if (
            call_score >= 62 and call_score > put_score
            and money_in >= 52 and net_flow >= -3
            and 1 <= len(call_missing) <= 3
        ):
            call_rows.append({
                "Ticker": ticker,
                "Price": safe_float(row.get("Price"), np.nan),
                "Call Score": round(call_score, 1),
                "Money In": round(money_in, 1),
                "Net Flow": round(net_flow, 1),
                "MTF": round(mtf, 1),
                "Pullback Risk": round(safe_float(row.get("Pullback Risk"), 50), 1),
                "Điều kiện còn thiếu": "; ".join(call_missing),
                "Action": "CHỜ TRIGGER",
            })

        if (
            put_score >= 62 and put_score > call_score
            and money_out >= 52 and net_flow <= 3
            and selloff >= 48
            and 1 <= len(put_missing) <= 3
        ):
            put_rows.append({
                "Ticker": ticker,
                "Price": safe_float(row.get("Price"), np.nan),
                "Put Score": round(put_score, 1),
                "Money Out": round(money_out, 1),
                "Net Flow": round(net_flow, 1),
                "MTF": round(mtf, 1),
                "Sell-off Risk": round(selloff, 1),
                "Điều kiện còn thiếu": "; ".join(put_missing),
                "Action": "CHỜ BREAKDOWN",
            })

    call_watch = pd.DataFrame(call_rows)
    put_watch = pd.DataFrame(put_rows)
    if not call_watch.empty:
        call_watch = call_watch.sort_values(
            ["Call Score", "Net Flow"], ascending=False
        ).head(12).reset_index(drop=True)
    if not put_watch.empty:
        put_watch = put_watch.sort_values(
            ["Put Score", "Net Flow"], ascending=[False, True]
        ).head(12).reset_index(drop=True)
    return call_watch, put_watch


def signal_methodology_text() -> str:
    return (
        "CALL/PUT Score là điểm mô hình suy ra từ giá, volume, đa khung, "
        "Money In/Out proxy, Net Flow proxy, pullback/sell-off risk và sector. "
        "Đây KHÔNG phải dữ liệu xác nhận người thật đang BUY TO OPEN option "
        "trên Robinhood và không chứng minh giao dịch của quỹ/cá mập."
    )

def build_bot_alerts(scan: pd.DataFrame, rotation: pd.DataFrame | None = None) -> list[dict]:
    call_df, put_df = build_signal_tables(scan)
    alerts: list[dict] = []

    if rotation is not None and not rotation.empty:
        strongest = rotation.iloc[0]
        weakest = rotation.iloc[-1]
        if safe_float(strongest.get("Rotation")) >= 8:
            alerts.append(_event(
                "good",
                "SECTOR",
                f"Rotation BOT — {strongest['Theme']}",
                f"Dòng tiền đang vào {strongest['Theme']}; leaders: {strongest['Leaders']}.",
            ))
        if safe_float(weakest.get("Rotation")) <= -8:
            alerts.append(_event(
                "bad",
                "SECTOR",
                f"Rotation BOT — rời {weakest['Theme']}",
                f"Nhóm yếu nhất là {weakest['Theme']}; laggards: {weakest['Laggards']}.",
            ))

    for _, row in call_df.head(5).iterrows():
        alerts.append(_event(
            "good",
            row["Ticker"],
            f"{row['Ticker']} — HIGH-CONFIDENCE CALL",
            f"Confidence {row['Confidence']:.0f}%. Entry "
            f"${row['Entry Low']:.2f}–${row['Entry High']:.2f}; "
            f"không chase trên ${row['Do Not Chase']:.2f}.",
        ))

    for _, row in put_df.head(5).iterrows():
        alerts.append(_event(
            "bad",
            row["Ticker"],
            f"{row['Ticker']} — HIGH-CONFIDENCE PUT",
            f"Confidence {row['Confidence']:.0f}%. Money Out "
            f"{row['Money Out']:.0f}; Sell-off Risk {row['Sell-off Risk']:.0f}%.",
        ))

    return alerts[:12]


def bot_summary(alerts: list[dict]) -> dict:
    return {
        "Total": len(alerts),
        "Bullish": sum(1 for item in alerts if item["kind"] == "good"),
        "Warnings": sum(1 for item in alerts if item["kind"] == "warning"),
        "Bearish": sum(1 for item in alerts if item["kind"] == "bad"),
    }
