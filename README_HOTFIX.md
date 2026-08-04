# ATLAS X 1.1 — Always-On Auto Mode Hotfix

Fixed:
- KeyError: Stock Confidence
- Option shortlist now accepts Confidence, Opportunity Score, or Trade Score.
- Option direction accepts both Signal and Action values.

Automatic behavior:
- HOME runs the first scan automatically.
- LIVE BOT is permanently enabled and reruns every 5 minutes while the Streamlit session is active.
- FAST PICKS uses the latest automatic scan.
- ATLAS BOT updates automatically.
- Removed RUN FULL SCAN, REFRESH FAST PICKS, RUN BOT NOW, and technical test buttons.

Upload all files from this package, or minimally replace:
- app.py
- quick_option.py

Commit:
ATLAS X 1.1: fix option confidence and enable always-on auto mode
