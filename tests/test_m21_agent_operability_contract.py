from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.agent_contract import (
    ACTION_CONTRACTS,
    ROUTE_CONTRACTS,
    agent_action_preflight_payload,
    agent_operability_payload,
)
from src.local_terminal.contracts import SHELL_ROUTE_IDS
from src.local_terminal.storage import LocalStateStore


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_agent_operability_contract_covers_all_routes_and_advanced_workflows(
    tmp_path: Path,
) -> None:
    payload = agent_operability_payload(tmp_path)
    routes = {row["route_id"]: row for row in payload["routes"]}
    actions = {row["action_id"]: row for row in payload["actions"]}

    assert payload["mode"] == "read_only_agent_contract"
    assert payload["summary"]["route_count"] == 16
    assert payload["summary"]["routes_match_shell"] is True
    assert payload["summary"]["preflight_available"] is True
    assert payload["preflight"]["endpoint"] == "/api/agent-actions/{action_id}/preflight"
    assert payload["preflight"]["action_executed"] is False
    assert "live_order" in payload["preflight"]["stop_gates"]
    assert payload["summary"]["selector_count"] == len(payload["selectors"])
    assert set(routes) == set(SHELL_ROUTE_IDS)
    assert routes["quantlib"]["primary_endpoint"] == "/api/quantlib"
    assert routes["quantlib"]["workspace_test_id"] == "workspace-quantlib"
    assert isinstance(routes["backtest"]["recommended_actions"], list)
    assert routes["backtest"]["recommended_actions"] == [
        "backtest_data_readiness",
        "backtest_run_closed_candle",
        "backtest_run_detail",
        "backtest_run_index",
        "backtest_artifact_health",
        "backtest_walk_forward_run",
        "backtest_optimize",
        "backtest_comparison_packet",
    ]
    assert routes["nodes"]["disabled_actions"] == ["nodes_deploy", "nodes_execute"]
    assert "workflow_health" in routes["nodes"]["state_fields"]
    assert "nodes_workflow_health" in routes["nodes"]["recommended_actions"]
    assert "macro_provider_stack" in routes["markets"]["state_fields"]
    assert "stock_status_lanes" in routes["markets"]["state_fields"]
    assert "stock_company_registry" in routes["markets"]["state_fields"]
    assert "stock_company_filings" in routes["markets"]["state_fields"]
    assert "stock_company_filings_watchlist" in routes["markets"]["state_fields"]
    assert "stock_xbrl_frames" in routes["markets"]["state_fields"]
    assert "provider_stack_panels" in routes["markets"]["state_fields"]
    assert "source_contract_panels" in routes["markets"]["state_fields"]
    assert "source_coverage_matrix" in routes["markets"]["state_fields"]
    assert "quote_reference_coverage" in routes["markets"]["state_fields"]
    assert "quote_snapshot_board" in routes["markets"]["state_fields"]
    assert "source_row_identity" in routes["markets"]["state_fields"]
    assert "research_lineage_source_rows" in routes["markets"]["state_fields"]
    assert "fx_h10_reference_rates" in routes["markets"]["state_fields"]
    assert "fx_bank_of_canada_reference_rates" in routes["markets"]["state_fields"]
    assert "fx_quote_watchlist" in routes["markets"]["state_fields"]
    assert "twelve_data_quote_watchlist" in routes["markets"]["state_fields"]
    assert "finnhub_equity_quote_watchlist" in routes["markets"]["state_fields"]
    assert "fmp_stock_quote_watchlist" in routes["markets"]["state_fields"]
    assert "stooq_quote_snapshot" in routes["markets"]["state_fields"]
    assert "moex_quote_snapshot" in routes["markets"]["state_fields"]
    assert "twse_quote_snapshot" in routes["markets"]["state_fields"]
    assert "nasdaq_trader_symbol_directory" in routes["markets"]["state_fields"]
    assert "nasdaq_trader_symbol_search" in routes["markets"]["state_fields"]
    assert "openfigi_identifier_mapping" in routes["markets"]["state_fields"]
    assert "commodity_cftc_cot_positioning" in routes["markets"]["state_fields"]
    assert "rates_sofr_reference" in routes["markets"]["state_fields"]
    assert "regional_bea_context" in routes["markets"]["state_fields"]
    assert "regional_census_context" in routes["markets"]["state_fields"]
    assert "research_lineage" in routes["backtest"]["state_fields"]
    assert "scan_seeded_provenance" in routes["backtest"]["state_fields"]
    assert "comparison_packet" in routes["backtest"]["state_fields"]
    assert "run_index" in routes["backtest"]["state_fields"]
    assert "artifact_health" in routes["backtest"]["state_fields"]
    assert "data_readiness" in routes["backtest"]["state_fields"]
    assert "backtest_data_readiness" in routes["backtest"]["recommended_actions"]
    assert "backtest_run_index" in routes["backtest"]["recommended_actions"]
    assert "backtest_artifact_health" in routes["backtest"]["recommended_actions"]
    assert "markets_etf_refresh" in routes["markets"]["recommended_actions"]
    assert "markets_quote_reference_coverage" in routes["markets"]["recommended_actions"]
    assert "markets_quote_snapshot_board" in routes["markets"]["recommended_actions"]
    assert "command_center_preflight_matrix" in routes["settings"]["recommended_actions"]
    assert "scan_readiness" in routes["algo"]["state_fields"]
    assert "scan_source_contract" in routes["algo"]["state_fields"]
    assert "scan_artifacts" in routes["algo"]["state_fields"]
    assert "scan_artifact_health" in routes["algo"]["state_fields"]
    assert "research_lineage" in routes["algo"]["state_fields"]
    assert "scan_seed" in routes["algo"]["state_fields"]
    assert "algo_scan_readiness" in routes["algo"]["recommended_actions"]
    assert "report_lineage" in routes["portfolio"]["state_fields"]
    assert "report_artifact_health" in routes["portfolio"]["state_fields"]
    assert "report_index" in routes["portfolio"]["state_fields"]
    assert "report_health" in routes["portfolio"]["state_fields"]
    assert "exposure_map" in routes["portfolio"]["state_fields"]
    assert "portfolio_report_index" in routes["portfolio"]["recommended_actions"]
    assert "portfolio_report_health" in routes["portfolio"]["recommended_actions"]
    assert "research_brief" in routes["news"]["state_fields"]
    assert "source_health" in routes["news"]["state_fields"]
    assert "research_brief_index" in routes["news"]["state_fields"]
    assert "topic_entity_map" in routes["news"]["state_fields"]
    assert "news_research_brief" in routes["news"]["recommended_actions"]
    assert "news_research_brief_index" in routes["news"]["recommended_actions"]
    assert "news_topic_entity_map" in routes["news"]["recommended_actions"]
    assert "context_contract" in routes["ai_chat"]["state_fields"]
    assert "session_health" in routes["ai_chat"]["state_fields"]
    assert "ai_chat_context_contract" in routes["ai_chat"]["recommended_actions"]
    assert "ai_chat_session_health" in routes["ai_chat"]["recommended_actions"]
    assert "analysis_health" in routes["code"]["state_fields"]
    assert "code_analysis_health" in routes["code"]["recommended_actions"]
    assert "preview_health" in routes["quant_lab"]["state_fields"]
    assert "quant_lab_preview_health" in routes["quant_lab"]["recommended_actions"]
    assert "calculation_health" in routes["quantlib"]["state_fields"]
    assert "quantlib_calculation_health" in routes["quantlib"]["recommended_actions"]
    assert "algo_scan_artifacts_repair" in routes["algo"]["recommended_actions"]
    assert "provider_refresh_result_semantics" in routes["settings"]["state_fields"]
    assert "provider_refresh_schedule_plan" in routes["settings"]["state_fields"]
    assert "advanced_outputs" in routes["settings"]["state_fields"]
    assert "advanced_output_manifest_index" in routes["settings"]["state_fields"]
    assert "advanced_output_health_matrix" in routes["settings"]["state_fields"]
    assert "advanced_output_io_contract" in routes["settings"]["state_fields"]
    assert "command_center_recovery_queue" in routes["settings"]["state_fields"]
    assert "agent_activity_journal" in routes["settings"]["state_fields"]
    assert "command_center_active_task" in routes["settings"]["state_fields"]
    assert "advanced_workflow_output_packet" in routes["settings"]["recommended_actions"]
    assert "advanced_workflow_output_index" in routes["settings"]["recommended_actions"]
    assert "advanced_workflow_output_health" in routes["settings"]["recommended_actions"]
    assert "advanced_workflow_io_contract" in routes["settings"]["recommended_actions"]
    assert "agent_activity_event" in routes["settings"]["recommended_actions"]
    assert "provider_refresh_public_start" in routes["settings"]["recommended_actions"]
    assert "provider_refresh_schedule_plan_inspect" in routes["settings"][
        "recommended_actions"
    ]
    assert all(isinstance(row["recommended_actions"], list) for row in payload["routes"])
    assert all(isinstance(row["disabled_actions"], list) for row in payload["routes"])
    assert actions["ai_chat_append_message"]["expected_error_codes"] == (
        "400 credential_material",
        "400 unsafe_artifact_path",
    )
    assert actions["ai_chat_context_contract"]["endpoint"] == "/api/ai-chat/context-contract"
    assert actions["ai_chat_context_contract"]["method"] == "GET"
    assert actions["ai_chat_context_contract"]["local_mutation"] is False
    assert actions["ai_chat_context_contract"]["writes_local_artifacts"] is False
    assert actions["ai_chat_context_contract"]["safety_class"] == (
        "metadata_only_ai_chat_context_contract"
    )
    assert actions["ai_chat_context_contract"]["response_contract"] == (
        "limits",
        "output_state",
        "source_citations",
        "artifact_provenance",
        "context_summary",
        "safety",
    )
    assert actions["ai_chat_session_health"]["endpoint"] == "/api/ai-chat/session-health"
    assert actions["ai_chat_session_health"]["method"] == "GET"
    assert actions["ai_chat_session_health"]["local_mutation"] is False
    assert actions["ai_chat_session_health"]["writes_local_artifacts"] is False
    assert actions["ai_chat_session_health"]["safety_class"] == (
        "metadata_only_ai_chat_session_health"
    )
    assert actions["ai_chat_session_health"]["response_contract"] == (
        "summary",
        "sessions",
        "recovery_queue",
        "recommended_actions",
        "safety",
    )
    assert actions["code_run_disabled"]["disabled_by_safety"] is True
    assert actions["code_analysis_health"]["endpoint"] == "/api/code/analysis-health"
    assert actions["code_analysis_health"]["method"] == "GET"
    assert actions["code_analysis_health"]["local_mutation"] is False
    assert actions["code_analysis_health"]["writes_local_artifacts"] is False
    assert actions["code_analysis_health"]["safety_class"] == (
        "metadata_only_code_analysis_health"
    )
    assert actions["code_analysis_health"]["response_contract"] == (
        "summary",
        "notebooks",
        "recovery_queue",
        "recommended_actions",
        "safety",
    )
    assert "analysis_result.static_outline" in actions["code_analyze"]["response_contract"]
    assert "static outline" in actions["code_analyze"]["output_contract"]
    assert actions["nodes_dry_run"]["writes_local_artifacts"] is True
    assert actions["nodes_workflow_health"]["endpoint"] == "/api/nodes/workflow-health"
    assert actions["nodes_workflow_health"]["method"] == "GET"
    assert actions["nodes_workflow_health"]["local_mutation"] is False
    assert actions["nodes_workflow_health"]["writes_local_artifacts"] is False
    assert actions["nodes_workflow_health"]["safety_class"] == (
        "metadata_only_nodes_workflow_health"
    )
    assert actions["nodes_workflow_health"]["response_contract"] == (
        "summary",
        "workflows",
        "recovery_queue",
        "recommended_actions",
        "safety",
    )
    assert actions["quant_lab_run_preview"]["safety_class"] == "local_preview_only"
    assert actions["quant_lab_preview_health"]["endpoint"] == (
        "/api/quant-lab/preview-health"
    )
    assert actions["quant_lab_preview_health"]["method"] == "GET"
    assert actions["quant_lab_preview_health"]["local_mutation"] is False
    assert actions["quant_lab_preview_health"]["writes_local_artifacts"] is False
    assert actions["quant_lab_preview_health"]["safety_class"] == (
        "metadata_only_quant_lab_preview_health"
    )
    assert actions["quant_lab_preview_health"]["response_contract"] == (
        "summary",
        "runs",
        "recovery_queue",
        "recommended_actions",
        "safety",
    )
    assert actions["quantlib_calculation_health"]["endpoint"] == (
        "/api/quantlib/calculation-health"
    )
    assert actions["quantlib_calculation_health"]["method"] == "GET"
    assert actions["quantlib_calculation_health"]["local_mutation"] is False
    assert actions["quantlib_calculation_health"]["writes_local_artifacts"] is False
    assert actions["quantlib_calculation_health"]["safety_class"] == (
        "metadata_only_quantlib_calculation_health"
    )
    assert actions["quantlib_calculation_health"]["response_contract"] == (
        "summary",
        "calculations",
        "recovery_queue",
        "recommended_actions",
        "safety",
    )
    assert actions["quantlib_compute"]["output_contract"] == (
        "writes request/response/report/error/context/manifest artifacts"
    )
    assert actions["store_optional_data_provider_secret"]["requires_confirmation"] is True
    assert actions["store_optional_data_provider_secret"]["safety_class"] == (
        "optional_data_provider_secret_local_only"
    )
    assert actions["provider_refresh_public_start"]["endpoint"] == (
        "/api/providers/refresh-public/jobs"
    )
    assert actions["markets_quote_reference_coverage"]["endpoint"] == (
        "/api/markets/quote-reference-coverage"
    )
    assert actions["markets_quote_reference_coverage"]["method"] == "GET"
    assert actions["markets_quote_reference_coverage"]["local_mutation"] is False
    assert actions["markets_quote_reference_coverage"]["writes_local_artifacts"] is False
    assert actions["markets_quote_reference_coverage"]["safety_class"] == (
        "read_only_markets_quote_reference_coverage"
    )
    assert actions["markets_quote_reference_coverage"]["response_contract"] == (
        "summary",
        "quote_lanes",
        "reference_lanes",
        "context_lanes",
        "snapshot_board",
        "recommended_actions",
        "safety",
    )
    assert actions["markets_quote_snapshot_board"]["endpoint"] == (
        "/api/markets/quote-snapshot-board"
    )
    assert actions["markets_quote_snapshot_board"]["method"] == "GET"
    assert actions["markets_quote_snapshot_board"]["local_mutation"] is False
    assert actions["markets_quote_snapshot_board"]["writes_local_artifacts"] is False
    assert actions["markets_quote_snapshot_board"]["safety_class"] == (
        "read_only_markets_quote_snapshot_board"
    )
    assert actions["markets_quote_snapshot_board"]["response_contract"] == (
        "summary",
        "rows",
        "safety",
    )
    assert "stocks.status_lanes" in actions["markets_stocks_refresh"]["response_contract"]
    assert "stocks.summary.filing_symbols" in actions["markets_stocks_refresh"]["response_contract"]
    assert "stocks.summary.frame_count" in actions["markets_stocks_refresh"]["response_contract"]
    assert "source_coverage_matrix" in actions["markets_stocks_refresh"]["response_contract"]
    assert "stocks.status_lanes" in actions[
        "markets_stocks_quote_watchlist_refresh"
    ]["response_contract"]
    for action_id in (
        "markets_refresh_public",
        "markets_etf_refresh",
        "markets_etf_quote_watchlist_refresh",
        "markets_rates_refresh",
        "markets_fx_refresh",
        "markets_fx_quote_watchlist_refresh",
        "markets_twelve_data_quote_watchlist_refresh",
        "markets_finnhub_quote_watchlist_refresh",
        "markets_fmp_quote_watchlist_refresh",
        "markets_stooq_quote_snapshot_refresh",
        "markets_moex_quote_snapshot_refresh",
        "markets_twse_quote_snapshot_refresh",
        "markets_nasdaq_symbol_directory_refresh",
        "markets_openfigi_mapping_refresh",
        "markets_commodities_refresh",
        "markets_cftc_cot_refresh",
        "markets_eia_refresh",
        "markets_macro_refresh",
        "markets_fred_refresh",
        "markets_bea_refresh",
        "markets_census_refresh",
        "markets_bls_macro_refresh",
    ):
        assert "source_coverage_matrix" in actions[action_id]["response_contract"]
        assert actions[action_id]["disabled_by_safety"] is False
        assert actions[action_id]["requires_confirmation"] is False
    assert actions["markets_fx_refresh"]["safety_class"] == "public_read_only_fx_reference"
    assert "rates.sofr" in actions["markets_rates_refresh"]["response_contract"]
    assert "fx.h10" in actions["markets_fx_refresh"]["response_contract"]
    assert "fx.boc" in actions["markets_fx_refresh"]["response_contract"]
    assert actions["markets_fx_quote_watchlist_refresh"]["safety_class"] == (
        "optional_key_market_data_no_broker_mutation"
    )
    assert actions["markets_fx_quote_watchlist_refresh"]["endpoint"] == (
        "/api/markets/fx/quote/refresh"
    )
    assert "fx.quote_watchlist" in actions[
        "markets_fx_quote_watchlist_refresh"
    ]["response_contract"]
    assert actions["markets_twelve_data_quote_watchlist_refresh"]["endpoint"] == (
        "/api/markets/twelve-data/quotes/refresh"
    )
    assert "research_summary.twelve_data_quotes" in actions[
        "markets_twelve_data_quote_watchlist_refresh"
    ]["response_contract"]
    assert actions["markets_finnhub_quote_watchlist_refresh"]["endpoint"] == (
        "/api/markets/finnhub/quotes/refresh"
    )
    assert actions["markets_finnhub_quote_watchlist_refresh"]["safety_class"] == (
        "optional_key_market_data_no_broker_mutation"
    )
    assert "research_summary.finnhub_quotes" in actions[
        "markets_finnhub_quote_watchlist_refresh"
    ]["response_contract"]
    assert actions["markets_fmp_quote_watchlist_refresh"]["endpoint"] == (
        "/api/markets/fmp/quotes/refresh"
    )
    assert actions["markets_fmp_quote_watchlist_refresh"]["safety_class"] == (
        "optional_key_market_data_no_broker_mutation"
    )
    assert "research_summary.fmp_quotes" in actions[
        "markets_fmp_quote_watchlist_refresh"
    ]["response_contract"]
    assert actions["markets_stooq_quote_snapshot_refresh"]["endpoint"] == (
        "/api/markets/stooq/quotes/refresh"
    )
    assert actions["markets_stooq_quote_snapshot_refresh"]["safety_class"] == (
        "public_read_only_market_data"
    )
    assert "research_summary.stooq_quotes" in actions[
        "markets_stooq_quote_snapshot_refresh"
    ]["response_contract"]
    assert actions["markets_moex_quote_snapshot_refresh"]["endpoint"] == (
        "/api/markets/moex/quotes/refresh"
    )
    assert actions["markets_moex_quote_snapshot_refresh"]["safety_class"] == (
        "public_read_only_market_data"
    )
    assert "research_summary.moex_quotes" in actions[
        "markets_moex_quote_snapshot_refresh"
    ]["response_contract"]
    assert actions["markets_twse_quote_snapshot_refresh"]["endpoint"] == (
        "/api/markets/twse/quotes/refresh"
    )
    assert actions["markets_twse_quote_snapshot_refresh"]["safety_class"] == (
        "public_read_only_market_data"
    )
    assert "research_summary.twse_quotes" in actions[
        "markets_twse_quote_snapshot_refresh"
    ]["response_contract"]
    assert actions["markets_nasdaq_symbol_directory_refresh"]["endpoint"] == (
        "/api/markets/nasdaq-trader/symbols/refresh"
    )
    assert actions["markets_nasdaq_symbol_directory_refresh"]["safety_class"] == (
        "public_read_only_reference_data"
    )
    assert "research_summary.nasdaq_symbols" in actions[
        "markets_nasdaq_symbol_directory_refresh"
    ]["response_contract"]
    assert actions["markets_nasdaq_symbol_directory_search"]["endpoint"] == (
        "/api/markets/nasdaq-trader/symbols/search"
    )
    assert actions["markets_nasdaq_symbol_directory_search"]["method"] == "GET"
    assert actions["markets_nasdaq_symbol_directory_search"]["local_mutation"] is False
    assert actions["markets_nasdaq_symbol_directory_search"]["safety_class"] == (
        "public_read_only_reference_data"
    )
    assert actions["markets_nasdaq_symbol_directory_search"]["response_contract"] == (
        "query",
        "rows",
        "total_matches",
        "quote_semantics",
        "orderable",
    )
    assert actions["markets_openfigi_mapping_refresh"]["endpoint"] == (
        "/api/markets/openfigi/mapping/refresh"
    )
    assert actions["markets_openfigi_mapping_refresh"]["safety_class"] == (
        "public_read_only_reference_data"
    )
    assert "research_summary.openfigi_mapping" in actions[
        "markets_openfigi_mapping_refresh"
    ]["response_contract"]
    assert actions["markets_cftc_cot_refresh"]["endpoint"] == (
        "/api/markets/cftc-cot/refresh"
    )
    assert actions["markets_cftc_cot_refresh"]["safety_class"] == (
        "public_read_only_commodity_positioning"
    )
    assert actions["markets_eia_refresh"]["safety_class"] == (
        "optional_key_research_data_no_broker_mutation"
    )
    assert actions["markets_fred_refresh"]["safety_class"] == (
        "optional_key_research_data_no_broker_mutation"
    )
    assert actions["markets_bea_refresh"]["endpoint"] == "/api/markets/bea/refresh"
    assert actions["markets_bea_refresh"]["safety_class"] == (
        "optional_key_research_data_no_broker_mutation"
    )
    assert "regional" in actions["markets_bea_refresh"]["response_contract"]
    assert actions["markets_census_refresh"]["endpoint"] == "/api/markets/census/refresh"
    assert actions["markets_census_refresh"]["safety_class"] == (
        "optional_key_research_data_no_broker_mutation"
    )
    assert "regional" in actions["markets_census_refresh"]["response_contract"]
    assert actions["markets_macro_refresh"]["safety_class"] == "public_read_only_macro_context"
    assert actions["provider_refresh_public_start"]["writes_local_artifacts"] is True
    assert actions["provider_refresh_public_start"]["safety_class"] == (
        "manual_public_no_key_provider_refresh"
    )
    assert "cache_available" in actions["provider_refresh_public_start"]["output_contract"]
    assert "artifact_root_health_matrix" in routes["settings"]["state_fields"]
    assert actions["artifact_lifecycle_root_health"]["endpoint"] == (
        "/api/artifact-lifecycle"
    )
    assert actions["artifact_lifecycle_root_health"]["method"] == "GET"
    assert actions["artifact_lifecycle_root_health"]["writes_local_artifacts"] is False
    assert actions["artifact_lifecycle_root_health"]["safety_class"] == (
        "metadata_only_artifact_root_supervision"
    )
    assert "roots[].supervision_ready" in actions[
        "artifact_lifecycle_root_health"
    ]["response_contract"]
    assert "runs[].summary.cache_available" in actions[
        "provider_refresh_lifecycle_inspect"
    ]["response_contract"]
    assert actions["provider_refresh_schedule_plan_inspect"]["endpoint"] == (
        "/api/providers/refresh-public/schedule-plan"
    )
    assert actions["provider_refresh_schedule_plan_inspect"]["method"] == "GET"
    assert actions["provider_refresh_schedule_plan_inspect"]["local_mutation"] is False
    assert actions["provider_refresh_schedule_plan_inspect"]["writes_local_artifacts"] is False
    assert actions["provider_refresh_schedule_plan_inspect"]["safety_class"] == (
        "read_only_provider_refresh_schedule_plan"
    )
    assert actions["provider_refresh_schedule_plan_inspect"]["response_contract"] == (
        "summary",
        "providers",
        "actions",
        "safety",
    )
    assert actions["backtest_walk_forward_run"]["endpoint"] == "/api/backtest/walk-forward"
    assert "manifest" in actions["backtest_walk_forward_run"]["response_contract"]
    assert actions["backtest_walk_forward_run"]["disabled_by_safety"] is False
    assert actions["backtest_comparison_packet"]["endpoint"] == (
        "/api/backtest/comparison-packet"
    )
    assert "ranked_rows" in actions["backtest_comparison_packet"]["response_contract"]
    assert actions["backtest_comparison_packet"]["safety_class"] == (
        "local_backtest_comparison_packet"
    )
    assert actions["backtest_comparison_packet"]["disabled_by_safety"] is False
    assert actions["backtest_run_index"]["endpoint"] == "/api/backtest/runs"
    assert actions["backtest_run_index"]["method"] == "GET"
    assert actions["backtest_run_index"]["writes_local_artifacts"] is False
    assert actions["backtest_run_index"]["safety_class"] == "local_backtest_run_index"
    assert "runs" in actions["backtest_run_index"]["response_contract"]
    assert actions["backtest_artifact_health"]["endpoint"] == "/api/backtest/artifact-health"
    assert actions["backtest_artifact_health"]["method"] == "GET"
    assert actions["backtest_artifact_health"]["writes_local_artifacts"] is False
    assert actions["backtest_artifact_health"]["safety_class"] == (
        "metadata_only_backtest_artifact_health"
    )
    assert "runs" in actions["backtest_artifact_health"]["response_contract"]
    assert actions["backtest_data_readiness"]["endpoint"] == (
        "/api/backtest/data-readiness"
    )
    assert actions["backtest_data_readiness"]["method"] == "GET"
    assert actions["backtest_data_readiness"]["writes_local_artifacts"] is False
    assert actions["backtest_data_readiness"]["safety_class"] == (
        "metadata_only_backtest_data_readiness"
    )
    assert "datasets" in actions["backtest_data_readiness"]["response_contract"]
    assert "research_lineage" in actions["backtest_run_closed_candle"]["response_contract"]
    assert actions["algo_scan_readiness"]["endpoint"] == "/api/algo/scan-readiness"
    assert actions["algo_scan_readiness"]["method"] == "GET"
    assert actions["algo_scan_readiness"]["writes_local_artifacts"] is False
    assert actions["algo_scan_readiness"]["safety_class"] == (
        "metadata_only_algo_scan_readiness"
    )
    assert "symbol_readiness" in actions["algo_scan_readiness"]["response_contract"]
    assert actions["algo_scan"]["writes_local_artifacts"] is True
    # M26 S1.3: keys are dotted paths matching the real nested response shape
    assert "scan_result.source_contract" in actions["algo_scan"]["response_contract"]
    assert "scan_result.research_lineage" in actions["algo_scan"]["response_contract"]
    assert "scan_result.artifacts" in actions["algo_scan"]["response_contract"]
    assert actions["algo_run_backtest"]["endpoint"] == "/api/algo/run-backtest"
    assert "backtest_result.research_lineage" in actions["algo_run_backtest"]["response_contract"]
    assert actions["algo_run_backtest"]["safety_class"] == (
        "closed_candle_scan_seeded_local_research"
    )
    assert actions["algo_run_backtest"]["disabled_by_safety"] is False
    assert actions["algo_scan_artifacts_repair"]["endpoint"] == "/api/algo/scan-artifacts/repair"
    assert actions["algo_scan_artifacts_repair"]["safety_class"] == (
        "non_destructive_local_artifact_repair"
    )
    assert actions["algo_scan_artifacts_repair"]["writes_local_artifacts"] is True
    assert actions["algo_scan_artifacts_repair"]["disabled_by_safety"] is False
    assert actions["algo_scan_artifacts_repair"]["expected_error_codes"] == (
        "400 no_scan_artifacts",
        "400 invalid_scan_state",
    )
    assert actions["portfolio_report"]["endpoint"] == "/api/portfolio/report"
    assert "report.artifact_files.exposure" in actions["portfolio_report"]["response_contract"]
    assert "report.exposure_row_count" in actions["portfolio_report"]["response_contract"]
    assert "report.artifact_files.lineage" in actions["portfolio_report"]["response_contract"]
    assert "report.artifact_health" in actions["portfolio_report"]["response_contract"]
    assert actions["portfolio_report"]["safety_class"] == "local_portfolio_research_packet"
    assert actions["portfolio_report"]["writes_local_artifacts"] is True
    assert actions["portfolio_report_index"]["endpoint"] == "/api/portfolio/reports"
    assert actions["portfolio_report_index"]["method"] == "GET"
    assert "reports" in actions["portfolio_report_index"]["response_contract"]
    assert actions["portfolio_report_index"]["safety_class"] == (
        "metadata_only_portfolio_report_index"
    )
    assert actions["portfolio_report_index"]["writes_local_artifacts"] is False
    assert actions["portfolio_report_health"]["endpoint"] == "/api/portfolio/report-health"
    assert actions["portfolio_report_health"]["method"] == "GET"
    assert "reports" in actions["portfolio_report_health"]["response_contract"]
    assert actions["portfolio_report_health"]["safety_class"] == (
        "metadata_only_portfolio_report_health"
    )
    assert actions["portfolio_report_health"]["writes_local_artifacts"] is False
    assert actions["portfolio_link_backtest"]["safety_class"] == "read_only_backtest_artifact_link"
    assert actions["portfolio_link_backtest"]["writes_local_artifacts"] is True
    assert actions["news_research_brief"]["endpoint"] == "/api/news/research-brief"
    assert "research_brief.artifacts.source_health" in actions[
        "news_research_brief"
    ]["response_contract"]
    assert actions["news_research_brief"]["safety_class"] == (
        "metadata_only_news_research_packet"
    )
    assert actions["news_research_brief"]["writes_local_artifacts"] is True
    assert actions["news_research_brief_index"]["endpoint"] == (
        "/api/news/research-briefs"
    )
    assert "recovery_queue" in actions["news_research_brief_index"]["response_contract"]
    assert actions["news_research_brief_index"]["safety_class"] == (
        "metadata_only_news_research_brief_index"
    )
    assert actions["news_research_brief_index"]["writes_local_artifacts"] is False
    assert actions["news_topic_entity_map"]["endpoint"] == "/api/news/topic-entity-map"
    assert actions["news_topic_entity_map"]["method"] == "GET"
    assert actions["news_topic_entity_map"]["writes_local_artifacts"] is False
    assert actions["news_topic_entity_map"]["safety_class"] == (
        "metadata_only_news_topic_entity_map"
    )
    assert "entities" in actions["news_topic_entity_map"]["response_contract"]
    assert actions["advanced_workflow_output_packet"]["endpoint"] == (
        "/api/advanced-workflows/output-packet"
    )
    assert actions["advanced_workflow_output_packet"]["safety_class"] == (
        "metadata_only_advanced_local_output_packet"
    )
    assert actions["advanced_workflow_output_packet"]["writes_local_artifacts"] is True
    assert "recovery_queue" in actions["advanced_workflow_output_packet"]["response_contract"]
    assert actions["advanced_workflow_output_index"]["endpoint"] == (
        "/api/advanced-workflows/output-packet"
    )
    assert "routes[].artifact_kinds" in actions["advanced_workflow_output_index"][
        "response_contract"
    ]
    assert "summary.state_artifact_file_count" in actions[
        "advanced_workflow_output_index"
    ]["response_contract"]
    assert "routes[].state_artifact_count" in actions[
        "advanced_workflow_output_index"
    ]["response_contract"]
    assert actions["advanced_workflow_output_index"]["safety_class"] == (
        "metadata_only_advanced_local_output_index"
    )
    assert actions["advanced_workflow_output_index"]["writes_local_artifacts"] is False
    assert actions["advanced_workflow_output_health"]["endpoint"] == (
        "/api/advanced-workflows/output-packet"
    )
    assert "routes[].missing_expected_kinds" in actions[
        "advanced_workflow_output_health"
    ]["response_contract"]
    assert actions["advanced_workflow_output_health"]["safety_class"] == (
        "metadata_only_advanced_local_output_health"
    )
    assert actions["advanced_workflow_output_health"]["writes_local_artifacts"] is False
    assert actions["advanced_workflow_io_contract"]["endpoint"] == (
        "/api/advanced-workflows/output-packet"
    )
    assert actions["advanced_workflow_io_contract"]["method"] == "GET"
    assert actions["advanced_workflow_io_contract"]["safety_class"] == (
        "metadata_only_advanced_local_output_io_contract"
    )
    assert actions["advanced_workflow_io_contract"]["writes_local_artifacts"] is False
    assert "routes[].io_contract.input_contract" in actions[
        "advanced_workflow_io_contract"
    ]["response_contract"]
    assert actions["agent_activity_event"]["endpoint"] == "/api/agent-activity/events"
    assert actions["agent_activity_event"]["safety_class"] == (
        "metadata_only_agent_activity_journal"
    )
    assert actions["agent_activity_event"]["writes_local_artifacts"] is True
    assert actions["agent_activity_event"]["disabled_by_safety"] is False
    assert actions["command_center_preflight_matrix"]["endpoint"] == (
        "/api/command-center/preflight-matrix"
    )
    assert actions["command_center_preflight_matrix"]["method"] == "GET"
    assert actions["command_center_preflight_matrix"]["writes_local_artifacts"] is False
    assert actions["command_center_preflight_matrix"]["safety_class"] == (
        "read_only_command_center_preflight_matrix"
    )
    assert "matrix.rows" in actions["command_center_preflight_matrix"][
        "response_contract"
    ]
    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["secret_values_returned"] is False
    assert payload["safety"]["live_trading"] is False
    assert payload["safety"]["installed_source_read"] is False


def test_agent_contract_api_is_read_only_and_does_not_create_secret_store(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/agent-contract")

    payload = response.json()
    assert response.status_code == 200
    assert payload["summary"]["route_count"] == 16
    assert payload["summary"]["advanced_route_count"] == 5
    assert any(
        selector["selector"] == "[data-testid='workspace-settings']"
        for selector in payload["selectors"]
    )
    assert any(error["error_code"] == "disabled_no_safety_contract" for error in payload["error_catalog"])
    assert payload["observation_evidence"]["retained_reference_screenshot"] is False
    assert payload["safety"]["destructive_actions_enabled"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_agent_action_preflight_is_read_only_and_contract_backed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    ready = client.get("/api/agent-actions/portfolio_report/preflight").json()
    disabled = client.get("/api/agent-actions/code_run_disabled/preflight").json()
    confirmation = agent_action_preflight_payload(
        tmp_path, "store_optional_data_provider_secret"
    )
    unknown = client.get("/api/agent-actions/not_a_real_action/preflight").json()

    assert ready["mode"] == "read_only_action_preflight"
    assert ready["status"] == "ready"
    assert ready["allowed_to_attempt"] is True
    assert ready["action"]["endpoint"] == "/api/portfolio/report"
    assert ready["action"]["writes_local_artifacts"] is True
    assert ready["safety"]["action_executed"] is False
    assert ready["safety"]["secret_values_returned"] is False
    assert "destructive_action" in ready["stop_gates"]
    assert disabled["status"] == "disabled_by_safety"
    assert disabled["allowed_to_attempt"] is False
    assert disabled["action"]["endpoint"] == "/api/code/run"
    assert confirmation["status"] == "requires_confirmation"
    assert confirmation["allowed_without_confirmation"] is False
    assert unknown["status"] == "unknown_action"
    assert unknown["allowed_to_attempt"] is False
    assert unknown["action"] == {}
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_governance_and_diagnostics_include_agent_contract_bundle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path, monkeypatch)

    governance = client.get("/api/governance").json()
    help_diagnostics = client.post("/api/help/diagnostics").json()
    governance_diagnostics = client.post("/api/governance/diagnostics").json()

    assert governance["agent_contract"]["summary"]["routes_match_shell"] is True
    assert governance["summary"]["agent_route_count"] == 16
    assert governance["summary"]["agent_disabled_action_count"] >= 1
    assert help_diagnostics["checks"]["agent_contract_read_only"] is True
    assert help_diagnostics["checks"]["agent_contract_routes_complete"] is True
    assert governance_diagnostics["checks"]["agent_contract_routes_complete"] is True
    assert governance_diagnostics["checks"]["agent_contract_actions_present"] is True
    assert governance_diagnostics["checks"]["agent_contract_selectors_present"] is True
    assert governance_diagnostics["safety"]["agent_contract_read_only"] is True
    assert (tmp_path / governance_diagnostics["artifacts"]["agent_contract"]).is_file()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_agent_contract_endpoints_match_fastapi_route_registry() -> None:
    app = server.create_app()
    registered = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
    }
    missing_primary = [
        ("GET", route.primary_endpoint)
        for route in ROUTE_CONTRACTS
        if ("GET", route.primary_endpoint) not in registered
    ]
    missing_actions = [
        (action.method, action.endpoint)
        for action in ACTION_CONTRACTS
        if (action.method, action.endpoint) not in registered
    ]

    assert missing_primary == []
    assert missing_actions == []


def test_every_route_recommended_action_resolves_in_action_contracts() -> None:
    # A route must never recommend an action the contract cannot preflight;
    # otherwise a contract-obedient agent is forbidden from its own route's
    # primary operations (the M25 audit found crypto paper orders in exactly
    # this state).
    declared = {action.action_id for action in ACTION_CONTRACTS}
    unresolved = [
        (route.route_id, action_id)
        for route in ROUTE_CONTRACTS
        for action_id in route.recommended_actions
        if action_id not in declared
    ]
    assert unresolved == []
