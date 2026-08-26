"""
Entry point. For each configured pair:
  1. Pull HTF + LTF candles from Twelve Data
  2. Run the sniper confluence engine
  3. If a high-confidence setup exists (and isn't in cooldown) -> send Telegram alert
  4. Otherwise -> log NO TRADE (only sent to Telegram if VERBOSE_NO_TRADE=1)

Run manually with: python main.py
Run on schedule via GitHub Actions (see .github/workflows/sniper_alerts.yml)
"""

import os
import time
import traceback

from config import PAIRS, HTF_INTERVAL, LTF_INTERVAL
from data_fetcher import fetch_candles
from signal_engine import evaluate_pair
from telegram_bot import format_signal_message, format_no_trade_message, send_telegram_message
from state import load_state, save_state, should_alert, mark_alerted
from news_filter import is_in_news_blackout

VERBOSE_NO_TRADE = os.environ.get("VERBOSE_NO_TRADE", "0") == "1"


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
                bar_index = len(ltf_df) - 1
                if should_alert(state, symbol, result["direction"], bar_index):
                    msg = format_signal_message(result)
                    send_telegram_message(msg)
                    mark_alerted(state, symbol, result["direction"], bar_index)
                    print(f"[ALERTED] {label}: {result['direction']} confidence={result['confidence']}")
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
