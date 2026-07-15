from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.census_data import (
    CENSUS_PROVIDER_ID,
    census_acs_profile_payload,
    normalize_census_acs_profile_data,
)
from otto.local_terminal.markets import default_markets_layout, markets_payload
from otto.local_terminal.research_data import research_data_payload
from otto.local_terminal.storage import LocalStateStore


def _synthetic_census_value() -> str:
    return "census-" + "local-" + "adapter"


def _secret_status(stored: bool) -> dict[str, Any]:
    return {
        "stored_provider_ids": [CENSUS_PROVIDER_ID] if stored else [],
        "api_secret_value_reads_enabled": False,
    }


def _census_raw() -> list[list[str]]:
    return [
        ["NAME", "DP05_0001E", "DP03_0062E", "DP03_0009PE", "DP03_0128PE", "state"],
        ["Alabama", "5024279", "59910", "3.2", "15.6", "01"],
        ["Alaska", "733583", "86917", "4.6", "10.5", "02"],
        ["Arizona", "7151502", "72581", "4.0", "12.8", "04"],
    ]


def _fake_census_fetcher(*, credential: str) -> list[list[str]]:
    assert credential == _synthetic_census_value()
    return _census_raw()


def test_census_optional_provider_requires_local_key_without_fixture_runtime() -> None:
    payload = census_acs_profile_payload({}, _secret_status(False), refresh=True)

    assert payload["status"]["provider_id"] == CENSUS_PROVIDER_ID
    assert payload["status"]["state"] == "key_required"
    assert payload["series"] == []
    assert payload["cache"]["census"] is None
    assert payload["summary"]["quote_semantics"] == "not_quote"
    payload_text = str(payload).lower()
    assert "offline_fixture" not in payload_text
    assert "mock" not in payload_text
    assert "api_key=" not in payload_text
    assert "protected_value" not in payload_text
    assert _synthetic_census_value() not in payload_text


def test_census_normalizes_acs_profile_rows_as_non_quote_regional_context() -> None:
    payload = normalize_census_acs_profile_data(
        _census_raw(),
        retrieved_at="2026-05-25T00:00:00Z",
    )

    assert payload["status"]["state"] == "live"
    assert payload["status"]["provider_id"] == CENSUS_PROVIDER_ID
    assert payload["summary"]["series_count"] == 12
    assert payload["summary"]["state_count"] == 3
    assert payload["summary"]["latest_value"] == "5024279"
    assert payload["summary"]["primary_geo"] == "Alabama"
    assert payload["series"][0]["provider_id"] == CENSUS_PROVIDER_ID
    assert payload["series"][0]["quote_semantics"] == "not_quote"
    assert payload["series"][0]["cache_path"] == (
        "market_data/regional/census/acs5_profile_state_2023.json"
    )
    assert payload["series"][1]["variable"] == "DP03_0062E"
    assert _synthetic_census_value() not in str(payload)


def test_census_flows_into_research_and_markets_regional_context() -> None:
    census = census_acs_profile_payload(
        {},
        _secret_status(True),
        refresh=True,
        credential=_synthetic_census_value(),
        fetcher=_fake_census_fetcher,
    )
    research = research_data_payload({}, {}, {}, {}, census_payload=census)
    markets = markets_payload(default_markets_layout(), {}, research_data=research)

    assert research["census"]["summary"]["series_count"] == 12
    assert "cache" not in research["census"]
    assert any(
        series["provider_id"] == CENSUS_PROVIDER_ID
        for series in research["macro"]["series"]
    )
    assert [row["provider_id"] for row in research["macro"]["provider_summaries"]] == [
        "dbnomics_public",
        "fred_optional_local_key",
        "bls_public_macro",
        "eurostat_hicp_public",
        "bea_regional_optional_key",
        CENSUS_PROVIDER_ID,
    ]
    assert markets["regional"]["summary"]["series_count"] == 12
    assert markets["regional"]["status"]["provider_id"] == CENSUS_PROVIDER_ID
    assert markets["regional"]["summary"]["primary_provider"] == CENSUS_PROVIDER_ID
    regional_row = next(
        row
        for row in markets["source_coverage_matrix"]
        if row["asset_family"] == "Regional" and row["runtime_role"] == "macro_context"
    )
    assert regional_row["provider_id"] == CENSUS_PROVIDER_ID
    assert regional_row["auth_mode"] == "optional_local_key"
    assert regional_row["safe_action_id"] == "markets_census_refresh"
    assert regional_row["quote_semantics"] == "not_quote"
    assert "real_order" not in str(markets).lower()


def test_census_refresh_endpoint_writes_cache_without_exposing_secret(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "_census_secret_status_from_store", lambda: _secret_status(True))
    monkeypatch.setattr(
        server,
        "read_local_data_provider_secret",
        lambda *args, **kwargs: _synthetic_census_value(),
    )
    monkeypatch.setattr(server, "CENSUS_FETCHER", _fake_census_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/census/acs-profile/refresh")
    markets = client.post("/api/markets/census/refresh")
    research = client.get("/api/research-data")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["primary_geo"] == "Alabama"
    assert markets.json()["regional"]["status"]["provider_id"] == CENSUS_PROVIDER_ID
    assert markets.json()["regional"]["summary"]["quote_state"] == "disabled_until_provider_gate"
    assert research.json()["census"]["summary"]["series_count"] == 12
    assert any(
        provider["provider_id"] == CENSUS_PROVIDER_ID and provider["health"]["state"] == "active"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["census_acs_profile_cache"] == (
        "market_data/regional/census/acs5_profile_state_2023.json"
    )
    assert (
        tmp_path / "market_data" / "regional" / "census" / "acs5_profile_state_2023.json"
    ).is_file()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert _synthetic_census_value() not in refreshed.text
    assert "protected_value" not in refreshed.text
    assert "api_key=" not in markets.text.lower()


def test_census_endpoint_without_key_returns_key_required_and_no_secret_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    refreshed = client.post("/api/census/acs-profile/refresh")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "key_required"
    assert refreshed.json()["summary"]["series_count"] == 0
    assert not (tmp_path / "market_data" / "regional" / "census").exists()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
