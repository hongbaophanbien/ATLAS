from __future__ import annotations
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from core import analyze_symbol
from data_provider import daily_history, hourly_history, intraday_5m_history, latest_session_quote
from earnings_engine import earnings_info
from flow_engine import money_flow_metrics, rank_candidate
from opportunity_engine import rank_opportunities
from reliability_engine import data_quality_summary, utc_now_iso
from overnight_engine import overnight_metrics, apply_overnight_adjustment
from option_flow_radar import build_flow_radar
from sector_engine import THEMES, build_theme_rotation
from snapshot_store import frame_to_records, save_snapshot, load_watchlist_settings
from watchlist_bot import build_signal_tables
from atlas_signal_refresh_hotfix import apply_decisions

SAN_JOSE=ZoneInfo("America/Los_Angeles")
DEFAULT = ['AAPL', 'ABBV', 'ADBE', 'ALAB', 'AMD', 'AMAT', 'AMZN', 'ARKX', 'ARM', 'ASML', 'ASTS', 'AVGO', 'BA', 'BAC', 'BE', 'BWXT', 'CAT', 'CCJ', 'CIBR', 'COP', 'CRM', 'CRWD', 'CVX', 'DELL', 'FTNT', 'GLW', 'GOOG', 'GOOGL', 'GS', 'IBM', 'IGV', 'INTC', 'IONQ', 'IWM', 'JNJ', 'JPM', 'KLAC', 'LEU', 'LLY', 'LRCX', 'LUNR', 'META', 'MP', 'MRK', 'MRVL', 'MS', 'MSFT', 'MU', 'NBIS', 'NOW', 'NVDA', 'OKLO', 'OKTA', 'ORCL', 'OXY', 'PANW', 'PLTR', 'POWL', 'QCOM', 'QBTS', 'QQQ', 'QUBT', 'RDW', 'RGTI', 'RKLB', 'SLB', 'SMCI', 'SMH', 'SMR', 'SNDK', 'SOXX', 'SPCX', 'SPY', 'TSLA', 'TSM', 'UNH', 'URA', 'USAR', 'UUUU', 'VRT', 'WDC', 'WFC', 'XLE', 'XLF', 'XLI', 'XLV', 'XOM', 'ZS']

def parse_watchlist():
    try:
        settings = load_watchlist_settings()
        stored = settings.get("watchlist") or []
        if stored:
            output = []
            for ticker in stored:
                ticker = str(ticker).strip().upper()
                if ticker == "SPCX":
                    ticker = "SPCX"
                if ticker and ticker not in output:
                    output.append(ticker)
            if output:
                return output[:120]
    except Exception as exc:
        print(f"Could not load shared watchlist: {exc}")

    raw = os.getenv("ATLAS_WATCHLIST", "")
    if not raw.strip():
        return DEFAULT

    output = []
    for token in raw.replace("\n", ",").split(","):
        token = token.strip().upper()
        if token == "SPCX":
            token = "SPCX"
        if token and token not in output:
            output.append(token)
    return output[:120]

def analyze_one(symbol, benchmark_df):
    daily=daily_history(symbol); intra=intraday_5m_history(symbol)
    if intra.empty: intra=hourly_history(symbol)
    base,_=analyze_symbol(symbol,daily,intra,benchmark_df,50.0)
    flow=money_flow_metrics(daily,intra); rank=rank_candidate(base,flow)
    if base and flow and rank:
        record = {**base, **flow, **rank}
        record.update(overnight_metrics(daily, intra))
        record.update(latest_session_quote(symbol))
        if record.get("Price Used"):
            record["Price"] = record["Price Used"]
        return apply_overnight_adjustment(record)
    return None


def build_earnings_14d(symbols):
    rows = []
    failures = []

    def fetch(ticker):
        try:
            record = earnings_info(ticker) or {}
            record["Ticker"] = ticker
            return record, None
        except Exception as exc:
            return None, f"{ticker}: {exc}"

    with ThreadPoolExecutor(max_workers=min(8, max(2, len(symbols)))) as ex:
        futures = {ex.submit(fetch, ticker): ticker for ticker in symbols}
        for future in as_completed(futures):
            record, error = future.result()
            if error:
                failures.append(error)
            elif record:
                rows.append(record)

    frame = pd.DataFrame(rows)
    if frame.empty or "Days to ER" not in frame.columns:
        return pd.DataFrame(), failures

    frame["Days to ER"] = pd.to_numeric(frame["Days to ER"], errors="coerce")
    frame = frame[
        frame["Days to ER"].notna()
        & (frame["Days to ER"] >= 0)
        & (frame["Days to ER"] <= 14)
    ].copy()

    if not frame.empty:
        frame = frame.sort_values(["Days to ER", "Ticker"]).reset_index(drop=True)

    return frame, failures


def build_flow_with_fallback(scan, opportunities):
    diagnostics = {
        "attempted_primary": 0,
        "attempted_fallback": 0,
        "contracts_found": 0,
        "status": "EMPTY",
        "message": "",
    }

    if scan is None or scan.empty:
        diagnostics["message"] = "Snapshot scan rỗng."
        return pd.DataFrame(), diagnostics

    primary = opportunities if opportunities is not None and not opportunities.empty else scan
    diagnostics["attempted_primary"] = min(12, len(primary))

    radar = build_flow_radar(scan, primary, max_symbols=12)

    if radar is None or radar.empty:
        fallback_order = [
            "SPY", "QQQ", "NVDA", "AMD", "TSLA", "META",
            "AAPL", "AVGO", "MU", "MRVL", "PANW", "CRWD",
        ]
        available = scan[scan["Ticker"].isin(fallback_order)].copy()

        if not available.empty:
            available["_flow_order"] = available["Ticker"].map(
                {ticker: index for index, ticker in enumerate(fallback_order)}
            )
            available = available.sort_values("_flow_order").drop(columns=["_flow_order"])
            diagnostics["attempted_fallback"] = len(available)
            radar = build_flow_radar(scan, available, max_symbols=len(available))

    if radar is not None and not radar.empty:
        diagnostics["contracts_found"] = len(radar)
        diagnostics["status"] = "READY"
        diagnostics["message"] = (
            f"Đã tìm thấy {len(radar)} hợp đồng activity đáng chú ý."
        )
        return radar, diagnostics

    diagnostics["message"] = (
        "Không có hợp đồng vượt bộ lọc thanh khoản/premium hoặc "
        "nguồn option-chain không trả dữ liệu trong lần chạy này."
    )
    return pd.DataFrame(), diagnostics

def main():
    started_monotonic = time.monotonic()
    started_at_utc = utc_now_iso()
    symbols = parse_watchlist()
    try:
        settings = load_watchlist_settings()
    except Exception:
        settings = {}

    benchmark = str(
        settings.get("benchmark") or os.getenv("ATLAS_BENCHMARK", "QQQ")
    ).upper()
    bdf = daily_history(benchmark)
    rows = []
    failures = []

    with ThreadPoolExecutor(max_workers=min(8, max(2, len(symbols)))) as ex:
        futs = {ex.submit(analyze_one, ticker, bdf): ticker for ticker in symbols}
        for future in as_completed(futs):
            ticker = futs[future]
            try:
                row = future.result()
                if row:
                    rows.append(row)
                else:
                    failures.append(ticker)
            except Exception as exc:
                failures.append(ticker)
                print(f"Failed {ticker}: {exc}")

    scan = pd.DataFrame(rows)
    rotation = build_theme_rotation(scan)
    opportunities = apply_decisions(rank_opportunities(scan))
    calls, puts = build_signal_tables(scan)
    board = pd.concat([calls, puts], ignore_index=True, sort=False)
    flow_radar, flow_radar_status = build_flow_with_fallback(
        scan, opportunities
    )
    earnings_14d, earnings_failures = build_earnings_14d(symbols)

    quality = data_quality_summary(
        scan=scan,
        opportunities=opportunities,
        flow_radar=flow_radar,
        failed_count=len(failures),
        requested_count=len(symbols),
    )
    finished_at_utc = utc_now_iso()
    duration_seconds = round(time.monotonic() - started_monotonic, 1)

    payload = {
        "scanner_status": quality,
        "scanner_started_at_utc": started_at_utc,
        "scanner_finished_at_utc": finished_at_utc,
        "scanner_duration_seconds": duration_seconds,
        "github_run_id": os.getenv("GITHUB_RUN_ID", ""),
        "github_run_attempt": os.getenv("GITHUB_RUN_ATTEMPT", ""),
        "github_sha": os.getenv("GITHUB_SHA", ""),
        "github_event_name": os.getenv("GITHUB_EVENT_NAME", ""),
        "data_provider": {
            "stock": "Yahoo Finance",
            "options": "Yahoo option-chain snapshot",
            "overnight": "Yahoo extended-hours proxy",
            "robinhood_24h": "NOT CONNECTED — no official public stock API",
        },
        "scan_time_san_jose": datetime.now(SAN_JOSE).strftime(
            "%Y-%m-%d %I:%M:%S %p %Z"
        ),
        "benchmark": benchmark,
        "watchlist_count": len(symbols),
        "scanned_count": len(scan),
        "qualified_count": len(opportunities),
        "hidden_count": max(0, len(scan) - len(opportunities)),
        "failed_count": len(failures),
        "failed_tickers": failures,
        "watchlist": symbols,
        "scan": frame_to_records(scan),
        "rotation": frame_to_records(rotation),
        "opportunities": frame_to_records(opportunities),
        "signal_board": frame_to_records(board),
        "flow_radar": frame_to_records(flow_radar),
        "flow_radar_status": flow_radar_status,
        "earnings_14d": frame_to_records(earnings_14d),
        "earnings_failure_count": len(earnings_failures),
    }
    save_snapshot(payload)
    print(
        "ATLAS_SNAPSHOT "
        f"status={quality['status']} "
        f"requested={len(symbols)} "
        f"scanned={len(scan)} "
        f"coverage={quality['coverage_pct']}% "
        f"qualified={len(opportunities)} "
        f"flow={len(flow_radar)} "
        f"earnings14d={len(earnings_14d)} "
        f"failed={len(failures)} "
        f"duration={duration_seconds}s"
    )

    if len(scan) == 0:
        raise RuntimeError("Scanner produced zero stock records.")



if __name__ == "__main__":
    main()
