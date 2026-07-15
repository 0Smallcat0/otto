import json
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.fmp_data import (
    FMP_PROVIDER_ID,
    FMP_WATCHLIST,
    fmp_quote_watchlist_payload,
    fmp_symbol_list,
    normalize_fmp_quote,
)
from otto.local_terminal.storage import LocalStateStore


def _synthetic_fmp_value() -> str:
    return "fmp-" + "local-" + "adapter"


def _secret_status(*, stored: bool) -> dict[str, object]:
    return {
        "status": "available" if stored else "ready",
        "stored_provider_ids": [FMP_PROVIDER_ID] if stored else [],
    }


def _quote_raw(symbol: str = "AAPL") -> list[dict[str, object]]:
    return [
        {
            "symbol": symbol,
            "name": f"{symbol} Inc.",
            "price": 192.25,
            "change": 1.25,
            "changesPercentage": 0.654,
            "dayHigh": 193.0,
            "dayLow": 190.5,
            "open": 191.0,
            "previousClose": 191.0,
            "volume": 1234567,
            "exchange": "NASDAQ",
            "timestamp": 1779667200,
        }
    ]


def _fake_fmp_fetcher(*, symbol: str, credential: str) -> list[dict[str, object]]:
    assert symbol in set(FMP_WATCHLIST)
    assert credential == _synthetic_fmp_value()
    return _quote_raw(symbol)


def test_fmp_payload_requires_local_key_without_fixture_runtime() -> None:
    payload = fmp_quote_watchlist_payload(
        {},
        _secret_status(stored=False),
        refresh=True,
        fetcher=_fake_fmp_fetcher,
    )

    assert payload["status"]["state"] == "key_required"
    assert payload["quotes"] == []
    assert payload["cache"]["fmp"] is None
    assert payload["summary"]["provider_id"] == FMP_PROVIDER_ID
    assert "offline_fixture" not in str(payload)


def test_fmp_symbol_list_uses_bounded_normalized_symbols() -> None:
    assert fmp_symbol_list("aapl, MSFT,NVDA,SPY,AAPL, bad symbol!") == [
        "AAPL",
        "MSFT",
        "NVDA",
        "SPY",
        "BADSYMBOL",
    ]
    assert fmp_symbol_list("") == list(FMP_WATCHLIST)


def test_fmp_normalizes_quote_without_key_material() -> None:
    payload = normalize_fmp_quote(
        _quote_raw(),
        symbol="AAPL",
        retrieved_at="2026-05-26T00:00:00Z",
    )

    assert payload["status"]["provider_id"] == FMP_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["price"] == "192.25"
    assert payload["quotes"][0]["quote_semantics"] == "quote_not_orderable"
    assert payload["quotes"][0]["live_action_enabled"] is False
    assert _synthetic_fmp_value() not in json.dumps(payload)


def test_fmp_refresh_endpoint_uses_internal_secret_reader_and_writes_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "_fmp_secret_status_from_store", lambda: _secret_status(stored=True))
    monkeypatch.setattr(server, "read_local_data_provider_secret", lambda *_, **__: _synthetic_fmp_value())
    monkeypatch.setattr(server, "FMP_FETCHER", _fake_fmp_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/fmp/quotes/refresh", json={"symbols": "AAPL,MSFT,NVDA,SPY"})
    markets = client.post("/api/markets/fmp/quotes/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["symbols"] == "AAPL,MSFT,NVDA,SPY"
    assert refreshed.json()["summary"]["row_count"] == 4
    assert "cache" not in refreshed.json()
    assert _synthetic_fmp_value() not in refreshed.text
    assert "apikey=" not in refreshed.text.lower()
    for symbol in FMP_WATCHLIST:
        cache_path = tmp_path / "market_data" / "quotes" / "fmp" / f"{symbol}.json"
        assert cache_path.is_file()
        assert _synthetic_fmp_value() not in cache_path.read_text(encoding="utf-8")

    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == FMP_PROVIDER_ID
    )
    assert source_row["state"] == "live"
    assert source_row["runtime_role"] == "stock_quote_watchlist_tertiary"
    assert source_row["quote_semantics"] == "quote_not_orderable"
    assert source_row["safe_action_id"] == "markets_fmp_quote_watchlist_refresh"
    assert source_row["live_action_enabled"] is False
    assert markets.json()["research_summary"]["fmp_quotes"]["row_count"] == 4
    assert any(
        provider["provider_id"] == FMP_PROVIDER_ID
        and provider["health"]["state"] == "active"
        and provider["health"]["cache_id"] == "fmp_quote_AAPL"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["fmp_quote_cache"].endswith("AAPL.json")
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_fmp_refresh_without_key_is_explicitly_gated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post("/api/fmp/quotes/refresh")
    markets = client.post("/api/markets/fmp/quotes/refresh")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "key_required"
    assert response.json()["quotes"] == []
    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == FMP_PROVIDER_ID
    )
    assert source_row["state"] == "key_required"
    assert source_row["gated_reason"] == "local_secret_required"
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert "offline_fixture" not in response.text
