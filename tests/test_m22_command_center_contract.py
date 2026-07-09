from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.command_center import command_center_payload
from src.local_terminal.governance import governance_payload
from src.local_terminal.storage import LocalStateStore


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_command_center_payload_composes_existing_supervision_state(tmp_path: Path) -> None:
    store = LocalStateStore(root=tmp_path)
    governance = governance_payload(store, version="test")

    payload = command_center_payload(governance)

    assert payload["mode"] == "read_only_ai_supervision_contract"
    assert payload["version"] == "m22-command-center-v1"
    assert payload["current_milestone"] == "M23.68 Final non-live completion audit"
    assert payload["mission_ledger"]["mode"] == "read_only_mission_ledger_snapshot"
    assert payload["mission_ledger"]["goal_status"] == (
        "complete_for_current_non_live_scope"
    )
    assert payload["mission_ledger"]["ledger_path"] == (
        "docs/planning/M22_MISSION_LEDGER.md"
    )
    assert payload["mission_ledger"]["latest_milestone_path"] == (
        "docs/planning/M23_FINAL_NON_LIVE_COMPLETION_AUDIT.md"
    )
    assert payload["mission_ledger"]["final_audit_path"] == (
        "docs/planning/M23_FINAL_NON_LIVE_COMPLETION_AUDIT.md"
    )
    assert payload["mission_ledger"]["do_not_redo_count"] == len(
        payload["mission_ledger"]["do_not_redo"]
    )
    assert payload["mission_ledger"]["partial_gap_count"] == len(
        payload["mission_ledger"]["partial_gaps"]
    )
    assert payload["mission_ledger"]["blocked_gate_count"] == len(
        payload["mission_ledger"]["blocked_gates"]
    )
    assert payload["mission_ledger"]["safety"]["destructive_actions_enabled"] is False
    assert payload["activity"]["milestone_status"] == "contract_available"
    assert [row["event_id"] for row in payload["activity_timeline"]] == [
        "current_milestone",
        "mission_ledger",
        "final_goal_audit",
        "route_action_contract",
        "provider_source_state",
        "provider_acquisition_gate",
        "artifact_recovery",
        "advanced_outputs",
        "agent_activity",
        "recovery_queue",
        "risk_gates",
    ]
    assert payload["activity_timeline"][0]["evidence"] == (
        "docs/planning/M23_FINAL_NON_LIVE_COMPLETION_AUDIT.md"
    )
    assert payload["activity_timeline"][1]["evidence"] == (
        "docs/planning/M22_MISSION_LEDGER.md"
    )
    assert payload["activity_timeline"][-1]["recovery_hint"] == (
        "Stop for live/private/account/payment/destructive gates."
    )
    assert payload["final_goal_audit"]["mode"] == (
        "read_only_final_non_live_completion_audit"
    )
    assert payload["final_goal_audit"]["goal_status"] == (
        "complete_for_current_non_live_scope"
    )
    assert payload["final_goal_audit"]["audit_path"] == (
        "docs/planning/M23_FINAL_NON_LIVE_COMPLETION_AUDIT.md"
    )
    assert payload["final_goal_audit"]["requirement_count"] == 12
    assert payload["final_goal_audit"]["completed_count"] == 12
    assert payload["final_goal_audit"]["partial_count"] == 0
    assert payload["final_goal_audit"]["unknown_count"] == 0
    assert payload["final_goal_audit"]["blocked_or_excluded_count"] == 5
    requirement_by_id = {
        row["requirement_id"]: row for row in payload["final_goal_audit"]["requirements"]
    }
    assert requirement_by_id["provider_data_strategy"]["status"] == "completed"
    assert requirement_by_id["markets_quote_reference_breadth"]["status"] == "completed"
    blocked_audit_by_id = {
        row["item_id"]: row
        for row in payload["final_goal_audit"]["blocked_or_excluded"]
    }
    assert blocked_audit_by_id["live_trading_and_brokerage"]["classification"] == (
        "excluded_by_goal"
    )
    assert blocked_audit_by_id["fresh_unrestricted_installed_app_observation"][
        "classification"
    ] == "blocked_by_external_account_gates"
    assert payload["final_goal_audit"]["provider_quote_breadth_closure"][
        "approved_next_count"
    ] == 0
    assert payload["final_goal_audit"]["safety"]["live_trading"] is False
    assert payload["route_action_contract"]["route_count"] == 16
    assert payload["route_action_contract"]["actions"]
    assert payload["route_action_contract"]["artifact_write_count"] > 0
    assert payload["route_action_contract"]["local_mutation_count"] > 0
    assert payload["route_action_contract"]["confirmation_required_count"] >= 0
    action_by_id = {
        action["action_id"]: action
        for action in payload["route_action_contract"]["actions"]
    }
    assert action_by_id["portfolio_report"]["route_id"] == "portfolio"
    assert action_by_id["portfolio_report"]["writes_local_artifacts"] is True
    assert action_by_id["portfolio_report"]["preflight_endpoint"] == (
        "/api/agent-actions/portfolio_report/preflight"
    )
    assert action_by_id["portfolio_report_health"]["endpoint"] == (
        "/api/portfolio/report-health"
    )
    assert action_by_id["portfolio_report_health"]["writes_local_artifacts"] is False
    assert action_by_id["ai_chat_session_health"]["endpoint"] == (
        "/api/ai-chat/session-health"
    )
    assert action_by_id["ai_chat_session_health"]["writes_local_artifacts"] is False
    assert action_by_id["ai_chat_session_health"]["safety_class"] == (
        "metadata_only_ai_chat_session_health"
    )
    assert action_by_id["nodes_workflow_health"]["endpoint"] == (
        "/api/nodes/workflow-health"
    )
    assert action_by_id["nodes_workflow_health"]["writes_local_artifacts"] is False
    assert action_by_id["nodes_workflow_health"]["safety_class"] == (
        "metadata_only_nodes_workflow_health"
    )
    assert action_by_id["code_analysis_health"]["endpoint"] == (
        "/api/code/analysis-health"
    )
    assert action_by_id["code_analysis_health"]["writes_local_artifacts"] is False
    assert action_by_id["code_analysis_health"]["safety_class"] == (
        "metadata_only_code_analysis_health"
    )
    assert action_by_id["quant_lab_preview_health"]["endpoint"] == (
        "/api/quant-lab/preview-health"
    )
    assert action_by_id["quant_lab_preview_health"]["writes_local_artifacts"] is False
    assert action_by_id["quant_lab_preview_health"]["safety_class"] == (
        "metadata_only_quant_lab_preview_health"
    )
    assert action_by_id["quantlib_calculation_health"]["endpoint"] == (
        "/api/quantlib/calculation-health"
    )
    assert action_by_id["quantlib_calculation_health"]["writes_local_artifacts"] is False
    assert action_by_id["quantlib_calculation_health"]["safety_class"] == (
        "metadata_only_quantlib_calculation_health"
    )
    assert action_by_id["provider_acquisition_gate_inspect"]["method"] == "GET"
    assert action_by_id["markets_quote_snapshot_board"]["endpoint"] == (
        "/api/markets/quote-snapshot-board"
    )
    assert action_by_id["markets_quote_snapshot_board"]["preflight_endpoint"] == (
        "/api/agent-actions/markets_quote_snapshot_board/preflight"
    )
    assert action_by_id["markets_quote_snapshot_board"]["writes_local_artifacts"] is False
    assert action_by_id["markets_openfigi_mapping_refresh"]["endpoint"] == (
        "/api/markets/openfigi/mapping/refresh"
    )
    assert action_by_id["markets_openfigi_mapping_refresh"]["safety_class"] == (
        "public_read_only_reference_data"
    )
    assert action_by_id["backtest_artifact_health"]["endpoint"] == (
        "/api/backtest/artifact-health"
    )
    assert action_by_id["backtest_artifact_health"]["writes_local_artifacts"] is False
    assert action_by_id["command_center_preflight_matrix"]["endpoint"] == (
        "/api/command-center/preflight-matrix"
    )
    assert action_by_id["command_center_preflight_matrix"]["writes_local_artifacts"] is False
    assert payload["route_action_contract"]["disabled_actions"]
    matrix = payload["route_action_contract"]["preflight_status_matrix"]
    assert matrix["mode"] == "read_only_command_center_preflight_matrix"
    assert matrix["endpoint"] == "/api/command-center/preflight-matrix"
    assert matrix["summary"]["row_count"] == payload["route_action_contract"]["action_count"]
    assert matrix["summary"]["ready_count"] > 0
    assert matrix["summary"]["disabled_by_safety_count"] == len(
        payload["route_action_contract"]["disabled_actions"]
    )
    matrix_by_id = {row["action_id"]: row for row in matrix["rows"]}
    assert matrix_by_id["markets_quote_snapshot_board"]["status"] == "ready"
    assert matrix_by_id["ai_chat_session_health"]["status"] == "ready"
    assert matrix_by_id["nodes_workflow_health"]["status"] == "ready"
    assert matrix_by_id["code_analysis_health"]["status"] == "ready"
    assert matrix_by_id["quant_lab_preview_health"]["status"] == "ready"
    assert matrix_by_id["quantlib_calculation_health"]["status"] == "ready"
    assert matrix_by_id["code_run_disabled"]["status"] == "disabled_by_safety"
    assert matrix_by_id["store_optional_data_provider_secret"]["status"] == (
        "requires_confirmation"
    )
    assert matrix_by_id["command_center_preflight_matrix"]["allowed_to_attempt"] is True
    assert matrix["safety"]["action_executed"] is False
    assert matrix["safety"]["secret_values_returned"] is False
    assert payload["provider_source_state"]["provider_count"] >= 1
    assert any(
        row["cache_path"] for row in payload["provider_source_state"]["cache_controls"]
    )
    assert payload["provider_acquisition_gate"]["summary"]["resume_state"] == (
        "backlog_exhausted_needs_research"
    )
    assert payload["provider_acquisition_gate"]["summary"]["approved_next_count"] == 0
    assert payload["provider_acquisition_gate"]["summary"]["implementation_allowed"] is False
    assert payload["provider_acquisition_gate"]["quote_breadth_closure"]["mode"] == (
        "non_live_quote_breadth_closure_v1"
    )
    assert payload["provider_acquisition_gate"]["quote_breadth_closure"][
        "implementation_allowed"
    ] is False
    assert payload["provider_acquisition_gate"]["quote_breadth_closure"][
        "provider_backlog"
    ]["candidate_count"] == 21
    assert "yahoo_finance_market_data_gate" in payload["provider_acquisition_gate"][
        "quote_breadth_closure"
    ]["blocked_gate_ids"]
    candidate_by_id = {
        candidate["candidate_id"]: candidate
        for candidate in payload["provider_acquisition_gate"]["candidates"]
    }
    assert candidate_by_id["iex_tops_market_data_gate"]["status"] == (
        "blocked_official_terms"
    )
    assert candidate_by_id["iex_tops_market_data_gate"]["auth_mode"] == (
        "subscriber_agreement_required"
    )
    assert candidate_by_id["cboe_delayed_quotes_gate"]["quote_semantics"] == (
        "quote_blocked_by_terms"
    )
    assert candidate_by_id["nasdaq_data_link_dataset_gate"]["status"] == (
        "blocked_dataset_specific_gate"
    )
    assert candidate_by_id["nasdaq_data_link_dataset_gate"]["auth_mode"] == (
        "account_or_dataset_subscription_required"
    )
    assert candidate_by_id["nasdaq_data_link_dataset_gate"]["quote_semantics"] == (
        "dataset_specific_not_approved"
    )
    assert candidate_by_id["jpx_jquants_market_data_gate"]["status"] == (
        "blocked_account_plan_gate"
    )
    assert candidate_by_id["jpx_jquants_market_data_gate"]["auth_mode"] == (
        "api_key_or_plan_required"
    )
    assert candidate_by_id["jpx_jquants_market_data_gate"]["quote_semantics"] == (
        "quote_blocked_by_account_plan"
    )
    assert "live_order" in payload["provider_acquisition_gate"]["stop_gates"]
    assert payload["provider_acquisition_gate"]["resume_contract"]["next_safe_step"] == (
        "Run a new provider-entry research gate before implementation."
    )
    assert payload["artifact_recovery"]["artifact_root_count"] >= 15
    assert payload["artifact_recovery"]["artifact_root_health_matrix"]["mode"] == (
        "metadata_only_artifact_root_supervision"
    )
    assert payload["artifact_recovery"]["artifact_root_health_matrix"]["summary"][
        "root_count"
    ] == payload["artifact_recovery"]["artifact_root_count"]
    assert payload["artifact_recovery"]["artifact_root_health_matrix"]["summary"][
        "destructive_action_count"
    ] == 0
    assert "latest_artifact_path" in payload["artifact_recovery"][
        "artifact_root_health_matrix"
    ]["roots"][0]
    assert "supervision_ready" in payload["artifact_recovery"][
        "artifact_root_health_matrix"
    ]["roots"][0]
    assert "recovery_queue" in payload["artifact_recovery"]
    assert payload["advanced_outputs"]["mode"] == "not_loaded"
    assert payload["advanced_outputs"]["summary"]["route_count"] == 0
    assert payload["agent_activity"]["mode"] == "not_loaded"
    assert payload["agent_activity"]["summary"] == {}
    assert payload["agent_activity"]["active_task"]["is_active"] is False
    assert payload["active_task"]["state"] == "none"
    assert payload["active_task"]["request_body_logged"] is False
    assert payload["active_task"]["action_executed_by_journal"] is False
    assert payload["active_task"]["destructive_actions_enabled"] is False
    assert payload["recovery_queue"]["mode"] == "read_only_recovery_queue"
    assert payload["recovery_queue"]["summary"]["item_count"] == 0
    assert payload["recovery_queue"]["safety"]["destructive_actions_enabled"] is False
    assert payload["risk_gates"]["live_mode_enabled"] is False
    assert payload["risk_gates"]["secret_value_reads_enabled"] is False
    assert payload["provenance_evidence"]["mission_ledger"] == (
        "docs/planning/M22_MISSION_LEDGER.md"
    )
    assert payload["provenance_evidence"]["final_non_live_parity_audit"] == (
        "docs/planning/M22_FINAL_NON_LIVE_PARITY_AUDIT.md"
    )
    assert payload["provenance_evidence"]["final_non_live_completion_audit"] == (
        "docs/planning/M23_FINAL_NON_LIVE_COMPLETION_AUDIT.md"
    )
    assert payload["provenance_evidence"]["current_milestone"] == (
        "docs/planning/M23_FINAL_NON_LIVE_COMPLETION_AUDIT.md"
    )
    assert payload["route_action_contract"]["preflight"]["endpoint"] == (
        "/api/agent-actions/{action_id}/preflight"
    )
    assert payload["route_action_contract"]["preflight"]["action_executed"] is False
    assert "live_order" in payload["route_action_contract"]["preflight"]["stop_gates"]
    assert payload["route_action_contract"]["preflight_status_matrix"]["safety"][
        "local_mutation_performed"
    ] is False
    assert payload["selectors"]["workspace"] == "[data-testid='workspace-command-center']"
    assert payload["selectors"]["mission_ledger"] == (
        "[data-testid='command-center-mission-ledger']"
    )
    assert payload["selectors"]["final_goal_audit"] == (
        "[data-testid='command-center-final-goal-audit']"
    )
    assert payload["selectors"]["activity_timeline"] == (
        "[data-testid='command-center-activity-timeline']"
    )
    assert payload["selectors"]["recovery_queue"] == (
        "[data-testid='command-center-recovery-queue']"
    )
    assert payload["selectors"]["provider_acquisition_gate"] == (
        "[data-testid='command-center-provider-acquisition-gate']"
    )
    assert payload["selectors"]["agent_activity"] == (
        "[data-testid='command-center-agent-activity']"
    )
    assert payload["selectors"]["active_task"] == (
        "[data-testid='command-center-active-task']"
    )
    assert payload["selectors"]["preflight_status_matrix"] == (
        "[data-testid='command-center-preflight-status-matrix']"
    )
    assert payload["safety"] == {
        "read_only": True,
        "external_network": False,
        "secret_values_returned": False,
        "content_read": False,
        "destructive_actions_enabled": False,
        "live_trading": False,
        "broker_mutation": False,
        "installed_source_read": False,
    }


def test_command_center_api_is_read_only_and_does_not_create_secret_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/command-center")

    payload = response.json()
    assert response.status_code == 200
    assert payload["mode"] == "read_only_ai_supervision_contract"
    assert payload["mission_ledger"]["goal_status"] == (
        "complete_for_current_non_live_scope"
    )
    assert payload["mission_ledger"]["partial_gap_count"] == 0
    assert payload["final_goal_audit"]["partial_count"] == 0
    assert payload["final_goal_audit"]["unknown_count"] == 0
    assert payload["mission_ledger"]["commit_cadence"] == (
        "one_verified_milestone_per_lore_commit"
    )
    assert payload["activity_timeline"][3]["summary"].startswith("16 routes / ")
    assert payload["activity_timeline"][3]["summary"].endswith("33 selectors")
    assert payload["activity_timeline"][5]["event_id"] == "provider_acquisition_gate"
    assert payload["activity_timeline"][5]["state"] == (
        "backlog_exhausted_needs_research"
    )
    assert payload["route_action_contract"]["preflight"]["method"] == "GET"
    assert payload["route_action_contract"]["route_count"] == 16
    assert payload["route_action_contract"]["actions"][0]["preflight_endpoint"].startswith(
        "/api/agent-actions/"
    )
    assert payload["route_action_contract"]["preflight_status_matrix"]["summary"][
        "row_count"
    ] == payload["route_action_contract"]["action_count"]
    assert payload["route_action_contract"]["preflight_status_matrix"]["summary"][
        "disabled_by_safety_count"
    ] == len(payload["route_action_contract"]["disabled_actions"])
    assert payload["advanced_outputs"]["summary"]["route_count"] == 5
    assert payload["artifact_recovery"]["artifact_root_health_matrix"]["summary"][
        "root_count"
    ] >= 15
    assert payload["artifact_recovery"]["artifact_root_health_matrix"]["summary"][
        "destructive_action_count"
    ] == 0
    assert payload["artifact_recovery"]["supervision_ready_root_count"] == payload[
        "artifact_recovery"
    ]["artifact_root_health_matrix"]["summary"]["supervision_ready_count"]
    assert "manifest_file_count" in payload["advanced_outputs"]["summary"]
    assert "state_artifact_file_count" in payload["advanced_outputs"]["summary"]
    assert "routes_health_partial" in payload["advanced_outputs"]["summary"]
    assert "supervision_ready_count" in payload["advanced_outputs"]["summary"]
    assert payload["advanced_outputs"]["summary"]["io_contract_route_count"] == 5
    assert "latest_manifest" in payload["advanced_outputs"]["routes"][0]
    assert "latest_state_artifact" in payload["advanced_outputs"]["routes"][0]
    assert "state_artifact_count" in payload["advanced_outputs"]["routes"][0]
    assert "missing_expected_kinds" in payload["advanced_outputs"]["routes"][0]
    assert "health_state" in payload["advanced_outputs"]["routes"][0]
    assert "io_contract" in payload["advanced_outputs"]["routes"][0]
    assert payload["advanced_outputs"]["routes"][0]["io_contract"]["read_mode"] == (
        "metadata_only"
    )
    assert payload["advanced_outputs"]["routes"][0]["io_contract"]["safety"][
        "content_read"
    ] is False
    assert payload["agent_activity"]["mode"] == "metadata_only_agent_activity_journal"
    assert payload["agent_activity"]["summary"]["event_count"] == 0
    assert payload["agent_activity"]["summary"]["active_task_state"] == "none"
    assert payload["agent_activity"]["active_task"]["is_active"] is False
    assert payload["active_task"]["is_active"] is False
    assert payload["active_task"]["action_id"] == ""
    assert payload["active_task"]["request_body_logged"] is False
    assert payload["active_task"]["action_executed_by_journal"] is False
    assert payload["active_task"]["destructive_actions_enabled"] is False
    assert payload["agent_activity"]["write_action"]["endpoint"] == "/api/agent-activity/events"
    assert payload["agent_activity"]["safety"]["request_body_logged"] is False
    assert payload["advanced_outputs"]["write_action"]["endpoint"] == (
        "/api/advanced-workflows/output-packet"
    )
    assert payload["advanced_outputs"]["safety"]["content_read"] is False
    assert payload["recovery_queue"]["summary"]["item_count"] == (
        payload["advanced_outputs"]["summary"]["recovery_recommended_count"]
    )
    assert payload["recovery_queue"]["summary"]["advanced_output_count"] == (
        payload["advanced_outputs"]["summary"]["recovery_recommended_count"]
    )
    assert payload["recovery_queue"]["summary"]["destructive_action_count"] == 0
    assert payload["recovery_queue"]["items"]
    assert {
        "queue_id",
        "source",
        "route_id",
        "recommended_action",
        "method",
        "endpoint",
        "safety_class",
        "destructive_actions_enabled",
    }.issubset(payload["recovery_queue"]["items"][0])
    assert all(
        item["destructive_actions_enabled"] is False
        for item in payload["recovery_queue"]["items"]
    )
    assert payload["risk_gates"]["installed_source_read"] is False
    assert payload["risk_gates"]["forbidden_capabilities"]["real_orders"] is False
    assert payload["safety"]["destructive_actions_enabled"] is False
    assert payload["safety"]["secret_values_returned"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    response_text = response.text.lower()
    assert "api_key=" not in response_text
    assert "protected_value" not in response_text
    assert "password" not in response_text


def test_command_center_preflight_matrix_api_is_read_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/command-center/preflight-matrix")

    payload = response.json()
    assert response.status_code == 200
    assert payload["mode"] == "read_only_command_center_preflight_matrix"
    assert payload["current_milestone"] == "M23.68 Final non-live completion audit"
    assert payload["matrix"]["summary"]["row_count"] >= 73
    assert payload["matrix"]["summary"]["ready_count"] > 0
    assert payload["matrix"]["summary"]["requires_confirmation_count"] >= 1
    assert payload["matrix"]["summary"]["disabled_by_safety_count"] >= 1
    rows = {row["action_id"]: row for row in payload["matrix"]["rows"]}
    assert rows["portfolio_report"]["status"] == "ready"
    assert rows["portfolio_report_health"]["status"] == "ready"
    assert rows["ai_chat_session_health"]["status"] == "ready"
    assert rows["nodes_workflow_health"]["status"] == "ready"
    assert rows["code_analysis_health"]["status"] == "ready"
    assert rows["quant_lab_preview_health"]["status"] == "ready"
    assert rows["quantlib_calculation_health"]["status"] == "ready"
    assert rows["code_run_disabled"]["status"] == "disabled_by_safety"
    assert rows["store_optional_data_provider_secret"]["status"] == (
        "requires_confirmation"
    )
    assert payload["preflight"]["action_executed"] is False
    assert payload["safety"]["action_executed"] is False
    assert payload["safety"]["local_mutation_performed"] is False
    assert payload["safety"]["secret_values_returned"] is False
    assert payload["safety"]["live_trading"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    response_text = response.text.lower()
    assert "api_key=" not in response_text
    assert "protected_value" not in response_text
    assert "password" not in response_text
