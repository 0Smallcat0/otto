from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from otto.local_terminal import crypto_data
from otto.local_terminal import server
from otto.local_terminal.crypto_data import crypto_detail_payload
from otto.local_terminal.storage import LocalStateStore


def _tickers(symbols: list[str]) -> list[dict[str, str]]:
    return [
        {
            "symbol": symbol,
            "lastPrice": "100.00" if symbol == "BTCUSDT" else "50.00",
            "priceChange": "1.00",
            "priceChangePercent": "1.00",
            "highPrice": "110.00",
            "lowPrice": "90.00",
            "volume": "1000",
            "bidPrice": "99.50",
            "askPrice": "100.50",
            "openPrice": "99.00",
        }
        for symbol in symbols
    ]


def _detail(symbol: str = "BTCUSDT", interval: str = "15m") -> dict[str, Any]:
    now = datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    return {
        "status": {
            "source": "binance_public",
            "state": "live",
            "last_update": now,
            "message": "Public read-only Binance depth, trades, and closed candles refreshed.",
            "symbol": symbol,
            "timeframe": interval,
            "provider_id": "binance_spot_public",
            "fallback_used": False,
        },
        "provider": {
            "provider_id": "binance_spot_public",
            "label": "Binance Spot public market data",
            "source": "binance_public",
            "state": "live",
            "retrieved_at": now,
            "docs_url": "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints",
            "cache_path": f"market_data/crypto/{symbol}/{interval}.json",
            "message": "No-key public market-data endpoints only.",
            "symbol": symbol,
            "timeframe": interval,
            "fallback_used": False,
            "auth_mode": "no-key",
            "safety_class": "public_read_only_market_data",
        },
        "depth": {
            "bids": [{"price": "99.90", "quantity": "1.2"}],
            "asks": [{"price": "100.10", "quantity": "1.1"}],
        },
        "trades": [
            {
                "trade_id": "1",
                "price": "100.00",
                "quantity": "0.5",
                "quote_quantity": "50.00",
                "traded_at": now,
                "side": "BUY",
                "source": "binance_public",
            }
        ],
        "candles": _candles(interval),
    }


def _candles(interval: str) -> list[dict[str, Any]]:
    start = datetime.now(tz=UTC) - timedelta(hours=12)
    rows = []
    for index in range(40):
        opened = start + timedelta(minutes=15 * index)
        base = 100 + index
        rows.append(
            {
                "opened_at": opened.isoformat(timespec="seconds"),
                "closed_at": (opened + timedelta(minutes=15)).isoformat(timespec="seconds"),
                "open": f"{base:.2f}",
                "high": f"{base + 2:.2f}",
                "low": f"{base - 2:.2f}",
                "close": f"{base + 1:.2f}",
                "volume": "10",
                "interval": interval,
                "closed": True,
            }
        )
    return rows


def test_crypto_detail_payload_refreshes_public_cache_without_secrets() -> None:
    payload = crypto_detail_payload({}, fetcher=lambda **kwargs: _detail(**kwargs), refresh=True)

    assert payload["status"]["source"] == "binance_public"
    assert payload["provider"]["auth_mode"] == "no-key"
    assert payload["depth"]["bids"]
    assert payload["trades"][0]["source"] == "binance_public"
    assert len(payload["candles"]) == 40
    assert "api_key" not in str(payload).lower()
    assert "private" not in payload["provider"]["auth_mode"].lower()


def test_public_crypto_detail_chain_falls_back_to_alternate_no_key_provider(monkeypatch) -> None:
    def _raise(**_kwargs):
        raise TimeoutError()

    def _kraken(**kwargs):
        payload = _detail(symbol=kwargs["symbol"], interval=kwargs["interval"])
        payload["status"] = {
            **payload["status"],
            "source": "kraken_public",
            "provider_id": "kraken_public_market_data",
        }
        payload["provider"] = {
            **payload["provider"],
            "source": "kraken_public",
            "provider_id": "kraken_public_market_data",
            "label": "Kraken public market data",
        }
        return payload

    monkeypatch.setattr(crypto_data, "fetch_binance_crypto_detail", _raise)
    monkeypatch.setattr(crypto_data, "fetch_kraken_crypto_detail", _kraken)

    payload = crypto_data.fetch_public_crypto_detail(symbol="BTCUSDT", interval="15m")

    assert payload["provider"]["source"] == "kraken_public"
    assert payload["provider"]["auth_mode"] == "no-key"


def test_crypto_refresh_api_writes_public_detail_cache_and_updates_payload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "MARKET_FETCHER", _tickers)
    monkeypatch.setattr(server, "CRYPTO_DETAIL_FETCHER", lambda **kwargs: _detail(**kwargs))
    client = TestClient(server.create_app())

    response = client.post("/api/crypto/refresh", json={"symbol": "BTCUSDT", "timeframe": "15m"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"]["status"]["source"] == "binance_public"
    assert payload["provider"]["source"] == "binance_public"
    assert payload["provider"]["state"] == "live"
    assert payload["quote"]["source"] == "binance_public"
    assert payload["watchlist"][0]["source"] == "binance_public"
    assert payload["chart"]["point_count"] == 40
    assert payload["artifacts"]["fills_jsonl"] == "artifacts/paper/{date}/fills.jsonl"
    assert payload["depth"]["bids"][0]["price"] == "99.90"
    assert payload["trades"][0]["source"] == "binance_public"
    assert len(payload["candles"]) == 40
    assert (tmp_path / "market_data" / "crypto" / "BTCUSDT" / "15m.json").is_file()

    provider_cache = client.get("/api/providers/cache").json()
    detail_cache = next(cache for cache in provider_cache["caches"] if cache["cache_id"] == "crypto_public_detail")
    assert detail_cache["state"] == "active"
    assert detail_cache["runtime_source"] == "binance_public"


def test_crypto_uses_public_detail_cache_when_ticker_refresh_is_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "MARKET_FETCHER", lambda _symbols: (_ for _ in ()).throw(TimeoutError()))
    monkeypatch.setattr(server, "CRYPTO_DETAIL_FETCHER", lambda **kwargs: _detail(**kwargs))
    client = TestClient(server.create_app())

    refreshed = client.post("/api/crypto/refresh", json={"symbol": "BTCUSDT", "timeframe": "15m"}).json()
    assert refreshed["market"]["status"]["source"] == "binance_public"
    assert refreshed["market"]["status"]["state"] == "live"
    assert refreshed["market"]["rows"][0]["price"] == "140.00"

    order = client.post(
        "/api/crypto/orders",
        json={"symbol": "BTCUSDT", "timeframe": "15m", "side": "BUY", "order_type": "MARKET", "quantity": "1"},
    ).json()
    assert order["submitted_order"]["status"] == "FILLED"
    assert order["submitted_order"]["quote_source"] == "binance_public"
    assert order["fills"][0]["price"] == "140.00"
    assert order["fills"][0]["quote_provider_id"] == "binance_spot_public"
    assert order["stats"]["last_fill_source"] == "binance_public"


def test_backtest_uses_provider_closed_candle_cache_when_present(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_crypto_detail_cache(_detail())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    response = client.post("/api/backtest/run", json={"symbol": "BTCUSDT", "timeframe": "15m"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["manifest"]["provider"] == "public_crypto_closed_candle_cache"
    assert payload["manifest"]["data_source"] == "binance_public"
    assert payload["manifest"]["provider_id"] == "binance_spot_public"
    assert len(payload["manifest"]["cache_snapshot_hash"]) == 64
    assert payload["manifest"]["deterministic_fallback"] is False
    assert payload["summary"]["data_source"] == "binance_public"
    assert payload["summary"]["deterministic_fallback"] is False
    assert payload["metrics"]["data_provider"] == "public_crypto_closed_candle_cache"
    assert payload["provenance"]["source_last_closed_at"]
    assert payload["summary"]["closed_candles"] == 40
    data_snapshot = tmp_path / payload["artifact_dir"] / "data_snapshot.json"
    snapshot = data_snapshot.read_text(encoding="utf-8")
    assert "binance_public" in snapshot
    assert "cache_snapshot_hash" in snapshot
    assert (tmp_path / payload["artifact_dir"] / "provenance.json").is_file()


def test_backtest_defaults_expose_provider_source_tabs_when_cache_exists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_crypto_detail_cache(_detail())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    payload = client.get("/api/backtest").json()

    assert payload["provider"] == "public_crypto_closed_candle_cache"
    assert payload["provider_status"]["source"] == "binance_public"
    assert payload["provider_status"]["cache_path"] == "market_data/crypto/BTCUSDT/15m.json"
    assert "Data Source" in payload["result_tabs"]
    assert "Artifacts" in payload["result_tabs"]
    assert "Walk-Forward" in payload["commands"]
