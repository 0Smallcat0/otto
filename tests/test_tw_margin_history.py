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
    deleveraging_progress,
    margin_session_row,
    margin_trend,
    merge_margin_session,
)


def _payload(
    stamp: str,
    change_pct: str,
    code: str = "0050",
    sym_pct: str = "-14.79",
    lots: int = 8901190,
) -> dict:
    return {
        "published_at": stamp,
        "issue_count": 1291,
        "margin_lots_today": lots,
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


# ── the comparison the streak could not make ──


def _series(*rows: tuple[str, str, int]):
    """(day, change_pct, lots) folded into a store, oldest first."""
    state = default_margin_history_state()
    for day, pct, lots in rows:
        state, _ = merge_margin_session(
            state,
            margin_session_row(_payload(f"Mon, {day} Aug 2026 21:00:00 GMT", pct, lots=lots)),
        )
    return state


def _candles(*rows: tuple[str, str]):
    return [{"closed_at": day, "close": close} for day, close in rows]


def test_the_index_falling_further_than_margin_reads_as_unfinished() -> None:
    """The real 2026-07-28 read: index -12.86%, margin -9.93%, not done.

    https://www.setn.com/news/1880517 — a bottom is not called while the tape
    has fallen further than the leverage behind it has unwound.
    """
    state = _series(
        ("03", "-3.00", 1_000_000),
        ("04", "-4.00", 950_000),
        ("05", "-2.93", 900_700),
    )
    progress = deleveraging_progress(
        state, _candles(("2026-08-03", "100.00"), ("2026-08-04", "92.00"), ("2026-08-05", "87.14"))
    )

    assert progress["margin_decline_pct"] == "-9.93"
    assert progress["index_decline_pct"] == "-12.86"
    assert progress["verdict"] == "incomplete"
    assert progress["window"] == ["2026-08-03", "2026-08-05"]


def test_margin_unwinding_faster_than_the_tape_is_the_other_answer() -> None:
    state = _series(("03", "-5.00", 1_000_000), ("04", "-8.00", 850_000))
    progress = deleveraging_progress(
        state, _candles(("2026-08-03", "100.00"), ("2026-08-04", "95.00"))
    )

    assert progress["verdict"] == "margin_led"


def test_a_long_streak_of_nothing_is_not_progress() -> None:
    """The number this replaces: three reducing sessions, deleveraging barely begun.

    consecutive_reducing_sessions counts days and cannot see distance. Three
    sessions of roughly -0.1% is a streak of three and gives back 0.3% against
    a market down 12%, which is the opposite of what a streak of three reads
    like on a screen.
    """
    state = _series(
        ("03", "-0.10", 1_000_000),
        ("04", "-0.10", 999_000),
        ("05", "-0.10", 998_000),
    )

    assert margin_trend(state)["consecutive_reducing_sessions"] == 3

    progress = deleveraging_progress(
        state, _candles(("2026-08-03", "100.00"), ("2026-08-05", "88.00"))
    )

    assert progress["margin_decline_pct"] == "-0.20"
    assert progress["verdict"] == "incomplete", (
        "a streak of three sessions must not read as deleveraging when the "
        "market has fallen sixty times further than margin has unwound"
    )


def test_an_index_cache_that_stops_short_is_said_so_not_compared_anyway() -> None:
    """A stale index leg silently compared over the wrong dates is a fake number."""
    state = _series(("03", "-3.00", 1_000_000), ("06", "-2.00", 900_000))
    progress = deleveraging_progress(
        state, _candles(("2026-08-03", "100.00"), ("2026-08-04", "92.00"))
    )

    assert progress["verdict"] == "unknown"
    assert progress["index_decline_pct"] is None
    assert "2026-08-04" in progress["reason"]
    assert "markets_history_refresh" in progress["reason"]
    # The half it does know is still reported rather than thrown away.
    assert progress["margin_decline_pct"] == "-10.00"


def test_one_session_cannot_have_a_cumulative_decline() -> None:
    state = _series(("05", "-1.45", 8_901_190))
    progress = deleveraging_progress(state, _candles(("2026-08-05", "100.00")))

    assert progress["verdict"] == "unknown"
    assert "at least two" in progress["reason"]


def test_a_rising_index_is_not_a_drawdown_to_measure_against() -> None:
    state = _series(("03", "-1.00", 1_000_000), ("04", "-1.00", 990_000))
    progress = deleveraging_progress(
        state, _candles(("2026-08-03", "100.00"), ("2026-08-04", "104.00"))
    )

    assert progress["verdict"] == "not_a_drawdown"
