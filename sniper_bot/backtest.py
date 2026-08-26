"""
Walk-forward backtest for the sniper signal engine.

For each historical bar, it feeds the engine only the data that would
have been available at that moment (no lookahead), records any TRADE
signal, then simulates forward to see which level — SL, TP1, TP2, or
TP3 — gets touched first. Produces a trade log CSV, an equity curve
PNG, and a printed summary.

Usage:
    python backtest.py --symbol BTC/USD --bars 3000
    python backtest.py --csv my_data.csv          # use your own OHLC data instead of the API

CSV format expected if using --csv: columns datetime,open,high,low,close
"""

import argparse
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import LTF_INTERVAL, HTF_INTERVAL, COOLDOWN_BARS
from data_fetcher import fetch_candles
from signal_engine import evaluate_pair

# How many LTF bars of trailing history the engine gets to look at,
# same as the live bot's CANDLE_COUNT — keeps backtest behaviour
# identical to production.
ENGINE_WINDOW = 150
MAX_HOLD_BARS = 200          # give up on an open trade after this many bars
HTF_RESAMPLE_RULE = "4h"     # must match HTF_INTERVAL's timeframe


def resample_to_htf(ltf_df: pd.DataFrame, rule: str = HTF_RESAMPLE_RULE) -> pd.DataFrame:
    """Builds higher-timeframe candles from LTF data up to the current point (no lookahead)."""
    df = ltf_df.set_index("datetime")
    htf = df.resample(rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"})
    htf = htf.dropna().reset_index()
    return htf


def simulate_trade(future_df: pd.DataFrame, signal: dict) -> dict:
    """
    Walks forward bar by bar from the signal point and returns which
    level was touched first: 'sl', 'tp1', 'tp2', 'tp3', or 'timeout'.
    """
    direction = signal["direction"]
    sl, tp1, tp2, tp3 = signal["sl"], signal["tp1"], signal["tp2"], signal["tp3"]

    for _, bar in future_df.head(MAX_HOLD_BARS).iterrows():
        if direction == "BUY":
            hit_sl = bar["low"] <= sl
            hit_tp3 = bar["high"] >= tp3
            hit_tp2 = bar["high"] >= tp2
            hit_tp1 = bar["high"] >= tp1
        else:
            hit_sl = bar["high"] >= sl
            hit_tp3 = bar["low"] <= tp3
            hit_tp2 = bar["low"] <= tp2
            hit_tp1 = bar["low"] <= tp1

        # Conservative assumption: if SL and a TP are hit in the same
        # bar, count it as the SL (protects against overstating results).
        if hit_sl:
            return {"outcome": "sl", "r": -1.0}
        if hit_tp3:
            return {"outcome": "tp3", "r": 3.0}
        if hit_tp2:
            return {"outcome": "tp2", "r": 2.0}
        if hit_tp1:
            return {"outcome": "tp1", "r": 1.0}

    return {"outcome": "timeout", "r": 0.0}


def run_backtest(symbol: str, label: str, ltf_df: pd.DataFrame) -> pd.DataFrame:
    trades = []
    last_alert_bar = {"BUY": -999, "SELL": -999}

    start = ENGINE_WINDOW + 20  # need enough history before we start evaluating
    for i in range(start, len(ltf_df) - 1):
        window = ltf_df.iloc[max(0, i - ENGINE_WINDOW): i + 1].reset_index(drop=True)
        htf_window = resample_to_htf(ltf_df.iloc[: i + 1])
        if len(htf_window) < 60:
            continue

        result = evaluate_pair(label, htf_window, window)
        if result["decision"] != "TRADE":
            continue

        direction = result["direction"]
        if (i - last_alert_bar[direction]) < COOLDOWN_BARS:
            continue

        future = ltf_df.iloc[i + 1:].reset_index(drop=True)
        outcome = simulate_trade(future, result)

        trades.append({
            "datetime": ltf_df.iloc[i]["datetime"],
            "bar_index": i,
            "direction": direction,
            "confidence": result["confidence"],
            "entry_low": result["entry_low"],
            "entry_high": result["entry_high"],
            "sl": result["sl"],
            "tp1": result["tp1"],
            "tp2": result["tp2"],
            "tp3": result["tp3"],
            "outcome": outcome["outcome"],
            "r_multiple": outcome["r"],
        })
        last_alert_bar[direction] = i

    return pd.DataFrame(trades)


def summarize(trades: pd.DataFrame, total_bars: int):
    if trades.empty:
        print("No trades were triggered over this dataset — engine stayed flat throughout.")
        return

    n = len(trades)
    wins = (trades["r_multiple"] > 0).sum()
    losses = (trades["r_multiple"] < 0).sum()
    timeouts = (trades["r_multiple"] == 0).sum()
    win_rate = wins / n * 100
    total_r = trades["r_multiple"].sum()
    avg_r = trades["r_multiple"].mean()

    equity = trades["r_multiple"].cumsum()
    running_max = equity.cummax()
    drawdown = equity - running_max
    max_dd = drawdown.min()

    print("\n=== BACKTEST SUMMARY ===")
    print(f"Bars scanned:        {total_bars}")
    print(f"Trades triggered:    {n}  ({n / total_bars * 100:.2f}% of bars — engine mostly said NO TRADE)")
    print(f"Wins / Losses / TO:  {wins} / {losses} / {timeouts}")
    print(f"Win rate:            {win_rate:.1f}%")
    print(f"Total R:             {total_r:.2f}")
    print(f"Average R / trade:   {avg_r:.2f}")
    print(f"Max drawdown (R):    {max_dd:.2f}")
    print(f"By outcome:\n{trades['outcome'].value_counts()}")

    plt.figure(figsize=(10, 5))
    plt.plot(equity.values)
    plt.title("Equity Curve (cumulative R multiples)")
    plt.xlabel("Trade #")
    plt.ylabel("Cumulative R")
    plt.grid(alpha=0.3)
    plt.savefig("backtest_equity_curve.png", dpi=150, bbox_inches="tight")
    print("\nSaved: backtest_equity_curve.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default="BTC/USD")
    parser.add_argument("--label", default=None)
    parser.add_argument("--bars", type=int, default=3000, help="how many LTF candles to pull from the API")
    parser.add_argument("--csv", default=None, help="path to a local CSV instead of hitting the API")
    args = parser.parse_args()

    label = args.label or args.symbol

    if args.csv:
        ltf_df = pd.read_csv(args.csv, parse_dates=["datetime"]).sort_values("datetime").reset_index(drop=True)
    else:
        ltf_df = fetch_candles(args.symbol, LTF_INTERVAL, outputsize=args.bars)

    print(f"Backtesting {label} on {len(ltf_df)} bars of {LTF_INTERVAL} data...")
    trades = run_backtest(args.symbol, label, ltf_df)

    if not trades.empty:
        trades.to_csv("backtest_trades.csv", index=False)
        print("Saved: backtest_trades.csv")

    summarize(trades, len(ltf_df))


if __name__ == "__main__":
    main()
