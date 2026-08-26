# Sniper Signal Bot — Setup Guide

## What this is
A confluence-based Telegram alert bot for BTC/USD, XAU/USD, and USD/JPY.
Instead of firing on a single indicator, it only alerts when structure,
liquidity, a valid zone (order block / FVG), and momentum all line up —
and it will explicitly say **NO TRADE** when they don't.

## How it differs from a typical single-signal bot
| | Single-indicator alert bot | This bot |
|---|---|---|
| **Trigger** | One condition (e.g. RSI < 30, price crosses MA) | 4 independent confluences must agree: HTF bias, structure break (BOS/CHoCH), liquidity sweep, momentum confirmation |
| **Output** | "Price hit X" | Full trade plan: entry zone, SL, TP1/TP2/TP3, R:R, confidence score, invalidation level |
| **Stop loss** | Fixed pips/% | Placed structurally — beyond the liquidity sweep wick, with an ATR buffer |
| **Silence** | Usually alerts constantly | Explicitly returns NO TRADE below a 70/100 confluence score — designed to be quiet most of the time |
| **Repeats** | Can spam the same level repeatedly | Cooldown state (`state.json`) prevents re-alerting the same setup for N candles |

## File overview
- `data_fetcher.py` — pulls candles from Twelve Data
- `structure.py` — swing highs/lows, BOS/CHoCH, HTF trend bias
- `liquidity.py` — liquidity sweep (stop hunt) detection
- `zones.py` — fair value gaps and order blocks (the entry zone)
- `momentum.py` — RSI divergence / momentum shift confirmation
- `signal_engine.py` — combines everything into a confidence score and builds entry/SL/TP
- `news_filter.py` — checks Finnhub's economic calendar and blocks alerts around high-impact events
- `telegram_bot.py` — formats and sends the alert
- `state.py` / `state.json` — cooldown tracking between runs
- `main.py` — orchestrates the whole live run
- `backtest.py` — walk-forward backtest of the engine against historical data
- `.github/workflows/sniper_alerts.yml` — runs the live bot every 15 minutes on GitHub Actions

## News / economic calendar filter
Before evaluating each pair, the bot checks Finnhub's free economic
calendar for high-impact events tied to that pair's relevant currencies
(e.g. USD for BTC/USD and XAU/USD; USD + JPY for USD/JPY). If "now"
falls within `NEWS_BLACKOUT_MINUTES_BEFORE`/`_AFTER` of a high-impact
event, the bot stands aside and logs a NO TRADE — even if the chart
looks perfect — because a CPI print or rate decision can invalidate a
clean technical setup in seconds.

- Get a free key at https://finnhub.io/register and set it as `FINNHUB_API_KEY`.
- If the key is missing or the API call fails, the filter **fails soft**:
  it logs a warning and lets the bot continue running technically-driven
  (never crashes the whole run over a calendar lookup).
- Tune `NEWS_MIN_IMPACT`, `NEWS_BLACKOUT_MINUTES_BEFORE/AFTER`, and each
  pair's `currencies` list in `config.py`.

## Backtesting
```bash
# Pull fresh data from Twelve Data and backtest BTC/USD
python backtest.py --symbol BTC/USD --bars 3000

# Or test against your own historical CSV (columns: datetime,open,high,low,close)
python backtest.py --csv my_data.csv --label "BTC/USD"
```
This walks forward bar-by-bar, feeding the engine only data that would
have been available at that point in time (no lookahead), records every
TRADE signal, then simulates forward to see which of SL/TP1/TP2/TP3 was
touched first. It respects the same cooldown as the live bot. Output:
- `backtest_trades.csv` — every triggered signal and its outcome
- `backtest_equity_curve.png` — cumulative R-multiple curve
- Console summary: trade count (as a % of bars — should be low, since
  the engine is designed to say NO TRADE most of the time), win rate,
  total R, average R, and max drawdown

Use this to tune `MIN_CONFIDENCE_TO_ALERT`, `SL_ATR_BUFFER`, and the
confluence weights in `config.py` before trusting live alerts. The
backtest does **not** currently account for the news blackout filter
(historical high-impact event data isn't pulled) — treat backtest
results as the pure technical edge, independent of news avoidance.

## Setup
1. Add these as **repo secrets** (Settings → Secrets and variables → Actions):
   - `TWELVE_DATA_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `FINNHUB_API_KEY` (optional but recommended — enables the news blackout filter)
2. Push this `sniper_bot/` folder (with the `.github/workflows/` file at repo root) to your GitHub repo.
3. The workflow runs automatically every 15 minutes, or trigger it manually from the Actions tab ("Run workflow").
4. To test locally first:
   ```bash
   pip install -r requirements.txt
   export TWELVE_DATA_API_KEY=xxx TELEGRAM_BOT_TOKEN=xxx TELEGRAM_CHAT_ID=xxx
   python main.py
   ```

## Tuning knobs (all in `config.py`)
- `MIN_CONFIDENCE_TO_ALERT` — raise for fewer, higher-quality signals; lower for more frequent ones
- `SL_ATR_BUFFER` — how much extra room beyond the sweep wick your stop gets
- `RR_TP1/2/3` — your reward targets in R multiples
- `COOLDOWN_BARS` — how many candles before the same pair/direction can re-alert

## Honest limitations
- Structure/FVG/order-block detection here uses standard, well-known
  definitions but is inherently simplified compared to manual chart reading —
  treat every alert as a *candidate* setup to confirm visually, not a
  blind auto-trade signal.
- The news filter only blocks *known scheduled* high-impact releases —
  it won't catch breaking geopolitical news, surprise central-bank
  statements, or flash-crash conditions.
- Backtest results don't include slippage, spread, or the news filter —
  treat them as an upper bound on the technical edge, not a live-trading guarantee.
- This is not financial advice; you are responsible for your own risk management.
