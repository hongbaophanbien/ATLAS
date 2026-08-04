
# ATLAS X 2.1 — Render-ready hotfix

Upload/replace these files in the GitHub repository root:

- app.py
- atlas_signal_refresh_hotfix.py
- background_scan.py
- quick_option.py
- worker_60s.py
- render.yaml

Then commit to `main`.

After Streamlit redeploys, verify:

1. FAST PICKS Decision shows BUY/WATCH CALL or PUT where eligible.
2. Option shortlist Signal is populated.
3. GitHub Actions still succeeds.
4. Then create Render Blueprint from `render.yaml`.
