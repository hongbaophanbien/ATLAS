# ATLAS X 1.8.3 — Clean Live Bot Table

Fixes the LIVE BOT 5M table.

Removed from LIVE BOT display:

- ATR
- 5D %
- 20D %
- EMA9
- EMA21
- EMA50
- CMF20
- Gap %
- Other raw diagnostic columns

LIVE BOT now uses the same decision-focused columns as FAST PICKS:

- Ticker
- Price
- 1D %
- RSI14
- Pullback Risk
- Trade Score
- Setup
- Preferred Vehicle
- Buy Zone Low / High
- Chase Limit
- Stop
- Sell Zone 1 / 2
- Trailing Stop
- Risk/Share
- Level Logic
- Money In / Out
- Flow Status
- Sell-off Risk
- Call Score / Put Score
- Category
- Action
- Signal
- Reasons
- ER Date
- ER Guidance
- Source

Numbers use the existing compact formatting rules, and Ticker/Action/Signal
remain sticky while scrolling horizontally.

Minimum update:

- Replace `app.py`

Commit:

`ATLAS X 1.8.3: clean LIVE BOT decision table`
