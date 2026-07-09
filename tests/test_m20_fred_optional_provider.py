from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.fred_data import (
    FRED_PROVIDER_ID,
    fred_data_payload,
    normalize_fred_series_observations,
)
from src.local_terminal.storage import LocalStateStore


def _synthetic_fred_value() -> str:
    return "fred-" + "local-" + "adapter"


def _fred_raw() -> dict[str, object]:
    return {
        "realtime_start": "2026-05-22",
        "realtime_end": "2026-05-22",
        "observation_start": "2026-05-01",
        "observation_end": "2026-05-22",
        "units": "lin",
        "frequency": "Daily",
        "observations": [
            {
                "realtime_start": "2026-05-22",
                "realtime_end": "2026-05-22",
                "date": "2026-05-22",
                "value": "4.31",
            },
            {
                "realtime_start": "2026-05-21",
                "realtime_end": "2026-05-21",
                "date": "2026-05-21",
                "value": "4.28",
            },
        ],
    }


def _secret_status(stored: bool) -> dict[str, Any]:
    return {
        "stored_provider_ids": [FRED_PROVIDER_ID] if stored else [],
        "api_secret_value_reads_enabled": False,
        "internal_provider_reads_enabled": True,
    }


def _fake_fred_fetcher(*, series_id: str, api_key: str, limit: int = 12) -> dict[str, object]:
    assert series_id == "DGS10"
    assert limit == 12
    assert api_key == _synthetic_fred_value()
    return _fred_raw()


def test_fred_payload_requires_local_key_without_fixture_runtime() -> None:
    payload = fred_data_payload({}, _secret_status(stored=False), refresh=True, fetcher=_fake_fred_fetcher)

    assert payload["status"]["state"] == "key_required"
    assert payload["series"] == []
    assert payload["cache"]["fred"] is None
    assert payload["summary"]["provider_id"] == FRED_PROVIDER_ID
    assert "api_key" not in str(payload).lower()


def test_fred_normalizes_series_observations_without_key_material() -> None:
    payload = normalize_fred_series_observations(_fred_raw(), retrieved_at="2026-05-23T00:00:00Z")

    assert payload["status"]["provider_id"] == FRED_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["latest_period"] == "2026-05-22"
    assert payload["summary"]["latest_value"] == "4.31"
    assert payload["series"][0]["observation_count"] == 2
    assert "api_key" not in str(payload).lower()


def test_fred_refresh_endpoint_uses_internal_secret_reader_and_writes_redacted_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "_fred_secret_status_from_store", lambda: _secret_status(stored=True))
    monkeypatch.setattr(server, "read_local_data_provider_secret", lambda *_, **__: _synthetic_fred_value())
    monkeypatch.setattr(server, "FRED_FETCHER", _fake_fred_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/fred/refresh")
    research = client.get("/api/research-data")
    markets = client.post("/api/markets/fred/refresh")
    providers = client.get("/api/providers")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["latest_value"] == "4.31"
    assert refreshed.json()["summary"]["provider_id"] == FRED_PROVIDER_ID
    assert "cache" not in refreshed.json()
    assert _synthetic_fred_value() not in refreshed.text
    assert "api_key=" not in refreshed.text.lower()
    cache_path = tmp_path / "market_data" / "macro" / "fred" / "DGS10.json"
    assert cache_path.is_file()
    assert _synthetic_fred_value() not in cache_path.read_text(encoding="utf-8")
    assert research.json()["fred"]["summary"]["latest_value"] == "4.31"
    assert any(series["provider_id"] == FRED_PROVIDER_ID for series in research.json()["macro"]["series"])
    assert markets.json()["indexes"]["summary"]["series_count"] >= 1
    assert any(
        provider["provider_id"] == FRED_PROVIDER_ID and provider["health"]["state"] == "active"
        for provider in providers.json()["providers"]
    )
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_fred_refresh_endpoint_without_key_is_explicitly_gated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post("/api/fred/refresh")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "key_required"
    assert response.json()["series"] == []
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert "offline_fixture" not in response.text
