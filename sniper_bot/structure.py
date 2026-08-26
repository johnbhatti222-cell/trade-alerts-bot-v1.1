"""
Market structure: swing highs/lows, Break of Structure (BOS),
Change of Character (CHoCH), and higher-timeframe trend bias.
"""

import pandas as pd
from config import SWING_LOOKBACK
from indicators import ema


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
    Simple, robust HTF trend read: EMA50 vs EMA200 slope + price position.
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
