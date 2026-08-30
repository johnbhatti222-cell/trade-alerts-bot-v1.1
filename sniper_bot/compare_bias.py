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

# structure.htf_bias is EMA-crossover (currently live).
# legacy_bias.htf_bias_structure is BOS/CHoCH + swing sequence (not live —
# tested worse in a real-data comparison; kept here for future re-testing).
LIVE_BIAS_FN = structure.htf_bias
ALT_BIAS_FN = legacy_bias.htf_bias_structure


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

    combined_live = []
    combined_alt = []

    print(f"{'Pair':<20} {'LIVE (EMA bias)':<55} {'ALT (structure bias)'}")
    print("-" * 130)

    for pair in pairs:
        symbol, label = pair["symbol"], pair["label"]
        ltf_df = fetch_candles(symbol, "5min", outputsize=args.bars)

        live_stats = run_one(symbol, label, ltf_df, LIVE_BIAS_FN)
        alt_stats = run_one(symbol, label, ltf_df, ALT_BIAS_FN)

        print(f"{label:<20} {fmt(live_stats):<55} {fmt(alt_stats)}")

        if live_stats.get("n", 0) > 0:
            combined_live.append(live_stats)
        if alt_stats.get("n", 0) > 0:
            combined_alt.append(alt_stats)

    signal_engine.htf_bias = LIVE_BIAS_FN  # always leave it restored to current/live behavior

    def combine(stat_list):
        if not stat_list:
            return "0 trades total"
        n = sum(s["n"] for s in stat_list)
        wins = sum(s["wins"] for s in stat_list)
        total_r = sum(s["total_r"] for s in stat_list)
        win_rate = wins / n * 100 if n else 0
        return f"{n} trades, {win_rate:.1f}% win, total R {total_r:+.2f}"

    print("-" * 130)
    print(f"{'COMBINED':<20} {combine(combined_live):<55} {combine(combined_alt)}")


if __name__ == "__main__":
    main()
