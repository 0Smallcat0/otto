"""Markets contracts, local panel state, and public crypto data adapters."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from datetime import UTC, datetime
from typing import Any
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import urlopen

from otto.local_terminal.nasdaq_trader_data import nasdaq_trader_symbol_search_payload
from otto.local_terminal.research_lineage import enrich_source_coverage_row


DEFAULT_MARKET_COLUMNS: list[str] = [
    "price",
    "chg",
    "chg_pct",
    "high",
    "low",
    "vol",
]
AVAILABLE_MARKET_COLUMNS: tuple[dict[str, str], ...] = (
    {"column_id": "chg", "label": "CHG"},
    {"column_id": "chg_pct", "label": "CHG%"},
    {"column_id": "high", "label": "HIGH"},
    {"column_id": "low", "label": "LOW"},
    {"column_id": "vol", "label": "VOL"},
    {"column_id": "bid", "label": "BID"},
    {"column_id": "ask", "label": "ASK"},
    {"column_id": "open", "label": "OPEN"},
    {"column_id": "name", "label": "NAME"},
    {"column_id": "source", "label": "SOURCE"},
    {"column_id": "state", "label": "STATE"},
    {"column_id": "provider_id", "label": "PROVIDER"},
    {"column_id": "retrieved_at", "label": "RETRIEVED"},
)
DEFAULT_MARKET_SYMBOLS: list[str] = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
MAX_MARKET_PANELS = 9
MAX_SYMBOLS_PER_PANEL = 12
DEFAULT_MARKET_PANELS: list[dict[str, Any]] = [
    {
        "panel_id": "crypto-majors",
        "title": "Crypto Majors",
        "column": 1,
        "symbols": list(DEFAULT_MARKET_SYMBOLS),
    }
]
ASSET_TABS: tuple[dict[str, str], ...] = (
    {
        "tab_id": "crypto",
        "label": "Crypto",
        "state": "public",
        "provider_id": "binance_spot_public",
        "source": "binance_public",
        "auth_mode": "no-key",
        "message": "Public ticker data with Kraken/Coinbase detail cache fallback.",
        "fallback": "stale public cache or unavailable rows with source diagnostics",
    },
    {
        "tab_id": "stocks",
        "label": "Stocks",
        "state": "key_required",
        "provider_id": (
            "sec_company_ticker_registry_public / sec_edgar_public / "
            "alphavantage_global_quote_optional_key"
        ),
        "source": "SEC company registry/fundamentals; Alpha Vantage quotes require local key",
        "auth_mode": "no-key fundamentals / optional local key quotes",
        "message": (
            "SEC public company registry and facts can populate Stocks; "
            "quote refresh is local-key gated."
        ),
        "fallback": (
            "SEC company registry/facts cache, Alpha Vantage local quote cache, "
            "or key-required state; no fake stock quotes"
        ),
    },
    {
        "tab_id": "etf",
        "label": "ETF",
        "state": "no_key_provider_ready",
        "provider_id": "sec_fund_ticker_registry_public / alphavantage_global_quote_optional_key",
        "source": "SEC fund ticker registry; Alpha Vantage ETF quotes require local key",
        "auth_mode": "no-key registry / optional local key quotes",
        "message": "SEC fund ticker registry can populate ETF/fund identifiers; ETF quote refresh is local-key gated.",
        "fallback": "SEC fund ticker cache, Alpha Vantage local ETF quote cache, or key-required state; no fake ETF quotes",
    },
    {
        "tab_id": "fx",
        "label": "FX",
        "state": "no_key_provider_ready",
        "provider_id": (
            "ecb_fx_reference_public / federal_reserve_h10_ddp_public / "
            "bank_of_canada_valet_fx_reference_public / premium_market_data_option"
        ),
        "source": "ECB, Federal Reserve, and Bank of Canada reference rates; optional/premium spot providers disabled",
        "auth_mode": "no-key reference / optional local key spot quotes",
        "message": (
            "ECB EUR, Federal Reserve H.10 USD, and Bank of Canada CAD reference "
            "rates can populate FX; tradable spot feeds remain gated."
        ),
        "fallback": "ECB/H.10/BoC reference cache or unavailable state with source and refresh guidance",
    },
    {
        "tab_id": "commodities",
        "label": "Commodities",
        "state": "no_key_provider_ready",
        "provider_id": (
            "world_bank_commodity_monthly_public / cftc_cot_legacy_public / "
            "premium_market_data_option"
        ),
        "source": "World Bank monthly Pink Sheet and CFTC COT positioning; spot/futures providers disabled",
        "auth_mode": "no-key reference/positioning / optional local key spot context",
        "message": "World Bank prices and CFTC COT positioning can populate this route.",
        "fallback": "World Bank/CFTC cache or unavailable state with source guidance",
    },
    {
        "tab_id": "rates",
        "label": "Bonds/Rates",
        "state": "no_key_provider_ready",
        "provider_id": "us_treasury_yield_public / nyfed_sofr_public / fred_optional_local_key",
        "source": "U.S. Treasury and NY Fed public reference rates; FRED blocked by local secret gate",
        "auth_mode": "no-key or optional local key",
        "message": "Treasury yield curve and NY Fed SOFR are available through public no-key feeds; FRED stays disabled.",
        "fallback": "Treasury/SOFR cache or unavailable state with source and refresh guidance",
    },
    {
        "tab_id": "indexes",
        "label": "Indexes",
        "state": "no_key_provider_ready",
        "provider_id": "premium_market_data_option / dbnomics_public / bls_public_macro / bea_regional_optional_key / census_api_optional_key",
        "source": "Public macro proxy; index quote provider not enabled",
        "auth_mode": "optional local key or no-key macro proxy",
        "message": "Public macro context can populate this tab; index quotes remain gated.",
        "fallback": "Public macro cache or setup card; no synthetic index levels",
    },
    {
        "tab_id": "regional",
        "label": "Regional",
        "state": "no_key_provider_ready",
        "provider_id": "premium_market_data_option / dbnomics_public / bls_public_macro / bea_regional_optional_key / census_api_optional_key",
        "source": "Public macro proxy; optional regional providers are local-key gated",
        "auth_mode": "optional local key or paid-gated",
        "message": "Public macro context can populate regional context; BEA/Census regional context is local-key gated.",
        "fallback": "Public macro cache or setup card; no synthetic regional levels",
    },
)
SYMBOL_NAMES: dict[str, str] = {
    "BTCUSDT": "Bitcoin / Tether",
    "ETHUSDT": "Ethereum / Tether",
    "SOLUSDT": "Solana / Tether",
    "BNBUSDT": "BNB / Tether",
    "XRPUSDT": "XRP / Tether",
    "ADAUSDT": "Cardano / Tether",
}
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"
SOURCE_COVERAGE_TTL_SECONDS: dict[str, int] = {
    "sec_edgar_public": 86400,
    "sec_xbrl_frames_public": 86400,
    "sec_company_ticker_registry_public": 86400,
    "sec_company_submissions_public": 86400,
    "sec_fund_ticker_registry_public": 86400,
    "alphavantage_global_quote_optional_key": 86400,
    "fred_optional_local_key": 86400,
    "bls_public_macro": 86400,
    "eurostat_hicp_public": 86400,
    "bea_regional_optional_key": 86400,
    "census_api_optional_key": 86400,
    "dbnomics_public": 86400,
    "us_treasury_yield_public": 86400,
    "nyfed_sofr_public": 86400,
    "ecb_fx_reference_public": 86400,
    "federal_reserve_h10_ddp_public": 86400,
    "bank_of_canada_valet_fx_reference_public": 86400,
    "world_bank_commodity_monthly_public": 604800,
    "cftc_cot_legacy_public": 604800,
    "eia_open_data_optional_key": 86400,
    "finnhub_equity_quote_optional_key": 86400,
    "stooq_public_quote_snapshot": 900,
    "moex_iss_delayed_quote_snapshot": 900,
    "twse_openapi_daily_quote_snapshot": 86400,
    "nasdaq_trader_symbol_directory_public": 86400,
    "openfigi_identifier_mapping_public": 86400,
}
SOURCE_COVERAGE_DOCS_URLS: dict[str, str] = {
    "sec_edgar_public": (
        "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
    ),
    "sec_xbrl_frames_public": (
        "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
    ),
    "sec_company_ticker_registry_public": (
        "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
    ),
    "sec_company_submissions_public": (
        "https://www.sec.gov/search-filings/edgar-application-programming-interfaces"
    ),
    "sec_fund_ticker_registry_public": (
        "https://www.sec.gov/files/company_tickers_mf.json"
    ),
    "alphavantage_global_quote_optional_key": "https://www.alphavantage.co/documentation/",
    "fred_optional_local_key": "https://fred.stlouisfed.org/docs/api/fred/",
    "bls_public_macro": "https://www.bls.gov/developers/api_signature_v2.htm",
    "eurostat_hicp_public": (
        "https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/"
        "api-detailed-guidelines/api-statistics"
    ),
    "bea_regional_optional_key": "https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf",
    "census_api_optional_key": "https://api.census.gov/data/2023/acs/acs5/profile.html",
    "dbnomics_public": "https://docs.db.nomics.world/",
    "us_treasury_yield_public": (
        "https://home.treasury.gov/policy-issues/financing-the-government/"
        "interest-rate-statistics/treasury-yield-curve-rates"
    ),
    "nyfed_sofr_public": "https://www.newyorkfed.org/markets/reference-rates/sofr",
    "ecb_fx_reference_public": "https://www.ecb.europa.eu/stats/eurofxref/",
    "federal_reserve_h10_ddp_public": (
        "https://www.federalreserve.gov/datadownload/choose.aspx?rel=h10"
    ),
    "bank_of_canada_valet_fx_reference_public": "https://www.bankofcanada.ca/valet/docs",
    "world_bank_commodity_monthly_public": (
        "https://www.worldbank.org/en/research/commodity-markets"
    ),
    "cftc_cot_legacy_public": (
        "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"
    ),
    "eia_open_data_optional_key": "https://www.eia.gov/opendata/documentation.php",
    "finnhub_equity_quote_optional_key": "https://finnhub.io/docs/api/quote",
    "stooq_public_quote_snapshot": "https://stooq.com/q/?s=^spx",
    "moex_iss_delayed_quote_snapshot": "https://www.moex.com/a2920",
    "twse_openapi_daily_quote_snapshot": "https://openapi.twse.com.tw/",
    "nasdaq_trader_symbol_directory_public": (
        "https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs"
    ),
    "openfigi_identifier_mapping_public": "https://www.openfigi.com/api/documentation",
}
SOURCE_COVERAGE_CACHE_PATHS: dict[str, str] = {
    "sec_edgar_public": "market_data/fundamentals/sec/0000320193/companyfacts.json",
    "sec_xbrl_frames_public": (
        "market_data/fundamentals/sec/frames/us-gaap/Assets/USD/CY2023Q4I.json"
    ),
    "sec_company_ticker_registry_public": (
        "market_data/fundamentals/sec/company_tickers.json"
    ),
    "sec_company_submissions_public": (
        "market_data/fundamentals/sec/0000320193/submissions.json"
    ),
    "sec_fund_ticker_registry_public": "market_data/funds/sec/company_tickers_mf.json",
    "alphavantage_global_quote_optional_key": (
        "market_data/equities/alphavantage/global_quote/AAPL.json"
    ),
    "fred_optional_local_key": "market_data/macro/fred/DGS10.json",
    "bls_public_macro": "market_data/macro/bls/latest_series.json",
    "eurostat_hicp_public": "market_data/macro/eurostat/hicp_ea20_cp00_i15.json",
    "bea_regional_optional_key": "market_data/regional/bea/SAGDP9N_LINE1_STATE.json",
    "census_api_optional_key": "market_data/regional/census/acs5_profile_state_2023.json",
    "dbnomics_public": "market_data/macro/dbnomics/INSEE/IPC-2015",
    "us_treasury_yield_public": "market_data/rates/treasury/daily_yield_curve.json",
    "nyfed_sofr_public": "market_data/rates/nyfed/sofr.json",
    "ecb_fx_reference_public": "market_data/fx/ecb/eurofxref_daily.json",
    "federal_reserve_h10_ddp_public": (
        "market_data/fx/federal_reserve/h10_reference_rates.json"
    ),
    "bank_of_canada_valet_fx_reference_public": (
        "market_data/fx/bank_of_canada/valet_fx_reference_rates.json"
    ),
    "world_bank_commodity_monthly_public": (
        "market_data/commodities/world_bank/pink_sheet_monthly.json"
    ),
    "cftc_cot_legacy_public": "market_data/commodities/cftc/cot_legacy_futures.json",
    "eia_open_data_optional_key": "market_data/commodities/eia/energy_series.json",
    "finnhub_equity_quote_optional_key": "market_data/quotes/finnhub/AAPL.json",
    "stooq_public_quote_snapshot": "market_data/quotes/stooq/AAPLUS.json",
    "moex_iss_delayed_quote_snapshot": "market_data/quotes/moex/SBER.json",
    "twse_openapi_daily_quote_snapshot": "market_data/quotes/twse/2330.json",
    "nasdaq_trader_symbol_directory_public": (
        "market_data/reference/nasdaq_trader/symbol_directory.json"
    ),
    "openfigi_identifier_mapping_public": "market_data/reference/openfigi/mapping.json",
}


def default_markets_layout() -> dict[str, Any]:
    return {
        "layout_id": "markets-default",
        "auto_refresh": False,
        "asset_tab": "crypto",
        "columns": list(DEFAULT_MARKET_COLUMNS),
        "panels": [dict(panel) for panel in DEFAULT_MARKET_PANELS],
    }


def normalize_markets_layout(layout: dict[str, Any]) -> dict[str, Any]:
    columns = _normalize_columns(layout.get("columns", DEFAULT_MARKET_COLUMNS))
    panels = _normalize_panels(layout.get("panels", DEFAULT_MARKET_PANELS))
    asset_tab = layout.get("asset_tab")
    if asset_tab not in {tab["tab_id"] for tab in ASSET_TABS}:
        asset_tab = "crypto"
    auto_refresh = layout.get("auto_refresh", False)
    return {
        "layout_id": "markets-default",
        "auto_refresh": auto_refresh is True,
        "asset_tab": asset_tab,
        "columns": columns,
        "panels": panels,
    }


def markets_payload(
    layout: dict[str, Any],
    cache: dict[str, Any] | None = None,
    crypto_detail_cache: dict[str, Any] | None = None,
    news_cache: dict[str, Any] | None = None,
    research_data: dict[str, Any] | None = None,
    rates_data: dict[str, Any] | None = None,
    fx_data: dict[str, Any] | None = None,
    commodity_data: dict[str, Any] | None = None,
    fund_data: dict[str, Any] | None = None,
    equity_quote_data: dict[str, Any] | None = None,
    etf_quote_data: dict[str, Any] | None = None,
    fx_quote_data: dict[str, Any] | None = None,
    twelve_data_quote_data: dict[str, Any] | None = None,
    finnhub_quote_data: dict[str, Any] | None = None,
    fmp_quote_data: dict[str, Any] | None = None,
    stooq_quote_data: dict[str, Any] | None = None,
    nasdaq_symbol_data: dict[str, Any] | None = None,
    moex_quote_data: dict[str, Any] | None = None,
    twse_quote_data: dict[str, Any] | None = None,
    openfigi_mapping_data: dict[str, Any] | None = None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    extra_symbols: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    normalized = normalize_markets_layout(layout)
    symbols = _layout_symbols(normalized)
    for extra_symbol in extra_symbols or ():
        if extra_symbol not in symbols:
            symbols.append(extra_symbol)
    status = _status(
        source="public_provider_unavailable",
        state="unavailable",
        last_update="not refreshed",
        message="No public ticker cache is available yet; refresh public crypto data or use a detail cache.",
    )
    rows = _unavailable_rows(symbols, status=status)

    if refresh and fetcher is not None:
        try:
            live_tickers = fetcher(symbols)
            provenance = _ticker_provenance(live_tickers)
            status = _status(
                source=provenance["source"],
                state="live",
                last_update=_utc_now(),
                message=provenance["message"],
                provider_id=provenance["provider_id"],
                cache_path="market_data/crypto_latest.json",
                fallback_used=provenance["fallback_used"],
            )
            rows = _rows_from_tickers(live_tickers, symbols, status=status)
            cache = {"status": status, "rows": rows}
        except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
            cache = cache or {}

    if status["state"] != "live" and cache:
        cached_rows = cache.get("rows")
        cached_status = cache.get("status")
        if isinstance(cached_rows, list) and isinstance(cached_status, dict):
            cached_last_update = str(cached_status.get("last_update") or "unknown")
            cache_age = _cache_age_seconds(cached_last_update)
            if (
                cache_age is not None
                and cache_age <= FRESH_TICKER_CACHE_SECONDS
                and str(cached_status.get("state")) == "live"
            ):
                # A refresh just wrote this cache; serving it back is not a failure.
                status = _status(
                    source=str(cached_status.get("source") or "binance_public"),
                    state="live",
                    last_update=cached_last_update,
                    message=str(cached_status.get("message") or "Public read-only Binance data refreshed."),
                    provider_id=str(cached_status.get("provider_id") or "binance_spot_public"),
                    cache_path=str(cached_status.get("cache_path") or "market_data/crypto_latest.json"),
                    fallback_used=False,
                )
            else:
                status = _status(
                    source=str(cached_status.get("source") or "binance_public"),
                    state="stale",
                    last_update=cached_last_update,
                    message="Using stale public ticker cache; refresh failed or has not run.",
                    provider_id=str(cached_status.get("provider_id") or "binance_spot_public"),
                    cache_path=str(cached_status.get("cache_path") or "market_data/crypto_latest.json"),
                    fallback_used=True,
                )
            rows = _filter_rows(cached_rows, symbols, status=status)

    if status["state"] not in {"live", "stale"} and crypto_detail_cache:
        detail_status, detail_rows = _rows_from_crypto_detail_cache(crypto_detail_cache, symbols)
        if detail_rows:
            status = detail_status
            rows = _merge_rows(_unavailable_rows(symbols, status=status), detail_rows)

    panels = [_panel_rows(panel, rows) for panel in normalized["panels"]]
    research_summary = _research_summary(
        research_data,
        news_cache,
        rates_data,
        fx_data,
        commodity_data,
        fund_data,
        equity_quote_data,
        etf_quote_data,
        fx_quote_data,
        twelve_data_quote_data,
        finnhub_quote_data,
        fmp_quote_data,
        stooq_quote_data,
        nasdaq_symbol_data,
        moex_quote_data,
        twse_quote_data,
        openfigi_mapping_data,
    )
    source_coverage_matrix = _source_coverage_matrix(
        research_summary,
        crypto_status=status,
        crypto_rows=rows,
    )
    return {
        "layout": normalized,
        "status": status,
        "asset_tabs": _asset_gateways(research_summary),
        "asset_gateways": _asset_gateways(research_summary),
        "available_columns": list(AVAILABLE_MARKET_COLUMNS),
        "source_summary": _source_summary(status, rows),
        "research_summary": research_summary,
        "source_coverage_matrix": source_coverage_matrix,
        "quote_reference_coverage": quote_reference_coverage_payload(source_coverage_matrix),
        "stocks": _stocks_view(research_summary),
        "etf": _etf_view(research_summary),
        "indexes": _macro_market_view(research_summary, "indexes"),
        "regional": _macro_market_view(research_summary, "regional"),
        "rates": _rates_view(research_summary),
        "fx": _fx_view(research_summary),
        "commodities": _commodities_view(research_summary),
        "rows": rows,
        "panels": panels,
        "cache": cache if status["state"] == "live" else None,
    }


def fetch_binance_tickers(symbols: list[str], timeout: float = 3.0) -> list[dict[str, Any]]:
    encoded_symbols = quote(json.dumps(symbols, separators=(",", ":")))
    url = f"{BINANCE_TICKER_URL}?symbols={encoded_symbols}"
    with urlopen(url, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Binance ticker response must be a list")
    return payload


def _normalize_columns(raw_columns: Any) -> list[str]:
    available = {"price"} | {column["column_id"] for column in AVAILABLE_MARKET_COLUMNS}
    columns: list[str] = []
    if isinstance(raw_columns, list):
        for column in raw_columns:
            if isinstance(column, str) and column in available and column not in columns:
                columns.append(column)
    return columns or list(DEFAULT_MARKET_COLUMNS)


def _normalize_panels(raw_panels: Any) -> list[dict[str, Any]]:
    panels: list[dict[str, Any]] = []
    if isinstance(raw_panels, list):
        for index, panel in enumerate(raw_panels[:MAX_MARKET_PANELS], start=1):
            if not isinstance(panel, dict):
                continue
            symbols = _normalize_symbols(panel.get("symbols", DEFAULT_MARKET_SYMBOLS))
            title = panel.get("title")
            panel_id = panel.get("panel_id")
            column = panel.get("column")
            panels.append(
                {
                    "panel_id": panel_id if isinstance(panel_id, str) and panel_id else f"panel-{index}",
                    "title": title[:80] if isinstance(title, str) and title.strip() else f"Panel {index}",
                    "column": column if isinstance(column, int) and 1 <= column <= 3 else 1,
                    "symbols": symbols,
                }
            )
    return panels or [dict(panel) for panel in DEFAULT_MARKET_PANELS]


def _normalize_symbols(raw_symbols: Any) -> list[str]:
    symbols: list[str] = []
    if isinstance(raw_symbols, list):
        for symbol in raw_symbols:
            if isinstance(symbol, str):
                normalized = "".join(ch for ch in symbol.upper() if ch.isalnum())[:20]
                if normalized and normalized not in symbols:
                    symbols.append(normalized)
                if len(symbols) >= MAX_SYMBOLS_PER_PANEL:
                    break
    return symbols or list(DEFAULT_MARKET_SYMBOLS)


def _layout_symbols(layout: dict[str, Any]) -> list[str]:
    symbols: list[str] = []
    for panel in layout["panels"]:
        for symbol in panel["symbols"]:
            if symbol not in symbols:
                symbols.append(symbol)
    return symbols or list(DEFAULT_MARKET_SYMBOLS)


def _ticker_provenance(tickers: Any) -> dict[str, Any]:
    """Which provider actually served these rows.

    A fetcher chain stamps `_source`/`_provider_id` on the rows it returns;
    without that the status block would claim Binance for data a fallback
    provider supplied (2026-07-17 dogfood P3).
    """
    default = {
        "source": "binance_public",
        "provider_id": "binance_spot_public",
        "message": "Public read-only Binance data refreshed.",
        "fallback_used": False,
    }
    if isinstance(tickers, (list, tuple)):
        for ticker in tickers:
            if isinstance(ticker, dict) and ticker.get("_source"):
                source = str(ticker["_source"])
                return {
                    "source": source,
                    "provider_id": str(ticker.get("_provider_id") or source),
                    "message": str(ticker.get("_message") or f"Public read-only {source} data refreshed."),
                    "fallback_used": source != default["source"],
                }
    return default


def _rows_from_tickers(
    tickers: Any,
    symbols: list[str],
    *,
    status: dict[str, Any],
) -> list[dict[str, str]]:
    rows_by_symbol: dict[str, dict[str, str]] = {}
    if isinstance(tickers, (list, tuple)):
        for ticker in tickers:
            if not isinstance(ticker, dict):
                continue
            symbol = str(ticker.get("symbol", "")).upper()
            if symbol not in symbols:
                continue
            rows_by_symbol[symbol] = {
                "symbol": symbol,
                "price": str(ticker.get("lastPrice", "")),
                "chg": str(ticker.get("priceChange", "")),
                "chg_pct": str(ticker.get("priceChangePercent", "")),
                "high": str(ticker.get("highPrice", "")),
                "low": str(ticker.get("lowPrice", "")),
                "vol": str(ticker.get("volume", "")),
                "bid": str(ticker.get("bidPrice", "")),
                "ask": str(ticker.get("askPrice", "")),
                "open": str(ticker.get("openPrice", "")),
                "name": SYMBOL_NAMES.get(symbol, symbol),
                "source": str(status.get("source") or ""),
                "state": str(status.get("state") or ""),
                "provider_id": str(status.get("provider_id") or ""),
                "retrieved_at": str(status.get("last_update") or ""),
                "cache_path": str(status.get("cache_path") or ""),
            }
    return [
        rows_by_symbol.get(symbol)
        or _unavailable_row(symbol, status=status)
        for symbol in symbols
    ]


def _filter_rows(
    rows: list[Any],
    symbols: list[str],
    *,
    status: dict[str, Any],
) -> list[dict[str, str]]:
    rows_by_symbol = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("symbol", "")).upper()
        if symbol in symbols:
            rows_by_symbol[symbol] = _coerce_market_row(row, status=status)
    return [rows_by_symbol.get(symbol) or _unavailable_row(symbol, status=status) for symbol in symbols]


def _unavailable_rows(symbols: list[str], *, status: dict[str, Any]) -> list[dict[str, str]]:
    return [_unavailable_row(symbol, status=status) for symbol in symbols]


def _unavailable_row(symbol: str, *, status: dict[str, Any]) -> dict[str, str]:
    return {
        "symbol": symbol,
        "price": "N/A",
        "chg": "N/A",
        "chg_pct": "N/A",
        "high": "N/A",
        "low": "N/A",
        "vol": "N/A",
        "bid": "N/A",
        "ask": "N/A",
        "open": "N/A",
        "name": SYMBOL_NAMES.get(symbol, symbol),
        "source": str(status.get("source") or "public_provider_unavailable"),
        "state": "unavailable",
        "provider_id": str(status.get("provider_id") or ""),
        "retrieved_at": str(status.get("last_update") or ""),
        "cache_path": str(status.get("cache_path") or ""),
    }


def _coerce_market_row(row: dict[str, Any], *, status: dict[str, Any]) -> dict[str, str]:
    symbol = str(row.get("symbol", "")).upper()
    return {
        "symbol": symbol,
        "price": str(row.get("price", "N/A")),
        "chg": str(row.get("chg", "N/A")),
        "chg_pct": str(row.get("chg_pct", "N/A")),
        "high": str(row.get("high", "N/A")),
        "low": str(row.get("low", "N/A")),
        "vol": str(row.get("vol", "N/A")),
        "bid": str(row.get("bid", "N/A")),
        "ask": str(row.get("ask", "N/A")),
        "open": str(row.get("open", "N/A")),
        "name": str(row.get("name") or SYMBOL_NAMES.get(symbol, symbol)),
        "source": str(row.get("source") or status.get("source") or ""),
        "state": str(row.get("state") or status.get("state") or ""),
        "provider_id": str(row.get("provider_id") or status.get("provider_id") or ""),
        "retrieved_at": str(row.get("retrieved_at") or status.get("last_update") or ""),
        "cache_path": str(row.get("cache_path") or status.get("cache_path") or ""),
    }


def _rows_from_crypto_detail_cache(
    cache: dict[str, Any],
    symbols: list[str],
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    status = cache.get("status") if isinstance(cache, dict) else {}
    status = status if isinstance(status, dict) else {}
    symbol = str(status.get("symbol") or "").upper()
    if symbol not in symbols:
        return _status(source="crypto_detail_cache_unavailable", state="unavailable"), []
    candles = [row for row in cache.get("candles", []) if isinstance(row, dict)]
    if not candles:
        return _status(source="crypto_detail_cache_unavailable", state="unavailable"), []
    latest = candles[-1]
    depth = cache.get("depth") if isinstance(cache.get("depth"), dict) else {}
    bids = [row for row in depth.get("bids", []) if isinstance(row, dict)] if isinstance(depth, dict) else []
    asks = [row for row in depth.get("asks", []) if isinstance(row, dict)] if isinstance(depth, dict) else []
    source = str(status.get("source") or "crypto_detail_cache")
    provider_id = str(status.get("provider_id") or "")
    timeframe = str(status.get("timeframe") or "15m")
    last_update = str(status.get("last_update") or "unknown")
    cache_path = f"market_data/crypto/{symbol}/{timeframe}.json"
    detail_status = _status(
        source=source,
        state="stale" if status.get("state") != "live" else "live",
        last_update=last_update,
        message=f"Using public crypto detail cache for {symbol}; ticker cache is unavailable.",
        provider_id=provider_id,
        cache_path=cache_path,
        fallback_used=True,
    )
    open_price = _decimal(latest.get("open"))
    close_price = _decimal(latest.get("close"))
    chg = close_price - open_price if open_price is not None and close_price is not None else None
    chg_pct = (chg / open_price * Decimal("100")) if chg is not None and open_price not in (None, Decimal("0")) else None
    row = {
        "symbol": symbol,
        "price": str(latest.get("close") or "N/A"),
        "chg": _format_decimal(chg),
        "chg_pct": _format_decimal(chg_pct),
        "high": str(latest.get("high") or "N/A"),
        "low": str(latest.get("low") or "N/A"),
        "vol": str(latest.get("volume") or "N/A"),
        "bid": str(bids[0].get("price") if bids else "N/A"),
        "ask": str(asks[0].get("price") if asks else "N/A"),
        "open": str(latest.get("open") or "N/A"),
        "name": SYMBOL_NAMES.get(symbol, symbol),
        "source": source,
        "state": str(detail_status["state"]),
        "provider_id": provider_id,
        "retrieved_at": last_update,
        "cache_path": cache_path,
    }
    return detail_status, [row]


def _merge_rows(base_rows: list[dict[str, str]], overlay_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    overlays = {row["symbol"]: row for row in overlay_rows}
    return [overlays.get(row["symbol"], row) for row in base_rows]


def _source_summary(status: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    available_rows = [row for row in rows if row.get("price") not in {"", "N/A"}]
    unavailable_rows = len(rows) - len(available_rows)
    return {
        "primary_source": str(status.get("source") or ""),
        "state": str(status.get("state") or ""),
        "provider_id": str(status.get("provider_id") or ""),
        "retrieved_at": str(status.get("last_update") or ""),
        "cache_path": str(status.get("cache_path") or ""),
        "fallback_used": bool(status.get("fallback_used")),
        "row_count": len(rows),
        "available_rows": len(available_rows),
        "unavailable_rows": unavailable_rows,
        "message": str(status.get("message") or ""),
    }


def _research_summary(
    research_data: dict[str, Any] | None,
    news_cache: dict[str, Any] | None,
    rates_data: dict[str, Any] | None = None,
    fx_data: dict[str, Any] | None = None,
    commodity_data: dict[str, Any] | None = None,
    fund_data: dict[str, Any] | None = None,
    equity_quote_data: dict[str, Any] | None = None,
    etf_quote_data: dict[str, Any] | None = None,
    fx_quote_data: dict[str, Any] | None = None,
    twelve_data_quote_data: dict[str, Any] | None = None,
    finnhub_quote_data: dict[str, Any] | None = None,
    fmp_quote_data: dict[str, Any] | None = None,
    stooq_quote_data: dict[str, Any] | None = None,
    nasdaq_symbol_data: dict[str, Any] | None = None,
    moex_quote_data: dict[str, Any] | None = None,
    twse_quote_data: dict[str, Any] | None = None,
    openfigi_mapping_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = research_data if isinstance(research_data, dict) else {}
    rates_payload = rates_data if isinstance(rates_data, dict) else {}
    fx_payload = fx_data if isinstance(fx_data, dict) else {}
    commodity_payload = commodity_data if isinstance(commodity_data, dict) else {}
    fund_payload = fund_data if isinstance(fund_data, dict) else {}
    quote_payload = equity_quote_data if isinstance(equity_quote_data, dict) else {}
    etf_quote_payload = etf_quote_data if isinstance(etf_quote_data, dict) else {}
    fx_quote_payload = fx_quote_data if isinstance(fx_quote_data, dict) else {}
    twelve_quote_payload = (
        twelve_data_quote_data if isinstance(twelve_data_quote_data, dict) else {}
    )
    finnhub_quote_payload = (
        finnhub_quote_data if isinstance(finnhub_quote_data, dict) else {}
    )
    fmp_quote_payload = fmp_quote_data if isinstance(fmp_quote_data, dict) else {}
    stooq_payload = stooq_quote_data if isinstance(stooq_quote_data, dict) else {}
    nasdaq_payload = nasdaq_symbol_data if isinstance(nasdaq_symbol_data, dict) else {}
    moex_payload = moex_quote_data if isinstance(moex_quote_data, dict) else {}
    twse_payload = twse_quote_data if isinstance(twse_quote_data, dict) else {}
    openfigi_payload = openfigi_mapping_data if isinstance(openfigi_mapping_data, dict) else {}
    fundamentals = data.get("fundamentals") if isinstance(data.get("fundamentals"), dict) else {}
    sec_frames = data.get("sec_frames") if isinstance(data.get("sec_frames"), dict) else {}
    equity_registry = (
        data.get("equity_registry") if isinstance(data.get("equity_registry"), dict) else {}
    )
    filings = data.get("filings") if isinstance(data.get("filings"), dict) else {}
    macro = data.get("macro") if isinstance(data.get("macro"), dict) else {}
    fred_core = data.get("fred_core") if isinstance(data.get("fred_core"), dict) else {}
    treasury = (
        rates_payload.get("treasury")
        if isinstance(rates_payload.get("treasury"), dict)
        else {}
    )
    sofr = rates_payload.get("sofr") if isinstance(rates_payload.get("sofr"), dict) else {}
    ecb_fx = fx_payload.get("ecb") if isinstance(fx_payload.get("ecb"), dict) else {}
    h10_fx = fx_payload.get("h10") if isinstance(fx_payload.get("h10"), dict) else {}
    boc_fx = fx_payload.get("boc") if isinstance(fx_payload.get("boc"), dict) else {}
    commodities = (
        commodity_payload.get("world_bank")
        if isinstance(commodity_payload.get("world_bank"), dict)
        else {}
    )
    cftc_cot = (
        commodity_payload.get("cftc")
        if isinstance(commodity_payload.get("cftc"), dict)
        else {}
    )
    eia_energy = (
        commodity_payload.get("eia")
        if isinstance(commodity_payload.get("eia"), dict)
        else {}
    )
    sec_funds = (
        fund_payload.get("sec_funds")
        if isinstance(fund_payload.get("sec_funds"), dict)
        else {}
    )
    equity_quotes = (
        quote_payload.get("alpha_vantage")
        if isinstance(quote_payload.get("alpha_vantage"), dict)
        else quote_payload
    )
    etf_quotes = (
        etf_quote_payload.get("alpha_vantage")
        if isinstance(etf_quote_payload.get("alpha_vantage"), dict)
        else etf_quote_payload
    )
    fx_quotes = (
        fx_quote_payload.get("alpha_vantage_fx")
        if isinstance(fx_quote_payload.get("alpha_vantage_fx"), dict)
        else fx_quote_payload
    )
    twelve_quotes = (
        twelve_quote_payload.get("twelve_data")
        if isinstance(twelve_quote_payload.get("twelve_data"), dict)
        else twelve_quote_payload
    )
    finnhub_quotes = (
        finnhub_quote_payload.get("finnhub")
        if isinstance(finnhub_quote_payload.get("finnhub"), dict)
        else finnhub_quote_payload
    )
    fmp_quotes = (
        fmp_quote_payload.get("fmp")
        if isinstance(fmp_quote_payload.get("fmp"), dict)
        else fmp_quote_payload
    )
    stooq_quotes = (
        stooq_payload.get("stooq")
        if isinstance(stooq_payload.get("stooq"), dict)
        else stooq_payload
    )
    moex_quotes = (
        moex_payload.get("moex")
        if isinstance(moex_payload.get("moex"), dict)
        else moex_payload
    )
    twse_quotes = (
        twse_payload.get("twse")
        if isinstance(twse_payload.get("twse"), dict)
        else twse_payload
    )
    nasdaq_symbols = (
        nasdaq_payload.get("nasdaq_trader")
        if isinstance(nasdaq_payload.get("nasdaq_trader"), dict)
        else nasdaq_payload
    )
    openfigi_mapping = (
        openfigi_payload.get("openfigi")
        if isinstance(openfigi_payload.get("openfigi"), dict)
        else openfigi_payload
    )
    f_status = fundamentals.get("status") if isinstance(fundamentals.get("status"), dict) else {}
    frames_status = sec_frames.get("status") if isinstance(sec_frames.get("status"), dict) else {}
    equity_registry_status = (
        equity_registry.get("status") if isinstance(equity_registry.get("status"), dict) else {}
    )
    filings_status = filings.get("status") if isinstance(filings.get("status"), dict) else {}
    m_status = macro.get("status") if isinstance(macro.get("status"), dict) else {}
    r_status = treasury.get("status") if isinstance(treasury.get("status"), dict) else {}
    sofr_status = sofr.get("status") if isinstance(sofr.get("status"), dict) else {}
    fx_status = ecb_fx.get("status") if isinstance(ecb_fx.get("status"), dict) else {}
    h10_status = h10_fx.get("status") if isinstance(h10_fx.get("status"), dict) else {}
    boc_status = boc_fx.get("status") if isinstance(boc_fx.get("status"), dict) else {}
    commodity_status = (
        commodities.get("status") if isinstance(commodities.get("status"), dict) else {}
    )
    cftc_status = cftc_cot.get("status") if isinstance(cftc_cot.get("status"), dict) else {}
    eia_status = (
        eia_energy.get("status") if isinstance(eia_energy.get("status"), dict) else {}
    )
    fund_status = sec_funds.get("status") if isinstance(sec_funds.get("status"), dict) else {}
    quote_status = (
        equity_quotes.get("status") if isinstance(equity_quotes.get("status"), dict) else {}
    )
    etf_quote_status = (
        etf_quotes.get("status") if isinstance(etf_quotes.get("status"), dict) else {}
    )
    fx_quote_status = fx_quotes.get("status") if isinstance(fx_quotes.get("status"), dict) else {}
    twelve_quote_status = (
        twelve_quotes.get("status") if isinstance(twelve_quotes.get("status"), dict) else {}
    )
    finnhub_quote_status = (
        finnhub_quotes.get("status") if isinstance(finnhub_quotes.get("status"), dict) else {}
    )
    fmp_quote_status = (
        fmp_quotes.get("status") if isinstance(fmp_quotes.get("status"), dict) else {}
    )
    stooq_quote_status = (
        stooq_quotes.get("status") if isinstance(stooq_quotes.get("status"), dict) else {}
    )
    moex_quote_status = (
        moex_quotes.get("status") if isinstance(moex_quotes.get("status"), dict) else {}
    )
    twse_quote_status = (
        twse_quotes.get("status") if isinstance(twse_quotes.get("status"), dict) else {}
    )
    nasdaq_symbol_status = (
        nasdaq_symbols.get("status") if isinstance(nasdaq_symbols.get("status"), dict) else {}
    )
    openfigi_status = (
        openfigi_mapping.get("status")
        if isinstance(openfigi_mapping.get("status"), dict)
        else {}
    )
    companies = fundamentals.get("companies") if isinstance(fundamentals.get("companies"), list) else []
    frames_summary = (
        sec_frames.get("summary") if isinstance(sec_frames.get("summary"), dict) else {}
    )
    frame_rows = sec_frames.get("rows") if isinstance(sec_frames.get("rows"), list) else []
    equity_registry_summary = (
        equity_registry.get("summary") if isinstance(equity_registry.get("summary"), dict) else {}
    )
    equity_registry_rows = (
        equity_registry.get("rows") if isinstance(equity_registry.get("rows"), list) else []
    )
    filings_summary = (
        filings.get("summary") if isinstance(filings.get("summary"), dict) else {}
    )
    filing_rows = filings.get("rows") if isinstance(filings.get("rows"), list) else []
    series = macro.get("series") if isinstance(macro.get("series"), list) else []
    macro_summary = macro.get("summary") if isinstance(macro.get("summary"), dict) else {}
    headline_series = macro.get("headline_series") if isinstance(macro.get("headline_series"), dict) else {}
    provider_summaries = (
        macro.get("provider_summaries") if isinstance(macro.get("provider_summaries"), list) else []
    )
    latest_rates = treasury.get("latest") if isinstance(treasury.get("latest"), dict) else {}
    tenors = latest_rates.get("tenors") if isinstance(latest_rates.get("tenors"), list) else []
    sofr_summary = sofr.get("summary") if isinstance(sofr.get("summary"), dict) else {}
    sofr_rows = sofr.get("rows") if isinstance(sofr.get("rows"), list) else []
    fx_summary = ecb_fx.get("summary") if isinstance(ecb_fx.get("summary"), dict) else {}
    fx_rows = ecb_fx.get("rows") if isinstance(ecb_fx.get("rows"), list) else []
    h10_summary = h10_fx.get("summary") if isinstance(h10_fx.get("summary"), dict) else {}
    h10_rows = h10_fx.get("rows") if isinstance(h10_fx.get("rows"), list) else []
    boc_summary = boc_fx.get("summary") if isinstance(boc_fx.get("summary"), dict) else {}
    boc_rows = boc_fx.get("rows") if isinstance(boc_fx.get("rows"), list) else []
    commodity_summary = (
        commodities.get("summary") if isinstance(commodities.get("summary"), dict) else {}
    )
    commodity_rows = (
        commodities.get("rows") if isinstance(commodities.get("rows"), list) else []
    )
    cftc_summary = (
        cftc_cot.get("summary") if isinstance(cftc_cot.get("summary"), dict) else {}
    )
    cftc_rows = cftc_cot.get("rows") if isinstance(cftc_cot.get("rows"), list) else []
    eia_series = (
        eia_energy.get("series") if isinstance(eia_energy.get("series"), list) else []
    )
    eia_summary = (
        eia_energy.get("summary") if isinstance(eia_energy.get("summary"), dict) else {}
    )
    fund_summary = sec_funds.get("summary") if isinstance(sec_funds.get("summary"), dict) else {}
    fund_rows = sec_funds.get("rows") if isinstance(sec_funds.get("rows"), list) else []
    quote_summary = (
        equity_quotes.get("summary") if isinstance(equity_quotes.get("summary"), dict) else {}
    )
    quote_rows = (
        equity_quotes.get("quotes") if isinstance(equity_quotes.get("quotes"), list) else []
    )
    etf_quote_summary = (
        etf_quotes.get("summary") if isinstance(etf_quotes.get("summary"), dict) else {}
    )
    etf_quote_rows = (
        etf_quotes.get("quotes") if isinstance(etf_quotes.get("quotes"), list) else []
    )
    fx_quote_summary = (
        fx_quotes.get("summary") if isinstance(fx_quotes.get("summary"), dict) else {}
    )
    fx_quote_rows = fx_quotes.get("quotes") if isinstance(fx_quotes.get("quotes"), list) else []
    twelve_quote_summary = (
        twelve_quotes.get("summary") if isinstance(twelve_quotes.get("summary"), dict) else {}
    )
    twelve_quote_rows = (
        twelve_quotes.get("quotes") if isinstance(twelve_quotes.get("quotes"), list) else []
    )
    finnhub_quote_summary = (
        finnhub_quotes.get("summary") if isinstance(finnhub_quotes.get("summary"), dict) else {}
    )
    finnhub_quote_rows = (
        finnhub_quotes.get("quotes") if isinstance(finnhub_quotes.get("quotes"), list) else []
    )
    fmp_quote_summary = (
        fmp_quotes.get("summary") if isinstance(fmp_quotes.get("summary"), dict) else {}
    )
    fmp_quote_rows = (
        fmp_quotes.get("quotes") if isinstance(fmp_quotes.get("quotes"), list) else []
    )
    stooq_quote_summary = (
        stooq_quotes.get("summary") if isinstance(stooq_quotes.get("summary"), dict) else {}
    )
    stooq_quote_rows = (
        stooq_quotes.get("quotes") if isinstance(stooq_quotes.get("quotes"), list) else []
    )
    moex_quote_summary = (
        moex_quotes.get("summary") if isinstance(moex_quotes.get("summary"), dict) else {}
    )
    moex_quote_rows = (
        moex_quotes.get("quotes") if isinstance(moex_quotes.get("quotes"), list) else []
    )
    twse_quote_summary = (
        twse_quotes.get("summary") if isinstance(twse_quotes.get("summary"), dict) else {}
    )
    twse_quote_rows = (
        twse_quotes.get("quotes") if isinstance(twse_quotes.get("quotes"), list) else []
    )
    nasdaq_symbol_summary = (
        nasdaq_symbols.get("summary") if isinstance(nasdaq_symbols.get("summary"), dict) else {}
    )
    nasdaq_symbol_rows = (
        nasdaq_symbols.get("symbols") if isinstance(nasdaq_symbols.get("symbols"), list) else []
    )
    openfigi_summary = (
        openfigi_mapping.get("summary")
        if isinstance(openfigi_mapping.get("summary"), dict)
        else {}
    )
    openfigi_rows = (
        openfigi_mapping.get("mappings")
        if isinstance(openfigi_mapping.get("mappings"), list)
        else []
    )
    news_items = news_cache.get("items") if isinstance(news_cache, dict) else []
    news_items = news_items if isinstance(news_items, list) else []
    return {
        "fundamentals": {
            "state": str(f_status.get("state") or "unavailable"),
            "source": str(f_status.get("source") or "sec_edgar_public"),
            "provider_id": str(f_status.get("provider_id") or "sec_edgar_public"),
            "retrieved_at": str(f_status.get("last_update") or "not refreshed"),
            "cache_path": str(f_status.get("cache_path") or ""),
            "docs_url": str(f_status.get("docs_url") or ""),
            "company_count": len(companies),
            "fact_count": sum(
                len(company.get("facts", []))
                for company in companies
                if isinstance(company, dict)
            ),
            "companies": _company_fact_rows(companies),
        },
        "sec_frames": {
            "state": str(frames_status.get("state") or "unavailable"),
            "source": str(frames_status.get("source") or "sec_xbrl_frames"),
            "provider_id": str(frames_status.get("provider_id") or "sec_xbrl_frames_public"),
            "retrieved_at": str(frames_status.get("last_update") or "not refreshed"),
            "cache_path": str(frames_status.get("cache_path") or ""),
            "docs_url": str(frames_status.get("docs_url") or ""),
            "taxonomy": str(frames_summary.get("taxonomy") or "us-gaap"),
            "tag": str(frames_summary.get("tag") or "Assets"),
            "unit": str(frames_summary.get("unit") or "USD"),
            "period": str(frames_summary.get("period") or "CY2023Q4I"),
            "label": str(frames_summary.get("label") or "Assets"),
            "description": str(frames_summary.get("description") or ""),
            "row_count": int(frames_summary.get("row_count") or 0),
            "source_row_count": int(frames_summary.get("source_row_count") or 0),
            "entity_count": int(frames_summary.get("entity_count") or 0),
            "quote_semantics": str(frames_summary.get("quote_semantics") or "not_quote"),
            "rows": _sec_frame_rows(frame_rows),
        },
        "equity_registry": {
            "state": str(equity_registry_status.get("state") or "unavailable"),
            "source": str(equity_registry_status.get("source") or "sec_company_ticker_registry"),
            "provider_id": str(
                equity_registry_status.get("provider_id")
                or "sec_company_ticker_registry_public"
            ),
            "retrieved_at": str(equity_registry_status.get("last_update") or "not refreshed"),
            "cache_path": str(equity_registry_status.get("cache_path") or ""),
            "docs_url": str(equity_registry_status.get("docs_url") or ""),
            "row_count": int(equity_registry_summary.get("row_count") or 0),
            "registry_total": int(equity_registry_summary.get("registry_total") or 0),
            "matched_symbols": str(equity_registry_summary.get("matched_symbols") or ""),
            "quote_state": str(
                equity_registry_summary.get("quote_state")
                or "disabled_until_optional_quote_provider"
            ),
            "quote_provider": str(
                equity_registry_summary.get("quote_provider")
                or "alphavantage_global_quote_optional_key"
            ),
            "rows": _company_registry_rows(equity_registry_rows),
        },
        "filings": {
            "state": str(filings_status.get("state") or "unavailable"),
            "source": str(filings_status.get("source") or "sec_company_submissions"),
            "provider_id": str(
                filings_status.get("provider_id") or "sec_company_submissions_public"
            ),
            "retrieved_at": str(filings_status.get("last_update") or "not refreshed"),
            "cache_path": str(filings_status.get("cache_path") or ""),
            "docs_url": str(filings_status.get("docs_url") or ""),
            "row_count": int(filings_summary.get("row_count") or 0),
            "latest_filing_date": str(filings_summary.get("latest_filing_date") or ""),
            "latest_form": str(filings_summary.get("latest_form") or ""),
            "symbol": str(filings_summary.get("symbol") or "AAPL"),
            "cik": str(filings_summary.get("cik") or "0000320193"),
            "company_count": int(filings_summary.get("company_count") or 0),
            "symbol_count": int(filings_summary.get("symbol_count") or 0),
            "symbols": str(filings_summary.get("symbols") or ""),
            "filing_symbols": str(filings_summary.get("filing_symbols") or ""),
            "latest_symbol": str(filings_summary.get("latest_symbol") or ""),
            "cache_paths": str(filings_summary.get("cache_paths") or ""),
            "rows": _company_filing_rows(filing_rows),
        },
        "macro": {
            "state": str(m_status.get("state") or "unavailable"),
            "source": str(m_status.get("source") or "dbnomics_public"),
            "provider_id": str(m_status.get("provider_id") or "dbnomics_public"),
            "retrieved_at": str(m_status.get("last_update") or "not refreshed"),
            "cache_path": str(m_status.get("cache_path") or ""),
            "docs_url": str(m_status.get("docs_url") or ""),
            "series_count": len(series),
            "provider_count": int(macro_summary.get("provider_count") or 0),
            "latest": str(
                macro_summary.get("latest_value")
                or headline_series.get("latest_value")
                or ""
            ),
            "latest_period": str(
                macro_summary.get("latest_period")
                or headline_series.get("latest_period")
                or ""
            ),
            "primary_provider": str(
                macro_summary.get("primary_provider") or headline_series.get("provider_id") or ""
            ),
            "headline_series_id": str(
                macro_summary.get("headline_series_id") or headline_series.get("series_id") or ""
            ),
            "headline_label": str(
                macro_summary.get("headline_label") or headline_series.get("label") or ""
            ),
            "headline_rule": str(macro_summary.get("headline_rule") or ""),
            "headline_series": _macro_series_rows([headline_series])[0] if headline_series else {},
            "provider_summaries": _macro_provider_summary_rows(provider_summaries),
            "series": _macro_series_rows(series),
        },
        "funds": {
            "state": str(fund_status.get("state") or "unavailable"),
            "source": str(fund_status.get("source") or "sec_fund_ticker_registry"),
            "provider_id": str(
                fund_status.get("provider_id") or "sec_fund_ticker_registry_public"
            ),
            "retrieved_at": str(fund_status.get("last_update") or "not refreshed"),
            "cache_path": str(fund_status.get("cache_path") or ""),
            "docs_url": str(fund_status.get("docs_url") or ""),
            "row_count": int(fund_summary.get("row_count") or 0),
            "registry_total": int(fund_summary.get("registry_total") or 0),
            "matched_symbols": str(fund_summary.get("matched_symbols") or ""),
            "quote_state": str(fund_summary.get("quote_state") or "disabled_until_provider_gate"),
            "quote_provider": str(
                fund_summary.get("quote_provider")
                or "optional_local_key_or_paid_etf_quote_provider"
            ),
            "rows": _fund_registry_rows(fund_rows),
        },
        "etf_quotes": {
            "state": str(etf_quote_status.get("state") or "key_required"),
            "source": str(etf_quote_status.get("source") or "alphavantage_global_quote"),
            "provider_id": str(
                etf_quote_status.get("provider_id") or "alphavantage_global_quote_optional_key"
            ),
            "retrieved_at": str(etf_quote_status.get("last_update") or "not refreshed"),
            "cache_path": str(etf_quote_status.get("cache_path") or ""),
            "docs_url": str(etf_quote_status.get("docs_url") or ""),
            "message": str(
                etf_quote_status.get("message")
                or "Store a local Alpha Vantage key before refreshing ETF quotes."
            ),
            "symbol": str(etf_quote_summary.get("symbol") or "SPY"),
            "symbols": str(etf_quote_summary.get("symbols") or etf_quote_summary.get("symbol") or "SPY"),
            "price": str(etf_quote_summary.get("price") or ""),
            "change": str(etf_quote_summary.get("change") or ""),
            "change_percent": str(etf_quote_summary.get("change_percent") or ""),
            "latest_trading_day": str(etf_quote_summary.get("latest_trading_day") or ""),
            "row_count": int(etf_quote_summary.get("row_count") or 0),
            "requested_count": int(etf_quote_summary.get("requested_count") or 0),
            "cached_count": int(etf_quote_summary.get("cached_count") or 0),
            "live_count": int(etf_quote_summary.get("live_count") or 0),
            "stale_count": int(etf_quote_summary.get("stale_count") or 0),
            "key_required_count": int(etf_quote_summary.get("key_required_count") or 0),
            "rows": _equity_quote_rows(etf_quote_rows),
        },
        "equity_quotes": {
            "state": str(quote_status.get("state") or "key_required"),
            "source": str(quote_status.get("source") or "alphavantage_global_quote"),
            "provider_id": str(
                quote_status.get("provider_id") or "alphavantage_global_quote_optional_key"
            ),
            "retrieved_at": str(quote_status.get("last_update") or "not refreshed"),
            "cache_path": str(quote_status.get("cache_path") or ""),
            "docs_url": str(quote_status.get("docs_url") or ""),
            "message": str(
                quote_status.get("message")
                or "Store a local Alpha Vantage key to refresh equity quotes."
            ),
            "symbol": str(quote_summary.get("symbol") or "AAPL"),
            "symbols": str(quote_summary.get("symbols") or quote_summary.get("symbol") or "AAPL"),
            "price": str(quote_summary.get("price") or ""),
            "change": str(quote_summary.get("change") or ""),
            "change_percent": str(quote_summary.get("change_percent") or ""),
            "latest_trading_day": str(quote_summary.get("latest_trading_day") or ""),
            "row_count": int(quote_summary.get("row_count") or 0),
            "requested_count": int(quote_summary.get("requested_count") or 0),
            "cached_count": int(quote_summary.get("cached_count") or 0),
            "live_count": int(quote_summary.get("live_count") or 0),
            "stale_count": int(quote_summary.get("stale_count") or 0),
            "key_required_count": int(quote_summary.get("key_required_count") or 0),
            "rows": _equity_quote_rows(quote_rows),
        },
        "rates": {
            "state": str(r_status.get("state") or "unavailable"),
            "source": str(r_status.get("source") or "us_treasury_public"),
            "provider_id": str(r_status.get("provider_id") or "us_treasury_yield_public"),
            "retrieved_at": str(r_status.get("last_update") or "not refreshed"),
            "cache_path": str(r_status.get("cache_path") or ""),
            "docs_url": str(r_status.get("docs_url") or ""),
            "latest_date": str(latest_rates.get("date") or ""),
            "tenor_count": len(tenors),
            "two_year": _tenor_rate(tenors, "2Y"),
            "ten_year": _tenor_rate(tenors, "10Y"),
            "thirty_year": _tenor_rate(tenors, "30Y"),
            "slope_10y_2y": _slope(tenors),
            "rows": [
                {
                    "tenor": str(row.get("tenor") or ""),
                    "rate": str(row.get("rate") or ""),
                    "unit": str(row.get("unit") or "percent"),
                }
                for row in tenors
                if isinstance(row, dict)
            ],
            "sofr": {
                "state": str(sofr_status.get("state") or "unavailable"),
                "source": str(sofr_status.get("source") or "nyfed_sofr_public"),
                "provider_id": str(sofr_status.get("provider_id") or "nyfed_sofr_public"),
                "retrieved_at": str(sofr_status.get("last_update") or "not refreshed"),
                "cache_path": str(sofr_status.get("cache_path") or ""),
                "docs_url": str(sofr_status.get("docs_url") or ""),
                "latest_date": str(sofr_summary.get("latest_date") or ""),
                "rate": str(sofr_summary.get("rate") or ""),
                "volume_in_billions": str(sofr_summary.get("volume_in_billions") or ""),
                "percentile_25": str(sofr_summary.get("percentile_25") or ""),
                "percentile_75": str(sofr_summary.get("percentile_75") or ""),
                "row_count": int(sofr_summary.get("row_count") or 0),
                "quote_semantics": str(sofr_summary.get("quote_semantics") or "reference_only"),
                "rows": [
                    {
                        "date": str(row.get("date") or ""),
                        "rate": str(row.get("rate") or ""),
                        "unit": str(row.get("unit") or "percent"),
                        "volume_in_billions": str(row.get("volume_in_billions") or ""),
                        "percentile_25": str(row.get("percentile_25") or ""),
                        "percentile_75": str(row.get("percentile_75") or ""),
                    }
                    for row in sofr_rows
                    if isinstance(row, dict)
                ],
            },
        },
        "twelve_data_quotes": {
            "state": str(twelve_quote_status.get("state") or "key_required"),
            "source": str(twelve_quote_status.get("source") or "twelve_data_quote"),
            "provider_id": str(
                twelve_quote_status.get("provider_id") or "twelve_data_quote_optional_key"
            ),
            "retrieved_at": str(twelve_quote_status.get("last_update") or "not refreshed"),
            "cache_path": str(
                twelve_quote_status.get("cache_path") or "market_data/quotes/twelve_data/AAPL.json"
            ),
            "docs_url": str(twelve_quote_status.get("docs_url") or ""),
            "message": str(
                twelve_quote_status.get("message")
                or "Store a local Twelve Data key before refreshing multi-asset quotes."
            ),
            "symbol": str(twelve_quote_summary.get("symbol") or "AAPL"),
            "symbols": str(twelve_quote_summary.get("symbols") or "AAPL,SPY,EUR/USD"),
            "price": str(twelve_quote_summary.get("price") or ""),
            "change": str(twelve_quote_summary.get("change") or ""),
            "change_percent": str(twelve_quote_summary.get("change_percent") or ""),
            "latest_trading_day": str(twelve_quote_summary.get("latest_trading_day") or ""),
            "row_count": int(twelve_quote_summary.get("row_count") or 0),
            "requested_count": int(twelve_quote_summary.get("requested_count") or 0),
            "cached_count": int(twelve_quote_summary.get("cached_count") or 0),
            "live_count": int(twelve_quote_summary.get("live_count") or 0),
            "stale_count": int(twelve_quote_summary.get("stale_count") or 0),
            "key_required_count": int(twelve_quote_summary.get("key_required_count") or 0),
            "rows": _twelve_data_quote_rows(twelve_quote_rows),
        },
        "finnhub_quotes": {
            "state": str(finnhub_quote_status.get("state") or "key_required"),
            "source": str(finnhub_quote_status.get("source") or "finnhub_quote"),
            "provider_id": str(
                finnhub_quote_status.get("provider_id") or "finnhub_equity_quote_optional_key"
            ),
            "retrieved_at": str(finnhub_quote_status.get("last_update") or "not refreshed"),
            "cache_path": str(
                finnhub_quote_status.get("cache_path") or "market_data/quotes/finnhub/AAPL.json"
            ),
            "docs_url": str(finnhub_quote_status.get("docs_url") or ""),
            "message": str(
                finnhub_quote_status.get("message")
                or "Store a local Finnhub key before refreshing equity quotes."
            ),
            "symbol": str(finnhub_quote_summary.get("symbol") or "AAPL"),
            "symbols": str(finnhub_quote_summary.get("symbols") or "AAPL,MSFT,NVDA,SPY"),
            "price": str(finnhub_quote_summary.get("price") or ""),
            "change": str(finnhub_quote_summary.get("change") or ""),
            "change_percent": str(finnhub_quote_summary.get("change_percent") or ""),
            "latest_trading_day": str(finnhub_quote_summary.get("latest_trading_day") or ""),
            "row_count": int(finnhub_quote_summary.get("row_count") or 0),
            "requested_count": int(finnhub_quote_summary.get("requested_count") or 0),
            "cached_count": int(finnhub_quote_summary.get("cached_count") or 0),
            "live_count": int(finnhub_quote_summary.get("live_count") or 0),
            "stale_count": int(finnhub_quote_summary.get("stale_count") or 0),
            "key_required_count": int(finnhub_quote_summary.get("key_required_count") or 0),
            "rows": _finnhub_quote_rows(finnhub_quote_rows),
        },
        "fred_macro": {
            "state": str(fred_core.get("state") or "key_required"),
            "provider_id": str(fred_core.get("provider_id") or "fred_optional_local_key"),
            "series_count": int(fred_core.get("series_count") or 0),
            "series": [
                {
                    "series_id": str(row.get("series_id") or ""),
                    "label": str(row.get("label") or ""),
                    "units": str(row.get("units") or ""),
                    "latest_value": str(row.get("latest_value") or ""),
                    "latest_period": str(row.get("latest_period") or ""),
                    "state": str(row.get("state") or ""),
                }
                for row in (
                    fred_core.get("series")
                    if isinstance(fred_core.get("series"), list)
                    else []
                )
                if isinstance(row, dict)
            ],
        },
        "fmp_quotes": {
            "state": str(fmp_quote_status.get("state") or "key_required"),
            "source": str(fmp_quote_status.get("source") or "fmp_stock_quote"),
            "provider_id": str(
                fmp_quote_status.get("provider_id") or "fmp_stock_quote_optional_key"
            ),
            "retrieved_at": str(fmp_quote_status.get("last_update") or "not refreshed"),
            "cache_path": str(
                fmp_quote_status.get("cache_path") or "market_data/quotes/fmp/AAPL.json"
            ),
            "docs_url": str(fmp_quote_status.get("docs_url") or ""),
            "message": str(
                fmp_quote_status.get("message")
                or "Store a local FMP key before refreshing stock quotes."
            ),
            "symbol": str(fmp_quote_summary.get("symbol") or "AAPL"),
            "symbols": str(fmp_quote_summary.get("symbols") or "AAPL,MSFT,NVDA,SPY"),
            "price": str(fmp_quote_summary.get("price") or ""),
            "change": str(fmp_quote_summary.get("change") or ""),
            "change_percent": str(fmp_quote_summary.get("change_percent") or ""),
            "latest_trading_day": str(fmp_quote_summary.get("latest_trading_day") or ""),
            "row_count": int(fmp_quote_summary.get("row_count") or 0),
            "requested_count": int(fmp_quote_summary.get("requested_count") or 0),
            "cached_count": int(fmp_quote_summary.get("cached_count") or 0),
            "live_count": int(fmp_quote_summary.get("live_count") or 0),
            "stale_count": int(fmp_quote_summary.get("stale_count") or 0),
            "key_required_count": int(fmp_quote_summary.get("key_required_count") or 0),
            "rows": _fmp_quote_rows(fmp_quote_rows),
        },
        "stooq_quotes": {
            "state": str(stooq_quote_status.get("state") or "unavailable"),
            "source": str(stooq_quote_status.get("source") or "stooq_current_quote_csv"),
            "provider_id": str(
                stooq_quote_status.get("provider_id") or "stooq_public_quote_snapshot"
            ),
            "retrieved_at": str(stooq_quote_status.get("last_update") or "not refreshed"),
            "cache_path": str(
                stooq_quote_status.get("cache_path") or "market_data/quotes/stooq/AAPLUS.json"
            ),
            "docs_url": str(stooq_quote_status.get("docs_url") or ""),
            "message": str(
                stooq_quote_status.get("message")
                or "Run Stooq public snapshot refresh to populate delayed non-orderable quotes."
            ),
            "symbol": str(stooq_quote_summary.get("symbol") or "AAPL.US"),
            "symbols": str(stooq_quote_summary.get("symbols") or "AAPL.US,SPY.US,^SPX,EURUSD"),
            "price": str(stooq_quote_summary.get("price") or ""),
            "change": str(stooq_quote_summary.get("change") or ""),
            "change_percent": str(stooq_quote_summary.get("change_percent") or ""),
            "latest_date": str(stooq_quote_summary.get("latest_date") or ""),
            "latest_time": str(stooq_quote_summary.get("latest_time") or ""),
            "row_count": int(stooq_quote_summary.get("row_count") or 0),
            "requested_count": int(stooq_quote_summary.get("requested_count") or 0),
            "live_count": int(stooq_quote_summary.get("live_count") or 0),
            "cached_count": int(stooq_quote_summary.get("cached_count") or 0),
            "stale_count": int(stooq_quote_summary.get("stale_count") or 0),
            "unavailable_count": int(stooq_quote_summary.get("unavailable_count") or 0),
            "quote_semantics": str(
                stooq_quote_summary.get("quote_semantics") or "quote_not_orderable"
            ),
            "rows": _stooq_quote_rows(stooq_quote_rows),
        },
        "moex_quotes": {
            "state": str(moex_quote_status.get("state") or "unavailable"),
            "source": str(moex_quote_status.get("source") or "moex_iss_marketdata_delayed"),
            "provider_id": str(
                moex_quote_status.get("provider_id") or "moex_iss_delayed_quote_snapshot"
            ),
            "retrieved_at": str(moex_quote_status.get("last_update") or "not refreshed"),
            "cache_path": str(
                moex_quote_status.get("cache_path") or "market_data/quotes/moex/SBER.json"
            ),
            "docs_url": str(moex_quote_status.get("docs_url") or ""),
            "message": str(
                moex_quote_status.get("message")
                or "Run MOEX ISS delayed quote refresh to populate non-orderable quotes."
            ),
            "symbol": str(moex_quote_summary.get("symbol") or "SBER"),
            "symbols": str(moex_quote_summary.get("symbols") or "SBER,GAZP,MOEX"),
            "price": str(moex_quote_summary.get("price") or ""),
            "change": str(moex_quote_summary.get("change") or ""),
            "change_percent": str(moex_quote_summary.get("change_percent") or ""),
            "latest_time": str(moex_quote_summary.get("latest_time") or ""),
            "row_count": int(moex_quote_summary.get("row_count") or 0),
            "requested_count": int(moex_quote_summary.get("requested_count") or 0),
            "live_count": int(moex_quote_summary.get("live_count") or 0),
            "cached_count": int(moex_quote_summary.get("cached_count") or 0),
            "stale_count": int(moex_quote_summary.get("stale_count") or 0),
            "unavailable_count": int(moex_quote_summary.get("unavailable_count") or 0),
            "quote_semantics": str(
                moex_quote_summary.get("quote_semantics") or "quote_not_orderable"
            ),
            "rows": _moex_quote_rows(moex_quote_rows),
        },
        "twse_quotes": {
            "state": str(twse_quote_status.get("state") or "unavailable"),
            "source": str(twse_quote_status.get("source") or "twse_stock_day_all_openapi"),
            "provider_id": str(
                twse_quote_status.get("provider_id") or "twse_openapi_daily_quote_snapshot"
            ),
            "retrieved_at": str(twse_quote_status.get("last_update") or "not refreshed"),
            "cache_path": str(
                twse_quote_status.get("cache_path") or "market_data/quotes/twse/2330.json"
            ),
            "docs_url": str(twse_quote_status.get("docs_url") or ""),
            "message": str(
                twse_quote_status.get("message")
                or "Run TWSE daily quote refresh to populate non-orderable quotes."
            ),
            "symbol": str(twse_quote_summary.get("symbol") or "2330"),
            "symbols": str(twse_quote_summary.get("symbols") or "2330,2317,0050"),
            "price": str(twse_quote_summary.get("price") or ""),
            "change": str(twse_quote_summary.get("change") or ""),
            "change_percent": str(twse_quote_summary.get("change_percent") or ""),
            "latest_date": str(twse_quote_summary.get("latest_date") or ""),
            "currency": str(twse_quote_summary.get("currency") or "TWD"),
            "row_count": int(twse_quote_summary.get("row_count") or 0),
            "requested_count": int(twse_quote_summary.get("requested_count") or 0),
            "live_count": int(twse_quote_summary.get("live_count") or 0),
            "cached_count": int(twse_quote_summary.get("cached_count") or 0),
            "stale_count": int(twse_quote_summary.get("stale_count") or 0),
            "unavailable_count": int(twse_quote_summary.get("unavailable_count") or 0),
            "quote_semantics": str(
                twse_quote_summary.get("quote_semantics") or "quote_not_orderable"
            ),
            "rows": _twse_quote_rows(twse_quote_rows),
        },
        "nasdaq_symbols": {
            "state": str(nasdaq_symbol_status.get("state") or "unavailable"),
            "source": str(
                nasdaq_symbol_status.get("source") or "nasdaq_trader_symbol_directory"
            ),
            "provider_id": str(
                nasdaq_symbol_status.get("provider_id")
                or "nasdaq_trader_symbol_directory_public"
            ),
            "retrieved_at": str(nasdaq_symbol_status.get("last_update") or "not refreshed"),
            "cache_path": str(
                nasdaq_symbol_status.get("cache_path")
                or "market_data/reference/nasdaq_trader/symbol_directory.json"
            ),
            "docs_url": str(nasdaq_symbol_status.get("docs_url") or ""),
            "message": str(
                nasdaq_symbol_status.get("message")
                or "Run Nasdaq Trader symbol-directory refresh to populate reference rows."
            ),
            "row_count": int(nasdaq_symbol_summary.get("row_count") or 0),
            "nasdaq_listed_count": int(nasdaq_symbol_summary.get("nasdaq_listed_count") or 0),
            "other_listed_count": int(nasdaq_symbol_summary.get("other_listed_count") or 0),
            "etf_count": int(nasdaq_symbol_summary.get("etf_count") or 0),
            "test_issue_count": int(nasdaq_symbol_summary.get("test_issue_count") or 0),
            "quote_semantics": str(nasdaq_symbol_summary.get("quote_semantics") or "not_quote"),
            "rows": _nasdaq_symbol_rows(nasdaq_symbol_rows),
            "search": nasdaq_trader_symbol_search_payload(
                nasdaq_symbols,
                query="AAPL",
                limit=12,
            ),
        },
        "openfigi_mapping": {
            "state": str(openfigi_status.get("state") or "unavailable"),
            "source": str(openfigi_status.get("source") or "openfigi_v3_mapping"),
            "provider_id": str(
                openfigi_status.get("provider_id") or "openfigi_identifier_mapping_public"
            ),
            "retrieved_at": str(openfigi_status.get("last_update") or "not refreshed"),
            "cache_path": str(
                openfigi_status.get("cache_path")
                or "market_data/reference/openfigi/mapping.json"
            ),
            "docs_url": str(openfigi_status.get("docs_url") or ""),
            "message": str(
                openfigi_status.get("message")
                or "Run OpenFIGI mapping refresh to populate identifier reference rows."
            ),
            "row_count": int(openfigi_summary.get("row_count") or 0),
            "requested_count": int(openfigi_summary.get("requested_count") or 0),
            "requested_symbols": str(openfigi_summary.get("requested_symbols") or "AAPL,MSFT,SPY"),
            "matched_symbol_count": int(openfigi_summary.get("matched_symbol_count") or 0),
            "unmatched_count": int(openfigi_summary.get("unmatched_count") or 0),
            "quote_semantics": str(openfigi_summary.get("quote_semantics") or "not_quote"),
            "rows": _openfigi_mapping_rows(openfigi_rows),
        },
        "fx": {
            "state": str(fx_status.get("state") or "unavailable"),
            "source": str(fx_status.get("source") or "ecb_fx_reference"),
            "provider_id": str(fx_status.get("provider_id") or "ecb_fx_reference_public"),
            "retrieved_at": str(fx_status.get("last_update") or "not refreshed"),
            "cache_path": str(fx_status.get("cache_path") or ""),
            "docs_url": str(fx_status.get("docs_url") or ""),
            "date": str(fx_summary.get("date") or ""),
            "row_count": int(fx_summary.get("row_count") or 0),
            "base": str(fx_summary.get("base") or "EUR"),
            "usd": str(fx_summary.get("usd") or ""),
            "gbp": str(fx_summary.get("gbp") or ""),
            "jpy": str(fx_summary.get("jpy") or ""),
            "chf": str(fx_summary.get("chf") or ""),
            "cny": str(fx_summary.get("cny") or ""),
            "h10": {
                "state": str(h10_status.get("state") or "unavailable"),
                "source": str(h10_status.get("source") or "federal_reserve_h10"),
                "provider_id": str(
                    h10_status.get("provider_id") or "federal_reserve_h10_ddp_public"
                ),
                "retrieved_at": str(h10_status.get("last_update") or "not refreshed"),
                "cache_path": str(h10_status.get("cache_path") or ""),
                "docs_url": str(h10_status.get("docs_url") or ""),
                "date": str(h10_summary.get("date") or ""),
                "row_count": int(h10_summary.get("row_count") or 0),
                "base": str(h10_summary.get("base") or "USD reference"),
                "eur": str(h10_summary.get("eur") or ""),
                "gbp": str(h10_summary.get("gbp") or ""),
                "jpy": str(h10_summary.get("jpy") or ""),
                "cad": str(h10_summary.get("cad") or ""),
                "cny": str(h10_summary.get("cny") or ""),
                "rows": [
                    {
                        "pair": str(row.get("pair") or ""),
                        "currency": str(row.get("currency") or ""),
                        "label": str(row.get("label") or ""),
                        "rate": str(row.get("rate") or ""),
                        "date": str(row.get("date") or ""),
                        "rate_basis": str(row.get("rate_basis") or ""),
                        "reference_only": bool(row.get("reference_only", True)),
                    }
                    for row in h10_rows
                    if isinstance(row, dict)
                ],
            },
            "boc": {
                "state": str(boc_status.get("state") or "unavailable"),
                "source": str(boc_status.get("source") or "bank_of_canada_valet"),
                "provider_id": str(
                    boc_status.get("provider_id") or "bank_of_canada_valet_fx_reference_public"
                ),
                "retrieved_at": str(boc_status.get("last_update") or "not refreshed"),
                "cache_path": str(boc_status.get("cache_path") or ""),
                "docs_url": str(boc_status.get("docs_url") or ""),
                "date": str(boc_summary.get("date") or ""),
                "row_count": int(boc_summary.get("row_count") or 0),
                "base": str(boc_summary.get("base") or "CAD reference"),
                "usd": str(boc_summary.get("usd") or ""),
                "eur": str(boc_summary.get("eur") or ""),
                "gbp": str(boc_summary.get("gbp") or ""),
                "jpy": str(boc_summary.get("jpy") or ""),
                "chf": str(boc_summary.get("chf") or ""),
                "quote_semantics": str(boc_summary.get("quote_semantics") or "reference_only"),
                "rows": [
                    {
                        "pair": str(row.get("pair") or ""),
                        "currency": str(row.get("currency") or ""),
                        "series": str(row.get("series") or ""),
                        "rate": str(row.get("rate") or ""),
                        "date": str(row.get("date") or ""),
                        "rate_basis": str(row.get("rate_basis") or ""),
                        "reference_only": bool(row.get("reference_only", True)),
                    }
                    for row in boc_rows
                    if isinstance(row, dict)
                ],
            },
            "quote_watchlist": {
                "state": str(fx_quote_status.get("state") or "key_required"),
                "source": str(fx_quote_status.get("source") or "alphavantage_currency_exchange_rate"),
                "provider_id": str(
                    fx_quote_status.get("provider_id") or "alphavantage_global_quote_optional_key"
                ),
                "retrieved_at": str(fx_quote_status.get("last_update") or "not refreshed"),
                "cache_path": str(
                    fx_quote_status.get("cache_path")
                    or "market_data/fx/alphavantage/currency_exchange/EURUSD.json"
                ),
                "docs_url": str(fx_quote_status.get("docs_url") or ""),
                "message": str(
                    fx_quote_status.get("message")
                    or "Store a local Alpha Vantage key before refreshing FX quotes."
                ),
                "pair": str(fx_quote_summary.get("pair") or "EUR/USD"),
                "pairs": str(fx_quote_summary.get("pairs") or "EUR/USD,USD/JPY,GBP/USD"),
                "rate": str(fx_quote_summary.get("rate") or ""),
                "bid": str(fx_quote_summary.get("bid") or ""),
                "ask": str(fx_quote_summary.get("ask") or ""),
                "last_refreshed": str(fx_quote_summary.get("last_refreshed") or ""),
                "row_count": int(fx_quote_summary.get("row_count") or 0),
                "requested_count": int(fx_quote_summary.get("requested_count") or 0),
                "cached_count": int(fx_quote_summary.get("cached_count") or 0),
                "live_count": int(fx_quote_summary.get("live_count") or 0),
                "stale_count": int(fx_quote_summary.get("stale_count") or 0),
                "key_required_count": int(fx_quote_summary.get("key_required_count") or 0),
                "rows": _fx_quote_rows(fx_quote_rows),
            },
            "rows": [
                {
                    "pair": str(row.get("pair") or ""),
                    "base": str(row.get("base") or "EUR"),
                    "quote": str(row.get("quote") or ""),
                    "rate": str(row.get("rate") or ""),
                    "date": str(row.get("date") or ""),
                }
                for row in fx_rows
                if isinstance(row, dict)
            ],
        },
        "commodities": {
            "state": str(commodity_status.get("state") or "unavailable"),
            "source": str(commodity_status.get("source") or "world_bank_pink_sheet"),
            "provider_id": str(
                commodity_status.get("provider_id") or "world_bank_commodity_monthly_public"
            ),
            "retrieved_at": str(commodity_status.get("last_update") or "not refreshed"),
            "cache_path": str(commodity_status.get("cache_path") or ""),
            "docs_url": str(commodity_status.get("docs_url") or ""),
            "period": str(commodity_summary.get("period") or ""),
            "updated_on": str(commodity_summary.get("updated_on") or ""),
            "row_count": int(commodity_summary.get("row_count") or 0),
            "crude_wti": str(commodity_summary.get("crude_wti") or ""),
            "crude_brent": str(commodity_summary.get("crude_brent") or ""),
            "ngas_us": str(commodity_summary.get("ngas_us") or ""),
            "gold": str(commodity_summary.get("gold") or ""),
            "copper": str(commodity_summary.get("copper") or ""),
            "wheat_us_srw": str(commodity_summary.get("wheat_us_srw") or ""),
            "rows": [
                {
                    "code": str(row.get("code") or ""),
                    "name": str(row.get("name") or ""),
                    "unit": str(row.get("unit") or ""),
                    "value": str(row.get("value") or ""),
                    "period": str(row.get("period") or ""),
                }
                for row in commodity_rows
                if isinstance(row, dict)
            ],
            "cftc": {
                "state": str(cftc_status.get("state") or "unavailable"),
                "source": str(cftc_status.get("source") or "cftc_cot_legacy_futures_only"),
                "provider_id": str(cftc_status.get("provider_id") or "cftc_cot_legacy_public"),
                "retrieved_at": str(cftc_status.get("last_update") or "not refreshed"),
                "cache_path": str(cftc_status.get("cache_path") or ""),
                "docs_url": str(cftc_status.get("docs_url") or ""),
                "message": str(
                    cftc_status.get("message")
                    or "Run COT to fetch public CFTC weekly positioning context."
                ),
                "row_count": int(cftc_summary.get("row_count") or len(cftc_rows)),
                "report_date": str(cftc_summary.get("report_date") or ""),
                "contracts": str(cftc_summary.get("contracts") or ""),
                "gold_noncommercial_net": str(
                    cftc_summary.get("gold_noncommercial_net") or ""
                ),
                "wti_crude_noncommercial_net": str(
                    cftc_summary.get("wti_crude_noncommercial_net") or ""
                ),
                "copper_noncommercial_net": str(
                    cftc_summary.get("copper_noncommercial_net") or ""
                ),
                "wheat_srw_noncommercial_net": str(
                    cftc_summary.get("wheat_srw_noncommercial_net") or ""
                ),
                "rows": [
                    {
                        "contract": str(row.get("contract") or ""),
                        "market_and_exchange_names": str(
                            row.get("market_and_exchange_names") or ""
                        ),
                        "report_date": str(row.get("report_date") or ""),
                        "open_interest": str(row.get("open_interest") or ""),
                        "noncommercial_long": str(row.get("noncommercial_long") or ""),
                        "noncommercial_short": str(row.get("noncommercial_short") or ""),
                        "noncommercial_net": str(row.get("noncommercial_net") or ""),
                        "commercial_net": str(row.get("commercial_net") or ""),
                    }
                    for row in cftc_rows
                    if isinstance(row, dict)
                ],
            },
            "energy": {
                "state": str(eia_status.get("state") or "key_required"),
                "source": str(eia_status.get("source") or "eia_open_data_api"),
                "provider_id": str(eia_status.get("provider_id") or "eia_open_data_optional_key"),
                "retrieved_at": str(eia_status.get("last_update") or "not refreshed"),
                "cache_path": str(eia_status.get("cache_path") or ""),
                "docs_url": str(eia_status.get("docs_url") or ""),
                "message": str(
                    eia_status.get("message")
                    or "Store a local EIA Open Data key before refreshing energy context."
                ),
                "series_count": int(eia_summary.get("series_count") or len(eia_series)),
                "latest_period": str(eia_summary.get("latest_period") or ""),
                "wti_spot": str(eia_summary.get("wti_spot") or ""),
                "brent_spot": str(eia_summary.get("brent_spot") or ""),
                "henry_hub": str(eia_summary.get("henry_hub") or ""),
                "series": [
                    {
                        "series_id": str(row.get("series_id") or ""),
                        "label": str(row.get("label") or row.get("series_id") or ""),
                        "period": str(row.get("period") or ""),
                        "value": str(row.get("value") or ""),
                        "unit": str(row.get("unit") or ""),
                        "frequency": str(row.get("frequency") or ""),
                    }
                    for row in eia_series
                    if isinstance(row, dict)
                ],
            },
        },
        "news": {
            "state": "cache_ready" if news_items else "cache_missing",
            "source": "public_rss",
            "retrieved_at": str(news_cache.get("fetched_at") if isinstance(news_cache, dict) else ""),
            "item_count": len(news_items),
            "source_count": len(
                {
                    str(item.get("source") or "")
                    for item in news_items
                    if isinstance(item, dict)
                }
            ),
        },
    }


def _source_coverage_matrix(
    research_summary: dict[str, Any],
    *,
    crypto_status: dict[str, Any] | None = None,
    crypto_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    fundamentals = _summary_section(research_summary, "fundamentals")
    sec_frames = _summary_section(research_summary, "sec_frames")
    equity_registry = _summary_section(research_summary, "equity_registry")
    filings = _summary_section(research_summary, "filings")
    equity_quotes = _summary_section(research_summary, "equity_quotes")
    funds = _summary_section(research_summary, "funds")
    etf_quotes = _summary_section(research_summary, "etf_quotes")
    macro = _summary_section(research_summary, "macro")
    rates = _summary_section(research_summary, "rates")
    fx = _summary_section(research_summary, "fx")
    fx_quote_watchlist = (
        fx.get("quote_watchlist") if isinstance(fx.get("quote_watchlist"), dict) else {}
    )
    boc_fx = fx.get("boc") if isinstance(fx.get("boc"), dict) else {}
    twelve_data_quotes = _summary_section(research_summary, "twelve_data_quotes")
    finnhub_quotes = _summary_section(research_summary, "finnhub_quotes")
    fmp_quotes = _summary_section(research_summary, "fmp_quotes")
    moex_quotes = _summary_section(research_summary, "moex_quotes")
    twse_quotes = _summary_section(research_summary, "twse_quotes")
    nasdaq_symbols = _summary_section(research_summary, "nasdaq_symbols")
    openfigi_mapping = _summary_section(research_summary, "openfigi_mapping")
    commodities = _summary_section(research_summary, "commodities")
    energy = commodities.get("energy") if isinstance(commodities.get("energy"), dict) else {}
    cftc_cot = commodities.get("cftc") if isinstance(commodities.get("cftc"), dict) else {}

    macro_provider_id = str(macro.get("provider_id") or "bls_public_macro")
    if "/" in macro_provider_id:
        macro_provider_id = str(macro.get("primary_provider") or "bls_public_macro")
    macro_auth_mode = "public_no_key"
    if macro_provider_id in {
        "fred_optional_local_key",
        "bea_regional_optional_key",
        "census_api_optional_key",
    }:
        macro_auth_mode = "optional_local_key"
    if macro_provider_id == "fred_optional_local_key":
        macro_safe_action_id = "markets_fred_refresh"
    elif macro_provider_id == "bea_regional_optional_key":
        macro_safe_action_id = "markets_bea_refresh"
    elif macro_provider_id == "census_api_optional_key":
        macro_safe_action_id = "markets_census_refresh"
    else:
        macro_safe_action_id = "markets_macro_refresh"

    return [
        _coverage_row(
            asset_family="Stocks",
            runtime_role="quote_watchlist",
            provider_id="alphavantage_global_quote_optional_key",
            auth_mode="optional_local_key",
            section=equity_quotes,
            row_count=equity_quotes.get("row_count"),
            quote_semantics="quote_not_orderable",
            safe_action_id="markets_stocks_quote_watchlist_refresh",
        ),
        _coverage_row(
            asset_family="Stocks",
            runtime_role="issuer_reference",
            provider_id="sec_company_ticker_registry_public",
            auth_mode="public_no_key",
            section=equity_registry,
            row_count=equity_registry.get("row_count"),
            quote_semantics="reference_only",
            safe_action_id="markets_stocks_refresh",
        ),
        _coverage_row(
            asset_family="Stocks",
            runtime_role="symbol_directory",
            provider_id="nasdaq_trader_symbol_directory_public",
            auth_mode="public_no_key",
            section=nasdaq_symbols,
            row_count=nasdaq_symbols.get("row_count"),
            quote_semantics="not_quote",
            safe_action_id="markets_nasdaq_symbol_directory_refresh",
        ),
        _coverage_row(
            asset_family="Stocks",
            runtime_role="identifier_mapping",
            provider_id="openfigi_identifier_mapping_public",
            auth_mode="public_no_key",
            section=openfigi_mapping,
            row_count=openfigi_mapping.get("row_count"),
            quote_semantics="not_quote",
            safe_action_id="markets_openfigi_mapping_refresh",
        ),
        _coverage_row(
            asset_family="Stocks",
            runtime_role="filing_metadata",
            provider_id="sec_company_submissions_public",
            auth_mode="public_no_key",
            section=filings,
            row_count=filings.get("row_count"),
            quote_semantics="not_quote",
            safe_action_id="markets_stocks_refresh",
        ),
        _coverage_row(
            asset_family="Stocks",
            runtime_role="fundamentals",
            provider_id="sec_edgar_public",
            auth_mode="public_no_key",
            section=fundamentals,
            row_count=fundamentals.get("fact_count"),
            quote_semantics="not_quote",
            safe_action_id="markets_stocks_refresh",
        ),
        _coverage_row(
            asset_family="Stocks",
            runtime_role="fundamental_frames",
            provider_id="sec_xbrl_frames_public",
            auth_mode="public_no_key",
            section=sec_frames,
            row_count=sec_frames.get("row_count"),
            quote_semantics="not_quote",
            safe_action_id="markets_stocks_refresh",
        ),
        _coverage_row(
            asset_family="ETF",
            runtime_role="fund_registry",
            provider_id="sec_fund_ticker_registry_public",
            auth_mode="public_no_key",
            section=funds,
            row_count=funds.get("row_count"),
            quote_semantics="reference_only",
            safe_action_id="markets_etf_refresh",
        ),
        _coverage_row(
            asset_family="ETF",
            runtime_role="quote_watchlist",
            provider_id="alphavantage_global_quote_optional_key",
            auth_mode="optional_local_key",
            section=etf_quotes,
            row_count=etf_quotes.get("row_count"),
            quote_semantics="quote_not_orderable",
            safe_action_id="markets_etf_quote_watchlist_refresh",
        ),
        _coverage_row(
            asset_family="FX",
            runtime_role="eur_reference_rates",
            provider_id="ecb_fx_reference_public",
            auth_mode="public_no_key",
            section=fx,
            row_count=fx.get("row_count"),
            quote_semantics="reference_only",
            safe_action_id="markets_fx_refresh",
        ),
        _coverage_row(
            asset_family="FX",
            runtime_role="usd_reference_rates",
            provider_id="federal_reserve_h10_ddp_public",
            auth_mode="public_no_key",
            section=fx.get("h10") if isinstance(fx.get("h10"), dict) else {},
            row_count=(
                fx.get("h10", {}).get("row_count")
                if isinstance(fx.get("h10"), dict)
                else 0
            ),
            quote_semantics="reference_only",
            safe_action_id="markets_fx_refresh",
        ),
        _coverage_row(
            asset_family="FX",
            runtime_role="cad_reference_rates",
            provider_id="bank_of_canada_valet_fx_reference_public",
            auth_mode="public_no_key",
            section=boc_fx,
            row_count=boc_fx.get("row_count"),
            quote_semantics="reference_only",
            safe_action_id="markets_fx_refresh",
        ),
        _coverage_row(
            asset_family="FX",
            runtime_role="quote_watchlist",
            provider_id="alphavantage_global_quote_optional_key",
            auth_mode="optional_local_key",
            section=fx_quote_watchlist,
            row_count=fx_quote_watchlist.get("row_count"),
            quote_semantics="quote_not_orderable",
            safe_action_id="markets_fx_quote_watchlist_refresh",
        ),
        _coverage_row(
            asset_family="Multi-Asset",
            runtime_role="quote_watchlist_secondary",
            provider_id="twelve_data_quote_optional_key",
            auth_mode="optional_local_key",
            section=twelve_data_quotes,
            row_count=twelve_data_quotes.get("row_count"),
            quote_semantics="quote_not_orderable",
            safe_action_id="markets_twelve_data_quote_watchlist_refresh",
        ),
        _coverage_row(
            asset_family="Stocks",
            runtime_role="equity_quote_watchlist_secondary",
            provider_id="finnhub_equity_quote_optional_key",
            auth_mode="optional_local_key",
            section=finnhub_quotes,
            row_count=finnhub_quotes.get("row_count"),
            quote_semantics="quote_not_orderable",
            safe_action_id="markets_finnhub_quote_watchlist_refresh",
        ),
        _coverage_row(
            asset_family="Stocks",
            runtime_role="stock_quote_watchlist_tertiary",
            provider_id="fmp_stock_quote_optional_key",
            auth_mode="optional_local_key",
            section=fmp_quotes,
            row_count=fmp_quotes.get("row_count"),
            quote_semantics="quote_not_orderable",
            safe_action_id="markets_fmp_quote_watchlist_refresh",
        ),
        _coverage_row(
            asset_family="Multi-Asset",
            runtime_role="international_delayed_quote_snapshot",
            provider_id="moex_iss_delayed_quote_snapshot",
            auth_mode="public_no_key",
            section=moex_quotes,
            row_count=moex_quotes.get("row_count"),
            quote_semantics="quote_not_orderable",
            safe_action_id="markets_moex_quote_snapshot_refresh",
        ),
        _coverage_row(
            asset_family="Stocks",
            runtime_role="twse_daily_quote_snapshot",
            provider_id="twse_openapi_daily_quote_snapshot",
            auth_mode="public_no_key",
            section=twse_quotes,
            row_count=twse_quotes.get("row_count"),
            quote_semantics="quote_not_orderable",
            safe_action_id="markets_twse_quote_snapshot_refresh",
        ),
        _coverage_row(
            asset_family="Commodities",
            runtime_role="monthly_reference_prices",
            provider_id="world_bank_commodity_monthly_public",
            auth_mode="public_no_key",
            section=commodities,
            row_count=commodities.get("row_count"),
            quote_semantics="reference_only",
            safe_action_id="markets_commodities_refresh",
        ),
        _coverage_row(
            asset_family="Commodities",
            runtime_role="positioning_context",
            provider_id="cftc_cot_legacy_public",
            auth_mode="public_no_key",
            section=cftc_cot,
            row_count=cftc_cot.get("row_count") if isinstance(cftc_cot, dict) else 0,
            quote_semantics="not_quote",
            safe_action_id="markets_cftc_cot_refresh",
        ),
        _coverage_row(
            asset_family="Commodities",
            runtime_role="energy_context",
            provider_id="eia_open_data_optional_key",
            auth_mode="optional_local_key",
            section=energy if isinstance(energy, dict) else {},
            row_count=energy.get("series_count") if isinstance(energy, dict) else 0,
            quote_semantics="not_quote",
            safe_action_id="markets_eia_refresh",
        ),
        _coverage_row(
            asset_family="Indexes",
            runtime_role="macro_context",
            provider_id=macro_provider_id,
            auth_mode=macro_auth_mode,
            section=macro,
            row_count=macro.get("series_count"),
            quote_semantics="not_quote",
            safe_action_id=macro_safe_action_id,
        ),
        _coverage_row(
            asset_family="Regional",
            runtime_role="macro_context",
            provider_id=macro_provider_id,
            auth_mode=macro_auth_mode,
            section=macro,
            row_count=macro.get("series_count"),
            quote_semantics="not_quote",
            safe_action_id=macro_safe_action_id,
        ),
        _coverage_row(
            asset_family="Bonds/Rates",
            runtime_role="yield_curve",
            provider_id="us_treasury_yield_public",
            auth_mode="public_no_key",
            section=rates,
            row_count=rates.get("tenor_count"),
            quote_semantics="reference_only",
            safe_action_id="markets_rates_refresh",
        ),
        _coverage_row(
            asset_family="Bonds/Rates",
            runtime_role="overnight_reference_rate",
            provider_id="nyfed_sofr_public",
            auth_mode="public_no_key",
            section=rates.get("sofr") if isinstance(rates.get("sofr"), dict) else {},
            row_count=(
                rates.get("sofr", {}).get("row_count")
                if isinstance(rates.get("sofr"), dict)
                else 0
            ),
            quote_semantics="reference_only",
            safe_action_id="markets_rates_refresh",
        ),
        # The crypto ticker lane that scans/backtests actually run on — kept
        # last so consumers that default to the first row keep their behavior.
        _coverage_row(
            asset_family="Crypto",
            runtime_role="quote_watchlist",
            provider_id="binance_spot_public",
            auth_mode="public_no_key",
            section={
                "provider_id": str((crypto_status or {}).get("provider_id") or "binance_spot_public"),
                "state": str((crypto_status or {}).get("state") or "unavailable"),
                "cache_path": str(
                    (crypto_status or {}).get("cache_path") or "market_data/crypto_latest.json"
                ),
                "retrieved_at": str((crypto_status or {}).get("last_update") or "not refreshed"),
            },
            row_count=len(
                [
                    row
                    for row in (crypto_rows or [])
                    if str(row.get("state")) in {"live", "stale"}
                ]
            ),
            quote_semantics="quote_not_orderable",
            safe_action_id="markets_refresh_public",
        ),
    ]


def quote_reference_coverage_payload(
    source_coverage_matrix: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return AI-agent-readable quote/reference coverage without provider calls."""

    rows = [row for row in source_coverage_matrix if isinstance(row, dict)]
    quote_lanes = [
        _coverage_supervision_lane(row)
        for row in rows
        if str(row.get("quote_semantics") or "") == "quote_not_orderable"
    ]
    reference_lanes = [
        _coverage_supervision_lane(row)
        for row in rows
        if str(row.get("quote_semantics") or "") == "reference_only"
    ]
    context_lanes = [
        _coverage_supervision_lane(row)
        for row in rows
        if str(row.get("quote_semantics") or "") == "not_quote"
    ]
    ready_quote_lanes = [row for row in quote_lanes if row["row_count"] > 0]
    gated_quote_lanes = [row for row in quote_lanes if row["gated_reason"]]
    return {
        "generated_at": _utc_now(),
        "mode": "read_only_markets_quote_reference_coverage",
        "summary": {
            "source_row_count": len(rows),
            "quote_lane_count": len(quote_lanes),
            "quote_ready_count": len(ready_quote_lanes),
            "quote_gated_count": len(gated_quote_lanes),
            "public_quote_lane_count": len(
                [row for row in quote_lanes if row["auth_mode"] == "public_no_key"]
            ),
            "optional_quote_lane_count": len(
                [row for row in quote_lanes if row["auth_mode"] == "optional_local_key"]
            ),
            "reference_lane_count": len(reference_lanes),
            "context_lane_count": len(context_lanes),
            "quote_rows_cached": sum(row["row_count"] for row in quote_lanes),
            "reference_rows_cached": sum(row["row_count"] for row in reference_lanes),
            "executable_quote_lane_count": 0,
            "orderable_lane_count": 0,
            "live_action_enabled_count": len(
                [row for row in rows if bool(row.get("live_action_enabled"))]
            ),
            "coverage_status": "partial_non_orderable_quotes",
        },
        "quote_lanes": quote_lanes,
        "reference_lanes": reference_lanes,
        "context_lanes": context_lanes,
        "snapshot_board": _quote_snapshot_board_payload(
            quote_lanes,
            reference_lanes=reference_lanes,
            context_lanes=context_lanes,
        ),
        "recommended_actions": _quote_reference_recommended_actions(quote_lanes),
        "safety": {
            "read_only": True,
            "uses_existing_source_coverage_matrix": True,
            "external_provider_calls": False,
            "writes_local_artifacts": False,
            "requires_secret": False,
            "secret_values": False,
            "orderable_quotes": False,
            "executable_quotes": False,
            "live_orders": False,
            "broker_routing": False,
            "real_balance": False,
            "margin": False,
            "leverage": False,
            "short": False,
            "derivatives": False,
        },
    }


def quote_snapshot_board_payload(
    source_coverage_matrix: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = [row for row in source_coverage_matrix if isinstance(row, dict)]
    quote_lanes = [
        _coverage_supervision_lane(row)
        for row in rows
        if str(row.get("quote_semantics") or "") == "quote_not_orderable"
    ]
    reference_lanes = [
        _coverage_supervision_lane(row)
        for row in rows
        if str(row.get("quote_semantics") or "") == "reference_only"
    ]
    context_lanes = [
        _coverage_supervision_lane(row)
        for row in rows
        if str(row.get("quote_semantics") or "") == "not_quote"
    ]
    return _quote_snapshot_board_payload(
        quote_lanes,
        reference_lanes=reference_lanes,
        context_lanes=context_lanes,
    )


def _quote_snapshot_board_payload(
    quote_lanes: list[dict[str, Any]],
    *,
    reference_lanes: list[dict[str, Any]],
    context_lanes: list[dict[str, Any]],
) -> dict[str, Any]:
    snapshot_rows = [
        _quote_snapshot_board_row(lane)
        for lane in sorted(quote_lanes, key=_quote_snapshot_sort_key)
    ]
    ready_rows = [row for row in snapshot_rows if row["row_count"] > 0]
    gated_rows = [row for row in snapshot_rows if row["requires_local_secret"]]
    refreshable_public_rows = [
        row
        for row in snapshot_rows
        if row["auth_mode"] == "public_no_key" and not row["requires_local_secret"]
    ]
    return {
        "generated_at": _utc_now(),
        "mode": "read_only_markets_quote_snapshot_board",
        "summary": {
            "snapshot_lane_count": len(snapshot_rows),
            "ready_snapshot_count": len(ready_rows),
            "public_snapshot_lane_count": len(
                [row for row in snapshot_rows if row["auth_mode"] == "public_no_key"]
            ),
            "optional_snapshot_lane_count": len(
                [
                    row
                    for row in snapshot_rows
                    if row["auth_mode"] == "optional_local_key"
                ]
            ),
            "key_required_snapshot_count": len(gated_rows),
            "refreshable_public_snapshot_count": len(refreshable_public_rows),
            "reference_lane_excluded_count": len(reference_lanes),
            "context_lane_excluded_count": len(context_lanes),
            "non_orderable_snapshot_count": len(snapshot_rows),
            "orderable_snapshot_count": 0,
            "executable_snapshot_count": 0,
            "coverage_status": "partial_non_orderable_quote_snapshots",
        },
        "rows": snapshot_rows,
        "safety": {
            "read_only": True,
            "uses_existing_source_coverage_matrix": True,
            "external_provider_calls": False,
            "writes_local_artifacts": False,
            "requires_secret_value": False,
            "secret_values": False,
            "orderable_quotes": False,
            "executable_quotes": False,
            "live_orders": False,
            "broker_routing": False,
            "real_balance": False,
            "margin": False,
            "leverage": False,
            "short": False,
            "derivatives": False,
        },
    }


def _quote_snapshot_sort_key(row: dict[str, Any]) -> tuple[int, str, str, str]:
    row_count = _coverage_int(row.get("row_count"))
    auth_mode = str(row.get("auth_mode") or "")
    gated_reason = str(row.get("gated_reason") or "")
    if row_count > 0:
        rank = 0
    elif auth_mode == "public_no_key" and not gated_reason:
        rank = 1
    elif auth_mode == "optional_local_key":
        rank = 2
    else:
        rank = 3
    return (
        rank,
        str(row.get("asset_family") or ""),
        str(row.get("runtime_role") or ""),
        str(row.get("provider_id") or ""),
    )


def _quote_snapshot_board_row(lane: dict[str, Any]) -> dict[str, Any]:
    action_id = str(lane.get("safe_action_id") or "")
    row_count = _coverage_int(lane.get("row_count"))
    auth_mode = str(lane.get("auth_mode") or "")
    gated_reason = str(lane.get("gated_reason") or "")
    requires_local_secret = auth_mode == "optional_local_key" and row_count <= 0
    if row_count > 0:
        supervision_state = "snapshot_cached"
    elif requires_local_secret:
        supervision_state = "local_secret_required"
    elif auth_mode == "public_no_key" and not gated_reason:
        supervision_state = "public_refresh_available"
    else:
        supervision_state = "unavailable"
    return {
        "board_row_id": f"{lane.get('markets_source_row_id')}:quote_snapshot",
        "asset_family": str(lane.get("asset_family") or ""),
        "runtime_role": str(lane.get("runtime_role") or ""),
        "provider_id": str(lane.get("provider_id") or ""),
        "auth_mode": auth_mode,
        "state": str(lane.get("state") or ""),
        "readiness": str(lane.get("readiness") or ""),
        "supervision_state": supervision_state,
        "row_count": row_count,
        "quote_semantics": str(lane.get("quote_semantics") or ""),
        "requires_local_secret": requires_local_secret,
        "gated_reason": gated_reason,
        "cache_path": str(lane.get("cache_path") or ""),
        "retrieved_at": str(lane.get("retrieved_at") or ""),
        "safe_action_id": action_id,
        "preflight_endpoint": (
            f"/api/agent-actions/{action_id}/preflight" if action_id else ""
        ),
        "next_safe_action": str(lane.get("next_safe_action") or ""),
        "orderable": False,
        "executable": False,
        "live_action_enabled": False,
        "markets_source_row_id": str(lane.get("markets_source_row_id") or ""),
    }


def _coverage_supervision_lane(row: dict[str, Any]) -> dict[str, Any]:
    row_count = _coverage_int(row.get("row_count"))
    gated_reason = str(row.get("gated_reason") or "")
    quote_semantics = str(row.get("quote_semantics") or "")
    return {
        "asset_family": str(row.get("asset_family") or ""),
        "runtime_role": str(row.get("runtime_role") or ""),
        "provider_id": str(row.get("provider_id") or ""),
        "auth_mode": str(row.get("auth_mode") or ""),
        "state": str(row.get("state") or "unavailable"),
        "row_count": row_count,
        "quote_semantics": quote_semantics,
        "readiness": _quote_reference_readiness(
            quote_semantics,
            row_count=row_count,
            gated_reason=gated_reason,
        ),
        "gated_reason": gated_reason,
        "safe_action_id": str(row.get("safe_action_id") or ""),
        "next_safe_action": str(row.get("next_safe_action") or ""),
        "cache_path": str(row.get("cache_path") or ""),
        "retrieved_at": str(row.get("retrieved_at") or ""),
        "markets_source_row_id": str(row.get("markets_source_row_id") or ""),
    }


def _quote_reference_readiness(
    quote_semantics: str,
    *,
    row_count: int,
    gated_reason: str,
) -> str:
    if quote_semantics == "quote_not_orderable":
        if row_count > 0:
            return "cached_non_orderable_quote"
        if gated_reason:
            return f"gated_{gated_reason}"
        return "quote_refresh_available"
    if quote_semantics == "reference_only":
        return "cached_reference" if row_count > 0 else "reference_refresh_available"
    return "context_available" if row_count > 0 else "context_not_populated"


def _quote_reference_recommended_actions(
    quote_lanes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for lane in quote_lanes:
        action_id = str(lane.get("safe_action_id") or "")
        if not action_id or action_id in seen:
            continue
        seen.add(action_id)
        actions.append(
            {
                "action_id": action_id,
                "ready": lane["auth_mode"] == "public_no_key" or lane["row_count"] > 0,
                "reason": lane["next_safe_action"] or "Inspect the source coverage matrix.",
                "requires_local_secret": lane["auth_mode"] == "optional_local_key"
                and lane["row_count"] <= 0,
            }
        )
    return actions


def _summary_section(research_summary: dict[str, Any], key: str) -> dict[str, Any]:
    section = research_summary.get(key)
    return section if isinstance(section, dict) else {}


def _coverage_row(
    *,
    asset_family: str,
    runtime_role: str,
    provider_id: str,
    auth_mode: str,
    section: dict[str, Any],
    row_count: Any,
    quote_semantics: str,
    safe_action_id: str,
) -> dict[str, Any]:
    resolved_provider_id = str(section.get("provider_id") or provider_id)
    if "/" in resolved_provider_id and provider_id in SOURCE_COVERAGE_TTL_SECONDS:
        resolved_provider_id = provider_id
    state = str(section.get("state") or "unavailable")
    resolved_row_count = _coverage_int(row_count)
    gated_reason = _coverage_gated_reason(state, auth_mode, resolved_row_count)
    row = {
        "asset_family": asset_family,
        "runtime_role": runtime_role,
        "provider_id": resolved_provider_id,
        "auth_mode": auth_mode,
        "state": state,
        "cache_path": str(
            section.get("cache_path")
            or SOURCE_COVERAGE_CACHE_PATHS.get(resolved_provider_id)
            or SOURCE_COVERAGE_CACHE_PATHS.get(provider_id)
            or ""
        ),
        "retrieved_at": str(section.get("retrieved_at") or "not refreshed"),
        "row_count": resolved_row_count,
        "freshness_ttl_seconds": int(
            SOURCE_COVERAGE_TTL_SECONDS.get(
                resolved_provider_id,
                SOURCE_COVERAGE_TTL_SECONDS.get(provider_id, 0),
            )
        ),
        "docs_url": str(
            section.get("docs_url")
            or SOURCE_COVERAGE_DOCS_URLS.get(resolved_provider_id)
            or SOURCE_COVERAGE_DOCS_URLS.get(provider_id)
            or ""
        ),
        "quote_semantics": quote_semantics,
        "gated_reason": gated_reason,
        "safe_action_id": safe_action_id,
        "next_safe_action": _coverage_next_safe_action(
            gated_reason,
            auth_mode=auth_mode,
            safe_action_id=safe_action_id,
        ),
    }
    return enrich_source_coverage_row(row)


def _coverage_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _coverage_gated_reason(state: str, auth_mode: str, row_count: int) -> str:
    normalized = state.lower()
    if auth_mode == "optional_local_key" and normalized in {
        "key_required",
        "provider_key_unavailable",
        "secret_storage_unavailable",
    }:
        return "local_secret_required"
    if normalized == "rate_limited":
        return "provider_rate_limited"
    if "provider_gate" in normalized or normalized == "plan_required":
        return "provider_gate_not_enabled"
    if row_count <= 0 and normalized in {"unavailable", "cache_missing", "not_refreshed"}:
        return "refresh_not_run"
    return ""


def _coverage_next_safe_action(
    gated_reason: str,
    *,
    auth_mode: str,
    safe_action_id: str,
) -> str:
    if gated_reason == "local_secret_required":
        return (
            "Use the reviewed local provider-key gate in Settings, then run "
            f"{safe_action_id}."
        )
    if gated_reason == "refresh_not_run" and auth_mode == "public_no_key":
        return f"Run {safe_action_id} to populate the public no-key cache."
    if gated_reason == "provider_rate_limited":
        return f"Retry {safe_action_id} after provider cooldown; reuse local cache meanwhile."
    if gated_reason == "provider_gate_not_enabled":
        return "Leave disabled until a dedicated provider-entry plan enables this lane."
    return f"Run {safe_action_id} to refresh or inspect the existing local cache."


def _stock_status_lanes(
    fundamentals: dict[str, Any],
    sec_frames: dict[str, Any],
    equity_registry: dict[str, Any],
    filings: dict[str, Any],
    equity_quotes: dict[str, Any],
    nasdaq_symbols: dict[str, Any],
) -> list[dict[str, Any]]:
    quote_state = str(equity_quotes.get("state") or "key_required")
    quote_count = int(equity_quotes.get("row_count") or 0)
    symbol_count = int(nasdaq_symbols.get("row_count") or 0)
    symbol_search = (
        nasdaq_symbols.get("search") if isinstance(nasdaq_symbols.get("search"), dict) else {}
    )
    registry_count = int(equity_registry.get("row_count") or 0)
    filing_count = int(filings.get("row_count") or 0)
    filing_symbols = str(filings.get("filing_symbols") or filings.get("symbols") or "AAPL")
    company_count = int(fundamentals.get("company_count") or 0)
    fact_count = int(fundamentals.get("fact_count") or 0)
    frame_count = int(sec_frames.get("row_count") or 0)
    frame_tag = str(sec_frames.get("tag") or "Assets")
    frame_period = str(sec_frames.get("period") or "CY2023Q4I")
    latest_form = str(filings.get("latest_form") or "N/A")
    latest_filing_date = str(filings.get("latest_filing_date") or "")
    quote_symbols = str(equity_quotes.get("symbols") or equity_quotes.get("symbol") or "AAPL")
    return [
        {
            "lane_id": "quotes",
            "label": "Quote Watchlist",
            "runtime_role": "optional_local_key_quotes",
            "provider_id": str(
                equity_quotes.get("provider_id") or "alphavantage_global_quote_optional_key"
            ),
            "source": str(equity_quotes.get("source") or "alphavantage_global_quote"),
            "state": quote_state,
            "retrieved_at": str(equity_quotes.get("retrieved_at") or "not refreshed"),
            "cache_path": str(equity_quotes.get("cache_path") or ""),
            "docs_url": str(equity_quotes.get("docs_url") or ""),
            "row_count": quote_count,
            "available": quote_count > 0,
            "gated": quote_count == 0 and quote_state == "key_required",
            "action_id": "markets_stocks_quote_watchlist_refresh",
            "summary": (
                f"{quote_count}/{int(equity_quotes.get('requested_count') or 0)} cached "
                f"for {quote_symbols}"
            ),
            "message": str(
                equity_quotes.get("message")
                or "Store a local Alpha Vantage key before refreshing equity quotes."
            ),
        },
        {
            "lane_id": "symbol_directory",
            "label": "Symbol Directory",
            "runtime_role": "public_symbol_reference",
            "provider_id": str(
                nasdaq_symbols.get("provider_id") or "nasdaq_trader_symbol_directory_public"
            ),
            "source": str(nasdaq_symbols.get("source") or "nasdaq_trader_symbol_directory"),
            "state": str(nasdaq_symbols.get("state") or "unavailable"),
            "retrieved_at": str(nasdaq_symbols.get("retrieved_at") or "not refreshed"),
            "cache_path": str(nasdaq_symbols.get("cache_path") or ""),
            "docs_url": str(nasdaq_symbols.get("docs_url") or ""),
            "row_count": symbol_count,
            "available": symbol_count > 0,
            "gated": False,
            "action_id": "markets_nasdaq_symbol_directory_search",
            "summary": (
                f"{symbol_count} reference rows / "
                f"{int(symbol_search.get('total_matches') or 0)} matches for "
                f"{symbol_search.get('query') or 'AAPL'}"
            ),
            "message": (
                "Public Nasdaq Trader symbol-directory reference rows; "
                "not quotes or orderable instruments."
            ),
        },
        {
            "lane_id": "registry",
            "label": "Company Registry",
            "runtime_role": "public_issuer_reference",
            "provider_id": str(
                equity_registry.get("provider_id") or "sec_company_ticker_registry_public"
            ),
            "source": str(equity_registry.get("source") or "sec_company_ticker_registry"),
            "state": str(equity_registry.get("state") or "unavailable"),
            "retrieved_at": str(equity_registry.get("retrieved_at") or "not refreshed"),
            "cache_path": str(equity_registry.get("cache_path") or ""),
            "docs_url": str(equity_registry.get("docs_url") or ""),
            "row_count": registry_count,
            "available": registry_count > 0,
            "gated": False,
            "action_id": "markets_stocks_refresh",
            "summary": (
                f"{registry_count}/{int(equity_registry.get('registry_total') or 0)} "
                "issuer rows"
            ),
            "message": "Public SEC company ticker registry; reference-only issuer mapping.",
        },
        {
            "lane_id": "filings",
            "label": "Recent Filings",
            "runtime_role": "public_filing_metadata",
            "provider_id": str(filings.get("provider_id") or "sec_company_submissions_public"),
            "source": str(filings.get("source") or "sec_company_submissions"),
            "state": str(filings.get("state") or "unavailable"),
            "retrieved_at": str(filings.get("retrieved_at") or "not refreshed"),
            "cache_path": str(filings.get("cache_path") or ""),
            "docs_url": str(filings.get("docs_url") or ""),
            "row_count": filing_count,
            "available": filing_count > 0,
            "gated": False,
            "action_id": "markets_stocks_refresh",
            "summary": (
                f"{filing_count} filings across {filing_symbols} / "
                f"{latest_form} {latest_filing_date}"
            ).strip(),
            "message": (
                "Public SEC recent-submissions watchlist metadata; no filing body is copied."
            ),
        },
        {
            "lane_id": "fundamentals",
            "label": "Company Facts",
            "runtime_role": "public_fundamentals",
            "provider_id": str(fundamentals.get("provider_id") or "sec_edgar_public"),
            "source": str(fundamentals.get("source") or "sec_edgar_public"),
            "state": str(fundamentals.get("state") or "unavailable"),
            "retrieved_at": str(fundamentals.get("retrieved_at") or "not refreshed"),
            "cache_path": str(fundamentals.get("cache_path") or ""),
            "docs_url": str(fundamentals.get("docs_url") or ""),
            "row_count": fact_count,
            "available": company_count > 0 or fact_count > 0,
            "gated": False,
            "action_id": "markets_stocks_refresh",
            "summary": f"{company_count} companies / {fact_count} facts",
            "message": "Public SEC companyfacts facts; reference-only fundamentals context.",
        },
        {
            "lane_id": "frames",
            "label": "XBRL Frames",
            "runtime_role": "public_fundamental_frames",
            "provider_id": str(sec_frames.get("provider_id") or "sec_xbrl_frames_public"),
            "source": str(sec_frames.get("source") or "sec_xbrl_frames"),
            "state": str(sec_frames.get("state") or "unavailable"),
            "retrieved_at": str(sec_frames.get("retrieved_at") or "not refreshed"),
            "cache_path": str(sec_frames.get("cache_path") or ""),
            "docs_url": str(sec_frames.get("docs_url") or ""),
            "row_count": frame_count,
            "available": frame_count > 0,
            "gated": False,
            "action_id": "markets_stocks_refresh",
            "summary": f"{frame_count} entities / {frame_tag} {frame_period}",
            "message": "Public SEC XBRL frame rows; cross-company fundamentals, not quotes.",
        },
    ]


def _stock_lane_summary(lanes: list[dict[str, Any]]) -> dict[str, Any]:
    available_lanes = [lane for lane in lanes if lane.get("available")]
    gated_lanes = [lane for lane in lanes if lane.get("gated")]
    primary_lane = available_lanes[0] if available_lanes else (lanes[0] if lanes else {})
    return {
        "status_lane_count": len(lanes),
        "available_lane_count": len(available_lanes),
        "gated_lane_count": len(gated_lanes),
        "primary_lane": str(primary_lane.get("lane_id") or ""),
        "available_lanes": ",".join(str(lane.get("lane_id")) for lane in available_lanes),
    }


def _asset_gateways(research_summary: dict[str, Any]) -> list[dict[str, str]]:
    fundamentals = research_summary.get("fundamentals")
    fundamentals = fundamentals if isinstance(fundamentals, dict) else {}
    sec_frames = research_summary.get("sec_frames")
    sec_frames = sec_frames if isinstance(sec_frames, dict) else {}
    equity_registry = research_summary.get("equity_registry")
    equity_registry = equity_registry if isinstance(equity_registry, dict) else {}
    filings = research_summary.get("filings")
    filings = filings if isinstance(filings, dict) else {}
    macro = research_summary.get("macro")
    macro = macro if isinstance(macro, dict) else {}
    rates = research_summary.get("rates")
    rates = rates if isinstance(rates, dict) else {}
    fx = research_summary.get("fx")
    fx = fx if isinstance(fx, dict) else {}
    fx_quote_watchlist = (
        fx.get("quote_watchlist") if isinstance(fx.get("quote_watchlist"), dict) else {}
    )
    commodities = research_summary.get("commodities")
    commodities = commodities if isinstance(commodities, dict) else {}
    funds = research_summary.get("funds")
    funds = funds if isinstance(funds, dict) else {}
    equity_quotes = research_summary.get("equity_quotes")
    equity_quotes = equity_quotes if isinstance(equity_quotes, dict) else {}
    etf_quotes = research_summary.get("etf_quotes")
    etf_quotes = etf_quotes if isinstance(etf_quotes, dict) else {}
    nasdaq_symbols = research_summary.get("nasdaq_symbols")
    nasdaq_symbols = nasdaq_symbols if isinstance(nasdaq_symbols, dict) else {}
    quote_state = str(equity_quotes.get("state") or "key_required")
    stock_lanes = _stock_status_lanes(
        fundamentals,
        sec_frames,
        equity_registry,
        filings,
        equity_quotes,
        nasdaq_symbols,
    )
    stock_lane_summary = _stock_lane_summary(stock_lanes)
    gateways = []
    for gateway in ASSET_TABS:
        next_gateway = dict(gateway)
        if gateway["tab_id"] == "stocks":
            available_count = int(stock_lane_summary["available_lane_count"])
            if available_count:
                next_gateway["state"] = "stock_lanes_available"
                next_gateway["source"] = "stock_provider_stack"
                next_gateway["provider_id"] = "stock_status_lanes"
                next_gateway["message"] = (
                    f"{available_count}/{stock_lane_summary['status_lane_count']} stock lanes "
                    f"available ({stock_lane_summary['available_lanes']}); inspect lane rows "
                    "for quote, registry, watchlist filings, fundamentals, and frame states."
                )
            else:
                next_gateway["state"] = quote_state
                next_gateway["source"] = str(
                    equity_quotes.get("source") or "alphavantage_global_quote"
                )
                next_gateway["provider_id"] = str(
                    equity_quotes.get("provider_id") or "alphavantage_global_quote_optional_key"
                )
                next_gateway["message"] = (
                    "Use STOCKS for SEC reference/fundamental lanes; use QUOTE after storing "
                    "a local Alpha Vantage key."
                )
        if gateway["tab_id"] == "etf":
            etf_quote_state = str(etf_quotes.get("state") or "key_required")
            if etf_quotes.get("row_count"):
                etf_message = "cached"
                if etf_quote_state == "stale_cache":
                    etf_message = "showing stale local ETF quote cache"
                elif etf_quote_state == "rate_limited":
                    etf_message = "rate-limited; showing local ETF quote cache"
                next_gateway["state"] = "quote_available" if etf_quote_state == "live" else etf_quote_state
                next_gateway["source"] = str(etf_quotes.get("source") or "alphavantage_global_quote")
                next_gateway["provider_id"] = str(
                    etf_quotes.get("provider_id") or "alphavantage_global_quote_optional_key"
                )
                next_gateway["message"] = (
                    f"Alpha Vantage ETF quote {etf_message} for {etf_quotes.get('symbols')}; "
                    "SEC fund registry remains available separately."
                )
            elif funds.get("row_count"):
                next_gateway["state"] = "fund_registry_available"
                next_gateway["source"] = str(funds.get("source") or "sec_fund_ticker_registry")
                next_gateway["message"] = (
                    f"SEC fund ticker registry cached for {funds.get('row_count')} rows; "
                    "Alpha Vantage ETF quote refresh requires a local key."
                )
            else:
                next_gateway["state"] = "no_key_provider_ready"
                next_gateway["source"] = "sec_fund_ticker_registry"
                next_gateway["message"] = (
                    "Use ETF refresh for SEC registry rows or ETF QUOTE after storing a local key."
                )
        if gateway["tab_id"] in {"fx", "commodities", "rates", "indexes", "regional"} and macro.get("series_count"):
            next_gateway["state"] = "macro_context_available"
            next_gateway["source"] = str(macro.get("source") or "macro_provider_mix")
            next_gateway["message"] = "Public macro series are cached; spot quotes remain provider-gated."
        elif gateway["tab_id"] in {"indexes", "regional"}:
            next_gateway["state"] = "no_key_provider_ready"
            next_gateway["source"] = "macro_provider_mix"
            next_gateway["message"] = (
                "Use MACRO or BLS refresh for public macro context, or BEA/Census after "
                "storing a local key for Regional context."
            )
        if gateway["tab_id"] == "fx":
            h10 = fx.get("h10") if isinstance(fx.get("h10"), dict) else {}
            if fx_quote_watchlist.get("row_count"):
                next_gateway["state"] = "fx_quote_available"
                next_gateway["source"] = str(
                    fx_quote_watchlist.get("source") or "alphavantage_currency_exchange_rate"
                )
                next_gateway["provider_id"] = str(
                    fx_quote_watchlist.get("provider_id")
                    or "alphavantage_global_quote_optional_key"
                )
                next_gateway["message"] = (
                    f"Alpha Vantage FX quote watchlist cached for "
                    f"{fx_quote_watchlist.get('pairs')}; quotes are not orderable."
                )
            elif fx.get("row_count") or h10.get("row_count"):
                next_gateway["state"] = "fx_reference_available"
                next_gateway["source"] = str(fx.get("source") or "ecb_fx_reference")
                next_gateway["message"] = (
                    f"ECB EUR reference rates cached for {fx.get('date') or 'no cache'}; "
                    f"Federal Reserve H.10 cached for {h10.get('date') or 'no cache'}; "
                    "optional spot quote watchlist requires a local Alpha Vantage key."
                )
            else:
                next_gateway["state"] = "no_key_provider_ready"
                next_gateway["source"] = "ecb_fx_reference / federal_reserve_h10 / alphavantage_fx"
                next_gateway["message"] = (
                    "Use FX refresh for public reference rates or FX QTE after storing a local key."
                )
        if gateway["tab_id"] == "commodities":
            cftc = commodities.get("cftc") if isinstance(commodities.get("cftc"), dict) else {}
            if commodities.get("row_count"):
                next_gateway["state"] = "commodity_reference_available"
                next_gateway["source"] = str(
                    commodities.get("source") or "world_bank_pink_sheet"
                )
                next_gateway["message"] = (
                    f"World Bank monthly commodity prices cached for {commodities.get('period')}; "
                    "spot/futures providers remain disabled."
                )
            elif cftc.get("row_count"):
                next_gateway["state"] = "commodity_positioning_available"
                next_gateway["source"] = str(cftc.get("source") or "cftc_cot_legacy_futures_only")
                next_gateway["provider_id"] = str(
                    cftc.get("provider_id") or "cftc_cot_legacy_public"
                )
                next_gateway["message"] = (
                    f"CFTC COT positioning cached for {cftc.get('report_date')}; "
                    "values remain non-tradable context."
                )
            else:
                next_gateway["state"] = "no_key_provider_ready"
                next_gateway["source"] = "world_bank_pink_sheet / cftc_cot"
                next_gateway["message"] = (
                    "Use COMMOD for Pink Sheet prices or COT for CFTC positioning context."
                )
            energy = commodities.get("energy") if isinstance(commodities.get("energy"), dict) else {}
            if energy.get("series_count"):
                next_gateway["state"] = "energy_context_available"
                next_gateway["source"] = str(energy.get("source") or "eia_open_data_api")
                next_gateway["message"] = (
                    f"EIA energy context cached for {energy.get('latest_period')}; "
                    "values remain non-tradable context series."
                )
            elif energy.get("state") == "key_required" and not commodities.get("row_count"):
                next_gateway["source"] = "world_bank_pink_sheet / eia_open_data_api"
                next_gateway["message"] = (
                    "Use COMMOD for no-key monthly reference data or store a local EIA key "
                    "for energy context."
                )
        if gateway["tab_id"] == "rates":
            sofr = rates.get("sofr") if isinstance(rates.get("sofr"), dict) else {}
            if rates.get("tenor_count") or sofr.get("row_count"):
                next_gateway["state"] = "rates_available"
                next_gateway["source"] = "us_treasury_public / nyfed_sofr_public"
                next_gateway["message"] = (
                    f"Treasury curve cached for {rates.get('latest_date') or 'no cache'}; "
                    f"SOFR cached for {sofr.get('latest_date') or 'no cache'}; "
                    "all rates remain reference-only."
                )
            else:
                next_gateway["state"] = "no_key_provider_ready"
                next_gateway["source"] = "us_treasury_public / nyfed_sofr_public"
                next_gateway["message"] = (
                    "Use rates refresh to populate public Treasury curve and SOFR reference data."
                )
        gateways.append(next_gateway)
    return gateways


def _macro_series_rows(series: list[Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in series:
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "series_id": str(row.get("series_id") or ""),
                "label": str(row.get("label") or ""),
                "dataset_name": str(row.get("dataset_name") or ""),
                "source": str(row.get("source") or "dbnomics_public"),
                "provider_id": str(row.get("provider_id") or "dbnomics_public"),
                "source_provider": str(row.get("source_provider") or ""),
                "dataset": str(row.get("dataset") or ""),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "docs_url": str(row.get("docs_url") or ""),
                "latest_period": str(row.get("latest_period") or ""),
                "latest_value": str(row.get("latest_value") or ""),
                "observation_count": str(row.get("observation_count") or ""),
                "frequency": str(row.get("frequency") or ""),
            }
        )
    return rows


def _macro_provider_summary_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "provider_id": str(row.get("provider_id") or ""),
                "state": str(row.get("state") or "unavailable"),
                "series_count": int(row.get("series_count") or 0),
                "latest_period": str(row.get("latest_period") or ""),
                "latest_value": str(row.get("latest_value") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "docs_url": str(row.get("docs_url") or ""),
                "selected_for_headline": bool(row.get("selected_for_headline")),
            }
        )
    return normalized


def _company_registry_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "cik": str(row.get("cik") or ""),
                "entity_name": str(row.get("entity_name") or ""),
                "source": str(row.get("source") or "sec_company_ticker_registry"),
                "provider_id": str(
                    row.get("provider_id") or "sec_company_ticker_registry_public"
                ),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "docs_url": str(row.get("docs_url") or ""),
                "reference_only": bool(row.get("reference_only", True)),
            }
        )
    return normalized


def _company_filing_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "cik": str(row.get("cik") or ""),
                "entity_name": str(row.get("entity_name") or ""),
                "accession_number": str(row.get("accession_number") or ""),
                "filing_date": str(row.get("filing_date") or ""),
                "report_date": str(row.get("report_date") or ""),
                "acceptance_datetime": str(row.get("acceptance_datetime") or ""),
                "form": str(row.get("form") or ""),
                "primary_document": str(row.get("primary_document") or ""),
                "description": str(row.get("description") or ""),
                "items": str(row.get("items") or ""),
                "source": str(row.get("source") or "sec_company_submissions"),
                "provider_id": str(row.get("provider_id") or "sec_company_submissions_public"),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "docs_url": str(row.get("docs_url") or ""),
                "filing_url": str(row.get("filing_url") or ""),
                "reference_only": bool(row.get("reference_only", True)),
            }
        )
    return normalized


def _company_fact_rows(companies: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for company in companies:
        if not isinstance(company, dict):
            continue
        facts = company.get("facts") if isinstance(company.get("facts"), list) else []
        rows.append(
            {
                "symbol": str(company.get("symbol") or ""),
                "cik": str(company.get("cik") or ""),
                "entity_name": str(company.get("entity_name") or ""),
                "source": str(company.get("source") or "sec_edgar_public"),
                "provider_id": str(company.get("provider_id") or "sec_edgar_public"),
                "retrieved_at": str(company.get("retrieved_at") or ""),
                "cache_path": str(company.get("cache_path") or ""),
                "docs_url": str(company.get("docs_url") or ""),
                "facts": [
                    {
                        "concept": str(fact.get("concept") or ""),
                        "label": str(fact.get("label") or ""),
                        "unit": str(fact.get("unit") or ""),
                        "value": str(fact.get("value") or ""),
                        "end": str(fact.get("end") or ""),
                        "fy": str(fact.get("fy") or ""),
                        "fp": str(fact.get("fp") or ""),
                        "form": str(fact.get("form") or ""),
                        "filed": str(fact.get("filed") or ""),
                    }
                    for fact in facts
                    if isinstance(fact, dict)
                ],
            }
        )
    return rows


def _sec_frame_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "cik": str(row.get("cik") or ""),
                "entity_name": str(row.get("entity_name") or ""),
                "taxonomy": str(row.get("taxonomy") or "us-gaap"),
                "tag": str(row.get("tag") or ""),
                "label": str(row.get("label") or row.get("tag") or ""),
                "unit": str(row.get("unit") or ""),
                "period": str(row.get("period") or ""),
                "value": str(row.get("value") or ""),
                "end": str(row.get("end") or ""),
                "fy": str(row.get("fy") or ""),
                "fp": str(row.get("fp") or ""),
                "form": str(row.get("form") or ""),
                "filed": str(row.get("filed") or ""),
                "frame": str(row.get("frame") or ""),
                "accession_number": str(row.get("accession_number") or ""),
                "location": str(row.get("location") or ""),
                "source": str(row.get("source") or "sec_xbrl_frames"),
                "provider_id": str(row.get("provider_id") or "sec_xbrl_frames_public"),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "docs_url": str(row.get("docs_url") or ""),
                "reference_only": bool(row.get("reference_only", True)),
            }
        )
    return normalized


def _fund_registry_rows(rows: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "cik": str(row.get("cik") or ""),
                "series_id": str(row.get("series_id") or ""),
                "class_id": str(row.get("class_id") or ""),
                "source": str(row.get("source") or "sec_fund_ticker_registry"),
                "provider_id": str(
                    row.get("provider_id") or "sec_fund_ticker_registry_public"
                ),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "docs_url": str(row.get("docs_url") or ""),
            }
        )
    return normalized


def _equity_quote_rows(rows: list[Any]) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "price": str(row.get("price") or ""),
                "open": str(row.get("open") or ""),
                "high": str(row.get("high") or ""),
                "low": str(row.get("low") or ""),
                "volume": str(row.get("volume") or ""),
                "latest_trading_day": str(row.get("latest_trading_day") or ""),
                "previous_close": str(row.get("previous_close") or ""),
                "change": str(row.get("change") or ""),
                "change_percent": str(row.get("change_percent") or ""),
                "source": str(row.get("source") or "alphavantage_global_quote"),
                "provider_id": str(
                    row.get("provider_id") or "alphavantage_global_quote_optional_key"
                ),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "docs_url": str(row.get("docs_url") or ""),
            }
        )
    return normalized


def _twelve_data_quote_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "name": str(row.get("name") or ""),
                "instrument_type": str(row.get("instrument_type") or ""),
                "exchange": str(row.get("exchange") or ""),
                "currency": str(row.get("currency") or ""),
                "price": str(row.get("price") or ""),
                "open": str(row.get("open") or ""),
                "high": str(row.get("high") or ""),
                "low": str(row.get("low") or ""),
                "volume": str(row.get("volume") or ""),
                "latest_trading_day": str(row.get("datetime") or ""),
                "previous_close": str(row.get("previous_close") or ""),
                "change": str(row.get("change") or ""),
                "change_percent": str(row.get("change_percent") or ""),
                "source": str(row.get("source") or "twelve_data_quote"),
                "provider_id": str(row.get("provider_id") or "twelve_data_quote_optional_key"),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "docs_url": str(row.get("docs_url") or ""),
                "quote_semantics": str(row.get("quote_semantics") or "quote_not_orderable"),
                "live_action_enabled": bool(row.get("live_action_enabled", False)),
            }
        )
    return normalized


def _finnhub_quote_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "price": str(row.get("price") or ""),
                "open": str(row.get("open") or ""),
                "high": str(row.get("high") or ""),
                "low": str(row.get("low") or ""),
                "volume": str(row.get("volume") or ""),
                "latest_trading_day": str(
                    row.get("latest_trading_day") or row.get("timestamp") or ""
                ),
                "previous_close": str(row.get("previous_close") or ""),
                "change": str(row.get("change") or ""),
                "change_percent": str(row.get("change_percent") or ""),
                "source": str(row.get("source") or "finnhub_quote"),
                "provider_id": str(
                    row.get("provider_id") or "finnhub_equity_quote_optional_key"
                ),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "docs_url": str(row.get("docs_url") or ""),
                "quote_semantics": str(row.get("quote_semantics") or "quote_not_orderable"),
                "live_action_enabled": bool(row.get("live_action_enabled", False)),
            }
        )
    return normalized


def _fmp_quote_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "name": str(row.get("name") or ""),
                "exchange": str(row.get("exchange") or ""),
                "price": str(row.get("price") or ""),
                "open": str(row.get("open") or ""),
                "high": str(row.get("high") or ""),
                "low": str(row.get("low") or ""),
                "volume": str(row.get("volume") or ""),
                "latest_trading_day": str(
                    row.get("latest_trading_day") or row.get("timestamp") or ""
                ),
                "previous_close": str(row.get("previous_close") or ""),
                "change": str(row.get("change") or ""),
                "change_percent": str(row.get("change_percent") or ""),
                "source": str(row.get("source") or "fmp_stock_quote"),
                "provider_id": str(row.get("provider_id") or "fmp_stock_quote_optional_key"),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "docs_url": str(row.get("docs_url") or ""),
                "quote_semantics": str(row.get("quote_semantics") or "quote_not_orderable"),
                "live_action_enabled": bool(row.get("live_action_enabled", False)),
            }
        )
    return normalized


def _stooq_quote_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "date": str(row.get("date") or ""),
                "time": str(row.get("time") or ""),
                "price": str(row.get("price") or row.get("close") or ""),
                "open": str(row.get("open") or ""),
                "high": str(row.get("high") or ""),
                "low": str(row.get("low") or ""),
                "close": str(row.get("close") or row.get("price") or ""),
                "volume": str(row.get("volume") or ""),
                "change": str(row.get("change") or ""),
                "change_percent": str(row.get("change_percent") or ""),
                "source": str(row.get("source") or "stooq_current_quote_csv"),
                "provider_id": str(row.get("provider_id") or "stooq_public_quote_snapshot"),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "quote_semantics": str(row.get("quote_semantics") or "quote_not_orderable"),
                "live_action_enabled": bool(row.get("live_action_enabled", False)),
            }
        )
    return normalized


def _moex_quote_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "name": str(row.get("name") or ""),
                "board_id": str(row.get("board_id") or ""),
                "price": str(row.get("price") or ""),
                "open": str(row.get("open") or ""),
                "high": str(row.get("high") or ""),
                "low": str(row.get("low") or ""),
                "volume": str(row.get("volume") or ""),
                "value": str(row.get("value") or ""),
                "bid": str(row.get("bid") or ""),
                "ask": str(row.get("ask") or ""),
                "update_time": str(row.get("update_time") or ""),
                "change": str(row.get("change") or ""),
                "change_percent": str(row.get("change_percent") or ""),
                "currency": str(row.get("currency") or "RUB"),
                "source": str(row.get("source") or "moex_iss_marketdata_delayed"),
                "provider_id": str(row.get("provider_id") or "moex_iss_delayed_quote_snapshot"),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "quote_semantics": str(row.get("quote_semantics") or "quote_not_orderable"),
                "live_action_enabled": bool(row.get("live_action_enabled", False)),
                "orderable": bool(row.get("orderable", False)),
            }
        )
    return normalized


def _twse_quote_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "name": str(row.get("name") or ""),
                "date": str(row.get("date") or ""),
                "price": str(row.get("price") or row.get("close") or ""),
                "open": str(row.get("open") or ""),
                "high": str(row.get("high") or ""),
                "low": str(row.get("low") or ""),
                "close": str(row.get("close") or row.get("price") or ""),
                "volume": str(row.get("volume") or ""),
                "value": str(row.get("value") or ""),
                "transaction_count": str(row.get("transaction_count") or ""),
                "change": str(row.get("change") or ""),
                "change_percent": str(row.get("change_percent") or ""),
                "currency": str(row.get("currency") or "TWD"),
                "source": str(row.get("source") or "twse_stock_day_all_openapi"),
                "provider_id": str(
                    row.get("provider_id") or "twse_openapi_daily_quote_snapshot"
                ),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "quote_semantics": str(row.get("quote_semantics") or "quote_not_orderable"),
                "live_action_enabled": bool(row.get("live_action_enabled", False)),
                "orderable": bool(row.get("orderable", False)),
                # When a fresher local close overrules the TWSE file, the row
                # keeps TWSE's source/provider fields but the number is not
                # theirs. Dropping this on the way through left the row
                # attributing a Yahoo close to TWSE (2026-07-28).
                "price_basis": str(row.get("price_basis") or ""),
            }
        )
    return normalized


def _nasdaq_symbol_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows[:25]:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "symbol": str(row.get("symbol") or ""),
                "name": str(row.get("name") or ""),
                "listing_exchange": str(row.get("listing_exchange") or ""),
                "market_category": str(row.get("market_category") or ""),
                "is_etf": bool(row.get("is_etf", False)),
                "source_file": str(row.get("source_file") or ""),
                "source": str(row.get("source") or "nasdaq_trader_symbol_directory"),
                "provider_id": str(
                    row.get("provider_id") or "nasdaq_trader_symbol_directory_public"
                ),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "quote_semantics": str(row.get("quote_semantics") or "not_quote"),
                "live_action_enabled": bool(row.get("live_action_enabled", False)),
            }
        )
    return normalized


def _openfigi_mapping_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows[:25]:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "request_symbol": str(row.get("request_symbol") or ""),
                "ticker": str(row.get("ticker") or ""),
                "name": str(row.get("name") or ""),
                "figi": str(row.get("figi") or ""),
                "composite_figi": str(row.get("composite_figi") or ""),
                "share_class_figi": str(row.get("share_class_figi") or ""),
                "exchange_code": str(row.get("exchange_code") or ""),
                "market_sector": str(row.get("market_sector") or ""),
                "security_type": str(row.get("security_type") or ""),
                "source": str(row.get("source") or "openfigi_v3_mapping"),
                "provider_id": str(
                    row.get("provider_id") or "openfigi_identifier_mapping_public"
                ),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "quote_semantics": str(row.get("quote_semantics") or "not_quote"),
                "live_action_enabled": bool(row.get("live_action_enabled", False)),
                "orderable": bool(row.get("orderable", False)),
            }
        )
    return normalized


def _fx_quote_rows(rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                "pair": str(row.get("pair") or ""),
                "from_currency": str(row.get("from_currency") or ""),
                "to_currency": str(row.get("to_currency") or ""),
                "rate": str(row.get("rate") or ""),
                "bid": str(row.get("bid") or ""),
                "ask": str(row.get("ask") or ""),
                "last_refreshed": str(row.get("last_refreshed") or ""),
                "time_zone": str(row.get("time_zone") or ""),
                "source": str(row.get("source") or "alphavantage_currency_exchange_rate"),
                "provider_id": str(
                    row.get("provider_id") or "alphavantage_global_quote_optional_key"
                ),
                "retrieved_at": str(row.get("retrieved_at") or ""),
                "cache_path": str(row.get("cache_path") or ""),
                "docs_url": str(row.get("docs_url") or ""),
                "quote_semantics": str(row.get("quote_semantics") or "quote_not_orderable"),
                "live_action_enabled": bool(row.get("live_action_enabled", False)),
            }
        )
    return normalized


def _stocks_view(research_summary: dict[str, Any]) -> dict[str, Any]:
    fundamentals = research_summary.get("fundamentals")
    fundamentals = fundamentals if isinstance(fundamentals, dict) else {}
    sec_frames = research_summary.get("sec_frames")
    sec_frames = sec_frames if isinstance(sec_frames, dict) else {}
    equity_registry = research_summary.get("equity_registry")
    equity_registry = equity_registry if isinstance(equity_registry, dict) else {}
    filings = research_summary.get("filings")
    filings = filings if isinstance(filings, dict) else {}
    equity_quotes = research_summary.get("equity_quotes")
    equity_quotes = equity_quotes if isinstance(equity_quotes, dict) else {}
    nasdaq_symbols = research_summary.get("nasdaq_symbols")
    nasdaq_symbols = nasdaq_symbols if isinstance(nasdaq_symbols, dict) else {}
    openfigi_mapping = research_summary.get("openfigi_mapping")
    openfigi_mapping = openfigi_mapping if isinstance(openfigi_mapping, dict) else {}
    status_lanes = _stock_status_lanes(
        fundamentals,
        sec_frames,
        equity_registry,
        filings,
        equity_quotes,
        nasdaq_symbols,
    )
    lane_summary = _stock_lane_summary(status_lanes)
    symbol_search = (
        nasdaq_symbols.get("search") if isinstance(nasdaq_symbols.get("search"), dict) else {}
    )
    return {
        "status": {
            "source": str(fundamentals.get("source") or "sec_edgar_public"),
            "state": str(fundamentals.get("state") or "unavailable"),
            "provider_id": str(fundamentals.get("provider_id") or "sec_edgar_public"),
            "retrieved_at": str(fundamentals.get("retrieved_at") or "not refreshed"),
            "cache_path": str(fundamentals.get("cache_path") or ""),
            "docs_url": str(fundamentals.get("docs_url") or ""),
        },
        "quote_status": {
            "source": str(equity_quotes.get("source") or "alphavantage_global_quote"),
            "state": str(equity_quotes.get("state") or "key_required"),
            "provider_id": str(
                equity_quotes.get("provider_id") or "alphavantage_global_quote_optional_key"
            ),
            "retrieved_at": str(equity_quotes.get("retrieved_at") or "not refreshed"),
            "cache_path": str(equity_quotes.get("cache_path") or ""),
            "docs_url": str(equity_quotes.get("docs_url") or ""),
            "message": str(
                equity_quotes.get("message")
                or "Store a local Alpha Vantage key before refreshing equity quotes."
            ),
        },
        "registry_status": {
            "source": str(equity_registry.get("source") or "sec_company_ticker_registry"),
            "state": str(equity_registry.get("state") or "unavailable"),
            "provider_id": str(
                equity_registry.get("provider_id") or "sec_company_ticker_registry_public"
            ),
            "retrieved_at": str(equity_registry.get("retrieved_at") or "not refreshed"),
            "cache_path": str(equity_registry.get("cache_path") or ""),
            "docs_url": str(equity_registry.get("docs_url") or ""),
        },
        "filings_status": {
            "source": str(filings.get("source") or "sec_company_submissions"),
            "state": str(filings.get("state") or "unavailable"),
            "provider_id": str(filings.get("provider_id") or "sec_company_submissions_public"),
            "retrieved_at": str(filings.get("retrieved_at") or "not refreshed"),
            "cache_path": str(filings.get("cache_path") or ""),
            "docs_url": str(filings.get("docs_url") or ""),
        },
        "frames_status": {
            "source": str(sec_frames.get("source") or "sec_xbrl_frames"),
            "state": str(sec_frames.get("state") or "unavailable"),
            "provider_id": str(sec_frames.get("provider_id") or "sec_xbrl_frames_public"),
            "retrieved_at": str(sec_frames.get("retrieved_at") or "not refreshed"),
            "cache_path": str(sec_frames.get("cache_path") or ""),
            "docs_url": str(sec_frames.get("docs_url") or ""),
        },
        "symbol_directory_status": {
            "source": str(nasdaq_symbols.get("source") or "nasdaq_trader_symbol_directory"),
            "state": str(nasdaq_symbols.get("state") or "unavailable"),
            "provider_id": str(
                nasdaq_symbols.get("provider_id") or "nasdaq_trader_symbol_directory_public"
            ),
            "retrieved_at": str(nasdaq_symbols.get("retrieved_at") or "not refreshed"),
            "cache_path": str(nasdaq_symbols.get("cache_path") or ""),
            "docs_url": str(nasdaq_symbols.get("docs_url") or ""),
            "message": str(
                nasdaq_symbols.get("message")
                or "Run Nasdaq Trader symbol refresh to populate symbol-directory rows."
            ),
        },
        "identifier_mapping_status": {
            "source": str(openfigi_mapping.get("source") or "openfigi_v3_mapping"),
            "state": str(openfigi_mapping.get("state") or "unavailable"),
            "provider_id": str(
                openfigi_mapping.get("provider_id") or "openfigi_identifier_mapping_public"
            ),
            "retrieved_at": str(openfigi_mapping.get("retrieved_at") or "not refreshed"),
            "cache_path": str(openfigi_mapping.get("cache_path") or ""),
            "docs_url": str(openfigi_mapping.get("docs_url") or ""),
            "message": str(
                openfigi_mapping.get("message")
                or "Run OpenFIGI mapping refresh to populate identifier rows."
            ),
        },
        "summary": {
            **lane_summary,
            "company_count": int(fundamentals.get("company_count") or 0),
            "fact_count": int(fundamentals.get("fact_count") or 0),
            "frame_count": int(sec_frames.get("row_count") or 0),
            "frame_entity_count": int(sec_frames.get("entity_count") or 0),
            "frame_tag": str(sec_frames.get("tag") or "Assets"),
            "frame_period": str(sec_frames.get("period") or "CY2023Q4I"),
            "frame_quote_semantics": str(sec_frames.get("quote_semantics") or "not_quote"),
            "registry_row_count": int(equity_registry.get("row_count") or 0),
            "registry_total": int(equity_registry.get("registry_total") or 0),
            "registry_matched_symbols": str(equity_registry.get("matched_symbols") or ""),
            "filing_count": int(filings.get("row_count") or 0),
            "filing_company_count": int(filings.get("company_count") or 0),
            "filing_symbol_count": int(filings.get("symbol_count") or 0),
            "filing_symbols": str(filings.get("filing_symbols") or filings.get("symbols") or ""),
            "latest_filing_date": str(filings.get("latest_filing_date") or ""),
            "latest_filing_form": str(filings.get("latest_form") or ""),
            "filing_symbol": str(filings.get("symbol") or "AAPL"),
            "latest_filing_symbol": str(filings.get("latest_symbol") or filings.get("symbol") or ""),
            "filing_cache_paths": str(filings.get("cache_paths") or ""),
            "quote_state": str(equity_quotes.get("state") or "key_required"),
            "quote_provider": str(
                equity_quotes.get("provider_id") or "alphavantage_global_quote_optional_key"
            ),
            "quote_symbol": str(equity_quotes.get("symbol") or "AAPL"),
            "quote_symbols": str(equity_quotes.get("symbols") or equity_quotes.get("symbol") or "AAPL"),
            "quote_price": str(equity_quotes.get("price") or ""),
            "quote_change": str(equity_quotes.get("change") or ""),
            "quote_change_percent": str(equity_quotes.get("change_percent") or ""),
            "quote_latest_trading_day": str(equity_quotes.get("latest_trading_day") or ""),
            "quote_row_count": int(equity_quotes.get("row_count") or 0),
            "quote_requested_count": int(equity_quotes.get("requested_count") or 0),
            "quote_cached_count": int(equity_quotes.get("cached_count") or 0),
            "quote_live_count": int(equity_quotes.get("live_count") or 0),
            "quote_stale_count": int(equity_quotes.get("stale_count") or 0),
            "symbol_directory_row_count": int(nasdaq_symbols.get("row_count") or 0),
            "symbol_directory_nasdaq_count": int(nasdaq_symbols.get("nasdaq_listed_count") or 0),
            "symbol_directory_other_count": int(nasdaq_symbols.get("other_listed_count") or 0),
            "symbol_directory_etf_count": int(nasdaq_symbols.get("etf_count") or 0),
            "symbol_directory_quote_semantics": str(
                nasdaq_symbols.get("quote_semantics") or "not_quote"
            ),
            "symbol_search_query": str(symbol_search.get("query") or "AAPL"),
            "symbol_search_row_count": int(symbol_search.get("row_count") or 0),
            "symbol_search_total_matches": int(symbol_search.get("total_matches") or 0),
            "identifier_mapping_row_count": int(openfigi_mapping.get("row_count") or 0),
            "identifier_mapping_requested_symbols": str(
                openfigi_mapping.get("requested_symbols") or "AAPL,MSFT,SPY"
            ),
            "identifier_mapping_matched_symbols": int(
                openfigi_mapping.get("matched_symbol_count") or 0
            ),
            "identifier_mapping_quote_semantics": str(
                openfigi_mapping.get("quote_semantics") or "not_quote"
            ),
        },
        "companies": (
            fundamentals.get("companies") if isinstance(fundamentals.get("companies"), list) else []
        ),
        "registry": (
            equity_registry.get("rows") if isinstance(equity_registry.get("rows"), list) else []
        ),
        "filings": filings.get("rows") if isinstance(filings.get("rows"), list) else [],
        "frames": sec_frames.get("rows") if isinstance(sec_frames.get("rows"), list) else [],
        "quotes": (
            equity_quotes.get("rows") if isinstance(equity_quotes.get("rows"), list) else []
        ),
        "symbols": nasdaq_symbols.get("rows") if isinstance(nasdaq_symbols.get("rows"), list) else [],
        "identifier_mappings": (
            openfigi_mapping.get("rows")
            if isinstance(openfigi_mapping.get("rows"), list)
            else []
        ),
        "symbol_search": symbol_search,
        "status_lanes": status_lanes,
    }


def _etf_view(research_summary: dict[str, Any]) -> dict[str, Any]:
    funds = research_summary.get("funds")
    funds = funds if isinstance(funds, dict) else {}
    etf_quotes = research_summary.get("etf_quotes")
    etf_quotes = etf_quotes if isinstance(etf_quotes, dict) else {}
    return {
        "status": {
            "source": str(funds.get("source") or "sec_fund_ticker_registry"),
            "state": str(funds.get("state") or "unavailable"),
            "provider_id": str(funds.get("provider_id") or "sec_fund_ticker_registry_public"),
            "retrieved_at": str(funds.get("retrieved_at") or "not refreshed"),
            "cache_path": str(funds.get("cache_path") or ""),
            "docs_url": str(funds.get("docs_url") or ""),
        },
        "quote_status": {
            "source": str(etf_quotes.get("source") or "alphavantage_global_quote"),
            "state": str(etf_quotes.get("state") or "key_required"),
            "provider_id": str(
                etf_quotes.get("provider_id") or "alphavantage_global_quote_optional_key"
            ),
            "retrieved_at": str(etf_quotes.get("retrieved_at") or "not refreshed"),
            "cache_path": str(etf_quotes.get("cache_path") or ""),
            "docs_url": str(etf_quotes.get("docs_url") or ""),
            "message": str(
                etf_quotes.get("message")
                or "Store a local Alpha Vantage key before refreshing ETF quotes."
            ),
        },
        "summary": {
            "row_count": int(funds.get("row_count") or 0),
            "registry_total": int(funds.get("registry_total") or 0),
            "matched_symbols": str(funds.get("matched_symbols") or ""),
            "quote_state": str(etf_quotes.get("state") or "key_required"),
            "quote_provider": str(
                etf_quotes.get("provider_id") or "alphavantage_global_quote_optional_key"
            ),
            "quote_symbol": str(etf_quotes.get("symbol") or "SPY"),
            "quote_symbols": str(etf_quotes.get("symbols") or etf_quotes.get("symbol") or "SPY"),
            "quote_price": str(etf_quotes.get("price") or ""),
            "quote_change": str(etf_quotes.get("change") or ""),
            "quote_change_percent": str(etf_quotes.get("change_percent") or ""),
            "quote_latest_trading_day": str(etf_quotes.get("latest_trading_day") or ""),
            "quote_row_count": int(etf_quotes.get("row_count") or 0),
            "quote_requested_count": int(etf_quotes.get("requested_count") or 0),
            "quote_cached_count": int(etf_quotes.get("cached_count") or 0),
            "quote_live_count": int(etf_quotes.get("live_count") or 0),
            "quote_stale_count": int(etf_quotes.get("stale_count") or 0),
        },
        "rows": funds.get("rows") if isinstance(funds.get("rows"), list) else [],
        "quotes": (
            etf_quotes.get("rows") if isinstance(etf_quotes.get("rows"), list) else []
        ),
    }


def _macro_market_view(research_summary: dict[str, Any], tab_id: str) -> dict[str, Any]:
    macro = research_summary.get("macro")
    macro = macro if isinstance(macro, dict) else {}
    label = "Index Macro Context" if tab_id == "indexes" else "Regional Macro Context"
    quote_gate = "optional_local_key_or_paid_index_provider" if tab_id == "indexes" else "optional_local_key_or_regional_provider"
    return {
        "status": {
            "source": str(macro.get("source") or "dbnomics_public"),
            "state": str(macro.get("state") or "unavailable"),
            "provider_id": str(macro.get("provider_id") or "dbnomics_public"),
            "retrieved_at": str(macro.get("retrieved_at") or "not refreshed"),
            "cache_path": str(macro.get("cache_path") or ""),
            "docs_url": str(macro.get("docs_url") or ""),
        },
        "summary": {
            "label": label,
            "series_count": int(macro.get("series_count") or 0),
            "provider_count": int(macro.get("provider_count") or 0),
            "latest": str(macro.get("latest") or ""),
            "latest_period": str(macro.get("latest_period") or ""),
            "primary_provider": str(macro.get("primary_provider") or ""),
            "headline_series_id": str(macro.get("headline_series_id") or ""),
            "headline_label": str(macro.get("headline_label") or ""),
            "headline_rule": str(macro.get("headline_rule") or ""),
            "quote_state": "disabled_until_provider_gate",
            "quote_provider": quote_gate,
        },
        "headline_series": (
            macro.get("headline_series") if isinstance(macro.get("headline_series"), dict) else {}
        ),
        "provider_summaries": (
            macro.get("provider_summaries") if isinstance(macro.get("provider_summaries"), list) else []
        ),
        "series": macro.get("series") if isinstance(macro.get("series"), list) else [],
    }


def _commodities_view(research_summary: dict[str, Any]) -> dict[str, Any]:
    commodities = research_summary.get("commodities")
    commodities = commodities if isinstance(commodities, dict) else {}
    energy = commodities.get("energy") if isinstance(commodities.get("energy"), dict) else {}
    cftc = commodities.get("cftc") if isinstance(commodities.get("cftc"), dict) else {}
    return {
        "status": {
            "source": str(commodities.get("source") or "world_bank_pink_sheet"),
            "state": str(commodities.get("state") or "unavailable"),
            "provider_id": str(
                commodities.get("provider_id") or "world_bank_commodity_monthly_public"
            ),
            "retrieved_at": str(commodities.get("retrieved_at") or "not refreshed"),
            "cache_path": str(commodities.get("cache_path") or ""),
            "docs_url": str(commodities.get("docs_url") or ""),
        },
        "summary": {
            "period": str(commodities.get("period") or ""),
            "updated_on": str(commodities.get("updated_on") or ""),
            "row_count": int(commodities.get("row_count") or 0),
            "crude_wti": str(commodities.get("crude_wti") or ""),
            "crude_brent": str(commodities.get("crude_brent") or ""),
            "ngas_us": str(commodities.get("ngas_us") or ""),
            "gold": str(commodities.get("gold") or ""),
            "copper": str(commodities.get("copper") or ""),
            "wheat_us_srw": str(commodities.get("wheat_us_srw") or ""),
        },
        "rows": commodities.get("rows") if isinstance(commodities.get("rows"), list) else [],
        "cftc": {
            "state": str(cftc.get("state") or "unavailable"),
            "source": str(cftc.get("source") or "cftc_cot_legacy_futures_only"),
            "provider_id": str(cftc.get("provider_id") or "cftc_cot_legacy_public"),
            "retrieved_at": str(cftc.get("retrieved_at") or "not refreshed"),
            "cache_path": str(cftc.get("cache_path") or ""),
            "docs_url": str(cftc.get("docs_url") or ""),
            "message": str(
                cftc.get("message") or "Run COT to fetch public CFTC weekly positioning context."
            ),
            "row_count": int(cftc.get("row_count") or 0),
            "report_date": str(cftc.get("report_date") or ""),
            "contracts": str(cftc.get("contracts") or ""),
            "gold_noncommercial_net": str(cftc.get("gold_noncommercial_net") or ""),
            "wti_crude_noncommercial_net": str(
                cftc.get("wti_crude_noncommercial_net") or ""
            ),
            "copper_noncommercial_net": str(cftc.get("copper_noncommercial_net") or ""),
            "wheat_srw_noncommercial_net": str(
                cftc.get("wheat_srw_noncommercial_net") or ""
            ),
            "rows": cftc.get("rows") if isinstance(cftc.get("rows"), list) else [],
        },
        "energy": {
            "state": str(energy.get("state") or "key_required"),
            "source": str(energy.get("source") or "eia_open_data_api"),
            "provider_id": str(energy.get("provider_id") or "eia_open_data_optional_key"),
            "retrieved_at": str(energy.get("retrieved_at") or "not refreshed"),
            "cache_path": str(energy.get("cache_path") or ""),
            "docs_url": str(energy.get("docs_url") or ""),
            "message": str(
                energy.get("message")
                or "Store a local EIA Open Data key before refreshing energy context."
            ),
            "series_count": int(energy.get("series_count") or 0),
            "latest_period": str(energy.get("latest_period") or ""),
            "wti_spot": str(energy.get("wti_spot") or ""),
            "brent_spot": str(energy.get("brent_spot") or ""),
            "henry_hub": str(energy.get("henry_hub") or ""),
            "series": energy.get("series") if isinstance(energy.get("series"), list) else [],
        },
    }


def _fx_view(research_summary: dict[str, Any]) -> dict[str, Any]:
    fx = research_summary.get("fx")
    fx = fx if isinstance(fx, dict) else {}
    h10 = fx.get("h10") if isinstance(fx.get("h10"), dict) else {}
    boc = fx.get("boc") if isinstance(fx.get("boc"), dict) else {}
    quote_watchlist = (
        fx.get("quote_watchlist") if isinstance(fx.get("quote_watchlist"), dict) else {}
    )
    return {
        "status": {
            "source": str(fx.get("source") or "ecb_fx_reference"),
            "state": str(fx.get("state") or "unavailable"),
            "provider_id": str(fx.get("provider_id") or "ecb_fx_reference_public"),
            "retrieved_at": str(fx.get("retrieved_at") or "not refreshed"),
            "cache_path": str(fx.get("cache_path") or ""),
            "docs_url": str(fx.get("docs_url") or ""),
        },
        "summary": {
            "date": str(fx.get("date") or ""),
            "row_count": int(fx.get("row_count") or 0),
            "base": str(fx.get("base") or "EUR"),
            "usd": str(fx.get("usd") or ""),
            "gbp": str(fx.get("gbp") or ""),
            "jpy": str(fx.get("jpy") or ""),
            "chf": str(fx.get("chf") or ""),
            "cny": str(fx.get("cny") or ""),
        },
        "h10": {
            "status": {
                "source": str(h10.get("source") or "federal_reserve_h10"),
                "state": str(h10.get("state") or "unavailable"),
                "provider_id": str(
                    h10.get("provider_id") or "federal_reserve_h10_ddp_public"
                ),
                "retrieved_at": str(h10.get("retrieved_at") or "not refreshed"),
                "cache_path": str(h10.get("cache_path") or ""),
                "docs_url": str(h10.get("docs_url") or ""),
            },
            "summary": {
                "date": str(h10.get("date") or ""),
                "row_count": int(h10.get("row_count") or 0),
                "base": str(h10.get("base") or "USD reference"),
                "eur": str(h10.get("eur") or ""),
                "gbp": str(h10.get("gbp") or ""),
                "jpy": str(h10.get("jpy") or ""),
                "cad": str(h10.get("cad") or ""),
                "cny": str(h10.get("cny") or ""),
            },
            "rows": h10.get("rows") if isinstance(h10.get("rows"), list) else [],
        },
        "boc": {
            "status": {
                "source": str(boc.get("source") or "bank_of_canada_valet"),
                "state": str(boc.get("state") or "unavailable"),
                "provider_id": str(
                    boc.get("provider_id") or "bank_of_canada_valet_fx_reference_public"
                ),
                "retrieved_at": str(boc.get("retrieved_at") or "not refreshed"),
                "cache_path": str(boc.get("cache_path") or ""),
                "docs_url": str(boc.get("docs_url") or ""),
            },
            "summary": {
                "date": str(boc.get("date") or ""),
                "row_count": int(boc.get("row_count") or 0),
                "base": str(boc.get("base") or "CAD reference"),
                "usd": str(boc.get("usd") or ""),
                "eur": str(boc.get("eur") or ""),
                "gbp": str(boc.get("gbp") or ""),
                "jpy": str(boc.get("jpy") or ""),
                "chf": str(boc.get("chf") or ""),
            },
            "rows": boc.get("rows") if isinstance(boc.get("rows"), list) else [],
        },
        "quote_watchlist": {
            "status": {
                "source": str(
                    quote_watchlist.get("source") or "alphavantage_currency_exchange_rate"
                ),
                "state": str(quote_watchlist.get("state") or "key_required"),
                "provider_id": str(
                    quote_watchlist.get("provider_id")
                    or "alphavantage_global_quote_optional_key"
                ),
                "retrieved_at": str(quote_watchlist.get("retrieved_at") or "not refreshed"),
                "cache_path": str(quote_watchlist.get("cache_path") or ""),
                "docs_url": str(quote_watchlist.get("docs_url") or ""),
                "message": str(
                    quote_watchlist.get("message")
                    or "Store a local Alpha Vantage key before refreshing FX quotes."
                ),
            },
            "summary": {
                "pair": str(quote_watchlist.get("pair") or "EUR/USD"),
                "pairs": str(quote_watchlist.get("pairs") or "EUR/USD,USD/JPY,GBP/USD"),
                "rate": str(quote_watchlist.get("rate") or ""),
                "bid": str(quote_watchlist.get("bid") or ""),
                "ask": str(quote_watchlist.get("ask") or ""),
                "last_refreshed": str(quote_watchlist.get("last_refreshed") or ""),
                "row_count": int(quote_watchlist.get("row_count") or 0),
                "requested_count": int(quote_watchlist.get("requested_count") or 0),
                "cached_count": int(quote_watchlist.get("cached_count") or 0),
                "live_count": int(quote_watchlist.get("live_count") or 0),
                "stale_count": int(quote_watchlist.get("stale_count") or 0),
                "key_required_count": int(quote_watchlist.get("key_required_count") or 0),
            },
            "rows": (
                quote_watchlist.get("rows")
                if isinstance(quote_watchlist.get("rows"), list)
                else []
            ),
        },
        "rows": fx.get("rows") if isinstance(fx.get("rows"), list) else [],
    }


def _rates_view(research_summary: dict[str, Any]) -> dict[str, Any]:
    rates = research_summary.get("rates")
    rates = rates if isinstance(rates, dict) else {}
    sofr = rates.get("sofr") if isinstance(rates.get("sofr"), dict) else {}
    return {
        "status": {
            "source": str(rates.get("source") or "us_treasury_public"),
            "state": str(rates.get("state") or "unavailable"),
            "provider_id": str(rates.get("provider_id") or "us_treasury_yield_public"),
            "retrieved_at": str(rates.get("retrieved_at") or "not refreshed"),
            "cache_path": str(rates.get("cache_path") or ""),
            "docs_url": str(rates.get("docs_url") or ""),
        },
        "summary": {
            "latest_date": str(rates.get("latest_date") or ""),
            "tenor_count": int(rates.get("tenor_count") or 0),
            "two_year": str(rates.get("two_year") or ""),
            "ten_year": str(rates.get("ten_year") or ""),
            "thirty_year": str(rates.get("thirty_year") or ""),
            "slope_10y_2y": str(rates.get("slope_10y_2y") or ""),
        },
        "rows": rates.get("rows") if isinstance(rates.get("rows"), list) else [],
        "sofr": {
            "status": {
                "source": str(sofr.get("source") or "nyfed_sofr_public"),
                "state": str(sofr.get("state") or "unavailable"),
                "provider_id": str(sofr.get("provider_id") or "nyfed_sofr_public"),
                "retrieved_at": str(sofr.get("retrieved_at") or "not refreshed"),
                "cache_path": str(sofr.get("cache_path") or ""),
                "docs_url": str(sofr.get("docs_url") or ""),
            },
            "summary": {
                "latest_date": str(sofr.get("latest_date") or ""),
                "rate": str(sofr.get("rate") or ""),
                "volume_in_billions": str(sofr.get("volume_in_billions") or ""),
                "percentile_25": str(sofr.get("percentile_25") or ""),
                "percentile_75": str(sofr.get("percentile_75") or ""),
                "row_count": int(sofr.get("row_count") or 0),
                "quote_semantics": str(sofr.get("quote_semantics") or "reference_only"),
            },
            "rows": sofr.get("rows") if isinstance(sofr.get("rows"), list) else [],
        },
    }


def _panel_rows(panel: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    rows_by_symbol = {row["symbol"]: row for row in rows}
    return {**panel, "rows": [rows_by_symbol[symbol] for symbol in panel["symbols"] if symbol in rows_by_symbol]}


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


# A cache written this recently is treated as the live refresh it came from,
# not as a stale fallback that should alarm the reader.
FRESH_TICKER_CACHE_SECONDS = 300


def _cache_age_seconds(last_update: str) -> float | None:
    try:
        stamp = datetime.fromisoformat(last_update)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return (datetime.now(tz=UTC) - stamp).total_seconds()


def _status(
    *,
    source: str,
    state: str,
    last_update: str = "not refreshed",
    message: str = "",
    provider_id: str = "",
    cache_path: str = "",
    fallback_used: bool = False,
) -> dict[str, Any]:
    return {
        "source": source,
        "state": state,
        "last_update": last_update,
        "message": message,
        "provider_id": provider_id,
        "cache_path": cache_path,
        "fallback_used": fallback_used,
    }


def _decimal(raw: Any) -> Decimal | None:
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return "N/A"
    return f"{value.quantize(Decimal('0.0001'))}"


def _tenor_rate(tenors: list[Any], tenor: str) -> str:
    for row in tenors:
        if isinstance(row, dict) and row.get("tenor") == tenor:
            return str(row.get("rate") or "")
    return ""


def _slope(tenors: list[Any]) -> str:
    two_year = _decimal(_tenor_rate(tenors, "2Y"))
    ten_year = _decimal(_tenor_rate(tenors, "10Y"))
    if two_year is None or ten_year is None:
        return ""
    return f"{(ten_year - two_year).quantize(Decimal('0.01'))}"
