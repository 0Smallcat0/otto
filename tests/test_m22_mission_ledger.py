from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs" / "planning" / "M22_MISSION_LEDGER.md"
FINAL_AUDIT = ROOT / "docs" / "planning" / "M22_FINAL_NON_LIVE_PARITY_AUDIT.md"
COMPLETION_AUDIT = ROOT / "docs" / "planning" / "M23_FINAL_NON_LIVE_COMPLETION_AUDIT.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_m22_mission_ledger_defines_resume_and_status_contract() -> None:
    text = _read(LEDGER)

    assert "M21.23" in text
    assert "2955c42" in text
    for status in ("completed", "partial", "blocked", "not-started"):
        assert f"`{status}`" in text
    for phrase in (
        "Do Not Redo",
        "Stop Gates",
        "Verification Cadence",
        "Resume Rules",
        "Command-center AI supervision contract",
    ):
        assert phrase in text


def test_m22_mission_ledger_preserves_forbidden_boundaries() -> None:
    text = _read(LEDGER)

    for forbidden_boundary in (
        "real orders",
        "real balance reads",
        "margin",
        "leverage",
        "short exposure",
        "derivatives",
        "payment",
        "subscription",
        "CR/credits",
        "cloud sync",
        "D:\\FinceptTerminal\\app\\scripts",
    ):
        assert forbidden_boundary in text


def test_project_state_points_to_m22_ledger() -> None:
    project_state = _read(ROOT / "PROJECT_STATE.md")

    assert "docs/planning/M22_MISSION_LEDGER.md" in project_state
    assert "M22.1: Mission ledger" in project_state
    assert "M23.31: Bank of Canada FX reference" in project_state
    assert "M23.32: Backtest volatility reversion" in project_state
    assert "M23.33: Portfolio report index" in project_state
    assert "M23.34: Finnhub equity quote watchlist" in project_state
    assert "M23.35: Advanced output state-file classification" in project_state
    assert "M23.36: Cboe delayed quote gate" in project_state
    assert "M23.37: FMP quote watchlist" in project_state
    assert "M23.38: Provider acquisition resume contract" in project_state
    assert "M23.39: Backtest data readiness" in project_state
    assert "M23.40: Algo scan readiness" in project_state
    assert "M23.41: News topic/entity map" in project_state
    assert "M23.42: IEX TOPS market data gate" in project_state
    assert "M23.43: Provider gate candidate detail" in project_state
    assert "M23.44: Backtest momentum continuation" in project_state
    assert "M23.45: Portfolio exposure map" in project_state
    assert "M23.46: Command Center action matrix" in project_state
    assert "M23.47: Markets quote snapshot board" in project_state
    assert "M23.48: Command Center preflight matrix" in project_state
    assert "M23.49: TWSE daily quote snapshots" in project_state
    assert "M23.50: Eurostat HICP macro context" in project_state
    assert "M23.51: Provider refresh schedule plan" in project_state
    assert "M23.52: Backtest artifact health matrix" in project_state
    assert "M23.53: OpenFIGI identifier mapping" in project_state
    assert "M23.54: Portfolio report health matrix" in project_state
    assert "M23.55: AI Chat session health matrix" in project_state
    assert "M23.56: Nodes workflow health matrix" in project_state
    assert "M23.57: Code analysis health matrix" in project_state
    assert "M23.58: Quant Lab preview health matrix" in project_state
    assert "M23.59: QuantLib calculation health matrix" in project_state
    assert "M23.60: Nasdaq Data Link provider gate" in project_state
    assert "M23.61: QuantLib implied-volatility calculator" in project_state
    assert "M23.62: Global Command Center drawer" in project_state
    assert "M23.63: Backtest RSI reversion" in project_state
    assert "M23.64: JPX/J-Quants provider gate" in project_state
    assert "M23.65: QuantLib option scenario grid" in project_state
    assert "M23.66: Yahoo Finance provider gate" in project_state
    assert "M23.67: Provider quote breadth closure" in project_state
    assert "M23.68: Final non-live completion audit" in project_state


def test_m22_final_audit_records_partial_goal_verdict_without_reopening_m22() -> None:
    ledger = _read(LEDGER)
    audit = _read(FINAL_AUDIT)

    assert "M22.9 Final non-live parity audit | completed" in ledger
    assert "M23.31 Bank of Canada FX reference | completed" in ledger
    assert "M23.32 Backtest volatility reversion | completed" in ledger
    assert "M23.33 Portfolio report index | completed" in ledger
    assert "M23.34 Finnhub equity quote watchlist | completed" in ledger
    assert "M23.35 Advanced output state-file classification | completed" in ledger
    assert "M23.36 Cboe delayed quote gate | completed" in ledger
    assert "M23.37 FMP quote watchlist | completed" in ledger
    assert "M23.38 Provider acquisition resume contract | completed" in ledger
    assert "M23.39 Backtest data readiness | completed" in ledger
    assert "M23.40 Algo scan readiness | completed" in ledger
    assert "M23.41 News topic/entity map | completed" in ledger
    assert "M23.42 IEX TOPS market data gate | completed" in ledger
    assert "M23.43 Provider gate candidate detail | completed" in ledger
    assert "M23.44 Backtest momentum continuation | completed" in ledger
    assert "M23.45 Portfolio exposure map | completed" in ledger
    assert "M23.46 Command Center action matrix | completed" in ledger
    assert "M23.47 Markets quote snapshot board | completed" in ledger
    assert "M23.48 Command Center preflight matrix | completed" in ledger
    assert "M23.49 TWSE daily quote snapshots | completed" in ledger
    assert "M23.50 Eurostat HICP macro context | completed" in ledger
    assert "M23.51 Provider refresh schedule plan | completed" in ledger
    assert "M23.52 Backtest artifact health matrix | completed" in ledger
    assert "M23.53 OpenFIGI identifier mapping | completed" in ledger
    assert "M23.54 Portfolio report health matrix | completed" in ledger
    assert "M23.55 AI Chat session health matrix | completed" in ledger
    assert "M23.56 Nodes workflow health matrix | completed" in ledger
    assert "M23.57 Code analysis health matrix | completed" in ledger
    assert "M23.58 Quant Lab preview health matrix | completed" in ledger
    assert "M23.59 QuantLib calculation health matrix | completed" in ledger
    assert "M23.60 Nasdaq Data Link provider gate | completed" in ledger
    assert "M23.61 QuantLib implied-volatility calculator | completed" in ledger
    assert "M23.62 Global Command Center drawer | completed" in ledger
    assert "M23.63 Backtest RSI reversion | completed" in ledger
    assert "M23.64 JPX/J-Quants provider gate | completed" in ledger
    assert "M23.65 QuantLib option scenario grid | completed" in ledger
    assert "M23.66 Yahoo Finance provider gate | completed" in ledger
    assert "M23.67 Provider quote breadth closure | completed" in ledger
    assert "M23.68 Final non-live completion audit | completed" in ledger
    assert "docs/planning/M22_FINAL_NON_LIVE_PARITY_AUDIT.md" in ledger
    assert "docs/planning/M23_BANK_OF_CANADA_FX_REFERENCE.md" in ledger
    assert "docs/planning/M23_BACKTEST_VOLATILITY_REVERSION.md" in ledger
    assert "docs/planning/M23_PORTFOLIO_REPORT_INDEX.md" in ledger
    assert "docs/planning/M23_FINNHUB_EQUITY_QUOTE_WATCHLIST.md" in ledger
    assert "docs/planning/M23_ADVANCED_OUTPUT_STATE_FILE_CLASSIFICATION.md" in ledger
    assert "docs/planning/M23_CBOE_DELAYED_QUOTE_GATE.md" in ledger
    assert "docs/planning/M23_FMP_QUOTE_WATCHLIST.md" in ledger
    assert "docs/planning/M23_PROVIDER_ACQUISITION_RESUME_CONTRACT.md" in ledger
    assert "docs/planning/M23_BACKTEST_DATA_READINESS.md" in ledger
    assert "docs/planning/M23_ALGO_SCAN_READINESS.md" in ledger
    assert "docs/planning/M23_NEWS_TOPIC_ENTITY_MAP.md" in ledger
    assert "docs/planning/M23_IEX_TOPS_MARKET_DATA_GATE.md" in ledger
    assert "docs/planning/M23_PROVIDER_GATE_CANDIDATE_DETAIL.md" in ledger
    assert "docs/planning/M23_BACKTEST_MOMENTUM_CONTINUATION.md" in ledger
    assert "docs/planning/M23_PORTFOLIO_EXPOSURE_MAP.md" in ledger
    assert "docs/planning/M23_COMMAND_CENTER_ACTION_MATRIX.md" in ledger
    assert "docs/planning/M23_MARKETS_QUOTE_SNAPSHOT_BOARD.md" in ledger
    assert "docs/planning/M23_COMMAND_CENTER_PREFLIGHT_MATRIX.md" in ledger
    assert "docs/planning/M23_TWSE_QUOTE_SNAPSHOT.md" in ledger
    assert "docs/planning/M23_EUROSTAT_HICP_CONTEXT.md" in ledger
    assert "docs/planning/M23_PROVIDER_REFRESH_SCHEDULE_PLAN.md" in ledger
    assert "docs/planning/M23_BACKTEST_ARTIFACT_HEALTH.md" in ledger
    assert "docs/planning/M23_OPENFIGI_IDENTIFIER_MAPPING.md" in ledger
    assert "docs/planning/M23_PORTFOLIO_REPORT_HEALTH.md" in ledger
    assert "docs/planning/M23_AI_CHAT_SESSION_HEALTH.md" in ledger
    assert "docs/planning/M23_NODES_WORKFLOW_HEALTH.md" in ledger
    assert "docs/planning/M23_CODE_ANALYSIS_HEALTH.md" in ledger
    assert "docs/planning/M23_QUANT_LAB_PREVIEW_HEALTH.md" in ledger
    assert "docs/planning/M23_QUANTLIB_CALCULATION_HEALTH.md" in ledger
    assert "docs/planning/M23_NASDAQ_DATA_LINK_GATE.md" in ledger
    assert "docs/planning/M23_QUANTLIB_IMPLIED_VOL_CALCULATOR.md" in ledger
    assert "docs/planning/M23_GLOBAL_COMMAND_CENTER_DRAWER.md" in ledger
    assert "docs/planning/M23_BACKTEST_RSI_REVERSION.md" in ledger
    assert "docs/planning/M23_JPX_JQUANTS_PROVIDER_GATE.md" in ledger
    assert "docs/planning/M23_QUANTLIB_OPTION_SCENARIO_GRID.md" in ledger
    assert "docs/planning/M23_YAHOO_FINANCE_PROVIDER_GATE.md" in ledger
    assert "docs/planning/M23_PROVIDER_QUOTE_BREADTH_CLOSURE.md" in ledger
    assert "docs/planning/M23_FINAL_NON_LIVE_COMPLETION_AUDIT.md" in ledger
    assert "Goal-completion status from this audit: `partial`." in audit
    assert "M22.1-M22.8" in audit
    for residual in (
        "Broader non-crypto executable quote breadth remains limited",
        "Fresh installed-Fincept observation after M22.8 was not performed",
        "Real execution runtimes remain blocked",
    ):
        assert residual in audit


def test_m23_final_completion_audit_closes_current_non_live_scope() -> None:
    audit = _read(COMPLETION_AUDIT)

    assert "Goal-completion status from this audit: `complete_for_current_non_live_scope`." in audit
    assert "M23.68 Final non-live completion audit" in audit
    assert "Requirement Matrix" in audit
    assert "continue_from_m21_23" in audit
    assert "provider_data_strategy" in audit
    assert "markets_quote_reference_breadth" in audit
    assert "final_non_live_completion_audit" in audit
    assert "No partial or unknown current-scope rows remain" in audit
    for excluded in (
        "live_trading_and_brokerage",
        "payment_subscription_cr_cloud",
        "destructive_artifact_lifecycle",
        "external_runtimes_and_managed_llm",
        "fresh_unrestricted_installed_app_observation",
    ):
        assert excluded in audit
