# ATLAS X 1.9.1 — Clean Decision Terminal

Fixes three UI/data problems.

## Theme Rooms
- Removes raw ATR, EMA9, EMA21, EMA50, CMF20, Gap and similar columns.
- Uses the same decision-focused columns as FAST PICKS.
- Keeps only Ticker sticky.

## Earnings 14D
- Removes the large multiselect with dozens of red ticker chips.
- GitHub Background Scanner creates the 14-day earnings list.
- The app only displays tickers with an ER date within 14 days.
- Shows source failure count.

## Flow Radar
- Primary scan uses high-ranked opportunities.
- If empty, fallback scans liquid names such as SPY, QQQ, NVDA, AMD, TSLA,
  META, AAPL, AVGO, MU, MRVL, PANW and CRWD.
- Saves diagnostics: attempted symbols, fallback symbols and contracts found.
- The app explains whether the snapshot is old or the option-chain filter
  returned no suitable contracts.

Upload all files, especially:
- app.py
- background_scan.py
- option_flow_radar.py

Then run GitHub Actions -> ATLAS Background Scanner once.

Commit:
`ATLAS X 1.9.1: clean Theme Rooms, automate Earnings 14D, diagnose Flow Radar`
