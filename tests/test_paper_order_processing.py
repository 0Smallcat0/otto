"""Resting-order processing (2026-07-21).

Until process_paper_orders existed a resting LIMIT/STOP order could never
fill — "the book supports LIMIT orders" was quietly false. These tests pin
the trigger rules, the freshness gate, and the refuse-don't-drop behavior
for orders that cannot fill safely.
"""

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.agent_contract import ACTION_CONTRACTS
from otto.local_terminal.crypto import (
    place_paper_order,
    process_paper_orders,
)
from otto.local_terminal.markets import default_markets_layout, markets_payload
from otto.local_terminal.storage import LocalStateStore
from market_fixtures import fake_binance_tickers as _fake_tickers


def _fresh_cache() -> dict:
    return markets_payload(default_markets_layout(), {}, fetcher=_fake_tickers, refresh=True)[
        "cache"
    ]


def _order(state: dict, cache: dict, **kwargs) -> tuple[dict, dict]:
    request = {"symbol": "BTCUSDT", "quantity": "0.01", **kwargs}
    return place_paper_order(state, request, cache)


def test_limit_buy_fills_at_market_price_when_crossed() -> None:
    cache = _fresh_cache()
    state, order = _order({}, cache, side="BUY", order_type="LIMIT", limit_price="120")
    assert order["status"] == "WORKING"
    state, report = process_paper_orders(state, cache)
    assert [f["order_id"] for f in report["filled"]] == [order["order_id"]]
    # crosses the spread: BUY pays the ask (100.50), never the limit price
    assert report["filled"][0]["fill_price"] == "100.50"
    assert report["filled"][0]["fill_basis"] == "ask"
    assert "limit 120.00 satisfied" in report["filled"][0]["trigger"]
    assert state["positions"]["BTCUSDT"]["quantity"] == "0.01"
    assert report["open_orders_remaining"] == 0


def test_limit_buy_below_market_keeps_resting() -> None:
    cache = _fresh_cache()
    state, order = _order({}, cache, side="BUY", order_type="LIMIT", limit_price="50")
    state, report = process_paper_orders(state, cache)
    assert report["filled"] == []
    assert report["skipped"] == []
    assert report["open_orders_remaining"] == 1
    resting = next(o for o in state["orders"] if o["order_id"] == order["order_id"])
    assert resting["status"] == "WORKING"


def test_stop_sell_triggers_and_closes_position() -> None:
    cache = _fresh_cache()
    state, _ = _order({}, cache, side="BUY", order_type="MARKET", quantity="0.5")
    state, stop = _order(
        state, cache, side="SELL", order_type="STOP", quantity="0.5", stop_price="150"
    )
    state, report = process_paper_orders(state, cache)
    assert [f["order_id"] for f in report["filled"]] == [stop["order_id"]]
    assert "stop 150.00 triggered" in report["filled"][0]["trigger"]
    # SELL hits the bid, not the last print
    assert report["filled"][0]["fill_price"] == "99.50"
    assert report["filled"][0]["fill_basis"] == "bid"
    assert "BTCUSDT" not in state["positions"]


def test_market_fill_without_book_uses_last_and_says_so() -> None:
    def _no_book_tickers(symbols: list[str]) -> list[dict[str, str]]:
        return [
            {
                "symbol": symbol,
                "lastPrice": "100.00",
                "priceChange": "1.00",
                "priceChangePercent": "1.00",
                "highPrice": "110.00",
                "lowPrice": "90.00",
                "volume": "12345",
                "openPrice": "99.00",
            }
            for symbol in symbols
        ]

    cache = markets_payload(
        default_markets_layout(), {}, fetcher=_no_book_tickers, refresh=True
    )["cache"]
    state, order = _order({}, cache, side="BUY", order_type="MARKET")
    assert order["fill_basis"] == "last_price_no_book"
    assert state["fills"][-1]["price"] == "100.00"


def test_book_side_far_from_last_is_refused_as_mixed_vintage() -> None:
    def _skewed_book_tickers(symbols: list[str]) -> list[dict[str, str]]:
        return [
            {
                "symbol": symbol,
                "lastPrice": "140.00",
                "priceChange": "1.00",
                "priceChangePercent": "1.00",
                "highPrice": "150.00",
                "lowPrice": "90.00",
                "volume": "12345",
                "bidPrice": "99.50",  # a cached ladder from another vintage
                "askPrice": "100.50",
                "openPrice": "139.00",
            }
            for symbol in symbols
        ]

    cache = markets_payload(
        default_markets_layout(), {}, fetcher=_skewed_book_tickers, refresh=True
    )["cache"]
    state, order = _order({}, cache, side="BUY", order_type="MARKET")
    # trusting the 100.50 ask against a 140 last would fill at a phantom level
    assert order["fill_basis"] == "last_price_book_out_of_band"
    assert state["fills"][-1]["price"] == "140.00"


def test_market_buy_pays_the_ask() -> None:
    cache = _fresh_cache()
    state, order = _order({}, cache, side="BUY", order_type="MARKET")
    assert order["fill_basis"] == "ask"
    assert state["fills"][-1]["price"] == "100.50"
    state, sell = _order(state, cache, side="SELL", order_type="MARKET")
    assert sell["fill_basis"] == "bid"
    assert state["fills"][-1]["price"] == "99.50"


def test_stop_limit_needs_both_conditions() -> None:
    cache = _fresh_cache()
    # stop met (100 >= 90) but limit not (100 <= 95 is false) -> keeps resting
    state, _ = _order(
        {}, cache, side="BUY", order_type="STOP_LIMIT", stop_price="90", limit_price="95"
    )
    state, report = process_paper_orders(state, cache)
    assert report["filled"] == []
    assert report["open_orders_remaining"] == 1
    # both met -> fills
    state, both = _order(
        state, cache, side="BUY", order_type="STOP_LIMIT", stop_price="90", limit_price="120"
    )
    state, report = process_paper_orders(state, cache)
    assert [f["order_id"] for f in report["filled"]] == [both["order_id"]]


def test_stale_or_missing_quote_skips_instead_of_filling() -> None:
    cache = _fresh_cache()
    state, order = _order({}, cache, side="BUY", order_type="LIMIT", limit_price="120")
    state, report = process_paper_orders(state, {})  # cold cache at processing time
    assert report["filled"] == []
    assert report["skipped"][0]["order_id"] == order["order_id"]
    assert "crypto_refresh_public" in report["skipped"][0]["reason"]
    resting = next(o for o in state["orders"] if o["order_id"] == order["order_id"])
    assert resting["status"] == "WORKING"


def test_insufficient_cash_at_processing_keeps_order_working() -> None:
    cache = _fresh_cache()
    state, resting = _order(
        {}, cache, side="BUY", order_type="LIMIT", quantity="800", limit_price="120"
    )
    # spend most of the cash after the order was placed
    state, _ = _order(state, cache, side="BUY", order_type="MARKET", quantity="300")
    state, report = process_paper_orders(state, cache)
    assert report["filled"] == []
    assert report["skipped"][0]["order_id"] == resting["order_id"]
    assert "insufficient paper cash" in report["skipped"][0]["reason"]


def test_sell_larger_than_remaining_position_keeps_order_working() -> None:
    cache = _fresh_cache()
    state, _ = _order({}, cache, side="BUY", order_type="MARKET", quantity="0.5")
    state, resting = _order(
        state, cache, side="SELL", order_type="LIMIT", quantity="0.5", limit_price="90"
    )
    state, _ = _order(state, cache, side="SELL", order_type="MARKET", quantity="0.4")
    state, report = process_paper_orders(state, cache)
    assert report["filled"] == []
    assert report["skipped"][0]["order_id"] == resting["order_id"]
    assert "position is smaller" in report["skipped"][0]["reason"]


def test_process_endpoint_and_contract(tmp_path, monkeypatch) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    store.write_market_cache(_fresh_cache())
    client = TestClient(server.create_app())

    submit = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "LIMIT",
            "quantity": "0.01",
            "limit_price": "150",
            "rationale": "resting-order dogfood",
        },
    )
    assert submit.status_code == 200

    processed = client.post("/api/crypto/orders/process")
    assert processed.status_code == 200
    body = processed.json()
    assert len(body["filled"]) == 1
    assert body["open_orders_remaining"] == 0
    assert "price PATH is also checked" in body["note"]
    assert body["account"]["cash"] != "100000.00"

    actions = {action.action_id: action for action in ACTION_CONTRACTS}
    entry = actions["crypto_process_paper_orders"]
    assert entry.endpoint == "/api/crypto/orders/process"
    assert entry.local_mutation is True


# ---- candle-path fills (2026-07-22): the gap between runs is now simulated --


from datetime import UTC, datetime, timedelta  # noqa: E402


def _candle(low: str, high: str, close: str, *, offset_s: int = 60) -> dict:
    closed = (datetime.now(tz=UTC) + timedelta(seconds=offset_s)).isoformat(
        timespec="seconds"
    )
    return {
        "closed_at": closed,
        "low": low,
        "high": high,
        "close": close,
        "open": low,
        "closed": True,
    }


def test_path_touched_limit_fills_at_the_limit_price() -> None:
    cache = _fresh_cache()
    state, order = _order({}, cache, side="BUY", order_type="LIMIT", limit_price="95")
    # current price 100 never triggers; the candle range dipped to 94
    state, report = process_paper_orders(
        state, cache, candles_by_symbol={"BTCUSDT": [_candle("94", "101", "99")]}
    )
    assert [f["order_id"] for f in report["filled"]] == [order["order_id"]]
    assert report["filled"][0]["fill_price"] == "95.00"  # the limit, never better
    assert report["filled"][0]["fill_basis"] == "path_limit_price"
    assert "candle path" in report["filled"][0]["trigger"]


def test_path_triggered_stop_fills_at_candle_close_not_stop() -> None:
    cache = _fresh_cache()
    state, _ = _order({}, cache, side="BUY", order_type="MARKET", quantity="0.5")
    state, stop = _order(
        state, cache, side="SELL", order_type="STOP", quantity="0.5", stop_price="96"
    )
    state, report = process_paper_orders(
        state, cache, candles_by_symbol={"BTCUSDT": [_candle("95", "99", "95.50")]}
    )
    assert [f["order_id"] for f in report["filled"]] == [stop["order_id"]]
    assert report["filled"][0]["fill_price"] == "95.50"  # close, not the 96 stop
    assert report["filled"][0]["fill_basis"] == "path_candle_close"


def test_candles_before_order_creation_do_not_fill() -> None:
    cache = _fresh_cache()
    state, order = _order({}, cache, side="BUY", order_type="LIMIT", limit_price="95")
    stale_candle = _candle("90", "101", "99", offset_s=-3600)  # closed before order
    state, report = process_paper_orders(
        state, cache, candles_by_symbol={"BTCUSDT": [stale_candle]}
    )
    assert report["filled"] == []
    resting = next(o for o in state["orders"] if o["order_id"] == order["order_id"])
    assert resting["status"] == "WORKING"


def test_stop_limit_is_excluded_from_path_fills() -> None:
    cache = _fresh_cache()
    state, _ = _order(
        {}, cache, side="BUY", order_type="STOP_LIMIT", stop_price="150",
        limit_price="160",
    )
    state, report = process_paper_orders(
        state, cache, candles_by_symbol={"BTCUSDT": [_candle("94", "155", "154")]}
    )
    assert report["filled"] == []
    assert report["open_orders_remaining"] == 1
    assert "STOP_LIMIT stays trigger-at-processing only" in report["note"]
