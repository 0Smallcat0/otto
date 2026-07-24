"""M28 — Yahoo Finance public no-key quote snapshot provider (replaces dead Stooq lane)."""

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore
from otto.local_terminal.yahoo_data import (
    YAHOO_PROVIDER_ID,
    YAHOO_WATCHLIST,
    normalize_yahoo_quote_snapshot,
    yahoo_quote_snapshot_payload,
    yahoo_symbol_list,
)


def _meta(symbol: str = "AAPL") -> dict[str, object]:
    return {
        "symbol": symbol,
        "currency": "USD",
        "exchangeName": "NMS",
        "fullExchangeName": "NasdaqGS",
        "regularMarketPrice": 310.66,
        "chartPreviousClose": 312.66,
        "regularMarketDayHigh": 315.48,
        "regularMarketDayLow": 310.15,
        "regularMarketVolume": 43670223,
        "regularMarketTime": 1783000000,
    }


def _fake_yahoo_fetcher(*, symbol: str) -> dict[str, object]:
    assert symbol in set(YAHOO_WATCHLIST)
    return _meta(symbol)


def test_yahoo_payload_is_explicitly_unavailable_without_cache_or_refresh() -> None:
    payload = yahoo_quote_snapshot_payload({}, refresh=False, fetcher=_fake_yahoo_fetcher)

    assert payload["status"]["state"] == "unavailable"
    assert payload["quotes"] == []
    assert payload["summary"]["provider_id"] == YAHOO_PROVIDER_ID
    assert payload["entry"]["auth_mode"] == "public-no-key"
    assert "offline_fixture" not in str(payload)


def test_yahoo_symbol_list_is_bounded_and_normalized() -> None:
    assert yahoo_symbol_list("aapl, MSFT,^gspc, aapl, bad symbol!") == [
        "AAPL",
        "MSFT",
        "^GSPC",
        "BADSYMBOL",
    ]
    assert yahoo_symbol_list("") == list(YAHOO_WATCHLIST)


def test_yahoo_normalizes_quote_snapshot_as_non_orderable() -> None:
    payload = normalize_yahoo_quote_snapshot(_meta())

    assert payload["status"]["provider_id"] == YAHOO_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["price"] == "310.66"
    row = payload["quotes"][0]
    assert row["change"] == "-2"
    assert row["previous_close"] == "312.66"
    assert row["currency"] == "USD"
    assert row["quote_semantics"] == "quote_not_orderable"
    assert row["live_action_enabled"] is False
    assert row["orderable"] is False


def test_yahoo_refresh_endpoint_writes_public_cache(tmp_path, monkeypatch) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "YAHOO_FETCHER", _fake_yahoo_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post(
        "/api/markets/yahoo/quotes/refresh",
        json={"symbols": "AAPL,MSFT,NVDA,SPY"},
    )
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["status"]["state"] == "live"
    assert body["summary"]["symbols"] == "AAPL,MSFT,NVDA,SPY"
    assert body["summary"]["row_count"] == 4
    assert "cache" not in body  # public payload strips the writable cache block
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert (tmp_path / "market_data" / "quotes" / "yahoo" / "AAPL.json").is_file()
    assert (tmp_path / "market_data" / "quotes" / "yahoo" / "SPY.json").is_file()
    assert local_state.json()["storage"]["yahoo_quote_cache"].endswith("AAPL.json")


def test_yahoo_get_without_cache_is_explicitly_unavailable(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/markets/yahoo/quotes")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "unavailable"
    assert response.json()["quotes"] == []
    assert "offline_fixture" not in response.text


def test_yahoo_action_registered_in_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    contract = client.get("/api/agent-contract").json()
    actions = {action["action_id"]: action for action in contract["actions"]}

    assert "markets_yahoo_quote_snapshot_refresh" in actions
    assert actions["markets_yahoo_quote_snapshot_refresh"]["method"] == "POST"
    assert (
        actions["markets_yahoo_quote_snapshot_refresh"]["safety_class"]
        == "public_read_only_market_data"
    )


# ---- transient-retry at order-submit time (2026-07-24 loop drill) ----


def test_fetch_retries_once_on_transient_network_blip(monkeypatch) -> None:
    import io
    import json as _json
    from urllib.error import URLError

    from otto.local_terminal import yahoo_data

    calls = {"n": 0}
    good = {"chart": {"error": None, "result": [{"meta": _meta("AAPL")}]}}

    def _flaky_urlopen(request, timeout=6.0):
        calls["n"] += 1
        if calls["n"] == 1:
            raise URLError("connection reset")
        return io.BytesIO(_json.dumps(good).encode("utf-8"))

    monkeypatch.setattr(yahoo_data, "urlopen", _flaky_urlopen)
    meta = yahoo_data.fetch_yahoo_quote_snapshot(symbol="AAPL")
    assert meta["symbol"] == "AAPL"
    assert calls["n"] == 2  # first attempt failed, retry succeeded


def test_fetch_raises_after_two_transient_failures(monkeypatch) -> None:
    from urllib.error import URLError

    from otto.local_terminal import yahoo_data

    calls = {"n": 0}

    def _always_fail(request, timeout=6.0):
        calls["n"] += 1
        raise URLError("down")

    monkeypatch.setattr(yahoo_data, "urlopen", _always_fail)
    try:
        yahoo_data.fetch_yahoo_quote_snapshot(symbol="AAPL")
    except URLError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected URLError after two failures")
    assert calls["n"] == 2  # exactly one retry, then give up
