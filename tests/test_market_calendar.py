"""Market-session guard: closed tape detection so the loop stops paying for it."""

from __future__ import annotations

from datetime import UTC, datetime

from otto.local_terminal.market_calendar import market_session, market_sessions_payload


def _at(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=UTC)


def test_weekend_closes_every_equity_market() -> None:
    sat = _at(2026, 7, 25, 12)  # Saturday, mid-day UTC
    assert market_session("us_equity", sat)["reason"] == "weekend"
    assert market_session("tw_equity", sat)["state"] == "closed"
    assert market_session("crypto", sat)["state"] == "open"
    payload = market_sessions_payload(sat)
    assert payload["all_equity_closed"] is True
    assert payload["any_equity_open"] is False


def test_us_regular_session_open_when_tw_is_after_hours() -> None:
    friday_14z = _at(2026, 7, 24, 14)  # 10:00 ET (open); 22:00 Taipei (closed)
    assert market_session("us_equity", friday_14z)["state"] == "open"
    assert market_session("tw_equity", friday_14z)["reason"] == "after_hours"
    payload = market_sessions_payload(friday_14z)
    assert payload["any_equity_open"] is True
    assert payload["all_equity_closed"] is False


def test_tw_regular_session_open_when_us_is_after_hours() -> None:
    friday_03z = _at(2026, 7, 24, 3)  # 11:00 Taipei (open); 23:00 ET prev (closed)
    assert market_session("tw_equity", friday_03z)["state"] == "open"
    assert market_session("us_equity", friday_03z)["reason"] == "after_hours"


def test_crypto_is_always_open() -> None:
    for moment in (_at(2026, 7, 25, 3), _at(2026, 7, 26, 18), _at(2026, 7, 24, 14)):
        assert market_session("crypto", moment) == {
            "market": "crypto",
            "state": "open",
            "reason": "24x7",
        }


def test_payload_is_naive_now_safe_and_notes_approximation() -> None:
    naive = datetime(2026, 7, 25, 12)  # no tzinfo → treated as UTC, must not crash
    payload = market_sessions_payload(naive)
    assert payload["all_equity_closed"] is True
    assert "holidays" in payload["note"].lower()
    assert payload["safety"]["external_calls"] is False
