"""Local governance payloads for settings, profile, help, and forum surfaces."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.local_terminal.agent_contract import agent_operability_payload
from src.local_terminal.artifact_lifecycle import artifact_lifecycle_payload
from src.local_terminal.contracts import (
    DEFAULT_LOCAL_PROFILE_POLICY,
    DEFAULT_SAFETY_INVARIANTS,
    is_repo_local_path,
)
from src.local_terminal.live_safety import live_safety_payload
from src.local_terminal.provider_refresh import (
    provider_refresh_lifecycle_payload,
    provider_refresh_schedule_plan_payload,
)
from src.local_terminal.providers import providers_payload
from src.local_terminal.secret_gate import secret_gate_payload


APPEARANCE_TOKEN_SOURCE = "frontend/src/theme.css"
COMPONENT_TOKEN_SOURCE = "frontend/src/terminal-components.css"
REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_USAGE_ROOTS: tuple[tuple[str, str, str], ...] = (
    ("backtests", "Backtests", "artifacts/backtests"),
    ("paper", "Paper ledger", "artifacts/paper"),
    ("portfolio", "Portfolio state", "artifacts/portfolio"),
    ("portfolio_reports", "Portfolio reports", "artifacts/portfolio/reports"),
    ("diagnostics", "Diagnostics", "artifacts/diagnostics"),
    ("forum", "Forum notes", "artifacts/forum"),
    ("chat", "AI Chat", "artifacts/chat"),
    ("code_workspace", "Code workspace", "artifacts/code_workspace"),
    ("quant_lab", "Quant Lab", "artifacts/quant_lab"),
    ("quantlib", "QuantLib", "artifacts/quantlib"),
)


def governance_payload(
    store: Any,
    *,
    version: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a clean-room local governance view without exposing credentials."""

    state = store.read_state()
    provider_state = providers_payload(store)
    live_state = live_safety_payload()
    context = context if isinstance(context, dict) else {}
    secret_status = _local_secret_status(store.root, provider_state)
    artifact_lifecycle = artifact_lifecycle_payload(store.root)
    agent_contract = agent_operability_payload(store.root)
    provider_refresh_lifecycle = provider_refresh_lifecycle_payload(store)
    provider_refresh_schedule_plan = provider_refresh_schedule_plan_payload(
        store,
        provider_payload=provider_state,
    )
    return {
        "generated_at": _utc_now(),
        "version": version,
        "summary": _summary(
            provider_state,
            live_state,
            context,
            artifact_lifecycle,
            agent_contract,
            provider_refresh_lifecycle,
        ),
        "provider_setup": _provider_setup(provider_state, secret_status),
        "cache_controls": _cache_controls(provider_state),
        "local_secret_status": secret_status,
        "source_wall": _source_wall_status(),
        "appearance": _appearance_status(state.get("settings", {}), state.get("profile", {})),
        "storage_paths": _storage_paths(store.root, state.get("storage", {})),
        "safety_gates": _safety_gates(live_state),
        "profile_scope": _profile_scope(state.get("profile", {})),
        "profile_usage": _profile_usage(store.root, version),
        "artifact_lifecycle": artifact_lifecycle,
        "agent_contract": agent_contract,
        "provider_refresh_lifecycle": provider_refresh_lifecycle,
        "provider_refresh_schedule_plan": provider_refresh_schedule_plan,
        "artifact_links": _artifact_links(context),
        "safety": {
            "cloud_account_required": False,
            "billing_enabled": False,
            "subscription_required": False,
            "private_api_key_flow": False,
            "real_order_path": False,
            "real_balance_read": False,
            "installed_source_read": False,
        },
    }


def governance_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload if isinstance(payload, dict) else {}
    secret_status = payload.get("local_secret_status")
    secret_status = secret_status if isinstance(secret_status, dict) else {}
    summary = payload.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    source_wall = payload.get("source_wall")
    source_wall = source_wall if isinstance(source_wall, dict) else {}
    return {
        "status": str(summary.get("status") or "not_loaded"),
        "provider_count": _int(summary.get("provider_count")),
        "active_provider_count": _int(summary.get("active_provider_count")),
        "cache_count": _int(summary.get("cache_count")),
        "artifact_link_count": _int(summary.get("artifact_link_count")),
        "agent_route_count": _int(summary.get("agent_route_count")),
        "agent_action_count": _int(summary.get("agent_action_count")),
        "agent_disabled_action_count": _int(summary.get("agent_disabled_action_count")),
        "secret_gate_state": str(secret_status.get("state") or "unknown"),
        "secret_policy_version": str(secret_status.get("policy_version") or "unknown"),
        "secret_writes_enabled": bool(secret_status.get("writes_enabled")),
        "key_entry_forms_enabled": bool(secret_status.get("key_entry_forms_enabled")),
        "source_wall_state": str(source_wall.get("state") or "unknown"),
    }


def _summary(
    provider_state: dict[str, Any],
    live_state: dict[str, Any],
    context: dict[str, Any],
    artifact_lifecycle: dict[str, Any],
    agent_contract: dict[str, Any],
    provider_refresh_lifecycle: dict[str, Any],
) -> dict[str, Any]:
    provider_summary = provider_state.get("summary")
    provider_summary = provider_summary if isinstance(provider_summary, dict) else {}
    context_summary = context.get("summary") if isinstance(context.get("summary"), dict) else {}
    lifecycle_summary = (
        artifact_lifecycle.get("summary") if isinstance(artifact_lifecycle.get("summary"), dict) else {}
    )
    agent_summary = (
        agent_contract.get("summary") if isinstance(agent_contract.get("summary"), dict) else {}
    )
    refresh_lifecycle_summary = (
        provider_refresh_lifecycle.get("summary")
        if isinstance(provider_refresh_lifecycle.get("summary"), dict)
        else {}
    )
    return {
        "status": "local_governance_ready",
        "provider_count": _int(provider_summary.get("provider_count")),
        "active_provider_count": _int(provider_summary.get("active")),
        "stale_provider_count": _int(provider_summary.get("stale_cache")),
        "key_required_count": _int(provider_summary.get("key_required")),
        "plan_required_count": _int(provider_summary.get("plan_required")),
        "disabled_by_safety_count": _int(provider_summary.get("disabled_by_safety")),
        "cache_count": len(provider_state.get("caches", []))
        if isinstance(provider_state.get("caches"), list)
        else 0,
        "artifact_link_count": _int(context_summary.get("artifact_count")),
        "artifact_root_count": _int(lifecycle_summary.get("root_count")),
        "active_artifact_root_count": _int(lifecycle_summary.get("active_root_count")),
        "artifact_file_count": _int(lifecycle_summary.get("file_count")),
        "artifact_archive_plan_run_count": _int(
            lifecycle_summary.get("archive_plan_run_count")
        ),
        "agent_route_count": _int(agent_summary.get("route_count")),
        "agent_action_count": _int(agent_summary.get("action_count")),
        "agent_disabled_action_count": _int(agent_summary.get("disabled_action_count")),
        "agent_routes_match_shell": bool(agent_summary.get("routes_match_shell")),
        "provider_refresh_run_count": _int(refresh_lifecycle_summary.get("run_count")),
        "provider_refresh_stale_interrupted_count": _int(
            refresh_lifecycle_summary.get("stale_interrupted_count")
        ),
        "provider_refresh_recovery_recommended_count": _int(
            refresh_lifecycle_summary.get("recovery_recommended_count")
        ),
        "live_safety_status": str(live_state.get("status") or "unknown"),
    }


def _provider_setup(
    provider_state: dict[str, Any],
    secret_status: dict[str, Any],
) -> list[dict[str, Any]]:
    providers = provider_state.get("providers") if isinstance(provider_state.get("providers"), list) else []
    secret_rows = {
        str(row.get("provider_id") or ""): row
        for row in secret_status.get("provider_secrets", [])
        if isinstance(row, dict)
    }
    rows: list[dict[str, Any]] = []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        auth_mode = str(provider.get("auth_mode") or "")
        health = provider.get("health") if isinstance(provider.get("health"), dict) else {}
        optional_key = "optional-local-key" in auth_mode
        forbidden = auth_mode == "forbidden"
        secret_row = secret_rows.get(str(provider.get("provider_id") or ""))
        secret_row = secret_row if isinstance(secret_row, dict) else {}
        eligible_secret = bool(secret_row.get("eligible"))
        stored_secret = bool(secret_row.get("stored"))
        form_enabled = optional_key and eligible_secret and bool(
            secret_status.get("key_entry_forms_enabled")
        )
        rows.append(
            {
                "provider_id": str(provider.get("provider_id") or ""),
                "label": str(provider.get("label") or ""),
                "implementation_status": str(provider.get("implementation_status") or ""),
                "auth_mode": auth_mode,
                "state": str(health.get("state") or provider.get("capability_state") or ""),
                "cache_path": str(health.get("cache_path") or ""),
                "retrieved_at": str(health.get("retrieved_at") or ""),
                "docs_checked_at": str(provider.get("docs_checked_at") or ""),
                "setup_state": _setup_state(
                    auth_mode,
                    str(health.get("state") or ""),
                    eligible_secret=eligible_secret,
                    stored_secret=stored_secret,
                ),
                "form_enabled": form_enabled,
                "secret_persistence_enabled": form_enabled
                and bool(secret_status.get("secret_persistence_enabled")),
                "secret_stored": stored_secret,
                "secret_sealed_id": str(secret_row.get("sealed_id") or ""),
                "secret_updated_at": str(secret_row.get("updated_at") or ""),
                "secret_blocked_reason": str(secret_row.get("blocked_reason") or ""),
                "optional_key": optional_key,
                "forbidden": forbidden,
                "message": _setup_message(provider, health, secret_row),
            }
        )
    return rows


def _cache_controls(provider_state: dict[str, Any]) -> list[dict[str, Any]]:
    caches = provider_state.get("caches") if isinstance(provider_state.get("caches"), list) else []
    rows: list[dict[str, Any]] = []
    for cache in caches:
        if not isinstance(cache, dict):
            continue
        rows.append(
            {
                "cache_id": str(cache.get("cache_id") or ""),
                "provider_id": str(cache.get("provider_id") or ""),
                "path": str(cache.get("path") or ""),
                "state": str(cache.get("state") or ""),
                "exists": bool(cache.get("exists")),
                "runtime_source": str(cache.get("runtime_source") or ""),
                "retrieved_at": str(cache.get("retrieved_at") or ""),
                "age_seconds": cache.get("age_seconds"),
                "ttl_seconds": _int(cache.get("ttl_seconds")),
                "control_state": _cache_control_state(str(cache.get("state") or "")),
                "safe_actions": _cache_safe_actions(str(cache.get("cache_id") or "")),
                "destructive_actions_enabled": False,
            }
        )
    return rows


def _local_secret_status(root: Path, provider_state: dict[str, Any]) -> dict[str, Any]:
    return secret_gate_payload(root, provider_state, design_doc_root=REPO_ROOT)


def _source_wall_status() -> dict[str, Any]:
    return {
        "state": "configured",
        "runtime_policy": "observe reference UI only; do not read installed implementation source",
        "installed_source_read": False,
        "installed_assets_copied": False,
        "runtime_branding_copied": False,
        "tests": [
            "tests/test_clean_room_source_wall.py",
            "tests/test_m19_governance_routes.py",
        ],
        "checks": {
            "source_wall_tests_declared": True,
            "runtime_surfaces_brand_neutral": True,
            "credentials_not_persisted": True,
            "installed_source_policy_visible": True,
        },
    }


def _appearance_status(settings: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "active_theme": str(settings.get("theme") or profile.get("theme") or "system"),
        "profile_theme": str(profile.get("theme") or "system"),
        "compact_mode": bool(settings.get("compact_mode")),
        "token_source": APPEARANCE_TOKEN_SOURCE,
        "component_source": COMPONENT_TOKEN_SOURCE,
        "style_policy": "muted dense terminal panels with low-contrast dark gray tokens",
        "tokens": [
            "terminal-bg",
            "terminal-shell",
            "terminal-panel",
            "terminal-text",
            "terminal-muted",
            "terminal-accent",
            "terminal-green",
            "terminal-red",
            "terminal-cyan",
        ],
    }


def _storage_paths(root: Path, storage: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def _safety_gates(live_state: dict[str, Any]) -> dict[str, Any]:
    required = (
        live_state.get("required_gates")
        if isinstance(live_state.get("required_gates"), list)
        else []
    )
    forbidden = (
        live_state.get("forbidden_capabilities")
        if isinstance(live_state.get("forbidden_capabilities"), dict)
        else {}
    )
    return {
        "status": str(live_state.get("status") or "unknown"),
        "contract_reviewed": bool(live_state.get("contract_reviewed")),
        "security_reviewed": bool(live_state.get("security_reviewed")),
        "live_mode_enabled": bool(live_state.get("live_mode_enabled")),
        "paper_mode_enabled": bool(live_state.get("paper_mode_enabled")),
        "required_gates": required,
        "forbidden_capabilities": forbidden,
        "disabled_action_count": len(live_state.get("disabled_actions", []))
        if isinstance(live_state.get("disabled_actions"), list)
        else 0,
    }


def _profile_scope(profile: dict[str, Any]) -> dict[str, Any]:
    profile_policy = asdict(DEFAULT_LOCAL_PROFILE_POLICY)
    safety = asdict(DEFAULT_SAFETY_INVARIANTS)
    return {
        "profile_id": str(profile.get("profile_id") or "local-default"),
        "display_name": str(profile.get("display_name") or "Local User")[:80],
        "default_route": str(profile.get("default_route") or "dashboard"),
        "theme": str(profile.get("theme") or "system"),
        "local_only": True,
        "cloud_identity": False,
        "billing_identity": False,
        "private_api_identity": False,
        "profile_policy": profile_policy,
        "safety_invariants": safety,
    }


def _profile_usage(root: Path, version: str) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    total_files = 0
    total_bytes = 0
    latest_ts = 0.0
    root_resolved = root.resolve()
    for usage_id, label, relative_path in PROFILE_USAGE_ROOTS:
        path = (root / relative_path).resolve()
        if not path.is_relative_to(root_resolved):
            continue
        stats = _tree_stats(path)
        total_files += stats["file_count"]
        total_bytes += stats["bytes"]
        latest_ts = max(latest_ts, stats["last_modified_ts"])
        rows.append(
            {
                "usage_id": usage_id,
                "label": label,
                "path": relative_path,
                "exists": path.exists(),
                "file_count": stats["file_count"],
                "dir_count": stats["dir_count"],
                "bytes": stats["bytes"],
                "last_modified_at": _timestamp_to_utc(stats["last_modified_ts"]),
            }
        )
    return {
        "mode": "local_usage_stats",
        "version": version,
        "build_channel": "local_git_worktree",
        "cloud_account_required": False,
        "billing_identity": False,
        "subscription_required": False,
        "credits_enabled": False,
        "private_api_identity": False,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "latest_activity_at": _timestamp_to_utc(latest_ts),
        "usage_rows": rows,
        "safety": {
            "content_read": False,
            "secret_scan": False,
            "external_network": False,
            "billing_enabled": False,
            "credits_enabled": False,
        },
    }


def _artifact_links(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    artifacts = context.get("artifacts") if isinstance(context.get("artifacts"), list) else []
    for artifact in artifacts[:12]:
        if not isinstance(artifact, dict):
            continue
        rows.append(
            {
                "kind": str(artifact.get("kind") or "artifact"),
                "label": str(artifact.get("label") or artifact.get("artifact_id") or ""),
                "path": str(artifact.get("path") or ""),
                "updated_at": str(artifact.get("updated_at") or ""),
                "bytes": _int(artifact.get("bytes")),
            }
        )
    sources = context.get("sources") if isinstance(context.get("sources"), list) else []
    for source in sources:
        if not isinstance(source, dict):
            continue
        path = str(source.get("cache_path") or "")
        if not path:
            continue
        rows.append(
            {
                "kind": "provider_cache",
                "label": str(source.get("label") or source.get("source_id") or ""),
                "path": path,
                "updated_at": str(source.get("updated_at") or ""),
                "bytes": 0,
            }
        )
        if len(rows) >= 16:
            break
    return rows


def _setup_state(
    auth_mode: str,
    state: str,
    *,
    eligible_secret: bool,
    stored_secret: bool,
) -> str:
    if auth_mode == "no-key":
        return "public_or_cache_runtime"
    if "optional-local-key" in auth_mode and "paid" in auth_mode:
        return "blocked_plan_and_secret_gate"
    if "optional-local-key" in auth_mode:
        if not eligible_secret:
            return "blocked_secret_storage_gate"
        if stored_secret:
            return "local_secret_stored_adapter_pending"
        return "ready_for_local_secret"
    if "paid" in auth_mode:
        return "blocked_plan_gate"
    if auth_mode == "forbidden":
        return "disabled_by_safety"
    return state or "inspect_provider"


def _setup_message(provider: dict[str, Any], health: dict[str, Any], secret_row: dict[str, Any]) -> str:
    auth_mode = str(provider.get("auth_mode") or "")
    if "optional-local-key" in auth_mode and "paid" in auth_mode:
        return "Capability visible; provider plan and local secret storage are both gated."
    if "optional-local-key" in auth_mode:
        if bool(secret_row.get("stored")):
            return "Local secret is sealed; provider adapter remains disabled until its adapter milestone."
        if bool(secret_row.get("eligible")):
            return "Local data-provider secret can be sealed with explicit opt-in."
        return "Capability visible; local secret storage is not enabled for this provider class."
    if "paid" in auth_mode:
        return "Capability visible; plan-gated provider is not activated locally."
    if auth_mode == "forbidden":
        return "Disabled by safety contract; paper and dry-run routes remain isolated."
    return str(health.get("message") or provider.get("fallback") or "Inspect provider state.")


def _cache_control_state(state: str) -> str:
    if state == "active":
        return "inspect_active_cache"
    if state == "stale_cache":
        return "inspect_stale_cache"
    if state in {"key_required", "plan_required", "disabled_by_safety"}:
        return "setup_gated"
    return "cache_not_populated"


def _cache_safe_actions(cache_id: str) -> list[str]:
    if cache_id in {"market_crypto_latest", "crypto_public_detail"}:
        return ["inspect", "refresh_from_markets_or_crypto_route"]
    if cache_id in {
        "news_public_rss",
        "fundamentals_sec",
        "fundamentals_sec_frames",
        "macro_dbnomics",
    }:
        return ["inspect", "refresh_from_news_route"]
    if cache_id in {
        "rates_treasury_yield_curve",
        "fx_ecb_reference_rates",
        "commodities_world_bank_monthly",
    }:
        return ["inspect", "refresh_from_markets_route"]
    return ["inspect"]


def _path_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _tree_stats(path: Path) -> dict[str, int | float]:
    stats: dict[str, int | float] = {
        "file_count": 0,
        "dir_count": 0,
        "bytes": 0,
        "last_modified_ts": 0.0,
    }
    if not path.exists():
        return stats
    candidates = [path] if path.is_file() else path.rglob("*")
    for candidate in candidates:
        try:
            if candidate.is_symlink():
                continue
            if candidate.is_dir():
                stats["dir_count"] = int(stats["dir_count"]) + 1
                continue
            if not candidate.is_file():
                continue
            file_stat = candidate.stat()
        except OSError:
            continue
        stats["file_count"] = int(stats["file_count"]) + 1
        stats["bytes"] = int(stats["bytes"]) + file_stat.st_size
        stats["last_modified_ts"] = max(float(stats["last_modified_ts"]), file_stat.st_mtime)
    return stats


def _int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(number, 0)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _timestamp_to_utc(timestamp: float) -> str:
    if timestamp <= 0:
        return ""
    return datetime.fromtimestamp(timestamp, UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
