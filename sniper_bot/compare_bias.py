"""
Compares the old EMA-crossover HTF bias against the new structure-based
HTF bias, on identical historical data, for all three configured pairs
(or ones you specify). Uses the same walk-forward backtest engine as
backtest.py for both runs — only the bias function differs.

Usage:
    python compare_bias.py --bars 3000
    python compare_bias.py --bars 3000 --symbols "BTC/USD,USD/JPY"
"""

import argparse
import pandas as pd

import signal_engine
import structure
import legacy_bias
from config import PAIRS
from data_fetcher import fetch_candles
from backtest import run_backtest, compute_stats, filter_alertable

# Keep a reference to the current (new) bias function so we can restore it
# after temporarily monkey-patching signal_engine to use the old one.
NEW_BIAS_FN = structure.htf_bias
OLD_BIAS_FN = legacy_bias.htf_bias_ema


def run_one(symbol: str, label: str, ltf_df: pd.DataFrame, bias_fn) -> dict:
    signal_engine.htf_bias = bias_fn
    trades = run_backtest(symbol, label, ltf_df)
    # Only count trades that would actually reach Telegram live (tier >=
    # MIN_TIER_TO_ALERT) — otherwise sub-threshold (C-tier) setups dilute
    # the comparison with trades nobody would ever act on.
    alerted = filter_alertable(trades)
    stats = compute_stats(alerted, len(ltf_df))
    return stats


def fmt(stats: dict) -> str:
    if stats.get("n", 0) == 0:
        return "0 trades (flat)"
    return (
        f"{stats['n']} trades, {stats['win_rate']:.1f}% win, "
        f"total R {stats['total_r']:+.2f}, avg R {stats['avg_r']:+.2f}, "
        f"max DD {stats['max_dd']:.2f}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=int, default=3000)
    parser.add_argument("--symbols", default=None, help="comma-separated, e.g. 'BTC/USD,USD/JPY'. Default: all configured pairs.")
    args = parser.parse_args()

    if args.symbols:
        wanted = {s.strip() for s in args.symbols.split(",")}
        pairs = [p for p in PAIRS if p["symbol"] in wanted]
    else:
        pairs = PAIRS

    combined_old = []
    combined_new = []

    print(f"{'Pair':<20} {'OLD (EMA bias)':<55} {'NEW (structure bias)'}")
    print("-" * 130)

    for pair in pairs:
        symbol, label = pair["symbol"], pair["label"]
        ltf_df = fetch_candles(symbol, "5min", outputsize=args.bars)

        old_stats = run_one(symbol, label, ltf_df, OLD_BIAS_FN)
        new_stats = run_one(symbol, label, ltf_df, NEW_BIAS_FN)

        print(f"{label:<20} {fmt(old_stats):<55} {fmt(new_stats)}")

        if old_stats.get("n", 0) > 0:
            combined_old.append(old_stats)
        if new_stats.get("n", 0) > 0:
            combined_new.append(new_stats)

    signal_engine.htf_bias = NEW_BIAS_FN  # always leave it restored to current/live behavior

    def combine(stat_list):
        if not stat_list:
            return "0 trades total"
        n = sum(s["n"] for s in stat_list)
        wins = sum(s["wins"] for s in stat_list)
        total_r = sum(s["total_r"] for s in stat_list)
        win_rate = wins / n * 100 if n else 0
        return f"{n} trades, {win_rate:.1f}% win, total R {total_r:+.2f}"

    print("-" * 130)
    print(f"{'COMBINED':<20} {combine(combined_old):<55} {combine(combined_new)}")


if __name__ == "__main__":
    main()
