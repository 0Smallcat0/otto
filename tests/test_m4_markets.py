import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.markets import default_markets_layout, markets_payload
from src.local_terminal.storage import LocalStateStore


def _fake_tickers(symbols: list[str]) -> list[dict[str, str]]:
    return [
        {
            "symbol": symbol,
            "lastPrice": "100.00",
            "priceChange": "1.00",
            "priceChangePercent": "1.00",
            "highPrice": "110.00",
            "lowPrice": "90.00",
            "volume": "12345",
            "bidPrice": "99.50",
            "askPrice": "100.50",
            "openPrice": "99.00",
        }
        for symbol in symbols
    ]


def _crypto_detail_cache() -> dict[str, object]:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "status": {
            "source": "kraken_public",
            "state": "live",
            "last_update": now,
            "message": "Public Kraken detail refreshed.",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "provider_id": "kraken_public_market_data",
        },
        "provider": {
            "provider_id": "kraken_public_market_data",
            "label": "Kraken public market data",
            "source": "kraken_public",
            "state": "live",
            "cache_path": "market_data/crypto/BTCUSDT/15m.json",
        },
        "depth": {
            "bids": [{"price": "101.90", "quantity": "1"}],
            "asks": [{"price": "102.10", "quantity": "1"}],
        },
        "trades": [],
        "candles": [
            {
                "opened_at": "2026-05-23T00:00:00+00:00",
                "closed_at": "2026-05-23T00:15:00+00:00",
                "open": "100.00",
                "high": "104.00",
                "low": "99.00",
                "close": "102.00",
                "volume": "25.5",
                "interval": "15m",
                "closed": True,
            }
        ],
    }


def test_markets_payload_refresh_cache_and_visible_stale_fallback() -> None:
    live = markets_payload(
        default_markets_layout(),
        {},
        fetcher=_fake_tickers,
        refresh=True,
    )
    # A cache written seconds ago is still the live refresh, not a stale alarm.
    fresh = markets_payload(default_markets_layout(), live["cache"])
    aged_cache = {
        "status": {**live["cache"]["status"], "last_update": "2026-05-23T00:00:00+00:00"},
        "rows": live["cache"]["rows"],
    }
    stale = markets_payload(default_markets_layout(), aged_cache)

    assert live["status"]["source"] == "binance_public"
    assert live["status"]["state"] == "live"
    assert live["status"]["provider_id"] == "binance_spot_public"
    assert live["rows"][0]["symbol"] == "BTCUSDT"
    assert live["rows"][0]["price"] == "100.00"
    assert live["rows"][0]["source"] == "binance_public"
    assert fresh["status"]["state"] == "live"
    assert fresh["status"]["fallback_used"] is False
    assert stale["status"]["state"] == "stale"
    assert "stale public ticker cache" in stale["status"]["message"]
    assert {
        "public",
        "no_key_provider_ready",
    } <= {tab["state"] for tab in live["asset_tabs"]}
    assert {tab["tab_id"] for tab in live["asset_tabs"] if tab["state"] == "no_key_provider_ready"} >= {
        "etf",
        "fx",
        "commodities",
        "rates",
        "indexes",
        "regional",
    }
    stock_tab = next(tab for tab in live["asset_tabs"] if tab["tab_id"] == "stocks")
    assert stock_tab["state"] == "key_required"
    assert stock_tab["provider_id"] == "alphavantage_global_quote_optional_key"
    assert all(tab["state"] != "placeholder" for tab in live["asset_tabs"])
    assert "offline_fixture" not in str(live).lower()
    assert "offline_fixture" not in str(stale).lower()


def test_markets_payload_uses_public_crypto_detail_cache_when_ticker_cache_missing() -> None:
    payload = markets_payload(
        default_markets_layout(),
        {},
        _crypto_detail_cache(),
        refresh=False,
    )

    assert payload["status"]["source"] == "kraken_public"
    assert payload["status"]["provider_id"] == "kraken_public_market_data"
    assert payload["rows"][0]["symbol"] == "BTCUSDT"
    assert payload["rows"][0]["price"] == "102.00"
    assert payload["rows"][0]["bid"] == "101.90"
    assert payload["rows"][0]["ask"] == "102.10"
    assert payload["source_summary"]["available_rows"] == 1
    assert payload["source_summary"]["unavailable_rows"] == 2
    assert "offline_fixture" not in str(payload).lower()


def test_markets_payload_without_provider_data_has_unavailable_rows_not_fake_prices() -> None:
    payload = markets_payload(default_markets_layout(), {}, refresh=False)

    assert payload["status"]["source"] == "public_provider_unavailable"
    assert payload["status"]["state"] == "unavailable"
    assert {row["price"] for row in payload["rows"]} == {"N/A"}
    assert all(row["source"] == "public_provider_unavailable" for row in payload["rows"])
    assert "offline_fixture" not in str(payload).lower()
    assert all("mock" not in gateway["fallback"].lower() for gateway in payload["asset_gateways"])


def test_markets_api_saves_layout_and_refreshes_public_cache(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    monkeypatch.setattr(server, "MARKET_FETCHER", _fake_tickers)
    client = TestClient(server.create_app())

    saved = client.post(
        "/api/markets/layout",
        json={
            "auto_refresh": False,
            "asset_tab": "crypto",
            "columns": ["price", "ask", "name", "not-a-column"],
            "panels": [
                {
                    "panel_id": "custom",
                    "title": "Custom Crypto",
                    "column": 2,
                    "symbols": ["btcusdt", "eth-usdt", "BTCUSDT"],
                }
            ],
        },
    )
    refreshed = client.post("/api/markets/refresh")
    state = client.get("/api/local-state")

    assert saved.status_code == 200
    assert saved.json()["layout"]["columns"] == ["price", "ask", "name"]
    assert saved.json()["layout"]["panels"][0]["symbols"] == ["BTCUSDT", "ETHUSDT"]
    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert (tmp_path / "market_data" / "crypto_latest.json").is_file()
    assert state.json()["storage"]["markets"] == "workspace_layouts/markets.json"
    assert state.json()["storage"]["market_cache"] == "market_data/crypto_latest.json"
    assert "api_key" not in refreshed.text.lower()
    assert "private" not in refreshed.text.lower()


def test_markets_get_prefers_public_data_when_auto_refresh_is_enabled(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_markets_layout({**default_markets_layout(), "auto_refresh": True})
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "MARKET_FETCHER", _fake_tickers)
    client = TestClient(server.create_app())

    response = client.get("/api/markets")

    assert response.status_code == 200
    assert response.json()["status"]["state"] == "live"
    assert response.json()["status"]["source"] == "binance_public"
    assert (tmp_path / "market_data" / "crypto_latest.json").is_file()


def test_markets_get_uses_crypto_detail_cache_without_ticker_refresh(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_markets_layout({**default_markets_layout(), "auto_refresh": False})
    store.write_crypto_detail_cache(_crypto_detail_cache())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    response = client.get("/api/markets")

    assert response.status_code == 200
    assert response.json()["status"]["source"] == "kraken_public"
    assert response.json()["rows"][0]["price"] == "102.00"
    assert response.json()["source_summary"]["available_rows"] == 1
    assert "offline_fixture" not in response.text.lower()


def test_markets_read_layout_normalizes_legacy_missing_auto_refresh(tmp_path: Path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.markets_path.parent.mkdir(parents=True, exist_ok=True)
    store.markets_path.write_text(
        json.dumps(
            {
                "layout_id": "markets-default",
                "asset_tab": "crypto",
                "columns": ["price"],
                "panels": [
                    {
                        "panel_id": "legacy",
                        "title": "Legacy",
                        "symbols": ["BTCUSDT"],
                        "column": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    layout = store.read_markets_layout()

    assert layout["auto_refresh"] is False
    assert layout["columns"] == ["price"]
    assert layout["panels"][0]["symbols"] == ["BTCUSDT"]


def test_markets_layout_caps_panels_and_symbols(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/markets/layout",
        json={
            "auto_refresh": False,
            "asset_tab": "crypto",
            "columns": ["price"],
            "panels": [
                {
                    "panel_id": f"panel-{index}",
                    "title": f"Panel {index}",
                    "column": 1,
                    "symbols": [f"SYM{symbol_index}USDT" for symbol_index in range(20)],
                }
                for index in range(20)
            ],
        },
    )

    assert response.status_code == 200
    assert len(response.json()["layout"]["panels"]) == 9
    assert all(len(panel["symbols"]) == 12 for panel in response.json()["layout"]["panels"])
