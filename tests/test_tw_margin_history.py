"""Margin balance is the second one-shot source, and it was keeping nothing.

TWSE publishes one MI_MARGN file and keeps no archive. The endpoint returned
today's snapshot — 1,291 issues, 515 reducing — and stored none of it, so every
session nobody fetched was permanently gone, with every test green.

A snapshot also cannot answer the question the data exists for. Price cannot
separate capitulation from continuation: both close at the low. A run of
sessions where forced sellers stop being forced can. On 2026-07-30 the
market-wide balance fell 0.72% while 406 issues *added* margin and 0050's own
rose 15.99% — deleveraging decelerating, visible only as a series.
"""

from __future__ import annotations

from datetime import UTC, datetime

from otto.local_terminal.twse_company import (
    default_margin_history_state,
    margin_session_row,
    margin_trend,
    merge_margin_session,
)


def _payload(stamp: str, change_pct: str, code: str = "0050", sym_pct: str = "-14.79") -> dict:
    return {
        "published_at": stamp,
        "issue_count": 1291,
        "margin_lots_today": 8901190,
        "margin_lots_prev": 9032004,
        "change_pct": change_pct,
        "reduced_symbol_count": 515,
        "increased_symbol_count": 548,
        "symbols": [
            {
                "code": code,
                "name": "元大台灣50",
                "margin_lots_today": 25389,
                "change_pct": sym_pct,
                "short_lots_today": 476,
            }
        ],
    }


def test_the_session_is_keyed_on_the_only_date_twse_gives() -> None:
    """The rows say 今日餘額 and carry no date; Last-Modified is all there is."""
    row = margin_session_row(_payload("Wed, 05 Aug 2026 21:23:22 GMT", "-1.45"))

    assert row is not None
    assert row["session"] == "2026-08-05"
    assert row["reduced_symbol_count"] == 515
    assert row["symbols"] == [
        {"code": "0050", "margin_lots_today": 25389, "change_pct": "-14.79"}
    ]


def test_a_payload_with_no_stamp_is_refused_rather_than_filed_under_a_guess() -> None:
    assert margin_session_row(_payload("", "-1.45")) is None
    assert margin_session_row(_payload("not a date", "-1.45")) is None

    state, report = merge_margin_session(default_margin_history_state(), None)

    assert report["added"] is False
    assert state["sessions"] == []


def test_the_same_session_fetched_twice_is_not_two_sessions() -> None:
    payload = _payload("Wed, 05 Aug 2026 21:23:22 GMT", "-1.45")
    state, first = merge_margin_session(default_margin_history_state(), margin_session_row(payload))
    state, second = merge_margin_session(state, margin_session_row(payload))

    assert first["added"] is True
    assert second["added"] is False
    assert second["held"] == 1


def test_an_existing_session_is_never_rewritten() -> None:
    """A published balance is a fact; a re-fetch must not revise history."""
    state, _ = merge_margin_session(
        default_margin_history_state(),
        margin_session_row(_payload("Wed, 05 Aug 2026 21:23:22 GMT", "-1.45")),
    )
    state, _ = merge_margin_session(
        state, margin_session_row(_payload("Wed, 05 Aug 2026 23:00:00 GMT", "+9.99"))
    )

    assert [r["change_pct"] for r in state["sessions"]] == ["-1.45"]


def test_the_trend_counts_the_run_a_single_snapshot_cannot_show() -> None:
    """Three sessions of deleveraging, then one that stops — the distinction."""
    state = default_margin_history_state()
    for day, pct in (("03", "-2.10"), ("04", "-1.80"), ("05", "-1.45")):
        state, _ = merge_margin_session(
            state, margin_session_row(_payload(f"Mon, {day} Aug 2026 21:00:00 GMT", pct))
        )

    assert margin_trend(state)["consecutive_reducing_sessions"] == 3

    state, _ = merge_margin_session(
        state, margin_session_row(_payload("Thu, 06 Aug 2026 21:00:00 GMT", "0.35"))
    )

    trend = margin_trend(state)
    assert trend["consecutive_reducing_sessions"] == 0, (
        "forced selling stopping is the signal; it must not be buried in a streak"
    )
    assert trend["sessions_held"] == ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06"]


def test_a_gap_reads_as_a_gap_not_a_quiet_market() -> None:
    state = default_margin_history_state()
    for day, pct in (("03", "-2.10"), ("06", "-1.45")):
        state, _ = merge_margin_session(
            state, margin_session_row(_payload(f"Mon, {day} Aug 2026 21:00:00 GMT", pct))
        )

    trend = margin_trend(state)

    assert trend["sessions_held"] == ["2026-08-03", "2026-08-06"]
    assert "a day nobody fetched" in trend["note"]


def test_the_store_is_capped(monkeypatch) -> None:
    from otto.local_terminal import twse_company

    monkeypatch.setattr(twse_company, "MAX_MARGIN_SESSIONS", 2)
    state = default_margin_history_state()
    now = datetime(2026, 8, 6, tzinfo=UTC)
    for day in ("03", "04", "05"):
        state, _ = merge_margin_session(
            state,
            margin_session_row(_payload(f"Mon, {day} Aug 2026 21:00:00 GMT", "-1.00")),
            now=now,
        )

    assert [r["session"] for r in state["sessions"]] == ["2026-08-04", "2026-08-05"]
