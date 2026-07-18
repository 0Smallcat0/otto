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
    with pytest.raises(EquityOrderError, match="MARKET orders only"):
        place_equity_paper_order(
            base, {"symbol": "AAPL", "side": "BUY", "quantity": "1",
                   "order_type": "LIMIT"}, _quote()
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
    assert summary["scope"]["order_types"] == ["MARKET"]
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
