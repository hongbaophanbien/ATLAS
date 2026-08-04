# ATLAS X 1.5 — Background Watchlist Sync

## What “Background Snapshot chưa cấu hình” means

The application code is present, but Supabase and GitHub Actions Secrets have
not been connected. Until they are connected, Streamlit must scan directly.

## New default focus

Semiconductor focus includes:
SMH, SOXX, NVDA, AMD, AVGO, TSM, MU, MRVL, ARM, INTC, SNDK,
AMAT, LRCX, KLAC, ASML, QCOM, ALAB, DELL, WDC and GLW.

Space list:
- Added SPCX
- Removed SPCE

## After setup

- GitHub Actions scans every 5 minutes even when the app is closed.
- Streamlit reads the prepared snapshot when opened.
- Watchlist edits in Streamlit are saved to Supabase.
- The background worker reads that same watchlist automatically.
- HOME shows requested, analyzed, qualified and hidden/failed counts.

## Supabase

1. Create a Supabase project.
2. Run `SUPABASE_SETUP.sql` in SQL Editor.
3. Copy Project URL, anon key and service_role key.

## GitHub Secrets

Repository -> Settings -> Secrets and variables -> Actions:

- `SUPABASE_URL` = Project URL
- `SUPABASE_KEY` = service_role key

Ensure `.github/workflows/atlas_background_scan.yml` exists on the default branch.

## Streamlit Secrets

Manage app -> Settings -> Secrets:

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_KEY = "YOUR_ANON_KEY"
SUPABASE_WRITE_KEY = "YOUR_SERVICE_ROLE_KEY"
```

## First test

GitHub -> Actions -> ATLAS Background Scanner -> Run workflow.

After a successful run, reopen ATLAS. HOME should say:

`Background Snapshot đang hoạt động.`

Scheduled runs are approximately every five minutes and can occasionally be
delayed by GitHub. This is not exchange-grade real-time data.
