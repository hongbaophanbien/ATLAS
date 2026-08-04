# ATLAS X 1.4.1 — HTML + Watchlist Persistence Hotfix

Fixed:
- `NameError: html is not defined` in the sticky FAST PICKS table.
- Custom watchlist no longer resets to DEFAULT after browser refresh.

How persistence works:
- The watchlist is normalized and stored in the app URL as `?watchlist=...`.
- Refreshing the page, bookmarking the URL, or reopening it on the same device keeps the list.
- Changing the watchlist clears stale scan results and triggers a new automatic scan.

Background scanner note:
- GitHub Actions cannot read a user's browser URL.
- To make the background scanner use the same custom list, set the GitHub Actions repository variable `ATLAS_WATCHLIST` to the comma-separated list.

Minimum update:
- `app.py`

Commit:
ATLAS X 1.4.1: fix html import and persist watchlist
