"""US-equity paper ledger — cross-asset allocation with crypto-book honesty.

The fill price is fetched live at submit (no separate refresh step, no
stale-fill window); a failed, non-USD, or stale quote refuses the order. v1
scope is stated, not implied: MARKET only, USD only, zero-commission
assumption on every fill record.
"""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.equity_paper import (
    EQUITY_QUOTE_MAX_AGE_SECONDS,
    EquityOrderError,
    default_equity_paper_state,
    equity_summary_payload,
    place_equity_paper_order,
)
from otto.local_terminal.storage import LocalStateStore


def _quote(symbol: str = "AAPL", price: str = "310.50", currency: str = "USD",
           age_seconds: float = 5.0) -> dict:
    stamp = (datetime.now(tz=UTC) - timedelta(seconds=age_seconds)).isoformat(
        timespec="seconds"
    )
    return {
        "symbol": symbol,
        "price": price,
        "currency": currency,
        "retrieved_at": stamp,
        "source": "yahoo_finance_chart_quote",
        "provider_id": "yahoo_finance_public_quote_snapshot",
    }


def test_buy_then_sell_realizes_pnl() -> None:
    state, order = place_equity_paper_order(
        default_equity_paper_state(),
        {"symbol": "AAPL", "side": "BUY", "quantity": "2"},
        _quote(price="300.00"),
    )
    assert order["status"] == "FILLED"
    assert order["quote_age_seconds"] <= 10
    assert state["positions"]["AAPL"]["avg_price"] == "300.00"
    assert state["account"]["cash"] == "99400.00"

    state, _ = place_equity_paper_order(
        state,
        {"symbol": "AAPL", "side": "SELL", "quantity": "1"},
        _quote(price="310.00"),
    )
    assert state["positions"]["AAPL"]["quantity"] == "1"
    assert state["positions"]["AAPL"]["realized_pnl"] == "10.00"
    assert state["account"]["cash"] == "99710.00"


def test_refusals_scope_and_freshness() -> None:
    base = default_equity_paper_state()
    with pytest.raises(EquityOrderError, match="STOP is not implemented"):
        place_equity_paper_order(
            base, {"symbol": "AAPL", "side": "BUY", "quantity": "1",
                   "order_type": "STOP"}, _quote()
        )
    with pytest.raises(EquityOrderError, match="quoted in TWD"):
        place_equity_paper_order(
            base, {"symbol": "2330.TW", "side": "BUY", "quantity": "1"},
            _quote(symbol="2330.TW", currency="TWD"),
        )
    with pytest.raises(EquityOrderError, match="not fresh"):
        place_equity_paper_order(
            base, {"symbol": "AAPL", "side": "BUY", "quantity": "1"},
            _quote(age_seconds=EQUITY_QUOTE_MAX_AGE_SECONDS + 30),
        )
    with pytest.raises(EquityOrderError, match="No live quote"):
        place_equity_paper_order(
            base, {"symbol": "AAPL", "side": "BUY", "quantity": "1"}, None
        )
    with pytest.raises(EquityOrderError, match="more than the long"):
        place_equity_paper_order(
            base, {"symbol": "AAPL", "side": "SELL", "quantity": "1"}, _quote()
        )
    with pytest.raises(EquityOrderError, match="Insufficient"):
        place_equity_paper_order(
            base, {"symbol": "AAPL", "side": "BUY", "quantity": "10000"},
            _quote(price="310.50"),
        )


def test_summary_marks_positions_and_states_scope() -> None:
    state, _ = place_equity_paper_order(
        default_equity_paper_state(),
        {"symbol": "AAPL", "side": "BUY", "quantity": "2"},
        _quote(price="300.00"),
    )
    summary = equity_summary_payload(state, [_quote(price="305.00", age_seconds=60)])
    position = summary["positions"][0]
    assert position["last_price"] == "305.00"
    assert position["unrealized_pnl"] == "10.00"
    assert position["quote_age_seconds"] >= 59
    assert summary["account"]["equity"] == "100010.00"
    assert summary["scope"]["order_types"] == ["MARKET", "LIMIT"]
    assert summary["safety"]["short"] is False

    unmarked = equity_summary_payload(state, [])
    assert unmarked["positions"][0]["last_price"] == "N/A"
    assert unmarked["account"]["equity"] == "100000.00"  # marked at avg by policy


def test_endpoint_fills_via_injected_live_lookup(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    meta_price = {"value": 310.50}

    def _fake_yahoo(*, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "currency": "USD",
            "exchangeName": "NMS",
            "fullExchangeName": "NasdaqGS",
            "regularMarketPrice": meta_price["value"],
            "chartPreviousClose": 300.0,
            "regularMarketDayHigh": 312.0,
            "regularMarketDayLow": 299.0,
            "regularMarketVolume": 1000,
            "regularMarketTime": int(datetime.now(tz=UTC).timestamp()),
        }

    monkeypatch.setattr(server, "YAHOO_FETCHER", _fake_yahoo)
    client = TestClient(server.create_app())

    response = client.post(
        "/api/equity/orders",
        json={"symbol": "aapl", "side": "BUY", "quantity": "1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["submitted_order"]["symbol"] == "AAPL"
    assert body["submitted_order"]["quote_price"] == "310.5"
    assert body["positions"][0]["symbol"] == "AAPL"

    summary = client.get("/api/equity/summary").json()
    assert summary["positions"][0]["quantity"] == "1"
    assert summary["asset_class"] == "us_equity"

    extra = client.post(
        "/api/equity/orders",
        json={"symbol": "AAPL", "side": "BUY", "quantity": "1", "leverage": 5},
    )
    assert extra.status_code == 422  # extra=forbid


def test_equity_state_is_backup_protected(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_equity_paper_state(default_equity_paper_state())
    store.write_equity_paper_state(default_equity_paper_state())
    backup = store.equity_paper_state_path.with_name(
        store.equity_paper_state_path.name + ".bak1"
    )
    assert backup.is_file()
    kinds = dict(store.protected_state_files())
    assert "equity_paper_state" in kinds


def test_contract_registration(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    contract = client.get("/api/agent-contract").json()
    actions = {action["action_id"]: action for action in contract["actions"]}
    assert actions["equity_submit_paper_order"]["endpoint"] == "/api/equity/orders"
    assert actions["equity_paper_summary"]["method"] == "GET"
    paper_route = next(r for r in contract["routes"] if r["route_id"] == "paper")
    assert "equity_submit_paper_order" in paper_route["recommended_actions"]


# ---- TW book (TWD, board lots, real fee/tax rules) ----

from otto.local_terminal.equity_paper import (  # noqa: E402
    TW_BOOK,
    default_tw_equity_paper_state,
)


def _tw_quote(price: str = "600.00", previous_close: str = "590.00",
              age_seconds: float = 5.0, symbol: str = "2330.TW") -> dict:
    row = _quote(symbol=symbol, price=price, currency="TWD", age_seconds=age_seconds)
    row["previous_close"] = previous_close
    return row


def test_tw_buy_charges_brokerage_and_sell_adds_tax() -> None:
    state, order = place_equity_paper_order(
        default_tw_equity_paper_state(),
        {"symbol": "2330.TW", "side": "BUY", "quantity": "1000"},
        _tw_quote(price="600.00"),
        TW_BOOK,
    )
    # notional 600000, brokerage 0.1425% = 855.00
    assert state["account"]["cash"] == "2399145.00"
    assert state["fills"][-1]["fee"] == "855.00"
    assert state["fills"][-1]["tax"] == "0.00"

    state, _ = place_equity_paper_order(
        state,
        {"symbol": "2330.TW", "side": "SELL", "quantity": "1000"},
        _tw_quote(price="610.00", previous_close="600.00"),
        TW_BOOK,
    )
    # proceeds 610000 - fee 869.25 - tax 1830 = 607300.75
    assert state["fills"][-1]["fee"] == "869.25"
    assert state["fills"][-1]["tax"] == "1830.00"
    assert state["account"]["cash"] == "3006445.75"
    assert "2330.TW" not in state["positions"]


def test_tw_minimum_brokerage_fee_applies() -> None:
    state, _ = place_equity_paper_order(
        default_tw_equity_paper_state(),
        {"symbol": "1234.TW", "side": "BUY", "quantity": "1000"},
        _tw_quote(price="10.00", previous_close="10.00", symbol="1234.TW"),
        TW_BOOK,
    )
    # notional 10000 -> 0.1425% = 14.25 -> below NT$20 minimum
    assert state["fills"][-1]["fee"] == "20.00"


def test_tw_odd_lot_fills_with_stated_caveat() -> None:
    # 10 shares of 2330 at 600 = NT$6,000 notional; 0.1425% = NT$8.55 -> the
    # NT$20 minimum applies. A 3M account is no longer locked to 3 board lots.
    state, order = place_equity_paper_order(
        default_tw_equity_paper_state(),
        {"symbol": "2330.TW", "side": "BUY", "quantity": "10"},
        _tw_quote(),
        TW_BOOK,
    )
    assert order["status"] == "FILLED"
    assert order["lot_type"] == "odd_lot"
    assert "unavailable" in order["odd_lot_note"]  # no session row injected here
    fill = state["fills"][-1]
    assert fill["lot_type"] == "odd_lot"
    assert fill["fee"] == "20.00"  # minimum applies to tiny odd-lot notionals
    assert state["positions"]["2330.TW"]["quantity"] == "10"


def test_tw_board_lot_is_labeled_and_fractional_shares_refused() -> None:
    state, order = place_equity_paper_order(
        default_tw_equity_paper_state(),
        {"symbol": "2330.TW", "side": "BUY", "quantity": "1000"},
        _tw_quote(),
        TW_BOOK,
    )
    assert order["lot_type"] == "board_lot"
    assert "odd_lot_note" not in order
    with pytest.raises(EquityOrderError, match="whole shares"):
        place_equity_paper_order(
            state,
            {"symbol": "2330.TW", "side": "BUY", "quantity": "10.5"},
            _tw_quote(),
            TW_BOOK,
        )


def test_tw_daily_limit_guard_refuses_anomalous_quotes() -> None:
    with pytest.raises(EquityOrderError, match="daily limit band"):
        place_equity_paper_order(
            default_tw_equity_paper_state(),
            {"symbol": "2330.TW", "side": "BUY", "quantity": "1000"},
            _tw_quote(price="700.00", previous_close="600.00"),  # +16.7%
            TW_BOOK,
        )


def test_tw_book_refuses_usd_symbols() -> None:
    with pytest.raises(EquityOrderError, match="TWD-quoted symbols only"):
        place_equity_paper_order(
            default_tw_equity_paper_state(),
            {"symbol": "AAPL", "side": "BUY", "quantity": "1000"},
            _quote(symbol="AAPL", currency="USD"),
            TW_BOOK,
        )


def test_tw_endpoint_fills_via_injected_lookup(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))

    def _fake_yahoo(*, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "currency": "TWD",
            "exchangeName": "TAI",
            "fullExchangeName": "Taiwan",
            "regularMarketPrice": 600.0,
            "chartPreviousClose": 595.0,
            "regularMarketDayHigh": 605.0,
            "regularMarketDayLow": 590.0,
            "regularMarketVolume": 1000,
            "regularMarketTime": int(datetime.now(tz=UTC).timestamp()),
        }

    monkeypatch.setattr(server, "YAHOO_FETCHER", _fake_yahoo)
    monkeypatch.setattr(server, "fetch_twse_odd_lot_row", lambda code: None)
    client = TestClient(server.create_app())

    response = client.post(
        "/api/equity/tw/orders",
        json={"symbol": "2330.tw", "side": "BUY", "quantity": "1000"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["submitted_order"]["symbol"] == "2330.TW"
    assert body["asset_class"] == "tw_equity"
    assert body["scope"]["lot_size"] == 1000

    odd = client.post(
        "/api/equity/tw/orders",
        json={"symbol": "2330.TW", "side": "BUY", "quantity": "500"},
    )
    assert odd.status_code == 200
    assert odd.json()["submitted_order"]["lot_type"] == "odd_lot"

    summary = client.get("/api/equity/tw/summary").json()
    assert summary["positions"][0]["quantity"] == "1500"
    assert summary["account"]["quote_asset"] == "TWD"
    assert "allowed" in summary["scope"]["odd_lot"]


def test_tw_state_is_backup_protected(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_tw_equity_paper_state(default_tw_equity_paper_state())
    store.write_tw_equity_paper_state(default_tw_equity_paper_state())
    backup = store.tw_equity_paper_state_path.with_name(
        store.tw_equity_paper_state_path.name + ".bak1"
    )
    assert backup.is_file()
    assert "tw_equity_paper_state" in dict(store.protected_state_files())


def test_summary_refresh_marks_positions_to_current_prices(tmp_path, monkeypatch) -> None:
    """P4 (2026-07-19 dogfood): a summary that marks at cost hides P&L.

    The default read stays cheap and local; ?refresh=true fetches current
    prices for held symbols only, so the decision loop sees real unrealized
    P&L instead of positions valued at their own cost basis.
    """
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    price = {"value": 300.0}

    def _fake_yahoo(*, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "currency": "USD",
            "exchangeName": "NMS",
            "fullExchangeName": "NasdaqGS",
            "regularMarketPrice": price["value"],
            "chartPreviousClose": 300.0,
            "regularMarketDayHigh": 320.0,
            "regularMarketDayLow": 295.0,
            "regularMarketVolume": 1000,
            "regularMarketTime": int(datetime.now(tz=UTC).timestamp()),
        }

    monkeypatch.setattr(server, "YAHOO_FETCHER", _fake_yahoo)
    client = TestClient(server.create_app())
    assert client.post(
        "/api/equity/orders", json={"symbol": "AAPL", "side": "BUY", "quantity": "2"}
    ).status_code == 200

    price["value"] = 330.0  # market moves after the fill
    refreshed = client.get("/api/equity/summary?refresh=true").json()
    position = refreshed["positions"][0]
    assert position["last_price"] == "330.00"
    assert position["unrealized_pnl"] == "60.00"
    assert refreshed["account"]["equity"] == "100060.00"

    # default read is still a cheap local read (no fetch): it serves the cache
    cached = client.get("/api/equity/summary").json()
    assert cached["positions"][0]["last_price"] in {"330.00", "300.00"}


def test_tw_summary_accepts_refresh_flag(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    empty = client.get("/api/equity/tw/summary?refresh=true")
    assert empty.status_code == 200
    assert empty.json()["positions"] == []  # no holdings, no network needed

# ---- LIMIT orders: rest, process, cancel (2026-07-22) ----

from otto.local_terminal.equity_paper import (  # noqa: E402
    cancel_equity_paper_order,
    process_equity_paper_orders,
)


def test_limit_below_market_rests_without_touching_cash() -> None:
    state, order = place_equity_paper_order(
        default_equity_paper_state(),
        {"symbol": "AAPL", "side": "BUY", "quantity": "2", "order_type": "LIMIT",
         "limit_price": "250.00"},
        _quote(price="300.00"),
    )
    assert order["status"] == "WORKING"
    assert order["limit_price"] == "250.00"
    assert "Resting LIMIT" in order["reason"]
    assert state["account"]["cash"] == "100000.00"
    assert state["fills"] == []
    assert state["ledger"][-1]["event"] == "WORKING"


def test_limit_at_or_better_fills_immediately_at_market() -> None:
    state, order = place_equity_paper_order(
        default_equity_paper_state(),
        {"symbol": "AAPL", "side": "BUY", "quantity": "1", "order_type": "LIMIT",
         "limit_price": "320.00"},
        _quote(price="300.00"),
    )
    assert order["status"] == "FILLED"
    assert "at or better than limit" in order["reason"]
    # fills at the market price, never at the limit itself
    assert state["fills"][-1]["price"] == "300.00"


def test_limit_requires_limit_price_and_checks_worst_case_cash() -> None:
    with pytest.raises(EquityOrderError, match="Limit price is required"):
        place_equity_paper_order(
            default_equity_paper_state(),
            {"symbol": "AAPL", "side": "BUY", "quantity": "1", "order_type": "LIMIT"},
            _quote(),
        )
    # resting BUY is checked against the limit (worst case), not the market
    with pytest.raises(EquityOrderError, match="Insufficient paper cash"):
        place_equity_paper_order(
            default_equity_paper_state(),
            {"symbol": "AAPL", "side": "BUY", "quantity": "400", "order_type": "LIMIT",
             "limit_price": "260.00"},  # 400 * 260 = 104,000 > 100,000
            _quote(price="300.00"),
        )


def test_process_fills_resting_limit_when_quote_crosses() -> None:
    state, order = place_equity_paper_order(
        default_equity_paper_state(),
        {"symbol": "AAPL", "side": "BUY", "quantity": "2", "order_type": "LIMIT",
         "limit_price": "250.00"},
        _quote(price="300.00"),
    )
    # not crossed yet -> untouched, not even "skipped"
    state, report = process_equity_paper_orders(state, [_quote(price="260.00")])
    assert report["filled"] == [] and report["skipped"] == []
    assert report["open_orders_remaining"] == 1
    # market drops through the limit -> fills at the live quote 245, not 250
    state, report = process_equity_paper_orders(state, [_quote(price="245.00")])
    assert [f["order_id"] for f in report["filled"]] == [order["order_id"]]
    assert report["filled"][0]["fill_price"] == "245.00"
    assert state["positions"]["AAPL"]["avg_price"] == "245.00"
    assert state["account"]["cash"] == "99510.00"
    assert report["open_orders_remaining"] == 0


def test_process_skips_stale_or_missing_quotes_with_reasons() -> None:
    state, order = place_equity_paper_order(
        default_equity_paper_state(),
        {"symbol": "AAPL", "side": "BUY", "quantity": "1", "order_type": "LIMIT",
         "limit_price": "250.00"},
        _quote(price="300.00"),
    )
    state, report = process_equity_paper_orders(state, [])
    assert report["skipped"][0]["reason"].startswith("no live quote")
    stale = _quote(price="200.00", age_seconds=EQUITY_QUOTE_MAX_AGE_SECONDS + 60)
    state, report = process_equity_paper_orders(state, [stale])
    assert "not fresh" in report["skipped"][0]["reason"]
    resting = next(o for o in state["orders"] if o["order_id"] == order["order_id"])
    assert resting["status"] == "WORKING"


def test_cancel_only_working_orders() -> None:
    state, order = place_equity_paper_order(
        default_equity_paper_state(),
        {"symbol": "AAPL", "side": "BUY", "quantity": "1", "order_type": "LIMIT",
         "limit_price": "250.00"},
        _quote(price="300.00"),
    )
    state, cancelled = cancel_equity_paper_order(state, order["order_id"])
    assert cancelled["status"] == "CANCELLED"
    assert state["ledger"][-1]["event"] == "CANCELLED"
    with pytest.raises(EquityOrderError, match="Only WORKING"):
        cancel_equity_paper_order(state, order["order_id"])
    with pytest.raises(EquityOrderError, match="Unknown equity paper order id"):
        cancel_equity_paper_order(state, "equity-nope")


def test_tw_limit_odd_lot_rests_and_fills_with_tw_fees() -> None:
    state, order = place_equity_paper_order(
        default_tw_equity_paper_state(),
        {"symbol": "2330.TW", "side": "BUY", "quantity": "10", "order_type": "LIMIT",
         "limit_price": "580.00"},
        _tw_quote(price="600.00"),
        TW_BOOK,
    )
    assert order["status"] == "WORKING"
    assert order["lot_type"] == "odd_lot"
    state, report = process_equity_paper_orders(
        state, [_tw_quote(price="575.00", previous_close="590.00")], TW_BOOK
    )
    assert len(report["filled"]) == 1
    fill = state["fills"][-1]
    assert fill["price"] == "575.00"
    assert fill["fee"] == "20.00"  # NT$20 minimum on the tiny odd-lot notional
    assert fill["lot_type"] == "odd_lot"


def test_equity_process_and_cancel_endpoints(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    live_price = {"value": 300.0}

    def _fake_yahoo(*, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "currency": "USD",
            "exchangeName": "NMS",
            "fullExchangeName": "NasdaqGS",
            "regularMarketPrice": live_price["value"],
            "chartPreviousClose": live_price["value"],
            "regularMarketDayHigh": live_price["value"] + 5,
            "regularMarketDayLow": live_price["value"] - 5,
            "regularMarketVolume": 1000,
            "regularMarketTime": int(datetime.now(tz=UTC).timestamp()),
        }

    monkeypatch.setattr(server, "YAHOO_FETCHER", _fake_yahoo)
    client = TestClient(server.create_app())

    submitted = client.post(
        "/api/equity/orders",
        json={"symbol": "AAPL", "side": "BUY", "quantity": "1",
              "order_type": "LIMIT", "limit_price": "250.00"},
    )
    assert submitted.status_code == 200
    order_id = submitted.json()["submitted_order"]["order_id"]
    assert submitted.json()["submitted_order"]["status"] == "WORKING"

    untouched = client.post("/api/equity/orders/process")
    assert untouched.status_code == 200
    assert untouched.json()["filled"] == []

    live_price["value"] = 240.0
    processed = client.post("/api/equity/orders/process")
    assert processed.status_code == 200
    assert [f["order_id"] for f in processed.json()["filled"]] == [order_id]
    assert processed.json()["filled"][0]["fill_price"] == "240.00"

    refused = client.post("/api/equity/orders/cancel", json={"order_id": order_id})
    assert refused.status_code == 400  # already FILLED

    resting = client.post(
        "/api/equity/orders",
        json={"symbol": "AAPL", "side": "BUY", "quantity": "1",
              "order_type": "LIMIT", "limit_price": "100.00"},
    )
    resting_id = resting.json()["submitted_order"]["order_id"]
    cancelled = client.post("/api/equity/orders/cancel", json={"order_id": resting_id})
    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled_order"]["status"] == "CANCELLED"
    assert cancelled.json()["open_orders_remaining"] == 0


# ---- odd-lot session pricing (2026-07-22): real TWT53U data, not a caveat ----


def _odd_lot_row(price="602.00", bid="601.00", ask="603.00") -> dict:
    return {"code": "2330", "price": price, "bid": bid, "ask": ask,
            "source": "twse_odd_lot_twt53u", "retrieved_at": "now"}


def test_odd_lot_buy_pays_the_odd_lot_session_ask() -> None:
    state, order = place_equity_paper_order(
        default_tw_equity_paper_state(),
        {"symbol": "2330.TW", "side": "BUY", "quantity": "10"},
        _tw_quote(price="600.00"),
        TW_BOOK,
        odd_lot_row=_odd_lot_row(),
    )
    assert order["odd_lot_fill_basis"] == "odd_lot_ask"
    assert "TWT53U" in order["odd_lot_note"]
    fill = state["fills"][-1]
    assert fill["price"] == "603.00"  # odd-lot ask, not the regular 600
    assert fill["odd_lot_fill_basis"] == "odd_lot_ask"


def test_odd_lot_sell_hits_the_odd_lot_bid_and_far_data_is_refused() -> None:
    state, _ = place_equity_paper_order(
        default_tw_equity_paper_state(),
        {"symbol": "2330.TW", "side": "BUY", "quantity": "10"},
        _tw_quote(price="600.00"),
        TW_BOOK,
    )
    state, sell = place_equity_paper_order(
        state,
        {"symbol": "2330.TW", "side": "SELL", "quantity": "10"},
        _tw_quote(price="600.00"),
        TW_BOOK,
        odd_lot_row=_odd_lot_row(),
    )
    assert sell["odd_lot_fill_basis"] == "odd_lot_bid"
    assert state["fills"][-1]["price"] == "601.00"

    # odd-lot data >5% away from the regular quote = mixed vintage, refused
    state2, order2 = place_equity_paper_order(
        default_tw_equity_paper_state(),
        {"symbol": "2330.TW", "side": "BUY", "quantity": "10"},
        _tw_quote(price="600.00"),
        TW_BOOK,
        odd_lot_row=_odd_lot_row(price="700.00", bid="699.00", ask="701.00"),
    )
    assert "odd_lot_fill_basis" not in order2
    assert state2["fills"][-1]["price"] == "600.00"
    assert "unavailable" in state2["fills"][-1]["odd_lot_note"]


def test_resting_odd_lot_limit_fills_at_session_price_when_processed() -> None:
    state, order = place_equity_paper_order(
        default_tw_equity_paper_state(),
        {"symbol": "2330.TW", "side": "BUY", "quantity": "10", "order_type": "LIMIT",
         "limit_price": "590.00"},
        _tw_quote(price="600.00"),
        TW_BOOK,
    )
    assert order["status"] == "WORKING"
    state, report = process_equity_paper_orders(
        state,
        [_tw_quote(price="588.00", previous_close="595.00")],
        TW_BOOK,
        odd_lot_rows={"2330": _odd_lot_row(price="589.00", bid="588.50", ask="589.50")},
    )
    assert len(report["filled"]) == 1
    fill = state["fills"][-1]
    assert fill["price"] == "589.50"  # odd-lot session ask
    assert fill["odd_lot_fill_basis"] == "odd_lot_ask"


def test_fetch_twse_odd_lot_row_parses_and_misses_cleanly() -> None:
    from otto.local_terminal.twse_data import fetch_twse_odd_lot_row

    rows = [{"Code": "2330", "Name": "台積電", "TradePrice": "2410.0000",
             "BestBidPrice": "2410.0000", "BestAskPrice": "2415.0000"}]
    row = fetch_twse_odd_lot_row("2330.TW", reader=lambda: rows)
    assert row["ask"] == "2415.0000"
    assert row["bid"] == "2410.0000"
    assert fetch_twse_odd_lot_row("9999", reader=lambda: rows) is None
    assert fetch_twse_odd_lot_row("2330", reader=lambda: (_ for _ in ()).throw(OSError())) is None
