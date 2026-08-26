"""
Liquidity sweep detection: price wicks through a prior swing
high/low (grabbing resting stop-loss/limit orders) and then closes
back inside range -> classic stop hunt before reversal.
"""

from config import EQUAL_LEVEL_TOLERANCE


def detect_liquidity_sweep(df, highs, lows):
    """
    Checks the most recently closed candle against the last few swing
    points for a sweep-and-reject pattern.
    Returns dict: {"type": "buy_side"/"sell_side"/None, "level": price, "wick_extreme": price}
    """
    if len(highs) < 1 or len(lows) < 1:
        return {"type": None, "level": None, "wick_extreme": None}

    last = df.iloc[-1]
    recent_highs = [p for _, p in highs[-3:]]
    recent_lows = [p for _, p in lows[-3:]]

    # Sell-side liquidity sweep (grabs stops below lows, then closes back up = bullish signal)
    for level in recent_lows:
        if last["low"] < level * (1 - EQUAL_LEVEL_TOLERANCE / 10) and last["close"] > level:
            return {"type": "sell_side", "level": level, "wick_extreme": last["low"]}

    # Buy-side liquidity sweep (grabs stops above highs, then closes back down = bearish signal)
    for level in recent_highs:
        if last["high"] > level * (1 + EQUAL_LEVEL_TOLERANCE / 10) and last["close"] < level:
            return {"type": "buy_side", "level": level, "wick_extreme": last["high"]}

    return {"type": None, "level": None, "wick_extreme": None}
