"""Read-only provider acquisition gate for future data breadth work."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any


PROVIDER_ACQUISITION_VERSION = "m22-provider-acquisition-gate-v1"
DOCS_CHECKED_AT = "2026-06-01"

PROVIDER_CANDIDATES: tuple[dict[str, Any], ...] = (
    {
        "candidate_id": "sec_xbrl_frames_public",
        "label": "SEC XBRL frames",
        "priority": 1,
        "status": "implemented_bounded_public_no_key",
        "asset_family": "Stocks",
        "runtime_role": "cross_company_fundamental_frames",
        "auth_mode": "public_no_key",
        # The frames API prefix used to sit here as if it were documentation.
        # Opened, it answers 404 — the path only resolves with a taxonomy, tag,
        # unit and period appended, and that is a response, not a page to read.
        "official_docs": [
            "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
        ],
        "quote_semantics": "not_quote",
        "cache_policy": {
            "path": "market_data/fundamentals/sec/frames/{taxonomy}/{tag}/{unit}/{period}.json",
            "ttl_seconds": 86400,
            "retention": "bounded tag/year/quarter frame snapshots",
        },
        "route_workflow_need": (
            "Markets Stocks and research-loop breadth need source-attributed cross-company "
            "fundamental context before any paid quote provider is considered."
        ),
        "implementation_gate": (
            "Use a small whitelist of tags/periods, SEC fair-access headers, source attribution, "
            "and reference/fundamental semantics only."
        ),
        "next_safe_action": (
            "Maintain bounded SEC frame cache/tests; Federal Reserve H.10 is now "
            "implemented as the next public no-key FX reference slice."
        ),
        "safety_class": "public_read_only_fundamentals",
    },
    {
        "candidate_id": "federal_reserve_h10_ddp_public",
        "label": "Federal Reserve H.10 Data Download Program",
        "priority": 2,
        "status": "implemented_public_no_key_reference",
        "asset_family": "FX",
        "runtime_role": "usd_fx_reference_rates",
        "auth_mode": "public_no_key",
        "official_docs": [
            "https://www.federalreserve.gov/datadownload/choose.aspx?rel=h10",
        ],
        "quote_semantics": "reference_only",
        "cache_policy": {
            "path": "market_data/fx/federal_reserve/h10_reference_rates.json",
            "ttl_seconds": 86400,
            "retention": "latest H.10 reference-rate package snapshot",
        },
        "route_workflow_need": (
            "FX already has ECB reference rates; H.10 can broaden USD reference context after "
            "the next Stocks fundamental breadth slice."
        ),
        "implementation_gate": (
            "Use published CSV/XML packages only, preserve Federal Reserve attribution, and never "
            "treat reference rates as executable FX quotes."
        ),
        "next_safe_action": (
            "Maintain H.10 FX reference cache/tests; choose another public no-key "
            "reference slice before optional-key or paid providers."
        ),
        "safety_class": "public_read_only_reference_data",
    },
    {
        "candidate_id": "eurostat_hicp_public",
        "label": "Eurostat HICP public macro data",
        "priority": 3,
        "status": "implemented_public_no_key_reference",
        "asset_family": "Indexes",
        "runtime_role": "euro_area_inflation_context",
        "auth_mode": "public_no_key",
        "official_docs": [
            "https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-detailed-guidelines/api-statistics",
            "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_midx/default/table",
        ],
        "quote_semantics": "not_quote",
        "cache_policy": {
            "path": "market_data/macro/eurostat/hicp_ea20_cp00_i15.json",
            "ttl_seconds": 86400,
            "retention": "bounded Eurostat HICP EA20 monthly index observations",
        },
        "route_workflow_need": (
            "Markets Indexes/Regional need more official public macro context beyond "
            "U.S.-centric labor/inflation and DBnomics proxy rows."
        ),
        "implementation_gate": (
            "Use only bounded Eurostat Statistics API HICP rows with lastTimePeriod=3; "
            "do not treat macro reference rows as quotes or trading signals."
        ),
        "next_safe_action": (
            "Maintain Eurostat HICP cache/tests; do not broaden datasets until a concrete "
            "route workflow needs the additional macro context."
        ),
        "safety_class": "public_read_only_macro",
    },
    {
        "candidate_id": "twelve_data_quote_optional_key",
        "label": "Twelve Data Quote",
        "priority": 4,
        "status": "implemented_bounded_optional_key",
        "asset_family": "Multi-Asset",
        "runtime_role": "secondary_quote_watchlist",
        "auth_mode": "optional_local_key",
        "official_docs": [
            "https://twelvedata.com/docs/llms",
            "https://twelvedata.com/docs/llms/market-data",
        ],
        "quote_semantics": "quote_not_orderable",
        "cache_policy": {
            "path": "market_data/quotes/twelve_data/{symbol}.json",
            "ttl_seconds": 86400,
            "retention": "bounded AAPL/SPY/EURUSD quote snapshots",
        },
        "route_workflow_need": (
            "Markets quote breadth needs a comparison-gated optional-key provider "
            "that is separate from Alpha Vantage without implying live orderability."
        ),
        "implementation_gate": (
            "Use only the official /quote endpoint with an already stored local key; "
            "do not sign up, collect unused keys, use batch/paid endpoints, or join "
            "public no-key refresh jobs."
        ),
        "next_safe_action": "Keep bounded cache/tests; do not broaden symbols without a concrete route need.",
        "safety_class": "optional_local_secret_data_provider",
    },
    {
        "candidate_id": "bea_regional_optional_key",
        "label": "BEA Regional API",
        "priority": 5,
        "status": "implemented_bounded_optional_key",
        "asset_family": "Regional",
        "runtime_role": "regional_macro_context",
        "auth_mode": "optional_local_key",
        "official_docs": [
            "https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf",
        ],
        "quote_semantics": "not_quote",
        "cache_policy": {
            "path": "market_data/regional/bea/SAGDP9N_LINE1_STATE.json",
            "ttl_seconds": 86400,
            "retention": "bounded BEA Regional real GDP state context rows",
        },
        "route_workflow_need": (
            "Regional route depth needs official state GDP context without turning "
            "regional macro data into executable quotes."
        ),
        "implementation_gate": (
            "Implemented only behind the local secret gate; do not sign up, collect "
            "unused keys, or expose UserID values."
        ),
        "next_safe_action": "Use Markets BEA refresh only after a user-owned local key exists.",
        "safety_class": "optional_local_secret_data_provider",
    },
    {
        "candidate_id": "census_api_optional_key",
        "label": "U.S. Census Data API",
        "priority": 6,
        "status": "implemented_bounded_optional_key",
        "asset_family": "Regional",
        "runtime_role": "demographic_economic_context",
        "auth_mode": "optional_local_key",
        "official_docs": [
            "https://www.census.gov/data/developers/guidance/api-user-guide.API_Key.html",
            "https://api.census.gov/data/2023/acs/acs5/profile.html",
            "https://api.census.gov/data/2023/acs/acs5/profile/variables.html",
        ],
        "quote_semantics": "not_quote",
        "cache_policy": {
            "path": "market_data/regional/census/acs5_profile_state_2023.json",
            "ttl_seconds": 86400,
            "retention": "bounded ACS 5-year profile state demographic/economic rows",
        },
        "route_workflow_need": (
            "Regional route depth needs official state-level demographic/economic "
            "context, and current official guidance says API calls require a key."
        ),
        "implementation_gate": (
            "Implemented only behind the local secret gate with bounded ACS profile "
            "variables; do not sign up, collect unused keys, or expose key values."
        ),
        "next_safe_action": "Use Markets Census refresh only after a user-owned local key exists.",
        "safety_class": "optional_local_secret_data_provider",
    },
    {
        "candidate_id": "nyfed_sofr_public",
        "label": "New York Fed SOFR Reference Rate",
        "priority": 6,
        "status": "implemented_public_no_key_reference",
        "asset_family": "Bonds/Rates",
        "runtime_role": "overnight_reference_rate",
        "auth_mode": "public_no_key",
        "official_docs": [
            "https://www.newyorkfed.org/markets/reference-rates/sofr",
            "https://markets.newyorkfed.org/static/docs/markets-api.html",
        ],
        "quote_semantics": "reference_only",
        "cache_policy": {
            "path": "market_data/rates/nyfed/sofr.json",
            "ttl_seconds": 86400,
            "retention": "latest SOFR reference-rate rows",
        },
        "route_workflow_need": (
            "Bonds/Rates needs another official public no-key reference source "
            "without mislabeling overnight reference rates as executable quotes."
        ),
        "implementation_gate": (
            "Use only New York Fed public Markets API reference-rate rows, preserve "
            "source attribution, and keep SOFR reference-only."
        ),
        "next_safe_action": (
            "Maintain SOFR cache/tests; do not turn reference rates into orderable "
            "fixed-income or funding quotes."
        ),
        "safety_class": "public_read_only_reference_data",
    },
    {
        "candidate_id": "bank_of_canada_valet_fx_reference_public",
        "label": "Bank of Canada Valet FX Reference Rates",
        "priority": 7,
        "status": "implemented_public_no_key_reference",
        "asset_family": "FX",
        "runtime_role": "cad_fx_reference_rates",
        "auth_mode": "public_no_key",
        "official_docs": [
            "https://www.bankofcanada.ca/valet/docs",
            "https://www.bankofcanada.ca/rates/exchange/",
            "https://www.bankofcanada.ca/rates/exchange/background-information-on-foreign-exchange-rates/",
        ],
        "quote_semantics": "reference_only",
        "cache_policy": {
            "path": "market_data/fx/bank_of_canada/valet_fx_reference_rates.json",
            "ttl_seconds": 86400,
            "retention": "latest bounded Valet CAD reference-rate observations",
        },
        "route_workflow_need": (
            "FX needs another official public no-key reference source beyond ECB EUR "
            "and Federal Reserve H.10 USD rows without becoming a spot-trading feed."
        ),
        "implementation_gate": (
            "Use only bounded Bank of Canada Valet observations, preserve source "
            "attribution, and keep indicative FX rates reference-only."
        ),
        "next_safe_action": (
            "Maintain BoC FX cache/tests; do not turn CAD reference rates into "
            "orderable FX quotes."
        ),
        "safety_class": "public_read_only_reference_data",
    },
    {
        "candidate_id": "cftc_cot_legacy_public",
        "label": "CFTC Commitments of Traders Legacy Futures",
        "priority": 8,
        "status": "implemented_public_no_key_context",
        "asset_family": "Commodities",
        "runtime_role": "positioning_context",
        "auth_mode": "public_no_key",
        "official_docs": [
            "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
            "https://dev.socrata.com/foundry/publicreporting.cftc.gov/6dca-aqww",
        ],
        "quote_semantics": "not_quote",
        "cache_policy": {
            "path": "market_data/commodities/cftc/cot_legacy_futures.json",
            "ttl_seconds": 604800,
            "retention": "latest bounded weekly COT commodity positioning rows",
        },
        "route_workflow_need": (
            "Commodities needs official public positioning context alongside monthly "
            "reference prices without enabling spot/futures execution."
        ),
        "implementation_gate": (
            "Use only bounded CFTC public reporting API rows, preserve CFTC attribution, "
            "and never treat positioning data as executable commodity quotes."
        ),
        "next_safe_action": (
            "Maintain CFTC COT cache/tests; future commodity execution data still needs "
            "a separate quote/provider and safety contract."
        ),
        "safety_class": "public_read_only_commodity_positioning",
    },
    {
        "candidate_id": "stooq_public_quote_snapshot",
        "label": "Stooq Public Quote Snapshot",
        "priority": 9,
        "status": "implemented_bounded_public_no_key_snapshot",
        "asset_family": "Multi-Asset",
        "runtime_role": "delayed_public_quote_snapshot",
        "auth_mode": "public_no_key",
        "official_docs": [
            "https://stooq.com/q/?s=^spx",
            "https://stooq.com/db/h/",
        ],
        "quote_semantics": "quote_not_orderable",
        "cache_policy": {
            "path": "market_data/quotes/stooq/{symbol}.json",
            "ttl_seconds": 900,
            "retention": "bounded AAPL.US/SPY.US/^SPX/EURUSD quote snapshots",
        },
        "route_workflow_need": (
            "Markets still needs a public no-key non-crypto quote snapshot lane that is "
            "separate from optional-key Alpha Vantage and Twelve Data."
        ),
        "implementation_gate": (
            "Use only bounded current CSV quote snapshots. Historical Stooq CSV downloads "
            "now require a CAPTCHA/API-link gate, so historical download is recorded but "
            "not implemented."
        ),
        "next_safe_action": (
            "Maintain bounded snapshot cache/tests; do not broaden symbols, scrape pages, "
            "or use the historical CAPTCHA/API-link path without a new reviewed gate."
        ),
        "safety_class": "public_read_only_market_data",
    },
    {
        "candidate_id": "nasdaq_trader_symbol_directory_public",
        "label": "Nasdaq Trader Symbol Directory",
        "priority": 10,
        "status": "implemented_public_no_key_reference",
        "asset_family": "Stocks",
        "runtime_role": "symbol_directory",
        "auth_mode": "public_no_key",
        "official_docs": [
            "https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs",
            "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
            "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
        ],
        "quote_semantics": "not_quote",
        "cache_policy": {
            "path": "market_data/reference/nasdaq_trader/symbol_directory.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized Nasdaq-listed and other-listed symbol directory rows",
        },
        "route_workflow_need": (
            "Markets and AI Agent symbol discovery need an official no-key listed-security "
            "reference source before any broader quote or provider routing work."
        ),
        "implementation_gate": (
            "Use only the official downloadable text files, preserve source-file attribution, "
            "filter test issues, and keep rows reference-only."
        ),
        "next_safe_action": (
            "Maintain symbol-directory cache/tests; do not treat rows as quotes, broker "
            "availability, balances, or executable instruments."
        ),
        "safety_class": "public_read_only_reference_data",
    },
    {
        "candidate_id": "moex_iss_delayed_quote_snapshot",
        "label": "MOEX ISS Delayed Quote Snapshot",
        "priority": 11,
        "status": "implemented_bounded_public_no_key_snapshot",
        "asset_family": "Multi-Asset",
        "runtime_role": "delayed_public_quote_snapshot",
        "auth_mode": "public_no_key",
        "official_docs": [
            "https://www.moex.com/a2920",
            "https://www.moex.com/files/4be999zbzp80bx2bgmwayrtyx0",
        ],
        "quote_semantics": "quote_not_orderable",
        "cache_policy": {
            "path": "market_data/quotes/moex/{symbol}.json",
            "ttl_seconds": 900,
            "retention": "bounded SBER/GAZP/MOEX delayed quote snapshots",
        },
        "route_workflow_need": (
            "Markets still needs more public no-key non-crypto quote breadth beyond "
            "U.S.-centric Stooq snapshots and optional-key providers."
        ),
        "implementation_gate": (
            "Use only bounded unauthenticated ISS securities marketdata requests. "
            "Do not request orderbooks, authenticated real-time data, private accounts, or broker actions."
        ),
        "next_safe_action": (
            "Maintain bounded delayed snapshot cache/tests; do not broaden symbols or "
            "use subscriber-only ISS data without a new reviewed gate."
        ),
        "safety_class": "public_read_only_market_data",
    },
    {
        "candidate_id": "twse_openapi_daily_quote_snapshot",
        "label": "TWSE OpenAPI Daily Quote Snapshot",
        "priority": 12,
        "status": "implemented_bounded_public_no_key_snapshot",
        "asset_family": "Stocks",
        "runtime_role": "twse_daily_quote_snapshot",
        "auth_mode": "public_no_key",
        "official_docs": [
            "https://openapi.twse.com.tw/",
            "https://openapi.twse.com.tw/v1/swagger.json",
        ],
        "quote_semantics": "quote_not_orderable",
        "cache_policy": {
            "path": "market_data/quotes/twse/{symbol}.json",
            "ttl_seconds": 86400,
            "retention": "bounded 2330/2317/0050 daily quote snapshots",
        },
        "route_workflow_need": (
            "Markets still needs more official public no-key equity quote breadth beyond "
            "U.S.-centric and MOEX snapshots while staying non-orderable."
        ),
        "implementation_gate": (
            "Use only the official TWSE OpenAPI STOCK_DAY_ALL daily listed-stock rows. "
            "Do not add realtime feeds, broker/private account access, balances, or order routing."
        ),
        "next_safe_action": (
            "Maintain bounded daily snapshot cache/tests; do not broaden into realtime "
            "or executable Taiwan equity workflows without a separate reviewed gate."
        ),
        "safety_class": "public_read_only_market_data",
    },
    {
        "candidate_id": "cboe_delayed_quotes_gate",
        "label": "Cboe Delayed Quotes Gate",
        "priority": 13,
        "status": "blocked_official_terms",
        "asset_family": "Stocks",
        "runtime_role": "delayed_public_quote_terms_gate",
        "auth_mode": "public_no_key",
        "official_docs": [
            "https://www.cboe.com/delayed_quotes/api/",
            "https://www.cboe.com/delayed_quotes/",
        ],
        "quote_semantics": "quote_blocked_by_terms",
        "cache_policy": {
            "path": "",
            "ttl_seconds": 0,
            "retention": "not cached; no adapter until licensed or explicitly permitted",
        },
        "route_workflow_need": (
            "Markets quote breadth needs documented public-source exclusions as much as "
            "implemented sources so AI Agents do not attempt unsafe quote scraping."
        ),
        "implementation_gate": (
            "Official delayed-quote pages are suitable for human lookup but are not approved "
            "as an automated local quote adapter. Do not crawl pages, reverse-engineer page "
            "payloads, or use the delayed-quote API for unattended data extraction."
        ),
        "next_safe_action": (
            "Keep as a blocked provider-entry record; use implemented Stooq/MOEX/public "
            "reference lanes or a reviewed licensed provider instead."
        ),
        "safety_class": "blocked_public_quote_terms_gate",
    },
    {
        "candidate_id": "iex_tops_market_data_gate",
        "label": "IEX TOPS Market Data Gate",
        "priority": 14,
        "status": "blocked_official_terms",
        "asset_family": "Stocks",
        "runtime_role": "realtime_exchange_top_of_book_terms_gate",
        "auth_mode": "subscriber_agreement_required",
        "official_docs": [
            "https://www.iexexchange.io/resources/trading/market-data",
            "https://www.iex.io/products/market-data-connectivity",
            "https://www.iex.io/resources/trading/fee-schedule",
        ],
        "quote_semantics": "quote_blocked_by_terms",
        "cache_policy": {
            "path": "",
            "ttl_seconds": 0,
            "retention": "not cached; no adapter until subscription agreements permit access",
        },
        "route_workflow_need": (
            "Markets quote breadth needs an explicit record that current IEX TOPS/DEEP "
            "feeds are real-time exchange data products, not an unattended public no-key "
            "REST quote source."
        ),
        "implementation_gate": (
            "Official IEX docs require completed market-data agreements/forms before "
            "accessing DEEP or TOPS real-time feeds. Do not reuse legacy IEX Cloud/no-key "
            "API assumptions, decode large HIST PCAP files, or add TOPS/DEEP adapters "
            "without a separate licensed data contract."
        ),
        "next_safe_action": (
            "Keep as a blocked provider-entry record; use implemented bounded quote "
            "snapshots or optional local-key lanes instead of IEX TOPS/DEEP until a "
            "licensed agreement-backed milestone exists."
        ),
        "safety_class": "blocked_exchange_market_data_terms_gate",
    },
    {
        "candidate_id": "finnhub_equity_quote_optional_key",
        "label": "Finnhub Equity Quote",
        "priority": 15,
        "status": "implemented_bounded_optional_key",
        "asset_family": "Stocks",
        "runtime_role": "secondary_equity_quote_watchlist",
        "auth_mode": "optional_local_key",
        "official_docs": [
            "https://finnhub.io/docs/api/quote",
            "https://finnhub.io/docs/api/rate-limit",
        ],
        "quote_semantics": "quote_not_orderable",
        "cache_policy": {
            "path": "market_data/quotes/finnhub/{symbol}.json",
            "ttl_seconds": 86400,
            "retention": "bounded AAPL/MSFT/NVDA/SPY quote snapshots",
        },
        "route_workflow_need": (
            "Markets quote breadth needs a second optional-key equity quote lane "
            "separate from Alpha Vantage and Twelve Data without implying orderability."
        ),
        "implementation_gate": (
            "Use only the official /quote endpoint through the local secret gate with "
            "an already stored local key; do not sign up, collect unused keys, use paid "
            "endpoints, or join public no-key refresh jobs."
        ),
        "next_safe_action": (
            "Keep bounded cache/tests; do not broaden symbols or request account/trading "
            "features without a separate reviewed gate."
        ),
        "safety_class": "optional_local_secret_data_provider",
    },
    {
        "candidate_id": "fmp_stock_quote_optional_key",
        "label": "FMP Stock Quote",
        "priority": 16,
        "status": "implemented_bounded_optional_key",
        "asset_family": "Stocks",
        "runtime_role": "tertiary_stock_quote_watchlist",
        "auth_mode": "optional_local_key",
        "official_docs": [
            "https://site.financialmodelingprep.com/developer/docs/stable/quote",
            "https://site.financialmodelingprep.com/developer/docs",
        ],
        "quote_semantics": "quote_not_orderable",
        "cache_policy": {
            "path": "market_data/quotes/fmp/{symbol}.json",
            "ttl_seconds": 86400,
            "retention": "bounded AAPL/MSFT/NVDA/SPY quote snapshots",
        },
        "route_workflow_need": (
            "Markets quote breadth needs another official optional-key stock quote lane "
            "without treating provider availability as broker/orderability."
        ),
        "implementation_gate": (
            "Use only the official stable quote endpoint through the local secret gate "
            "with an already stored local key; do not sign up, collect unused keys, use "
            "paid endpoints, or join public no-key refresh jobs."
        ),
        "next_safe_action": (
            "Keep bounded cache/tests; do not broaden symbols, use MCP/account features, "
            "or request trading/account APIs without a separate reviewed gate."
        ),
        "safety_class": "optional_local_secret_data_provider",
    },
    {
        "candidate_id": "openfigi_identifier_mapping_public",
        "label": "OpenFIGI Identifier Mapping",
        "priority": 17,
        "status": "implemented_public_no_key_reference",
        "asset_family": "Stocks",
        "runtime_role": "identifier_mapping",
        "auth_mode": "public_no_key",
        # The v3 mapping endpoint is POST-only and answers 405 to anyone who
        # opens it; the documentation is the page above it.
        "official_docs": [
            "https://www.openfigi.com/api/documentation",
        ],
        "quote_semantics": "not_quote",
        "cache_policy": {
            "path": "market_data/reference/openfigi/mapping.json",
            "ttl_seconds": 86400,
            "retention": "bounded AAPL/MSFT/SPY ticker-to-FIGI mapping rows",
        },
        "route_workflow_need": (
            "Markets and AI Agent symbol resolution need a public identifier-mapping "
            "lane that complements Nasdaq Trader rows without implying quote coverage."
        ),
        "implementation_gate": (
            "Use only bounded OpenFIGI v3 mapping jobs without an API key, preserve "
            "identifier/reference semantics, and do not collect unused optional keys."
        ),
        "next_safe_action": (
            "Maintain bounded mapping cache/tests; do not treat FIGI rows as prices, "
            "broker availability, balances, or executable instruments."
        ),
        "safety_class": "public_read_only_reference_data",
    },
    {
        "candidate_id": "nasdaq_data_link_dataset_gate",
        "label": "Nasdaq Data Link dataset gate",
        "priority": 18,
        "status": "blocked_dataset_specific_gate",
        "asset_family": "Cross-asset",
        "runtime_role": "dataset_catalog_gate",
        "auth_mode": "account_or_dataset_subscription_required",
        "official_docs": [
            "https://docs.data.nasdaq.com/docs/getting-started",
            "https://docs.data.nasdaq.com/docs/data-organization",
            "https://docs.data.nasdaq.com/v1.0/docs/getting-started",
        ],
        "quote_semantics": "dataset_specific_not_approved",
        "cache_policy": {
            "path": "",
            "ttl_seconds": 0,
            "retention": "no cache; record-only provider-entry gate",
        },
        "route_workflow_need": (
            "Provider breadth needs a visible gate for Nasdaq Data Link because many "
            "financial/economic datasets are product-specific, account-keyed, or premium."
        ),
        "implementation_gate": (
            "Do not add an adapter, signup flow, bundled key, crawler, paid dataset, "
            "or broad catalog integration until a concrete free dataset product page, "
            "auth mode, API route, cache schema, quote semantics, and route need are "
            "reviewed in a separate provider-entry slice."
        ),
        "next_safe_action": (
            "Keep this as a blocked provider-entry record; use direct official public "
            "sources first when available instead of collecting a Nasdaq Data Link key."
        ),
        "safety_class": "blocked_account_dataset_gate",
    },
    {
        "candidate_id": "jpx_jquants_market_data_gate",
        "label": "JPX / J-Quants market data gate",
        "priority": 19,
        "status": "blocked_account_plan_gate",
        "asset_family": "Stocks",
        "runtime_role": "japan_equity_market_data_gate",
        "auth_mode": "api_key_or_plan_required",
        "official_docs": [
            "https://jpx-jquants.com/en",
            "https://www.jpx.co.jp/english/corporate/news/news-releases/6020/20260119.html",
            "https://www.jpx.co.jp/english/markets/data-catalog/",
            "https://www.jpx.co.jp/english/markets/statistics-equities/price/",
        ],
        "quote_semantics": "quote_blocked_by_account_plan",
        "cache_policy": {
            "path": "",
            "ttl_seconds": 0,
            "retention": "no cache; record-only provider-entry gate",
        },
        "route_workflow_need": (
            "Markets quote breadth needs Japan equity coverage evidence, but current "
            "official JPX/J-Quants surfaces are account/API-key, plan, portal, or "
            "monthly-file workflows rather than a reviewed public no-key quote adapter."
        ),
        "implementation_gate": (
            "Do not add a J-Quants adapter, API-key prompt, CSV bulk downloader, portal "
            "crawler, monthly quotation parser, cache, refresh row, or source coverage "
            "until a separate slice defines a concrete allowed dataset, auth mode, "
            "cache schema, quote semantics, route need, and no-subscription boundary."
        ),
        "next_safe_action": (
            "Keep this as a blocked provider-entry record; use implemented public "
            "snapshot/reference lanes first or run a new official-doc gate for a concrete "
            "Japan equity dataset."
        ),
        "safety_class": "blocked_account_plan_market_data_gate",
    },
    {
        "candidate_id": "yahoo_finance_market_data_gate",
        "label": "Yahoo Finance market data gate",
        "priority": 20,
        "status": "blocked_terms_credentials_gate",
        "asset_family": "Multi-Asset",
        "runtime_role": "unofficial_quote_endpoint_gate",
        "auth_mode": "application_id_or_api_credentials_required",
        "official_docs": [
            "https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html",
            "https://legal.yahoo.com/us/en/yahoo/guidelines/ydn/index.html",
            "https://legal.yahoo.com/us/en/yahoo/privacy/products/developer/",
            "https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apitnc/index.html",
        ],
        "quote_semantics": "quote_blocked_by_terms_credentials",
        "cache_policy": {
            "path": "",
            "ttl_seconds": 0,
            "retention": "no cache; record-only provider-entry gate",
        },
        "route_workflow_need": (
            "Markets quote breadth needs a visible gate for Yahoo Finance because "
            "common query endpoints are often treated as public no-key quote APIs, "
            "but current official Yahoo API materials route API usage through "
            "application identity, API documentation, credentials, and usage limits."
        ),
        "implementation_gate": (
            "Do not add a Yahoo Finance adapter, query endpoint crawler, chart/quote "
            "scraper, crumb/cookie flow, cache, refresh row, or source coverage row "
            "until Yahoo publishes or grants a concrete finance market-data API "
            "contract with auth mode, route need, cache schema, quote semantics, "
            "display/retention terms, and no-subscription boundary reviewed."
        ),
        "next_safe_action": (
            "Keep this as a blocked provider-entry record; use implemented official "
            "public/optional-key quote lanes first or run a separate approved Yahoo "
            "finance API contract review if official finance API access becomes "
            "available."
        ),
        "safety_class": "blocked_terms_credentials_market_data_gate",
    },
)


def _actionable_candidate_status(status: str) -> bool:
    return not (
        status.startswith("implemented")
        or status.startswith("blocked")
        or status.startswith("deferred")
    )


def provider_acquisition_gate_payload() -> dict[str, Any]:
    """Return ranked provider candidates without signing up, fetching, or mutating state."""

    candidates = [dict(candidate) for candidate in PROVIDER_CANDIDATES]
    status_counts = Counter(str(candidate.get("status") or "") for candidate in candidates)
    auth_counts = Counter(str(candidate.get("auth_mode") or "") for candidate in candidates)
    next_candidate = next(
        (
            candidate
            for candidate in candidates
            if _actionable_candidate_status(str(candidate.get("status") or ""))
        ),
        {},
    )
    implemented_count = sum(
        count for status, count in status_counts.items() if str(status).startswith("implemented")
    )
    blocked_count = sum(
        count for status, count in status_counts.items() if str(status).startswith("blocked")
    )
    approved_next_count = status_counts.get("approved_next_public_no_key", 0)
    resume_contract = _resume_contract(
        candidates=candidates,
        next_candidate=next_candidate,
        implemented_count=implemented_count,
        blocked_count=blocked_count,
        approved_next_count=approved_next_count,
    )
    quote_breadth_closure = _quote_breadth_closure(
        candidates=candidates,
        resume_contract=resume_contract,
        blocked_count=blocked_count,
        approved_next_count=approved_next_count,
    )
    return {
        "generated_at": _utc_now(),
        "mode": "read_only_provider_acquisition_gate",
        "version": PROVIDER_ACQUISITION_VERSION,
        "docs_checked_at": DOCS_CHECKED_AT,
        "summary": {
            "candidate_count": len(candidates),
            "public_no_key_count": auth_counts.get("public_no_key", 0),
            "optional_local_key_count": auth_counts.get("optional_local_key", 0),
            "approved_next_count": approved_next_count,
            "implemented_count": implemented_count,
            "deferred_optional_key_count": status_counts.get("deferred_optional_key", 0),
            "blocked_count": blocked_count,
            "next_candidate_id": str(next_candidate.get("candidate_id") or ""),
            "next_candidate_status": str(next_candidate.get("status") or ""),
            "resume_state": str(resume_contract["state"]),
            "requires_official_research": bool(
                resume_contract["requires_official_docs_refresh"]
            ),
            "implementation_allowed": bool(resume_contract["implementation_allowed"]),
        },
        "resume_contract": resume_contract,
        "quote_breadth_closure": quote_breadth_closure,
        "candidates": candidates,
        "rules": {
            "public_no_key_first": True,
            "optional_keys_only_with_immediate_route_need": True,
            "no_unused_key_hoarding": True,
            "paid_or_plan_gated_activation": False,
            "broker_or_live_provider_activation": False,
        },
        "stop_gates": [
            "captcha",
            "2fa",
            "payment",
            "identity_verification",
            "security_alert",
            "broker_exchange_private_account",
            "live_order",
            "destructive_action",
        ],
        "safety": {
            "read_only": True,
            "external_network_fetch": False,
            "provider_signup": False,
            "secret_values_returned": False,
            "paid_provider_enabled": False,
            "live_trading": False,
            "installed_source_read": False,
        },
    }


def _quote_breadth_closure(
    *,
    candidates: list[dict[str, Any]],
    resume_contract: dict[str, Any],
    blocked_count: int,
    approved_next_count: int,
) -> dict[str, Any]:
    implemented_quote_candidates = [
        candidate
        for candidate in candidates
        if str(candidate.get("status") or "").startswith("implemented")
        and str(candidate.get("quote_semantics") or "") == "quote_not_orderable"
    ]
    blocked_gate_candidates = [
        candidate
        for candidate in candidates
        if str(candidate.get("status") or "").startswith("blocked")
    ]
    return {
        "mode": "non_live_quote_breadth_closure_v1",
        "status": "closed_until_new_official_provider_gate",
        "implementation_allowed": False,
        "next_safe_action": (
            "Run a new official-doc provider-entry research gate before adapter work."
        ),
        "non_live_scope": {
            "orderable_quotes": False,
            "executable_quotes": False,
            "broker_routing": False,
            "real_balances": False,
            "live_orders": False,
        },
        "provider_backlog": {
            "resume_state": str(resume_contract.get("state") or ""),
            "candidate_count": len(candidates),
            "implemented_or_blocked_count": int(
                resume_contract.get("implemented_or_blocked_count") or 0
            ),
            "approved_next_count": approved_next_count,
            "blocked_count": blocked_count,
            "blocked_market_data_gate_count": len(blocked_gate_candidates),
            "implemented_quote_lane_count": len(implemented_quote_candidates),
        },
        "blocked_gate_ids": [
            str(candidate.get("candidate_id") or "")
            for candidate in blocked_gate_candidates
        ],
        "implemented_quote_candidate_ids": [
            str(candidate.get("candidate_id") or "")
            for candidate in implemented_quote_candidates
        ],
        "agent_rule": (
            "Treat the current provider backlog as finite evidence, not a loop to "
            "retry blocked providers. Broad executable or orderable quote parity is "
            "outside the current non-live/no-subscription boundary until a concrete "
            "provider-entry gate approves a source."
        ),
        "stop_gates": [
            "captcha",
            "2fa",
            "payment",
            "identity_verification",
            "security_alert",
            "broker_exchange_private_account",
            "live_order",
            "destructive_action",
        ],
    }


def _resume_contract(
    *,
    candidates: list[dict[str, Any]],
    next_candidate: dict[str, Any],
    implemented_count: int,
    blocked_count: int,
    approved_next_count: int,
) -> dict[str, Any]:
    has_next_candidate = bool(next_candidate.get("candidate_id"))
    candidate_count = len(candidates)
    exhausted = not has_next_candidate and candidate_count == implemented_count + blocked_count
    state = "candidate_ready" if has_next_candidate else "research_required"
    if exhausted:
        state = "backlog_exhausted_needs_research"
    return {
        "state": state,
        "implementation_allowed": has_next_candidate,
        "requires_official_docs_refresh": not has_next_candidate,
        "next_candidate_id": str(next_candidate.get("candidate_id") or ""),
        "next_candidate_status": str(next_candidate.get("status") or ""),
        "approved_next_count": approved_next_count,
        "implemented_or_blocked_count": implemented_count + blocked_count,
        "candidate_count": candidate_count,
        "blocked_count": blocked_count,
        "next_safe_step": (
            "Implement the approved next candidate after focused tests."
            if has_next_candidate
            else "Run a new provider-entry research gate before implementation."
        ),
        "anti_stall_rule": (
            "Do not add another provider adapter, signup flow, optional-key prompt, "
            "or crawler until official docs, auth mode, quote semantics, cache policy, "
            "and route need are recorded in this gate."
        ),
        "do_not_retry_status_prefixes": [
            "implemented",
            "blocked",
            "deferred",
        ],
    }


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
