import json
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore
from otto.local_terminal.twelve_data import (
    TWELVE_DATA_PROVIDER_ID,
    TWELVE_DATA_WATCHLIST,
    normalize_twelve_data_quote,
    twelve_data_quote_watchlist_payload,
    twelve_data_symbol_list,
)


def _synthetic_twelve_value() -> str:
    return "twelve-" + "local-" + "adapter"


def _secret_status(*, stored: bool) -> dict[str, object]:
    return {
        "status": "available" if stored else "ready",
        "stored_provider_ids": [TWELVE_DATA_PROVIDER_ID] if stored else [],
    }


def _quote_raw(symbol: str = "AAPL") -> dict[str, object]:
    return {
        "symbol": symbol,
        "name": f"{symbol} instrument",
        "exchange": "NASDAQ" if "/" not in symbol else "FOREX",
        "mic_code": "XNAS" if "/" not in symbol else "",
        "currency": "USD",
        "datetime": "2026-05-25",
        "timestamp": 1779667200,
        "last_quote_at": 1779667200,
        "open": "120.00",
        "high": "125.00",
        "low": "119.50",
        "close": "123.45",
        "volume": "1000",
        "previous_close": "122.00",
        "change": "1.45",
        "percent_change": "1.1885",
        "is_market_open": False,
        "type": "ETF" if symbol == "SPY" else "Common Stock",
    }


def _fake_twelve_fetcher(*, symbol: str, credential: str) -> dict[str, object]:
    assert symbol in set(TWELVE_DATA_WATCHLIST)
    assert credential == _synthetic_twelve_value()
    return _quote_raw(symbol=symbol)


def test_twelve_data_payload_requires_local_key_without_fixture_runtime() -> None:
    payload = twelve_data_quote_watchlist_payload(
        {},
        _secret_status(stored=False),
        refresh=True,
        fetcher=_fake_twelve_fetcher,
    )

    assert payload["status"]["state"] == "key_required"
    assert payload["quotes"] == []
    assert payload["cache"]["twelve_data"] is None
    assert payload["summary"]["provider_id"] == TWELVE_DATA_PROVIDER_ID
    assert "offline_fixture" not in str(payload)


def test_twelve_data_symbol_list_uses_bounded_normalized_symbols() -> None:
    assert twelve_data_symbol_list("aapl, SPY,EUR/USD,SPY,INVALID SYMBOL") == [
        "AAPL",
        "SPY",
        "EUR/USD",
        "INVALIDSYMBOL",
    ]
    assert twelve_data_symbol_list("") == list(TWELVE_DATA_WATCHLIST)


def test_twelve_data_normalizes_quote_without_key_material() -> None:
    payload = normalize_twelve_data_quote(
        _quote_raw(),
        retrieved_at="2026-05-25T00:00:00Z",
    )

    assert payload["status"]["provider_id"] == TWELVE_DATA_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["price"] == "123.45"
    assert payload["quotes"][0]["quote_semantics"] == "quote_not_orderable"
    assert payload["quotes"][0]["live_action_enabled"] is False
    assert _synthetic_twelve_value() not in json.dumps(payload)


def test_twelve_data_refresh_endpoint_uses_internal_secret_reader_and_writes_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(
        server,
        "_twelve_data_secret_status_from_store",
        lambda: _secret_status(stored=True),
    )
    monkeypatch.setattr(server, "read_local_data_provider_secret", lambda *_, **__: _synthetic_twelve_value())
    monkeypatch.setattr(server, "TWELVE_DATA_FETCHER", _fake_twelve_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post(
        "/api/twelve-data/quotes/refresh",
        json={"symbols": "AAPL,SPY,EUR/USD,SPY"},
    )
    markets = client.post("/api/markets/twelve-data/quotes/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["symbols"] == "AAPL,SPY,EUR/USD"
    assert refreshed.json()["summary"]["row_count"] == 3
    assert "cache" not in refreshed.json()
    assert _synthetic_twelve_value() not in refreshed.text
    assert "api_key=" not in refreshed.text.lower()
    assert (tmp_path / "market_data" / "quotes" / "twelve_data" / "AAPL.json").is_file()
    assert (tmp_path / "market_data" / "quotes" / "twelve_data" / "SPY.json").is_file()
    assert (tmp_path / "market_data" / "quotes" / "twelve_data" / "EURUSD.json").is_file()
    assert _synthetic_twelve_value() not in (
        tmp_path / "market_data" / "quotes" / "twelve_data" / "AAPL.json"
    ).read_text(encoding="utf-8")

    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == TWELVE_DATA_PROVIDER_ID
    )
    assert source_row["state"] == "live"
    assert source_row["runtime_role"] == "quote_watchlist_secondary"
    assert source_row["quote_semantics"] == "quote_not_orderable"
    assert source_row["safe_action_id"] == "markets_twelve_data_quote_watchlist_refresh"
    # M27-R2: an empty markets-route refresh follows the user fx watchlist
    # (default EUR/USD) instead of the old hardcoded three-symbol list.
    assert markets.json()["research_summary"]["twelve_data_quotes"]["row_count"] == 1
    assert any(
        provider["provider_id"] == TWELVE_DATA_PROVIDER_ID
        and provider["health"]["state"] == "active"
        and provider["health"]["cache_id"] == "twelve_data_quote_AAPL"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["twelve_data_quote_cache"].endswith("AAPL.json")
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_twelve_data_refresh_without_key_is_explicitly_gated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post("/api/twelve-data/quotes/refresh")
    markets = client.post("/api/markets/twelve-data/quotes/refresh")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "key_required"
    assert response.json()["quotes"] == []
    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == TWELVE_DATA_PROVIDER_ID
    )
    assert source_row["state"] == "key_required"
    assert source_row["gated_reason"] == "local_secret_required"
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert "offline_fixture" not in response.text
