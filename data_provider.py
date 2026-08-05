from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import pandas as pd
import requests
import yfinance as yf


_DATA_ERRORS: dict[str, list[str]] = {}


def _key(symbol: str, interval: str) -> str:
    return f"{symbol.upper()}::{interval}"


def _record_error(symbol: str, interval: str, source: str, error: Any) -> None:
    key = _key(symbol, interval)
    message = f"{source}: {type(error).__name__}: {error}"
    _DATA_ERRORS.setdefault(key, [])
    if message not in _DATA_ERRORS[key]:
        _DATA_ERRORS[key].append(message)


def clear_data_errors(symbol: str | None = None) -> None:
    if symbol is None:
        _DATA_ERRORS.clear()
        return
    prefix = f"{symbol.upper()}::"
    for key in list(_DATA_ERRORS):
        if key.startswith(prefix):
            _DATA_ERRORS.pop(key, None)


def get_data_error(symbol: str, interval: str | None = None) -> str:
    symbol = symbol.upper()
    if interval:
        messages = _DATA_ERRORS.get(_key(symbol, interval), [])
    else:
        messages = []
        for key, values in _DATA_ERRORS.items():
            if key.startswith(f"{symbol}::"):
                messages.extend(values)
    return "\n".join(messages[-8:])


def flatten_ohlcv(df: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    out = df.copy()
    if isinstance(out.columns, pd.MultiIndex):
        level0 = set(out.columns.get_level_values(0))
        level1 = set(out.columns.get_level_values(1))
        fields = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}

        if fields & level0:
            if symbol and symbol in level1:
                out = out.xs(symbol, axis=1, level=1, drop_level=True)
            elif len(level1) == 1:
                out.columns = out.columns.get_level_values(0)
            else:
                return pd.DataFrame()
        elif fields & level1:
            if symbol and symbol in level0:
                out = out.xs(symbol, axis=1, level=0, drop_level=True)
            elif len(level0) == 1:
                out.columns = out.columns.get_level_values(1)
            else:
                return pd.DataFrame()

    # Some providers use lowercase names.
    rename = {}
    for col in out.columns:
        name = str(col)
        low = name.lower()
        if low == "open":
            rename[col] = "Open"
        elif low == "high":
            rename[col] = "High"
        elif low == "low":
            rename[col] = "Low"
        elif low in {"close", "adj close", "adjclose"}:
            if "Close" not in rename.values():
                rename[col] = "Close"
        elif low == "volume":
            rename[col] = "Volume"
    out = out.rename(columns=rename)

    wanted = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in out.columns]
    if "Close" not in wanted:
        return pd.DataFrame()

    out = out[wanted].copy()
    for col in wanted:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    if "Volume" not in out.columns:
        out["Volume"] = 0.0
    for col in ["Open", "High", "Low"]:
        if col not in out.columns:
            out[col] = out["Close"]

    out = out[["Open", "High", "Low", "Close", "Volume"]]
    out = out[~out.index.duplicated(keep="last")]
    return out.dropna(subset=["Close"]).sort_index()


def _yf_download(
    symbol: str,
    *,
    period: str,
    interval: str,
    prepost: bool,
    auto_adjust: bool,
) -> pd.DataFrame:
    # multi_level_index=False avoids one common single-ticker parsing problem.
    raw = yf.download(
        symbol,
        period=period,
        interval=interval,
        prepost=prepost,
        auto_adjust=auto_adjust,
        actions=False,
        progress=False,
        threads=False,
        timeout=25,
        repair=False,
        group_by="column",
        multi_level_index=False,
    )
    return flatten_ohlcv(raw, symbol)


def _ticker_history(
    symbol: str,
    *,
    period: str,
    interval: str,
    prepost: bool,
    auto_adjust: bool,
) -> pd.DataFrame:
    raw = yf.Ticker(symbol).history(
        period=period,
        interval=interval,
        prepost=prepost,
        auto_adjust=auto_adjust,
        actions=False,
        repair=False,
        timeout=25,
        raise_errors=True,
    )
    return flatten_ohlcv(raw, symbol)


def _direct_chart(
    symbol: str,
    *,
    period: str,
    interval: str,
    prepost: bool,
) -> pd.DataFrame:
    # Final fallback using Yahoo's chart response. No trading or account access.
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}"
    params = {
        "range": period,
        "interval": interval,
        "includePrePost": "true" if prepost else "false",
        "events": "div,splits",
        "corsDomain": "finance.yahoo.com",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/150 Safari/537.36"
        )
    }
    response = requests.get(url, params=params, headers=headers, timeout=25)
    response.raise_for_status()
    payload = response.json()
    chart = payload.get("chart", {})
    if chart.get("error"):
        raise RuntimeError(chart["error"])

    result = (chart.get("result") or [None])[0]
    if not result:
        return pd.DataFrame()

    timestamps = result.get("timestamp") or []
    quote_data = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    if not timestamps:
        return pd.DataFrame()

    length = len(timestamps)
    def fit(values, default=None):
        values = list(values or [])
        if len(values) < length:
            values.extend([default] * (length - len(values)))
        return values[:length]

    idx = pd.to_datetime(timestamps, unit="s", utc=True)
    raw = pd.DataFrame(
        {
            "Open": fit(quote_data.get("open")),
            "High": fit(quote_data.get("high")),
            "Low": fit(quote_data.get("low")),
            "Close": fit(quote_data.get("close")),
            "Volume": fit(quote_data.get("volume"), 0),
        },
        index=idx,
    )
    return flatten_ohlcv(raw, symbol)


def download_history(
    symbol: str,
    *,
    period: str,
    interval: str,
    prepost: bool = False,
    auto_adjust: bool = True,
) -> pd.DataFrame:
    symbol = symbol.strip().upper()
    clear_data_errors(symbol)

    attempts = [
        ("yf.download", _yf_download),
        ("Ticker.history", _ticker_history),
        ("Yahoo chart fallback", _direct_chart),
    ]

    for source, loader in attempts:
        try:
            if source == "Yahoo chart fallback":
                data = loader(
                    symbol,
                    period=period,
                    interval=interval,
                    prepost=prepost,
                )
            else:
                data = loader(
                    symbol,
                    period=period,
                    interval=interval,
                    prepost=prepost,
                    auto_adjust=auto_adjust,
                )
            if not data.empty:
                return data
            _record_error(symbol, interval, source, "returned 0 rows")
        except Exception as exc:
            _record_error(symbol, interval, source, exc)

    return pd.DataFrame()


def daily_history(symbol: str) -> pd.DataFrame:
    # 2y is enough for indicators and less likely to time out than 5y.
    data = download_history(symbol, period="2y", interval="1d", prepost=False)
    if len(data) < 55:
        # Retry maximum history for newly relisted/special tickers.
        retry = download_history(symbol, period="max", interval="1d", prepost=False)
        if len(retry) > len(data):
            data = retry
    return data


def hourly_history(symbol: str) -> pd.DataFrame:
    data = download_history(symbol, period="60d", interval="1h", prepost=False)
    if data.empty:
        data = download_history(symbol, period="60d", interval="60m", prepost=False)
    return data


def extended_history(symbol: str) -> pd.DataFrame:
    return download_history(symbol, period="5d", interval="5m", prepost=True)


def expirations(symbol: str) -> list[str]:
    symbol = symbol.strip().upper()
    try:
        values = list(yf.Ticker(symbol).options)
        if not values:
            _record_error(symbol, "options", "Ticker.options", "returned no expirations")
        return values
    except Exception as exc:
        _record_error(symbol, "options", "Ticker.options", exc)
        return []


def option_chain(symbol: str, expiry: str):
    symbol = symbol.strip().upper()
    try:
        return yf.Ticker(symbol).option_chain(expiry)
    except Exception as exc:
        _record_error(symbol, "options", f"option_chain({expiry})", exc)
        return None



def online_status() -> dict:
    """Lightweight online check using Yahoo's public chart endpoint."""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/QQQ"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/150 Safari/537.36"
        )
    }
    try:
        response = requests.get(
            url,
            params={"range": "1d", "interval": "5m"},
            headers=headers,
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        result = ((payload.get("chart") or {}).get("result") or [])
        return {
            "online": bool(result),
            "provider": "Yahoo chart",
            "message": "Kết nối dữ liệu hoạt động." if result else "Yahoo không trả dữ liệu.",
        }
    except Exception as exc:
        return {
            "online": False,
            "provider": "Yahoo chart",
            "message": f"{type(exc).__name__}: {exc}",
        }


def intraday_5m_history(symbol: str) -> pd.DataFrame:
    return download_history(
        symbol,
        period="5d",
        interval="5m",
        prepost=True,
        auto_adjust=True,
    )


def _session_from_san_jose_timestamp(ts: pd.Timestamp) -> str:
    """Classify a market timestamp using San Jose/Pacific trading windows."""
    if ts is None or pd.isna(ts):
        return "UNKNOWN"

    local = pd.Timestamp(ts)
    if local.tzinfo is None:
        local = local.tz_localize("UTC")
    local = local.tz_convert("America/Los_Angeles")

    # Saturday/Sunday: no official US equity session.
    if local.weekday() >= 5:
        return "CLOSED"

    minute = local.hour * 60 + local.minute
    if 60 <= minute < 390:       # 1:00–6:30 PT = 4:00–9:30 ET
        return "PRE-MARKET"
    if 390 <= minute < 780:      # 6:30–13:00 PT = 9:30–16:00 ET
        return "REGULAR MARKET"
    if 780 <= minute < 1020:     # 13:00–17:00 PT = 16:00–20:00 ET
        return "AFTER-HOURS"
    return "OVERNIGHT"


def _expected_session_now() -> str:
    now = pd.Timestamp.now(tz="America/Los_Angeles")
    if now.weekday() >= 5:
        return "CLOSED"
    minute = now.hour * 60 + now.minute
    if 60 <= minute < 390:
        return "PRE-MARKET"
    if 390 <= minute < 780:
        return "REGULAR MARKET"
    if 780 <= minute < 1020:
        return "AFTER-HOURS"
    return "OVERNIGHT"


def latest_session_quote(symbol: str) -> dict:
    """
    Return the latest provider-supported quote with explicit session/freshness.

    Yahoo generally supplies regular, pre-market and after-hours bars. It does
    not guarantee a complete broker-style overnight tape. During the overnight
    window, ATLAS only labels a quote OVERNIGHT when the returned timestamp is
    actually recent; otherwise it is marked stale instead of inventing a price.
    """
    symbol = symbol.strip().upper()
    now_utc = pd.Timestamp.now(tz="UTC")
    expected_session = _expected_session_now()

    frame = download_history(
        symbol,
        period="1d",
        interval="1m",
        prepost=True,
        auto_adjust=False,
    )
    source = "Yahoo 1m extended"

    if frame.empty:
        frame = download_history(
            symbol,
            period="5d",
            interval="5m",
            prepost=True,
            auto_adjust=False,
        )
        source = "Yahoo 5m extended fallback"

    if frame.empty:
        return {
            "Price Used": None,
            "Price Session": expected_session,
            "Price Updated": None,
            "Price Age Seconds": None,
            "Price Fresh": False,
            "Price Source": source,
            "Price Warning": "Không lấy được giá phiên hiện tại.",
        }

    close = pd.to_numeric(frame["Close"], errors="coerce").dropna()
    if close.empty:
        return {
            "Price Used": None,
            "Price Session": expected_session,
            "Price Updated": None,
            "Price Age Seconds": None,
            "Price Fresh": False,
            "Price Source": source,
            "Price Warning": "Không có close hợp lệ.",
        }

    ts = pd.Timestamp(close.index[-1])
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    ts_utc = ts.tz_convert("UTC")
    ts_sj = ts_utc.tz_convert("America/Los_Angeles")
    age_seconds = max(0.0, (now_utc - ts_utc).total_seconds())
    actual_session = _session_from_san_jose_timestamp(ts_utc)

    thresholds = {
        "REGULAR MARKET": 120,
        "PRE-MARKET": 180,
        "AFTER-HOURS": 180,
        "OVERNIGHT": 300,
        "CLOSED": 900,
        "UNKNOWN": 180,
    }
    threshold = thresholds.get(expected_session, 180)

    # A quote is fresh only when its timestamp belongs to the current session
    # and falls inside the session-specific age threshold.
    session_matches = (
        actual_session == expected_session
        or (expected_session == "CLOSED" and actual_session in {
            "REGULAR MARKET", "AFTER-HOURS", "PRE-MARKET"
        })
    )
    fresh = bool(session_matches and age_seconds <= threshold)

    warning = ""
    if expected_session == "OVERNIGHT" and not fresh:
        warning = (
            "Nguồn miễn phí không trả tape overnight đủ mới; "
            "ATLAS không dùng giá cũ để phát plan mới."
        )
    elif not fresh:
        warning = (
            f"Giá {actual_session} đã cũ so với phiên {expected_session}; "
            "không phát plan mới."
        )

    return {
        "Price Used": round(float(close.iloc[-1]), 4),
        "Price Session": actual_session,
        "Expected Session": expected_session,
        "Price Updated": ts_sj.strftime("%Y-%m-%d %I:%M:%S %p %Z"),
        "Price Updated ISO": ts_utc.isoformat(),
        "Price Age Seconds": round(age_seconds, 1),
        "Price Fresh": fresh,
        "Price Source": source,
        "Price Warning": warning,
    }
