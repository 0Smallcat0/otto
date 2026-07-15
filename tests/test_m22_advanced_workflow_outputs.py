from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_advanced_workflow_output_packet_writes_metadata_only_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    chat_messages = tmp_path / "artifacts" / "chat" / "chat-local" / "messages.jsonl"
    chat_messages.parent.mkdir(parents=True)
    chat_messages.write_text(
        json.dumps({"role": "assistant", "content": "local dry-run output"}) + "\n",
        encoding="utf-8",
    )
    dry_run = tmp_path / "artifacts" / "workflows" / "workflow-local" / "dry_run.json"
    dry_run.parent.mkdir(parents=True)
    dry_run.write_text(json.dumps({"dry_run": True, "mutation": False}), encoding="utf-8")
    (dry_run.parent / "dry_run_manifest.json").write_text(
        json.dumps({"artifact_contract": "nodes_dry_run_v1"}),
        encoding="utf-8",
    )
    (dry_run.parent / "dry_run_report.md").write_text("dry-run report", encoding="utf-8")
    client = _client(tmp_path, monkeypatch)

    readonly = client.get("/api/advanced-workflows/output-packet")
    response = client.post("/api/advanced-workflows/output-packet")

    payload = response.json()
    routes = {row["route_id"]: row for row in payload["routes"]}
    artifact_dir = tmp_path / payload["artifact_dir"]

    assert readonly.status_code == 200
    assert readonly.json()["summary"]["route_count"] == 5
    assert response.status_code == 200
    assert payload["contract"] == "advanced_workflow_output_packet_v1"
    assert payload["summary"]["route_count"] == 5
    assert payload["summary"]["routes_with_outputs"] == 2
    assert payload["summary"]["routes_missing_outputs"] == 3
    assert payload["summary"]["state_artifact_file_count"] == 0
    assert payload["summary"]["manifest_file_count"] == 1
    assert payload["summary"]["report_file_count"] == 1
    assert payload["summary"]["error_log_file_count"] == 0
    assert payload["summary"]["routes_health_complete"] == 2
    assert payload["summary"]["routes_health_partial"] == 0
    assert payload["summary"]["routes_health_missing"] == 3
    assert payload["summary"]["supervision_ready_count"] == 2
    assert payload["summary"]["io_contract_route_count"] == 5
    assert routes["ai_chat"]["latest_artifacts"][0]["path"] == (
        "artifacts/chat/chat-local/messages.jsonl"
    )
    assert routes["ai_chat"]["artifact_kinds"]["data"] == 1
    assert routes["ai_chat"]["state_artifact_count"] == 0
    assert routes["ai_chat"]["latest_manifest_path"] == ""
    assert routes["ai_chat"]["health_state"] == "complete"
    assert routes["ai_chat"]["missing_expected_kinds"] == []
    assert routes["nodes"]["latest_manifest_path"] == (
        "artifacts/workflows/workflow-local/dry_run_manifest.json"
    )
    assert routes["nodes"]["latest_report_path"] == (
        "artifacts/workflows/workflow-local/dry_run_report.md"
    )
    assert routes["nodes"]["artifact_kinds"]["manifest"] == 1
    assert routes["nodes"]["state_artifact_count"] == 0
    assert routes["nodes"]["artifact_kinds"]["report"] == 1
    assert routes["nodes"]["expected_artifact_kinds"] == ["data", "manifest", "report"]
    assert routes["nodes"]["health_state"] == "complete"
    assert routes["nodes"]["supervision_ready"] is True
    assert any(
        row["path"]
        == (
            "artifacts/workflows/workflow-local/dry_run.json"
        )
        for row in routes["nodes"]["latest_artifacts"]
    )
    assert routes["nodes"]["output_state"] == "available"
    assert routes["nodes"]["io_contract"]["contract_id"] == "nodes_advanced_output_io_v1"
    assert routes["nodes"]["io_contract"]["input_contract"] == [
        "workflow_id:string",
        "workflow_definition:local_nodes_graph",
        "context:provider_cache_and_artifact_metadata",
    ]
    assert routes["nodes"]["io_contract"]["output_contract"] == [
        "dry_run.json:data",
        "dry_run_manifest.json:manifest",
        "dry_run_report.md:report",
    ]
    assert routes["nodes"]["io_contract"]["error_contract"] == [
        "400 invalid_workflow",
        "403 nodes_execute_disabled",
    ]
    assert routes["nodes"]["io_contract"]["latest_output_paths"]["latest_artifact"].startswith(
        "artifacts/workflows/workflow-local/"
    )
    assert routes["nodes"]["io_contract"]["latest_output_paths"]["manifest"] == (
        "artifacts/workflows/workflow-local/dry_run_manifest.json"
    )
    assert routes["nodes"]["io_contract"]["latest_output_paths"]["report"] == (
        "artifacts/workflows/workflow-local/dry_run_report.md"
    )
    assert routes["nodes"]["io_contract"]["latest_output_paths"]["error_log"] == ""
    assert routes["nodes"]["io_contract"]["read_mode"] == "metadata_only"
    assert routes["nodes"]["io_contract"]["safety"]["content_read"] is False
    assert routes["nodes"]["io_contract"]["safety"]["execution_enabled"] is False
    assert routes["code"]["safe_output_action"]["action_id"] == "code_analyze"
    assert "analysis.json:data+static_outline" in routes["code"]["io_contract"][
        "output_contract"
    ]
    assert {
        item["route_id"]: item["recommended_action"] for item in payload["recovery_queue"]
    } == {
        "code": "code_analyze",
        "quant_lab": "quant_lab_run_preview",
        "quantlib": "quantlib_compute",
    }
    assert payload["safety"]["metadata_only"] is True
    assert payload["safety"]["content_read"] is False
    assert payload["safety"]["execution_enabled"] is False
    assert payload["safety"]["broker_mutation"] is False
    assert payload["safety"]["live_trading"] is False
    assert artifact_dir.is_dir()
    for artifact_path in payload["artifacts"].values():
        assert (tmp_path / artifact_path).is_file()
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifact_contract"] == "advanced_workflow_output_packet_v1"
    assert manifest["summary"]["recovery_recommended_count"] == 3


def test_advanced_workflow_output_packet_reports_partial_health_without_content_reads(
    tmp_path: Path,
    monkeypatch,
) -> None:
    code_artifact = tmp_path / "artifacts" / "code_workspace" / "notebook-local" / "analysis.json"
    code_artifact.parent.mkdir(parents=True)
    code_artifact.write_text(json.dumps({"status": "completed"}), encoding="utf-8")
    client = _client(tmp_path, monkeypatch)

    payload = client.get("/api/advanced-workflows/output-packet").json()
    routes = {row["route_id"]: row for row in payload["routes"]}

    assert payload["summary"]["routes_health_complete"] == 0
    assert payload["summary"]["routes_health_partial"] == 1
    assert payload["summary"]["routes_health_missing"] == 4
    assert payload["summary"]["supervision_ready_count"] == 0
    assert routes["code"]["health_state"] == "partial"
    assert routes["code"]["io_contract"]["contract_id"] == "code_advanced_output_io_v1"
    assert routes["code"]["io_contract"]["latest_output_paths"]["latest_artifact"] == (
        "artifacts/code_workspace/notebook-local/analysis.json"
    )
    assert routes["code"]["io_contract"]["safety"]["metadata_only"] is True
    assert routes["code"]["missing_expected_kinds"] == ["manifest", "report"]
    assert routes["code"]["health_reason"] == "missing expected artifact kinds: manifest, report"
    assert routes["code"]["supervision_ready"] is False
    assert routes["code"]["artifact_kinds"]["data"] == 1
    recovery = {item["route_id"]: item for item in payload["recovery_queue"]}
    assert recovery["code"]["state"] == "partial"
    assert recovery["code"]["recommended_action"] == "code_analyze"
    assert recovery["code"]["reason"] == "missing expected artifact kinds: manifest, report"
    assert payload["safety"]["content_read"] is False
    assert payload["safety"]["execution_enabled"] is False


def test_advanced_workflow_output_packet_separates_route_state_files_from_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_files = {
        "artifacts/chat/chat_state.json": {"active_session_id": "local"},
        "artifacts/workflows/nodes_state.json": {"workflows": {}},
        "artifacts/code_workspace/code_state.json": {"notebooks": {}},
        "artifacts/quant_lab/quant_lab_state.json": {"runs": {}},
        "artifacts/quantlib/quantlib_state.json": {"calculations": {}},
    }
    for relative, payload in state_files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    client = _client(tmp_path, monkeypatch)

    payload = client.get("/api/advanced-workflows/output-packet").json()
    routes = {row["route_id"]: row for row in payload["routes"]}

    assert payload["summary"]["routes_with_outputs"] == 0
    assert payload["summary"]["routes_missing_outputs"] == 5
    assert payload["summary"]["routes_health_partial"] == 0
    assert payload["summary"]["routes_health_missing"] == 5
    assert payload["summary"]["artifact_file_count"] == 0
    assert payload["summary"]["state_artifact_file_count"] == 5
    assert payload["summary"]["supervision_ready_count"] == 0
    for route_id, route in routes.items():
        assert route["artifact_count"] == 0
        assert route["state_artifact_count"] == 1
        assert route["state_artifacts"][0]["path"].startswith(route["artifact_root"])
        assert route["latest_state_artifact_path"] == route["state_artifacts"][0]["path"]
        assert route["health_state"] == "missing_output"
        assert route["health_reason"] == "no local output artifacts indexed"
        assert route["supervision_ready"] is False
        assert route["latest_artifacts"] == []
        assert route["io_contract"]["latest_output_paths"]["latest_artifact"] == ""
    assert {
        item["route_id"]: item["reason"] for item in payload["recovery_queue"]
    } == {
        "ai_chat": "no local output artifacts indexed for this advanced route",
        "nodes": "no local output artifacts indexed for this advanced route",
        "code": "no local output artifacts indexed for this advanced route",
        "quant_lab": "no local output artifacts indexed for this advanced route",
        "quantlib": "no local output artifacts indexed for this advanced route",
    }
    assert payload["safety"]["content_read"] is False
    assert payload["safety"]["execution_enabled"] is False
