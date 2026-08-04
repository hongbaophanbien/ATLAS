# ATLAS X 1.8.5 — Safe Settings Sync

Fixes the sidebar error:

`401 Client Error: Unauthorized ... /rest/v1/atlas_settings?on_conflict=id`

Behavior:

- Snapshot reads continue using `SUPABASE_KEY`.
- Settings writes prefer `SUPABASE_WRITE_KEY`.
- A 401/403 response no longer crashes or displays a long raw URL.
- Watchlist remains saved in Streamlit session and the app URL even when
  shared Supabase synchronization is unavailable.
- Sidebar shows a short status:
  `Watchlist đã lưu trong app. Chưa đồng bộ chạy nền.`

To enable shared/background watchlist synchronization, add this to
Streamlit Secrets:

```toml
SUPABASE_WRITE_KEY = "sb_secret_..."
```

Minimum update:

- `app.py`
- `snapshot_store.py`

Commit:

`ATLAS X 1.8.5: add safe settings write fallback`
