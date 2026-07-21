"""Net-value history + decision journal (2026-07-21).

The loop can run; this layer measures whether running it is any good.
Covers: rationale round-trip on order records, snapshot rows built from the
three book summaries with mark-quality fields, window performance arithmetic
vs benchmarks, retention cap, endpoints, backups, and contract registration.
"""

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.agent_contract import ACTION_CONTRACTS
from otto.local_terminal.crypto import (
    paper_summary_payload,
    place_paper_order,
)
from otto.local_terminal.equity_paper import (
    default_equity_paper_state,
    equity_summary_payload,
    place_equity_paper_order,
)
from otto.local_terminal.markets import default_markets_layout, markets_payload
from otto.local_terminal.paper_history import (
    MAX_SNAPSHOTS,
    clean_rationale,
    normalize_paper_history_state,
    paper_history_payload,
    record_paper_snapshot,
)
from otto.local_terminal.storage import LocalStateStore
from market_fixtures import fake_binance_tickers as _fake_tickers


def _fresh_market_cache() -> dict:
    live = markets_payload(default_markets_layout(), {}, fetcher=_fake_tickers, refresh=True)
    return live["cache"]


def _equity_quote(symbol: str = "AAPL", price: str = "300.00") -> dict:
    return {
        "symbol": symbol,
        "price": price,
        "currency": "USD",
        "previous_close": price,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "yahoo_public",
        "provider_id": "yahoo_chart_public",
    }


def _fake_summary(currency: str, equity: str, positions: list | None = None) -> dict:
    scope = {"currency": f"{currency} symbols only"} if currency != "USDT" else {}
    return {
        "account": {"cash": "0.00", "equity": equity, "total_pnl": "0.00"},
        "positions": positions or [],
        "scope": scope,
    }


def _benchmark(symbol: str, price: str) -> dict:
    return {
        "symbol": symbol,
        "price": price,
        "currency": "USD",
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


# ---- decision journal -------------------------------------------------------


def test_crypto_order_rationale_round_trips_into_summary() -> None:
    cache = _fresh_market_cache()
    state, order = place_paper_order(
        {},
        {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "0.01",
            "rationale": "BTC broke resistance; sizing 1% of book",
        },
        cache,
    )
    assert order["rationale"] == "BTC broke resistance; sizing 1% of book"
    summary = paper_summary_payload(state, cache)
    assert summary["recent_orders"][-1]["rationale"] == order["rationale"]


def test_equity_order_rationale_is_bounded_and_optional() -> None:
    state, order = place_equity_paper_order(
        default_equity_paper_state(),
        {"symbol": "AAPL", "side": "BUY", "quantity": "1", "rationale": "x" * 600},
        _equity_quote(),
    )
    assert len(order["rationale"]) == 500
    summary = equity_summary_payload(state)
    assert summary["recent_orders"][-1]["rationale"] == order["rationale"]

    _, bare = place_equity_paper_order(
        state, {"symbol": "AAPL", "side": "BUY", "quantity": "1"}, _equity_quote()
    )
    assert bare["rationale"] is None
    assert clean_rationale("   ") is None


# ---- snapshot rows ----------------------------------------------------------


def test_snapshot_records_three_books_with_mark_quality() -> None:
    positions = [
        {"symbol": "AAPL", "last_price": "300.00", "quote_age_seconds": 42},
        {"symbol": "MSFT", "last_price": "N/A", "quote_age_seconds": None},
    ]
    history, snapshot = record_paper_snapshot(
        {},
        crypto_summary=_fake_summary("USDT", "100000.00"),
        us_summary=_fake_summary("USD", "100600.00", positions),
        tw_summary=_fake_summary("TWD", "3000000.00"),
        benchmark_rows=[_benchmark("BTC-USD", "50000")],
        note="  after loop step  ",
    )
    assert len(history["snapshots"]) == 1
    books = {row["book"]: row for row in snapshot["books"]}
    assert books["crypto_usdt"]["currency"] == "USDT"
    assert books["us_equity_usd"]["equity"] == "100600.00"
    assert books["us_equity_usd"]["position_count"] == 2
    assert books["us_equity_usd"]["unmarked_position_count"] == 1
    assert books["us_equity_usd"]["oldest_quote_age_seconds"] == 42
    assert books["tw_equity_twd"]["currency"] == "TWD"
    assert snapshot["note"] == "after loop step"

    marks = {row["symbol"]: row for row in snapshot["benchmarks"]}
    assert marks["BTC-USD"]["state"] == "live"
    assert marks["BTC-USD"]["price"] == "50000"
    # missing benchmarks are recorded as unavailable, never dropped
    assert marks["SPY"]["state"] == "unavailable"
    assert marks["0050.TW"]["state"] == "unavailable"


# ---- window performance -----------------------------------------------------


def _two_snapshot_history() -> dict:
    history, _ = record_paper_snapshot(
        {},
        crypto_summary=_fake_summary("USDT", "100000.00"),
        us_summary=_fake_summary("USD", "100000.00"),
        tw_summary=_fake_summary("TWD", "3000000.00"),
        benchmark_rows=[_benchmark("BTC-USD", "50000")],
    )
    history, _ = record_paper_snapshot(
        history,
        crypto_summary=_fake_summary("USDT", "110000.00"),
        us_summary=_fake_summary("USD", "95000.00"),
        tw_summary=_fake_summary("TWD", "3000000.00"),
        benchmark_rows=[_benchmark("BTC-USD", "55000")],
    )
    return history


def test_history_measures_book_and_benchmark_change_over_window() -> None:
    payload = paper_history_payload(_two_snapshot_history())
    perf = payload["performance"]
    books = {row["book"]: row for row in perf["books"]}
    assert books["crypto_usdt"]["change_pct"] == "10.00"
    assert books["us_equity_usd"]["change_pct"] == "-5.00"
    assert books["tw_equity_twd"]["change_pct"] == "0.00"
    marks = {row["symbol"]: row for row in perf["benchmarks"]}
    assert marks["BTC-USD"]["change_pct"] == "10.00"
    # unavailable at both endpoints -> null, and the note says null != zero
    assert marks["SPY"]["change_pct"] is None
    assert "missing data, not zero performance" in perf["note"]
    assert perf["window"]["snapshot_count"] == 2


def test_history_needs_two_snapshots_before_performance() -> None:
    empty = paper_history_payload({})
    assert empty["performance"] is None
    assert "at least two snapshots" in empty["performance_note"]
    one, _ = record_paper_snapshot(
        {},
        crypto_summary=_fake_summary("USDT", "1.00"),
        us_summary=_fake_summary("USD", "1.00"),
        tw_summary=_fake_summary("TWD", "1.00"),
    )
    assert paper_history_payload(one)["performance"] is None


def test_normalize_caps_retained_snapshots_keeping_newest() -> None:
    rows = [{"snapshot_id": f"snap-{i}"} for i in range(MAX_SNAPSHOTS + 5)]
    state = normalize_paper_history_state({"snapshots": rows})
    assert len(state["snapshots"]) == MAX_SNAPSHOTS
    assert state["snapshots"][-1]["snapshot_id"] == f"snap-{MAX_SNAPSHOTS + 4}"
    assert state["snapshots"][0]["snapshot_id"] == "snap-5"


# ---- endpoints + persistence ------------------------------------------------


def test_snapshot_and_history_endpoints_with_backups(tmp_path, monkeypatch) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    store.write_market_cache(_fresh_market_cache())
    client = TestClient(server.create_app())

    # refresh=false: hermetic — no held equity symbols, benchmarks from cold
    # cache are recorded as unavailable instead of fetched
    first = client.post("/api/paper/snapshot", json={"refresh": False, "note": "day 1"})
    assert first.status_code == 200
    body = first.json()
    assert {row["book"] for row in body["snapshot"]["books"]} == {
        "crypto_usdt",
        "us_equity_usd",
        "tw_equity_twd",
    }
    assert body["snapshot_count_total"] == 1
    assert body["read_action"] == "paper_history"
    assert store.paper_history_path.is_file()

    second = client.post("/api/paper/snapshot", json={"refresh": False})
    assert second.status_code == 200
    assert second.json()["snapshot_count_total"] == 2
    bak = store.paper_history_path.with_name("paper_history.json.bak1")
    assert bak.is_file(), "history writes must rotate backups like every ledger"

    history = client.get("/api/paper/history", params={"limit": 1})
    assert history.status_code == 200
    payload = history.json()
    assert payload["snapshot_count_total"] == 2
    assert payload["snapshot_count_returned"] == 1
    assert payload["performance"] is None  # limit=1 window can't measure change

    unknown = client.post("/api/paper/snapshot", json={"bogus": True})
    assert unknown.status_code == 422


def test_contract_registers_history_actions() -> None:
    actions = {action.action_id: action for action in ACTION_CONTRACTS}
    snapshot = actions["paper_snapshot_record"]
    assert snapshot.method == "POST"
    assert snapshot.endpoint == "/api/paper/snapshot"
    assert snapshot.local_mutation is True
    history = actions["paper_history"]
    assert history.method == "GET"
    assert history.endpoint == "/api/paper/history"
    assert history.local_mutation is False
