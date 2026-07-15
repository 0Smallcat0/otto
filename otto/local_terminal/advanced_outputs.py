"""Metadata-only output packets for advanced local workflows."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from otto.local_terminal.advanced_context import sanitize_advanced_context


ARTIFACT_SUFFIXES = {".csv", ".ipynb", ".json", ".jsonl", ".log", ".md", ".txt"}
OUTPUT_PACKET_PREFIX = "advanced-output-packet-"
ADVANCED_ROUTE_STATE_FILES: dict[str, tuple[str, ...]] = {
    "ai_chat": ("chat_state.json",),
    "nodes": ("nodes_state.json",),
    "code": ("code_state.json",),
    "quant_lab": ("quant_lab_state.json",),
    "quantlib": ("quantlib_state.json",),
}
ADVANCED_OUTPUT_ROUTES: tuple[dict[str, str | tuple[str, ...]], ...] = (
    {
        "route_id": "ai_chat",
        "label": "AI Chat",
        "artifact_root": "artifacts/chat",
        "safe_action_id": "ai_chat_append_message",
        "safe_endpoint": "/api/ai-chat/messages",
        "safe_action": "append a dry-run context message with read-only linked artifacts",
        "expected_artifact_kinds": ("data",),
        "input_contract": (
            "session_id:string",
            "content:string<=4000",
            "linked_artifacts:string[] allowed local artifact/cache paths",
        ),
        "output_contract": ("messages.jsonl:data", "assistant_reply:local_context_brief"),
        "error_contract": ("400 credential_material", "400 unsafe_artifact_path"),
        "blocked_runtime_actions": ("managed_llm_call", "broker_mutation"),
    },
    {
        "route_id": "nodes",
        "label": "Nodes",
        "artifact_root": "artifacts/workflows",
        "safe_action_id": "nodes_dry_run",
        "safe_endpoint": "/api/nodes/dry-run",
        "safe_action": "write a non-mutating workflow dry-run bundle",
        "expected_artifact_kinds": ("data", "manifest", "report"),
        "input_contract": (
            "workflow_id:string",
            "workflow_definition:local_nodes_graph",
            "context:provider_cache_and_artifact_metadata",
        ),
        "output_contract": (
            "dry_run.json:data",
            "dry_run_manifest.json:manifest",
            "dry_run_report.md:report",
        ),
        "error_contract": ("400 invalid_workflow", "403 nodes_execute_disabled"),
        "blocked_runtime_actions": ("nodes_deploy", "nodes_execute"),
    },
    {
        "route_id": "code",
        "label": "Code",
        "artifact_root": "artifacts/code_workspace",
        "safe_action_id": "code_analyze",
        "safe_endpoint": "/api/code/analyze",
        "safe_action": "write a static notebook analysis bundle",
        "expected_artifact_kinds": ("data", "manifest", "report"),
        "input_contract": (
            "notebook_id:string",
            "cells:static_notebook_cells",
            "context:provider_cache_and_artifact_metadata",
        ),
        "output_contract": (
            "analysis.json:data+static_outline",
            "analysis_manifest.json:manifest+static_outline",
            "analysis_report.md:report",
        ),
        "error_contract": ("400 invalid_notebook", "403 code_run_disabled"),
        "blocked_runtime_actions": ("code_run", "code_run_all"),
    },
    {
        "route_id": "quant_lab",
        "label": "Quant Lab",
        "artifact_root": "artifacts/quant_lab",
        "safe_action_id": "quant_lab_run_preview",
        "safe_endpoint": "/api/quant-lab/run-preview",
        "safe_action": "write a local preview bundle for safe modules",
        "expected_artifact_kinds": ("data", "manifest", "report", "error_log"),
        "input_contract": (
            "module_slug:string",
            "inputs:bounded_object",
            "context:provider_cache_and_artifact_metadata",
        ),
        "output_contract": (
            "input.json:data",
            "output.json:data",
            "manifest.json:manifest",
            "report.md:report",
            "error.log:error_log",
        ),
        "error_contract": ("400 invalid_module_or_inputs", "403 quant_lab_execute_disabled"),
        "blocked_runtime_actions": ("quant_lab_execute", "quant_lab_deep_agent"),
    },
    {
        "route_id": "quantlib",
        "label": "QuantLib",
        "artifact_root": "artifacts/quantlib",
        "safe_action_id": "quantlib_compute",
        "safe_endpoint": "/api/quantlib/compute",
        "safe_action": "write deterministic local calculator artifacts",
        "expected_artifact_kinds": ("data", "manifest", "report", "error_log"),
        "input_contract": (
            "action_id:string",
            "request_body:bounded_numeric_object",
            "context:provider_cache_and_artifact_metadata",
        ),
        "output_contract": (
            "request.json:data",
            "response.json:data",
            "context.json:data",
            "manifest.json:manifest",
            "report.md:report",
            "error.log:error_log",
        ),
        "error_contract": ("400 invalid_request_body", "403 external_quantlib_runtime_disabled"),
        "blocked_runtime_actions": ("quantlib_external_execute",),
    },
)


def advanced_workflow_output_packet(
    root: Path,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a route-indexed packet over advanced workflow outputs.

    This intentionally reads filesystem metadata only. It does not open artifact
    contents, execute notebooks/workflows, or call providers.
    """

    root = root.resolve()
    safe_context = sanitize_advanced_context(context)
    routes = [_route_output_row(root, route) for route in ADVANCED_OUTPUT_ROUTES]
    recovery_queue = [_recovery_row(route) for route in routes if route["health_state"] != "complete"]
    artifact_count = sum(int(route["artifact_count"]) for route in routes)
    state_artifact_count = sum(int(route["state_artifact_count"]) for route in routes)
    artifact_kinds = _sum_artifact_kinds(routes)
    return {
        "generated_at": _utc_now(),
        "mode": "metadata_only_advanced_workflow_output_packet",
        "contract": "advanced_workflow_output_packet_v1",
        "summary": {
            "route_count": len(routes),
            "routes_with_outputs": sum(1 for route in routes if route["has_outputs"]),
            "routes_missing_outputs": sum(1 for route in routes if not route["has_outputs"]),
            "artifact_file_count": artifact_count,
            "state_artifact_file_count": state_artifact_count,
            "manifest_file_count": artifact_kinds["manifest"],
            "report_file_count": artifact_kinds["report"],
            "error_log_file_count": artifact_kinds["error_log"],
            "routes_health_complete": sum(1 for route in routes if route["health_state"] == "complete"),
            "routes_health_partial": sum(1 for route in routes if route["health_state"] == "partial"),
            "routes_health_missing": sum(
                1 for route in routes if route["health_state"] == "missing_output"
            ),
            "supervision_ready_count": sum(1 for route in routes if route["supervision_ready"]),
            "source_count": safe_context["summary"]["source_count"],
            "ready_source_count": safe_context["summary"]["ready_source_count"],
            "context_artifact_count": safe_context["summary"]["artifact_count"],
            "recovery_recommended_count": len(recovery_queue),
            "io_contract_route_count": sum(1 for route in routes if route["io_contract"]),
        },
        "routes": routes,
        "source_context": {
            "summary": safe_context["summary"],
            "sources": [
                {
                    "source_id": source["source_id"],
                    "state": source["state"],
                    "cache_path": source["cache_path"],
                    "record_count": source["record_count"],
                }
                for source in safe_context["sources"][:8]
            ],
        },
        "recovery_queue": recovery_queue,
        "write_action": {
            "method": "POST",
            "endpoint": "/api/advanced-workflows/output-packet",
            "enabled": True,
            "writes_local_artifacts": True,
            "artifact_root": "artifacts/diagnostics",
        },
        "safety": _safety_payload(),
    }


def write_advanced_workflow_output_packet(
    root: Path,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write the metadata-only advanced output packet as local diagnostics."""

    root = root.resolve()
    packet = advanced_workflow_output_packet(root, context)
    run_id = f"{OUTPUT_PACKET_PREFIX}{uuid4().hex[:12]}"
    artifact_dir = _safe_packet_dir(root, run_id)
    artifacts = {
        "packet": f"artifacts/diagnostics/{run_id}/advanced_output_packet.json",
        "manifest": f"artifacts/diagnostics/{run_id}/manifest.json",
        "report": f"artifacts/diagnostics/{run_id}/advanced_output_packet.md",
        "error_log": f"artifacts/diagnostics/{run_id}/error.log",
    }
    manifest = {
        "run_id": run_id,
        "created_at": _utc_now(),
        "artifact_contract": "advanced_workflow_output_packet_v1",
        "output_mode": packet["mode"],
        "artifact_dir": f"artifacts/diagnostics/{run_id}",
        "artifacts": artifacts,
        "summary": packet["summary"],
        "safety": packet["safety"],
    }
    snapshot = {
        **packet,
        "run_id": run_id,
        "status": "saved_locally",
        "artifact_dir": f"artifacts/diagnostics/{run_id}",
        "artifacts": artifacts,
        "manifest": manifest,
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifact_dir / "advanced_output_packet.json", snapshot)
    _write_json(artifact_dir / "manifest.json", manifest)
    (artifact_dir / "advanced_output_packet.md").write_text(
        _packet_markdown(snapshot),
        encoding="utf-8",
    )
    (artifact_dir / "error.log").write_text("", encoding="utf-8")
    return snapshot


def _route_output_row(
    root: Path,
    route: dict[str, str | tuple[str, ...]],
) -> dict[str, Any]:
    artifact_root = str(route["artifact_root"])
    route_id = str(route["route_id"])
    artifacts, state_artifacts = _artifact_rows(root, artifact_root, route_id=route_id)
    latest = artifacts[:5]
    latest_state = state_artifacts[:5]
    artifact_kinds = _artifact_kind_counts(artifacts)
    expected_kinds = tuple(str(kind) for kind in route["expected_artifact_kinds"])
    missing_kinds = _missing_expected_kinds(artifact_kinds, expected_kinds)
    health_state = _health_state(bool(artifacts), missing_kinds)
    latest_output_paths = {
        "latest_artifact": str(latest[0]["path"]) if latest else "",
        "manifest": _latest_path_by_kind(artifacts, "manifest"),
        "report": _latest_path_by_kind(artifacts, "report"),
        "error_log": _latest_path_by_kind(artifacts, "error_log"),
    }
    safe_output_action = {
        "action_id": str(route["safe_action_id"]),
        "endpoint": str(route["safe_endpoint"]),
        "description": str(route["safe_action"]),
    }
    return {
        "route_id": str(route["route_id"]),
        "label": str(route["label"]),
        "artifact_root": artifact_root,
        "artifact_count": len(artifacts),
        "state_artifact_count": len(state_artifacts),
        "has_outputs": bool(artifacts),
        "output_state": "available" if artifacts else "missing_output",
        "health_state": health_state,
        "supervision_ready": health_state == "complete",
        "expected_artifact_kinds": list(expected_kinds),
        "missing_expected_kinds": missing_kinds,
        "health_reason": _health_reason(bool(artifacts), missing_kinds),
        "artifact_kinds": artifact_kinds,
        "latest_artifact_path": latest_output_paths["latest_artifact"],
        "latest_manifest_path": latest_output_paths["manifest"],
        "latest_report_path": latest_output_paths["report"],
        "latest_error_log_path": latest_output_paths["error_log"],
        "latest_artifacts": latest,
        "latest_state_artifact_path": str(latest_state[0]["path"]) if latest_state else "",
        "state_artifacts": latest_state,
        "safe_output_action": safe_output_action,
        "blocked_runtime_actions": [str(action) for action in route["blocked_runtime_actions"]],
        "io_contract": _io_contract(route, latest_output_paths, safe_output_action),
    }


def _artifact_rows(
    root: Path,
    artifact_root: str,
    *,
    route_id: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = (root / artifact_root).resolve()
    root = root.resolve()
    if not base.is_relative_to(root) or not base.exists() or not base.is_dir():
        return [], []
    rows: list[dict[str, Any]] = []
    state_rows: list[dict[str, Any]] = []
    state_file_names = set(ADVANCED_ROUTE_STATE_FILES.get(route_id, ()))
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in ARTIFACT_SUFFIXES:
            continue
        try:
            resolved = path.resolve()
            relative = resolved.relative_to(root).as_posix()
            stat = resolved.stat()
        except (OSError, ValueError):
            continue
        row = {
            "path": relative,
            "label": path.name,
            "bytes": max(0, int(stat.st_size)),
            "updated_at": datetime.fromtimestamp(stat.st_mtime, UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
        }
        if resolved.parent == base and path.name in state_file_names:
            state_rows.append(row)
        else:
            rows.append(row)
    return (
        sorted(rows, key=lambda row: str(row["updated_at"]), reverse=True),
        sorted(state_rows, key=lambda row: str(row["updated_at"]), reverse=True),
    )


def _recovery_row(route: dict[str, Any]) -> dict[str, str]:
    missing_kinds = [str(kind) for kind in route.get("missing_expected_kinds") or []]
    reason = (
        "no local output artifacts indexed for this advanced route"
        if route["health_state"] == "missing_output"
        else f"missing expected artifact kinds: {', '.join(missing_kinds)}"
    )
    return {
        "route_id": str(route["route_id"]),
        "state": str(route["health_state"]),
        "recommended_action": str(route["safe_output_action"]["action_id"]),
        "endpoint": str(route["safe_output_action"]["endpoint"]),
        "reason": reason,
    }


def _io_contract(
    route: dict[str, str | tuple[str, ...]],
    latest_output_paths: dict[str, str],
    safe_output_action: dict[str, str],
) -> dict[str, Any]:
    route_id = str(route["route_id"])
    return {
        "contract_id": f"{route_id}_advanced_output_io_v1",
        "input_contract": _route_contract_list(route, "input_contract"),
        "output_contract": _route_contract_list(route, "output_contract"),
        "error_contract": _route_contract_list(route, "error_contract"),
        "artifact_root": str(route["artifact_root"]),
        "latest_output_paths": latest_output_paths,
        "safe_action": safe_output_action,
        "blocked_runtime_actions": [str(action) for action in route["blocked_runtime_actions"]],
        "read_mode": "metadata_only",
        "safety": {
            "metadata_only": True,
            "content_read": False,
            "execution_enabled": False,
            "external_network": False,
            "credentials_required": False,
            "broker_mutation": False,
            "live_trading": False,
        },
    }


def _route_contract_list(
    route: dict[str, str | tuple[str, ...]],
    key: str,
) -> list[str]:
    value = route.get(key)
    if isinstance(value, tuple):
        return [str(item) for item in value]
    return []


def _artifact_kind_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"manifest": 0, "report": 0, "error_log": 0, "data": 0}
    for row in rows:
        counts[_artifact_kind(str(row["path"]))] += 1
    return counts


def _sum_artifact_kinds(routes: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"manifest": 0, "report": 0, "error_log": 0, "data": 0}
    for route in routes:
        route_counts = route.get("artifact_kinds")
        if not isinstance(route_counts, dict):
            continue
        for key in counts:
            counts[key] += int(route_counts.get(key) or 0)
    return counts


def _missing_expected_kinds(counts: dict[str, int], expected_kinds: tuple[str, ...]) -> list[str]:
    return [kind for kind in expected_kinds if int(counts.get(kind) or 0) == 0]


def _health_state(has_outputs: bool, missing_kinds: list[str]) -> str:
    if not has_outputs:
        return "missing_output"
    if missing_kinds:
        return "partial"
    return "complete"


def _health_reason(has_outputs: bool, missing_kinds: list[str]) -> str:
    if not has_outputs:
        return "no local output artifacts indexed"
    if missing_kinds:
        return f"missing expected artifact kinds: {', '.join(missing_kinds)}"
    return "expected metadata artifacts are present"


def _latest_path_by_kind(rows: list[dict[str, Any]], kind: str) -> str:
    for row in rows:
        path = str(row["path"])
        if _artifact_kind(path) == kind:
            return path
    return ""


def _artifact_kind(path: str) -> str:
    name = Path(path).name.lower()
    suffix = Path(path).suffix.lower()
    if name == "error.log" or suffix == ".log":
        return "error_log"
    if name == "manifest.json" or name.endswith("_manifest.json"):
        return "manifest"
    if suffix == ".md":
        return "report"
    return "data"


def _packet_markdown(packet: dict[str, Any]) -> str:
    summary = packet["summary"]
    lines = [
        f"# Advanced Workflow Output Packet {packet['run_id']}",
        "",
        f"- Status: {packet['status']}",
        f"- Routes with outputs: {summary['routes_with_outputs']} / {summary['route_count']}",
        f"- Supervision ready: {summary['supervision_ready_count']} / {summary['route_count']}",
        f"- Artifact files: {summary['artifact_file_count']}",
        f"- Recovery recommended: {summary['recovery_recommended_count']}",
        "- Safety: metadata only, no content reads, no execution, no external network, no broker mutation",
        "",
        "## Routes",
    ]
    for route in packet["routes"]:
        latest = route["latest_artifacts"][0]["path"] if route["latest_artifacts"] else "none"
        action = route["safe_output_action"]["action_id"]
        lines.append(
            f"- {route['route_id']}: {route['health_state']}; "
            f"{route['artifact_count']} artifacts; latest={latest}; action={action}"
        )
    if packet["recovery_queue"]:
        lines.extend(["", "## Recovery Queue"])
        lines.extend(
            f"- {item['route_id']}: {item['recommended_action']} ({item['endpoint']})"
            for item in packet["recovery_queue"]
        )
    return "\n".join(lines) + "\n"


def _safe_packet_dir(root: Path, run_id: str) -> Path:
    if not run_id.startswith(OUTPUT_PACKET_PREFIX):
        raise ValueError("Invalid advanced output packet id")
    path = (root / "artifacts" / "diagnostics" / run_id).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Advanced output packet path must stay inside repository")
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _safety_payload() -> dict[str, bool]:
    return {
        "metadata_only": True,
        "content_read": False,
        "external_network": False,
        "execution_enabled": False,
        "script_execution": False,
        "managed_llm_call": False,
        "credentials_required": False,
        "secret_values_returned": False,
        "destructive_actions_enabled": False,
        "artifact_roots_mutated": False,
        "live_trading": False,
        "broker_mutation": False,
        "real_orders": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives": False,
        "installed_source_read": False,
    }


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
