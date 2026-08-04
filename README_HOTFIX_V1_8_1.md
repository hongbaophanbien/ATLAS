# ATLAS X 1.8.1 — Snapshot Only Hotfix

This hotfix removes every automatic direct scan that was triggered when the
Streamlit app opened or when FAST PICKS rendered.

## Fixed behavior

- HOME loads `atlas_snapshots` once at startup.
- LIVE BOT reloads the Supabase snapshot every five minutes while the app is open.
- FAST PICKS reads the same snapshot.
- No `run_full_scan()` fallback occurs when Streamlit Secrets are missing.
- On missing/invalid snapshot, the UI shows a configuration error instead of
  scanning all 88 tickers.
- New Supabase `sb_publishable_` and `sb_secret_` keys are sent through the
  `apikey` header without an invalid Bearer header.
- Legacy JWT keys beginning with `eyJ` remain supported.

## Required Streamlit Secrets

```toml
SUPABASE_URL = "https://YOUR_PROJECT.supabase.co"
SUPABASE_KEY = "sb_publishable_..."
```

Optional, only for saving the shared watchlist from Streamlit:

```toml
SUPABASE_WRITE_KEY = "sb_secret_..."
```

## Minimum update

Replace:

- `app.py`
- `snapshot_store.py`

Commit:

`ATLAS X 1.8.1: disable direct scans and enforce Supabase snapshot mode`
