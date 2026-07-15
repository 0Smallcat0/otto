from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore
from otto.local_terminal.stooq_data import (
    STOOQ_PROVIDER_ID,
    STOOQ_WATCHLIST,
    normalize_stooq_quote_snapshot,
    stooq_quote_snapshot_payload,
    stooq_symbol_list,
)


def _raw(symbol: str = "AAPL.US") -> dict[str, str]:
    return {
        "Symbol": symbol,
        "Date": "2026-05-22",
        "Time": "22:00:19",
        "Open": "306.12",
        "High": "311.40",
        "Low": "305.84",
        "Close": "308.82",
        "Volume": "43670223",
    }


def _fake_stooq_fetcher(*, symbol: str) -> dict[str, str]:
    assert symbol in set(STOOQ_WATCHLIST)
    return _raw(symbol=symbol)


def test_stooq_payload_uses_explicit_unavailable_state_without_fixture_runtime() -> None:
    payload = stooq_quote_snapshot_payload(
        {},
        refresh=False,
        fetcher=_fake_stooq_fetcher,
    )

    assert payload["status"]["state"] == "unavailable"
    assert payload["quotes"] == []
    assert payload["summary"]["provider_id"] == STOOQ_PROVIDER_ID
    assert payload["entry"]["auth_mode"] == "public-no-key"
    assert "offline_fixture" not in str(payload)


def test_stooq_symbol_list_is_bounded_and_normalized() -> None:
    assert stooq_symbol_list("aapl.us, SPY.US,^spx,EUR/USD,SPY.US, bad symbol!") == [
        "AAPL.US",
        "SPY.US",
        "^SPX",
        "EURUSD",
        "BADSYMBOL",
    ]
    assert stooq_symbol_list("") == list(STOOQ_WATCHLIST)


def test_stooq_normalizes_quote_snapshot_as_non_orderable() -> None:
    payload = normalize_stooq_quote_snapshot(_raw())

    assert payload["status"]["provider_id"] == STOOQ_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["price"] == "308.82"
    assert payload["quotes"][0]["quote_semantics"] == "quote_not_orderable"
    assert payload["quotes"][0]["live_action_enabled"] is False
    assert payload["quotes"][0]["orderable"] is False


def test_stooq_refresh_endpoint_writes_public_cache_and_markets_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "STOOQ_FETCHER", _fake_stooq_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post(
        "/api/stooq/quote-snapshots/refresh",
        json={"symbols": "AAPL.US,SPY.US,^SPX,EURUSD"},
    )
    markets = client.post("/api/markets/stooq/quotes/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["symbols"] == "AAPL.US,SPY.US,^SPX,EURUSD"
    assert refreshed.json()["summary"]["row_count"] == 4
    assert "cache" not in refreshed.json()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert (tmp_path / "market_data" / "quotes" / "stooq" / "AAPLUS.json").is_file()
    assert (tmp_path / "market_data" / "quotes" / "stooq" / "SPYUS.json").is_file()
    assert (tmp_path / "market_data" / "quotes" / "stooq" / "SPX.json").is_file()
    assert (tmp_path / "market_data" / "quotes" / "stooq" / "EURUSD.json").is_file()

    assert markets.json()["research_summary"]["stooq_quotes"]["row_count"] == 4
    assert any(
        provider["provider_id"] == STOOQ_PROVIDER_ID
        and provider["health"]["state"] == "active"
        and provider["health"]["cache_id"] == "stooq_quote_AAPLUS"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["stooq_quote_cache"].endswith("AAPLUS.json")


def test_stooq_market_refresh_without_cache_is_explicitly_not_refreshed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/stooq/quote-snapshots")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "unavailable"
    assert response.json()["quotes"] == []
    assert "offline_fixture" not in response.text
