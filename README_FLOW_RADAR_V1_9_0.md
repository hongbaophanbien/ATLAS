# ATLAS X 1.9.0 — Technical Flow Radar

Adds a background-generated option activity radar.

## Important limitation

Free Yahoo option-chain snapshots do not expose individual trade prints or
reliably classify:

- Buy to open
- Sell to open
- Buy to close
- Sell to close
- Sweep / block
- Multi-leg strategy

Therefore ATLAS labels the result as `activity`, not confirmed whale buying.

## Logic

Flow Score combines:

- Premium Proxy = Volume × midpoint × 100
- Volume / Open Interest
- Liquidity and bid/ask spread
- Delta relevance
- DTE and moneyness filters
- Alignment with ATLAS chart bias, MTF, Money In/Out, Call Score and Put Score

Conflicting flow is labeled `CONFLICT / HEDGE RISK`.

## Architecture

GitHub Actions:
1. Scans stocks.
2. Builds opportunities.
3. Fetches option-chain snapshots for up to 12 high-priority symbols.
4. Saves `flow_radar` inside `atlas_snapshots`.

Streamlit:
- Reads the saved radar.
- Does not fetch option chains when iPhone opens the app.

## Minimum update

Upload all files, especially:

- `app.py`
- `background_scan.py`
- `option_flow_radar.py`

Then manually run `ATLAS Background Scanner` once.

Commit:

`ATLAS X 1.9.0: add chart-confirmed background Flow Radar`
