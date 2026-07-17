from datetime import UTC, datetime

import json
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.portfolio import portfolio_report_health_payload, portfolio_report_index
from otto.local_terminal.storage import LocalStateStore


def _public_market_cache() -> dict[str, object]:
    return {
        "status": {
            "source": "binance_public",
            "state": "live",
            "last_update": datetime.now(UTC).isoformat(timespec="seconds"),
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
                "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "cache_path": "market_data/crypto_latest.json",
            }
        ],
    }


def _offline_fixture_market_cache() -> dict[str, object]:
    return {
        "status": {
            "source": "offline_fixture",
            "state": "offline",
            "last_update": datetime.now(UTC).isoformat(timespec="seconds"),
            "provider_id": "",
            "cache_path": "market_data/crypto_latest.json",
        },
        "rows": [
            {
                "symbol": "BTCUSDT",
                "price": "99999.00",
                "chg_pct": "5.00",
                "source": "offline_fixture",
                "state": "offline",
                "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "cache_path": "market_data/crypto_latest.json",
            }
        ],
    }


def _strategy() -> dict[str, object]:
    return {
        "name": "Local Breakout",
        "description": "Dry-run closed-candle strategy",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "entry_conditions": ["close above 20 period high"],
        "exit_conditions": ["fast SMA crosses below slow SMA"],
        "risk_settings": {
            "stop_loss_pct": "4",
            "take_profit_pct": "10",
            "trailing_stop_pct": "0",
        },
        "backtest": {
            "initial_cash": "50000",
            "fast_window": 3,
            "slow_window": 5,
            "fee_rate": "0.001",
            "slippage_bps": "2",
        },
    }


def test_portfolio_create_writes_local_state_and_exports(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/portfolio/create",
        json={"name": "Local Book", "owner": "Research Desk", "currency": "USD"},
    )
    state = client.get("/api/local-state")
    exported = client.get("/api/portfolio/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["first_use"] is False
    assert payload["portfolio"]["name"] == "Local Book"
    assert payload["portfolio"]["source"] == "manual"
    assert payload["positions"] == []
    assert payload["summary"]["portfolio_value"] == "0.00"
    assert (tmp_path / "artifacts" / "portfolio" / "portfolio_state.json").is_file()
    assert state.json()["storage"]["portfolio_state"] == "artifacts/portfolio/portfolio_state.json"
    assert exported.status_code == 200
    assert exported.json()["name"] == "Local Book"
    assert exported.json()["export_artifacts"]["manifest"].startswith(
        "artifacts/portfolio/exports/"
    )
    assert (tmp_path / exported.json()["export_artifacts"]["manifest"]).is_file()


def test_portfolio_demo_has_dense_workspace_and_local_safety(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post("/api/portfolio/demo")

    assert response.status_code == 200
    payload = response.json()
    assert payload["portfolio"]["source"] == "demo"
    assert len(payload["positions"]) == 12
    assert all("E" not in position["quantity"] for position in payload["positions"])
    assert all("E" not in transaction["quantity"] for transaction in payload["transactions"])
    assert payload["summary"]["position_count"] == 12
    assert payload["summary"]["transaction_count"] == 12
    assert payload["summary"]["portfolio_value"] != "0.00"
    assert payload["toolbar"][:3] == ["BUY", "SELL", "DIV"]
    assert payload["tabs"] == [
        "Performance",
        "Positions",
        "Exposure",
        "Pricing",
        "Risk",
        "Allocation",
        "Correlation",
        "Transactions",
        "Report",
        "Artifacts",
    ]
    assert payload["allocation"]
    assert payload["exposure_map"][0]["symbol"]
    assert payload["exposure_map"][0]["concentration_state"] in {"normal", "watch", "high"}
    assert "beta_contribution" in payload["exposure_map"][0]
    assert payload["performance"]
    assert payload["performance"][1]["period_return_pct"]
    assert payload["correlation"]["symbols"]
    assert payload["risk"][0]["metric"] == "concentration_pct"
    assert payload["pricing"]["status"]["source"] == "provider_unavailable"
    assert payload["pricing"]["status"]["local_snapshot_count"] == "12"
    assert payload["report"]["status"] == "not_generated"
    assert payload["safety"] == {
        "real_orders": False,
        "private_api_required": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives": False,
        "buy_sell_route": "crypto_paper",
    }


def test_portfolio_report_writes_local_analytics_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    client.post("/api/portfolio/demo")

    response = client.post("/api/portfolio/report")

    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["status"] == "generated"
    assert payload["portfolio"]["last_report"]["safety"]["local_artifact_only"] is True
    assert payload["portfolio"]["last_report"]["safety"]["real_orders"] is False
    assert payload["portfolio"]["last_report"]["safety"]["real_balance"] is False
    assert payload["report"]["exposure_row_count"] == str(len(payload["exposure_map"]))
    artifact_files = payload["report"]["artifact_files"]
    assert artifact_files["summary"].startswith("artifacts/portfolio/reports/")
    assert artifact_files["risk"].endswith("/risk.json")
    assert artifact_files["performance"].endswith("/performance.csv")
    assert artifact_files["exposure"].endswith("/exposure.csv")
    assert artifact_files["lineage"].endswith("/lineage.json")
    assert artifact_files["artifact_health"].endswith("/artifact_health.json")
    assert artifact_files["report"].endswith("/report.md")
    for artifact in artifact_files.values():
        assert (tmp_path / artifact).is_file()
    lineage = json.loads((tmp_path / artifact_files["lineage"]).read_text(encoding="utf-8"))
    health = json.loads(
        (tmp_path / artifact_files["artifact_health"]).read_text(encoding="utf-8")
    )
    manifest = json.loads((tmp_path / artifact_files["manifest"]).read_text(encoding="utf-8"))
    assert lineage["contract"] == "portfolio_report_lineage_v1"
    assert health["status"] == "no_linked_artifacts"
    assert health["safety"]["destructive_actions_enabled"] is False
    assert manifest["artifact_contract"] == "local_portfolio_report_artifacts_v3"
    assert manifest["exposure_row_count"] == len(payload["exposure_map"])
    exposure_text = (tmp_path / artifact_files["exposure"]).read_text(encoding="utf-8")
    assert "beta_contribution" in exposure_text
    assert "concentration_state" in exposure_text
    report_text = (tmp_path / artifact_files["report"]).read_text(encoding="utf-8")
    assert "local artifact only" in report_text
    assert "no live orders" in report_text
    assert "## Exposure" in report_text
    assert payload["report_index"]["mode"] == "local_portfolio_report_index"
    assert payload["report_index"]["summary"]["report_count"] == 1
    assert payload["report_index"]["summary"]["active_report_id"] == payload["report"][
        "report_id"
    ]
    assert payload["report_index"]["reports"][0]["complete"] is True
    assert payload["report_health"]["mode"] == "metadata_only_portfolio_report_health"
    assert payload["report_health"]["summary"]["report_count"] == 1
    assert payload["report_health"]["summary"]["complete_count"] == 1
    assert payload["report_health"]["reports"][0]["supervision_ready"] is True
    assert payload["report_index"]["safety"]["file_content_read"] is False


def test_portfolio_report_index_tracks_local_artifacts_without_content_reads(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    client.post("/api/portfolio/demo")
    written = client.post("/api/portfolio/report").json()

    payload = client.get("/api/portfolio/reports").json()

    assert payload["mode"] == "local_portfolio_report_index"
    assert payload["contract"] == "portfolio_report_index_v1"
    assert payload["summary"]["report_count"] == 1
    assert payload["summary"]["complete_report_count"] == 1
    assert payload["summary"]["active_report_id"] == written["report"]["report_id"]
    assert payload["reports"][0]["active_portfolio_report"] is True
    assert payload["reports"][0]["artifact_count"] == 9
    assert payload["reports"][0]["missing_artifact_count"] == 0
    assert payload["reports"][0]["files"][0]["bytes"] > 0
    assert payload["recovery_queue"] == []
    assert payload["recommended_actions"][0]["action_id"] == "portfolio_report"
    assert payload["safety"]["metadata_only"] is True
    assert payload["safety"]["file_content_read"] is False
    assert payload["safety"]["destructive_actions_enabled"] is False
    assert payload["safety"]["real_balance"] is False
    assert payload["safety"]["live_trading"] is False


def test_portfolio_report_index_reports_missing_artifact_recovery(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    client.post("/api/portfolio/demo")
    written = client.post("/api/portfolio/report").json()
    risk_path = tmp_path / written["report"]["artifact_files"]["risk"]
    risk_path.unlink()

    payload = portfolio_report_index(tmp_path, server.STORE.read_portfolio_state())

    assert payload["summary"]["report_count"] == 1
    assert payload["summary"]["incomplete_report_count"] == 1
    assert payload["summary"]["missing_artifact_count"] == 1
    assert payload["reports"][0]["complete"] is False
    assert payload["reports"][0]["missing_artifact_count"] == 1
    assert payload["recovery_queue"][0]["recommended_action"] == "portfolio_report"
    assert payload["recovery_queue"][0]["destructive_action_required"] is False


def test_portfolio_report_health_reports_expected_files_without_content_reads(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    client.post("/api/portfolio/demo")
    written = client.post("/api/portfolio/report").json()

    response = client.get("/api/portfolio/report-health")
    defaults = client.get("/api/portfolio").json()

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "metadata_only_portfolio_report_health"
    assert payload["contract"] == "portfolio_report_health_v1"
    assert payload["summary"]["report_count"] == 1
    assert payload["summary"]["complete_count"] == 1
    assert payload["summary"]["partial_count"] == 0
    assert payload["summary"]["missing_artifact_count"] == 0
    assert payload["summary"]["supervision_ready_count"] == 1
    assert payload["summary"]["expected_artifact_count"] == 9
    assert payload["summary"] == defaults["report_health"]["summary"]
    row = payload["reports"][0]
    assert row["report_id"] == written["report"]["report_id"]
    assert row["artifact_dir"] == f"artifacts/portfolio/reports/{row['report_id']}"
    assert row["health_state"] == "complete"
    assert row["expected_count"] == 9
    assert row["present_count"] == 9
    assert row["missing_count"] == 0
    assert row["missing_artifacts"] == []
    assert row["manifest_path"].endswith("/manifest.json")
    assert row["supervision_ready"] is True
    assert payload["recommended_actions"][0]["action_id"] == "portfolio_report_index"
    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["file_content_read"] is False
    assert payload["safety"]["artifact_content_indexing"] is False
    assert payload["safety"]["writes_local_artifacts"] is False
    assert payload["safety"]["automatic_repair_enabled"] is False
    assert payload["safety"]["destructive_actions_enabled"] is False
    assert payload["safety"]["real_orders"] is False
    assert payload["safety"]["real_balance"] is False
    assert payload["safety"]["live_trading"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()

    (tmp_path / written["report"]["artifact_files"]["risk"]).unlink()
    partial = portfolio_report_health_payload(tmp_path, server.STORE.read_portfolio_state())

    assert partial["summary"]["complete_count"] == 0
    assert partial["summary"]["partial_count"] == 1
    assert partial["summary"]["missing_artifact_count"] == 1
    assert partial["reports"][0]["health_state"] == "partial_missing_artifacts"
    assert partial["reports"][0]["missing_artifacts"] == ["risk.json"]
    assert partial["reports"][0]["supervision_ready"] is False
    assert partial["recovery_queue"][0]["destructive_action_required"] is False


def test_portfolio_import_create_new_and_merge_modes(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    imported = {
        "name": "Imported Book",
        "owner": "Local User",
        "currency": "USD",
        "positions": [
            {
                "symbol": "BTCUSDT",
                "name": "Bitcoin",
                "asset_class": "Crypto",
                "sector": "Digital Assets",
                "quantity": "1",
                "avg_cost": "60000",
                "last_price": "65000",
                "currency": "USD",
            }
        ],
        "transactions": [
            {
                "date": "2026-05-22T00:00:00Z",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": "1",
                "price": "60000",
            }
        ],
    }

    create_new = client.post(
        "/api/portfolio/import",
        json={"mode": "create_new", "portfolio": imported},
    )
    active_id = create_new.json()["active_portfolio_id"]
    merge = client.post(
        "/api/portfolio/import",
        json={"mode": "merge", "target_portfolio_id": active_id, "portfolio": imported},
    )

    assert create_new.status_code == 200
    assert create_new.json()["portfolio"]["source"] == "import_json"
    assert create_new.json()["positions"][0]["quantity"] == "1"
    assert merge.status_code == 200
    assert merge.json()["active_portfolio_id"] == active_id
    assert merge.json()["positions"][0]["quantity"] == "2"
    assert merge.json()["summary"]["transaction_count"] == 2
    assert merge.json()["portfolio"]["source"] == "import_json"
    transaction_ids = [
        transaction["transaction_id"] for transaction in merge.json()["transactions"]
    ]
    assert len(transaction_ids) == len(set(transaction_ids))


def test_portfolio_import_rejects_unsafe_rows_without_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    negative = client.post(
        "/api/portfolio/import",
        json={
            "mode": "create_new",
            "portfolio": {
                "name": "Bad Book",
                "owner": "Local User",
                "currency": "USD",
                "positions": [{"symbol": "AAPL", "quantity": "-1", "avg_cost": "100"}],
            },
        },
    )
    oversell = client.post(
        "/api/portfolio/import",
        json={
            "mode": "create_new",
            "portfolio": {
                "name": "Bad Transactions",
                "owner": "Local User",
                "currency": "USD",
                "transactions": [
                    {"symbol": "AAPL", "side": "SELL", "quantity": "1", "price": "100"}
                ],
            },
        },
    )

    assert negative.status_code == 400
    assert negative.json()["detail"] == "Position quantity must be positive"
    assert oversell.status_code == 400
    assert oversell.json()["detail"] == "Transaction sell exceeds current holding"
    assert not (tmp_path / "artifacts" / "portfolio").exists()


def test_portfolio_import_rejects_silent_drop_and_limit_cases(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    non_object_position = client.post(
        "/api/portfolio/import",
        json={
            "mode": "create_new",
            "portfolio": {
                "name": "Bad Rows",
                "owner": "Local User",
                "currency": "USD",
                "positions": ["AAPL"],
            },
        },
    )
    too_many_transactions = client.post(
        "/api/portfolio/import",
        json={
            "mode": "create_new",
            "portfolio": {
                "name": "Too Many",
                "owner": "Local User",
                "currency": "USD",
                "transactions": [
                    {"symbol": "AAPL", "side": "BUY", "quantity": "1", "price": "100"}
                    for _ in range(501)
                ],
            },
        },
    )
    contradiction = client.post(
        "/api/portfolio/import",
        json={
            "mode": "create_new",
            "portfolio": {
                "name": "Contradictory Book",
                "owner": "Local User",
                "currency": "USD",
                "positions": [{"symbol": "AAPL", "quantity": "2", "avg_cost": "100"}],
                "transactions": [
                    {"symbol": "AAPL", "side": "BUY", "quantity": "1", "price": "100"}
                ],
            },
        },
    )

    assert non_object_position.status_code == 400
    assert non_object_position.json()["detail"] == "Position rows must be objects"
    assert too_many_transactions.status_code == 400
    assert too_many_transactions.json()["detail"] == "Transactions exceed limit of 500"
    assert contradiction.status_code == 400
    assert contradiction.json()["detail"] == "Positions do not match transaction holdings"
    assert not (tmp_path / "artifacts" / "portfolio").exists()


def test_portfolio_rejects_corrupt_existing_state_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    state_path = tmp_path / "artifacts" / "portfolio" / "portfolio_state.json"
    state_path.parent.mkdir(parents=True)
    corrupt = {
        "active_portfolio_id": "bad",
        "portfolios": {
            "bad": {
                "name": "Corrupt",
                "owner": "Local User",
                "currency": "USD",
                "positions": [{"symbol": "AAPL", "quantity": "-1", "avg_cost": "100"}],
            }
        },
    }
    state_path.write_text(json.dumps(corrupt, sort_keys=True), encoding="utf-8")
    client = TestClient(server.create_app())

    response = client.post(
        "/api/portfolio/create",
        json={"name": "New Book", "owner": "Local User", "currency": "USD"},
    )

    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "Stored portfolio bad is invalid: Position quantity must be positive"
    )
    assert json.loads(state_path.read_text(encoding="utf-8")) == corrupt


def test_portfolio_rejects_parse_corrupt_existing_state_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    state_path = tmp_path / "artifacts" / "portfolio" / "portfolio_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not-json", encoding="utf-8")
    client = TestClient(server.create_app())

    readonly = client.get("/api/portfolio")
    response = client.post(
        "/api/portfolio/create",
        json={"name": "New Book", "owner": "Local User", "currency": "USD"},
    )

    assert readonly.status_code == 200
    assert readonly.json()["invalid_portfolios"] == {
        "portfolio_state.json": "Invalid portfolio state JSON"
    }
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Portfolio state is invalid: portfolio_state.json: Invalid portfolio state JSON"
    )
    assert state_path.read_text(encoding="utf-8") == "{not-json"


def test_portfolio_links_paper_ledger_without_live_order_bypass(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_public_market_cache())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())
    order = client.post(
        "/api/crypto/orders",
        json={
            "symbol": "BTCUSDT",
            "side": "BUY",
            "order_type": "MARKET",
            "quantity": "0.01",
        },
    )

    linked = client.post("/api/portfolio/link-paper")

    assert order.status_code == 200
    assert linked.status_code == 200
    payload = linked.json()
    assert payload["portfolio"]["source"] == "paper_ledger"
    assert payload["portfolio"]["linked_artifacts"][0] == "artifacts/paper/paper_state.json"
    assert any(path.endswith("/fills.jsonl") for path in payload["portfolio"]["linked_artifacts"])
    assert payload["positions"][0]["symbol"] == "BTCUSDT"
    assert payload["positions"][0]["last_price"] == "1000.00"
    assert payload["positions"][0]["price_source"] == "binance_public"
    assert payload["pricing"]["status"]["provider_price_count"] == "1"
    assert payload["transactions"][0]["source"] == "paper_ledger"
    assert payload["safety"]["real_orders"] is False


def test_portfolio_links_backtest_artifact_read_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    run = client.post("/api/backtest/run", json={})

    linked = client.post(
        "/api/portfolio/link-backtest",
        json={"artifact_dir": run.json()["artifact_dir"]},
    )

    assert run.status_code == 200
    assert linked.status_code == 200
    payload = linked.json()
    assert payload["portfolio"]["source"] == "backtest"
    assert f"{run.json()['artifact_dir']}/manifest.json" in payload["portfolio"]["linked_artifacts"]
    assert f"{run.json()['artifact_dir']}/summary.json" in payload["portfolio"]["linked_artifacts"]
    assert f"{run.json()['artifact_dir']}/trades.csv" in payload["portfolio"]["linked_artifacts"]
    assert f"{run.json()['artifact_dir']}/signals.csv" in payload["portfolio"]["linked_artifacts"]
    assert (
        f"{run.json()['artifact_dir']}/indicators.json" in payload["portfolio"]["linked_artifacts"]
    )
    assert (
        f"{run.json()['artifact_dir']}/returns_analysis.json"
        in payload["portfolio"]["linked_artifacts"]
    )
    assert (
        f"{run.json()['artifact_dir']}/returns_curve.csv"
        in payload["portfolio"]["linked_artifacts"]
    )
    assert (
        f"{run.json()['artifact_dir']}/data_snapshot.json"
        in payload["portfolio"]["linked_artifacts"]
    )
    assert (
        f"{run.json()['artifact_dir']}/provenance.json" in payload["portfolio"]["linked_artifacts"]
    )
    assert "Backtest" in payload["tabs"]
    context = payload["portfolio"]["backtest_context"]
    assert context["run_id"] == run.json()["run_id"]
    assert context["strategy"] == "sma_cross"
    assert context["strategy_label"] == "SMA Cross"
    assert context["provider"] == "deterministic_local_closed_candle"
    assert context["total_return_pct"] == run.json()["summary"]["return_pct"]
    assert context["signal_count"] == str(len(run.json()["signals"]))
    assert context["returns_curve_rows"] == str(len(run.json()["returns_curve"]))
    assert context["artifact_files"]["returns_analysis"].endswith("/returns_analysis.json")
    assert payload["summary"]["transaction_count"] == len(run.json()["trades"])
    assert payload["safety"]["real_orders"] is False


def test_portfolio_report_preserves_scan_seeded_lineage_and_artifact_health(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_public_market_cache())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())
    strategy_id = client.post("/api/algo/strategy", json=_strategy()).json()["active_strategy_id"]
    scan = client.post(
        "/api/algo/scan",
        json={"strategy_id": strategy_id, "symbols": "BTCUSDT", "timeframe": "15m"},
    ).json()["scan_result"]
    backtest = client.post(
        "/api/algo/run-backtest",
        json={
            "strategy_id": strategy_id,
            "scan_seed": {
                "scan_id": scan["scan_id"],
                "scan_artifact_hash": scan["research_lineage"]["scan_artifact_hash"],
            },
        },
    ).json()["backtest_result"]
    linked = client.post(
        "/api/portfolio/link-backtest",
        json={"artifact_dir": backtest["artifact_dir"]},
    )

    response = client.post("/api/portfolio/report")

    assert linked.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    artifact_files = payload["report"]["artifact_files"]
    lineage = json.loads((tmp_path / artifact_files["lineage"]).read_text(encoding="utf-8"))
    health = json.loads(
        (tmp_path / artifact_files["artifact_health"]).read_text(encoding="utf-8")
    )
    assert payload["portfolio"]["backtest_context"]["research_lineage"] == (
        backtest["research_lineage"]
    )
    assert payload["report"]["lineage_summary"]["backtest_run_id"] == backtest["run_id"]
    assert payload["report"]["lineage_summary"]["provider_id"] == (
        backtest["research_lineage"]["provider_id"]
    )
    assert payload["report"]["artifact_health"]["status"] == "complete"
    assert lineage["research_lineage"]["scan_id"] == scan["scan_id"]
    assert lineage["research_lineage"]["backtest_run_id"] == backtest["run_id"]
    assert lineage["safety"]["live_action_enabled"] is False
    assert health["status"] == "complete"
    assert health["summary"]["missing_artifact_count"] == "0"
    assert health["summary"]["unsafe_artifact_count"] == "0"
    assert health["recovery_queue"] == []
    assert all(row["sha256"] for row in health["rows"])
    assert all(row["path"].startswith("artifacts/backtests/") for row in health["rows"])


def test_portfolio_ignores_unsafe_backtest_manifest_artifact_paths(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    run = client.post("/api/backtest/run", json={})
    run_dir = tmp_path / run.json()["artifact_dir"]
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact_files"]["signals"] = "../unsafe-signals.csv"
    manifest["artifact_files"]["returns_analysis"] = "artifacts/portfolio/unsafe.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    linked = client.post(
        "/api/portfolio/link-backtest", json={"artifact_dir": run.json()["artifact_dir"]}
    )

    assert linked.status_code == 200
    payload_text = json.dumps(linked.json())
    assert "unsafe-signals" not in payload_text
    assert "artifacts/portfolio/unsafe.json" not in payload_text
    assert (
        f"{run.json()['artifact_dir']}/signals.csv"
        not in linked.json()["portfolio"]["linked_artifacts"]
    )
    assert "signals" not in linked.json()["portfolio"]["backtest_context"]["artifact_files"]


def test_portfolio_import_export_uses_provider_prices_and_manifest(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_public_market_cache())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())
    imported = {
        "name": "Crypto Book",
        "owner": "Local User",
        "currency": "USDT",
        "positions": [
            {
                "symbol": "BTCUSDT",
                "name": "Bitcoin",
                "asset_class": "Crypto",
                "sector": "Digital Assets",
                "quantity": "2",
                "avg_cost": "600.00",
                "last_price": "650.00",
                "currency": "USDT",
            }
        ],
        "transactions": [
            {
                "date": "2026-05-22T00:00:00Z",
                "symbol": "BTCUSDT",
                "side": "BUY",
                "quantity": "2",
                "price": "600.00",
            }
        ],
    }

    created = client.post(
        "/api/portfolio/import", json={"mode": "create_new", "portfolio": imported}
    )
    exported = client.get("/api/portfolio/export")

    assert created.status_code == 200
    payload = created.json()
    assert payload["positions"][0]["last_price"] == "1000.00"
    assert payload["summary"]["portfolio_value"] == "2000.00"
    assert payload["positions"][0]["price_source"] == "binance_public"
    assert payload["pricing"]["status"]["provider_price_count"] == "1"
    assert exported.status_code == 200
    export_payload = exported.json()
    assert export_payload["positions"][0]["price_source"] == "binance_public"
    assert export_payload["export_manifest"]["pricing"]["provider_price_count"] == "1"
    assert (tmp_path / export_payload["export_artifacts"]["portfolio"]).is_file()
    assert (tmp_path / export_payload["export_artifacts"]["manifest"]).is_file()


def test_portfolio_ignores_offline_fixture_prices_for_crypto_valuation(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_offline_fixture_market_cache())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    created = client.post(
        "/api/portfolio/import",
        json={
            "mode": "create_new",
            "portfolio": {
                "name": "Fixture Guard",
                "owner": "Local User",
                "currency": "USDT",
                "positions": [
                    {
                        "symbol": "BTCUSDT",
                        "name": "Bitcoin",
                        "asset_class": "Crypto",
                        "sector": "Digital Assets",
                        "quantity": "1",
                        "avg_cost": "600.00",
                        "last_price": "650.00",
                        "currency": "USDT",
                    }
                ],
            },
        },
    )

    assert created.status_code == 200
    payload = created.json()
    assert payload["positions"][0]["last_price"] == "650.00"
    assert payload["positions"][0]["price_source"] == "provider_unavailable"
    assert payload["pricing"]["status"]["provider_price_count"] == "0"
    assert payload["pricing"]["status"]["unavailable_count"] == "1"


def test_portfolio_rejects_linked_artifact_truncation_and_position_only_merge(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    position_only = {
        "name": "Snapshot Book",
        "owner": "Local User",
        "currency": "USD",
        "positions": [{"symbol": "AAPL", "quantity": "1", "avg_cost": "100"}],
    }
    imported = {
        "name": "Imported Book",
        "owner": "Local User",
        "currency": "USD",
        "positions": [{"symbol": "MSFT", "quantity": "1", "avg_cost": "200"}],
        "transactions": [{"symbol": "MSFT", "side": "BUY", "quantity": "1", "price": "200"}],
    }

    too_many_artifacts = client.post(
        "/api/portfolio/import",
        json={
            "mode": "create_new",
            "portfolio": {
                **position_only,
                "linked_artifacts": [f"artifact-{index}.json" for index in range(21)],
            },
        },
    )
    created = client.post(
        "/api/portfolio/import",
        json={"mode": "create_new", "portfolio": position_only},
    )
    merge = client.post(
        "/api/portfolio/import",
        json={
            "mode": "merge",
            "target_portfolio_id": created.json()["active_portfolio_id"],
            "portfolio": imported,
        },
    )

    assert too_many_artifacts.status_code == 400
    assert too_many_artifacts.json()["detail"] == "Linked artifacts exceed limit of 20"
    assert created.status_code == 200
    assert merge.status_code == 400
    assert merge.json()["detail"] == "Merge target requires transaction history"


def test_portfolio_delete_requires_confirmation_and_moves_active(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    first = client.post(
        "/api/portfolio/create",
        json={"name": "Keep Book", "owner": "Local User", "currency": "USD"},
    ).json()
    second = client.post(
        "/api/portfolio/create",
        json={"name": "Junk Book", "owner": "Local User", "currency": "USD"},
    ).json()
    junk_id = second["active_portfolio_id"]

    unconfirmed = client.post("/api/portfolio/delete", json={"portfolio_id": junk_id})
    assert unconfirmed.status_code == 400
    assert unconfirmed.json()["detail"] == "Delete confirmation is required"

    deleted = client.post(
        "/api/portfolio/delete", json={"portfolio_id": junk_id, "confirm": True}
    )
    assert deleted.status_code == 200
    payload = deleted.json()
    assert junk_id not in {p["portfolio_id"] for p in payload["portfolios"]}
    assert payload["active_portfolio_id"] == first["active_portfolio_id"]

    unknown = client.post(
        "/api/portfolio/delete", json={"portfolio_id": "portfolio-missing", "confirm": True}
    )
    assert unknown.status_code == 400
    assert unknown.json()["detail"] == "Unknown portfolio id"
