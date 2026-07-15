from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.fx_data import (
    fx_data_payload,
    normalize_bank_of_canada_valet_fx_reference_rates,
    normalize_ecb_fx_reference_rates,
    normalize_federal_reserve_h10_reference_rates,
)
from otto.local_terminal.markets import default_markets_layout, markets_payload
from otto.local_terminal.providers import providers_payload
from otto.local_terminal.storage import LocalStateStore


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ecb_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope
  xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01"
  xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <Cube>
    <Cube time="2026-05-22">
      <Cube currency="USD" rate="1.1595"/>
      <Cube currency="JPY" rate="184.53"/>
      <Cube currency="GBP" rate="0.86418"/>
      <Cube currency="CHF" rate="0.9119"/>
      <Cube currency="CNY" rate="7.8791"/>
    </Cube>
  </Cube>
</gesmes:Envelope>
"""


def _fake_fx() -> str:
    return _ecb_xml()


def _h10_csv() -> str:
    return "\n".join(
        [
            (
                '"Series Description","Euro-Area Euro","United Kingdom Pound",'
                '"Canadian Dollar","Chinese Yuan","Japanese Yen"'
            ),
            '"Unit:","Currency","Currency","Currency","Currency","Currency"',
            '"Multiplier:","1","1","1","1","1"',
            '"Currency:","EUR","GBP","CAD","CNY","JPY"',
            (
                '"Unique Identifier:","H10/H10/RXI$US_N.B.EU",'
                '"H10/H10/RXI$US_N.B.UK","H10/H10/RXI_N.B.CA",'
                '"H10/H10/RXI_N.B.CH","H10/H10/RXI_N.B.JA"'
            ),
            (
                '"Time Period","RXI$US_N.B.EU","RXI$US_N.B.UK","RXI_N.B.CA",'
                '"RXI_N.B.CH","RXI_N.B.JA"'
            ),
            "2026-05-14,1.1678,1.3480,1.3724,6.7851,158.0800",
            "2026-05-15,1.1627,1.3332,1.3750,6.8092,158.6900",
        ]
    )


def _fake_h10() -> str:
    return _h10_csv()


def _boc_json() -> dict[str, object]:
    return {
        "observations": [
            {
                "d": "2026-05-25",
                "FXUSDCAD": {"v": "1.3804"},
                "FXEURCAD": {"v": "1.6072"},
                "FXGBPCAD": {"v": "1.8639"},
                "FXJPYCAD": {"v": "0.008690"},
                "FXCHFCAD": {"v": "1.7246"},
            }
        ]
    }


def _fake_boc() -> dict[str, object]:
    return _boc_json()


def test_ecb_fx_normalize_no_key_reference_xml() -> None:
    payload = normalize_ecb_fx_reference_rates(_ecb_xml(), retrieved_at=_now())

    assert payload["status"]["provider_id"] == "ecb_fx_reference_public"
    assert payload["status"]["source"] == "ecb_fx_reference"
    assert payload["latest"]["date"] == "2026-05-22"
    usd = next(row for row in payload["rows"] if row["quote"] == "USD")
    assert usd["pair"] == "EUR/USD"
    assert usd["rate"] == "1.1595"
    assert usd["reference_only"] is True
    assert "api_key" not in str(payload).lower()


def test_federal_reserve_h10_normalize_no_key_reference_csv() -> None:
    payload = normalize_federal_reserve_h10_reference_rates(
        _h10_csv(),
        retrieved_at=_now(),
    )

    assert payload["status"]["provider_id"] == "federal_reserve_h10_ddp_public"
    assert payload["status"]["source"] == "federal_reserve_h10"
    assert payload["latest"]["date"] == "2026-05-15"
    eur = next(row for row in payload["rows"] if row["currency"] == "EUR")
    jpy = next(row for row in payload["rows"] if row["currency"] == "JPY")
    assert eur["pair"] == "EUR/USD"
    assert eur["rate_basis"] == "usd_per_currency"
    assert jpy["pair"] == "USD/JPY"
    assert jpy["rate_basis"] == "currency_per_usd"
    assert eur["reference_only"] is True
    assert "api_key" not in str(payload).lower()


def test_bank_of_canada_valet_normalize_no_key_reference_json() -> None:
    payload = normalize_bank_of_canada_valet_fx_reference_rates(
        _boc_json(),
        retrieved_at=_now(),
    )

    assert payload["status"]["provider_id"] == "bank_of_canada_valet_fx_reference_public"
    assert payload["status"]["source"] == "bank_of_canada_valet"
    assert payload["latest"]["date"] == "2026-05-25"
    usd = next(row for row in payload["rows"] if row["currency"] == "USD")
    assert usd["pair"] == "USD/CAD"
    assert usd["rate"] == "1.3804"
    assert usd["rate_basis"] == "cad_per_currency"
    assert usd["reference_only"] is True
    assert "api_key" not in str(payload).lower()


def test_fx_payload_and_markets_expose_reference_rates_without_fixture_prices() -> None:
    fx = fx_data_payload(
        fetcher=_fake_fx,
        h10_fetcher=_fake_h10,
        boc_fetcher=_fake_boc,
        refresh=True,
    )
    markets = markets_payload(default_markets_layout(), {}, fx_data=fx)

    assert fx["status"]["state"] == "live"
    assert fx["ecb"]["summary"]["date"] == "2026-05-22"
    assert fx["ecb"]["summary"]["usd"] == "1.1595"
    assert fx["h10"]["summary"]["date"] == "2026-05-15"
    assert fx["h10"]["summary"]["eur"] == "1.1627"
    assert fx["boc"]["summary"]["date"] == "2026-05-25"
    assert fx["boc"]["summary"]["usd"] == "1.3804"
    assert markets["fx"]["summary"]["usd"] == "1.1595"
    assert markets["fx"]["h10"]["summary"]["jpy"] == "158.6900"
    assert markets["fx"]["boc"]["summary"]["usd"] == "1.3804"
    assert markets["fx"]["rows"][0]["pair"].startswith("EUR/")
    assert markets["fx"]["h10"]["rows"][0]["reference_only"] is True
    assert markets["fx"]["boc"]["rows"][0]["reference_only"] is True
    assert any(
        gateway["tab_id"] == "fx" and gateway["state"] == "fx_reference_available"
        for gateway in markets["asset_gateways"]
    )
    assert "offline_fixture" not in str(markets).lower()
    assert "mock" not in str(markets["fx"]).lower()


def test_fx_refresh_writes_cache_and_updates_provider_health(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "FX_FETCHER", _fake_fx)
    monkeypatch.setattr(server, "FED_H10_FETCHER", _fake_h10)
    monkeypatch.setattr(server, "BOC_FX_FETCHER", _fake_boc)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/markets/fx/refresh")
    fx = client.get("/api/fx")
    providers = providers_payload(store)
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["fx"]["status"]["state"] == "live"
    assert refreshed.json()["fx"]["summary"]["date"] == "2026-05-22"
    assert refreshed.json()["fx"]["h10"]["summary"]["date"] == "2026-05-15"
    assert refreshed.json()["fx"]["boc"]["summary"]["date"] == "2026-05-25"
    assert fx.status_code == 200
    assert fx.json()["ecb"]["summary"]["row_count"] == 5
    assert fx.json()["h10"]["summary"]["row_count"] == 5
    assert fx.json()["boc"]["summary"]["row_count"] == 5
    assert "cache" not in fx.json()
    assert (tmp_path / "market_data" / "fx" / "ecb" / "eurofxref_daily.json").is_file()
    assert (
        tmp_path / "market_data" / "fx" / "federal_reserve" / "h10_reference_rates.json"
    ).is_file()
    assert (
        tmp_path / "market_data" / "fx" / "bank_of_canada" / "valet_fx_reference_rates.json"
    ).is_file()
    assert any(
        provider["provider_id"] == "ecb_fx_reference_public"
        and provider["health"]["state"] == "active"
        for provider in providers["providers"]
    )
    assert any(
        provider["provider_id"] == "federal_reserve_h10_ddp_public"
        and provider["health"]["state"] == "active"
        for provider in providers["providers"]
    )
    assert any(
        provider["provider_id"] == "bank_of_canada_valet_fx_reference_public"
        and provider["health"]["state"] == "active"
        for provider in providers["providers"]
    )
    assert local_state.json()["storage"]["ecb_fx_cache"] == (
        "market_data/fx/ecb/eurofxref_daily.json"
    )
    assert local_state.json()["storage"]["federal_reserve_h10_fx_cache"] == (
        "market_data/fx/federal_reserve/h10_reference_rates.json"
    )
    assert local_state.json()["storage"]["bank_of_canada_fx_cache"] == (
        "market_data/fx/bank_of_canada/valet_fx_reference_rates.json"
    )
    assert "api_key" not in refreshed.text.lower()
    assert "private" not in refreshed.text.lower()
