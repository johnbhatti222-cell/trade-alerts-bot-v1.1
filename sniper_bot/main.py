"""
Entry point. For each configured pair:
  1. Pull HTF + LTF candles from Twelve Data
  2. Run the sniper confluence engine (returns a graded tier: A+/A/B/C, or None)
  3. If the tier meets MIN_TIER_TO_ALERT (and isn't in cooldown) -> send Telegram alert
  4. Otherwise -> log it (only sent to Telegram if VERBOSE_NO_TRADE=1)

Run manually with: python main.py
Run on schedule via GitHub Actions (see .github/workflows/sniper_alerts.yml)
"""

import os
import time
import traceback
import pandas as pd

from config import PAIRS, HTF_INTERVAL, LTF_INTERVAL, COOLDOWN_BARS, MIN_TIER_TO_ALERT
from data_fetcher import fetch_candles
from signal_engine import evaluate_pair
from telegram_bot import format_signal_message, format_no_trade_message, send_telegram_message
from state import load_state, save_state, should_alert, mark_alerted
from news_filter import is_in_news_blackout
from tiering import meets_minimum

VERBOSE_NO_TRADE = os.environ.get("VERBOSE_NO_TRADE", "0") == "1"

# Cooldown expressed as real elapsed time (COOLDOWN_BARS worth of LTF
# candles), since live runs don't share a persistent bar index across
# separate process invocations — see state.py for why.
COOLDOWN_GAP = pd.Timedelta(LTF_INTERVAL) * COOLDOWN_BARS


def run():
    state = load_state()

    for pair in PAIRS:
        symbol = pair["symbol"]
        label = pair["label"]
        try:
            news_check = is_in_news_blackout(pair.get("currencies", []))
            if news_check["blackout"]:
                reason = f"{label}: NEWS BLACKOUT — {news_check['event']}. Standing aside for capital preservation."
                print(f"[NO TRADE - NEWS] {reason}")
                if VERBOSE_NO_TRADE:
                    send_telegram_message(format_no_trade_message(label, reason))
                time.sleep(1)
                continue

            htf_df = fetch_candles(symbol, HTF_INTERVAL)
            ltf_df = fetch_candles(symbol, LTF_INTERVAL)

            result = evaluate_pair(label, htf_df, ltf_df)

            if result["decision"] == "TRADE":
                tier = result["tier"]
                if not meets_minimum(tier, MIN_TIER_TO_ALERT):
                    print(f"[TIER TOO LOW] {label}: {result['direction']} tier={tier} confidence={result['confidence']} "
                          f"session={result['session']} — below MIN_TIER_TO_ALERT={MIN_TIER_TO_ALERT}")
                    if VERBOSE_NO_TRADE:
                        send_telegram_message(format_no_trade_message(
                            label, f"tier {tier} (confidence {result['confidence']}, session {result['session']}) "
                                   f"— below the {MIN_TIER_TO_ALERT} minimum to alert"))
                    continue

                latest_time = ltf_df.iloc[-1]["datetime"]
                if should_alert(state, symbol, result["direction"], latest_time, COOLDOWN_GAP):
                    msg = format_signal_message(result)
                    send_telegram_message(msg)
                    mark_alerted(state, symbol, result["direction"], latest_time)
                    print(f"[ALERTED] {label}: {result['direction']} tier={tier} confidence={result['confidence']}")
                else:
                    print(f"[SKIPPED-COOLDOWN] {label}: {result['direction']} already alerted recently")
            else:
                print(f"[NO TRADE] {result['reason']}")
                if VERBOSE_NO_TRADE:
                    send_telegram_message(format_no_trade_message(label, result["reason"]))

        except Exception as e:
            print(f"[ERROR] {label}: {e}")
            traceback.print_exc()

        time.sleep(1)  # be gentle on API rate limits

    save_state(state)


if __name__ == "__main__":
    run()
