"""
Tiny persistence layer so GitHub Actions runs (which are stateless
containers) don't spam duplicate alerts for the same setup.
State is stored in state.json and must be committed back to the repo
by the workflow after each run (see .github/workflows/sniper_alerts.yml).

Cooldown is tracked by wall-clock time, not a positional bar index.
Each live run fetches an independent, freshly-windowed candle set from
the API, so "position within that array" (e.g. len(df)-1) is NOT a
meaningful measure of elapsed time across separate runs — it's a
constant every single time, which would make the cooldown never expire
after the first alert. A real timestamp comparison is the only thing
that actually reflects time passing between runs.
"""

import json
import os
from datetime import datetime, timezone
from config import STATE_FILE


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def should_alert(state: dict, symbol: str, direction: str, current_time: datetime, min_gap) -> bool:
    """
    current_time: the timestamp to compare against (typically the latest
                  candle's datetime, or datetime.now(timezone.utc)).
    min_gap: a timedelta — minimum real time that must have passed since
             the last alert for this symbol/direction before alerting again.
    """
    key = f"{symbol}:{direction}"
    last_str = state.get(key)
    if last_str is None:
        return True

    try:
        last_time = datetime.fromisoformat(last_str)
    except (TypeError, ValueError):
        # Legacy/malformed entry (e.g. an old integer bar-index value from
        # before this fix) — can't compare meaningfully, so allow the alert
        # rather than silently staying muted on bad data.
        return True

    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    if last_time.tzinfo is None:
        last_time = last_time.replace(tzinfo=timezone.utc)

    return (current_time - last_time) >= min_gap


def mark_alerted(state: dict, symbol: str, direction: str, current_time: datetime):
    state[f"{symbol}:{direction}"] = current_time.isoformat()
