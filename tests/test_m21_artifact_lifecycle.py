import json
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.artifact_lifecycle import (
    artifact_lifecycle_payload,
    run_artifact_archive_plan,
)
from src.local_terminal.storage import LocalStateStore


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_artifact_lifecycle_reports_metadata_without_content_reads(tmp_path: Path) -> None:
    (tmp_path / "artifacts" / "backtests" / "run-1").mkdir(parents=True)
    (tmp_path / "artifacts" / "backtests" / "run-1" / "summary.json").write_text(
        '{"status":"complete"}',
        encoding="utf-8",
    )
    (tmp_path / "artifacts" / "diagnostics" / "provider-refresh-abc123def456").mkdir(
        parents=True
    )
    (tmp_path / "artifacts" / "diagnostics" / "provider-refresh-abc123def456" / "manifest.json").write_text(
        '{"run_id":"provider-refresh-abc123def456"}',
        encoding="utf-8",
    )

    payload = artifact_lifecycle_payload(tmp_path)
    rows = {row["root_id"]: row for row in payload["roots"]}

    assert payload["mode"] == "read_only_metadata_inventory"
    assert payload["summary"]["root_count"] >= 15
    assert payload["summary"]["file_count"] == 2
    assert payload["summary"]["supervision_ready_root_count"] == 2
    assert payload["summary"]["empty_root_count"] == 0
    assert payload["summary"]["missing_root_count"] >= 1
    assert payload["diagnostics"]["provider_refresh"]["run_count"] == 1
    assert rows["backtests"]["state"] == "active"
    assert rows["backtests"]["file_count"] == 1
    assert rows["backtests"]["latest_artifact_path"] == "artifacts/backtests/run-1/summary.json"
    assert rows["backtests"]["supervision_ready"] is True
    assert rows["backtests"]["recovery_hint"] == "Metadata is ready for agent supervision."
    assert rows["backtests"]["destructive_actions_enabled"] is False
    assert rows["backtests"]["research_lineage_supported"] is True
    assert rows["backtests"]["lineage_manifest_contract"] == (
        "research_lineage_v1_metadata_only"
    )
    assert rows["backtests"]["lineage_content_read"] is False
    assert rows["algo"]["research_lineage_supported"] is True
    assert rows["market_data"]["research_lineage_supported"] is False
    assert rows["market_data"]["state"] == "missing"
    assert rows["market_data"]["latest_artifact_path"] == ""
    assert rows["market_data"]["supervision_ready"] is False
    assert payload["safety"]["content_read"] is False
    assert payload["safety"]["external_network"] is False
    assert payload["safety"]["destructive_actions_enabled"] is False


def test_artifact_archive_plan_writes_metadata_only_non_destructive_bundle(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "artifacts" / "backtests" / "run-1"
    run_dir.mkdir(parents=True)
    summary_path = run_dir / "summary.json"
    summary_path.write_text(
        '{"status":"complete","note":"SYNTHETIC_TEST_SECRET_DO_NOT_LEAK"}',
        encoding="utf-8",
    )
    stale_mtime = time.time() - 40 * 24 * 60 * 60
    os.utime(summary_path, (stale_mtime, stale_mtime))
    os.utime(run_dir, (stale_mtime, stale_mtime))
    before_paths = sorted(
        path.relative_to(tmp_path).as_posix()
        for path in (tmp_path / "artifacts").rglob("*")
        if path.is_file()
    )

    payload = run_artifact_archive_plan(tmp_path)

    after_paths = sorted(
        path.relative_to(tmp_path).as_posix()
        for path in (tmp_path / "artifacts" / "backtests").rglob("*")
        if path.is_file()
    )
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["mode"] == "metadata_only_archive_plan"
    assert payload["status"] == "saved_locally"
    assert payload["run_id"].startswith("artifact-lifecycle-plan-")
    assert payload["summary"]["archive_candidate_count"] >= 1
    assert payload["actions"]["archive_enabled"] is False
    assert payload["actions"]["delete_enabled"] is False
    assert payload["safety"]["destructive_actions_enabled"] is False
    assert payload["safety"]["content_read"] is False
    assert payload["safety"]["artifact_roots_mutated"] is False
    assert any(
        row["root_id"] == "backtests" and row["proposed_action"] == "archive_candidate"
        for row in payload["candidates"]
    )
    assert "SYNTHETIC_TEST_SECRET_DO_NOT_LEAK" not in serialized
    assert summary_path.read_text(encoding="utf-8").endswith(
        '"SYNTHETIC_TEST_SECRET_DO_NOT_LEAK"}'
    )
    assert before_paths == ["artifacts/backtests/run-1/summary.json"]
    assert after_paths == ["artifacts/backtests/run-1/summary.json"]
    assert (tmp_path / payload["artifacts"]["archive_plan"]).is_file()
    assert (tmp_path / payload["artifacts"]["manifest"]).is_file()
    assert (tmp_path / payload["artifacts"]["report"]).is_file()


def test_artifact_lifecycle_api_is_read_only_and_agent_operable(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/artifact-lifecycle")

    payload = response.json()
    assert response.status_code == 200
    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["credentials_required"] is False
    assert payload["safety"]["live_trading"] is False
    assert any(row["root_id"] == "diagnostics" for row in payload["roots"])
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_artifact_archive_plan_api_is_non_destructive_and_agent_operable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "artifacts" / "quantlib").mkdir(parents=True)
    (tmp_path / "artifacts" / "quantlib" / "response.json").write_text(
        '{"result":1}',
        encoding="utf-8",
    )
    client = _client(tmp_path, monkeypatch)

    response = client.post("/api/artifact-lifecycle/archive-plan")

    payload = response.json()
    assert response.status_code == 200
    assert payload["safety"]["content_read"] is False
    assert payload["safety"]["files_deleted"] is False
    assert payload["safety"]["files_moved"] is False
    assert payload["actions"]["archive_enabled"] is False
    assert payload["actions"]["prune_enabled"] is False
    assert (tmp_path / "artifacts" / "quantlib" / "response.json").is_file()
    assert (tmp_path / payload["artifacts"]["manifest"]).is_file()
    governance = client.get("/api/governance").json()
    assert governance["artifact_lifecycle"]["summary"]["archive_plan_run_count"] == 1
    assert (
        governance["artifact_lifecycle"]["diagnostics"]["archive_plans"]["latest_run_id"]
        == payload["run_id"]
    )
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_governance_diagnostics_include_artifact_lifecycle_bundle(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "artifacts" / "forum").mkdir(parents=True)
    (tmp_path / "artifacts" / "forum" / "forum_state.json").write_text(
        '{"posts":[],"active_channel_id":"general","selected_post_id":null}',
        encoding="utf-8",
    )
    client = _client(tmp_path, monkeypatch)

    governance = client.get("/api/governance").json()
    diagnostics = client.post("/api/governance/diagnostics").json()
    help_diagnostics = client.post("/api/help/diagnostics").json()

    assert governance["artifact_lifecycle"]["safety"]["read_only"] is True
    assert governance["summary"]["artifact_root_count"] >= 15
    assert diagnostics["checks"]["artifact_lifecycle_rows_present"] is True
    assert diagnostics["checks"]["artifact_lifecycle_metadata_only"] is True
    assert diagnostics["checks"]["destructive_artifact_actions_disabled"] is True
    assert diagnostics["checks"]["artifact_archive_plan_non_destructive"] is True
    assert diagnostics["safety"]["artifact_delete_enabled"] is False
    assert diagnostics["safety"]["artifact_archive_plan_write_enabled"] is True
    assert (tmp_path / diagnostics["artifacts"]["artifact_lifecycle"]).is_file()
    assert help_diagnostics["checks"]["artifact_lifecycle_read_only"] is True
    assert help_diagnostics["checks"]["artifact_lifecycle_archive_plan_non_destructive"] is True
    assert help_diagnostics["artifact_lifecycle"]["safety"]["content_read"] is False
