import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.storage import LocalStateStore


def _workflow() -> dict[str, object]:
    return {
        "name": "Local Research Flow",
        "description": "Dry-run workflow for public market data and local display.",
        "mode": "dry_run",
        "nodes": [
            {
                "node_id": "manual_trigger",
                "node_type": "manual_trigger",
                "label": "Manual Trigger",
                "x": 80,
                "y": 120,
                "config": {},
            },
            {
                "node_id": "crypto_price",
                "node_type": "crypto_price",
                "label": "Crypto Price",
                "x": 300,
                "y": 120,
                "config": {"symbol": "BTCUSDT"},
            },
            {
                "node_id": "results_display",
                "node_type": "results_display",
                "label": "Results Display",
                "x": 520,
                "y": 120,
                "config": {},
            },
        ],
        "edges": [
            {
                "edge_id": "manual_trigger-crypto_price",
                "source": "manual_trigger",
                "target": "crypto_price",
            },
            {
                "edge_id": "crypto_price-results_display",
                "source": "crypto_price",
                "target": "results_display",
            },
        ],
    }


def test_nodes_initial_payload_reports_library_templates_and_safety(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/nodes")

    payload = response.json()
    assert response.status_code == 200
    assert payload["first_use"] is True
    assert payload["engine"]["engine_id"] == "local_nodes_v1"
    assert {section["category"] for section in payload["library"]} >= {
        "Analytics",
        "Utilities",
        "Trading",
        "Data Transform",
        "Safety",
        "Control Flow",
        "Market Data",
        "Core",
    }
    assert payload["templates"][0]["template_id"] == "template-hello-local"
    assert payload["safety"] == {
        "dry_run_only": True,
        "deploy_enabled": False,
        "execute_enabled": False,
        "live_deployment": False,
        "broker_routing": False,
        "real_orders": False,
        "private_api_required": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives": False,
        "external_mutation": False,
        "output": "plan_only",
        "runtime_state": "disabled_no_safety_contract",
    }


def test_nodes_template_save_export_and_definition_artifact(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    loaded = client.post(
        "/api/nodes/template",
        json={"template_id": "template-hello-local"},
    )
    payload = loaded.json()
    workflow_id = payload["active_workflow_id"]
    exported = client.post("/api/nodes/export", json={"workflow_id": workflow_id})
    local_state = client.get("/api/local-state")

    assert loaded.status_code == 200
    assert payload["active_workflow"]["name"] == "Hello Local Workflow"
    assert payload["engine"]["node_count"] == 3
    assert exported.status_code == 200
    assert exported.json()["workflow"]["workflow_id"] == workflow_id
    assert (tmp_path / "artifacts" / "workflows" / "nodes_state.json").is_file()
    assert (tmp_path / "artifacts" / "workflows" / workflow_id / "definition.json").is_file()
    assert local_state.json()["storage"]["nodes_state"] == "artifacts/workflows/nodes_state.json"


def test_nodes_import_select_node_and_dry_run_is_non_mutating(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    imported = client.post("/api/nodes/import", json={"workflow": _workflow()})
    workflow_id = imported.json()["active_workflow_id"]
    selected = client.post("/api/nodes/select-node", json={"node_id": "crypto_price"})
    planned = client.post("/api/nodes/dry-run", json={"workflow_id": workflow_id})

    assert imported.status_code == 200
    assert selected.status_code == 200
    assert selected.json()["selected_node"]["node_type"] == "crypto_price"
    assert planned.status_code == 200
    dry_run = planned.json()["dry_run_result"]
    assert dry_run["dry_run"] is True
    assert dry_run["mutation"] is False
    assert dry_run["deploy_enabled"] is False
    assert dry_run["execute_enabled"] is False
    assert dry_run["output_summary"]["output_mode"] == "local_dry_run_artifact"
    assert dry_run["output_summary"]["read_provider_cache_count"] == 1
    assert dry_run["output_summary"]["runtime_allowed"] is False
    assert dry_run["artifact_files"]["report"].endswith("/dry_run_report.md")
    assert dry_run["artifact_files"]["manifest"].endswith("/dry_run_manifest.json")
    assert {step["mutation"] for step in dry_run["steps"]} == {False}
    assert {step["runtime_allowed"] for step in dry_run["steps"]} == {False}
    for artifact in dry_run["artifact_files"].values():
        assert (tmp_path / artifact).is_file()
    report_text = (tmp_path / dry_run["artifact_files"]["report"]).read_text(encoding="utf-8")
    assert "Nodes Dry-Run Report" in report_text
    assert "dry-run only" in report_text
    manifest = json.loads(
        (tmp_path / dry_run["artifact_files"]["manifest"]).read_text(encoding="utf-8")
    )
    assert manifest["safety"]["dry_run_only"] is True
    assert manifest["safety"]["real_orders"] is False


def test_nodes_workflow_health_is_metadata_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    initial = client.get("/api/nodes/workflow-health")

    assert initial.status_code == 200
    assert initial.json()["mode"] == "metadata_only_nodes_workflow_health"
    assert initial.json()["summary"]["workflow_count"] == 0
    assert initial.json()["summary"]["recovery_queue_count"] == 1
    assert initial.json()["safety"]["workflow_execution"] is False
    assert initial.json()["safety"]["artifact_content_read"] is False
    assert initial.json()["safety"]["automatic_repair_enabled"] is False

    imported = client.post("/api/nodes/import", json={"workflow": _workflow()})
    workflow_id = imported.json()["active_workflow_id"]
    health_after_import = client.get("/api/nodes/workflow-health").json()
    imported_row = health_after_import["workflows"][0]

    assert imported.status_code == 200
    assert imported.json()["workflow_health"]["summary"]["workflow_count"] == 1
    assert imported_row["workflow_id"] == workflow_id
    assert imported_row["health_state"] == "partial_missing_dry_run"
    assert imported_row["definition_artifact_exists"] is True
    assert imported_row["dry_run_artifact_exists"] is False
    assert imported_row["missing_count"] == 3
    assert imported_row["supervision_ready"] is True
    assert health_after_import["summary"]["partial_count"] == 1
    assert health_after_import["summary"]["missing_artifact_count"] == 3
    assert health_after_import["summary"]["supervision_ready_count"] == 1
    assert health_after_import["recovery_queue"][0]["recommended_action"] == "nodes_dry_run"

    planned = client.post("/api/nodes/dry-run", json={"workflow_id": workflow_id})
    embedded_health = planned.json()["workflow_health"]
    completed_row = embedded_health["workflows"][0]

    assert planned.status_code == 200
    assert completed_row["health_state"] == "complete"
    assert completed_row["missing_count"] == 0
    assert completed_row["present_count"] == 4
    assert completed_row["artifact_bytes"] > 0
    assert completed_row["last_dry_run_plan_id"] == planned.json()["dry_run_result"]["plan_id"]
    assert embedded_health["summary"]["complete_count"] == 1
    assert embedded_health["summary"]["recovery_queue_count"] == 0

    report_path = tmp_path / completed_row["report_artifact_path"]
    report_path.unlink()
    health_after_missing_report = client.get("/api/nodes/workflow-health")
    missing_report_row = health_after_missing_report.json()["workflows"][0]

    assert health_after_missing_report.status_code == 200
    assert missing_report_row["health_state"] == "partial_missing_dry_run"
    assert missing_report_row["report_artifact_exists"] is False
    assert health_after_missing_report.json()["summary"]["recovery_queue_count"] == 1
    assert "Nodes Dry-Run Report" not in health_after_missing_report.text


def test_nodes_runtime_deploy_and_execute_are_disabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    deploy = client.post("/api/nodes/deploy")
    execute = client.post("/api/nodes/execute")

    assert deploy.status_code == 403
    assert deploy.json()["detail"]["state"] == "disabled"
    assert deploy.json()["detail"]["safety"]["live_deployment"] is False
    assert execute.status_code == 403
    assert execute.json()["detail"]["state"] == "disabled"
    assert execute.json()["detail"]["safety"]["real_orders"] is False


def test_nodes_rejects_live_or_secret_import_without_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    live_config = client.post(
        "/api/nodes/import",
        json={
            "workflow": {
                **_workflow(),
                "nodes": [
                    {
                        "node_id": "place_order",
                        "node_type": "place_order",
                        "label": "Place Order",
                        "x": 80,
                        "y": 120,
                        "config": {"live": True},
                    }
                ],
                "edges": [],
            }
        },
    )
    live_value = client.post(
        "/api/nodes/import",
        json={
            "workflow": {
                **_workflow(),
                "nodes": [
                    {
                        "node_id": "place_order",
                        "node_type": "place_order",
                        "label": "Place Order",
                        "x": 80,
                        "y": 120,
                        "config": {"mode": "live"},
                    }
                ],
                "edges": [],
            }
        },
    )
    secret_config = client.post(
        "/api/nodes/import",
        json={
            "workflow": {
                **_workflow(),
                "description": "private_key=abc123",
            }
        },
    )

    assert live_config.status_code == 400
    assert live_config.json()["detail"] == "Node config contains forbidden runtime key"
    assert live_value.status_code == 400
    assert live_value.json()["detail"] == "Node config contains forbidden runtime value"
    assert secret_config.status_code == 400
    assert secret_config.json()["detail"] == "Text appears to contain credential material"
    assert not (tmp_path / "artifacts" / "workflows").exists()


def test_nodes_import_with_supplied_id_cannot_bypass_workflow_limit(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    workflows = {
        f"workflow-{index:03d}": {
            "workflow_id": f"workflow-{index:03d}",
            "name": f"Workflow {index:03d}",
            "description": "Dry-run workflow.",
            "mode": "dry_run",
            "nodes": [],
            "edges": [],
            "created_at": "2026-05-22T00:00:00Z",
            "updated_at": "2026-05-22T00:00:00Z",
        }
        for index in range(80)
    }
    store.write_nodes_state(
        {
            "active_workflow_id": "workflow-000",
            "workflows": workflows,
        }
    )
    client = TestClient(server.create_app())

    response = client.post(
        "/api/nodes/import",
        json={
            "workflow": {
                **_workflow(),
                "workflow_id": "workflow-extra",
            }
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Workflows exceed limit of 80"
    state_path = tmp_path / "artifacts" / "workflows" / "nodes_state.json"
    assert len(json.loads(state_path.read_text(encoding="utf-8"))["workflows"]) == 80


def test_nodes_corrupt_existing_state_blocks_mutation_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    state_path = tmp_path / "artifacts" / "workflows" / "nodes_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not-json", encoding="utf-8")
    client = TestClient(server.create_app())

    readonly = client.get("/api/nodes")
    response = client.post(
        "/api/nodes/import",
        json={"workflow": _workflow()},
    )

    assert readonly.status_code == 200
    assert readonly.json()["invalid_workflows"]["nodes_state.json"] == ("Invalid nodes state JSON")
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Nodes state is invalid: nodes_state.json: Invalid nodes state JSON"
    )
    assert state_path.read_text(encoding="utf-8") == "{not-json"


def test_nodes_tampered_dry_run_blocks_mutation_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    imported = client.post("/api/nodes/import", json={"workflow": _workflow()})
    state_path = tmp_path / "artifacts" / "workflows" / "nodes_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["last_dry_run"] = {
        "plan_id": "tampered",
        "workflow_id": imported.json()["active_workflow_id"],
        "status": "complete",
        "dry_run": False,
        "mutation": True,
        "steps": [],
        "created_at": "2026-05-22T00:00:00Z",
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    readonly = client.get("/api/nodes")
    response = client.post("/api/nodes/clear")

    assert readonly.status_code == 200
    assert readonly.json()["last_dry_run"] is None
    assert readonly.json()["invalid_workflows"]["last_dry_run"] == (
        "Dry-run result must be non-mutating"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Stored dry-run is invalid: Dry-run result must be non-mutating"
    )
