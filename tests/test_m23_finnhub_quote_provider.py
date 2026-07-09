import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.finnhub_data import (
    FINNHUB_PROVIDER_ID,
    FINNHUB_WATCHLIST,
    finnhub_quote_watchlist_payload,
    finnhub_symbol_list,
    normalize_finnhub_quote,
)
from src.local_terminal.storage import LocalStateStore


def _synthetic_finnhub_value() -> str:
    return "finnhub-" + "local-" + "adapter"


def _secret_status(*, stored: bool) -> dict[str, object]:
    return {
        "status": "available" if stored else "ready",
        "stored_provider_ids": [FINNHUB_PROVIDER_ID] if stored else [],
    }


def _quote_raw() -> dict[str, object]:
    return {
        "c": 192.25,
        "d": 1.25,
        "dp": 0.654,
        "h": 193.0,
        "l": 190.5,
        "o": 191.0,
        "pc": 191.0,
        "t": 1779667200,
    }


def _fake_finnhub_fetcher(*, symbol: str, credential: str) -> dict[str, object]:
    assert symbol in set(FINNHUB_WATCHLIST)
    assert credential == _synthetic_finnhub_value()
    return _quote_raw()


def test_finnhub_payload_requires_local_key_without_fixture_runtime() -> None:
    payload = finnhub_quote_watchlist_payload(
        {},
        _secret_status(stored=False),
        refresh=True,
        fetcher=_fake_finnhub_fetcher,
    )

    assert payload["status"]["state"] == "key_required"
    assert payload["quotes"] == []
    assert payload["cache"]["finnhub"] is None
    assert payload["summary"]["provider_id"] == FINNHUB_PROVIDER_ID
    assert "offline_fixture" not in str(payload)


def test_finnhub_symbol_list_uses_bounded_normalized_symbols() -> None:
    assert finnhub_symbol_list("aapl, MSFT,NVDA,SPY,AAPL, bad symbol!") == [
        "AAPL",
        "MSFT",
        "NVDA",
        "SPY",
        "BADSYMBOL",
    ]
    assert finnhub_symbol_list("") == list(FINNHUB_WATCHLIST)


def test_finnhub_normalizes_quote_without_key_material() -> None:
    payload = normalize_finnhub_quote(
        _quote_raw(),
        symbol="AAPL",
        retrieved_at="2026-05-26T00:00:00Z",
    )

    assert payload["status"]["provider_id"] == FINNHUB_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["price"] == "192.25"
    assert payload["quotes"][0]["quote_semantics"] == "quote_not_orderable"
    assert payload["quotes"][0]["live_action_enabled"] is False
    assert _synthetic_finnhub_value() not in json.dumps(payload)


def test_finnhub_refresh_endpoint_uses_internal_secret_reader_and_writes_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(
        server,
        "_finnhub_secret_status_from_store",
        lambda: _secret_status(stored=True),
    )
    monkeypatch.setattr(server, "read_local_data_provider_secret", lambda *_, **__: _synthetic_finnhub_value())
    monkeypatch.setattr(server, "FINNHUB_FETCHER", _fake_finnhub_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post(
        "/api/finnhub/quotes/refresh",
        json={"symbols": "AAPL,MSFT,NVDA,SPY"},
    )
    markets = client.post("/api/markets/finnhub/quotes/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["symbols"] == "AAPL,MSFT,NVDA,SPY"
    assert refreshed.json()["summary"]["row_count"] == 4
    assert "cache" not in refreshed.json()
    assert _synthetic_finnhub_value() not in refreshed.text
    assert "token=" not in refreshed.text.lower()
    for symbol in FINNHUB_WATCHLIST:
        cache_path = tmp_path / "market_data" / "quotes" / "finnhub" / f"{symbol}.json"
        assert cache_path.is_file()
        assert _synthetic_finnhub_value() not in cache_path.read_text(encoding="utf-8")

    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == FINNHUB_PROVIDER_ID
    )
    assert source_row["state"] == "live"
    assert source_row["runtime_role"] == "equity_quote_watchlist_secondary"
    assert source_row["quote_semantics"] == "quote_not_orderable"
    assert source_row["safe_action_id"] == "markets_finnhub_quote_watchlist_refresh"
    assert source_row["live_action_enabled"] is False
    assert markets.json()["research_summary"]["finnhub_quotes"]["row_count"] == 4
    assert any(
        provider["provider_id"] == FINNHUB_PROVIDER_ID
        and provider["health"]["state"] == "active"
        and provider["health"]["cache_id"] == "finnhub_quote_AAPL"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["finnhub_quote_cache"].endswith("AAPL.json")
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_finnhub_refresh_without_key_is_explicitly_gated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post("/api/finnhub/quotes/refresh")
    markets = client.post("/api/markets/finnhub/quotes/refresh")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "key_required"
    assert response.json()["quotes"] == []
    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == FINNHUB_PROVIDER_ID
    )
    assert source_row["state"] == "key_required"
    assert source_row["gated_reason"] == "local_secret_required"
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert "offline_fixture" not in response.text
