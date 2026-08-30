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

from config import LTF_INTERVAL, HTF_INTERVAL, COOLDOWN_BARS, MIN_TIER_TO_ALERT
from data_fetcher import fetch_candles
from signal_engine import evaluate_pair
from tiering import meets_minimum

# How many LTF bars of trailing history the engine gets to look at,
# same as the live bot's CANDLE_COUNT — keeps backtest behaviour
# identical to production.
ENGINE_WINDOW = 150
MAX_HOLD_BARS = 200          # give up on an open trade after this many bars
HTF_RESAMPLE_RULE = "15min"  # must match HTF_INTERVAL's timeframe


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


# How many trailing HTF bars evaluate_pair() gets to look at — matches
# CANDLE_COUNT in config.py (what the live bot actually fetches each run),
# so backtest behavior mirrors production instead of growing unboundedly.
HTF_WINDOW_CAP = 150


def run_backtest(symbol: str, label: str, ltf_df: pd.DataFrame) -> pd.DataFrame:
    trades = []
    last_alert_bar = {"BUY": -999, "SELL": -999}

    # Precompute the full HTF resample ONCE (not once per bar — that was
    # the O(n^2) bottleneck). Completed HTF bars never change once formed,
    # so it's safe to reuse this and just slice up to "now" for each bar.
    full_htf_df = resample_to_htf(ltf_df)
    htf_bucket_starts = full_htf_df["datetime"].values

    start = ENGINE_WINDOW + 20  # need enough history before we start evaluating
    for i in range(start, len(ltf_df) - 1):
        window = ltf_df.iloc[max(0, i - ENGINE_WINDOW): i + 1].reset_index(drop=True)

        current_time = ltf_df.iloc[i]["datetime"]
        bucket_start = current_time.floor(HTF_RESAMPLE_RULE)
        # Only HTF bars that fully closed before the current bucket started
        # are usable — this is what actually prevents lookahead.
        idx = htf_bucket_starts.searchsorted(bucket_start, side="left")
        htf_window = full_htf_df.iloc[max(0, idx - HTF_WINDOW_CAP): idx]

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
            "tier": result["tier"],
            "session": result["session"],
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


def compute_stats(trades: pd.DataFrame, total_bars: int) -> dict:
    """Pure stats computation, reusable by both the CLI and the bias comparison script."""
    if trades.empty:
        return {"n": 0, "total_bars": total_bars}

    n = len(trades)
    wins = int((trades["r_multiple"] > 0).sum())
    losses = int((trades["r_multiple"] < 0).sum())
    timeouts = int((trades["r_multiple"] == 0).sum())
    win_rate = wins / n * 100
    total_r = float(trades["r_multiple"].sum())
    avg_r = float(trades["r_multiple"].mean())

    equity = trades["r_multiple"].cumsum()
    running_max = equity.cummax()
    drawdown = equity - running_max
    max_dd = float(drawdown.min())

    return {
        "n": n, "total_bars": total_bars, "wins": wins, "losses": losses,
        "timeouts": timeouts, "win_rate": win_rate, "total_r": total_r,
        "avg_r": avg_r, "max_dd": max_dd, "equity": equity,
    }


def filter_alertable(trades: pd.DataFrame) -> pd.DataFrame:
    """
    Filters to only the trades that would actually reach Telegram live —
    i.e. tier >= MIN_TIER_TO_ALERT. Sub-threshold tiers (typically C) are
    still computed and recorded for the tier-comparison breakdown, but
    including them in the headline stats would overstate real trade
    frequency and dilute win-rate/R numbers with setups nobody ever acts on.
    """
    if trades.empty or "tier" not in trades.columns:
        return trades
    mask = trades["tier"].apply(lambda t: meets_minimum(t, MIN_TIER_TO_ALERT))
    return trades[mask].reset_index(drop=True)


def summarize(trades: pd.DataFrame, total_bars: int):
    alerted = filter_alertable(trades)
    stats = compute_stats(alerted, total_bars)
    if stats["n"] == 0:
        print(f"No trades met the {MIN_TIER_TO_ALERT} tier threshold — engine stayed flat throughout "
              f"(from the user's perspective; {len(trades)} sub-threshold setups were scored but never alerted).")
        return

    print("\n=== BACKTEST SUMMARY (alerted trades only, tier >= " + MIN_TIER_TO_ALERT + ") ===")
    print(f"Bars scanned:        {stats['total_bars']}")
    print(f"Trades alerted:      {stats['n']}  ({stats['n'] / total_bars * 100:.2f}% of bars)")
    if len(trades) > stats["n"]:
        print(f"  (of {len(trades)} total setups scored; {len(trades) - stats['n']} were sub-threshold and never alerted)")
    print(f"Wins / Losses / TO:  {stats['wins']} / {stats['losses']} / {stats['timeouts']}")
    print(f"Win rate:            {stats['win_rate']:.1f}%")
    print(f"Total R:             {stats['total_r']:.2f}")
    print(f"Average R / trade:   {stats['avg_r']:.2f}")
    print(f"Max drawdown (R):    {stats['max_dd']:.2f}")
    print(f"By outcome:\n{alerted['outcome'].value_counts()}")

    if "tier" in trades.columns:
        print("\nBy tier, ALL scored setups including sub-threshold (does higher conviction actually perform better?):")
        for tier_name in ["A+", "A", "B", "C"]:
            tier_trades = trades[trades["tier"] == tier_name]
            if len(tier_trades) == 0:
                continue
            t_wins = (tier_trades["r_multiple"] > 0).sum()
            t_win_rate = t_wins / len(tier_trades) * 100
            t_total_r = tier_trades["r_multiple"].sum()
            t_avg_r = tier_trades["r_multiple"].mean()
            print(f"  {tier_name:<3} — {len(tier_trades)} trades, {t_win_rate:.1f}% win, "
                  f"total R {t_total_r:+.2f}, avg R {t_avg_r:+.2f}")

    equity = stats["equity"]
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
