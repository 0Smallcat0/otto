from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore
from otto.local_terminal.twse_data import (
    TWSE_PROVIDER_ID,
    TWSE_WATCHLIST,
    normalize_twse_quote_snapshot,
    twse_quote_snapshot_payload,
    twse_symbol_list,
)


def _raw() -> list[dict[str, str]]:
    return [
        {
            "Date": "20260526",
            "Code": "2330",
            "Name": "TSMC",
            "TradeVolume": "25,713,389",
            "TradeValue": "22,181,949,200",
            "OpeningPrice": "860.00",
            "HighestPrice": "870.00",
            "LowestPrice": "855.00",
            "ClosingPrice": "865.00",
            "Change": "+5.00",
            "Transaction": "33,112",
        },
        {
            "Date": "20260526",
            "Code": "2317",
            "Name": "Hon Hai",
            "TradeVolume": "51,230,000",
            "TradeValue": "8,742,000,000",
            "OpeningPrice": "169.50",
            "HighestPrice": "172.00",
            "LowestPrice": "168.00",
            "ClosingPrice": "171.00",
            "Change": "+1.50",
            "Transaction": "22,100",
        },
        {
            "Date": "20260526",
            "Code": "0050",
            "Name": "Yuanta Taiwan 50",
            "TradeVolume": "9,820,000",
            "TradeValue": "1,852,300,000",
            "OpeningPrice": "188.20",
            "HighestPrice": "189.10",
            "LowestPrice": "187.80",
            "ClosingPrice": "188.90",
            "Change": "+0.70",
            "Transaction": "8,700",
        },
    ]


def _fake_twse_fetcher() -> list[dict[str, str]]:
    return _raw()


def test_twse_payload_uses_explicit_unavailable_state_without_fixture_runtime() -> None:
    payload = twse_quote_snapshot_payload(
        {},
        refresh=False,
        fetcher=_fake_twse_fetcher,
    )

    assert payload["status"]["state"] == "unavailable"
    assert payload["quotes"] == []
    assert payload["summary"]["provider_id"] == TWSE_PROVIDER_ID
    assert payload["entry"]["auth_mode"] == "public-no-key"
    assert "offline_fixture" not in str(payload)


def test_twse_symbol_list_is_bounded_and_normalized() -> None:
    assert twse_symbol_list("2330, 2317,0050,2330, bad symbol!, 006208") == [
        "2330",
        "2317",
        "0050",
        "BADSYMBOL",
        "006208",
    ]
    assert twse_symbol_list("") == list(TWSE_WATCHLIST)


def test_twse_normalizes_daily_quote_snapshot_as_non_orderable() -> None:
    payload = normalize_twse_quote_snapshot(_raw())

    assert payload["status"]["provider_id"] == TWSE_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["price"] == "865.00"
    assert payload["summary"]["latest_date"] == "20260526"
    assert payload["quotes"][0]["quote_semantics"] == "quote_not_orderable"
    assert payload["quotes"][0]["live_action_enabled"] is False
    assert payload["quotes"][0]["orderable"] is False
    assert payload["quotes"][0]["currency"] == "TWD"


def test_twse_refresh_endpoint_writes_public_cache_and_markets_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "TWSE_FETCHER", _fake_twse_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post(
        "/api/twse/quote-snapshots/refresh",
        json={"symbols": "2330,2317,0050"},
    )
    markets = client.post("/api/markets/twse/quotes/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["symbols"] == "2330,2317,0050"
    assert refreshed.json()["summary"]["row_count"] == 3
    assert "cache" not in refreshed.json()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert (tmp_path / "market_data" / "quotes" / "twse" / "2330.json").is_file()
    assert (tmp_path / "market_data" / "quotes" / "twse" / "2317.json").is_file()
    assert (tmp_path / "market_data" / "quotes" / "twse" / "0050.json").is_file()

    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == TWSE_PROVIDER_ID
    )
    assert source_row["state"] == "live"
    assert source_row["auth_mode"] == "public_no_key"
    assert source_row["runtime_role"] == "twse_daily_quote_snapshot"
    assert source_row["quote_semantics"] == "quote_not_orderable"
    assert source_row["safe_action_id"] == "markets_twse_quote_snapshot_refresh"
    assert source_row["live_action_enabled"] is False
    assert markets.json()["research_summary"]["twse_quotes"]["row_count"] == 3
    assert any(
        provider["provider_id"] == TWSE_PROVIDER_ID
        and provider["health"]["state"] == "active"
        and provider["health"]["cache_id"] == "twse_quote_2330"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["twse_quote_cache"].endswith("2330.json")


def test_twse_market_refresh_without_cache_is_explicitly_not_refreshed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/twse/quote-snapshots")
    markets = client.get("/api/markets")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "unavailable"
    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == TWSE_PROVIDER_ID
    )
    assert source_row["gated_reason"] == "refresh_not_run"
    assert source_row["next_safe_action"] == (
        "Run markets_twse_quote_snapshot_refresh to populate the public no-key cache."
    )
    assert "offline_fixture" not in response.text
