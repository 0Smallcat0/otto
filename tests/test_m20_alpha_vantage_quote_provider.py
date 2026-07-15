import json
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.alpha_vantage_data import (
    ALPHA_VANTAGE_DEFAULT_ETF_SYMBOL,
    ALPHA_VANTAGE_ETF_WATCHLIST,
    ALPHA_VANTAGE_FX_WATCHLIST,
    ALPHA_VANTAGE_PROVIDER_ID,
    ALPHA_VANTAGE_STOCK_WATCHLIST,
    alpha_vantage_fx_pair_list,
    alpha_vantage_fx_quote_watchlist_payload,
    alpha_vantage_quote_payload,
    alpha_vantage_quote_watchlist_payload,
    alpha_vantage_symbol_list,
    normalize_alpha_vantage_currency_exchange_rate,
    normalize_alpha_vantage_global_quote,
)
from otto.local_terminal.markets import default_markets_layout, markets_payload
from otto.local_terminal.storage import LocalStateStore


def _synthetic_alpha_value() -> str:
    return "alpha-" + "local-" + "adapter"


def _global_quote_raw(symbol: str = "AAPL") -> dict[str, object]:
    return {
        "Global Quote": {
            "01. symbol": symbol,
            "02. open": "196.1000",
            "03. high": "198.4000",
            "04. low": "195.2100",
            "05. price": "197.5300",
            "06. volume": "45123456",
            "07. latest trading day": "2026-05-22",
            "08. previous close": "196.2100",
            "09. change": "1.3200",
            "10. change percent": "0.6727%",
        }
    }


def _fx_quote_raw(pair: str = "EUR/USD") -> dict[str, object]:
    left, right = pair.split("/")
    return {
        "Realtime Currency Exchange Rate": {
            "1. From_Currency Code": left,
            "2. From_Currency Name": f"{left} currency",
            "3. To_Currency Code": right,
            "4. To_Currency Name": f"{right} currency",
            "5. Exchange Rate": "1.2345",
            "6. Last Refreshed": "2026-05-25 12:00:00",
            "7. Time Zone": "UTC",
            "8. Bid Price": "1.2344",
            "9. Ask Price": "1.2346",
        }
    }


def _secret_status(stored: bool) -> dict[str, Any]:
    return {
        "stored_provider_ids": [ALPHA_VANTAGE_PROVIDER_ID] if stored else [],
        "api_secret_value_reads_enabled": False,
        "internal_provider_reads_enabled": True,
    }


def _fake_alpha_fetcher(*, symbol: str, credential: str) -> dict[str, object]:
    assert symbol in {*ALPHA_VANTAGE_STOCK_WATCHLIST, *ALPHA_VANTAGE_ETF_WATCHLIST}
    assert credential == _synthetic_alpha_value()
    return _global_quote_raw(symbol=symbol)


def _fake_alpha_fx_fetcher(*, pair: str, credential: str) -> dict[str, object]:
    assert pair in set(ALPHA_VANTAGE_FX_WATCHLIST)
    assert credential == _synthetic_alpha_value()
    return _fx_quote_raw(pair=pair)


def test_alpha_vantage_payload_requires_local_key_without_fixture_runtime() -> None:
    payload = alpha_vantage_quote_payload(
        {},
        _secret_status(stored=False),
        refresh=True,
        fetcher=_fake_alpha_fetcher,
    )

    assert payload["status"]["state"] == "key_required"
    assert payload["quotes"] == []
    assert payload["cache"]["alpha_vantage"] is None
    assert payload["summary"]["provider_id"] == ALPHA_VANTAGE_PROVIDER_ID
    assert "offline_fixture" not in str(payload)


def test_alpha_vantage_normalizes_global_quote_without_key_material() -> None:
    payload = normalize_alpha_vantage_global_quote(
        _global_quote_raw(),
        retrieved_at="2026-05-23T00:00:00Z",
    )

    assert payload["status"]["provider_id"] == ALPHA_VANTAGE_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["symbol"] == "AAPL"
    assert payload["summary"]["price"] == "197.5300"
    assert payload["quotes"][0]["change_percent"] == "0.6727%"
    assert _synthetic_alpha_value() not in str(payload)


def test_alpha_vantage_stale_cache_payload_is_serializable_and_not_overstated() -> None:
    cached = normalize_alpha_vantage_global_quote(
        _global_quote_raw(),
        retrieved_at="2026-05-23T00:00:00Z",
    )

    payload = alpha_vantage_quote_payload(
        cached,
        _secret_status(stored=False),
        refresh=True,
        fetcher=_fake_alpha_fetcher,
    )

    assert payload["status"]["state"] == "stale_cache"
    assert payload["summary"]["price"] == "197.5300"
    assert payload["cache"]["alpha_vantage"] is not payload
    json.dumps(payload)

    markets = markets_payload(
        default_markets_layout(),
        {},
        equity_quote_data=payload,
    )
    stock_gateway = next(
        gateway for gateway in markets["asset_gateways"] if gateway["tab_id"] == "stocks"
    )
    assert stock_gateway["state"] == "stock_lanes_available"
    assert stock_gateway["provider_id"] == "stock_status_lanes"
    assert markets["stocks"]["summary"]["available_lane_count"] == 1
    assert markets["stocks"]["status_lanes"][0]["lane_id"] == "quotes"
    assert markets["stocks"]["status_lanes"][0]["state"] == "stale_cache"


def test_alpha_vantage_watchlist_payload_sanitizes_symbols_and_combines_rows() -> None:
    payload = alpha_vantage_quote_watchlist_payload(
        {},
        _secret_status(stored=True),
        refresh=True,
        credential=_synthetic_alpha_value(),
        fetcher=_fake_alpha_fetcher,
        symbols=["aapl", "MSFT", "MSFT", "NVDA"],
    )

    assert payload["status"]["state"] == "live"
    assert payload["status"]["symbols"] == ["AAPL", "MSFT", "NVDA"]
    assert payload["summary"]["symbols"] == "AAPL,MSFT,NVDA"
    assert payload["summary"]["requested_count"] == 3
    assert payload["summary"]["row_count"] == 3
    assert [quote["symbol"] for quote in payload["quotes"]] == ["AAPL", "MSFT", "NVDA"]
    assert "cache" in payload
    assert set(payload["cache"]["alpha_vantage_by_symbol"]) == {"AAPL", "MSFT", "NVDA"}
    assert _synthetic_alpha_value() not in json.dumps(payload)


def test_alpha_vantage_symbol_list_uses_fallback_for_empty_agent_input() -> None:
    assert alpha_vantage_symbol_list("", fallback_symbols=ALPHA_VANTAGE_ETF_WATCHLIST) == [
        "SPY",
        "QQQ",
        "IWM",
    ]


def test_alpha_vantage_fx_pair_list_uses_bounded_normalized_pairs() -> None:
    assert alpha_vantage_fx_pair_list("eurusd, USD-JPY,USD/JPY,INVALID") == [
        "EUR/USD",
        "USD/JPY",
    ]
    assert alpha_vantage_fx_pair_list("") == list(ALPHA_VANTAGE_FX_WATCHLIST)


def test_alpha_vantage_normalizes_fx_quote_without_key_material() -> None:
    payload = normalize_alpha_vantage_currency_exchange_rate(
        _fx_quote_raw(),
        retrieved_at="2026-05-25T00:00:00Z",
    )

    assert payload["status"]["provider_id"] == ALPHA_VANTAGE_PROVIDER_ID
    assert payload["status"]["state"] == "live"
    assert payload["summary"]["pair"] == "EUR/USD"
    assert payload["summary"]["rate"] == "1.2345"
    assert payload["quotes"][0]["quote_semantics"] == "quote_not_orderable"
    assert payload["quotes"][0]["live_action_enabled"] is False
    assert _synthetic_alpha_value() not in str(payload)


def test_alpha_vantage_fx_watchlist_payload_sanitizes_pairs_and_combines_rows() -> None:
    payload = alpha_vantage_fx_quote_watchlist_payload(
        {},
        _secret_status(stored=True),
        refresh=True,
        credential=_synthetic_alpha_value(),
        fetcher=_fake_alpha_fx_fetcher,
        pairs=["eurusd", "USD/JPY", "USD/JPY", "gbp-usd"],
    )

    assert payload["status"]["state"] == "live"
    assert payload["status"]["pairs"] == ["EUR/USD", "USD/JPY", "GBP/USD"]
    assert payload["summary"]["pairs"] == "EUR/USD,USD/JPY,GBP/USD"
    assert payload["summary"]["requested_count"] == 3
    assert payload["summary"]["row_count"] == 3
    assert [quote["pair"] for quote in payload["quotes"]] == [
        "EUR/USD",
        "USD/JPY",
        "GBP/USD",
    ]
    assert set(payload["cache"]["alpha_vantage_fx_by_pair"]) == {
        "EURUSD",
        "USDJPY",
        "GBPUSD",
    }
    assert _synthetic_alpha_value() not in json.dumps(payload)


def test_alpha_vantage_refresh_endpoint_uses_internal_secret_reader_and_writes_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(
        server,
        "_alpha_vantage_secret_status_from_store",
        lambda: _secret_status(stored=True),
    )
    monkeypatch.setattr(server, "read_local_data_provider_secret", lambda *_, **__: _synthetic_alpha_value())
    monkeypatch.setattr(server, "ALPHA_VANTAGE_FETCHER", _fake_alpha_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/alpha-vantage/equity-quote/refresh")
    markets = client.post("/api/markets/stocks/quote/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["price"] == "197.5300"
    assert refreshed.json()["summary"]["provider_id"] == ALPHA_VANTAGE_PROVIDER_ID
    assert "cache" not in refreshed.json()
    assert _synthetic_alpha_value() not in refreshed.text
    assert "api_key=" not in refreshed.text.lower()
    cache_path = tmp_path / "market_data" / "equities" / "alphavantage" / "global_quote" / "AAPL.json"
    assert cache_path.is_file()
    assert (
        tmp_path / "market_data" / "equities" / "alphavantage" / "global_quote" / "MSFT.json"
    ).is_file()
    assert (
        tmp_path / "market_data" / "equities" / "alphavantage" / "global_quote" / "NVDA.json"
    ).is_file()
    assert _synthetic_alpha_value() not in cache_path.read_text(encoding="utf-8")
    assert markets.json()["stocks"]["summary"]["quote_price"] == "197.5300"
    assert markets.json()["stocks"]["summary"]["quote_state"] == "live"
    assert markets.json()["stocks"]["summary"]["quote_symbols"] == "AAPL,MSFT,NVDA"
    assert markets.json()["stocks"]["summary"]["quote_row_count"] == 3
    assert [row["symbol"] for row in markets.json()["stocks"]["quotes"]] == [
        "AAPL",
        "MSFT",
        "NVDA",
    ]
    assert markets.json()["stocks"]["quotes"][0]["provider_id"] == ALPHA_VANTAGE_PROVIDER_ID
    stock_gateway = next(
        gateway for gateway in markets.json()["asset_gateways"] if gateway["tab_id"] == "stocks"
    )
    assert stock_gateway["state"] == "stock_lanes_available"
    assert stock_gateway["provider_id"] == "stock_status_lanes"
    assert markets.json()["stocks"]["summary"]["available_lane_count"] == 1
    assert any(
        provider["provider_id"] == ALPHA_VANTAGE_PROVIDER_ID
        and provider["health"]["state"] == "active"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["alpha_vantage_equity_quote_cache"].endswith("AAPL.json")
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_alpha_vantage_etf_quote_uses_spy_cache_without_exposing_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(
        server,
        "_alpha_vantage_secret_status_from_store",
        lambda: _secret_status(stored=True),
    )
    monkeypatch.setattr(server, "read_local_data_provider_secret", lambda *_, **__: _synthetic_alpha_value())
    monkeypatch.setattr(server, "ALPHA_VANTAGE_FETCHER", _fake_alpha_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post("/api/alpha-vantage/etf-quote/refresh")
    markets = client.post("/api/markets/etf/quote/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["symbol"] == ALPHA_VANTAGE_DEFAULT_ETF_SYMBOL
    assert "cache" not in refreshed.json()
    assert _synthetic_alpha_value() not in refreshed.text
    cache_path = (
        tmp_path
        / "market_data"
        / "equities"
        / "alphavantage"
        / "global_quote"
        / "SPY.json"
    )
    assert cache_path.is_file()
    assert (
        tmp_path / "market_data" / "equities" / "alphavantage" / "global_quote" / "QQQ.json"
    ).is_file()
    assert (
        tmp_path / "market_data" / "equities" / "alphavantage" / "global_quote" / "IWM.json"
    ).is_file()
    assert _synthetic_alpha_value() not in cache_path.read_text(encoding="utf-8")
    assert markets.json()["etf"]["summary"]["quote_state"] == "live"
    assert markets.json()["etf"]["summary"]["quote_symbol"] == "SPY"
    assert markets.json()["etf"]["summary"]["quote_symbols"] == "SPY,QQQ,IWM"
    assert markets.json()["etf"]["summary"]["quote_row_count"] == 3
    assert [row["symbol"] for row in markets.json()["etf"]["quotes"]] == [
        "SPY",
        "QQQ",
        "IWM",
    ]
    assert markets.json()["etf"]["quotes"][0]["provider_id"] == ALPHA_VANTAGE_PROVIDER_ID
    etf_gateway = next(
        gateway for gateway in markets.json()["asset_gateways"] if gateway["tab_id"] == "etf"
    )
    assert etf_gateway["state"] == "quote_available"
    assert any(
        provider["provider_id"] == ALPHA_VANTAGE_PROVIDER_ID
        and provider["health"]["state"] == "active"
        and provider["health"]["cache_id"] == "etf_quote_alphavantage_SPY"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["alpha_vantage_etf_quote_cache"].endswith("SPY.json")
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_alpha_vantage_watchlist_endpoints_accept_agent_symbol_lists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(
        server,
        "_alpha_vantage_secret_status_from_store",
        lambda: _secret_status(stored=True),
    )
    monkeypatch.setattr(server, "read_local_data_provider_secret", lambda *_, **__: _synthetic_alpha_value())
    monkeypatch.setattr(server, "ALPHA_VANTAGE_FETCHER", _fake_alpha_fetcher)
    client = TestClient(server.create_app())

    equities = client.post(
        "/api/alpha-vantage/equity-quotes/refresh",
        json={"symbols": "AAPL,MSFT,NVDA,MSFT"},
    )
    etfs = client.post(
        "/api/alpha-vantage/etf-quotes/refresh",
        json={"symbols": ["SPY", "QQQ", "IWM"]},
    )

    assert equities.status_code == 200
    assert equities.json()["summary"]["symbols"] == "AAPL,MSFT,NVDA"
    assert equities.json()["summary"]["row_count"] == 3
    assert "cache" not in equities.json()
    assert _synthetic_alpha_value() not in equities.text
    assert etfs.status_code == 200
    assert etfs.json()["summary"]["symbols"] == "SPY,QQQ,IWM"
    assert etfs.json()["summary"]["row_count"] == 3
    assert "cache" not in etfs.json()
    assert _synthetic_alpha_value() not in etfs.text
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_alpha_vantage_fx_quote_endpoint_uses_internal_secret_reader_and_writes_cache(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(
        server,
        "_alpha_vantage_secret_status_from_store",
        lambda: _secret_status(stored=True),
    )
    monkeypatch.setattr(server, "read_local_data_provider_secret", lambda *_, **__: _synthetic_alpha_value())
    monkeypatch.setattr(server, "ALPHA_VANTAGE_FX_FETCHER", _fake_alpha_fx_fetcher)
    client = TestClient(server.create_app())

    refreshed = client.post(
        "/api/alpha-vantage/fx-quotes/refresh",
        json={"pairs": "EURUSD,USD/JPY,GBP-USD"},
    )
    markets = client.post("/api/markets/fx/quote/refresh")
    providers = client.get("/api/providers")
    local_state = client.get("/api/local-state")

    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert refreshed.json()["summary"]["pairs"] == "EUR/USD,USD/JPY,GBP/USD"
    assert refreshed.json()["summary"]["row_count"] == 3
    assert "cache" not in refreshed.json()
    assert _synthetic_alpha_value() not in refreshed.text
    cache_path = (
        tmp_path
        / "market_data"
        / "fx"
        / "alphavantage"
        / "currency_exchange"
        / "EURUSD.json"
    )
    assert cache_path.is_file()
    assert (
        tmp_path / "market_data" / "fx" / "alphavantage" / "currency_exchange" / "USDJPY.json"
    ).is_file()
    assert (
        tmp_path / "market_data" / "fx" / "alphavantage" / "currency_exchange" / "GBPUSD.json"
    ).is_file()
    assert _synthetic_alpha_value() not in cache_path.read_text(encoding="utf-8")
    assert markets.json()["fx"]["quote_watchlist"]["summary"]["row_count"] == 3
    assert markets.json()["fx"]["quote_watchlist"]["summary"]["pairs"] == (
        "EUR/USD,USD/JPY,GBP/USD"
    )
    assert markets.json()["fx"]["quote_watchlist"]["rows"][0]["quote_semantics"] == (
        "quote_not_orderable"
    )
    fx_gateway = next(
        gateway for gateway in markets.json()["asset_gateways"] if gateway["tab_id"] == "fx"
    )
    assert fx_gateway["state"] == "fx_quote_available"
    assert any(
        provider["provider_id"] == ALPHA_VANTAGE_PROVIDER_ID
        and provider["health"]["state"] == "active"
        and provider["health"]["cache_id"] == "fx_quote_alphavantage_EURUSD"
        for provider in providers.json()["providers"]
    )
    assert local_state.json()["storage"]["alpha_vantage_fx_quote_cache"].endswith("EURUSD.json")
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_alpha_vantage_refresh_endpoint_without_key_is_explicitly_gated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post("/api/alpha-vantage/equity-quote/refresh")
    markets = client.post("/api/markets/stocks/quote/refresh")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "key_required"
    assert response.json()["quotes"] == []
    assert markets.json()["stocks"]["summary"]["quote_state"] == "key_required"
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert "offline_fixture" not in response.text


def test_alpha_vantage_etf_refresh_without_key_is_explicitly_gated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post("/api/alpha-vantage/etf-quote/refresh")
    markets = client.post("/api/markets/etf/quote/refresh")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "key_required"
    assert response.json()["summary"]["symbol"] == "SPY"
    assert response.json()["quotes"] == []
    assert markets.json()["etf"]["summary"]["quote_state"] == "key_required"
    assert markets.json()["etf"]["summary"]["quote_symbol"] == "SPY"
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert "offline_fixture" not in response.text


def test_alpha_vantage_fx_refresh_without_key_is_explicitly_gated(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post("/api/alpha-vantage/fx-quotes/refresh")
    markets = client.post("/api/markets/fx/quote/refresh")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "key_required"
    assert response.json()["summary"]["pairs"] == "EUR/USD,USD/JPY,GBP/USD"
    assert response.json()["quotes"] == []
    assert markets.json()["fx"]["quote_watchlist"]["status"]["state"] == "key_required"
    assert markets.json()["fx"]["quote_watchlist"]["summary"]["row_count"] == 0
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert "offline_fixture" not in response.text
