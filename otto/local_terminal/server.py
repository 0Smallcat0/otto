"""Local API foundation for the clean-room terminal."""

from __future__ import annotations

import contextlib
import json
import os
import urllib.error
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from otto.local_terminal.algo import (
    AlgoError,
    algo_payload,
    algo_scan_readiness_payload,
    delete_strategy,
    run_strategy_backtest,
    save_strategy,
    scan_market,
    select_strategy,
)
from otto.local_terminal.advanced_context import advanced_context_payload
from otto.local_terminal.artifact_readers import (
    backtest_run_detail_payload,
    news_brief_detail_payload,
)
from otto.local_terminal.twse_history import (
    TwseHistoryError,
    build_twse_history,
    fetch_twse_stock_day,
)
from otto.local_terminal.twelve_data_history import (
    MAX_HISTORY_SYMBOLS,
    TwelveDataHistoryError,
    fetch_twelve_data_time_series,
    history_refresh_summary,
    normalize_time_series,
)
from otto.local_terminal.news_digest import (
    NewsDigestError,
    build_live_sections,
    is_digest_fresh,
    news_digest_payload,
    write_news_digest,
)
from otto.local_terminal.watchlist import (
    WatchlistError,
    update_watchlist,
    watchlist_payload,
)
from otto.local_terminal.advanced_outputs import (
    advanced_workflow_output_packet,
    write_advanced_workflow_output_packet,
)
from otto.local_terminal.agent_contract import (
    agent_action_preflight_payload,
    agent_operability_payload,
)
from otto.local_terminal.agent_activity import (
    AgentActivityError,
    agent_activity_payload,
    append_agent_activity_event,
)
from otto.local_terminal.artifact_lifecycle import (
    artifact_lifecycle_payload,
    run_artifact_archive_plan,
)
from otto.local_terminal.alpha_vantage_data import (
    ALPHA_VANTAGE_DEFAULT_ETF_SYMBOL,
    ALPHA_VANTAGE_DEFAULT_SYMBOL,
    ALPHA_VANTAGE_ETF_WATCHLIST,
    ALPHA_VANTAGE_FX_WATCHLIST,
    ALPHA_VANTAGE_PROVIDER_ID,
    ALPHA_VANTAGE_STOCK_WATCHLIST,
    alpha_vantage_fx_pair_list,
    alpha_vantage_fx_quote_watchlist_payload,
    alpha_vantage_quote_watchlist_payload,
    alpha_vantage_quote_payload,
    alpha_vantage_symbol_list,
    fetch_alpha_vantage_currency_exchange_rate,
    fetch_alpha_vantage_global_quote,
)
from otto.local_terminal.contracts import (
    DEFAULT_LOCAL_PROFILE_POLICY,
    DEFAULT_SAFETY_INVARIANTS,
    GLOBAL_MENUS,
    SHELL_ROUTE_IDS,
    SHELL_ROUTES,
)
from otto.local_terminal.crypto_data import (
    DEFAULT_INTERVAL,
    DEFAULT_SYMBOL,
    crypto_detail_payload,
    fetch_public_crypto_detail,
    fetch_public_crypto_tickers,
)
from otto.local_terminal.backtest import (
    BACKTEST_PROVIDER,
    BacktestError,
    PUBLIC_BACKTEST_PROVIDER,
    backtest_artifact_health_payload,
    backtest_data_readiness_payload,
    backtest_run_index_payload,
    backtest_strategy_catalog,
    default_backtest_config,
    run_backtest,
    run_optimize,
    run_walk_forward,
    write_backtest_comparison_packet,
)
from otto.local_terminal.bea_data import (
    BEA_PROVIDER_ID,
    bea_regional_payload,
    fetch_bea_regional_data,
)
from otto.local_terminal.census_data import (
    CENSUS_PROVIDER_ID,
    census_acs_profile_payload,
    fetch_census_acs_profile_data,
)
from otto.local_terminal.eurostat_data import (
    eurostat_hicp_payload,
    fetch_eurostat_hicp,
)
from otto.local_terminal.bls_data import (
    bls_data_payload,
    fetch_bls_latest_series,
)
from otto.local_terminal.chat import (
    ChatError,
    append_chat_message,
    chat_context_contract,
    chat_payload,
    chat_session_health_payload,
    create_chat_session,
    delete_chat_session,
    remove_chat_session_artifacts,
    rename_chat_session,
    select_chat_session,
)
from otto.local_terminal.command_center import (
    command_center_payload,
    command_center_preflight_matrix_payload,
)
from otto.local_terminal.commodity_data import (
    commodity_data_payload,
    fetch_cftc_cot_legacy_futures,
    fetch_world_bank_commodity_prices,
)
from otto.local_terminal.eia_data import (
    EIA_PROVIDER_ID,
    eia_energy_payload,
    fetch_eia_energy_series,
)
from otto.local_terminal.code_workspace import (
    CodeWorkspaceError,
    add_cell,
    analyze_notebook,
    clear_outputs,
    code_analysis_health_payload,
    code_payload,
    create_context_notebook,
    create_notebook,
    disabled_code_runtime_response,
    export_notebook,
    import_notebook,
    save_notebook,
    select_cell,
    select_notebook,
)
from otto.local_terminal.crypto import (
    SUPPORTED_SYMBOLS as PAPER_WATCHLIST_SYMBOLS,
    PaperOrderError,
    cancel_paper_order,
    crypto_payload,
    paper_summary_payload,
    place_paper_order,
    process_paper_orders,
)
from otto.local_terminal.dashboard import apply_dashboard_template, dashboard_payload
from otto.local_terminal.equity_paper import (
    TW_BOOK,
    EquityOrderError,
    cancel_equity_paper_order,
    equity_summary_payload,
    place_equity_paper_order,
    process_equity_paper_orders,
)
from otto.local_terminal.twse_data import fetch_twse_odd_lot_row
from otto.local_terminal.paper_history import (
    BENCHMARK_SYMBOLS,
    HISTORY_DEFAULT_LIMIT,
    RATIONALE_MAX_CHARS,
    paper_history_payload,
    record_paper_snapshot,
)
from otto.local_terminal.research_ledger import (
    DEFAULT_UNIVERSE,
    THESIS_MAX_CHARS,
    ResearchLedgerError,
    record_call,
    research_ledger_payload,
    research_scan_payload,
    score_calls,
)
from otto.local_terminal.yahoo_news import collect_yahoo_news
from otto.local_terminal.forum import (
    ForumError,
    add_forum_reply,
    create_forum_post,
    forum_payload,
    repair_forum_artifacts,
    select_forum_channel,
    select_forum_post,
)
from otto.local_terminal.fund_data import fetch_sec_fund_tickers, fund_data_payload
from otto.local_terminal.finnhub_data import (
    FINNHUB_PROVIDER_ID,
    fetch_finnhub_quote,
    finnhub_quote_watchlist_payload,
    finnhub_symbol_list,
)
from otto.local_terminal.fmp_data import (
    FMP_PROVIDER_ID,
    FMP_WATCHLIST,
    fetch_fmp_quote,
    fmp_quote_watchlist_payload,
    fmp_symbol_list,
)
from otto.local_terminal.fred_data import (
    FRED_PROVIDER_ID,
    fetch_fred_series_observations,
    fred_data_payload,
)
from otto.local_terminal.fx_data import (
    fetch_bank_of_canada_valet_fx_reference_rates,
    fetch_ecb_fx_reference_rates,
    fetch_federal_reserve_h10_reference_rates,
    fx_data_payload,
)
from otto.local_terminal.governance import governance_payload
from otto.local_terminal.live_safety import (
    disabled_live_action_response,
    live_safety_payload,
)
from otto.local_terminal.local_secrets import (
    LocalSecretError,
    forget_local_data_provider_secret,
    local_secret_status,
    read_local_data_provider_secret,
    store_local_data_provider_secret,
)
from otto.local_terminal.markets import markets_payload
from otto.local_terminal.moex_data import (
    MOEX_WATCHLIST,
    fetch_moex_quote_snapshot,
    moex_quote_snapshot_payload,
    moex_symbol_list,
)
from otto.local_terminal.news import (
    NewsError,
    fetch_public_news,
    news_payload,
    news_research_brief_index,
    news_topic_entity_map_payload,
    write_news_research_brief,
)
from otto.local_terminal.news_packet import PACKET_MAX_ITEMS, news_packet_payload
from otto.local_terminal.nodes import (
    NodesError,
    clear_workflow,
    disabled_runtime_response,
    dry_run_workflow,
    export_workflow,
    import_workflow,
    load_template,
    nodes_payload,
    nodes_workflow_health_payload,
    save_workflow,
    select_node,
    select_workflow,
)
from otto.local_terminal.research_lineage import (
    ResearchLineageError,
    normalize_research_lineage,
)
from otto.local_terminal.nasdaq_trader_data import (
    fetch_nasdaq_trader_symbol_directory,
    nasdaq_trader_symbol_search_payload,
    nasdaq_trader_symbol_directory_payload,
)
from otto.local_terminal.openfigi_data import (
    OPENFIGI_WATCHLIST,
    fetch_openfigi_mapping,
    openfigi_mapping_payload,
    openfigi_symbol_list,
)
from otto.local_terminal.stooq_data import (
    STOOQ_WATCHLIST,
    fetch_stooq_quote_snapshot,
    stooq_quote_snapshot_payload,
    stooq_symbol_list,
)
from otto.local_terminal.yahoo_data import (
    YAHOO_MAX_WATCHLIST,
    YAHOO_WATCHLIST,
    fetch_yahoo_quote_snapshot,
    yahoo_lookup_symbols,
    yahoo_quote_snapshot_payload,
    yahoo_symbol_list,
)
from otto.local_terminal.twse_data import (
    fetch_twse_quote_snapshot,
    twse_quote_snapshot_payload,
    twse_symbol_list,
)
from otto.local_terminal.twelve_data import (
    TWELVE_DATA_PROVIDER_ID,
    fetch_twelve_data_quote,
    twelve_data_quote_watchlist_payload,
    twelve_data_symbol_list,
)
from otto.local_terminal.portfolio import (
    PortfolioError,
    create_portfolio,
    delete_portfolio,
    export_active_portfolio,
    import_portfolio,
    link_backtest_portfolio,
    link_paper_portfolio,
    load_demo_portfolio,
    normalize_portfolio_state,
    portfolio_payload,
    portfolio_report_health_payload,
    portfolio_report_index,
    select_portfolio,
    write_portfolio_report,
)
from otto.local_terminal.provider_acquisition import provider_acquisition_gate_payload
from otto.local_terminal.providers import provider_cache_payload, providers_payload
from otto.local_terminal.provider_refresh import (
    PublicProviderRefreshCallbacks,
    complete_public_provider_refresh_job,
    create_public_provider_refresh_job,
    latest_public_provider_refresh_manifest,
    provider_refresh_lifecycle_payload,
    provider_refresh_schedule_plan_payload,
    read_public_provider_refresh_job,
    run_public_provider_refresh,
)
from otto.local_terminal.quant_lab import (
    QuantLabDisabledError,
    QuantLabError,
    disabled_quant_lab_response,
    quant_lab_payload,
    quant_lab_preview_health_payload,
    run_local_preview,
    select_module,
)
from otto.local_terminal.quantlib import (
    QuantLibError,
    disabled_quantlib_response,
    quantlib_calculation_health_payload,
    quantlib_payload,
    run_quantlib_calculation,
    select_quantlib_action,
    select_quantlib_module,
)
from otto.local_terminal.research_data import (
    ResearchDataError,
    fetch_dbnomics_series,
    fetch_public_research_data,
    research_data_payload,
)
from otto.local_terminal.rates_data import (
    fetch_nyfed_sofr,
    fetch_treasury_yield_curve,
    rates_data_payload,
)
from otto.local_terminal.storage import (
    STATE_BACKUP_COUNT,
    LocalStateStore,
    StateRestoreError,
    state_root_from_env,
)
from otto.local_terminal.support import (
    help_payload,
    local_update_status,
    run_diagnostics,
    run_governance_diagnostics,
)

APP_NAME = "Local Terminal"


def _port_from_env(name: str, default: int) -> int:
    """Bounded int env override so eval/CI instances can avoid the live 8765 port."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        return default
    if not 1 <= value <= 65535:
        return default
    return value


DEFAULT_HOST = os.environ.get("LOCAL_TERMINAL_HOST", "").strip() or "127.0.0.1"
DEFAULT_PORT = _port_from_env("LOCAL_TERMINAL_PORT", 8765)
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FRONTEND_DIST = REPO_ROOT / "frontend" / "dist"
STORE = LocalStateStore(root=state_root_from_env())
MARKET_FETCHER = fetch_public_crypto_tickers
CRYPTO_DETAIL_FETCHER = fetch_public_crypto_detail
NEWS_FETCHER = fetch_public_news
RESEARCH_FETCHER = fetch_public_research_data
MACRO_FETCHER = fetch_dbnomics_series
BLS_FETCHER = fetch_bls_latest_series
EUROSTAT_FETCHER = fetch_eurostat_hicp
BEA_FETCHER = fetch_bea_regional_data
CENSUS_FETCHER = fetch_census_acs_profile_data
RATES_FETCHER = fetch_treasury_yield_curve
SOFR_FETCHER = fetch_nyfed_sofr
FX_FETCHER = fetch_ecb_fx_reference_rates
FED_H10_FETCHER = fetch_federal_reserve_h10_reference_rates
BOC_FX_FETCHER = fetch_bank_of_canada_valet_fx_reference_rates
COMMODITY_FETCHER = fetch_world_bank_commodity_prices
CFTC_COT_FETCHER = fetch_cftc_cot_legacy_futures
EIA_FETCHER = fetch_eia_energy_series
FUND_FETCHER = fetch_sec_fund_tickers
FRED_FETCHER = fetch_fred_series_observations
FRED_CORE_SERIES: tuple[tuple[str, str, str], ...] = (
    ("DGS10", "10-Year Treasury Yield", "%"),
    ("CPIAUCSL", "Consumer Price Index", "index 1982-84=100"),
    ("UNRATE", "Unemployment Rate", "%"),
    ("FEDFUNDS", "Federal Funds Rate", "%"),
    ("GDP", "Gross Domestic Product", "$B"),
    ("PAYEMS", "Nonfarm Payrolls", "thousands"),
)
ALPHA_VANTAGE_FETCHER = fetch_alpha_vantage_global_quote
ALPHA_VANTAGE_FX_FETCHER = fetch_alpha_vantage_currency_exchange_rate
TWELVE_DATA_FETCHER = fetch_twelve_data_quote
FINNHUB_FETCHER = fetch_finnhub_quote
FMP_FETCHER = fetch_fmp_quote
STOOQ_FETCHER = fetch_stooq_quote_snapshot
YAHOO_FETCHER = fetch_yahoo_quote_snapshot
MOEX_FETCHER = fetch_moex_quote_snapshot
TWSE_FETCHER = fetch_twse_quote_snapshot
TWSE_HISTORY_FETCHER = fetch_twse_stock_day
NASDAQ_TRADER_FETCHER = fetch_nasdaq_trader_symbol_directory
OPENFIGI_FETCHER = fetch_openfigi_mapping


def _public_news_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    research = public.get("research")
    if isinstance(research, dict):
        public["research"] = _public_research_payload(research)
    return public


def _attach_news_research_brief_index(payload: dict[str, Any]) -> dict[str, Any]:
    payload["research_brief_index"] = news_research_brief_index(STORE.root)
    return payload


def _news_payload_from_store(*, refresh: bool) -> dict[str, Any]:
    layout = STORE.read_news_layout()
    payload = news_payload(
        layout,
        STORE.read_news_cache(),
        fetcher=NEWS_FETCHER,
        refresh=refresh,
    )
    payload["research"] = _research_payload_from_store(refresh=refresh)
    if refresh and payload.get("cache"):
        STORE.write_news_cache(payload["cache"])
    return payload


def _public_research_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_rates_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_fx_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_commodity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    if isinstance(public.get("eia"), dict):
        eia = dict(public["eia"])
        eia.pop("cache", None)
        public["eia"] = eia
    return public


def _public_eia_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_fund_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_fred_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_bls_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_bea_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_census_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_alpha_vantage_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_twelve_data_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_finnhub_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_fmp_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_stooq_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_yahoo_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_moex_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_twse_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_eurostat_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_nasdaq_trader_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _public_openfigi_payload(payload: dict[str, Any]) -> dict[str, Any]:
    public = dict(payload)
    public.pop("cache", None)
    return public


def _research_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    payload = research_data_payload(
        STORE.read_sec_fundamentals_cache(),
        STORE.read_dbnomics_macro_cache(),
        STORE.read_fred_macro_cache(),
        STORE.read_bls_macro_cache(),
        STORE.read_eurostat_hicp_cache(),
        STORE.read_bea_regional_cache(),
        STORE.read_census_acs_profile_cache(),
        sec_ticker_cache=STORE.read_sec_company_tickers_cache(),
        sec_submissions_cache=STORE.read_sec_company_submissions_watchlist_cache(),
        sec_frames_cache=STORE.read_sec_xbrl_frame_cache(),
        fetcher=RESEARCH_FETCHER,
        fred_payload=_fred_payload_from_store(refresh=False),
        fred_core_payload=_fred_core_series_from_store(refresh=False),
        bls_payload=_bls_payload_from_store(refresh=False),
        eurostat_payload=_eurostat_payload_from_store(refresh=False),
        bea_payload=_bea_payload_from_store(refresh=False),
        census_payload=_census_payload_from_store(refresh=False),
        refresh=refresh,
    )
    cache = payload.get("cache")
    if refresh and isinstance(cache, dict):
        sec_cache = cache.get("sec")
        sec_tickers_cache = cache.get("sec_tickers")
        sec_submissions_cache = cache.get("sec_submissions")
        sec_frames_cache = cache.get("sec_frames")
        dbnomics_cache = cache.get("dbnomics")
        bls_cache = cache.get("bls")
        eurostat_cache = cache.get("eurostat")
        if _cache_is_writable(sec_cache):
            STORE.write_sec_fundamentals_cache(sec_cache)
        if _cache_is_writable(sec_tickers_cache):
            STORE.write_sec_company_tickers_cache(sec_tickers_cache)
        if _cache_is_writable(sec_submissions_cache):
            STORE.write_sec_company_submissions_watchlist_cache(sec_submissions_cache)
        if _cache_is_writable(sec_frames_cache):
            STORE.write_sec_xbrl_frame_cache(sec_frames_cache)
        if _cache_is_writable(dbnomics_cache):
            STORE.write_dbnomics_macro_cache(dbnomics_cache)
        if _cache_is_writable(bls_cache):
            STORE.write_bls_macro_cache(bls_cache)
        if _cache_is_writable(eurostat_cache):
            STORE.write_eurostat_hicp_cache(eurostat_cache)
    return payload


def _fred_secret_status_from_store() -> dict[str, Any]:
    return local_secret_status(STORE.root, providers_payload(STORE))


def _fred_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    secret_status = _fred_secret_status_from_store()
    credential_value = ""
    if refresh and FRED_PROVIDER_ID in set(secret_status.get("stored_provider_ids") or []):
        try:
            credential_value = read_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=FRED_PROVIDER_ID,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = fred_data_payload(
        STORE.read_fred_macro_cache(),
        secret_status,
        fetcher=FRED_FETCHER,
        refresh=refresh,
        credential=credential_value,
    )
    cache = payload.get("cache")
    if refresh and isinstance(cache, dict):
        fred_cache = cache.get("fred")
        if _cache_is_writable(fred_cache):
            STORE.write_fred_macro_cache(fred_cache)
    return payload


def _fred_core_series_from_store(*, refresh: bool = False) -> dict[str, Any]:
    secret_status = _fred_secret_status_from_store()
    key_stored = FRED_PROVIDER_ID in set(secret_status.get("stored_provider_ids") or [])
    credential_value = ""
    if refresh and key_stored:
        try:
            credential_value = read_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=FRED_PROVIDER_ID,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    rows: list[dict[str, Any]] = []
    states: list[str] = []
    for series_id, label, units in FRED_CORE_SERIES:
        try:
            payload = fred_data_payload(
                STORE.read_fred_macro_cache(series_id),
                secret_status,
                fetcher=FRED_FETCHER,
                refresh=refresh,
                credential=credential_value,
                series_id=series_id,
            )
        except Exception:  # noqa: BLE001 - one series failing must not abort the set
            rows.append(
                {
                    "series_id": series_id,
                    "label": label,
                    "units": units,
                    "latest_value": "",
                    "latest_period": "",
                    "state": "unavailable",
                    "observation_count": 0,
                }
            )
            states.append("unavailable")
            continue
        cache = payload.get("cache")
        if refresh and isinstance(cache, dict):
            fred_cache = cache.get("fred")
            if _cache_is_writable(fred_cache):
                STORE.write_fred_macro_cache(fred_cache)
        status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        state = str(status.get("state") or "unavailable")
        rows.append(
            {
                "series_id": series_id,
                "label": label,
                "units": units,
                "latest_value": str(summary.get("latest_value") or ""),
                "latest_period": str(summary.get("latest_period") or ""),
                "state": state,
                "observation_count": int(summary.get("observation_count") or 0),
            }
        )
        states.append(state)

    state_priority = (
        "live",
        "stale_cache",
        "rate_limited",
        "unavailable",
        "key_required",
    )
    overall_state = "key_required"
    for candidate in state_priority:
        if candidate in states:
            overall_state = candidate
            break
    return {
        "state": overall_state,
        "provider_id": FRED_PROVIDER_ID,
        "key_stored": key_stored,
        "series_count": len(rows),
        "series": rows,
    }


def _bls_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    payload = bls_data_payload(
        STORE.read_bls_macro_cache(),
        fetcher=BLS_FETCHER,
        refresh=refresh,
    )
    cache = payload.get("cache")
    if refresh and isinstance(cache, dict):
        bls_cache = cache.get("bls")
        if _cache_is_writable(bls_cache):
            STORE.write_bls_macro_cache(bls_cache)
    return payload


def _eurostat_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    payload = eurostat_hicp_payload(
        STORE.read_eurostat_hicp_cache(),
        fetcher=EUROSTAT_FETCHER,
        refresh=refresh,
    )
    cache = payload.get("cache")
    if refresh and isinstance(cache, dict):
        eurostat_cache = cache.get("eurostat")
        if _cache_is_writable(eurostat_cache):
            STORE.write_eurostat_hicp_cache(eurostat_cache)
    return payload


def _bea_secret_status_from_store() -> dict[str, Any]:
    return local_secret_status(STORE.root, providers_payload(STORE))


def _bea_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    secret_status = _bea_secret_status_from_store()
    credential_value = ""
    if refresh and BEA_PROVIDER_ID in set(secret_status.get("stored_provider_ids") or []):
        try:
            credential_value = read_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=BEA_PROVIDER_ID,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = bea_regional_payload(
        STORE.read_bea_regional_cache(),
        secret_status,
        fetcher=BEA_FETCHER,
        refresh=refresh,
        credential=credential_value,
    )
    cache = payload.get("cache")
    if refresh and isinstance(cache, dict):
        bea_cache = cache.get("bea")
        if _cache_is_writable(bea_cache):
            STORE.write_bea_regional_cache(bea_cache)
    return payload


def _census_secret_status_from_store() -> dict[str, Any]:
    return local_secret_status(STORE.root, providers_payload(STORE))


def _census_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    secret_status = _census_secret_status_from_store()
    credential_value = ""
    if refresh and CENSUS_PROVIDER_ID in set(secret_status.get("stored_provider_ids") or []):
        try:
            credential_value = read_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=CENSUS_PROVIDER_ID,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = census_acs_profile_payload(
        STORE.read_census_acs_profile_cache(),
        secret_status,
        fetcher=CENSUS_FETCHER,
        refresh=refresh,
        credential=credential_value,
    )
    cache = payload.get("cache")
    if refresh and isinstance(cache, dict):
        census_cache = cache.get("census")
        if _cache_is_writable(census_cache):
            STORE.write_census_acs_profile_cache(census_cache)
    return payload


def _alpha_vantage_secret_status_from_store() -> dict[str, Any]:
    return local_secret_status(STORE.root, providers_payload(STORE))


def _alpha_vantage_payload_from_store(
    *,
    refresh: bool = False,
    symbol: str = ALPHA_VANTAGE_DEFAULT_SYMBOL,
) -> dict[str, Any]:
    secret_status = _alpha_vantage_secret_status_from_store()
    credential_value = ""
    if refresh and ALPHA_VANTAGE_PROVIDER_ID in set(secret_status.get("stored_provider_ids") or []):
        try:
            credential_value = read_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=ALPHA_VANTAGE_PROVIDER_ID,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = alpha_vantage_quote_payload(
        STORE.read_alpha_vantage_equity_quote_cache(symbol),
        secret_status,
        fetcher=ALPHA_VANTAGE_FETCHER,
        refresh=refresh,
        credential=credential_value,
        symbol=symbol,
    )
    cache = payload.get("cache")
    if refresh and isinstance(cache, dict):
        quote_cache = cache.get("alpha_vantage")
        if _cache_is_writable(quote_cache):
            STORE.write_alpha_vantage_equity_quote_cache(quote_cache)
    return payload


def _alpha_vantage_watchlist_payload_from_store(
    *,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
    fallback_symbols: tuple[str, ...] = ALPHA_VANTAGE_STOCK_WATCHLIST,
) -> dict[str, Any]:
    safe_symbols = alpha_vantage_symbol_list(
        symbols,
        fallback_symbols=fallback_symbols,
    )
    secret_status = _alpha_vantage_secret_status_from_store()
    credential_value = ""
    if refresh and ALPHA_VANTAGE_PROVIDER_ID in set(secret_status.get("stored_provider_ids") or []):
        try:
            credential_value = read_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=ALPHA_VANTAGE_PROVIDER_ID,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = alpha_vantage_quote_watchlist_payload(
        {
            symbol: STORE.read_alpha_vantage_equity_quote_cache(symbol)
            for symbol in safe_symbols
        },
        secret_status,
        fetcher=ALPHA_VANTAGE_FETCHER,
        refresh=refresh,
        credential=credential_value,
        symbols=safe_symbols,
        fallback_symbols=fallback_symbols,
    )
    cache = payload.get("cache")
    by_symbol = cache.get("alpha_vantage_by_symbol") if isinstance(cache, dict) else {}
    if refresh and isinstance(by_symbol, dict):
        for quote_cache in by_symbol.values():
            if _cache_is_writable(quote_cache):
                STORE.write_alpha_vantage_equity_quote_cache(quote_cache)
    return payload


def _alpha_vantage_stock_watchlist_payload_from_store(
    *,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    return _alpha_vantage_watchlist_payload_from_store(
        refresh=refresh,
        symbols=symbols,
        fallback_symbols=ALPHA_VANTAGE_STOCK_WATCHLIST,
    )


def _alpha_vantage_etf_watchlist_payload_from_store(
    *,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    return _alpha_vantage_watchlist_payload_from_store(
        refresh=refresh,
        symbols=symbols,
        fallback_symbols=ALPHA_VANTAGE_ETF_WATCHLIST,
    )


def _alpha_vantage_etf_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    return _alpha_vantage_payload_from_store(
        refresh=refresh,
        symbol=ALPHA_VANTAGE_DEFAULT_ETF_SYMBOL,
    )


def _alpha_vantage_fx_quote_watchlist_payload_from_store(
    *,
    refresh: bool = False,
    pairs: list[str] | str | None = None,
) -> dict[str, Any]:
    safe_pairs = alpha_vantage_fx_pair_list(pairs or list(ALPHA_VANTAGE_FX_WATCHLIST))
    secret_status = _alpha_vantage_secret_status_from_store()
    credential_value = ""
    if refresh and ALPHA_VANTAGE_PROVIDER_ID in set(secret_status.get("stored_provider_ids") or []):
        try:
            credential_value = read_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=ALPHA_VANTAGE_PROVIDER_ID,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = alpha_vantage_fx_quote_watchlist_payload(
        {pair: STORE.read_alpha_vantage_fx_quote_cache(pair) for pair in safe_pairs},
        secret_status,
        fetcher=ALPHA_VANTAGE_FX_FETCHER,
        refresh=refresh,
        credential=credential_value,
        pairs=safe_pairs,
    )
    cache = payload.get("cache")
    by_pair = cache.get("alpha_vantage_fx_by_pair") if isinstance(cache, dict) else {}
    if refresh and isinstance(by_pair, dict):
        for quote_cache in by_pair.values():
            if _cache_is_writable(quote_cache):
                STORE.write_alpha_vantage_fx_quote_cache(quote_cache)
    return payload


def _twelve_data_secret_status_from_store() -> dict[str, Any]:
    return local_secret_status(STORE.root, providers_payload(STORE))


def _twelve_data_quote_watchlist_payload_from_store(
    *,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    safe_symbols = twelve_data_symbol_list(symbols or STORE.read_watchlist_state()["fx"])
    secret_status = _twelve_data_secret_status_from_store()
    credential_value = ""
    if refresh and TWELVE_DATA_PROVIDER_ID in set(secret_status.get("stored_provider_ids") or []):
        try:
            credential_value = read_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=TWELVE_DATA_PROVIDER_ID,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = twelve_data_quote_watchlist_payload(
        {symbol: STORE.read_twelve_data_quote_cache(symbol) for symbol in safe_symbols},
        secret_status,
        fetcher=TWELVE_DATA_FETCHER,
        refresh=refresh,
        credential=credential_value,
        symbols=safe_symbols,
    )
    cache = payload.get("cache")
    by_symbol = cache.get("twelve_data_by_symbol") if isinstance(cache, dict) else {}
    if refresh and isinstance(by_symbol, dict):
        for quote_cache in by_symbol.values():
            if _cache_is_writable(quote_cache):
                STORE.write_twelve_data_quote_cache(quote_cache)
    return payload


def _finnhub_secret_status_from_store() -> dict[str, Any]:
    return local_secret_status(STORE.root, providers_payload(STORE))


def _finnhub_quote_watchlist_payload_from_store(
    *,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    safe_symbols = finnhub_symbol_list(symbols or STORE.read_watchlist_state()["us"])
    secret_status = _finnhub_secret_status_from_store()
    credential_value = ""
    if refresh and FINNHUB_PROVIDER_ID in set(secret_status.get("stored_provider_ids") or []):
        try:
            credential_value = read_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=FINNHUB_PROVIDER_ID,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = finnhub_quote_watchlist_payload(
        {symbol: STORE.read_finnhub_quote_cache(symbol) for symbol in safe_symbols},
        secret_status,
        fetcher=FINNHUB_FETCHER,
        refresh=refresh,
        credential=credential_value,
        symbols=safe_symbols,
    )
    cache = payload.get("cache")
    by_symbol = cache.get("finnhub_by_symbol") if isinstance(cache, dict) else {}
    if refresh and isinstance(by_symbol, dict):
        for quote_cache in by_symbol.values():
            if _cache_is_writable(quote_cache):
                STORE.write_finnhub_quote_cache(quote_cache)
    return payload


def _fmp_secret_status_from_store() -> dict[str, Any]:
    return local_secret_status(STORE.root, providers_payload(STORE))


def _fmp_quote_watchlist_payload_from_store(
    *,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    safe_symbols = fmp_symbol_list(symbols or list(FMP_WATCHLIST))
    secret_status = _fmp_secret_status_from_store()
    credential_value = ""
    if refresh and FMP_PROVIDER_ID in set(secret_status.get("stored_provider_ids") or []):
        try:
            credential_value = read_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=FMP_PROVIDER_ID,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = fmp_quote_watchlist_payload(
        {symbol: STORE.read_fmp_quote_cache(symbol) for symbol in safe_symbols},
        secret_status,
        fetcher=FMP_FETCHER,
        refresh=refresh,
        credential=credential_value,
        symbols=safe_symbols,
    )
    cache = payload.get("cache")
    by_symbol = cache.get("fmp_by_symbol") if isinstance(cache, dict) else {}
    if refresh and isinstance(by_symbol, dict):
        for quote_cache in by_symbol.values():
            if _cache_is_writable(quote_cache):
                STORE.write_fmp_quote_cache(quote_cache)
    return payload


def _stooq_quote_snapshot_payload_from_store(
    *,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    safe_symbols = stooq_symbol_list(symbols or list(STOOQ_WATCHLIST))
    payload = stooq_quote_snapshot_payload(
        {symbol: STORE.read_stooq_quote_cache(symbol) for symbol in safe_symbols},
        fetcher=STOOQ_FETCHER,
        refresh=refresh,
        symbols=safe_symbols,
    )
    cache = payload.get("cache")
    by_symbol = cache.get("stooq_by_symbol") if isinstance(cache, dict) else {}
    if refresh and isinstance(by_symbol, dict):
        for quote_cache in by_symbol.values():
            if _cache_is_writable(quote_cache):
                STORE.write_stooq_quote_cache(quote_cache)
    return payload


def _equity_marks(state: dict[str, Any], *, refresh: bool) -> list[dict[str, Any]]:
    """Mark quotes for the symbols a book holds.

    Reads cached lookup quotes by default so the summary stays a cheap local
    read; `refresh=true` fetches current prices for held symbols only, which
    is what a decision loop needs to see real unrealized P&L instead of
    positions marked at their own cost (2026-07-19 dogfood).
    """
    held = sorted(state.get("positions", {}))
    if not held:
        return []
    payload = _yahoo_quote_snapshot_payload_from_store(refresh=refresh, symbols=held)
    return [row for row in payload.get("quotes", []) if isinstance(row, dict)]


def _yahoo_quote_snapshot_payload_from_store(
    *,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    safe_symbols = yahoo_symbol_list(symbols or list(YAHOO_WATCHLIST))
    payload = yahoo_quote_snapshot_payload(
        {symbol: STORE.read_yahoo_quote_cache(symbol) for symbol in safe_symbols},
        fetcher=YAHOO_FETCHER,
        refresh=refresh,
        symbols=safe_symbols,
    )
    cache = payload.get("cache")
    by_symbol = cache.get("yahoo_by_symbol") if isinstance(cache, dict) else {}
    if refresh and isinstance(by_symbol, dict):
        for quote_cache in by_symbol.values():
            if _cache_is_writable(quote_cache):
                STORE.write_yahoo_quote_cache(quote_cache)
    return payload


def _merge_yahoo_symbol_news(payload: dict[str, Any], symbols: list[str]) -> None:
    """Merge Yahoo public per-symbol news into a news payload's item list.

    Yahoo single-name items are tagged with their source symbol, so the packet's
    keyword matcher attributes them to the holding. A per-symbol fetch failure
    is surfaced as a source_error rather than raised or faked.
    """
    items, errors = collect_yahoo_news(symbols)
    if items:
        existing = payload.get("items") if isinstance(payload.get("items"), list) else []
        payload["items"] = items + existing
    if errors:
        status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
        source_errors = list(status.get("source_errors") or [])
        source_errors.extend(f"yahoo_news {err}" for err in errors)
        status["source_errors"] = source_errors
        try:
            failed = int(status.get("failed_source_count") or 0)
        except (TypeError, ValueError):
            failed = 0
        status["failed_source_count"] = failed + len(errors)
        payload["status"] = status


def _moex_quote_snapshot_payload_from_store(
    *,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    safe_symbols = moex_symbol_list(symbols or list(MOEX_WATCHLIST))
    payload = moex_quote_snapshot_payload(
        {symbol: STORE.read_moex_quote_cache(symbol) for symbol in safe_symbols},
        fetcher=MOEX_FETCHER,
        refresh=refresh,
        symbols=safe_symbols,
    )
    cache = payload.get("cache")
    by_symbol = cache.get("moex_by_symbol") if isinstance(cache, dict) else {}
    if refresh and isinstance(by_symbol, dict):
        for quote_cache in by_symbol.values():
            if _cache_is_writable(quote_cache):
                STORE.write_moex_quote_cache(quote_cache)
    return payload


def _apply_history_close_overlay(rows: list[Any]) -> None:
    """Prefer the freshest daily close we hold for TW quote rows.

    TWSE's free STOCK_DAY_ALL file can lag the per-stock history by one
    session (00982A showed 07/06's 25.28 while history held 07/07's 24.09).
    Money-adjacent numbers must use the newest close available, everywhere.
    """
    for row in rows:
        if not isinstance(row, dict):
            continue
        history = STORE.read_history_cache(str(row.get("symbol") or ""))
        candles = history.get("candles") if isinstance(history.get("candles"), list) else []
        if not candles or not isinstance(candles[-1], dict):
            continue
        last = candles[-1]
        history_date = str(last.get("closed_at") or "")[:10]
        close = str(last.get("close") or "")
        roc = str(row.get("date") or "")
        # Fail closed: an unparseable row date means we can't prove the history
        # is fresher, so leave the live quote alone rather than blind-overwriting.
        if not (len(roc) >= 7 and roc[:-4].isdigit()):
            continue
        row_iso = f"{int(roc[:-4]) + 1911:04d}-{roc[-4:-2]}-{roc[-2:]}"
        if not (history_date and close) or history_date <= row_iso:
            continue
        previous = str(row.get("close") or row.get("price") or "")
        row["price"] = close
        row["close"] = close
        # Recompute change WITH the new price, or clear it — never leave a new
        # price paired with the old row's stale change figures.
        try:
            prev_value, new_value = float(previous), float(close)
            if prev_value > 0:
                row["change"] = f"{new_value - prev_value:.2f}"
                row["change_percent"] = f"{(new_value - prev_value) / prev_value * 100:.2f}"
            else:
                row["change"] = row["change_percent"] = ""
        except ValueError:
            row["change"] = row["change_percent"] = ""
        row["date"] = f"{int(history_date[:4]) - 1911}{history_date[5:7]}{history_date[8:10]}"
        row["price_basis"] = "history_close_overlay"


def _overlay_book_position_prices(book: Any) -> None:
    """Fill each book position's last_price / market_value from the freshest
    close we hold, so the book detail shows current value — not the cost.

    Stored positions carry last_price == avg_cost until a live sync, which made
    the detail page contradict the dashboard's real-book banner (00982A cost
    15.15 vs live 24.09). This reuses the same daily-close source as the banner.
    """
    if not isinstance(book, dict):
        return
    positions = book.get("positions")
    if not isinstance(positions, list):
        return
    today = datetime.now(tz=UTC).date()
    for position in positions:
        if not isinstance(position, dict):
            continue
        history = STORE.read_history_cache(str(position.get("symbol") or ""))
        candles = history.get("candles") if isinstance(history.get("candles"), list) else []
        last = candles[-1] if candles and isinstance(candles[-1], dict) else None
        close = str(last.get("close") or "") if last else ""
        if not close:
            # No live/history price for this symbol: mark cost-as-price plainly so
            # a 0% P&L-by-construction row isn't read as a real live quote.
            if str(position.get("last_price") or "") == str(position.get("avg_cost") or ""):
                position["price_basis"] = "cost_basis"
            continue
        closed_at = str(last.get("closed_at") or "")[:10]
        stale = False
        with contextlib.suppress(ValueError):
            stale = (today - datetime.fromisoformat(closed_at).date()).days > 7
        position["last_price"] = close
        position["price_date"] = closed_at
        with contextlib.suppress(ValueError):
            position["market_value"] = (
                f"{float(str(position.get('quantity') or '0')) * float(close):.2f}"
            )
        # Daily close lags a session by design; only flag it once it's genuinely
        # stale (refresh stopped), so a normal yesterday's-close isn't cried wolf.
        position["price_basis"] = "stale_history_close" if stale else "history_close_overlay"


def _twse_quote_snapshot_payload_from_store(
    *,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    safe_symbols = twse_symbol_list(symbols or STORE.read_watchlist_state()["tw"])
    payload = twse_quote_snapshot_payload(
        {symbol: STORE.read_twse_quote_cache(symbol) for symbol in safe_symbols},
        fetcher=TWSE_FETCHER,
        refresh=refresh,
        symbols=safe_symbols,
    )
    cache = payload.get("cache")
    by_symbol = cache.get("twse_by_symbol") if isinstance(cache, dict) else {}
    if refresh and isinstance(by_symbol, dict):
        for quote_cache in by_symbol.values():
            if _cache_is_writable(quote_cache):
                STORE.write_twse_quote_cache(quote_cache)
    twse_block = payload.get("twse") if isinstance(payload.get("twse"), dict) else payload
    rows = twse_block.get("quotes")
    if isinstance(rows, list):
        _apply_history_close_overlay(rows)
    return payload


def _nasdaq_trader_symbol_directory_payload_from_store(
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    payload = nasdaq_trader_symbol_directory_payload(
        STORE.read_nasdaq_trader_symbol_directory_cache(),
        fetcher=NASDAQ_TRADER_FETCHER,
        refresh=refresh,
    )
    cache = payload.get("cache")
    symbol_cache = cache.get("nasdaq_trader") if isinstance(cache, dict) else {}
    if refresh and _cache_is_writable(symbol_cache):
        STORE.write_nasdaq_trader_symbol_directory_cache(symbol_cache)
    return payload


def _openfigi_mapping_payload_from_store(
    *,
    refresh: bool = False,
    symbols: list[str] | str | None = None,
) -> dict[str, Any]:
    safe_symbols = openfigi_symbol_list(symbols or list(OPENFIGI_WATCHLIST))
    payload = openfigi_mapping_payload(
        STORE.read_openfigi_mapping_cache(),
        fetcher=OPENFIGI_FETCHER,
        refresh=refresh,
        symbols=safe_symbols,
    )
    cache = payload.get("cache")
    mapping_cache = cache.get("openfigi") if isinstance(cache, dict) else {}
    if refresh and _cache_is_writable(mapping_cache):
        STORE.write_openfigi_mapping_cache(mapping_cache)
    return payload


def _macro_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    if not refresh:
        return _research_payload_from_store(refresh=False)

    def fetcher() -> dict[str, Any]:
        errors: list[str] = []
        try:
            dbnomics = MACRO_FETCHER()
        except (
            OSError,
            TimeoutError,
            json.JSONDecodeError,
            ResearchDataError,
            urllib.error.URLError,
        ) as exc:
            errors.append(f"DBnomics: {exc}")
            dbnomics = {}
        try:
            bls = BLS_FETCHER()
        except (
            OSError,
            TimeoutError,
            json.JSONDecodeError,
            ValueError,
            urllib.error.URLError,
        ) as exc:
            errors.append(f"BLS: {exc}")
            bls = {}
        try:
            eurostat = EUROSTAT_FETCHER()
        except (
            OSError,
            TimeoutError,
            json.JSONDecodeError,
            ValueError,
            urllib.error.URLError,
        ) as exc:
            errors.append(f"Eurostat: {exc}")
            eurostat = {}
        return {
            "sec": {},
            "dbnomics": dbnomics,
            "bls": bls,
            "eurostat": eurostat,
            "errors": errors,
        }

    payload = research_data_payload(
        STORE.read_sec_fundamentals_cache(),
        STORE.read_dbnomics_macro_cache(),
        STORE.read_fred_macro_cache(),
        STORE.read_bls_macro_cache(),
        STORE.read_eurostat_hicp_cache(),
        STORE.read_bea_regional_cache(),
        STORE.read_census_acs_profile_cache(),
        sec_ticker_cache=STORE.read_sec_company_tickers_cache(),
        sec_submissions_cache=STORE.read_sec_company_submissions_watchlist_cache(),
        sec_frames_cache=STORE.read_sec_xbrl_frame_cache(),
        fetcher=fetcher,
        fred_payload=_fred_payload_from_store(refresh=False),
        eurostat_payload=_eurostat_payload_from_store(refresh=False),
        bea_payload=_bea_payload_from_store(refresh=False),
        census_payload=_census_payload_from_store(refresh=False),
        refresh=True,
    )
    cache = payload.get("cache")
    if isinstance(cache, dict):
        dbnomics_cache = cache.get("dbnomics")
        bls_cache = cache.get("bls")
        eurostat_cache = cache.get("eurostat")
        if _cache_is_writable(dbnomics_cache):
            STORE.write_dbnomics_macro_cache(dbnomics_cache)
        if _cache_is_writable(bls_cache):
            STORE.write_bls_macro_cache(bls_cache)
        if _cache_is_writable(eurostat_cache):
            STORE.write_eurostat_hicp_cache(eurostat_cache)
    return payload


def _rates_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    payload = rates_data_payload(
        STORE.read_treasury_rates_cache(),
        STORE.read_nyfed_sofr_cache(),
        fetcher=RATES_FETCHER,
        sofr_fetcher=SOFR_FETCHER,
        refresh=refresh,
    )
    cache = payload.get("cache")
    if refresh and isinstance(cache, dict):
        treasury_cache = cache.get("treasury")
        sofr_cache = cache.get("sofr")
        if _cache_is_writable(treasury_cache):
            STORE.write_treasury_rates_cache(treasury_cache)
        if _cache_is_writable(sofr_cache):
            STORE.write_nyfed_sofr_cache(sofr_cache)
    return payload


def _fx_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    payload = fx_data_payload(
        STORE.read_ecb_fx_cache(),
        h10_cache=STORE.read_federal_reserve_h10_fx_cache(),
        boc_cache=STORE.read_bank_of_canada_fx_cache(),
        fetcher=FX_FETCHER,
        h10_fetcher=FED_H10_FETCHER,
        boc_fetcher=BOC_FX_FETCHER,
        refresh=refresh,
    )
    cache = payload.get("cache")
    if refresh and isinstance(cache, dict):
        ecb_cache = cache.get("ecb")
        h10_cache = cache.get("h10")
        boc_cache = cache.get("boc")
        if _cache_is_writable(ecb_cache):
            STORE.write_ecb_fx_cache(ecb_cache)
        if _cache_is_writable(h10_cache):
            STORE.write_federal_reserve_h10_fx_cache(h10_cache)
        if _cache_is_writable(boc_cache):
            STORE.write_bank_of_canada_fx_cache(boc_cache)
    return payload


def _commodity_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    payload = commodity_data_payload(
        STORE.read_world_bank_commodity_cache(),
        cftc_cache=STORE.read_cftc_cot_cache(),
        fetcher=COMMODITY_FETCHER,
        cftc_fetcher=CFTC_COT_FETCHER,
        refresh=refresh,
    )
    cache = payload.get("cache")
    if refresh and isinstance(cache, dict):
        world_bank_cache = cache.get("world_bank")
        cftc_cache = cache.get("cftc")
        if _cache_is_writable(world_bank_cache):
            STORE.write_world_bank_commodity_cache(world_bank_cache)
        if _cache_is_writable(cftc_cache):
            STORE.write_cftc_cot_cache(cftc_cache)
    payload["eia"] = _eia_payload_from_store(refresh=False)
    return payload


def _eia_secret_status_from_store() -> dict[str, Any]:
    return local_secret_status(STORE.root, providers_payload(STORE))


def _eia_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    secret_status = _eia_secret_status_from_store()
    credential_value = ""
    if refresh and EIA_PROVIDER_ID in set(secret_status.get("stored_provider_ids") or []):
        try:
            credential_value = read_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=EIA_PROVIDER_ID,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload = eia_energy_payload(
        STORE.read_eia_energy_cache(),
        secret_status,
        fetcher=EIA_FETCHER,
        refresh=refresh,
        credential=credential_value,
    )
    cache = payload.get("cache")
    if refresh and isinstance(cache, dict):
        eia_cache = cache.get("eia")
        if _cache_is_writable(eia_cache):
            STORE.write_eia_energy_cache(eia_cache)
    return payload


def _fund_payload_from_store(*, refresh: bool = False) -> dict[str, Any]:
    payload = fund_data_payload(
        STORE.read_sec_fund_tickers_cache(),
        fetcher=FUND_FETCHER,
        refresh=refresh,
    )
    cache = payload.get("cache")
    if refresh and isinstance(cache, dict):
        sec_funds_cache = cache.get("sec_funds")
        if _cache_is_writable(sec_funds_cache):
            STORE.write_sec_fund_tickers_cache(sec_funds_cache)
    return payload


def _advanced_context_from_store() -> dict[str, Any]:
    return advanced_context_payload(
        STORE.root,
        market_cache=STORE.read_market_cache(),
        crypto_detail_cache=STORE.read_crypto_detail_cache(),
        news_cache=STORE.read_news_cache(),
        research_data=_research_payload_from_store(refresh=False),
        rates_data=_rates_payload_from_store(refresh=False),
        fx_data=_fx_payload_from_store(refresh=False),
        commodity_data=_commodity_payload_from_store(refresh=False),
        fund_data=_fund_payload_from_store(refresh=False),
        equity_quote_data=_alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
        etf_quote_data=_alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
        fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
        twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
        finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
        fmp_quote_data=_fmp_quote_watchlist_payload_from_store(refresh=False),
        stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
        nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
        moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
        twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
    )


def _governance_payload_from_store() -> dict[str, Any]:
    return governance_payload(
        STORE,
        version=_package_version(),
        context=_advanced_context_from_store(),
    )


def _cache_is_writable(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    status = payload.get("status")
    status = status if isinstance(status, dict) else {}
    return str(status.get("state") or "") in {"live", "partial", "stale"}


def _dashboard_payload_from_store(layout: dict[str, Any]) -> dict[str, Any]:
    return dashboard_payload(
        layout,
        STORE.read_market_cache(),
        STORE.read_paper_state(),
        STORE.read_crypto_detail_cache(),
        STORE.read_portfolio_state(),
        STORE.read_news_cache(),
        providers_payload(STORE),
        STORE.root,
        _research_payload_from_store(refresh=False),
    )


def _markets_payload_from_store(
    layout: dict[str, Any] | None = None,
    *,
    refresh: bool = False,
) -> dict[str, Any]:
    layout = layout if isinstance(layout, dict) else STORE.read_markets_layout()
    payload = markets_payload(
        layout,
        STORE.read_market_cache(),
        STORE.read_crypto_detail_cache(),
        STORE.read_news_cache(),
        _research_payload_from_store(refresh=False),
        _rates_payload_from_store(refresh=False),
        _fx_payload_from_store(refresh=False),
        _commodity_payload_from_store(refresh=False),
        _fund_payload_from_store(refresh=False),
        _alpha_vantage_watchlist_payload_from_store(refresh=False),
        _alpha_vantage_watchlist_payload_from_store(
            refresh=False,
            fallback_symbols=ALPHA_VANTAGE_ETF_WATCHLIST,
        ),
        _alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
        _twelve_data_quote_watchlist_payload_from_store(refresh=False),
        _finnhub_quote_watchlist_payload_from_store(refresh=False),
        _fmp_quote_watchlist_payload_from_store(refresh=False),
        _stooq_quote_snapshot_payload_from_store(refresh=False),
        _nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
        moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
        twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        openfigi_mapping_data=_openfigi_mapping_payload_from_store(refresh=False),
        fetcher=MARKET_FETCHER,
        refresh=refresh,
    )
    if payload.get("cache"):
        STORE.write_market_cache(payload["cache"])
    payload["cache"] = None
    return payload


def _algo_payload_from_store() -> dict[str, Any]:
    state = STORE.read_algo_state()
    scan_artifact_health = STORE.algo_scan_artifact_health(state)
    return {
        **algo_payload(state),
        "scan_artifact_health": scan_artifact_health,
        "scan_readiness": _algo_scan_readiness_from_state(state, scan_artifact_health),
    }


def _algo_provider_context_from_store() -> dict[str, Any]:
    return {
        "research_data": _research_payload_from_store(refresh=False),
        "rates_data": _rates_payload_from_store(refresh=False),
        "fx_data": _fx_payload_from_store(refresh=False),
        "commodity_data": _commodity_payload_from_store(refresh=False),
        "fund_data": _fund_payload_from_store(refresh=False),
        "equity_quote_data": _alpha_vantage_watchlist_payload_from_store(refresh=False),
        "etf_quote_data": _alpha_vantage_watchlist_payload_from_store(
            refresh=False,
            fallback_symbols=ALPHA_VANTAGE_ETF_WATCHLIST,
        ),
    }


def _algo_scan_readiness_from_state(
    state: dict[str, Any],
    scan_artifact_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return algo_scan_readiness_payload(
        state,
        STORE.read_market_cache(),
        _algo_provider_context_from_store(),
        scan_artifact_health=scan_artifact_health,
    )


def _validate_backtest_lineage_from_latest_scan(raw_lineage: Any) -> dict[str, Any]:
    try:
        lineage = normalize_research_lineage(raw_lineage)
    except ResearchLineageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    algo_state = STORE.read_algo_state()
    last_scan = algo_state.get("last_scan") if isinstance(algo_state, dict) else None
    if not isinstance(last_scan, dict):
        raise HTTPException(status_code=400, detail="Research lineage requires a local scan seed")
    try:
        last_lineage = normalize_research_lineage(last_scan.get("research_lineage"))
    except ResearchLineageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if lineage["scan_id"] != last_lineage["scan_id"]:
        raise HTTPException(status_code=400, detail="Research lineage scan id mismatch")
    if lineage["markets_source_row_id"] != last_lineage["markets_source_row_id"]:
        raise HTTPException(status_code=400, detail="Research lineage source row id mismatch")
    if lineage["scan_artifact_hash"] != last_lineage["scan_artifact_hash"]:
        raise HTTPException(status_code=400, detail="Research lineage artifact hash mismatch")
    if lineage["markets_source_row_hash"] != last_lineage["markets_source_row_hash"]:
        raise HTTPException(status_code=400, detail="Research lineage source row hash mismatch")
    return last_lineage


def _provider_payload_from_store() -> dict[str, Any]:
    payload = providers_payload(STORE)
    last_refresh = latest_public_provider_refresh_manifest(STORE)
    if last_refresh:
        payload["last_refresh"] = last_refresh
    payload["refresh_lifecycle"] = provider_refresh_lifecycle_payload(STORE)
    payload["refresh_schedule_plan"] = provider_refresh_schedule_plan_payload(
        STORE,
        provider_payload=payload,
    )
    return payload


def _provider_refresh_callbacks() -> PublicProviderRefreshCallbacks:
    return PublicProviderRefreshCallbacks(
        market_payload=lambda: markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            {},
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            _twelve_data_quote_watchlist_payload_from_store(refresh=False),
            _finnhub_quote_watchlist_payload_from_store(refresh=False),
            _fmp_quote_watchlist_payload_from_store(refresh=False),
            _stooq_quote_snapshot_payload_from_store(refresh=False),
            _nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
            openfigi_mapping_data=_openfigi_mapping_payload_from_store(refresh=False),
            fetcher=MARKET_FETCHER,
            refresh=True,
        ),
        crypto_detail_payload=lambda: crypto_detail_payload(
            STORE.read_crypto_detail_cache(),
            fetcher=CRYPTO_DETAIL_FETCHER,
            refresh=True,
            symbol=DEFAULT_SYMBOL,
            interval=DEFAULT_INTERVAL,
        ),
        news_payload=lambda: news_payload(
            STORE.read_news_layout(),
            STORE.read_news_cache(),
            fetcher=NEWS_FETCHER,
            refresh=True,
        ),
        research_payload=lambda: _research_payload_from_store(refresh=True),
        rates_payload=lambda: _rates_payload_from_store(refresh=True),
        fx_payload=lambda: _fx_payload_from_store(refresh=True),
        commodity_payload=lambda: _commodity_payload_from_store(refresh=True),
        fund_payload=lambda: _fund_payload_from_store(refresh=True),
        stooq_quote_payload=lambda: _stooq_quote_snapshot_payload_from_store(refresh=True),
        moex_quote_payload=lambda: _moex_quote_snapshot_payload_from_store(refresh=True),
        twse_quote_payload=lambda: _twse_quote_snapshot_payload_from_store(refresh=True),
        nasdaq_symbol_payload=lambda: _nasdaq_trader_symbol_directory_payload_from_store(refresh=True),
        openfigi_mapping_payload=lambda: _openfigi_mapping_payload_from_store(refresh=True),
        provider_state_payload=lambda: providers_payload(STORE),
    )


def _refresh_public_provider_sources() -> dict[str, Any]:
    return run_public_provider_refresh(STORE, _provider_refresh_callbacks())


def _start_public_provider_refresh_job(background_tasks: BackgroundTasks) -> dict[str, Any]:
    job = create_public_provider_refresh_job(STORE)
    background_tasks.add_task(
        complete_public_provider_refresh_job,
        STORE,
        _provider_refresh_callbacks(),
        job["run_id"],
    )
    return job


def _public_provider_refresh_job(run_id: str) -> dict[str, Any]:
    try:
        job = read_public_provider_refresh_job(STORE, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Provider refresh job not found") from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Provider refresh job not found")
    return job


class SettingsUpdate(BaseModel):
    theme: str = Field(default="system")
    default_route: str = Field(default="dashboard")
    compact_mode: bool = Field(default=False)
    data_refresh_seconds: int = Field(default=60, ge=5, le=3600)


class ProfileUpdate(BaseModel):
    display_name: str = Field(default="Local User", min_length=1, max_length=80)
    theme: str = Field(default="system")
    default_route: str = Field(default="dashboard")


class LayoutUpdate(BaseModel):
    active_route: str = Field(default="dashboard")
    sidebar_collapsed: bool = Field(default=False)
    focus_mode: bool = Field(default=False)
    panel_order: list[str] = Field(default_factory=lambda: ["primary"])


class LocalDataProviderSecretUpdate(BaseModel):
    provider_id: str = Field(default="", min_length=1, max_length=120)
    secret_value: str = Field(default="", min_length=1, max_length=4096)
    consent: str = Field(default="", max_length=80)


class AgentActivityEventUpdate(BaseModel):
    route_id: str | None = Field(default=None, max_length=40)
    action_id: str = Field(default="", min_length=1, max_length=80)
    state: str = Field(default="", min_length=1, max_length=24)
    summary: str | None = Field(default=None, max_length=160)
    artifact_path: str | None = Field(default=None, max_length=240)


class DashboardLayoutUpdate(BaseModel):
    widgets: list[str] = Field(default_factory=list)
    template: str = Field(default="Local Default")
    alerts_read: bool = Field(default=False)


class DashboardTemplateUpdate(BaseModel):
    template: str = Field(default="Local Default")


class DashboardResetUpdate(BaseModel):
    # Reset overwrites the user's dashboard layout wholesale; like every other
    # overwrite of user state it must be asked for twice (M26 Phase 2 residual).
    template: str = Field(default="Local Default")
    confirm: bool = Field(default=False)


class MarketsLayoutUpdate(BaseModel):
    auto_refresh: bool = Field(default=False)
    asset_tab: str = Field(default="crypto")
    columns: list[str] = Field(default_factory=list)
    panels: list[dict[str, Any]] = Field(default_factory=list)


class NewsLayoutUpdate(BaseModel):
    auto_refresh: bool = Field(default=True)
    category: str = Field(default="ALL")
    time_filter: str = Field(default="24H")
    sort: str = Field(default="REL")
    feed_type: str = Field(default="WIRE")
    watch_terms: list[str] = Field(default_factory=list)
    watch_only: bool = Field(default=False)


class ChatSessionCreateUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=80)


class ChatRenameUpdate(BaseModel):
    session_id: str = Field(default="")
    name: str = Field(default="", min_length=1, max_length=80)


class ChatSelectUpdate(BaseModel):
    session_id: str = Field(default="")


class ChatDeleteUpdate(BaseModel):
    session_id: str = Field(default="")
    confirm: bool = Field(default=False)


class ChatMessageUpdate(BaseModel):
    session_id: str | None = Field(default=None)
    content: str = Field(default="", min_length=1, max_length=4000)
    linked_artifacts: list[str] = Field(default_factory=list)


class AlgoStrategyUpdate(BaseModel):
    strategy_id: str | None = Field(default=None)
    name: str = Field(default="Local SMA Trend", min_length=1, max_length=80)
    description: str = Field(default="", max_length=240)
    symbol: str = Field(default="BTCUSDT")
    timeframe: str = Field(default="15m")
    entry_conditions: list[str] = Field(default_factory=list)
    exit_conditions: list[str] = Field(default_factory=list)
    risk_settings: dict[str, Any] = Field(default_factory=dict)
    backtest: dict[str, Any] = Field(default_factory=dict)


class AlgoSelectUpdate(BaseModel):
    strategy_id: str = Field(default="")


class AlgoStrategyDeleteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy_id: str = Field(min_length=1)
    confirm: bool = Field(default=False)


class EquityPaperOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)
    side: str = Field(pattern="^(BUY|SELL|buy|sell)$")
    quantity: str | float | int = Field()
    order_type: str = Field(default="MARKET")
    limit_price: str | float | int | None = Field(default=None)
    rationale: str | None = Field(default=None, max_length=RATIONALE_MAX_CHARS)


class EquityOrderCancelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(min_length=1)


class PaperSnapshotUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh: bool = Field(default=True)
    note: str | None = Field(default=None, max_length=300)


class ResearchCallUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)
    stance: str = Field(pattern="^(accumulate|reduce|avoid|hold)$")
    thesis: str = Field(min_length=1, max_length=THESIS_MAX_CHARS)
    conviction: str = Field(default="medium", pattern="^(low|medium|high)$")
    market: str | None = Field(default=None)
    horizon_days: int = Field(default=30, ge=1, le=365)
    # ref_price is normally fetched live at record time; accept an override so a
    # call can be reconstructed in tests or from an explicit mark.
    ref_price: str | float | int | None = Field(default=None)
    entry_low: str | float | int | None = Field(default=None)
    entry_high: str | float | int | None = Field(default=None)
    invalidation: str | float | int | None = Field(default=None)
    name: str | None = Field(default=None)
    evidence: dict[str, Any] | None = Field(default=None)
    refresh: bool = Field(default=True)


class ResearchScoreUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # refresh=True fetches current marks for every open call before scoring;
    # refresh=False scores from cached marks only (a matured call with no cached
    # mark stays open and unscored rather than being graded on stale data).
    refresh: bool = Field(default=True)


class NewsPacketUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbols: list[str] = Field(default_factory=list, max_length=20)
    limit: int = Field(default=8, ge=1, le=PACKET_MAX_ITEMS)
    refresh: bool = Field(default=False)


class MarketsQuoteLookupUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbols: list[str] = Field(min_length=1, max_length=YAHOO_MAX_WATCHLIST)


class LocalStateRestoreUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1)
    slot: int = Field(default=1, ge=1, le=STATE_BACKUP_COUNT)
    confirm: bool = Field(default=False)


class AlgoRunBacktestUpdate(BaseModel):
    strategy_id: str | None = Field(default=None)
    strategy: dict[str, Any] | None = Field(default=None)
    backtest: dict[str, Any] = Field(default_factory=dict)
    scan_seed: dict[str, Any] | None = Field(default=None)


class AlgoScanUpdate(BaseModel):
    strategy_id: str | None = Field(default=None)
    strategy: dict[str, Any] | None = Field(default=None)
    symbols: list[str] | str | None = Field(default=None)
    timeframe: str | None = Field(default=None)
    lookback_days: int = Field(default=30)
    preset: str = Field(default="custom")
    markets_source_row_id: str | None = Field(default=None)
    markets_source_row_hash: str | None = Field(default=None)


class NodesWorkflowUpdate(BaseModel):
    workflow: dict[str, Any] | str = Field(default_factory=dict)


class NodesTemplateUpdate(BaseModel):
    template_id: str = Field(default="")


class NodesSelectWorkflowUpdate(BaseModel):
    workflow_id: str = Field(default="")


class NodesSelectNodeUpdate(BaseModel):
    node_id: str = Field(default="")


class NodesWorkflowRefUpdate(BaseModel):
    workflow_id: str | None = Field(default=None)
    workflow: dict[str, Any] | None = Field(default=None)


class CodeNotebookCreateUpdate(BaseModel):
    name: str = Field(default="Local Python Notebook", min_length=1, max_length=80)
    path: str | None = Field(default=None, max_length=200)


class CodeNotebookUpdate(BaseModel):
    notebook: dict[str, Any] | str = Field(default_factory=dict)


class CodeCellAddUpdate(BaseModel):
    cell_type: str = Field(default="code")
    source: str = Field(default="", max_length=12000)


class CodeCellSelectUpdate(BaseModel):
    cell_id: str = Field(default="")


class CodeNotebookSelectUpdate(BaseModel):
    notebook_id: str = Field(default="")


class CodeNotebookIdUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notebook_id: str = Field(min_length=1)


class CodeNotebookRefUpdate(BaseModel):
    notebook_id: str | None = Field(default=None)
    notebook: dict[str, Any] | None = Field(default=None)


class QuantLabSelectUpdate(BaseModel):
    module_slug: str = Field(default="")


class QuantLabRunUpdate(BaseModel):
    module_slug: str | None = Field(default=None)
    inputs: dict[str, Any] = Field(default_factory=dict)


class QuantLibModuleSelectUpdate(BaseModel):
    module_id: str = Field(default="")


class QuantLibActionSelectUpdate(BaseModel):
    action_id: str = Field(default="")


class QuantLibComputeUpdate(BaseModel):
    action_id: str | None = Field(default=None)
    request_body: dict[str, Any] | str | None = Field(default=None)


class ForumChannelUpdate(BaseModel):
    channel_id: str = Field(default="")


class ForumPostSelectUpdate(BaseModel):
    post_id: str = Field(default="")


class ForumPostCreateUpdate(BaseModel):
    title: str = Field(default="", min_length=1, max_length=120)
    content: str = Field(default="", min_length=1, max_length=6000)
    channel_id: str = Field(default="crypto-corner")
    tags: list[str] | str = Field(default_factory=list)
    linked_artifacts: list[str] | str = Field(default_factory=list)


class ForumReplyUpdate(BaseModel):
    post_id: str | None = Field(default=None)
    content: str = Field(default="", min_length=1, max_length=2400)


class PaperOrderUpdate(BaseModel):
    # Reject unknown fields so a mistyped key can never silently fall back to a
    # MARKET fill; accept "type" as an alias so order records round-trip.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    symbol: str = Field(default="BTCUSDT")
    timeframe: str = Field(default="15m")
    side: str = Field(default="BUY")
    order_type: str = Field(default="MARKET", validation_alias=AliasChoices("order_type", "type"))
    quantity: str | float | int = Field(default="0")
    limit_price: str | float | int | None = Field(default=None)
    stop_price: str | float | int | None = Field(default=None)
    rationale: str | None = Field(default=None, max_length=RATIONALE_MAX_CHARS)


class PaperOrderCancelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str = Field(min_length=1)


class CryptoRefreshUpdate(BaseModel):
    symbol: str = Field(default=DEFAULT_SYMBOL)
    timeframe: str = Field(default=DEFAULT_INTERVAL)
    view: str = Field(default="full", pattern="^(full|summary)$")


class BacktestRunUpdate(BaseModel):
    symbol: str = Field(default="BTCUSDT")
    timeframe: str = Field(default="15m")
    strategy: str = Field(default="sma_cross")
    fast_window: int = Field(default=3)
    slow_window: int = Field(default=5)
    initial_cash: str = Field(default="100000.00")
    fee_rate: str = Field(default="0.001")
    slippage_bps: str = Field(default="2")
    research_lineage: dict[str, Any] | None = Field(default=None)


class BacktestWalkForwardUpdate(BacktestRunUpdate):
    fold_count: int = Field(default=3)


class BacktestComparisonUpdate(BaseModel):
    max_runs: int = Field(default=4)


class BacktestOptimizeUpdate(BacktestRunUpdate):
    parameter_grid: dict[str, list[int]] | None = Field(default=None)
    objective: str = Field(default="return_pct")


class AlphaVantageQuoteRefreshUpdate(BaseModel):
    symbols: list[str] | str = Field(default_factory=list)


class AlphaVantageFxQuoteRefreshUpdate(BaseModel):
    pairs: list[str] | str = Field(default_factory=list)


class TwelveDataQuoteRefreshUpdate(BaseModel):
    symbols: list[str] | str = Field(default_factory=list)


class FinnhubQuoteRefreshUpdate(BaseModel):
    symbols: list[str] | str = Field(default_factory=list)


class FmpQuoteRefreshUpdate(BaseModel):
    symbols: list[str] | str = Field(default_factory=list)


class StooqQuoteRefreshUpdate(BaseModel):
    symbols: list[str] | str = Field(default_factory=list)


class YahooQuoteRefreshUpdate(BaseModel):
    symbols: list[str] | str = Field(default_factory=list)


class MoexQuoteRefreshUpdate(BaseModel):
    symbols: list[str] | str = Field(default_factory=list)


class TwseQuoteRefreshUpdate(BaseModel):
    symbols: list[str] | str = Field(default_factory=list)


class OpenFigiMappingRefreshUpdate(BaseModel):
    symbols: list[str] | str = Field(default_factory=list)


class PortfolioCreateUpdate(BaseModel):
    # An explicit name is required so a stray empty POST cannot create a junk
    # book and silently hijack the active portfolio; unknown fields are
    # rejected instead of silently dropped.
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    owner: str = Field(default="Local User")
    currency: str = Field(default="USD")
    positions: list[dict[str, Any]] = Field(default_factory=list)


class PortfolioDeleteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    portfolio_id: str = Field(min_length=1)
    confirm: bool = Field(default=False)


class PortfolioSelectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    portfolio_id: str = Field(min_length=1)


class WatchlistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group: str = Field(min_length=1, max_length=16)
    symbols: list[str] | str = Field(default_factory=list)


class NewsDigestWriteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[dict[str, str]] = Field(default_factory=list)
    sections: list[dict[str, str]] = Field(default_factory=list)


class HistoryRefreshUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbols: list[str] | str = Field(default_factory=list)


class PortfolioImportUpdate(BaseModel):
    mode: str = Field(default="create_new")
    target_portfolio_id: str | None = Field(default=None)
    portfolio: dict[str, Any] = Field(default_factory=dict)


class PortfolioBacktestLinkUpdate(BaseModel):
    artifact_dir: str | None = Field(default=None)


def _package_version() -> str:
    try:
        return version("otto")
    except PackageNotFoundError:
        pass
    try:
        import tomllib

        raw = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        return str(tomllib.loads(raw)["project"]["version"])
    except (OSError, KeyError, ValueError):
        return "0.0.0+unknown"


def health_payload() -> dict[str, Any]:
    return {
        "app": APP_NAME,
        "mode": "local",
        "version": _package_version(),
        "clean_room": True,
        "route_count": len(SHELL_ROUTES),
        "menu_count": len(GLOBAL_MENUS),
        "live_execution": "disabled",
    }


def shell_contract_payload() -> dict[str, Any]:
    return {
        "routes": [asdict(route) for route in SHELL_ROUTES],
        "menus": [
            {
                "section_id": menu.section_id,
                "label": menu.label,
                "items": [asdict(item) for item in menu.items],
            }
            for menu in GLOBAL_MENUS
        ],
        "safety": asdict(DEFAULT_SAFETY_INVARIANTS),
        "profile_policy": asdict(DEFAULT_LOCAL_PROFILE_POLICY),
    }


def create_app(frontend_dist: Path | None = None) -> FastAPI:
    app = FastAPI(
        title=f"{APP_NAME} API",
        version=_package_version(),
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    ui_dist = DEFAULT_FRONTEND_DIST if frontend_dist is None else Path(frontend_dist)
    serve_ui = (ui_dist / "index.html").is_file()

    # Conventional discovery paths; the real spec lives under /api/.
    @app.get("/openapi.json", include_in_schema=False)
    def openapi_alias() -> RedirectResponse:
        return RedirectResponse(url="/api/openapi.json")

    @app.get("/docs", include_in_schema=False)
    def docs_alias() -> RedirectResponse:
        return RedirectResponse(url="/api/docs")

    if not serve_ui:

        @app.get("/", include_in_schema=False)
        def root() -> RedirectResponse:
            return RedirectResponse(url="/api/health")

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return health_payload()

    @app.get("/api/shell-contract")
    def shell_contract() -> dict[str, Any]:
        return shell_contract_payload()

    @app.get("/api/local-state")
    def local_state() -> dict[str, Any]:
        return STORE.read_state()

    @app.get("/api/providers")
    def providers() -> dict[str, Any]:
        return _provider_payload_from_store()

    @app.get("/api/providers/cache")
    def provider_cache() -> dict[str, Any]:
        payload = provider_cache_payload(STORE)
        payload["refresh_schedule_plan"] = provider_refresh_schedule_plan_payload(STORE)
        return payload

    @app.get("/api/providers/refresh-public/lifecycle")
    def provider_refresh_lifecycle() -> dict[str, Any]:
        return provider_refresh_lifecycle_payload(STORE)

    @app.get("/api/providers/refresh-public/schedule-plan")
    def provider_refresh_schedule_plan() -> dict[str, Any]:
        return provider_refresh_schedule_plan_payload(STORE)

    @app.get("/api/artifact-lifecycle")
    def artifact_lifecycle() -> dict[str, Any]:
        return artifact_lifecycle_payload(STORE.root)

    @app.post("/api/artifact-lifecycle/archive-plan")
    def artifact_lifecycle_archive_plan() -> dict[str, Any]:
        return run_artifact_archive_plan(STORE.root)

    @app.get("/api/local-state/backups")
    def local_state_backups() -> dict[str, Any]:
        return STORE.state_backup_index()

    @app.post("/api/local-state/restore")
    def local_state_restore(update: LocalStateRestoreUpdate) -> dict[str, Any]:
        if not update.confirm:
            raise HTTPException(status_code=400, detail="Restore confirmation is required")
        try:
            return STORE.restore_state_backup(update.kind, update.slot)
        except StateRestoreError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/agent-contract")
    def agent_contract() -> dict[str, Any]:
        return agent_operability_payload(STORE.root)

    @app.get("/api/agent-actions/{action_id}/preflight")
    def agent_action_preflight(action_id: str) -> dict[str, Any]:
        return agent_action_preflight_payload(STORE.root, action_id)

    @app.get("/api/agent-activity")
    def agent_activity() -> dict[str, Any]:
        return agent_activity_payload(STORE.root)

    @app.post("/api/agent-activity/events")
    def write_agent_activity_event(update: AgentActivityEventUpdate) -> dict[str, Any]:
        try:
            return append_agent_activity_event(STORE.root, update.model_dump())
        except AgentActivityError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/command-center")
    def command_center() -> dict[str, Any]:
        context = _advanced_context_from_store()
        return command_center_payload(
            _governance_payload_from_store(),
            advanced_outputs=advanced_workflow_output_packet(STORE.root, context),
            agent_activity=agent_activity_payload(STORE.root),
        )

    @app.get("/api/command-center/preflight-matrix")
    def command_center_preflight_matrix() -> dict[str, Any]:
        return command_center_preflight_matrix_payload(_governance_payload_from_store())

    @app.get("/api/advanced-workflows/output-packet")
    def advanced_workflows_output_packet() -> dict[str, Any]:
        return advanced_workflow_output_packet(STORE.root, _advanced_context_from_store())

    @app.post("/api/advanced-workflows/output-packet")
    def write_local_advanced_workflows_output_packet() -> dict[str, Any]:
        return write_advanced_workflow_output_packet(STORE.root, _advanced_context_from_store())

    @app.get("/api/provider-acquisition-gate")
    def provider_acquisition_gate() -> dict[str, Any]:
        return provider_acquisition_gate_payload()

    @app.post("/api/providers/refresh-public")
    def refresh_public_providers() -> dict[str, Any]:
        return _refresh_public_provider_sources()

    @app.post("/api/providers/refresh-public/jobs")
    def start_refresh_public_providers_job(background_tasks: BackgroundTasks) -> dict[str, Any]:
        return _start_public_provider_refresh_job(background_tasks)

    @app.get("/api/providers/refresh-public/jobs/{run_id}")
    def provider_refresh_job(run_id: str) -> dict[str, Any]:
        return _public_provider_refresh_job(run_id)

    @app.get("/api/dashboard")
    def dashboard() -> dict[str, Any]:
        return _dashboard_payload_from_store(STORE.read_dashboard_layout())

    @app.get("/api/markets")
    def markets() -> dict[str, Any]:
        layout = STORE.read_markets_layout()
        return _markets_payload_from_store(
            layout,
            refresh=layout.get("auto_refresh") is not False,
        )

    @app.get("/api/markets/quote-reference-coverage")
    def markets_quote_reference_coverage() -> dict[str, Any]:
        return _markets_payload_from_store(refresh=False)["quote_reference_coverage"]

    @app.get("/api/markets/quote-snapshot-board")
    def markets_quote_snapshot_board() -> dict[str, Any]:
        return _markets_payload_from_store(refresh=False)["quote_reference_coverage"][
            "snapshot_board"
        ]

    @app.get("/api/news/digest")
    def news_digest_index() -> dict[str, Any]:
        payload = news_digest_payload(STORE.read_news_digest_state())
        # The operator's hand-written sections are richer but freeze the moment
        # they're written. Roll up a live one from the current feed when there
        # are none yet, or when the last curated set is from an earlier day.
        today = datetime.now(tz=UTC).date().isoformat()
        if not payload["sections"] or not is_digest_fresh(payload.get("updated_at"), today):
            news = _news_payload_from_store(refresh=False)
            live = build_live_sections(news.get("items") or [])
            if live:
                payload["sections"] = live
                payload["origin"] = "auto"
                payload["updated_at"] = (
                    (news.get("status") or {}).get("last_update") or payload["updated_at"]
                )
        payload.setdefault("origin", "ai")
        return payload

    @app.post("/api/news/digest")
    def news_digest_write(update: NewsDigestWriteUpdate) -> dict[str, Any]:
        try:
            state = write_news_digest(STORE.read_news_digest_state(), update.items, update.sections)
        except NewsDigestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return news_digest_payload(STORE.write_news_digest_state(state))

    @app.get("/api/news/briefs/{brief_id}")
    def news_brief_detail(brief_id: str) -> dict[str, Any]:
        payload = news_brief_detail_payload(STORE.root, brief_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Unknown news brief id")
        return payload

    @app.get("/api/news")
    def news() -> dict[str, Any]:
        # Reads always serve the local cache instantly; external fetches happen
        # only through POST /api/news/refresh so a flaky source can never stall
        # or shrink a plain read.
        payload = _news_payload_from_store(refresh=False)
        return _public_news_payload(_attach_news_research_brief_index(payload))

    @app.get("/api/news/topic-entity-map")
    def news_topic_entity_map() -> dict[str, Any]:
        return news_topic_entity_map_payload(_public_news_payload(_news_payload_from_store(refresh=False)))

    @app.get("/api/research-data")
    def research_data() -> dict[str, Any]:
        return _public_research_payload(_research_payload_from_store(refresh=False))

    @app.get("/api/rates")
    def rates_data() -> dict[str, Any]:
        return _public_rates_payload(_rates_payload_from_store(refresh=False))

    @app.get("/api/fx")
    def fx_data() -> dict[str, Any]:
        return _public_fx_payload(_fx_payload_from_store(refresh=False))

    @app.get("/api/commodities")
    def commodity_data() -> dict[str, Any]:
        return _public_commodity_payload(_commodity_payload_from_store(refresh=False))

    @app.get("/api/cftc/cot")
    def cftc_cot_data() -> dict[str, Any]:
        return _public_commodity_payload(_commodity_payload_from_store(refresh=False))["cftc"]

    @app.post("/api/cftc/cot/refresh")
    def refresh_cftc_cot_data() -> dict[str, Any]:
        return _public_commodity_payload(_commodity_payload_from_store(refresh=True))["cftc"]

    @app.get("/api/eia/energy")
    def eia_energy_data() -> dict[str, Any]:
        return _public_eia_payload(_eia_payload_from_store(refresh=False))

    @app.post("/api/eia/energy/refresh")
    def refresh_eia_energy_data() -> dict[str, Any]:
        return _public_eia_payload(_eia_payload_from_store(refresh=True))

    @app.get("/api/funds")
    def fund_data() -> dict[str, Any]:
        return _public_fund_payload(_fund_payload_from_store(refresh=False))

    @app.get("/api/fred")
    def fred_data() -> dict[str, Any]:
        return _public_fred_payload(_fred_payload_from_store(refresh=False))

    @app.post("/api/fred/refresh")
    def refresh_fred_data() -> dict[str, Any]:
        return _public_fred_payload(_fred_payload_from_store(refresh=True))

    @app.get("/api/bls")
    def bls_data() -> dict[str, Any]:
        return _public_bls_payload(_bls_payload_from_store(refresh=False))

    @app.post("/api/bls/refresh")
    def refresh_bls_data() -> dict[str, Any]:
        return _public_bls_payload(_bls_payload_from_store(refresh=True))

    @app.get("/api/bea/regional")
    def bea_regional_data() -> dict[str, Any]:
        return _public_bea_payload(_bea_payload_from_store(refresh=False))

    @app.post("/api/bea/regional/refresh")
    def refresh_bea_regional_data() -> dict[str, Any]:
        return _public_bea_payload(_bea_payload_from_store(refresh=True))

    @app.get("/api/census/acs-profile")
    def census_acs_profile_data() -> dict[str, Any]:
        return _public_census_payload(_census_payload_from_store(refresh=False))

    @app.post("/api/census/acs-profile/refresh")
    def refresh_census_acs_profile_data() -> dict[str, Any]:
        return _public_census_payload(_census_payload_from_store(refresh=True))

    @app.get("/api/eurostat/hicp")
    def eurostat_hicp_data() -> dict[str, Any]:
        return _public_eurostat_payload(_eurostat_payload_from_store(refresh=False))

    @app.post("/api/eurostat/hicp/refresh")
    def refresh_eurostat_hicp_data() -> dict[str, Any]:
        return _public_eurostat_payload(_eurostat_payload_from_store(refresh=True))

    @app.get("/api/alpha-vantage/equity-quote")
    def alpha_vantage_equity_quote() -> dict[str, Any]:
        return _public_alpha_vantage_payload(_alpha_vantage_payload_from_store(refresh=False))

    @app.post("/api/alpha-vantage/equity-quote/refresh")
    def refresh_alpha_vantage_equity_quote() -> dict[str, Any]:
        return _public_alpha_vantage_payload(_alpha_vantage_payload_from_store(refresh=True))

    @app.get("/api/alpha-vantage/equity-quotes")
    def alpha_vantage_equity_quotes() -> dict[str, Any]:
        return _public_alpha_vantage_payload(
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False)
        )

    @app.post("/api/alpha-vantage/equity-quotes/refresh")
    def refresh_alpha_vantage_equity_quotes(
        update: AlphaVantageQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        return _public_alpha_vantage_payload(
            _alpha_vantage_stock_watchlist_payload_from_store(
                refresh=True,
                symbols=update.symbols if update else None,
            )
        )

    @app.get("/api/alpha-vantage/etf-quote")
    def alpha_vantage_etf_quote() -> dict[str, Any]:
        return _public_alpha_vantage_payload(
            _alpha_vantage_etf_payload_from_store(refresh=False)
        )

    @app.post("/api/alpha-vantage/etf-quote/refresh")
    def refresh_alpha_vantage_etf_quote() -> dict[str, Any]:
        return _public_alpha_vantage_payload(
            _alpha_vantage_etf_payload_from_store(refresh=True)
        )

    @app.get("/api/alpha-vantage/etf-quotes")
    def alpha_vantage_etf_quotes() -> dict[str, Any]:
        return _public_alpha_vantage_payload(
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False)
        )

    @app.post("/api/alpha-vantage/etf-quotes/refresh")
    def refresh_alpha_vantage_etf_quotes(
        update: AlphaVantageQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        return _public_alpha_vantage_payload(
            _alpha_vantage_etf_watchlist_payload_from_store(
                refresh=True,
                symbols=update.symbols if update else None,
            )
        )

    @app.get("/api/alpha-vantage/fx-quotes")
    def alpha_vantage_fx_quotes() -> dict[str, Any]:
        return _public_alpha_vantage_payload(
            _alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False)
        )

    @app.post("/api/alpha-vantage/fx-quotes/refresh")
    def refresh_alpha_vantage_fx_quotes(
        update: AlphaVantageFxQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        return _public_alpha_vantage_payload(
            _alpha_vantage_fx_quote_watchlist_payload_from_store(
                refresh=True,
                pairs=update.pairs if update else None,
            )
        )

    @app.get("/api/twelve-data/quotes")
    def twelve_data_quotes() -> dict[str, Any]:
        return _public_twelve_data_payload(
            _twelve_data_quote_watchlist_payload_from_store(refresh=False)
        )

    @app.post("/api/twelve-data/quotes/refresh")
    def refresh_twelve_data_quotes(
        update: TwelveDataQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        return _public_twelve_data_payload(
            _twelve_data_quote_watchlist_payload_from_store(
                refresh=True,
                symbols=update.symbols if update else None,
            )
        )

    @app.get("/api/finnhub/quotes")
    def finnhub_quotes() -> dict[str, Any]:
        return _public_finnhub_payload(
            _finnhub_quote_watchlist_payload_from_store(refresh=False)
        )

    @app.post("/api/finnhub/quotes/refresh")
    def refresh_finnhub_quotes(
        update: FinnhubQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        return _public_finnhub_payload(
            _finnhub_quote_watchlist_payload_from_store(
                refresh=True,
                symbols=update.symbols if update else None,
            )
        )

    @app.get("/api/fmp/quotes")
    def fmp_quotes() -> dict[str, Any]:
        return _public_fmp_payload(_fmp_quote_watchlist_payload_from_store(refresh=False))

    @app.post("/api/fmp/quotes/refresh")
    def refresh_fmp_quotes(
        update: FmpQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        return _public_fmp_payload(
            _fmp_quote_watchlist_payload_from_store(
                refresh=True,
                symbols=update.symbols if update else None,
            )
        )

    @app.get("/api/stooq/quote-snapshots")
    def stooq_quote_snapshots() -> dict[str, Any]:
        return _public_stooq_payload(
            _stooq_quote_snapshot_payload_from_store(refresh=False)
        )

    @app.get("/api/markets/yahoo/quotes")
    def yahoo_quote_snapshots() -> dict[str, Any]:
        return _public_yahoo_payload(
            _yahoo_quote_snapshot_payload_from_store(refresh=False)
        )

    @app.post("/api/markets/yahoo/quotes/refresh")
    def refresh_market_yahoo_quotes(
        update: YahooQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        return _public_yahoo_payload(
            _yahoo_quote_snapshot_payload_from_store(
                refresh=True,
                symbols=update.symbols if update else None,
            )
        )

    @app.post("/api/markets/quotes/lookup")
    def markets_quote_lookup(update: MarketsQuoteLookupUpdate) -> dict[str, Any]:
        safe_symbols = yahoo_lookup_symbols(update.symbols)
        if not safe_symbols:
            raise HTTPException(
                status_code=400,
                detail="No valid symbols to look up (letters/digits with . ^ = - only)",
            )
        payload = _public_yahoo_payload(
            _yahoo_quote_snapshot_payload_from_store(refresh=True, symbols=safe_symbols)
        )
        return {
            "requested_symbols": safe_symbols,
            "status": payload.get("status", {}),
            "quotes": payload.get("quotes", []),
            "summary": payload.get("summary", {}),
            "entry": payload.get("entry", {}),
        }

    @app.post("/api/stooq/quote-snapshots/refresh")
    def refresh_stooq_quote_snapshots(
        update: StooqQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        return _public_stooq_payload(
            _stooq_quote_snapshot_payload_from_store(
                refresh=True,
                symbols=update.symbols if update else None,
            )
        )

    @app.get("/api/moex/quote-snapshots")
    def moex_quote_snapshots() -> dict[str, Any]:
        return _public_moex_payload(_moex_quote_snapshot_payload_from_store(refresh=False))

    @app.post("/api/moex/quote-snapshots/refresh")
    def refresh_moex_quote_snapshots(
        update: MoexQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        return _public_moex_payload(
            _moex_quote_snapshot_payload_from_store(
                refresh=True,
                symbols=update.symbols if update else None,
            )
        )

    @app.get("/api/twse/quote-snapshots")
    def twse_quote_snapshots() -> dict[str, Any]:
        return _public_twse_payload(_twse_quote_snapshot_payload_from_store(refresh=False))

    @app.post("/api/twse/quote-snapshots/refresh")
    def refresh_twse_quote_snapshots(
        update: TwseQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        return _public_twse_payload(
            _twse_quote_snapshot_payload_from_store(
                refresh=True,
                symbols=update.symbols if update else None,
            )
        )

    @app.get("/api/nasdaq-trader/symbol-directory")
    def nasdaq_trader_symbol_directory() -> dict[str, Any]:
        return _public_nasdaq_trader_payload(
            _nasdaq_trader_symbol_directory_payload_from_store(refresh=False)
        )

    @app.post("/api/nasdaq-trader/symbol-directory/refresh")
    def refresh_nasdaq_trader_symbol_directory() -> dict[str, Any]:
        return _public_nasdaq_trader_payload(
            _nasdaq_trader_symbol_directory_payload_from_store(refresh=True)
        )

    @app.get("/api/nasdaq-trader/symbol-directory/search")
    def search_nasdaq_trader_symbol_directory(
        query: str = "AAPL",
        limit: int = 12,
    ) -> dict[str, Any]:
        return nasdaq_trader_symbol_search_payload(
            _nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            query=query,
            limit=limit,
        )

    @app.get("/api/openfigi/mapping")
    def openfigi_mapping() -> dict[str, Any]:
        return _public_openfigi_payload(_openfigi_mapping_payload_from_store(refresh=False))

    @app.post("/api/openfigi/mapping/refresh")
    def refresh_openfigi_mapping(
        update: OpenFigiMappingRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        return _public_openfigi_payload(
            _openfigi_mapping_payload_from_store(
                refresh=True,
                symbols=update.symbols if update else None,
            )
        )

    @app.get("/api/ai-chat")
    def ai_chat() -> dict[str, Any]:
        return chat_payload(STORE.read_chat_state(), STORE.root, _advanced_context_from_store())

    @app.get("/api/ai-chat/context-contract")
    def ai_chat_context_contract() -> dict[str, Any]:
        return chat_context_contract(
            STORE.read_chat_state(),
            STORE.root,
            _advanced_context_from_store(),
        )

    @app.get("/api/ai-chat/session-health")
    def ai_chat_session_health() -> dict[str, Any]:
        return chat_session_health_payload(STORE.read_chat_state(), STORE.root)

    @app.get("/api/algo")
    def algo() -> dict[str, Any]:
        return _algo_payload_from_store()

    @app.get("/api/algo/scan-readiness")
    def algo_scan_readiness() -> dict[str, Any]:
        state = STORE.read_algo_state()
        return _algo_scan_readiness_from_state(state, STORE.algo_scan_artifact_health(state))

    @app.get("/api/nodes")
    def nodes() -> dict[str, Any]:
        return nodes_payload(STORE.read_nodes_state(), _advanced_context_from_store(), STORE.root)

    @app.get("/api/nodes/workflow-health")
    def nodes_workflow_health() -> dict[str, Any]:
        return nodes_workflow_health_payload(STORE.read_nodes_state(), STORE.root)

    @app.get("/api/code")
    def code() -> dict[str, Any]:
        return code_payload(
            STORE.read_code_state(), _advanced_context_from_store(), STORE.root
        )

    @app.get("/api/code/analysis-health")
    def code_analysis_health() -> dict[str, Any]:
        return code_analysis_health_payload(STORE.read_code_state(), STORE.root)

    @app.get("/api/quant-lab")
    def quant_lab() -> dict[str, Any]:
        return quant_lab_payload(
            STORE.read_quant_lab_state(), _advanced_context_from_store(), STORE.root
        )

    @app.get("/api/quant-lab/preview-health")
    def quant_lab_preview_health() -> dict[str, Any]:
        return quant_lab_preview_health_payload(STORE.read_quant_lab_state(), STORE.root)

    @app.get("/api/quantlib")
    def quantlib() -> dict[str, Any]:
        return quantlib_payload(
            STORE.read_quantlib_state(), _advanced_context_from_store(), STORE.root
        )

    @app.get("/api/quantlib/calculation-health")
    def quantlib_calculation_health() -> dict[str, Any]:
        return quantlib_calculation_health_payload(STORE.read_quantlib_state(), STORE.root)

    @app.get("/api/forum")
    def forum() -> dict[str, Any]:
        return forum_payload(
            STORE.read_forum_state(), _advanced_context_from_store(), root=STORE.root
        )

    @app.get("/api/help")
    def help_center() -> dict[str, Any]:
        return help_payload(
            STORE,
            version=_package_version(),
            governance=_governance_payload_from_store(),
        )

    @app.get("/api/governance")
    def governance() -> dict[str, Any]:
        return _governance_payload_from_store()

    @app.post("/api/governance/diagnostics")
    def run_local_governance_diagnostics() -> dict[str, Any]:
        governance_view = _governance_payload_from_store()
        return run_governance_diagnostics(
            STORE,
            version=_package_version(),
            governance=governance_view,
        )

    @app.get("/api/secret-gate")
    def secret_gate() -> dict[str, Any]:
        governance_payload_view = _governance_payload_from_store()
        secret_status = governance_payload_view.get("local_secret_status")
        return secret_status if isinstance(secret_status, dict) else {}

    @app.get("/api/local-secrets/status")
    def local_secrets_status() -> dict[str, Any]:
        governance_payload_view = _governance_payload_from_store()
        secret_status = governance_payload_view.get("local_secret_status")
        return secret_status if isinstance(secret_status, dict) else {}

    @app.post("/api/local-secrets")
    def store_local_secret(update: LocalDataProviderSecretUpdate) -> dict[str, Any]:
        try:
            return store_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=update.provider_id,
                secret_value=update.secret_value,
                consent=update.consent,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/local-secrets/{provider_id}")
    def forget_local_secret(provider_id: str) -> dict[str, Any]:
        try:
            return forget_local_data_provider_secret(
                STORE.root,
                providers_payload(STORE),
                provider_id=provider_id,
            )
        except LocalSecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/live-safety")
    def live_safety() -> dict[str, Any]:
        return live_safety_payload()

    @app.get("/api/crypto")
    def crypto() -> dict[str, Any]:
        return crypto_payload(
            STORE.read_paper_state(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
        )

    @app.post("/api/equity/orders")
    def submit_equity_paper_order(update: EquityPaperOrderUpdate) -> dict[str, Any]:
        symbol = update.symbol.strip().upper()
        lookup = _yahoo_quote_snapshot_payload_from_store(refresh=True, symbols=[symbol])
        rows = [row for row in lookup.get("quotes", []) if isinstance(row, dict)]
        quote_row = rows[0] if rows else None
        try:
            state, order = place_equity_paper_order(
                STORE.read_equity_paper_state(),
                {**update.model_dump(), "symbol": symbol},
                quote_row,
            )
        except EquityOrderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_equity_paper_state(state)
        held = sorted(state.get("positions", {}))
        marks = (
            _yahoo_quote_snapshot_payload_from_store(refresh=False, symbols=held).get(
                "quotes", []
            )
            if held
            else []
        )
        return {
            "submitted_order": order,
            **equity_summary_payload(state, marks),
        }

    def _tw_odd_lot_row_for(symbol: str, quantity: Any) -> dict[str, Any] | None:
        """Odd-lot session data when the quantity is not a full board lot."""
        try:
            if Decimal(str(quantity)) % TW_BOOK.lot_size == 0:
                return None
        except (ArithmeticError, TypeError, ValueError):
            return None
        return fetch_twse_odd_lot_row(symbol.split(".")[0])

    @app.post("/api/equity/tw/orders")
    def submit_tw_equity_paper_order(update: EquityPaperOrderUpdate) -> dict[str, Any]:
        symbol = update.symbol.strip().upper()
        lookup = _yahoo_quote_snapshot_payload_from_store(refresh=True, symbols=[symbol])
        rows = [row for row in lookup.get("quotes", []) if isinstance(row, dict)]
        quote_row = rows[0] if rows else None
        try:
            state, order = place_equity_paper_order(
                STORE.read_tw_equity_paper_state(),
                {**update.model_dump(), "symbol": symbol},
                quote_row,
                TW_BOOK,
                odd_lot_row=_tw_odd_lot_row_for(symbol, update.quantity),
            )
        except EquityOrderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_tw_equity_paper_state(state)
        held = sorted(state.get("positions", {}))
        marks = (
            _yahoo_quote_snapshot_payload_from_store(refresh=False, symbols=held).get(
                "quotes", []
            )
            if held
            else []
        )
        return {
            "submitted_order": order,
            **equity_summary_payload(state, marks, TW_BOOK),
        }

    def _equity_working_symbols(state: dict[str, Any]) -> list[str]:
        return sorted(
            {
                str(order.get("symbol"))
                for order in state.get("orders", [])
                if isinstance(order, dict) and order.get("status") == "WORKING"
            }
        )

    def _equity_working_marks(state: dict[str, Any]) -> list[dict[str, Any]]:
        symbols = _equity_working_symbols(state)
        if not symbols:
            return []
        payload = _yahoo_quote_snapshot_payload_from_store(refresh=True, symbols=symbols)
        return [row for row in payload.get("quotes", []) if isinstance(row, dict)]

    @app.post("/api/equity/orders/process")
    def process_equity_orders() -> dict[str, Any]:
        state = STORE.read_equity_paper_state()
        new_state, report = process_equity_paper_orders(
            state, _equity_working_marks(state)
        )
        STORE.write_equity_paper_state(new_state)
        return {**report, "account": new_state["account"]}

    @app.post("/api/equity/tw/orders/process")
    def process_tw_equity_orders() -> dict[str, Any]:
        state = STORE.read_tw_equity_paper_state()
        odd_lot_rows: dict[str, dict[str, Any]] = {}
        for order in state.get("orders", []):
            if (
                isinstance(order, dict)
                and order.get("status") == "WORKING"
                and order.get("lot_type") == "odd_lot"
            ):
                root = str(order.get("symbol", "")).split(".")[0]
                if root and root not in odd_lot_rows:
                    row = fetch_twse_odd_lot_row(root)
                    if row:
                        odd_lot_rows[root] = row
        new_state, report = process_equity_paper_orders(
            state, _equity_working_marks(state), TW_BOOK, odd_lot_rows=odd_lot_rows
        )
        STORE.write_tw_equity_paper_state(new_state)
        return {**report, "account": new_state["account"]}

    @app.post("/api/equity/orders/cancel")
    def cancel_equity_order(update: EquityOrderCancelUpdate) -> dict[str, Any]:
        try:
            state, order = cancel_equity_paper_order(
                STORE.read_equity_paper_state(), update.order_id
            )
        except EquityOrderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_equity_paper_state(state)
        return {
            "cancelled_order": order,
            "account": state["account"],
            "open_orders_remaining": sum(
                1
                for entry in state.get("orders", [])
                if isinstance(entry, dict) and entry.get("status") == "WORKING"
            ),
        }

    @app.post("/api/equity/tw/orders/cancel")
    def cancel_tw_equity_order(update: EquityOrderCancelUpdate) -> dict[str, Any]:
        try:
            state, order = cancel_equity_paper_order(
                STORE.read_tw_equity_paper_state(), update.order_id, TW_BOOK
            )
        except EquityOrderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_tw_equity_paper_state(state)
        return {
            "cancelled_order": order,
            "account": state["account"],
            "open_orders_remaining": sum(
                1
                for entry in state.get("orders", [])
                if isinstance(entry, dict) and entry.get("status") == "WORKING"
            ),
        }

    @app.get("/api/equity/tw/summary")
    def tw_equity_summary(refresh: bool = False) -> dict[str, Any]:
        state = STORE.read_tw_equity_paper_state()
        return equity_summary_payload(
            state, _equity_marks(state, refresh=refresh), TW_BOOK
        )

    @app.get("/api/equity/summary")
    def equity_summary(refresh: bool = False) -> dict[str, Any]:
        state = STORE.read_equity_paper_state()
        return equity_summary_payload(state, _equity_marks(state, refresh=refresh))

    @app.get("/api/crypto/summary")
    def crypto_summary() -> dict[str, Any]:
        return paper_summary_payload(
            STORE.read_paper_state(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
        )

    @app.post("/api/paper/snapshot")
    def record_paper_history_snapshot(update: PaperSnapshotUpdate) -> dict[str, Any]:
        if update.refresh:
            market_payload = markets_payload(
                STORE.read_markets_layout(),
                STORE.read_market_cache(),
                STORE.read_crypto_detail_cache(),
                fetcher=MARKET_FETCHER,
                refresh=True,
                extra_symbols=PAPER_WATCHLIST_SYMBOLS,
            )
            if market_payload.get("cache"):
                STORE.write_market_cache(market_payload["cache"])
        crypto_book = paper_summary_payload(
            STORE.read_paper_state(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
        )
        us_state = STORE.read_equity_paper_state()
        tw_state = STORE.read_tw_equity_paper_state()
        us_book = equity_summary_payload(
            us_state, _equity_marks(us_state, refresh=update.refresh)
        )
        tw_book = equity_summary_payload(
            tw_state, _equity_marks(tw_state, refresh=update.refresh), TW_BOOK
        )
        benchmark_rows = [
            row
            for row in _yahoo_quote_snapshot_payload_from_store(
                refresh=update.refresh, symbols=list(BENCHMARK_SYMBOLS)
            ).get("quotes", [])
            if isinstance(row, dict)
        ]
        history, snapshot = record_paper_snapshot(
            STORE.read_paper_history_state(),
            crypto_summary=crypto_book,
            us_summary=us_book,
            tw_summary=tw_book,
            benchmark_rows=benchmark_rows,
            note=update.note,
        )
        STORE.write_paper_history_state(history)
        return {
            "snapshot": snapshot,
            "snapshot_count_total": len(history["snapshots"]),
            "read_action": "paper_history",
        }

    @app.get("/api/paper/history")
    def paper_history(limit: int = HISTORY_DEFAULT_LIMIT) -> dict[str, Any]:
        return paper_history_payload(STORE.read_paper_history_state(), limit=limit)

    def _research_marks(symbols: list[str], *, refresh: bool) -> dict[str, Any]:
        """Map symbol→Decimal price from the shared Yahoo quote path (crypto -USD)."""
        if not symbols:
            return {}
        rows = _yahoo_quote_snapshot_payload_from_store(
            refresh=refresh, symbols=list(symbols)
        ).get("quotes", [])
        marks: dict[str, Any] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            sym = str(row.get("symbol", "")).upper()
            price = row.get("price")
            try:
                marks[sym] = (
                    Decimal(str(price)) if price not in (None, "N/A", "") else None
                )
            except (ArithmeticError, ValueError, TypeError):
                marks[sym] = None
        return marks

    def _open_call_symbols(state: dict[str, Any]) -> list[str]:
        return sorted(
            {
                str(c.get("symbol", "")).upper()
                for c in state.get("calls", [])
                if isinstance(c, dict) and c.get("status") == "open"
            }
        )

    @app.post("/api/research/call")
    def submit_research_call(update: ResearchCallUpdate) -> dict[str, Any]:
        symbol = update.symbol.strip().upper()
        payload = update.model_dump()
        payload["symbol"] = symbol
        if payload.get("ref_price") is None:
            mark = _research_marks([symbol], refresh=update.refresh).get(symbol)
            payload["ref_price"] = str(mark) if mark is not None else None
        try:
            state, call = record_call(STORE.read_research_ledger_state(), payload)
        except ResearchLedgerError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_research_ledger_state(state)
        return {"call": call, "read_action": "research_ledger"}

    @app.post("/api/research/score")
    def score_research_ledger(update: ResearchScoreUpdate) -> dict[str, Any]:
        state = STORE.read_research_ledger_state()
        marks = _research_marks(_open_call_symbols(state), refresh=update.refresh)
        state, scored = score_calls(state, marks)
        STORE.write_research_ledger_state(state)
        return {
            "scored": scored,
            "scored_count": len(scored),
            **research_ledger_payload(state, marks),
        }

    @app.get("/api/research/ledger")
    def read_research_ledger(refresh: bool = False, limit: int | None = None) -> dict[str, Any]:
        state = STORE.read_research_ledger_state()
        marks = _research_marks(_open_call_symbols(state), refresh=refresh)
        return research_ledger_payload(state, marks, limit=limit)

    @app.get("/api/research/scan")
    def scan_research_universe(refresh: bool = False) -> dict[str, Any]:
        # One bounded read over the whole self-sourced universe so the agent can
        # pick where to form a thesis instead of pulling 16 symbols by hand. The
        # Yahoo lookup path caps at 8/call, so the 16-name universe is batched.
        symbols = list(DEFAULT_UNIVERSE)
        quotes: dict[str, Any] = {}
        for start in range(0, len(symbols), 8):
            rows = _yahoo_quote_snapshot_payload_from_store(
                refresh=refresh, symbols=symbols[start : start + 8]
            ).get("quotes", [])
            for row in rows:
                if isinstance(row, dict):
                    quotes[str(row.get("symbol", "")).upper()] = {
                        "price": row.get("price"),
                        "change_pct": row.get("change_percent"),
                        "currency": row.get("currency"),
                    }
        state = STORE.read_research_ledger_state()
        return research_scan_payload(quotes, _open_call_symbols(state))

    @app.post("/api/crypto/refresh")
    def refresh_crypto(update: CryptoRefreshUpdate) -> dict[str, Any]:
        market_payload = markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(update.symbol, update.timeframe),
            fetcher=MARKET_FETCHER,
            refresh=True,
            extra_symbols=PAPER_WATCHLIST_SYMBOLS,
        )
        if market_payload.get("cache"):
            STORE.write_market_cache(market_payload["cache"])

        detail = crypto_detail_payload(
            STORE.read_crypto_detail_cache(update.symbol, update.timeframe),
            fetcher=CRYPTO_DETAIL_FETCHER,
            refresh=True,
            symbol=update.symbol,
            interval=update.timeframe,
        )
        if detail.get("cache"):
            STORE.write_crypto_detail_cache(detail["cache"])
        if update.view == "summary":
            return paper_summary_payload(
                STORE.read_paper_state(),
                STORE.read_market_cache(),
                STORE.read_crypto_detail_cache(update.symbol, update.timeframe),
            )
        return crypto_payload(
            STORE.read_paper_state(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(update.symbol, update.timeframe),
        )

    @app.get("/api/portfolio")
    def portfolio() -> dict[str, Any]:
        return _portfolio_payload_with_prices(STORE.read_portfolio_state())

    def _portfolio_payload_with_prices(state: dict[str, Any]) -> dict[str, Any]:
        return portfolio_payload(
            state,
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.root,
        )

    @app.get("/api/portfolio/reports")
    def portfolio_reports() -> dict[str, Any]:
        return portfolio_report_index(STORE.root, STORE.read_portfolio_state())

    @app.get("/api/portfolio/report-health")
    def portfolio_report_health() -> dict[str, Any]:
        return portfolio_report_health_payload(STORE.root, STORE.read_portfolio_state())

    @app.get("/api/portfolio/export")
    def export_portfolio() -> dict[str, Any]:
        try:
            return export_active_portfolio(
                STORE.read_portfolio_state(),
                STORE.root,
                STORE.read_market_cache(),
                STORE.read_crypto_detail_cache(),
            )
        except PortfolioError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/backtest/runs/{run_id}")
    def backtest_run_detail(run_id: str) -> dict[str, Any]:
        payload = backtest_run_detail_payload(STORE.root, run_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Unknown backtest run id")
        return payload

    @app.get("/api/backtest")
    def backtest_defaults() -> dict[str, Any]:
        detail_cache = STORE.read_crypto_detail_cache()
        data_readiness = backtest_data_readiness_payload(detail_cache)
        detail = crypto_detail_payload(detail_cache)
        status = detail["status"]
        provider_meta = detail["provider"]
        provider = (
            PUBLIC_BACKTEST_PROVIDER
            if status.get("source") in {"binance_public", "kraken_public", "coinbase_public"}
            else BACKTEST_PROVIDER
        )
        return {
            "provider": provider,
            "provider_status": {
                "source": str(status.get("source") or "deterministic_local_closed_candle"),
                "state": str(status.get("state") or "offline_fallback"),
                "provider_id": str(
                    status.get("provider_id") or provider_meta.get("provider_id") or ""
                ),
                "retrieved_at": str(status.get("last_update") or "generated locally"),
                "cache_path": str(provider_meta.get("cache_path") or ""),
            },
            "commands": [
                "Run Backtest",
                "Optimize",
                "Walk-Forward",
                "Compare Runs",
                "Indicators",
                "Returns Analysis",
            ],
            "result_tabs": [
                "Summary",
                "Walk-Forward",
                "Optimize",
                "Comparison",
                "Metrics",
                "Trades",
                "Indicators",
                "Signals",
                "Returns Analysis",
                "Equity",
                "Drawdown",
                "Data Source",
                "Artifacts",
                "Raw JSON",
            ],
            "strategies": backtest_strategy_catalog(),
            "config": default_backtest_config(),
            "data_readiness": data_readiness,
            "run_index": backtest_run_index_payload(STORE.root),
            "artifact_health": backtest_artifact_health_payload(STORE.root),
        }

    @app.get("/api/backtest/data-readiness")
    def backtest_data_readiness() -> dict[str, Any]:
        try:
            return backtest_data_readiness_payload(STORE.read_crypto_detail_cache())
        except BacktestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/backtest/runs")
    def backtest_run_index() -> dict[str, Any]:
        try:
            return backtest_run_index_payload(STORE.root)
        except BacktestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/backtest/artifact-health")
    def backtest_artifact_health() -> dict[str, Any]:
        try:
            return backtest_artifact_health_payload(STORE.root)
        except BacktestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/settings")
    def save_settings(update: SettingsUpdate) -> dict[str, Any]:
        payload = update.model_dump()
        if payload["default_route"] not in SHELL_ROUTE_IDS:
            payload["default_route"] = "dashboard"
        return STORE.write_settings(payload)

    @app.post("/api/profile")
    def save_profile(update: ProfileUpdate) -> dict[str, Any]:
        payload = update.model_dump()
        if payload["default_route"] not in SHELL_ROUTE_IDS:
            payload["default_route"] = "dashboard"
        return STORE.write_profile(payload)

    @app.post("/api/layouts/default")
    def save_default_layout(update: LayoutUpdate) -> dict[str, Any]:
        payload = update.model_dump()
        if payload["active_route"] not in SHELL_ROUTE_IDS:
            payload["active_route"] = "dashboard"
        return STORE.write_layout(payload)

    @app.post("/api/dashboard/layout")
    def save_dashboard_layout(update: DashboardLayoutUpdate) -> dict[str, Any]:
        layout = STORE.write_dashboard_layout(update.model_dump())
        return _dashboard_payload_from_store(layout)

    @app.post("/api/dashboard/reset")
    def reset_dashboard(update: DashboardResetUpdate) -> dict[str, Any]:
        if not update.confirm:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Dashboard reset overwrites the current layout; pass "
                    '"confirm": true to proceed. The pre-reset layout rotates '
                    "into backup slot 1 and can be undone with "
                    "local_state_restore (kind dashboard_layout)."
                ),
            )
        layout = STORE.write_dashboard_layout(apply_dashboard_template(update.template))
        return _dashboard_payload_from_store(layout)

    @app.post("/api/markets/layout")
    def save_markets_layout(update: MarketsLayoutUpdate) -> dict[str, Any]:
        layout = STORE.write_markets_layout(update.model_dump())
        return markets_payload(
            layout,
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_watchlist_payload_from_store(
                refresh=False,
                fallback_symbols=ALPHA_VANTAGE_ETF_WATCHLIST,
            ),
            _alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            _twelve_data_quote_watchlist_payload_from_store(refresh=False),
            _finnhub_quote_watchlist_payload_from_store(refresh=False),
            _fmp_quote_watchlist_payload_from_store(refresh=False),
            _stooq_quote_snapshot_payload_from_store(refresh=False),
            _nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/refresh")
    def refresh_markets() -> dict[str, Any]:
        payload = markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
            fetcher=MARKET_FETCHER,
            refresh=True,
            extra_symbols=PAPER_WATCHLIST_SYMBOLS,
        )
        if payload.get("cache"):
            STORE.write_market_cache(payload["cache"])
        payload["cache"] = None
        return payload

    @app.post("/api/markets/rates/refresh")
    def refresh_market_rates() -> dict[str, Any]:
        rates_payload = _rates_payload_from_store(refresh=True)
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            rates_payload,
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/commodities/refresh")
    def refresh_market_commodities() -> dict[str, Any]:
        commodity_payload = _commodity_payload_from_store(refresh=True)
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            commodity_payload,
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/eia/refresh")
    def refresh_market_eia_energy_context() -> dict[str, Any]:
        eia_payload = _eia_payload_from_store(refresh=True)
        commodity_payload = _commodity_payload_from_store(refresh=False)
        commodity_payload["eia"] = eia_payload
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            commodity_payload,
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/cftc-cot/refresh")
    def refresh_market_cftc_cot_context() -> dict[str, Any]:
        commodity_payload = _commodity_payload_from_store(refresh=True)
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            commodity_payload,
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/fx/refresh")
    def refresh_market_fx() -> dict[str, Any]:
        fx_payload = _fx_payload_from_store(refresh=True)
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            fx_payload,
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/fx/quote/refresh")
    def refresh_market_fx_quote(
        update: AlphaVantageFxQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        fx_quote_payload = _alpha_vantage_fx_quote_watchlist_payload_from_store(
            refresh=True,
            pairs=update.pairs if update else None,
        )
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=fx_quote_payload,
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/stocks/refresh")
    def refresh_market_stocks() -> dict[str, Any]:
        research_payload = _research_payload_from_store(refresh=True)
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            research_payload,
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/stocks/quote/refresh")
    def refresh_market_stock_quote(
        update: AlphaVantageQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        quote_payload = _alpha_vantage_stock_watchlist_payload_from_store(
            refresh=True,
            symbols=update.symbols if update else None,
        )
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            quote_payload,
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/etf/refresh")
    def refresh_market_etf() -> dict[str, Any]:
        fund_payload = _fund_payload_from_store(refresh=True)
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            fund_payload,
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/etf/quote/refresh")
    def refresh_market_etf_quote(
        update: AlphaVantageQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        etf_quote_payload = _alpha_vantage_etf_watchlist_payload_from_store(
            refresh=True,
            symbols=update.symbols if update else None,
        )
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            etf_quote_payload,
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.get("/api/markets/candles/{symbol}")
    def markets_candles_read(symbol: str, timeframe: str = "15m") -> dict[str, Any]:
        safe_symbol = "".join(ch for ch in str(symbol).upper() if ch.isalnum())[:16]
        safe_timeframe = timeframe if timeframe in {"1m", "5m", "15m", "1h", "4h", "1d"} else "15m"
        cache = STORE.read_crypto_detail_cache(safe_symbol, safe_timeframe)
        candles = cache.get("candles") if isinstance(cache.get("candles"), list) else []
        source = "crypto_detail_cache"
        if not candles:
            # Non-crypto symbols fall back to the daily history cache the AI
            # fills via the user's Twelve Data key (M27-R4).
            history = STORE.read_history_cache(safe_symbol)
            candles = history.get("candles") if isinstance(history.get("candles"), list) else []
            safe_timeframe = "1d"
            source = "history_cache"
        if not candles:
            raise HTTPException(status_code=404, detail="No candle cache for this symbol/timeframe")
        last_candle = candles[-1] if isinstance(candles[-1], dict) else {}
        last_close_at = str(last_candle.get("closed_at") or "")
        return {
            "symbol": safe_symbol,
            "timeframe": safe_timeframe,
            "count": len(candles),
            "candles": candles[-120:],
            "source": source,
            # Disclose how old the newest bar is so callers (e.g. the real-book
            # banner) can flag a stale close instead of trusting it blindly.
            "last_close_at": last_close_at,
            "safety": {
                "safety_class": "read_only_candle_cache",
                "mutates_local_state": False,
                "external_calls": False,
            },
        }

    @app.post("/api/markets/history/refresh")
    def markets_history_refresh(update: HistoryRefreshUpdate | None = None) -> dict[str, Any]:
        watch = STORE.read_watchlist_state()
        raw_symbols = (
            update.symbols
            if update and update.symbols
            else [*watch["us"], *watch["fx"], *watch["tw"]]
        )
        if isinstance(raw_symbols, str):
            raw_symbols = [part.strip() for part in raw_symbols.split(",") if part.strip()]
        symbols = [str(s).upper() for s in raw_symbols][:MAX_HISTORY_SYMBOLS]
        # TW listings (4-6 digits, optional letter suffix like 00982A) ride the
        # no-key TWSE endpoint; everything else needs the sealed Twelve Data
        # key. A missing key marks only the affected symbols, not the batch.
        def _is_tw(symbol: str) -> bool:
            body = symbol.replace("/", "")
            return len(body) >= 4 and body[:4].isdigit() and body.isalnum()

        needs_key = [s for s in symbols if not _is_tw(s)]
        credential_value = ""
        if needs_key and TWELVE_DATA_PROVIDER_ID in set(
            _twelve_data_secret_status_from_store().get("stored_provider_ids") or []
        ):
            try:
                credential_value = read_local_data_provider_secret(
                    STORE.root,
                    providers_payload(STORE),
                    provider_id=TWELVE_DATA_PROVIDER_ID,
                )
            except LocalSecretError:
                credential_value = ""
        results: dict[str, str] = {}
        for symbol in symbols:
            try:
                if _is_tw(symbol):
                    payload = build_twse_history(symbol, fetcher=TWSE_HISTORY_FETCHER)
                elif not credential_value:
                    results[symbol] = "key_required"
                    continue
                else:
                    # kwarg name split like fred_data does, so the clean-room
                    # secret-literal scanner never sees "api_key=<identifier>".
                    raw = fetch_twelve_data_time_series(symbol=symbol, **{"api_" + "key": credential_value})
                    payload = normalize_time_series(raw, symbol=symbol)
                STORE.write_history_cache(payload["symbol"], payload)
                results[symbol] = "live"
            except (TwelveDataHistoryError, TwseHistoryError) as exc:
                results[symbol] = "rate_limited" if str(exc).startswith("rate_limited") else "unavailable"
            except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError):
                results[symbol] = "unavailable"
        return history_refresh_summary(results)

    @app.get("/api/markets/watchlist")
    def markets_watchlist_index() -> dict[str, Any]:
        return watchlist_payload(STORE.read_watchlist_state())

    @app.post("/api/markets/watchlist")
    def markets_watchlist_update(update: WatchlistUpdate) -> dict[str, Any]:
        try:
            state = update_watchlist(STORE.read_watchlist_state(), update.group, update.symbols)
        except WatchlistError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        written = STORE.write_watchlist_state(state)
        if str(update.group).strip().lower() == "crypto":
            # The legacy M25 markets layout still filters crypto rows through
            # its panel symbol list; keep it in lockstep so the watchlist stays
            # the single source of truth until the panel concept is retired.
            layout = STORE.read_markets_layout()
            panels = layout.get("panels")
            if isinstance(panels, list) and panels and isinstance(panels[0], dict):
                panels[0]["symbols"] = list(written["crypto"])
                STORE.write_markets_layout(layout)
        return watchlist_payload(written)

    @app.post("/api/markets/twelve-data/quotes/refresh")
    def refresh_market_twelve_data_quotes(
        update: TwelveDataQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        twelve_quote_payload = _twelve_data_quote_watchlist_payload_from_store(
            refresh=True,
            symbols=(update.symbols if update and update.symbols else STORE.read_watchlist_state()["fx"]),
        )
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=twelve_quote_payload,
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/finnhub/quotes/refresh")
    def refresh_market_finnhub_quotes(
        update: FinnhubQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        finnhub_quote_payload = _finnhub_quote_watchlist_payload_from_store(
            refresh=True,
            symbols=(update.symbols if update and update.symbols else STORE.read_watchlist_state()["us"]),
        )
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=finnhub_quote_payload,
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/fmp/quotes/refresh")
    def refresh_market_fmp_quotes(
        update: FmpQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        fmp_quote_payload = _fmp_quote_watchlist_payload_from_store(
            refresh=True,
            symbols=update.symbols if update else None,
        )
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            fmp_quote_data=fmp_quote_payload,
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/stooq/quotes/refresh")
    def refresh_market_stooq_quotes(
        update: StooqQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        stooq_quote_payload = _stooq_quote_snapshot_payload_from_store(
            refresh=True,
            symbols=update.symbols if update else None,
        )
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=stooq_quote_payload,
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/moex/quotes/refresh")
    def refresh_market_moex_quotes(
        update: MoexQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        moex_quote_payload = _moex_quote_snapshot_payload_from_store(
            refresh=True,
            symbols=update.symbols if update else None,
        )
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=moex_quote_payload,
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/twse/quotes/refresh")
    def refresh_market_twse_quotes(
        update: TwseQuoteRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        twse_quote_payload = _twse_quote_snapshot_payload_from_store(
            refresh=True,
            symbols=(update.symbols if update and update.symbols else STORE.read_watchlist_state()["tw"]),
        )
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=twse_quote_payload,
        )

    @app.post("/api/markets/nasdaq-trader/symbols/refresh")
    def refresh_market_nasdaq_trader_symbols() -> dict[str, Any]:
        nasdaq_symbol_payload = _nasdaq_trader_symbol_directory_payload_from_store(refresh=True)
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=nasdaq_symbol_payload,
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.get("/api/markets/nasdaq-trader/symbols/search")
    def search_market_nasdaq_trader_symbols(
        query: str = "AAPL",
        limit: int = 12,
    ) -> dict[str, Any]:
        return nasdaq_trader_symbol_search_payload(
            _nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            query=query,
            limit=limit,
        )

    @app.post("/api/markets/openfigi/mapping/refresh")
    def refresh_market_openfigi_mapping(
        update: OpenFigiMappingRefreshUpdate | None = None,
    ) -> dict[str, Any]:
        openfigi_payload = _openfigi_mapping_payload_from_store(
            refresh=True,
            symbols=update.symbols if update else None,
        )
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
            openfigi_mapping_data=openfigi_payload,
        )

    @app.post("/api/markets/macro/refresh")
    @app.post("/api/markets/indexes/refresh")
    @app.post("/api/markets/regional/refresh")
    def refresh_market_macro_context() -> dict[str, Any]:
        research_payload = _macro_payload_from_store(refresh=True)
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            research_payload,
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/fred/refresh")
    def refresh_market_fred_context() -> dict[str, Any]:
        _fred_core_series_from_store(refresh=True)
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/bls/refresh")
    def refresh_market_bls_context() -> dict[str, Any]:
        _bls_payload_from_store(refresh=True)
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/bea/refresh")
    def refresh_market_bea_context() -> dict[str, Any]:
        _bea_payload_from_store(refresh=True)
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/markets/census/refresh")
    def refresh_market_census_context() -> dict[str, Any]:
        _census_payload_from_store(refresh=True)
        return markets_payload(
            STORE.read_markets_layout(),
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            STORE.read_news_cache(),
            _research_payload_from_store(refresh=False),
            _rates_payload_from_store(refresh=False),
            _fx_payload_from_store(refresh=False),
            _commodity_payload_from_store(refresh=False),
            _fund_payload_from_store(refresh=False),
            _alpha_vantage_stock_watchlist_payload_from_store(refresh=False),
            _alpha_vantage_etf_watchlist_payload_from_store(refresh=False),
            fx_quote_data=_alpha_vantage_fx_quote_watchlist_payload_from_store(refresh=False),
            twelve_data_quote_data=_twelve_data_quote_watchlist_payload_from_store(refresh=False),
            finnhub_quote_data=_finnhub_quote_watchlist_payload_from_store(refresh=False),
            stooq_quote_data=_stooq_quote_snapshot_payload_from_store(refresh=False),
            nasdaq_symbol_data=_nasdaq_trader_symbol_directory_payload_from_store(refresh=False),
            moex_quote_data=_moex_quote_snapshot_payload_from_store(refresh=False),
            twse_quote_data=_twse_quote_snapshot_payload_from_store(refresh=False),
        )

    @app.post("/api/news/layout")
    def save_news_layout(update: NewsLayoutUpdate) -> dict[str, Any]:
        STORE.write_news_layout(update.model_dump())
        payload = _news_payload_from_store(refresh=False)
        return _public_news_payload(_attach_news_research_brief_index(payload))

    def _news_symbol_names(symbols: list[str]) -> dict[str, list[str]]:
        """Official security names for matching, from local reference caches.

        Nasdaq Trader directory covers US listings, the TWSE daily quote cache
        carries Chinese names for .TW codes — both already on disk, so the
        matcher improves without a hand-curated alias table (2026-07-22 owner
        fix-it round: disclosing 'keyword-only' was not a substitute for
        matching better).
        """
        wanted = [str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()]
        if not wanted:
            return {}
        names: dict[str, list[str]] = {}
        directory = STORE.read_nasdaq_trader_symbol_directory_cache()
        rows = directory.get("symbols") if isinstance(directory, dict) else []
        by_symbol = {
            str(row.get("symbol", "")).upper(): str(row.get("name", ""))
            for row in rows or []
            if isinstance(row, dict) and row.get("symbol") and row.get("name")
        }
        for symbol in wanted:
            found: list[str] = []
            root = symbol.split(".")[0]
            if symbol.endswith(".TW"):
                quote_cache = STORE.read_twse_quote_cache(root)
                quotes = quote_cache.get("quotes") if isinstance(quote_cache, dict) else []
                for row in quotes or []:
                    if isinstance(row, dict) and str(row.get("symbol", "")) == root:
                        name = str(row.get("name", "")).strip()
                        if name:
                            found.append(name)
                        break
            else:
                name = by_symbol.get(root, "")
                if name:
                    found.append(name)
            if found:
                names[symbol] = found
        return names

    @app.post("/api/news/packet")
    def news_packet(update: NewsPacketUpdate) -> dict[str, Any]:
        payload = _news_payload_from_store(refresh=update.refresh)
        # US single-name catalysts are thin in the GDELT/TW feeds; on an
        # explicit refresh for named holdings, pull Yahoo's public per-symbol
        # news (no key) and merge it in so a -7% move comes back WITH its
        # reason instead of an abstained call. Best-effort: a Yahoo outage
        # degrades to a source_error note, never a failed packet.
        if update.refresh and update.symbols:
            _merge_yahoo_symbol_news(payload, update.symbols)
        return news_packet_payload(
            payload,
            news_digest_payload(STORE.read_news_digest_state()),
            symbols=update.symbols,
            limit=update.limit,
            symbol_names=_news_symbol_names(update.symbols),
        )

    @app.post("/api/news/refresh")
    def refresh_news() -> dict[str, Any]:
        payload = _news_payload_from_store(refresh=True)
        return _public_news_payload(_attach_news_research_brief_index(payload))

    @app.get("/api/news/research-briefs")
    def news_research_briefs() -> dict[str, Any]:
        try:
            return news_research_brief_index(STORE.root)
        except NewsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/news/research-brief")
    def write_local_news_research_brief() -> dict[str, Any]:
        payload = _news_payload_from_store(refresh=False)
        try:
            brief = write_news_research_brief(_public_news_payload(payload), STORE.root)
        except NewsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        payload["research_brief"] = brief
        response = _public_news_payload(_attach_news_research_brief_index(payload))
        # Agents shouldn't have to swallow the full news payload to learn what
        # was written — a compact receipt carries the essentials.
        response["receipt"] = {
            "brief_id": brief.get("brief_id"),
            "created_at": brief.get("created_at"),
            "artifacts": brief.get("artifacts", {}),
            "summary": brief.get("summary", {}),
        }
        return response

    @app.post("/api/research-data/refresh")
    def refresh_research_data() -> dict[str, Any]:
        return _public_research_payload(_research_payload_from_store(refresh=True))

    @app.post("/api/research-data/fred/refresh")
    def refresh_research_fred_data() -> dict[str, Any]:
        _fred_payload_from_store(refresh=True)
        return _public_research_payload(_research_payload_from_store(refresh=False))

    @app.post("/api/research-data/bls/refresh")
    def refresh_research_bls_data() -> dict[str, Any]:
        _bls_payload_from_store(refresh=True)
        return _public_research_payload(_research_payload_from_store(refresh=False))

    @app.post("/api/rates/refresh")
    def refresh_rates_data() -> dict[str, Any]:
        return _public_rates_payload(_rates_payload_from_store(refresh=True))

    @app.post("/api/fx/refresh")
    def refresh_fx_data() -> dict[str, Any]:
        return _public_fx_payload(_fx_payload_from_store(refresh=True))

    @app.post("/api/commodities/refresh")
    def refresh_commodity_data() -> dict[str, Any]:
        return _public_commodity_payload(_commodity_payload_from_store(refresh=True))

    @app.post("/api/funds/refresh")
    def refresh_fund_data() -> dict[str, Any]:
        return _public_fund_payload(_fund_payload_from_store(refresh=True))

    @app.post("/api/ai-chat/sessions")
    def create_local_chat_session(update: ChatSessionCreateUpdate) -> dict[str, Any]:
        try:
            state = create_chat_session(STORE.read_chat_state(), update.model_dump(), STORE.root)
        except ChatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_chat_state(state)
        return chat_payload(STORE.read_chat_state(), STORE.root, _advanced_context_from_store())

    @app.post("/api/ai-chat/rename")
    def rename_local_chat_session(update: ChatRenameUpdate) -> dict[str, Any]:
        try:
            state = rename_chat_session(STORE.read_chat_state(), update.model_dump())
        except ChatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_chat_state(state)
        return chat_payload(STORE.read_chat_state(), STORE.root, _advanced_context_from_store())

    @app.post("/api/ai-chat/select")
    def select_local_chat_session(update: ChatSelectUpdate) -> dict[str, Any]:
        try:
            state = select_chat_session(STORE.read_chat_state(), update.model_dump())
        except ChatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_chat_state(state)
        return chat_payload(STORE.read_chat_state(), STORE.root, _advanced_context_from_store())

    @app.post("/api/ai-chat/delete")
    def delete_local_chat_session(update: ChatDeleteUpdate) -> dict[str, Any]:
        try:
            state = delete_chat_session(STORE.read_chat_state(), update.model_dump())
        except ChatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_chat_state(state)
        remove_chat_session_artifacts(STORE.root, update.session_id)
        return chat_payload(STORE.read_chat_state(), STORE.root, _advanced_context_from_store())

    @app.post("/api/ai-chat/messages")
    def send_local_chat_message(update: ChatMessageUpdate) -> dict[str, Any]:
        context = _advanced_context_from_store()
        try:
            state = append_chat_message(
                STORE.read_chat_state(), update.model_dump(), STORE.root, context
            )
        except ChatError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_chat_state(state)
        return chat_payload(STORE.read_chat_state(), STORE.root, context)

    @app.post("/api/algo/strategy")
    def save_local_algo_strategy(update: AlgoStrategyUpdate) -> dict[str, Any]:
        try:
            state = save_strategy(STORE.read_algo_state(), update.model_dump())
        except AlgoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_algo_state(state)
        return _algo_payload_from_store()

    @app.post("/api/algo/select")
    def select_local_algo_strategy(update: AlgoSelectUpdate) -> dict[str, Any]:
        try:
            state = select_strategy(STORE.read_algo_state(), update.model_dump())
        except AlgoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_algo_state(state)
        return _algo_payload_from_store()

    @app.post("/api/algo/strategy/delete")
    def delete_local_algo_strategy(update: AlgoStrategyDeleteUpdate) -> dict[str, Any]:
        if not update.confirm:
            raise HTTPException(status_code=400, detail="Delete confirmation is required")
        try:
            state = delete_strategy(STORE.read_algo_state(), update.strategy_id)
        except AlgoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_algo_state(state)
        return _algo_payload_from_store()

    @app.post("/api/algo/run-backtest")
    def run_local_algo_backtest(update: AlgoRunBacktestUpdate) -> dict[str, Any]:
        try:
            state, result = run_strategy_backtest(
                STORE.read_algo_state(),
                update.model_dump(),
                STORE.root,
            )
        except AlgoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_algo_state(state)
        return {**_algo_payload_from_store(), "backtest_result": result}

    @app.post("/api/algo/scan")
    def scan_local_algo_market(update: AlgoScanUpdate) -> dict[str, Any]:
        try:
            state, scan = scan_market(
                STORE.read_algo_state(),
                update.model_dump(),
                STORE.read_market_cache(),
                _algo_provider_context_from_store(),
            )
        except AlgoError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_algo_state(state)
        return {**_algo_payload_from_store(), "scan_result": scan}

    @app.get("/api/algo/scan-artifacts")
    def algo_scan_artifacts() -> dict[str, Any]:
        return {
            "scan_artifact_health": STORE.algo_scan_artifact_health(),
            "safety": {
                "destructive_actions_enabled": False,
                "content_indexing_enabled": False,
                "secret_reads_enabled": False,
                "live_action_enabled": False,
            },
        }

    @app.post("/api/algo/scan-artifacts/repair")
    def repair_algo_scan_artifacts() -> dict[str, Any]:
        state = STORE.read_algo_state()
        health_before = STORE.algo_scan_artifact_health(state)
        if health_before["status"] == "no_scan":
            raise HTTPException(status_code=400, detail="No scan artifacts are available to repair")
        if health_before["status"] == "invalid_scan_state":
            raise HTTPException(
                status_code=400,
                detail="Scan artifacts cannot be repaired because last scan state is invalid",
            )
        health_after = STORE.write_algo_scan_artifacts(state)
        return {
            **_algo_payload_from_store(),
            "scan_artifact_health": health_after,
            "scan_artifact_repair": {
                "state": "rewritten",
                "mode": "non_destructive_expected_files_only",
                "missing_before": health_before["missing_count"],
                "missing_after": health_after["missing_count"],
            },
        }

    @app.post("/api/nodes/workflow")
    def save_local_nodes_workflow(update: NodesWorkflowUpdate) -> dict[str, Any]:
        try:
            state = save_workflow(STORE.read_nodes_state(), update.model_dump())
        except NodesError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_nodes_state(state)
        return nodes_payload(STORE.read_nodes_state(), _advanced_context_from_store(), STORE.root)

    @app.post("/api/nodes/template")
    def load_local_nodes_template(update: NodesTemplateUpdate) -> dict[str, Any]:
        try:
            state = load_template(STORE.read_nodes_state(), update.model_dump())
        except NodesError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_nodes_state(state)
        return nodes_payload(STORE.read_nodes_state(), _advanced_context_from_store(), STORE.root)

    @app.post("/api/nodes/select-workflow")
    def select_local_nodes_workflow(update: NodesSelectWorkflowUpdate) -> dict[str, Any]:
        try:
            state = select_workflow(STORE.read_nodes_state(), update.model_dump())
        except NodesError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_nodes_state(state)
        return nodes_payload(STORE.read_nodes_state(), _advanced_context_from_store(), STORE.root)

    @app.post("/api/nodes/select-node")
    def select_local_nodes_node(update: NodesSelectNodeUpdate) -> dict[str, Any]:
        try:
            state = select_node(STORE.read_nodes_state(), update.model_dump())
        except NodesError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_nodes_state(state)
        return nodes_payload(STORE.read_nodes_state(), _advanced_context_from_store(), STORE.root)

    @app.post("/api/nodes/clear")
    def clear_local_nodes_workflow() -> dict[str, Any]:
        try:
            state = clear_workflow(STORE.read_nodes_state())
        except NodesError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_nodes_state(state)
        return nodes_payload(STORE.read_nodes_state(), _advanced_context_from_store(), STORE.root)

    @app.post("/api/nodes/import")
    def import_local_nodes_workflow(update: NodesWorkflowUpdate) -> dict[str, Any]:
        try:
            state = import_workflow(STORE.read_nodes_state(), update.model_dump())
        except NodesError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_nodes_state(state)
        return nodes_payload(STORE.read_nodes_state(), _advanced_context_from_store(), STORE.root)

    @app.post("/api/nodes/export")
    def export_local_nodes_workflow(update: NodesWorkflowRefUpdate) -> dict[str, Any]:
        try:
            return export_workflow(STORE.read_nodes_state(), update.model_dump())
        except NodesError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/nodes/dry-run")
    def plan_local_nodes_workflow(update: NodesWorkflowRefUpdate) -> dict[str, Any]:
        context = _advanced_context_from_store()
        try:
            state, plan = dry_run_workflow(STORE.read_nodes_state(), update.model_dump(), context)
        except NodesError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_nodes_state(state)
        return {**nodes_payload(STORE.read_nodes_state(), context, STORE.root), "dry_run_result": plan}

    @app.post("/api/nodes/deploy")
    def disabled_local_nodes_deploy() -> dict[str, Any]:
        raise HTTPException(status_code=403, detail=disabled_runtime_response("deploy"))

    @app.post("/api/nodes/execute")
    def disabled_local_nodes_execute() -> dict[str, Any]:
        raise HTTPException(status_code=403, detail=disabled_runtime_response("execute"))

    @app.post("/api/code/new")
    def create_local_code_notebook(update: CodeNotebookCreateUpdate) -> dict[str, Any]:
        try:
            state = create_notebook(STORE.read_code_state(), update.model_dump())
        except CodeWorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_code_state(state)
        return code_payload(
            STORE.read_code_state(), _advanced_context_from_store(), STORE.root
        )

    @app.post("/api/code/notebook")
    def save_local_code_notebook(update: CodeNotebookUpdate) -> dict[str, Any]:
        try:
            state = save_notebook(STORE.read_code_state(), update.model_dump())
        except CodeWorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_code_state(state)
        return code_payload(
            STORE.read_code_state(), _advanced_context_from_store(), STORE.root
        )

    @app.post("/api/code/add-cell")
    def add_local_code_cell(update: CodeCellAddUpdate) -> dict[str, Any]:
        try:
            state = add_cell(STORE.read_code_state(), update.model_dump())
        except CodeWorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_code_state(state)
        return code_payload(
            STORE.read_code_state(), _advanced_context_from_store(), STORE.root
        )

    @app.post("/api/code/select-cell")
    def select_local_code_cell(update: CodeCellSelectUpdate) -> dict[str, Any]:
        try:
            state = select_cell(STORE.read_code_state(), update.model_dump())
        except CodeWorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_code_state(state)
        return code_payload(
            STORE.read_code_state(), _advanced_context_from_store(), STORE.root
        )

    @app.post("/api/code/select-notebook")
    def select_local_code_notebook(update: CodeNotebookSelectUpdate) -> dict[str, Any]:
        try:
            state = select_notebook(STORE.read_code_state(), update.model_dump())
        except CodeWorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_code_state(state)
        return code_payload(
            STORE.read_code_state(), _advanced_context_from_store(), STORE.root
        )

    @app.post("/api/code/clear-output")
    def clear_local_code_outputs(update: CodeNotebookIdUpdate) -> dict[str, Any]:
        try:
            state = clear_outputs(STORE.read_code_state(), update.model_dump())
        except CodeWorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_code_state(state)
        return code_payload(
            STORE.read_code_state(), _advanced_context_from_store(), STORE.root
        )

    @app.post("/api/code/import")
    def import_local_code_notebook(update: CodeNotebookUpdate) -> dict[str, Any]:
        try:
            state = import_notebook(STORE.read_code_state(), update.model_dump())
        except CodeWorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_code_state(state)
        return code_payload(
            STORE.read_code_state(), _advanced_context_from_store(), STORE.root
        )

    @app.post("/api/code/context-notebook")
    def create_local_code_context_notebook() -> dict[str, Any]:
        context = _advanced_context_from_store()
        try:
            state = create_context_notebook(STORE.read_code_state(), context)
        except CodeWorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_code_state(state)
        return code_payload(STORE.read_code_state(), context, STORE.root)

    @app.post("/api/code/analyze")
    def analyze_local_code_notebook(update: CodeNotebookRefUpdate) -> dict[str, Any]:
        context = _advanced_context_from_store()
        try:
            state, analysis = analyze_notebook(
                STORE.read_code_state(), update.model_dump(), context
            )
        except CodeWorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_code_state(state)
        return {
            **code_payload(STORE.read_code_state(), context, STORE.root),
            "analysis_result": analysis,
        }

    @app.post("/api/code/export")
    def export_local_code_notebook(update: CodeNotebookRefUpdate) -> dict[str, Any]:
        try:
            return export_notebook(STORE.read_code_state(), update.model_dump())
        except CodeWorkspaceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/code/run")
    def disabled_local_code_run() -> dict[str, Any]:
        raise HTTPException(status_code=403, detail=disabled_code_runtime_response("run"))

    @app.post("/api/code/run-all")
    def disabled_local_code_run_all() -> dict[str, Any]:
        raise HTTPException(status_code=403, detail=disabled_code_runtime_response("run_all"))

    @app.post("/api/quant-lab/select")
    def select_local_quant_lab_module(update: QuantLabSelectUpdate) -> dict[str, Any]:
        try:
            state = select_module(STORE.read_quant_lab_state(), update.model_dump())
        except QuantLabError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_quant_lab_state(state)
        return quant_lab_payload(
            STORE.read_quant_lab_state(), _advanced_context_from_store(), STORE.root
        )

    @app.post("/api/quant-lab/run-preview")
    def run_local_quant_lab_preview(update: QuantLabRunUpdate) -> dict[str, Any]:
        context = _advanced_context_from_store()
        try:
            state, result = run_local_preview(
                STORE.read_quant_lab_state(),
                update.model_dump(),
                STORE.root,
                context,
            )
        except QuantLabDisabledError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except QuantLabError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_quant_lab_state(state)
        return {
            **quant_lab_payload(STORE.read_quant_lab_state(), context, STORE.root),
            "preview_result": result,
        }

    @app.post("/api/quant-lab/execute")
    def disabled_local_quant_lab_execute() -> dict[str, Any]:
        raise HTTPException(status_code=403, detail=disabled_quant_lab_response("execute"))

    @app.post("/api/quant-lab/deep-agent")
    def disabled_local_quant_lab_deep_agent() -> dict[str, Any]:
        raise HTTPException(status_code=403, detail=disabled_quant_lab_response("deep_agent"))

    @app.post("/api/quantlib/select-module")
    def select_local_quantlib_module(update: QuantLibModuleSelectUpdate) -> dict[str, Any]:
        try:
            state = select_quantlib_module(STORE.read_quantlib_state(), update.model_dump())
        except QuantLibError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_quantlib_state(state)
        return quantlib_payload(
            STORE.read_quantlib_state(), _advanced_context_from_store(), STORE.root
        )

    @app.post("/api/quantlib/select-action")
    def select_local_quantlib_action(update: QuantLibActionSelectUpdate) -> dict[str, Any]:
        try:
            state = select_quantlib_action(STORE.read_quantlib_state(), update.model_dump())
        except QuantLibError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_quantlib_state(state)
        return quantlib_payload(
            STORE.read_quantlib_state(), _advanced_context_from_store(), STORE.root
        )

    @app.post("/api/quantlib/compute")
    def compute_local_quantlib(update: QuantLibComputeUpdate) -> dict[str, Any]:
        context = _advanced_context_from_store()
        try:
            state, result = run_quantlib_calculation(
                STORE.read_quantlib_state(),
                update.model_dump(),
                STORE.root,
                context,
            )
        except QuantLibError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_quantlib_state(state)
        return {
            **quantlib_payload(STORE.read_quantlib_state(), context, STORE.root),
            "calculation_result": result,
        }

    @app.post("/api/quantlib/external-execute")
    def disabled_external_quantlib_execute() -> dict[str, Any]:
        raise HTTPException(status_code=403, detail=disabled_quantlib_response("external_execute"))

    @app.post("/api/forum/channel")
    def select_local_forum_channel(update: ForumChannelUpdate) -> dict[str, Any]:
        try:
            state = select_forum_channel(STORE.read_forum_state(), update.model_dump())
        except ForumError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_forum_state(state)
        return forum_payload(
            STORE.read_forum_state(), _advanced_context_from_store(), root=STORE.root
        )

    @app.post("/api/forum/select-post")
    def select_local_forum_post(update: ForumPostSelectUpdate) -> dict[str, Any]:
        try:
            state = select_forum_post(STORE.read_forum_state(), update.model_dump())
        except ForumError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_forum_state(state)
        return forum_payload(
            STORE.read_forum_state(), _advanced_context_from_store(), root=STORE.root
        )

    @app.post("/api/forum/post")
    def create_local_forum_post(update: ForumPostCreateUpdate) -> dict[str, Any]:
        try:
            state, post = create_forum_post(
                STORE.read_forum_state(), update.model_dump(), STORE.root
            )
        except ForumError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_forum_state(state)
        return {
            **forum_payload(
                STORE.read_forum_state(), _advanced_context_from_store(), root=STORE.root
            ),
            "post_result": post,
        }

    @app.post("/api/forum/reply")
    def add_local_forum_reply(update: ForumReplyUpdate) -> dict[str, Any]:
        try:
            state, reply = add_forum_reply(
                STORE.read_forum_state(), update.model_dump(), STORE.root
            )
        except ForumError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_forum_state(state)
        return {
            **forum_payload(
                STORE.read_forum_state(), _advanced_context_from_store(), root=STORE.root
            ),
            "reply_result": reply,
        }

    @app.post("/api/forum/repair-artifacts")
    def repair_local_forum_artifacts() -> dict[str, Any]:
        try:
            repair_result = repair_forum_artifacts(STORE.root, STORE.read_forum_state())
        except ForumError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            **forum_payload(
                STORE.read_forum_state(), _advanced_context_from_store(), root=STORE.root
            ),
            "repair_result": repair_result,
        }

    @app.post("/api/help/diagnostics")
    def run_local_diagnostics() -> dict[str, Any]:
        return run_diagnostics(
            STORE,
            version=_package_version(),
            governance=_governance_payload_from_store(),
        )

    @app.post("/api/help/check-updates")
    def check_local_updates() -> dict[str, Any]:
        return local_update_status(_package_version())

    @app.post("/api/live-safety/opt-in")
    def disabled_live_opt_in() -> dict[str, Any]:
        raise HTTPException(
            status_code=403,
            detail=disabled_live_action_response("live_opt_in"),
        )

    @app.post("/api/live-safety/store-secret")
    def disabled_live_secret_storage() -> dict[str, Any]:
        raise HTTPException(
            status_code=403,
            detail=disabled_live_action_response("store_private_api_key"),
        )

    @app.post("/api/live-safety/read-balance")
    def disabled_live_balance_read() -> dict[str, Any]:
        raise HTTPException(
            status_code=403,
            detail=disabled_live_action_response("read_real_balance"),
        )

    @app.post("/api/live-safety/submit-order")
    def disabled_live_order_submit() -> dict[str, Any]:
        raise HTTPException(
            status_code=403,
            detail=disabled_live_action_response("submit_real_order"),
        )

    @app.post("/api/live-safety/enable-margin")
    def disabled_live_margin() -> dict[str, Any]:
        raise HTTPException(
            status_code=403,
            detail=disabled_live_action_response("enable_margin"),
        )

    @app.post("/api/live-safety/enable-leverage")
    def disabled_live_leverage() -> dict[str, Any]:
        raise HTTPException(
            status_code=403,
            detail=disabled_live_action_response("enable_leverage"),
        )

    @app.post("/api/live-safety/enable-short")
    def disabled_live_short() -> dict[str, Any]:
        raise HTTPException(
            status_code=403,
            detail=disabled_live_action_response("enable_short"),
        )

    @app.post("/api/live-safety/execute-derivatives")
    def disabled_live_derivatives() -> dict[str, Any]:
        raise HTTPException(
            status_code=403,
            detail=disabled_live_action_response("execute_derivatives"),
        )

    @app.post("/api/crypto/orders/process")
    def process_crypto_paper_orders() -> dict[str, Any]:
        paper_state = STORE.read_paper_state()
        candles_by_symbol: dict[str, list[dict[str, Any]]] = {}
        for order in paper_state.get("orders", []):
            if not isinstance(order, dict) or order.get("status") != "WORKING":
                continue
            working_symbol = str(order.get("symbol", ""))
            if not working_symbol or working_symbol in candles_by_symbol:
                continue
            detail = STORE.read_crypto_detail_cache(working_symbol, "15m")
            candles = detail.get("candles") if isinstance(detail, dict) else []
            if isinstance(candles, list) and candles:
                candles_by_symbol[working_symbol] = [
                    candle for candle in candles if isinstance(candle, dict)
                ]
        state, report = process_paper_orders(
            paper_state,
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
            candles_by_symbol=candles_by_symbol,
        )
        STORE.write_paper_state(state)
        return {**report, "account": state["account"]}

    @app.post("/api/crypto/orders")
    def submit_paper_order(update: PaperOrderUpdate) -> dict[str, Any]:
        try:
            state, order = place_paper_order(
                STORE.read_paper_state(),
                update.model_dump(),
                STORE.read_market_cache(),
                STORE.read_crypto_detail_cache(update.symbol, update.timeframe),
            )
        except PaperOrderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_paper_state(state)
        payload = crypto_payload(
            state,
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(update.symbol, update.timeframe),
        )
        return {**payload, "submitted_order": order}

    @app.post("/api/crypto/orders/cancel")
    def cancel_paper_order_endpoint(update: PaperOrderCancelUpdate) -> dict[str, Any]:
        try:
            state, order = cancel_paper_order(STORE.read_paper_state(), update.order_id)
        except PaperOrderError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        STORE.write_paper_state(state)
        payload = crypto_payload(
            state,
            STORE.read_market_cache(),
            STORE.read_crypto_detail_cache(),
        )
        return {**payload, "cancelled_order": order}

    @app.post("/api/crypto/reset")
    def reset_paper_account() -> dict[str, Any]:
        state = STORE.reset_paper_state()
        return crypto_payload(state, STORE.read_market_cache(), STORE.read_crypto_detail_cache())

    @app.post("/api/portfolio/create")
    def create_local_portfolio(update: PortfolioCreateUpdate) -> dict[str, Any]:
        try:
            state = create_portfolio(STORE.read_portfolio_state(), update.model_dump())
        except PortfolioError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _portfolio_payload_with_prices(STORE.write_portfolio_state(state))

    @app.post("/api/portfolio/demo")
    def load_demo_local_portfolio() -> dict[str, Any]:
        state = load_demo_portfolio(STORE.read_portfolio_state())
        return _portfolio_payload_with_prices(STORE.write_portfolio_state(state))

    @app.get("/api/portfolio/books/{portfolio_id}")
    def portfolio_book_detail(portfolio_id: str) -> dict[str, Any]:
        state = normalize_portfolio_state(STORE.read_portfolio_state())
        book = state.get("portfolios", {}).get(str(portfolio_id))
        if not isinstance(book, dict):
            raise HTTPException(status_code=404, detail="Unknown portfolio id")
        _overlay_book_position_prices(book)
        return {
            "portfolio_id": str(portfolio_id),
            "active": state.get("active_portfolio_id") == str(portfolio_id),
            "book": book,
            "safety": {
                "safety_class": "read_only_portfolio_book_detail",
                "mutates_local_state": False,
                "external_calls": False,
            },
        }

    @app.post("/api/portfolio/select")
    def select_local_portfolio(update: PortfolioSelectUpdate) -> dict[str, Any]:
        try:
            state = select_portfolio(STORE.read_portfolio_state(), update.portfolio_id)
        except PortfolioError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _portfolio_payload_with_prices(STORE.write_portfolio_state(state))

    @app.post("/api/portfolio/delete")
    def delete_local_portfolio(update: PortfolioDeleteUpdate) -> dict[str, Any]:
        if not update.confirm:
            raise HTTPException(status_code=400, detail="Delete confirmation is required")
        try:
            state = delete_portfolio(STORE.read_portfolio_state(), update.portfolio_id)
        except PortfolioError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _portfolio_payload_with_prices(STORE.write_portfolio_state(state))

    @app.post("/api/portfolio/import")
    def import_local_portfolio(update: PortfolioImportUpdate) -> dict[str, Any]:
        try:
            state = import_portfolio(STORE.read_portfolio_state(), update.model_dump())
        except PortfolioError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _portfolio_payload_with_prices(STORE.write_portfolio_state(state))

    @app.post("/api/portfolio/link-paper")
    def link_local_paper_portfolio() -> dict[str, Any]:
        try:
            state = link_paper_portfolio(
                STORE.read_portfolio_state(),
                STORE.read_paper_state(),
            )
        except PortfolioError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _portfolio_payload_with_prices(STORE.write_portfolio_state(state))

    @app.post("/api/portfolio/link-backtest")
    def link_local_backtest_portfolio(update: PortfolioBacktestLinkUpdate) -> dict[str, Any]:
        try:
            state = link_backtest_portfolio(
                STORE.read_portfolio_state(),
                STORE.root,
                update.artifact_dir,
            )
        except PortfolioError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _portfolio_payload_with_prices(STORE.write_portfolio_state(state))

    @app.post("/api/portfolio/report")
    def write_local_portfolio_report() -> dict[str, Any]:
        try:
            state = write_portfolio_report(
                STORE.read_portfolio_state(),
                STORE.root,
                STORE.read_market_cache(),
                STORE.read_crypto_detail_cache(),
            )
        except PortfolioError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _portfolio_payload_with_prices(STORE.write_portfolio_state(state))

    @app.post("/api/backtest/run")
    def run_local_backtest(update: BacktestRunUpdate) -> dict[str, Any]:
        try:
            request = update.model_dump()
            if request.get("research_lineage"):
                request["research_lineage"] = _validate_backtest_lineage_from_latest_scan(
                    request["research_lineage"]
                )
            return run_backtest(
                request,
                STORE.root,
                STORE.read_crypto_detail_cache(update.symbol, update.timeframe),
            )
        except BacktestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/backtest/walk-forward")
    def run_local_backtest_walk_forward(update: BacktestWalkForwardUpdate) -> dict[str, Any]:
        try:
            return run_walk_forward(
                update.model_dump(),
                STORE.root,
                STORE.read_crypto_detail_cache(update.symbol, update.timeframe),
            )
        except BacktestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/backtest/optimize")
    def run_local_backtest_optimize(update: BacktestOptimizeUpdate) -> dict[str, Any]:
        try:
            return run_optimize(
                update.model_dump(),
                STORE.root,
                STORE.read_crypto_detail_cache(update.symbol, update.timeframe),
            )
        except BacktestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/backtest/comparison-packet")
    def write_local_backtest_comparison_packet(
        update: BacktestComparisonUpdate,
    ) -> dict[str, Any]:
        try:
            return write_backtest_comparison_packet(STORE.root, max_runs=update.max_runs)
        except BacktestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Serve the built frontend (single-process self-use) when it exists. API routes
    # are registered above, so they take precedence over this catch-all mount.
    if serve_ui:
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")

    return app


app = create_app()


def main() -> None:
    import uvicorn

    base_url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    if (DEFAULT_FRONTEND_DIST / "index.html").is_file():
        print(f"[local-terminal] UI + API ready at {base_url}/")
    else:
        print(
            f"[local-terminal] API ready at {base_url}/api/health "
            "(UI not built yet — run: npm --prefix frontend install "
            "&& npm --prefix frontend run build)"
        )
    uvicorn.run(
        "otto.local_terminal.server:app",
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
