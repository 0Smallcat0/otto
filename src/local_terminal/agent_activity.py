"""Metadata-only local AI Agent activity journal."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.local_terminal.agent_contract import ACTION_CONTRACTS, ROUTE_CONTRACTS
from src.local_terminal.secret_gate import contains_secret_material

AGENT_ACTIVITY_PATH = "artifacts/agent_activity/activity.jsonl"
AGENT_ACTIVITY_CONTRACT = "agent_activity_journal_v1"
AGENT_ACTIVITY_STATES = {"planned", "running", "succeeded", "failed", "blocked", "skipped"}
ACTIVE_ACTIVITY_STATES = {"planned", "running", "blocked"}
MAX_ACTIVITY_EVENTS = 100
MAX_TEXT_LENGTH = 160
SENSITIVE_TEXT_PATTERN = re.compile(
    r"(@|bearer\s+|api[\s_-]*key|password|passphrase|pin|token|secret|private[\s_-]*key)",
    re.IGNORECASE,
)


class AgentActivityError(ValueError):
    """Raised when an activity journal event violates the metadata-only contract."""


def agent_activity_payload(root: Path, *, limit: int = 20) -> dict[str, Any]:
    """Return recent metadata-only Agent activity without reading external content."""

    path = _activity_path(root)
    events = _read_events(path)[-max(1, min(limit, MAX_ACTIVITY_EVENTS)) :]
    latest = events[-1] if events else {}
    active_task = _active_task(latest)
    return {
        "generated_at": _utc_now(),
        "mode": "metadata_only_agent_activity_journal",
        "contract": AGENT_ACTIVITY_CONTRACT,
        "artifact_path": AGENT_ACTIVITY_PATH,
        "summary": {
            "event_count": len(events),
            "latest_state": str(latest.get("state") or "none"),
            "latest_route_id": str(latest.get("route_id") or ""),
            "latest_action_id": str(latest.get("action_id") or ""),
            "active_task_state": str(active_task["state"]),
            "active_route_id": str(active_task["route_id"]),
            "active_action_id": str(active_task["action_id"]),
            "max_returned_events": max(1, min(limit, MAX_ACTIVITY_EVENTS)),
        },
        "active_task": active_task,
        "events": list(reversed(events)),
        "write_action": {
            "action_id": "agent_activity_event",
            "method": "POST",
            "endpoint": "/api/agent-activity/events",
            "request_contract": "route_id/action_id/state/summary/artifact_path metadata only",
        },
        "safety": _safety(),
    }


def append_agent_activity_event(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    """Append one bounded metadata event and return the updated activity payload."""

    event = _event_from_request(request)
    path = _activity_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")
    payload = agent_activity_payload(root)
    payload["last_event"] = event
    return payload


def _event_from_request(request: dict[str, Any]) -> dict[str, Any]:
    action_id = _bounded_text(request.get("action_id"), "action_id", max_length=80)
    action = next((item for item in ACTION_CONTRACTS if item.action_id == action_id), None)
    if action is None:
        raise AgentActivityError("Unknown action_id for agent activity event")
    route_id = _bounded_text(request.get("route_id") or action.route_id, "route_id", max_length=40)
    if route_id not in {route.route_id for route in ROUTE_CONTRACTS}:
        raise AgentActivityError("Unknown route_id for agent activity event")
    if route_id != action.route_id:
        raise AgentActivityError("route_id does not match action_id")
    state = _bounded_text(request.get("state"), "state", max_length=24)
    if state not in AGENT_ACTIVITY_STATES:
        raise AgentActivityError("Unsupported agent activity state")
    summary = _bounded_text(request.get("summary"), "summary", required=False)
    artifact_path = _artifact_path_text(request.get("artifact_path"))
    event = {
        "event_id": f"agent-event-{uuid4().hex[:12]}",
        "created_at": _utc_now(),
        "route_id": route_id,
        "action_id": action.action_id,
        "state": state,
        "summary": summary or f"{action.label}: {state}",
        "artifact_path": artifact_path,
        "method": action.method,
        "endpoint": action.endpoint,
        "safety_class": action.safety_class,
        "writes_local_artifacts": action.writes_local_artifacts,
        "metadata_only": True,
        "request_body_logged": False,
        "action_executed_by_journal": False,
        "destructive_actions_enabled": False,
    }
    if contains_secret_material(event):
        raise AgentActivityError("Agent activity event contains secret-like material")
    return event


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows[-MAX_ACTIVITY_EVENTS:]


def _active_task(event: dict[str, Any]) -> dict[str, Any]:
    state = str(event.get("state") or "")
    if state not in ACTIVE_ACTIVITY_STATES:
        return _inactive_task()
    return {
        "is_active": True,
        "state": state,
        "route_id": str(event.get("route_id") or ""),
        "action_id": str(event.get("action_id") or ""),
        "summary": str(event.get("summary") or ""),
        "artifact_path": str(event.get("artifact_path") or ""),
        "method": str(event.get("method") or ""),
        "endpoint": str(event.get("endpoint") or ""),
        "safety_class": str(event.get("safety_class") or ""),
        "event_id": str(event.get("event_id") or ""),
        "created_at": str(event.get("created_at") or ""),
        "request_body_logged": bool(event.get("request_body_logged")),
        "action_executed_by_journal": bool(event.get("action_executed_by_journal")),
        "destructive_actions_enabled": bool(event.get("destructive_actions_enabled")),
        "recovery_hint": "Append a terminal succeeded, failed, or skipped event when the local action finishes.",
    }


def _inactive_task() -> dict[str, Any]:
    return {
        "is_active": False,
        "state": "none",
        "route_id": "",
        "action_id": "",
        "summary": "",
        "artifact_path": "",
        "method": "",
        "endpoint": "",
        "safety_class": "",
        "event_id": "",
        "created_at": "",
        "request_body_logged": False,
        "action_executed_by_journal": False,
        "destructive_actions_enabled": False,
        "recovery_hint": "No active metadata task is currently declared.",
    }


def _activity_path(root: Path) -> Path:
    path = (root / AGENT_ACTIVITY_PATH).resolve()
    if not path.is_relative_to(root.resolve()):
        raise AgentActivityError("Agent activity path escapes repository root")
    return path


def _artifact_path_text(raw: Any) -> str:
    text = _bounded_text(raw, "artifact_path", required=False, max_length=240)
    if not text:
        return ""
    path = Path(text)
    if path.is_absolute() or ".." in path.parts or not text.startswith("artifacts/"):
        raise AgentActivityError("artifact_path must be a repo-local artifacts/ path")
    return text


def _bounded_text(
    raw: Any,
    field: str,
    *,
    required: bool = True,
    max_length: int = MAX_TEXT_LENGTH,
) -> str:
    text = str(raw or "").strip()
    if required and not text:
        raise AgentActivityError(f"{field} is required")
    if len(text) > max_length:
        raise AgentActivityError(f"{field} is too long")
    if SENSITIVE_TEXT_PATTERN.search(text):
        raise AgentActivityError(f"{field} contains secret-like material")
    return text


def _safety() -> dict[str, bool]:
    return {
        "metadata_only": True,
        "request_body_logged": False,
        "secret_values_returned": False,
        "secret_values_stored": False,
        "external_network": False,
        "action_execution": False,
        "destructive_actions_enabled": False,
        "live_trading": False,
        "broker_mutation": False,
        "installed_source_read": False,
    }


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()
