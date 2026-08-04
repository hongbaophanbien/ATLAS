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
