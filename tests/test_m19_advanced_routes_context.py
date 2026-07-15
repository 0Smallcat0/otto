from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore


def _now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _market_cache() -> dict[str, object]:
    now = _now()
    return {
        "status": {
            "source": "binance_public",
            "state": "live",
            "last_update": now,
            "provider_id": "binance_spot_public",
        },
        "rows": [
            {
                "symbol": "BTCUSDT",
                "price": "65000.00",
                "source": "binance_public",
                "provider_id": "binance_spot_public",
                "retrieved_at": now,
            }
        ],
    }


def _crypto_detail_cache() -> dict[str, object]:
    now = datetime.now(tz=UTC)
    return {
        "status": {
            "source": "binance_public",
            "state": "live",
            "last_update": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "message": "Public read-only detail cache.",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "provider_id": "binance_spot_public",
        },
        "provider": {
            "provider_id": "binance_spot_public",
            "auth_mode": "no-key",
            "safety_class": "public_read_only_market_data",
        },
        "candles": [
            {
                "opened_at": (now - timedelta(minutes=45 - 15 * index)).isoformat(
                    timespec="seconds"
                ),
                "closed_at": (now - timedelta(minutes=30 - 15 * index)).isoformat(
                    timespec="seconds"
                ),
                "close": str(65000 + index * 125),
                "closed": True,
            }
            for index in range(4)
        ],
        "depth": {"bids": [{"price": "65300", "quantity": "1"}], "asks": []},
        "trades": [],
    }


def _seed_context_store(tmp_path: Path) -> LocalStateStore:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_market_cache())
    store.write_crypto_detail_cache(_crypto_detail_cache())
    store.write_news_cache(
        {
            "fetched_at": _now(),
            "items": [
                {
                    "item_id": "m19-advanced-news",
                    "title": "Public cache update",
                    "source": "Public RSS",
                    "category": "CRPT",
                    "published_at": _now(),
                    "summary": "Source-attributed headline metadata.",
                }
            ],
        }
    )
    artifact = tmp_path / "artifacts" / "backtests" / "run-advanced" / "summary.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"return_pct": "2.4"}), encoding="utf-8")
    return store


def test_ai_chat_answers_from_provider_cache_without_broker_mutation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _seed_context_store(tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    initial = client.get("/api/ai-chat")
    session_id = client.post("/api/ai-chat/sessions", json={"name": "Provider Review"}).json()[
        "active_session_id"
    ]
    response = client.post(
        "/api/ai-chat/messages",
        json={
            "session_id": session_id,
            "content": "Summarize the provider cache and linked candle artifact.",
            "linked_artifacts": ["market_data/crypto/BTCUSDT/15m.json"],
        },
    )

    payload = response.json()
    assistant = payload["messages"][-1]
    assert initial.status_code == 200
    assert initial.json()["context"]["summary"]["ready_source_count"] >= 3
    assert response.status_code == 200
    assert payload["context"]["summary"]["primary_cache_path"] == "market_data/crypto_latest.json"
    assert assistant["role"] == "assistant"
    assert "Local context brief" in assistant["content"]
    assert "Provider/cache context:" in assistant["content"]
    assert "Focused local sources:" in assistant["content"]
    assert "Crypto detail cache" in assistant["content"]
    assert "market_data/crypto/BTCUSDT/15m.json" in assistant["content"]
    assert "cannot place orders" in assistant["content"]
    assert payload["safety"]["broker_mutation"] is False
    assert payload["messages"][0]["linked_artifacts"][0]["read_mode"] == "read_only"


def test_advanced_routes_write_outputs_with_shared_context(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = _seed_context_store(tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    nodes = client.post("/api/nodes/template", json={"template_id": "template-provider-context"})
    workflow_id = nodes.json()["active_workflow_id"]
    dry_run = client.post("/api/nodes/dry-run", json={"workflow_id": workflow_id})
    code = client.post("/api/code/context-notebook")
    qlab = client.post("/api/quant-lab/run-preview", json={"module_slug": "feature-engineering"})
    qlib = client.post("/api/quantlib/compute", json={"action_id": "bs-price"})

    dry_run_plan = dry_run.json()["dry_run_result"]
    code_notebook = code.json()["active_notebook"]
    qlab_result = qlab.json()["preview_result"]
    qlib_result = qlib.json()["calculation_result"]

    assert nodes.status_code == 200
    assert dry_run.status_code == 200
    assert dry_run_plan["context"]["summary"]["ready_source_count"] >= 3
    assert dry_run_plan["context"]["summary"]["artifact_count"] >= 1
    assert any(
        artifact["kind"] == "backtest"
        and artifact["path"] == "artifacts/backtests/run-advanced/summary.json"
        for artifact in dry_run_plan["context"]["artifacts"]
    )
    assert any(step["action"] == "read_provider_cache" for step in dry_run_plan["steps"])
    assert any(
        step["context_source"] == "market_data/crypto/BTCUSDT/15m.json"
        for step in dry_run_plan["steps"]
    )
    assert any(
        step["context_source"] == "artifacts/backtests/run-advanced/summary.json"
        for step in dry_run_plan["steps"]
    )
    assert (tmp_path / "artifacts" / "workflows" / workflow_id / "dry_run.json").is_file()

    assert code.status_code == 200
    assert code_notebook["name"] == "Provider Context Notebook"
    assert code_notebook["path"].startswith("artifacts/code_workspace/")
    assert "provider_cache_paths" in code_notebook["cells"][1]["source"]
    assert (tmp_path / code_notebook["path"]).is_file()

    assert qlab.status_code == 200
    assert qlab_result["inputs"]["price_data"] == "65000,65125,65250,65375"
    assert qlab_result["output"]["context"]["ready_source_count"] >= 3
    assert qlab_result["output"]["output_mode"] == "local_context_bundle"
    assert any(
        source["cache_path"] == "market_data/crypto_latest.json"
        for source in qlab_result["output"]["source_provenance"]
    )
    assert any(
        artifact["path"] == "artifacts/backtests/run-advanced/summary.json"
        for artifact in qlab_result["output"]["artifact_inputs"]
    )
    assert (tmp_path / qlab_result["artifacts"]["output"]).is_file()
    assert (tmp_path / qlab_result["artifacts"]["context"]).is_file()
    assert (tmp_path / qlab_result["artifacts"]["manifest"]).is_file()

    assert qlib.status_code == 200
    assert qlib_result["request_body"]["spot"] == 65000.0
    assert (
        qlib_result["response_body"]["context"]["primary_cache_path"]
        == "market_data/crypto_latest.json"
    )
    assert qlib_result["response_body"]["output_mode"] == "local_context_calculation"
    assert any(
        source["cache_path"] == "market_data/crypto_latest.json"
        for source in qlib_result["response_body"]["source_provenance"]
    )
    assert any(
        artifact["path"] == "artifacts/backtests/run-advanced/summary.json"
        for artifact in qlib_result["response_body"]["artifact_inputs"]
    )
    assert (tmp_path / qlib_result["artifacts"]["response"]).is_file()
    assert (tmp_path / qlib_result["artifacts"]["context"]).is_file()
    assert (tmp_path / qlib_result["artifacts"]["manifest"]).is_file()
