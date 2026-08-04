# ATLAS X 1.7 — Global Sticky Ticker

The frozen ticker behavior now applies to every table that contains a Ticker
column, not only FAST PICKS.

Updated tables include:

- HOME Top Opportunities
- LIVE BOT
- FAST PICKS
- Option Shortlist
- Earnings 14D
- Theme Rooms
- CALL Confirmed / CALL Watch
- PUT Confirmed / PUT Watch
- Watch Engine
- AI SEMI ONLY
- System Health ticker diagnostics

Behavior:

- Ticker remains visible while scrolling horizontally.
- Header remains visible while scrolling vertically.
- Important identity columns such as Action, Signal, Decision, or Conviction
  are also frozen in selected trading tables.
- Mobile touch scrolling remains enabled.
- Tables without a Ticker column continue to use their normal layout.

Minimum update:
- app.py

Commit:
ATLAS X 1.7: apply sticky ticker to all trading tables
