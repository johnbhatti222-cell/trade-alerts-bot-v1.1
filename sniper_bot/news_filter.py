"""
High-impact news filter. Blocks alerts around major economic releases
(NFP, CPI, rate decisions, etc.) that can invalidate technical setups
in minutes regardless of how clean the chart looks.

Uses Finnhub's free economic calendar endpoint. Get a free API key at
https://finnhub.io/register and set FINNHUB_API_KEY as an env var / secret.
"""

import requests
from datetime import datetime, timedelta, timezone
from config import (
    FINNHUB_API_KEY,
    NEWS_BLACKOUT_MINUTES_BEFORE,
    NEWS_BLACKOUT_MINUTES_AFTER,
    NEWS_MIN_IMPACT,
)

CALENDAR_URL = "https://finnhub.io/api/v1/calendar/economic"


def fetch_upcoming_events(days_ahead: int = 2) -> list:
    """
    Pulls economic calendar events for today through `days_ahead` days out.
    Returns a list of dicts with at least: event, country, time, impact.
    Fails soft (returns []) if the API key is missing or the call errors -
    a news filter that silently breaks should never be the reason the whole
    bot goes down.
    """
    if not FINNHUB_API_KEY:
        print("[news_filter] No FINNHUB_API_KEY set — skipping news filter (running blind to news).")
        return []

    today = datetime.now(timezone.utc).date()
    end = today + timedelta(days=days_ahead)

    params = {
        "from": today.isoformat(),
        "to": end.isoformat(),
        "token": FINNHUB_API_KEY,
    }
    try:
        resp = requests.get(CALENDAR_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("economicCalendar", [])
    except Exception as e:
        print(f"[news_filter] Failed to fetch economic calendar: {e} — proceeding without news filter.")
        return []


def _impact_rank(impact: str) -> int:
    order = {"low": 1, "medium": 2, "high": 3}
    return order.get((impact or "").lower(), 0)


def is_in_news_blackout(currencies: list) -> dict:
    """
    Checks whether "now" falls inside a blackout window around any
    high-impact event for the given currencies (e.g. ['USD'] or ['USD', 'JPY']).

    Returns {"blackout": bool, "event": str or None}
    """
    events = fetch_upcoming_events()
    if not events:
        return {"blackout": False, "event": None}

    now = datetime.now(timezone.utc)
    min_rank = _impact_rank(NEWS_MIN_IMPACT)

    for ev in events:
        country = (ev.get("country") or "").upper()
        if country not in currencies:
            continue
        if _impact_rank(ev.get("impact")) < min_rank:
            continue

        ev_time_raw = ev.get("time")  # Finnhub returns "YYYY-MM-DD HH:MM:SS" UTC
        if not ev_time_raw:
            continue
        try:
            ev_time = datetime.strptime(ev_time_raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        window_start = ev_time - timedelta(minutes=NEWS_BLACKOUT_MINUTES_BEFORE)
        window_end = ev_time + timedelta(minutes=NEWS_BLACKOUT_MINUTES_AFTER)

        if window_start <= now <= window_end:
            label = f"{ev.get('event', 'High-impact event')} ({country}) at {ev_time_raw} UTC"
            return {"blackout": True, "event": label}

    return {"blackout": False, "event": None}
