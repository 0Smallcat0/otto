"""M27-R3 — read-only candle endpoint feeding the expanded-row charts."""

import json

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.storage import LocalStateStore


def _seed_candles(store: LocalStateStore, symbol: str = "BTCUSDT", timeframe: str = "15m") -> None:
    path = store.crypto_detail_cache_path(symbol, timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)
    candles = [
        {
            "open": f"{100 + i}.00",
            "high": f"{101 + i}.00",
            "low": f"{99 + i}.00",
            "close": f"{100.5 + i}",
            "closed": True,
            "closed_at": f"2026-07-06T{10 + (i % 12):02d}:14:59+00:00",
        }
        for i in range(130)
    ]
    path.write_text(json.dumps({"candles": candles, "status": {}}), encoding="utf-8")


def test_candles_endpoint_serves_bounded_cache(tmp_path, monkeypatch) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    _seed_candles(store)
    client = TestClient(server.create_app())

    body = client.get("/api/markets/candles/BTCUSDT").json()
    assert body["symbol"] == "BTCUSDT"
    assert body["timeframe"] == "15m"
    assert body["count"] == 130
    assert len(body["candles"]) == 120  # bounded to the newest 120
    assert body["safety"]["external_calls"] is False

    # unknown timeframe falls back to 15m instead of 404ing
    fallback = client.get("/api/markets/candles/btcusdt?timeframe=2h")
    assert fallback.status_code == 200
    assert fallback.json()["timeframe"] == "15m"


def test_candles_endpoint_404s_without_cache(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    assert client.get("/api/markets/candles/ETHUSDT").status_code == 404
    assert client.get("/api/markets/candles/..%2fescape").status_code == 404
