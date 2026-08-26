"""
Pulls OHLC candles from Twelve Data and returns clean pandas DataFrames.
"""

import requests
import pandas as pd
from config import TWELVE_DATA_API_KEY, CANDLE_COUNT

BASE_URL = "https://api.twelvedata.com/time_series"


def fetch_candles(symbol: str, interval: str, outputsize: int = CANDLE_COUNT) -> pd.DataFrame:
    """
    Fetch candles for a symbol/interval from Twelve Data.
    Returns a DataFrame sorted oldest -> newest with columns:
    datetime, open, high, low, close, volume
    """
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": TWELVE_DATA_API_KEY,
        "format": "JSON",
    }
    resp = requests.get(BASE_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    if "values" not in data:
        raise RuntimeError(f"Twelve Data error for {symbol}/{interval}: {data}")

    df = pd.DataFrame(data["values"])
    df = df.rename(columns={"datetime": "datetime"})
    numeric_cols = ["open", "high", "low", "close"]
    if "volume" in df.columns:
        numeric_cols.append("volume")
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime").reset_index(drop=True)
    return df
