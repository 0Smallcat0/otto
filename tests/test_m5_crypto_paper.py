import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.storage import LocalStateStore


def _public_market_cache() -> dict[str, object]:
    return {
        "status": {
            "source": "binance_public",
            "state": "live",
            "last_update": "2026-05-23T00:00:00Z",
            "message": "Public read-only Binance data refreshed.",
            "provider_id": "binance_spot_public",
            "cache_path": "market_data/crypto_latest.json",
            "fallback_used": False,
        },
        "rows": [
            {
                "symbol": "BTCUSDT",
                "price": "1000.00",
                "chg": "10.00",
                "chg_pct": "1.00",
                "high": "1010.00",
                "low": "990.00",
                "vol": "100",
                "bid": "999.00",
                "ask": "1001.00",
                "open": "990.00",
                "name": "Bitcoin / Tether",
                "source": "binance_public",
                "state": "live",
                "provider_id": "binance_spot_public",
                "retrieved_at": "2026-05-23T00:00:00Z",
                "cache_path": "market_data/crypto_latest.json",
            }
        ],
    }


def test_crypto_market_buy_fills_and_writes_local_paper_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_public_market_cache())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    response = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "0.1",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "paper"
    assert payload["submitted_order"]["status"] == "FILLED"
    assert payload["submitted_order"]["quote_source"] == "binance_public"
    assert payload["positions"][0]["symbol"] == "BTCUSDT"
    assert payload["fills"][0]["quote_source"] == "binance_public"
    assert payload["ledger"][0]["quote_price"] == "1000.00"
    assert payload["quote"]["source"] == "binance_public"
    assert payload["watchlist"][0]["source"] == "binance_public"
    assert float(payload["account"]["cash"]) < 100000
    assert (tmp_path / "artifacts" / "paper" / "paper_state.json").is_file()
    artifact_date = payload["fills"][0]["filled_at"][:10]
    orders_jsonl = tmp_path / "artifacts" / "paper" / artifact_date / "orders.jsonl"
    fills_jsonl = tmp_path / "artifacts" / "paper" / artifact_date / "fills.jsonl"
    account_jsonl = tmp_path / "artifacts" / "paper" / artifact_date / "account_snapshots.jsonl"
    assert orders_jsonl.is_file()
    assert fills_jsonl.is_file()
    assert account_jsonl.is_file()
    assert json.loads(fills_jsonl.read_text(encoding="utf-8").splitlines()[0])["quote_source"] == "binance_public"
    assert payload["safety"] == {
        "real_orders": False,
        "private_api_required": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives": False,
    }


def test_crypto_rejects_oversell_and_negative_cash(tmp_path: Path, monkeypatch) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_public_market_cache())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    oversell = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "SELL",
            "order_type": "MARKET",
            "quantity": "1",
        },
    )
    too_large = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "100",
        },
    )
    state = client.get("/api/crypto").json()

    assert oversell.status_code == 400
    assert oversell.json()["detail"] == "Cannot sell more than long paper position"
    assert too_large.status_code == 400
    assert too_large.json()["detail"] == "Insufficient paper cash"
    assert state["positions"] == []
    assert state["account"]["cash"] == "100000.00"
    assert "api_key" not in oversell.text.lower()
    assert "real order" not in too_large.text.lower()


def test_crypto_working_limit_order_is_paper_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "ETHUSDT",
            "side": "BUY",
            "order_type": "LIMIT",
            "quantity": "1",
            "limit_price": "1000",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["submitted_order"]["status"] == "WORKING"
    assert payload["submitted_order"]["quote_source"] == "public_provider_unavailable"
    assert payload["ledger"][0]["quote_source"] == "public_provider_unavailable"
    assert payload["fills"] == []
    assert payload["stats"]["open_orders"] == 1
    assert payload["stats"]["paper_only"] is True


def test_crypto_default_payload_has_structured_unavailable_state_not_fixture(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    payload = client.get("/api/crypto").json()

    assert payload["market"]["status"]["source"] == "public_provider_unavailable"
    assert payload["quote"]["source"] == "public_provider_unavailable"
    assert payload["chart"]["point_count"] == 0
    assert payload["artifacts"]["paper_state"] == "artifacts/paper/paper_state.json"
    assert "offline_fixture" not in str(payload).lower()


def test_crypto_rejects_unaffordable_working_buy_orders(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    limit_response = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "LIMIT",
            "quantity": "1",
            "limit_price": "1000000",
        },
    )
    stop_limit_response = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "STOP_LIMIT",
            "quantity": "1",
            "limit_price": "1000000",
            "stop_price": "900000",
        },
    )

    assert limit_response.status_code == 400
    assert limit_response.json()["detail"] == "Insufficient paper cash"
    assert stop_limit_response.status_code == 400
    assert stop_limit_response.json()["detail"] == "Insufficient paper cash"


def test_crypto_rejects_non_finite_and_extreme_numbers(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    nan_response = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "NaN",
        },
    )
    infinity_response = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "Infinity",
        },
    )
    extreme_response = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "1e10000",
        },
    )

    assert nan_response.status_code == 400
    assert nan_response.json()["detail"] == "Quantity must be finite"
    assert infinity_response.status_code == 400
    assert infinity_response.json()["detail"] == "Quantity must be finite"
    assert extreme_response.status_code == 400
    assert extreme_response.json()["detail"] == "Quantity is too large"


def test_paper_order_type_alias_and_unknown_field_rejection(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_public_market_cache())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    # "type" (the response field name) must round-trip as a LIMIT order, never
    # silently fall back to an instant MARKET fill.
    aliased = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "type": "LIMIT",
            "limit_price": "900",
            "quantity": "0.1",
        },
    )
    assert aliased.status_code == 200
    assert aliased.json()["submitted_order"]["type"] == "LIMIT"
    assert aliased.json()["submitted_order"]["status"] == "WORKING"

    # Any other unknown field is rejected instead of silently dropped.
    unknown = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "0.1",
            "limit_pricee": "900",
        },
    )
    assert unknown.status_code == 422

    # Numeric quantity is as valid as the string form.
    numeric = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": 0.1,
        },
    )
    assert numeric.status_code == 200
    assert numeric.json()["submitted_order"]["status"] == "FILLED"


def test_cancel_working_paper_order(tmp_path: Path, monkeypatch) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_public_market_cache())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    placed = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "LIMIT",
            "limit_price": "900",
            "quantity": "0.1",
        },
    )
    order_id = placed.json()["submitted_order"]["order_id"]
    assert placed.json()["submitted_order"]["status"] == "WORKING"

    cancelled = client.post("/api/crypto/orders/cancel", json={"order_id": order_id})
    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled_order"]["status"] == "CANCELLED"

    # A cancelled order cannot be cancelled twice, and unknown ids fail clean.
    again = client.post("/api/crypto/orders/cancel", json={"order_id": order_id})
    assert again.status_code == 400
    assert again.json()["detail"] == "Only WORKING paper orders can be cancelled"
    unknown = client.post("/api/crypto/orders/cancel", json={"order_id": "paper-missing"})
    assert unknown.status_code == 400
    assert unknown.json()["detail"] == "Unknown paper order id"
