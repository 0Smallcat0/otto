from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.eia_data import (
    EIA_PROVIDER_ID,
    eia_energy_payload,
    normalize_eia_energy_series,
)
from src.local_terminal.markets import default_markets_layout, markets_payload
from src.local_terminal.storage import LocalStateStore


def _synthetic_eia_value() -> str:
    return "eia-" + "local-" + "adapter"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _secret_status(stored: bool) -> dict[str, Any]:
    return {
        "stored_provider_ids": [EIA_PROVIDER_ID] if stored else [],
        "api_secret_value_reads_enabled": False,
    }


def _eia_raw() -> dict[str, object]:
    return {
        "series": [
            {
                "series_id": "PET.RWTC.D",
                "name": "WTI Cushing spot price",
                "units": "dollars per barrel",
                "frequency": "daily",
                "data": [["2026-05-20", "63.50"], ["2026-05-19", "62.75"]],
            },
            {
                "series_id": "PET.RBRTE.D",
                "name": "Brent spot price",
                "units": "dollars per barrel",
                "frequency": "daily",
                "data": [["2026-05-20", "67.10"]],
            },
            {
                "series_id": "NG.RNGWHHD.D",
                "name": "Henry Hub natural gas spot price",
                "units": "dollars per million Btu",
                "frequency": "daily",
                "data": [["2026-05-20", "3.21"]],
            },
        ]
    }


def _fake_eia_fetcher(*, api_key: str, series_ids: list[str], limit: int = 8) -> dict[str, object]:
    assert api_key == _synthetic_eia_value()
    assert "PET.RWTC.D" in series_ids
    assert limit == 8
    return _eia_raw()


def test_eia_payload_requires_local_key_without_fixture_runtime() -> None:
    payload = eia_energy_payload({}, _secret_status(stored=False), refresh=True, fetcher=_fake_eia_fetcher)

    assert payload["status"]["state"] == "key_required"
    assert payload["series"] == []
    assert payload["cache"]["eia"] is None
    assert payload["summary"]["wti_spot"] == ""
    assert "offline_fixture" not in str(payload).lower()
    assert "mock" not in str(payload).lower()


def test_eia_normalizes_seriesid_payload_without_key_material() -> None:
    payload = normalize_eia_energy_series(_eia_raw(), retrieved_at=_now())

    assert payload["status"]["provider_id"] == EIA_PROVIDER_ID
    assert payload["status"]["source"] == "eia_open_data_api"
    assert payload["summary"]["series_count"] == 3
    assert payload["summary"]["wti_spot"] == "63.5"
    assert payload["summary"]["brent_spot"] == "67.1"
    assert payload["summary"]["henry_hub"] == "3.21"
    assert payload["series"][0]["cache_path"] == "market_data/commodities/eia/energy_series.json"
    assert "api_key" not in str(payload).lower()
    assert _synthetic_eia_value() not in str(payload)


def test_eia_energy_context_flows_into_markets_commodities() -> None:
    eia = eia_energy_payload(
        {},
        _secret_status(stored=True),
        refresh=True,
        credential=_synthetic_eia_value(),
        fetcher=_fake_eia_fetcher,
    )
    markets = markets_payload(
        default_markets_layout(),
        {},
        commodity_data={"world_bank": {}, "eia": eia},
    )

    assert markets["commodities"]["energy"]["state"] == "live"
    assert markets["commodities"]["energy"]["series_count"] == 3
    assert markets["commodities"]["energy"]["wti_spot"] == "63.5"
    assert any(
        gateway["tab_id"] == "commodities"
        and gateway["state"] == "energy_context_available"
        for gateway in markets["asset_gateways"]
    )
    assert "offline_fixture" not in str(markets).lower()


def test_eia_refresh_endpoint_uses_internal_secret_reader_and_writes_redacted_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "_eia_secret_status_from_store", lambda: _secret_status(stored=True))
    monkeypatch.setattr(server, "read_local_data_provider_secret", lambda *_, **__: _synthetic_eia_value())
    monkeypatch.setattr(server, "EIA_FETCHER", _fake_eia_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/eia/energy/refresh")
    markets = client.post("/api/markets/eia/refresh")
    public = client.get("/api/commodities")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["wti_spot"] == "63.5"
    assert "cache" not in refreshed.json()
    assert markets.json()["commodities"]["energy"]["state"] == "live"
    assert markets.json()["commodities"]["energy"]["brent_spot"] == "67.1"
    assert public.json()["eia"]["summary"]["henry_hub"] == "3.21"
    assert "cache" not in public.json()["eia"]
    cache_path = tmp_path / "market_data" / "commodities" / "eia" / "energy_series.json"
    assert cache_path.is_file()
    assert _synthetic_eia_value() not in refreshed.text
    assert _synthetic_eia_value() not in markets.text
    assert _synthetic_eia_value() not in cache_path.read_text(encoding="utf-8")


def test_eia_refresh_endpoint_without_key_is_explicitly_gated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    monkeypatch.setattr(server, "_eia_secret_status_from_store", lambda: _secret_status(stored=False))
    client = TestClient(server.create_app())

    response = client.post("/api/eia/energy/refresh")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "key_required"
    assert response.json()["series"] == []
    assert not (tmp_path / "market_data" / "commodities" / "eia").exists()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
