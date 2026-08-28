"""
Lightweight indicator implementations (no TA-Lib dependency).
"""

import pandas as pd
import numpy as np
from config import ATR_PERIOD


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))

    # avg_loss == 0 means zero losses over the lookback window (a pure
    # trending move) — this makes rs = inf, which the code above turns
    # into NaN via the replace(0, nan) guard against real division errors.
    # That NaN was previously being silently filled to a neutral 50,
    # which is wrong: zero losses means RSI should read 100 (maximally
    # overbought), not neutral — exactly the condition momentum
    # confirmation most needs to detect. Only truly flat, no-movement
    # data (avg_gain also 0) is genuinely neutral.
    zero_loss = avg_loss == 0
    result = result.mask(zero_loss & (avg_gain > 0), 100.0)
    result = result.mask(zero_loss & (avg_gain == 0), 50.0)

    result = result.fillna(50)  # neutral only during the warm-up period (insufficient data)
    return result


def atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()
