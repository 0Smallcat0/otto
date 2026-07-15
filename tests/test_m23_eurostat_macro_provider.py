from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.eurostat_data import (
    EUROSTAT_PROVIDER_ID,
    eurostat_hicp_payload,
    normalize_eurostat_hicp,
)
from otto.local_terminal.markets import default_markets_layout, markets_payload
from otto.local_terminal.research_data import research_data_payload
from otto.local_terminal.storage import LocalStateStore


def _raw() -> dict[str, object]:
    return {
        "version": "2.0",
        "label": "HICP - monthly data (index) (1996-2025)",
        "source": "ESTAT",
        "updated": "2026-02-06T23:00:00+0100",
        "value": {"0": 129.72, "1": 129.34, "2": 129.57},
        "dimension": {
            "time": {
                "category": {
                    "index": {
                        "2025-10": 0,
                        "2025-11": 1,
                        "2025-12": 2,
                    }
                }
            }
        },
    }


def _fake_fetcher() -> dict[str, object]:
    return _raw()


def test_eurostat_payload_uses_explicit_unavailable_state_without_fixture_runtime() -> None:
    payload = eurostat_hicp_payload({}, refresh=False, fetcher=_fake_fetcher)

    assert payload["status"]["state"] == "unavailable"
    assert payload["series"] == []
    assert payload["summary"]["provider_id"] == EUROSTAT_PROVIDER_ID
    assert payload["summary"]["quote_semantics"] == "not_quote"
    assert payload["entry"]["auth_mode"] == "no-key"
    assert "offline_fixture" not in str(payload)


def test_eurostat_normalizes_hicp_rows_as_macro_context_not_quotes() -> None:
    payload = normalize_eurostat_hicp(_raw(), retrieved_at="2026-05-27T00:00:00Z")

    assert payload["status"]["provider_id"] == EUROSTAT_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["status"]["data_vintage"] == "aged"
    assert "months old" in payload["status"]["message"]
    assert payload["status"]["orderable"] is False
    assert payload["status"]["live_action_enabled"] is False
    assert payload["summary"]["latest_period"] == "2025-12"
    assert payload["summary"]["latest_value"] == "129.57"
    assert payload["summary"]["quote_semantics"] == "not_quote"
    assert payload["series"][0]["series_id"] == "prc_hicp_midx.EA20.CP00.I15"
    assert payload["series"][0]["cache_path"] == (
        "market_data/macro/eurostat/hicp_ea20_cp00_i15.json"
    )
    assert payload["observations"][0]["period"] == "2025-12"
    assert "real_order" not in str(payload).lower()


def test_eurostat_flows_into_research_and_markets_macro_context() -> None:
    eurostat = eurostat_hicp_payload({}, refresh=True, fetcher=_fake_fetcher)
    research = research_data_payload({}, {}, {}, {}, eurostat_payload=eurostat)
    markets = markets_payload(default_markets_layout(), {}, research_data=research)

    assert research["eurostat"]["summary"]["series_count"] == 1
    assert "cache" not in research["eurostat"]
    assert "cache" not in research["cache"]["eurostat"]
    assert any(
        series["provider_id"] == EUROSTAT_PROVIDER_ID
        for series in research["macro"]["series"]
    )
    assert any(
        row["provider_id"] == EUROSTAT_PROVIDER_ID and row["series_count"] == 1
        for row in research["macro"]["provider_summaries"]
    )
    assert markets["indexes"]["summary"]["provider_count"] == 1
    assert markets["indexes"]["status"]["provider_id"] == EUROSTAT_PROVIDER_ID
    assert markets["indexes"]["summary"]["primary_provider"] == EUROSTAT_PROVIDER_ID
    assert markets["indexes"]["summary"]["headline_series_id"] == (
        "prc_hicp_midx.EA20.CP00.I15"
    )
    assert markets["indexes"]["headline_series"]["provider_id"] == EUROSTAT_PROVIDER_ID
    assert markets["indexes"]["series"][0]["latest_value"] == "129.57"
    assert "api_key" not in str(markets).lower()
    assert "real_order" not in str(markets).lower()


def test_eurostat_refresh_endpoint_writes_public_cache_and_markets_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "EUROSTAT_FETCHER", _fake_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/eurostat/hicp/refresh")
    markets = client.get("/api/markets")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["status"]["data_vintage"] == "aged"
    assert refreshed.json()["summary"]["latest_period"] == "2025-12"
    assert "cache" not in refreshed.json()
    assert (
        tmp_path / "market_data" / "macro" / "eurostat" / "hicp_ea20_cp00_i15.json"
    ).is_file()
    source_row = next(
        row
        for row in markets.json()["source_coverage_matrix"]
        if row["provider_id"] == EUROSTAT_PROVIDER_ID
    )
    assert source_row["asset_family"] == "Indexes"
    assert source_row["runtime_role"] == "macro_context"
    assert source_row["auth_mode"] == "public_no_key"
    assert source_row["quote_semantics"] == "not_quote"
    assert source_row["safe_action_id"] == "markets_macro_refresh"
    assert source_row["live_action_enabled"] is False
    assert markets.json()["indexes"]["status"]["provider_id"] == EUROSTAT_PROVIDER_ID
    assert any(
        provider["provider_id"] == EUROSTAT_PROVIDER_ID
        and provider["health"]["state"] == "active"
        and provider["health"]["cache_id"] == "macro_eurostat_hicp"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["eurostat_hicp_cache"].endswith(
        "hicp_ea20_cp00_i15.json"
    )
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert "api_key=" not in refreshed.text.lower()
    assert "private_key" not in markets.text.lower()
