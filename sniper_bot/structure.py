"""
Market structure: swing highs/lows, Break of Structure (BOS),
Change of Character (CHoCH), and higher-timeframe trend bias.
"""

import pandas as pd
from config import SWING_LOOKBACK


def find_swings(df: pd.DataFrame, lookback: int = SWING_LOOKBACK):
    """
    Fractal swing detection: a bar is a swing high if it's the highest
    high within `lookback` bars on both sides (same for swing low).
    Returns two lists of (index, price) tuples.
    """
    highs, lows = [], []
    n = len(df)
    for i in range(lookback, n - lookback):
        window_high = df["high"].iloc[i - lookback: i + lookback + 1]
        window_low = df["low"].iloc[i - lookback: i + lookback + 1]
        if df["high"].iloc[i] == window_high.max():
            highs.append((i, df["high"].iloc[i]))
        if df["low"].iloc[i] == window_low.min():
            lows.append((i, df["low"].iloc[i]))
    return highs, lows


def htf_bias(df: pd.DataFrame) -> str:
    """
    Structure-based HTF trend read (replaces the old EMA-crossover version,
    which lagged behind sharp reversals because moving averages are slow
    to catch up after a strong break of structure).

    Priority order:
      1. A fresh BOS/CHoCH on this timeframe -> that direction, immediately.
         This is what lets the engine react to a sharp reversal (like a
         V-shaped bounce breaking back above a swing high) without waiting
         for a moving average to turn.
      2. No fresh break -> fall back to the broader swing sequence (higher
         highs/higher lows = bullish, lower highs/lower lows = bearish).
      3. Neither condition is clean -> 'ranging'.

    Returns 'bullish', 'bearish', or 'ranging'.
    """
    if len(df) < 20:
        return "ranging"

    highs, lows = find_swings(df)
    if len(highs) < 2 or len(lows) < 2:
        return "ranging"

    structure_event = detect_bos_choch(df, highs, lows)
    if structure_event in ("bos_bullish", "choch_bullish"):
        return "bullish"
    if structure_event in ("bos_bearish", "choch_bearish"):
        return "bearish"

    last_high, prev_high = highs[-1][1], highs[-2][1]
    last_low, prev_low = lows[-1][1], lows[-2][1]

    if last_high > prev_high and last_low > prev_low:
        return "bullish"
    if last_high < prev_high and last_low < prev_low:
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
