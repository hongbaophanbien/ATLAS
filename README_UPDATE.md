# ATLAS X 2.3 UPDATE 01

Upload/replace these files in the GitHub repository.

## Main changes in app.py
- Entry Radar directly after Fast Picks.
- Entry Radar scans the full snapshot Watchlist.
- Sticky/frozen Ticker column.
- CALL ranking using Money In/Out, RSI, Trend, Entry, Call/Put score and distance to Call Zone.
- Human-readable Setup and concise Reason.
- TP1 displayed when available from snapshot.
- ER 14D tab removed.
- Fixed incorrect tab index collisions in the supplied app.py.
- Fast Picks no longer calls earnings APIs for every row while rendering.
- Online status check cached for 60 seconds to reduce rerun latency.

The other four Python files are included unchanged from the supplied build so the ZIP can be uploaded as one coherent set.
