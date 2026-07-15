from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.markets import default_markets_layout, markets_payload
from otto.local_terminal.research_data import research_data_payload
from otto.local_terminal.storage import LocalStateStore


DBNOMICS_SERIES_ID = "INSEE/IPC-2015/A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


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


def _fake_macro() -> dict[str, object]:
    return _dbnomics_raw()


def test_markets_payload_exposes_index_and_regional_macro_context() -> None:
    payload = markets_payload(
        default_markets_layout(),
        {},
        research_data=research_data_payload({}, _dbnomics_raw()),
    )

    assert payload["indexes"]["status"]["provider_id"] == "dbnomics_public"
    assert payload["indexes"]["status"]["source"] == "dbnomics_public"
    assert payload["indexes"]["summary"]["series_count"] == 1
    assert payload["indexes"]["summary"]["provider_count"] == 1
    assert payload["indexes"]["summary"]["latest"] == "119.34"
    assert payload["indexes"]["summary"]["primary_provider"] == "dbnomics_public"
    assert payload["indexes"]["summary"]["headline_series_id"] == DBNOMICS_SERIES_ID
    assert "dbnomics_public" in payload["indexes"]["summary"]["headline_rule"]
    assert payload["indexes"]["summary"]["quote_state"] == "disabled_until_provider_gate"
    assert payload["indexes"]["provider_summaries"][0]["selected_for_headline"] is True
    assert payload["indexes"]["series"][0]["latest_value"] == "119.34"
    assert payload["indexes"]["series"][0]["source_provider"] == "INSEE"
    assert payload["regional"]["summary"]["series_count"] == 1
    assert payload["regional"]["summary"]["quote_provider"] == "optional_local_key_or_regional_provider"
    assert any(
        gateway["tab_id"] == "indexes" and gateway["state"] == "macro_context_available"
        for gateway in payload["asset_gateways"]
    )
    assert any(
        gateway["tab_id"] == "regional" and gateway["state"] == "macro_context_available"
        for gateway in payload["asset_gateways"]
    )
    assert "api_key" not in str(payload).lower()
    assert "real_order" not in str(payload).lower()
    assert "synthetic" not in str(payload["indexes"]).lower()


def test_markets_macro_refresh_writes_dbnomics_cache_and_keeps_quotes_gated(
    tmp_path: Path,
    monkeypatch,
    ) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    monkeypatch.setattr(server, "MACRO_FETCHER", _fake_macro)
    monkeypatch.setattr(server, "BLS_FETCHER", lambda: {})
    monkeypatch.setattr(server, "EUROSTAT_FETCHER", lambda: {})
    client = TestClient(server.create_app())

    refreshed = client.post("/api/markets/macro/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["indexes"]["status"]["state"] == "live"
    assert body["indexes"]["summary"]["series_count"] == 1
    assert body["regional"]["status"]["state"] == "live"
    assert body["regional"]["series"][0]["latest_period"] == "2025"
    assert body["regional"]["summary"]["quote_state"] == "disabled_until_provider_gate"
    assert (
        tmp_path
        / "market_data"
        / "macro"
        / "dbnomics"
        / "INSEE"
        / "IPC-2015"
        / "A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE.json"
    ).is_file()
    assert not (tmp_path / "market_data" / "fundamentals" / "sec" / "0000320193" / "companyfacts.json").exists()
    assert any(
        provider["provider_id"] == "dbnomics_public"
        and provider["health"]["state"] == "active"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["dbnomics_macro_cache"].endswith(".json")
    assert "api_key" not in refreshed.text.lower()
    assert "real_order" not in refreshed.text.lower()
    assert "mock" not in refreshed.text.lower()
