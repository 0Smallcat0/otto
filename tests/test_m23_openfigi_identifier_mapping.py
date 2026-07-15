from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.openfigi_data import (
    OPENFIGI_PROVIDER_ID,
    normalize_openfigi_mapping,
    openfigi_mapping_payload,
    openfigi_symbol_list,
)
from otto.local_terminal.storage import LocalStateStore


def _raw_mapping() -> list[dict[str, object]]:
    return [
        {
            "data": [
                {
                    "figi": "BBG000B9XRY4",
                    "name": "APPLE INC",
                    "ticker": "AAPL",
                    "exchCode": "US",
                    "compositeFIGI": "BBG000B9XRY4",
                    "shareClassFIGI": "BBG001S5N8V8",
                    "securityType": "Common Stock",
                    "marketSector": "Equity",
                    "securityType2": "Common Stock",
                    "securityDescription": "AAPL",
                }
            ]
        },
        {
            "data": [
                {
                    "figi": "BBG000BPH459",
                    "name": "MICROSOFT CORP",
                    "ticker": "MSFT",
                    "exchCode": "US",
                    "compositeFIGI": "BBG000BPH459",
                    "shareClassFIGI": "BBG001S5TD05",
                    "securityType": "Common Stock",
                    "marketSector": "Equity",
                    "securityType2": "Common Stock",
                    "securityDescription": "MSFT",
                }
            ]
        },
        {"warning": "No identifier found."},
    ]


def _fake_openfigi_fetcher(jobs: list[dict[str, object]]) -> list[dict[str, object]]:
    assert jobs[0]["idType"] == "TICKER"
    assert jobs[0]["exchCode"] == "US"
    return _raw_mapping()


def test_openfigi_payload_uses_explicit_unavailable_state_without_fixture_runtime() -> None:
    payload = openfigi_mapping_payload(
        {},
        refresh=False,
        fetcher=_fake_openfigi_fetcher,
    )

    assert payload["status"]["state"] == "unavailable"
    assert payload["mappings"] == []
    assert payload["summary"]["provider_id"] == OPENFIGI_PROVIDER_ID
    assert payload["entry"]["auth_mode"] == "public-no-key"
    assert "offline_fixture" not in str(payload)


def test_openfigi_normalizes_identifier_mapping_as_not_quote() -> None:
    payload = normalize_openfigi_mapping(
        _raw_mapping(),
        requested_symbols=["AAPL", "MSFT", "SPY"],
        retrieved_at="2026-05-27T00:00:00Z",
    )

    assert payload["status"]["provider_id"] == OPENFIGI_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["row_count"] == 2
    assert payload["summary"]["matched_symbol_count"] == 2
    assert payload["summary"]["unmatched_count"] == 1
    assert payload["summary"]["quote_semantics"] == "not_quote"
    assert payload["mappings"][0]["request_symbol"] == "AAPL"
    assert payload["mappings"][0]["figi"] == "BBG000B9XRY4"
    assert payload["mappings"][0]["quote_semantics"] == "not_quote"
    assert payload["mappings"][0]["live_action_enabled"] is False
    assert payload["mappings"][0]["orderable"] is False


def test_openfigi_symbols_are_bounded_and_normalized() -> None:
    assert openfigi_symbol_list("aapl, msft, spy, aapl, bad symbol!, nvda") == [
        "AAPL",
        "MSFT",
        "SPY",
        "BADSYMBOL",
        "NVDA",
    ]


def test_openfigi_refresh_failure_preserves_requested_symbols_without_cache() -> None:
    def failing_fetcher(jobs: list[dict[str, object]]) -> list[dict[str, object]]:
        assert jobs[0]["idValue"] == "TSLA"
        raise OSError("rate limited")

    payload = openfigi_mapping_payload(
        {},
        refresh=True,
        symbols="TSLA",
        fetcher=failing_fetcher,
    )

    assert payload["status"]["state"] == "unavailable"
    assert payload["summary"]["requested_symbols"] == "TSLA"
    assert payload["summary"]["row_count"] == 0
    assert payload["mappings"] == []


def test_openfigi_refresh_endpoint_writes_reference_cache_and_markets_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "OPENFIGI_FETCHER", _fake_openfigi_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post(
        "/api/openfigi/mapping/refresh",
        json={"symbols": "AAPL,MSFT,SPY"},
    )
    markets = client.post("/api/markets/openfigi/mapping/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["row_count"] == 2
    assert refreshed.json()["mappings"][0]["figi"] == "BBG000B9XRY4"
    assert "cache" not in refreshed.json()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert (tmp_path / "market_data" / "reference" / "openfigi" / "mapping.json").is_file()

    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == OPENFIGI_PROVIDER_ID
    )
    assert source_row["state"] == "live"
    assert source_row["auth_mode"] == "public_no_key"
    assert source_row["runtime_role"] == "identifier_mapping"
    assert source_row["quote_semantics"] == "not_quote"
    assert source_row["safe_action_id"] == "markets_openfigi_mapping_refresh"
    assert source_row["context_only"] is True
    assert source_row["live_action_enabled"] is False
    assert markets.json()["research_summary"]["openfigi_mapping"]["row_count"] == 2
    assert markets.json()["stocks"]["identifier_mapping_status"]["provider_id"] == (
        OPENFIGI_PROVIDER_ID
    )
    assert markets.json()["stocks"]["summary"]["identifier_mapping_row_count"] == 2
    assert markets.json()["stocks"]["summary"]["identifier_mapping_quote_semantics"] == (
        "not_quote"
    )
    assert markets.json()["stocks"]["identifier_mappings"][0]["orderable"] is False
    assert any(
        provider["provider_id"] == OPENFIGI_PROVIDER_ID
        and provider["health"]["state"] == "active"
        and provider["health"]["cache_id"] == "openfigi_identifier_mapping"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["openfigi_mapping_cache"].endswith(
        "market_data/reference/openfigi/mapping.json"
    )


def test_openfigi_market_refresh_without_cache_is_explicitly_not_refreshed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/openfigi/mapping")
    markets = client.get("/api/markets")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "unavailable"
    assert response.json()["mappings"] == []
    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == OPENFIGI_PROVIDER_ID
    )
    assert source_row["gated_reason"] == "refresh_not_run"
    assert source_row["next_safe_action"] == (
        "Run markets_openfigi_mapping_refresh to populate the public no-key cache."
    )
    assert "offline_fixture" not in response.text
