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
