from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.bls_data import (
    BLS_PROVIDER_ID,
    bls_data_payload,
    normalize_bls_latest_series,
)
from src.local_terminal.markets import default_markets_layout, markets_payload
from src.local_terminal.research_data import research_data_payload
from src.local_terminal.storage import LocalStateStore


DBNOMICS_SERIES_ID = "INSEE/IPC-2015/A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE"


def _bls_raw() -> dict[str, object]:
    return {
        "series": [
            {
                "series_id": "LNS14000000",
                "data": [
                    {
                        "year": "2026",
                        "period": "M04",
                        "periodName": "April",
                        "latest": "true",
                        "value": "4.2",
                    }
                ],
            },
            {
                "series_id": "CES0000000001",
                "data": [
                    {
                        "year": "2026",
                        "period": "M04",
                        "periodName": "April",
                        "latest": "true",
                        "value": "159540",
                    }
                ],
            },
            {
                "series_id": "CUSR0000SA0",
                "data": [
                    {
                        "year": "2026",
                        "period": "M04",
                        "periodName": "April",
                        "latest": "true",
                        "value": "320.795",
                    }
                ],
            },
        ]
    }


def _dbnomics_raw() -> dict[str, object]:
    return {
        "series": {
            "docs": [
                {
                    "provider_code": "INSEE",
                    "dataset_code": "IPC-2015",
                    "series_code": "A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE",
                    "series_name": "Annual CPI all items",
                    "dataset_name": "Consumer price index",
                    "period": ["2024", "2025"],
                    "value": [117.2, 119.34],
                    "@frequency": "annual",
                    "indexed_at": "2026-01-15T00:00:00Z",
                }
            ]
        }
    }


def _fake_bls_fetcher(*, series_ids: list[str]) -> dict[str, object]:
    assert "LNS14000000" in series_ids
    return _bls_raw()


def test_bls_normalizes_latest_series_without_key_or_fixture_runtime() -> None:
    payload = normalize_bls_latest_series(_bls_raw(), retrieved_at="2026-05-24T00:00:00Z")

    assert payload["status"]["provider_id"] == BLS_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["series_count"] == 3
    assert payload["summary"]["unemployment_rate"] == "4.2"
    assert payload["summary"]["nonfarm_payrolls"] == "159540"
    assert payload["summary"]["cpi_u"] == "320.795"
    assert payload["series"][0]["cache_path"] == "market_data/macro/bls/latest_series.json"
    assert payload["series"][0]["docs_url"].startswith("https://www.bls.gov/developers/")
    assert "api_key" not in str(payload).lower()
    assert "offline_fixture" not in str(payload).lower()
    assert "mock" not in str(payload).lower()


def test_bls_flows_into_research_and_markets_macro_context() -> None:
    bls = bls_data_payload({}, refresh=True, fetcher=_fake_bls_fetcher)
    research = research_data_payload({}, {}, {}, {}, bls_payload=bls)
    markets = markets_payload(
        default_markets_layout(),
        {},
        research_data=research,
    )

    assert research["bls"]["summary"]["series_count"] == 3
    assert research["status"]["source_count"] == 8
    assert "macro summaries" in research["status"]["message"]
    assert "cache" not in research["cache"]["bls"]
    assert any(series["provider_id"] == BLS_PROVIDER_ID for series in research["macro"]["series"])
    assert markets["indexes"]["summary"]["series_count"] == 3
    assert markets["indexes"]["summary"]["provider_count"] == 1
    assert markets["indexes"]["status"]["provider_id"] == BLS_PROVIDER_ID
    assert markets["indexes"]["summary"]["primary_provider"] == BLS_PROVIDER_ID
    assert markets["indexes"]["summary"]["headline_series_id"] == "LNS14000000"
    assert markets["indexes"]["headline_series"]["provider_id"] == BLS_PROVIDER_ID
    assert markets["indexes"]["series"][0]["latest_value"] == "4.2"
    assert any(
        gateway["tab_id"] == "indexes" and gateway["state"] == "macro_context_available"
        for gateway in markets["asset_gateways"]
    )
    assert "api_key" not in str(markets).lower()
    assert "real_order" not in str(markets).lower()


def test_macro_provider_mix_uses_explicit_headline_contract() -> None:
    bls = bls_data_payload({}, refresh=True, fetcher=_fake_bls_fetcher)
    research = research_data_payload({}, _dbnomics_raw(), {}, {}, bls_payload=bls)
    markets = markets_payload(default_markets_layout(), {}, research_data=research)

    assert research["macro"]["summary"]["provider_count"] == 2
    assert research["macro"]["summary"]["primary_provider"] == "dbnomics_public"
    assert research["macro"]["summary"]["headline_series_id"] == DBNOMICS_SERIES_ID
    assert research["macro"]["headline_series"]["latest_value"] == "119.34"
    assert [row["provider_id"] for row in research["macro"]["provider_summaries"]] == [
        "dbnomics_public",
        "fred_optional_local_key",
        BLS_PROVIDER_ID,
        "eurostat_hicp_public",
        "bea_regional_optional_key",
        "census_api_optional_key",
    ]
    assert markets["indexes"]["summary"]["primary_provider"] == "dbnomics_public"
    assert markets["indexes"]["summary"]["provider_count"] == 2
    assert markets["indexes"]["summary"]["latest"] == "119.34"
    assert any(
        row["provider_id"] == BLS_PROVIDER_ID and row["series_count"] == 3
        for row in markets["indexes"]["provider_summaries"]
    )
    assert "real_order" not in str(markets).lower()


def test_bls_refresh_endpoint_writes_cache_and_keeps_quotes_gated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "BLS_FETCHER", _fake_bls_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/bls/refresh")
    markets = client.post("/api/markets/bls/refresh")
    research = client.get("/api/research-data")
    providers = client.get("/api/providers")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["unemployment_rate"] == "4.2"
    assert "cache" not in refreshed.json()
    assert markets.json()["indexes"]["status"]["provider_id"] == BLS_PROVIDER_ID
    assert markets.json()["regional"]["summary"]["quote_state"] == "disabled_until_provider_gate"
    assert research.json()["bls"]["summary"]["series_count"] == 3
    assert any(
        provider["provider_id"] == BLS_PROVIDER_ID and provider["health"]["state"] == "active"
        for provider in providers.json()["providers"]
    )
    assert (tmp_path / "market_data" / "macro" / "bls" / "latest_series.json").is_file()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert "api_key=" not in refreshed.text.lower()
    assert "private_key" not in markets.text.lower()
