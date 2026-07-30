"""Research ledger: reasoned calls recorded, then scored on real subsequent price."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from otto.local_terminal.research_ledger import (
    DEFAULT_UNIVERSE,
    ResearchLedgerError,
    default_research_ledger_state,
    normalize_research_ledger_state,
    record_call,
    research_ledger_payload,
    research_scan_payload,
    scan_candidates,
    score_calls,
)


def _record(state, **kw):
    payload = {
        "symbol": "2330.TW",
        "stance": "accumulate",
        "thesis": "reasoning goes here",
        "ref_price": "100",
        "horizon_days": 30,
    }
    payload.update(kw)
    return record_call(state, payload)


def test_record_infers_market_and_name_from_universe() -> None:
    state, call = _record(default_research_ledger_state(), symbol="2330.tw")
    assert call["symbol"] == "2330.TW"
    assert call["market"] == "tw_equity"
    assert call["name"] == DEFAULT_UNIVERSE["2330.TW"][1]
    assert call["status"] == "open"
    assert call["ref_price"] == "100"
    assert state["calls"][-1]["call_id"] == call["call_id"]


def test_record_requires_thesis_stance_and_price() -> None:
    base = default_research_ledger_state()
    with pytest.raises(ResearchLedgerError, match="thesis"):
        _record(base, thesis="   ")
    with pytest.raises(ResearchLedgerError, match="stance"):
        _record(base, stance="moon")
    with pytest.raises(ResearchLedgerError, match="ref_price"):
        _record(base, ref_price=None)
    with pytest.raises(ResearchLedgerError, match="market"):
        # unknown symbol, no explicit market → cannot classify
        _record(base, symbol="ZZZZ", market=None)


def _mature(call_state):
    """Push every call's maturity into the past so scoring engages."""
    for c in call_state["calls"]:
        c["matures_at"] = (datetime.now(tz=UTC) - timedelta(days=1)).isoformat()
    return call_state


def test_accumulate_scores_worked_failed_and_flat() -> None:
    # up 10% → worked
    st, _ = _record(default_research_ledger_state(), ref_price="100")
    st, scored = score_calls(_mature(st), {"2330.TW": Decimal("110")})
    assert scored[0]["outcome"] == "worked"
    assert scored[0]["favor_pct"] == "10.00"
    assert scored[0]["status"] == "scored"

    # down 10% → failed
    st, _ = _record(default_research_ledger_state(), ref_price="100")
    st, scored = score_calls(_mature(st), {"2330.TW": Decimal("90")})
    assert scored[0]["outcome"] == "failed"

    # +0.5% inside the flat band → flat, not a win
    st, _ = _record(default_research_ledger_state(), ref_price="100")
    st, scored = score_calls(_mature(st), {"2330.TW": Decimal("100.5")})
    assert scored[0]["outcome"] == "flat"


def test_reduce_and_avoid_are_right_when_price_falls() -> None:
    st, _ = _record(default_research_ledger_state(), stance="reduce", ref_price="100")
    st, scored = score_calls(_mature(st), {"2330.TW": Decimal("90")})
    assert scored[0]["outcome"] == "worked"
    assert scored[0]["favor_pct"] == "10.00"  # fell 10% = 10% in favor of reduce

    st, _ = _record(default_research_ledger_state(), stance="avoid", ref_price="100")
    st, scored = score_calls(_mature(st), {"2330.TW": Decimal("120")})
    assert scored[0]["outcome"] == "failed"  # rose = avoid was wrong


def test_hold_worked_when_range_bound_else_moved() -> None:
    st, _ = _record(default_research_ledger_state(), stance="hold", ref_price="100")
    st, scored = score_calls(_mature(st), {"2330.TW": Decimal("100.8")})
    assert scored[0]["outcome"] == "worked"  # stayed within band

    st, _ = _record(default_research_ledger_state(), stance="hold", ref_price="100")
    st, scored = score_calls(_mature(st), {"2330.TW": Decimal("108")})
    assert scored[0]["outcome"] == "moved"


def test_invalidation_breach_closes_early_even_before_horizon() -> None:
    # accumulate with a stop at 95; price 94 breaches it though horizon is future
    st, call = _record(
        default_research_ledger_state(), ref_price="100", invalidation="95"
    )
    assert call["matures_at"] > datetime.now(tz=UTC).isoformat()  # not matured
    st, scored = score_calls(st, {"2330.TW": Decimal("94")})
    assert len(scored) == 1
    assert scored[0]["outcome"] == "invalidated"


def test_a_hold_settles_when_it_breaks_the_level_it_named() -> None:
    """The real 00982A case: struck 20.09, named 19.5, traded 19.45, settled nothing.

    Holds were exempt from the breach check on the reasoning that holding has
    no single side. Every hold written here named a one-sided level and the
    wall renders them as 跌破 X, inferring the side from where the level sits
    against the struck price. Only the scorer disagreed, so the call would
    have drifted to its 08-27 horizon and scored on whatever price happened to
    be there (2026-07-29).
    """
    st, call = _record(
        default_research_ledger_state(), stance="hold", ref_price="20.09", invalidation="19.5"
    )
    assert call["matures_at"] > datetime.now(tz=UTC).isoformat()  # not matured

    st, scored = score_calls(st, {"2330.TW": Decimal("19.45")})

    assert len(scored) == 1
    assert scored[0]["outcome"] == "invalidated"


def test_a_hold_whose_level_sits_above_it_breaks_upward() -> None:
    """The side is read from the data, not assumed to be downward."""
    st, _ = _record(
        default_research_ledger_state(), stance="hold", ref_price="100", invalidation="110"
    )

    intact = score_calls(st, {"2330.TW": Decimal("109")})[1]
    breached = score_calls(st, {"2330.TW": Decimal("111")})[1]

    assert intact == []
    assert breached[0]["outcome"] == "invalidated"


def test_a_hold_above_its_floor_keeps_running() -> None:
    st, _ = _record(
        default_research_ledger_state(), stance="hold", ref_price="20.09", invalidation="19.5"
    )

    st, scored = score_calls(st, {"2330.TW": Decimal("19.55")})

    assert scored == []
    assert st["calls"][0]["status"] == "open"


def test_a_sizing_call_is_never_settled_by_a_level() -> None:
    """size_down makes no directional claim, so no price can prove it wrong."""
    st, _ = _record(
        default_research_ledger_state(),
        stance="size_down",
        ref_price="18",
        invalidation="16",
        weight_pct="63.5",
    )

    st, scored = score_calls(st, {"2330.TW": Decimal("15")})

    assert scored == []
    assert st["calls"][0]["status"] == "open"


def test_unmatured_intact_call_stays_open_and_no_mark_never_graded() -> None:
    st, _ = _record(default_research_ledger_state(), ref_price="100", invalidation="80")
    # not matured, invalidation not breached → stays open
    st, scored = score_calls(st, {"2330.TW": Decimal("101")})
    assert scored == []
    assert st["calls"][0]["status"] == "open"

    # matured but no usable mark → still not graded
    st, scored = score_calls(_mature(st), {"2330.TW": None})
    assert scored == []
    assert st["calls"][0]["status"] == "open"


def test_scorecard_excludes_flat_from_hit_rate() -> None:
    st = default_research_ledger_state()
    st, _ = _record(st, ref_price="100")  # will be worked
    st, _ = _record(st, ref_price="100")  # will be failed
    st, _ = _record(st, ref_price="100")  # will be flat
    marks_seq = [Decimal("110"), Decimal("90"), Decimal("100.2")]
    # score each individually so they get distinct marks
    st = _mature(st)
    for call, mark in zip(st["calls"], marks_seq, strict=True):
        call_state = {"calls": [call]}
        _, _ = score_calls(call_state, {"2330.TW": mark})
    payload = research_ledger_payload(st)
    card = payload["scorecard"]
    assert card["scored_count"] == 3
    # worked=1, failed=1 decided; flat excluded → hit rate 50%
    assert card["hit_rate_pct"] == "50.0"


def test_payload_shows_unrealized_favor_for_open_calls() -> None:
    st, _ = _record(default_research_ledger_state(), stance="accumulate", ref_price="100")
    payload = research_ledger_payload(st, {"2330.TW": Decimal("105")})
    row = payload["open_calls"][0]
    assert row["unrealized_pct"] == "5.00"
    assert row["unrealized_favor_pct"] == "5.00"
    assert payload["open_count"] == 1
    assert payload["scored_count"] == 0


def test_scan_ranks_by_absolute_move_and_flags_open_calls() -> None:
    quotes = {
        "2330.TW": {"price": "2355", "change_pct": "-2.08", "currency": "TWD"},
        "GOOGL": {"price": "318", "change_pct": "-7.13", "currency": "USD"},
        "BTC-USD": {"price": "65300", "change_pct": "0.37", "currency": "USD"},
        # NVDA left unpriced → must sink below priced rows
    }
    rows = scan_candidates(quotes, open_symbols=["2330.TW"])
    by_symbol = {r["symbol"]: r for r in rows}
    # biggest absolute mover first among priced names
    priced = [r for r in rows if r["change_pct"] is not None]
    assert priced[0]["symbol"] == "GOOGL"  # |-7.13| tops |-2.08| and |0.37|
    assert by_symbol["2330.TW"]["has_open_call"] is True
    assert by_symbol["GOOGL"]["has_open_call"] is False
    # unpriced names present but ranked after every priced one
    assert by_symbol["NVDA"]["change_pct"] is None
    assert rows.index(by_symbol["NVDA"]) > rows.index(by_symbol["BTC-USD"])
    assert len(rows) == len(DEFAULT_UNIVERSE)


def test_owned_holdings_join_the_universe_and_sort_first() -> None:
    # The owner really holds 00982A/2834; they are NOT in DEFAULT_UNIVERSE, and
    # a research loop that ignores his real money is researching the wrong list.
    owned = {"00982A.TW": ("tw_equity", "主動群益台灣強棒"), "2834.TW": ("tw_equity", "臺企銀")}
    quotes = {
        "00982A.TW": {"price": "21.98", "change_pct": "-2.22"},
        "2834.TW": {"price": "18.0", "change_pct": "1.12"},
        "GOOGL": {"price": "318", "change_pct": "-7.13"},  # much bigger mover
    }
    rows = scan_candidates(quotes, open_symbols=["2834.TW"], owned=owned)
    # owner's positions rank above the -7% mover: real money outranks size
    assert [r["symbol"] for r in rows[:2]] == ["00982A.TW", "2834.TW"]
    assert rows[0]["owned"] is True and rows[0]["name"] == "主動群益台灣強棒"
    assert rows[2]["symbol"] == "GOOGL" and rows[2]["owned"] is False
    assert len(rows) == len(DEFAULT_UNIVERSE) + 2

    payload = research_scan_payload(quotes, ["2834.TW"], owned)
    assert payload["owned_count"] == 2
    # 2834 already journaled; 00982A is a real holding with NO view — the gap
    assert payload["owned_without_call"] == ["00982A.TW"]
    assert payload["universe_size"] == len(DEFAULT_UNIVERSE) + 2


def test_scan_without_owned_holdings_is_unchanged() -> None:
    rows = scan_candidates({"AAPL": {"price": "331", "change_pct": "3.0"}})
    assert len(rows) == len(DEFAULT_UNIVERSE)
    assert all(r["owned"] is False for r in rows)
    assert research_scan_payload(None)["owned_without_call"] == []


def test_scan_payload_counts_priced_and_notes_signal() -> None:
    payload = research_scan_payload({"AAPL": {"price": "321", "change_pct": "-1.3"}}, [])
    assert payload["universe_size"] == len(DEFAULT_UNIVERSE)
    assert payload["priced_count"] == 1
    assert "not a call" in payload["note"].lower()
    assert payload["safety"]["paper_only"] is True


def test_normalize_drops_junk_and_caps() -> None:
    assert normalize_research_ledger_state(None) == {"calls": []}
    assert normalize_research_ledger_state({"calls": "nope"}) == {"calls": []}
    mixed = {"calls": [{"call_id": "a"}, "junk", 5, {"call_id": "b"}]}
    out = normalize_research_ledger_state(mixed)
    assert [c["call_id"] for c in out["calls"]] == ["a", "b"]


def test_size_down_requires_a_weight_number() -> None:
    with pytest.raises(ResearchLedgerError, match="weight_pct"):
        _record(default_research_ledger_state(), stance="size_down")


def test_size_down_is_scored_on_risk_not_direction() -> None:
    # The owner's real book held one name at 63.5%. A concentration warning
    # makes no directional claim, so it must never be graded as a price call.
    st, call = _record(
        default_research_ledger_state(), stance="size_down", ref_price="100", weight_pct="63.5", cap_pct="40"
    )
    assert call["weight_pct"] == "63.50" and call["cap_pct"] == "40.00"

    # rose 20%: the warning simply did not bite — NOT a "failed" call
    up, scored = score_calls(_mature({"calls": [dict(call)]}), {"2330.TW": Decimal("120")})
    assert scored[0]["outcome"] == "risk_not_realized"
    assert scored[0]["favor_pct"] is None  # no directional favor is invented
    assert scored[0]["realized_pct"] == "20.00"

    # dropped 15%: the oversized position did inflict real damage
    down, scored = score_calls(_mature({"calls": [dict(call)]}), {"2330.TW": Decimal("85")})
    assert scored[0]["outcome"] == "risk_realized"

    # a 5% dip is not material for a sizing warning
    _, scored = score_calls(_mature({"calls": [dict(call)]}), {"2330.TW": Decimal("95")})
    assert scored[0]["outcome"] == "risk_not_realized"


def test_an_open_call_carries_the_live_book_weight_beside_the_struck_one() -> None:
    """The board printed a 07-25 weight in the present tense.

    2834 was 63.5% of the book when the warning was written and 66.85% four days
    later — the concentration had grown, which is exactly the case the warning
    exists for, and the wall said 63.5% as if nothing had moved. Same shape as
    ref_price vs mark_price (2026-07-29 dogfood).
    """
    st, _ = _record(
        default_research_ledger_state(),
        stance="size_down",
        ref_price="18.0",
        weight_pct="63.5",
        cap_pct="40",
    )
    payload = research_ledger_payload(st, weights={"2330.TW": Decimal("66.85")})
    row = payload["open_calls"][0]
    assert row["weight_pct"] == "63.50"  # what it weighed when struck, untouched
    assert row["mark_weight_pct"] == "66.85"  # what it weighs now

    # no live weight (symbol not in the book, or the book cannot be priced):
    # the field is absent, so the wall can say "at entry" instead of guessing
    assert research_ledger_payload(st)["open_calls"][0]["mark_weight_pct"] is None


def test_a_concentration_that_grew_is_flagged_for_review() -> None:
    """A sizing call had no review path at all until its horizon ran out.

    It has no invalidation and no entry band, so every price-based rule skips
    it — 2834 drifted from 63.5% to 67.2% of the book with nothing flagged. A
    warning whose risk got worse is the case most worth re-reading; a position
    shrinking back toward the cap is the warning working, so only growth flags
    (2026-07-29, owner asked for the rule).
    """
    st, _ = _record(
        default_research_ledger_state(),
        stance="size_down",
        ref_price="18.0",
        weight_pct="63.5",
        cap_pct="40",
    )

    def reasons(weight: str | None) -> list[str]:
        weights = {"2330.TW": Decimal(weight)} if weight else None
        return research_ledger_payload(st, weights=weights)["open_calls"][0]["review_reasons"]

    grew = reasons("67.24")  # +5.9% — past REVIEW_DRIFT_PCT
    assert any("grew to 67.24%" in r for r in grew)
    assert not reasons("65.0")  # +2.4% — the book breathing, not a worse risk
    assert not reasons("40.0")  # shrank back to the cap: the warning worked
    assert not reasons(None)  # no live weight: nothing to compare, no flag


def test_sizing_calls_are_excluded_from_the_directional_hit_rate() -> None:
    st = default_research_ledger_state()
    st, directional = _record(st, ref_price="100")  # accumulate
    st, sizing = _record(st, stance="size_down", ref_price="100", weight_pct="63.5")
    st = _mature(st)
    # accumulate wins (+10%), sizing call's own drop would look like a "loss"
    scored_state, _ = score_calls(st, {"2330.TW": Decimal("110")})
    card = research_ledger_payload(scored_state)["scorecard"]
    assert card["scored_count"] == 2
    assert card["decided_count"] == 1  # only the directional call counts
    assert card["hit_rate_pct"] == "100.0"  # sizing cannot dilute or inflate it
    assert card["sizing"]["scored_count"] == 1
    assert "not a directional prediction" in card["sizing"]["note"]


def test_open_call_flags_price_drift_for_review() -> None:
    st, _ = _record(default_research_ledger_state(), ref_price="100")
    quiet = research_ledger_payload(st, {"2330.TW": Decimal("102")})
    assert quiet["needs_review_count"] == 0  # 2% drift is not worth a rethink
    assert quiet["open_calls"][0]["needs_review"] is False

    drifted = research_ledger_payload(st, {"2330.TW": Decimal("108")})
    assert drifted["needs_review"] == ["2330.TW"]
    assert "moved 8.0%" in drifted["open_calls"][0]["review_reasons"][0]


def test_open_call_flags_approaching_invalidation() -> None:
    # struck at 100 with a stop at 90; 92 is 20% of the way left → review
    st, _ = _record(default_research_ledger_state(), ref_price="100", invalidation="90")
    payload = research_ledger_payload(st, {"2330.TW": Decimal("92")})
    reasons = " ".join(payload["open_calls"][0]["review_reasons"])
    assert "invalidation" in reasons
    assert payload["needs_review_count"] == 1


def test_open_call_flags_an_entry_band_the_market_has_left() -> None:
    """The real 0050 case: 97.15 against a 98-101 band, flagged by nothing.

    Drift was 4.3% and the price still sat 33% of the way from its
    invalidation — under both thresholds — so a call whose only actionable
    instruction had been void for days would have scored untouched
    (2026-07-28).
    """
    st, _ = _record(
        default_research_ledger_state(),
        stance="accumulate",
        ref_price="101.5",
        invalidation="95",
        entry_low="98",
        entry_high="101",
    )

    inside = research_ledger_payload(st, {"2330.TW": Decimal("99")})
    assert inside["needs_review_count"] == 0

    below = research_ledger_payload(st, {"2330.TW": Decimal("97.15")})
    assert "below its 98 entry" in " ".join(below["open_calls"][0]["review_reasons"])

    # Running away above the ceiling voids the staged entry just as surely.
    above = research_ledger_payload(st, {"2330.TW": Decimal("104")})
    assert "ran past its 101 entry" in " ".join(above["open_calls"][0]["review_reasons"])


def test_a_hold_is_not_flagged_forever_for_a_pullback_that_never_came() -> None:
    """AAPL: hold, do not chase, look for a pullback to 320-328. It went to 337.

    The view did not go stale — the conditional entry simply never triggered.
    And unlike drift, invalidation proximity and elapsed horizon, a passed band
    never un-passes, so the flag would have sat amber for the twenty-six days
    to maturity. A warning that can never be resolved stops being read
    (2026-07-28).
    """
    st, _ = _record(
        default_research_ledger_state(),
        stance="hold",
        ref_price="331.67",
        invalidation="315",
        entry_low="320",
        entry_high="328",
    )

    payload = research_ledger_payload(st, {"2330.TW": Decimal("336.91")})

    assert payload["needs_review_count"] == 0


def test_a_call_with_no_entry_band_is_not_flagged_for_one() -> None:
    """Most calls name no band; inventing a breach for them would be noise."""
    st, _ = _record(default_research_ledger_state(), ref_price="100")

    payload = research_ledger_payload(st, {"2330.TW": Decimal("100.5")})

    assert payload["needs_review_count"] == 0


def test_open_call_flags_nearly_elapsed_horizon() -> None:
    st, call = _record(default_research_ledger_state(), ref_price="100", horizon_days=10)
    # rewind the call's start so 90% of its horizon has passed
    call["as_of"] = (datetime.now(tz=UTC) - timedelta(days=9)).isoformat()
    call["matures_at"] = (datetime.now(tz=UTC) + timedelta(days=1)).isoformat()
    payload = research_ledger_payload({"calls": [call]}, {"2330.TW": Decimal("100")})
    assert payload["needs_review_count"] == 1
    assert "horizon" in payload["open_calls"][0]["review_reasons"][0]


def test_breached_call_is_not_double_flagged_as_approaching() -> None:
    # already through the stop: scoring closes it, review must not also nag
    st, _ = _record(default_research_ledger_state(), ref_price="100", invalidation="90")
    payload = research_ledger_payload(st, {"2330.TW": Decimal("88")})
    reasons = " ".join(payload["open_calls"][0]["review_reasons"])
    assert "invalidation" not in reasons  # breach is scoring's job, not review's


def _age_call(state, matured_days_ago, horizon_days=30):
    """Make a call that matured N days ago with the given horizon."""
    call = state["calls"][0]
    call["horizon_days"] = horizon_days
    call["as_of"] = (
        datetime.now(tz=UTC) - timedelta(days=horizon_days + matured_days_ago)
    ).isoformat()
    call["matures_at"] = (datetime.now(tz=UTC) - timedelta(days=matured_days_ago)).isoformat()
    return state


def test_score_run_on_time_honors_the_window() -> None:
    st, _ = _record(default_research_ledger_state(), ref_price="100", horizon_days=30)
    st, scored = score_calls(_age_call(st, matured_days_ago=1), {"2330.TW": Decimal("110")})
    assert scored[0]["scored_late_days"] == 1
    assert scored[0]["window_honored"] is True  # 1 day late on a 30-day call


def test_badly_late_score_is_marked_and_kept_out_of_the_hit_rate() -> None:
    # nothing ran for 20 days after a 30-day call matured: the measured window
    # is 50 days, not the 30 the thesis claimed
    st, _ = _record(default_research_ledger_state(), ref_price="100", horizon_days=30)
    st, scored = score_calls(_age_call(st, matured_days_ago=20), {"2330.TW": Decimal("110")})
    assert scored[0]["scored_late_days"] == 20
    assert scored[0]["window_honored"] is False
    assert scored[0]["outcome"] == "worked"  # the raw outcome is still visible

    card = research_ledger_payload(st)["scorecard"]
    assert card["stale_scored_count"] == 1
    assert card["decided_count"] == 0  # excluded — cannot claim this as a hit
    assert card["hit_rate_pct"] is None
    assert "rounds were missed" in card["stale_note"]


def test_invalidation_breach_is_never_late() -> None:
    # a breach is an event, scored whenever price crosses — not a deadline
    st, _ = _record(
        default_research_ledger_state(), ref_price="100", invalidation="95", horizon_days=30
    )
    st, scored = score_calls(_age_call(st, matured_days_ago=90), {"2330.TW": Decimal("90")})
    assert scored[0]["outcome"] == "invalidated"
    assert scored[0]["window_honored"] is True
    assert scored[0]["scored_late_days"] == 0


def test_superseding_a_call_withdraws_it_instead_of_stacking() -> None:
    # The owner's largest holding once appeared three times with three
    # different invalidation levels because "supersede" was only a convention.
    st, first = _record(default_research_ledger_state(), ref_price="100", invalidation="90")
    st, second = _record(st, ref_price="100", invalidation="95", supersedes=first["call_id"])

    old = st["calls"][0]
    assert old["status"] == "superseded"
    assert old["superseded_by"] == second["call_id"]
    assert old["superseded_at"] == second["as_of"]
    assert second["supersedes"] == first["call_id"]

    payload = research_ledger_payload(st)
    assert payload["open_count"] == 1  # only the replacement is live
    assert payload["superseded_count"] == 1
    assert [c["call_id"] for c in payload["open_calls"]] == [second["call_id"]]


def test_a_withdrawn_view_is_never_scored() -> None:
    st, first = _record(default_research_ledger_state(), ref_price="100")
    st, _ = _record(st, ref_price="100", supersedes=first["call_id"])
    st, scored = score_calls(_mature(st), {"2330.TW": Decimal("120")})
    # the replacement scores; the withdrawn thesis is not graded
    assert len(scored) == 1
    assert scored[0]["supersedes"] == first["call_id"]
    assert st["calls"][0]["status"] == "superseded"
    card = research_ledger_payload(st)["scorecard"]
    assert card["scored_count"] == 1


def test_supersede_refuses_unknown_or_closed_targets() -> None:
    st, first = _record(default_research_ledger_state(), ref_price="100")
    with pytest.raises(ResearchLedgerError, match="no call"):
        _record(st, ref_price="100", supersedes="call-nope")
    st, _ = _record(st, ref_price="100", supersedes=first["call_id"])
    with pytest.raises(ResearchLedgerError, match="superseded, not open"):
        _record(st, ref_price="100", supersedes=first["call_id"])


def test_a_hold_that_lost_less_than_the_index_is_not_the_same_as_losing() -> None:
    """The scorecard said 0.0% hit rate and could not say whether that beat owning the index.

    2330 was graded a pure loss at -6.58% over a window the TW market fell
    further; a hold that loses less than the alternative is not a failure, and
    the owner's question is "did you beat the market", which a hit rate cannot
    answer (2026-07-30).
    """
    st, call = _record(
        default_research_ledger_state(),
        stance="hold",
        ref_price="2355",
        benchmark_price="100",  # 0050.TW at strike
    )
    assert call["benchmark_symbol"] == "0050.TW"
    assert call["benchmark_ref_price"] == "100"

    # the call fell 6.58%; the index fell 10% over the same window
    st, scored = score_calls(
        _mature(st), {"2330.TW": Decimal("2200"), "0050.TW": Decimal("90")}
    )
    row = scored[0]
    assert row["realized_pct"] == "-6.58"  # still a loss in absolute terms
    assert row["benchmark_pct"] == "-10.00"
    assert row["excess_pct"] == "3.42"  # and still ahead of owning the index
    assert row["beat_benchmark"] is True

    card = research_ledger_payload(st)["scorecard"]["vs_benchmark"]
    assert card["judged_count"] == 1 and card["beat_count"] == 1
    assert card["beat_rate_pct"] == "100.0"
    assert card["unmeasured_count"] == 0


def test_an_avoid_beats_the_market_by_lagging_it() -> None:
    # "stay out of this" wins when the thing avoided underperformed. Scoring it
    # by the same >0 rule as a buy would grade every correct avoid as a miss.
    st, _ = _record(
        default_research_ledger_state(),
        stance="avoid",
        ref_price="100",
        benchmark_price="100",
    )
    st, scored = score_calls(
        _mature(st), {"2330.TW": Decimal("90"), "0050.TW": Decimal("105")}
    )
    assert scored[0]["excess_pct"] == "-15.00"
    assert scored[0]["beat_benchmark"] is True


def test_a_window_with_no_benchmark_is_unmeasured_not_a_draw() -> None:
    # Calls struck before the benchmark existed carry no strike level. Scoring
    # them as 0% excess would report "matched the market" about a window nobody
    # measured — and would dilute the beat rate with fiction.
    st, call = _record(default_research_ledger_state(), stance="hold", ref_price="100")
    assert call["benchmark_ref_price"] is None
    st, scored = score_calls(
        _mature(st), {"2330.TW": Decimal("110"), "0050.TW": Decimal("100")}
    )
    assert scored[0]["excess_pct"] is None
    assert scored[0]["beat_benchmark"] is None
    card = research_ledger_payload(st)["scorecard"]["vs_benchmark"]
    assert card["judged_count"] == 0 and card["unmeasured_count"] == 1
    assert card["beat_rate_pct"] is None  # no rate invented from nothing


def test_the_benchmark_cannot_outperform_itself() -> None:
    # 0050 is the TW benchmark. A call on it gets an excess of zero by
    # construction; calling that a win or a loss would be arithmetic, not skill.
    st, _ = _record(
        default_research_ledger_state(),
        symbol="0050.TW",
        stance="avoid",
        ref_price="100",
        benchmark_price="100",
    )
    st, scored = score_calls(_mature(st), {"0050.TW": Decimal("90")})
    assert scored[0]["excess_pct"] == "0.00"
    assert scored[0]["beat_benchmark"] is None


def test_a_sizing_warning_makes_no_claim_about_relative_return() -> None:
    st, _ = _record(
        default_research_ledger_state(),
        stance="size_down",
        ref_price="100",
        weight_pct="63.5",
        benchmark_price="100",
    )
    st, scored = score_calls(
        _mature(st), {"2330.TW": Decimal("85"), "0050.TW": Decimal("100")}
    )
    assert scored[0]["excess_pct"] == "-15.00"  # the fact is still recorded
    assert scored[0]["beat_benchmark"] is None  # but no verdict is invented
