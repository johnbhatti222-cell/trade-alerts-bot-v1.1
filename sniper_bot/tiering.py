"""
Converts a raw confluence score + market session into a trade tier.
This replaces the old single binary threshold (>=70 or nothing) with a
graded output, so setups that are "good but not perfect" or "perfect
but in a quiet session" are visible and labeled, rather than fully
suppressed.

Tiers, highest to lowest conviction:
  A+  : perfect confluence (100) during a high-liquidity session
  A   : perfect confluence in a quiet session, OR strong confluence (75+)
        during a high-liquidity session
  B   : strong confluence (75+) during a quiet session
  C   : moderate confluence (50-74) — below "strong", regardless of session
  None: below 50, or no directional bias — not worth reporting at all
"""

TIER_ORDER = ["C", "B", "A", "A+"]  # low to high, for threshold comparisons


def determine_tier(score: int, session: str) -> str | None:
    good_session = session in ("prime", "active")

    if score >= 100:
        return "A+" if good_session else "A"
    if score >= 75:
        return "A" if good_session else "B"
    if score >= 50:
        return "C"
    return None


def meets_minimum(tier: str | None, min_tier: str) -> bool:
    """True if `tier` is at or above `min_tier` in conviction. None never meets any minimum."""
    if tier is None:
        return False
    return TIER_ORDER.index(tier) >= TIER_ORDER.index(min_tier)
