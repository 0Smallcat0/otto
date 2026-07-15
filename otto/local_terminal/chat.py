"""Local AI Chat workspace contracts and artifacts."""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from otto.local_terminal.advanced_context import sanitize_advanced_context


CHAT_PROVIDER = "local_dry_run_assistant"
MAX_SESSIONS = 100
MAX_MESSAGES_PER_SESSION = 400
MAX_LINKED_ARTIFACTS = 8
MAX_LINKED_ARTIFACT_BYTES = 128 * 1024
ALLOWED_ARTIFACT_PREFIXES = (
    "artifacts/backtests/",
    "artifacts/news/",
    "artifacts/paper/",
    "artifacts/portfolio/",
    "market_data/",
)
ALLOWED_ARTIFACT_EXTENSIONS = {".csv", ".json", ".jsonl", ".md", ".txt"}
ALLOWED_MESSAGE_EFFECTS = {"read_only", "dry_run_response"}
SECRET_PATTERNS = (
    re.compile(
        r"[\"']?(api[\s_-]*key|apikey|access[\s_-]*token|refresh[\s_-]*token|"
        r"secret[\s_-]*key|client[\s_-]*secret|private[\s_-]*key|password|"
        r"passphrase|pin|token|secret)[\"']?\s*[:=]\s*[\"']?[^\"'\s,}]+",
        re.IGNORECASE,
    ),
    re.compile(r"\bauthorization\s*:\s*[^,\s]+", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bprivate\s+key\b", re.IGNORECASE),
)


class ChatError(ValueError):
    """Raised when a local chat request violates chat rules."""


def default_chat_state() -> dict[str, Any]:
    return {
        "active_session_id": None,
        "sessions": {},
        "updated_at": "not started",
    }


def normalize_chat_state(state: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    default = default_chat_state()
    invalid_sessions = (
        {str(key): str(value) for key, value in state.get("invalid_sessions", {}).items()}
        if isinstance(state.get("invalid_sessions"), dict)
        else {}
    )
    if strict and invalid_sessions:
        first_key, first_value = next(iter(invalid_sessions.items()))
        raise ChatError(f"Chat state is invalid: {first_key}: {first_value}")

    raw_sessions = state.get("sessions")
    sessions: dict[str, dict[str, Any]] = {}
    if isinstance(raw_sessions, dict):
        if len(raw_sessions) > MAX_SESSIONS:
            raise ChatError(f"Chat sessions exceed limit of {MAX_SESSIONS}")
        for session_id, raw_session in raw_sessions.items():
            if not isinstance(raw_session, dict):
                if strict:
                    raise ChatError(f"Stored chat session {session_id} must be an object")
                invalid_sessions[str(session_id)] = "Stored chat session must be an object"
                continue
            try:
                session = _normalize_session(raw_session, fallback_id=str(session_id))
            except ChatError as exc:
                if strict:
                    raise ChatError(f"Stored chat session {session_id} is invalid: {exc}") from exc
                invalid_sessions[str(session_id)] = str(exc)
                continue
            sessions[session["session_id"]] = session
    elif raw_sessions not in (None, {}):
        if strict:
            raise ChatError("Stored chat sessions must be an object")
        invalid_sessions["sessions"] = "Stored chat sessions must be an object"

    active_id = str(state.get("active_session_id") or "")
    if active_id not in sessions:
        active_id = _latest_session_id(sessions)
    return {
        **default,
        "active_session_id": active_id or None,
        "sessions": sessions,
        "invalid_sessions": invalid_sessions,
        "updated_at": str(state.get("updated_at") or default["updated_at"]),
    }


def chat_payload(
    state: dict[str, Any], root: Path, context: dict[str, Any] | None = None
) -> dict[str, Any]:
    chat_state = normalize_chat_state(state, strict=False)
    active_id = chat_state["active_session_id"]
    messages, message_errors = (
        _read_messages(root, active_id, strict=False) if active_id else ([], {})
    )
    if active_id and active_id in chat_state["sessions"]:
        chat_state["sessions"][active_id]["message_count"] = len(messages)
    active_session = copy.deepcopy(chat_state["sessions"].get(active_id)) if active_id else None
    return {
        "active_session_id": active_id,
        "first_use": active_session is None,
        "sessions": _session_list(chat_state),
        "active_session": active_session,
        "messages": messages,
        "message_errors": message_errors,
        "invalid_sessions": chat_state["invalid_sessions"],
        "commands": ["New Chat", "Rename", "Delete", "Send", "Link Artifact"],
        "provider": provider_status(),
        "safety": safety_payload(),
        "artifact_root": "artifacts/chat",
        "context": sanitize_advanced_context(context),
        "context_contract": chat_context_contract(state, root, context),
        "session_health": chat_session_health_payload(state, root),
    }


def chat_context_contract(
    state: dict[str, Any],
    root: Path,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a metadata-only contract for AI Chat context use."""

    chat_state = normalize_chat_state(state, strict=False)
    active_id = chat_state["active_session_id"]
    messages, message_errors = (
        _read_messages(root, active_id, strict=False) if active_id else ([], {})
    )
    active_session = chat_state["sessions"].get(active_id) if active_id else None
    safe_context = sanitize_advanced_context(context)
    assistant_messages = [message for message in messages if message["role"] == "assistant"]
    latest_message = messages[-1] if messages else {}
    latest_assistant = assistant_messages[-1] if assistant_messages else {}
    linked_artifacts = (
        list(active_session.get("linked_artifacts", []))
        if isinstance(active_session, dict)
        else []
    )
    return {
        "mode": "metadata_only_ai_chat_context_contract",
        "limits": {
            "max_sessions": MAX_SESSIONS,
            "max_messages_per_session": MAX_MESSAGES_PER_SESSION,
            "max_prompt_chars": 4000,
            "max_linked_artifacts": MAX_LINKED_ARTIFACTS,
            "max_linked_artifact_bytes": MAX_LINKED_ARTIFACT_BYTES,
            "allowed_artifact_prefixes": list(ALLOWED_ARTIFACT_PREFIXES),
            "allowed_artifact_extensions": sorted(ALLOWED_ARTIFACT_EXTENSIONS),
        },
        "output_state": {
            "active_session_id": active_id or "",
            "session_count": len(chat_state["sessions"]),
            "message_count": len(messages),
            "assistant_message_count": len(assistant_messages),
            "message_error_count": len(message_errors),
            "invalid_session_count": len(chat_state["invalid_sessions"]),
            "latest_message_role": str(latest_message.get("role") or ""),
            "latest_message_effect": str(latest_message.get("effect") or ""),
            "latest_message_at": str(latest_message.get("created_at") or ""),
            "latest_assistant_at": str(latest_assistant.get("created_at") or ""),
            "messages_artifact_path": (
                f"artifacts/chat/{active_id}/messages.jsonl" if active_id else ""
            ),
            "assistant_output_mode": "local_dry_run_context_brief",
        },
        "source_citations": _chat_source_citations(safe_context),
        "artifact_provenance": {
            "linked_artifact_count": len(linked_artifacts),
            "linked_artifacts": linked_artifacts,
            "context_artifact_count": len(safe_context["artifacts"]),
            "context_artifacts": _chat_context_artifacts(safe_context),
        },
        "context_summary": safe_context["summary"],
        "safety": {
            "read_only": True,
            "metadata_only": True,
            "external_network": False,
            "provider_calls": False,
            "managed_llm": False,
            "artifact_content_read": False,
            "artifact_content_indexing": False,
            "secret_values_returned": False,
            "credentials_persisted": False,
            "broker_mutation": False,
            "ledger_mutation": False,
            "real_orders": False,
            "real_balance": False,
            "live_trading": False,
        },
    }


def chat_session_health_payload(state: dict[str, Any], root: Path) -> dict[str, Any]:
    """Return metadata-only health for local AI Chat session artifacts."""

    chat_state = normalize_chat_state(state, strict=False)
    rows = [_chat_session_health_row(root, chat_state, session) for session in _session_list(chat_state)]
    recovery_queue = _chat_session_recovery_queue(rows)
    latest = rows[0] if rows else {}
    return {
        "mode": "metadata_only_ai_chat_session_health",
        "contract": "ai_chat_session_health_v1",
        "generated_at": _utc_now(),
        "root": "artifacts/chat",
        "summary": {
            "session_count": len(rows),
            "complete_count": sum(1 for row in rows if row["health_state"] == "complete"),
            "empty_count": sum(1 for row in rows if row["health_state"] == "empty_session"),
            "partial_count": sum(1 for row in rows if row["health_state"].startswith("partial")),
            "missing_message_artifact_count": sum(
                1 for row in rows if row["health_state"] == "partial_missing_messages"
            ),
            "supervision_ready_count": sum(1 for row in rows if row["supervision_ready"]),
            "invalid_session_count": len(chat_state["invalid_sessions"]),
            "active_session_id": str(chat_state.get("active_session_id") or ""),
            "latest_session_id": str(latest.get("session_id") or ""),
            "recovery_queue_count": len(recovery_queue),
            "destructive_action_count": 0,
        },
        "sessions": rows,
        "recovery_queue": recovery_queue,
        "recommended_actions": [
            {
                "action_id": "ai_chat_create_session",
                "endpoint": "/api/ai-chat/sessions",
                "method": "POST",
                "ready": True,
                "reason": "Create a new local dry-run session when no healthy transcript is available.",
            },
            {
                "action_id": "ai_chat_context_contract",
                "endpoint": "/api/ai-chat/context-contract",
                "method": "GET",
                "ready": bool(rows),
                "reason": "Inspect metadata-only context limits and provenance before using a session.",
            },
        ],
        "safety": {
            "local_only": True,
            "read_only": True,
            "metadata_only": True,
            "message_content_read": False,
            "artifact_content_indexing": False,
            "request_response_replay": False,
            "writes_local_artifacts": False,
            "automatic_repair_enabled": False,
            "destructive_actions_enabled": False,
            "provider_calls": False,
            "managed_llm": False,
            "secret_values_returned": False,
            "credentials_persisted": False,
            "broker_mutation": False,
            "ledger_mutation": False,
            "real_orders": False,
            "real_balance": False,
            "live_trading": False,
        },
    }


def _chat_session_health_row(
    root: Path,
    chat_state: dict[str, Any],
    session: dict[str, Any],
) -> dict[str, Any]:
    session_id = str(session.get("session_id") or "")
    session_dir = _session_dir(root, session_id)
    messages_path = _messages_path(root, session_id)
    session_dir_exists = session_dir.is_dir()
    messages_exists = messages_path.is_file()
    stat = messages_path.stat() if messages_exists else None
    declared_message_count = int(session.get("message_count") or 0)
    if declared_message_count > 0 and not messages_exists:
        health_state = "partial_missing_messages"
    elif declared_message_count == 0 and not messages_exists:
        health_state = "empty_session"
    else:
        health_state = "complete"
    return {
        "session_id": session_id,
        "name": str(session.get("name") or ""),
        "provider": str(session.get("provider") or CHAT_PROVIDER),
        "active_session": str(chat_state.get("active_session_id") or "") == session_id,
        "created_at": str(session.get("created_at") or ""),
        "updated_at": str(session.get("updated_at") or ""),
        "health_state": health_state,
        "session_dir": f"artifacts/chat/{session_id}",
        "session_dir_exists": session_dir_exists,
        "messages_artifact_path": f"artifacts/chat/{session_id}/messages.jsonl",
        "messages_artifact_exists": messages_exists,
        "messages_bytes": stat.st_size if stat else 0,
        "latest_updated_at": _timestamp_text(stat.st_mtime) if stat else "",
        "declared_message_count": declared_message_count,
        "linked_artifact_count": len(session.get("linked_artifacts", [])),
        "supervision_ready": health_state in {"complete", "empty_session"},
        "recovery_hint": (
            "ready_for_agent_selection"
            if health_state == "complete"
            else (
                "send_a_local_dry_run_message_to_create_messages_artifact"
                if health_state == "empty_session"
                else "create a new local session or send a new dry-run message; do not repair transcript files in place"
            )
        ),
        "message_content_read": False,
        "destructive_actions_enabled": False,
    }


def _chat_session_recovery_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return [
            {
                "queue_id": "ai_chat_session_health:none",
                "session_id": "",
                "artifact_path": "artifacts/chat",
                "recommended_action": "ai_chat_create_session",
                "endpoint": "/api/ai-chat/sessions",
                "method": "POST",
                "reason": "No local AI Chat sessions exist.",
                "destructive_action_required": False,
                "writes_local_artifacts": True,
            }
        ]
    queue = []
    for row in rows:
        if row["health_state"] != "partial_missing_messages":
            continue
        queue.append(
            {
                "queue_id": f"ai_chat_session_health:{row['session_id']}:messages",
                "session_id": row["session_id"],
                "artifact_path": row["messages_artifact_path"],
                "recommended_action": "ai_chat_create_session",
                "endpoint": "/api/ai-chat/sessions",
                "method": "POST",
                "reason": "Stored session declares messages but the local transcript artifact is missing.",
                "destructive_action_required": False,
                "writes_local_artifacts": True,
            }
        )
    return queue


def provider_status() -> dict[str, Any]:
    return {
        "provider_id": CHAT_PROVIDER,
        "label": "Local assistant",
        "state": "dry_run",
        "external_network": False,
        "managed_cloud": False,
        "cloud_account_required": False,
        "subscription_required": False,
        "cr_required": False,
        "private_api_required": False,
        "secret_storage": "not_configured",
        "message": "Local dry-run responses only; no broker or ledger mutation.",
    }


def safety_payload() -> dict[str, Any]:
    return {
        "managed_llm": False,
        "cloud_account_required": False,
        "subscription_required": False,
        "cr_required": False,
        "private_api_required": False,
        "real_orders": False,
        "broker_mutation": False,
        "ledger_mutation": False,
        "credentials_persisted": False,
        "linked_artifacts_read_only": True,
    }


def create_chat_session(
    state: dict[str, Any], request: dict[str, Any], root: Path
) -> dict[str, Any]:
    chat_state = normalize_chat_state(copy.deepcopy(state))
    if len(chat_state["sessions"]) >= MAX_SESSIONS:
        raise ChatError(f"Chat sessions exceed limit of {MAX_SESSIONS}")
    now = _utc_now()
    session_id = f"chat-{uuid4().hex[:12]}"
    name = _session_name(request.get("name") or _default_session_name())
    session = _normalize_session(
        {
            "session_id": session_id,
            "name": name,
            "provider": CHAT_PROVIDER,
            "linked_artifacts": [],
            "message_count": 0,
            "created_at": now,
            "updated_at": now,
        }
    )
    chat_state["sessions"][session_id] = session
    chat_state["active_session_id"] = session_id
    chat_state["updated_at"] = now
    _session_dir(root, session_id).mkdir(parents=True, exist_ok=True)
    return chat_state


def rename_chat_session(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    chat_state = normalize_chat_state(copy.deepcopy(state))
    session_id = _session_id(request.get("session_id"))
    if session_id not in chat_state["sessions"]:
        raise ChatError("Chat session not found")
    now = _utc_now()
    chat_state["sessions"][session_id]["name"] = _session_name(request.get("name"))
    chat_state["sessions"][session_id]["updated_at"] = now
    chat_state["active_session_id"] = session_id
    chat_state["updated_at"] = now
    return chat_state


def select_chat_session(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    chat_state = normalize_chat_state(copy.deepcopy(state))
    session_id = _session_id(request.get("session_id"))
    if session_id not in chat_state["sessions"]:
        raise ChatError("Chat session not found")
    chat_state["active_session_id"] = session_id
    chat_state["updated_at"] = _utc_now()
    return chat_state


def delete_chat_session(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    if request.get("confirm") is not True:
        raise ChatError("Delete confirmation is required")
    chat_state = normalize_chat_state(copy.deepcopy(state))
    session_id = _session_id(request.get("session_id"))
    if session_id not in chat_state["sessions"]:
        raise ChatError("Chat session not found")
    chat_state["sessions"].pop(session_id)
    chat_state["active_session_id"] = _latest_session_id(chat_state["sessions"]) or None
    chat_state["updated_at"] = _utc_now()
    return chat_state


def remove_chat_session_artifacts(root: Path, session_id: str) -> None:
    _remove_session_dir(root, session_id)


def append_chat_message(
    state: dict[str, Any],
    request: dict[str, Any],
    root: Path,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    chat_state = normalize_chat_state(copy.deepcopy(state))
    session_id = str(request.get("session_id") or chat_state.get("active_session_id") or "")
    if not session_id:
        chat_state = create_chat_session(chat_state, {"name": _default_session_name()}, root)
        session_id = str(chat_state["active_session_id"])
    session_id = _session_id(session_id)
    if session_id not in chat_state["sessions"]:
        raise ChatError("Chat session not found")

    existing_messages, message_errors = _read_messages(root, session_id, strict=True)
    if message_errors:
        first_key, first_value = next(iter(message_errors.items()))
        raise ChatError(f"Stored chat messages are invalid: {first_key}: {first_value}")
    if len(existing_messages) + 2 > MAX_MESSAGES_PER_SESSION:
        raise ChatError(f"Chat messages exceed limit of {MAX_MESSAGES_PER_SESSION}")

    content = _message_content(request.get("content"))
    linked_artifacts = _linked_artifacts(root, request.get("linked_artifacts", []))
    now = _utc_now()
    user_message = {
        "message_id": f"msg-{uuid4().hex[:12]}",
        "session_id": session_id,
        "role": "user",
        "content": content,
        "linked_artifacts": linked_artifacts,
        "effect": "read_only",
        "broker_mutation": False,
        "created_at": now,
    }
    assistant_message = {
        "message_id": f"msg-{uuid4().hex[:12]}",
        "session_id": session_id,
        "role": "assistant",
        "content": _assistant_response(content, linked_artifacts, context),
        "linked_artifacts": [],
        "effect": "dry_run_response",
        "broker_mutation": False,
        "created_at": now,
    }
    _append_messages(root, session_id, [user_message, assistant_message])

    session = chat_state["sessions"][session_id]
    session["message_count"] = int(session.get("message_count", 0)) + 2
    session["linked_artifacts"] = _merge_artifact_paths(
        session.get("linked_artifacts", []),
        [artifact["path"] for artifact in linked_artifacts],
    )
    session["updated_at"] = now
    chat_state["active_session_id"] = session_id
    chat_state["updated_at"] = now
    return chat_state


def _normalize_session(raw: dict[str, Any], fallback_id: str | None = None) -> dict[str, Any]:
    session_id = _session_id(raw.get("session_id") or fallback_id)
    provider = str(raw.get("provider") or CHAT_PROVIDER)
    if provider != CHAT_PROVIDER:
        provider = CHAT_PROVIDER
    return {
        "session_id": session_id,
        "name": _session_name(raw.get("name")),
        "provider": provider,
        "linked_artifacts": _stored_artifact_paths(raw.get("linked_artifacts", [])),
        "message_count": _non_negative_int(raw.get("message_count", 0), "Message count"),
        "created_at": str(raw.get("created_at") or _utc_now()),
        "updated_at": str(raw.get("updated_at") or raw.get("created_at") or _utc_now()),
    }


def _session_list(chat_state: dict[str, Any]) -> list[dict[str, Any]]:
    sessions = list(chat_state["sessions"].values())
    return sorted(sessions, key=lambda session: str(session.get("updated_at", "")), reverse=True)


def _latest_session_id(sessions: dict[str, dict[str, Any]]) -> str:
    if not sessions:
        return ""
    return max(sessions.values(), key=lambda session: str(session.get("updated_at", "")))[
        "session_id"
    ]


def _read_messages(
    root: Path,
    session_id: str | None,
    *,
    strict: bool,
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    if not session_id:
        return [], {}
    path = _messages_path(root, session_id)
    if not path.exists():
        return [], {}
    messages = []
    errors: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], {path.name: "Cannot read chat messages"}
    if len(lines) > MAX_MESSAGES_PER_SESSION:
        message = f"Messages exceed limit of {MAX_MESSAGES_PER_SESSION}"
        if strict:
            raise ChatError(message)
        errors[path.name] = message
        lines = lines[:MAX_MESSAGES_PER_SESSION]
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
            messages.append(_normalize_message(root, raw, session_id))
        except (ChatError, json.JSONDecodeError) as exc:
            if strict:
                raise ChatError(f"Stored chat message line {index} is invalid: {exc}") from exc
            errors[f"{path.name}:{index}"] = str(exc)
    return messages, errors


def _normalize_message(root: Path, raw: Any, session_id: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ChatError("Chat message must be an object")
    role = str(raw.get("role") or "")
    if role not in {"user", "assistant"}:
        raise ChatError("Chat message role must be user or assistant")
    message_session_id = _session_id(raw.get("session_id") or session_id)
    if message_session_id != session_id:
        raise ChatError("Chat message session does not match")
    content = str(raw.get("content") or "").strip()
    if not content:
        raise ChatError("Chat message content is required")
    if _contains_secret(content):
        raise ChatError("Chat message appears to contain credential material")
    effect = str(raw.get("effect") or "read_only")
    if effect not in ALLOWED_MESSAGE_EFFECTS:
        raise ChatError("Chat message effect is not allowed")
    if raw.get("broker_mutation", False) not in (False, None):
        raise ChatError("Chat message cannot report broker mutation")
    return {
        "message_id": str(raw.get("message_id") or f"msg-{uuid4().hex[:12]}"),
        "session_id": message_session_id,
        "role": role,
        "content": content[:5000],
        "linked_artifacts": _message_artifacts(root, raw.get("linked_artifacts", [])),
        "effect": effect,
        "broker_mutation": False,
        "created_at": str(raw.get("created_at") or _utc_now()),
    }


def _message_artifacts(root: Path, raw: Any) -> list[dict[str, Any]]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise ChatError("Linked artifacts must be a list")
    if len(raw) > MAX_LINKED_ARTIFACTS:
        raise ChatError(f"Linked artifacts exceed limit of {MAX_LINKED_ARTIFACTS}")
    artifacts = []
    for item in raw[:MAX_LINKED_ARTIFACTS]:
        if not isinstance(item, dict):
            raise ChatError("Linked artifact rows must be objects")
        artifact = _artifact_metadata(root, _stored_artifact_path(item.get("path")))
        expected_bytes = item.get("bytes")
        if (
            expected_bytes not in (None, "")
            and _non_negative_int(expected_bytes, "Artifact bytes") != artifact["bytes"]
        ):
            raise ChatError("Linked artifact size changed")
        expected_digest = str(item.get("sha256") or "")
        if expected_digest and expected_digest != artifact["sha256"]:
            raise ChatError("Linked artifact digest changed")
        artifacts.append(artifact)
    return artifacts


def _append_messages(root: Path, session_id: str, messages: list[dict[str, Any]]) -> None:
    path = _messages_path(root, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for message in messages:
            handle.write(json.dumps(message, sort_keys=True))
            handle.write("\n")


def _linked_artifacts(root: Path, raw_artifacts: Any) -> list[dict[str, Any]]:
    paths = _stored_artifact_paths(raw_artifacts)
    if len(paths) > MAX_LINKED_ARTIFACTS:
        raise ChatError(f"Linked artifacts exceed limit of {MAX_LINKED_ARTIFACTS}")
    artifacts = []
    for path in paths:
        artifacts.append(_artifact_metadata(root, path))
    return artifacts


def _artifact_metadata(root: Path, raw_path: str) -> dict[str, Any]:
    resolved = _resolve_local_artifact(root, raw_path)
    size = resolved.stat().st_size
    if size > MAX_LINKED_ARTIFACT_BYTES:
        raise ChatError("Linked artifact is too large")
    digest = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return {
        "path": resolved.relative_to(root.resolve()).as_posix(),
        "bytes": size,
        "sha256": digest,
        "read_mode": "read_only",
    }


def _resolve_local_artifact(root: Path, raw_path: str) -> Path:
    if _looks_absolute(raw_path):
        raise ChatError("Linked artifact path must be repo-relative")
    relative = raw_path.replace("\\", "/").lstrip("/")
    if not any(relative.startswith(prefix) for prefix in ALLOWED_ARTIFACT_PREFIXES):
        raise ChatError("Linked artifact must be under allowed local artifact paths")
    resolved = (root / relative).resolve()
    root_resolved = root.resolve()
    if not resolved.is_relative_to(root_resolved):
        raise ChatError("Linked artifact must stay inside repository")
    if not resolved.is_file():
        raise ChatError("Linked artifact file was not found")
    if resolved.suffix.lower() not in ALLOWED_ARTIFACT_EXTENSIONS:
        raise ChatError("Linked artifact extension is not allowed")
    return resolved


def _stored_artifact_paths(raw: Any) -> list[str]:
    if raw in (None, ""):
        return []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        raise ChatError("Linked artifacts must be a list")
    paths = [_stored_artifact_path(item) for item in raw if str(item).strip()]
    return list(dict.fromkeys(paths))


def _stored_artifact_path(raw: Any) -> str:
    value = str(raw or "").strip().replace("\\", "/")
    if not value:
        raise ChatError("Linked artifact path is required")
    if _looks_absolute(value):
        raise ChatError("Linked artifact path must be repo-relative")
    value = value.lstrip("/")
    if len(value) > 240:
        raise ChatError("Linked artifact path is too long")
    if ".." in Path(value).parts:
        raise ChatError("Linked artifact must not contain parent traversal")
    if not any(value.startswith(prefix) for prefix in ALLOWED_ARTIFACT_PREFIXES):
        raise ChatError("Linked artifact must be under allowed local artifact paths")
    if Path(value).suffix.lower() not in ALLOWED_ARTIFACT_EXTENSIONS:
        raise ChatError("Linked artifact extension is not allowed")
    return value


def _merge_artifact_paths(existing: Any, incoming: list[str]) -> list[str]:
    merged = _stored_artifact_paths(existing) + incoming
    return list(dict.fromkeys(merged))[:MAX_LINKED_ARTIFACTS]


def _messages_path(root: Path, session_id: str) -> Path:
    return _session_dir(root, session_id) / "messages.jsonl"


def _session_dir(root: Path, session_id: str) -> Path:
    path = (root / "artifacts" / "chat" / _session_id(session_id)).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ChatError("Chat session path must stay inside repository")
    return path


def _remove_session_dir(root: Path, session_id: str) -> None:
    path = _session_dir(root, session_id)
    if path.exists():
        shutil.rmtree(path)


def _session_id(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value.startswith("chat-"):
        raise ChatError("Chat session id is required")
    suffix = value.removeprefix("chat-")
    if not suffix or len(suffix) > 32 or not all(ch.isalnum() or ch == "-" for ch in suffix):
        raise ChatError("Chat session id is invalid")
    return value


def _session_name(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ChatError("Session name is required")
    if _contains_secret(value):
        raise ChatError("Session name appears to contain credential material")
    return value[:80]


def _message_content(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        raise ChatError("Message content is required")
    if len(value) > 4000:
        raise ChatError("Message content is too long")
    if _contains_secret(value):
        raise ChatError("Message appears to contain credential material")
    return value


def _contains_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _assistant_response(
    content: str,
    linked_artifacts: list[dict[str, Any]],
    context: dict[str, Any] | None,
) -> str:
    digest = " ".join(content.split())[:220]
    safe_context = sanitize_advanced_context(context)
    summary = safe_context["summary"]
    focused_sources = _focused_context_sources(content, safe_context["sources"])
    source_summary = (
        "; ".join(
            (
                f"{source['label']}={source['state']}"
                f"/{source['record_count']} rows"
                f"/{source['cache_path'] or 'no-cache-path'}"
            )
            for source in focused_sources[:4]
        )
        or "no focused provider cache"
    )
    artifact_summary = (
        "; ".join(
            f"{artifact['path']} ({artifact['bytes']} bytes)"
            for artifact in linked_artifacts[:MAX_LINKED_ARTIFACTS]
        )
        or "none linked"
    )
    indexed_artifacts = (
        "; ".join(
            f"{artifact['kind']}:{artifact['path']}" for artifact in safe_context["artifacts"][:4]
        )
        or "none indexed"
    )
    return (
        "Local context brief. "
        f"Request digest: {digest}. "
        f"Provider/cache context: {summary['ready_source_count']} ready of "
        f"{summary['source_count']} sources; primary cache: "
        f"{summary['primary_cache_path'] or 'none'}; latest price: "
        f"{summary['latest_price'] or 'n/a'}. "
        f"Focused local sources: {source_summary}. "
        f"Linked local artifacts: {artifact_summary}. "
        f"Indexed local artifacts: {summary['artifact_count']} total; {indexed_artifacts}. "
        "Safety: read-only dry-run response; cannot place orders, change broker state, "
        "read real balances, persist credentials, or mutate ledgers."
    )


def _focused_context_sources(content: str, sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    query = content.lower()
    focus_terms = {
        "backtest": {"backtest", "strategy", "signal", "return", "drawdown"},
        "portfolio": {"portfolio", "holding", "risk", "allocation", "report"},
        "crypto": {"crypto", "btc", "eth", "quote", "candle", "trade", "market"},
        "macro": {"macro", "rate", "fx", "commodity", "fundamental", "sec", "dbnomics"},
        "news": {"news", "headline", "rss", "article"},
    }
    matched = {
        group for group, terms in focus_terms.items() if any(term in query for term in terms)
    }

    def score(source: dict[str, Any]) -> tuple[int, int]:
        searchable = " ".join(
            str(source.get(key) or "").lower()
            for key in ("source_id", "label", "kind", "detail", "cache_path")
        )
        focus_score = sum(1 for group in matched if group in searchable)
        ready_score = 1 if source.get("state") not in {"unavailable", "cache_missing"} else 0
        return (focus_score, ready_score)

    ranked = sorted(sources, key=score, reverse=True)
    focused = [source for source in ranked if score(source)[0] > 0]
    return focused or [source for source in ranked if score(source)[1] > 0] or ranked


def _chat_source_citations(context: dict[str, Any]) -> list[dict[str, Any]]:
    citations = []
    for index, source in enumerate(context["sources"], start=1):
        citations.append(
            {
                "citation_id": f"ctx-source-{index}",
                "source_id": source["source_id"],
                "label": source["label"],
                "kind": source["kind"],
                "state": source["state"],
                "provider_id": source["provider_id"],
                "cache_path": source["cache_path"],
                "record_count": source["record_count"],
                "updated_at": source["updated_at"],
                "detail": source["detail"],
            }
        )
    return citations


def _chat_context_artifacts(context: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "artifact_id": artifact["artifact_id"],
            "label": artifact["label"],
            "kind": artifact["kind"],
            "path": artifact["path"],
            "bytes": artifact["bytes"],
            "updated_at": artifact["updated_at"],
            "read_mode": "metadata_only",
        }
        for artifact in context["artifacts"]
    ]


def _default_session_name() -> str:
    return f"Local Session {uuid4().hex[:4].upper()}"


def _non_negative_int(raw: Any, label: str) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ChatError(f"{label} must be numeric") from None
    if value < 0:
        raise ChatError(f"{label} must be non-negative")
    return value


def _looks_absolute(raw_path: str) -> bool:
    return raw_path.startswith(("/", "\\")) or (len(raw_path) > 2 and raw_path[1] == ":")


def _timestamp_text(timestamp: float) -> str:
    if timestamp <= 0:
        return ""
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
