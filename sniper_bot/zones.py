"""
Fair Value Gap (FVG) and Order Block (OB) detection - the "zone"
component of the sniper entry (where price should return to before
we consider an entry valid).
"""


def find_fvgs(df, max_lookback=20):
    """
    3-candle imbalance check across the most recent `max_lookback` bars.
    Bullish FVG: candle[i-1].low > candle[i+1].high is NOT it -
    standard definition: gap between candle1.high and candle3.low (bullish),
    or candle1.low and candle3.high (bearish).
    Returns list of dicts: {"type": "bullish"/"bearish", "top": .., "bottom": ..}
    """
    fvgs = []
    n = len(df)
    start = max(2, n - max_lookback)
    for i in range(start, n):
        c1 = df.iloc[i - 2]
        c3 = df.iloc[i]
        # Bullish FVG: gap up, candle3's low still above candle1's high
        if c3["low"] > c1["high"]:
            fvgs.append({"type": "bullish", "top": c3["low"], "bottom": c1["high"], "index": i})
        # Bearish FVG: gap down, candle3's high still below candle1's low
        if c3["high"] < c1["low"]:
            fvgs.append({"type": "bearish", "top": c1["low"], "bottom": c3["high"], "index": i})
    return fvgs


def find_last_order_block(df, direction: str, lookback=25):
    """
    Simplified order block: the last opposite-colored candle before a
    strong displacement move in `direction` ('bullish' or 'bearish').
    Returns dict {"top": .., "bottom": ..} or None.
    """
    n = len(df)
    start = max(1, n - lookback)
    candidates = []

    for i in range(start, n - 1):
        candle = df.iloc[i]
        next_candle = df.iloc[i + 1]
        body = abs(candle["close"] - candle["open"])
        next_body = abs(next_candle["close"] - next_candle["open"])

        if direction == "bullish":
            is_down_candle = candle["close"] < candle["open"]
            strong_up_next = next_candle["close"] > next_candle["open"] and next_body > body * 1.3
            if is_down_candle and strong_up_next:
                candidates.append({"top": candle["open"], "bottom": candle["low"], "index": i})

        if direction == "bearish":
            is_up_candle = candle["close"] > candle["open"]
            strong_down_next = next_candle["close"] < next_candle["open"] and next_body > body * 1.3
            if is_up_candle and strong_down_next:
                candidates.append({"top": candle["high"], "bottom": candle["open"], "index": i})

    return candidates[-1] if candidates else None


def price_in_zone(price: float, zone: dict) -> bool:
    if not zone:
        return False
    lo, hi = sorted([zone["top"], zone["bottom"]])
    return lo <= price <= hi
