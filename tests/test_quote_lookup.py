"""Any-symbol quote lookup — the "quote exactly what I asked for" entry point.

The Yahoo refresh action always accepted arbitrary symbols, but its name and
map entry read as "update the stored watchlist caches", so an agent had no
discoverable way to answer "what is TSLA at right now?". The lookup endpoint
is that semantic entry: explicit symbols only, no watchlist fallback (an
all-invalid request is refused, never silently answered with defaults), and
a flat response an agent can read without spelunking.
"""

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore
from otto.local_terminal.yahoo_data import YAHOO_WATCHLIST, yahoo_lookup_symbols


def _meta(symbol: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "currency": "USD",
        "exchangeName": "NMS",
        "fullExchangeName": "NasdaqGS",
        "regularMarketPrice": 394.46,
        "chartPreviousClose": 396.18,
        "regularMarketDayHigh": 406.59,
        "regularMarketDayLow": 390.66,
        "regularMarketVolume": 31393664,
        "regularMarketTime": 1783000000,
    }


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    monkeypatch.setattr(server, "YAHOO_FETCHER", lambda *, symbol: _meta(symbol))
    return TestClient(server.create_app())


def test_lookup_symbols_have_no_watchlist_fallback() -> None:
    assert yahoo_lookup_symbols(["tsla", "2330.tw", "tsla"]) == ["TSLA", "2330.TW"]
    assert yahoo_lookup_symbols([]) == []
    assert yahoo_lookup_symbols(["!!!", "   "]) == []
    assert yahoo_lookup_symbols(None) == []


def test_lookup_returns_live_quotes_for_arbitrary_symbols(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        "/api/markets/quotes/lookup", json={"symbols": ["TSLA", "2330.TW"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requested_symbols"] == ["TSLA", "2330.TW"]
    assert body["status"]["state"] == "live"
    symbols = [row["symbol"] for row in body["quotes"]]
    assert symbols == ["TSLA", "2330.TW"]
    row = body["quotes"][0]
    assert row["price"] == "394.46"
    assert row["currency"] == "USD"
    assert "change_percent" in row
    # lookup responses stay flat: no giant markets payload around them
    assert "research_summary" not in body


def test_lookup_refuses_all_invalid_and_empty_requests(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    all_invalid = client.post("/api/markets/quotes/lookup", json={"symbols": ["!!!"]})
    assert all_invalid.status_code == 400
    assert "No valid symbols" in all_invalid.json()["detail"]

    empty = client.post("/api/markets/quotes/lookup", json={"symbols": []})
    assert empty.status_code == 422  # pydantic min_length

    too_many = client.post(
        "/api/markets/quotes/lookup",
        json={"symbols": [f"SYM{i}" for i in range(9)]},
    )
    assert too_many.status_code == 422  # pydantic max_length

    extra_field = client.post(
        "/api/markets/quotes/lookup", json={"symbols": ["TSLA"], "refresh": True}
    )
    assert extra_field.status_code == 422  # extra="forbid"


def test_lookup_never_answers_with_the_default_watchlist(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post("/api/markets/quotes/lookup", json={"symbols": ["TSLA"]})
    body = response.json()
    returned = {row["symbol"] for row in body["quotes"]}
    assert returned == {"TSLA"}
    assert not returned & (set(YAHOO_WATCHLIST) - {"TSLA"})


def test_lookup_action_registered_in_agent_contract(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    contract = client.get("/api/agent-contract").json()
    actions = {action["action_id"]: action for action in contract["actions"]}
    entry = actions["markets_quote_lookup"]
    assert entry["method"] == "POST"
    assert entry["endpoint"] == "/api/markets/quotes/lookup"
    assert entry["safety_class"] == "public_read_only_market_data"
    assert entry["requires_confirmation"] is False
    assert "ANY Yahoo Finance symbol" in entry["request_contract"]

    markets_route = next(r for r in contract["routes"] if r["route_id"] == "markets")
    assert "markets_quote_lookup" in markets_route["recommended_actions"]
