from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.fund_data import fund_data_payload, normalize_sec_fund_tickers
from otto.local_terminal.markets import default_markets_layout, markets_payload
from otto.local_terminal.providers import providers_payload
from otto.local_terminal.storage import LocalStateStore


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sec_funds_raw() -> dict[str, object]:
    return {
        "fields": ["cik", "seriesId", "classId", "symbol"],
        "data": [
            [36405, "S000002848", "C000007808", "VTI"],
            [794105, "S000002564", "C000046844", "BND"],
            [1067839, "S000101292", "C000271435", "QQQ"],
            [1100663, "S000004310", "C000012040", "IVV"],
            [1532203, "S000035729", "C000109503", "BNDX"],
            [1547576, "S000041596", "C000129136", "KWEB"],
        ],
    }


def _fake_funds() -> dict[str, object]:
    return _sec_funds_raw()


def test_sec_fund_tickers_normalize_no_key_registry() -> None:
    payload = normalize_sec_fund_tickers(_sec_funds_raw(), retrieved_at=_now())

    assert payload["status"]["provider_id"] == "sec_fund_ticker_registry_public"
    assert payload["status"]["source"] == "sec_fund_ticker_registry"
    assert payload["summary"]["row_count"] == 6
    assert payload["summary"]["registry_total"] == 6
    assert payload["summary"]["quote_state"] == "disabled_until_provider_gate"
    assert payload["rows"][0]["symbol"] == "BND"
    assert payload["rows"][0]["reference_only"] is True
    assert "api_key" not in str(payload).lower()


def test_markets_payload_exposes_etf_fund_registry_without_quote_prices() -> None:
    funds = fund_data_payload(fetcher=_fake_funds, refresh=True)
    markets = markets_payload(default_markets_layout(), {}, fund_data=funds)

    assert funds["status"]["state"] == "live"
    assert markets["etf"]["status"]["provider_id"] == "sec_fund_ticker_registry_public"
    assert markets["etf"]["summary"]["row_count"] == 6
    assert markets["etf"]["summary"]["quote_state"] == "key_required"
    assert markets["etf"]["summary"]["quote_provider"] == "alphavantage_global_quote_optional_key"
    assert markets["etf"]["quotes"] == []
    assert markets["research_summary"]["funds"]["rows"][0]["symbol"] == "BND"
    assert markets["research_summary"]["etf_quotes"]["symbol"] == "SPY"
    assert any(
        gateway["tab_id"] == "etf" and gateway["state"] == "fund_registry_available"
        for gateway in markets["asset_gateways"]
    )
    assert "offline_fixture" not in str(markets).lower()
    assert "mock" not in str(markets["etf"]).lower()


def test_etf_refresh_writes_cache_and_updates_provider_health(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "FUND_FETCHER", _fake_funds)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/markets/etf/refresh")
    funds = client.get("/api/funds")
    providers = providers_payload(store)
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    body = refreshed.json()
    assert body["etf"]["status"]["state"] == "live"
    assert body["etf"]["summary"]["row_count"] == 6
    assert body["etf"]["summary"]["quote_state"] == "key_required"
    assert body["etf"]["summary"]["quote_symbol"] == "SPY"
    etf_gateway = next(gateway for gateway in body["asset_gateways"] if gateway["tab_id"] == "etf")
    assert etf_gateway["state"] == "fund_registry_available"
    assert funds.status_code == 200
    assert "cache" not in funds.json()
    assert (tmp_path / "market_data" / "funds" / "sec" / "company_tickers_mf.json").is_file()
    assert any(
        provider["provider_id"] == "sec_fund_ticker_registry_public"
        and provider["health"]["state"] == "active"
        for provider in providers["providers"]
    )
    assert local_state.json()["storage"]["sec_fund_tickers_cache"] == (
        "market_data/funds/sec/company_tickers_mf.json"
    )
    assert "api_key" not in refreshed.text.lower()
    assert "real_order" not in refreshed.text.lower()
