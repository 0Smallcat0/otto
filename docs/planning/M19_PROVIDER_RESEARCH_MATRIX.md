# M19 Provider Research Matrix

This matrix is planning evidence for the next long-running rebuild. It does not authorize writing API keys to the repo, enabling paid services, or creating live trading paths.

## Provider Strategy

Runtime user-visible data should come from real provider adapters or clearly labeled disabled/gated surfaces. Deterministic fixtures remain valid for tests and offline fallback only. Provider adapters must expose `source`, `freshness`, `retrieved_at`, `cache_path`, `license_note`, and `capability_state` so the UI can avoid vague `Not connected` states.

## Matrix Schema

| Field | Required meaning |
| --- | --- |
| Provider | Human-readable provider name and adapter id. |
| Coverage | Asset classes or workflows covered: crypto, stocks, ETF, FX, commodities, news, macro, fundamentals, options, etc. |
| Official source | Primary documentation URL used for implementation. |
| Auth mode | `no-key`, `optional-local-key`, `paid-gated`, or `forbidden-live/private`. |
| Terms/license risk | Main usage and redistribution risk to document before implementation. |
| Rate limits | Known limits or where to read them. |
| Complexity | Low/medium/high for a local Python adapter. |
| Local cache strategy | Cache path, TTL, stale behavior, and provenance. |
| Test fixture strategy | Deterministic payloads created from adapter contracts, not user-visible runtime data. |
| Fallback behavior | How UI behaves on provider failure without becoming an empty shell. |
| Clean-room/safety implication | Boundary notes, especially key handling and live trading separation. |

## Candidate Providers

| Provider | Coverage | Official source | Auth mode | Terms/license risk | Rate limits | Complexity | Local cache strategy | Test fixture strategy | Fallback behavior | Clean-room/safety implication |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Binance Spot public market data | Crypto ticker, depth, trades, klines | https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints | no-key for public market data | Exchange terms; display attribution and do not imply broker connectivity | Endpoint request weights are documented per endpoint | Low | `market_data/binance/{symbol}/{endpoint}.json`, short TTL for ticker/depth, longer TTL for candles | Contract fixtures for depth/ticker/kline shapes | Show stale cached crypto data with last update, retry action, and provider error detail | Market data only. Do not use trading/account endpoints. |
| Kraken public market data | Crypto OHLC, ticker, order book, trades | https://docs.kraken.com/api/docs/rest-api/get-ohlc-data/ | no-key for public market data | Exchange terms; OHLC history is limited | OHLC returns up to recent 720 entries | Low-medium | `market_data/kraken/{pair}/{endpoint}.json` with interval-aware TTL | Contract fixtures for recent OHLC/order book | Pair-level stale cache and provider-specific warning | Market data only. Private/account/trading endpoints are out of scope. |
| Coinbase Advanced Trade public endpoints | Crypto public products, book, candles, market trades | https://docs.cdp.coinbase.com/coinbase-business/advanced-trade-apis/rest-api | no-key public endpoints; private endpoints require auth | Exchange terms; do not mix public endpoints with account/trade endpoints | Public endpoints use 1s cache per docs; authenticated/private endpoints forbidden for now | Medium | `market_data/coinbase/{product}/...` with 1s+ TTL controls | Public product/candle/book payload fixtures | Use public product/book/candle state; if unavailable fall back to Binance/Kraken chain | Explicit adapter allowlist must block private orders/accounts/futures/perps. |
| SEC EDGAR data APIs | US company submissions, XBRL company facts, frames | https://www.sec.gov/search-filings/edgar-application-programming-interfaces | no-key | Must comply with SEC automated access policies and respectful User-Agent | SEC publishes access guidance; bulk ZIPs available for large data | Medium | `fundamentals/sec/{cik}/companyfacts.json`, nightly/filing-aware TTL | Small companyfacts/submissions fixture with source metadata | Company panels show filing facts, update delay, and missing concept states | No private data. No scraping source pages beyond documented APIs. |
| SEC company ticker registry | Public company ticker, CIK, and EDGAR company-name mapping | https://www.sec.gov/files/company_tickers.json | no-key | Public SEC reference mapping; do not present rows as stock quotes | Use daily local cache and declared User-Agent under SEC fair-access guidance | Low | `fundamentals/sec/company_tickers.json`, daily TTL | Object fixture for AAPL/MSFT/NVDA | Stocks tab shows issuer registry/source/cache rows and keeps quote provider separate | Reference data only. No quote feed, private data, trading, or subscription path. |
| SEC fund ticker registry | ETF/fund CIK, series, class, ticker mapping | https://www.sec.gov/edgar/searchedgar/accessing-edgar-data.htm and https://www.sec.gov/files/company_tickers_mf.json | no-key | Public SEC reference mapping; do not present rows as ETF quotes | Use daily local cache and declared User-Agent under SEC fair-access guidance | Low-medium | `funds/sec/company_tickers_mf.json`, daily TTL | Fields/data fixture for QQQ/VTI/IVV/BND/BNDX/KWEB | ETF tab shows registry/source/cache rows and quote gate | Reference data only. No quote feed, private data, trading, or subscription path. |
| FRED API | Macro/economic series and release calendar data | https://fred.stlouisfed.org/docs/api/api_key.html, https://fred.stlouisfed.org/docs/api/fred/series_observations.html, and https://fred.stlouisfed.org/docs/api/terms_of_use.html | optional-local-key | API key belongs to user and must stay local | FRED requires user-owned API keys for web service requests and may limit traffic | Low-medium | `macro/fred/{series_id}.json`, series frequency TTL | Series observations fixture with key redacted | M20.25 implements `DGS10` behind local secret store; without a stored key the UI shows `key_required` and no fixture runtime data | Store key only in local secret store, never in repo/logs/screenshots; show source notice and no endorsement/logo behavior. |
| DBnomics | Macro/economic time series from public institutions | https://db.nomics.world/about | no-key/public web API | Source data keeps original provider terms; DBnomics aggregate under ODbL | Rate limits to verify per docs before adapter | Medium | `macro/dbnomics/{provider}/{dataset}/{series}.json`, daily TTL | Series fixture with source provider identifiers | Show macro series from public sources before key-gated FRED when possible | Good no-key first macro adapter, but preserve source attribution. |
| World Bank Commodity Markets Pink Sheet | Commodities, energy, metals, agriculture, monthly reference prices | https://www.worldbank.org/en/research/commodity-markets | no-key | Public reference data; preserve attribution and do not present monthly values as executable spot/futures quotes | Monthly public XLSX; use weekly local cache and avoid repeated downloads | Medium | `market_data/commodities/world_bank/pink_sheet_monthly.json`, weekly TTL | Minimal XLSX fixture generated in tests from adapter contract | Show stale monthly commodity values or explicit unavailable state with refresh guidance | Market/reference data only. No futures execution, leverage, margin, or private data. |
| Alpha Vantage | Stocks, ETF, FX, crypto, commodities, fundamentals, news-like data | https://www.alphavantage.co/documentation/, https://www.alphavantage.co/premium/, and https://www.alphavantage.co/terms_of_service/ | optional-local-key | Free/paid plan limits; user key required | M20.26 implements `GLOBAL_QUOTE` for `AAPL`; M20.27 extends the same reviewed pattern to `SPY` ETF quote cache. Official premium page states standard free usage is 25 requests/day, and docs state default quote freshness is end-of-day unless the user has realtime/delayed entitlement | Medium | `market_data/equities/alphavantage/global_quote/AAPL.json` and `market_data/equities/alphavantage/global_quote/SPY.json`, daily TTL | `Global Quote` fixture shape for tests only | Stocks and ETF tabs show quote cache or `key_required`, while SEC fundamentals/fund registry remain separate no-key reference sources | Key must be local secret only. Do not expose in frontend, docs, logs, screenshots; not part of public no-key refresh jobs. |
| Twelve Data | Stocks, ETF, mutual funds, FX, commodities, crypto, fundamentals | https://twelvedata.com/docs and https://twelvedata.com/pricing | optional-local-key / paid-gated | Plan/market-data display rights; premium endpoints gated | Credits per minute and 429 behavior documented | Medium-high | `market_data/twelvedata/{endpoint}/{symbol}.json`, credit-aware TTL | Fixture for time_series/price/errors | Capability-aware UI: available, needs key, needs plan, or rate-limited | Use only after local opt-in. No bundled key. |
| FMP | Stocks, historical prices, fundamentals, indexes, economics, crypto, forex, commodities, news | https://site.financialmodelingprep.com/developer/docs | optional-local-key / paid-gated | Free and paid plan restrictions; endpoint support varies | Free customers have daily request limits per FMP FAQ | Medium | `market_data/fmp/{endpoint}/{symbol}.json`, daily/rate-aware TTL | Fixture for quote/profile/history/fundamental endpoints | Show partial provider cards by endpoint support | Key local only; no subscription activation by agent. |
| Finnhub | Stocks, forex, crypto, company fundamentals, estimates, news, sentiment | https://finnhub.io/docs/api | optional-local-key / paid-gated | Free key and plan restrictions; endpoint/market entitlements vary | Rate limits vary by plan and endpoint | Medium | `market_data/finnhub/{endpoint}/{symbol}.json`, provider TTL | Quote/news/company fixtures | News and market widgets can use it only when key configured | Key local only; do not represent as account or brokerage integration. |
| Polygon/Massive | US stocks, options, indices, forex, crypto, economy, news-like/reference data | https://massive.com/docs/rest/stocks/overview | optional-local-key / paid-gated | Market-data plan and display rights; formerly Polygon branding may redirect | Free/basic plan capabilities vary by asset class | High | `market_data/polygon/{asset}/{endpoint}.json`, plan-aware TTL | Aggregate/snapshot fixture | Use as premium-ready provider, not default | No key in repo. Options data is data-only; no options execution. |
| Nasdaq Data Link | Free/premium economic and financial datasets | https://docs.data.nasdaq.com/docs/getting-started | optional-local-key / paid-gated | Many datasets premium/subscription; dataset-specific terms | Anonymous and authenticated limits documented by Nasdaq help | Medium | `market_data/nasdaq_data_link/{dataset}.json`, dataset TTL | Time-series/table fixture | Dataset browser can show free/premium/gated status | Do not subscribe/purchase automatically. |
| NewsAPI | General market/company news headlines/articles | https://newsapi.org/docs/endpoints | optional-local-key / paid-gated | News redistribution, plan, and source rights must be respected | Plan-specific rate limits | Low-medium | `news/newsapi/{query}.json`, short TTL | Headline/search fixture | News route shows source, date, and key-needed setup state | No key in repo; avoid full article copying. |
| GDELT Cloud | Structured global news/events/stories/entities | https://docs.gdeltcloud.com/api-reference/v2 | optional-local-key | Requires API key format in docs; generated structured data, not direct market news | To verify per account/docs | Medium | `news/gdelt/{query}.json`, hourly TTL | Event/story fixture | Macro/geopolitical news panels can show structured event feed | Key local only; attribution and no raw article copying. |

## Recommended Provider Build Order

1. Build a provider registry and cache contract that all routes can consume.
2. Replace visible crypto fixture states with Binance/Kraken/Coinbase public adapter chain.
3. Add SEC and DBnomics no-key adapters for company fundamentals and macro panels.
4. Add optional local secret gate contract and provider setup UI before implementing key-gated adapters. M20.24 enables reviewed local persistence for eligible data-provider keys; M20.25 uses it for the first FRED adapter, M20.26 uses it for Alpha Vantage stock quote, and M20.27 extends Alpha Vantage to ETF quote while keeping paid/live/private paths blocked.
5. Add one key-gated multi-asset provider adapter behind explicit local opt-in.
6. Add news provider adapter after source/license display rules are implemented.
7. Keep broker/private/live APIs as disabled future milestones until the live-safety contract is independently completed.

## Provider Adapter Entry Gate

Before implementing any provider adapter, create a short provider entry note or code-adjacent metadata record with:

- official documentation URL and date checked
- exact endpoints to use
- auth mode and whether credentials are forbidden, optional local-only, or paid-gated
- rate limits/request weights and TTL implications
- terms/license/display-risk summary
- local cache path and retention policy
- normalized schemas and provider error states
- test fixture source and redaction rules
- fallback behavior when network, auth, rate limit, or plan fails
- UI source attribution requirements
- safety boundary: market-data-only, no account/trading/private/live path

Optional-key providers require the reviewed local secret-storage gate, provider-entry metadata, redaction tests, and UI attribution before use. Paid/subscription providers remain recorded as options only; no purchase, activation, or bundled key is permitted.

## Sources

- Binance Spot Market Data: https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints
- Kraken OHLC Data: https://docs.kraken.com/api/docs/rest-api/get-ohlc-data/
- Coinbase Advanced Trade Endpoints: https://docs.cdp.coinbase.com/coinbase-business/advanced-trade-apis/rest-api
- SEC EDGAR APIs: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC EDGAR Accessing Data / fund ticker registry: https://www.sec.gov/edgar/searchedgar/accessing-edgar-data.htm, https://www.sec.gov/files/company_tickers_mf.json
- FRED API Key and Series Observations: https://fred.stlouisfed.org/docs/api/api_key.html, https://fred.stlouisfed.org/docs/api/fred/series_observations.html
- DBnomics About/API: https://db.nomics.world/about
- World Bank Commodity Markets: https://www.worldbank.org/en/research/commodity-markets
- Alpha Vantage Documentation: https://www.alphavantage.co/documentation/
- Twelve Data Documentation/Pricing: https://twelvedata.com/docs, https://twelvedata.com/pricing
- FMP Documentation: https://site.financialmodelingprep.com/developer/docs
- Finnhub Documentation: https://finnhub.io/docs/api
- Polygon/Massive Stocks REST Overview: https://massive.com/docs/rest/stocks/overview
- Nasdaq Data Link Getting Started: https://docs.data.nasdaq.com/docs/getting-started
- NewsAPI Endpoints: https://newsapi.org/docs/endpoints
- GDELT Cloud API v2: https://docs.gdeltcloud.com/api-reference/v2
