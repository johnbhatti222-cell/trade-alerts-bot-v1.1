"""
Classifies the current bar's time into a market session quality tag —
used as a tier modifier, not a confluence vote. A technically identical
setup means something different at the London/NY overlap (high
liquidity, moves more likely to follow through) than during a quiet
overnight session (thin liquidity, more prone to fakeouts).

Assumes timestamps are UTC, matching Twelve Data's convention for the
pairs this bot uses. If that assumption is ever wrong for your feed,
the session boundaries below need shifting accordingly.
"""

import pandas as pd
from config import SESSION_LONDON, SESSION_NY, SESSION_OVERLAP


def get_session(dt: pd.Timestamp) -> str:
    """
    Returns 'prime' (London/NY overlap), 'active' (a single major
    session), or 'quiet' (outside both).
    """
    hour = dt.hour

    overlap_start, overlap_end = SESSION_OVERLAP
    if overlap_start <= hour < overlap_end:
        return "prime"

    london_start, london_end = SESSION_LONDON
    ny_start, ny_end = SESSION_NY
    if (london_start <= hour < london_end) or (ny_start <= hour < ny_end):
        return "active"

    return "quiet"
