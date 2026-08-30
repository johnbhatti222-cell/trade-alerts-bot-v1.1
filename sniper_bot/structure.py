"""
Market structure: swing highs/lows, Break of Structure (BOS),
Change of Character (CHoCH), and higher-timeframe trend bias.

Note on htf_bias(): this is the EMA-crossover version. A structure-based
alternative (BOS/CHoCH + swing sequence) was tried and compared here via
compare_bias.py — it initially tested well in isolation, but a later
real-data comparison (after chart patterns + tiering were added) showed
EMA bias clearly outperforming it, consistently including a repeated
weakness on XAU/USD specifically across three separate test runs. EMA
was restored as the live version; the structure-based alternative is
preserved in legacy_bias.py for any future re-testing.
"""

import pandas as pd
import numpy as np
from config import SWING_LOOKBACK
from indicators import ema


def find_swings(df: pd.DataFrame, lookback: int = SWING_LOOKBACK):
    """
    Fractal swing detection: a bar is a swing high if it's the highest
    high within `lookback` bars on both sides (same for swing low).
    Returns two lists of (position, price) tuples, where position is
    always a 0-based positional index into df — matching the original
    implementation's semantics regardless of df's actual pandas index
    labels (callers elsewhere rely on positional indexing, e.g. via
    .iloc, into aligned Series computed from the same df).

    Vectorized via pandas rolling (centered) instead of a per-bar Python
    loop with repeated .iloc slicing — same fractal definition, same
    output, much faster on the window sizes used by the backtest.
    """
    window = 2 * lookback + 1
    high_vals = df["high"].to_numpy()
    low_vals = df["low"].to_numpy()

    roll_max = df["high"].rolling(window=window, center=True, min_periods=window).max().to_numpy()
    roll_min = df["low"].rolling(window=window, center=True, min_periods=window).min().to_numpy()

    is_high = high_vals == roll_max
    is_low = low_vals == roll_min

    high_positions = np.flatnonzero(is_high)
    low_positions = np.flatnonzero(is_low)

    highs = [(int(p), float(high_vals[p])) for p in high_positions]
    lows = [(int(p), float(low_vals[p])) for p in low_positions]
    return highs, lows


def htf_bias(df: pd.DataFrame) -> str:
    """
    EMA-crossover HTF trend read: EMA20 vs EMA50 slope + price position.
    Returns 'bullish', 'bearish', or 'ranging'.
    """
    if len(df) < 60:
        return "ranging"
    fast = ema(df["close"], 20)
    slow = ema(df["close"], 50)
    price = df["close"].iloc[-1]

    fast_now, fast_prev = fast.iloc[-1], fast.iloc[-5]
    slow_now = slow.iloc[-1]

    if price > slow_now and fast_now > fast_prev and fast_now > slow_now:
        return "bullish"
    if price < slow_now and fast_now < fast_prev and fast_now < slow_now:
        return "bearish"
    return "ranging"


def detect_bos_choch(df: pd.DataFrame, highs, lows):
    """
    Look at the most recent swing points to classify the latest
    structural event:
      - 'bos_bullish'  : price closed above the last swing high in an uptrend
      - 'bos_bearish'  : price closed below the last swing low in a downtrend
      - 'choch_bullish': price closed above the last swing high after a downtrend
      - 'choch_bearish': price closed below the last swing low after an uptrend
      - 'none'         : no clean structural break yet
    """
    if len(highs) < 2 or len(lows) < 2:
        return "none"

    last_close = df["close"].iloc[-1]
    last_swing_high = highs[-1][1]
    last_swing_low = lows[-1][1]
    prev_swing_high = highs[-2][1]
    prev_swing_low = lows[-2][1]

    was_uptrend = prev_swing_high < last_swing_high and prev_swing_low < last_swing_low
    was_downtrend = prev_swing_high > last_swing_high and prev_swing_low > last_swing_low

    if last_close > last_swing_high:
        return "bos_bullish" if was_uptrend else "choch_bullish"
    if last_close < last_swing_low:
        return "bos_bearish" if was_downtrend else "choch_bearish"
    return "none"
