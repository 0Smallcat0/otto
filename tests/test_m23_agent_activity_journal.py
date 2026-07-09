from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.agent_activity import agent_activity_payload
from src.local_terminal.storage import LocalStateStore


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_agent_activity_journal_records_metadata_only_events(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    empty = client.get("/api/agent-activity").json()
    response = client.post(
        "/api/agent-activity/events",
        json={
            "action_id": "portfolio_report",
            "state": "running",
            "summary": "Portfolio report started",
            "artifact_path": "artifacts/portfolio/reports/report-1/manifest.json",
        },
    )
    payload = response.json()
    command_center = client.get("/api/command-center").json()

    assert empty["summary"]["event_count"] == 0
    assert response.status_code == 200
    assert payload["summary"]["event_count"] == 1
    assert payload["summary"]["latest_state"] == "running"
    assert payload["summary"]["active_task_state"] == "running"
    assert payload["summary"]["active_action_id"] == "portfolio_report"
    assert payload["active_task"]["is_active"] is True
    assert payload["active_task"]["state"] == "running"
    assert payload["active_task"]["route_id"] == "portfolio"
    assert payload["active_task"]["action_id"] == "portfolio_report"
    assert payload["active_task"]["request_body_logged"] is False
    assert payload["active_task"]["action_executed_by_journal"] is False
    assert payload["active_task"]["destructive_actions_enabled"] is False
    assert payload["last_event"]["route_id"] == "portfolio"
    assert payload["last_event"]["action_id"] == "portfolio_report"
    assert payload["last_event"]["request_body_logged"] is False
    assert payload["last_event"]["action_executed_by_journal"] is False
    assert payload["safety"]["secret_values_stored"] is False
    assert payload["safety"]["action_execution"] is False
    assert (tmp_path / "artifacts" / "agent_activity" / "activity.jsonl").is_file()
    assert command_center["agent_activity"]["summary"]["event_count"] == 1
    assert command_center["agent_activity"]["active_task"]["is_active"] is True
    assert command_center["active_task"]["action_id"] == "portfolio_report"
    assert command_center["active_task"]["state"] == "running"
    assert command_center["active_task"]["request_body_logged"] is False
    assert command_center["selectors"]["active_task"] == (
        "[data-testid='command-center-active-task']"
    )
    assert command_center["agent_activity"]["events"][0]["action_id"] == "portfolio_report"
    assert command_center["agent_activity"]["safety"]["request_body_logged"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()

    complete = client.post(
        "/api/agent-activity/events",
        json={
            "action_id": "portfolio_report",
            "state": "succeeded",
            "summary": "Portfolio report finished",
            "artifact_path": "artifacts/portfolio/reports/report-1/manifest.json",
        },
    ).json()

    assert complete["summary"]["latest_state"] == "succeeded"
    assert complete["summary"]["active_task_state"] == "none"
    assert complete["active_task"]["is_active"] is False
    assert complete["active_task"]["action_id"] == ""


def test_agent_activity_journal_rejects_secret_like_or_unknown_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    secret = client.post(
        "/api/agent-activity/events",
        json={
            "action_id": "portfolio_report",
            "state": "running",
            "summary": "pin: 123456789",
        },
    )
    unknown = client.post(
        "/api/agent-activity/events",
        json={"action_id": "not_real", "state": "running"},
    )
    bad_path = client.post(
        "/api/agent-activity/events",
        json={
            "action_id": "portfolio_report",
            "state": "running",
            "artifact_path": "../outside.json",
        },
    )

    assert secret.status_code == 400
    assert "secret-like material" in secret.json()["detail"]
    assert unknown.status_code == 400
    assert unknown.json()["detail"] == "Unknown action_id for agent activity event"
    assert bad_path.status_code == 400
    assert bad_path.json()["detail"] == "artifact_path must be a repo-local artifacts/ path"
    assert agent_activity_payload(tmp_path)["events"] == []
    assert not (tmp_path / "artifacts" / "agent_activity" / "activity.jsonl").exists()
