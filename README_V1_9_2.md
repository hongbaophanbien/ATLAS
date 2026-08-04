# ATLAS X 1.9.2 — Overnight Confirmation

Adds extended-hours confirmation to every decision table and Flow Radar.

Columns:
- Extended Price
- Overnight %
- Premarket % / After Hours % (stored in snapshot)
- Overnight Bias
- Overnight Confirm
- Gap Risk
- Overnight Session
- Overnight Updated

Scoring:
- Overnight influence is capped at 8 points.
- It confirms or conflicts with CALL/PUT signals but never creates a trade alone.
- Large gaps are labeled WAIT RETEST / DO NOT CHASE.
- Missing data is DATA UNAVAILABLE, never fake 0%.

Limitation:
Yahoo data is an extended-hours proxy, generally 04:00-20:00 ET. It is not the
complete Robinhood 24-hour overnight market.

Upload all files and run GitHub Actions once.

Commit:
`ATLAS X 1.9.2: add overnight confirmation and gap-risk logic`
