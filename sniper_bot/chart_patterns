"""
Classic chart pattern detection, built on the same fractal swing
highs/lows already computed by structure.find_swings() — no new data
requirements, unlike volume (which turned out to be unavailable for
these pairs). Patterns checked, by direction:

  Bearish: Double Top, Head & Shoulders, Descending Triangle breakdown
  Bullish: Double Bottom, Inverse Head & Shoulders, Ascending Triangle breakout

Each pattern requires the neckline/boundary to actually be BROKEN by
the current close, not just "shape present" — a pattern that has
formed but not yet confirmed by a breakout doesn't count. This matches
the same "wait for confirmation" philosophy as the rest of the engine.
"""

from config import PATTERN_LEVEL_TOLERANCE


def _levels_equal(a: float, b: float, tolerance: float = PATTERN_LEVEL_TOLERANCE) -> bool:
    """True if two price levels are within tolerance% of each other."""
    if a == 0 or b == 0:
        return False
    return abs(a - b) / max(abs(a), abs(b)) <= tolerance


def _detect_double_top(df, highs, lows):
    if len(highs) < 2 or len(lows) < 1:
        return None
    h2_idx, h2 = highs[-1]
    h1_idx, h1 = highs[-2]
    if not _levels_equal(h1, h2):
        return None

    # Neckline = lowest swing low strictly between the two tops
    between_lows = [p for i, p in lows if h1_idx < i < h2_idx]
    if not between_lows:
        return None
    neckline = min(between_lows)

    last_close = df["close"].iloc[-1]
    if last_close < neckline:
        return {"confirmed": True, "reason": f"Double Top confirmed (neckline {neckline:.4f} broken)"}
    return None


def _detect_double_bottom(df, highs, lows):
    if len(lows) < 2 or len(highs) < 1:
        return None
    l2_idx, l2 = lows[-1]
    l1_idx, l1 = lows[-2]
    if not _levels_equal(l1, l2):
        return None

    between_highs = [p for i, p in highs if l1_idx < i < l2_idx]
    if not between_highs:
        return None
    neckline = max(between_highs)

    last_close = df["close"].iloc[-1]
    if last_close > neckline:
        return {"confirmed": True, "reason": f"Double Bottom confirmed (neckline {neckline:.4f} broken)"}
    return None


def _detect_head_and_shoulders(df, highs, lows):
    if len(highs) < 3 or len(lows) < 2:
        return None
    (ls_idx, left_shoulder), (h_idx, head), (rs_idx, right_shoulder) = highs[-3], highs[-2], highs[-1]

    if not (head > left_shoulder and head > right_shoulder):
        return None
    if not _levels_equal(left_shoulder, right_shoulder, tolerance=PATTERN_LEVEL_TOLERANCE * 2):
        return None

    neckline_points = [p for i, p in lows if ls_idx < i < rs_idx]
    if not neckline_points:
        return None
    neckline = min(neckline_points)

    last_close = df["close"].iloc[-1]
    if last_close < neckline:
        return {"confirmed": True, "reason": f"Head & Shoulders confirmed (neckline {neckline:.4f} broken)"}
    return None


def _detect_inverse_head_and_shoulders(df, highs, lows):
    if len(lows) < 3 or len(highs) < 2:
        return None
    (ls_idx, left_shoulder), (h_idx, head), (rs_idx, right_shoulder) = lows[-3], lows[-2], lows[-1]

    if not (head < left_shoulder and head < right_shoulder):
        return None
    if not _levels_equal(left_shoulder, right_shoulder, tolerance=PATTERN_LEVEL_TOLERANCE * 2):
        return None

    neckline_points = [p for i, p in highs if ls_idx < i < rs_idx]
    if not neckline_points:
        return None
    neckline = max(neckline_points)

    last_close = df["close"].iloc[-1]
    if last_close > neckline:
        return {"confirmed": True, "reason": f"Inverse Head & Shoulders confirmed (neckline {neckline:.4f} broken)"}
    return None


def _detect_descending_triangle(df, highs, lows):
    """Roughly flat support (lows), falling resistance (highs) -> confirmed on a breakDOWN below support."""
    if len(highs) < 3 or len(lows) < 3:
        return None
    recent_highs = highs[-3:]
    recent_lows = lows[-3:]

    highs_falling = recent_highs[0][1] > recent_highs[1][1] > recent_highs[2][1]
    low_vals = [p for _, p in recent_lows]
    lows_flat = _levels_equal(min(low_vals), max(low_vals), tolerance=PATTERN_LEVEL_TOLERANCE * 2)

    if not (highs_falling and lows_flat):
        return None

    support = min(low_vals)
    last_close = df["close"].iloc[-1]
    if last_close < support:
        return {"confirmed": True, "reason": f"Descending Triangle breakdown (support {support:.4f} broken)"}
    return None


def _detect_ascending_triangle(df, highs, lows):
    """Roughly flat resistance (highs), rising support (lows) -> confirmed on a breakOUT above resistance."""
    if len(highs) < 3 or len(lows) < 3:
        return None
    recent_highs = highs[-3:]
    recent_lows = lows[-3:]

    lows_rising = recent_lows[0][1] < recent_lows[1][1] < recent_lows[2][1]
    high_vals = [p for _, p in recent_highs]
    highs_flat = _levels_equal(min(high_vals), max(high_vals), tolerance=PATTERN_LEVEL_TOLERANCE * 2)

    if not (lows_rising and highs_flat):
        return None

    resistance = max(high_vals)
    last_close = df["close"].iloc[-1]
    if last_close > resistance:
        return {"confirmed": True, "reason": f"Ascending Triangle breakout (resistance {resistance:.4f} broken)"}
    return None


def check_chart_pattern(df, highs, lows, direction: str) -> dict:
    """
    direction: 'bullish' or 'bearish'
    Checks all patterns relevant to that direction, returns the first
    one that's actually confirmed (shape present AND breakout happened).
    Returns {"confirmed": bool, "reason": str}
    """
    if direction == "bearish":
        for detector in (_detect_double_top, _detect_head_and_shoulders, _detect_descending_triangle):
            result = detector(df, highs, lows)
            if result:
                return result
        return {"confirmed": False, "reason": "no confirmed bearish chart pattern"}

    if direction == "bullish":
        for detector in (_detect_double_bottom, _detect_inverse_head_and_shoulders, _detect_ascending_triangle):
            result = detector(df, highs, lows)
            if result:
                return result
        return {"confirmed": False, "reason": "no confirmed bullish chart pattern"}

    return {"confirmed": False, "reason": "unknown direction"}
