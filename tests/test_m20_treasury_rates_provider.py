from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.markets import default_markets_layout, markets_payload
from otto.local_terminal.providers import providers_payload
from otto.local_terminal.rates_data import (
    normalize_nyfed_sofr,
    normalize_treasury_yield_curve,
    rates_data_payload,
)
from otto.local_terminal.storage import LocalStateStore


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _treasury_xml() -> str:
    return """<?xml version="1.0" encoding="utf-8" standalone="yes" ?>
<feed xml:base="https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
  xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices"
  xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
  xmlns="http://www.w3.org/2005/Atom">
<entry>
<content type="application/xml">
<m:properties>
<d:NEW_DATE m:type="Edm.DateTime">2026-05-21T00:00:00</d:NEW_DATE>
<d:BC_1MONTH m:type="Edm.Double">3.91</d:BC_1MONTH>
<d:BC_2YEAR m:type="Edm.Double">3.98</d:BC_2YEAR>
<d:BC_10YEAR m:type="Edm.Double">4.53</d:BC_10YEAR>
<d:BC_30YEAR m:type="Edm.Double">5.05</d:BC_30YEAR>
</m:properties>
</content>
</entry>
<entry>
<content type="application/xml">
<m:properties>
<d:NEW_DATE m:type="Edm.DateTime">2026-05-22T00:00:00</d:NEW_DATE>
<d:BC_1MONTH m:type="Edm.Double">3.92</d:BC_1MONTH>
<d:BC_2YEAR m:type="Edm.Double">4.02</d:BC_2YEAR>
<d:BC_10YEAR m:type="Edm.Double">4.57</d:BC_10YEAR>
<d:BC_30YEAR m:type="Edm.Double">5.08</d:BC_30YEAR>
</m:properties>
</content>
</entry>
</feed>
"""


def _fake_rates() -> str:
    return _treasury_xml()


def _sofr_json() -> dict[str, object]:
    return {
        "refRates": [
            {
                "effectiveDate": "2026-05-21",
                "type": "SOFR",
                "percentRate": 3.51,
                "percentPercentile25": 3.51,
                "percentPercentile75": 3.55,
                "volumeInBillions": 3077,
                "revisionIndicator": "",
            },
            {
                "effectiveDate": "2026-05-22",
                "type": "SOFR",
                "percentRate": 3.52,
                "percentPercentile25": 3.51,
                "percentPercentile75": 3.56,
                "volumeInBillions": 3081,
                "revisionIndicator": "",
            },
        ]
    }


def _fake_sofr() -> dict[str, object]:
    return _sofr_json()


def test_treasury_rates_normalize_no_key_xml_feed() -> None:
    payload = normalize_treasury_yield_curve(_treasury_xml(), retrieved_at=_now())

    assert payload["status"]["provider_id"] == "us_treasury_yield_public"
    assert payload["status"]["source"] == "us_treasury_public"
    assert payload["latest"]["date"] == "2026-05-22"
    assert payload["latest"]["tenors"][0] == {
        "tenor": "1M",
        "field": "BC_1MONTH",
        "rate": "3.92",
        "unit": "percent",
    }
    assert payload["latest"]["tenors"][2]["tenor"] == "10Y"
    assert "api_key" not in str(payload).lower()


def test_nyfed_sofr_normalize_no_key_json_feed() -> None:
    payload = normalize_nyfed_sofr(_sofr_json(), retrieved_at=_now())

    assert payload["status"]["provider_id"] == "nyfed_sofr_public"
    assert payload["status"]["source"] == "nyfed_sofr_public"
    assert payload["latest"]["date"] == "2026-05-22"
    assert payload["latest"]["rate"] == "3.52"
    assert payload["latest"]["volume_in_billions"] == "3081"
    assert "api_key" not in str(payload).lower()


def test_rates_payload_and_markets_expose_treasury_curve_without_fixture_prices() -> None:
    rates = rates_data_payload(fetcher=_fake_rates, sofr_fetcher=_fake_sofr, refresh=True)
    markets = markets_payload(default_markets_layout(), {}, rates_data=rates)

    assert rates["status"]["state"] == "live"
    assert rates["treasury"]["summary"]["latest_date"] == "2026-05-22"
    assert rates["treasury"]["summary"]["ten_year"] == "4.57"
    assert rates["treasury"]["summary"]["slope_10y_2y"] == "0.55"
    assert rates["sofr"]["summary"]["latest_date"] == "2026-05-22"
    assert rates["sofr"]["summary"]["rate"] == "3.52"
    assert markets["rates"]["summary"]["ten_year"] == "4.57"
    assert markets["rates"]["sofr"]["summary"]["rate"] == "3.52"
    assert markets["rates"]["rows"][2]["tenor"] == "10Y"
    assert any(
        row["provider_id"] == "nyfed_sofr_public"
        and row["runtime_role"] == "overnight_reference_rate"
        and row["quote_semantics"] == "reference_only"
        for row in markets["source_coverage_matrix"]
    )
    assert any(
        gateway["tab_id"] == "rates" and gateway["state"] == "rates_available"
        for gateway in markets["asset_gateways"]
    )
    assert "offline_fixture" not in str(markets).lower()
    assert "mock" not in str(markets["rates"]).lower()


def test_rates_refresh_writes_cache_and_updates_provider_health(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "RATES_FETCHER", _fake_rates)
    monkeypatch.setattr(server, "SOFR_FETCHER", _fake_sofr)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/markets/rates/refresh")
    rates = client.get("/api/rates")
    providers = providers_payload(store)
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["rates"]["status"]["state"] == "live"
    assert refreshed.json()["rates"]["summary"]["latest_date"] == "2026-05-22"
    assert rates.status_code == 200
    assert rates.json()["treasury"]["summary"]["tenor_count"] == 4
    assert rates.json()["sofr"]["summary"]["rate"] == "3.52"
    assert "cache" not in rates.json()
    assert (tmp_path / "market_data" / "rates" / "treasury" / "daily_yield_curve.json").is_file()
    assert (tmp_path / "market_data" / "rates" / "nyfed" / "sofr.json").is_file()
    assert any(
        provider["provider_id"] == "us_treasury_yield_public"
        and provider["health"]["state"] == "active"
        for provider in providers["providers"]
    )
    assert any(
        provider["provider_id"] == "nyfed_sofr_public"
        and provider["health"]["state"] == "active"
        for provider in providers["providers"]
    )
    assert local_state.json()["storage"]["treasury_rates_cache"] == (
        "market_data/rates/treasury/daily_yield_curve.json"
    )
    assert local_state.json()["storage"]["nyfed_sofr_cache"] == "market_data/rates/nyfed/sofr.json"
    assert "api_key" not in refreshed.text.lower()
    assert "private" not in refreshed.text.lower()
