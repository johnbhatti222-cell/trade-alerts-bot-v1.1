"""
The structure-based HTF bias (BOS/CHoCH + swing sequence), kept here so
compare_bias.py can re-test it against the live EMA-crossover version in
structure.py if you ever want to revisit this.

History: this was briefly the live version, on the theory that it would
react faster to sharp reversals than EMA crossovers (which lag). It
tested well in isolation early on, but a later real-data comparison —
run after chart patterns and tiering were added — showed EMA bias
clearly outperforming it (61.9% vs 38.9% combined win rate across
BTC/USD, XAU/USD, USD/JPY), with a consistent, repeated weakness on
XAU/USD specifically across three separate test runs. EMA was restored
as the live version in structure.py; this is preserved here, not used
by the live bot.
"""

import pandas as pd
from structure import find_swings, detect_bos_choch


def htf_bias_structure(df: pd.DataFrame) -> str:
    """
    Priority order:
      1. A fresh BOS/CHoCH on this timeframe -> that direction, immediately.
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
