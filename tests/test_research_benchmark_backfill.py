"""Benchmark levels reconstructed for calls struck before stamping existed.

Stamping shipped 2026-07-30; every call journaled before it carries no index
level on either end, so "did this beat owning the market" — the question the
ledger was built to answer — could not be answered for the entire existing
record. A published daily close recovers it. These pin the two things that make
that honest: the reconstruction never pretends to be a live stamp, and it never
silently invents a session the exchange did not print.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from otto.local_terminal import yahoo_data
from otto.local_terminal.research_ledger import (
    BENCHMARK_SOURCE_BACKFILL,
    BENCHMARK_SOURCE_LIVE,
    BENCHMARK_SOURCE_SELF,
    backfill_benchmarks,
    default_research_ledger_state,
    record_call,
    research_ledger_payload,
    score_calls,
)

# 07-25 and 07-26 are a weekend: a call struck then has no close of its own.
TW_CLOSES = {
    "0050.TW": {
        "2026-07-24": "101.70",
        "2026-07-27": "101.45",
        "2026-07-28": "97.15",
        "2026-07-29": "93.70",
        "2026-07-31": "102.85",
    }
}


def _record(state, **kw):
    payload = {
        "symbol": "2330.TW",
        "stance": "hold",
        "thesis": "reasoning goes here",
        "ref_price": "2355",
        "horizon_days": 30,
    }
    payload.update(kw)
    return record_call(state, payload)


def _struck_on(call: dict, day: str) -> None:
    """Backdate a call so it looks like one journaled before stamping existed.

    matures_at travels with as_of: a call whose strike date moves but whose
    maturity does not is not a historical call, it is an inconsistent one.
    """
    struck = datetime.fromisoformat(f"{day}T05:00:00+00:00")
    call["as_of"] = struck.isoformat(timespec="seconds")
    call["matures_at"] = (struck + timedelta(days=int(call["horizon_days"]))).isoformat(
        timespec="seconds"
    )
    call["benchmark_ref_price"] = None
    call["benchmark_ref_source"] = None


def test_backfill_falls_back_to_the_previous_session_and_names_it() -> None:
    state, call = _record(default_research_ledger_state())
    _struck_on(call, "2026-07-25")  # Saturday

    state, report = backfill_benchmarks(state, TW_CLOSES)

    filled = state["calls"][0]
    assert filled["benchmark_ref_price"] == "101.70"
    # The date recorded is the session actually used, not the call's own day.
    assert filled["benchmark_ref_session"] == "2026-07-24"
    assert filled["benchmark_ref_source"] == BENCHMARK_SOURCE_BACKFILL
    assert report["filled_count"] == 1


def test_backfill_never_overwrites_a_level_stamped_live() -> None:
    state, call = _record(default_research_ledger_state(), benchmark_price="99.99")
    assert call["benchmark_ref_source"] == BENCHMARK_SOURCE_LIVE

    state, report = backfill_benchmarks(state, TW_CLOSES)

    assert state["calls"][0]["benchmark_ref_price"] == "99.99"
    assert state["calls"][0]["benchmark_ref_source"] == BENCHMARK_SOURCE_LIVE
    assert report["skipped_already_stamped"] == 1
    assert report["filled_count"] == 0


def test_backfill_leaves_superseded_calls_alone() -> None:
    state, first = _record(default_research_ledger_state())
    _struck_on(first, "2026-07-24")
    state, _ = _record(state, symbol="2330.TW", supersedes=first["call_id"])

    state, report = backfill_benchmarks(state, TW_CLOSES)

    superseded = [c for c in state["calls"] if c["status"] == "superseded"]
    assert superseded and superseded[0]["benchmark_ref_price"] is None
    assert report["skipped_superseded"] == 1


def test_backfill_grades_an_already_scored_call_against_the_index() -> None:
    """The case the whole feature exists for.

    2330 was graded a pure loss at -6.58% over a window 0050 fell 7.87%. A hold
    that loses less than owning the index is not a failure, and the hit rate
    cannot say so.
    """
    state, call = _record(default_research_ledger_state(), ref_price="2355", invalidation="2200")
    _struck_on(call, "2026-07-24")
    state, scored = score_calls(
        state, {"2330.TW": Decimal("2200")}, now=datetime(2026, 7, 29, tzinfo=UTC)
    )
    assert scored and scored[0]["realized_pct"] == "-6.58"
    assert scored[0]["beat_benchmark"] is None  # nothing to measure against yet

    state, report = backfill_benchmarks(state, TW_CLOSES)

    graded = state["calls"][0]
    assert graded["benchmark_ref_price"] == "101.70"
    assert graded["benchmark_score_price"] == "93.70"
    assert graded["benchmark_pct"] == "-7.87"
    assert graded["excess_pct"] == "1.29"
    assert graded["beat_benchmark"] is True
    assert report["filled"][0]["score_session"] == "2026-07-29"


def test_a_call_on_its_own_benchmark_gets_no_verdict() -> None:
    state, call = _record(
        default_research_ledger_state(),
        symbol="0050.TW",
        stance="avoid",
        ref_price="97.15",
        # The real call: stay out at 97.15, wrong if it runs back above 100.
        invalidation="100",
    )
    _struck_on(call, "2026-07-28")
    state, _ = score_calls(
        state, {"0050.TW": Decimal("102.85")}, now=datetime(2026, 7, 31, tzinfo=UTC)
    )

    state, _ = backfill_benchmarks(state, TW_CLOSES)

    graded = state["calls"][0]
    # Both legs come off the call itself, not off a close on a different clock:
    # taking the daily close here would price 0050-the-call against
    # 0050-the-index at two different instants and invent an excess return for
    # an instrument against itself.
    assert graded["benchmark_ref_source"] == BENCHMARK_SOURCE_SELF
    assert graded["benchmark_ref_price"] == graded["ref_price"]
    assert graded["excess_pct"] == "0.00"  # zero by construction
    assert graded["beat_benchmark"] is None  # 0050 cannot outperform 0050


def test_a_call_on_its_own_benchmark_never_takes_a_close_off_another_clock() -> None:
    """The BTC case: struck intraday at 65,337.77, that session closed 64,098.50.

    Reconstructing the benchmark leg from the close would have scored the call
    as beating itself by 1.9%, and that number would have gone into
    avg_excess_pct as if it were signal.
    """
    state, call = _record(
        default_research_ledger_state(),
        symbol="BTC-USD",
        market="crypto",
        stance="hold",
        ref_price="65337.77",
    )
    _struck_on(call, "2026-07-24")

    state, _ = backfill_benchmarks(state, {"BTC-USD": {"2026-07-24": "64098.4961"}})

    filled = state["calls"][0]
    assert filled["benchmark_ref_price"] == "65337.77"
    assert filled["benchmark_ref_source"] == BENCHMARK_SOURCE_SELF


def test_scorecard_says_how_many_verdicts_rest_on_reconstruction() -> None:
    state, call = _record(default_research_ledger_state(), ref_price="2355", invalidation="2200")
    _struck_on(call, "2026-07-24")
    state, _ = score_calls(
        state, {"2330.TW": Decimal("2200")}, now=datetime(2026, 7, 29, tzinfo=UTC)
    )
    state, _ = backfill_benchmarks(state, TW_CLOSES)

    card = research_ledger_payload(state)["scorecard"]["vs_benchmark"]

    assert card["judged_count"] == 1
    assert card["backfilled_count"] == 1
    assert "provisional" in card["note"]


def test_backfill_reports_a_call_it_cannot_reach() -> None:
    state, call = _record(default_research_ledger_state())
    _struck_on(call, "2026-07-01")  # before any close we hold

    state, report = backfill_benchmarks(state, TW_CLOSES)

    assert report["filled_count"] == 0
    assert report["unfilled_count"] == 1
    assert report["unfilled"][0]["reason"] == "no close at or before as_of"
    assert state["calls"][0]["benchmark_ref_price"] is None


def test_daily_closes_drop_the_null_bar_of_a_session_in_progress(monkeypatch) -> None:
    """Yahoo emits a bar with a null close for the session still running.

    Reading it as a real level puts a hole where a price is expected — the same
    shape as every stale-quote defect this terminal has shipped.
    """
    body = json.dumps(
        {
            "chart": {
                "result": [
                    {
                        "timestamp": [1785196800, 1785283200, 1785369600],
                        # 101.70 as float64 round-trips through JSON like this.
                        "indicators": {
                            "quote": [{"close": [101.69999694824219, None, 97.1500015258789]}]
                        },
                    }
                ],
                "error": None,
            }
        }
    ).encode()

    class _Response:
        def read(self) -> bytes:
            return body

        def __enter__(self):
            return self

        def __exit__(self, *_args) -> bool:
            return False

    monkeypatch.setattr(yahoo_data, "urlopen", lambda *a, **k: _Response())

    closes = yahoo_data.fetch_yahoo_daily_closes(
        symbol="0050.TW", start="2026-07-24", end="2026-07-28"
    )

    # Two sessions, and the float64 artefact rounded off rather than journaled
    # as eleven digits the exchange never printed.
    assert list(closes.values()) == ["101.7", "97.15"]
    assert len(closes) == 2
