from __future__ import annotations

from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf


def _as_datetime(value: Any):
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    try:
        return pd.to_datetime(value).to_pydatetime()
    except Exception:
        return None


def _calendar_earnings(symbol: str):
    try:
        calendar = yf.Ticker(symbol).calendar
    except Exception:
        return None, "Unknown"

    if calendar is None:
        return None, "Unknown"

    earnings_value = None

    if isinstance(calendar, dict):
        earnings_value = calendar.get("Earnings Date") or calendar.get("EarningsDate")
    elif isinstance(calendar, pd.DataFrame):
        if "Earnings Date" in calendar.index:
            values = calendar.loc["Earnings Date"].dropna().tolist()
            earnings_value = values[0] if values else None
        elif "Earnings Date" in calendar.columns:
            values = calendar["Earnings Date"].dropna().tolist()
            earnings_value = values[0] if values else None

    if isinstance(earnings_value, (list, tuple, np.ndarray, pd.Series)):
        earnings_value = next((x for x in earnings_value if x is not None), None)

    dt = _as_datetime(earnings_value)
    timing = "Unknown"
    if dt is not None:
        hour = dt.hour
        if 4 <= hour < 9:
            timing = "Before Open"
        elif hour >= 16:
            timing = "After Close"
    return dt, timing


def _earnings_dates_fallback(symbol: str):
    try:
        frame = yf.Ticker(symbol).get_earnings_dates(limit=12)
    except Exception:
        return None, "Unknown"

    if frame is None or frame.empty:
        return None, "Unknown"

    today = pd.Timestamp.now(tz=None).normalize()
    index = pd.to_datetime(frame.index, errors="coerce")
    if getattr(index, "tz", None) is not None:
        index = index.tz_localize(None)

    future = [x for x in index if pd.notna(x) and x.normalize() >= today]
    if not future:
        return None, "Unknown"

    dt = min(future).to_pydatetime()
    timing = "Before Open" if 4 <= dt.hour < 9 else "After Close" if dt.hour >= 16 else "Unknown"
    return dt, timing


def earnings_info(symbol: str) -> dict:
    dt, timing = _calendar_earnings(symbol)
    source = "calendar"

    if dt is None:
        dt, timing = _earnings_dates_fallback(symbol)
        source = "earnings_dates"

    if dt is None:
        return {
            "Ticker": symbol,
            "ER Date": None,
            "ER Timing": "Unknown",
            "Days to ER": None,
            "ER Status": "UNKNOWN",
            "ER Guidance": "Xác nhận ER thủ công trước khi vào option.",
            "Source": source,
        }

    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)

    days = (dt.date() - date.today()).days

    if days < 0:
        status = "PAST"
        guidance = "Dữ liệu ER có thể chưa cập nhật."
    elif days == 0:
        status = "ER TODAY"
        guidance = "Tránh setup thường. Chỉ dùng ER Lotto nếu chấp nhận mất toàn bộ premium."
    elif days <= 2:
        status = "ER VERY SOON"
        guidance = "Rủi ro IV crush rất cao; setup thường nên tránh giữ xuyên ER."
    elif days <= 7:
        status = "ER THIS WEEK"
        guidance = "Chỉ dùng expiration trước ER hoặc thoát trước báo cáo."
    elif days <= 14:
        status = "ER NEAR"
        guidance = "Theo dõi IV tăng; lập kế hoạch thoát trước ER nếu không chơi lotto."
    else:
        status = "CLEAR"
        guidance = "ER chưa gần, nhưng vẫn kiểm tra lại trước khi đặt lệnh."

    return {
        "Ticker": symbol,
        "ER Date": dt.strftime("%Y-%m-%d"),
        "ER Timing": timing,
        "Days to ER": days,
        "ER Status": status,
        "ER Guidance": guidance,
        "Source": source,
    }


def add_earnings_to_signals(signals: pd.DataFrame) -> pd.DataFrame:
    if signals is None or signals.empty:
        return pd.DataFrame()

    rows = []
    for _, row in signals.iterrows():
        info = earnings_info(str(row["Ticker"]))
        record = row.to_dict()
        record.update(info)
        rows.append(record)

    return pd.DataFrame(rows)


def regular_trade_allowed(days_to_er, expiration: str | None = None) -> bool:
    if days_to_er is None or pd.isna(days_to_er):
        return True
    days = int(days_to_er)
    if days < 0:
        return True
    if days <= 2:
        return False

    if expiration:
        try:
            exp_date = datetime.strptime(expiration, "%Y-%m-%d").date()
            er_date = date.today() + pd.Timedelta(days=days)
            return exp_date < er_date
        except Exception:
            pass

    return days > 7


def lotto_label(days_to_er) -> str:
    if days_to_er is None or pd.isna(days_to_er):
        return "NO ER DATA"
    days = int(days_to_er)
    if days == 0:
        return "ER TODAY — EXTREME RISK"
    if 1 <= days <= 2:
        return "ER LOTTO WINDOW"
    if 3 <= days <= 7:
        return "PRE-ER WATCH"
    return "NOT LOTTO WINDOW"
