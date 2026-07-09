"""Local dry-run workflow definitions for the Nodes workspace."""

from __future__ import annotations

import copy
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.local_terminal.advanced_context import sanitize_advanced_context


MAX_WORKFLOWS = 80
MAX_WORKFLOW_NODES = 80
MAX_WORKFLOW_EDGES = 120
MAX_CONFIG_KEYS = 32
MAX_CONFIG_VALUE_LENGTH = 240
WORKFLOW_MODES = {"local", "paper", "dry_run"}
FORBIDDEN_CONFIG_TERMS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "private_key",
    "live",
    "real_order",
    "real_balance",
    "margin",
    "leverage",
    "short",
    "derivative",
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


class NodesError(ValueError):
    """Raised when a workflow request violates local dry-run rules."""


NODE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "node_type": "manual_trigger",
        "category": "Control Flow",
        "name": "Manual Trigger",
        "inputs": [],
        "outputs": ["event"],
        "safety_level": "local",
    },
    {
        "node_type": "set_variable",
        "category": "Core",
        "name": "Set Variable",
        "inputs": ["event"],
        "outputs": ["value"],
        "safety_level": "local",
    },
    {
        "node_type": "results_display",
        "category": "Core",
        "name": "Results Display",
        "inputs": ["value"],
        "outputs": [],
        "safety_level": "local",
    },
    {
        "node_type": "crypto_price",
        "category": "Market Data",
        "name": "Crypto Price",
        "inputs": ["symbol"],
        "outputs": ["price"],
        "safety_level": "public_read_only",
    },
    {
        "node_type": "historical_data",
        "category": "Market Data",
        "name": "Historical Data",
        "inputs": ["symbol", "timeframe"],
        "outputs": ["bars"],
        "safety_level": "public_read_only",
    },
    {
        "node_type": "market_news",
        "category": "Market Data",
        "name": "Market News",
        "inputs": ["query"],
        "outputs": ["articles"],
        "safety_level": "public_read_only",
    },
    {
        "node_type": "backtest_engine",
        "category": "Analytics",
        "name": "Backtest Engine",
        "inputs": ["bars", "strategy"],
        "outputs": ["summary"],
        "safety_level": "local",
    },
    {
        "node_type": "risk_analysis",
        "category": "Analytics",
        "name": "Risk Analysis",
        "inputs": ["positions"],
        "outputs": ["risk"],
        "safety_level": "local",
    },
    {
        "node_type": "sharpe_sortino",
        "category": "Analytics",
        "name": "Sharpe / Sortino",
        "inputs": ["returns"],
        "outputs": ["metrics"],
        "safety_level": "local",
    },
    {
        "node_type": "filter",
        "category": "Data Transform",
        "name": "Filter",
        "inputs": ["rows"],
        "outputs": ["rows"],
        "safety_level": "local",
    },
    {
        "node_type": "map",
        "category": "Data Transform",
        "name": "Map",
        "inputs": ["rows"],
        "outputs": ["rows"],
        "safety_level": "local",
    },
    {
        "node_type": "aggregate",
        "category": "Data Transform",
        "name": "Aggregate",
        "inputs": ["rows"],
        "outputs": ["summary"],
        "safety_level": "local",
    },
    {
        "node_type": "risk_check",
        "category": "Safety",
        "name": "Risk Check",
        "inputs": ["intent"],
        "outputs": ["decision"],
        "safety_level": "local_guard",
    },
    {
        "node_type": "position_size_limit",
        "category": "Safety",
        "name": "Position Size Limit",
        "inputs": ["intent"],
        "outputs": ["decision"],
        "safety_level": "local_guard",
    },
    {
        "node_type": "loss_limit",
        "category": "Safety",
        "name": "Loss Limit",
        "inputs": ["ledger"],
        "outputs": ["decision"],
        "safety_level": "local_guard",
    },
    {
        "node_type": "place_order",
        "category": "Trading",
        "name": "Place Order",
        "inputs": ["intent"],
        "outputs": ["paper_order_intent"],
        "safety_level": "paper_only",
    },
    {
        "node_type": "get_positions",
        "category": "Trading",
        "name": "Get Positions",
        "inputs": [],
        "outputs": ["paper_positions"],
        "safety_level": "paper_only",
    },
    {
        "node_type": "get_balance",
        "category": "Trading",
        "name": "Get Balance",
        "inputs": [],
        "outputs": ["paper_balance"],
        "safety_level": "paper_only",
    },
    {
        "node_type": "log",
        "category": "Utilities",
        "name": "Log",
        "inputs": ["value"],
        "outputs": [],
        "safety_level": "local",
    },
    {
        "node_type": "assert",
        "category": "Utilities",
        "name": "Assert",
        "inputs": ["value"],
        "outputs": ["value"],
        "safety_level": "local",
    },
    {
        "node_type": "mcp_tool",
        "category": "MCP",
        "name": "MCP Tool",
        "inputs": ["request"],
        "outputs": ["response"],
        "safety_level": "disabled_external",
    },
    {
        "node_type": "ai_agent",
        "category": "Agents",
        "name": "AI Agent",
        "inputs": ["prompt"],
        "outputs": ["draft"],
        "safety_level": "disabled_external",
    },
    {
        "node_type": "webhook",
        "category": "Notifications",
        "name": "Webhook",
        "inputs": ["message"],
        "outputs": [],
        "safety_level": "disabled_external",
    },
)
NODE_DEFINITION_BY_TYPE = {
    str(definition["node_type"]): definition for definition in NODE_DEFINITIONS
}


def default_nodes_state() -> dict[str, Any]:
    return {
        "active_workflow_id": None,
        "workflows": {},
        "selected_node_id": None,
        "last_dry_run": None,
        "updated_at": "not started",
    }


def default_workflow_request() -> dict[str, Any]:
    return {
        "name": "Local Workflow Draft",
        "description": "Dry-run workflow definition stored locally.",
        "mode": "dry_run",
        "nodes": [],
        "edges": [],
    }


def workflow_templates() -> list[dict[str, Any]]:
    return [
        {
            "template_id": "template-hello-local",
            "name": "Hello Local Workflow",
            "description": "Manual trigger to variable to result display.",
            "mode": "dry_run",
            "nodes": [
                _node("manual_trigger", "Manual Trigger", 35, 110),
                _node("set_variable", "Set Variable", 180, 110, {"value": "hello"}),
                _node("results_display", "Results Display", 325, 110),
            ],
            "edges": [
                _edge("manual_trigger", "set_variable"),
                _edge("set_variable", "results_display"),
            ],
        },
        {
            "template_id": "template-provider-context",
            "name": "Provider Context Brief",
            "description": "Dry-run public cache and local artifact context into a result display.",
            "mode": "dry_run",
            "nodes": [
                _node("manual_trigger", "Manual Trigger", 35, 100),
                _node("historical_data", "Provider Candles", 175, 100, {"symbol": "BTCUSDT"}),
                _node("backtest_engine", "Backtest Artifact", 315, 100),
                _node("market_news", "News Cache", 455, 100, {"query": "macro"}),
                _node("results_display", "Context Brief", 595, 100),
            ],
            "edges": [
                _edge("manual_trigger", "historical_data"),
                _edge("historical_data", "backtest_engine"),
                _edge("backtest_engine", "market_news"),
                _edge("market_news", "results_display"),
            ],
        },
    ]


def nodes_safety_payload() -> dict[str, bool | str]:
    return {
        "dry_run_only": True,
        "deploy_enabled": False,
        "execute_enabled": False,
        "live_deployment": False,
        "broker_routing": False,
        "real_orders": False,
        "private_api_required": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives": False,
        "external_mutation": False,
        "output": "plan_only",
        "runtime_state": "disabled_no_safety_contract",
    }


def normalize_nodes_state(state: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    default = default_nodes_state()
    invalid_workflows = (
        {str(key): str(value) for key, value in state.get("invalid_workflows", {}).items()}
        if isinstance(state.get("invalid_workflows"), dict)
        else {}
    )
    if strict and invalid_workflows:
        first_key, first_value = next(iter(invalid_workflows.items()))
        raise NodesError(f"Nodes state is invalid: {first_key}: {first_value}")

    raw_workflows = state.get("workflows")
    workflows: dict[str, dict[str, Any]] = {}
    if isinstance(raw_workflows, dict):
        if len(raw_workflows) > MAX_WORKFLOWS:
            raise NodesError(f"Workflows exceed limit of {MAX_WORKFLOWS}")
        for workflow_id, raw_workflow in raw_workflows.items():
            if not isinstance(raw_workflow, dict):
                if strict:
                    raise NodesError(f"Stored workflow {workflow_id} must be an object")
                invalid_workflows[str(workflow_id)] = "Stored workflow must be an object"
                continue
            try:
                workflow = normalize_workflow(raw_workflow, fallback_id=str(workflow_id))
            except NodesError as exc:
                if strict:
                    raise NodesError(f"Stored workflow {workflow_id} is invalid: {exc}") from exc
                invalid_workflows[str(workflow_id)] = str(exc)
                continue
            workflows[workflow["workflow_id"]] = workflow
    elif raw_workflows not in (None, {}):
        if strict:
            raise NodesError("Stored workflows must be an object")
        invalid_workflows["workflows"] = "Stored workflows must be an object"

    active_id = str(state.get("active_workflow_id") or "")
    if active_id not in workflows:
        active_id = _latest_workflow_id(workflows)

    try:
        last_dry_run = _normalize_dry_run(state.get("last_dry_run"))
    except NodesError as exc:
        if strict:
            raise NodesError(f"Stored dry-run is invalid: {exc}") from exc
        invalid_workflows["last_dry_run"] = str(exc)
        last_dry_run = None
    selected_node_id = str(state.get("selected_node_id") or "")
    if active_id and selected_node_id not in {
        node["node_id"] for node in workflows[active_id]["nodes"]
    }:
        selected_node_id = ""
    return {
        **default,
        "active_workflow_id": active_id or None,
        "workflows": workflows,
        "selected_node_id": selected_node_id or None,
        "last_dry_run": last_dry_run,
        "invalid_workflows": invalid_workflows,
        "updated_at": str(state.get("updated_at") or default["updated_at"]),
    }


def nodes_workflow_health_payload(state: dict[str, Any], root: Path) -> dict[str, Any]:
    """Return metadata-only health for local Nodes workflow artifacts."""

    nodes_state = normalize_nodes_state(state, strict=False)
    rows = [
        _workflow_health_row(root, nodes_state, workflow)
        for workflow in sorted(
            nodes_state["workflows"].values(),
            key=lambda workflow: str(workflow.get("updated_at", "")),
            reverse=True,
        )
    ]
    recovery_queue = _workflow_health_recovery_queue(rows)
    latest = rows[0] if rows else {}
    return {
        "mode": "metadata_only_nodes_workflow_health",
        "contract": "nodes_workflow_health_v1",
        "generated_at": _utc_now(),
        "root": "artifacts/workflows",
        "summary": {
            "workflow_count": len(rows),
            "complete_count": sum(1 for row in rows if row["health_state"] == "complete"),
            "empty_workflow_count": sum(
                1 for row in rows if row["health_state"] == "empty_workflow"
            ),
            "partial_count": sum(1 for row in rows if row["health_state"].startswith("partial")),
            "missing_artifact_count": sum(int(row["missing_count"]) for row in rows),
            "supervision_ready_count": sum(1 for row in rows if row["supervision_ready"]),
            "invalid_workflow_count": len(nodes_state["invalid_workflows"]),
            "active_workflow_id": str(nodes_state.get("active_workflow_id") or ""),
            "latest_workflow_id": str(latest.get("workflow_id") or ""),
            "recovery_queue_count": len(recovery_queue),
            "destructive_action_count": 0,
        },
        "workflows": rows,
        "recovery_queue": recovery_queue,
        "recommended_actions": [
            {
                "action_id": "nodes_dry_run",
                "endpoint": "/api/nodes/dry-run",
                "method": "POST",
                "ready": any(row["definition_artifact_exists"] for row in rows),
                "reason": (
                    "Run a local dry-run to create missing Nodes output artifacts."
                    if rows
                    else "Load or import a local workflow before running a dry-run."
                ),
            }
        ],
        "safety": {
            "local_only": True,
            "read_only": True,
            "metadata_only": True,
            "workflow_execution": False,
            "artifact_content_read": False,
            "artifact_content_indexing": False,
            "writes_local_artifacts": False,
            "automatic_repair_enabled": False,
            "destructive_actions_enabled": False,
            "provider_calls": False,
            "secret_values_returned": False,
            "credentials_persisted": False,
            "broker_mutation": False,
            "ledger_mutation": False,
            "real_orders": False,
            "real_balance": False,
            "live_trading": False,
        },
    }


def nodes_payload(
    state: dict[str, Any],
    context: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    nodes_state = normalize_nodes_state(state, strict=False)
    active_id = nodes_state["active_workflow_id"]
    active_workflow = copy.deepcopy(nodes_state["workflows"].get(active_id)) if active_id else None
    selected_node = None
    if active_workflow and nodes_state["selected_node_id"]:
        selected_node = next(
            (
                copy.deepcopy(node)
                for node in active_workflow["nodes"]
                if node["node_id"] == nodes_state["selected_node_id"]
            ),
            None,
        )
    return {
        "active_workflow_id": active_id,
        "first_use": active_workflow is None,
        "toolbar": [
            "Undo",
            "Redo",
            "Save",
            "Load",
            "Clear",
            "Import",
            "Export",
            "Templates",
            "Deploy",
            "Execute",
        ],
        "library": _library_payload(),
        "templates": workflow_templates(),
        "workflows": _workflow_list(nodes_state),
        "active_workflow": active_workflow,
        "workflow_draft": active_workflow or default_workflow_request(),
        "selected_node": selected_node,
        "last_dry_run": nodes_state["last_dry_run"],
        "invalid_workflows": nodes_state["invalid_workflows"],
        "engine": {
            "engine_id": "local_nodes_v1",
            "state": "draft",
            "workflow_count": len(nodes_state["workflows"]),
            "node_count": len(active_workflow["nodes"]) if active_workflow else 0,
            "edge_count": len(active_workflow["edges"]) if active_workflow else 0,
        },
        "safety": nodes_safety_payload(),
        "context": sanitize_advanced_context(context),
        "workflow_health": nodes_workflow_health_payload(nodes_state, root or Path.cwd()),
    }


def save_workflow(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    nodes_state = normalize_nodes_state(copy.deepcopy(state))
    workflow_request = (
        request.get("workflow") if isinstance(request.get("workflow"), dict) else request
    )
    requested_id = str(workflow_request.get("workflow_id") or "")
    if requested_id:
        requested_id = _safe_id(requested_id, "Workflow id")
    if (
        len(nodes_state["workflows"]) >= MAX_WORKFLOWS
        and requested_id not in nodes_state["workflows"]
    ):
        raise NodesError(f"Workflows exceed limit of {MAX_WORKFLOWS}")
    now = _utc_now()
    workflow = normalize_workflow(
        {
            **workflow_request,
            "workflow_id": workflow_request.get("workflow_id") or f"workflow-{uuid4().hex[:12]}",
            "created_at": workflow_request.get("created_at") or now,
            "updated_at": now,
        }
    )
    nodes_state["workflows"][workflow["workflow_id"]] = workflow
    nodes_state["active_workflow_id"] = workflow["workflow_id"]
    nodes_state["selected_node_id"] = workflow["nodes"][0]["node_id"] if workflow["nodes"] else None
    nodes_state["updated_at"] = now
    return nodes_state


def load_template(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    template_id = str(request.get("template_id") or "")
    template = next(
        (template for template in workflow_templates() if template["template_id"] == template_id),
        None,
    )
    if template is None:
        raise NodesError("Workflow template not found")
    return save_workflow(
        state,
        {
            "name": template["name"],
            "description": template["description"],
            "mode": template["mode"],
            "nodes": template["nodes"],
            "edges": template["edges"],
        },
    )


def select_workflow(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    nodes_state = normalize_nodes_state(copy.deepcopy(state))
    workflow_id = _safe_id(request.get("workflow_id"), "Workflow id")
    if workflow_id not in nodes_state["workflows"]:
        raise NodesError("Workflow not found")
    nodes_state["active_workflow_id"] = workflow_id
    nodes_state["selected_node_id"] = (
        nodes_state["workflows"][workflow_id]["nodes"][0]["node_id"]
        if nodes_state["workflows"][workflow_id]["nodes"]
        else None
    )
    nodes_state["updated_at"] = _utc_now()
    return nodes_state


def select_node(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    nodes_state = normalize_nodes_state(copy.deepcopy(state))
    active_id = str(nodes_state.get("active_workflow_id") or "")
    if not active_id:
        raise NodesError("Workflow is required")
    node_id = _safe_id(request.get("node_id"), "Node id")
    if node_id not in {node["node_id"] for node in nodes_state["workflows"][active_id]["nodes"]}:
        raise NodesError("Node not found")
    nodes_state["selected_node_id"] = node_id
    nodes_state["updated_at"] = _utc_now()
    return nodes_state


def clear_workflow(state: dict[str, Any]) -> dict[str, Any]:
    nodes_state = normalize_nodes_state(copy.deepcopy(state))
    nodes_state["active_workflow_id"] = None
    nodes_state["selected_node_id"] = None
    nodes_state["last_dry_run"] = None
    nodes_state["updated_at"] = _utc_now()
    return nodes_state


def import_workflow(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    raw_workflow = request.get("workflow")
    if isinstance(raw_workflow, str):
        try:
            raw_workflow = json.loads(raw_workflow)
        except json.JSONDecodeError:
            raise NodesError("Workflow import JSON is invalid") from None
    if not isinstance(raw_workflow, dict):
        raise NodesError("Workflow import must be an object")
    return save_workflow(state, {"workflow": raw_workflow})


def export_workflow(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    workflow = _workflow_from_request_or_state(normalize_nodes_state(state), request)
    return {
        "workflow": copy.deepcopy(workflow),
        "safety": nodes_safety_payload(),
    }


def dry_run_workflow(
    state: dict[str, Any],
    request: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    nodes_state = normalize_nodes_state(copy.deepcopy(state))
    workflow = _workflow_from_request_or_state(nodes_state, request)
    steps = []
    safe_context = sanitize_advanced_context(context)
    for index, node in enumerate(workflow["nodes"], start=1):
        definition = NODE_DEFINITION_BY_TYPE[node["node_type"]]
        blocked = definition["safety_level"] == "disabled_external"
        action = "blocked_external" if blocked else "plan_only"
        if definition["safety_level"] == "paper_only":
            action = "paper_intent_plan_only"
        if definition["safety_level"] == "public_read_only":
            action = "read_provider_cache"
        steps.append(
            {
                "index": index,
                "node_id": node["node_id"],
                "label": node["label"],
                "node_type": node["node_type"],
                "category": node["category"],
                "safety_level": definition["safety_level"],
                "action": action,
                "mutation": False,
                "runtime_allowed": False,
                "context_source": _context_source_for_node(node["node_type"], safe_context),
            }
        )
    artifact_files = _dry_run_artifact_files(workflow["workflow_id"])
    plan = {
        "plan_id": f"dry-run-{uuid4().hex[:12]}",
        "workflow_id": workflow["workflow_id"],
        "status": "blocked"
        if any(step["action"] == "blocked_external" for step in steps)
        else "planned",
        "dry_run": True,
        "deploy_enabled": False,
        "execute_enabled": False,
        "mutation": False,
        "steps": steps,
        "output_summary": {
            "output_mode": "local_dry_run_artifact",
            "step_count": len(steps),
            "read_provider_cache_count": sum(
                1 for step in steps if step["action"] == "read_provider_cache"
            ),
            "paper_intent_count": sum(
                1 for step in steps if step["action"] == "paper_intent_plan_only"
            ),
            "blocked_external_count": sum(
                1 for step in steps if step["action"] == "blocked_external"
            ),
            "context_source_count": sum(1 for step in steps if step["context_source"]),
            "artifact_count": safe_context["summary"]["artifact_count"],
            "runtime_allowed": False,
            "mutation": False,
        },
        "context": {
            "summary": safe_context["summary"],
            "sources": [
                {
                    "source_id": source["source_id"],
                    "state": source["state"],
                    "cache_path": source["cache_path"],
                }
                for source in safe_context["sources"][:6]
            ],
            "artifacts": [
                {
                    "kind": artifact["kind"],
                    "path": artifact["path"],
                }
                for artifact in safe_context["artifacts"][:6]
            ],
        },
        "artifact_files": artifact_files,
        "created_at": _utc_now(),
    }
    nodes_state["last_dry_run"] = plan
    nodes_state["active_workflow_id"] = workflow["workflow_id"]
    nodes_state["updated_at"] = plan["created_at"]
    return nodes_state, plan


def dry_run_artifact_manifest(workflow: dict[str, Any], dry_run: dict[str, Any]) -> dict[str, Any]:
    artifact_files = (
        dry_run.get("artifact_files") if isinstance(dry_run.get("artifact_files"), dict) else {}
    )
    output_summary = (
        dry_run.get("output_summary") if isinstance(dry_run.get("output_summary"), dict) else {}
    )
    return {
        "workflow_id": str(workflow.get("workflow_id") or dry_run.get("workflow_id") or ""),
        "workflow_name": str(workflow.get("name") or ""),
        "plan_id": str(dry_run.get("plan_id") or ""),
        "status": str(dry_run.get("status") or ""),
        "created_at": str(dry_run.get("created_at") or ""),
        "artifact_files": artifact_files,
        "output_summary": output_summary,
        "safety": {
            "local_artifact_only": True,
            "dry_run_only": True,
            "deploy_enabled": False,
            "execute_enabled": False,
            "runtime_allowed": False,
            "mutation": False,
            "real_orders": False,
            "private_api_required": False,
            "real_balance": False,
            "margin": False,
            "leverage": False,
            "short": False,
            "derivatives": False,
        },
    }


def dry_run_report_text(workflow: dict[str, Any], dry_run: dict[str, Any]) -> str:
    output_summary = (
        dry_run.get("output_summary") if isinstance(dry_run.get("output_summary"), dict) else {}
    )
    context = dry_run.get("context") if isinstance(dry_run.get("context"), dict) else {}
    sources = context.get("sources") if isinstance(context.get("sources"), list) else []
    artifacts = context.get("artifacts") if isinstance(context.get("artifacts"), list) else []
    steps = dry_run.get("steps") if isinstance(dry_run.get("steps"), list) else []
    lines = [
        f"# Nodes Dry-Run Report {dry_run.get('plan_id', '')}",
        "",
        f"- Workflow: {workflow.get('name', '')}",
        f"- Workflow ID: {dry_run.get('workflow_id', '')}",
        f"- Status: {dry_run.get('status', '')}",
        f"- Output mode: {output_summary.get('output_mode', 'local_dry_run_artifact')}",
        f"- Steps: {output_summary.get('step_count', 0)}",
        f"- Provider reads: {output_summary.get('read_provider_cache_count', 0)}",
        f"- Context sources used: {output_summary.get('context_source_count', 0)}",
        "- Safety: dry-run only, no deploy, no execute, no mutation, no real orders",
        "",
        "## Steps",
    ]
    lines.extend(
        (
            f"- {step.get('index', '')}. {step.get('label', '')}: "
            f"{step.get('action', '')} / {step.get('safety_level', '')}"
            f"{' / ' + str(step.get('context_source')) if step.get('context_source') else ''}"
        )
        for step in steps
        if isinstance(step, dict)
    )
    lines.extend(["", "## Sources"])
    lines.extend(
        f"- {source.get('source_id', '')}: {source.get('state', '')} / {source.get('cache_path', '')}"
        for source in sources
        if isinstance(source, dict)
    )
    lines.extend(["", "## Local Artifacts"])
    lines.extend(
        f"- {artifact.get('kind', '')}: {artifact.get('path', '')}"
        for artifact in artifacts
        if isinstance(artifact, dict)
    )
    return "\n".join(lines) + "\n"


def disabled_runtime_response(action: str) -> dict[str, Any]:
    return {
        "action": action,
        "state": "disabled",
        "reason": "Nodes runtime is dry-run only until a dedicated live safety contract exists.",
        "safety": nodes_safety_payload(),
    }


def normalize_workflow(raw: dict[str, Any], fallback_id: str | None = None) -> dict[str, Any]:
    workflow_id = _safe_id(raw.get("workflow_id") or fallback_id, "Workflow id")
    nodes = _workflow_nodes(raw.get("nodes", []))
    edges = _workflow_edges(raw.get("edges", []), {node["node_id"] for node in nodes})
    mode = str(raw.get("mode") or "dry_run")
    if mode not in WORKFLOW_MODES:
        raise NodesError("Workflow mode is not allowed")
    return {
        "workflow_id": workflow_id,
        "name": _safe_text(raw.get("name"), "Workflow name", 80),
        "description": _optional_text(raw.get("description"), "", 240),
        "mode": mode,
        "nodes": nodes,
        "edges": edges,
        "created_at": str(raw.get("created_at") or _utc_now()),
        "updated_at": str(raw.get("updated_at") or _utc_now()),
    }


def _workflow_health_row(
    root: Path,
    nodes_state: dict[str, Any],
    workflow: dict[str, Any],
) -> dict[str, Any]:
    workflow_id = str(workflow["workflow_id"])
    file_rows: list[dict[str, Any]] = []
    mtimes: list[float] = []
    artifact_bytes = 0
    for name, relative_path in _dry_run_artifact_files(workflow_id).items():
        exists, size, mtime = _workflow_artifact_stat(root, relative_path)
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
    definition_exists = bool(by_name["definition"]["exists"])
    if not workflow["nodes"] and not workflow["edges"]:
        health_state = "empty_workflow"
    elif not missing:
        health_state = "complete"
    elif not definition_exists:
        health_state = "partial_missing_definition"
    else:
        health_state = "partial_missing_dry_run"
    last_dry_run = nodes_state.get("last_dry_run") if isinstance(nodes_state, dict) else None
    last_plan_id = ""
    if isinstance(last_dry_run, dict) and last_dry_run.get("workflow_id") == workflow_id:
        last_plan_id = str(last_dry_run.get("plan_id") or "")
    return {
        "workflow_id": workflow_id,
        "name": str(workflow.get("name") or ""),
        "mode": str(workflow.get("mode") or ""),
        "active_workflow": str(nodes_state.get("active_workflow_id") or "") == workflow_id,
        "node_count": len(workflow["nodes"]),
        "edge_count": len(workflow["edges"]),
        "created_at": str(workflow.get("created_at") or ""),
        "updated_at": str(workflow.get("updated_at") or ""),
        "health_state": health_state,
        "expected_count": len(file_rows),
        "present_count": len(present),
        "missing_count": len(missing),
        "present_artifacts": present,
        "missing_artifacts": missing,
        "files": file_rows,
        "definition_artifact_path": str(by_name["definition"]["path"]),
        "definition_artifact_exists": definition_exists,
        "dry_run_artifact_path": str(by_name["dry_run"]["path"]),
        "dry_run_artifact_exists": bool(by_name["dry_run"]["exists"]),
        "report_artifact_path": str(by_name["report"]["path"]),
        "report_artifact_exists": bool(by_name["report"]["exists"]),
        "manifest_artifact_path": str(by_name["manifest"]["path"]),
        "manifest_artifact_exists": bool(by_name["manifest"]["exists"]),
        "artifact_bytes": artifact_bytes,
        "latest_artifact_updated_at": _timestamp_text(max(mtimes) if mtimes else None),
        "last_dry_run_plan_id": last_plan_id,
        "supervision_ready": definition_exists,
        "recovery_hint": (
            "ready_for_nodes_dry_run_or_agent_inspection"
            if definition_exists and health_state != "complete"
            else (
                "ready_for_agent_supervision"
                if health_state == "complete"
                else "load_or_import_a_local_workflow_before_dry_run"
            )
        ),
        "artifact_content_read": False,
        "destructive_actions_enabled": False,
    }


def _workflow_health_recovery_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return [
            {
                "queue_id": "nodes_workflow_health:none",
                "workflow_id": "",
                "artifact_path": "artifacts/workflows",
                "recommended_action": "nodes_dry_run",
                "endpoint": "/api/nodes/dry-run",
                "method": "POST",
                "reason": "No local Nodes workflows exist; load or import a workflow before dry-run.",
                "destructive_action_required": False,
                "writes_local_artifacts": True,
            }
        ]
    queue = []
    for row in rows:
        if int(row["missing_count"]) == 0:
            continue
        queue.append(
            {
                "queue_id": f"nodes_workflow_health:{row['workflow_id']}:artifacts",
                "workflow_id": row["workflow_id"],
                "artifact_path": row["definition_artifact_path"],
                "recommended_action": "nodes_dry_run",
                "endpoint": "/api/nodes/dry-run",
                "method": "POST",
                "reason": "Regenerate local dry-run artifacts from the stored workflow definition.",
                "destructive_action_required": False,
                "writes_local_artifacts": True,
            }
        )
    return queue


def _workflow_artifact_stat(root: Path, relative_path: str) -> tuple[bool, int, float | None]:
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
    return datetime.fromtimestamp(timestamp, UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _library_payload() -> list[dict[str, Any]]:
    categories: dict[str, list[dict[str, Any]]] = {}
    for definition in NODE_DEFINITIONS:
        item = {
            "node_type": definition["node_type"],
            "name": definition["name"],
            "inputs": definition["inputs"],
            "outputs": definition["outputs"],
            "safety_level": definition["safety_level"],
        }
        categories.setdefault(str(definition["category"]), []).append(item)
    return [
        {
            "category": category,
            "count": len(items),
            "nodes": items,
        }
        for category, items in categories.items()
    ]


def _workflow_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    workflows = list(state["workflows"].values())
    return [
        {
            "workflow_id": workflow["workflow_id"],
            "name": workflow["name"],
            "mode": workflow["mode"],
            "node_count": len(workflow["nodes"]),
            "edge_count": len(workflow["edges"]),
            "updated_at": workflow["updated_at"],
        }
        for workflow in sorted(
            workflows,
            key=lambda workflow: str(workflow.get("updated_at", "")),
            reverse=True,
        )
    ]


def _latest_workflow_id(workflows: dict[str, dict[str, Any]]) -> str:
    if not workflows:
        return ""
    return max(workflows.values(), key=lambda workflow: str(workflow.get("updated_at", "")))[
        "workflow_id"
    ]


def _workflow_from_request_or_state(
    state: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    if isinstance(request.get("workflow"), dict):
        return normalize_workflow(request["workflow"])
    workflow_id = str(request.get("workflow_id") or state.get("active_workflow_id") or "")
    if not workflow_id:
        raise NodesError("Workflow is required")
    workflow_id = _safe_id(workflow_id, "Workflow id")
    if workflow_id not in state["workflows"]:
        raise NodesError("Workflow not found")
    return state["workflows"][workflow_id]


def _workflow_nodes(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise NodesError("Workflow nodes must be a list")
    if len(raw) > MAX_WORKFLOW_NODES:
        raise NodesError(f"Workflow nodes exceed limit of {MAX_WORKFLOW_NODES}")
    nodes = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise NodesError("Workflow node must be an object")
        node_type = str(item.get("node_type") or "")
        if node_type not in NODE_DEFINITION_BY_TYPE:
            raise NodesError("Workflow node type is not allowed")
        definition = NODE_DEFINITION_BY_TYPE[node_type]
        node_id = _safe_id(item.get("node_id") or node_type, "Node id")
        if node_id in seen:
            raise NodesError("Workflow node ids must be unique")
        seen.add(node_id)
        nodes.append(
            {
                "node_id": node_id,
                "node_type": node_type,
                "label": _safe_text(item.get("label") or definition["name"], "Node label", 80),
                "category": definition["category"],
                "x": _bounded_int(item.get("x", 0), "Node x", -4000, 4000),
                "y": _bounded_int(item.get("y", 0), "Node y", -4000, 4000),
                "config": _node_config(item.get("config", {})),
                "safety_level": definition["safety_level"],
            }
        )
    return nodes


def _workflow_edges(raw: Any, node_ids: set[str]) -> list[dict[str, str]]:
    if not isinstance(raw, list):
        raise NodesError("Workflow edges must be a list")
    if len(raw) > MAX_WORKFLOW_EDGES:
        raise NodesError(f"Workflow edges exceed limit of {MAX_WORKFLOW_EDGES}")
    edges = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise NodesError("Workflow edge must be an object")
        source = _safe_id(item.get("source"), "Edge source")
        target = _safe_id(item.get("target"), "Edge target")
        if source not in node_ids or target not in node_ids:
            raise NodesError("Workflow edge references missing node")
        edge_id = _safe_id(item.get("edge_id") or f"{source}-{target}", "Edge id")
        if edge_id in seen:
            raise NodesError("Workflow edge ids must be unique")
        seen.add(edge_id)
        edges.append({"edge_id": edge_id, "source": source, "target": target})
    return edges


def _node_config(raw: Any) -> dict[str, str | int | float | bool | None]:
    if not isinstance(raw, dict):
        raise NodesError("Node config must be an object")
    if len(raw) > MAX_CONFIG_KEYS:
        raise NodesError(f"Node config exceeds limit of {MAX_CONFIG_KEYS}")
    config: dict[str, str | int | float | bool | None] = {}
    for raw_key, value in raw.items():
        key = _safe_text(raw_key, "Config key", 60)
        lowered = key.lower().replace("-", "_").replace(" ", "_")
        if any(term in lowered for term in FORBIDDEN_CONFIG_TERMS):
            raise NodesError("Node config contains forbidden runtime key")
        if isinstance(value, str):
            if _contains_secret(value):
                raise NodesError("Node config appears to contain credential material")
            normalized_value = value.lower().replace("-", "_").replace(" ", "_")
            if any(term in normalized_value for term in FORBIDDEN_CONFIG_TERMS):
                raise NodesError("Node config contains forbidden runtime value")
            config[key] = value[:MAX_CONFIG_VALUE_LENGTH]
        elif isinstance(value, bool | int | float) or value is None:
            config[key] = value
        else:
            raise NodesError("Node config values must be scalar")
    return config


def _normalize_dry_run(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise NodesError("Dry-run result must be an object")
    if raw.get("dry_run") is not True or raw.get("mutation") not in (False, None):
        raise NodesError("Dry-run result must be non-mutating")
    raw_steps = raw.get("steps")
    if not isinstance(raw_steps, list):
        raise NodesError("Dry-run steps must be a list")
    workflow_id = _safe_id(raw.get("workflow_id"), "Workflow id")
    return {
        "plan_id": _safe_text(raw.get("plan_id"), "Dry-run id", 80),
        "workflow_id": workflow_id,
        "status": _safe_text(raw.get("status"), "Dry-run status", 40),
        "dry_run": True,
        "deploy_enabled": False,
        "execute_enabled": False,
        "mutation": False,
        "steps": [_normalize_dry_run_step(step) for step in raw_steps[:MAX_WORKFLOW_NODES]],
        "output_summary": _normalize_dry_run_output_summary(raw.get("output_summary")),
        "context": _normalize_dry_run_context(raw.get("context")),
        "artifact_files": _normalize_dry_run_artifact_files(raw.get("artifact_files"), workflow_id),
        "created_at": _safe_text(raw.get("created_at"), "Dry-run timestamp", 80),
    }


def _normalize_dry_run_step(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise NodesError("Dry-run step must be an object")
    if raw.get("mutation") not in (False, None):
        raise NodesError("Dry-run step must be non-mutating")
    return {
        "index": _bounded_int(raw.get("index"), "Dry-run index", 1, MAX_WORKFLOW_NODES),
        "node_id": _safe_id(raw.get("node_id"), "Node id"),
        "label": _safe_text(raw.get("label"), "Dry-run label", 80),
        "node_type": _safe_text(raw.get("node_type"), "Node type", 80),
        "category": _safe_text(raw.get("category"), "Node category", 80),
        "safety_level": _safe_text(raw.get("safety_level"), "Safety level", 80),
        "action": _safe_text(raw.get("action"), "Dry-run action", 80),
        "mutation": False,
        "runtime_allowed": False,
        "context_source": _optional_text(raw.get("context_source"), "", 160),
    }


def _normalize_dry_run_context(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {"summary": {}, "sources": [], "artifacts": []}
    summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    sources = raw.get("sources") if isinstance(raw.get("sources"), list) else []
    artifacts = raw.get("artifacts") if isinstance(raw.get("artifacts"), list) else []
    return {
        "summary": {
            "source_count": _bounded_int(
                summary.get("source_count", 0), "Source count", 0, MAX_WORKFLOW_NODES
            ),
            "ready_source_count": _bounded_int(
                summary.get("ready_source_count", 0),
                "Ready source count",
                0,
                MAX_WORKFLOW_NODES,
            ),
            "artifact_count": _bounded_int(
                summary.get("artifact_count", 0), "Artifact count", 0, 1000
            ),
        },
        "sources": [
            {
                "source_id": _optional_text(source.get("source_id"), "", 80),
                "state": _optional_text(source.get("state"), "", 40),
                "cache_path": _optional_text(source.get("cache_path"), "", 240),
            }
            for source in sources[:8]
            if isinstance(source, dict)
        ],
        "artifacts": [
            {
                "kind": _optional_text(artifact.get("kind"), "", 40),
                "path": _optional_text(artifact.get("path"), "", 240),
            }
            for artifact in artifacts[:8]
            if isinstance(artifact, dict)
        ],
    }


def _normalize_dry_run_output_summary(raw: Any) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "output_mode": _optional_text(raw.get("output_mode"), "local_dry_run_artifact", 80),
        "step_count": _bounded_int(raw.get("step_count", 0), "Step count", 0, MAX_WORKFLOW_NODES),
        "read_provider_cache_count": _bounded_int(
            raw.get("read_provider_cache_count", 0),
            "Provider read count",
            0,
            MAX_WORKFLOW_NODES,
        ),
        "paper_intent_count": _bounded_int(
            raw.get("paper_intent_count", 0),
            "Paper intent count",
            0,
            MAX_WORKFLOW_NODES,
        ),
        "blocked_external_count": _bounded_int(
            raw.get("blocked_external_count", 0),
            "Blocked external count",
            0,
            MAX_WORKFLOW_NODES,
        ),
        "context_source_count": _bounded_int(
            raw.get("context_source_count", 0),
            "Context source count",
            0,
            MAX_WORKFLOW_NODES,
        ),
        "artifact_count": _bounded_int(raw.get("artifact_count", 0), "Artifact count", 0, 1000),
        "runtime_allowed": False,
        "mutation": False,
    }


def _normalize_dry_run_artifact_files(raw: Any, workflow_id: str) -> dict[str, str]:
    if raw in (None, ""):
        return _dry_run_artifact_files(workflow_id)
    if not isinstance(raw, dict):
        raise NodesError("Dry-run artifact files must be an object")
    allowed = {"definition", "dry_run", "report", "manifest"}
    files = {}
    for raw_key, raw_path in raw.items():
        key = _optional_text(raw_key, "", 40)
        if key not in allowed:
            continue
        path = _safe_workflow_artifact_path(raw_path, workflow_id)
        if path:
            files[key] = path
    defaults = _dry_run_artifact_files(workflow_id)
    return {**defaults, **files}


def _dry_run_artifact_files(workflow_id: str) -> dict[str, str]:
    prefix = f"artifacts/workflows/{workflow_id}"
    return {
        "definition": f"{prefix}/definition.json",
        "dry_run": f"{prefix}/dry_run.json",
        "report": f"{prefix}/dry_run_report.md",
        "manifest": f"{prefix}/dry_run_manifest.json",
    }


def _safe_workflow_artifact_path(raw_path: Any, workflow_id: str) -> str:
    value = _optional_text(raw_path, "", 240).replace("\\", "/")
    prefix = f"artifacts/workflows/{workflow_id}/"
    if not value.startswith(prefix):
        return ""
    if ".." in value.split("/"):
        return ""
    if value.rsplit(".", 1)[-1] not in {"json", "md"}:
        return ""
    return value


def _context_source_for_node(node_type: str, context: dict[str, Any]) -> str:
    preferred = {
        "crypto_price": "crypto_detail_cache",
        "historical_data": "crypto_detail_cache",
        "market_news": "news_cache",
        "backtest_engine": "backtest",
        "risk_analysis": "portfolio",
    }
    target = preferred.get(node_type)
    if not target:
        return ""
    for source in context["sources"]:
        if source["source_id"] == target:
            return source["cache_path"] or source["source_id"]
    for artifact in context.get("artifacts", []):
        if artifact.get("kind") == target:
            return str(artifact.get("path") or "")
    return ""


def _node(
    node_type: str, label: str, x: int, y: int, config: dict[str, Any] | None = None
) -> dict[str, Any]:
    definition = NODE_DEFINITION_BY_TYPE[node_type]
    return {
        "node_id": node_type,
        "node_type": node_type,
        "label": label,
        "category": definition["category"],
        "x": x,
        "y": y,
        "config": config or {},
        "safety_level": definition["safety_level"],
    }


def _edge(source: str, target: str) -> dict[str, str]:
    return {
        "edge_id": f"{source}-{target}",
        "source": source,
        "target": target,
    }


def _safe_id(raw: Any, label: str) -> str:
    value = str(raw or "").strip()
    if not value or len(value) > 80:
        raise NodesError(f"{label} is required")
    if not all(ch.isalnum() or ch in {"-", "_"} for ch in value):
        raise NodesError(f"{label} is invalid")
    return value


def _safe_text(raw: Any, label: str, max_length: int) -> str:
    value = str(raw or "").strip()
    if not value:
        raise NodesError(f"{label} is required")
    if _contains_secret(value):
        raise NodesError(f"{label} appears to contain credential material")
    return value[:max_length]


def _optional_text(raw: Any, default: str, max_length: int) -> str:
    value = str(raw or default).strip()
    if value and _contains_secret(value):
        raise NodesError("Text appears to contain credential material")
    return value[:max_length]


def _contains_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _bounded_int(raw: Any, label: str, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise NodesError(f"{label} must be numeric") from None
    if value < minimum:
        raise NodesError(f"{label} is below minimum")
    if value > maximum:
        raise NodesError(f"{label} is too large")
    return value


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
