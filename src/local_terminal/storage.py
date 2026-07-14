"""Repo-local persistence for shell settings, profile, and layouts."""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.local_terminal.algo import (
    default_algo_state,
    normalize_algo_state,
    scan_artifact_manifest,
    scan_report_text,
)
from src.local_terminal.dashboard import (
    default_dashboard_layout,
    normalize_dashboard_layout,
)
from src.local_terminal.chat import default_chat_state, normalize_chat_state
from src.local_terminal.code_workspace import (
    code_analysis_manifest,
    code_analysis_report_text,
    default_code_state,
    normalize_code_state,
    notebook_to_ipynb,
)
from src.local_terminal.crypto import default_paper_state, normalize_paper_state
from src.local_terminal.news_digest import default_news_digest_state, normalize_news_digest_state
from src.local_terminal.watchlist import default_watchlist_state, normalize_watchlist_state
from src.local_terminal.forum import default_forum_state, normalize_forum_state
from src.local_terminal.markets import default_markets_layout, normalize_markets_layout
from src.local_terminal.news import default_news_layout, normalize_news_layout
from src.local_terminal.nodes import (
    default_nodes_state,
    dry_run_artifact_manifest,
    dry_run_report_text,
    normalize_nodes_state,
)
from src.local_terminal.portfolio import (
    default_portfolio_state,
    normalize_portfolio_state,
)
from src.local_terminal.quant_lab import default_quant_lab_state, normalize_quant_lab_state
from src.local_terminal.quantlib import default_quantlib_state, normalize_quantlib_state
from src.local_terminal.research_data import (
    SEC_DEFAULT_COMPANY_WATCHLIST,
    safe_sec_cik,
    sec_xbrl_frame_cache_path,
)


ROOT = Path(__file__).resolve().parents[2]


def default_state_root(module_root: Path = ROOT) -> Path:
    """Where user state lives by default.

    In a repo checkout (``pyproject.toml`` beside ``src/``) state stays inside
    the repository, as always. Installed as a wheel (pip/uvx) there is no
    repository, so state moves to ``~/.otto`` — never into site-packages.
    """
    if (module_root / "pyproject.toml").is_file():
        return module_root
    return Path.home() / ".otto"


DEFAULT_STATE_ROOT = default_state_root()

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "system",
    "default_route": "dashboard",
    "compact_mode": False,
    "data_refresh_seconds": 60,
}

DEFAULT_PROFILE: dict[str, Any] = {
    "profile_id": "local-default",
    "display_name": "Local User",
    "theme": "system",
    "default_route": "dashboard",
    "cloud_account_required": False,
    "billing_enabled": False,
    "subscription_required": False,
    "cr_required": False,
    "credits_enabled": False,
    "private_api_required": False,
}

DEFAULT_LAYOUT: dict[str, Any] = {
    "layout_id": "default",
    "active_route": "dashboard",
    "sidebar_collapsed": False,
    "focus_mode": False,
    "panel_order": ["primary"],
}


@dataclass(frozen=True)
class LocalStateStore:
    root: Path = DEFAULT_STATE_ROOT

    @property
    def settings_path(self) -> Path:
        return self.root / "settings" / "local_settings.json"

    @property
    def profile_path(self) -> Path:
        return self.root / "settings" / "local_profile.json"

    @property
    def layout_path(self) -> Path:
        return self.root / "workspace_layouts" / "default.json"

    @property
    def dashboard_path(self) -> Path:
        return self.root / "workspace_layouts" / "dashboard.json"

    @property
    def markets_path(self) -> Path:
        return self.root / "workspace_layouts" / "markets.json"

    @property
    def news_path(self) -> Path:
        return self.root / "workspace_layouts" / "news.json"

    @property
    def market_cache_path(self) -> Path:
        return self.root / "market_data" / "crypto_latest.json"

    def crypto_detail_cache_path(self, symbol: str = "BTCUSDT", timeframe: str = "15m") -> Path:
        safe_symbol = "".join(ch for ch in symbol.upper() if ch.isalnum())[:20] or "BTCUSDT"
        safe_timeframe = "".join(ch for ch in timeframe if ch.isalnum())[:8] or "15m"
        return self.root / "market_data" / "crypto" / safe_symbol / f"{safe_timeframe}.json"

    @property
    def paper_state_path(self) -> Path:
        return self.root / "artifacts" / "paper" / "paper_state.json"

    @property
    def portfolio_state_path(self) -> Path:
        return self.root / "artifacts" / "portfolio" / "portfolio_state.json"

    @property
    def news_cache_path(self) -> Path:
        return self.root / "artifacts" / "news" / "news_cache.json"

    def sec_fundamentals_cache_path(self, cik: str = "0000320193") -> Path:
        safe_cik = safe_sec_cik(cik)
        return self.root / "market_data" / "fundamentals" / "sec" / safe_cik / "companyfacts.json"

    @property
    def sec_company_tickers_cache_path(self) -> Path:
        return self.root / "market_data" / "fundamentals" / "sec" / "company_tickers.json"

    def sec_company_submissions_cache_path(self, cik: str = "0000320193") -> Path:
        safe_cik = safe_sec_cik(cik)
        return self.root / "market_data" / "fundamentals" / "sec" / safe_cik / "submissions.json"

    def sec_xbrl_frame_cache_path(self) -> Path:
        return self.root / sec_xbrl_frame_cache_path()

    def dbnomics_macro_cache_path(
        self,
        provider: str = "INSEE",
        dataset: str = "IPC-2015",
        series: str = "A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE",
    ) -> Path:
        safe_provider = _safe_path_part(provider, "provider")
        safe_dataset = _safe_path_part(dataset, "dataset")
        safe_series = _safe_path_part(series, "series")
        return (
            self.root
            / "market_data"
            / "macro"
            / "dbnomics"
            / safe_provider
            / safe_dataset
            / f"{safe_series}.json"
        )

    def fred_macro_cache_path(self, series: str = "DGS10") -> Path:
        safe_series = _safe_path_part(series.upper(), "DGS10")
        return self.root / "market_data" / "macro" / "fred" / f"{safe_series}.json"

    @property
    def bls_macro_cache_path(self) -> Path:
        return self.root / "market_data" / "macro" / "bls" / "latest_series.json"

    @property
    def eurostat_hicp_cache_path(self) -> Path:
        return self.root / "market_data" / "macro" / "eurostat" / "hicp_ea20_cp00_i15.json"

    @property
    def nasdaq_trader_symbol_directory_cache_path(self) -> Path:
        return (
            self.root
            / "market_data"
            / "reference"
            / "nasdaq_trader"
            / "symbol_directory.json"
        )

    @property
    def bea_regional_cache_path(self) -> Path:
        return (
            self.root
            / "market_data"
            / "regional"
            / "bea"
            / "SAGDP9N_LINE1_STATE.json"
        )

    @property
    def census_acs_profile_cache_path(self) -> Path:
        return (
            self.root
            / "market_data"
            / "regional"
            / "census"
            / "acs5_profile_state_2023.json"
        )

    def alpha_vantage_equity_quote_cache_path(self, symbol: str = "AAPL") -> Path:
        safe_symbol = _safe_path_part(symbol.upper(), "AAPL")
        return (
            self.root
            / "market_data"
            / "equities"
            / "alphavantage"
            / "global_quote"
            / f"{safe_symbol}.json"
        )

    def alpha_vantage_fx_quote_cache_path(self, pair: str = "EUR/USD") -> Path:
        safe_pair = _safe_path_part(pair.upper().replace("/", ""), "EURUSD")
        return (
            self.root
            / "market_data"
            / "fx"
            / "alphavantage"
            / "currency_exchange"
            / f"{safe_pair}.json"
        )

    def twelve_data_quote_cache_path(self, symbol: str = "AAPL") -> Path:
        safe_symbol = _safe_path_part(symbol.upper().replace("/", ""), "AAPL")
        return self.root / "market_data" / "quotes" / "twelve_data" / f"{safe_symbol}.json"

    def finnhub_quote_cache_path(self, symbol: str = "AAPL") -> Path:
        safe_symbol = _safe_path_part(symbol.upper(), "AAPL")
        return self.root / "market_data" / "quotes" / "finnhub" / f"{safe_symbol}.json"

    def fmp_quote_cache_path(self, symbol: str = "AAPL") -> Path:
        safe_symbol = _safe_path_part(symbol.upper(), "AAPL")
        return self.root / "market_data" / "quotes" / "fmp" / f"{safe_symbol}.json"

    def stooq_quote_cache_path(self, symbol: str = "AAPL.US") -> Path:
        safe_symbol = _safe_path_part(
            "".join(ch for ch in symbol.upper().replace("/", "") if ch.isalnum()),
            "AAPLUS",
        )
        return self.root / "market_data" / "quotes" / "stooq" / f"{safe_symbol}.json"

    def yahoo_quote_cache_path(self, symbol: str = "AAPL") -> Path:
        safe_symbol = _safe_path_part(
            "".join(ch for ch in symbol.upper().replace("/", "") if ch.isalnum()),
            "AAPL",
        )
        return self.root / "market_data" / "quotes" / "yahoo" / f"{safe_symbol}.json"

    def moex_quote_cache_path(self, symbol: str = "SBER") -> Path:
        safe_symbol = _safe_path_part(
            "".join(ch for ch in symbol.upper().replace("/", "") if ch.isalnum()),
            "SBER",
        )
        return self.root / "market_data" / "quotes" / "moex" / f"{safe_symbol}.json"

    def twse_quote_cache_path(self, symbol: str = "2330") -> Path:
        safe_symbol = _safe_path_part(
            "".join(ch for ch in symbol.upper().replace("/", "") if ch.isalnum()),
            "2330",
        )
        return self.root / "market_data" / "quotes" / "twse" / f"{safe_symbol}.json"

    @property
    def openfigi_mapping_cache_path(self) -> Path:
        return self.root / "market_data" / "reference" / "openfigi" / "mapping.json"

    @property
    def treasury_rates_cache_path(self) -> Path:
        return self.root / "market_data" / "rates" / "treasury" / "daily_yield_curve.json"

    @property
    def nyfed_sofr_cache_path(self) -> Path:
        return self.root / "market_data" / "rates" / "nyfed" / "sofr.json"

    @property
    def ecb_fx_cache_path(self) -> Path:
        return self.root / "market_data" / "fx" / "ecb" / "eurofxref_daily.json"

    @property
    def federal_reserve_h10_fx_cache_path(self) -> Path:
        return (
            self.root
            / "market_data"
            / "fx"
            / "federal_reserve"
            / "h10_reference_rates.json"
        )

    @property
    def bank_of_canada_fx_cache_path(self) -> Path:
        return (
            self.root
            / "market_data"
            / "fx"
            / "bank_of_canada"
            / "valet_fx_reference_rates.json"
        )

    @property
    def world_bank_commodity_cache_path(self) -> Path:
        return self.root / "market_data" / "commodities" / "world_bank" / "pink_sheet_monthly.json"

    @property
    def cftc_cot_cache_path(self) -> Path:
        return self.root / "market_data" / "commodities" / "cftc" / "cot_legacy_futures.json"

    @property
    def eia_energy_cache_path(self) -> Path:
        return self.root / "market_data" / "commodities" / "eia" / "energy_series.json"

    @property
    def sec_fund_tickers_cache_path(self) -> Path:
        return self.root / "market_data" / "funds" / "sec" / "company_tickers_mf.json"

    @property
    def chat_state_path(self) -> Path:
        return self.root / "artifacts" / "chat" / "chat_state.json"

    @property
    def algo_state_path(self) -> Path:
        return self.root / "artifacts" / "algo" / "algo_state.json"

    @property
    def nodes_state_path(self) -> Path:
        return self.root / "artifacts" / "workflows" / "nodes_state.json"

    @property
    def code_state_path(self) -> Path:
        return self.root / "artifacts" / "code_workspace" / "code_state.json"

    @property
    def quant_lab_state_path(self) -> Path:
        return self.root / "artifacts" / "quant_lab" / "quant_lab_state.json"

    @property
    def quantlib_state_path(self) -> Path:
        return self.root / "artifacts" / "quantlib" / "quantlib_state.json"

    @property
    def forum_state_path(self) -> Path:
        return self.root / "artifacts" / "forum" / "forum_state.json"

    @property
    def watchlist_state_path(self) -> Path:
        return self.root / "artifacts" / "markets" / "watchlist_state.json"

    @property
    def news_digest_state_path(self) -> Path:
        return self.root / "artifacts" / "news" / "news_digest_state.json"

    @property
    def diagnostics_root_path(self) -> Path:
        return self.root / "artifacts" / "diagnostics"

    def read_settings(self) -> dict[str, Any]:
        return _read_json(self.settings_path, DEFAULT_SETTINGS)

    def write_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        settings = {**DEFAULT_SETTINGS, **payload}
        return _write_json(
            self.settings_path, settings, self.root, keep_backups=STATE_BACKUP_COUNT
        )

    def read_profile(self) -> dict[str, Any]:
        return _sanitize_profile(_read_json(self.profile_path, DEFAULT_PROFILE))

    def write_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(
            self.profile_path,
            _sanitize_profile({**DEFAULT_PROFILE, **payload}),
            self.root,
            keep_backups=STATE_BACKUP_COUNT,
        )

    def read_layout(self) -> dict[str, Any]:
        return _read_json(self.layout_path, DEFAULT_LAYOUT)

    def write_layout(self, payload: dict[str, Any]) -> dict[str, Any]:
        layout = {**DEFAULT_LAYOUT, **payload, "layout_id": "default"}
        return _write_json(self.layout_path, layout, self.root, keep_backups=STATE_BACKUP_COUNT)

    def read_dashboard_layout(self) -> dict[str, Any]:
        return _read_json(self.dashboard_path, default_dashboard_layout())

    def write_dashboard_layout(self, payload: dict[str, Any]) -> dict[str, Any]:
        layout = normalize_dashboard_layout({**default_dashboard_layout(), **payload})
        return _write_json(
            self.dashboard_path, layout, self.root, keep_backups=STATE_BACKUP_COUNT
        )

    def read_markets_layout(self) -> dict[str, Any]:
        return normalize_markets_layout(
            {**default_markets_layout(), **_read_json(self.markets_path, default_markets_layout())}
        )

    def write_markets_layout(self, payload: dict[str, Any]) -> dict[str, Any]:
        layout = normalize_markets_layout({**default_markets_layout(), **payload})
        return _write_json(self.markets_path, layout, self.root, keep_backups=STATE_BACKUP_COUNT)

    def read_news_layout(self) -> dict[str, Any]:
        return _read_json(self.news_path, default_news_layout())

    def write_news_layout(self, payload: dict[str, Any]) -> dict[str, Any]:
        layout = normalize_news_layout({**default_news_layout(), **payload})
        return _write_json(self.news_path, layout, self.root, keep_backups=STATE_BACKUP_COUNT)

    def read_market_cache(self) -> dict[str, Any]:
        return _read_json(self.market_cache_path, {})

    def write_market_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        # Merge rows by symbol instead of replacing the file: a partial
        # provider failure (one symbol fetched, others rate-limited) must not
        # silently drop the surviving rows — the M27-R2 watchlist wall renders
        # missing symbols as "pending", which made this shrinkage visible.
        merged = dict(payload) if isinstance(payload, dict) else {}
        incoming_rows = merged.get("rows")
        if isinstance(incoming_rows, list):
            existing = _read_json(self.market_cache_path, {})
            existing_rows = existing.get("rows") if isinstance(existing, dict) else None
            if isinstance(existing_rows, list):
                by_symbol = {
                    str(row.get("symbol")): row
                    for row in existing_rows
                    if isinstance(row, dict) and row.get("symbol")
                }
                for row in incoming_rows:
                    if isinstance(row, dict) and row.get("symbol"):
                        by_symbol[str(row.get("symbol"))] = row
                merged["rows"] = list(by_symbol.values())
        return _write_json(self.market_cache_path, merged, self.root)

    def history_cache_path(self, symbol: str) -> Path:
        safe = "".join(ch for ch in str(symbol).upper() if ch.isalnum())[:16] or "UNKNOWN"
        return self.root / "market_data" / "history" / f"{safe}.json"

    def read_history_cache(self, symbol: str) -> dict[str, Any]:
        return _read_json(self.history_cache_path(symbol), {})

    def write_history_cache(self, symbol: str, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.history_cache_path(symbol), payload, self.root)

    def read_crypto_detail_cache(
        self, symbol: str = "BTCUSDT", timeframe: str = "15m"
    ) -> dict[str, Any]:
        return _read_json(self.crypto_detail_cache_path(symbol, timeframe), {})

    def write_crypto_detail_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") if isinstance(payload, dict) else {}
        status = status if isinstance(status, dict) else {}
        symbol = str(status.get("symbol") or "BTCUSDT")
        timeframe = str(status.get("timeframe") or "15m")
        return _write_json(self.crypto_detail_cache_path(symbol, timeframe), payload, self.root)

    def read_news_cache(self) -> dict[str, Any]:
        return _read_json(self.news_cache_path, {})

    def write_news_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.news_cache_path, payload, self.root)

    def read_sec_fundamentals_cache(self) -> dict[str, Any]:
        return _read_json(self.sec_fundamentals_cache_path(), {})

    def write_sec_fundamentals_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.sec_fundamentals_cache_path(), payload, self.root)

    def read_sec_company_tickers_cache(self) -> dict[str, Any]:
        return _read_json(self.sec_company_tickers_cache_path, {})

    def write_sec_company_tickers_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.sec_company_tickers_cache_path, payload, self.root)

    def read_sec_company_submissions_cache(self, cik: str = "0000320193") -> dict[str, Any]:
        return _read_json(self.sec_company_submissions_cache_path(cik), {})

    def read_sec_company_submissions_watchlist_cache(self) -> dict[str, Any]:
        return {
            "by_symbol": {
                company["symbol"]: self.read_sec_company_submissions_cache(company["cik"])
                for company in SEC_DEFAULT_COMPANY_WATCHLIST
            }
        }

    def write_sec_company_submissions_cache(
        self,
        payload: dict[str, Any],
        cik: str | None = None,
    ) -> dict[str, Any]:
        resolved_cik = cik or _sec_submission_payload_cik(payload)
        return _write_json(self.sec_company_submissions_cache_path(resolved_cik), payload, self.root)

    def write_sec_company_submissions_watchlist_cache(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        written: dict[str, Any] = {}
        rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
        if not rows:
            return written
        by_cik: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            cik = safe_sec_cik(row.get("cik"))
            if cik == "0000000000":
                continue
            by_cik.setdefault(cik, []).append(row)
        for cik, cik_rows in by_cik.items():
            cache_path = _relative(self.sec_company_submissions_cache_path(cik), self.root)
            latest = cik_rows[0]
            symbol = str(latest.get("symbol") or "")
            normalized = {
                "status": {
                    **dict(payload.get("status") or {}),
                    "cache_path": cache_path,
                },
                "rows": cik_rows,
                "summary": {
                    "row_count": len(cik_rows),
                    "latest_filing_date": str(latest.get("filing_date") or ""),
                    "latest_form": str(latest.get("form") or ""),
                    "symbol": symbol,
                    "cik": cik,
                    "company_count": 1,
                    "symbol_count": 1 if symbol else 0,
                    "symbols": symbol,
                    "filing_symbols": symbol,
                    "latest_symbol": symbol,
                    "cache_paths": cache_path,
                    "source_error_count": 0,
                    "source": "sec_company_submissions",
                },
            }
            written[cik] = self.write_sec_company_submissions_cache(normalized, cik)
        return written

    def read_sec_xbrl_frame_cache(self) -> dict[str, Any]:
        return _read_json(self.sec_xbrl_frame_cache_path(), {})

    def write_sec_xbrl_frame_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.sec_xbrl_frame_cache_path(), payload, self.root)

    def read_dbnomics_macro_cache(self) -> dict[str, Any]:
        return _read_json(self.dbnomics_macro_cache_path(), {})

    def write_dbnomics_macro_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.dbnomics_macro_cache_path(), payload, self.root)

    def read_fred_macro_cache(self, series: str = "DGS10") -> dict[str, Any]:
        return _read_json(self.fred_macro_cache_path(series), {})

    def write_fred_macro_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else {}
        if isinstance(status, dict) and status.get("series_id"):
            series_id = str(status.get("series_id"))
        elif isinstance(summary, dict) and summary.get("series_id"):
            series_id = str(summary.get("series_id"))
        else:
            series_id = "DGS10"
        return _write_json(self.fred_macro_cache_path(series_id), payload, self.root)

    def read_bls_macro_cache(self) -> dict[str, Any]:
        return _read_json(self.bls_macro_cache_path, {})

    def write_bls_macro_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.bls_macro_cache_path, payload, self.root)

    def read_eurostat_hicp_cache(self) -> dict[str, Any]:
        return _read_json(self.eurostat_hicp_cache_path, {})

    def write_eurostat_hicp_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.eurostat_hicp_cache_path, payload, self.root)

    def read_nasdaq_trader_symbol_directory_cache(self) -> dict[str, Any]:
        return _read_json(self.nasdaq_trader_symbol_directory_cache_path, {})

    def write_nasdaq_trader_symbol_directory_cache(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return _write_json(
            self.nasdaq_trader_symbol_directory_cache_path,
            payload,
            self.root,
        )

    def read_openfigi_mapping_cache(self) -> dict[str, Any]:
        return _read_json(self.openfigi_mapping_cache_path, {})

    def write_openfigi_mapping_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.openfigi_mapping_cache_path, payload, self.root)

    def read_bea_regional_cache(self) -> dict[str, Any]:
        return _read_json(self.bea_regional_cache_path, {})

    def write_bea_regional_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.bea_regional_cache_path, payload, self.root)

    def read_census_acs_profile_cache(self) -> dict[str, Any]:
        return _read_json(self.census_acs_profile_cache_path, {})

    def write_census_acs_profile_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.census_acs_profile_cache_path, payload, self.root)

    def read_alpha_vantage_equity_quote_cache(self, symbol: str = "AAPL") -> dict[str, Any]:
        return _read_json(self.alpha_vantage_equity_quote_cache_path(symbol), {})

    def write_alpha_vantage_equity_quote_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else {}
        if isinstance(status, dict) and status.get("symbol"):
            symbol = str(status.get("symbol"))
        elif isinstance(summary, dict) and summary.get("symbol"):
            symbol = str(summary.get("symbol"))
        else:
            symbol = "AAPL"
        return _write_json(self.alpha_vantage_equity_quote_cache_path(symbol), payload, self.root)

    def read_alpha_vantage_fx_quote_cache(self, pair: str = "EUR/USD") -> dict[str, Any]:
        return _read_json(self.alpha_vantage_fx_quote_cache_path(pair), {})

    def write_alpha_vantage_fx_quote_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else {}
        if isinstance(status, dict) and status.get("pair"):
            pair = str(status.get("pair"))
        elif isinstance(summary, dict) and summary.get("pair"):
            pair = str(summary.get("pair"))
        else:
            pair = "EUR/USD"
        return _write_json(self.alpha_vantage_fx_quote_cache_path(pair), payload, self.root)

    def read_twelve_data_quote_cache(self, symbol: str = "AAPL") -> dict[str, Any]:
        return _read_json(self.twelve_data_quote_cache_path(symbol), {})

    def write_twelve_data_quote_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else {}
        if isinstance(status, dict) and status.get("symbol"):
            symbol = str(status.get("symbol"))
        elif isinstance(summary, dict) and summary.get("symbol"):
            symbol = str(summary.get("symbol"))
        else:
            symbol = "AAPL"
        return _write_json(self.twelve_data_quote_cache_path(symbol), payload, self.root)

    def read_finnhub_quote_cache(self, symbol: str = "AAPL") -> dict[str, Any]:
        return _read_json(self.finnhub_quote_cache_path(symbol), {})

    def write_finnhub_quote_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else {}
        if isinstance(status, dict) and status.get("symbol"):
            symbol = str(status.get("symbol"))
        elif isinstance(summary, dict) and summary.get("symbol"):
            symbol = str(summary.get("symbol"))
        else:
            symbol = "AAPL"
        return _write_json(self.finnhub_quote_cache_path(symbol), payload, self.root)

    def read_fmp_quote_cache(self, symbol: str = "AAPL") -> dict[str, Any]:
        return _read_json(self.fmp_quote_cache_path(symbol), {})

    def write_fmp_quote_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else {}
        if isinstance(status, dict) and status.get("symbol"):
            symbol = str(status.get("symbol"))
        elif isinstance(summary, dict) and summary.get("symbol"):
            symbol = str(summary.get("symbol"))
        else:
            symbol = "AAPL"
        return _write_json(self.fmp_quote_cache_path(symbol), payload, self.root)

    def read_stooq_quote_cache(self, symbol: str = "AAPL.US") -> dict[str, Any]:
        return _read_json(self.stooq_quote_cache_path(symbol), {})

    def write_stooq_quote_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else {}
        if isinstance(status, dict) and status.get("symbol"):
            symbol = str(status.get("symbol"))
        elif isinstance(summary, dict) and summary.get("symbol"):
            symbol = str(summary.get("symbol"))
        else:
            symbol = "AAPL.US"
        return _write_json(self.stooq_quote_cache_path(symbol), payload, self.root)

    def read_yahoo_quote_cache(self, symbol: str = "AAPL") -> dict[str, Any]:
        return _read_json(self.yahoo_quote_cache_path(symbol), {})

    def write_yahoo_quote_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else {}
        if isinstance(status, dict) and status.get("symbol"):
            symbol = str(status.get("symbol"))
        elif isinstance(summary, dict) and summary.get("symbol"):
            symbol = str(summary.get("symbol"))
        else:
            symbol = "AAPL"
        return _write_json(self.yahoo_quote_cache_path(symbol), payload, self.root)

    def read_moex_quote_cache(self, symbol: str = "SBER") -> dict[str, Any]:
        return _read_json(self.moex_quote_cache_path(symbol), {})

    def write_moex_quote_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else {}
        if isinstance(status, dict) and status.get("symbol"):
            symbol = str(status.get("symbol"))
        elif isinstance(summary, dict) and summary.get("symbol"):
            symbol = str(summary.get("symbol"))
        else:
            symbol = "SBER"
        return _write_json(self.moex_quote_cache_path(symbol), payload, self.root)

    def read_twse_quote_cache(self, symbol: str = "2330") -> dict[str, Any]:
        return _read_json(self.twse_quote_cache_path(symbol), {})

    def write_twse_quote_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        status = payload.get("status") if isinstance(payload, dict) else {}
        summary = payload.get("summary") if isinstance(payload, dict) else {}
        if isinstance(status, dict) and status.get("symbol"):
            symbol = str(status.get("symbol"))
        elif isinstance(summary, dict) and summary.get("symbol"):
            symbol = str(summary.get("symbol"))
        else:
            symbol = "2330"
        return _write_json(self.twse_quote_cache_path(symbol), payload, self.root)

    def read_treasury_rates_cache(self) -> dict[str, Any]:
        return _read_json(self.treasury_rates_cache_path, {})

    def write_treasury_rates_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.treasury_rates_cache_path, payload, self.root)

    def read_nyfed_sofr_cache(self) -> dict[str, Any]:
        return _read_json(self.nyfed_sofr_cache_path, {})

    def write_nyfed_sofr_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.nyfed_sofr_cache_path, payload, self.root)

    def read_ecb_fx_cache(self) -> dict[str, Any]:
        return _read_json(self.ecb_fx_cache_path, {})

    def write_ecb_fx_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.ecb_fx_cache_path, payload, self.root)

    def read_federal_reserve_h10_fx_cache(self) -> dict[str, Any]:
        return _read_json(self.federal_reserve_h10_fx_cache_path, {})

    def write_federal_reserve_h10_fx_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.federal_reserve_h10_fx_cache_path, payload, self.root)

    def read_bank_of_canada_fx_cache(self) -> dict[str, Any]:
        return _read_json(self.bank_of_canada_fx_cache_path, {})

    def write_bank_of_canada_fx_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.bank_of_canada_fx_cache_path, payload, self.root)

    def read_world_bank_commodity_cache(self) -> dict[str, Any]:
        return _read_json(self.world_bank_commodity_cache_path, {})

    def write_world_bank_commodity_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.world_bank_commodity_cache_path, payload, self.root)

    def read_cftc_cot_cache(self) -> dict[str, Any]:
        return _read_json(self.cftc_cot_cache_path, {})

    def write_cftc_cot_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.cftc_cot_cache_path, payload, self.root)

    def read_eia_energy_cache(self) -> dict[str, Any]:
        return _read_json(self.eia_energy_cache_path, {})

    def write_eia_energy_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.eia_energy_cache_path, payload, self.root)

    def read_sec_fund_tickers_cache(self) -> dict[str, Any]:
        return _read_json(self.sec_fund_tickers_cache_path, {})

    def write_sec_fund_tickers_cache(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(self.sec_fund_tickers_cache_path, payload, self.root)

    def read_chat_state(self) -> dict[str, Any]:
        return _read_chat_state_json(self.chat_state_path)

    def write_chat_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(
            self.chat_state_path,
            normalize_chat_state(payload),
            self.root,
            keep_backups=STATE_BACKUP_COUNT,
        )

    def read_algo_state(self) -> dict[str, Any]:
        return _read_algo_state_json(self.algo_state_path)

    def write_algo_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = _write_json(
            self.algo_state_path,
            normalize_algo_state(payload),
            self.root,
            keep_backups=STATE_BACKUP_COUNT,
        )
        self.write_algo_scan_artifacts(state)
        return state

    def algo_scan_artifact_health(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        state = normalize_algo_state(payload if payload is not None else self.read_algo_state(), strict=False)
        invalid_scan = state.get("invalid_strategies", {}).get("last_scan")
        if invalid_scan:
            return {
                "status": "invalid_scan_state",
                "mode": "latest_scan_artifact_mirror",
                "scan_id": "",
                "artifact_dir": "",
                "expected_count": 3,
                "present_count": 0,
                "missing_count": 3,
                "files": [],
                "repair_available": False,
                "repair_action": "algo_scan_artifacts_repair",
                "state_is_source": False,
                "destructive_actions_enabled": False,
                "validation_error": str(invalid_scan),
            }
        last_scan = state.get("last_scan")
        if not isinstance(last_scan, dict):
            return {
                "status": "no_scan",
                "mode": "latest_scan_artifact_mirror",
                "scan_id": "",
                "artifact_dir": "",
                "expected_count": 0,
                "present_count": 0,
                "missing_count": 0,
                "files": [],
                "repair_available": False,
                "repair_action": "algo_scan_artifacts_repair",
                "state_is_source": True,
                "destructive_actions_enabled": False,
            }
        return _algo_scan_artifact_health_from_scan(self.root, last_scan)

    def write_algo_scan_artifacts(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = normalize_algo_state(payload, strict=False)
        last_scan = state.get("last_scan")
        if not isinstance(last_scan, dict):
            return self.algo_scan_artifact_health(state)
        artifact_dir = self.root / str(last_scan["artifact_dir"])
        _write_json(artifact_dir / "scan.json", last_scan, self.root)
        _write_text(artifact_dir / "scan_report.md", scan_report_text(last_scan), self.root)
        _write_json(artifact_dir / "manifest.json", scan_artifact_manifest(last_scan), self.root)
        return self.algo_scan_artifact_health(state)

    def read_nodes_state(self) -> dict[str, Any]:
        return _read_nodes_state_json(self.nodes_state_path)

    def write_nodes_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = _write_json(
            self.nodes_state_path,
            normalize_nodes_state(payload),
            self.root,
            keep_backups=STATE_BACKUP_COUNT,
        )
        active_id = state.get("active_workflow_id")
        workflows = state.get("workflows")
        if active_id and isinstance(workflows, dict) and active_id in workflows:
            _write_json(
                self.root / "artifacts" / "workflows" / str(active_id) / "definition.json",
                workflows[active_id],
                self.root,
            )
            last_dry_run = state.get("last_dry_run")
            if isinstance(last_dry_run, dict) and last_dry_run.get("workflow_id") == active_id:
                workflow_dir = self.root / "artifacts" / "workflows" / str(active_id)
                _write_json(
                    workflow_dir / "dry_run.json",
                    last_dry_run,
                    self.root,
                )
                _write_text(
                    workflow_dir / "dry_run_report.md",
                    dry_run_report_text(workflows[active_id], last_dry_run),
                    self.root,
                )
                _write_json(
                    workflow_dir / "dry_run_manifest.json",
                    dry_run_artifact_manifest(workflows[active_id], last_dry_run),
                    self.root,
                )
        return state

    def read_code_state(self) -> dict[str, Any]:
        return _read_code_state_json(self.code_state_path)

    def write_code_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = _write_json(
            self.code_state_path,
            normalize_code_state(payload),
            self.root,
            keep_backups=STATE_BACKUP_COUNT,
        )
        active_id = state.get("active_notebook_id")
        notebooks = state.get("notebooks")
        if active_id and isinstance(notebooks, dict) and active_id in notebooks:
            notebook = notebooks[active_id]
            _write_json(self.root / str(notebook["path"]), notebook_to_ipynb(notebook), self.root)
            last_analysis = state.get("last_analysis")
            if isinstance(last_analysis, dict) and last_analysis.get("notebook_id") == active_id:
                analysis_dir = self.root / "artifacts" / "code_workspace" / str(active_id)
                _write_json(analysis_dir / "analysis.json", last_analysis, self.root)
                _write_text(
                    analysis_dir / "analysis_report.md",
                    code_analysis_report_text(notebook, last_analysis),
                    self.root,
                )
                _write_json(
                    analysis_dir / "analysis_manifest.json",
                    code_analysis_manifest(notebook, last_analysis),
                    self.root,
                )
        return state

    def read_quant_lab_state(self) -> dict[str, Any]:
        return _read_quant_lab_state_json(self.quant_lab_state_path)

    def write_quant_lab_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(
            self.quant_lab_state_path,
            normalize_quant_lab_state(payload),
            self.root,
            keep_backups=STATE_BACKUP_COUNT,
        )

    def read_quantlib_state(self) -> dict[str, Any]:
        return _read_quantlib_state_json(self.quantlib_state_path)

    def write_quantlib_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(
            self.quantlib_state_path,
            normalize_quantlib_state(payload),
            self.root,
            keep_backups=STATE_BACKUP_COUNT,
        )

    def read_watchlist_state(self) -> dict[str, Any]:
        return normalize_watchlist_state(_read_json(self.watchlist_state_path, default_watchlist_state()))

    def write_watchlist_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(
            self.watchlist_state_path,
            normalize_watchlist_state(payload),
            self.root,
            keep_backups=STATE_BACKUP_COUNT,
        )

    def read_news_digest_state(self) -> dict[str, Any]:
        return normalize_news_digest_state(_read_json(self.news_digest_state_path, default_news_digest_state()))

    def write_news_digest_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(
            self.news_digest_state_path,
            normalize_news_digest_state(payload),
            self.root,
            keep_backups=STATE_BACKUP_COUNT,
        )

    def read_forum_state(self) -> dict[str, Any]:
        return _read_forum_state_json(self.forum_state_path)

    def write_forum_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(
            self.forum_state_path,
            normalize_forum_state(payload),
            self.root,
            keep_backups=STATE_BACKUP_COUNT,
        )

    def read_paper_state(self) -> dict[str, Any]:
        return _read_json(self.paper_state_path, default_paper_state())

    def write_paper_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        state = _write_json(
            self.paper_state_path,
            normalize_paper_state(payload),
            self.root,
            keep_backups=STATE_BACKUP_COUNT,
        )
        _write_paper_event_artifacts(state, self.root)
        return state

    def reset_paper_state(self) -> dict[str, Any]:
        return self.write_paper_state(default_paper_state())

    def read_portfolio_state(self) -> dict[str, Any]:
        return _read_portfolio_state_json(self.portfolio_state_path)

    def write_portfolio_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        return _write_json(
            self.portfolio_state_path,
            normalize_portfolio_state(payload),
            self.root,
            keep_backups=STATE_BACKUP_COUNT,
        )

    def protected_state_files(self) -> list[tuple[str, Path]]:
        """The user-state files that keep rotating pre-write backups (S0.1)."""
        return [
            ("settings", self.settings_path),
            ("profile", self.profile_path),
            ("layout", self.layout_path),
            ("dashboard_layout", self.dashboard_path),
            ("markets_layout", self.markets_path),
            ("news_layout", self.news_path),
            ("chat_state", self.chat_state_path),
            ("algo_state", self.algo_state_path),
            ("nodes_state", self.nodes_state_path),
            ("code_state", self.code_state_path),
            ("quant_lab_state", self.quant_lab_state_path),
            ("quantlib_state", self.quantlib_state_path),
            ("forum_state", self.forum_state_path),
            ("paper_state", self.paper_state_path),
            ("portfolio_state", self.portfolio_state_path),
            ("watchlist_state", self.watchlist_state_path),
            ("news_digest_state", self.news_digest_state_path),
        ]

    def state_backup_index(self) -> dict[str, Any]:
        """Metadata-only view of every backup slot; never reads file contents.

        `modified_at` carries the backed-up version's own mtime (copy2 keeps
        it), i.e. "state as of this time", not "backup taken at this time".
        """
        rows: list[dict[str, Any]] = []
        backup_total = 0
        for kind, path in self.protected_state_files():
            backups: list[dict[str, Any]] = []
            for slot in range(1, STATE_BACKUP_COUNT + 1):
                bak = path.with_name(f"{path.name}.bak{slot}")
                if not bak.is_file():
                    continue
                stat = bak.stat()
                backups.append(
                    {
                        "slot": slot,
                        "path": _relative(bak, self.root),
                        "size_bytes": stat.st_size,
                        "modified_at": datetime.fromtimestamp(
                            stat.st_mtime, tz=UTC
                        ).isoformat(timespec="seconds"),
                    }
                )
            backup_total += len(backups)
            rows.append(
                {
                    "kind": kind,
                    "state_path": _relative(path, self.root),
                    "state_exists": path.is_file(),
                    "backup_count": len(backups),
                    "backups": backups,
                }
            )
        return {
            "summary": {
                "protected_file_count": len(rows),
                "backup_file_count": backup_total,
                "keep_backups": STATE_BACKUP_COUNT,
            },
            "rows": rows,
            "safety": {
                "reads_file_contents": False,
                "mutates_local_state": False,
                "restore_endpoint_available": True,
                "restore_endpoint": "/api/local-state/restore",
                "manual_restore_doc": "docs/planning/M26_AGENT_READINESS_PLAN.md",
            },
        }

    def restore_state_backup(self, kind: str, slot: int) -> dict[str, Any]:
        """Copy backup slot `slot` back over the live state file for `kind`.

        The pre-restore live file rotates into slot 1 first, so every restore
        is itself undoable. An unreadable or non-object backup aborts with
        zero writes — never restore from a broken baseline.
        """
        paths = dict(self.protected_state_files())
        path = paths.get(kind)
        if path is None:
            known = ", ".join(sorted(paths))
            raise StateRestoreError(f"Unknown protected state kind '{kind}' (known: {known})")
        if not 1 <= slot <= STATE_BACKUP_COUNT:
            raise StateRestoreError(f"Backup slot must be 1..{STATE_BACKUP_COUNT}, got {slot}")
        backup = path.with_name(f"{path.name}.bak{slot}")
        if not backup.is_file():
            raise StateRestoreError(f"No backup in slot {slot} for '{kind}'")
        try:
            payload = json.loads(backup.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StateRestoreError(
                f"Backup slot {slot} for '{kind}' is unreadable; aborted with zero writes"
            ) from exc
        if not isinstance(payload, dict):
            raise StateRestoreError(
                f"Backup slot {slot} for '{kind}' is not a JSON object; aborted with zero writes"
            )
        backup_stat = backup.stat()
        had_live_file = path.is_file()
        _write_json(path, payload, self.root, keep_backups=STATE_BACKUP_COUNT)
        return {
            "kind": kind,
            "state_path": _relative(path, self.root),
            "restored_from": {
                "slot": slot,
                "path": _relative(backup, self.root),
                "modified_at": datetime.fromtimestamp(backup_stat.st_mtime, tz=UTC).isoformat(
                    timespec="seconds"
                ),
                "size_bytes": backup_stat.st_size,
            },
            "undo": {
                "available": had_live_file,
                "path": _relative(path.with_name(f"{path.name}.bak1"), self.root),
                "how": (
                    "the pre-restore version rotated into slot 1; restore the same "
                    "kind with slot=1 to undo"
                    if had_live_file
                    else "no live file existed before this restore; nothing rotated"
                ),
            },
            "safety": {
                "mutates_local_state": True,
                "confirm_required": True,
                "zero_write_on_unreadable_backup": True,
            },
        }

    def read_state(self) -> dict[str, Any]:
        return {
            "settings": self.read_settings(),
            "profile": self.read_profile(),
            "layout": self.read_layout(),
            "storage": {
                "settings": _relative(self.settings_path, self.root),
                "profile": _relative(self.profile_path, self.root),
                "layout": _relative(self.layout_path, self.root),
                "dashboard": _relative(self.dashboard_path, self.root),
                "markets": _relative(self.markets_path, self.root),
                "news": _relative(self.news_path, self.root),
                "market_cache": _relative(self.market_cache_path, self.root),
                "crypto_detail_cache": _relative(self.crypto_detail_cache_path(), self.root),
                "news_cache": _relative(self.news_cache_path, self.root),
                "sec_fundamentals_cache": _relative(self.sec_fundamentals_cache_path(), self.root),
                "sec_company_tickers_cache": _relative(
                    self.sec_company_tickers_cache_path,
                    self.root,
                ),
                "sec_company_submissions_cache": _relative(
                    self.sec_company_submissions_cache_path(),
                    self.root,
                ),
                "sec_company_submissions_watchlist_caches": [
                    _relative(self.sec_company_submissions_cache_path(company["cik"]), self.root)
                    for company in SEC_DEFAULT_COMPANY_WATCHLIST
                ],
                "sec_xbrl_frames_cache": _relative(self.sec_xbrl_frame_cache_path(), self.root),
                "dbnomics_macro_cache": _relative(self.dbnomics_macro_cache_path(), self.root),
                "fred_macro_cache": _relative(self.fred_macro_cache_path(), self.root),
                "bls_macro_cache": _relative(self.bls_macro_cache_path, self.root),
                "eurostat_hicp_cache": _relative(self.eurostat_hicp_cache_path, self.root),
                "nasdaq_trader_symbol_directory_cache": _relative(
                    self.nasdaq_trader_symbol_directory_cache_path,
                    self.root,
                ),
                "openfigi_mapping_cache": _relative(
                    self.openfigi_mapping_cache_path,
                    self.root,
                ),
                "bea_regional_cache": _relative(self.bea_regional_cache_path, self.root),
                "census_acs_profile_cache": _relative(
                    self.census_acs_profile_cache_path, self.root
                ),
                "alpha_vantage_equity_quote_cache": _relative(
                    self.alpha_vantage_equity_quote_cache_path(), self.root
                ),
                "alpha_vantage_etf_quote_cache": _relative(
                    self.alpha_vantage_equity_quote_cache_path("SPY"), self.root
                ),
                "alpha_vantage_fx_quote_cache": _relative(
                    self.alpha_vantage_fx_quote_cache_path(), self.root
                ),
                "twelve_data_quote_cache": _relative(
                    self.twelve_data_quote_cache_path(), self.root
                ),
                "finnhub_quote_cache": _relative(
                    self.finnhub_quote_cache_path(), self.root
                ),
                "fmp_quote_cache": _relative(self.fmp_quote_cache_path(), self.root),
                "stooq_quote_cache": _relative(self.stooq_quote_cache_path(), self.root),
                "yahoo_quote_cache": _relative(self.yahoo_quote_cache_path(), self.root),
                "moex_quote_cache": _relative(self.moex_quote_cache_path(), self.root),
                "twse_quote_cache": _relative(self.twse_quote_cache_path(), self.root),
                "treasury_rates_cache": _relative(self.treasury_rates_cache_path, self.root),
                "nyfed_sofr_cache": _relative(self.nyfed_sofr_cache_path, self.root),
                "ecb_fx_cache": _relative(self.ecb_fx_cache_path, self.root),
                "federal_reserve_h10_fx_cache": _relative(
                    self.federal_reserve_h10_fx_cache_path,
                    self.root,
                ),
                "bank_of_canada_fx_cache": _relative(
                    self.bank_of_canada_fx_cache_path,
                    self.root,
                ),
                "world_bank_commodity_cache": _relative(
                    self.world_bank_commodity_cache_path, self.root
                ),
                "cftc_cot_cache": _relative(self.cftc_cot_cache_path, self.root),
                "eia_energy_cache": _relative(self.eia_energy_cache_path, self.root),
                "sec_fund_tickers_cache": _relative(self.sec_fund_tickers_cache_path, self.root),
                "paper_state": _relative(self.paper_state_path, self.root),
                "portfolio_state": _relative(self.portfolio_state_path, self.root),
                "chat_state": _relative(self.chat_state_path, self.root),
                "algo_state": _relative(self.algo_state_path, self.root),
                "algo_scan_artifacts": "artifacts/algo/scans",
                "nodes_state": _relative(self.nodes_state_path, self.root),
                "code_state": _relative(self.code_state_path, self.root),
                "quant_lab_state": _relative(self.quant_lab_state_path, self.root),
                "quantlib_state": _relative(self.quantlib_state_path, self.root),
                "forum_state": _relative(self.forum_state_path, self.root),
                "diagnostics_artifacts": _relative(self.diagnostics_root_path, self.root),
            },
        }


def _relative(path: Path, root: Path) -> str:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        path_text = _strip_windows_extended_prefix(str(resolved_path))
        root_text = _strip_windows_extended_prefix(str(resolved_root))
        path_cmp = os.path.normcase(os.path.normpath(path_text))
        root_cmp = os.path.normcase(os.path.normpath(root_text))
        if path_cmp != root_cmp and not path_cmp.startswith(root_cmp + os.sep):
            raise
        return Path(os.path.relpath(path_text, root_text)).as_posix()


def _strip_windows_extended_prefix(value: str) -> str:
    return value[4:] if value.startswith("\\\\?\\") else value


def _safe_path_part(raw: str, fallback: str) -> str:
    value = "".join(ch for ch in str(raw) if ch.isalnum() or ch in {"-", ".", "_"})
    return value[:120] or fallback


def _sec_submission_payload_cik(payload: dict[str, Any]) -> str:
    status = payload.get("status") if isinstance(payload, dict) else {}
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    rows = payload.get("rows") if isinstance(payload, dict) else []
    if isinstance(summary, dict) and summary.get("cik"):
        return safe_sec_cik(summary.get("cik"))
    if isinstance(status, dict) and status.get("cik"):
        return safe_sec_cik(status.get("cik"))
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict) and row.get("cik"):
                return safe_sec_cik(row.get("cik"))
    return "0000320193"


def state_root_from_env() -> Path:
    raw_root = os.environ.get("LOCAL_TERMINAL_STATE_ROOT")
    if not raw_root:
        return DEFAULT_STATE_ROOT

    root = Path(raw_root)
    resolved = root.resolve()
    if not resolved.is_relative_to(DEFAULT_STATE_ROOT.resolve()):
        raise ValueError(
            "LOCAL_TERMINAL_STATE_ROOT must stay inside the repository "
            "(or inside ~/.otto for an installed, non-checkout run)"
        )
    return resolved


def _sanitize_profile(payload: dict[str, Any]) -> dict[str, Any]:
    profile = {**DEFAULT_PROFILE, **payload}
    profile.update(
        {
            "cloud_account_required": False,
            "billing_enabled": False,
            "subscription_required": False,
            "cr_required": False,
            "credits_enabled": False,
            "private_api_required": False,
        }
    )
    return profile


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return dict(default)
    if not isinstance(value, dict):
        return dict(default)
    return {**default, **value}


def _read_portfolio_state_json(path: Path) -> dict[str, Any]:
    default = default_portfolio_state()
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError:
        return {
            **default,
            "invalid_portfolios": {
                path.name: "Invalid portfolio state JSON",
            },
        }
    except OSError:
        return {
            **default,
            "invalid_portfolios": {
                path.name: "Cannot read portfolio state JSON",
            },
        }
    if not isinstance(value, dict):
        return {
            **default,
            "invalid_portfolios": {
                path.name: "Portfolio state JSON must be an object",
            },
        }
    return {**default, **value}


def _read_chat_state_json(path: Path) -> dict[str, Any]:
    default = default_chat_state()
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError:
        return {
            **default,
            "invalid_sessions": {
                path.name: "Invalid chat state JSON",
            },
        }
    except OSError:
        return {
            **default,
            "invalid_sessions": {
                path.name: "Cannot read chat state JSON",
            },
        }
    if not isinstance(value, dict):
        return {
            **default,
            "invalid_sessions": {
                path.name: "Chat state JSON must be an object",
            },
        }
    return {**default, **value}


def _read_algo_state_json(path: Path) -> dict[str, Any]:
    default = default_algo_state()
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError:
        return {
            **default,
            "invalid_strategies": {
                path.name: "Invalid algo state JSON",
            },
        }
    except OSError:
        return {
            **default,
            "invalid_strategies": {
                path.name: "Cannot read algo state JSON",
            },
        }
    if not isinstance(value, dict):
        return {
            **default,
            "invalid_strategies": {
                path.name: "Algo state JSON must be an object",
            },
        }
    return {**default, **value}


def _read_nodes_state_json(path: Path) -> dict[str, Any]:
    default = default_nodes_state()
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError:
        return {
            **default,
            "invalid_workflows": {
                path.name: "Invalid nodes state JSON",
            },
        }
    except OSError:
        return {
            **default,
            "invalid_workflows": {
                path.name: "Cannot read nodes state JSON",
            },
        }
    if not isinstance(value, dict):
        return {
            **default,
            "invalid_workflows": {
                path.name: "Nodes state JSON must be an object",
            },
        }
    return {**default, **value}


def _read_code_state_json(path: Path) -> dict[str, Any]:
    default = default_code_state()
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError:
        return {
            **default,
            "invalid_notebooks": {
                path.name: "Invalid code state JSON",
            },
        }
    except OSError:
        return {
            **default,
            "invalid_notebooks": {
                path.name: "Cannot read code state JSON",
            },
        }
    if not isinstance(value, dict):
        return {
            **default,
            "invalid_notebooks": {
                path.name: "Code state JSON must be an object",
            },
        }
    return {**default, **value}


def _read_quant_lab_state_json(path: Path) -> dict[str, Any]:
    default = default_quant_lab_state()
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError:
        return {
            **default,
            "invalid_runs": {
                path.name: "Invalid Quant Lab state JSON",
            },
        }
    except OSError:
        return {
            **default,
            "invalid_runs": {
                path.name: "Cannot read Quant Lab state JSON",
            },
        }
    if not isinstance(value, dict):
        return {
            **default,
            "invalid_runs": {
                path.name: "Quant Lab state JSON must be an object",
            },
        }
    return {**default, **value}


def _read_quantlib_state_json(path: Path) -> dict[str, Any]:
    default = default_quantlib_state()
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError:
        return {
            **default,
            "invalid_calculations": {
                path.name: "Invalid QuantLib state JSON",
            },
        }
    except OSError:
        return {
            **default,
            "invalid_calculations": {
                path.name: "Cannot read QuantLib state JSON",
            },
        }
    if not isinstance(value, dict):
        return {
            **default,
            "invalid_calculations": {
                path.name: "QuantLib state JSON must be an object",
            },
        }
    return {**default, **value}


def _read_forum_state_json(path: Path) -> dict[str, Any]:
    default = default_forum_state()
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except json.JSONDecodeError:
        return {
            **default,
            "invalid_posts": {
                path.name: "Invalid forum state JSON",
            },
        }
    except OSError:
        return {
            **default,
            "invalid_posts": {
                path.name: "Cannot read forum state JSON",
            },
        }
    if not isinstance(value, dict):
        return {
            **default,
            "invalid_posts": {
                path.name: "Forum state JSON must be an object",
            },
        }
    return {**default, **value}


STATE_BACKUP_COUNT = 3


class StateRestoreError(ValueError):
    """A state-backup restore request that must be refused (zero writes)."""


def _rotate_state_backups(path: Path, keep_backups: int) -> None:
    """Copy the current state file to <name>.bak1 (newest) before it is replaced.

    Best-effort by design: a failed rotation must never block persisting the
    user's new state, so OS-level failures degrade to skipping this backup
    round instead of raising. Backups are plain siblings (`x.json.bak1`) so
    `*.json` globs and artifact scanners never pick them up.
    """
    if not path.exists():
        return
    try:
        path.with_name(f"{path.name}.bak{keep_backups}").unlink(missing_ok=True)
        for index in range(keep_backups - 1, 0, -1):
            source = path.with_name(f"{path.name}.bak{index}")
            if source.exists():
                _replace_with_retry(source, path.with_name(f"{path.name}.bak{index + 1}"))
        shutil.copy2(path, path.with_name(f"{path.name}.bak1"))
    except OSError:
        return


def _write_json(
    path: Path, payload: dict[str, Any], root: Path, *, keep_backups: int = 0
) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Refusing to write outside repository: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _temporary_write_path(path)
    with tmp_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    if keep_backups > 0:
        _rotate_state_backups(path, keep_backups)
    _replace_with_retry(tmp_path, path)
    return payload


def _write_text(path: Path, payload: str, root: Path) -> None:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Refusing to write outside repository: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _temporary_write_path(path)
    tmp_path.write_text(payload, encoding="utf-8", newline="\n")
    _replace_with_retry(tmp_path, path)


def _algo_scan_artifact_health_from_scan(root: Path, scan: dict[str, Any]) -> dict[str, Any]:
    expected = {
        "scan": "scan.json",
        "report": "scan_report.md",
        "manifest": "manifest.json",
    }
    artifact_dir = str(scan.get("artifact_dir") or "")
    files: list[dict[str, Any]] = []
    present_count = 0
    for kind, filename in expected.items():
        relative_path = str(scan.get("artifacts", {}).get(kind) or f"{artifact_dir}/{filename}")
        path = root / relative_path
        resolved = path.resolve()
        inside_root = resolved.is_relative_to(root.resolve())
        exists = inside_root and path.is_file()
        size_bytes = path.stat().st_size if exists else 0
        if exists:
            present_count += 1
        files.append(
            {
                "kind": kind,
                "path": relative_path,
                "exists": exists,
                "size_bytes": size_bytes,
                "state": "present" if exists else "missing",
                "repairable": inside_root,
            }
        )
    missing_count = len(expected) - present_count
    return {
        "status": "complete" if missing_count == 0 else "repairable_missing",
        "mode": "latest_scan_artifact_mirror",
        "scan_id": str(scan.get("scan_id") or ""),
        "artifact_dir": artifact_dir,
        "expected_count": len(expected),
        "present_count": present_count,
        "missing_count": missing_count,
        "files": files,
        "repair_available": True,
        "repair_action": "algo_scan_artifacts_repair",
        "state_is_source": True,
        "destructive_actions_enabled": False,
    }


def _temporary_write_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")


def _replace_with_retry(tmp_path: Path, path: Path) -> None:
    for attempt in range(5):
        try:
            tmp_path.replace(path)
            return
        except PermissionError:
            if attempt == 4:
                try:
                    tmp_path.unlink(missing_ok=True)
                finally:
                    raise
            time.sleep(0.05 * (attempt + 1))


def _write_paper_event_artifacts(state: dict[str, Any], root: Path) -> None:
    orders = state.get("orders") if isinstance(state.get("orders"), list) else []
    fills = state.get("fills") if isinstance(state.get("fills"), list) else []
    ledger = state.get("ledger") if isinstance(state.get("ledger"), list) else []
    account = state.get("account") if isinstance(state.get("account"), dict) else {}

    for date_key, rows in _group_events_by_date(orders, "created_at").items():
        _write_jsonl(root / "artifacts" / "paper" / date_key / "orders.jsonl", rows, root)
    for date_key, rows in _group_events_by_date(fills, "filled_at").items():
        _write_jsonl(root / "artifacts" / "paper" / date_key / "fills.jsonl", rows, root)
    for date_key, rows in _group_events_by_date(ledger, "recorded_at").items():
        _write_jsonl(root / "artifacts" / "paper" / date_key / "ledger.jsonl", rows, root)
    account_date = _date_from_timestamp(account.get("updated_at"))
    if account_date:
        _write_jsonl(
            root / "artifacts" / "paper" / account_date / "account_snapshots.jsonl",
            [account],
            root,
        )


def _group_events_by_date(rows: list[Any], timestamp_key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        date_key = _date_from_timestamp(row.get(timestamp_key))
        if date_key:
            grouped.setdefault(date_key, []).append(row)
    return grouped


def _date_from_timestamp(raw: Any) -> str:
    if not isinstance(raw, str) or len(raw) < 10:
        return ""
    date_key = raw[:10]
    return date_key if len(date_key) == 10 and date_key[4] == "-" and date_key[7] == "-" else ""


def _write_jsonl(path: Path, rows: list[dict[str, Any]], root: Path) -> None:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f"Refusing to write outside repository: {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = _temporary_write_path(path)
    with tmp_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            json.dump(row, handle, sort_keys=True)
            handle.write("\n")
    _replace_with_retry(tmp_path, path)
