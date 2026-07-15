"""Local secret-storage gate contract for optional data-provider keys.

The HTTP surface only returns redacted status and write/delete actions. Secret
values are sealed in a repo-local ignored store and are never returned by API
payloads, diagnostics, docs, screenshots, or commits.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from otto.local_terminal.local_secrets import (
    LOCAL_SECRET_STORE,
    local_secret_status,
)


SECRET_GATE_DOC = "docs/planning/M19_LOCAL_SECRET_STORAGE_GATE.md"
PLANNED_SECRET_STORE = LOCAL_SECRET_STORE
SECRET_POLICY_VERSION = "local-secret-store-v1"
REDACTION_MARKER = "[redacted]"
SECRET_FIELD_PATTERN = re.compile(
    r"(api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|"
    r"secret[_-]?key|private[_-]?key|password|passphrase|pin|token|secret)",
    re.IGNORECASE,
)
SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"\b(api[\s_-]*key|access[\s_-]*token|refresh[\s_-]*token|client[\s_-]*secret|"
    r"secret[\s_-]*key|private[\s_-]*key|password|passphrase|pin|token|secret)"
    r"\s*[:=]\s*[^\s,;}]+",
    re.IGNORECASE,
)


def secret_gate_payload(
    root: Path,
    provider_state: dict[str, Any],
    *,
    design_doc_root: Path,
) -> dict[str, Any]:
    """Return local-secret gate status without exposing values."""

    optional_provider_ids = _optional_key_provider_ids(provider_state)
    planned_path = (root / PLANNED_SECRET_STORE).resolve()
    design_doc_exists = (design_doc_root / SECRET_GATE_DOC).is_file()
    store_status = local_secret_status(root, provider_state)
    writes_enabled = bool(store_status.get("writes_enabled"))
    forms_enabled = bool(store_status.get("key_entry_forms_enabled"))
    persistence_enabled = bool(store_status.get("secret_persistence_enabled"))
    eligible_provider_ids = _string_list(store_status.get("eligible_provider_ids"))
    blocked_provider_ids = _string_list(store_status.get("blocked_provider_ids"))
    stored_provider_ids = _string_list(store_status.get("stored_provider_ids"))
    return {
        "state": _gate_state(design_doc_exists, store_status),
        "policy_version": SECRET_POLICY_VERSION,
        "design_doc": SECRET_GATE_DOC,
        "design_doc_exists": design_doc_exists,
        "planned_store_path": PLANNED_SECRET_STORE,
        "planned_store_exists": planned_path.exists(),
        "writes_enabled": writes_enabled,
        "reads_enabled": False,
        "api_secret_value_reads_enabled": False,
        "internal_provider_reads_enabled": bool(
            store_status.get("internal_provider_reads_enabled")
        ),
        "key_entry_forms_enabled": forms_enabled,
        "secret_persistence_enabled": persistence_enabled,
        "local_only": True,
        "repo_local_ignored_path": True,
        "redaction_policy": "redact provider keys from API payloads, diagnostics, logs, docs, screenshots, and commits",
        "redaction_marker": REDACTION_MARKER,
        "optional_key_provider_count": len(optional_provider_ids),
        "eligible_provider_ids": eligible_provider_ids,
        "blocked_provider_ids": blocked_provider_ids,
        "stored_provider_ids": stored_provider_ids,
        "stored_provider_count": int(store_status.get("stored_provider_count") or 0),
        "storage_mode": str(store_status.get("storage_mode") or "unknown"),
        "storage_available": bool(store_status.get("storage_available")),
        "consent_phrase": str(store_status.get("consent_phrase") or ""),
        "allowed_provider_class": str(store_status.get("allowed_provider_class") or ""),
        "provider_secrets": store_status.get("provider_secrets", []),
        "forbidden_surfaces": [
            "tracked files",
            "logs",
            "screenshots",
            "diagnostics contents",
            "docs",
            "commit messages",
            "frontend runtime state",
        ],
        "enablement_requirements": [
            "local-only storage design reviewed and implemented",
            "redaction tests pass",
            "explicit opt-in setup UI reviewed",
            "source-wall tests pass",
            "code review pass",
            "security review pass",
        ],
        "storage_contract": {
            "format": "provider-scoped local JSON envelope with OS-sealed value material",
            "path": PLANNED_SECRET_STORE,
            "tracked_by_git": False,
            "created_by_current_runtime": persistence_enabled,
            "allowed_provider_class": "optional_local_key_data_provider_only",
            "forbidden_provider_class": "broker_exchange_private_or_live_trading",
            "http_value_read_endpoint": False,
            "paid_plan_provider_key_entry": False,
        },
        "redaction_probe": redact_secret_material(
            {
                "provider_id": "example_optional_provider",
                "api_key": "abc123",
                "note": "api key: abc123",
            }
        ),
    }


def redact_secret_material(value: Any) -> Any:
    """Return a copy with secret-looking fields and assignments redacted."""

    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = str(key)
            if SECRET_FIELD_PATTERN.search(safe_key):
                redacted[safe_key] = REDACTION_MARKER
            else:
                redacted[safe_key] = redact_secret_material(item)
        return redacted
    if isinstance(value, list):
        return [redact_secret_material(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secret_material(item) for item in value)
    if isinstance(value, str):
        return SECRET_ASSIGNMENT_PATTERN.sub(
            lambda match: f"{match.group(1)}: {REDACTION_MARKER}",
            value,
        )
    return value


def contains_secret_material(value: Any) -> bool:
    """Return True when redaction would change the supplied value."""

    return redact_secret_material(value) != value


def _optional_key_provider_ids(provider_state: dict[str, Any]) -> list[str]:
    providers = provider_state.get("providers") if isinstance(provider_state.get("providers"), list) else []
    ids: list[str] = []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        auth_mode = str(provider.get("auth_mode") or "")
        if "optional-local-key" in auth_mode:
            ids.append(str(provider.get("provider_id") or ""))
    return [provider_id for provider_id in ids if provider_id]


def _gate_state(design_doc_exists: bool, store_status: dict[str, Any]) -> str:
    if not design_doc_exists:
        return "disabled_until_design_review"
    if not bool(store_status.get("storage_available")):
        return "local_secret_store_unavailable"
    return "local_secret_store_ready"


def _string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item)]
