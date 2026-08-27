"""
Central configuration for the Sniper Signal Bot.
All secrets are read from environment variables (set as GitHub Actions secrets).
"""

import os

# --- API credentials (set these as repo secrets, never hardcode) ---
TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
FINNHUB_API_KEY = os.environ.get("FINNHUB_API_KEY", "")  # free tier: https://finnhub.io/register

# --- Instruments to scan ---
# Twelve Data symbol format: "BTC/USD", "XAU/USD", "USD/JPY"
# "currencies": which economic-calendar currencies can invalidate this pair's setups
PAIRS = [
    {"symbol": "BTC/USD", "label": "BTC/USD", "pip_size": 1.0, "currencies": ["USD"]},
    {"symbol": "XAU/USD", "label": "XAU/USD (Gold)", "pip_size": 0.1, "currencies": ["USD"]},
    {"symbol": "USD/JPY", "label": "USD/JPY", "pip_size": 0.01, "currencies": ["USD", "JPY"]},
]

# --- News / economic calendar blackout ---
NEWS_MIN_IMPACT = "high"           # only "high" impact events trigger a blackout
NEWS_BLACKOUT_MINUTES_BEFORE = 30  # stop alerting this many minutes before the event
NEWS_BLACKOUT_MINUTES_AFTER = 30   # ...and resume this many minutes after it

# --- Timeframes ---
HTF_INTERVAL = "15min"   # higher timeframe -> trend bias
LTF_INTERVAL = "5min"    # lower timeframe -> entry trigger
CANDLE_COUNT = 150      # bars to pull each run (enough history for swings/ATR)

# --- Structure detection ---
SWING_LOOKBACK = 2       # bars each side for fractal swing high/low
EQUAL_LEVEL_TOLERANCE = 0.0015  # % tolerance to treat two highs/lows as "equal" (liquidity pool)

# --- Risk engine ---
ATR_PERIOD = 14
SL_ATR_BUFFER = 0.25     # extra buffer beyond the sweep wick, in ATR multiples
RR_TP1 = 1.0
RR_TP2 = 2.0
RR_TP3 = 3.0

# --- Confidence scoring weights (must sum to 100) ---
WEIGHTS = {
    "bias_alignment": 25,   # LTF setup agrees with HTF trend
    "zone_quality": 25,     # entry sits at FVG / order block / clean S-R
    "liquidity_sweep": 25,  # confirmed stop hunt before the move
    "momentum_confirmation": 25,  # RSI divergence / shift confirms
}
MIN_CONFIDENCE_TO_ALERT = 70  # below this -> NO TRADE, even if some confluence exists

# --- Alert throttling ---
STATE_FILE = os.path.join(os.path.dirname(__file__), "state.json")
COOLDOWN_BARS = 6   # don't re-alert the same pair/direction within N LTF candles
