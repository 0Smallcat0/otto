"""Provider registry, cache freshness, and clean-room data-source gates."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DOCS_CHECKED_AT = "2026-05-26"
CACHE_STATE_ACTIVE = "active"
ERROR_STATES = (
    "unavailable",
    "rate_limited",
    "key_required",
    "plan_required",
    "stale_cache",
    "disabled_by_safety",
    "retired",
)
ENTRY_REQUIRED_FIELDS = (
    "provider_id",
    "label",
    "coverage",
    "official_docs",
    "auth_mode",
    "rate_limit",
    "terms_risk",
    "cache_policy",
    "schemas",
    "fallback",
    "safety_class",
    "source_attribution",
    "tests",
    "secret_gate",
)

PROVIDER_ENTRY_TEMPLATE: dict[str, Any] = {
    "required_fields": list(ENTRY_REQUIRED_FIELDS),
    "required_error_states": list(ERROR_STATES),
    "adapter_gate": (
        "No adapter is implementation-ready until official docs, auth mode, rate limit, "
        "terms risk, cache/TTL, normalized schema, fallback behavior, tests, UI attribution, "
        "and safety class are recorded."
    ),
    "secret_gate": (
        "Optional-key providers stay disabled until local secret storage is designed, tested, "
        "reviewed, and proven not to write secrets to repo, logs, screenshots, or commits."
    ),
}

ERROR_STATE_CATALOG: dict[str, dict[str, str]] = {
    "unavailable": {
        "label": "Unavailable",
        "meaning": "Provider is implemented or planned, but no current runtime payload is available.",
        "ui_action": "Show provider, source, cache path, and retry/setup detail instead of empty copy.",
    },
    "rate_limited": {
        "label": "Rate limited",
        "meaning": "Provider rejected or deferred requests because request limits were hit.",
        "ui_action": "Show last successful cache and backoff/retry guidance.",
    },
    "key_required": {
        "label": "Key required",
        "meaning": "Provider requires a user-owned local credential before it can run.",
        "ui_action": "Keep disabled until the local secret-storage contract exists.",
    },
    "plan_required": {
        "label": "Plan required",
        "meaning": "Provider capability depends on a paid or entitlement-gated plan.",
        "ui_action": "Record option only; do not purchase, activate, or imply availability.",
    },
    "stale_cache": {
        "label": "Stale cache",
        "meaning": "Local cache exists but is older than the provider TTL.",
        "ui_action": "Use the cache only with visible source, age, and retry state.",
    },
    "disabled_by_safety": {
        "label": "Disabled by safety",
        "meaning": "Capability is blocked by clean-room, credential, or live-trading safety gates.",
        "ui_action": "Render disabled controls and explain the missing safety contract.",
    },
    "retired": {
        "label": "Retired",
        "meaning": "The upstream endpoint was permanently closed by the provider; a successor source covers the capability.",
        "ui_action": "Point at the successor action instead of retrying a dead endpoint.",
    },
}

PROVIDER_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "provider_id": "binance_spot_public",
        "label": "Binance Spot public market data",
        "adapter_id": "binance_spot_public",
        "implementation_status": "implemented",
        "coverage": ["crypto", "24hr ticker", "watchlist quotes", "order book", "recent trades", "klines"],
        "official_docs": [
            "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints",
            "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/limits",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": (
            "24hr ticker symbols 1-20 request weight 2; HTTP 429 requires backoff and "
            "Retry-After handling."
        ),
        "terms_risk": "Exchange market-data display requires source attribution; market data only.",
        "cache_policy": {
            "cache_id": "market_crypto_latest",
            "path": "market_data/crypto_latest.json",
            "ttl_seconds": 60,
            "retention": "latest snapshot",
            "stale_behavior": "show stale cache with last successful refresh",
            "detail_cache_id": "crypto_public_detail",
            "detail_path": "market_data/crypto/{symbol}/{timeframe}.json",
            "detail_ttl_seconds": 30,
        },
        "schemas": ["ticker_24hr_rows", "market_status", "order_book_depth", "recent_trades", "closed_klines"],
        "fallback": "Use stale cache if present; offline fixture is only an explicit fallback.",
        "safety_class": "public_read_only_market_data",
        "source_attribution": {
            "name": "Binance Spot",
            "url": "https://api.binance.com/api/v3",
        },
        "tests": ["provider_cache_state", "crypto_detail_provider_chain", "market_cache_primary_runtime", "source_wall"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "kraken_public_market_data",
        "label": "Kraken public market data",
        "adapter_id": "kraken_public_market_data",
        "implementation_status": "implemented_fallback",
        "coverage": ["crypto", "ticker", "OHLC", "order book", "recent trades"],
        "official_docs": [
            "https://docs.kraken.com/api/docs/rest-api/get-ticker-information/",
            "https://docs.kraken.com/api/docs/rest-api/get-ohlc-data/",
            "https://docs.kraken.com/api/docs/rest-api/get-order-book/",
            "https://docs.kraken.com/api/docs/rest-api/get-recent-trades/",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Public REST market data only; use short TTL cache and back off on provider errors.",
        "terms_risk": "Exchange market-data display requires source attribution; market data only.",
        "cache_policy": {
            "cache_id": "kraken_public_detail",
            "path": "market_data/crypto/{symbol}/{timeframe}.json",
            "ttl_seconds": 30,
            "retention": "latest per symbol/timeframe detail snapshot",
            "stale_behavior": "fallback source only; show stale cache with provider name",
        },
        "schemas": ["order_book_depth", "recent_trades", "closed_ohlc"],
        "fallback": "Used after Binance public detail refresh fails; never use private/account/trading endpoints.",
        "safety_class": "public_read_only_market_data",
        "source_attribution": {"name": "Kraken", "url": "https://api.kraken.com/0/public"},
        "tests": ["crypto_detail_provider_chain", "source_wall"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "coinbase_public_market_data",
        "label": "Coinbase public market data",
        "adapter_id": "coinbase_public_market_data",
        "implementation_status": "implemented_fallback",
        "coverage": ["crypto", "public product", "book", "candles", "market trades"],
        "official_docs": [
            "https://docs.cdp.coinbase.com/coinbase-business/advanced-trade-apis/rest-api",
            "https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-product-book",
            "https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-product-candles",
            "https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/public/get-public-market-trades",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key public endpoints; private endpoints forbidden for this milestone",
        "rate_limit": "Public endpoints use short cache behavior per Coinbase docs; keep a local TTL cache.",
        "terms_risk": "Public market-data display requires source attribution; do not mix with account/order APIs.",
        "cache_policy": {
            "cache_id": "coinbase_public_detail",
            "path": "market_data/crypto/{symbol}/{timeframe}.json",
            "ttl_seconds": 30,
            "retention": "latest per symbol/timeframe detail snapshot",
            "stale_behavior": "fallback source only; show stale cache with provider name",
        },
        "schemas": ["order_book_depth", "recent_trades", "closed_candles"],
        "fallback": "Used after Binance and Kraken public detail refresh fail; private endpoints remain unreachable.",
        "safety_class": "public_read_only_market_data",
        "source_attribution": {
            "name": "Coinbase",
            "url": "https://api.coinbase.com/api/v3/brokerage/market",
        },
        "tests": ["crypto_detail_provider_chain", "source_wall"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "public_rss_news",
        "label": "Public RSS news feeds",
        "adapter_id": "public_rss_news",
        "implementation_status": "implemented",
        "coverage": ["news", "macro headlines", "crypto headlines"],
        "official_docs": [
            "https://www.federalreserve.gov/feeds/press_all.xml",
            "https://www.sec.gov/news/pressreleases.rss",
            "https://www.coindesk.com/arc/outboundfeeds/rss/",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Source-specific RSS feeds; cache locally and fetch respectfully.",
        "terms_risk": "Headline/source attribution only; do not scrape or copy full articles.",
        "cache_policy": {
            "cache_id": "news_public_rss",
            "path": "artifacts/news/news_cache.json",
            "ttl_seconds": 900,
            "retention": "latest normalized feed batch",
            "stale_behavior": "show stale feed with source errors",
        },
        "schemas": ["news_items", "news_status"],
        "fallback": "Use stale cache or explicit local fallback headlines when feeds fail.",
        "safety_class": "public_read_only_news",
        "source_attribution": {"name": "Public RSS", "url": "configured source feed URLs"},
        "tests": ["news_cache_state", "source_attribution", "no_full_article_copy"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "sec_edgar_public",
        "label": "SEC EDGAR data APIs",
        "adapter_id": "sec_edgar_public",
        "implementation_status": "implemented",
        "coverage": ["fundamentals", "company submissions", "XBRL facts"],
        "official_docs": [
            "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
            "https://www.sec.gov/about/developer-resources",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Respect SEC fair-access guidance: no more than 10 requests per second.",
        "terms_risk": "Public SEC data; preserve source attribution and update timing.",
        "cache_policy": {
            "cache_id": "fundamentals_sec",
            "path": "market_data/fundamentals/sec/0000320193/companyfacts.json",
            "ttl_seconds": 86400,
            "retention": "filing-aware company facts cache",
            "stale_behavior": "show filing date and nightly bulk refresh note",
        },
        "schemas": ["submissions", "companyfacts", "frames"],
        "fallback": "Show stale SEC cache or unavailable state with source and retry guidance.",
        "safety_class": "public_read_only_fundamentals",
        "source_attribution": {"name": "SEC EDGAR", "url": "https://data.sec.gov/"},
        "tests": ["provider_entry_gate", "schema_normalization", "source_attribution", "cache_ttl"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "sec_xbrl_frames_public",
        "label": "SEC XBRL frames",
        "adapter_id": "sec_xbrl_frames_public",
        "implementation_status": "implemented",
        "coverage": ["stocks", "cross-company fundamental frames", "issuer reference context"],
        "official_docs": [
            "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
            "https://www.sec.gov/about/developer-resources",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Respect SEC fair-access guidance: no more than 10 requests per second.",
        "terms_risk": (
            "Public SEC XBRL frame data; preserve source attribution and do not present "
            "fundamental rows as quotes, advice, or executable signals."
        ),
        "cache_policy": {
            "cache_id": "fundamentals_sec_frames",
            "path": "market_data/fundamentals/sec/frames/us-gaap/Assets/USD/CY2023Q4I.json",
            "ttl_seconds": 86400,
            "retention": "bounded taxonomy/tag/unit/period frame snapshot",
            "stale_behavior": "show stale frame rows with tag, period, source, and cache path",
        },
        "schemas": ["frames"],
        "fallback": "Show stale SEC frame cache or unavailable state with source and retry guidance.",
        "safety_class": "public_read_only_fundamental_frames",
        "source_attribution": {"name": "SEC XBRL frames", "url": "https://data.sec.gov/"},
        "tests": ["provider_entry_gate", "schema_normalization", "source_attribution", "cache_ttl"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "sec_company_ticker_registry_public",
        "label": "SEC public company ticker registry",
        "adapter_id": "sec_company_ticker_registry_public",
        "implementation_status": "implemented",
        "coverage": ["stocks", "company ticker registry", "CIK mapping", "issuer reference"],
        "official_docs": [
            "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
            "https://www.sec.gov/files/company_tickers.json",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use daily local cache and comply with SEC fair-access guidance.",
        "terms_risk": (
            "Public SEC ticker mapping; preserve source attribution and do not present "
            "registry rows as executable stock quotes."
        ),
        "cache_policy": {
            "cache_id": "equities_sec_company_tickers",
            "path": "market_data/fundamentals/sec/company_tickers.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized company ticker registry sample",
            "stale_behavior": "show stale registry rows with quote provider still gated",
        },
        "schemas": ["company_ticker_registry_rows", "issuer_cik_mapping"],
        "fallback": "Show stale SEC company ticker registry or unavailable state; no synthetic quotes.",
        "safety_class": "public_read_only_company_reference",
        "source_attribution": {
            "name": "SEC company ticker file",
            "url": "https://www.sec.gov/files/company_tickers.json",
        },
        "tests": ["provider_entry_gate", "schema_normalization", "cache_ttl", "markets_stocks_ui"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "sec_company_submissions_public",
        "label": "SEC public company submissions",
        "adapter_id": "sec_company_submissions_public",
        "implementation_status": "implemented",
        "coverage": [
            "stocks",
            "bounded AAPL/MSFT/NVDA watchlist",
            "company submissions",
            "recent filings",
            "issuer reference",
        ],
        "official_docs": [
            "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
            "https://data.sec.gov/submissions/CIK0000320193.json",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use daily local cache and comply with SEC fair-access guidance.",
        "terms_risk": (
            "Public SEC filing metadata; preserve source attribution and do not present "
            "filings as quotes, investment advice, or executable trading signals."
        ),
        "cache_policy": {
            "cache_id": "equities_sec_company_submissions",
            "path": "market_data/fundamentals/sec/{cik}/submissions.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized recent company filing rows per bounded watchlist CIK",
            "stale_behavior": "show stale filing rows with source and retrieval time",
        },
        "schemas": ["company_submission_rows", "recent_filing_metadata"],
        "fallback": "Show stale SEC submissions cache or unavailable state; no synthetic filings.",
        "safety_class": "public_read_only_company_filings",
        "source_attribution": {"name": "SEC EDGAR submissions", "url": "https://data.sec.gov/"},
        "tests": ["provider_entry_gate", "schema_normalization", "cache_ttl", "markets_stocks_ui"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "sec_fund_ticker_registry_public",
        "label": "SEC fund ticker registry",
        "adapter_id": "sec_fund_ticker_registry_public",
        "implementation_status": "implemented",
        "coverage": ["ETF", "funds", "fund ticker registry", "series and class identifiers"],
        "official_docs": [
            "https://www.sec.gov/edgar/searchedgar/accessing-edgar-data.htm",
            "https://www.sec.gov/files/company_tickers_mf.json",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use daily local cache and comply with SEC fair-access guidance.",
        "terms_risk": (
            "Public SEC fund ticker mapping; preserve source attribution and do not present "
            "registry rows as executable ETF quotes."
        ),
        "cache_policy": {
            "cache_id": "funds_sec_tickers",
            "path": "market_data/funds/sec/company_tickers_mf.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized fund ticker registry sample",
            "stale_behavior": "show stale registry rows with quote provider still gated",
        },
        "schemas": ["fund_ticker_registry_rows", "series_class_identifiers"],
        "fallback": "Show stale SEC fund ticker registry or unavailable state; no synthetic quotes.",
        "safety_class": "public_read_only_fund_reference",
        "source_attribution": {
            "name": "SEC EDGAR fund ticker file",
            "url": "https://www.sec.gov/files/company_tickers_mf.json",
        },
        "tests": ["provider_entry_gate", "schema_normalization", "cache_ttl", "markets_etf_ui"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "dbnomics_public",
        "label": "DBnomics public macro data",
        "adapter_id": "dbnomics_public",
        "implementation_status": "implemented",
        "coverage": ["macro", "economic series", "public institution datasets"],
        "official_docs": ["https://docs.db.nomics.world/"],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use daily local cache; verify provider-specific limits before broad fetches.",
        "terms_risk": "Original source terms apply; preserve DBnomics provider and dataset codes.",
        "cache_policy": {
            "cache_id": "macro_dbnomics",
            "path": (
                "market_data/macro/dbnomics/INSEE/IPC-2015/"
                "A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE.json"
            ),
            "ttl_seconds": 86400,
            "retention": "series-level JSON cache",
            "stale_behavior": "show source provider, dataset, and last update",
        },
        "schemas": ["macro_series", "dataset_metadata"],
        "fallback": "Show stale DBnomics cache or unavailable state with source and retry guidance.",
        "safety_class": "public_read_only_macro",
        "source_attribution": {"name": "DBnomics", "url": "https://api.db.nomics.world/"},
        "tests": ["provider_entry_gate", "source_terms", "cache_ttl"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "bls_public_macro",
        "label": "BLS public macro/labor data",
        "adapter_id": "bls_public_macro",
        "implementation_status": "implemented",
        "coverage": ["macro", "labor", "inflation", "economic series", "latest public observations"],
        "official_docs": [
            "https://www.bls.gov/developers/api_signature_v2.htm",
            "https://www.bls.gov/developers/home.htm",
            "https://www.bls.gov/developers/api_unix_v2.htm",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use daily local cache and bounded latest-series requests for public BLS API data.",
        "terms_risk": "Public government macro/labor data; preserve BLS attribution and do not treat as tradable quotes.",
        "cache_policy": {
            "cache_id": "macro_bls_latest",
            "path": "market_data/macro/bls/latest_series.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized BLS macro/labor series batch",
            "stale_behavior": "show last local BLS observations with source and retry guidance",
        },
        "schemas": ["bls_latest_series_rows", "macro_series"],
        "fallback": "Show stale BLS cache or unavailable state; never use fixture macro values as runtime data.",
        "safety_class": "public_read_only_macro",
        "source_attribution": {
            "name": "U.S. Bureau of Labor Statistics Public Data API",
            "url": "https://api.bls.gov/publicAPI/v2/",
        },
        "tests": ["provider_entry_gate", "schema_normalization", "cache_ttl", "markets_macro_ui"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "eurostat_hicp_public",
        "label": "Eurostat HICP public macro data",
        "adapter_id": "eurostat_hicp_public",
        "implementation_status": "implemented",
        "coverage": ["macro", "inflation", "Euro area", "HICP", "latest public observations"],
        "official_docs": [
            "https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-detailed-guidelines/api-statistics",
            "https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_midx/default/table",
        ],
        "docs_checked_at": "2026-05-27",
        "auth_mode": "no-key",
        "rate_limit": "Use daily local cache and bounded lastTimePeriod=3 HICP requests.",
        "terms_risk": (
            "Official Eurostat macro/reference data; preserve attribution and do not "
            "treat HICP rows as tradable quotes or signals."
        ),
        "cache_policy": {
            "cache_id": "macro_eurostat_hicp",
            "path": "market_data/macro/eurostat/hicp_ea20_cp00_i15.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized Eurostat HICP monthly observations",
            "stale_behavior": "show last local HICP observations with source and retry guidance",
        },
        "schemas": ["eurostat_hicp_rows", "macro_series"],
        "fallback": "Show stale Eurostat HICP cache or unavailable state; never use fixture macro values.",
        "safety_class": "public_read_only_macro",
        "source_attribution": {
            "name": "Eurostat Statistics API",
            "url": "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/",
        },
        "tests": ["provider_entry_gate", "schema_normalization", "cache_ttl", "markets_macro_ui"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "us_treasury_yield_public",
        "label": "U.S. Treasury daily yield curve",
        "adapter_id": "us_treasury_yield_public",
        "implementation_status": "implemented",
        "coverage": ["rates", "bonds", "Treasury yield curve", "daily tenors"],
        "official_docs": ["https://home.treasury.gov/treasury-daily-interest-rate-xml-feed"],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use daily local cache; Treasury XML feed is public read-only data.",
        "terms_risk": "Public government rate data; preserve source attribution and retrieval date.",
        "cache_policy": {
            "cache_id": "rates_treasury_yield_curve",
            "path": "market_data/rates/treasury/daily_yield_curve.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized annual feed snapshot",
            "stale_behavior": "show last local curve with latest observation date and retry action",
        },
        "schemas": ["daily_yield_curve_rows", "tenor_rate_points", "rates_summary"],
        "fallback": "Show stale Treasury curve or unavailable state with source and refresh guidance.",
        "safety_class": "public_read_only_rates",
        "source_attribution": {
            "name": "U.S. Treasury",
            "url": "https://home.treasury.gov/resource-center/data-chart-center/interest-rates",
        },
        "tests": ["provider_entry_gate", "schema_normalization", "cache_ttl", "markets_rates_ui"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "nyfed_sofr_public",
        "label": "New York Fed SOFR reference rate",
        "adapter_id": "nyfed_sofr_public",
        "implementation_status": "implemented",
        "coverage": ["rates", "SOFR", "secured overnight financing rate", "daily reference rate"],
        "official_docs": [
            "https://www.newyorkfed.org/markets/reference-rates/sofr",
            "https://markets.newyorkfed.org/static/docs/markets-api.html",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use daily local cache; New York Fed Markets API is public read-only reference data.",
        "terms_risk": (
            "SOFR is reference-rate data; preserve New York Fed attribution and do not "
            "present it as an executable quote."
        ),
        "cache_policy": {
            "cache_id": "rates_nyfed_sofr",
            "path": "market_data/rates/nyfed/sofr.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized SOFR reference-rate rows",
            "stale_behavior": "show last local SOFR cache with latest effective date and retry action",
        },
        "schemas": ["sofr_ref_rate_rows", "rates_summary"],
        "fallback": "Show stale SOFR cache or unavailable state with source and refresh guidance.",
        "safety_class": "public_read_only_rates",
        "source_attribution": {
            "name": "Federal Reserve Bank of New York",
            "url": "https://markets.newyorkfed.org/api/rates/secured/sofr/last/10.json",
        },
        "tests": ["provider_entry_gate", "schema_normalization", "cache_ttl", "markets_rates_ui"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "ecb_fx_reference_public",
        "label": "ECB euro foreign exchange reference rates",
        "adapter_id": "ecb_fx_reference_public",
        "implementation_status": "implemented",
        "coverage": ["FX", "EUR reference rates", "currency pairs", "daily reference rates"],
        "official_docs": [
            "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-xml.html",
            "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use daily local cache; ECB latest XML feed is public read-only data.",
        "terms_risk": (
            "ECB reference rates are information-only; preserve attribution and do not present "
            "them as executable trading quotes."
        ),
        "cache_policy": {
            "cache_id": "fx_ecb_reference_rates",
            "path": "market_data/fx/ecb/eurofxref_daily.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized daily reference-rate snapshot",
            "stale_behavior": "show last local reference rates with date and retry action",
        },
        "schemas": ["ecb_eurofxref_rows", "fx_pair_reference_rates", "fx_summary"],
        "fallback": "Show stale ECB reference rates or unavailable state with source and refresh guidance.",
        "safety_class": "public_read_only_fx_reference",
        "source_attribution": {
            "name": "European Central Bank",
            "url": "https://www.ecb.europa.eu/stats/eurofxref/",
        },
        "tests": ["provider_entry_gate", "schema_normalization", "cache_ttl", "markets_fx_ui"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "federal_reserve_h10_ddp_public",
        "label": "Federal Reserve H.10 foreign exchange reference rates",
        "adapter_id": "federal_reserve_h10_ddp_public",
        "implementation_status": "implemented",
        "coverage": ["FX", "USD reference rates", "currency pairs", "daily reference rates"],
        "official_docs": [
            "https://www.federalreserve.gov/datadownload/choose.aspx?rel=h10",
            (
                "https://www.federalreserve.gov/datadownload/Output.aspx?"
                "rel=H10&filetype=csv"
            ),
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": (
            "Use daily local cache; Federal Reserve H.10 DDP CSV package is public "
            "read-only reference data."
        ),
        "terms_risk": (
            "Federal Reserve H.10 rates are reference data; preserve attribution and "
            "do not present them as executable FX quotes."
        ),
        "cache_policy": {
            "cache_id": "fx_federal_reserve_h10_reference_rates",
            "path": "market_data/fx/federal_reserve/h10_reference_rates.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized H.10 daily reference-rate package snapshot",
            "stale_behavior": "show last local H.10 rates with date and retry action",
        },
        "schemas": ["federal_reserve_h10_rows", "fx_usd_reference_rates", "fx_summary"],
        "fallback": "Show stale H.10 reference rates or unavailable state with source and refresh guidance.",
        "safety_class": "public_read_only_fx_reference",
        "source_attribution": {
            "name": "Federal Reserve H.10",
            "url": "https://www.federalreserve.gov/datadownload/choose.aspx?rel=h10",
        },
        "tests": ["provider_entry_gate", "schema_normalization", "cache_ttl", "markets_fx_ui"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "bank_of_canada_valet_fx_reference_public",
        "label": "Bank of Canada Valet foreign exchange reference rates",
        "adapter_id": "bank_of_canada_valet_fx_reference_public",
        "implementation_status": "implemented",
        "coverage": ["FX", "CAD reference rates", "currency pairs", "daily reference rates"],
        "official_docs": [
            "https://www.bankofcanada.ca/valet/docs",
            "https://www.bankofcanada.ca/rates/exchange/",
            "https://www.bankofcanada.ca/rates/exchange/background-information-on-foreign-exchange-rates/",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": (
            "Use daily local cache; Bank of Canada Valet observations are public "
            "read-only reference data."
        ),
        "terms_risk": (
            "Bank of Canada exchange rates are indicative reference data and are "
            "not executable transaction quotes."
        ),
        "cache_policy": {
            "cache_id": "fx_bank_of_canada_valet_reference_rates",
            "path": "market_data/fx/bank_of_canada/valet_fx_reference_rates.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized Valet CAD reference-rate observations",
            "stale_behavior": "show last local BoC rates with date and retry action",
        },
        "schemas": ["bank_of_canada_valet_rows", "fx_cad_reference_rates", "fx_summary"],
        "fallback": "Show stale BoC reference rates or unavailable state with source and refresh guidance.",
        "safety_class": "public_read_only_fx_reference",
        "source_attribution": {
            "name": "Bank of Canada",
            "url": "https://www.bankofcanada.ca/rates/exchange/",
        },
        "tests": ["provider_entry_gate", "schema_normalization", "cache_ttl", "markets_fx_ui"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "world_bank_commodity_monthly_public",
        "label": "World Bank commodity monthly prices",
        "adapter_id": "world_bank_commodity_monthly_public",
        "implementation_status": "implemented",
        "coverage": ["commodities", "energy", "metals", "agriculture", "monthly reference prices"],
        "official_docs": [
            "https://www.worldbank.org/en/research/commodity-markets",
            (
                "https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/"
                "related/CMO-Historical-Data-Monthly.xlsx"
            ),
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use weekly local cache; World Bank Pink Sheet monthly XLSX is public reference data.",
        "terms_risk": (
            "Preserve World Bank attribution and do not present monthly commodity values "
            "as executable spot or futures quotes."
        ),
        "cache_policy": {
            "cache_id": "commodities_world_bank_monthly",
            "path": "market_data/commodities/world_bank/pink_sheet_monthly.json",
            "ttl_seconds": 604800,
            "retention": "latest normalized monthly commodity price snapshot",
            "stale_behavior": "show last local monthly values with period and retry action",
        },
        "schemas": ["pink_sheet_monthly_rows", "commodity_reference_prices", "commodity_summary"],
        "fallback": "Show stale World Bank commodity prices or unavailable state with source guidance.",
        "safety_class": "public_read_only_commodity_reference",
        "source_attribution": {
            "name": "World Bank Commodity Markets",
            "url": "https://www.worldbank.org/en/research/commodity-markets",
        },
        "tests": ["provider_entry_gate", "schema_normalization", "cache_ttl", "markets_commodities_ui"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "cftc_cot_legacy_public",
        "label": "CFTC Commitments of Traders legacy futures",
        "adapter_id": "cftc_cot_legacy_public",
        "implementation_status": "implemented",
        "coverage": ["commodities", "futures positioning", "open interest", "weekly context"],
        "official_docs": [
            "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
            "https://dev.socrata.com/foundry/publicreporting.cftc.gov/6dca-aqww",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use weekly local cache; query only bounded public CFTC PRE rows.",
        "terms_risk": (
            "Preserve CFTC attribution and present COT values as positioning context, "
            "not executable spot or futures quotes."
        ),
        "cache_policy": {
            "cache_id": "commodities_cftc_cot_legacy",
            "path": "market_data/commodities/cftc/cot_legacy_futures.json",
            "ttl_seconds": 604800,
            "retention": "latest normalized bounded weekly COT commodity positioning rows",
            "stale_behavior": "show last local COT rows with report date and retry action",
        },
        "schemas": ["cftc_cot_legacy_rows", "commodity_positioning_context"],
        "fallback": "Show stale CFTC COT positioning rows or unavailable state with source guidance.",
        "safety_class": "public_read_only_commodity_positioning",
        "source_attribution": {
            "name": "CFTC Commitments of Traders",
            "url": "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm",
        },
        "tests": ["provider_entry_gate", "schema_normalization", "cache_ttl", "markets_cot_ui"],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "eia_open_data_optional_key",
        "label": "EIA Open Data energy context",
        "adapter_id": "eia_open_data_optional_key",
        "implementation_status": "implemented",
        "coverage": ["commodities", "energy", "WTI", "Brent", "Henry Hub", "energy context"],
        "official_docs": [
            "https://www.eia.gov/opendata/documentation.php",
            "https://www.eia.gov/opendata/v1/register.php",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": (
            "EIA APIv2 requires a user-owned key and may temporarily suspend keys "
            "that exceed request tolerances; use a daily local cache."
        ),
        "terms_risk": (
            "User-owned free key; preserve EIA attribution and present energy series "
            "as context data, not executable spot or futures quotes."
        ),
        "cache_policy": {
            "cache_id": "eia_energy_series",
            "path": "market_data/commodities/eia/energy_series.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized WTI, Brent, and Henry Hub context rows",
            "stale_behavior": "show last local energy series with key/setup state and retry action",
        },
        "schemas": ["eia_seriesid_energy_rows", "energy_context_summary"],
        "fallback": "Show World Bank no-key commodity context or last local EIA cache; never use fixture energy prices.",
        "safety_class": "optional_local_secret_data_provider",
        "source_attribution": {
            "name": "U.S. Energy Information Administration Open Data",
            "url": "https://www.eia.gov/opendata/",
        },
        "tests": ["secret_gate", "redacted_refresh", "cache_ttl", "markets_energy_context_ui"],
        "secret_gate": "local_secret_store_required",
        "capability_state": "key_required",
    },
    {
        "provider_id": "fred_optional_local_key",
        "label": "FRED economic data",
        "adapter_id": "fred_optional_local_key",
        "implementation_status": "implemented",
        "coverage": ["macro", "economic series", "release calendar"],
        "official_docs": [
            "https://fred.stlouisfed.org/docs/api/api_key.html",
            "https://fred.stlouisfed.org/docs/api/fred/series_observations.html",
            "https://fred.stlouisfed.org/docs/api/terms_of_use.html",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": "FRED may limit web service requests; use a daily local series cache.",
        "terms_risk": (
            "User-owned key; show source notice, avoid provider logo/trademark use, "
            "and never commit, log, screenshot, or expose credential material."
        ),
        "cache_policy": {
            "cache_id": "macro_fred_DGS10",
            "path": "market_data/macro/fred/DGS10.json",
            "ttl_seconds": 86400,
            "retention": "latest DGS10 series observations JSON cache",
            "stale_behavior": "show last local observations with key/setup state and retry action",
        },
        "schemas": ["series_observations"],
        "fallback": "Use DBnomics/no-key macro path or last local FRED cache; never use fixtures as runtime data.",
        "safety_class": "optional_local_secret_data_provider",
        "source_attribution": {
            "name": "FRED API",
            "url": "https://fred.stlouisfed.org/docs/api/",
        },
        "tests": ["secret_gate", "redacted_refresh", "cache_ttl", "source_attribution"],
        "secret_gate": "local_secret_store_required",
        "capability_state": "key_required",
    },
    {
        "provider_id": "bea_regional_optional_key",
        "label": "BEA Regional API",
        "adapter_id": "bea_regional_optional_key",
        "implementation_status": "implemented",
        "coverage": ["regional", "macro", "state GDP", "economic context"],
        "official_docs": [
            "https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf",
            "https://apps.bea.gov/API/signup/",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": (
            "BEA Regional requests require a user-owned UserID; use official "
            "SAGDP9N state rows with bounded local normalization and a daily local cache."
        ),
        "terms_risk": (
            "User-owned key; preserve BEA attribution and present regional data "
            "as macro context, not quotes, balances, or trade instructions."
        ),
        "cache_policy": {
            "cache_id": "regional_bea_SAGDP9N_LINE1_STATE",
            "path": "market_data/regional/bea/SAGDP9N_LINE1_STATE.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized BEA Regional real GDP rows",
            "stale_behavior": "show last local regional context with key/setup state and retry action",
        },
        "schemas": ["bea_regional_series_rows", "regional_macro_context_summary"],
        "fallback": "Show DBnomics/BLS public macro context or last local BEA cache; never use fixtures.",
        "safety_class": "optional_local_secret_data_provider",
        "source_attribution": {
            "name": "U.S. Bureau of Economic Analysis API",
            "url": "https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf",
        },
        "tests": ["secret_gate", "redacted_refresh", "cache_ttl", "markets_regional_context"],
        "secret_gate": "local_secret_store_required",
        "capability_state": "key_required",
    },
    {
        "provider_id": "census_api_optional_key",
        "label": "Census ACS 5-Year Profile API",
        "adapter_id": "census_api_optional_key",
        "implementation_status": "implemented",
        "coverage": ["regional", "macro", "demographics", "economic context"],
        "official_docs": [
            "https://www.census.gov/data/developers/guidance/api-user-guide.API_Key.html",
            "https://api.census.gov/data/2023/acs/acs5/profile.html",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": (
            "Census ACS profile requests require a user-owned API key for this "
            "local adapter; use bounded state-level profile rows and a daily local cache."
        ),
        "terms_risk": (
            "User-owned key; preserve Census attribution and present ACS profile "
            "data as regional context, not quotes, balances, or trade instructions."
        ),
        "cache_policy": {
            "cache_id": "regional_census_ACS5_PROFILE_STATE_2023",
            "path": "market_data/regional/census/acs5_profile_state_2023.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized Census ACS state profile rows",
            "stale_behavior": "show last local ACS context with key/setup state and retry action",
        },
        "schemas": ["census_acs_profile_series_rows", "regional_context_summary"],
        "fallback": "Show DBnomics/BLS/BEA context or last local Census cache; never use fixtures.",
        "safety_class": "optional_local_secret_data_provider",
        "source_attribution": {
            "name": "U.S. Census Bureau Data API",
            "url": "https://api.census.gov/data/2023/acs/acs5/profile.html",
        },
        "tests": ["secret_gate", "redacted_refresh", "cache_ttl", "markets_regional_context"],
        "secret_gate": "local_secret_store_required",
        "capability_state": "key_required",
    },
    {
        "provider_id": "alphavantage_global_quote_optional_key",
        "label": "Alpha Vantage Global Quote",
        "adapter_id": "alphavantage_global_quote_optional_key",
        "implementation_status": "implemented",
        "coverage": ["stocks", "ETF", "FX", "bounded quote watchlists", "price", "volume"],
        "official_docs": [
            "https://www.alphavantage.co/documentation/",
            "https://www.alphavantage.co/premium/",
            "https://www.alphavantage.co/terms_of_service/",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": (
            "Standard free usage is 25 requests/day; Global Quote returns one ticker per "
            "request and should use per-symbol daily local caches."
        ),
        "terms_risk": (
            "User-owned key and plan-specific entitlements; default quote data is end-of-day "
            "unless the user has separate exchange entitlement. No bundled key, broker link, "
            "or live execution use."
        ),
        "cache_policy": {
            "cache_id": "equity_quote_alphavantage_AAPL",
            "secondary_cache_ids": [
                "equity_quote_alphavantage_MSFT",
                "equity_quote_alphavantage_NVDA",
                "etf_quote_alphavantage_SPY",
                "etf_quote_alphavantage_QQQ",
                "etf_quote_alphavantage_IWM",
                "fx_quote_alphavantage_EURUSD",
                "fx_quote_alphavantage_USDJPY",
                "fx_quote_alphavantage_GBPUSD",
            ],
            "path": (
                "market_data/equities/alphavantage/global_quote/{symbol}.json "
                "for AAPL/MSFT/NVDA and SPY/QQQ/IWM watchlists; "
                "market_data/fx/alphavantage/currency_exchange/{pair}.json "
                "for EURUSD/USDJPY/GBPUSD"
            ),
            "ttl_seconds": 86400,
            "retention": "latest normalized per-symbol Global Quote JSON cache",
            "stale_behavior": "show last local quote with key/setup state and retry action",
        },
        "schemas": [
            "global_quote_equity_watchlist_rows",
            "global_quote_etf_watchlist_rows",
            "currency_exchange_fx_watchlist_rows",
        ],
        "fallback": (
            "Show last local quote cache or key-required state; never use fixture "
            "stock, ETF, or FX quotes."
        ),
        "safety_class": "optional_local_secret_data_provider",
        "source_attribution": {
            "name": "Alpha Vantage",
            "url": "https://www.alphavantage.co/documentation/",
        },
        "tests": [
            "secret_gate",
            "redacted_refresh",
            "cache_ttl",
            "markets_stocks_quote_ui",
            "markets_etf_quote_ui",
            "markets_fx_quote_ui",
        ],
        "secret_gate": "local_secret_store_required",
        "capability_state": "key_required",
    },
    {
        "provider_id": "twelve_data_quote_optional_key",
        "label": "Twelve Data Quote",
        "adapter_id": "twelve_data_quote_optional_key",
        "implementation_status": "implemented",
        "coverage": ["stocks", "ETF", "FX", "bounded multi-asset quote watchlist"],
        "official_docs": [
            "https://twelvedata.com/docs/llms",
            "https://twelvedata.com/docs/llms/market-data",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": (
            "Quote endpoint costs 1 API credit per symbol; keep bounded symbols and "
            "daily local caches."
        ),
        "terms_risk": (
            "User-owned key and plan-specific entitlements; no bundled key, broker "
            "link, live execution use, signup, or payment activation."
        ),
        "cache_policy": {
            "cache_id": "twelve_data_quote_AAPL",
            "secondary_cache_ids": [
                "twelve_data_quote_SPY",
                "twelve_data_quote_EURUSD",
            ],
            "path": "market_data/quotes/twelve_data/{symbol}.json for AAPL/SPY/EURUSD watchlist",
            "ttl_seconds": 86400,
            "retention": "latest normalized per-symbol Twelve Data quote JSON cache",
            "stale_behavior": "show last local quote with key/setup state and retry action",
        },
        "schemas": ["twelve_data_quote_watchlist_rows"],
        "fallback": "Show last local quote cache or key-required state; never use fixture quotes.",
        "safety_class": "optional_local_secret_data_provider",
        "source_attribution": {
            "name": "Twelve Data",
            "url": "https://twelvedata.com/docs/llms/market-data",
        },
        "tests": [
            "secret_gate",
            "redacted_refresh",
            "cache_ttl",
            "markets_source_coverage_matrix",
        ],
        "secret_gate": "local_secret_store_required",
        "capability_state": "key_required",
    },
    {
        "provider_id": "finnhub_equity_quote_optional_key",
        "label": "Finnhub Equity Quote",
        "adapter_id": "finnhub_equity_quote_optional_key",
        "implementation_status": "implemented",
        "coverage": ["stocks", "ETF", "bounded equity quote watchlist"],
        "official_docs": [
            "https://finnhub.io/docs/api/quote",
            "https://finnhub.io/docs/api/rate-limit",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": (
            "Quote endpoint requires a user token; keep bounded symbols and "
            "daily local caches."
        ),
        "terms_risk": (
            "User-owned key and plan-specific entitlements; no bundled key, "
            "broker link, live execution use, signup, or payment activation."
        ),
        "cache_policy": {
            "cache_id": "finnhub_quote_AAPL",
            "secondary_cache_ids": [
                "finnhub_quote_MSFT",
                "finnhub_quote_NVDA",
                "finnhub_quote_SPY",
            ],
            "path": "market_data/quotes/finnhub/{symbol}.json for AAPL/MSFT/NVDA/SPY watchlist",
            "ttl_seconds": 86400,
            "retention": "latest normalized per-symbol Finnhub quote JSON cache",
            "stale_behavior": "show last local quote with key/setup state and retry action",
        },
        "schemas": ["finnhub_equity_quote_watchlist_rows"],
        "fallback": "Show last local quote cache or key-required state; never use fixture quotes.",
        "safety_class": "optional_local_secret_data_provider",
        "source_attribution": {
            "name": "Finnhub",
            "url": "https://finnhub.io/docs/api/quote",
        },
        "tests": [
            "secret_gate",
            "redacted_refresh",
            "cache_ttl",
            "markets_source_coverage_matrix",
        ],
        "secret_gate": "local_secret_store_required",
        "capability_state": "key_required",
    },
    {
        "provider_id": "fmp_stock_quote_optional_key",
        "label": "FMP Stock Quote",
        "adapter_id": "fmp_stock_quote_optional_key",
        "implementation_status": "implemented",
        "coverage": ["stocks", "ETF", "bounded stock quote watchlist"],
        "official_docs": [
            "https://site.financialmodelingprep.com/developer/docs/stable/quote",
            "https://site.financialmodelingprep.com/developer/docs",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key",
        "rate_limit": (
            "Stable quote endpoint requires a user API key; keep bounded symbols "
            "and daily local caches."
        ),
        "terms_risk": (
            "User-owned key and plan-specific entitlements; no bundled key, "
            "broker link, live execution use, signup, or payment activation."
        ),
        "cache_policy": {
            "cache_id": "fmp_quote_AAPL",
            "secondary_cache_ids": [
                "fmp_quote_MSFT",
                "fmp_quote_NVDA",
                "fmp_quote_SPY",
            ],
            "path": "market_data/quotes/fmp/{symbol}.json for AAPL/MSFT/NVDA/SPY watchlist",
            "ttl_seconds": 86400,
            "retention": "latest normalized per-symbol FMP quote JSON cache",
            "stale_behavior": "show last local quote with key/setup state and retry action",
        },
        "schemas": ["fmp_stock_quote_watchlist_rows"],
        "fallback": "Show last local quote cache or key-required state; never use fixture quotes.",
        "safety_class": "optional_local_secret_data_provider",
        "source_attribution": {
            "name": "Financial Modeling Prep",
            "url": "https://site.financialmodelingprep.com/developer/docs/stable/quote",
        },
        "tests": [
            "secret_gate",
            "redacted_refresh",
            "cache_ttl",
            "markets_source_coverage_matrix",
        ],
        "secret_gate": "local_secret_store_required",
        "capability_state": "key_required",
    },
    {
        "provider_id": "stooq_public_quote_snapshot",
        "label": "Stooq Public Quote Snapshot",
        "adapter_id": "stooq_public_quote_snapshot",
        # Stooq closed the no-key CSV quote endpoint in 2026-07 (404 on both
        # domains, JS wall on history). markets_quote_lookup (Yahoo) covers
        # every symbol this served; kept in the registry as history.
        "implementation_status": "retired_upstream_endpoint",
        "coverage": ["stocks", "ETF", "indexes", "FX", "bounded delayed quote snapshot"],
        "official_docs": [
            "https://stooq.com/q/?s=^spx",
            "https://stooq.com/db/h/",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Bounded per-symbol current CSV snapshot requests only; no bulk crawl.",
        "terms_risk": (
            "Stooq quote pages attribute upstream data providers. Historical CSV download "
            "requires a CAPTCHA/API-link gate and is intentionally not implemented here."
        ),
        "cache_policy": {
            "cache_id": "stooq_quote_AAPLUS",
            "secondary_cache_ids": [
                "stooq_quote_SPYUS",
                "stooq_quote_SPX",
                "stooq_quote_EURUSD",
            ],
            "path": "market_data/quotes/stooq/{symbol}.json for AAPL.US/SPY.US/^SPX/EURUSD watchlist",
            "ttl_seconds": 900,
            "retention": "latest normalized per-symbol Stooq CSV quote snapshot",
            "stale_behavior": "show last local snapshot with source/date/time and refresh guidance",
        },
        "schemas": ["stooq_quote_snapshot_rows"],
        "fallback": "Show last local snapshot cache or unavailable state; never use fixture quotes.",
        "safety_class": "public_read_only_market_data",
        "source_attribution": {
            "name": "Stooq",
            "url": "https://stooq.com/q/",
        },
        "tests": [
            "public_no_key_refresh",
            "cache_ttl",
            "markets_source_coverage_matrix",
            "source_wall",
        ],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "nasdaq_trader_symbol_directory_public",
        "label": "Nasdaq Trader Symbol Directory",
        "adapter_id": "nasdaq_trader_symbol_directory_public",
        "implementation_status": "implemented",
        "coverage": ["stocks", "ETF", "listed securities", "symbol reference"],
        "official_docs": [
            "https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs",
            "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
            "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Use daily local cache and the two official downloadable text files only.",
        "terms_risk": (
            "Symbol-directory rows are reference metadata only; do not represent them "
            "as quotes, executable market data, broker availability, or balances."
        ),
        "cache_policy": {
            "cache_id": "nasdaq_trader_symbol_directory",
            "path": "market_data/reference/nasdaq_trader/symbol_directory.json",
            "ttl_seconds": 86400,
            "retention": "latest normalized Nasdaq-listed and other-listed symbol directory rows",
            "stale_behavior": "show last local directory with source-file and refresh guidance",
        },
        "schemas": ["nasdaq_trader_symbol_directory_rows"],
        "fallback": "Show last local symbol-directory cache or unavailable state; never use fixtures.",
        "safety_class": "public_read_only_reference_data",
        "source_attribution": {
            "name": "Nasdaq Trader",
            "url": "https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs",
        },
        "tests": [
            "public_no_key_refresh",
            "cache_ttl",
            "markets_source_coverage_matrix",
            "source_wall",
        ],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "openfigi_identifier_mapping_public",
        "label": "OpenFIGI Identifier Mapping",
        "adapter_id": "openfigi_identifier_mapping_public",
        "implementation_status": "implemented",
        "coverage": ["stocks", "listed securities", "FIGI identifier reference"],
        "official_docs": [
            "https://www.openfigi.com/api/documentation",
            "https://api.openfigi.com/v3/mapping",
        ],
        "docs_checked_at": "2026-05-27",
        "auth_mode": "no-key",
        "rate_limit": (
            "Bounded v3 mapping jobs only; unauthenticated requests have the lower "
            "OpenFIGI public rate limit."
        ),
        "terms_risk": (
            "OpenFIGI rows are identifier metadata only; do not represent them as "
            "quotes, executable market data, broker availability, or balances."
        ),
        "cache_policy": {
            "cache_id": "openfigi_identifier_mapping",
            "path": "market_data/reference/openfigi/mapping.json",
            "ttl_seconds": 86400,
            "retention": "latest bounded ticker-to-FIGI mapping rows",
            "stale_behavior": "show last local mapping cache with source and refresh guidance",
        },
        "schemas": ["openfigi_mapping_rows"],
        "fallback": "Show last local OpenFIGI mapping cache or unavailable state; never use fixtures.",
        "safety_class": "public_read_only_reference_data",
        "source_attribution": {
            "name": "OpenFIGI",
            "url": "https://www.openfigi.com/api/documentation",
        },
        "tests": [
            "public_no_key_refresh",
            "cache_ttl",
            "markets_source_coverage_matrix",
            "source_wall",
        ],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "moex_iss_delayed_quote_snapshot",
        "label": "MOEX ISS Delayed Quote Snapshot",
        "adapter_id": "moex_iss_delayed_quote_snapshot",
        "implementation_status": "implemented",
        "coverage": ["stocks", "international equities", "bounded delayed quote snapshot"],
        "official_docs": [
            "https://www.moex.com/a2920",
            "https://www.moex.com/files/4be999zbzp80bx2bgmwayrtyx0",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "no-key",
        "rate_limit": "Bounded per-security ISS marketdata requests only; no orderbook/authenticated calls.",
        "terms_risk": (
            "MOEX ISS documentation allows delayed unauthenticated market data; orderbooks "
            "and real-time/subscriber data stay out of scope."
        ),
        "cache_policy": {
            "cache_id": "moex_quote_SBER",
            "secondary_cache_ids": [
                "moex_quote_GAZP",
                "moex_quote_MOEX",
            ],
            "path": "market_data/quotes/moex/{symbol}.json for SBER/GAZP/MOEX watchlist",
            "ttl_seconds": 900,
            "retention": "latest normalized per-symbol MOEX ISS delayed quote snapshot",
            "stale_behavior": "show last local delayed snapshot with source/time and refresh guidance",
        },
        "schemas": ["moex_delayed_quote_snapshot_rows"],
        "fallback": "Show last local delayed snapshot cache or unavailable state; never use fixture quotes.",
        "safety_class": "public_read_only_market_data",
        "source_attribution": {
            "name": "Moscow Exchange ISS",
            "url": "https://iss.moex.com/",
        },
        "tests": [
            "public_no_key_refresh",
            "cache_ttl",
            "markets_source_coverage_matrix",
            "source_wall",
        ],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "twse_openapi_daily_quote_snapshot",
        "label": "TWSE OpenAPI Daily Quote Snapshot",
        "adapter_id": "twse_openapi_daily_quote_snapshot",
        "implementation_status": "implemented",
        "coverage": ["stocks", "Taiwan listed equities", "bounded daily quote snapshot"],
        "official_docs": [
            "https://openapi.twse.com.tw/",
            "https://openapi.twse.com.tw/v1/swagger.json",
        ],
        "docs_checked_at": "2026-05-27",
        "auth_mode": "no-key",
        "rate_limit": "Bounded STOCK_DAY_ALL refreshes only; no private, broker, or realtime feeds.",
        "terms_risk": (
            "TWSE OpenAPI daily trading rows are public delayed snapshots; keep them "
            "non-orderable and do not imply broker connectivity, balances, or live execution."
        ),
        "cache_policy": {
            "cache_id": "twse_quote_2330",
            "secondary_cache_ids": [
                "twse_quote_2317",
                "twse_quote_0050",
            ],
            "path": "market_data/quotes/twse/{symbol}.json for 2330/2317/0050 watchlist",
            "ttl_seconds": 86400,
            "retention": "latest normalized per-symbol TWSE OpenAPI daily quote snapshot",
            "stale_behavior": "show last local daily snapshot with source/date and refresh guidance",
        },
        "schemas": ["twse_daily_quote_snapshot_rows"],
        "fallback": "Show last local daily snapshot cache or unavailable state; never use fixture quotes.",
        "safety_class": "public_read_only_market_data",
        "source_attribution": {
            "name": "Taiwan Stock Exchange OpenAPI",
            "url": "https://openapi.twse.com.tw/",
        },
        "tests": [
            "public_no_key_refresh",
            "cache_ttl",
            "markets_source_coverage_matrix",
            "source_wall",
        ],
        "secret_gate": "not_required",
    },
    {
        "provider_id": "premium_market_data_option",
        "label": "Premium multi-asset market-data option",
        "adapter_id": "premium_market_data_option",
        "implementation_status": "recorded_option_only",
        "coverage": ["stocks", "ETF", "FX", "commodities", "fundamentals", "news"],
        "official_docs": [
            "https://www.alphavantage.co/documentation/",
            "https://site.financialmodelingprep.com/developer/docs",
        ],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "optional-local-key / paid-gated",
        "rate_limit": "Plan-specific; verify per endpoint before implementation.",
        "terms_risk": "Paid entitlement and display rights vary; no purchase or activation by agent.",
        "cache_policy": {
            "cache_id": "premium_market_data",
            "path": "market_data/premium",
            "ttl_seconds": 3600,
            "retention": "endpoint-aware provider cache",
            "stale_behavior": "show plan-required and provider capability detail",
        },
        "schemas": ["quotes", "historical_prices", "fundamentals", "news_headlines"],
        "fallback": "Show plan-required provider row; keep route surfaces useful through no-key providers.",
        "safety_class": "paid_optional_data_provider",
        "source_attribution": {"name": "Optional external data provider", "url": "provider docs"},
        "tests": ["plan_gate", "secret_gate", "provider_capability_matrix"],
        "secret_gate": "blocked_until_local_secret_storage_review",
        "capability_state": "plan_required",
    },
    {
        "provider_id": "private_broker_live_execution",
        "label": "Private broker live execution",
        "adapter_id": "private_broker_live_execution",
        "implementation_status": "forbidden_until_live_safety_contract",
        "coverage": ["live orders", "private balances", "broker account"],
        "official_docs": [],
        "docs_checked_at": DOCS_CHECKED_AT,
        "auth_mode": "forbidden",
        "rate_limit": "Not applicable while disabled by safety.",
        "terms_risk": "Live execution is not reachable without independent safety contract and review.",
        "cache_policy": {
            "cache_id": "none",
            "path": "",
            "ttl_seconds": 0,
            "retention": "none",
            "stale_behavior": "none",
        },
        "schemas": [],
        "fallback": "Use paper/dry-run surfaces only.",
        "safety_class": "disabled_by_live_safety",
        "source_attribution": {"name": "Disabled", "url": ""},
        "tests": ["disabled_reachability", "paper_live_isolation", "source_wall"],
        "secret_gate": "forbidden_until_safety_contract",
        "capability_state": "disabled_by_safety",
    },
)


def providers_payload(store: Any) -> dict[str, Any]:
    """Return provider registry plus cache freshness for the current local state."""

    root = store.root
    crypto_detail_cache = store.read_crypto_detail_cache()
    crypto_detail_status = (
        crypto_detail_cache.get("status") if isinstance(crypto_detail_cache, dict) else {}
    )
    crypto_detail_status = crypto_detail_status if isinstance(crypto_detail_status, dict) else {}
    crypto_detail_provider_id = str(
        crypto_detail_status.get("provider_id") or "binance_spot_public"
    )
    cache_states = {
        "market_crypto_latest": _cache_state(
            cache_id="market_crypto_latest",
            provider_id="binance_spot_public",
            path=store.market_cache_path,
            root=root,
            ttl_seconds=60,
            payload=store.read_market_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "crypto_public_detail": _cache_state(
            cache_id="crypto_public_detail",
            provider_id=crypto_detail_provider_id,
            path=store.crypto_detail_cache_path(),
            root=root,
            ttl_seconds=30,
            payload=crypto_detail_cache,
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "news_public_rss": _cache_state(
            cache_id="news_public_rss",
            provider_id="public_rss_news",
            path=store.news_cache_path,
            root=root,
            ttl_seconds=900,
            payload=store.read_news_cache(),
            timestamp_keys=("fetched_at",),
            nested_status=False,
        ),
        "fundamentals_sec": _cache_state(
            cache_id="fundamentals_sec",
            provider_id="sec_edgar_public",
            path=store.sec_fundamentals_cache_path(),
            root=root,
            ttl_seconds=86400,
            payload=store.read_sec_fundamentals_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "fundamentals_sec_frames": _cache_state(
            cache_id="fundamentals_sec_frames",
            provider_id="sec_xbrl_frames_public",
            path=store.sec_xbrl_frame_cache_path(),
            root=root,
            ttl_seconds=86400,
            payload=store.read_sec_xbrl_frame_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "equities_sec_company_tickers": _cache_state(
            cache_id="equities_sec_company_tickers",
            provider_id="sec_company_ticker_registry_public",
            path=store.sec_company_tickers_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_sec_company_tickers_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "equities_sec_company_submissions": _cache_state(
            cache_id="equities_sec_company_submissions",
            provider_id="sec_company_submissions_public",
            path=store.sec_company_submissions_cache_path(),
            root=root,
            ttl_seconds=86400,
            payload=store.read_sec_company_submissions_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "macro_dbnomics": _cache_state(
            cache_id="macro_dbnomics",
            provider_id="dbnomics_public",
            path=store.dbnomics_macro_cache_path(),
            root=root,
            ttl_seconds=86400,
            payload=store.read_dbnomics_macro_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "macro_fred_DGS10": _cache_state(
            cache_id="macro_fred_DGS10",
            provider_id="fred_optional_local_key",
            path=store.fred_macro_cache_path(),
            root=root,
            ttl_seconds=86400,
            payload=store.read_fred_macro_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "macro_bls_latest": _cache_state(
            cache_id="macro_bls_latest",
            provider_id="bls_public_macro",
            path=store.bls_macro_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_bls_macro_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "macro_eurostat_hicp": _cache_state(
            cache_id="macro_eurostat_hicp",
            provider_id="eurostat_hicp_public",
            path=store.eurostat_hicp_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_eurostat_hicp_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "regional_bea_SAGDP9N_LINE1_STATE": _cache_state(
            cache_id="regional_bea_SAGDP9N_LINE1_STATE",
            provider_id="bea_regional_optional_key",
            path=store.bea_regional_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_bea_regional_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "regional_census_ACS5_PROFILE_STATE_2023": _cache_state(
            cache_id="regional_census_ACS5_PROFILE_STATE_2023",
            provider_id="census_api_optional_key",
            path=store.census_acs_profile_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_census_acs_profile_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "equity_quote_alphavantage_AAPL": _cache_state(
            cache_id="equity_quote_alphavantage_AAPL",
            provider_id="alphavantage_global_quote_optional_key",
            path=store.alpha_vantage_equity_quote_cache_path(),
            root=root,
            ttl_seconds=86400,
            payload=store.read_alpha_vantage_equity_quote_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "equity_quote_alphavantage_MSFT": _cache_state(
            cache_id="equity_quote_alphavantage_MSFT",
            provider_id="alphavantage_global_quote_optional_key",
            path=store.alpha_vantage_equity_quote_cache_path("MSFT"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_alpha_vantage_equity_quote_cache("MSFT"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "equity_quote_alphavantage_NVDA": _cache_state(
            cache_id="equity_quote_alphavantage_NVDA",
            provider_id="alphavantage_global_quote_optional_key",
            path=store.alpha_vantage_equity_quote_cache_path("NVDA"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_alpha_vantage_equity_quote_cache("NVDA"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "etf_quote_alphavantage_SPY": _cache_state(
            cache_id="etf_quote_alphavantage_SPY",
            provider_id="alphavantage_global_quote_optional_key",
            path=store.alpha_vantage_equity_quote_cache_path("SPY"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_alpha_vantage_equity_quote_cache("SPY"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "etf_quote_alphavantage_QQQ": _cache_state(
            cache_id="etf_quote_alphavantage_QQQ",
            provider_id="alphavantage_global_quote_optional_key",
            path=store.alpha_vantage_equity_quote_cache_path("QQQ"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_alpha_vantage_equity_quote_cache("QQQ"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "etf_quote_alphavantage_IWM": _cache_state(
            cache_id="etf_quote_alphavantage_IWM",
            provider_id="alphavantage_global_quote_optional_key",
            path=store.alpha_vantage_equity_quote_cache_path("IWM"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_alpha_vantage_equity_quote_cache("IWM"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "fx_quote_alphavantage_EURUSD": _cache_state(
            cache_id="fx_quote_alphavantage_EURUSD",
            provider_id="alphavantage_global_quote_optional_key",
            path=store.alpha_vantage_fx_quote_cache_path("EUR/USD"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_alpha_vantage_fx_quote_cache("EUR/USD"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "fx_quote_alphavantage_USDJPY": _cache_state(
            cache_id="fx_quote_alphavantage_USDJPY",
            provider_id="alphavantage_global_quote_optional_key",
            path=store.alpha_vantage_fx_quote_cache_path("USD/JPY"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_alpha_vantage_fx_quote_cache("USD/JPY"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "fx_quote_alphavantage_GBPUSD": _cache_state(
            cache_id="fx_quote_alphavantage_GBPUSD",
            provider_id="alphavantage_global_quote_optional_key",
            path=store.alpha_vantage_fx_quote_cache_path("GBP/USD"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_alpha_vantage_fx_quote_cache("GBP/USD"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "twelve_data_quote_AAPL": _cache_state(
            cache_id="twelve_data_quote_AAPL",
            provider_id="twelve_data_quote_optional_key",
            path=store.twelve_data_quote_cache_path("AAPL"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_twelve_data_quote_cache("AAPL"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "twelve_data_quote_SPY": _cache_state(
            cache_id="twelve_data_quote_SPY",
            provider_id="twelve_data_quote_optional_key",
            path=store.twelve_data_quote_cache_path("SPY"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_twelve_data_quote_cache("SPY"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "twelve_data_quote_EURUSD": _cache_state(
            cache_id="twelve_data_quote_EURUSD",
            provider_id="twelve_data_quote_optional_key",
            path=store.twelve_data_quote_cache_path("EUR/USD"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_twelve_data_quote_cache("EUR/USD"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "finnhub_quote_AAPL": _cache_state(
            cache_id="finnhub_quote_AAPL",
            provider_id="finnhub_equity_quote_optional_key",
            path=store.finnhub_quote_cache_path("AAPL"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_finnhub_quote_cache("AAPL"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "finnhub_quote_MSFT": _cache_state(
            cache_id="finnhub_quote_MSFT",
            provider_id="finnhub_equity_quote_optional_key",
            path=store.finnhub_quote_cache_path("MSFT"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_finnhub_quote_cache("MSFT"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "finnhub_quote_NVDA": _cache_state(
            cache_id="finnhub_quote_NVDA",
            provider_id="finnhub_equity_quote_optional_key",
            path=store.finnhub_quote_cache_path("NVDA"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_finnhub_quote_cache("NVDA"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "finnhub_quote_SPY": _cache_state(
            cache_id="finnhub_quote_SPY",
            provider_id="finnhub_equity_quote_optional_key",
            path=store.finnhub_quote_cache_path("SPY"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_finnhub_quote_cache("SPY"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "fmp_quote_AAPL": _cache_state(
            cache_id="fmp_quote_AAPL",
            provider_id="fmp_stock_quote_optional_key",
            path=store.fmp_quote_cache_path("AAPL"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_fmp_quote_cache("AAPL"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "fmp_quote_MSFT": _cache_state(
            cache_id="fmp_quote_MSFT",
            provider_id="fmp_stock_quote_optional_key",
            path=store.fmp_quote_cache_path("MSFT"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_fmp_quote_cache("MSFT"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "fmp_quote_NVDA": _cache_state(
            cache_id="fmp_quote_NVDA",
            provider_id="fmp_stock_quote_optional_key",
            path=store.fmp_quote_cache_path("NVDA"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_fmp_quote_cache("NVDA"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "fmp_quote_SPY": _cache_state(
            cache_id="fmp_quote_SPY",
            provider_id="fmp_stock_quote_optional_key",
            path=store.fmp_quote_cache_path("SPY"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_fmp_quote_cache("SPY"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "stooq_quote_AAPLUS": _cache_state(
            cache_id="stooq_quote_AAPLUS",
            provider_id="stooq_public_quote_snapshot",
            path=store.stooq_quote_cache_path("AAPL.US"),
            root=root,
            ttl_seconds=900,
            payload=store.read_stooq_quote_cache("AAPL.US"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "stooq_quote_SPYUS": _cache_state(
            cache_id="stooq_quote_SPYUS",
            provider_id="stooq_public_quote_snapshot",
            path=store.stooq_quote_cache_path("SPY.US"),
            root=root,
            ttl_seconds=900,
            payload=store.read_stooq_quote_cache("SPY.US"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "stooq_quote_SPX": _cache_state(
            cache_id="stooq_quote_SPX",
            provider_id="stooq_public_quote_snapshot",
            path=store.stooq_quote_cache_path("^SPX"),
            root=root,
            ttl_seconds=900,
            payload=store.read_stooq_quote_cache("^SPX"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "stooq_quote_EURUSD": _cache_state(
            cache_id="stooq_quote_EURUSD",
            provider_id="stooq_public_quote_snapshot",
            path=store.stooq_quote_cache_path("EURUSD"),
            root=root,
            ttl_seconds=900,
            payload=store.read_stooq_quote_cache("EURUSD"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "moex_quote_SBER": _cache_state(
            cache_id="moex_quote_SBER",
            provider_id="moex_iss_delayed_quote_snapshot",
            path=store.moex_quote_cache_path("SBER"),
            root=root,
            ttl_seconds=900,
            payload=store.read_moex_quote_cache("SBER"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "moex_quote_GAZP": _cache_state(
            cache_id="moex_quote_GAZP",
            provider_id="moex_iss_delayed_quote_snapshot",
            path=store.moex_quote_cache_path("GAZP"),
            root=root,
            ttl_seconds=900,
            payload=store.read_moex_quote_cache("GAZP"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "moex_quote_MOEX": _cache_state(
            cache_id="moex_quote_MOEX",
            provider_id="moex_iss_delayed_quote_snapshot",
            path=store.moex_quote_cache_path("MOEX"),
            root=root,
            ttl_seconds=900,
            payload=store.read_moex_quote_cache("MOEX"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "twse_quote_2330": _cache_state(
            cache_id="twse_quote_2330",
            provider_id="twse_openapi_daily_quote_snapshot",
            path=store.twse_quote_cache_path("2330"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_twse_quote_cache("2330"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "twse_quote_2317": _cache_state(
            cache_id="twse_quote_2317",
            provider_id="twse_openapi_daily_quote_snapshot",
            path=store.twse_quote_cache_path("2317"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_twse_quote_cache("2317"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "twse_quote_0050": _cache_state(
            cache_id="twse_quote_0050",
            provider_id="twse_openapi_daily_quote_snapshot",
            path=store.twse_quote_cache_path("0050"),
            root=root,
            ttl_seconds=86400,
            payload=store.read_twse_quote_cache("0050"),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "nasdaq_trader_symbol_directory": _cache_state(
            cache_id="nasdaq_trader_symbol_directory",
            provider_id="nasdaq_trader_symbol_directory_public",
            path=store.nasdaq_trader_symbol_directory_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_nasdaq_trader_symbol_directory_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "openfigi_identifier_mapping": _cache_state(
            cache_id="openfigi_identifier_mapping",
            provider_id="openfigi_identifier_mapping_public",
            path=store.openfigi_mapping_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_openfigi_mapping_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "rates_treasury_yield_curve": _cache_state(
            cache_id="rates_treasury_yield_curve",
            provider_id="us_treasury_yield_public",
            path=store.treasury_rates_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_treasury_rates_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "rates_nyfed_sofr": _cache_state(
            cache_id="rates_nyfed_sofr",
            provider_id="nyfed_sofr_public",
            path=store.nyfed_sofr_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_nyfed_sofr_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "fx_ecb_reference_rates": _cache_state(
            cache_id="fx_ecb_reference_rates",
            provider_id="ecb_fx_reference_public",
            path=store.ecb_fx_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_ecb_fx_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "fx_federal_reserve_h10_reference_rates": _cache_state(
            cache_id="fx_federal_reserve_h10_reference_rates",
            provider_id="federal_reserve_h10_ddp_public",
            path=store.federal_reserve_h10_fx_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_federal_reserve_h10_fx_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "fx_bank_of_canada_valet_reference_rates": _cache_state(
            cache_id="fx_bank_of_canada_valet_reference_rates",
            provider_id="bank_of_canada_valet_fx_reference_public",
            path=store.bank_of_canada_fx_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_bank_of_canada_fx_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "commodities_world_bank_monthly": _cache_state(
            cache_id="commodities_world_bank_monthly",
            provider_id="world_bank_commodity_monthly_public",
            path=store.world_bank_commodity_cache_path,
            root=root,
            ttl_seconds=604800,
            payload=store.read_world_bank_commodity_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "commodities_cftc_cot_legacy": _cache_state(
            cache_id="commodities_cftc_cot_legacy",
            provider_id="cftc_cot_legacy_public",
            path=store.cftc_cot_cache_path,
            root=root,
            ttl_seconds=604800,
            payload=store.read_cftc_cot_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "eia_energy_series": _cache_state(
            cache_id="eia_energy_series",
            provider_id="eia_open_data_optional_key",
            path=store.eia_energy_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_eia_energy_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
        "funds_sec_tickers": _cache_state(
            cache_id="funds_sec_tickers",
            provider_id="sec_fund_ticker_registry_public",
            path=store.sec_fund_tickers_cache_path,
            root=root,
            ttl_seconds=86400,
            payload=store.read_sec_fund_tickers_cache(),
            timestamp_keys=("last_update",),
            nested_status=True,
        ),
    }
    providers = [_provider_with_health(entry, cache_states) for entry in PROVIDER_REGISTRY]
    state_counts = Counter(provider["health"]["state"] for provider in providers)
    # Derived from ERROR_STATES rather than hand-listed. The hand-listed
    # version was written before "retired" existed, so when stooq's endpoint
    # closed and the state was added to the catalogue the summary silently
    # stopped adding up: 33 counted against 34 providers, with one simply
    # absent (2026-07-27 dogfood). A new state now cannot be forgotten here.
    summary = {
        "provider_count": len(providers),
        "implemented_count": sum(
            1 for provider in providers if provider["implementation_status"] == "implemented"
        ),
        "active": state_counts.get(CACHE_STATE_ACTIVE, 0),
        **{state: state_counts.get(state, 0) for state in ERROR_STATES},
    }
    # Anything the registry reports that neither the catalogue nor "active"
    # covers. Nonzero means a provider is in a state nothing on screen can
    # name, which is worth surfacing rather than rounding away.
    summary["uncategorised"] = len(providers) - sum(
        summary[key] for key in (CACHE_STATE_ACTIVE, *ERROR_STATES)
    )
    # "Is a capability I rely on going unserved right now?" — not "is any row
    # in a non-active state", which counts things that are working as designed.
    #
    # A first pass at this counted unavailable + retired and put "2 不能用" on
    # the system page. Both were false alarms. Coinbase is a fallback whose own
    # entry says it is used only after Binance and Kraken fail; it has no cache
    # because the primaries have not failed. Stooq is retired with its
    # successor named in the message — replaced, not broken. Neither is
    # something the owner can or should act on (2026-07-27 dogfood, correcting
    # the same day's earlier commit).
    standby = sum(
        1
        for provider in providers
        if provider["health"]["state"] == "unavailable"
        and provider["implementation_status"] == "implemented_fallback"
    )
    summary["standby"] = standby
    summary["superseded"] = summary["retired"]
    # A primary with nothing to serve, or a provider being throttled, is a real
    # loss of service. plan_required and disabled_by_safety are deliberate — a
    # tier we do not buy and the live-trading gate — and are reported elsewhere.
    summary["broken"] = summary["unavailable"] - standby + summary["rate_limited"]
    return {
        "generated_at": _utc_now(),
        "docs_checked_at": DOCS_CHECKED_AT,
        "entry_template": PROVIDER_ENTRY_TEMPLATE,
        "error_state_catalog": ERROR_STATE_CATALOG,
        "summary": summary,
        "providers": providers,
        "caches": list(cache_states.values()),
        "freshness_strip": [_freshness_item(provider) for provider in providers],
        "safety": {
            "private_api_keys_persisted": False,
            "live_execution_reachable": False,
            "paid_provider_enabled": False,
            "installed_source_used": False,
        },
    }


def provider_cache_payload(store: Any) -> dict[str, Any]:
    payload = providers_payload(store)
    return {
        "generated_at": payload["generated_at"],
        "summary": payload["summary"],
        "caches": payload["caches"],
        "error_state_catalog": payload["error_state_catalog"],
    }


def _provider_with_health(
    entry: dict[str, Any],
    cache_states: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    provider = {**entry}
    if str(provider.get("implementation_status", "")).startswith("retired"):
        provider["health"] = {
            "state": "retired",
            "runtime_source": provider["provider_id"],
            "retrieved_at": "",
            "age_seconds": None,
            "cache_path": "",
            "message": (
                "Upstream endpoint was closed by the provider; "
                "markets_quote_lookup (Yahoo) supersedes it."
            ),
        }
        return provider
    cache_policy = provider.get("cache_policy", {})
    cache_id = cache_policy.get("cache_id")
    cache_candidates = [cache_states.get(str(cache_id))]
    secondary_cache_ids = cache_policy.get("secondary_cache_ids")
    if isinstance(secondary_cache_ids, list):
        cache_candidates.extend(
            cache_states.get(str(candidate))
            for candidate in secondary_cache_ids
            if candidate
        )
    cache = next(
        (
            candidate
            for candidate in cache_candidates
            if isinstance(candidate, dict) and candidate["state"] != "unavailable"
        ),
        cache_candidates[0],
    )
    detail_cache = cache_states.get("crypto_public_detail")
    if (
        isinstance(detail_cache, dict)
        and detail_cache["provider_id"] == provider["provider_id"]
        and detail_cache["state"] != "unavailable"
    ):
        cache = detail_cache
    default_state = str(provider.get("capability_state") or "")
    if (
        cache is not None
        and cache["state"] == "unavailable"
        and default_state in ERROR_STATES
    ):
        state = default_state
        message = ERROR_STATE_CATALOG[state]["meaning"]
        runtime_source = provider["provider_id"]
        cache = None
    elif cache is not None:
        state = cache["state"]
        message = cache["message"]
        runtime_source = cache["runtime_source"]
    elif default_state in ERROR_STATES:
        state = default_state
        message = ERROR_STATE_CATALOG[state]["meaning"]
        runtime_source = provider["provider_id"]
    else:
        state = "unavailable"
        message = "Adapter is implemented or planned, but no cache state is present."
        runtime_source = provider["provider_id"]

    provider["health"] = {
        "state": state,
        "runtime_source": runtime_source,
        "message": message,
        "cache_id": cache["cache_id"] if cache else cache_id or "",
        "cache_path": cache["path"] if cache else str(cache_policy.get("path") or ""),
        "retrieved_at": cache["retrieved_at"] if cache else "",
        "age_seconds": cache["age_seconds"] if cache else None,
        "stale_after_seconds": cache["ttl_seconds"] if cache else cache_policy.get("ttl_seconds", 0),
        "source_url": provider.get("source_attribution", {}).get("url", ""),
    }
    return provider


def _cache_state(
    *,
    cache_id: str,
    provider_id: str,
    path: Path,
    root: Path,
    ttl_seconds: int,
    payload: dict[str, Any],
    timestamp_keys: tuple[str, ...],
    nested_status: bool,
) -> dict[str, Any]:
    status = payload.get("status") if nested_status else payload
    status = status if isinstance(status, dict) else {}
    timestamp = _first_timestamp(status, timestamp_keys)
    source = str(status.get("source") or provider_id)
    runtime_state = str(status.get("state") or "")
    if runtime_state == "rate_limited":
        state = "rate_limited"
        message = "Provider reported rate limiting; retain stale cache and back off."
    elif timestamp is None:
        state = "unavailable"
        message = "No provider cache timestamp is available yet."
    else:
        age_seconds = max(0, int((datetime.now(tz=UTC) - timestamp).total_seconds()))
        state = CACHE_STATE_ACTIVE if age_seconds <= ttl_seconds else "stale_cache"
        message = (
            "Provider cache is within TTL."
            if state == CACHE_STATE_ACTIVE
            else "Provider cache exists but is older than TTL."
        )
        return {
            "cache_id": cache_id,
            "provider_id": provider_id,
            "path": _relative(path, root),
            "exists": path.exists(),
            "state": state,
            "runtime_source": source,
            "retrieved_at": timestamp.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "age_seconds": age_seconds,
            "ttl_seconds": ttl_seconds,
            "message": message,
        }

    return {
        "cache_id": cache_id,
        "provider_id": provider_id,
        "path": _relative(path, root),
        "exists": path.exists(),
        "state": state,
        "runtime_source": source,
        "retrieved_at": "",
        "age_seconds": None,
        "ttl_seconds": ttl_seconds,
        "message": message,
    }


def _freshness_item(provider: dict[str, Any]) -> dict[str, Any]:
    health = provider["health"]
    return {
        "provider_id": provider["provider_id"],
        "label": provider["label"],
        "state": health["state"],
        "source": health["runtime_source"],
        "retrieved_at": health["retrieved_at"],
        "age_seconds": health["age_seconds"],
        "cache_path": health["cache_path"],
        "message": health["message"],
        "auth_mode": provider["auth_mode"],
        "safety_class": provider["safety_class"],
    }


def _first_timestamp(status: dict[str, Any], keys: tuple[str, ...]) -> datetime | None:
    for key in keys:
        raw = status.get(key)
        if not isinstance(raw, str) or raw in {"", "not refreshed", "not started", "unknown"}:
            continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def _relative(path: Path, root: Path) -> str:
    if not path:
        return ""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
