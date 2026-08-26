"""
Tiny persistence layer so GitHub Actions runs (which are stateless
containers) don't spam duplicate alerts for the same setup.
State is stored in state.json and must be committed back to the repo
by the workflow after each run (see .github/workflows/sniper_alerts.yml).
"""

import json
import os
from config import STATE_FILE, COOLDOWN_BARS


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def should_alert(state: dict, symbol: str, direction: str, current_bar_index: int) -> bool:
    key = f"{symbol}:{direction}"
    last_index = state.get(key)
    if last_index is None:
        return True
    return (current_bar_index - last_index) >= COOLDOWN_BARS


def mark_alerted(state: dict, symbol: str, direction: str, current_bar_index: int):
    state[f"{symbol}:{direction}"] = current_bar_index
