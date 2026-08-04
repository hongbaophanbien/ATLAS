from __future__ import annotations

import html
import json
import re
from urllib.parse import quote


EXCHANGE_MAP = {
    "SNDK": "NASDAQ",
    "MU": "NASDAQ",
    "WDC": "NASDAQ",
    "AMD": "NASDAQ",
    "NVDA": "NASDAQ",
    "AVGO": "NASDAQ",
    "ARM": "NASDAQ",
    "MRVL": "NASDAQ",
    "AMAT": "NASDAQ",
    "LRCX": "NASDAQ",
    "GLW": "NYSE",
    "DELL": "NYSE",
    "ORCL": "NYSE",
    "PLTR": "NASDAQ",
    "PANW": "NASDAQ",
    "CRWD": "NASDAQ",
    "AAPL": "NASDAQ",
    "MSFT": "NASDAQ",
    "META": "NASDAQ",
    "GOOG": "NASDAQ",
    "GOOGL": "NASDAQ",
    "AMZN": "NASDAQ",
    "TSLA": "NASDAQ",
    "QQQ": "NASDAQ",
    "SPY": "AMEX",
    "SMH": "AMEX",
    "SOXX": "NASDAQ",
    "IGV": "AMEX",
    "AIQ": "NASDAQ",
    "XLK": "AMEX",
    "XLF": "AMEX",
    "XLE": "AMEX",
    "XLI": "AMEX",
    "XLV": "AMEX",
    "XLY": "AMEX",
    "XLP": "AMEX",
    "XLU": "AMEX",
    "IWM": "AMEX",
}


def sanitize_symbol(symbol: str) -> str:
    value = str(symbol or "").strip().upper()
    if ":" in value:
        exchange, ticker = value.split(":", 1)
        exchange = re.sub(r"[^A-Z0-9_.-]", "", exchange)
        ticker = re.sub(r"[^A-Z0-9./_-]", "", ticker)
        return f"{exchange}:{ticker}"
    return re.sub(r"[^A-Z0-9./_-]", "", value)


def resolve_tradingview_symbol(symbol: str, exchange_override: str = "Auto") -> str:
    clean = sanitize_symbol(symbol)
    if ":" in clean:
        return clean

    override = str(exchange_override or "Auto").upper()
    exchange = EXCHANGE_MAP.get(clean, "NASDAQ") if override == "AUTO" else override
    return f"{exchange}:{clean}"


def build_tradingview_html(
    symbol: str,
    *,
    interval: str = "D",
    theme: str = "dark",
    exchange_override: str = "Auto",
    watchlist: list[str] | None = None,
    height: int = 720,
) -> str:
    resolved = resolve_tradingview_symbol(symbol, exchange_override)
    tv_watchlist = [
        resolve_tradingview_symbol(item, "Auto")
        for item in (watchlist or [])
        if sanitize_symbol(item)
    ][:30]

    config = {
        "autosize": True,
        "symbol": resolved,
        "interval": interval,
        "timezone": "exchange",
        "theme": theme,
        "style": "1",
        "locale": "en",
        "backgroundColor": "#0E1117" if theme == "dark" else "#FFFFFF",
        "gridColor": "rgba(120, 123, 134, 0.12)",
        "withdateranges": True,
        "hide_side_toolbar": False,
        "hide_top_toolbar": False,
        "hide_legend": False,
        "hide_volume": False,
        "allow_symbol_change": True,
        "save_image": True,
        "details": True,
        "hotlist": False,
        "calendar": False,
        "watchlist": tv_watchlist,
        "studies": [
            "MASimple@tv-basicstudies",
            "RSI@tv-basicstudies",
            "MACD@tv-basicstudies",
        ],
        "show_popup_button": True,
        "popup_width": "1200",
        "popup_height": "760",
        "support_host": "https://www.tradingview.com",
    }

    safe_symbol = html.escape(resolved)
    symbol_url = quote(resolved.replace(":", "-"), safe="-")
    config_json = json.dumps(config, ensure_ascii=False)

    return f"""
    <div class="tradingview-widget-container" style="height:{int(height)}px;width:100%">
      <div class="tradingview-widget-container__widget" style="height:calc(100% - 28px);width:100%"></div>
      <div class="tradingview-widget-copyright" style="font-size:12px">
        <a href="https://www.tradingview.com/symbols/{symbol_url}/"
           rel="noopener nofollow" target="_blank">
          <span class="blue-text">{safe_symbol} chart</span>
        </a>
        <span class="trademark"> by TradingView</span>
      </div>
      <script type="text/javascript"
              src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
              async>
      {config_json}
      </script>
    </div>
    """
