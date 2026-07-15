"""Read-only artifact lifecycle inventory for AI-agent-operated workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class ArtifactRoot:
    root_id: str
    label: str
    path: str
    routes: tuple[str, ...]


ARTIFACT_ROOTS: tuple[ArtifactRoot, ...] = (
    ArtifactRoot("backtests", "Backtest runs", "artifacts/backtests", ("backtest", "portfolio")),
    ArtifactRoot("paper", "Paper ledger", "artifacts/paper", ("crypto", "portfolio")),
    ArtifactRoot("portfolio", "Portfolio state", "artifacts/portfolio", ("portfolio",)),
    ArtifactRoot("news", "News cache", "artifacts/news", ("news", "dashboard")),
    ArtifactRoot("chat", "AI Chat sessions", "artifacts/chat", ("ai_chat",)),
    ArtifactRoot("algo", "Algo strategies", "artifacts/algo", ("algo", "backtest")),
    ArtifactRoot("workflows", "Nodes workflows", "artifacts/workflows", ("nodes",)),
    ArtifactRoot("code_workspace", "Code workspace", "artifacts/code_workspace", ("code",)),
    ArtifactRoot("quant_lab", "Quant Lab bundles", "artifacts/quant_lab", ("quant_lab",)),
    ArtifactRoot("quantlib", "QuantLib runs", "artifacts/quantlib", ("quantlib",)),
    ArtifactRoot("forum", "Forum notes", "artifacts/forum", ("forum", "help")),
    ArtifactRoot("diagnostics", "Diagnostics", "artifacts/diagnostics", ("settings", "help")),
    ArtifactRoot("reports", "Reports", "artifacts/reports", ("dashboard", "portfolio")),
    ArtifactRoot("screenshots", "Screenshots", "artifacts/screenshots", ("all",)),
    ArtifactRoot("market_data", "Provider caches", "market_data", ("dashboard", "markets")),
)

ARCHIVE_PLAN_PREFIX = "artifact-lifecycle-plan-"
DEFAULT_ARCHIVE_STALE_AFTER_DAYS = 30
DEFAULT_LARGE_ROOT_BYTES = 50 * 1024 * 1024


def artifact_lifecycle_payload(root: Path) -> dict[str, Any]:
    """Return metadata-only lifecycle state without reading artifact contents."""

    root = root.resolve()
    rows = [_artifact_root_row(root, artifact_root) for artifact_root in ARTIFACT_ROOTS]
    provider_refresh = _diagnostic_family(root, prefix="provider-refresh-")
    governance_diagnostics = _diagnostic_family(root, prefix="gov-")
    help_diagnostics = _diagnostic_family(root, prefix="diag-")
    archive_plans = _diagnostic_family(root, prefix=ARCHIVE_PLAN_PREFIX)
    total_files = sum(_int(row["file_count"]) for row in rows)
    total_bytes = sum(_int(row["total_bytes"]) for row in rows)
    active_roots = sum(1 for row in rows if row["state"] == "active")
    empty_roots = sum(1 for row in rows if row["state"] == "empty")
    missing_roots = sum(1 for row in rows if row["state"] == "missing")
    blocked_roots = sum(1 for row in rows if str(row["state"]).startswith("blocked"))
    supervision_ready_roots = sum(1 for row in rows if bool(row.get("supervision_ready")))
    lineage_supported_roots = sum(
        1 for row in rows if bool(row.get("research_lineage_supported"))
    )
    return {
        "generated_at": _utc_now(),
        "mode": "read_only_metadata_inventory",
        "summary": {
            "root_count": len(rows),
            "active_root_count": active_roots,
            "empty_root_count": empty_roots,
            "missing_root_count": missing_roots,
            "blocked_root_count": blocked_roots,
            "supervision_ready_root_count": supervision_ready_roots,
            "lineage_supported_root_count": lineage_supported_roots,
            "file_count": total_files,
            "total_bytes": total_bytes,
            "provider_refresh_run_count": provider_refresh["run_count"],
            "governance_diagnostic_run_count": governance_diagnostics["run_count"],
            "help_diagnostic_run_count": help_diagnostics["run_count"],
            "archive_plan_run_count": archive_plans["run_count"],
        },
        "roots": rows,
        "diagnostics": {
            "provider_refresh": provider_refresh,
            "governance": governance_diagnostics,
            "help": help_diagnostics,
            "archive_plans": archive_plans,
        },
        "actions": {
            "inspect_metadata": True,
            "refresh_allowed_elsewhere": True,
            "archive_plan_enabled": True,
            "prune_enabled": False,
            "archive_enabled": False,
            "delete_enabled": False,
            "recover_enabled": False,
        },
        "safety": {
            "read_only": True,
            "content_read": False,
            "external_network": False,
            "credentials_required": False,
            "secret_scan": False,
            "destructive_actions_enabled": False,
            "live_trading": False,
            "broker_mutation": False,
            "installed_source_read": False,
        },
    }


def artifact_archive_plan_payload(
    root: Path,
    *,
    stale_after_days: int = DEFAULT_ARCHIVE_STALE_AFTER_DAYS,
    large_root_bytes: int = DEFAULT_LARGE_ROOT_BYTES,
) -> dict[str, Any]:
    """Build a metadata-only archive/prune plan without mutating artifact roots."""

    root = root.resolve()
    generated_at = _utc_now()
    generated_dt = _parse_utc(generated_at) or datetime.now(UTC).replace(microsecond=0)
    inventory = artifact_lifecycle_payload(root)
    stale_after_seconds = max(stale_after_days, 0) * 24 * 60 * 60
    candidates = [
        _archive_plan_candidate(
            row,
            generated_dt=generated_dt,
            stale_after_seconds=stale_after_seconds,
            large_root_bytes=max(0, int(large_root_bytes)),
        )
        for row in inventory["roots"]
    ]
    archive_candidates = [
        row for row in candidates if row["proposed_action"] == "archive_candidate"
    ]
    blocked = [row for row in candidates if row["proposed_action"] == "blocked"]
    monitor = [row for row in candidates if row["proposed_action"] == "monitor"]
    no_action = [row for row in candidates if row["proposed_action"] == "no_action"]
    return {
        "generated_at": generated_at,
        "mode": "metadata_only_archive_plan",
        "inventory_mode": inventory["mode"],
        "retention": {
            "stale_after_days": stale_after_days,
            "stale_after_seconds": stale_after_seconds,
            "large_root_bytes": large_root_bytes,
        },
        "summary": {
            "root_count": len(candidates),
            "archive_candidate_count": len(archive_candidates),
            "monitor_count": len(monitor),
            "no_action_count": len(no_action),
            "blocked_count": len(blocked),
            "file_count": inventory["summary"]["file_count"],
            "total_bytes": inventory["summary"]["total_bytes"],
        },
        "candidates": candidates,
        "actions": {
            "write_plan_artifact": True,
            "archive_enabled": False,
            "prune_enabled": False,
            "delete_enabled": False,
            "move_enabled": False,
            "recover_enabled": False,
        },
        "safety": {
            "content_read": False,
            "metadata_only": True,
            "external_network": False,
            "credentials_required": False,
            "secret_values_returned": False,
            "destructive_actions_enabled": False,
            "artifact_roots_mutated": False,
            "files_deleted": False,
            "files_moved": False,
            "live_trading": False,
            "broker_mutation": False,
            "installed_source_read": False,
        },
    }


def run_artifact_archive_plan(
    root: Path,
    *,
    stale_after_days: int = DEFAULT_ARCHIVE_STALE_AFTER_DAYS,
    large_root_bytes: int = DEFAULT_LARGE_ROOT_BYTES,
) -> dict[str, Any]:
    """Write a local archive plan bundle without moving, deleting, or reading artifacts."""

    root = root.resolve()
    plan = artifact_archive_plan_payload(
        root,
        stale_after_days=stale_after_days,
        large_root_bytes=large_root_bytes,
    )
    run_id = f"{ARCHIVE_PLAN_PREFIX}{uuid4().hex[:12]}"
    artifact_dir = _safe_plan_dir(root, run_id)
    artifacts = {
        "archive_plan": f"artifacts/diagnostics/{run_id}/archive_plan.json",
        "manifest": f"artifacts/diagnostics/{run_id}/manifest.json",
        "report": f"artifacts/diagnostics/{run_id}/archive_plan.md",
        "error_log": f"artifacts/diagnostics/{run_id}/error.log",
    }
    manifest = {
        "run_id": run_id,
        "created_at": _utc_now(),
        "output_mode": "metadata_only_artifact_archive_plan",
        "artifact_dir": f"artifacts/diagnostics/{run_id}",
        "artifacts": artifacts,
        "summary": plan["summary"],
        "retention": plan["retention"],
        "safety": plan["safety"],
    }
    snapshot = {
        **plan,
        "run_id": run_id,
        "status": "saved_locally",
        "artifact_dir": f"artifacts/diagnostics/{run_id}",
        "artifacts": artifacts,
        "manifest": manifest,
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifact_dir / "archive_plan.json", snapshot)
    _write_json(artifact_dir / "manifest.json", manifest)
    (artifact_dir / "archive_plan.md").write_text(
        _archive_plan_markdown(snapshot),
        encoding="utf-8",
    )
    (artifact_dir / "error.log").write_text("", encoding="utf-8")
    return snapshot


def _artifact_root_row(root: Path, artifact_root: ArtifactRoot) -> dict[str, Any]:
    path = (root / artifact_root.path).resolve()
    stays_inside = path.is_relative_to(root)
    lineage_contract = _lineage_contract(artifact_root)
    if not stays_inside:
        return {
            "root_id": artifact_root.root_id,
            "label": artifact_root.label,
            "path": artifact_root.path,
            "routes": list(artifact_root.routes),
            "exists": False,
            "stays_inside_repo": False,
            "state": "blocked_outside_repo",
            "file_count": 0,
            "directory_count": 0,
            "total_bytes": 0,
            "newest_updated_at": "",
            "latest_artifact_path": "",
            "lifecycle_state": "blocked",
            "safe_actions": [],
            "supervision_ready": False,
            "recovery_hint": "Manual review required before an agent can trust this root path.",
            "destructive_actions_enabled": False,
            **lineage_contract,
        }
    if not path.exists():
        return _empty_row(artifact_root, state="missing")

    file_count = 0
    directory_count = 0
    total_bytes = 0
    newest_mtime = 0.0
    newest_file_mtime = 0.0
    latest_artifact_path = ""
    for child in path.rglob("*"):
        try:
            if child.is_symlink():
                continue
            resolved_child = child.resolve()
            if not resolved_child.is_relative_to(root):
                continue
            stat = child.stat()
        except OSError:
            continue
        newest_mtime = max(newest_mtime, stat.st_mtime)
        if child.is_file():
            file_count += 1
            total_bytes += stat.st_size
            if stat.st_mtime >= newest_file_mtime:
                newest_file_mtime = stat.st_mtime
                latest_artifact_path = resolved_child.relative_to(root).as_posix()
        elif child.is_dir():
            directory_count += 1

    state = "active" if file_count > 0 else "empty"
    supervision_ready = state == "active" and latest_artifact_path != ""
    return {
        "root_id": artifact_root.root_id,
        "label": artifact_root.label,
        "path": artifact_root.path,
        "routes": list(artifact_root.routes),
        "exists": True,
        "stays_inside_repo": True,
        "state": state,
        "file_count": file_count,
        "directory_count": directory_count,
        "total_bytes": total_bytes,
        "newest_updated_at": _mtime_to_utc(newest_mtime),
        "latest_artifact_path": latest_artifact_path,
        "lifecycle_state": "inspectable" if state == "active" else "waiting_for_first_artifact",
        "safe_actions": ["inspect_metadata", "open_artifact_paths"],
        "supervision_ready": supervision_ready,
        "recovery_hint": (
            "Metadata is ready for agent supervision."
            if supervision_ready
            else "Root exists but no artifact file is available yet."
        ),
        "destructive_actions_enabled": False,
        **lineage_contract,
    }


def _archive_plan_candidate(
    row: dict[str, Any],
    *,
    generated_dt: datetime,
    stale_after_seconds: int,
    large_root_bytes: int,
) -> dict[str, Any]:
    state = str(row.get("state") or "")
    newest_updated_at = str(row.get("newest_updated_at") or "")
    newest = _parse_utc(newest_updated_at)
    age_seconds = (
        max(0, int((generated_dt - newest).total_seconds())) if newest is not None else None
    )
    reasons: list[str] = []
    proposed_action = "no_action"
    if row.get("stays_inside_repo") is not True:
        proposed_action = "blocked"
        reasons.append("root path is outside repository boundary")
    elif state in {"missing", "empty"}:
        reasons.append("root has no artifact files")
    elif state == "active":
        if age_seconds is not None and age_seconds >= stale_after_seconds:
            reasons.append("newest artifact is older than retention threshold")
        if _int(row.get("total_bytes")) >= large_root_bytes and large_root_bytes > 0:
            reasons.append("root size meets large-root threshold")
        proposed_action = "archive_candidate" if reasons else "monitor"
        if not reasons:
            reasons.append("active root remains inside active retention window")
    else:
        proposed_action = "monitor"
        reasons.append(f"root state {state} requires operator review")

    return {
        "root_id": str(row.get("root_id") or ""),
        "label": str(row.get("label") or ""),
        "path": str(row.get("path") or ""),
        "routes": list(row.get("routes") or []),
        "state": state,
        "file_count": _int(row.get("file_count")),
        "directory_count": _int(row.get("directory_count")),
        "total_bytes": _int(row.get("total_bytes")),
        "newest_updated_at": newest_updated_at,
        "age_seconds": age_seconds,
        "proposed_action": proposed_action,
        "reasons": reasons,
        "requires_manual_review": proposed_action in {"archive_candidate", "blocked"},
        "will_mutate_files": False,
    }


def _empty_row(artifact_root: ArtifactRoot, *, state: str) -> dict[str, Any]:
    return {
        "root_id": artifact_root.root_id,
        "label": artifact_root.label,
        "path": artifact_root.path,
        "routes": list(artifact_root.routes),
        "exists": False,
        "stays_inside_repo": True,
        "state": state,
        "file_count": 0,
        "directory_count": 0,
        "total_bytes": 0,
        "newest_updated_at": "",
        "latest_artifact_path": "",
        "lifecycle_state": "not_created",
        "safe_actions": [],
        "supervision_ready": False,
        "recovery_hint": "Generate a safe local workflow output before expecting artifact files.",
        "destructive_actions_enabled": False,
        **_lineage_contract(artifact_root),
    }


def _lineage_contract(artifact_root: ArtifactRoot) -> dict[str, Any]:
    supported = artifact_root.root_id in {"algo", "backtests"}
    return {
        "research_lineage_supported": supported,
        "lineage_manifest_contract": (
            "research_lineage_v1_metadata_only"
            if supported
            else "not_applicable_for_root"
        ),
        "lineage_content_read": False,
    }


def _diagnostic_family(root: Path, *, prefix: str) -> dict[str, Any]:
    diagnostics_root = (root / "artifacts" / "diagnostics").resolve()
    if not diagnostics_root.exists() or not diagnostics_root.is_relative_to(root):
        return {"run_count": 0, "latest_run_id": "", "latest_updated_at": "", "latest_path": ""}

    run_count = 0
    latest_mtime = 0.0
    latest_path = ""
    latest_run_id = ""
    for child in diagnostics_root.iterdir():
        try:
            if not child.is_dir() or not child.name.startswith(prefix):
                continue
            stat = child.stat()
        except OSError:
            continue
        run_count += 1
        if stat.st_mtime >= latest_mtime:
            latest_mtime = stat.st_mtime
            latest_path = f"artifacts/diagnostics/{child.name}"
            latest_run_id = child.name
    return {
        "run_count": run_count,
        "latest_run_id": latest_run_id,
        "latest_updated_at": _mtime_to_utc(latest_mtime),
        "latest_path": latest_path,
    }


def _safe_plan_dir(root: Path, run_id: str) -> Path:
    if not run_id.startswith(ARCHIVE_PLAN_PREFIX) or len(run_id) != len(ARCHIVE_PLAN_PREFIX) + 12:
        raise ValueError("Archive plan run id is invalid")
    diagnostics_root = (root / "artifacts" / "diagnostics").resolve()
    artifact_dir = (diagnostics_root / run_id).resolve()
    if not artifact_dir.is_relative_to(diagnostics_root):
        raise ValueError("Archive plan directory must stay under artifacts/diagnostics")
    return artifact_dir


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _archive_plan_markdown(snapshot: dict[str, Any]) -> str:
    summary = snapshot.get("summary", {})
    safety = snapshot.get("safety", {})
    candidates = snapshot.get("candidates", [])
    candidate_lines = "\n".join(
        "- {root_id}: {action} ({files} files, {bytes} bytes)".format(
            root_id=str(row.get("root_id") or ""),
            action=str(row.get("proposed_action") or ""),
            files=_int(row.get("file_count")),
            bytes=_int(row.get("total_bytes")),
        )
        for row in candidates
        if isinstance(row, dict)
    )
    summary_lines = "\n".join(f"- {key}: {value}" for key, value in summary.items())
    safety_lines = "\n".join(f"- {key}: {value}" for key, value in safety.items())
    return (
        "# Artifact Archive Plan\n\n"
        f"Run: {snapshot.get('run_id', '')}\n\n"
        "## Summary\n\n"
        f"{summary_lines}\n\n"
        "## Candidates\n\n"
        f"{candidate_lines}\n\n"
        "## Safety\n\n"
        f"{safety_lines}\n"
    )


def _mtime_to_utc(value: float) -> str:
    if value <= 0:
        return ""
    return datetime.fromtimestamp(value, UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
