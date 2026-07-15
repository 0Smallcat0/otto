"""Read-only AI supervision contract for the local command center."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from otto.local_terminal.provider_acquisition import provider_acquisition_gate_payload


COMMAND_CENTER_VERSION = "m22-command-center-v1"
CURRENT_MILESTONE = "M23.68 Final non-live completion audit"
CURRENT_MILESTONE_PATH = "docs/planning/M23_FINAL_NON_LIVE_COMPLETION_AUDIT.md"
FINAL_COMPLETION_AUDIT_PATH = "docs/planning/M23_FINAL_NON_LIVE_COMPLETION_AUDIT.md"


def command_center_payload(
    governance: dict[str, Any] | None,
    *,
    current_milestone: str = CURRENT_MILESTONE,
    advanced_outputs: dict[str, Any] | None = None,
    agent_activity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a machine-operable supervision view without mutating local state."""

    governance = governance if isinstance(governance, dict) else {}
    summary = _dict(governance.get("summary"))
    agent_contract = _dict(governance.get("agent_contract"))
    artifact_lifecycle = _dict(governance.get("artifact_lifecycle"))
    provider_refresh = _dict(governance.get("provider_refresh_lifecycle"))
    local_secret_status = _dict(governance.get("local_secret_status"))
    safety_gates = _dict(governance.get("safety_gates"))
    source_wall = _dict(governance.get("source_wall"))

    activity = _activity(summary, agent_contract)
    route_action_contract = _route_action_contract(agent_contract)
    provider_source_state = _provider_source_state(governance, summary)
    provider_acquisition_gate = provider_acquisition_gate_payload()
    artifact_recovery = _artifact_recovery(artifact_lifecycle, provider_refresh)
    advanced_output_state = _advanced_outputs(advanced_outputs)
    agent_activity_state = _agent_activity(agent_activity)
    active_task = _dict(agent_activity_state.get("active_task"))
    recovery_queue = _recovery_queue(
        artifact_recovery,
        advanced_output_state,
        agent_contract,
    )
    risk_gates = _risk_gates(safety_gates, local_secret_status, source_wall)
    provenance_evidence = _provenance_evidence()
    final_goal_audit = _final_goal_audit(
        current_milestone=current_milestone,
        route_action_contract=route_action_contract,
        provider_acquisition_gate=provider_acquisition_gate,
        artifact_recovery=artifact_recovery,
        advanced_outputs=advanced_output_state,
        risk_gates=risk_gates,
    )
    mission_ledger = _mission_ledger_snapshot(
        current_milestone=current_milestone,
        provenance_evidence=provenance_evidence,
    )
    activity_timeline = _activity_timeline(
        current_milestone=current_milestone,
        mission_ledger=mission_ledger,
        final_goal_audit=final_goal_audit,
        activity=activity,
        route_action_contract=route_action_contract,
        provider_source_state=provider_source_state,
        provider_acquisition_gate=provider_acquisition_gate,
        artifact_recovery=artifact_recovery,
        advanced_outputs=advanced_output_state,
        agent_activity=agent_activity_state,
        active_task=active_task,
        recovery_queue=recovery_queue,
        risk_gates=risk_gates,
        provenance_evidence=provenance_evidence,
    )

    return {
        "generated_at": _utc_now(),
        "mode": "read_only_ai_supervision_contract",
        "version": COMMAND_CENTER_VERSION,
        "current_milestone": current_milestone,
        "mission_ledger": mission_ledger,
        "final_goal_audit": final_goal_audit,
        "activity": activity,
        "activity_timeline": activity_timeline,
        "route_action_contract": route_action_contract,
        "provider_source_state": provider_source_state,
        "provider_acquisition_gate": provider_acquisition_gate,
        "artifact_recovery": artifact_recovery,
        "advanced_outputs": advanced_output_state,
        "agent_activity": agent_activity_state,
        "active_task": active_task,
        "recovery_queue": recovery_queue,
        "risk_gates": risk_gates,
        "provenance_evidence": provenance_evidence,
        "selectors": _selectors(),
        "safety": {
            "read_only": True,
            "external_network": False,
            "secret_values_returned": False,
            "content_read": False,
            "destructive_actions_enabled": False,
            "live_trading": False,
            "broker_mutation": False,
            "installed_source_read": False,
        },
    }


def command_center_preflight_matrix_payload(
    governance: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return action preflight status rows without executing any action."""

    governance = governance if isinstance(governance, dict) else {}
    agent_contract = _dict(governance.get("agent_contract"))
    route_action_contract = _route_action_contract(agent_contract)
    return {
        "generated_at": _utc_now(),
        "mode": "read_only_command_center_preflight_matrix",
        "current_milestone": CURRENT_MILESTONE,
        "matrix": route_action_contract["preflight_status_matrix"],
        "preflight": route_action_contract["preflight"],
        "safety": {
            "read_only": True,
            "action_executed": False,
            "local_mutation_performed": False,
            "external_network": False,
            "secret_values_returned": False,
            "destructive_actions_enabled": False,
            "live_trading": False,
            "broker_mutation": False,
            "installed_source_read": False,
        },
    }


def _activity_timeline(
    *,
    current_milestone: str,
    mission_ledger: dict[str, Any],
    final_goal_audit: dict[str, Any],
    activity: dict[str, Any],
    route_action_contract: dict[str, Any],
    provider_source_state: dict[str, Any],
    provider_acquisition_gate: dict[str, Any],
    artifact_recovery: dict[str, Any],
    advanced_outputs: dict[str, Any],
    agent_activity: dict[str, Any],
    active_task: dict[str, Any],
    recovery_queue: dict[str, Any],
    risk_gates: dict[str, Any],
    provenance_evidence: dict[str, Any],
) -> list[dict[str, Any]]:
    return [
        {
            "event_id": "current_milestone",
            "state": str(activity.get("milestone_status") or "unknown"),
            "risk_level": "info",
            "summary": current_milestone,
            "evidence": str(provenance_evidence.get("current_milestone") or ""),
            "recovery_hint": "Resume from the mission ledger before selecting the next action.",
        },
        {
            "event_id": "mission_ledger",
            "state": str(mission_ledger.get("goal_status") or "unknown"),
            "risk_level": "info",
            "summary": (
                f"{_int(mission_ledger.get('do_not_redo_count'))} do-not-redo / "
                f"{_int(mission_ledger.get('partial_gap_count'))} partial gaps / "
                f"{_int(mission_ledger.get('blocked_gate_count'))} stop gates"
            ),
            "evidence": str(mission_ledger.get("ledger_path") or ""),
            "recovery_hint": str(
                mission_ledger.get("resume_rule")
                or "Resume from the mission ledger before editing."
            ),
        },
        {
            "event_id": "final_goal_audit",
            "state": str(final_goal_audit.get("goal_status") or "unknown"),
            "risk_level": "info",
            "summary": (
                f"{_int(final_goal_audit.get('completed_count'))} completed / "
                f"{_int(final_goal_audit.get('partial_count'))} partial / "
                f"{_int(final_goal_audit.get('blocked_or_excluded_count'))} blocked-or-excluded"
            ),
            "evidence": str(final_goal_audit.get("audit_path") or ""),
            "recovery_hint": str(
                final_goal_audit.get("next_action_policy")
                or "Only reopen scope through a new reviewed milestone."
            ),
        },
        {
            "event_id": "route_action_contract",
            "state": "available" if route_action_contract.get("route_count") else "missing",
            "risk_level": "info",
            "summary": (
                f"{_int(route_action_contract.get('route_count'))} routes / "
                f"{_int(route_action_contract.get('action_count'))} actions / "
                f"{_int(route_action_contract.get('selector_count'))} selectors"
            ),
            "evidence": "GET /api/agent-contract",
            "recovery_hint": "Use route actions and selectors before UI scraping.",
        },
        {
            "event_id": "provider_source_state",
            "state": "available" if provider_source_state.get("provider_count") else "missing",
            "risk_level": "watch" if provider_source_state.get("key_required_count") else "info",
            "summary": (
                f"{_int(provider_source_state.get('active_provider_count'))} active / "
                f"{_int(provider_source_state.get('key_required_count'))} key-required / "
                f"{_int(provider_source_state.get('plan_required_count'))} plan-gated"
            ),
            "evidence": "GET /api/providers",
            "recovery_hint": "Prefer public no-key refreshes; use local-secret gates only when a milestone requires it.",
        },
        {
            "event_id": "provider_acquisition_gate",
            "state": str(_dict(provider_acquisition_gate.get("summary")).get("resume_state") or "unknown"),
            "risk_level": "watch"
            if _dict(provider_acquisition_gate.get("summary")).get("requires_official_research")
            else "info",
            "summary": (
                f"{_int(_dict(provider_acquisition_gate.get('summary')).get('implemented_count'))} implemented / "
                f"{_int(_dict(provider_acquisition_gate.get('summary')).get('blocked_count'))} blocked / "
                f"{_int(_dict(provider_acquisition_gate.get('summary')).get('approved_next_count'))} approved next"
            ),
            "evidence": "GET /api/provider-acquisition-gate",
            "recovery_hint": str(
                _dict(provider_acquisition_gate.get("resume_contract")).get("next_safe_step")
                or "Use provider acquisition gate before adding provider adapters."
            ),
        },
        {
            "event_id": "artifact_recovery",
            "state": "queued" if artifact_recovery.get("recovery_queue") else "clear",
            "risk_level": "watch" if artifact_recovery.get("recovery_queue") else "info",
            "summary": (
                f"{_int(artifact_recovery.get('artifact_root_count'))} roots / "
                f"{_int(artifact_recovery.get('artifact_file_count'))} files / "
                f"{len(_list(artifact_recovery.get('recovery_queue')))} recovery"
            ),
            "evidence": "GET /api/artifact-lifecycle",
            "recovery_hint": "Run only non-destructive recovery actions exposed by the agent contract.",
        },
        {
            "event_id": "advanced_outputs",
            "state": str(advanced_outputs.get("mode") or "not_loaded"),
            "risk_level": "watch"
            if _int(_dict(advanced_outputs.get("summary")).get("recovery_recommended_count"))
            else "info",
            "summary": (
                f"{_int(_dict(advanced_outputs.get('summary')).get('routes_with_outputs'))} routes with outputs / "
                f"{_int(_dict(advanced_outputs.get('summary')).get('artifact_file_count'))} files"
            ),
            "evidence": "GET /api/advanced-workflows/output-packet",
            "recovery_hint": "Write metadata-only output packets; do not enable runtime execution.",
        },
        {
            "event_id": "agent_activity",
            "state": str(_dict(agent_activity.get("summary")).get("latest_state") or "none"),
            "risk_level": "watch" if active_task.get("is_active") else "info",
            "summary": (
                f"{_int(_dict(agent_activity.get('summary')).get('event_count'))} events / "
                f"{str(_dict(agent_activity.get('summary')).get('latest_action_id') or 'none')} / "
                f"active={str(active_task.get('action_id') or 'none')}"
            ),
            "evidence": "GET /api/agent-activity",
            "recovery_hint": "Append metadata-only events; never log request bodies or secrets.",
        },
        {
            "event_id": "recovery_queue",
            "state": "queued" if _int(_dict(recovery_queue.get("summary")).get("item_count")) else "clear",
            "risk_level": "watch"
            if _int(_dict(recovery_queue.get("summary")).get("item_count"))
            else "info",
            "summary": (
                f"{_int(_dict(recovery_queue.get('summary')).get('item_count'))} queued / "
                f"{_int(_dict(recovery_queue.get('summary')).get('advanced_output_count'))} advanced / "
                f"{_int(_dict(recovery_queue.get('summary')).get('provider_refresh_count'))} provider"
            ),
            "evidence": "GET /api/command-center",
            "recovery_hint": "Use only listed non-destructive actions and stop at live/private/destructive gates.",
        },
        {
            "event_id": "risk_gates",
            "state": str(risk_gates.get("live_safety_status") or "unknown"),
            "risk_level": "blocked" if risk_gates.get("live_mode_enabled") else "info",
            "summary": (
                f"live={bool(risk_gates.get('live_mode_enabled'))} / "
                f"secrets={bool(risk_gates.get('secret_value_reads_enabled'))} / "
                f"source_wall={risk_gates.get('source_wall_state') or 'unknown'}"
            ),
            "evidence": "GET /api/live-safety",
            "recovery_hint": "Stop for live/private/account/payment/destructive gates.",
        },
    ]


def _advanced_outputs(packet: dict[str, Any] | None) -> dict[str, Any]:
    packet = _dict(packet)
    summary = _dict(packet.get("summary"))
    return {
        "mode": str(packet.get("mode") or "not_loaded"),
        "contract": str(packet.get("contract") or ""),
        "summary": {
            "route_count": _int(summary.get("route_count")),
            "routes_with_outputs": _int(summary.get("routes_with_outputs")),
            "routes_missing_outputs": _int(summary.get("routes_missing_outputs")),
            "artifact_file_count": _int(summary.get("artifact_file_count")),
            "state_artifact_file_count": _int(summary.get("state_artifact_file_count")),
            "manifest_file_count": _int(summary.get("manifest_file_count")),
            "report_file_count": _int(summary.get("report_file_count")),
            "error_log_file_count": _int(summary.get("error_log_file_count")),
            "routes_health_complete": _int(summary.get("routes_health_complete")),
            "routes_health_partial": _int(summary.get("routes_health_partial")),
            "routes_health_missing": _int(summary.get("routes_health_missing")),
            "supervision_ready_count": _int(summary.get("supervision_ready_count")),
            "ready_source_count": _int(summary.get("ready_source_count")),
            "recovery_recommended_count": _int(summary.get("recovery_recommended_count")),
            "io_contract_route_count": _int(summary.get("io_contract_route_count")),
        },
        "routes": [
            {
                "route_id": str(route.get("route_id") or ""),
                "artifact_root": str(route.get("artifact_root") or ""),
                "artifact_count": _int(route.get("artifact_count")),
                "state_artifact_count": _int(route.get("state_artifact_count")),
                "has_outputs": bool(route.get("has_outputs")),
                "output_state": str(route.get("output_state") or ""),
                "health_state": str(route.get("health_state") or ""),
                "supervision_ready": bool(route.get("supervision_ready")),
                "expected_artifact_kinds": [
                    str(kind) for kind in _list(route.get("expected_artifact_kinds"))
                ],
                "missing_expected_kinds": [
                    str(kind) for kind in _list(route.get("missing_expected_kinds"))
                ],
                "health_reason": str(route.get("health_reason") or ""),
                "manifest_file_count": _int(_dict(route.get("artifact_kinds")).get("manifest")),
                "report_file_count": _int(_dict(route.get("artifact_kinds")).get("report")),
                "error_log_file_count": _int(_dict(route.get("artifact_kinds")).get("error_log")),
                "latest_artifact": _latest_artifact_path(route),
                "latest_manifest": str(route.get("latest_manifest_path") or ""),
                "latest_report": str(route.get("latest_report_path") or ""),
                "latest_error_log": str(route.get("latest_error_log_path") or ""),
                "latest_state_artifact": str(route.get("latest_state_artifact_path") or ""),
                "safe_action_id": str(_dict(route.get("safe_output_action")).get("action_id") or ""),
                "safe_endpoint": str(_dict(route.get("safe_output_action")).get("endpoint") or ""),
                "io_contract": _advanced_output_io_contract(route.get("io_contract")),
            }
            for route in _list(packet.get("routes"))
            if isinstance(route, dict)
        ],
        "recovery_queue": [
            {
                "route_id": str(item.get("route_id") or ""),
                "recommended_action": str(item.get("recommended_action") or ""),
                "endpoint": str(item.get("endpoint") or ""),
                "reason": str(item.get("reason") or ""),
            }
            for item in _list(packet.get("recovery_queue"))
            if isinstance(item, dict)
        ],
        "write_action": _dict(packet.get("write_action")),
        "safety": _dict(packet.get("safety")),
    }


def _agent_activity(activity: dict[str, Any] | None) -> dict[str, Any]:
    activity = _dict(activity)
    return {
        "mode": str(activity.get("mode") or "not_loaded"),
        "contract": str(activity.get("contract") or ""),
        "artifact_path": str(activity.get("artifact_path") or "artifacts/agent_activity/activity.jsonl"),
        "summary": _dict(activity.get("summary")),
        "active_task": _active_task(activity.get("active_task")),
        "events": [
            {
                "event_id": str(event.get("event_id") or ""),
                "created_at": str(event.get("created_at") or ""),
                "route_id": str(event.get("route_id") or ""),
                "action_id": str(event.get("action_id") or ""),
                "state": str(event.get("state") or ""),
                "summary": str(event.get("summary") or ""),
                "artifact_path": str(event.get("artifact_path") or ""),
                "endpoint": str(event.get("endpoint") or ""),
                "safety_class": str(event.get("safety_class") or ""),
                "request_body_logged": bool(event.get("request_body_logged")),
                "destructive_actions_enabled": bool(event.get("destructive_actions_enabled")),
            }
            for event in _list(activity.get("events"))
            if isinstance(event, dict)
        ],
        "write_action": _dict(activity.get("write_action")),
        "safety": _dict(activity.get("safety")),
    }


def _recovery_queue(
    artifact_recovery: dict[str, Any],
    advanced_outputs: dict[str, Any],
    agent_contract: dict[str, Any],
) -> dict[str, Any]:
    action_index = _action_index(agent_contract)
    items: list[dict[str, Any]] = []
    for row in _list(artifact_recovery.get("recovery_queue")):
        if not isinstance(row, dict):
            continue
        recommended_action = str(row.get("recommended_action") or "")
        action_id = (
            "provider_refresh_public_start"
            if "start_new_manual_refresh_job" in recommended_action
            else "provider_refresh_lifecycle_inspect"
        )
        action = _dict(action_index.get(action_id))
        items.append(
            _queue_item(
                queue_id=f"provider_refresh:{row.get('run_id') or 'unknown'}",
                source="provider_refresh_lifecycle",
                route_id="settings",
                state=str(row.get("lifecycle_state") or row.get("status") or ""),
                recommended_action=action_id,
                endpoint=str(action.get("endpoint") or "/api/providers/refresh-public/lifecycle"),
                method=str(action.get("method") or "GET"),
                reason=f"{recommended_action}: {row.get('artifact_dir') or ''}".strip(": "),
                artifact_path=str(row.get("artifact_dir") or ""),
                safety_class=str(action.get("safety_class") or "read_only_provider_refresh_lifecycle"),
                writes_local_artifacts=bool(action.get("writes_local_artifacts")),
            )
        )
    for row in _list(advanced_outputs.get("recovery_queue")):
        if not isinstance(row, dict):
            continue
        action_id = str(row.get("recommended_action") or "")
        action = _dict(action_index.get(action_id))
        route_id = str(row.get("route_id") or "")
        items.append(
            _queue_item(
                queue_id=f"advanced_outputs:{route_id or 'unknown'}",
                source="advanced_outputs",
                route_id=route_id,
                state=str(row.get("state") or "missing_output_artifacts"),
                recommended_action=action_id,
                endpoint=str(row.get("endpoint") or action.get("endpoint") or ""),
                method=str(action.get("method") or "POST"),
                reason=str(row.get("reason") or "write metadata-only advanced output packet"),
                artifact_path="",
                safety_class=str(
                    action.get("safety_class") or "metadata_only_advanced_local_output_packet"
                ),
                writes_local_artifacts=True,
            )
        )
    return {
        "mode": "read_only_recovery_queue",
        "summary": {
            "item_count": len(items),
            "provider_refresh_count": sum(
                1 for item in items if item["source"] == "provider_refresh_lifecycle"
            ),
            "advanced_output_count": sum(1 for item in items if item["source"] == "advanced_outputs"),
            "destructive_action_count": sum(
                1 for item in items if bool(item["destructive_actions_enabled"])
            ),
            "writes_local_artifacts_count": sum(
                1 for item in items if bool(item["writes_local_artifacts"])
            ),
        },
        "items": items,
        "safety": {
            "read_only_queue": True,
            "content_read": False,
            "secret_values_returned": False,
            "destructive_actions_enabled": False,
            "live_trading": False,
            "broker_mutation": False,
            "installed_source_read": False,
        },
    }


def _queue_item(
    *,
    queue_id: str,
    source: str,
    route_id: str,
    state: str,
    recommended_action: str,
    endpoint: str,
    method: str,
    reason: str,
    artifact_path: str,
    safety_class: str,
    writes_local_artifacts: bool,
) -> dict[str, Any]:
    return {
        "queue_id": queue_id,
        "source": source,
        "route_id": route_id,
        "state": state,
        "recommended_action": recommended_action,
        "method": method,
        "endpoint": endpoint,
        "reason": reason,
        "artifact_path": artifact_path,
        "safety_class": safety_class,
        "writes_local_artifacts": writes_local_artifacts,
        "requires_confirmation": False,
        "destructive_actions_enabled": False,
    }


def _action_index(agent_contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(action.get("action_id") or ""): action
        for action in _list(agent_contract.get("actions"))
        if isinstance(action, dict)
    }


def _activity(summary: dict[str, Any], agent_contract: dict[str, Any]) -> dict[str, Any]:
    agent_summary = _dict(agent_contract.get("summary"))
    return {
        "goal": "complete_non_live_ai_agent_first_local_terminal",
        "milestone_status": "contract_available",
        "agent_route_count": _int(summary.get("agent_route_count")),
        "agent_action_count": _int(summary.get("agent_action_count")),
        "agent_disabled_action_count": _int(summary.get("agent_disabled_action_count")),
        "routes_match_shell": bool(agent_summary.get("routes_match_shell")),
        "operator_instruction": "Use this payload before UI scraping or route-specific action selection.",
    }


def _mission_ledger_snapshot(
    *,
    current_milestone: str,
    provenance_evidence: dict[str, Any],
) -> dict[str, Any]:
    do_not_redo = [
        "16 route shell and global menus",
        "local settings, profile, and layouts",
        "paper crypto and paper/live isolation",
        "provider freshness and source coverage matrix",
        "AI Agent contract and command-center supervision surfaces",
        "M21.22-M21.23 cleanup and M22-M23 verified milestones",
    ]
    partial_gaps: list[str] = []
    blocked_gates = [
        "CAPTCHA",
        "2FA",
        "payment",
        "identity verification",
        "security alerts",
        "broker or exchange binding",
        "real balance reads",
        "live orders",
        "destructive artifact actions",
    ]
    return {
        "mode": "read_only_mission_ledger_snapshot",
        "goal_status": "complete_for_current_non_live_scope",
        "current_milestone": current_milestone,
        "ledger_path": str(provenance_evidence.get("mission_ledger") or ""),
        "final_audit_path": str(
            provenance_evidence.get("final_non_live_completion_audit") or ""
        ),
        "latest_milestone_path": str(provenance_evidence.get("current_milestone") or ""),
        "do_not_redo_count": len(do_not_redo),
        "partial_gap_count": len(partial_gaps),
        "blocked_gate_count": len(blocked_gates),
        "commit_cadence": "one_verified_milestone_per_lore_commit",
        "resume_rule": "Resume from the mission ledger, then PROJECT_STATE.md, then the latest milestone document.",
        "do_not_redo": do_not_redo,
        "partial_gaps": partial_gaps,
        "blocked_gates": blocked_gates,
        "status_classes": {
            "completed": "fresh evidence proves the milestone is implemented and verified",
            "partial": "useful behavior exists, but current evidence does not prove completion",
            "blocked": "progress requires a gated external step or forbidden safety boundary",
            "not-started": "no current local implementation evidence exists",
        },
        "next_action_policy": (
            "Current non-live scope is complete; reopen only through a new official "
            "provider-entry gate or a separate reviewed safety contract."
        ),
        "safety": {
            "read_only": True,
            "content_read": False,
            "secret_values_returned": False,
            "destructive_actions_enabled": False,
            "live_trading": False,
            "broker_mutation": False,
            "installed_source_read": False,
        },
    }


def _final_goal_audit(
    *,
    current_milestone: str,
    route_action_contract: dict[str, Any],
    provider_acquisition_gate: dict[str, Any],
    artifact_recovery: dict[str, Any],
    advanced_outputs: dict[str, Any],
    risk_gates: dict[str, Any],
) -> dict[str, Any]:
    provider_summary = _dict(provider_acquisition_gate.get("summary"))
    quote_closure = _dict(provider_acquisition_gate.get("quote_breadth_closure"))
    quote_backlog = _dict(quote_closure.get("provider_backlog"))
    advanced_summary = _dict(advanced_outputs.get("summary"))
    artifact_matrix = _dict(artifact_recovery.get("artifact_root_health_matrix"))
    artifact_summary = _dict(artifact_matrix.get("summary"))
    requirements = [
        {
            "requirement_id": "continue_from_m21_23",
            "status": "completed",
            "evidence": "PROJECT_STATE.md; docs/planning/M22_MISSION_LEDGER.md",
            "proof": "M22-M23 milestones extend the M21.23 baseline without reopening completed route shells.",
        },
        {
            "requirement_id": "preserve_do_not_redo_surfaces",
            "status": "completed",
            "evidence": "docs/planning/M22_MISSION_LEDGER.md",
            "proof": "Route shell, local state, paper crypto, provider freshness, secret gate, agent contract, and cleanup surfaces remain protected.",
        },
        {
            "requirement_id": "clean_room_and_source_wall",
            "status": "completed",
            "evidence": "tests/test_clean_room_source_wall.py; GET /api/command-center",
            "proof": "Command Center safety denies installed-source reads and copied branding/runtime assets.",
        },
        {
            "requirement_id": "live_private_payment_exclusion",
            "status": "completed",
            "evidence": "tests/test_m16_live_safety.py; GET /api/live-safety",
            "proof": "Live orders, broker mutation, real balances, margin, leverage, short exposure, derivatives, payment, subscription, and cloud sync stay disabled.",
        },
        {
            "requirement_id": "command_center_supervision",
            "status": "completed",
            "evidence": "GET /api/command-center; frontend CommandCenterPanel",
            "proof": "Active task, route actions, preflight, provider state, recovery queue, risk gates, provenance, and final audit are exposed through stable selectors.",
        },
        {
            "requirement_id": "ai_agent_operability",
            "status": "completed",
            "evidence": "GET /api/agent-contract",
            "proof": (
                f"{_int(route_action_contract.get('route_count'))} routes, "
                f"{_int(route_action_contract.get('action_count'))} actions, and "
                f"{_int(route_action_contract.get('selector_count'))} selectors are machine readable."
            ),
        },
        {
            "requirement_id": "provider_data_strategy",
            "status": "completed",
            "evidence": "GET /api/provider-acquisition-gate",
            "proof": (
                f"{_int(provider_summary.get('candidate_count'))} candidates reviewed, "
                f"{_int(provider_summary.get('approved_next_count'))} approved next, "
                f"resume_state={provider_summary.get('resume_state') or 'unknown'}."
            ),
        },
        {
            "requirement_id": "markets_quote_reference_breadth",
            "status": "completed",
            "evidence": "docs/planning/M23_PROVIDER_QUOTE_BREADTH_CLOSURE.md",
            "proof": (
                f"Quote breadth closure is {quote_closure.get('status') or 'unknown'} with "
                f"{_int(quote_backlog.get('implemented_quote_lane_count'))} quote lanes and "
                f"{_int(quote_backlog.get('blocked_market_data_gate_count'))} blocked official gates."
            ),
        },
        {
            "requirement_id": "backtest_algo_portfolio_depth",
            "status": "completed",
            "evidence": "docs/planning/M23_BACKTEST_RSI_REVERSION.md; docs/planning/M23_PORTFOLIO_EXPOSURE_MAP.md",
            "proof": "Local closed-candle strategies, scan/readiness lineage, reports, exposure maps, and artifact health exist without optimize/live/deploy.",
        },
        {
            "requirement_id": "news_research_artifact_lifecycle",
            "status": "completed",
            "evidence": "docs/planning/M23_NEWS_TOPIC_ENTITY_MAP.md; GET /api/artifact-lifecycle",
            "proof": (
                f"Metadata-only research and artifact supervision cover "
                f"{_int(artifact_summary.get('root_count'))} artifact roots with destructive actions disabled."
            ),
        },
        {
            "requirement_id": "advanced_safe_local_outputs",
            "status": "completed",
            "evidence": "GET /api/advanced-workflows/output-packet",
            "proof": (
                f"{_int(advanced_summary.get('route_count'))} advanced routes expose metadata, IO contracts, and local-output health without runtime execution."
            ),
        },
        {
            "requirement_id": "final_non_live_completion_audit",
            "status": "completed",
            "evidence": FINAL_COMPLETION_AUDIT_PATH,
            "proof": "This read-only audit matrix separates completed current scope from excluded or blocked safety boundaries.",
        },
    ]
    blocked_or_excluded = [
        {
            "item_id": "live_trading_and_brokerage",
            "classification": "excluded_by_goal",
            "reason": "Live trading, real orders, broker/exchange binding, real balances, margin, leverage, shorts, and derivatives are outside this goal.",
        },
        {
            "item_id": "payment_subscription_cr_cloud",
            "classification": "excluded_by_goal",
            "reason": "Payment, subscription, CR/credits, and cloud sync are forbidden by the local no-subscription boundary.",
        },
        {
            "item_id": "destructive_artifact_lifecycle",
            "classification": "blocked_by_safety_contract",
            "reason": "Archive/prune/delete/restore execution requires a separate destructive-action safety contract.",
        },
        {
            "item_id": "external_runtimes_and_managed_llm",
            "classification": "blocked_by_safety_contract",
            "reason": "Notebook kernels, workflow execution, managed LLM calls, deep-agent runs, and external QuantLib runtime are excluded until separately reviewed.",
        },
        {
            "item_id": "fresh_unrestricted_installed_app_observation",
            "classification": "blocked_by_external_account_gates",
            "reason": "Existing sanitized observations are valid workflow evidence; unrestricted account/commercial/security-gated observation remains a stop-gated external step.",
        },
    ]
    return {
        "mode": "read_only_final_non_live_completion_audit",
        "goal_status": "complete_for_current_non_live_scope",
        "current_milestone": current_milestone,
        "audit_path": FINAL_COMPLETION_AUDIT_PATH,
        "requirement_count": len(requirements),
        "completed_count": sum(1 for row in requirements if row["status"] == "completed"),
        "partial_count": 0,
        "unknown_count": 0,
        "blocked_or_excluded_count": len(blocked_or_excluded),
        "requirements": requirements,
        "blocked_or_excluded": blocked_or_excluded,
        "provider_quote_breadth_closure": {
            "status": str(quote_closure.get("status") or ""),
            "implementation_allowed": bool(quote_closure.get("implementation_allowed")),
            "approved_next_count": _int(quote_backlog.get("approved_next_count")),
            "implemented_or_blocked_count": _int(
                quote_backlog.get("implemented_or_blocked_count")
            ),
            "candidate_count": _int(quote_backlog.get("candidate_count")),
            "blocked_gate_ids": _string_list(quote_closure.get("blocked_gate_ids")),
        },
        "next_action_policy": (
            "Do not continue adding product scope after this audit unless a new user goal "
            "opens a reviewed provider-entry gate or a separate safety contract."
        ),
        "safety": {
            "read_only": True,
            "content_read": False,
            "secret_values_returned": False,
            "destructive_actions_enabled": False,
            "live_trading": False,
            "broker_mutation": False,
            "installed_source_read": False,
            "external_network": False,
        },
        "risk_gate_snapshot": {
            "live_mode_enabled": bool(risk_gates.get("live_mode_enabled")),
            "secret_value_reads_enabled": bool(risk_gates.get("secret_value_reads_enabled")),
            "installed_source_read": bool(risk_gates.get("installed_source_read")),
            "runtime_branding_copied": bool(risk_gates.get("runtime_branding_copied")),
        },
    }


def _route_action_contract(agent_contract: dict[str, Any]) -> dict[str, Any]:
    summary = _dict(agent_contract.get("summary"))
    routes = _list(agent_contract.get("routes"))
    actions = _list(agent_contract.get("actions"))
    preflight = _dict(agent_contract.get("preflight"))
    preflight_endpoint = str(
        preflight.get("endpoint") or "/api/agent-actions/{action_id}/preflight"
    )
    action_rows = [
        {
            "action_id": str(action.get("action_id") or ""),
            "route_id": str(action.get("route_id") or ""),
            "label": str(action.get("label") or ""),
            "method": str(action.get("method") or ""),
            "endpoint": str(action.get("endpoint") or ""),
            "safety_class": str(action.get("safety_class") or ""),
            "local_mutation": bool(action.get("local_mutation")),
            "writes_local_artifacts": bool(action.get("writes_local_artifacts")),
            "requires_confirmation": bool(action.get("requires_confirmation")),
            "disabled_by_safety": bool(action.get("disabled_by_safety")),
            "expected_error_codes": _string_list(action.get("expected_error_codes")),
            "preflight_endpoint": preflight_endpoint.replace(
                "{action_id}", str(action.get("action_id") or "")
            ),
        }
        for action in actions
        if isinstance(action, dict)
    ]
    disabled_actions = [
        {
            "action_id": str(action.get("action_id") or ""),
            "route_id": str(action.get("route_id") or ""),
            "endpoint": str(action.get("endpoint") or ""),
            "safety_class": str(action.get("safety_class") or ""),
            "expected_error_codes": _string_list(action.get("expected_error_codes")),
        }
        for action in actions
        if isinstance(action, dict) and bool(action.get("disabled_by_safety"))
    ]
    return {
        "route_count": _int(summary.get("route_count")),
        "action_count": _int(summary.get("action_count")),
        "selector_count": _int(summary.get("selector_count")),
        "local_mutation_count": sum(1 for action in action_rows if action["local_mutation"]),
        "artifact_write_count": sum(
            1 for action in action_rows if action["writes_local_artifacts"]
        ),
        "confirmation_required_count": sum(
            1 for action in action_rows if action["requires_confirmation"]
        ),
        "actions": action_rows,
        "routes": [
            {
                "route_id": str(route.get("route_id") or ""),
                "path": str(route.get("path") or ""),
                "primary_endpoint": str(route.get("primary_endpoint") or ""),
                "workspace_test_id": str(route.get("workspace_test_id") or ""),
                "recommended_actions": _string_list(route.get("recommended_actions")),
                "disabled_actions": _string_list(route.get("disabled_actions")),
            }
            for route in routes
            if isinstance(route, dict)
        ],
        "disabled_actions": disabled_actions,
        "preflight": {
            "mode": str(preflight.get("mode") or "read_only_action_preflight"),
            "method": str(preflight.get("method") or "GET"),
            "endpoint": preflight_endpoint,
            "action_executed": bool(preflight.get("action_executed")),
            "stop_gates": _string_list(preflight.get("stop_gates")),
        },
        "preflight_status_matrix": _preflight_status_matrix(
            action_rows,
            preflight_endpoint,
        ),
    }


def _preflight_status_matrix(
    action_rows: list[dict[str, Any]],
    preflight_endpoint: str,
) -> dict[str, Any]:
    rows = [_preflight_status_row(action) for action in action_rows]
    return {
        "mode": "read_only_command_center_preflight_matrix",
        "endpoint": "/api/command-center/preflight-matrix",
        "preflight_endpoint_template": preflight_endpoint,
        "summary": {
            "row_count": len(rows),
            "ready_count": sum(1 for row in rows if row["status"] == "ready"),
            "requires_confirmation_count": sum(
                1 for row in rows if row["status"] == "requires_confirmation"
            ),
            "disabled_by_safety_count": sum(
                1 for row in rows if row["status"] == "disabled_by_safety"
            ),
            "allowed_to_attempt_count": sum(
                1 for row in rows if row["allowed_to_attempt"]
            ),
            "local_mutation_count": sum(1 for row in rows if row["local_mutation"]),
            "artifact_write_count": sum(
                1 for row in rows if row["writes_local_artifacts"]
            ),
        },
        "rows": rows,
        "safety": {
            "read_only": True,
            "action_executed": False,
            "local_mutation_performed": False,
            "external_network": False,
            "secret_values_returned": False,
            "destructive_actions_enabled": False,
            "live_trading": False,
            "broker_mutation": False,
            "installed_source_read": False,
        },
    }


def _preflight_status_row(action: dict[str, Any]) -> dict[str, Any]:
    disabled_by_safety = bool(action.get("disabled_by_safety"))
    requires_confirmation = bool(action.get("requires_confirmation"))
    if disabled_by_safety:
        status = "disabled_by_safety"
        reason = "Action is present but blocked by the safety contract."
    elif requires_confirmation:
        status = "requires_confirmation"
        reason = "Action is present but requires explicit local confirmation before use."
    else:
        status = "ready"
        reason = "Action is listed as available by the AI Agent contract."
    allowed_to_attempt = status == "ready"
    return {
        "action_id": str(action.get("action_id") or ""),
        "route_id": str(action.get("route_id") or ""),
        "status": status,
        "allowed_to_attempt": allowed_to_attempt,
        "allowed_without_confirmation": allowed_to_attempt,
        "reason": reason,
        "method": str(action.get("method") or ""),
        "endpoint": str(action.get("endpoint") or ""),
        "preflight_endpoint": str(action.get("preflight_endpoint") or ""),
        "safety_class": str(action.get("safety_class") or ""),
        "local_mutation": bool(action.get("local_mutation")),
        "writes_local_artifacts": bool(action.get("writes_local_artifacts")),
        "requires_confirmation": requires_confirmation,
        "disabled_by_safety": disabled_by_safety,
        "expected_error_codes": _string_list(action.get("expected_error_codes")),
    }


def _provider_source_state(
    governance: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, Any]:
    provider_setup = _list(governance.get("provider_setup"))
    cache_controls = _list(governance.get("cache_controls"))
    return {
        "provider_count": _int(summary.get("provider_count")),
        "active_provider_count": _int(summary.get("active_provider_count")),
        "stale_provider_count": _int(summary.get("stale_provider_count")),
        "key_required_count": _int(summary.get("key_required_count")),
        "plan_required_count": _int(summary.get("plan_required_count")),
        "disabled_by_safety_count": _int(summary.get("disabled_by_safety_count")),
        "cache_count": _int(summary.get("cache_count")),
        "providers": [
            {
                "provider_id": str(provider.get("provider_id") or ""),
                "auth_mode": str(provider.get("auth_mode") or ""),
                "state": str(provider.get("state") or ""),
                "setup_state": str(provider.get("setup_state") or ""),
                "cache_path": str(provider.get("cache_path") or ""),
                "docs_checked_at": str(provider.get("docs_checked_at") or ""),
                "form_enabled": bool(provider.get("form_enabled")),
                "forbidden": bool(provider.get("forbidden")),
            }
            for provider in provider_setup
            if isinstance(provider, dict)
        ],
        "cache_controls": [
            {
                "provider_id": str(cache.get("provider_id") or ""),
                "cache_path": str(cache.get("cache_path") or cache.get("path") or ""),
                "state": str(cache.get("state") or ""),
                "refresh_action": str(cache.get("refresh_action") or ""),
            }
            for cache in cache_controls
            if isinstance(cache, dict)
        ],
    }


def _artifact_recovery(
    artifact_lifecycle: dict[str, Any],
    provider_refresh: dict[str, Any],
) -> dict[str, Any]:
    lifecycle_summary = _dict(artifact_lifecycle.get("summary"))
    refresh_summary = _dict(provider_refresh.get("summary"))
    refresh_runs = _list(provider_refresh.get("runs"))
    root_health_matrix = _artifact_root_health_matrix(artifact_lifecycle.get("roots"))
    return {
        "artifact_root_count": _int(lifecycle_summary.get("root_count")),
        "active_artifact_root_count": _int(lifecycle_summary.get("active_root_count")),
        "empty_artifact_root_count": _int(lifecycle_summary.get("empty_root_count")),
        "missing_artifact_root_count": _int(lifecycle_summary.get("missing_root_count")),
        "blocked_artifact_root_count": _int(lifecycle_summary.get("blocked_root_count")),
        "supervision_ready_root_count": _int(
            lifecycle_summary.get("supervision_ready_root_count")
        ),
        "artifact_file_count": _int(lifecycle_summary.get("file_count")),
        "archive_plan_run_count": _int(lifecycle_summary.get("archive_plan_run_count")),
        "provider_refresh_recovery_recommended_count": _int(
            refresh_summary.get("recovery_recommended_count")
        ),
        "artifact_root_health_matrix": root_health_matrix,
        "artifact_actions": _dict(artifact_lifecycle.get("actions")),
        "provider_refresh_actions": _dict(provider_refresh.get("actions")),
        "recovery_queue": [
            {
                "run_id": str(run.get("run_id") or ""),
                "status": str(run.get("status") or ""),
                "lifecycle_state": str(run.get("lifecycle_state") or ""),
                "recommended_action": str(_dict(run.get("recovery")).get("recommended_action") or ""),
                "artifact_dir": str(run.get("artifact_dir") or ""),
            }
            for run in refresh_runs
            if isinstance(run, dict)
            and str(_dict(run.get("recovery")).get("recommended_action") or "")
        ],
    }


def _artifact_root_health_matrix(value: Any) -> dict[str, Any]:
    rows = [
        _artifact_root_health_row(row)
        for row in _list(value)
        if isinstance(row, dict)
    ]
    return {
        "mode": "metadata_only_artifact_root_supervision",
        "summary": {
            "root_count": len(rows),
            "active_root_count": sum(1 for row in rows if row["state"] == "active"),
            "empty_root_count": sum(1 for row in rows if row["state"] == "empty"),
            "missing_root_count": sum(1 for row in rows if row["state"] == "missing"),
            "blocked_root_count": sum(
                1 for row in rows if str(row["state"]).startswith("blocked")
            ),
            "supervision_ready_count": sum(
                1 for row in rows if bool(row["supervision_ready"])
            ),
            "destructive_action_count": sum(
                1 for row in rows if bool(row["destructive_actions_enabled"])
            ),
        },
        "roots": rows,
    }


def _artifact_root_health_row(row: dict[str, Any]) -> dict[str, Any]:
    state = str(row.get("state") or "")
    supervision_ready = bool(row.get("supervision_ready"))
    if "supervision_ready" not in row:
        supervision_ready = (
            state == "active"
            and bool(row.get("stays_inside_repo"))
            and _int(row.get("file_count")) > 0
            and not bool(row.get("destructive_actions_enabled"))
        )
    return {
        "root_id": str(row.get("root_id") or ""),
        "label": str(row.get("label") or ""),
        "path": str(row.get("path") or ""),
        "routes": _string_list(row.get("routes")),
        "state": state,
        "lifecycle_state": str(row.get("lifecycle_state") or ""),
        "file_count": _int(row.get("file_count")),
        "total_bytes": _int(row.get("total_bytes")),
        "newest_updated_at": str(row.get("newest_updated_at") or ""),
        "latest_artifact_path": str(row.get("latest_artifact_path") or ""),
        "supervision_ready": supervision_ready,
        "safe_actions": _string_list(row.get("safe_actions")),
        "recovery_hint": str(row.get("recovery_hint") or ""),
        "research_lineage_supported": bool(row.get("research_lineage_supported")),
        "destructive_actions_enabled": bool(row.get("destructive_actions_enabled")),
    }


def _risk_gates(
    safety_gates: dict[str, Any],
    local_secret_status: dict[str, Any],
    source_wall: dict[str, Any],
) -> dict[str, Any]:
    return {
        "live_safety_status": str(safety_gates.get("status") or "unknown"),
        "live_mode_enabled": bool(safety_gates.get("live_mode_enabled")),
        "paper_mode_enabled": bool(safety_gates.get("paper_mode_enabled")),
        "forbidden_capabilities": _dict(safety_gates.get("forbidden_capabilities")),
        "disabled_action_count": _int(safety_gates.get("disabled_action_count")),
        "secret_writes_enabled": bool(local_secret_status.get("writes_enabled")),
        "secret_value_reads_enabled": bool(local_secret_status.get("api_secret_value_reads_enabled")),
        "stored_provider_count": _int(local_secret_status.get("stored_provider_count")),
        "source_wall_state": str(source_wall.get("state") or "unknown"),
        "installed_source_read": bool(source_wall.get("installed_source_read")),
        "runtime_branding_copied": bool(source_wall.get("runtime_branding_copied")),
    }


def _advanced_output_io_contract(value: Any) -> dict[str, Any]:
    contract = _dict(value)
    latest_paths = _dict(contract.get("latest_output_paths"))
    safe_action = _dict(contract.get("safe_action"))
    safety = _dict(contract.get("safety"))
    return {
        "contract_id": str(contract.get("contract_id") or ""),
        "input_contract": _string_list(contract.get("input_contract")),
        "output_contract": _string_list(contract.get("output_contract")),
        "error_contract": _string_list(contract.get("error_contract")),
        "artifact_root": str(contract.get("artifact_root") or ""),
        "latest_output_paths": {
            "latest_artifact": str(latest_paths.get("latest_artifact") or ""),
            "manifest": str(latest_paths.get("manifest") or ""),
            "report": str(latest_paths.get("report") or ""),
            "error_log": str(latest_paths.get("error_log") or ""),
        },
        "safe_action": {
            "action_id": str(safe_action.get("action_id") or ""),
            "endpoint": str(safe_action.get("endpoint") or ""),
            "description": str(safe_action.get("description") or ""),
        },
        "blocked_runtime_actions": _string_list(contract.get("blocked_runtime_actions")),
        "read_mode": str(contract.get("read_mode") or "metadata_only"),
        "safety": {
            "metadata_only": bool(safety.get("metadata_only")),
            "content_read": bool(safety.get("content_read")),
            "execution_enabled": bool(safety.get("execution_enabled")),
            "external_network": bool(safety.get("external_network")),
            "credentials_required": bool(safety.get("credentials_required")),
            "broker_mutation": bool(safety.get("broker_mutation")),
            "live_trading": bool(safety.get("live_trading")),
        },
    }


def _provenance_evidence() -> dict[str, Any]:
    return {
        "mission_ledger": "docs/planning/M22_MISSION_LEDGER.md",
        "project_state": "PROJECT_STATE.md",
        "route_gap_report": "docs/planning/M21_ROUTE_GAP_REPORT.md",
        "provider_research_matrix": "docs/planning/M21_PROVIDER_RESEARCH_MATRIX.md",
        "observation_protocol": "docs/planning/M21_OBSERVATION_AND_COMPARISON_PROTOCOL.md",
        "karpathy_cleanup": "docs/planning/M21_KARPATHY_CLEANUP.md",
        "final_non_live_parity_audit": "docs/planning/M22_FINAL_NON_LIVE_PARITY_AUDIT.md",
        "final_non_live_completion_audit": FINAL_COMPLETION_AUDIT_PATH,
        "current_milestone": CURRENT_MILESTONE_PATH,
    }


def _selectors() -> dict[str, str]:
    return {
        "workspace": "[data-testid='workspace-command-center']",
        "activity": "[data-testid='command-center-activity']",
        "mission_ledger": "[data-testid='command-center-mission-ledger']",
        "final_goal_audit": "[data-testid='command-center-final-goal-audit']",
        "activity_timeline": "[data-testid='command-center-activity-timeline']",
        "route_action_contract": "[data-testid='command-center-route-action-contract']",
        "provider_source_state": "[data-testid='command-center-provider-source-state']",
        "provider_acquisition_gate": "[data-testid='command-center-provider-acquisition-gate']",
        "artifact_recovery": "[data-testid='command-center-artifact-recovery']",
        "advanced_outputs": "[data-testid='command-center-advanced-outputs']",
        "agent_activity": "[data-testid='command-center-agent-activity']",
        "active_task": "[data-testid='command-center-active-task']",
        "recovery_queue": "[data-testid='command-center-recovery-queue']",
        "preflight_status_matrix": "[data-testid='command-center-preflight-status-matrix']",
        "risk_gates": "[data-testid='command-center-risk-gates']",
        "provenance_evidence": "[data-testid='command-center-provenance-evidence']",
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _active_task(value: Any) -> dict[str, Any]:
    task = _dict(value)
    return {
        "is_active": bool(task.get("is_active")),
        "state": str(task.get("state") or "none"),
        "route_id": str(task.get("route_id") or ""),
        "action_id": str(task.get("action_id") or ""),
        "summary": str(task.get("summary") or ""),
        "artifact_path": str(task.get("artifact_path") or ""),
        "method": str(task.get("method") or ""),
        "endpoint": str(task.get("endpoint") or ""),
        "safety_class": str(task.get("safety_class") or ""),
        "event_id": str(task.get("event_id") or ""),
        "created_at": str(task.get("created_at") or ""),
        "request_body_logged": bool(task.get("request_body_logged")),
        "action_executed_by_journal": bool(task.get("action_executed_by_journal")),
        "destructive_actions_enabled": bool(task.get("destructive_actions_enabled")),
        "recovery_hint": str(task.get("recovery_hint") or "No active metadata task is currently declared."),
    }


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_list(value: Any) -> list[str]:
    return [str(item) for item in _list(value)]


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _latest_artifact_path(route: dict[str, Any]) -> str:
    artifacts = _list(route.get("latest_artifacts"))
    for artifact in artifacts:
        if isinstance(artifact, dict):
            path = str(artifact.get("path") or "")
            if path:
                return path
    return ""


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
