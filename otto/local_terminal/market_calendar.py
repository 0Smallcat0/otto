"""Market-session guard so the decision loop stops paying for a closed tape.

The 30-minute loop fires around the clock, but on weekends and after hours the
equity tape is frozen: a scan then reports Friday's move as today's "biggest
mover", and each round pays to fetch quotes/news that cannot have changed. This
is a cheap, no-network calendar the loop can check FIRST — if the equity
markets are closed it can skip the heavy fetch churn and honestly hold, instead
of mistaking stale quotes for fresh signals.

Deliberately approximate and honest about it:
- regular sessions only (no pre/post-market), and it ignores exchange holidays;
- US hours are expressed in UTC assuming EDT (summer) and shift ~1h under EST,
  so intraday edges near the open/close can be off by an hour half the year;
- a weekend "closed", which is the case that actually wastes money, is exact.
Crypto trades 24x7, so it is always open.
"""

from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Any

# Regular cash sessions expressed in UTC. TW has no DST so its window is exact;
# US assumes EDT (summer) — see the module docstring caveat.
WEEKDAY_SESSIONS: dict[str, tuple[time, time]] = {
    "us_equity": (time(13, 30), time(20, 0)),  # ~09:30-16:00 America/New_York (EDT)
    "tw_equity": (time(1, 0), time(5, 30)),  # 09:00-13:30 Asia/Taipei (UTC+8)
}
CALENDAR_MARKETS = ("crypto", "us_equity", "tw_equity")


def market_session(market: str, now: datetime) -> dict[str, Any]:
    """State of one market at `now` (a UTC-aware datetime)."""
    if market == "crypto":
        return {"market": market, "state": "open", "reason": "24x7"}
    hours = WEEKDAY_SESSIONS.get(market)
    if hours is None:
        return {"market": market, "state": "unknown", "reason": "no_calendar"}
    if now.weekday() >= 5:  # Sat/Sun (UTC weekday aligns with both windows)
        return {"market": market, "state": "closed", "reason": "weekend"}
    open_t, close_t = hours
    if open_t <= now.timetz().replace(tzinfo=None) <= close_t:
        return {"market": market, "state": "open", "reason": "regular_session"}
    return {"market": market, "state": "closed", "reason": "after_hours"}


def market_sessions_payload(now: datetime | None = None) -> dict[str, Any]:
    """Per-market open/closed with an all_equity_closed flag for the loop."""
    now = now or datetime.now(tz=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    sessions = [market_session(market, now) for market in CALENDAR_MARKETS]
    equity = [s for s in sessions if s["market"] != "crypto"]
    any_equity_open = any(s["state"] == "open" for s in equity)
    return {
        "as_of": now.isoformat(timespec="seconds"),
        "sessions": sessions,
        "any_equity_open": any_equity_open,
        "all_equity_closed": not any_equity_open,
        "note": (
            "Approximate: regular cash sessions only, ignores exchange holidays; "
            "US hours assume EDT and shift ~1h under EST, so intraday edges can be "
            "off by an hour half the year. A weekend 'closed' is exact. When a "
            "market is closed its scan change_pct is the last session's move, not "
            "today's — do not read it as a fresh signal. crypto is 24x7."
        ),
        "safety": {"read_only": True, "external_calls": False},
    }
