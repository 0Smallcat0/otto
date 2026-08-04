"""A dividend must not read as a loss.

台企銀 (2834) closed 2026-08-04 at 16.90 against a previous close of 18.20 and
every surface called it −7.14%, the worst move in the universe, on a day the
index fell 1.32%. It had gone ex-rights-and-dividend that morning for 1.471029
per share; against TWSE's own 16.72 reference price it rose 1.08% and beat the
index by 2.4 points. Taiwan listings do this once a year, so the misread is
annual on every TW holding rather than rare.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from otto.local_terminal import twse_corporate_actions as ca
from otto.local_terminal.research_ledger import (
    default_research_ledger_state,
    record_call,
    research_ledger_payload,
    research_scan_payload,
    scan_candidates,
    score_calls,
)

FIELDS = [
    "資料日期",
    "股票代號",
    "股票名稱",
    "除權息前收盤價",
    "除權息參考價",
    "權值+息值",
    "權/息",
]

# The real row TWSE served for 2026-08-04.
ROW_2834 = ["115年08月04日", "2834", "臺企銀", "18.20", "16.72", "1.471029", "權息"]
ROW_2211 = ["115年07月20日", "2211", "長榮鋼", "94.20", "87.70", "6.500000", "息"]


def _payload(rows, fields=None):
    return {"stat": "OK", "fields": fields or FIELDS, "data": rows}


def test_reads_the_real_2834_row() -> None:
    events = ca.normalize_twse_ex_rights(_payload([ROW_2834]))

    assert events == [
        {
            "ex_date": "2026-08-04",
            "code": "2834",
            "symbol": "2834.TW",
            "name": "臺企銀",
            "prev_close": "18.20",
            "reference_price": "16.72",
            "value_per_share": "1.471029",
            "kind": "權息",
            "source": "twse_twt49u_ex_right",
        }
    ]


def test_roc_year_becomes_gregorian() -> None:
    assert ca.roc_to_iso("115年08月04日") == "2026-08-04"
    assert ca.roc_to_iso("") is None
    assert ca.roc_to_iso("garbage") is None


def test_columns_are_resolved_by_name_not_position() -> None:
    """A reordered column must not be applied as if it were a price.

    Read by index, this row hands 1.471029 to reference_price and 16.72 to the
    distributed value — an adjustment that is silently wrong rather than absent.
    """
    swapped_fields = [
        "資料日期",
        "股票代號",
        "股票名稱",
        "除權息前收盤價",
        "權值+息值",
        "除權息參考價",
        "權/息",
    ]
    row = ["115年08月04日", "2834", "臺企銀", "18.20", "1.471029", "16.72", "權息"]

    events = ca.normalize_twse_ex_rights(_payload([row], fields=swapped_fields))

    assert events[0]["reference_price"] == "16.72"
    assert events[0]["value_per_share"] == "1.471029"


def test_a_missing_column_raises_rather_than_guessing() -> None:
    short_fields = ["資料日期", "股票代號", "股票名稱"]
    with pytest.raises(ca.TwseExRightError, match="missing columns"):
        ca.normalize_twse_ex_rights(_payload([["115年08月04日", "2834", "臺企銀"]], short_fields))


def test_a_non_ok_response_raises() -> None:
    with pytest.raises(ca.TwseExRightError, match="not OK"):
        ca.normalize_twse_ex_rights({"stat": "查無資料", "fields": FIELDS, "data": []})


def test_the_event_on_the_strike_day_itself_is_not_added_back() -> None:
    """It was already inside the price the call was struck at.

    Adding it would credit the holder with a dividend their entry price had
    already discounted — an invented gain, which is worse than the loss it
    replaces.
    """
    events = ca.normalize_twse_ex_rights(_payload([ROW_2834]))

    same_day = ca.distributed_between(
        events, symbol="2834.TW", after="2026-08-04", upto="2026-08-05"
    )
    spanning = ca.distributed_between(
        events, symbol="2834.TW", after="2026-07-25", upto="2026-08-05"
    )

    assert same_day == Decimal("0")
    assert spanning == Decimal("1.471029")


def test_an_event_after_the_window_is_not_counted() -> None:
    events = ca.normalize_twse_ex_rights(_payload([ROW_2834]))

    assert ca.distributed_between(
        events, symbol="2834.TW", after="2026-07-25", upto="2026-08-03"
    ) == Decimal("0")


def test_the_real_2834_call_made_money_and_was_scored_as_losing() -> None:
    """The whole point, in the numbers that provoked it.

    The open hold call was struck at 18.00 on 2026-07-25. Priced naively at
    16.90 it reads −6.11% and sits 5.6% above a 16.00 invalidation it was never
    measured against. Counting the 1.471029 the holder actually received, the
    position is up 2.06% — and 0050 fell 1.03% over the same window, so the
    call the ledger was about to grade a failure beat the index by three
    points. The gap between the two readings is 8.17 percentage points.
    """
    events = ca.normalize_twse_ex_rights(_payload([ROW_2834]))
    distributed = ca.distributed_between(
        events, symbol="2834.TW", after="2026-07-25", upto="2026-08-05"
    )

    naive = (Decimal("16.90") / Decimal("18.00") - 1) * 100
    adjusted = ca.adjusted_return_pct(
        ref_price=Decimal("18.00"), price=Decimal("16.90"), distributed=distributed
    )

    assert f"{naive:.2f}" == "-6.11"
    assert f"{adjusted:.2f}" == "2.06"
    assert f"{adjusted - naive:.2f}" == "8.17"


def test_grouping_sorts_oldest_first() -> None:
    events = ca.normalize_twse_ex_rights(_payload([ROW_2834, ROW_2211]))

    grouped = ca.events_by_symbol(events)

    assert set(grouped) == {"2834.TW", "2211.TW"}
    assert grouped["2834.TW"][0]["ex_date"] == "2026-08-04"


def test_fetch_surfaces_a_transport_failure_rather_than_an_empty_list(monkeypatch) -> None:
    """An unreachable TWSE must not look like "no company paid a dividend".

    Silently returning [] would leave every adjustment off and every dividend
    reading as a loss again, with nothing saying so.
    """

    def _boom(*_args, **_kwargs):
        raise TimeoutError("connection timed out")

    monkeypatch.setattr(ca, "urlopen", _boom)

    with pytest.raises(ca.TwseExRightError, match="fetch failed"):
        ca.fetch_twse_ex_rights(start="2026-07-01", end="2026-08-05")


def test_scan_reports_the_real_move_not_the_payout() -> None:
    """The number that nearly bought a panic.

    2834 printed 16.90 against an 18.20 close: −7.14%, the largest fall in the
    universe, sorted straight to the top of the research queue on a day the
    index fell 1.32%. Measured against the 16.72 reference price TWSE opened it
    at, it rose 1.08% and beat the index by two and a half points.
    """
    events = ca.normalize_twse_ex_rights(_payload([ROW_2834]))
    quotes = {
        "2834.TW": {"price": "16.90", "change_pct": "-7.14", "currency": "TWD"},
        "2330.TW": {"price": "2320.0", "change_pct": "-2.11", "currency": "TWD"},
    }

    rows = scan_candidates(quotes, owned={"2834.TW": ("tw_equity", "臺企銀")}, ex_events=events)
    by_symbol = {row["symbol"]: row for row in rows}

    assert by_symbol["2834.TW"]["change_pct"] == "1.08"
    assert "16.72 reference price" in by_symbol["2834.TW"]["ex_dividend_today"]
    # An untouched name keeps its raw quote and gains no note.
    assert by_symbol["2330.TW"]["change_pct"] == "-2.11"
    assert by_symbol["2330.TW"]["ex_dividend_today"] is None


def test_a_quote_that_has_moved_past_the_ex_date_is_left_alone() -> None:
    """The match is made by the quote, not by the calendar.

    The day after, the change is measured from 16.90 — a close that never held
    the payout. Adjusting again would subtract a dividend twice. Matching on
    "is the ex-date recent" cannot tell these two apart; reversing the quote's
    own change can.
    """
    events = ca.normalize_twse_ex_rights(_payload([ROW_2834]))
    quotes = {"2834.TW": {"price": "17.15", "change_pct": "1.48", "currency": "TWD"}}

    rows = scan_candidates(quotes, owned={"2834.TW": ("tw_equity", "臺企銀")}, ex_events=events)

    assert rows[0]["change_pct"] == "1.48"
    assert rows[0]["ex_dividend_today"] is None


def test_scan_payload_names_the_symbols_that_paid_out() -> None:
    events = ca.normalize_twse_ex_rights(_payload([ROW_2834]))
    quotes = {"2834.TW": {"price": "16.90", "change_pct": "-7.14", "currency": "TWD"}}

    payload = research_scan_payload(
        quotes, owned={"2834.TW": ("tw_equity", "臺企銀")}, ex_events=events
    )

    assert payload["ex_dividend_today"] == ["2834.TW"]
    assert "nobody suffered" in payload["note"]


def test_scoring_adds_back_what_the_holder_was_paid() -> None:
    """End of the same story, in the ledger rather than the scan.

    A hold struck at 18.00 with a 17.00 invalidation: the raw 16.90 print
    breaches it and closes the thesis as invalidated. The holder is not below
    17.00 — they hold 16.90 of share and 1.47 of payout.
    """
    events = ca.normalize_twse_ex_rights(_payload([ROW_2834]))
    state, call = record_call(
        default_research_ledger_state(),
        {
            "symbol": "2834.TW",
            "market": "tw_equity",
            "stance": "hold",
            "thesis": "reasoning goes here",
            "ref_price": "18.00",
            "invalidation": "17.00",
            "horizon_days": 45,
        },
    )
    call["as_of"] = "2026-07-25T05:00:00+00:00"
    call["matures_at"] = "2026-09-08T05:00:00+00:00"
    now = datetime(2026, 8, 5, tzinfo=UTC)
    marks = {"2834.TW": Decimal("16.90")}

    _, without = score_calls(json.loads(json.dumps(state)), marks, now=now)
    kept, with_events = score_calls(state, marks, now=now, ex_events=events)

    assert without[0]["outcome"] == "invalidated"
    assert without[0]["realized_pct"] == "-6.11"
    assert with_events == []  # thesis intact, still running
    assert kept["calls"][0]["status"] == "open"


def test_the_board_stops_flagging_a_payout_as_drift() -> None:
    """The surface the owner actually reads, and the last one to be fixed.

    Scoring and the scan were corrected first and this was not, so the board
    still showed the 2834 hold at −6.11% with "price moved 6.1% from the 18.0 it
    was struck at — rethink this". The holder was up 2.06% and there was nothing
    to rethink. The raw print stays on the row as quote_price so it still ties
    back to the tape.
    """
    events = ca.normalize_twse_ex_rights(_payload([ROW_2834]))
    state, call = record_call(
        default_research_ledger_state(),
        {
            "symbol": "2834.TW",
            "market": "tw_equity",
            "stance": "hold",
            "thesis": "reasoning goes here",
            "ref_price": "18.00",
            "invalidation": "16.00",
            "horizon_days": 45,
        },
    )
    call["as_of"] = "2026-07-25T05:00:00+00:00"
    call["matures_at"] = "2026-09-08T05:00:00+00:00"
    marks = {"2834.TW": Decimal("16.90")}

    naive = research_ledger_payload(json.loads(json.dumps(state)), marks)["open_calls"][0]
    fixed = research_ledger_payload(state, marks, ex_events=events)["open_calls"][0]

    assert naive["unrealized_pct"] == "-6.11"
    assert naive["needs_review"] is True

    assert fixed["unrealized_pct"] == "2.06"
    assert fixed["needs_review"] is False
    assert fixed["quote_price"] == "16.90"
    assert fixed["distributed_per_share"] == "1.471029"


def test_live_twse_still_serves_the_columns_this_reads() -> None:
    """Contract check against the real endpoint, skipped when offline.

    Pinned to a window whose content cannot change: 2026-08-04 is in the past.
    """
    try:
        events = ca.fetch_twse_ex_rights(start="2026-08-04", end="2026-08-04")
    except ca.TwseExRightError as exc:  # pragma: no cover - network dependent
        pytest.skip(f"TWSE unreachable: {exc}")
    hit = [e for e in events if e["symbol"] == "2834.TW"]
    assert hit, "2834 went ex-rights on 2026-08-04; TWSE no longer reports it"
    assert hit[0]["value_per_share"] == "1.471029"
    assert json.dumps(hit[0])  # serialisable as-is
