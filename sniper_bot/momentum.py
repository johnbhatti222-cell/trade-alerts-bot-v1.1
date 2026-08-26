"""
Momentum confirmation: RSI divergence between the last two comparable
swing points, or a simple momentum shift out of oversold/overbought.
"""

from indicators import rsi


def check_momentum_confirmation(df, lows, highs, direction: str) -> dict:
    """
    direction: 'bullish' or 'bearish' - the direction we're looking to confirm.
    Returns {"confirmed": bool, "reason": str}
    """
    r = rsi(df["close"])
    last_rsi = r.iloc[-1]

    if direction == "bullish":
        # Simple oversold recovery
        if last_rsi < 45 and r.iloc[-1] > r.iloc[-2] > r.iloc[-3]:
            oversold_recovery = True
        else:
            oversold_recovery = False

        # Bullish divergence: price makes a lower low, RSI makes a higher low
        divergence = False
        if len(lows) >= 2:
            (i1, p1), (i2, p2) = lows[-2], lows[-1]
            if p2 < p1 and r.iloc[i2] > r.iloc[i1]:
                divergence = True

        if divergence:
            return {"confirmed": True, "reason": "bullish RSI divergence"}
        if oversold_recovery:
            return {"confirmed": True, "reason": "RSI recovering from oversold"}
        return {"confirmed": False, "reason": "no bullish momentum confirmation"}

    if direction == "bearish":
        overbought_reversal = last_rsi > 55 and r.iloc[-1] < r.iloc[-2] < r.iloc[-3]

        divergence = False
        if len(highs) >= 2:
            (i1, p1), (i2, p2) = highs[-2], highs[-1]
            if p2 > p1 and r.iloc[i2] < r.iloc[i1]:
                divergence = True

        if divergence:
            return {"confirmed": True, "reason": "bearish RSI divergence"}
        if overbought_reversal:
            return {"confirmed": True, "reason": "RSI turning down from overbought"}
        return {"confirmed": False, "reason": "no bearish momentum confirmation"}

    return {"confirmed": False, "reason": "unknown direction"}
