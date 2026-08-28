"""
The core sniper engine: combines structure, liquidity, zones, and
momentum into a single graded signal with entry/SL/TP1-3 and a
confidence score. This is where "do not force trades" is enforced -
if confluence is weak, it returns a NO_TRADE result.
"""

from config import WEIGHTS, MIN_CONFIDENCE_TO_ALERT, SL_ATR_BUFFER, RR_TP1, RR_TP2, RR_TP3
from indicators import atr
from structure import find_swings, htf_bias, detect_bos_choch
from liquidity import detect_liquidity_sweep
from zones import find_fvgs, find_last_order_block, price_in_zone
from momentum import check_momentum_confirmation
from chart_patterns import check_chart_pattern


NO_TRADE = {"decision": "NO_TRADE"}


def evaluate_pair(label: str, htf_df, ltf_df) -> dict:
    """
    Runs the full confluence check for one instrument.
    htf_df: higher-timeframe candles (trend bias)
    ltf_df: lower-timeframe candles (entry trigger)
    Returns a fully-formed signal dict, or {"decision": "NO_TRADE", "reason": ...}
    """
    bias = htf_bias(htf_df)
    if bias == "ranging":
        return {**NO_TRADE, "reason": f"{label}: HTF bias is ranging/unclear — no directional edge."}

    direction = "bullish" if bias == "bullish" else "bearish"

    ltf_highs, ltf_lows = find_swings(ltf_df)
    structure_event = detect_bos_choch(ltf_df, ltf_highs, ltf_lows)

    sweep = detect_liquidity_sweep(ltf_df, ltf_highs, ltf_lows)
    sweep_aligned = (
        (direction == "bullish" and sweep["type"] == "sell_side")
        or (direction == "bearish" and sweep["type"] == "buy_side")
    )

    ob = find_last_order_block(ltf_df, direction)
    fvgs = [f for f in find_fvgs(ltf_df) if f["type"] == direction]
    last_price = ltf_df["close"].iloc[-1]

    in_ob = price_in_zone(last_price, ob) if ob else False
    in_fvg = any(price_in_zone(last_price, f) for f in fvgs)
    zone_hit = in_ob or in_fvg

    momentum = check_momentum_confirmation(ltf_df, ltf_lows, ltf_highs, direction)
    pattern_check = check_chart_pattern(ltf_df, ltf_highs, ltf_lows, direction)

    # --- Confluence scoring ---
    score = 0
    reasons = []

    if (direction == "bullish" and structure_event in ("bos_bullish", "choch_bullish")) or \
       (direction == "bearish" and structure_event in ("bos_bearish", "choch_bearish")):
        score += WEIGHTS["bias_alignment"]
        reasons.append(f"LTF structure ({structure_event}) aligns with HTF {bias} bias")

    if zone_hit:
        score += WEIGHTS["zone_quality"]
        reasons.append("Price reacting at order block / fair value gap")

    if sweep_aligned:
        score += WEIGHTS["liquidity_sweep"]
        reasons.append(f"Liquidity sweep confirmed ({sweep['type']} at {sweep['level']:.4f})")

    if momentum["confirmed"]:
        score += WEIGHTS["momentum_confirmation"]
        reasons.append(momentum["reason"])

    if pattern_check["confirmed"]:
        score += WEIGHTS["chart_pattern"]
        reasons.append(pattern_check["reason"])

    if score < MIN_CONFIDENCE_TO_ALERT:
        return {
            **NO_TRADE,
            "reason": f"{label}: confluence score {score}/100 — below {MIN_CONFIDENCE_TO_ALERT} threshold. "
                      f"Found: {', '.join(reasons) if reasons else 'no meaningful confluence'}.",
        }

    # --- Build entry / SL / TP ---
    a = atr(ltf_df).iloc[-1]
    entry_zone = ob if in_ob else (fvgs[-1] if in_fvg else None)
    if entry_zone is None:
        entry_low, entry_high = last_price * 0.999, last_price * 1.001
    else:
        entry_low, entry_high = sorted([entry_zone["top"], entry_zone["bottom"]])

    entry_mid = (entry_low + entry_high) / 2

    # Only use the sweep's wick as an SL anchor if it's actually the RIGHT
    # kind of sweep for this direction (sweep_aligned). An unaligned sweep
    # (e.g. a buy_side sweep found while direction is bullish) belongs to
    # an unrelated setup and its wick price is not a meaningful invalidation
    # level here — using it regardless of alignment could anchor the SL to
    # an arbitrary, unrelated price far from the actual entry.
    aligned_wick = sweep["wick_extreme"] if sweep_aligned else None

    if direction == "bullish":
        invalidation = min(entry_low, aligned_wick or entry_low) - (a * SL_ATR_BUFFER)
        sl = invalidation
        risk = entry_mid - sl
        tp1 = entry_mid + risk * RR_TP1
        tp2 = entry_mid + risk * RR_TP2
        tp3 = entry_mid + risk * RR_TP3
        trade_direction = "BUY"
    else:
        invalidation = max(entry_high, aligned_wick or entry_high) + (a * SL_ATR_BUFFER)
        sl = invalidation
        risk = sl - entry_mid
        tp1 = entry_mid - risk * RR_TP1
        tp2 = entry_mid - risk * RR_TP2
        tp3 = entry_mid - risk * RR_TP3
        trade_direction = "SELL"

    rr_final = RR_TP2  # headline R:R quoted is TP2

    return {
        "decision": "TRADE",
        "label": label,
        "direction": trade_direction,
        "bias": bias,
        "entry_low": entry_low,
        "entry_high": entry_high,
        "sl": sl,
        "tp1": tp1,
        "tp2": tp2,
        "tp3": tp3,
        "rr": rr_final,
        "confidence": score,
        "invalidation": invalidation,
        "reasons": reasons,
        "structure_event": structure_event,
    }
