"""Local notebook editing contracts for the Code workspace."""

from __future__ import annotations

import ast
import copy
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.local_terminal.advanced_context import context_for_artifact, sanitize_advanced_context


MAX_NOTEBOOKS = 60
MAX_CELLS = 120
MAX_SOURCE_LENGTH = 12000
MAX_OUTPUTS = 20
MAX_OUTPUT_LENGTH = 2000
CELL_TYPES = {"code", "markdown"}
ALLOWED_CELL_STATES = {"not_run", "idle", "saved", "imported"}
FORBIDDEN_RUNTIME_PATTERNS = (
    re.compile(r"\bcreate_order\s*\(", re.IGNORECASE),
    re.compile(r"\bplace_order\s*\(", re.IGNORECASE),
    re.compile(r"\bfetch_balance\s*\(", re.IGNORECASE),
    re.compile(r"\bset_leverage\s*\(", re.IGNORECASE),
    re.compile(r"\bset_margin_mode\s*\(", re.IGNORECASE),
    re.compile(r"\blive[_\s-]*(order|trading|execution)\b", re.IGNORECASE),
    re.compile(r"\breal[_\s-]*(order|balance)\b", re.IGNORECASE),
    re.compile(r"\b(ccxt|binance)\.[A-Za-z_]+", re.IGNORECASE),
)
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
    re.compile(r"\bprivate[\s_-]+key\b", re.IGNORECASE),
)


class CodeWorkspaceError(ValueError):
    """Raised when a notebook request violates local edit-only rules."""


def default_code_state() -> dict[str, Any]:
    return {
        "active_notebook_id": None,
        "notebooks": {},
        "selected_cell_id": None,
        "sidebar_open": True,
        "last_export": None,
        "last_analysis": None,
        "updated_at": "not started",
    }


def default_notebook_request() -> dict[str, Any]:
    return {
        "name": "Local Python Notebook",
        "path": "",
        "kernel": "Python 3.12 local",
        "kernel_status": "idle",
        "execution_state": "idle",
        "cells": [
            {
                "cell_id": "cell-local-draft",
                "cell_type": "code",
                "source": "# Local Python Notebook\n# Store notes and analysis locally.",
                "outputs": [],
                "execution_count": None,
                "execution_state": "not_run",
            }
        ],
    }


def code_safety_payload() -> dict[str, bool | str]:
    return {
        "local_files_only": True,
        "execution_enabled": False,
        "run_enabled": False,
        "run_all_enabled": False,
        "kernel_process_enabled": False,
        "cloud_execution": False,
        "external_network": False,
        "private_api_required": False,
        "credentials_persisted": False,
        "broker_mutation": False,
        "real_orders": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives": False,
        "output": "edit_only",
        "runtime_state": "disabled_no_sandbox_contract",
    }


def normalize_code_state(state: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    default = default_code_state()
    invalid_notebooks = (
        {str(key): str(value) for key, value in state.get("invalid_notebooks", {}).items()}
        if isinstance(state.get("invalid_notebooks"), dict)
        else {}
    )
    if strict and invalid_notebooks:
        first_key, first_value = next(iter(invalid_notebooks.items()))
        raise CodeWorkspaceError(f"Code state is invalid: {first_key}: {first_value}")

    raw_notebooks = state.get("notebooks")
    notebooks: dict[str, dict[str, Any]] = {}
    if isinstance(raw_notebooks, dict):
        if len(raw_notebooks) > MAX_NOTEBOOKS:
            raise CodeWorkspaceError(f"Notebooks exceed limit of {MAX_NOTEBOOKS}")
        for notebook_id, raw_notebook in raw_notebooks.items():
            if not isinstance(raw_notebook, dict):
                if strict:
                    raise CodeWorkspaceError(f"Stored notebook {notebook_id} must be an object")
                invalid_notebooks[str(notebook_id)] = "Stored notebook must be an object"
                continue
            try:
                notebook = normalize_notebook(raw_notebook, fallback_id=str(notebook_id))
            except CodeWorkspaceError as exc:
                if strict:
                    raise CodeWorkspaceError(
                        f"Stored notebook {notebook_id} is invalid: {exc}"
                    ) from exc
                invalid_notebooks[str(notebook_id)] = str(exc)
                continue
            notebooks[notebook["notebook_id"]] = notebook
    elif raw_notebooks not in (None, {}):
        if strict:
            raise CodeWorkspaceError("Stored notebooks must be an object")
        invalid_notebooks["notebooks"] = "Stored notebooks must be an object"

    active_id = str(state.get("active_notebook_id") or "")
    if active_id not in notebooks:
        active_id = _latest_notebook_id(notebooks)

    selected_cell_id = str(state.get("selected_cell_id") or "")
    if active_id and selected_cell_id not in {
        cell["cell_id"] for cell in notebooks[active_id]["cells"]
    }:
        selected_cell_id = notebooks[active_id]["cells"][0]["cell_id"]

    try:
        last_export = _normalize_last_export(state.get("last_export"))
    except CodeWorkspaceError as exc:
        if strict:
            raise CodeWorkspaceError(f"Stored export is invalid: {exc}") from exc
        invalid_notebooks["last_export"] = str(exc)
        last_export = None
    try:
        last_analysis = _normalize_last_analysis(state.get("last_analysis"), active_id)
    except CodeWorkspaceError as exc:
        if strict:
            raise CodeWorkspaceError(f"Stored analysis is invalid: {exc}") from exc
        invalid_notebooks["last_analysis"] = str(exc)
        last_analysis = None

    return {
        **default,
        "active_notebook_id": active_id or None,
        "notebooks": notebooks,
        "selected_cell_id": selected_cell_id or None,
        "sidebar_open": state.get("sidebar_open") is not False,
        "last_export": last_export,
        "last_analysis": last_analysis,
        "invalid_notebooks": invalid_notebooks,
        "updated_at": str(state.get("updated_at") or default["updated_at"]),
    }


def code_analysis_health_payload(state: dict[str, Any], root: Path) -> dict[str, Any]:
    """Return metadata-only health for local Code static-analysis artifacts."""

    code_state = normalize_code_state(state, strict=False)
    rows = [
        _analysis_health_row(root, code_state, notebook)
        for notebook in sorted(
            code_state["notebooks"].values(),
            key=lambda notebook: str(notebook.get("updated_at", "")),
            reverse=True,
        )
    ]
    recovery_queue = _analysis_health_recovery_queue(rows)
    latest = rows[0] if rows else {}
    return {
        "mode": "metadata_only_code_analysis_health",
        "contract": "code_analysis_health_v1",
        "generated_at": _utc_now(),
        "root": "artifacts/code_workspace",
        "summary": {
            "notebook_count": len(rows),
            "complete_count": sum(1 for row in rows if row["health_state"] == "complete"),
            "empty_notebook_count": sum(
                1 for row in rows if row["health_state"] == "empty_notebook"
            ),
            "partial_count": sum(1 for row in rows if row["health_state"].startswith("partial")),
            "missing_artifact_count": sum(int(row["missing_count"]) for row in rows),
            "supervision_ready_count": sum(1 for row in rows if row["supervision_ready"]),
            "invalid_notebook_count": len(code_state["invalid_notebooks"]),
            "active_notebook_id": str(code_state.get("active_notebook_id") or ""),
            "latest_notebook_id": str(latest.get("notebook_id") or ""),
            "latest_analysis_id": str(latest.get("last_analysis_id") or ""),
            "recovery_queue_count": len(recovery_queue),
            "destructive_action_count": 0,
        },
        "notebooks": rows,
        "recovery_queue": recovery_queue,
        "recommended_actions": [
            {
                "action_id": "code_analyze",
                "endpoint": "/api/code/analyze",
                "method": "POST",
                "ready": any(row["notebook_artifact_exists"] for row in rows),
                "reason": (
                    "Run local static analysis to create missing Code output artifacts."
                    if rows
                    else "Create or import a local notebook before static analysis."
                ),
            }
        ],
        "safety": {
            "local_only": True,
            "read_only": True,
            "metadata_only": True,
            "notebook_execution": False,
            "kernel_process_enabled": False,
            "source_returned": False,
            "artifact_content_read": False,
            "artifact_content_indexing": False,
            "writes_local_artifacts": False,
            "automatic_repair_enabled": False,
            "destructive_actions_enabled": False,
            "provider_calls": False,
            "external_network": False,
            "secret_values_returned": False,
            "credentials_persisted": False,
            "broker_mutation": False,
            "ledger_mutation": False,
            "real_orders": False,
            "real_balance": False,
            "live_trading": False,
        },
    }


def code_payload(
    state: dict[str, Any],
    context: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    code_state = normalize_code_state(state, strict=False)
    active_id = code_state["active_notebook_id"]
    active_notebook = copy.deepcopy(code_state["notebooks"].get(active_id)) if active_id else None
    selected_cell = None
    if active_notebook and code_state["selected_cell_id"]:
        selected_cell = next(
            (
                copy.deepcopy(cell)
                for cell in active_notebook["cells"]
                if cell["cell_id"] == code_state["selected_cell_id"]
            ),
            None,
        )
    return {
        "active_notebook_id": active_id,
        "first_use": active_notebook is None,
        "title": "PYTHON NOTEBOOK",
        "toolbar": [
            "NEW",
            "OPEN",
            "SAVE",
            "+ CELL",
            "CONTEXT NB",
            "ANALYZE",
            "CLEAR OUT",
            "RUN ALL",
            "SIDEBAR",
        ],
        "cell_controls": ["RUN", "TYPE", "UP", "DN", "DEL"],
        "notebooks": _notebook_list(code_state),
        "active_notebook": active_notebook,
        "notebook_draft": active_notebook or default_notebook_request(),
        "selected_cell": selected_cell,
        "sidebar_open": code_state["sidebar_open"],
        "last_export": code_state["last_export"],
        "last_analysis": code_state["last_analysis"],
        "invalid_notebooks": code_state["invalid_notebooks"],
        "engine": {
            "engine_id": "local_code_v1",
            "state": "editing",
            "kernel_status": active_notebook["kernel_status"] if active_notebook else "idle",
            "kernel": active_notebook["kernel"] if active_notebook else "Python 3.12 local",
            "notebook_count": len(code_state["notebooks"]),
            "cell_count": len(active_notebook["cells"]) if active_notebook else 1,
        },
        "safety": code_safety_payload(),
        "file_format": {
            "primary": "ipynb",
            "open_dialog": "local_json_import",
            "save_dialog": "repo_local_artifact",
        },
        "context": sanitize_advanced_context(context),
        "analysis_health": code_analysis_health_payload(code_state, root or Path.cwd()),
    }


def create_notebook(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    code_state = normalize_code_state(copy.deepcopy(state))
    if len(code_state["notebooks"]) >= MAX_NOTEBOOKS:
        raise CodeWorkspaceError(f"Notebooks exceed limit of {MAX_NOTEBOOKS}")
    now = _utc_now()
    notebook_id = f"notebook-{uuid4().hex[:12]}"
    notebook = normalize_notebook(
        {
            **default_notebook_request(),
            **request,
            "notebook_id": notebook_id,
            "created_at": now,
            "updated_at": now,
        }
    )
    code_state["notebooks"][notebook["notebook_id"]] = notebook
    code_state["active_notebook_id"] = notebook["notebook_id"]
    code_state["selected_cell_id"] = notebook["cells"][0]["cell_id"]
    code_state["updated_at"] = now
    return code_state


def create_context_notebook(
    state: dict[str, Any], context: dict[str, Any] | None
) -> dict[str, Any]:
    safe_context = sanitize_advanced_context(context)
    summary = safe_context["summary"]
    sources = safe_context["sources"]
    artifacts = safe_context["artifacts"][:8]
    source_lines = (
        "\n".join(
            f"- {source['label']}: {source['state']} ({source['cache_path'] or source['source_id']})"
            for source in sources
        )
        or "- No provider cache has been indexed yet."
    )
    artifact_lines = (
        "\n".join(f"- {artifact['kind']}: {artifact['path']}" for artifact in artifacts)
        or "- No local artifacts indexed yet."
    )
    source_paths = [source["cache_path"] for source in sources if source["cache_path"]]
    notebook = {
        "name": "Provider Context Notebook",
        "kernel": "Python 3.12 local",
        "kernel_status": "idle",
        "execution_state": "idle",
        "cells": [
            {
                "cell_id": "cell-context-summary",
                "cell_type": "markdown",
                "source": (
                    "# Local provider context\n\n"
                    f"Ready sources: {summary['ready_source_count']} / {summary['source_count']}\n\n"
                    f"{source_lines}\n\n"
                    "This notebook is saved locally and execution remains disabled."
                ),
                "outputs": [],
                "execution_count": None,
                "execution_state": "not_run",
            },
            {
                "cell_id": "cell-context-paths",
                "cell_type": "code",
                "source": (
                    "# Read-only local dataset paths. Execution is disabled in this workspace.\n"
                    f"provider_cache_paths = {json.dumps(source_paths, sort_keys=True)}\n"
                    f"context_summary = {json.dumps(context_for_artifact(safe_context), sort_keys=True)}"
                ),
                "outputs": [
                    {
                        "output_type": "display_data",
                        "text": (
                            f"{summary['ready_source_count']} ready provider/cache sources; "
                            f"{summary['artifact_count']} indexed artifacts."
                        ),
                    }
                ],
                "execution_count": None,
                "execution_state": "saved",
            },
            {
                "cell_id": "cell-context-artifacts",
                "cell_type": "markdown",
                "source": f"# Local artifacts\n\n{artifact_lines}",
                "outputs": [],
                "execution_count": None,
                "execution_state": "not_run",
            },
        ],
    }
    return create_notebook(state, notebook)


def save_notebook(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    code_state = normalize_code_state(copy.deepcopy(state))
    notebook_request = (
        request.get("notebook") if isinstance(request.get("notebook"), dict) else request
    )
    requested_id = str(notebook_request.get("notebook_id") or "")
    if requested_id:
        requested_id = _safe_id(requested_id, "Notebook id")
    if (
        len(code_state["notebooks"]) >= MAX_NOTEBOOKS
        and requested_id not in code_state["notebooks"]
    ):
        raise CodeWorkspaceError(f"Notebooks exceed limit of {MAX_NOTEBOOKS}")

    now = _utc_now()
    previous = code_state["notebooks"].get(requested_id, {}) if requested_id else {}
    notebook = normalize_notebook(
        {
            **notebook_request,
            "notebook_id": requested_id or f"notebook-{uuid4().hex[:12]}",
            "created_at": notebook_request.get("created_at") or previous.get("created_at") or now,
            "updated_at": now,
        }
    )
    code_state["notebooks"][notebook["notebook_id"]] = notebook
    code_state["active_notebook_id"] = notebook["notebook_id"]
    code_state["selected_cell_id"] = notebook["cells"][0]["cell_id"]
    code_state["updated_at"] = now
    return code_state


def add_cell(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    code_state = normalize_code_state(copy.deepcopy(state))
    notebook = _active_notebook(code_state)
    if len(notebook["cells"]) >= MAX_CELLS:
        raise CodeWorkspaceError(f"Notebook cells exceed limit of {MAX_CELLS}")
    cell = normalize_cell(
        {
            "cell_id": f"cell-{uuid4().hex[:12]}",
            "cell_type": request.get("cell_type") or "code",
            "source": request.get("source") or "",
            "outputs": [],
            "execution_count": None,
            "execution_state": "not_run",
        }
    )
    notebook["cells"].append(cell)
    notebook["updated_at"] = _utc_now()
    code_state["selected_cell_id"] = cell["cell_id"]
    code_state["updated_at"] = notebook["updated_at"]
    return code_state


def select_cell(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    code_state = normalize_code_state(copy.deepcopy(state))
    notebook = _active_notebook(code_state)
    cell_id = _safe_id(request.get("cell_id"), "Cell id")
    if cell_id not in {cell["cell_id"] for cell in notebook["cells"]}:
        raise CodeWorkspaceError("Cell not found")
    code_state["selected_cell_id"] = cell_id
    code_state["updated_at"] = _utc_now()
    return code_state


def select_notebook(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    code_state = normalize_code_state(copy.deepcopy(state))
    notebook_id = _safe_id(request.get("notebook_id"), "Notebook id")
    if notebook_id not in code_state["notebooks"]:
        raise CodeWorkspaceError("Notebook not found")
    notebook = code_state["notebooks"][notebook_id]
    code_state["active_notebook_id"] = notebook_id
    code_state["selected_cell_id"] = notebook["cells"][0]["cell_id"]
    code_state["updated_at"] = _utc_now()
    return code_state


def clear_outputs(state: dict[str, Any], request: dict[str, Any] | None = None) -> dict[str, Any]:
    code_state = normalize_code_state(copy.deepcopy(state))
    notebook = _notebook_from_existing_id(code_state, request or {})
    for cell in notebook["cells"]:
        cell["outputs"] = []
        cell["execution_count"] = None
        cell["execution_state"] = "not_run"
    notebook["updated_at"] = _utc_now()
    code_state["notebooks"][notebook["notebook_id"]] = notebook
    code_state["active_notebook_id"] = notebook["notebook_id"]
    code_state["updated_at"] = notebook["updated_at"]
    return code_state


def import_notebook(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    raw_notebook = request.get("notebook", request.get("ipynb"))
    if isinstance(raw_notebook, str):
        try:
            raw_notebook = json.loads(raw_notebook)
        except json.JSONDecodeError:
            raise CodeWorkspaceError("Notebook import JSON is invalid") from None
    if not isinstance(raw_notebook, dict):
        raise CodeWorkspaceError("Notebook import must be an object")
    if "nbformat" in raw_notebook:
        raw_notebook = notebook_from_ipynb(raw_notebook)
    return save_notebook(state, {"notebook": raw_notebook})


def export_notebook(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    code_state = normalize_code_state(state)
    notebook = _notebook_from_request_or_state(code_state, request)
    ipynb = notebook_to_ipynb(notebook)
    return {
        "notebook": copy.deepcopy(notebook),
        "ipynb": ipynb,
        "format": "ipynb",
        "safety": code_safety_payload(),
    }


def analyze_notebook(
    state: dict[str, Any],
    request: dict[str, Any],
    context: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    code_state = normalize_code_state(copy.deepcopy(state))
    notebook = _notebook_from_request_or_state(code_state, request)
    safe_context = sanitize_advanced_context(context)
    analysis = _notebook_static_analysis(notebook, safe_context)
    if (
        len(code_state["notebooks"]) >= MAX_NOTEBOOKS
        and notebook["notebook_id"] not in code_state["notebooks"]
    ):
        raise CodeWorkspaceError(f"Notebooks exceed limit of {MAX_NOTEBOOKS}")
    code_state["notebooks"][notebook["notebook_id"]] = notebook
    code_state["last_analysis"] = analysis
    code_state["active_notebook_id"] = notebook["notebook_id"]
    code_state["selected_cell_id"] = notebook["cells"][0]["cell_id"]
    code_state["updated_at"] = analysis["created_at"]
    return code_state, analysis


def code_analysis_manifest(notebook: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    return {
        "notebook_id": str(notebook.get("notebook_id") or analysis.get("notebook_id") or ""),
        "notebook_name": str(notebook.get("name") or analysis.get("notebook_name") or ""),
        "analysis_id": str(analysis.get("analysis_id") or ""),
        "status": str(analysis.get("status") or ""),
        "created_at": str(analysis.get("created_at") or ""),
        "artifact_files": analysis.get("artifact_files")
        if isinstance(analysis.get("artifact_files"), dict)
        else {},
        "summary": analysis.get("summary") if isinstance(analysis.get("summary"), dict) else {},
        "static_outline": analysis.get("static_outline")
        if isinstance(analysis.get("static_outline"), dict)
        else {},
        "safety": {
            "local_artifact_only": True,
            "static_analysis_only": True,
            "execution_enabled": False,
            "kernel_process_enabled": False,
            "external_network": False,
            "broker_mutation": False,
            "credentials_persisted": False,
            "real_orders": False,
            "private_api_required": False,
            "real_balance": False,
            "margin": False,
            "leverage": False,
            "short": False,
            "derivatives": False,
        },
    }


def code_analysis_report_text(notebook: dict[str, Any], analysis: dict[str, Any]) -> str:
    summary = analysis.get("summary") if isinstance(analysis.get("summary"), dict) else {}
    context_sources = (
        analysis.get("context_sources") if isinstance(analysis.get("context_sources"), list) else []
    )
    artifact_refs = (
        analysis.get("referenced_artifacts")
        if isinstance(analysis.get("referenced_artifacts"), list)
        else []
    )
    lines = [
        f"# Code Notebook Static Report {analysis.get('analysis_id', '')}",
        "",
        f"- Notebook: {notebook.get('name', '')}",
        f"- Notebook ID: {analysis.get('notebook_id', '')}",
        f"- Status: {analysis.get('status', '')}",
        f"- Output mode: {analysis.get('output_mode', 'local_static_notebook_report')}",
        f"- Cells: {summary.get('cell_count', 0)}",
        f"- Code cells: {summary.get('code_cell_count', 0)}",
        f"- Markdown cells: {summary.get('markdown_cell_count', 0)}",
        f"- Source lines: {summary.get('source_line_count', 0)}",
        f"- Imports: {summary.get('import_count', 0)}",
        f"- Definitions: {summary.get('definition_count', 0)}",
        f"- Calls: {summary.get('call_count', 0)}",
        f"- Syntax errors: {summary.get('syntax_error_count', 0)}",
        f"- Provider/cache sources indexed: {summary.get('context_source_count', 0)}",
        f"- Local artifact references: {summary.get('local_artifact_reference_count', 0)}",
        "- Safety: static analysis only, no kernel, no execution, no external network, no broker mutation",
        "",
        "## Static Outline",
    ]
    outline = analysis.get("static_outline") if isinstance(analysis.get("static_outline"), dict) else {}
    lines.extend(
        f"- import: {item}"
        for item in outline.get("imports", [])
        if isinstance(item, str)
    )
    lines.extend(
        f"- {item.get('kind', 'definition')}: {item.get('name', '')}"
        for item in outline.get("definitions", [])
        if isinstance(item, dict)
    )
    lines.extend(
        f"- call: {item}"
        for item in outline.get("calls", [])
        if isinstance(item, str)
    )
    if not outline.get("imports") and not outline.get("definitions") and not outline.get("calls"):
        lines.append("- No import, definition, or call outline detected.")
    if outline.get("syntax_errors"):
        lines.extend(
            f"- syntax error: {item}"
            for item in outline.get("syntax_errors", [])
            if isinstance(item, str)
        )
    lines.extend(
        [
            "",
            "## Context Sources",
        ]
    )
    lines.extend(
        f"- {source.get('source_id', '')}: {source.get('state', '')} / {source.get('cache_path', '')}"
        for source in context_sources
        if isinstance(source, dict)
    )
    lines.extend(["", "## Referenced Local Artifacts"])
    lines.extend(f"- {artifact}" for artifact in artifact_refs)
    if not artifact_refs:
        lines.append("- No explicit local artifact paths found in notebook source.")
    return "\n".join(lines) + "\n"


def disabled_code_runtime_response(action: str) -> dict[str, Any]:
    return {
        "action": action,
        "state": "disabled",
        "reason": "Code execution is disabled until a dedicated local sandbox policy exists.",
        "safety": code_safety_payload(),
    }


def normalize_notebook(raw: dict[str, Any], fallback_id: str | None = None) -> dict[str, Any]:
    notebook_id = _safe_id(raw.get("notebook_id") or fallback_id, "Notebook id")
    raw_cells = raw.get("cells") if isinstance(raw.get("cells"), list) else None
    cells = _notebook_cells(raw_cells or default_notebook_request()["cells"])
    kernel_status = _kernel_status(raw.get("kernel_status") or raw.get("execution_state") or "idle")
    return {
        "notebook_id": notebook_id,
        "name": _safe_text(raw.get("name") or "Local Python Notebook", "Notebook name", 80),
        "path": _safe_notebook_path(raw.get("path"), notebook_id),
        "cells": cells,
        "kernel": _safe_text(raw.get("kernel") or "Python 3.12 local", "Kernel", 80),
        "kernel_status": kernel_status,
        "execution_state": kernel_status,
        "created_at": str(raw.get("created_at") or _utc_now()),
        "updated_at": str(raw.get("updated_at") or _utc_now()),
    }


def normalize_cell(raw: dict[str, Any]) -> dict[str, Any]:
    cell_type = str(raw.get("cell_type") or "code")
    if cell_type not in CELL_TYPES:
        raise CodeWorkspaceError("Cell type is not allowed")
    execution_state = str(raw.get("execution_state") or "not_run")
    if execution_state not in ALLOWED_CELL_STATES:
        raise CodeWorkspaceError("Cell execution state is not allowed")
    return {
        "cell_id": _safe_id(raw.get("cell_id") or f"cell-{uuid4().hex[:12]}", "Cell id"),
        "cell_type": cell_type,
        "source": _safe_source(raw.get("source", "")),
        "outputs": _cell_outputs(raw.get("outputs", [])),
        "execution_count": _execution_count(raw.get("execution_count")),
        "execution_state": execution_state,
    }


def notebook_to_ipynb(notebook: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_notebook(notebook)
    return {
        "cells": [
            {
                "cell_type": cell["cell_type"],
                "execution_count": cell["execution_count"],
                "metadata": {},
                "outputs": cell["outputs"] if cell["cell_type"] == "code" else [],
                "source": _source_to_lines(cell["source"]),
            }
            for cell in normalized["cells"]
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {
                "name": "python",
                "version": "3.12",
            },
            "local_terminal": {
                "execution_enabled": False,
                "notebook_id": normalized["notebook_id"],
            },
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def notebook_from_ipynb(raw: dict[str, Any]) -> dict[str, Any]:
    cells = []
    raw_cells = raw.get("cells")
    if not isinstance(raw_cells, list):
        raise CodeWorkspaceError("Notebook cells must be a list")
    for raw_cell in raw_cells:
        if not isinstance(raw_cell, dict):
            raise CodeWorkspaceError("Notebook cell must be an object")
        cell_type = str(raw_cell.get("cell_type") or "code")
        cells.append(
            {
                "cell_id": f"cell-{uuid4().hex[:12]}",
                "cell_type": cell_type,
                "source": _source_from_raw(raw_cell.get("source", "")),
                "outputs": raw_cell.get("outputs", []),
                "execution_count": raw_cell.get("execution_count"),
                "execution_state": "imported",
            }
        )
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    local_meta = (
        metadata.get("local_terminal") if isinstance(metadata.get("local_terminal"), dict) else {}
    )
    return {
        "notebook_id": str(local_meta.get("notebook_id") or f"notebook-{uuid4().hex[:12]}"),
        "name": str(local_meta.get("name") or "Imported Notebook"),
        "path": str(local_meta.get("path") or ""),
        "kernel": "Python 3.12 local",
        "kernel_status": "idle",
        "execution_state": "idle",
        "cells": cells or default_notebook_request()["cells"],
    }


def _notebook_cells(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise CodeWorkspaceError("Notebook cells must be a list")
    if len(raw) > MAX_CELLS:
        raise CodeWorkspaceError(f"Notebook cells exceed limit of {MAX_CELLS}")
    cells = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise CodeWorkspaceError("Notebook cell must be an object")
        cell = normalize_cell(item)
        if cell["cell_id"] in seen:
            raise CodeWorkspaceError("Notebook cell ids must be unique")
        seen.add(cell["cell_id"])
        cells.append(cell)
    if not cells:
        return _notebook_cells(default_notebook_request()["cells"])
    return cells


def _notebook_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    notebooks = list(state["notebooks"].values())
    return [
        {
            "notebook_id": notebook["notebook_id"],
            "name": notebook["name"],
            "path": notebook["path"],
            "cell_count": len(notebook["cells"]),
            "kernel_status": notebook["kernel_status"],
            "updated_at": notebook["updated_at"],
        }
        for notebook in sorted(
            notebooks,
            key=lambda notebook: str(notebook.get("updated_at", "")),
            reverse=True,
        )
    ]


def _analysis_health_row(
    root: Path,
    code_state: dict[str, Any],
    notebook: dict[str, Any],
) -> dict[str, Any]:
    notebook_id = str(notebook["notebook_id"])
    file_rows: list[dict[str, Any]] = []
    mtimes: list[float] = []
    artifact_bytes = 0
    for name, relative_path in _analysis_artifact_files(notebook_id).items():
        exists, size, mtime = _code_artifact_stat(root, relative_path)
        if mtime is not None:
            mtimes.append(mtime)
        artifact_bytes += size
        file_rows.append(
            {
                "name": name,
                "path": relative_path,
                "exists": exists,
                "bytes": size,
                "updated_at": _timestamp_text(mtime),
            }
        )
    by_name = {row["name"]: row for row in file_rows}
    present = [row["name"] for row in file_rows if row["exists"]]
    missing = [row["name"] for row in file_rows if not row["exists"]]
    notebook_exists = bool(by_name["notebook"]["exists"])
    has_cells = bool(notebook["cells"])
    last_analysis = code_state.get("last_analysis") if isinstance(code_state, dict) else None
    last_analysis_id = ""
    if isinstance(last_analysis, dict) and last_analysis.get("notebook_id") == notebook_id:
        last_analysis_id = str(last_analysis.get("analysis_id") or "")
    if not has_cells:
        health_state = "empty_notebook"
    elif not notebook_exists:
        health_state = "partial_missing_notebook"
    elif not missing and last_analysis_id:
        health_state = "complete"
    else:
        health_state = "partial_missing_analysis"
    return {
        "notebook_id": notebook_id,
        "name": str(notebook.get("name") or ""),
        "active_notebook": str(code_state.get("active_notebook_id") or "") == notebook_id,
        "kernel_status": str(notebook.get("kernel_status") or ""),
        "cell_count": len(notebook["cells"]),
        "code_cell_count": sum(1 for cell in notebook["cells"] if cell["cell_type"] == "code"),
        "markdown_cell_count": sum(
            1 for cell in notebook["cells"] if cell["cell_type"] == "markdown"
        ),
        "created_at": str(notebook.get("created_at") or ""),
        "updated_at": str(notebook.get("updated_at") or ""),
        "health_state": health_state,
        "expected_count": len(file_rows),
        "present_count": len(present),
        "missing_count": len(missing),
        "present_artifacts": present,
        "missing_artifacts": missing,
        "files": file_rows,
        "notebook_artifact_path": str(by_name["notebook"]["path"]),
        "notebook_artifact_exists": notebook_exists,
        "analysis_artifact_path": str(by_name["analysis"]["path"]),
        "analysis_artifact_exists": bool(by_name["analysis"]["exists"]),
        "report_artifact_path": str(by_name["report"]["path"]),
        "report_artifact_exists": bool(by_name["report"]["exists"]),
        "manifest_artifact_path": str(by_name["manifest"]["path"]),
        "manifest_artifact_exists": bool(by_name["manifest"]["exists"]),
        "artifact_bytes": artifact_bytes,
        "latest_artifact_updated_at": _timestamp_text(max(mtimes) if mtimes else None),
        "last_analysis_id": last_analysis_id,
        "supervision_ready": notebook_exists,
        "recovery_hint": (
            "ready_for_static_analysis_or_agent_inspection"
            if notebook_exists and health_state != "complete"
            else (
                "ready_for_agent_supervision"
                if health_state == "complete"
                else "create_or_import_a_local_notebook_before_static_analysis"
            )
        ),
        "source_returned": False,
        "artifact_content_read": False,
        "destructive_actions_enabled": False,
    }


def _analysis_health_recovery_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return [
            {
                "queue_id": "code_analysis_health:none",
                "notebook_id": "",
                "artifact_path": "artifacts/code_workspace",
                "recommended_action": "code_analyze",
                "endpoint": "/api/code/analyze",
                "method": "POST",
                "reason": "No local Code notebooks exist; create or import one before static analysis.",
                "destructive_action_required": False,
                "writes_local_artifacts": True,
            }
        ]
    queue = []
    for row in rows:
        if int(row["missing_count"]) == 0 and row["last_analysis_id"]:
            continue
        queue.append(
            {
                "queue_id": f"code_analysis_health:{row['notebook_id']}:artifacts",
                "notebook_id": row["notebook_id"],
                "artifact_path": row["notebook_artifact_path"],
                "recommended_action": "code_analyze",
                "endpoint": "/api/code/analyze",
                "method": "POST",
                "reason": "Regenerate local static-analysis artifacts from the stored notebook.",
                "destructive_action_required": False,
                "writes_local_artifacts": True,
            }
        )
    return queue


def _code_artifact_stat(root: Path, relative_path: str) -> tuple[bool, int, float | None]:
    try:
        resolved_root = root.resolve()
        resolved_path = (root / relative_path).resolve()
    except OSError:
        return False, 0, None
    if not resolved_path.is_relative_to(resolved_root) or not resolved_path.is_file():
        return False, 0, None
    try:
        stat = resolved_path.stat()
    except OSError:
        return False, 0, None
    return True, stat.st_size, stat.st_mtime


def _timestamp_text(timestamp: float | None) -> str:
    if timestamp is None:
        return ""
    return (
        datetime.fromtimestamp(timestamp, UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _latest_notebook_id(notebooks: dict[str, dict[str, Any]]) -> str:
    if not notebooks:
        return ""
    return max(notebooks.values(), key=lambda notebook: str(notebook.get("updated_at", "")))[
        "notebook_id"
    ]


def _active_notebook(state: dict[str, Any]) -> dict[str, Any]:
    active_id = str(state.get("active_notebook_id") or "")
    if not active_id or active_id not in state["notebooks"]:
        raise CodeWorkspaceError("Notebook is required")
    return state["notebooks"][active_id]


def _notebook_from_request_or_state(
    state: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    if isinstance(request.get("notebook"), dict):
        return normalize_notebook(request["notebook"])
    notebook_id = str(request.get("notebook_id") or state.get("active_notebook_id") or "")
    if not notebook_id:
        raise CodeWorkspaceError("Notebook is required")
    notebook_id = _safe_id(notebook_id, "Notebook id")
    if notebook_id not in state["notebooks"]:
        raise CodeWorkspaceError("Notebook not found")
    return copy.deepcopy(state["notebooks"][notebook_id])


def _notebook_from_existing_id(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    notebook_id = str(request.get("notebook_id") or state.get("active_notebook_id") or "")
    if not notebook_id:
        raise CodeWorkspaceError("Notebook is required")
    notebook_id = _safe_id(notebook_id, "Notebook id")
    if notebook_id not in state["notebooks"]:
        raise CodeWorkspaceError("Notebook not found")
    return copy.deepcopy(state["notebooks"][notebook_id])


def _normalize_last_export(raw: Any) -> dict[str, str] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    return {
        "notebook_id": _safe_id(raw.get("notebook_id"), "Notebook id"),
        "path": _safe_notebook_path(raw.get("path"), str(raw.get("notebook_id") or "notebook")),
        "format": _safe_text(raw.get("format") or "ipynb", "Export format", 20),
        "created_at": _safe_text(raw.get("created_at"), "Export timestamp", 80),
    }


def _normalize_last_analysis(raw: Any, active_notebook_id: str) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        return None
    notebook_id = _safe_id(raw.get("notebook_id") or active_notebook_id, "Notebook id")
    artifact_files = _normalize_analysis_artifact_files(raw.get("artifact_files"), notebook_id)
    summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    return {
        "analysis_id": _safe_text(raw.get("analysis_id"), "Analysis id", 80),
        "notebook_id": notebook_id,
        "notebook_name": _safe_text(raw.get("notebook_name"), "Notebook name", 80),
        "status": _safe_text(raw.get("status") or "completed", "Analysis status", 40),
        "output_mode": _safe_text(
            raw.get("output_mode") or "local_static_notebook_report",
            "Analysis output mode",
            80,
        ),
        "summary": {
            "cell_count": _bounded_int(summary.get("cell_count", 0), "Cell count", 0, MAX_CELLS),
            "code_cell_count": _bounded_int(
                summary.get("code_cell_count", 0), "Code cell count", 0, MAX_CELLS
            ),
            "markdown_cell_count": _bounded_int(
                summary.get("markdown_cell_count", 0), "Markdown cell count", 0, MAX_CELLS
            ),
            "output_cell_count": _bounded_int(
                summary.get("output_cell_count", 0), "Output cell count", 0, MAX_CELLS
            ),
            "source_line_count": _bounded_int(
                summary.get("source_line_count", 0), "Source line count", 0, 20000
            ),
            "context_source_count": _bounded_int(
                summary.get("context_source_count", 0), "Context source count", 0, MAX_CELLS
            ),
            "context_artifact_count": _bounded_int(
                summary.get("context_artifact_count", 0), "Context artifact count", 0, 1000
            ),
            "local_artifact_reference_count": _bounded_int(
                summary.get("local_artifact_reference_count", 0),
                "Local artifact reference count",
                0,
                1000,
            ),
            "import_count": _bounded_int(summary.get("import_count", 0), "Import count", 0, 1000),
            "definition_count": _bounded_int(
                summary.get("definition_count", 0), "Definition count", 0, 1000
            ),
            "call_count": _bounded_int(summary.get("call_count", 0), "Call count", 0, 2000),
            "syntax_error_count": _bounded_int(
                summary.get("syntax_error_count", 0), "Syntax error count", 0, MAX_CELLS
            ),
            "execution_enabled": False,
            "mutation": False,
        },
        "referenced_artifacts": _safe_artifact_refs(raw.get("referenced_artifacts")),
        "context_sources": _safe_context_source_refs(raw.get("context_sources")),
        "static_outline": _safe_static_outline(raw.get("static_outline")),
        "artifact_files": artifact_files,
        "created_at": _safe_text(raw.get("created_at"), "Analysis timestamp", 80),
    }


def _safe_id(raw: Any, label: str) -> str:
    value = str(raw or "").strip()
    if not value or len(value) > 80:
        raise CodeWorkspaceError(f"{label} is required")
    if not all(ch.isalnum() or ch in {"-", "_"} for ch in value):
        raise CodeWorkspaceError(f"{label} is invalid")
    return value


def _notebook_static_analysis(notebook: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    cells = notebook.get("cells") if isinstance(notebook.get("cells"), list) else []
    source_lines = sum(len(str(cell.get("source") or "").splitlines()) for cell in cells)
    referenced_artifacts = _extract_local_artifact_refs(cells, context)
    static_outline = _notebook_static_outline(cells)
    notebook_id = notebook["notebook_id"]
    context_sources = [
        {
            "source_id": str(source.get("source_id") or ""),
            "label": str(source.get("label") or ""),
            "state": str(source.get("state") or ""),
            "cache_path": str(source.get("cache_path") or ""),
        }
        for source in context["sources"][:8]
        if isinstance(source, dict)
    ]
    analysis = {
        "analysis_id": f"code-analysis-{uuid4().hex[:12]}",
        "notebook_id": notebook_id,
        "notebook_name": notebook["name"],
        "status": "completed",
        "output_mode": "local_static_notebook_report",
        "summary": {
            "cell_count": len(cells),
            "code_cell_count": sum(1 for cell in cells if cell.get("cell_type") == "code"),
            "markdown_cell_count": sum(1 for cell in cells if cell.get("cell_type") == "markdown"),
            "output_cell_count": sum(1 for cell in cells if cell.get("outputs")),
            "source_line_count": source_lines,
            "context_source_count": len(context_sources),
            "context_artifact_count": int(context["summary"]["artifact_count"]),
            "local_artifact_reference_count": len(referenced_artifacts),
            "import_count": len(static_outline["imports"]),
            "definition_count": len(static_outline["definitions"]),
            "call_count": len(static_outline["calls"]),
            "syntax_error_count": len(static_outline["syntax_errors"]),
            "execution_enabled": False,
            "mutation": False,
        },
        "referenced_artifacts": referenced_artifacts,
        "context_sources": context_sources,
        "static_outline": static_outline,
        "artifact_files": _analysis_artifact_files(notebook_id),
        "created_at": _utc_now(),
    }
    return _normalize_last_analysis(analysis, notebook_id) or analysis


def _analysis_artifact_files(notebook_id: str) -> dict[str, str]:
    prefix = f"artifacts/code_workspace/{notebook_id}"
    return {
        "notebook": f"artifacts/code_workspace/{notebook_id}.ipynb",
        "analysis": f"{prefix}/analysis.json",
        "report": f"{prefix}/analysis_report.md",
        "manifest": f"{prefix}/analysis_manifest.json",
    }


def _normalize_analysis_artifact_files(raw: Any, notebook_id: str) -> dict[str, str]:
    if raw in (None, ""):
        return _analysis_artifact_files(notebook_id)
    if not isinstance(raw, dict):
        raise CodeWorkspaceError("Analysis artifact files must be an object")
    allowed = {"notebook", "analysis", "report", "manifest"}
    files = {}
    for raw_key, raw_path in raw.items():
        key = str(raw_key or "").strip()
        if key not in allowed:
            continue
        path = _safe_code_artifact_path(raw_path, notebook_id)
        if path:
            files[key] = path
    defaults = _analysis_artifact_files(notebook_id)
    return {**defaults, **files}


def _safe_code_artifact_path(raw_path: Any, notebook_id: str) -> str:
    value = str(raw_path or "").strip().replace("\\", "/")
    notebook_file = f"artifacts/code_workspace/{notebook_id}.ipynb"
    analysis_prefix = f"artifacts/code_workspace/{notebook_id}/"
    if value == notebook_file:
        return value
    if not value.startswith(analysis_prefix):
        return ""
    if ".." in value.split("/"):
        return ""
    if value.rsplit(".", 1)[-1] not in {"json", "md"}:
        return ""
    return value


def _extract_local_artifact_refs(cells: list[dict[str, Any]], context: dict[str, Any]) -> list[str]:
    refs: set[str] = set()
    pattern = re.compile(r"\b(?:artifacts|market_data)/[A-Za-z0-9_./-]+")
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        for match in pattern.findall(str(cell.get("source") or "")):
            safe_ref = _safe_local_ref(match)
            if safe_ref:
                refs.add(safe_ref)
    for artifact in context["artifacts"][:8]:
        if isinstance(artifact, dict):
            safe_ref = _safe_local_ref(str(artifact.get("path") or ""))
            if safe_ref:
                refs.add(safe_ref)
    return sorted(refs)[:24]


def _safe_local_ref(raw_path: str) -> str:
    value = str(raw_path or "").strip().replace("\\", "/").rstrip(".,;:)\"'")
    if not value.startswith(("artifacts/", "market_data/")):
        return ""
    if ".." in value.split("/"):
        return ""
    if any(part.startswith(".") for part in value.split("/")):
        return ""
    return value[:240]


def _safe_artifact_refs(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    refs = []
    for item in raw[:24]:
        safe_ref = _safe_local_ref(str(item or ""))
        if safe_ref:
            refs.append(safe_ref)
    return refs


def _safe_context_source_refs(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    refs = []
    for item in raw[:8]:
        if not isinstance(item, dict):
            continue
        refs.append(
            {
                "source_id": _safe_text(item.get("source_id") or "source", "Source id", 80),
                "label": _safe_text(item.get("label") or "Source", "Source label", 80),
                "state": _safe_text(item.get("state") or "unknown", "Source state", 40),
                "cache_path": _safe_local_ref(str(item.get("cache_path") or "")),
            }
        )
    return refs


def _notebook_static_outline(cells: list[dict[str, Any]]) -> dict[str, Any]:
    imports: set[str] = set()
    definitions: list[dict[str, str]] = []
    calls: set[str] = set()
    syntax_errors: list[str] = []
    for index, cell in enumerate(cells, start=1):
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        source = _source_from_raw(cell.get("source"))
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            syntax_errors.append(f"cell {index}: line {exc.lineno or 0}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(_safe_outline_name(alias.name))
            elif isinstance(node, ast.ImportFrom):
                module = _safe_outline_name(node.module or "")
                for alias in node.names:
                    name = _safe_outline_name(alias.name)
                    imports.add(f"{module}.{name}" if module else name)
            elif isinstance(node, ast.FunctionDef):
                definitions.append({"kind": "function", "name": _safe_outline_name(node.name)})
            elif isinstance(node, ast.AsyncFunctionDef):
                definitions.append({"kind": "async_function", "name": _safe_outline_name(node.name)})
            elif isinstance(node, ast.ClassDef):
                definitions.append({"kind": "class", "name": _safe_outline_name(node.name)})
            elif isinstance(node, ast.Call):
                call_name = _call_name(node.func)
                if call_name:
                    calls.add(call_name)
    return {
        "imports": sorted(item for item in imports if item)[:24],
        "definitions": [item for item in definitions if item["name"]][:24],
        "calls": sorted(calls)[:32],
        "syntax_errors": syntax_errors[:12],
        "safety": {
            "static_parse_only": True,
            "execution_enabled": False,
            "source_returned": False,
        },
    }


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return _safe_outline_name(node.id)
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        name = _safe_outline_name(node.attr)
        return f"{parent}.{name}" if parent and name else name
    return ""


def _safe_static_outline(raw: Any) -> dict[str, Any]:
    outline = raw if isinstance(raw, dict) else {}
    return {
        "imports": _safe_outline_names(outline.get("imports"), 24),
        "definitions": _safe_outline_definitions(outline.get("definitions")),
        "calls": _safe_outline_names(outline.get("calls"), 32),
        "syntax_errors": _safe_outline_names(outline.get("syntax_errors"), 12),
        "safety": {
            "static_parse_only": True,
            "execution_enabled": False,
            "source_returned": False,
        },
    }


def _safe_outline_definitions(raw: Any) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        return []
    definitions = []
    for item in raw[:24]:
        if not isinstance(item, dict):
            continue
        kind = _safe_outline_name(item.get("kind"))
        name = _safe_outline_name(item.get("name"))
        if kind and name:
            definitions.append({"kind": kind, "name": name})
    return definitions


def _safe_outline_names(raw: Any, limit: int) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [name for name in (_safe_outline_name(item) for item in raw[:limit]) if name]


def _safe_outline_name(raw: Any) -> str:
    value = str(raw or "").strip()
    value = re.sub(r"[^A-Za-z0-9_.:-]", "", value)
    return value[:120]


def _bounded_int(raw: Any, label: str, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise CodeWorkspaceError(f"{label} must be numeric") from None
    if value < minimum or value > maximum:
        raise CodeWorkspaceError(f"{label} is out of range")
    return value


def _safe_text(raw: Any, label: str, max_length: int) -> str:
    value = str(raw or "").strip()
    if not value:
        raise CodeWorkspaceError(f"{label} is required")
    if _contains_secret(value):
        raise CodeWorkspaceError(f"{label} appears to contain credential material")
    return value[:max_length]


def _safe_source(raw: Any) -> str:
    value = _source_from_raw(raw)
    if len(value) > MAX_SOURCE_LENGTH:
        raise CodeWorkspaceError(f"Cell source exceeds limit of {MAX_SOURCE_LENGTH}")
    if _contains_secret(value):
        raise CodeWorkspaceError("Cell source appears to contain credential material")
    if _contains_forbidden_runtime_intent(value):
        raise CodeWorkspaceError("Cell source contains forbidden live runtime intent")
    return value


def _source_from_raw(raw: Any) -> str:
    if isinstance(raw, list):
        return "".join(str(part) for part in raw)
    return str(raw or "")


def _source_to_lines(source: str) -> list[str]:
    if not source:
        return []
    lines = source.splitlines(keepends=True)
    if source and not source.endswith(("\n", "\r")) and lines:
        lines[-1] = lines[-1]
    return lines


def _cell_outputs(raw: Any) -> list[dict[str, str]]:
    if raw in (None, []):
        return []
    if not isinstance(raw, list):
        raise CodeWorkspaceError("Cell outputs must be a list")
    outputs = []
    for item in raw[:MAX_OUTPUTS]:
        outputs.append(_cell_output(item))
    return outputs


def _cell_output(raw: Any) -> dict[str, str]:
    if isinstance(raw, dict):
        output_type = str(raw.get("output_type") or "display_data")
        text_raw = raw.get("text", raw.get("data", ""))
        text = (
            json.dumps(text_raw, sort_keys=True)
            if isinstance(text_raw, dict)
            else str(text_raw or "")
        )
    else:
        output_type = "stream"
        text = str(raw or "")
    if _contains_secret(text):
        raise CodeWorkspaceError("Cell output appears to contain credential material")
    return {
        "output_type": _safe_text(output_type, "Output type", 40),
        "text": text[:MAX_OUTPUT_LENGTH],
    }


def _execution_count(raw: Any) -> int | None:
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise CodeWorkspaceError("Execution count must be numeric") from None
    if value < 0 or value > 99999:
        raise CodeWorkspaceError("Execution count is invalid")
    return value


def _kernel_status(raw: Any) -> str:
    value = str(raw or "idle").strip().lower()
    if value not in {"idle", "saved", "imported"}:
        raise CodeWorkspaceError("Kernel status is not allowed")
    return "idle" if value in {"saved", "imported"} else value


def _safe_notebook_path(raw: Any, notebook_id: str) -> str:
    value = str(raw or "").strip().replace("\\", "/")
    if not value:
        value = f"artifacts/code_workspace/{notebook_id}.ipynb"
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise CodeWorkspaceError("Notebook path must be repository-local")
    if ".." in value.split("/"):
        raise CodeWorkspaceError("Notebook path cannot traverse directories")
    if not value.endswith(".ipynb"):
        raise CodeWorkspaceError("Notebook path must use .ipynb")
    if not value.startswith("artifacts/code_workspace/"):
        raise CodeWorkspaceError("Notebook path must stay under artifacts/code_workspace")
    return value


def _contains_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _contains_forbidden_runtime_intent(value: str) -> bool:
    return any(pattern.search(value) for pattern in FORBIDDEN_RUNTIME_PATTERNS)


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
