from __future__ import annotations

import pandas as pd

from core import safe_float


def build_watch_actions(scan: pd.DataFrame, watchlist: list[str]) -> pd.DataFrame:
    if scan is None or scan.empty:
        return pd.DataFrame()

    rows = []
    selected = scan[scan["Ticker"].isin(watchlist)].copy()

    for _, row in selected.iterrows():
        ticker = row["Ticker"]
        call_score = safe_float(row.get("Call Score"), 50)
        put_score = safe_float(row.get("Put Score"), 50)
        pullback = safe_float(row.get("Pullback Risk"), 50)
        selloff = safe_float(row.get("Sell-off Risk"), 50)
        money_in = safe_float(row.get("Money In"), 50)
        money_out = safe_float(row.get("Money Out"), 50)

        if call_score >= 68 and money_in >= 62 and pullback <= 58:
            action = "CANH BUY CALL"
        elif call_score >= 62 and pullback > 68:
            action = "BULLISH NHƯNG CHỜ RETEST"
        elif put_score >= 68 and money_out >= 62 and selloff >= 62:
            action = "CANH BUY PUT"
        else:
            action = "WAIT"

        rows.append({
            "Ticker": ticker,
            "Action": action,
            "Price": row.get("Price"),
            "Money In": money_in,
            "Money Out": money_out,
            "Call Score": call_score,
            "Put Score": put_score,
            "Pullback Risk": pullback,
            "Sell-off Risk": selloff,
        })

    return pd.DataFrame(rows)
