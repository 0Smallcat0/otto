"""Local help, about, update, and diagnostics payloads."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from otto.local_terminal.agent_contract import agent_operability_payload
from otto.local_terminal.artifact_lifecycle import artifact_lifecycle_payload
from otto.local_terminal.contracts import (
    DEFAULT_LOCAL_PROFILE_POLICY,
    DEFAULT_SAFETY_INVARIANTS,
    GLOBAL_MENUS,
    SHELL_ROUTES,
    is_repo_local_path,
)
from otto.local_terminal.forum import forum_artifact_health
from otto.local_terminal.governance import governance_summary
from otto.local_terminal.provider_refresh import provider_refresh_lifecycle_payload


HELP_SECTIONS: tuple[dict[str, Any], ...] = (
    {
        "section_id": "help_center",
        "label": "Help Center",
        "items": [
            "Local docs and workflow notes",
            "Troubleshooting and diagnostics",
            "Data storage and artifact locations",
            "Safety limits for trading, code, nodes, and quant workflows",
        ],
    },
    {
        "section_id": "diagnostics",
        "label": "Diagnostics",
        "items": [
            "Route and menu contract checks",
            "Repo-local storage path checks",
            "Safety invariant checks",
            "Optional local diagnostics artifact export",
        ],
    },
    {
        "section_id": "governance",
        "label": "Governance",
        "items": [
            "Provider setup and cache status",
            "Local secret-storage gate status",
            "Source-wall diagnostics",
            "Route artifact links",
        ],
    },
    {
        "section_id": "about",
        "label": "About Local Terminal",
        "items": [
            "Clean-room local financial terminal",
            "Local-first settings, layouts, reports, screenshots, and artifacts",
            "Public read-only data at runtime where available",
            "No cloud account, subscription, credits, billing, or private API required",
        ],
    },
    {
        "section_id": "privacy",
        "label": "Local Privacy",
        "items": [
            "Settings and workspace data stay under this repository by default",
            "Credentials and private keys are not requested or persisted",
            "Diagnostics report paths and sizes only, not file contents",
            "Local artifacts can be deleted from ignored artifact folders",
        ],
    },
    {
        "section_id": "terms",
        "label": "Local Terms",
        "items": [
            "Personal local research tool",
            "Analysis and journaled paper decisions, not licensed financial "
            "advice; no broker execution",
            "Paper and dry-run surfaces remain isolated from live execution",
            "Live-mode work requires a separate safety contract",
        ],
    },
    {
        "section_id": "attributions",
        "label": "Attributions",
        "items": [
            "Built from local observation evidence and independent implementation",
            "Public data adapters must keep source attribution in their own payloads",
            "No installed runtime, assets, branding, or implementation source copied",
        ],
    },
    {
        "section_id": "updates",
        "label": "Updates",
        "items": [
            "Local manifest version only",
            "No external update server check",
            "Use git history and local release notes for changes",
        ],
    },
)


def support_safety_payload() -> dict[str, bool | str]:
    return {
        "local_help_only": True,
        "external_browser": False,
        "external_network": False,
        "cloud_account_required": False,
        "subscription_required": False,
        "billing_enabled": False,
        "cr_required": False,
        "private_api_required": False,
        "credentials_persisted": False,
        "real_orders": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives_execution": False,
        "broker_mutation": False,
        "output": "local_help_and_diagnostics",
    }


def help_payload(
    store: Any,
    *,
    version: str,
    governance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "title": "Local Terminal Help",
        "version": version,
        "sections": list(HELP_SECTIONS),
        "diagnostics": diagnostics_payload(store, version=version, governance=governance),
        "governance": governance_summary(governance),
        "update_status": local_update_status(version),
        "safety": support_safety_payload(),
    }


def local_update_status(version: str) -> dict[str, Any]:
    return {
        "current_version": version,
        "channel": "local_manifest",
        "network_check": False,
        "external_update_server": False,
        "status": "local_manifest_only",
        "message": "External update checks are disabled for the local clean-room build.",
    }


def diagnostics_payload(
    store: Any,
    *,
    version: str,
    governance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = store.read_state()
    storage_rows = _storage_rows(store.root, state.get("storage", {}))
    safety = asdict(DEFAULT_SAFETY_INVARIANTS)
    profile_policy = asdict(DEFAULT_LOCAL_PROFILE_POLICY)
    governance_view = governance_summary(governance)
    artifact_lifecycle = _artifact_lifecycle_view(store, governance)
    agent_contract = _agent_contract_view(store, governance)
    provider_refresh_lifecycle = _provider_refresh_lifecycle_view(store, governance)
    forum_health = forum_artifact_health(store.root, store.read_forum_state())
    return {
        "run_id": None,
        "created_at": _utc_now(),
        "app": "Local Terminal",
        "version": version,
        "route_count": len(SHELL_ROUTES),
        "menu_count": len(GLOBAL_MENUS),
        "storage": storage_rows,
        "checks": {
            "routes_complete": len(SHELL_ROUTES) == 16,
            "menus_complete": len(GLOBAL_MENUS) == 4,
            "storage_repo_local": all(row["repo_local"] for row in storage_rows),
            "live_execution": "disabled",
            "forbidden_safety_disabled": not any(safety.values()),
            "remote_profile_requirements_disabled": not any(profile_policy.values()),
            "governance_loaded": governance_view["status"] == "local_governance_ready",
            "secret_value_api_reads_disabled": True,
            "secret_writes_data_provider_scoped": governance_view[
                "secret_writes_enabled"
            ]
            is True,
            "source_wall_configured": governance_view["source_wall_state"] == "configured",
            "forum_artifacts_repairable": forum_health["status"]
            in {"healthy", "repair_available", "orphan_review"},
            "forum_prune_destructive_disabled": forum_health["safety"][
                "destructive_actions_enabled"
            ]
            is False,
            "artifact_lifecycle_read_only": artifact_lifecycle["safety"]["read_only"] is True,
            "artifact_lifecycle_destructive_disabled": artifact_lifecycle["safety"][
                "destructive_actions_enabled"
            ]
            is False,
            "artifact_lifecycle_archive_plan_non_destructive": artifact_lifecycle[
                "actions"
            ].get("archive_plan_enabled")
            is True
            and artifact_lifecycle["actions"].get("archive_enabled") is False,
            "agent_contract_read_only": agent_contract["safety"]["read_only"] is True,
            "agent_contract_routes_complete": agent_contract["summary"][
                "routes_match_shell"
            ]
            is True,
            "agent_contract_disabled_actions_declared": agent_contract["summary"][
                "disabled_action_count"
            ]
            >= 1,
            "provider_refresh_lifecycle_read_only": provider_refresh_lifecycle["safety"][
                "read_only"
            ]
            is True,
            "provider_refresh_stale_recovery_non_mutating": provider_refresh_lifecycle[
                "safety"
            ]["job_status_mutation"]
            is False,
        },
        "safety": {
            **support_safety_payload(),
            "shell": safety,
            "profile_policy": profile_policy,
        },
        "governance": governance_view,
        "artifact_lifecycle": artifact_lifecycle,
        "agent_contract": agent_contract,
        "provider_refresh_lifecycle": provider_refresh_lifecycle,
        "forum_artifact_health": forum_health,
        "artifacts": {},
        "artifact_dir": None,
    }


def run_diagnostics(
    store: Any,
    *,
    version: str,
    governance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snapshot = diagnostics_payload(store, version=version, governance=governance)
    run_id = f"diag-{uuid4().hex[:12]}"
    artifact_dir = _safe_diagnostics_dir(store.root, run_id)
    artifacts = {
        "diagnostics": f"artifacts/diagnostics/{run_id}/diagnostics.json",
        "report": f"artifacts/diagnostics/{run_id}/report.md",
        "error_log": f"artifacts/diagnostics/{run_id}/error.log",
    }
    snapshot = {
        **snapshot,
        "run_id": run_id,
        "artifact_dir": f"artifacts/diagnostics/{run_id}",
        "artifacts": artifacts,
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifact_dir / "diagnostics.json", snapshot)
    (artifact_dir / "report.md").write_text(_diagnostics_markdown(snapshot), encoding="utf-8")
    (artifact_dir / "error.log").write_text("", encoding="utf-8")
    return snapshot


def run_governance_diagnostics(
    store: Any,
    *,
    version: str,
    governance: dict[str, Any],
) -> dict[str, Any]:
    """Write a read-only governance/cache diagnostic bundle for Settings."""

    run_id = f"gov-{uuid4().hex[:12]}"
    artifact_dir = _safe_prefixed_diagnostics_dir(store.root, run_id, prefix="gov-")
    governance_view = governance if isinstance(governance, dict) else {}
    summary = governance_summary(governance_view)
    provider_cache = {
        "summary": governance_view.get("summary", {}),
        "provider_setup": governance_view.get("provider_setup", []),
        "cache_controls": governance_view.get("cache_controls", []),
        "artifact_links": governance_view.get("artifact_links", []),
        "artifact_lifecycle": governance_view.get("artifact_lifecycle", {}),
        "agent_contract": governance_view.get("agent_contract", {}),
        "provider_refresh_lifecycle": governance_view.get("provider_refresh_lifecycle", {}),
    }
    artifact_lifecycle = provider_cache["artifact_lifecycle"]
    artifact_lifecycle = (
        artifact_lifecycle if isinstance(artifact_lifecycle, dict) else artifact_lifecycle_payload(store.root)
    )
    agent_contract = provider_cache["agent_contract"]
    agent_contract = (
        agent_contract if isinstance(agent_contract, dict) else agent_operability_payload(store.root)
    )
    provider_refresh_lifecycle = provider_cache["provider_refresh_lifecycle"]
    provider_refresh_lifecycle = (
        provider_refresh_lifecycle
        if isinstance(provider_refresh_lifecycle, dict)
        else provider_refresh_lifecycle_payload(store)
    )
    source_wall = governance_view.get("source_wall")
    source_wall = source_wall if isinstance(source_wall, dict) else {}
    local_secret_status = governance_view.get("local_secret_status")
    local_secret_status = local_secret_status if isinstance(local_secret_status, dict) else {}
    safety = {
        "output_mode": "local_governance_cache_diagnostics",
        "read_only": True,
        "external_network": False,
        "cache_delete_enabled": False,
        "cache_prune_enabled": False,
        "artifact_prune_enabled": False,
        "artifact_archive_plan_write_enabled": True,
        "artifact_archive_enabled": False,
        "artifact_delete_enabled": False,
        "artifact_content_reads_enabled": False,
        "agent_contract_read_only": True,
        "agent_contract_content_reads_enabled": False,
        "provider_refresh_lifecycle_read_only": True,
        "provider_refresh_status_recovery_writes_enabled": False,
        "secret_value_api_reads_enabled": False,
        "data_provider_secret_writes_enabled": bool(
            local_secret_status.get("writes_enabled", False)
        ),
        "key_entry_forms_enabled": bool(
            local_secret_status.get("key_entry_forms_enabled", False)
        ),
        "installed_source_read": False,
        "private_api_key_flow": False,
        "real_order_path": False,
        "real_balance_read": False,
        "broker_mutation": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives_execution": False,
    }
    checks = {
        "governance_loaded": summary["status"] == "local_governance_ready",
        "provider_setup_rows_present": bool(provider_cache["provider_setup"]),
        "cache_controls_present": bool(provider_cache["cache_controls"]),
        "source_wall_configured": summary["source_wall_state"] == "configured",
        "secret_value_api_reads_disabled": local_secret_status.get(
            "api_secret_value_reads_enabled", False
        )
        is False,
        "secret_writes_data_provider_scoped": local_secret_status.get(
            "allowed_provider_class"
        )
        == "optional_local_secret_data_provider",
        "key_forms_data_provider_scoped": bool(
            local_secret_status.get("key_entry_forms_enabled", False)
        )
        == bool(local_secret_status.get("writes_enabled", False)),
        "installed_source_not_read": source_wall.get("installed_source_read") is False,
        "destructive_cache_actions_disabled": all(
            isinstance(row, dict) and row.get("destructive_actions_enabled") is False
            for row in provider_cache["cache_controls"]
            if isinstance(row, dict)
        ),
        "artifact_lifecycle_rows_present": bool(artifact_lifecycle.get("roots")),
        "artifact_lifecycle_metadata_only": artifact_lifecycle.get("safety", {}).get("content_read")
        is False,
        "destructive_artifact_actions_disabled": artifact_lifecycle.get("safety", {}).get(
            "destructive_actions_enabled"
        )
        is False,
        "artifact_archive_plan_non_destructive": artifact_lifecycle.get("actions", {}).get(
            "archive_plan_enabled"
        )
        is True
        and artifact_lifecycle.get("actions", {}).get("archive_enabled") is False,
        "agent_contract_routes_complete": agent_contract.get("summary", {}).get(
            "routes_match_shell"
        )
        is True,
        "agent_contract_actions_present": bool(agent_contract.get("actions")),
        "agent_contract_selectors_present": bool(agent_contract.get("selectors")),
        "agent_contract_safety_read_only": agent_contract.get("safety", {}).get("read_only")
        is True,
        "provider_refresh_lifecycle_rows_present": isinstance(
            provider_refresh_lifecycle.get("runs"), list
        ),
        "provider_refresh_lifecycle_read_only": provider_refresh_lifecycle.get(
            "safety", {}
        ).get("read_only")
        is True,
        "provider_refresh_destructive_cleanup_disabled": provider_refresh_lifecycle.get(
            "safety", {}
        ).get("destructive_actions_enabled")
        is False,
    }
    artifacts = {
        "governance": f"artifacts/diagnostics/{run_id}/governance.json",
        "provider_cache": f"artifacts/diagnostics/{run_id}/provider_cache.json",
        "artifact_lifecycle": f"artifacts/diagnostics/{run_id}/artifact_lifecycle.json",
        "agent_contract": f"artifacts/diagnostics/{run_id}/agent_contract.json",
        "provider_refresh_lifecycle": (
            f"artifacts/diagnostics/{run_id}/provider_refresh_lifecycle.json"
        ),
        "source_wall": f"artifacts/diagnostics/{run_id}/source_wall.json",
        "manifest": f"artifacts/diagnostics/{run_id}/manifest.json",
        "report": f"artifacts/diagnostics/{run_id}/report.md",
        "error_log": f"artifacts/diagnostics/{run_id}/error.log",
    }
    manifest = {
        "run_id": run_id,
        "created_at": _utc_now(),
        "version": version,
        "output_mode": safety["output_mode"],
        "artifact_dir": f"artifacts/diagnostics/{run_id}",
        "artifacts": artifacts,
        "summary": summary,
        "checks": checks,
        "safety": safety,
        "source_wall": {
            "state": source_wall.get("state", "unknown"),
            "installed_source_read": source_wall.get("installed_source_read", False),
            "installed_assets_copied": source_wall.get("installed_assets_copied", False),
            "runtime_branding_copied": source_wall.get("runtime_branding_copied", False),
        },
        "local_secret_status": {
            "state": local_secret_status.get("state", "unknown"),
            "planned_store_path": local_secret_status.get(
                "planned_store_path", "settings/local_secrets.json"
            ),
            "planned_store_exists": local_secret_status.get("planned_store_exists", False),
            "writes_enabled": local_secret_status.get("writes_enabled", False),
            "reads_enabled": local_secret_status.get("reads_enabled", False),
            "api_secret_value_reads_enabled": local_secret_status.get(
                "api_secret_value_reads_enabled", False
            ),
            "internal_provider_reads_enabled": local_secret_status.get(
                "internal_provider_reads_enabled", False
            ),
            "key_entry_forms_enabled": local_secret_status.get(
                "key_entry_forms_enabled", False
            ),
            "secret_persistence_enabled": local_secret_status.get(
                "secret_persistence_enabled", False
            ),
            "policy_version": local_secret_status.get("policy_version", "unknown"),
            "optional_key_provider_count": local_secret_status.get(
                "optional_key_provider_count", 0
            ),
        },
    }
    snapshot = {
        **manifest,
        "status": "saved_locally",
        "governance": governance_view,
        "provider_cache": provider_cache,
    }

    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifact_dir / "governance.json", governance_view)
    _write_json(artifact_dir / "provider_cache.json", provider_cache)
    _write_json(artifact_dir / "artifact_lifecycle.json", artifact_lifecycle)
    _write_json(artifact_dir / "agent_contract.json", agent_contract)
    _write_json(artifact_dir / "provider_refresh_lifecycle.json", provider_refresh_lifecycle)
    _write_json(artifact_dir / "source_wall.json", source_wall)
    _write_json(artifact_dir / "manifest.json", manifest)
    (artifact_dir / "report.md").write_text(
        _governance_diagnostics_markdown(snapshot), encoding="utf-8"
    )
    (artifact_dir / "error.log").write_text("", encoding="utf-8")
    return snapshot


def _storage_rows(root: Path, storage: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, raw_path in sorted(storage.items()):
        path = str(raw_path)
        repo_local = is_repo_local_path(path)
        resolved = (root / path).resolve() if repo_local else root.resolve()
        stays_inside = repo_local and resolved.is_relative_to(root.resolve())
        rows.append(
            {
                "key": key,
                "path": path,
                "repo_local": repo_local,
                "stays_inside_repo": stays_inside,
                "exists": resolved.exists() if stays_inside else False,
                "bytes": _path_size(resolved) if stays_inside and resolved.is_file() else 0,
            }
        )
    return rows


def _artifact_lifecycle_view(store: Any, governance: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(governance, dict):
        payload = governance.get("artifact_lifecycle")
        if isinstance(payload, dict):
            return payload
    return artifact_lifecycle_payload(store.root)


def _agent_contract_view(store: Any, governance: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(governance, dict):
        payload = governance.get("agent_contract")
        if isinstance(payload, dict):
            return payload
    return agent_operability_payload(store.root)


def _provider_refresh_lifecycle_view(
    store: Any,
    governance: dict[str, Any] | None,
) -> dict[str, Any]:
    if isinstance(governance, dict):
        payload = governance.get("provider_refresh_lifecycle")
        if isinstance(payload, dict):
            return payload
    return provider_refresh_lifecycle_payload(store)


def _path_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _safe_diagnostics_dir(root: Path, run_id: str) -> Path:
    if not run_id.startswith("diag-") or len(run_id) != 17:
        raise ValueError("Diagnostics run id is invalid")
    return _safe_prefixed_diagnostics_dir(root, run_id, prefix="diag-")


def _safe_prefixed_diagnostics_dir(root: Path, run_id: str, *, prefix: str) -> Path:
    if not run_id.startswith(prefix) or len(run_id) != len(prefix) + 12:
        raise ValueError("Diagnostics run id is invalid")
    diagnostics_root = (root / "artifacts" / "diagnostics").resolve()
    artifact_dir = (diagnostics_root / run_id).resolve()
    if not artifact_dir.is_relative_to(diagnostics_root):
        raise ValueError("Diagnostics artifact directory must stay under artifacts/diagnostics")
    return artifact_dir


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _diagnostics_markdown(snapshot: dict[str, Any]) -> str:
    checks = "\n".join(
        f"- {key}: {value}" for key, value in snapshot.get("checks", {}).items()
    )
    storage = "\n".join(
        f"- {row['key']}: {row['path']} ({row['bytes']} bytes)"
        for row in snapshot.get("storage", [])
    )
    governance = "\n".join(
        f"- {key}: {value}" for key, value in snapshot.get("governance", {}).items()
    )
    forum_health = snapshot.get("forum_artifact_health", {})
    forum_summary = forum_health.get("summary") if isinstance(forum_health, dict) else {}
    artifact_lifecycle = snapshot.get("artifact_lifecycle", {})
    lifecycle_summary = (
        artifact_lifecycle.get("summary") if isinstance(artifact_lifecycle, dict) else {}
    )
    agent_contract = snapshot.get("agent_contract", {})
    agent_summary = agent_contract.get("summary") if isinstance(agent_contract, dict) else {}
    provider_refresh = snapshot.get("provider_refresh_lifecycle", {})
    refresh_summary = (
        provider_refresh.get("summary") if isinstance(provider_refresh, dict) else {}
    )
    forum_lines = "\n".join(
        f"- {key}: {value}"
        for key, value in (forum_summary if isinstance(forum_summary, dict) else {}).items()
    )
    lifecycle_lines = "\n".join(
        f"- {key}: {value}"
        for key, value in (
            lifecycle_summary if isinstance(lifecycle_summary, dict) else {}
        ).items()
    )
    agent_lines = "\n".join(
        f"- {key}: {value}"
        for key, value in (agent_summary if isinstance(agent_summary, dict) else {}).items()
    )
    provider_refresh_lines = "\n".join(
        f"- {key}: {value}"
        for key, value in (refresh_summary if isinstance(refresh_summary, dict) else {}).items()
    )
    return (
        "# Local Diagnostics\n\n"
        f"Run: {snapshot['run_id']}\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Governance\n\n"
        f"{governance}\n\n"
        "## Forum Artifact Health\n\n"
        f"- status: {forum_health.get('status', 'unknown') if isinstance(forum_health, dict) else 'unknown'}\n"
        f"{forum_lines}\n\n"
        "## Artifact Lifecycle\n\n"
        f"{lifecycle_lines}\n\n"
        "## Agent Contract\n\n"
        f"{agent_lines}\n\n"
        "## Provider Refresh Lifecycle\n\n"
        f"{provider_refresh_lines}\n\n"
        "## Storage\n\n"
        f"{storage}\n"
    )


def _governance_diagnostics_markdown(snapshot: dict[str, Any]) -> str:
    summary = "\n".join(
        f"- {key}: {value}" for key, value in snapshot.get("summary", {}).items()
    )
    checks = "\n".join(
        f"- {key}: {value}" for key, value in snapshot.get("checks", {}).items()
    )
    safety = "\n".join(
        f"- {key}: {value}" for key, value in snapshot.get("safety", {}).items()
    )
    artifacts = "\n".join(
        f"- {key}: {value}" for key, value in snapshot.get("artifacts", {}).items()
    )
    artifact_lifecycle = snapshot.get("provider_cache", {}).get("artifact_lifecycle", {})
    lifecycle_summary = (
        artifact_lifecycle.get("summary") if isinstance(artifact_lifecycle, dict) else {}
    )
    lifecycle = "\n".join(
        f"- {key}: {value}"
        for key, value in (
            lifecycle_summary if isinstance(lifecycle_summary, dict) else {}
        ).items()
    )
    agent_contract = snapshot.get("provider_cache", {}).get("agent_contract", {})
    agent_summary = agent_contract.get("summary") if isinstance(agent_contract, dict) else {}
    provider_refresh = snapshot.get("provider_cache", {}).get("provider_refresh_lifecycle", {})
    refresh_summary = (
        provider_refresh.get("summary") if isinstance(provider_refresh, dict) else {}
    )
    agent = "\n".join(
        f"- {key}: {value}"
        for key, value in (agent_summary if isinstance(agent_summary, dict) else {}).items()
    )
    provider_refresh_lines = "\n".join(
        f"- {key}: {value}"
        for key, value in (refresh_summary if isinstance(refresh_summary, dict) else {}).items()
    )
    return (
        "# Governance Diagnostics\n\n"
        f"Run: {snapshot['run_id']}\n\n"
        f"Output mode: {snapshot['output_mode']}\n\n"
        "## Summary\n\n"
        f"{summary}\n\n"
        "## Checks\n\n"
        f"{checks}\n\n"
        "## Safety\n\n"
        f"{safety}\n\n"
        "## Artifact Lifecycle\n\n"
        f"{lifecycle}\n\n"
        "## Agent Contract\n\n"
        f"{agent}\n\n"
        "## Provider Refresh Lifecycle\n\n"
        f"{provider_refresh_lines}\n\n"
        "## Artifacts\n\n"
        f"{artifacts}\n"
    )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
