"""P1 from the 2026-07-17 dogfood: the decision loop needs a ~1KB view.

The full paper payload runs 74k+ chars of order history, depth ladders, raw
trades, and candles. `GET /api/crypto/summary` returns exactly what the
agent loop needs: account with total P&L, positions marked to the freshest
known price, open orders, and per-symbol quote age against the fill gate's
TTL — small enough to read on every iteration.
"""

import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.crypto import (
    QUOTE_FRESHNESS_TTL_SECONDS,
    default_paper_state,
    paper_summary_payload,
    place_paper_order,
)
from otto.local_terminal.storage import LocalStateStore


def _stamp(age_seconds: float) -> str:
    return (
        datetime.now(tz=UTC) - timedelta(seconds=age_seconds)
    ).isoformat(timespec="seconds")


def _market_cache(retrieved_at: str, price: str = "64000.00000000") -> dict:
    return {
        "rows": [
            {
                "symbol": "BTCUSDT",
                "price": price,
                "chg": "100.0",
                "chg_pct": "0.15",
                "bid": "63999.9",
                "ask": "64000.1",
                "name": "Bitcoin / Tether",
                "source": "binance_public",
                "state": "live",
                "provider_id": "binance_spot_public",
                "retrieved_at": retrieved_at,
                "cache_path": "market_data/crypto_latest.json",
            }
        ],
        "status": {
            "source": "binance_public",
            "state": "live",
            "last_update": retrieved_at,
            "provider_id": "binance_spot_public",
            "cache_path": "market_data/crypto_latest.json",
        },
    }


def test_summary_is_compact_and_marks_positions_to_market() -> None:
    cache = _market_cache(_stamp(30), price="66000.00000000")
    state, _ = place_paper_order(
        default_paper_state(),
        {"symbol": "BTCUSDT", "side": "BUY", "order_type": "MARKET", "quantity": "0.001"},
        _market_cache(_stamp(10), price="64000.00000000"),
    )
    summary = paper_summary_payload(state, cache)

    assert len(json.dumps(summary)) < 3000  # vs 74k+ for the full payload

    position = summary["positions"][0]
    assert position["symbol"] == "BTCUSDT"
    assert position["last_price"] == "66000.00"
    assert float(position["unrealized_pnl"]) == 2.0  # 0.001 * (66000-64000)
    assert abs(float(position["unrealized_pnl_pct"]) - 3.125) < 0.01
    assert position["quote_age_seconds"] <= 60

    assert summary["freshness"]["all_fresh"] is True
    assert summary["freshness"]["ttl_seconds"] == QUOTE_FRESHNESS_TTL_SECONDS
    assert float(summary["account"]["total_pnl"]) != 0  # fees + mark move


def test_summary_flags_stale_quotes_for_the_gate() -> None:
    stale = _stamp(QUOTE_FRESHNESS_TTL_SECONDS + 120)
    summary = paper_summary_payload(default_paper_state(), _market_cache(stale))
    quote = summary["quotes"][0]
    assert quote["age_seconds"] > QUOTE_FRESHNESS_TTL_SECONDS
    assert quote["state"] == "stale_cache"
    assert summary["freshness"]["all_fresh"] is False
    assert summary["freshness"]["refresh_action"] == "crypto_refresh_public"


def test_summary_endpoint_and_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/crypto/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["safety"]["paper_only"] is True
    assert body["account"]["cash"] == "100000.00"

    contract = client.get("/api/agent-contract").json()
    actions = {action["action_id"]: action for action in contract["actions"]}
    entry = actions["paper_account_summary"]
    assert entry["method"] == "GET"
    assert entry["endpoint"] == "/api/crypto/summary"
    assert entry["local_mutation"] is False

    paper_route = next(r for r in contract["routes"] if r["route_id"] == "paper")
    assert paper_route["recommended_actions"][0] == "paper_account_summary"
