from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from statistics import NormalDist
from typing import Iterable

import numpy as np
import pandas as pd


EPS = 1e-12


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    if value is None or not math.isfinite(float(value)):
        return low
    return max(low, min(high, float(value)))


def safe_float(value, default: float = np.nan) -> float:
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def ensure_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    wanted = ["Open", "High", "Low", "Close", "Volume"]
    if not set(wanted).issubset(out.columns):
        return pd.DataFrame()
    out = out[wanted]
    for col in wanted:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna(subset=["Open", "High", "Low", "Close"])
    out["Volume"] = out["Volume"].fillna(0.0)
    return out.sort_index()


def resample_ohlcv(df: pd.DataFrame, rule: str, *, offset: str | None = None) -> pd.DataFrame:
    out = ensure_ohlcv(df)
    if out.empty:
        return out
    kwargs = {"label": "right", "closed": "right"}
    if offset:
        kwargs["origin"] = "start_day"
        kwargs["offset"] = offset
    return (
        out.resample(rule, **kwargs)
        .agg({"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        .dropna(subset=["Open", "High", "Low", "Close"])
    )


def ema(series: pd.Series, length: int) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").ewm(span=length, adjust=False).mean()


def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    delta = s.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    avg_loss = loss.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(50.0)


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    data = ensure_ohlcv(df)
    if data.empty:
        return pd.Series(dtype=float)
    prev_close = data["Close"].shift(1)
    tr = pd.concat(
        [
            data["High"] - data["Low"],
            (data["High"] - prev_close).abs(),
            (data["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def mfi(df: pd.DataFrame, length: int = 14) -> pd.Series:
    data = ensure_ohlcv(df)
    if data.empty:
        return pd.Series(dtype=float)
    typical = (data["High"] + data["Low"] + data["Close"]) / 3.0
    raw_money = typical * data["Volume"]
    direction = typical.diff()
    positive = raw_money.where(direction > 0, 0.0)
    negative = raw_money.where(direction < 0, 0.0).abs()
    pos_sum = positive.rolling(length, min_periods=length).sum()
    neg_sum = negative.rolling(length, min_periods=length).sum()
    ratio = pos_sum / neg_sum.replace(0, np.nan)
    out = 100 - (100 / (1 + ratio))
    return out.fillna(50.0)


def obv(df: pd.DataFrame) -> pd.Series:
    data = ensure_ohlcv(df)
    if data.empty:
        return pd.Series(dtype=float)
    direction = np.sign(data["Close"].diff()).fillna(0.0)
    return (direction * data["Volume"]).cumsum()


def cmf(df: pd.DataFrame, length: int = 20) -> pd.Series:
    data = ensure_ohlcv(df)
    if data.empty:
        return pd.Series(dtype=float)
    spread = (data["High"] - data["Low"]).replace(0, np.nan)
    multiplier = ((data["Close"] - data["Low"]) - (data["High"] - data["Close"])) / spread
    money_flow_volume = multiplier.fillna(0.0) * data["Volume"]
    return money_flow_volume.rolling(length, min_periods=length).sum() / data["Volume"].rolling(
        length, min_periods=length
    ).sum().replace(0, np.nan)


def macd_hist(series: pd.Series) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    macd = ema(s, 12) - ema(s, 26)
    signal = ema(macd, 9)
    return macd - signal


def rolling_slope(values: pd.Series, length: int = 20) -> float:
    s = pd.to_numeric(values, errors="coerce").dropna().tail(length)
    if len(s) < max(5, length // 2):
        return 0.0
    y = s.to_numpy(dtype=float)
    scale = max(np.nanmean(np.abs(y)), EPS)
    y = y / scale
    x = np.arange(len(y), dtype=float)
    return safe_float(np.polyfit(x, y, 1)[0], 0.0)


def close_location(df: pd.DataFrame) -> pd.Series:
    data = ensure_ohlcv(df)
    spread = (data["High"] - data["Low"]).replace(0, np.nan)
    return ((data["Close"] - data["Low"]) / spread * 100).fillna(50.0)


def _return_pct(series: pd.Series, bars: int) -> float:
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) <= bars:
        return np.nan
    return safe_float((s.iloc[-1] / s.iloc[-1 - bars] - 1.0) * 100)


@dataclass
class TimeframeSnapshot:
    timeframe: str
    bars: int
    price: float
    return_1bar_pct: float
    return_5bar_pct: float
    ema9: float
    ema21: float
    ema50: float
    rsi14: float
    mfi14: float
    cmf20: float
    atr_pct: float
    macd_hist: float
    trend_score: float
    trend: str


def timeframe_snapshot(df: pd.DataFrame, timeframe: str) -> TimeframeSnapshot | None:
    data = ensure_ohlcv(df)
    if len(data) < 22:
        return None

    close = data["Close"]
    ema9_s = ema(close, 9)
    ema21_s = ema(close, 21)
    ema50_s = ema(close, 50)
    rsi_s = rsi(close, 14)
    mfi_s = mfi(data, 14)
    cmf_s = cmf(data, 20)
    atr_s = atr(data, 14)
    macd_s = macd_hist(close)

    price = safe_float(close.iloc[-1])
    e9 = safe_float(ema9_s.iloc[-1])
    e21 = safe_float(ema21_s.iloc[-1])
    e50 = safe_float(ema50_s.iloc[-1]) if len(data) >= 50 else np.nan
    rsi_now = safe_float(rsi_s.iloc[-1], 50.0)
    mfi_now = safe_float(mfi_s.iloc[-1], 50.0)
    cmf_now = safe_float(cmf_s.iloc[-1], 0.0)
    atr_now = safe_float(atr_s.iloc[-1])
    macd_now = safe_float(macd_s.iloc[-1], 0.0)

    score = 0.0
    score += 8 if price > e9 else 0
    score += 13 if price > e21 else 0
    if math.isfinite(e50):
        score += 10 if price > e50 else 0
    else:
        score += 5
    score += 10 if e9 > e21 else 0
    if math.isfinite(e50):
        score += 10 if e21 > e50 else 0
    else:
        score += 5
    score += 10 if rolling_slope(ema21_s, min(12, len(ema21_s))) > 0 else 0

    if 50 <= rsi_now <= 70:
        score += 12
    elif 42 <= rsi_now < 50:
        score += 7
    elif 70 < rsi_now <= 78:
        score += 6
    elif rsi_now < 35:
        score -= 4

    if 50 <= mfi_now <= 80:
        score += 9
    elif 40 <= mfi_now < 50:
        score += 5
    elif mfi_now > 85:
        score += 2

    if cmf_now >= 0.12:
        score += 9
    elif cmf_now > 0:
        score += 5
    elif cmf_now < -0.12:
        score -= 5

    score += 8 if macd_now > 0 else 0
    score += 6 if safe_float(close_location(data).iloc[-1], 50.0) >= 60 else 0
    score += 5 if _return_pct(close, 1) > 0 else 0
    score = clamp(score)

    if score >= 70:
        trend = "Bullish"
    elif score <= 38:
        trend = "Bearish"
    else:
        trend = "Neutral"

    return TimeframeSnapshot(
        timeframe=timeframe,
        bars=len(data),
        price=price,
        return_1bar_pct=_return_pct(close, 1),
        return_5bar_pct=_return_pct(close, 5),
        ema9=e9,
        ema21=e21,
        ema50=e50,
        rsi14=rsi_now,
        mfi14=mfi_now,
        cmf20=cmf_now,
        atr_pct=(atr_now / price * 100) if price > 0 and math.isfinite(atr_now) else np.nan,
        macd_hist=macd_now,
        trend_score=score,
        trend=trend,
    )


def build_timeframes(daily: pd.DataFrame, hourly: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    daily = ensure_ohlcv(daily)
    hourly = ensure_ohlcv(hourly) if hourly is not None else pd.DataFrame()
    frames: dict[str, pd.DataFrame] = {
        "1M": resample_ohlcv(daily, "ME"),
        "1W": resample_ohlcv(daily, "W-FRI"),
        "1D": daily,
    }
    if not hourly.empty:
        frames["4H"] = resample_ohlcv(hourly, "4h", offset="9h30min")
        frames["2H"] = resample_ohlcv(hourly, "2h", offset="9h30min")
    else:
        frames["4H"] = pd.DataFrame()
        frames["2H"] = pd.DataFrame()
    return frames


def multi_timeframe_report(daily: pd.DataFrame, hourly: pd.DataFrame | None = None) -> tuple[pd.DataFrame, float, int]:
    frames = build_timeframes(daily, hourly)
    weights = {"1M": 0.15, "1W": 0.20, "1D": 0.25, "4H": 0.20, "2H": 0.20}
    rows: list[dict] = []
    weighted = 0.0
    used_weight = 0.0
    bullish_count = 0
    for name in ["1M", "1W", "1D", "4H", "2H"]:
        snap = timeframe_snapshot(frames[name], name)
        if snap is None:
            continue
        row = asdict(snap)
        rows.append(row)
        weighted += snap.trend_score * weights[name]
        used_weight += weights[name]
        bullish_count += int(snap.trend == "Bullish")
    total_score = weighted / used_weight if used_weight > 0 else 0.0
    return pd.DataFrame(rows), clamp(total_score), bullish_count


def _percentile_component(value: float, low: float, high: float) -> float:
    if not math.isfinite(value):
        return 50.0
    return clamp((value - low) / max(high - low, EPS) * 100)


def smart_money_proxy(df: pd.DataFrame) -> dict:
    data = ensure_ohlcv(df)
    if len(data) < 30:
        return {
            "Smart Money Score": 0.0,
            "CMF20": np.nan,
            "MFI14": np.nan,
            "OBV Slope": np.nan,
            "Up/Down Volume": np.nan,
            "Accumulation Days": 0,
            "Distribution Days": 0,
        }

    close = data["Close"]
    volume = data["Volume"]
    cmf_now = safe_float(cmf(data, 20).iloc[-1], 0.0)
    mfi_now = safe_float(mfi(data, 14).iloc[-1], 50.0)
    obv_slope = rolling_slope(obv(data), 20)

    returns = close.pct_change()
    recent = data.tail(20).copy()
    recent_ret = returns.tail(20)
    avg_vol20 = safe_float(volume.shift(1).rolling(20).mean().iloc[-1], safe_float(volume.tail(20).mean(), 0.0))
    high_volume = recent["Volume"] >= avg_vol20 * 1.2 if avg_vol20 > 0 else pd.Series(False, index=recent.index)
    close_loc = close_location(recent)
    accumulation = int(((recent_ret > 0) & high_volume & (close_loc >= 60)).sum())
    distribution = int(((recent_ret < 0) & high_volume & (close_loc <= 40)).sum())

    up_volume = safe_float(volume.tail(20)[returns.tail(20) > 0].sum(), 0.0)
    down_volume = safe_float(volume.tail(20)[returns.tail(20) < 0].sum(), 0.0)
    up_down = up_volume / max(down_volume, EPS)

    cmf_component = _percentile_component(cmf_now, -0.25, 0.25)
    if 50 <= mfi_now <= 80:
        mfi_component = 75 + (mfi_now - 50) / 30 * 25
    elif 35 <= mfi_now < 50:
        mfi_component = 45 + (mfi_now - 35) / 15 * 30
    elif mfi_now > 80:
        mfi_component = max(55, 100 - (mfi_now - 80) * 2.25)
    else:
        mfi_component = max(0, mfi_now)
    obv_component = clamp(50 + obv_slope * 1200)
    up_down_component = clamp(50 + math.log(max(up_down, EPS)) * 25)
    acc_component = clamp(50 + (accumulation - distribution) * 10)

    score = (
        cmf_component * 0.28
        + mfi_component * 0.20
        + obv_component * 0.20
        + up_down_component * 0.16
        + acc_component * 0.16
    )
    return {
        "Smart Money Score": round(clamp(score), 1),
        "CMF20": cmf_now,
        "MFI14": mfi_now,
        "OBV Slope": obv_slope,
        "Up/Down Volume": up_down,
        "Accumulation Days": accumulation,
        "Distribution Days": distribution,
    }


def pullback_and_reversal(df: pd.DataFrame, hourly: pd.DataFrame | None = None) -> dict:
    data = ensure_ohlcv(df)
    if len(data) < 55:
        return {}
    close, high, low, volume = data["Close"], data["High"], data["Low"], data["Volume"]
    rsi_s = rsi(close, 14)
    mfi_s = mfi(data, 14)
    cmf_s = cmf(data, 20)
    e9, e21, e50 = ema(close, 9), ema(close, 21), ema(close, 50)
    atr_s = atr(data, 14)
    price = safe_float(close.iloc[-1])
    atr_now = safe_float(atr_s.iloc[-1])
    rsi_now = safe_float(rsi_s.iloc[-1], 50.0)
    mfi_now = safe_float(mfi_s.iloc[-1], 50.0)
    cmf_now = safe_float(cmf_s.iloc[-1], 0.0)
    e9_now, e21_now, e50_now = safe_float(e9.iloc[-1]), safe_float(e21.iloc[-1]), safe_float(e50.iloc[-1])

    ret1, ret5, ret20 = _return_pct(close, 1), _return_pct(close, 5), _return_pct(close, 20)
    avg_vol = safe_float(volume.shift(1).rolling(20).mean().iloc[-1], safe_float(volume.tail(20).mean(), 0.0))
    rvol = safe_float(volume.iloc[-1] / avg_vol, np.nan) if avg_vol > 0 else np.nan
    low20, high20 = safe_float(low.tail(20).min()), safe_float(high.tail(20).max())
    range_pos = (price - low20) / max(high20 - low20, EPS) * 100
    extension_atr = (price - e21_now) / atr_now if atr_now > 0 else np.nan
    distance_ema21 = (price / e21_now - 1) * 100 if e21_now > 0 else np.nan
    close_loc = safe_float(close_location(data).iloc[-1], 50.0)
    gap_pct = (safe_float(data["Open"].iloc[-1]) / safe_float(close.iloc[-2]) - 1) * 100
    upper_wick_pct = (safe_float(high.iloc[-1]) - price) / max(safe_float(high.iloc[-1]) - safe_float(low.iloc[-1]), EPS) * 100

    pullback = 0.0
    pullback += 25 if rsi_now >= 80 else 18 if rsi_now >= 72 else 10 if rsi_now >= 66 else 0
    if math.isfinite(extension_atr):
        pullback += 28 if extension_atr >= 3.0 else 20 if extension_atr >= 2.0 else 10 if extension_atr >= 1.25 else 0
    pullback += 14 if range_pos >= 95 else 8 if range_pos >= 85 else 0
    pullback += 14 if ret5 >= 15 else 8 if ret5 >= 8 else 0
    pullback += 10 if ret1 >= 10 else 5 if ret1 >= 5 else 0
    pullback += 8 if gap_pct >= 6 else 4 if gap_pct >= 3 else 0
    if rvol >= 2 and upper_wick_pct >= 45:
        pullback += 12
    elif ret1 > 2 and close_loc < 45:
        pullback += 8
    if mfi_now >= 88:
        pullback += 6

    crossed_ema9 = bool(close.iloc[-2] <= e9.iloc[-2] and close.iloc[-1] > e9.iloc[-1])
    reclaimed_ema21 = bool(close.iloc[-2] <= e21.iloc[-2] and close.iloc[-1] > e21.iloc[-1])
    broke_prev_high = bool(price > safe_float(high.iloc[-2]))
    rsi_cross_40 = bool(rsi_s.iloc[-2] <= 40 < rsi_s.iloc[-1])
    mfi_cross_50 = bool(mfi_s.iloc[-2] <= 50 < mfi_s.iloc[-1])
    cmf_rising = bool(cmf_s.iloc[-1] > cmf_s.iloc[-3]) if len(cmf_s) >= 3 else False

    reversal = 0.0
    reversal += 12 if range_pos <= 20 else 7 if range_pos <= 40 else 0
    reversal += 10 if rsi_now <= 35 else 6 if rsi_now <= 48 else 0
    reversal += 18 if crossed_ema9 else 0
    reversal += 14 if reclaimed_ema21 else 0
    reversal += 14 if broke_prev_high else 0
    reversal += 10 if rsi_cross_40 else 0
    reversal += 8 if mfi_cross_50 else 0
    reversal += 7 if cmf_rising else 0
    reversal += 10 if rvol >= 1.5 else 5 if rvol >= 1.15 else 0
    reversal += 7 if close_loc >= 70 else 3 if close_loc >= 55 else 0

    # Intraday confirmation from 2H if available.
    intraday_score = np.nan
    if hourly is not None and not ensure_ohlcv(hourly).empty:
        tf2h = timeframe_snapshot(resample_ohlcv(hourly, "2h", offset="9h30min"), "2H")
        if tf2h:
            intraday_score = tf2h.trend_score
            if tf2h.trend_score >= 65:
                reversal += 8
            elif tf2h.trend_score <= 35:
                reversal -= 8

    return {
        "Price": price,
        "1D %": ret1,
        "5D %": ret5,
        "20D %": ret20,
        "RSI14": rsi_now,
        "RVOL20": rvol,
        "ATR": atr_now,
        "ATR %": atr_now / price * 100 if price > 0 else np.nan,
        "EMA9": e9_now,
        "EMA21": e21_now,
        "EMA50": e50_now,
        "Dist EMA21 %": distance_ema21,
        "Extension ATR": extension_atr,
        "20D Range Pos %": range_pos,
        "Close Location %": close_loc,
        "Gap %": gap_pct,
        "Pullback Risk": round(clamp(pullback), 1),
        "Reversal Score": round(clamp(reversal), 1),
        "2H Trend Score": intraday_score,
    }


def technical_levels(
    df: pd.DataFrame,
    setup: str,
    *,
    pullback_risk: float = 50.0,
    trend_score: float = 50.0,
) -> dict:
    """
    Reference trade plan from ATR, EMA structure and recent swing levels.
    Levels are planning zones, not guaranteed fills.
    """
    data = ensure_ohlcv(df)
    if len(data) < 30:
        return {}

    close = data["Close"]
    price = safe_float(close.iloc[-1])
    atr_now = safe_float(atr(data, 14).iloc[-1], price * 0.03)
    e9 = safe_float(ema(close, 9).iloc[-1], price)
    e21 = safe_float(ema(close, 21).iloc[-1], price)
    e50 = safe_float(ema(close, 50).iloc[-1], price)
    low5 = safe_float(data["Low"].tail(5).min())
    low20 = safe_float(data["Low"].tail(20).min())
    high20 = safe_float(data["High"].tail(20).max())
    prev_high = safe_float(data["High"].iloc[-2])
    prev_low = safe_float(data["Low"].iloc[-2])

    if not math.isfinite(atr_now) or atr_now <= 0:
        atr_now = max(price * 0.03, 0.01)

    setup_lower = str(setup).lower()
    is_reversal = "reversal" in setup_lower
    is_momentum = "momentum" in setup_lower or "breakout" in setup_lower
    is_hot = pullback_risk >= 68

    if is_hot:
        buy_high = min(e9, price - 0.30 * atr_now)
        buy_low = min(e21, buy_high - 0.45 * atr_now)
        logic = "Quá nóng: chỉ chờ pullback về EMA9/EMA21; không mua đuổi."
    elif is_reversal:
        buy_low = max(low20, min(e21, prev_low) - 0.15 * atr_now)
        buy_high = min(price, max(e9, prev_high) + 0.10 * atr_now)
        logic = "Reversal: chỉ mua khi vùng hỗ trợ giữ được và giá reclaim EMA9/đỉnh phiên trước."
    elif is_momentum:
        breakout_level = max(prev_high, high20 - 0.15 * atr_now)
        buy_low = min(e9, breakout_level - 0.30 * atr_now)
        buy_high = min(price + 0.25 * atr_now, max(e9, breakout_level + 0.10 * atr_now))
        logic = "Momentum: ưu tiên pullback giữ EMA9 hoặc breakout có volume xác nhận."
    else:
        buy_low = min(e21, price - 0.45 * atr_now)
        buy_high = min(price, max(e9, price - 0.10 * atr_now))
        logic = "Chưa đồng thuận: chỉ cân nhắc gần hỗ trợ, không mua giữa biên."

    buy_low = max(0.01, buy_low)
    buy_high = max(0.01, buy_high)
    if buy_high < buy_low:
        buy_low, buy_high = buy_high, buy_low

    chase_limit = max(buy_high, price + (0.15 if is_hot else 0.35) * atr_now)

    stop = min(low5, e21) - 0.25 * atr_now
    if is_reversal:
        stop = min(stop, low20 - 0.15 * atr_now)
    if stop >= buy_low or stop <= 0:
        stop = buy_low - 1.10 * atr_now
    stop = max(0.01, stop)

    entry_mid = (buy_low + buy_high) / 2.0
    risk = max(entry_mid - stop, 0.65 * atr_now)

    sell1 = max(high20, entry_mid + 1.50 * risk)
    sell2 = max(sell1 + 0.70 * atr_now, entry_mid + 2.50 * risk)

    if is_hot:
        sell1 = max(price + 0.50 * atr_now, entry_mid + 1.20 * risk)
        sell2 = max(price + 1.20 * atr_now, entry_mid + 2.00 * risk)

    trailing_stop = max(e9, price - 1.10 * atr_now)
    if trend_score < 48:
        trailing_stop = max(e21, price - 0.85 * atr_now)

    return {
        "Buy Zone Low": round(buy_low, 2),
        "Buy Zone High": round(buy_high, 2),
        "Chase Limit": round(chase_limit, 2),
        "Stop": round(stop, 2),
        "Sell Zone 1": round(sell1, 2),
        "Sell Zone 2": round(sell2, 2),
        "Trailing Stop": round(trailing_stop, 2),
        "Risk/Share": round(risk, 2),
        "Level Logic": logic,
    }


def classify_setup(
    multi_score: float,
    bullish_timeframes: int,
    smart_score: float,
    pullback_risk: float,
    reversal_score: float,
    relative_20d: float,
) -> tuple[str, str, float]:
    relative_component = clamp(50 + relative_20d * 2.5)
    entry_component = max(reversal_score, multi_score if pullback_risk < 55 else multi_score * 0.65)
    trade_score = (
        multi_score * 0.32
        + smart_score * 0.23
        + relative_component * 0.13
        + entry_component * 0.17
        + bullish_timeframes / 5 * 100 * 0.15
        - pullback_risk * 0.28
    )
    trade_score = clamp(trade_score)

    if pullback_risk >= 72:
        return "Quá nóng – chờ pullback/base", "Không chase call ngắn hạn", trade_score
    if reversal_score >= 63 and multi_score >= 48 and smart_score >= 52:
        return "Reversal xác nhận", "Shares starter; call sau breakout", trade_score
    if multi_score >= 70 and smart_score >= 58 and relative_20d > 0 and bullish_timeframes >= 3:
        return "Momentum xác nhận", "Shares hoặc call có DTE buffer", trade_score
    if multi_score >= 58 and smart_score >= 48 and pullback_risk < 62:
        return "Theo dõi pullback/breakout", "Shares an toàn hơn; call khi có trigger", trade_score
    if smart_score < 40 and multi_score < 48:
        return "Dòng tiền yếu", "Đứng ngoài", trade_score
    return "Chưa đồng thuận", "Theo dõi, chưa vào", trade_score


def analyze_symbol(
    symbol: str,
    daily: pd.DataFrame,
    hourly: pd.DataFrame | None,
    benchmark_daily: pd.DataFrame | None = None,
    sector_flow_score: float = 50.0,
) -> tuple[dict, pd.DataFrame]:
    mtf_df, multi_score, bullish_count = multi_timeframe_report(daily, hourly)
    pr = pullback_and_reversal(daily, hourly)
    smart = smart_money_proxy(daily)
    if not pr:
        return {}, mtf_df

    benchmark_ret20 = 0.0
    if benchmark_daily is not None and not ensure_ohlcv(benchmark_daily).empty:
        benchmark_ret20 = _return_pct(ensure_ohlcv(benchmark_daily)["Close"], 20)
        if not math.isfinite(benchmark_ret20):
            benchmark_ret20 = 0.0
    relative20 = safe_float(pr["20D %"], 0.0) - benchmark_ret20
    setup, vehicle, base_trade_score = classify_setup(
        multi_score,
        bullish_count,
        smart["Smart Money Score"],
        pr["Pullback Risk"],
        pr["Reversal Score"],
        relative20,
    )
    trade_score = clamp(base_trade_score * 0.85 + sector_flow_score * 0.15)
    levels = technical_levels(
        daily,
        setup,
        pullback_risk=pr["Pullback Risk"],
        trend_score=multi_score,
    )

    row = {
        "Ticker": symbol,
        **pr,
        **smart,
        "MTF Score": round(multi_score, 1),
        "Bullish TF": bullish_count,
        "RS vs Benchmark 20D": relative20,
        "Sector Flow": sector_flow_score,
        "Trade Score": round(trade_score, 1),
        "Setup": setup,
        "Preferred Vehicle": vehicle,
        **levels,
    }
    return row, mtf_df


# ------------------------------ Options math ------------------------------

def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@dataclass
class Greeks:
    option_type: str
    theoretical_price: float
    delta: float
    gamma: float
    theta_per_day: float
    vega_per_1pct: float
    rho_per_1pct: float
    probability_itm: float


def black_scholes_greeks(
    spot: float,
    strike: float,
    years: float,
    rate: float,
    iv: float,
    option_type: str = "call",
    dividend_yield: float = 0.0,
) -> Greeks:
    option_type = option_type.lower()
    if option_type not in {"call", "put"}:
        raise ValueError("option_type must be 'call' or 'put'")
    if min(spot, strike, years, iv) <= 0:
        return Greeks(option_type, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan)

    sqrt_t = math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate - dividend_yield + 0.5 * iv * iv) * years) / (iv * sqrt_t)
    d2 = d1 - iv * sqrt_t
    disc_r = math.exp(-rate * years)
    disc_q = math.exp(-dividend_yield * years)

    gamma = disc_q * norm_pdf(d1) / (spot * iv * sqrt_t)
    vega = spot * disc_q * norm_pdf(d1) * sqrt_t / 100.0

    if option_type == "call":
        price = spot * disc_q * norm_cdf(d1) - strike * disc_r * norm_cdf(d2)
        delta = disc_q * norm_cdf(d1)
        theta_annual = (
            -spot * disc_q * norm_pdf(d1) * iv / (2 * sqrt_t)
            - rate * strike * disc_r * norm_cdf(d2)
            + dividend_yield * spot * disc_q * norm_cdf(d1)
        )
        rho = strike * years * disc_r * norm_cdf(d2) / 100.0
        probability_itm = norm_cdf(d2)
    else:
        price = strike * disc_r * norm_cdf(-d2) - spot * disc_q * norm_cdf(-d1)
        delta = -disc_q * norm_cdf(-d1)
        theta_annual = (
            -spot * disc_q * norm_pdf(d1) * iv / (2 * sqrt_t)
            + rate * strike * disc_r * norm_cdf(-d2)
            - dividend_yield * spot * disc_q * norm_cdf(-d1)
        )
        rho = -strike * years * disc_r * norm_cdf(-d2) / 100.0
        probability_itm = norm_cdf(-d2)

    return Greeks(
        option_type=option_type,
        theoretical_price=price,
        delta=delta,
        gamma=gamma,
        theta_per_day=theta_annual / 365.0,
        vega_per_1pct=vega,
        rho_per_1pct=rho,
        probability_itm=probability_itm,
    )


def option_style_target(style: str) -> tuple[float, float, float]:
    style = style.lower()
    if "an toàn" in style or "safe" in style:
        return 0.68, 0.58, 0.82
    if "tấn công" in style or "aggressive" in style:
        return 0.42, 0.30, 0.55
    return 0.56, 0.45, 0.68


def enrich_option_chain(
    chain: pd.DataFrame,
    spot: float,
    expiry: pd.Timestamp,
    option_type: str,
    hold_days: int,
    max_contract_budget: float,
    style: str = "Cân bằng",
    rate: float = 0.04,
    dividend_yield: float = 0.0,
) -> pd.DataFrame:
    if chain is None or chain.empty:
        return pd.DataFrame()
    out = chain.copy()
    numeric_cols = ["strike", "bid", "ask", "lastPrice", "volume", "openInterest", "impliedVolatility"]
    for col in numeric_cols:
        out[col] = pd.to_numeric(out.get(col), errors="coerce")
    out["volume"] = out["volume"].fillna(0.0)
    out["openInterest"] = out["openInterest"].fillna(0.0)
    out["mid"] = (out["bid"].fillna(0.0) + out["ask"].fillna(0.0)) / 2.0
    out["premium_$"] = out["ask"] * 100.0
    out["spread_%"] = np.where(out["mid"] > 0, (out["ask"] - out["bid"]) / out["mid"] * 100.0, np.nan)
    out["moneyness_%"] = (out["strike"] / spot - 1.0) * 100.0

    expiry_ts = pd.Timestamp(expiry)
    if expiry_ts.tzinfo is None:
        expiry_ts = expiry_ts.tz_localize("America/New_York")
    now = pd.Timestamp.now(tz="America/New_York")
    years = max((expiry_ts - now).total_seconds() / (365.0 * 24 * 3600), 1 / 3650)
    dte = max((expiry_ts.date() - now.date()).days, 0)
    out["DTE"] = dte
    out["DTE buffer"] = dte - int(hold_days)

    greeks = []
    for strike, iv in zip(out["strike"], out["impliedVolatility"]):
        if pd.isna(strike) or pd.isna(iv) or iv <= 0:
            greeks.append(Greeks(option_type, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan))
        else:
            greeks.append(
                black_scholes_greeks(
                    spot,
                    float(strike),
                    years,
                    rate,
                    float(iv),
                    option_type=option_type,
                    dividend_yield=dividend_yield,
                )
            )

    out["theoretical"] = [g.theoretical_price for g in greeks]
    out["delta"] = [g.delta for g in greeks]
    out["gamma"] = [g.gamma for g in greeks]
    out["theta/day"] = [g.theta_per_day for g in greeks]
    out["vega/1%"] = [g.vega_per_1pct for g in greeks]
    out["prob_ITM"] = [g.probability_itm for g in greeks]
    out["theta_$contract/day"] = out["theta/day"] * 100.0
    out["theta_%premium/day"] = np.where(
        out["ask"] > 0, np.abs(out["theta/day"]) / out["ask"] * 100.0, np.nan
    )
    if option_type == "call":
        out["breakeven"] = out["strike"] + out["ask"]
    else:
        out["breakeven"] = out["strike"] - out["ask"]
    out["expected_move_$"] = spot * out["impliedVolatility"] * math.sqrt(max(dte, 1) / 365.0)
    out["volume/OI"] = out["volume"] / out["openInterest"].replace(0, np.nan)

    target, low_delta, high_delta = option_style_target(style)
    absolute_delta = out["delta"].abs()
    delta_score = (1.0 - (absolute_delta - target).abs() / max(target, 0.01)).clip(lower=0, upper=1) * 35
    dte_score = np.select(
        [out["DTE buffer"] >= 14, out["DTE buffer"] >= 7, out["DTE buffer"] >= 3],
        [20, 14, 7],
        default=0,
    )
    spread_score = (1 - out["spread_%"].fillna(100).clip(0, 30) / 30) * 15
    liquidity_score = (
        np.log1p(out["openInterest"]).rank(pct=True) * 8
        + np.log1p(out["volume"]).rank(pct=True) * 7
    )
    theta_score = (1 - out["theta_%premium/day"].fillna(10).clip(0, 5) / 5) * 10
    out["Option Fit Score"] = (delta_score + dte_score + spread_score + liquidity_score + theta_score).round(1)
    out["Delta Fit"] = np.where(absolute_delta.between(low_delta, high_delta), "Good", "Outside target")
    out["Within Budget"] = out["premium_$"] <= max_contract_budget

    # Hard filters retain nearby strikes but do not hide useful comparisons.
    out = out[
        (out["strike"] >= spot * 0.70)
        & (out["strike"] <= spot * 1.35)
        & (out["ask"] > 0)
        & (out["Within Budget"])
    ].copy()
    return out.sort_values(["Option Fit Score", "openInterest", "volume"], ascending=False)


def option_flow_summary(calls: pd.DataFrame, puts: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    def prep(df: pd.DataFrame, side: str) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()
        out = df.copy()
        for col in ["strike", "bid", "ask", "volume", "openInterest", "impliedVolatility"]:
            out[col] = pd.to_numeric(out.get(col), errors="coerce")
        out["volume"] = out["volume"].fillna(0.0)
        out["openInterest"] = out["openInterest"].fillna(0.0)
        out["Side"] = side
        out["Volume/OI"] = out["volume"] / out["openInterest"].replace(0, np.nan)
        out["Notional Proxy"] = out["volume"] * ((out["bid"].fillna(0) + out["ask"].fillna(0)) / 2) * 100
        return out

    c = prep(calls, "CALL")
    p = prep(puts, "PUT")
    call_vol = safe_float(c["volume"].sum(), 0.0) if not c.empty else 0.0
    put_vol = safe_float(p["volume"].sum(), 0.0) if not p.empty else 0.0
    call_oi = safe_float(c["openInterest"].sum(), 0.0) if not c.empty else 0.0
    put_oi = safe_float(p["openInterest"].sum(), 0.0) if not p.empty else 0.0
    summary = {
        "Call Volume": call_vol,
        "Put Volume": put_vol,
        "Call/Put Volume": call_vol / max(put_vol, EPS),
        "Call OI": call_oi,
        "Put OI": put_oi,
        "Call/Put OI": call_oi / max(put_oi, EPS),
    }
    combined = pd.concat([c, p], ignore_index=True)
    if combined.empty:
        return summary, combined
    unusual = combined[
        (combined["volume"] >= 50)
        & ((combined["Volume/OI"] >= 0.75) | (combined["openInterest"] == 0))
    ].copy()
    cols = [
        "Side",
        "contractSymbol",
        "strike",
        "bid",
        "ask",
        "volume",
        "openInterest",
        "Volume/OI",
        "impliedVolatility",
        "Notional Proxy",
    ]
    return summary, unusual[[c for c in cols if c in unusual.columns]].sort_values(
        ["Notional Proxy", "volume"], ascending=False
    )


def position_size_shares(capital: float, risk_pct: float, entry: float, stop: float) -> dict:
    risk_budget = max(0.0, capital * risk_pct / 100.0)
    risk_per_share = max(entry - stop, 0.0)
    by_risk = math.floor(risk_budget / risk_per_share) if risk_per_share > 0 else 0
    by_cash = math.floor(capital / entry) if entry > 0 else 0
    shares = max(0, min(by_risk, by_cash))
    return {
        "Risk Budget": risk_budget,
        "Risk/Share": risk_per_share,
        "Shares": shares,
        "Capital Used": shares * entry,
        "Max Planned Loss": shares * risk_per_share,
    }


def position_size_options(capital: float, risk_pct: float, premium_per_contract: float, max_capital_pct: float = 25.0) -> dict:
    risk_budget = max(0.0, capital * risk_pct / 100.0)
    capital_cap = max(0.0, capital * max_capital_pct / 100.0)
    allowed = min(risk_budget, capital_cap)
    contracts = math.floor(allowed / premium_per_contract) if premium_per_contract > 0 else 0
    return {
        "Risk Budget": risk_budget,
        "Option Capital Cap": capital_cap,
        "Contracts": contracts,
        "Premium at Risk": contracts * premium_per_contract,
    }


def reprice_option_scenarios(
    spot: float,
    strike: float,
    iv: float,
    dte: int,
    hold_days: int,
    option_type: str,
    current_ask: float,
    atr_value: float,
    rate: float = 0.04,
) -> pd.DataFrame:
    remaining = max(dte - hold_days, 0)
    years = max(remaining / 365.0, 1 / 3650)
    moves = [-2, -1, 0, 1, 2]
    iv_changes = [-0.10, 0.0, 0.10]
    rows = []
    for atr_move in moves:
        future_spot = max(0.01, spot + atr_move * atr_value)
        for iv_change in iv_changes:
            future_iv = max(0.01, iv * (1 + iv_change))
            g = black_scholes_greeks(future_spot, strike, years, rate, future_iv, option_type)
            rows.append(
                {
                    "Stock Move (ATR)": atr_move,
                    "IV Change": f"{iv_change:+.0%}",
                    "Future Stock": future_spot,
                    "Estimated Option": g.theoretical_price,
                    "P/L per Contract": (g.theoretical_price - current_ask) * 100,
                }
            )
    return pd.DataFrame(rows)
