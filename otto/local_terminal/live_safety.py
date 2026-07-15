"""Live trading safety contract surface with no live execution path."""

from __future__ import annotations

from typing import Any


LIVE_SAFETY_STATUS = "disabled_no_safety_contract"
LIVE_SAFETY_VERSION = "m16-contract-draft"

REQUIRED_GATES: tuple[dict[str, str | bool], ...] = (
    {
        "gate_id": "local_secret_storage",
        "label": "Local secret storage design",
        "state": "missing",
        "required": True,
        "evidence": "No private API key storage is implemented.",
    },
    {
        "gate_id": "explicit_live_mode_opt_in",
        "label": "Explicit live-mode opt-in",
        "state": "missing",
        "required": True,
        "evidence": "Live mode cannot be enabled from UI or API.",
    },
    {
        "gate_id": "confirmation_gates",
        "label": "Confirmation gates",
        "state": "missing",
        "required": True,
        "evidence": "No live order confirmation workflow exists.",
    },
    {
        "gate_id": "balance_read_confirmation_gate",
        "label": "Balance read confirmation gate",
        "state": "missing",
        "required": True,
        "evidence": "No real balance read confirmation workflow exists.",
    },
    {
        "gate_id": "audit_logs",
        "label": "Audit and reject logs",
        "state": "missing",
        "required": True,
        "evidence": "No live audit log writer exists.",
    },
    {
        "gate_id": "kill_switch",
        "label": "Kill switch behavior",
        "state": "missing",
        "required": True,
        "evidence": "Default kill switch state is locked/engaged.",
    },
    {
        "gate_id": "paper_live_isolation",
        "label": "Paper/live environment isolation",
        "state": "missing",
        "required": True,
        "evidence": "Only paper broker state exists.",
    },
    {
        "gate_id": "static_reachability",
        "label": "Static reachability checks",
        "state": "missing",
        "required": True,
        "evidence": "Future live code must prove no bypass paths.",
    },
    {
        "gate_id": "security_review",
        "label": "Security review approval",
        "state": "missing",
        "required": True,
        "evidence": "No live-mode security review exists.",
    },
    {
        "gate_id": "unit_integration_e2e_coverage",
        "label": "Unit, integration, and E2E coverage",
        "state": "missing",
        "required": True,
        "evidence": "Live-mode test coverage is not implemented.",
    },
    {
        "gate_id": "code_review_security_review",
        "label": "Code review and security review approval",
        "state": "missing",
        "required": True,
        "evidence": "No live-mode code review and security review approvals exist.",
    },
)

FORBIDDEN_CAPABILITIES: dict[str, bool] = {
    "reachable_live_execution": False,
    "real_orders": False,
    "private_api_keys": False,
    "real_balance_reads": False,
    "margin": False,
    "leverage": False,
    "short": False,
    "derivatives_execution": False,
    "broker_mutation": False,
    "external_network_required": False,
}

DISABLED_ACTIONS: tuple[dict[str, str], ...] = (
    {
        "action_id": "live_opt_in",
        "label": "Live Opt-In",
        "reason": "Explicit live-mode opt-in is unavailable until all safety gates pass.",
    },
    {
        "action_id": "store_private_api_key",
        "label": "Store Private API Key",
        "reason": "Local secret storage design is not implemented.",
    },
    {
        "action_id": "read_real_balance",
        "label": "Read Real Balance",
        "reason": "Real balance reads are blocked until paper/live isolation exists.",
    },
    {
        "action_id": "submit_real_order",
        "label": "Submit Real Order",
        "reason": "Real order submission is blocked until confirmations, audit logs, and kill switch exist.",
    },
    {
        "action_id": "enable_margin",
        "label": "Enable Margin",
        "reason": "Margin remains prohibited until separately authorized by live safety review.",
    },
    {
        "action_id": "enable_leverage",
        "label": "Enable Leverage",
        "reason": "Leverage remains prohibited until separately authorized by live safety review.",
    },
    {
        "action_id": "enable_short",
        "label": "Enable Short",
        "reason": "Short exposure remains prohibited until separately authorized by live safety review.",
    },
    {
        "action_id": "execute_derivatives",
        "label": "Execute Derivatives",
        "reason": "Derivatives execution remains prohibited until separately authorized by live safety review.",
    },
)

DISABLED_ENDPOINTS: tuple[dict[str, str], ...] = (
    {"endpoint": "/api/live-safety/opt-in", "action_id": "live_opt_in"},
    {"endpoint": "/api/live-safety/store-secret", "action_id": "store_private_api_key"},
    {"endpoint": "/api/live-safety/read-balance", "action_id": "read_real_balance"},
    {"endpoint": "/api/live-safety/submit-order", "action_id": "submit_real_order"},
    {"endpoint": "/api/live-safety/enable-margin", "action_id": "enable_margin"},
    {"endpoint": "/api/live-safety/enable-leverage", "action_id": "enable_leverage"},
    {"endpoint": "/api/live-safety/enable-short", "action_id": "enable_short"},
    {"endpoint": "/api/live-safety/execute-derivatives", "action_id": "execute_derivatives"},
)


def live_safety_payload() -> dict[str, Any]:
    return {
        "version": LIVE_SAFETY_VERSION,
        "status": LIVE_SAFETY_STATUS,
        "contract_reviewed": False,
        "security_reviewed": False,
        "live_mode_enabled": False,
        "paper_mode_enabled": True,
        "allowed_today": [
            "public_read_only_market_data",
            "paper_broker_orders",
            "local_backtest_artifacts",
            "local_journal_and_diagnostics",
        ],
        "required_gates": [dict(gate) for gate in REQUIRED_GATES],
        "forbidden_capabilities": dict(FORBIDDEN_CAPABILITIES),
        "paper_live_isolation": {
            "paper_state_path": "artifacts/paper/paper_state.json",
            "live_state_path": None,
            "shared_order_router": False,
            "paper_can_submit_live_order": False,
            "live_can_mutate_paper_ledger": False,
        },
        "secret_storage": {
            "state": "not_configured",
            "writes_enabled": False,
            "repo_plaintext_allowed": False,
            "private_api_required": False,
        },
        "audit_policy": {
            "state": "not_configured",
            "live_order_attempts_logged": False,
            "rejects_logged": False,
            "redaction_required": True,
        },
        "kill_switch": {
            "state": "engaged",
            "live_mode_locked": True,
            "default_action": "reject_live_request",
        },
        "disabled_actions": [dict(action) for action in DISABLED_ACTIONS],
    }


def disabled_live_action_response(action_id: str) -> dict[str, Any]:
    action = next(
        (item for item in DISABLED_ACTIONS if item["action_id"] == action_id),
        {
            "action_id": action_id,
            "label": action_id.replace("_", " ").title(),
            "reason": "Live trading is disabled until the safety contract passes review.",
        },
    )
    return {
        "action": action,
        "status": LIVE_SAFETY_STATUS,
        "reason": action["reason"],
        "safety": live_safety_payload(),
    }
