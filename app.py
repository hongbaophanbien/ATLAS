from __future__ import annotations

import html
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from chart_engine import make_analysis_chart, select_chart_frame
from core import analyze_symbol
from data_provider import (
    daily_history,
    hourly_history,
    intraday_5m_history,
    online_status,
    get_data_error,
    latest_session_quote,
)
from earnings_engine import earnings_info, lotto_label
from flow_engine import market_pulse, money_flow_metrics, rank_candidate
from live_feed import make_feed
from market_story_engine import build_market_narrative
from opportunity_engine import rank_opportunities
from quick_option import shortlist_contracts
from atlas_signal_refresh_hotfix import (
    apply_decisions,
    fill_option_signals,
    compact_numbers,
)
from retest_engine import analyze_retest
from sector_engine import THEMES, build_theme_rotation
from story_engine import analyst_consensus, signal_fusion, build_story
from system_health import health_report
from trade_plan_engine import build_trade_plan, trade_plan_html
from watch_engine import build_watch_actions
from semi_engine import SEMI_UNIVERSE, build_semi_dashboard, semi_market_summary
from watchlist_bot import (
    build_bot_alerts, bot_summary, build_signal_tables,
    build_signal_watch, signal_methodology_text,
)
from signal_brain import signal_fusion_html
from reliability_engine import snapshot_freshness
from snapshot_store import (
    configured as snapshot_configured,
    load_snapshot,
    load_watchlist_settings,
    save_watchlist_settings,
    records_to_frame,
)


APP_TITLE = "ATLAS X 2.2 — SESSION PRICE + UNIFIED TRADE PLAN"
SAN_JOSE_TZ = ZoneInfo("America/Los_Angeles")
DEFAULT = ['AAPL', 'ABBV', 'ADBE', 'ALAB', 'AMD', 'AMAT', 'AMZN', 'ARKX', 'ARM', 'ASML', 'ASTS', 'AVGO', 'BA', 'BAC', 'BE', 'BWXT', 'CAT', 'CCJ', 'CIBR', 'COP', 'CRM', 'CRWD', 'CVX', 'DELL', 'FTNT', 'GLW', 'GOOG', 'GOOGL', 'GS', 'IBM', 'IGV', 'INTC', 'IONQ', 'IWM', 'JNJ', 'JPM', 'KLAC', 'LEU', 'LLY', 'LRCX', 'LUNR', 'META', 'MP', 'MRK', 'MRVL', 'MS', 'MSFT', 'MU', 'NBIS', 'NOW', 'NVDA', 'OKLO', 'OKTA', 'ORCL', 'OXY', 'PANW', 'PLTR', 'POWL', 'QCOM', 'QBTS', 'QQQ', 'QUBT', 'RDW', 'RGTI', 'RKLB', 'SLB', 'SMCI', 'SMH', 'SMR', 'SNDK', 'SOXX', 'SPCX', 'SPY', 'TSLA', 'TSM', 'UNH', 'URA', 'USAR', 'UUUU', 'VRT', 'WDC', 'WFC', 'XLE', 'XLF', 'XLI', 'XLV', 'XOM', 'ZS']

st.set_page_config(page_title=APP_TITLE, page_icon="⚡", layout="wide")

st.markdown(r"""
<style>
@media (max-width: 768px) {
  div[data-testid="stTextInput"] input {
    min-height: 48px !important;
    font-size: 16px !important;
  }
  div[data-testid="stButton"] button {
    min-height: 46px !important;
  }
}
</style>
""", unsafe_allow_html=True)

st.markdown(r"""
<style>
@media (max-width: 768px) {
  .atlas-table th,
  .atlas-table td {
    padding: 8px 10px !important;
    white-space: nowrap !important;
    font-size: 13px !important;
  }

  .atlas-table th:first-child,
  .atlas-table td:first-child {
    min-width: 74px !important;
    width: 74px !important;
    max-width: 74px !important;
    left: 0 !important;
  }

  .atlas-table th:nth-child(2),
  .atlas-table td:nth-child(2),
  .atlas-table th:nth-child(3),
  .atlas-table td:nth-child(3) {
    position: static !important;
    left: auto !important;
    min-width: 92px !important;
  }
}
</style>
""", unsafe_allow_html=True)
st.title(APP_TITLE)
st.caption(
    "Opportunity Engine • Retest Engine • Conviction • Live 5M • "
    "Earnings • Rotation • Signal Fusion • Trade Plan • Option Finder"
)


@st.cache_data(ttl=180, show_spinner=False)
def get_daily(symbol: str):
    return daily_history(symbol)


@st.cache_data(ttl=55, show_spinner=False)
def get_intraday(symbol: str):
    frame = intraday_5m_history(symbol)
    return frame if not frame.empty else hourly_history(symbol)


@st.cache_data(ttl=900, show_spinner=False)
def get_earnings(symbol: str):
    return earnings_info(symbol)


@st.cache_data(ttl=45, show_spinner=False)
def get_latest_session_quote(symbol: str):
    return latest_session_quote(symbol)


def sj_now():
    return datetime.now(SAN_JOSE_TZ)


def market_mode(now=None):
    now = now or sj_now()
    if now.weekday() >= 5:
        return "WEEKEND"
    t = now.time()
    if time(1, 0) <= t < time(6, 30):
        return "PREMARKET"
    if time(6, 30) <= t < time(13, 0):
        return "MARKET OPEN"
    if time(13, 0) <= t < time(17, 0):
        return "AFTER HOURS"
    return "CLOSED"


def parse_symbols(text):
    output = []
    normalized = str(text or "").replace("\n", ",")
    for token in normalized.split(","):
        token = token.strip().upper()
        if token == "SPCE":
            token = "SPCX"
        if token and token not in output:
            output.append(token)

    output = [ticker for ticker in output if ticker != "SPCE"]
    return output[:150]


def _query_watchlist_value() -> str:
    try:
        value = st.query_params.get("watchlist", "")
        if isinstance(value, list):
            value = value[0] if value else ""
        return str(value or "")
    except Exception:
        return ""


def _initial_watchlist_text() -> str:
    try:
        shared = load_watchlist_settings()
        stored = parse_symbols(",".join(shared.get("watchlist") or []))
        if len(stored) >= 5:
            return ", ".join(stored)
    except Exception:
        pass

    saved = parse_symbols(_query_watchlist_value())
    if len(saved) >= 5:
        return ", ".join(saved)

    # Repair the accidental SPCX-only state.
    return ", ".join(DEFAULT)


def persist_watchlist() -> None:
    symbols_saved = parse_symbols(st.session_state.get("watchlist_editor", ""))
    if not symbols_saved:
        symbols_saved = DEFAULT.copy()

    # Never assign to watchlist_editor inside its own widget callback.
    # Save the normalized value externally; the current widget value remains valid.
    st.query_params["watchlist"] = ",".join(symbols_saved)

    try:
        sync_result = save_watchlist_settings(
            symbols_saved,
            st.session_state.get("benchmark_selector", "QQQ"),
        )
        if sync_result.get("synced"):
            st.session_state["watchlist_sync_status"] = (
                "Đã đồng bộ watchlist với Background Scanner."
            )
        else:
            st.session_state["watchlist_sync_status"] = (
                "Watchlist đã lưu trong app. Chưa đồng bộ chạy nền."
            )
    except Exception as exc:
        st.session_state["watchlist_sync_status"] = (
            "Chưa đồng bộ chạy nền: " + str(exc)
        )

    for key in [
        "scan", "rotation", "opportunities", "signal_board", "feed",
        "bot_alerts", "fast_board", "fast_contracts", "scan_time",
        "atlas_auto_started", "atlas_snapshot_boot_attempted",
        "atlas_snapshot_boot_loaded", "flow_radar", "last_live_refresh",
    ]:
        st.session_state.pop(key, None)


def restore_master_watchlist() -> None:
    # Button callbacks run before Streamlit recreates the widgets.
    st.session_state["watchlist_editor"] = ", ".join(DEFAULT)
    st.query_params["watchlist"] = ",".join(DEFAULT)

    try:
        sync_result = save_watchlist_settings(
            DEFAULT,
            st.session_state.get("benchmark_selector", "QQQ"),
        )
        if sync_result.get("synced"):
            st.session_state["watchlist_sync_status"] = (
                "Đã khôi phục và đồng bộ Master Watchlist."
            )
        else:
            st.session_state["watchlist_sync_status"] = (
                "Đã khôi phục Master Watchlist trong app. "
                "Chưa đồng bộ chạy nền."
            )
    except Exception as exc:
        st.session_state["watchlist_sync_status"] = (
            "Đã khôi phục local; chưa đồng bộ chạy nền: " + str(exc)
        )

    for key in [
        "scan", "rotation", "opportunities", "signal_board", "feed",
        "bot_alerts", "fast_board", "fast_contracts", "scan_time",
        "atlas_auto_started", "atlas_snapshot_boot_attempted",
        "atlas_snapshot_boot_loaded", "flow_radar", "last_live_refresh",
    ]:
        st.session_state.pop(key, None)


if "watchlist_editor" not in st.session_state:
    st.session_state["watchlist_editor"] = _initial_watchlist_text()



def add_ticker_mobile() -> None:
    raw = str(st.session_state.get("mobile_ticker_input", "") or "")
    additions = parse_symbols(raw)

    if not additions:
        st.session_state["mobile_add_status"] = "Nhập ít nhất một mã hợp lệ."
        return

    current = parse_symbols(st.session_state.get("watchlist_editor", ""))
    merged = current.copy()

    for ticker in additions:
        if ticker not in merged:
            merged.append(ticker)

    st.session_state["watchlist_editor"] = ", ".join(merged)
    st.query_params["watchlist"] = ",".join(merged)
    st.session_state["mobile_ticker_input"] = ""

    try:
        sync_result = save_watchlist_settings(
            merged,
            st.session_state.get("benchmark_selector", "QQQ"),
        )
        if sync_result.get("synced"):
            st.session_state["mobile_add_status"] = (
                f"Đã thêm {', '.join(additions)} và đồng bộ chạy nền."
            )
        else:
            st.session_state["mobile_add_status"] = (
                f"Đã thêm {', '.join(additions)} vào app."
            )
    except Exception:
        st.session_state["mobile_add_status"] = (
            f"Đã thêm {', '.join(additions)} vào app."
        )

    for key in [
        "scan", "rotation", "opportunities", "signal_board", "feed",
        "bot_alerts", "fast_board", "fast_contracts", "scan_time",
        "atlas_auto_started", "atlas_snapshot_boot_attempted",
        "atlas_snapshot_boot_loaded", "flow_radar", "last_live_refresh",
    ]:
        st.session_state.pop(key, None)

def style_table(df):
    formats = {
        "Price":"${:,.2f}", "1D %":"{:+.1f}%", "5D %":"{:+.1f}%",
        "Rotation":"{:+.1f}", "Money In":"{:.1f}", "Money Out":"{:.1f}",
        "Net Flow":"{:+.1f}", "Sell-off Risk":"{:.1f}%",
        "Pullback Risk":"{:.1f}%", "Call Score":"{:.1f}",
        "Put Score":"{:.1f}", "Confidence":"{:.1f}%",
        "Opportunity Score":"{:.1f}", "MTF Score":"{:.1f}",
        "Trend":"{:.1f}", "MTF":"{:.1f}", "Flow Score":"{:.1f}",
        "Breadth Up %":"{:.1f}", "Outflow Score":"{:.1f}",
    }
    return df.style.format({k:v for k,v in formats.items() if k in df.columns})


def scan_one(symbol, benchmark_df):
    daily = daily_history(symbol)
    intraday = intraday_5m_history(symbol)
    if intraday.empty:
        intraday = hourly_history(symbol)
    base, mtf = analyze_symbol(symbol, daily, intraday, benchmark_df, 50.0)
    flow = money_flow_metrics(daily, intraday)
    rank = rank_candidate(base, flow)
    if base and flow and rank:
        return {**base, **flow, **rank}
    return None


def scan_universe(symbols, benchmark):
    symbols = [s for s in symbols if s]
    if not symbols:
        return pd.DataFrame()

    benchmark_df = daily_history(benchmark)
    records = []
    progress = st.progress(0, text="Đang quét toàn bộ watchlist...")

    workers = min(8, max(2, len(symbols)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(scan_one, s, benchmark_df): s for s in symbols}
        done = 0
        for future in as_completed(futures):
            done += 1
            try:
                row = future.result()
                if row:
                    records.append(row)
            except Exception:
                pass
            progress.progress(done / len(symbols), text=f"Đã quét {done}/{len(symbols)}")

    progress.empty()
    return pd.DataFrame(records)


def enrich_earnings(frame):
    if frame is None or frame.empty:
        return pd.DataFrame()
    rows = []
    for _, row in frame.iterrows():
        record = row.to_dict()
        record.update(get_earnings(str(row["Ticker"])))
        rows.append(record)
    return pd.DataFrame(rows)



def load_background_snapshot_into_session() -> bool:
    if not snapshot_configured(): return False
    try: payload=load_snapshot()
    except Exception as exc:
        st.session_state["snapshot_error"]=str(exc); return False
    if not payload: return False
    st.session_state["scan"]=records_to_frame(payload.get("scan"))
    st.session_state["rotation"]=records_to_frame(payload.get("rotation"))
    st.session_state["opportunities"]=records_to_frame(payload.get("opportunities"))
    st.session_state["signal_board"]=records_to_frame(payload.get("signal_board"))
    st.session_state["flow_radar"] = records_to_frame(payload.get("flow_radar"))
    st.session_state["flow_radar_status"] = payload.get("flow_radar_status") or {}
    st.session_state["earnings_14d"] = records_to_frame(payload.get("earnings_14d"))
    st.session_state["earnings_failure_count"] = payload.get("earnings_failure_count", 0)
    st.session_state["scanner_status"] = payload.get("scanner_status") or {}
    st.session_state["scanner_duration_seconds"] = payload.get("scanner_duration_seconds")
    st.session_state["scanner_finished_at_utc"] = payload.get("scanner_finished_at_utc")
    st.session_state["snapshot_updated_at"] = payload.get("_snapshot_updated_at")
    st.session_state["github_run_id"] = payload.get("github_run_id", "")
    st.session_state["data_provider_status"] = payload.get("data_provider") or {}
    st.session_state["scan_time"] = payload.get(
        "scan_time_san_jose",
        payload.get("_snapshot_updated_at", "Unknown"),
    )
    st.session_state["snapshot_watchlist_count"] = payload.get("watchlist_count", 0)
    st.session_state["snapshot_scanned_count"] = payload.get(
        "scanned_count", len(st.session_state["scan"])
    )
    st.session_state["snapshot_qualified_count"] = payload.get(
        "qualified_count", len(st.session_state["opportunities"])
    )
    st.session_state["snapshot_hidden_count"] = payload.get(
        "hidden_count",
        max(0, len(st.session_state["scan"]) - len(st.session_state["opportunities"])),
    )
    st.session_state["snapshot_failed_count"] = payload.get("failed_count", 0)
    st.session_state["loaded_background_snapshot"] = True
    return True

if "background_snapshot_attempted" not in st.session_state:
    st.session_state["background_snapshot_attempted"] = True
    query_symbols = parse_symbols(_query_watchlist_value())
    # A custom watchlist must be scanned from its own symbols, not from a stale default snapshot.
    if not query_symbols or query_symbols == DEFAULT:
        load_background_snapshot_into_session()



def _format_us_date(value):
    """Display dates as M/D/YY, for example 8/21/26."""
    if value is None:
        return "—"
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return str(value)
        return f"{parsed.month}/{parsed.day}/{str(parsed.year)[-2:]}"
    except Exception:
        return str(value)


def _global_table_value(column, value):
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except Exception:
        pass

    if column in {"Expiration", "ER Date", "Date"}:
        return _format_us_date(value)

    money_columns = {
        "Price", "Stock Price", "Strike", "Bid", "Ask", "Premium",
        "Entry Low", "Entry High", "Buy Zone Low", "Buy Zone High",
        "Chase Limit", "Stop", "TP1", "TP2", "Sell Zone 1",
        "Sell Zone 2", "Breakdown Level", "Invalidation",
    }
    percent_columns = {
        "1D %", "5D %", "Pullback Risk", "Sell-off Risk",
        "Confidence", "CALL %", "PUT %", "WAIT %", "IV",
        "Breadth Up %", "Outflow Score",
    }
    signed_columns = {"Net Flow", "Rotation"}
    one_decimal_columns = {
        "RSI14", "Trade Score", "Opportunity Score", "Money In",
        "Money Out", "MTF Score", "MTF", "Trend", "Call Score",
        "Put Score", "Contract Score", "Stock Confidence", "Flow Score",
        "Delta", "Theta/day",
    }
    integer_columns = {"Volume", "OI", "Open Interest", "Members"}

    try:
        number = float(value)
        if column in money_columns:
            return f"${number:,.2f}"
        if column in percent_columns:
            if column in {"1D %", "5D %"}:
                return f"{number:+.1f}%"
            return f"{number:.1f}%"
        if column in signed_columns:
            return f"{number:+.1f}"
        if column in integer_columns:
            return f"{number:,.0f}"
        if column in one_decimal_columns:
            # Greeks need two decimals; scores use one.
            if column in {"Delta", "Theta/day"}:
                return f"{number:.2f}"
            return f"{number:.1f}"
        # Never expose long floating-point strings in any table.
        return f"{number:,.2f}"
    except Exception:
        return str(value)


def global_sticky_table_html(
    frame,
    height=520,
    sticky_columns=("Ticker",),
):
    """Render any dataframe with sticky header and sticky identity columns."""
    if frame is None or frame.empty:
        return """
        <div style="padding:18px;border:1px solid #303744;border-radius:10px;
                    color:#aeb8c8;background:#0e131b">
          Không có dữ liệu đủ điều kiện.
        </div>
        """

    data = frame.copy()
    columns = list(data.columns)
    sticky = [column for column in sticky_columns if column in columns]

    # Calculate left offsets for up to three frozen columns.
    widths = {}
    for column in sticky:
        if column == "Ticker":
            widths[column] = 88
        elif column in {"Action", "Signal", "Decision", "Conviction"}:
            widths[column] = 124
        else:
            widths[column] = 110

    offsets = {}
    running = 0
    for column in sticky:
        offsets[column] = running
        running += widths[column]

    header_cells = []
    for column in columns:
        styles = []
        classes = []
        if column in sticky:
            styles.extend([
                "position:sticky",
                f"left:{offsets[column]}px",
                f"min-width:{widths[column]}px",
                f"width:{widths[column]}px",
                "z-index:40",
            ])
            classes.append("sticky-header")
        header_cells.append(
            f'<th class="{" ".join(classes)}" style="{";".join(styles)}">'
            f'{html.escape(str(column))}</th>'
        )

    body_rows = []
    for _, row in data.iterrows():
        cells = []
        for column in columns:
            value = _global_table_value(column, row.get(column))
            styles = []
            classes = []
            if column in sticky:
                styles.extend([
                    "position:sticky",
                    f"left:{offsets[column]}px",
                    f"min-width:{widths[column]}px",
                    f"width:{widths[column]}px",
                    "z-index:25",
                ])
                classes.append("sticky-body")
            if column == "Ticker":
                classes.append("ticker")
            cells.append(
                f'<td class="{" ".join(classes)}" style="{";".join(styles)}">'
                f'{html.escape(value)}</td>'
            )
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    min_width = max(1100, len(columns) * 125)
    safe_height = int(max(220, min(height, 850)))

    return f"""
    <style>
      :root {{ color-scheme: dark; }}
      html, body {{
        margin:0; padding:0; background:transparent;
        font-family:Arial,Helvetica,sans-serif;
      }}
      .global-table-wrap {{
        width:100%;
        height:{safe_height}px;
        overflow:auto;
        border:1px solid #303744;
        border-radius:10px;
        background:#0e131b;
        -webkit-overflow-scrolling:touch;
        overscroll-behavior:contain;
      }}
      .global-table-wrap table {{
        border-collapse:separate;
        border-spacing:0;
        min-width:{min_width}px;
        width:max-content;
        color:#f3f5f8;
        font-size:13px;
      }}
      .global-table-wrap th,
      .global-table-wrap td {{
        padding:10px 12px;
        border-right:1px solid #303744;
        border-bottom:1px solid #303744;
        white-space:nowrap;
        text-align:left;
        background:#0e131b;
      }}
      .global-table-wrap thead th {{
        position:sticky;
        top:0;
        z-index:30;
        background:#1a202b;
        color:#b9c4d3;
        font-weight:700;
      }}
      .global-table-wrap .sticky-header {{
        background:#253044;
        box-shadow:2px 0 0 #414d60;
      }}
      .global-table-wrap .sticky-body {{
        background:#151d29;
        box-shadow:2px 0 0 #354154;
      }}
      .global-table-wrap td.ticker {{
        color:#fff;
        font-weight:850;
      }}
      .global-table-wrap tbody tr:hover td {{
        background:#172131;
      }}
      .global-table-wrap tbody tr:hover .sticky-body {{
        background:#223047;
      }}
      @media(max-width:700px) {{
        .global-table-wrap {{
          height:min({safe_height}px, 62vh);
        }}
        .global-table-wrap table {{ font-size:12px; }}
        .global-table-wrap th,
        .global-table-wrap td {{ padding:9px 10px; }}
      }}
    </style>
    <div class="global-table-wrap">
      <table>
        <thead><tr>{"".join(header_cells)}</tr></thead>
        <tbody>{"".join(body_rows)}</tbody>
      </table>
    </div>
    """


def show_global_table(
    frame,
    height=520,
    sticky_columns=("Ticker",),
):
    components.html(
        global_sticky_table_html(
            frame,
            height=height,
            sticky_columns=sticky_columns,
        ),
        height=height + 38,
        scrolling=False,
    )

FAST_PICK_COLUMNS = [
    "Ticker",
    "Price",
    "Decision",
    "1D %",
    "Overnight Bias",
    "RSI14",
    "Pullback Risk",
    "Trade Score",
    "Setup",
    "Preferred Vehicle",
    "Buy Zone Low",
    "Buy Zone High",
    "Chase Limit",
    "Stop",
    "Sell Zone 1",
    "Sell Zone 2",
    "Level Logic",
    "Money In",
    "Money Out",
    "Flow Status",
    "Sell-off Risk",
    "Call Score",
    "Put Score",
    "Reasons",
]


def _combine_unique_text(row, columns):
    values = []
    for column in columns:
        value = str(row.get(column, "") or "").strip()
        if value and value.lower() not in {"nan", "none", "—"} and value not in values:
            values.append(value)
    return " • ".join(values) if values else "WAIT"


def prepare_main_decision_frame(frame):
    """Apply only the explicitly requested decision-table changes."""
    if frame is None or frame.empty:
        return pd.DataFrame()

    output = frame.copy()

    # New Stop = average of old Stop and Trailing Stop.
    if "Stop" in output.columns and "Trailing Stop" in output.columns:
        stop = pd.to_numeric(output["Stop"], errors="coerce")
        trailing = pd.to_numeric(output["Trailing Stop"], errors="coerce")
        output["Stop"] = pd.concat([stop, trailing], axis=1).mean(axis=1, skipna=True)

    # Decision must be a real CALL/PUT decision, not concatenated labels.
    output = apply_decisions(output)

    drop_columns = [
        "Extended Price", "Overnight %", "Overnight Confirm",
        "Overnight Updated", "Gap Risk", "Overnight Session",
        "Trailing Stop", "Risk/Share", "Category", "Action", "Signal",
        "ER Date", "ER Guidance", "Source",
    ]
    return output.drop(columns=[c for c in drop_columns if c in output.columns])


THEME_ROOM_COLUMNS = [
    "Ticker", "Price", "Category", "Action", "1D %", "Overnight Bias",
    "RSI14", "Pullback Risk", "Trade Score", "Setup", "Preferred Vehicle",
    "Buy Zone Low", "Buy Zone High", "Chase Limit", "Stop",
    "Sell Zone 1", "Sell Zone 2", "Level Logic", "Money In", "Money Out",
    "Flow Status", "Sell-off Risk", "Call Score", "Put Score", "Signal",
    "Reasons",
]


def prepare_theme_room_frame(frame):
    """Theme Rooms keeps Category and Action as separate leading columns."""
    if frame is None or frame.empty:
        return pd.DataFrame()

    output = frame.copy()
    if "Stop" in output.columns and "Trailing Stop" in output.columns:
        stop = pd.to_numeric(output["Stop"], errors="coerce")
        trailing = pd.to_numeric(output["Trailing Stop"], errors="coerce")
        output["Stop"] = pd.concat([stop, trailing], axis=1).mean(axis=1, skipna=True)

    drop_columns = [
        "Extended Price", "Overnight %", "Overnight Confirm",
        "Overnight Updated", "Gap Risk", "Overnight Session",
        "Trailing Stop", "Risk/Share", "ER Date", "ER Guidance", "Source",
    ]
    output = output.drop(columns=[c for c in drop_columns if c in output.columns])

    leading = [c for c in ["Ticker", "Price", "Category", "Action"] if c in output.columns]
    remaining = [c for c in output.columns if c not in leading]
    return output[leading + remaining]


def _display_value(column, value):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"

    money_columns = {
        "Price", "Extended Price", "Buy Zone Low", "Buy Zone High", "Chase Limit", "Stop",
        "Sell Zone 1", "Sell Zone 2", "Trailing Stop", "Risk/Share",
    }
    percent_columns = {"1D %", "Overnight %", "Premarket %", "After Hours %", "Pullback Risk", "Sell-off Risk"}
    one_decimal_columns = {
        "RSI14", "Trade Score", "Money In", "Money Out",
        "Call Score", "Put Score",
    }

    try:
        number = float(value)
        if column in money_columns:
            return f"${number:,.2f}"
        if column in percent_columns:
            return f"{number:+.1f}%" if column in {"1D %", "Overnight %", "Premarket %", "After Hours %"} else f"{number:.1f}%"
        if column in one_decimal_columns:
            return f"{number:.1f}"
    except Exception:
        pass

    return str(value)


def sticky_fast_picks_html(frame):
    if frame is None or frame.empty:
        return "<div>Không có dữ liệu.</div>"

    columns = [column for column in FAST_PICK_COLUMNS if column in frame.columns]
    data = frame[columns].copy()

    header_cells = "".join(
        f"<th>{html.escape(str(column))}</th>" for column in columns
    )

    body_rows = []
    for _, row in data.iterrows():
        cells = []
        for index, column in enumerate(columns):
            value = _display_value(column, row.get(column))
            css_class = "ticker-cell" if index == 0 else ""
            cells.append(
                f'<td class="{css_class}">{html.escape(value)}</td>'
            )
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    return f"""
    <style>
      :root {{
        color-scheme: dark;
      }}
      html, body {{
        margin: 0;
        padding: 0;
        background: transparent;
        font-family: Arial, sans-serif;
      }}
      .atlas-table-wrap {{
        width: 100%;
        height: 650px;
        overflow: auto;
        border: 1px solid #303744;
        border-radius: 10px;
        background: #0e131b;
        -webkit-overflow-scrolling: touch;
      }}
      table {{
        border-collapse: separate;
        border-spacing: 0;
        min-width: 2900px;
        width: max-content;
        color: #f3f5f8;
        font-size: 13px;
      }}
      th, td {{
        padding: 10px 12px;
        border-right: 1px solid #303744;
        border-bottom: 1px solid #303744;
        white-space: nowrap;
        text-align: left;
        background: #0e131b;
      }}
      thead th {{
        position: sticky;
        top: 0;
        z-index: 10;
        background: #1a202b;
        color: #b9c4d3;
        font-weight: 700;
      }}
      thead th:first-child {{
        left: 0;
        z-index: 30;
        background: #202938;
        min-width: 76px;
      }}
      tbody td:first-child {{
        position: sticky;
        left: 0;
        z-index: 20;
        min-width: 76px;
        background: #151d29;
        color: #ffffff;
        font-weight: 800;
        box-shadow: 2px 0 0 #3a4555;
      }}
      tbody tr:hover td {{
        background: #172131;
      }}
      tbody tr:hover td:first-child {{
        background: #223047;
      }}
      @media (max-width: 700px) {{
        .atlas-table-wrap {{
          height: 560px;
        }}
        table {{
          font-size: 12px;
        }}
        th, td {{
          padding: 9px 10px;
        }}
      }}
    </style>
    <div class="atlas-table-wrap">
      <table>
        <thead><tr>{header_cells}</tr></thead>
        <tbody>{"".join(body_rows)}</tbody>
      </table>
    </div>
    """


def compact_status_strip(items):
    """Render important-but-secondary HOME metrics in a compact row."""
    cards = []
    for label, value in items:
        cards.append(
            '<div class="atlas-mini-card">'
            f'<div class="atlas-mini-label">{html.escape(str(label))}</div>'
            f'<div class="atlas-mini-value">{html.escape(str(value))}</div>'
            '</div>'
        )

    st.markdown(
        """
        <style>
          .atlas-mini-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 8px;
            margin: 4px 0 10px 0;
          }
          .atlas-mini-card {
            border: 1px solid #2c3441;
            border-radius: 8px;
            background: #111720;
            padding: 8px 10px;
            min-height: 52px;
          }
          .atlas-mini-label {
            color: #9da8b7;
            font-size: 0.72rem;
            line-height: 1.05rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          .atlas-mini-value {
            color: #f5f7fa;
            font-size: 1.02rem;
            line-height: 1.3rem;
            font-weight: 700;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          @media (max-width: 760px) {
            .atlas-mini-grid {
              grid-template-columns: repeat(2, minmax(0, 1fr));
            }
          }
        </style>
        <div class="atlas-mini-grid">""" + "".join(cards) + "</div>",
        unsafe_allow_html=True,
    )


def prepare_option_shortlist(opportunities, option_budget):
    """Create the actionable option shortlist used on HOME."""
    if opportunities is None or opportunities.empty:
        return pd.DataFrame()

    enriched = prepare_main_decision_frame(enrich_earnings(opportunities))
    if "Days to ER" in enriched.columns:
        enriched = enriched[
            enriched["Days to ER"].isna() | (enriched["Days to ER"] > 2)
        ].reset_index(drop=True)

    if "Decision" not in enriched.columns:
        return pd.DataFrame()

    actionable = enriched[
        enriched["Decision"].isin(
            ["BUY CALL", "WATCH CALL", "BUY PUT", "WATCH PUT"]
        )
    ].copy()

    top = actionable.head(10)
    if top.empty:
        return pd.DataFrame()

    contracts = shortlist_contracts(
        top,
        "Ngày mai",
        option_budget,
        limit=min(10, len(top)),
        lotto_mode=False,
    )
    contracts = fill_option_signals(contracts, enriched)
    return compact_numbers(contracts)


def render_option_shortlist(opportunities, option_budget, table_height=430):
    """Render Option Shortlist at the top of HOME."""
    st.markdown("### 🎯 Option Shortlist")
    st.caption(
        "Danh sách CALL/PUT ưu tiên từ snapshot mới nhất. "
        "Bảng này được đưa lên HOME để xem ngay khi mở ATLAS."
    )

    contracts = prepare_option_shortlist(opportunities, option_budget)
    option_columns = [
        "Ticker", "Signal", "Expiration", "Stock Price", "Strike",
        "Bid", "Ask", "Premium", "Delta", "Theta/day", "IV",
        "Volume", "OI", "Contract Score", "Stock Confidence",
    ]

    if contracts.empty:
        st.info(
            "Chưa có contract đạt đủ điều kiện thanh khoản/ngân sách "
            "trong snapshot hiện tại."
        )
        return

    option_columns = [
        column for column in option_columns if column in contracts.columns
    ]
    show_global_table(
        contracts[option_columns],
        height=table_height,
        sticky_columns=("Ticker",),
    )


with st.sidebar:
    st.header("Thiết lập")
    st.text_area(
        "Watchlist",
        key="watchlist_editor",
        height=240,
        on_change=persist_watchlist,
        help=(
            "Thêm ticker bằng dấu phẩy. Danh sách tự lưu vào URL sau khi "
            "bạn nhấn Enter hoặc rời khỏi ô nhập."
        ),
    )
    symbols = parse_symbols(st.session_state.get("watchlist_editor", "")) or DEFAULT.copy()
    st.caption(f"Đã lưu {len(symbols)} mã trong URL của app.")
    st.button(
        "Khôi phục Master Watchlist",
        use_container_width=True,
        on_click=restore_master_watchlist,
    )

    st.markdown("#### Thêm mã nhanh")
    st.text_input(
        "Ticker mới",
        key="mobile_ticker_input",
        placeholder="Ví dụ: SPCX hoặc AMD, AVGO",
        label_visibility="collapsed",
    )
    st.button(
        "➕ ADD TICKER",
        use_container_width=True,
        on_click=add_ticker_mobile,
    )

    if st.session_state.get("mobile_add_status"):
        st.caption(st.session_state["mobile_add_status"])

    if parse_symbols(_query_watchlist_value()) and parse_symbols(_query_watchlist_value()) != DEFAULT:
        st.info(
            "Watchlist tùy chỉnh đang được lưu. Khi Background Snapshot đã cấu hình, "
            "BOT chạy nền sẽ tự đọc cùng danh sách này."
        )
    benchmark = st.selectbox(
        "Benchmark", ["QQQ","SPY","SMH"], index=0,
        key="benchmark_selector",
    )
    default_watch = [x for x in ["PANW","GOOGL","META","NBIS","TSM","NVDA","CRM","INTC"] if x in symbols]
    personal_watch = st.multiselect("Watch Engine", symbols, default=default_watch)
    option_budget = st.number_input(
        "Ngân sách option mặc định ($)",
        min_value=50.0,
        value=1000.0,
        step=50.0,
    )
    sync_message = st.session_state.get("watchlist_sync_status")
    if sync_message:
        st.caption(sync_message)

    status = online_status()
    if status.get("online"):
        st.success("🟢 Data online")
    else:
        st.error("🔴 Data offline")
    if st.button("Clear cache"):
        st.cache_data.clear()
        st.rerun()


tabs = st.tabs([
    "HOME",
    "FAST PICKS",
    "ATLAS BOT",
    "Sector Rotation",
    "Theme Rooms",
    "Trade Plan",
    "Top CALL / PUT",
    "FLOW RADAR",
    "Watch Engine",
    "AI SEMI ONLY",
    "System Health",
    "Earnings 14D",
])

@st.fragment(run_every="60s")
def atlas_snapshot_auto_refresh():
    """Poll Supabase every 60 seconds and rerun only when snapshot changes."""
    if not snapshot_configured():
        return
    try:
        payload = load_snapshot()
        new_updated_at = payload.get("_snapshot_updated_at") if payload else None
        current_updated_at = st.session_state.get("snapshot_updated_at")
        if new_updated_at and new_updated_at != current_updated_at:
            st.session_state["snapshot_updated_at"] = new_updated_at
            st.rerun()
    except Exception as exc:
        st.session_state["snapshot_poll_error"] = str(exc)


atlas_snapshot_auto_refresh()



def run_full_scan():
    scan = scan_universe(symbols, benchmark)
    rotation = build_theme_rotation(scan)
    opportunities = rank_opportunities(scan)
    signals = build_signal_tables(scan)
    calls, puts = signals
    board = pd.concat([calls, puts], ignore_index=True, sort=False)
    st.session_state["scan"] = scan
    st.session_state["rotation"] = rotation
    st.session_state["opportunities"] = opportunities
    st.session_state["signal_board"] = board
    st.session_state["feed"] = make_feed(scan, rotation)
    st.session_state["bot_alerts"] = build_bot_alerts(scan, rotation)
    st.session_state["scan_time"] = sj_now().strftime("%Y-%m-%d %I:%M:%S %p %Z")


with tabs[0]:
    st.subheader("🏠 ATLAS HOME")

    # Bảng 1: Option Shortlist luôn được ưu tiên ở đầu HOME.
    home_opportunities = st.session_state.get("opportunities", pd.DataFrame())
    render_option_shortlist(
        home_opportunities,
        option_budget,
        table_height=430,
    )

    # Snapshot-first startup. Never run a direct 88-ticker scan on app open.
    if "atlas_snapshot_boot_attempted" not in st.session_state:
        st.session_state["atlas_snapshot_boot_attempted"] = True
        if snapshot_configured():
            loaded = load_background_snapshot_into_session()
            st.session_state["atlas_snapshot_boot_loaded"] = bool(loaded)
        else:
            st.session_state["atlas_snapshot_boot_loaded"] = False

    scan = st.session_state.get("scan", pd.DataFrame())
    rotation = st.session_state.get("rotation", pd.DataFrame())
    opportunities = st.session_state.get("opportunities", pd.DataFrame())

    scan_now = scan
    opportunities_now = opportunities
    requested_count = int(
        st.session_state.get("snapshot_watchlist_count", len(symbols))
    )
    scanned_count = int(
        st.session_state.get("snapshot_scanned_count", len(scan_now))
    )
    qualified_count = int(
        st.session_state.get("snapshot_qualified_count", len(opportunities_now))
    )
    hidden_count = int(
        st.session_state.get(
            "snapshot_hidden_count",
            max(0, scanned_count - qualified_count),
        )
    )
    failed_count = int(
        st.session_state.get(
            "snapshot_failed_count",
            max(0, requested_count - scanned_count),
        )
    )

    if scan.empty:
        if snapshot_configured():
            error_text = st.session_state.get("snapshot_error", "")
            if error_text:
                st.error(
                    "Không đọc được Background Snapshot từ Supabase. "
                    f"Chi tiết: {error_text}"
                )
            else:
                st.warning(
                    "Snapshot chưa có dữ liệu hợp lệ. "
                    "Hãy chạy lại GitHub Action ATLAS Background Scanner."
                )
        else:
            st.warning(
                "Streamlit Secrets chưa có SUPABASE_URL và SUPABASE_KEY. "
                "ATLAS không quét trực tiếp để tránh chờ lâu trên điện thoại."
            )
    else:
        # Bảng 2: Top Opportunities nằm ngay sau Option Shortlist.
        st.markdown("### 🔥 Top Opportunities")
        if opportunities.empty:
            st.warning("Không có setup đạt chuẩn A/B. Không ép giao dịch.")
        else:
            cols = [
                "Ticker", "Action", "Opportunity Score", "Price",
                "Money In", "Money Out", "Net Flow", "MTF Score",
                "Pullback Risk", "Sell-off Risk", "Reasons",
            ]
            show_global_table(
                opportunities[[c for c in cols if c in opportunities.columns]],
                height=500,
                sticky_columns=("Ticker",),
            )

        # Thông tin phụ chuyển xuống cuối HOME.
        st.divider()
        st.markdown("### System & Market Overview")

        now = sj_now()
        compact_status_strip([
            ("San Jose", now.strftime("%I:%M:%S %p")),
            ("Market mode", market_mode(now)),
            ("Watchlist", len(symbols)),
            ("Last scan", st.session_state.get("scan_time", "Never")),
        ])

        if st.session_state.get("loaded_background_snapshot"):
            st.success(
                "Background Snapshot đang hoạt động. "
                "App đang đọc kết quả đã quét sẵn."
            )
        elif not snapshot_configured():
            st.warning(
                "Background Snapshot chưa cấu hình. "
                "Hiện app vẫn phải quét trực tiếp."
            )

        compact_status_strip([
            ("Yêu cầu quét", requested_count),
            ("Đã phân tích", scanned_count),
            ("Đủ chuẩn", qualified_count),
            ("Ẩn / lỗi", hidden_count + failed_count),
        ])
        st.caption(
            "Top Opportunities chỉ hiện mã vượt bộ lọc. "
            "Các mã còn lại vẫn được quét nhưng không đủ chuẩn để khuyến nghị."
        )

        pulse = market_pulse(scan)
        compact_status_strip([
            ("Regime", pulse.get("Regime")),
            ("Market Pulse", f"{pulse.get('Market Pulse',0):.0f}"),
            ("Risk", f"{pulse.get('Risk Level',0):.0f}"),
            ("Breadth", f"{pulse.get('Breadth Up %',0):.0f}%"),
        ])
        st.info(build_market_narrative(scan, rotation))



with tabs[1]:
    st.subheader("⚡ FAST PICKS — quét toàn bộ list, chỉ hiện mã đủ chuẩn")
    # FAST PICKS reads the latest background snapshot only.
    if st.session_state.get("scan", pd.DataFrame()).empty and snapshot_configured():
        load_background_snapshot_into_session()

    opportunities = st.session_state.get("opportunities", pd.DataFrame())
    if opportunities.empty:
        st.info("Chưa có dữ liệu hoặc không có setup đủ chuẩn.")
    else:
        enriched = prepare_main_decision_frame(enrich_earnings(opportunities))
        if "Days to ER" in enriched.columns:
            enriched = enriched[
                enriched["Days to ER"].isna() | (enriched["Days to ER"] > 2)
            ].reset_index(drop=True)

        st.caption(
            "Kéo ngang để xem thêm cột. Chỉ Ticker được giữ cố định khi kéo ngang."
        )
        fast_display = enriched[[
            c for c in FAST_PICK_COLUMNS if c in enriched.columns
        ]]
        show_global_table(
            fast_display,
            height=650,
            sticky_columns=("Ticker",),
        )



with tabs[2]:
    st.subheader("🤖 ATLAS BOT")
    scan = st.session_state.get("scan", pd.DataFrame())
    rotation = st.session_state.get("rotation", pd.DataFrame())
    if scan.empty:
        st.info("ATLAS đang chờ dữ liệu quét tự động.")
    else:
        st.session_state["bot_alerts"] = build_bot_alerts(scan, rotation)
        alerts = st.session_state.get("bot_alerts", [])
        summary = bot_summary(alerts)
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Alerts", summary["Total"])
        c2.metric("Bullish", summary["Bullish"])
        c3.metric("Warnings", summary["Warnings"])
        c4.metric("Bearish", summary["Bearish"])
        for event in alerts:
            text = f"**{event['time']} — {event['title']}**\n\n{event['detail']}"
            if event["kind"] == "good":
                st.success(text)
            elif event["kind"] == "bad":
                st.error(text)
            else:
                st.warning(text)


with tabs[7]:
    st.subheader("📅 Earnings Radar — 14 ngày")
    st.caption(
        "Tự động chỉ hiện mã có ER trong 14 ngày. "
        "Không cần chọn hàng chục ticker bằng các ô đỏ."
    )

    frame = st.session_state.get("earnings_14d", pd.DataFrame()).copy()

    if frame.empty:
        st.info(
            "Snapshot hiện tại chưa có mã ER trong 14 ngày, hoặc lịch ER chưa "
            "được tạo. Chạy lại GitHub Background Scanner sau khi cập nhật."
        )
    else:
        display_columns = [
            "Ticker", "ER Date", "Days to ER", "Timing",
            "ER Guidance", "Source",
        ]
        display_columns = [c for c in display_columns if c in frame.columns]

        e1, e2, e3 = st.columns(3)
        e1.metric("ER trong 14 ngày", len(frame))
        e2.metric(
            "Trong 7 ngày",
            int(
                (
                    pd.to_numeric(frame["Days to ER"], errors="coerce") <= 7
                ).sum()
            ) if "Days to ER" in frame.columns else 0,
        )
        e3.metric(
            "Lỗi nguồn lịch",
            int(st.session_state.get("earnings_failure_count", 0)),
        )

        show_global_table(
            frame[display_columns],
            height=520,
            sticky_columns=("Ticker",),
        )

        st.warning(
            "Trade thường: tránh giữ option xuyên ER. "
            "ER Lotto chỉ dùng số tiền chấp nhận mất toàn bộ."
        )


with tabs[3]:
    st.subheader("Sector Rotation")
    rotation = st.session_state.get("rotation", pd.DataFrame())
    if rotation.empty:
        st.info("ATLAS đang chờ dữ liệu quét tự động.")
    else:
        st.dataframe(style_table(rotation), hide_index=True, use_container_width=True, height=620)


with tabs[4]:
    st.subheader("Theme Rooms")
    scan = st.session_state.get("scan", pd.DataFrame())
    theme = st.selectbox("Theme", list(THEMES), key="theme_room")

    if scan.empty:
        st.info("ATLAS đang chờ dữ liệu snapshot.")
    else:
        room = scan[scan["Ticker"].isin(THEMES[theme])].copy()

        if room.empty:
            st.warning("Không có dữ liệu cho theme này.")
        else:
            sort_columns = [
                column for column in ["Trade Score", "Net Flow"]
                if column in room.columns
            ]
            if sort_columns:
                room = room.sort_values(
                    sort_columns,
                    ascending=[False] * len(sort_columns),
                )

            room = prepare_theme_room_frame(enrich_earnings(room))
            room_columns = [
                column for column in THEME_ROOM_COLUMNS
                if column in room.columns
            ]

            st.caption(
                "Chỉ hiện bảng quyết định đã tinh gọn; "
                "không hiện ATR, EMA, CMF hay Gap thô."
            )
            show_global_table(
                room[room_columns],
                height=560,
                sticky_columns=("Ticker",),
            )


with tabs[5]:
    st.subheader("Trade Plan — Signal Fusion hợp nhất")
    scan = st.session_state.get("scan", pd.DataFrame())
    snapshot_symbols = scan["Ticker"].tolist() if not scan.empty else []
    options = list(dict.fromkeys(symbols + snapshot_symbols))
    ticker = st.selectbox("Ticker", options, key="unified_plan_ticker")

    if ticker not in snapshot_symbols:
        st.info(
            f"{ticker}: PENDING FIRST SCAN — worker sẽ ưu tiên mã này "
            "ở chu kỳ kế tiếp."
        )

    horizon = st.selectbox(
        "Horizon",
        [
            "Day trade",
            "Ngày mai",
            "Swing 3–5 ngày",
            "Swing 1–2 tuần",
            "Swing 2–3 tháng",
        ],
        index=1,
        key="unified_plan_horizon",
    )

    daily = get_daily(ticker)
    intraday = get_intraday(ticker)
    benchmark_df = get_daily(benchmark)
    base, mtf = analyze_symbol(ticker, daily, intraday, benchmark_df, 50.0)
    flow = money_flow_metrics(daily, intraday)
    price_context = get_latest_session_quote(ticker)

    if base and flow:
        base.update(flow)
        plan = build_trade_plan(
            ticker,
            daily,
            base,
            mtf,
            horizon,
            price_context=price_context,
        )
        fusion = signal_fusion(base, flow, plan, {})
        retest = analyze_retest(daily, base)

        # Keep the full Signal Fusion information, then the concrete plan.
        components.html(
            signal_fusion_html(ticker, plan, fusion, retest, base, flow),
            height=760,
            scrolling=True,
        )
        components.html(
            trade_plan_html(plan),
            height=1320,
            scrolling=True,
        )

        frame, label = select_chart_frame(daily, intraday, "4H")
        if not frame.empty:
            st.plotly_chart(
                make_analysis_chart(
                    frame,
                    f"{ticker} — {label}",
                    bars=180,
                    show_vwap=True,
                ),
                use_container_width=True,
            )
    else:
        st.warning("Không đủ dữ liệu để xây dựng Trade Plan.")


with tabs[6]:
    st.subheader("Top CALL / PUT")
    scan = st.session_state.get("scan", pd.DataFrame())

    if scan.empty:
        st.info("ATLAS đang chờ dữ liệu quét tự động.")
    else:
        calls, puts = build_signal_tables(scan)
        call_watch, put_watch = build_signal_watch(scan)

        st.info(signal_methodology_text())

        left, right = st.columns(2)
        with left:
            st.markdown("### 🟢 CALL CONFIRMED")
            if calls.empty:
                st.info("Không có CALL được xác nhận trong lần quét này.")
            else:
                show_global_table(
                    calls,
                    height=380,
                    sticky_columns=("Ticker",),
                )

            st.markdown("#### 🟡 CALL WATCH — gần đủ điều kiện")
            if call_watch.empty:
                st.caption("Không có CALL near-miss đáng theo dõi.")
            else:
                show_global_table(
                    call_watch,
                    height=330,
                    sticky_columns=("Ticker",),
                )

        with right:
            st.markdown("### 🔴 PUT CONFIRMED")
            if puts.empty:
                bearish_count = int(
                    (
                        (scan.get("Money Out", pd.Series(dtype=float)) >
                         scan.get("Money In", pd.Series(dtype=float)))
                        & (scan.get("Net Flow", pd.Series(dtype=float)) < 0)
                    ).sum()
                ) if not scan.empty else 0
                st.info(
                    "Không có PUT được xác nhận. "
                    f"Có {bearish_count} mã có dấu hiệu yếu nhưng chưa vượt đủ bộ lọc."
                )
            else:
                show_global_table(
                    puts,
                    height=380,
                    sticky_columns=("Ticker",),
                )

            st.markdown("#### 🟠 PUT WATCH — chờ breakdown")
            if put_watch.empty:
                st.caption(
                    "Không có PUT near-miss. Không nên ép mua PUT khi chưa có breakdown."
                )
            else:
                show_global_table(
                    put_watch,
                    height=330,
                    sticky_columns=("Ticker",),
                )

        with st.expander("ATLAS đang dựa vào đâu?"):
            st.markdown(
                """
**Nguồn miễn phí hiện tại**

- Giá và volume công khai qua Yahoo/yfinance.
- Khung intraday 5 phút, hourly và daily khi dữ liệu có.
- RSI, EMA, ATR, đa khung, vị trí trong range.
- Money In/Out và Net Flow là **proxy từ giá–volume**.
- Pullback Risk, Sell-off Risk và Sector Rotation.
- Earnings trong 14 ngày.

**Không phải option flow thật**

CALL Score và PUT Score không chứng minh cá mập đang BUY TO OPEN.
Hệ thống chưa biết chắc giao dịch là opening, closing, hedge hay spread.
                """
            )



with tabs[7]:
    st.subheader("🌊 FLOW RADAR — Notable Option Activity")
    st.caption(
        "Được tính bởi GitHub Background Scanner và đọc từ snapshot. "
        "Không quét option chain khi bạn mở iPhone."
    )

    st.warning(
        "Dữ liệu miễn phí không xác định chắc BUY TO OPEN, SELL TO OPEN, "
        "sweep, block hay multi-leg. Overnight là Yahoo extended-hours proxy, không phải tape 24 giờ đầy đủ. Premium là proxy = Volume × midpoint × 100; "
        "không phải tổng premium khớp chính xác."
    )

    flow_radar = st.session_state.get("flow_radar", pd.DataFrame())

    if flow_radar.empty:
        flow_status = st.session_state.get("flow_radar_status", {}) or {}
        status_message = flow_status.get(
            "message",
            "Snapshot chưa có Flow Radar.",
        )

        d1, d2, d3 = st.columns(3)
        d1.metric(
            "Primary symbols",
            int(flow_status.get("attempted_primary", 0)),
        )
        d2.metric(
            "Fallback symbols",
            int(flow_status.get("attempted_fallback", 0)),
        )
        d3.metric(
            "Contracts found",
            int(flow_status.get("contracts_found", 0)),
        )

        st.info(status_message)
        st.caption(
            "Nếu cả Primary và Fallback đều bằng 0, snapshot vẫn là bản cũ. "
            "Nếu đã thử mã nhưng Contracts found = 0, nguồn option chain hoặc "
            "bộ lọc thanh khoản chưa tìm thấy hợp đồng phù hợp."
        )
    else:
        minimum_score = st.slider(
            "Minimum Flow Score",
            min_value=40,
            max_value=90,
            value=62,
            step=1,
            key="flow_radar_min_score",
        )
        alignment_filter = st.multiselect(
            "Alignment",
            ["ALIGNED", "UNCONFIRMED", "CONFLICT / HEDGE RISK"],
            default=["ALIGNED", "UNCONFIRMED"],
            key="flow_alignment_filter",
        )

        filtered_flow = flow_radar[
            (pd.to_numeric(flow_radar["Flow Score"], errors="coerce") >= minimum_score)
            & (flow_radar["Alignment"].isin(alignment_filter))
        ].copy()

        f1, f2, f3, f4 = st.columns(4)
        f1.metric("Contracts", len(filtered_flow))
        f2.metric(
            "CALL activity",
            int((filtered_flow.get("Side", pd.Series(dtype=str)) == "CALL").sum()),
        )
        f3.metric(
            "PUT activity",
            int((filtered_flow.get("Side", pd.Series(dtype=str)) == "PUT").sum()),
        )
        f4.metric(
            "Aligned",
            int((filtered_flow.get("Alignment", pd.Series(dtype=str)) == "ALIGNED").sum()),
        )

        flow_columns = [
            "Ticker", "Side", "Contract", "Flow Score", "Alignment",
            "Chart Bias", "Overnight %", "Overnight Bias", "Overnight Confirm",
            "Gap Risk", "Premium Proxy", "Volume", "OI", "Vol/OI",
            "Spread %", "IV %", "Delta", "DTE", "Moneyness %",
            "Interpretation", "Trigger", "Invalidation", "Execution",
        ]
        flow_columns = [c for c in flow_columns if c in filtered_flow.columns]

        if filtered_flow.empty:
            st.info("Không có hợp đồng vượt bộ lọc hiện tại.")
        else:
            # Keep every original contract and column, but group contracts from
            # the same ticker together. Repeated ticker labels are hidden so
            # NVDA, SPY, AVGO... read as clear visual groups.
            grouped_flow = filtered_flow.copy()

            sort_columns = [
                column for column in ["Ticker", "Flow Score", "DTE", "Contract"]
                if column in grouped_flow.columns
            ]
            ascending = [
                True if column == "Ticker" else False
                for column in sort_columns
            ]
            if sort_columns:
                grouped_flow = grouped_flow.sort_values(
                    sort_columns,
                    ascending=ascending,
                    kind="stable",
                ).reset_index(drop=True)

            display_flow = grouped_flow[flow_columns].copy()
            if "Ticker" in display_flow.columns:
                duplicate_ticker = display_flow["Ticker"].eq(
                    display_flow["Ticker"].shift()
                )
                display_flow.loc[duplicate_ticker, "Ticker"] = ""

            show_global_table(
                display_flow,
                height=650,
                sticky_columns=("Ticker",),
            )

        with st.expander("Cách ATLAS chấm Flow Score"):
            st.markdown(
                """
- **Premium Proxy:** quy mô hoạt động ước tính.
- **Volume/OI:** volume hôm nay có bất thường so với vị thế mở hay không.
- **Liquidity:** OI + volume và spread.
- **Delta relevance:** ưu tiên hợp đồng có khả năng phản ứng thực tế, không quá xa OTM.
- **Technical alignment:** CALL phải đồng thuận chart bullish; PUT phải đồng thuận chart bearish.
- **Conflict/Hedge Risk:** flow đi ngược chart có thể là hedge, closing hoặc một chân của spread.
- ATLAS chỉ đề xuất **chờ trigger**, không mua theo premium lớn một cách tự động.
                """
            )



with tabs[7]:
    st.subheader("Watch Engine")
    scan = st.session_state.get("scan", pd.DataFrame())
    watch = build_watch_actions(scan, personal_watch)
    if watch.empty:
        st.info("ATLAS đang chờ dữ liệu quét tự động.")
    else:
        show_global_table(
            watch,
            height=560,
            sticky_columns=("Ticker",),
        )



with tabs[7]:
    st.subheader("🧠 AI SEMI ONLY — CALL / PUT COMMAND CENTER")
    st.caption(
        "Chỉ phân tích nhóm AI–Semiconductor. "
        "ATLAS không ép PUT chỉ vì CALL chưa đạt; khi thiếu xác nhận sẽ ghi WAIT."
    )

    scan = st.session_state.get("scan", pd.DataFrame())
    if scan.empty:
        st.info("ATLAS đang chờ dữ liệu quét tự động.")
    else:
        semi_frame = build_semi_dashboard(scan)
        summary = semi_market_summary(semi_frame)

        s1, s2, s3, s4, s5 = st.columns(5)
        s1.metric("SEMI Bias", summary["bias"])
        s2.metric("CALL confirmed", summary["call_count"])
        s3.metric("PUT confirmed", summary["put_count"])
        s4.metric("WAIT", summary["wait_count"])
        s5.metric("Leader / Weakest", f"{summary['leader']} / {summary['weakest']}")

        if semi_frame.empty:
            st.warning(
                "Không có dữ liệu nhóm Semi trong snapshot hiện tại. "
                "Hãy bảo đảm watchlist có SMH, SOXX và các ticker bán dẫn."
            )
        else:
            display_cols = [
                "Ticker", "Decision", "CALL %", "PUT %", "WAIT %",
                "Price", "Money In", "Money Out", "Net Flow", "MTF Score",
                "Pullback Risk", "Sell-off Risk", "Call Score", "Put Score",
                "Reason",
            ]
            show_global_table(
                semi_frame[display_cols],
                height=560,
                sticky_columns=("Ticker",),
            )

            st.markdown("### Kế hoạch chi tiết")
            selected_ticker = st.selectbox(
                "Chọn mã Semi",
                semi_frame["Ticker"].tolist(),
                key="semi_plan_ticker",
            )
            horizon = st.selectbox(
                "Khung kế hoạch",
                ["Day trade", "Ngày mai", "Swing 3–5 ngày", "Swing 1–2 tuần"],
                index=1,
                key="semi_plan_horizon",
            )

            selected_row = scan[scan["Ticker"] == selected_ticker].head(1)
            semi_signal = semi_frame[
                semi_frame["Ticker"] == selected_ticker
            ].iloc[0]

            if selected_row.empty:
                st.warning("Không tìm thấy dữ liệu chi tiết cho ticker.")
            else:
                daily = get_daily(selected_ticker)
                intraday = get_intraday(selected_ticker)
                benchmark_df = get_daily(benchmark)
                base, mtf = analyze_symbol(
                    selected_ticker,
                    daily,
                    intraday,
                    benchmark_df,
                    50.0,
                )
                flow = money_flow_metrics(daily, intraday)

                if base and flow:
                    base.update(flow)
                    plan = build_trade_plan(
                        selected_ticker,
                        daily,
                        base,
                        mtf,
                        horizon,
                    )

                    p1, p2, p3, p4 = st.columns(4)
                    p1.metric("Decision", semi_signal["Decision"])
                    p2.metric("CALL probability", f"{semi_signal['CALL %']:.1f}%")
                    p3.metric("PUT probability", f"{semi_signal['PUT %']:.1f}%")
                    p4.metric("WAIT probability", f"{semi_signal['WAIT %']:.1f}%")

                    if semi_signal["Decision"] == "CALL":
                        st.success(
                            "CALL chỉ hợp lệ khi giá giữ vùng entry hoặc breakout "
                            "có volume xác nhận. Mất stop thì hủy CALL."
                        )
                    elif semi_signal["Decision"] == "PUT":
                        st.error(
                            "PUT chỉ hợp lệ khi breakdown và retest thất bại. "
                            "Vượt invalidation/stop thì hủy PUT."
                        )
                    else:
                        st.warning(
                            "WAIT: bias hiện tại chưa đủ để vào lệnh. "
                            "Không chuyển sang hướng ngược lại chỉ vì một phía chưa đạt."
                        )

                    components.html(
                        trade_plan_html(plan),
                        height=1180,
                        scrolling=True,
                    )
                else:
                    st.warning("Không đủ dữ liệu để tạo kế hoạch.")




with tabs[7]:
    st.subheader("🩺 System Health — Always-On Scanner")

    freshness = snapshot_freshness(
        st.session_state.get("snapshot_updated_at")
        or st.session_state.get("scanner_finished_at_utc")
    )
    scanner_status = st.session_state.get("scanner_status", {}) or {}
    flow_status = st.session_state.get("flow_radar_status", {}) or {}
    providers = st.session_state.get("data_provider_status", {}) or {}

    h1, h2, h3, h4 = st.columns(4)
    h1.metric(
        "Snapshot",
        freshness.get("status", "UNKNOWN"),
        "—" if freshness.get("age_minutes") is None
        else f"{freshness['age_minutes']} min old",
    )
    h2.metric(
        "Scanner",
        scanner_status.get("status", "UNKNOWN"),
        f"{scanner_status.get('coverage_pct', 0)}% coverage",
    )
    h3.metric(
        "Flow contracts",
        scanner_status.get(
            "flow_contract_count",
            flow_status.get("contracts_found", 0),
        ),
    )
    h4.metric(
        "Duration",
        "—" if st.session_state.get("scanner_duration_seconds") is None
        else f"{st.session_state['scanner_duration_seconds']}s",
    )

    if freshness.get("status") == "FRESH":
        st.success(
            "Snapshot đang mới. iPhone có thể dùng dữ liệu đã tính sẵn."
        )
    elif freshness.get("status") == "DELAYED":
        st.warning(
            "GitHub có thể đang trễ. Không xem các con số là real-time tuyệt đối."
        )
    elif freshness.get("status") == "STALE":
        st.error(
            "Snapshot đã quá 15 phút. Không dùng Flow/Overnight để vào lệnh "
            "cho đến khi scanner cập nhật lại."
        )
    else:
        st.warning(freshness.get("message", "Không xác định được độ mới."))

    if scanner_status.get("status") == "DEGRADED":
        st.warning(scanner_status.get("message", "Dữ liệu đang thiếu."))
    elif scanner_status.get("status") == "FAILED":
        st.error(scanner_status.get("message", "Scanner thất bại."))
    elif scanner_status.get("status") == "READY":
        st.success(scanner_status.get("message", "Scanner sẵn sàng."))

    st.markdown("### Kiểm chứng con số")
    diagnostics = pd.DataFrame([
        {
            "Metric": "Requested tickers",
            "Value": scanner_status.get("requested_count", 0),
            "Rule": "Danh sách yêu cầu quét",
        },
        {
            "Metric": "Scanned tickers",
            "Value": scanner_status.get("scanned_count", 0),
            "Rule": "Phải đủ coverage",
        },
        {
            "Metric": "Qualified",
            "Value": scanner_status.get("qualified_count", 0),
            "Rule": "Mã vượt bộ lọc",
        },
        {
            "Metric": "Flow contracts",
            "Value": scanner_status.get(
                "flow_contract_count",
                flow_status.get("contracts_found", 0),
            ),
            "Rule": "Phải có Volume/OI/Bid/Ask",
        },
        {
            "Metric": "Failed tickers",
            "Value": scanner_status.get("failed_count", 0),
            "Rule": "Càng thấp càng tốt",
        },
        {
            "Metric": "GitHub Run ID",
            "Value": st.session_state.get("github_run_id", "—"),
            "Rule": "Đối chiếu với Actions",
        },
    ])
    st.dataframe(diagnostics, hide_index=True, use_container_width=True)

    st.markdown("### Nguồn dữ liệu")
    provider_rows = [
        {"Source": "Stocks", "Status": providers.get("stock", "Yahoo Finance")},
        {"Source": "Options", "Status": providers.get("options", "Yahoo option chain")},
        {"Source": "Overnight", "Status": providers.get("overnight", "Yahoo extended-hours proxy")},
        {"Source": "Robinhood 24H", "Status": providers.get(
            "robinhood_24h",
            "NOT CONNECTED — no official public stock API",
        )},
    ]
    st.dataframe(
        pd.DataFrame(provider_rows),
        hide_index=True,
        use_container_width=True,
    )

    st.info(
        "GitHub Actions chạy theo lịch, không phải server 24/7. "
        "Dấu Success chỉ chứng minh job kết thúc; hãy dùng Snapshot age, "
        "coverage và Flow contracts để quyết định dữ liệu có dùng được hay không."
    )

