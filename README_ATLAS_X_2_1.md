# ATLAS X 2.1 — Complete Market Update

This package consolidates the requested changes from the full working session.

## Navigation

- LIVE BOT 5M removed because it duplicated HOME / FAST PICKS.
- TradingView removed.
- Earnings 14D moved to the final tab.
- All other tabs remain.

## Main decision tables

Removed:

- Extended Price
- Overnight %
- Overnight Confirm
- Gap Risk
- Overnight Session
- Overnight Updated
- Trailing Stop
- Risk/Share
- ER Date
- ER Guidance
- Source

Kept:

- Overnight Bias
- All other columns not explicitly removed

Calculated:

`Stop = average(old Stop, old Trailing Stop)`

HOME / FAST PICKS merge Category + Action + Signal into `Decision`,
placed immediately after Ticker and Price.

Theme Rooms keeps Category and Action as separate columns immediately
after Ticker and Price.

## Option shortlist

- Dates shown as M/D/YY.
- Calls prefer strikes at or slightly above stock price.
- Puts prefer strikes at or slightly below stock price.
- Target Delta: approximately 0.50.
- Target Theta/day: approximately -0.20 per share.
- DTE replaced by Stock Price.
- Spread removed from display.
- Volume and OI retained.
- Reason removed.
- Dates across global tables use M/D/YY.

## Trade Plan

Plan A, Plan B and Plan C are displayed as separate highlighted cards.
The explanation underneath is also highlighted.

## Add ticker

A newly added ticker appears immediately in Trade Plan and Signal Fusion
as `PENDING FIRST SCAN`, even before it exists in the previous snapshot.

## 60-second refresh

There are two different refresh layers:

1. `worker_60s.py` runs `background_scan.py` every 60 seconds.
2. Streamlit polls Supabase every 60 seconds while the app is open.

GitHub Actions cannot guarantee a 60-second schedule. The included GitHub
workflow is a five-minute backup. For real 60-second snapshots, deploy
`worker_60s.py` as an always-on worker using `render.yaml`, `Procfile`, or
`Dockerfile.worker`.

## Reliability fixes included

- Correct earnings import (`earnings_info`).
- Strict Supabase JSON sanitization.
- NaN/Infinity converted to null.
- GitHub retry.
- Detailed Supabase error body.
- Reduced excessive decimal places.

## Recommended commit

`ATLAS X 2.1: consolidate tables options trade plans ticker sync and 60s worker`
