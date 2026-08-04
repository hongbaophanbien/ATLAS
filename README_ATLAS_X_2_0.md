# ATLAS X 2.0 — Always-On Reliability

## What this version solves

A green GitHub Action is not enough. This build records and displays:

- Snapshot age
- Scanner start and finish time
- Scanner duration
- Requested and scanned ticker counts
- Coverage percentage
- Failed ticker count
- Qualified opportunity count
- Flow contract count
- Whether Flow has Volume/OI/Bid/Ask
- GitHub Run ID
- Provider status

## GitHub schedule

The workflow runs every five minutes, offset at minute 2, 7, 12, etc.

```yaml
- cron: "2-59/5 * * * *"
```

It retries once after 20 seconds if the scanner fails.

Important:

- GitHub Actions is scheduled execution, not a permanently running server.
- Runs can be delayed.
- The app treats snapshots older than 15 minutes as STALE.
- Do not trade from Flow or Overnight when System Health says STALE.

## Robinhood 24H

Robinhood offers 24-hour trading for eligible stocks and ETFs, but this build
does not log into or scrape the private Robinhood stock API.

Current provider:

- Yahoo extended-hours proxy for premarket and after-hours
- Robinhood 24H status shown as NOT CONNECTED

Reason:

- Robinhood's public developer documentation currently exposes an official
  Crypto Trading API, not a general public stock 24H market-data API.
- Reverse-engineered login APIs can break and may create account/security risk.

A future licensed market-data provider can be connected through the provider
status interface without changing the decision engine.

## Files to upload

Upload the full ZIP. Critical files:

- `.github/workflows/atlas_background_scan.yml`
- `app.py`
- `background_scan.py`
- `reliability_engine.py`
- `overnight_engine.py`
- `option_flow_radar.py`

## After upload

1. Commit all files to the default branch.
2. Confirm GitHub Secrets:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`
   - `SUPABASE_WRITE_KEY`
3. Run the workflow manually once.
4. Open System Health.
5. Only trust the data when:
   - Snapshot = FRESH
   - Scanner = READY
   - Coverage is acceptable
   - Flow contracts > 0 for Flow analysis

Commit message:

`ATLAS X 2.0: add always-on schedule, retries and data reliability telemetry`
