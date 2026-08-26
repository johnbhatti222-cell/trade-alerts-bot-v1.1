"""
Formats a signal dict into the exact structured alert format and
sends it to Telegram.
"""

import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, LTF_INTERVAL


def format_signal_message(signal: dict) -> str:
    return (
        f"🎯 *SNIPER SETUP — {signal['label']}*\n\n"
        f"*Direction:* {signal['direction']}\n"
        f"*Market Bias:* {signal['bias'].upper()}\n"
        f"*Timeframe:* {LTF_INTERVAL} entry / 4H bias\n\n"
        f"*Entry Zone:* {signal['entry_low']:.4f} – {signal['entry_high']:.4f}\n"
        f"*Stop Loss:* {signal['sl']:.4f}\n"
        f"*TP1:* {signal['tp1']:.4f}\n"
        f"*TP2:* {signal['tp2']:.4f}\n"
        f"*TP3:* {signal['tp3']:.4f}\n"
        f"*Risk:Reward (to TP2):* 1:{signal['rr']:.1f}\n\n"
        f"*Confidence Score:* {signal['confidence']}/100\n"
        f"*Invalidation Level:* {signal['invalidation']:.4f}\n"
        f"*Structural Event:* {signal['structure_event']}\n\n"
        f"*Confluences:*\n" + "\n".join(f"• {r}" for r in signal["reasons"]) + "\n\n"
        f"⚠️ Not financial advice. Manage risk — size positions off the SL distance, not conviction."
    )


def format_no_trade_message(label: str, reason: str) -> str:
    return f"🚫 *{label}: NO TRADE — WAIT FOR CONFIRMATION*\n{reason}"


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Telegram credentials missing — set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.")

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    resp = requests.post(url, data=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()
