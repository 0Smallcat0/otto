# M21 Provider Research Matrix

Date: 2026-06-01

## Rules

- Use official docs and primary sources.
- Prefer public no-key providers.
- Optional personal/free keys are allowed only through local secret storage.
- Paid-gated providers are recorded as options only; do not activate payment or
  subscription flows.
- Broker/private/live providers remain forbidden until a separate safety goal.

## Source Verification

Official or primary-source documentation was refreshed on 2026-05-24 before using this
matrix as M21 planning evidence:

- SEC EDGAR application programming interfaces.
- U.S. Treasury daily interest rate XML feed.
- ECB euro foreign exchange reference feed.
- Federal Reserve H.10 Data Download Program.
- Bank of Canada Valet API and exchange-rate background pages, refreshed on
  2026-05-26 for the bounded CAD FX reference-rate slice.
- New York Fed SOFR reference-rate page and Markets Data API, refreshed again
  on 2026-05-26 for the Bonds/Rates SOFR implementation slice.
- World Bank Commodity Markets page.
- CFTC Commitments of Traders reports and Public Reporting Environment Socrata
  API, refreshed on 2026-05-26 for the Commodities positioning-context slice.
- DBnomics documentation.
- BLS Public Data API developer documentation.
- FRED API documentation.
- BEA API and Web Service API User Guide, refreshed again on 2026-05-25 for the
  Regional `SAGDP9N` implementation slice.
- U.S. Census Data API key guide and 2023 ACS 5-year Data Profile docs,
  refreshed again on 2026-05-25 for the Regional ACS implementation slice.
- Alpha Vantage API documentation.
- EIA Open Data API documentation.
- GDELT DOC 2.0 API reference article.
- GDELT Cloud API documentation.
- Twelve Data API/pricing/credit documentation, refreshed again on 2026-05-25
  for the `/quote` implementation slice.
- Finnhub quote and rate-limit documentation, refreshed on 2026-05-26 for the
  bounded optional-key equity quote watchlist slice.
- Stooq quote and historical data pages, refreshed on 2026-05-26 for the bounded
  public quote snapshot slice. Current quote CSV rows were public no-key in live
  smoke tests; historical CSV download returned a CAPTCHA/API-link gate and is
  not implemented.
- Nasdaq Trader Symbol Directory docs and downloadable text files, refreshed on
  2026-05-26 for the public symbol-directory slice. The official symbol-directory
  docs list `nasdaqlisted.txt` and `otherlisted.txt`, and the no-write live smoke
  normalized the files as reference-only rows without credentials.
- MOEX ISS documentation and developer manual, refreshed on 2026-05-26 for the
  bounded delayed quote snapshot slice. Live no-secret ISS smoke returned
  `SBER/GAZP/MOEX` shares marketdata rows on board `TQBR`; rows are delayed and
  non-orderable.
- OpenFIGI API documentation and v3 mapping endpoint, refreshed on 2026-05-27
  for the bounded identifier-mapping slice. The local adapter uses public
  no-key mapping jobs only and treats returned FIGI rows as reference metadata,
  not quotes or tradeability evidence.
- Cboe Delayed Quotes pages, refreshed on 2026-05-26 for provider-entry gate
  classification. The official delayed-quote page is kept as a human lookup and
  blocked automation candidate, not a local adapter source.
- IEX TOPS/DEEP market-data materials, refreshed on 2026-05-26 for provider-entry
  gate classification. The official materials route real-time feeds through
  market-data agreements, forms, connectivity, and fee-schedule terms, not an
  unattended public no-key REST quote source.
- Nasdaq Data Link getting-started, data organization, and legacy API-key
  documentation, refreshed on 2026-05-31 for provider-entry gate
  classification.
- JPX/J-Quants website, JPX January 19 2026 J-Quants API enhancement release,
  JPxData Portal page, and JPX monthly quotations page, refreshed on 2026-05-31
  for provider-entry gate classification.
- Yahoo API terms, Yahoo Developer Network guidelines, Yahoo Developer Network
  privacy materials, and Yahoo API credential terms, refreshed on 2026-06-01
  for provider-entry gate classification.

## Matrix

| Provider | Coverage | Official docs | Auth mode | Rate / limits notes | Terms / display risk | M21 decision |
| --- | --- | --- | --- | --- | --- | --- |
| SEC EDGAR data APIs | Fundamentals, submissions, company facts, fund ticker registry | https://www.sec.gov/search-filings/edgar-application-programming-interfaces | no-key | SEC fair-access guidance applies; existing repo records 10 req/sec guidance and declared User-Agent requirements. | Public government data; preserve attribution and do not represent fundamentals, ticker registries, or filings as quotes. | Implemented for company facts, company/fund ticker registries, M21.16 company submissions metadata, and M21.19 bounded `AAPL/MSFT/NVDA` submissions watchlist caches. |
| U.S. Treasury daily yield curve | Treasury rates, bonds/rates reference | https://home.treasury.gov/treasury-daily-interest-rate-xml-feed | no-key | Daily reference feed. | Public reference data; not executable quotes. | Already implemented; keep as rates reference. |
| New York Fed SOFR | Secured Overnight Financing Rate, overnight rates reference | https://www.newyorkfed.org/markets/reference-rates/sofr and https://markets.newyorkfed.org/static/docs/markets-api.html | no-key | Daily public Markets API reference-rate rows; use daily local cache. | Reference rate data only; preserve New York Fed attribution and do not treat as executable quote or funding trade. | Implemented in M23.11 as `nyfed_sofr_public` with Markets `overnight_reference_rate` coverage. |
| ECB euro foreign exchange reference rates | EUR FX reference rates | https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml | no-key | Daily reference feed. | Reference rates only; do not treat as executable spot FX. | Already implemented; keep as FX reference. |
| Federal Reserve H.10 Data Download Program | USD FX reference rates | https://www.federalreserve.gov/datadownload/choose.aspx?rel=h10 | no-key | Daily public Data Download package; use local cache. | Reference rates only; preserve Federal Reserve attribution and do not treat as executable spot FX. | Implemented in M23.1 as `federal_reserve_h10_ddp_public` with Markets `usd_reference_rates` coverage. |
| Bank of Canada Valet FX observations | CAD FX reference rates | https://www.bankofcanada.ca/valet/docs and https://www.bankofcanada.ca/rates/exchange/ | no-key | Daily public Valet observations; use bounded series and daily local cache. | Bank of Canada exchange rates are indicative reference data; preserve attribution and do not treat as executable spot FX. | Implemented in M23.31 as `bank_of_canada_valet_fx_reference_public` with Markets `cad_reference_rates` coverage. |
| World Bank Commodity Markets Pink Sheet | Monthly commodity reference prices | https://www.worldbank.org/en/research/commodity-markets | no-key public file | Monthly reference cadence. | Reference data only; not spot/futures quotes. | Already implemented; keep as commodities reference. |
| CFTC Commitments of Traders Legacy Futures Only | Weekly commodity positioning context for selected futures contracts | https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm and https://dev.socrata.com/foundry/publicreporting.cftc.gov/6dca-aqww | no-key public endpoint | Weekly public reporting data; use bounded contract filters and weekly local cache. | Public positioning context only; preserve CFTC attribution and do not represent COT rows as spot prices, futures quotes, broker signals, or derivatives execution data. | Implemented in M23.14 as `cftc_cot_legacy_public` for Markets Commodities positioning context. |
| DBnomics | Public macro/economic series | https://docs.db.nomics.world/ | no-key | Dataset-specific cadence; use local cache. | Preserve institution/source attribution. | Already implemented; keep as macro provider. |
| BLS Public Data API | Labor, inflation, and official U.S. macro/labor series | https://www.bls.gov/developers/api_signature_v2.htm | no-key | Latest-series API supports bounded no-key requests; use daily local cache. | Public government macro/labor data; preserve BLS attribution and do not represent it as executable quotes. | Implemented in M21.9 for Markets Indexes/Regional macro context. |
| Eurostat Statistics API | Euro area HICP inflation macro context | https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-detailed-guidelines/api-statistics and https://ec.europa.eu/eurostat/databrowser/view/prc_hicp_midx/default/table | no-key | Bounded Statistics API request with `lastTimePeriod=3`, `geo=EA20`, `coicop=CP00`, `unit=I15`, and daily local cache. | Official Eurostat macro/reference data only; preserve attribution and do not represent HICP rows as executable quotes, balances, trade signals, or orderable instruments. | Implemented in M23.50 as `eurostat_hicp_public` for Markets Indexes/Regional macro context. |
| FRED | Macro series and release data | https://fred.stlouisfed.org/docs/api/fred/ | optional local key | FRED docs require API keys for web service requests. | User-owned key; preserve FRED attribution and terms. | Already implemented for `DGS10`; expand only behind local secret storage. |
| BEA Regional API | State GDP and regional macro context | https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf | optional local key | BEA Regional `GetData` requires a user-owned UserID; keep bounded `SAGDP9N` state rows with daily local cache. | Public government macro data; preserve BEA attribution and never represent it as quotes, balances, or trade instructions. | Implemented in M23.5 for Markets Regional context behind the local secret gate. |
| U.S. Census Data API | ACS state demographic/economic context | https://www.census.gov/data/developers/guidance/api-user-guide.API_Key.html and https://api.census.gov/data/2023/acs/acs5/profile.html | optional local key | Current Census guidance requires an API key for data queries; keep a bounded ACS 5-year Data Profile state slice with daily local cache. | Public government demographic/economic data; preserve Census attribution and never represent it as quotes, balances, or trade instructions. | Implemented in M23.6 for Markets Regional context behind the local secret gate. |
| Alpha Vantage | Stock/ETF quotes, FX, commodities, indicators, news/sentiment | https://www.alphavantage.co/documentation/ | optional local key | `GLOBAL_QUOTE` returns one ticker per request; `CURRENCY_EXCHANGE_RATE` returns one currency pair per request; bulk quote is premium. Keep bounded per-symbol/per-pair caches and do not rely on paid bulk behavior. | Do not imply paid realtime coverage; show stale/rate-limited/key-required states, keep FX quote rows non-orderable. | Implemented for bounded Stocks `AAPL/MSFT/NVDA` and ETF `SPY/QQQ/IWM` quote watchlists in M21.6, and bounded FX `EUR/USD`, `USD/JPY`, `GBP/USD` quote watchlist in M23.2. |
| EIA Open Data API | Energy datasets and commodity/energy context | https://www.eia.gov/opendata/documentation.php | free API key | EIA APIv2 requires a unique key sent as query parameter. | Public energy data; source attribution required; not tradable commodity quotes. | Implemented in M21.3 for optional-key Markets Commodities energy context. |
| GDELT Project DOC API | Global news article discovery and topic search | https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/ | no-key public endpoint | Use bounded queries and local cache; HTTP 429 must degrade to partial/stale/offline state. | Link/metadata only; do not copy full articles. | Implemented in M21.2 for News metadata breadth and intel-strip state. |
| GDELT Cloud API v2 | Events, stories, entities, geography, energy | https://docs.gdeltcloud.com/api-reference | API-key-authenticated cloud product | Requires key-authenticated Cloud API. | Cloud-product semantics; do not confuse with no-key DOC API. | Record only unless user explicitly authorizes signup. |
| Twelve Data | Multi-asset market data | https://twelvedata.com/docs/llms and https://twelvedata.com/docs/llms/market-data | optional local key / quota-gated | `/quote` costs 1 API credit per symbol; keep bounded symbols and daily local caches. | Avoid paid/credit dependency as primary runtime; quote rows are non-orderable. | Implemented in M23.4 as bounded secondary `AAPL/SPY/EURUSD` quote watchlist behind the local secret gate. |
| Finnhub | Equity quote snapshots | https://finnhub.io/docs/api/quote and https://finnhub.io/docs/api/rate-limit | optional local key | `/quote` requires a user token; keep bounded `AAPL/MSFT/NVDA/SPY` requests and daily local caches. | User-owned key only; quote rows are non-orderable and must not imply broker routing, balances, or live trading. | Implemented in M23.34 as `finnhub_equity_quote_optional_key` behind the local secret gate. |
| Stooq | Delayed/current public quote snapshots for selected equities, ETF, index, and FX symbols | https://stooq.com/q/?s=^spx and https://stooq.com/db/h/ | no-key for current quote CSV snapshot; historical CSV download CAPTCHA/API-link gated | Keep bounded per-symbol current CSV snapshot requests and 15-minute local cache; do not crawl pages or use bulk historical download. | Public quote snapshots are non-orderable delayed/reference data; historical download is blocked by CAPTCHA/API-link gate. | Implemented in M23.16 as `stooq_public_quote_snapshot` for bounded `AAPL.US/SPY.US/^SPX/EURUSD` snapshots. |
| Nasdaq Trader Symbol Directory | Nasdaq-listed and other-listed security symbol reference metadata | https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs plus `nasdaqlisted.txt` and `otherlisted.txt` | no-key | Files are updated periodically throughout the day; use a daily local cache and do not scrape pages or use market-data feeds. | Reference identifiers only; not quotes, broker availability, balances, or executable market data. | Implemented in M23.17 as `nasdaq_trader_symbol_directory_public`; M23.18 adds cache-only Markets/AI Agent symbol search. |
| OpenFIGI v3 Mapping | Ticker-to-FIGI/security identifier reference metadata | https://www.openfigi.com/api/documentation and https://api.openfigi.com/v3/mapping | no-key for bounded public mapping jobs | Use small `TICKER`/`US` mapping batches and a daily local cache; do not use OpenFIGI as a quote or instrument-routing provider. | Identifier/reference metadata only; preserve attribution and do not represent FIGI rows as prices, broker availability, balances, tradeability, or executable market data. | Implemented in M23.53 as `openfigi_identifier_mapping_public` for bounded `AAPL/MSFT/SPY` identifier mapping rows. |
| MOEX ISS | Delayed shares marketdata quote snapshots for selected MOEX securities | https://www.moex.com/a2920 and https://www.moex.com/files/4be999zbzp80bx2bgmwayrtyx0 | no-key delayed public marketdata | Keep bounded per-symbol `SBER/GAZP/MOEX` snapshot requests and 15-minute local cache; do not use authenticated realtime feeds, orderbooks, or private trading APIs. | Public delayed quote snapshots are non-orderable; do not imply tradeability, broker connectivity, balances, or executable order routing. | Implemented in M23.19 as `moex_iss_delayed_quote_snapshot` for bounded `SBER/GAZP/MOEX` snapshots. |
| TWSE OpenAPI | Daily listed-stock quote snapshots for selected Taiwan equities/ETF | https://openapi.twse.com.tw/ and https://openapi.twse.com.tw/v1/swagger.json | no-key public daily rows | Keep bounded `STOCK_DAY_ALL` refreshes for `2330/2317/0050` and cache under `market_data/quotes/twse/{symbol}.json`; do not use realtime feeds, private account data, broker APIs, or orderbooks. | Public daily quote snapshots are non-orderable; do not imply tradeability, broker connectivity, balances, or executable order routing. | Implemented in M23.49 as `twse_openapi_daily_quote_snapshot` for bounded `2330/2317/0050` snapshots. |
| Cboe Delayed Quotes | Human delayed quote lookup for listed products | https://www.cboe.com/delayed_quotes/api/ and https://www.cboe.com/delayed_quotes/ | public page, no local adapter | Do not crawl pages, reverse-engineer page payloads, or use the delayed-quote API for unattended extraction. | Automation/terms risk; keep out of provider refresh, cache, source coverage, and quote/reference lanes. | M23.36 records `cboe_delayed_quotes_gate` as `blocked_official_terms`; no adapter, cache, endpoint, or secret flow is implemented. |
| IEX TOPS/DEEP Market Data | Real-time exchange top-of-book/depth market data | https://www.iexexchange.io/resources/trading/market-data, https://www.iex.io/products/market-data-connectivity, and https://www.iex.io/resources/trading/fee-schedule | subscriber agreement / market-data forms required | Do not reuse legacy IEX Cloud/no-key assumptions, add feed decoders, parse HIST PCAP files, or request agreements/connectivity inside this product. | Licensed exchange market-data terms; keep out of provider refresh, cache, source coverage, and quote/reference lanes until a separate agreement-backed contract exists. | M23.42 records `iex_tops_market_data_gate` as `blocked_official_terms`; no adapter, cache, endpoint, feed decoder, or secret flow is implemented. |
| Financial Modeling Prep Stable Quote | Optional stock quote watchlist | https://site.financialmodelingprep.com/developer/docs/stable/quote and https://site.financialmodelingprep.com/developer/docs | optional local API key | Stable quote endpoint requires API-key authorization; no signup, bundled key, public refresh, paid endpoint, MCP/account integration, or broad symbol expansion. | Official-doc gated optional-key quote lane only. | M23.37 implements bounded `AAPL/MSFT/NVDA/SPY` quote caches under `market_data/quotes/fmp/{symbol}.json`, non-orderable `quote_not_orderable` semantics, and local-secret-gated refresh. |
| Nasdaq Data Link | Financial/economic datasets | https://docs.data.nasdaq.com/docs/getting-started, https://docs.data.nasdaq.com/docs/data-organization, and https://docs.data.nasdaq.com/v1.0/docs/getting-started | account / dataset-dependent | Free/open datasets exist, but current docs also state most datasets are premium, product pages define API/free-premium status, and legacy API usage requires a user account key. | Subscription, account-key, and dataset-entitlement risk. | M23.60 records `nasdaq_data_link_dataset_gate` as `blocked_dataset_specific_gate`; no adapter, signup, key collection, catalog crawl, cache, or source coverage is implemented. |
| JPX / J-Quants | Japanese equity market data and JPX catalog/statistics surfaces | https://jpx-jquants.com/en, https://www.jpx.co.jp/english/corporate/news/news-releases/6020/20260119.html, https://www.jpx.co.jp/english/markets/data-catalog/, and https://www.jpx.co.jp/english/markets/statistics-equities/price/ | API key / plan / portal / monthly file dependent | J-Quants V2 uses API-key authentication; Free has delayed stock OHLC coverage but no CSV download; CSV bulk delivery is Light Plan or higher; JPxData Portal is a beta catalog/search portal; monthly quotations are monthly statistics files. | Account, plan/payment, portal automation, and quote-semantics risk. | M23.64 records `jpx_jquants_market_data_gate` as `blocked_account_plan_gate`; no adapter, API-key prompt, CSV bulk downloader, portal crawler, monthly quotation parser, cache, refresh row, or source coverage is implemented. |
| Yahoo Finance / Yahoo APIs | Multi-asset market data often requested through unofficial Yahoo Finance query/chart endpoints | https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apiforydn/index.html, https://legal.yahoo.com/us/en/yahoo/guidelines/ydn/index.html, https://legal.yahoo.com/us/en/yahoo/privacy/products/developer/, and https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apitnc/index.html | Application ID / API credentials / API-specific documentation dependent | Yahoo API terms and developer materials describe API-specific documentation, discretionary rate limits, Application ID requirements, and credential/account responsibility. | Terms, credential, undocumented endpoint, retention/display, and automation risk. | M23.66 records `yahoo_finance_market_data_gate` as `blocked_terms_credentials_gate`; no adapter, query endpoint crawler, chart/quote scraper, crumb/cookie flow, cache, refresh row, or source coverage is implemented. |

## Bounded Implementation Recommendation

M21.1 added read-only artifact/provider lifecycle visibility before further provider
expansion. M21.2 implements GDELT DOC API for News depth. M21.3 implements EIA Open
Data as optional-key energy context for Markets Commodities. M21.6 expands the
existing Alpha Vantage optional-key `GLOBAL_QUOTE` implementation into bounded
per-symbol Stocks/ETF watchlists after confirming the official endpoint shape.

The next provider candidate should focus on either another official/public
non-crypto source, a Markets panel split, or a separate comparison-gated provider
adapter before adding more Alpha Vantage/Twelve Data breadth.

M21.9 implements the next official/public no-key source by adding BLS latest
macro/labor series for Markets Indexes and Regional context. The next provider
candidate should now avoid piling more series into the same macro panel until the
Markets panel split/source attribution UX is reviewed.

M21.16 implements the SEC submissions branch of the existing SEC EDGAR official
API entry by adding recent company filing metadata for Markets Stocks. M21.19
then expands that lane into bounded `AAPL/MSFT/NVDA` per-CIK submissions caches
after the status-lane separation made filing coverage inspectable. The next
provider candidate should avoid overloading Stocks with more SEC rows until the
filing/fundamental/registry/quote separation is reviewed in browser evidence.

M21.20 does not add another provider. It adds a Markets `source_coverage_matrix`
Provider Entry Gate so future provider work can be compared by asset family,
runtime role, provider ID, auth mode, cache path, row count, TTL, official docs
URL, quote semantics, gated reason, and safe action before implementation. The
next provider candidate should enter through this matrix instead of adding
route-specific source tables or implying quote coverage from reference data.

M23.2 reuses the existing Alpha Vantage provider-entry gate for a bounded FX
quote watchlist after M23.1 added Federal Reserve H.10 reference rates. Future
FX work should not reopen ECB/H.10 reference wiring or expand Alpha Vantage pair
count without a concrete quota/cache need and explicit non-orderable semantics.

M23.31 adds Bank of Canada Valet as a public no-key CAD reference-rate provider.
Future FX work should preserve ECB, Federal Reserve H.10, Bank of Canada, and
optional-key quote-watchlist separation; BoC rows are reference-only and must not
be treated as orderable quotes, broker connectivity, balances, or a reason to
collect unused keys.

M23.4 implements the Twelve Data optional-key candidate as a bounded secondary
quote provider after refreshing official `/quote` docs. Future Twelve Data work
should not add batch, paid, or broader symbol coverage without a concrete route
need and must keep the provider outside public no-key refresh jobs.

M23.34 implements Finnhub as a bounded optional-key equity quote lane after
refreshing official quote/rate-limit docs. Future Finnhub work should not add
account/trading APIs, paid/realtime entitlement assumptions, broader symbols, or
public no-key refresh behavior without a new provider-entry gate and immediate
route need.

M23.5 implements BEA Regional as a bounded optional-key macro-context provider
for Markets Regional after refreshing official BEA API docs. Future Regional
work should not treat BEA rows as quotes.

M23.6 implements Census ACS 5-year Data Profile as a bounded optional-key
Regional demographic/economic context provider after refreshing official
Census API docs. Future Regional work should not treat Census rows as quotes or
broaden Census variables/geographies without a concrete provider-entry gate and
immediate route need.

M23.11 implements New York Fed SOFR as a public no-key Bonds/Rates reference
provider. Future rates work should preserve Treasury yield-curve and SOFR
separation, keep both reference-only, and avoid turning rates reference rows
into executable fixed-income/funding quotes.

M23.14 implements CFTC COT Legacy Futures Only as a public no-key Commodities
positioning-context provider. Future commodity work should preserve the
World Bank price-reference, CFTC positioning-context, and EIA energy-context
separation, and must not use COT rows as executable spot/futures quotes.

M23.16 implements Stooq as a bounded public no-key quote snapshot lane after the
current quote CSV surface live-smoked without credentials. The historical Stooq CSV
download path returned a CAPTCHA/API-link gate, so that path remains blocked and
must not be implemented without a separate reviewed gate.

M23.17 implements Nasdaq Trader Symbol Directory as a public no-key reference
provider after refreshing the official symbol-directory docs and text files.
Future symbol-search UI may reuse the cache, but symbol rows must remain
reference-only and must not be treated as quotes, broker/exchange availability,
balances, or executable instruments.
M23.18 adds cache-only symbol search over that directory; search remains
`not_quote`, non-orderable, and outside broker/exchange/live semantics.

M23.53 implements OpenFIGI v3 mapping as a bounded public no-key identifier
mapping lane. Future identifier work may reuse the cache for source-linked
symbol resolution, but FIGI rows must remain `not_quote`, context-only,
non-orderable, and outside broker/exchange/balance/tradeability semantics.

M23.19 implements MOEX ISS delayed quote snapshots as a bounded public no-key
Markets provider-breadth lane after official-doc review and no-secret live smoke.
Future MOEX work must keep delayed snapshots non-orderable and must not add
authenticated realtime feeds, orderbooks, broker/exchange connectivity, balances,
or tradeability without a separate reviewed gate.

M23.49 implements TWSE OpenAPI daily quote snapshots as a bounded public
no-key Markets provider-breadth lane after official OpenAPI review. Future TWSE
work must keep daily snapshots non-orderable and must not add realtime feeds,
private account access, broker/exchange connectivity, balances, or order
routing without a separate reviewed gate.

M23.50 implements Eurostat HICP as a bounded public no-key macro-context lane
after official Statistics API review. Future Eurostat work must keep HICP rows
as `not_quote` macro/reference context and must not broaden datasets, create
trade signals, imply orderability, or add broker/account/balance behavior
without a separate reviewed route need and provider-entry gate.

M23.36 records Cboe Delayed Quotes as a blocked provider-entry gate after
official-page review. Future quote-breadth work must not use Cboe page payloads,
delayed-quote API paths, or page crawling as a local adapter unless a separate
licensed/terms-reviewed data contract explicitly permits automation.

M23.37 implements FMP stable quote as a bounded optional-key stock quote lane
after official-doc review. Future FMP work must not add provider signup, account
or MCP integration, paid endpoints, public no-key refresh jobs, broader symbols,
or trading/account APIs without a separate reviewed provider-entry gate and
immediate route need.

M23.42 records IEX TOPS/DEEP as a blocked provider-entry gate after official-doc
review. Future quote-breadth work must not reuse legacy IEX Cloud/no-key
assumptions, decode TOPS/DEEP feeds, parse HIST PCAP files, request
market-data agreements/connectivity, or add IEX source coverage unless a
separate licensed data contract explicitly permits the local adapter.

M23.60 records Nasdaq Data Link as a blocked dataset-specific provider gate
after official-doc review. Future Nasdaq Data Link work must not add an adapter,
signup, account-key prompt, catalog crawler, dataset cache, provider refresh row,
or source coverage unless a concrete free dataset product page, auth mode, API
route, cache schema, quote semantics, and route need are reviewed in a separate
provider-entry slice.

M23.64 records JPX/J-Quants as a blocked account/plan provider gate after
official-doc review. Future Japan equity work must not add a J-Quants adapter,
API-key prompt, CSV bulk downloader, JPxData Portal crawler, monthly quotation
parser, provider cache, refresh row, or source coverage unless a concrete
allowed dataset, auth mode, route need, cache schema, quote semantics, and
no-subscription boundary are reviewed in a separate provider-entry slice.

M23.66 records Yahoo Finance as a blocked terms/credentials provider gate after
official Yahoo API terms/guidelines review. Future Yahoo Finance work must not
add a query endpoint crawler, chart/quote scraper, crumb/cookie flow, provider
cache, refresh row, or source coverage unless a concrete official finance
market-data API contract, auth mode, route need, cache schema, quote semantics,
display/retention terms, and no-subscription boundary are reviewed in a
separate provider-entry slice.

M23.67 records the current quote-breadth closure contract. The reviewed provider
backlog has 21 candidates, 16 implemented candidates, 5 blocked provider-entry
gates, and 0 approved next candidates, so future work should start with a new
official-doc provider-entry gate rather than retrying blocked sources or
mislabeling reference/context/non-orderable lanes as executable quotes.
