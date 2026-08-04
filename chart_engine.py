from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core import atr, ema, ensure_ohlcv, resample_ohlcv, rsi, safe_float


def select_chart_frame(
    daily: pd.DataFrame,
    hourly: pd.DataFrame,
    timeframe: str,
) -> tuple[pd.DataFrame, str]:
    daily = ensure_ohlcv(daily)
    hourly = ensure_ohlcv(hourly)

    if timeframe == "1M":
        return resample_ohlcv(daily, "ME"), "Monthly"
    if timeframe == "1W":
        return resample_ohlcv(daily, "W-FRI"), "Weekly"
    if timeframe == "1D":
        return daily, "Daily"
    if timeframe == "4H":
        return resample_ohlcv(hourly, "4h", offset="9h30min"), "4-hour"
    if timeframe == "2H":
        return resample_ohlcv(hourly, "2h", offset="9h30min"), "2-hour"
    return hourly, "1-hour"


def session_vwap(df: pd.DataFrame) -> pd.Series:
    data = ensure_ohlcv(df)
    if data.empty:
        return pd.Series(dtype=float)

    typical = (data["High"] + data["Low"] + data["Close"]) / 3.0
    volume = data["Volume"].fillna(0.0)
    if isinstance(data.index, pd.DatetimeIndex):
        dates = pd.Series(data.index.date, index=data.index)
        cumulative_pv = (typical * volume).groupby(dates).cumsum()
        cumulative_volume = volume.groupby(dates).cumsum().replace(0, np.nan)
        return cumulative_pv / cumulative_volume

    cumulative_volume = volume.cumsum().replace(0, np.nan)
    return (typical * volume).cumsum() / cumulative_volume


def _cluster_levels(values: Iterable[float], tolerance: float) -> list[float]:
    clean = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not clean:
        return []

    clusters: list[list[float]] = [[clean[0]]]
    for value in clean[1:]:
        center = float(np.mean(clusters[-1]))
        if abs(value - center) <= tolerance:
            clusters[-1].append(value)
        else:
            clusters.append([value])
    return [float(np.mean(cluster)) for cluster in clusters]


def automatic_levels(
    df: pd.DataFrame,
    lookback: int = 180,
    pivot_window: int = 4,
) -> dict[str, list[float]]:
    data = ensure_ohlcv(df).tail(lookback)
    if len(data) < 20:
        return {"supports": [], "resistances": []}

    high = data["High"]
    low = data["Low"]
    span = pivot_window * 2 + 1
    pivot_high = high[high.eq(high.rolling(span, center=True).max())]
    pivot_low = low[low.eq(low.rolling(span, center=True).min())]

    atr_series = atr(data, 14).dropna()
    tolerance = safe_float(atr_series.iloc[-1], safe_float(data["Close"].iloc[-1]) * 0.02) * 0.55
    tolerance = max(tolerance, safe_float(data["Close"].iloc[-1]) * 0.0025)

    resistance_candidates = _cluster_levels(pivot_high.tail(24).tolist(), tolerance)
    support_candidates = _cluster_levels(pivot_low.tail(24).tolist(), tolerance)
    price = safe_float(data["Close"].iloc[-1])

    supports = sorted([level for level in support_candidates if level < price], reverse=True)[:3]
    resistances = sorted([level for level in resistance_candidates if level > price])[:3]

    # Add recent range boundaries if pivot detection is sparse.
    recent = data.tail(min(60, len(data)))
    if len(supports) < 2:
        for candidate in [recent["Low"].tail(20).min(), recent["Low"].tail(50).min()]:
            value = safe_float(candidate)
            if value < price and all(abs(value - x) > tolerance for x in supports):
                supports.append(value)
    if len(resistances) < 2:
        for candidate in [recent["High"].tail(20).max(), recent["High"].tail(50).max()]:
            value = safe_float(candidate)
            if value > price and all(abs(value - x) > tolerance for x in resistances):
                resistances.append(value)

    return {
        "supports": sorted(supports, reverse=True)[:3],
        "resistances": sorted(resistances)[:3],
    }


def make_analysis_chart(
    df: pd.DataFrame,
    title: str,
    *,
    bars: int = 180,
    show_vwap: bool = False,
) -> go.Figure:
    data = ensure_ohlcv(df).tail(bars)
    if data.empty:
        return go.Figure()

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.025,
        row_heights=[0.66, 0.18, 0.16],
    )

    fig.add_trace(
        go.Candlestick(
            x=data.index,
            open=data["Open"],
            high=data["High"],
            low=data["Low"],
            close=data["Close"],
            name="Price",
        ),
        row=1,
        col=1,
    )

    for length in (9, 21, 50):
        fig.add_trace(
            go.Scatter(
                x=data.index,
                y=ema(data["Close"], length),
                mode="lines",
                name=f"EMA{length}",
                line={"width": 1.35},
            ),
            row=1,
            col=1,
        )

    if show_vwap:
        vwap = session_vwap(data)
        if not vwap.dropna().empty:
            fig.add_trace(
                go.Scatter(
                    x=data.index,
                    y=vwap,
                    mode="lines",
                    name="VWAP",
                    line={"width": 1.4, "dash": "dot"},
                ),
                row=1,
                col=1,
            )

    levels = automatic_levels(data)
    for index, level in enumerate(levels["supports"], start=1):
        fig.add_hline(
            y=level,
            line_dash="dash",
            line_width=1,
            annotation_text=f"S{index} {level:.2f}",
            annotation_position="bottom right",
            row=1,
            col=1,
        )
    for index, level in enumerate(levels["resistances"], start=1):
        fig.add_hline(
            y=level,
            line_dash="dot",
            line_width=1,
            annotation_text=f"R{index} {level:.2f}",
            annotation_position="top right",
            row=1,
            col=1,
        )

    fig.add_trace(
        go.Bar(x=data.index, y=data["Volume"], name="Volume"),
        row=2,
        col=1,
    )

    rsi14 = rsi(data["Close"], 14)
    fig.add_trace(
        go.Scatter(x=data.index, y=rsi14, mode="lines", name="RSI14", line={"width": 1.4}),
        row=3,
        col=1,
    )
    fig.add_hline(y=70, line_dash="dash", line_width=1, row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_width=1, row=3, col=1)

    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Volume", row=2, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
    fig.update_xaxes(rangeslider_visible=False)
    fig.update_layout(
        title=title,
        height=760,
        margin={"l": 10, "r": 10, "t": 55, "b": 10},
        hovermode="x unified",
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "left", "x": 0},
    )
    return fig


def _status(value: float, green: float, yellow: float, *, lower_is_better: bool = False) -> str:
    if not math.isfinite(float(value)):
        return "⚪"
    if lower_is_better:
        if value <= green:
            return "✅"
        if value <= yellow:
            return "⚠️"
        return "⛔"
    if value >= green:
        return "✅"
    if value >= yellow:
        return "⚠️"
    return "⛔"


def confirmation_checklist(row: dict, mtf_report: pd.DataFrame) -> pd.DataFrame:
    if not row:
        return pd.DataFrame()

    tf_map = {}
    if mtf_report is not None and not mtf_report.empty:
        for _, tf_row in mtf_report.iterrows():
            tf_map[str(tf_row.get("timeframe"))] = tf_row

    tf4 = safe_float(tf_map.get("4H", {}).get("trend_score") if "4H" in tf_map else np.nan)
    tf2 = safe_float(tf_map.get("2H", {}).get("trend_score") if "2H" in tf_map else np.nan)
    extension = abs(safe_float(row.get("Extension ATR"), np.nan))

    records = [
        {
            "Trạng thái": _status(safe_float(row.get("Sector Flow"), np.nan), 58, 48),
            "Kiểm tra": "Dòng tiền ngành",
            "Giá trị": f"{safe_float(row.get('Sector Flow'), 0):.1f}",
            "Ý nghĩa": "Sector mạnh giúp breakout có xác suất giữ giá tốt hơn.",
        },
        {
            "Trạng thái": _status(safe_float(row.get("MTF Score"), np.nan), 65, 52),
            "Kiểm tra": "Đồng thuận đa khung",
            "Giá trị": f"{safe_float(row.get('MTF Score'), 0):.1f}",
            "Ý nghĩa": "Ưu tiên khi 1W/1D và khung timing không xung đột.",
        },
        {
            "Trạng thái": _status(tf4, 62, 48),
            "Kiểm tra": "Xu hướng 4H",
            "Giá trị": "N/A" if not math.isfinite(tf4) else f"{tf4:.1f}",
            "Ý nghĩa": "4H dùng để phân biệt pullback khỏe với xu hướng đang gãy.",
        },
        {
            "Trạng thái": _status(tf2, 62, 48),
            "Kiểm tra": "Trigger 2H",
            "Giá trị": "N/A" if not math.isfinite(tf2) else f"{tf2:.1f}",
            "Ý nghĩa": "2H phù hợp để xác nhận điểm vào swing ngắn.",
        },
        {
            "Trạng thái": _status(safe_float(row.get("Smart Money Score"), np.nan), 58, 46),
            "Kiểm tra": "Price-volume flow",
            "Giá trị": f"{safe_float(row.get('Smart Money Score'), 0):.1f}",
            "Ý nghĩa": "CMF/MFI/OBV và accumulation phải hỗ trợ hướng giá.",
        },
        {
            "Trạng thái": _status(safe_float(row.get("Pullback Risk"), np.nan), 52, 68, lower_is_better=True),
            "Kiểm tra": "Rủi ro pullback",
            "Giá trị": f"{safe_float(row.get('Pullback Risk'), 0):.1f}",
            "Ý nghĩa": "Điểm cao nghĩa là giá đã kéo quá xa hoặc có dấu hiệu exhaustion.",
        },
        {
            "Trạng thái": _status(extension, 1.35, 2.35, lower_is_better=True),
            "Kiểm tra": "Độ xa EMA21 theo ATR",
            "Giá trị": "N/A" if not math.isfinite(extension) else f"{extension:.2f} ATR",
            "Ý nghĩa": "Call ngắn hạn rủi ro hơn khi giá quá xa hỗ trợ động.",
        },
        {
            "Trạng thái": _status(safe_float(row.get("RVOL20"), np.nan), 1.25, 0.85),
            "Kiểm tra": "Relative volume",
            "Giá trị": f"{safe_float(row.get('RVOL20'), 0):.2f}",
            "Ý nghĩa": "Volume xác nhận giúp phân biệt breakout thật và nhịp kéo yếu.",
        },
    ]
    return pd.DataFrame(records)


def decision_summary(row: dict, checklist: pd.DataFrame) -> dict[str, str]:
    if not row or checklist is None or checklist.empty:
        return {
            "decision": "CHƯA CÓ DỮ LIỆU",
            "vehicle": "Đứng ngoài",
            "reason": "Chưa đủ dữ liệu để xác nhận.",
        }

    statuses = checklist["Trạng thái"].tolist()
    green = statuses.count("✅")
    red = statuses.count("⛔")
    pullback = safe_float(row.get("Pullback Risk"), 100)
    trade_score = safe_float(row.get("Trade Score"), 0)

    if pullback >= 72:
        decision = "CHỜ PULLBACK / TẠO BASE"
        vehicle = "Không chase call ngắn hạn"
        reason = "Giá đang quá nóng; lợi thế risk/reward không còn tốt."
    elif red >= 3 or trade_score < 40:
        decision = "TRÁNH / ĐỨNG NGOÀI"
        vehicle = "Không mở vị thế mới"
        reason = "Có quá nhiều điều kiện chống lại setup."
    elif trade_score >= 60 and green >= 5 and red <= 1:
        decision = "ĐỦ ĐIỀU KIỆN THEO DÕI ENTRY"
        vehicle = str(row.get("Preferred Vehicle", "Shares hoặc call có DTE buffer"))
        reason = "Dòng tiền, đa khung và độ nóng tương đối đồng thuận."
    else:
        decision = "WATCHLIST – CHỜ TRIGGER"
        vehicle = "Shares nhỏ hoặc chờ breakout/reclaim trước khi dùng call"
        reason = "Setup có điểm tốt nhưng chưa đủ đồng thuận để vào ngay."

    return {"decision": decision, "vehicle": vehicle, "reason": reason}
