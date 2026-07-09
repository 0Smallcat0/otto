from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.bea_data import (
    BEA_PROVIDER_ID,
    bea_regional_payload,
    normalize_bea_regional_data,
)
from src.local_terminal.markets import default_markets_layout, markets_payload
from src.local_terminal.research_data import research_data_payload
from src.local_terminal.storage import LocalStateStore


def _synthetic_bea_value() -> str:
    return "bea-" + "local-" + "adapter"


def _secret_status(stored: bool) -> dict[str, Any]:
    return {
        "stored_provider_ids": [BEA_PROVIDER_ID] if stored else [],
        "api_secret_value_reads_enabled": False,
    }


def _bea_raw() -> dict[str, Any]:
    return {
        "BEAAPI": {
            "Results": {
                "Data": [
                    {
                        "Code": "SAGDP9N-1",
                        "GeoFips": "00000",
                        "GeoName": "United States",
                        "TimePeriod": "2024",
                        "CL_UNIT": "Millions of chained 2017 dollars",
                        "UNIT_MULT": "6",
                        "DataValue": "23,304,712.4",
                    },
                    {
                        "Code": "SAGDP9N-1",
                        "GeoFips": "01000",
                        "GeoName": "Alabama",
                        "TimePeriod": "2024",
                        "CL_UNIT": "Millions of chained 2017 dollars",
                        "UNIT_MULT": "6",
                        "DataValue": "244,139.2",
                    },
                ]
            }
        }
    }


def _fake_bea_fetcher(*, credential: str) -> dict[str, Any]:
    assert credential == _synthetic_bea_value()
    return _bea_raw()


def test_bea_optional_provider_requires_local_key_without_fixture_runtime() -> None:
    payload = bea_regional_payload({}, _secret_status(False), refresh=True)

    assert payload["status"]["provider_id"] == BEA_PROVIDER_ID
    assert payload["status"]["state"] == "key_required"
    assert payload["series"] == []
    assert payload["cache"]["bea"] is None
    assert payload["summary"]["quote_semantics"] == "not_quote"
    payload_text = str(payload).lower()
    assert "offline_fixture" not in payload_text
    assert "mock" not in payload_text
    assert "api_key" not in payload_text


def test_bea_normalizes_regional_rows_as_non_quote_macro_context() -> None:
    payload = normalize_bea_regional_data(
        _bea_raw(),
        retrieved_at="2026-05-25T00:00:00Z",
    )

    assert payload["status"]["state"] == "live"
    assert payload["status"]["provider_id"] == BEA_PROVIDER_ID
    assert payload["summary"]["series_count"] == 2
    assert payload["summary"]["latest_value"] == "23304712.4"
    assert payload["summary"]["primary_geo"] == "United States"
    assert payload["series"][0]["provider_id"] == BEA_PROVIDER_ID
    assert payload["series"][0]["quote_semantics"] == "not_quote"
    assert payload["series"][0]["cache_path"] == (
        "market_data/regional/bea/SAGDP9N_LINE1_STATE.json"
    )
    assert payload["series"][1]["geo_name"] == "Alabama"
    assert _synthetic_bea_value() not in str(payload)


def test_bea_flows_into_research_and_markets_regional_context() -> None:
    bea = bea_regional_payload(
        {},
        _secret_status(True),
        refresh=True,
        credential=_synthetic_bea_value(),
        fetcher=_fake_bea_fetcher,
    )
    research = research_data_payload({}, {}, {}, {}, bea_payload=bea)
    markets = markets_payload(default_markets_layout(), {}, research_data=research)

    assert research["bea"]["summary"]["series_count"] == 2
    assert "cache" not in research["bea"]
    assert any(
        series["provider_id"] == BEA_PROVIDER_ID
        for series in research["macro"]["series"]
    )
    assert [row["provider_id"] for row in research["macro"]["provider_summaries"]] == [
        "dbnomics_public",
        "fred_optional_local_key",
        "bls_public_macro",
        "eurostat_hicp_public",
        BEA_PROVIDER_ID,
        "census_api_optional_key",
    ]
    assert markets["regional"]["summary"]["series_count"] == 2
    assert markets["regional"]["status"]["provider_id"] == BEA_PROVIDER_ID
    assert markets["regional"]["summary"]["primary_provider"] == BEA_PROVIDER_ID
    regional_row = next(
        row
        for row in markets["source_coverage_matrix"]
        if row["asset_family"] == "Regional" and row["runtime_role"] == "macro_context"
    )
    assert regional_row["provider_id"] == BEA_PROVIDER_ID
    assert regional_row["auth_mode"] == "optional_local_key"
    assert regional_row["safe_action_id"] == "markets_bea_refresh"
    assert regional_row["quote_semantics"] == "not_quote"
    assert "real_order" not in str(markets).lower()


def test_bea_refresh_endpoint_writes_cache_without_exposing_secret(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "_bea_secret_status_from_store", lambda: _secret_status(True))
    monkeypatch.setattr(
        server,
        "read_local_data_provider_secret",
        lambda *args, **kwargs: _synthetic_bea_value(),
    )
    monkeypatch.setattr(server, "BEA_FETCHER", _fake_bea_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/bea/regional/refresh")
    markets = client.post("/api/markets/bea/refresh")
    research = client.get("/api/research-data")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["primary_geo"] == "United States"
    assert markets.json()["regional"]["status"]["provider_id"] == BEA_PROVIDER_ID
    assert markets.json()["regional"]["summary"]["quote_state"] == "disabled_until_provider_gate"
    assert research.json()["bea"]["summary"]["series_count"] == 2
    assert any(
        provider["provider_id"] == BEA_PROVIDER_ID and provider["health"]["state"] == "active"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["bea_regional_cache"] == (
        "market_data/regional/bea/SAGDP9N_LINE1_STATE.json"
    )
    assert (tmp_path / "market_data" / "regional" / "bea" / "SAGDP9N_LINE1_STATE.json").is_file()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert _synthetic_bea_value() not in refreshed.text
    assert "protected_value" not in refreshed.text
    assert "api_key=" not in markets.text.lower()


def test_bea_endpoint_without_key_returns_key_required_and_no_secret_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    refreshed = client.post("/api/bea/regional/refresh")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "key_required"
    assert refreshed.json()["summary"]["series_count"] == 0
    assert not (tmp_path / "market_data" / "regional" / "bea").exists()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
