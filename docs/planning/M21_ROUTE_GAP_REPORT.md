# M21 Route Gap Report

Date: 2026-05-24

## Evidence Anchors

- `PROJECT_STATE.md`
- `docs/planning/FINAL_HANDOFF.md`
- `.omx/plans/ralplan-m21-parity-depth-20260524T093313Z.md`
- `docs/reference/fincept-platform-test/FEATURE_MATRIX.md`
- `docs/reference/fincept-platform-test/screenshots/`
- `docs/reference/fincept-platform-test/logs/`

## Cross-Route Findings

- All 15 planned routes exist.
- Provider/cache/freshness metadata exists and is surfaced across many routes.
- M20.22-M20.23 added bounded public provider refresh jobs; M21.17 separates
  current-run writes from cache availability/reuse in refresh results.
- M20.24-M20.27 added local secret storage and optional-key FRED / Alpha Vantage
  provider adapters.
- The largest remaining M21 gaps are route workflow depth, broader non-crypto provider
  coverage, artifact lifecycle/prune/archive/recovery, and AI-agent-operable contracts.
- Live/private/broker execution remains intentionally disabled.

## Gap Matrix

| Route | Current provider/data flow | State/cache/artifact flow | Main M21 gap | M21 target | Verification |
| --- | --- | --- | --- | --- | --- |
| Dashboard | Aggregates provider freshness, crypto pulse, paper, portfolio, news, backtest, macro setup, and global Command Center drawer supervision. | Reads local layout, provider/cache state, and read-only Command Center payload. | More multi-asset breadth and lifecycle visibility remain open, but global Agent supervision is now route-independent. | Show provider breadth, refresh job state, artifact health, stale/gated reasons, and always-reachable Command Center context. | Dashboard API tests, browser screenshot, no fixture-primary check, shell Command Center drawer E2E. |
| Markets | Crypto, Treasury, NY Fed SOFR, ECB/H.10/Bank of Canada FX, World Bank commodities, SEC fundamentals/funds, Nasdaq Trader symbol directory/search, OpenFIGI identifier mapping, DBnomics, BLS, Eurostat, FRED, Alpha Vantage stock/ETF/FX, Twelve Data bounded quotes, Finnhub bounded equity quotes, FMP bounded stock quotes, Stooq bounded public quote snapshots, MOEX bounded delayed quote snapshots, TWSE bounded daily quote snapshots, BEA/Census Regional context, EIA energy context, and Cboe/IEX/Nasdaq Data Link/JPX-J-Quants/Yahoo Finance blocked provider-gate evidence. | Per-route refresh/search endpoints and cache paths, including BLS macro/labor latest-series cache, Eurostat `market_data/macro/eurostat/hicp_ea20_cp00_i15.json` HICP macro cache, SOFR reference cache, Bank of Canada Valet FX reference cache, Finnhub `market_data/quotes/finnhub/{symbol}.json` snapshots, FMP `market_data/quotes/fmp/{symbol}.json` snapshots, Stooq `market_data/quotes/stooq/{symbol}.json` snapshots, MOEX `market_data/quotes/moex/{symbol}.json` snapshots, TWSE `market_data/quotes/twse/{symbol}.json` snapshots, Nasdaq Trader `market_data/reference/nasdaq_trader/symbol_directory.json` reference rows, and OpenFIGI `market_data/reference/openfigi/mapping.json` identifier rows. M21.11 splits macro provider/source attribution into Provider Stack and Source Contract panels; M21.12 extends that split to Stocks, ETF, FX, Commodities, and Bonds/Rates. M21.20 adds `source_coverage_matrix` as the provider-entry/source-state contract across Markets families. M23.26 derives `quote_reference_coverage` from that matrix for AI Agent supervision, and M23.47 adds `quote_reference_coverage.snapshot_board` / `GET /api/markets/quote-snapshot-board` as a cache/preflight board over non-orderable quote lanes. M23.36 records `cboe_delayed_quotes_gate` as blocked rather than an adapter, M23.42 records IEX TOPS/DEEP as an agreement-gated market-data product rather than a public no-key REST quote lane, M23.60 records Nasdaq Data Link as blocked until a concrete free dataset gate exists, M23.64 records JPX/J-Quants as blocked until a concrete allowed no-subscription dataset gate exists, M23.66 records Yahoo Finance as blocked until a concrete official finance market-data API contract exists, and M23.67 adds `quote_breadth_closure` to the provider gate. | Executable quote breadth remains excluded from the current non-live/no-subscription scope unless a future official provider-entry gate approves a concrete source; BoC FX rows are CAD reference rates, Eurostat HICP rows are macro context, Finnhub/FMP/Alpha Vantage/Twelve Data quotes are optional-key non-orderable rows, Stooq/MOEX/TWSE rows are delayed/daily non-orderable snapshots, Nasdaq Trader rows/search and OpenFIGI rows are symbol/identifier reference metadata, and Cboe/IEX/Nasdaq Data Link/JPX-J-Quants/Yahoo Finance sources are not automation-approved adapter inputs. | Reuse lifecycle/quote/source attribution split components, the M21.20 source coverage matrix, the M23.26 quote/reference coverage view, the M23.47 quote snapshot board, and the M23.67 quote-breadth closure before adding more providers; keep Treasury/SOFR/H.10/ECB/BoC/World Bank/Eurostat rows reference or context-only, optional-key quote lanes non-orderable, Stooq/MOEX/TWSE rows non-orderable, Nasdaq Trader/OpenFIGI rows reference-only, and Cboe/IEX/Nasdaq Data Link/JPX-J-Quants/Yahoo Finance market-data gates blocked unless a licensed/terms-reviewed, concrete official, free-dataset, or no-subscription dataset contract exists. | Provider tests, Markets E2E, source attribution, source coverage matrix contract tests, quote/reference coverage contract tests, quote snapshot board contract tests, provider-acquisition blocked-gate and quote-closure tests. |
| Crypto | Public Binance/Kraken/Coinbase detail chain; paper-only runtime. | Public detail cache, paper ledger artifacts. | Needs richer provider depth only after non-crypto breadth. | Preserve paper/live isolation and provenance. | Crypto provider chain and live-safety tests. |
| Portfolio | Provider-priced crypto holdings, local reports, paper/backtest links, report index, local exposure map, and report health matrix. | Local portfolio state, exports, reports, `exposure.csv`, lineage, report artifact-health rows, and metadata-only expected-file health. | Lifecycle/prune/archive for generated reports and linked artifacts remains non-destructive only; report content indexing and automatic repair remain blocked. | Agent-readable artifact health, exposure supervision, and recovery status. | Portfolio tests, artifact path tests, exposure-map UI/API tests, report-health contract tests. |
| News | Public RSS feed cache plus macro/fundamentals context; M21.2 adds GDELT DOC ArticleList metadata. | `artifacts/news/news_cache.json` with provider/intel metadata plus metadata-only research brief, brief-index, and M23.41 topic/entity map supervision. | Source depth and metadata linking are improved, but broader provider resilience remains open. | Keep metadata-only no-key news breadth, source/provider states, FEEDS/ARTS/CLST/SRCS/SENT/WATCHES style route state, local brief lifecycle visibility, and topic/entity map safety flags. | News tests, provider docs, no full-article copy check, browser screenshot, brief-index and topic-map contract checks. |
| AI Chat | Local context brief from provider/cache and artifacts plus M23.27 metadata-only context contract and M23.55 session health matrix. | Chat JSON/JSONL artifacts plus M23.22 advanced output kind/latest-path index, M23.23 health-state coverage, M23.35 state-file separation, `context_contract` source/provenance/output-state fields, and `session_health` transcript metadata. | Agent-operable context is stronger, but managed LLM, request/response replay, artifact content indexing, and runtime execution remain blocked. | Use the M23.27 context contract and M23.55 session health matrix before any richer assistant work; keep tool-readable context limits, transcript file state, citations, artifact provenance, state-file/output separation, and metadata-only output state explicit. | AI Chat tests, context-contract/session-health tests, advanced-output packet tests, and artifact safety tests. |
| Backtest | Local strategy catalog; provider cache when available; deterministic fallback. | Backtest artifacts, provenance, walk-forward bundles, local comparison packets, read-only run index, M23.52 expected-file artifact health matrix, and M23.63 RSI reversion strategy breadth. | Non-crypto/provider-backed data remains narrow and strategy breadth is still bounded to local examples. | Expand strategy/data plan only through scoped local-research slices before any optimize/deploy/live workflow. | Backtest tests, provenance manifest checks, comparison-packet, run-index, artifact-health, and strategy-breadth contract checks. |
| Algo | Local strategies, scanner, backtest handoff, latest scan artifact health, and M23.40 scan-readiness metadata. | Strategy state and scan artifacts. | Scanner usefulness still depends on thin provider/cache breadth. | Route scans through researched provider/cache state with no live actions, and expose pre-scan readiness before running artifact-writing scanner actions. | Algo tests and live-safety checks. |
| Nodes | Local workflow definitions and dry-run artifacts. | Workflow state plus dry-run bundle, M23.22 manifest/report/error-log index coverage, M23.23 health-state coverage, M23.28 IO contract fields, M23.35 state-file separation, and M23.56 route-local workflow health. | Runtime execution remains blocked; dry-run IO and artifact health are now machine-readable. | Use the M23.28 IO contract and M23.56 workflow health before adding typed dry-run outputs; keep state files separate from latest output paths and metadata-only output health. | Nodes tests, workflow-health tests, advanced-output packet tests, and disabled execute/deploy tests. |
| Code | Static notebook analysis and artifacts; execution disabled. | Notebook state and analysis artifacts plus M23.22 manifest/report/error-log index, M23.23 health-state coverage, M23.28 IO contract fields, M23.30 static outline metadata, M23.35 state-file separation, and M23.57 route-local analysis health. | Runtime execution remains blocked; static-analysis IO and artifact health are now machine-readable. | Expand read-only context notebook and artifact manifest semantics without notebook execution; use M23.57 analysis health before deeper notebook outputs, and do not treat notebook state as output evidence. | Code tests, analysis-health tests, advanced-output packet tests, and disabled runtime tests. |
| Quant Lab | Local preview bundles with context and manifests. | Quant Lab artifacts plus M23.22 manifest/report/error-log index, M23.23 health-state coverage, M23.28 IO contract fields, M23.35 state-file separation for `quant_lab_state.json`, and M23.58 route-local preview health. | Many modules remain preview-only and execution/deep-agent runtime remains blocked; preview IO and artifact health are now machine-readable. | Select a small set of safe local workflows with reproducible outputs and metadata-only output supervision; use M23.58 preview health before deeper Quant Lab outputs, and do not treat route state as output completion. | Quant Lab tests, preview-health tests, advanced-output packet tests, and safety checks. |
| QuantLib | Deterministic calculators with context/provenance bundles. | QuantLib request/response/report/error/context/manifest plus M23.22 manifest/report/error-log index, M23.23 health-state coverage, M23.28 IO contract fields, M23.29 fixed-income duration/convexity calculator breadth, M23.35 state-file separation for `quantlib_state.json`, M23.59 route-local calculation health, M23.61 implied-volatility calculator breadth, and M23.65 option scenario grid artifacts. | Artifact lifecycle health is machine-readable and calculator breadth now includes fixed-income, implied-volatility, and scenario-grid examples, but breadth remains bounded local analytics and external runtime remains blocked. | Add bounded calculator examples before external runtime; do not treat route state as calculator output evidence or scenario rows as fetched quotes/orderable derivatives data. | QuantLib tests, calculation-health tests, advanced-output packet tests, scenario-grid tests, and artifact boundary tests. |
| Forum | Local notes, replies, artifact health repair. | Forum state and derivative artifacts. | Good local lifecycle precedent; needs cross-route issue linkage. | Use as route-gap issue log tied to M21 artifacts. | Forum artifact tests. |
| Settings | Provider setup, secret status, governance diagnostics, and provider refresh result semantics. | Local settings, secret gate, gov diagnostics, provider-refresh job artifacts. | Future lifecycle automation still needs reviewed mutation semantics. | Keep manual refresh AI-operable with explicit written/available/reused cache fields before automatic refresh or recovery mutation. | Governance/provider tests, browser screenshot, secret scan. |
| Profile | Local build/usage stats, no billing/account identity. | Metadata-only usage rows. | Needs agent-oriented local operator profile and lifecycle totals. | Keep personal identity absent; expose local runtime/use metadata. | Governance/profile tests. |

## M21.17 Provider Refresh Result Semantics Slice

The seventeenth implementation slice closes the M21.16 refresh-result watch:

- Public no-key provider refresh manifests now distinguish `cache_written_this_run`
  from `cache_available` and `cache_reused`.
- `cache_written` remains as a compatibility alias for current-run writes, not stale
  cache availability.
- Provider Freshness shows written / available / reused counts so AI Agents can
  decide whether a run fetched fresh data, reused stale cache, or had no runtime
  cache.
- Settings agent contract now advertises `provider_refresh_public_start` and
  `provider_refresh_result_semantics`.
- No automatic scheduling, status rewrite, credential read/write, optional-key
  refresh, live trading, broker/private flow, destructive cleanup, or installed-source
  read was added.

## M21.18 Stock Status Lanes Slice

The eighteenth implementation slice closes the current Stocks route headline/gateway
ambiguity:

- Markets Stocks now exposes `stocks.status_lanes` for quote watchlist, company
  registry, recent filings, and company facts.
- The Stocks gateway reports `stock_lanes_available` when any lane has runtime
  evidence, so filings or quotes no longer hide the other lane states.
- The Stocks UI includes a dense Status Lanes panel and the Source Contract panel
  reports lane counts and primary lane.
- The AI Agent contract now advertises `stock_status_lanes` and Stocks refresh
  actions include `stocks.status_lanes` in their response contracts.
- No new provider adapter, credential handling, paid data, live trading, broker
  flow, destructive artifact action, installed-source read, branding, or
  fixture-primary runtime claim was added.

## M21.19 Stock Filings Watchlist Slice

The nineteenth implementation slice closes the single-company SEC submissions
cache limitation left after the filings lane became visible:

- Markets Stocks recent filing metadata now aggregates bounded `AAPL/MSFT/NVDA`
  SEC submissions rows while preserving per-CIK cache files.
- The Stocks UI adds a symbol column and filing-symbol summaries so an AI Agent can
  distinguish quote watchlist state from SEC filing coverage.
- Public provider refresh results and storage state point at the watchlist cache
  set rather than only the default `AAPL` submissions path.
- The Markets agent contract now advertises `stock_company_filings_watchlist` and
  `stocks.summary.filing_symbols`.
- No credentials, provider signup, paid data, live trading, broker/private flow,
  destructive artifact action, installed-source read, branding, commercial copy,
  or fixture-primary runtime claim was added.

## M21.20 Markets Source Coverage Matrix Slice

The twentieth implementation slice creates the Markets provider-entry/source-state
contract before adding another provider adapter:

- `/api/markets` exposes `source_coverage_matrix` rows for Stocks, ETF, FX,
  Commodities, Indexes, Regional, and Bonds/Rates.
- Each row carries asset family, runtime role, provider ID, auth mode, state,
  cache path, retrieved time, row count, freshness TTL, docs URL, quote semantics,
  gated reason, safe action ID, and next safe action.
- The Markets UI adds a dense Provider Entry Gate table with stable
  `markets-source-coverage-*` selectors for AI Agent operation.
- The Markets agent contract advertises the matrix route state and includes it in
  relevant public no-key and optional-key refresh action response contracts.
- No new provider adapter, key acquisition, paid/bulk data, live trading,
  broker/private flow, destructive artifact action, installed-source read,
  branding, commercial copy, or fixture-primary runtime claim was added.

## Selected M21 Slice

The initial implementation slice should be artifact/provider lifecycle visibility:

- Low risk: read-only, local, no credentials, no live trading.
- High value: improves all routes and supports AI Agent operation.
- Fits current architecture: governance, Help diagnostics, provider refresh artifacts,
  storage paths, and existing artifact health patterns already exist.
- Verification is tractable with focused governance/support tests and browser evidence.

## M21.2 News Slice

The second implementation slice is News route GDELT DOC metadata enrichment:

- Matches observed Fincept News workflow depth: command strip, intel counters, clustered
  feed mode, provider/source breadth, and selected item metadata.
- Uses a no-key public provider and stores metadata only.
- Keeps article body fetch/copy, paid GDELT Cloud, AI summary calls, login, credentials,
  and live/broker paths out of scope.
- Verification is tracked in `docs/planning/M21_NEWS_GDELT_DOC.md`.

## M21.3 EIA Energy Context Slice

The third implementation slice is Markets Commodities EIA Open Data energy context:

- Matches the M21 provider-breadth priority for non-crypto market context.
- Uses official EIA Open Data documentation and the existing local secret store.
- Keeps EIA as optional-key, reference-only energy context; no public no-key refresh,
  no fixture/default energy values, no paid provider, and no executable commodity
  quote/futures/live-trading path were added.
- Verification is tracked in `docs/planning/M21_EIA_ENERGY_CONTEXT.md`.

## M23.21 News Research Brief Index Slice

This later implementation slice deepens News/Research artifact lifecycle
visibility without expanding content or provider risk:

- Adds metadata-only `GET /api/news/research-briefs` for local
  `artifacts/news/research_briefs/news-brief-*` bundles.
- Inventories expected brief files using directory entries and file stats only;
  it does not read article bodies, brief JSON, source-health JSON, or Markdown
  content.
- Adds public News payload `research_brief_index`, News UI `INDEX` supervision
  strip, and AI Agent action `news_research_brief_index`.
- Recovery hints remain advisory and point to regenerating a metadata-only News
  brief; no delete, move, restore, archive, provider signup, credential read,
  cloud sync, or live trading path is enabled.
- Verification is tracked in `docs/planning/M23_NEWS_RESEARCH_BRIEF_INDEX.md`.

## M23.41 News Topic Entity Map Slice

This later implementation slice deepens News/Research AI Agent supervision
without adding provider or content risk:

- Adds metadata-only `GET /api/news/topic-entity-map` derived from current News
  payload rows.
- Embeds `topic_entity_map` in `/api/news` so agents can inspect topic rows,
  entity rows, and topic/entity edges before writing local research briefs.
- Adds News UI selector `news-topic-entity-map` and AI Agent action
  `news_topic_entity_map`.
- Keeps provider refresh, article-body reads, full article copy, AI summarizer
  calls, artifact writes, paid/cloud news, credential access, live trading, and
  destructive recovery disabled.
- Verification is tracked in `docs/planning/M23_NEWS_TOPIC_ENTITY_MAP.md`.

## M23.22 Advanced Output Manifest Index Slice

This later implementation slice deepens advanced-route output visibility without
turning dry-run/static/local preview routes into execution runtimes:

- Extends metadata-only `GET /api/advanced-workflows/output-packet` for AI Chat,
  Nodes, Code, Quant Lab, and QuantLib output roots.
- Adds artifact kind counts and latest manifest/report/error-log paths so AI
  Agents can inspect local output availability without opening artifact content.
- Adds Command Center advanced-output rows and AI Agent action
  `advanced_workflow_output_index`.
- Recovery remains advisory; no route execution, notebook kernel, workflow
  runtime, managed LLM call, external QuantLib runtime, route-output mutation,
  credential read, cloud sync, or destructive recovery path is enabled.
- Verification is tracked in `docs/planning/M23_ADVANCED_OUTPUT_MANIFEST_INDEX.md`.

## M23.23 Advanced Output Health Matrix Slice

This later implementation slice deepens advanced-route output supervision
without opening or repairing artifacts:

- Extends metadata-only `GET /api/advanced-workflows/output-packet` with
  per-route `health_state`, `expected_artifact_kinds`,
  `missing_expected_kinds`, and `supervision_ready`.
- Adds summary counts for complete, partial, and missing advanced-route output
  health so Command Center can show whether local outputs are agent-reviewable.
- Adds AI Agent action `advanced_workflow_output_health`.
- Recovery remains advisory; no artifact content indexing, route execution,
  notebook kernel, workflow runtime, managed LLM call, external QuantLib runtime,
  route-output mutation, credential read, cloud sync, automatic repair, or
  destructive recovery path is enabled.
- Verification is tracked in `docs/planning/M23_ADVANCED_OUTPUT_HEALTH_MATRIX.md`.

## M23.24 Artifact Root Supervision Matrix Slice

This later implementation slice deepens artifact lifecycle visibility across all
local artifact/cache roots without opening or repairing files:

- Extends metadata-only `GET /api/artifact-lifecycle` rows with latest artifact
  path, supervision-ready state, and advisory recovery hints.
- Adds Command Center `artifact_root_health_matrix` so AI Agents and human
  supervisors can see active, empty, missing, blocked, and ready roots from the
  central supervision payload.
- Adds AI Agent action `artifact_lifecycle_root_health`.
- Recovery remains advisory; no artifact content reads, content indexing,
  automatic repair, archive/prune/delete/move/restore execution, provider
  signup, credential read, cloud sync, or live/private trading path is enabled.
- Verification is tracked in
  `docs/planning/M23_ARTIFACT_ROOT_SUPERVISION_MATRIX.md`.

## M21.4 Agent Operability Contract Slice

The fourth implementation slice is a read-only AI Agent operability contract:

- Matches the future operating model where a human asks an AI Agent to operate the
  local terminal through stable APIs and selectors.
- Converts observed dense route/action structure into neutral local route/action/error
  contracts without copying branding, commercial copy, account mechanics, or source.
- Exposes all 15 route endpoints, stable selectors, safe local actions, disabled
  safety gates, artifact outputs, and error recovery rules through `/api/agent-contract`.
- Surfaces the same contract in governance/help diagnostics and Settings so agents can
  discover it without scraping UI text.
- Verification is tracked in `docs/planning/M21_AGENT_OPERABILITY_CONTRACT.md`.

## M21.5 Provider Refresh Lifecycle Slice

The fifth implementation slice is read-only provider refresh lifecycle/recovery
visibility:

- Directly addresses the M20.23 watch item for interrupted queued/running jobs,
  manifest-only refresh history, failed runs, and stale job recovery guidance.
- Exposes `/api/providers/refresh-public/lifecycle`, includes `refresh_lifecycle`
  in `/api/providers`, and surfaces the same state in governance, Help diagnostics,
  Settings, and the Provider Freshness strip.
- Keeps recovery non-mutating: no status rewrite, prune, archive, delete, cache
  mutation, external network call, credential read, optional-key refresh, live
  trading path, or installed-source read was added.
- Verification is tracked in `docs/planning/M21_PROVIDER_REFRESH_LIFECYCLE.md`.

## M23.51 Provider Refresh Schedule Plan Slice

This later implementation slice deepens provider refresh lifecycle supervision
without enabling automatic refresh automation:

- Exposes `GET /api/providers/refresh-public/schedule-plan` as a read-only due,
  stale, missing, and within-TTL view over providers already covered by the
  manual public no-key refresh job.
- Embeds `refresh_schedule_plan` in `/api/providers`, `/api/providers/cache`,
  and `/api/governance`, and surfaces compact schedule counts in Provider
  Freshness.
- Adds Settings AI Agent action `provider_refresh_schedule_plan_inspect` so an
  agent can decide whether the manual refresh action is useful without guessing
  from UI copy.
- Keeps automatic scheduling, provider calls, job starts, cache mutation,
  stale-job recovery mutation, optional-key refresh, secret access, destructive
  cleanup, broker/exchange behavior, and live/private behavior disabled.
- Verification is tracked in
  `docs/planning/M23_PROVIDER_REFRESH_SCHEDULE_PLAN.md`.

## M23.52 Backtest Artifact Health Matrix Slice

This later implementation slice deepens Backtest artifact supervision without
expanding execution:

- Exposes `GET /api/backtest/artifact-health` as a metadata-only expected-file
  matrix for local closed-candle `bt-*` run directories.
- Embeds `artifact_health` in `/api/backtest`, adds UI selector
  `backtest-artifact-health`, and adds AI Agent action
  `backtest_artifact_health`.
- Reports expected, present, and missing artifact counts, latest artifact path,
  manifest path, `supervision_ready`, and advisory recovery hints.
- Keeps artifact content reads, automatic repair, Backtest reruns, optimize,
  deployment, broker routing, credentials, destructive lifecycle actions, and
  live/private behavior disabled.
- Verification is tracked in
  `docs/planning/M23_BACKTEST_ARTIFACT_HEALTH.md`.

## M23.53 OpenFIGI Identifier Mapping Slice

This later implementation slice deepens Markets Stocks identifier reference
coverage without adding executable quotes:

- Adds `openfigi_identifier_mapping_public` as a public no-key OpenFIGI v3
  mapping adapter with local cache `market_data/reference/openfigi/mapping.json`.
- Exposes `GET /api/openfigi/mapping`, `POST /api/openfigi/mapping/refresh`,
  and `POST /api/markets/openfigi/mapping/refresh`.
- Adds Markets `Stocks / identifier_mapping` source coverage and Stocks summary
  rows for bounded `AAPL/MSFT/SPY` FIGI mappings.
- Adds provider registry/freshness/storage/public-refresh coverage and AI Agent
  action `markets_openfigi_mapping_refresh`.
- Keeps FIGI rows `not_quote`, context-only, non-orderable, outside broker,
  exchange, balance, tradeability, order-routing, and live/private semantics.
- Verification is tracked in
  `docs/planning/M23_OPENFIGI_IDENTIFIER_MAPPING.md`.

## M23.54 Portfolio Report Health Matrix Slice

This later implementation slice deepens Portfolio artifact supervision without
adding optimizer, balance, broker, or live behavior:

- Adds `GET /api/portfolio/report-health` and embeds `report_health` in
  `GET /api/portfolio`.
- Adds Portfolio UI selector `portfolio-report-health` and AI Agent action
  `portfolio_report_health`.
- Reports expected, present, and missing files for local
  `portfolio-report-*` directories, plus manifest/lineage/artifact-health paths,
  `supervision_ready`, and non-mutating recovery hints.
- Keeps report content reads, artifact text indexing, automatic repair, report
  reruns from the health endpoint, optimizer output, real balances, broker
  routing, credentials, destructive lifecycle actions, and live/private behavior
  disabled.
- Verification is tracked in
  `docs/planning/M23_PORTFOLIO_REPORT_HEALTH.md`.

## M23.55 AI Chat Session Health Matrix Slice

This later implementation slice deepens AI Chat session supervision without
adding managed LLM, replay, provider, or destructive lifecycle behavior:

- Adds read-only `GET /api/ai-chat/session-health`.
- Embeds `session_health` in `GET /api/ai-chat`.
- Adds AI Chat UI selector `ai-chat-session-health` and AI Agent action
  `ai_chat_session_health`.
- Reports local session/transcript metadata, transcript existence, byte size,
  declared message count, `health_state`, `supervision_ready`, and
  non-mutating recovery hints without opening message content.
- Keeps AI Chat local dry-run only: no message content read, request/response
  replay, managed LLM call, provider call, credential access, automatic repair,
  destructive lifecycle action, broker routing, or live/private behavior.
- Verification is tracked in
  `docs/planning/M23_AI_CHAT_SESSION_HEALTH.md`.

## M23.56 Nodes Workflow Health Matrix Slice

This later implementation slice deepens Nodes workflow supervision without
adding runtime execution, provider calls, repair, or destructive lifecycle
behavior:

- Adds read-only `GET /api/nodes/workflow-health`.
- Embeds `workflow_health` in `GET /api/nodes`.
- Adds Nodes UI selector `nodes-workflow-health` and AI Agent action
  `nodes_workflow_health`.
- Reports stored workflow artifact metadata, definition/dry-run/report/manifest
  file existence, byte sizes, `health_state`, `supervision_ready`, and
  non-mutating recovery hints without opening artifact contents.
- Keeps Nodes local dry-run only: no workflow execution, artifact content read,
  provider call, credential access, automatic repair, destructive lifecycle
  action, broker routing, or live/private behavior.
- Verification is tracked in
  `docs/planning/M23_NODES_WORKFLOW_HEALTH.md`.

## M23.57 Code Analysis Health Matrix Slice

This later implementation slice deepens Code notebook/static-analysis
supervision without adding notebook execution, kernel processes, source return,
provider calls, repair, or destructive lifecycle behavior:

- Adds read-only `GET /api/code/analysis-health`.
- Embeds `analysis_health` in `GET /api/code` and Code mutation responses.
- Adds Code UI selector `code-analysis-health` and AI Agent action
  `code_analysis_health`.
- Reports stored notebook and static-analysis artifact metadata,
  notebook/analysis/report/manifest file existence, byte sizes,
  `health_state`, `supervision_ready`, and non-mutating recovery hints without
  opening notebook source or artifact contents.
- Keeps Code local static-analysis only: no notebook execution, kernel process,
  source return, artifact content read/indexing, provider call, credential
  access, automatic repair, destructive lifecycle action, broker routing, or
  live/private behavior.
- Verification is tracked in
  `docs/planning/M23_CODE_ANALYSIS_HEALTH.md`.

## M23.58 Quant Lab Preview Health Matrix Slice

This later implementation slice deepens Quant Lab preview supervision without
adding script execution, external runtime, deep-agent execution, model training,
provider calls, repair, or destructive lifecycle behavior:

- Adds read-only `GET /api/quant-lab/preview-health`.
- Embeds `preview_health` in `GET /api/quant-lab`, module selection, and preview
  responses.
- Adds Quant Lab UI selector `quant-lab-preview-health` and AI Agent action
  `quant_lab_preview_health`.
- Reports stored preview artifact metadata, input/output/context/manifest/report
  and error-log file existence, byte sizes, `health_state`,
  `supervision_ready`, and non-mutating recovery hints without opening artifact
  contents.
- Keeps Quant Lab local preview only: no script execution, external runtime,
  deep-agent execution, model training, artifact content read/indexing,
  provider call, credential access, automatic repair, destructive lifecycle
  action, broker routing, or live/private behavior.
- Verification is tracked in
  `docs/planning/M23_QUANT_LAB_PREVIEW_HEALTH.md`.

## M23.59 QuantLib Calculation Health Matrix Slice

This later implementation slice deepens QuantLib calculator supervision without
adding external QuantLib runtime access, external API/provider calls, artifact
content reads, repair, or destructive lifecycle behavior:

- Adds read-only `GET /api/quantlib/calculation-health`.
- Embeds `calculation_health` in `GET /api/quantlib`, module selection, action
  selection, and compute responses.
- Adds QuantLib UI selector `quantlib-calculation-health` and AI Agent action
  `quantlib_calculation_health`.
- Reports stored calculation artifact metadata, request/response/context/
  manifest/report and error-log file existence, byte sizes, `health_state`,
  `supervision_ready`, and non-mutating recovery hints without opening artifact
  contents.
- Keeps QuantLib deterministic local calculator only: no external runtime,
  external API/provider call, artifact content read/indexing, credential
  access, automatic repair, destructive lifecycle action, derivatives
  execution, broker routing, or live/private behavior.
- Verification is tracked in
  `docs/planning/M23_QUANTLIB_CALCULATION_HEALTH.md`.

## M23.60 Nasdaq Data Link Provider Gate Slice

This later implementation slice deepens provider-entry discipline without
adding a provider adapter, signup flow, account-key prompt, catalog crawler,
dataset API call, cache write, source-coverage row, or public refresh behavior:

- Adds provider acquisition candidate `nasdaq_data_link_dataset_gate`.
- Classifies the candidate as `blocked_dataset_specific_gate` after official
  Nasdaq Data Link documentation review.
- Records that free/open datasets exist, but product pages decide API/free-
  premium status and many datasets are premium or account-keyed.
- Keeps `implementation_allowed=false`, `approved_next_count=0`, and
  `resume_state=backlog_exhausted_needs_research`.
- Shows the blocked row in Command Center so AI Agents do not treat Nasdaq Data
  Link as a retryable or approved quote adapter.
- Verification is tracked in
  `docs/planning/M23_NASDAQ_DATA_LINK_GATE.md`.

## M23.61 QuantLib Implied-Volatility Calculator Slice

This later implementation slice deepens QuantLib calculator breadth without
adding external QuantLib runtime access, external API/provider calls, broker
routing, derivatives execution, or live/private behavior:

- Adds `implied-volatility` as a deterministic stdlib quick action.
- Solves Black-Scholes implied volatility from caller-supplied `market_price`
  using bounded bisection.
- Writes the existing local QuantLib request/response/context/manifest/report/
  error-log bundle.
- Exposes the preset through frontend fallback state and focused UI selection
  coverage.
- Moves Command Center provenance to
  `docs/planning/M23_QUANTLIB_IMPLIED_VOL_CALCULATOR.md`.
- Verification is tracked in
  `docs/planning/M23_QUANTLIB_IMPLIED_VOL_CALCULATOR.md`.

## M23.64 JPX/J-Quants Provider Gate Slice

This later implementation slice deepens provider-entry discipline without
adding a provider adapter, API-key prompt, CSV bulk downloader, portal crawler,
monthly quotation parser, cache write, source-coverage row, or public refresh
behavior:

- Adds provider acquisition candidate `jpx_jquants_market_data_gate`.
- Classifies the candidate as `blocked_account_plan_gate` after official
  JPX/J-Quants documentation review.
- Records that J-Quants V2 uses API-key authentication, Free plan data is
  delayed and excludes CSV download, CSV bulk delivery is Light Plan or higher,
  JPxData Portal is a beta catalog/search portal, and monthly quotations are
  statistics files rather than a current quote adapter.
- Keeps `implementation_allowed=false`, `approved_next_count=0`, and
  `resume_state=backlog_exhausted_needs_research`.
- Shows the blocked row in Command Center so AI Agents do not treat
  JPX/J-Quants as a retryable or approved no-key quote adapter.
- Verification is tracked in
  `docs/planning/M23_JPX_JQUANTS_PROVIDER_GATE.md`.

## M23.65 QuantLib Option Scenario Grid Slice

This later implementation slice deepens QuantLib local calculator breadth
without adding external QuantLib runtime access, external API/provider calls,
market-price fetching, broker routing, derivatives execution, or live/private
behavior:

- Adds `option-scenario-grid` as a deterministic stdlib quick action.
- Computes bounded Black-Scholes scenario rows from caller-supplied spot,
  strike, rate, volatility, maturity, option type, and 3-9 scenario shocks.
- Writes the existing local QuantLib request/response/context/manifest/report/
  error-log bundle.
- Exposes the preset through frontend fallback state and focused UI selection
  coverage.
- Moves Command Center provenance to
  `docs/planning/M23_QUANTLIB_OPTION_SCENARIO_GRID.md`.
- Verification is tracked in
  `docs/planning/M23_QUANTLIB_OPTION_SCENARIO_GRID.md`.

## M23.66 Yahoo Finance Provider Gate Slice

This later implementation slice deepens provider-entry discipline without
adding a Yahoo Finance adapter, query endpoint crawler, chart/quote scraper,
crumb/cookie flow, cache write, source-coverage row, or public refresh behavior:

- Adds provider acquisition candidate `yahoo_finance_market_data_gate`.
- Classifies the candidate as `blocked_terms_credentials_gate` after official
  Yahoo API terms, guidelines, developer network, and credential materials
  review.
- Records that Yahoo API usage depends on API-specific documentation,
  application identity, API keys or credentials, rate limits, and acceptable-use
  restrictions, while the reviewed official materials do not provide a concrete
  Yahoo Finance no-key market-data API contract for unattended quote caching.
- Keeps `implementation_allowed=false`, `approved_next_count=0`, and
  `resume_state=backlog_exhausted_needs_research`.
- Shows the blocked row in Command Center so AI Agents do not treat Yahoo
  Finance query/chart endpoints as retryable or approved no-key quote adapters.
- Verification is tracked in
  `docs/planning/M23_YAHOO_FINANCE_PROVIDER_GATE.md`.

## M23.67 Provider Quote Breadth Closure Slice

This later implementation slice closes the current provider quote-breadth loop
without adding provider behavior:

- Adds provider acquisition `quote_breadth_closure`.
- Records that the 21 reviewed candidates are either implemented or blocked,
  with 0 approved next candidates and 5 blocked provider gates.
- Exposes the closure through Command Center so AI Agents do not keep retrying
  Cboe/IEX/Nasdaq Data Link/JPX-J-Quants/Yahoo Finance or mislabel
  non-orderable/reference/context rows as executable quotes.
- Keeps executable/orderable quote parity outside the current non-live,
  no-subscription scope until a future official provider-entry gate approves a
  concrete source.
- Verification is tracked in
  `docs/planning/M23_PROVIDER_QUOTE_BREADTH_CLOSURE.md`.

## M23.62 Global Command Center Drawer Slice

This later implementation slice deepens command-center-first UI supervision
without adding a route or backend action:

- Adds a shell-strip `OPEN` control for Command Center supervision.
- Adds a route-independent drawer that displays active task, mission ledger,
  recovery, risk gates, timeline, preflight rows, recovery queue, and
  provenance from the existing read-only `/api/command-center` payload.
- Keeps Settings `CommandCenterPanel` as the deep inspection surface.
- Does not execute actions, authorize recovery, mutate artifacts, call
  providers, expose credentials, route broker actions, or enable live/private
  behavior.
- Verification is tracked in
  `docs/planning/M23_GLOBAL_COMMAND_CENTER_DRAWER.md`.

## M21.6 Alpha Vantage Quote Watchlist Slice

The sixth implementation slice is optional-key Alpha Vantage quote watchlist
depth for Markets Stocks and ETF:

- Directly addresses the Markets quote-breadth gap without introducing paid bulk
  endpoints, broker keys, live execution, or fixture/default quote prices.
- Keeps `GLOBAL_QUOTE` behind the reviewed local secret store and caches each
  symbol independently under `market_data/equities/alphavantage/global_quote/`.
- Expands the default Stocks quote surface from `AAPL` to `AAPL/MSFT/NVDA` and
  ETF from `SPY` to `SPY/QQQ/IWM`, with capped sanitized agent overrides.
- Updates provider freshness, Markets UI, and the AI Agent contract so an agent can
  inspect row counts, cached/live/stale state, cache paths, and source attribution.
- Verification is tracked in `docs/planning/M21_ALPHA_VANTAGE_QUOTE_WATCHLIST.md`.

## M21.7 Backtest Walk-Forward Slice

The seventh implementation slice is local Backtest walk-forward workflow depth:

- Directly addresses the Backtest command-depth gap from sanitized Fincept evidence,
  where `Walk-Forward` is an enabled command alongside Run Backtest and Optimize.
- Implements fixed-parameter, closed-candle walk-forward validation under
  `/api/backtest/walk-forward` with fold summary/folds/report/manifest artifacts.
- Keeps Optimize, live trading, private provider keys, broker routing, real balances,
  margin, leverage, short exposure, derivatives, paid data, and fixture-primary runtime
  out of scope.
- Updates the Backtest UI and AI Agent contract so agents can run and inspect
  walk-forward artifacts through stable local surfaces.
- Verification is tracked in `docs/planning/M21_BACKTEST_WALK_FORWARD.md`.

## M23.20 Backtest Comparison Packet Slice

This later implementation slice deepens Backtest research artifact usability
without reopening optimize/deploy/live surfaces:

- Adds `POST /api/backtest/comparison-packet` for bounded comparison of recent
  local `bt-*` artifacts.
- Writes `comparison.json`, `rows.csv`, `manifest.json`, and `report.md` under
  `artifacts/backtests/comparisons/`.
- Adds the Backtest `Compare Runs` UI command and `Comparison` result tab.
- Updates the AI Agent contract with `backtest_comparison_packet` and state
  field `comparison_packet`.
- Keeps optimize, replay, deployment, broker routing, live orders, real balances,
  and destructive artifact lifecycle execution out of scope.
- Verification is tracked in `docs/planning/M23_BACKTEST_COMPARISON_PACKET.md`.

## M23.25 Backtest Run Index Slice

This later implementation slice deepens Backtest workflow supervision without
opening optimize, replay, deploy, broker, or live surfaces:

- Adds read-only `GET /api/backtest/runs` for bounded inspection of recent local
  `bt-*` run metadata.
- Embeds `run_index` in `GET /api/backtest` so route defaults include latest
  run, comparison readiness, recommended next action, and safety flags.
- Adds Backtest UI selector `backtest-run-index` and AI Agent action
  `backtest_run_index`.
- The index returns in-memory metadata only; it does not write artifacts, rerun
  strategies, optimize, replay, deploy, mutate Portfolio state, route broker
  actions, submit live orders, or execute destructive lifecycle actions.
- Verification is tracked in `docs/planning/M23_BACKTEST_RUN_INDEX.md`.

## M23.26 Markets Quote Reference Coverage Slice

This later implementation slice deepens Markets AI Agent supervision without
adding provider breadth or mislabeling reference data:

- Adds `quote_reference_coverage` to `/api/markets` and read-only
  `GET /api/markets/quote-reference-coverage`.
- Summarizes quote, reference, and context lanes from the existing
  `source_coverage_matrix`.
- Adds Markets UI selector `markets-quote-reference-coverage` and AI Agent
  action `markets_quote_reference_coverage`.
- Keeps all quote lanes non-orderable and reports zero executable/orderable/live
  lanes; no provider calls, signup, secrets, artifact writes, broker routing, or
  live trading path is added.
- Verification is tracked in
  `docs/planning/M23_MARKETS_QUOTE_REFERENCE_COVERAGE.md`.

## M23.27 AI Chat Context Contract Slice

This later implementation slice deepens AI Chat AI Agent supervision without
adding managed LLM behavior or artifact content reads:

- Adds `context_contract` to `/api/ai-chat` and read-only
  `GET /api/ai-chat/context-contract`.
- Reports prompt/session/artifact limits, transcript output state, source
  citations, linked artifact provenance, context artifact metadata, and safety
  flags.
- Adds AI Chat UI selector `ai-chat-context-contract` and AI Agent action
  `ai_chat_context_contract`.
- Keeps AI Chat local dry-run only: no provider calls, managed LLM execution,
  artifact content indexing, request/response replay, credentials, broker
  routing, or live trading path is added.
- Verification is tracked in `docs/planning/M23_AI_CHAT_CONTEXT_CONTRACT.md`.

## M23.28 Advanced Output IO Contract Slice

This later implementation slice deepens advanced-route AI Agent supervision
without executing routes or reading artifact contents:

- Adds `io_contract` to each route row in
  `GET /api/advanced-workflows/output-packet`.
- Reports per-route safe input contracts, output artifact contracts, error
  contracts, latest output paths, safe local action, blocked runtime actions,
  read mode, and safety flags.
- Surfaces the same contract through Command Center advanced outputs.
- Adds Settings route state `advanced_output_io_contract` and AI Agent action
  `advanced_workflow_io_contract`.
- Keeps AI Chat, Nodes, Code, Quant Lab, and QuantLib bounded to dry-run,
  static-analysis, local-preview, and deterministic-calculator behavior; no
  workflow execution, notebook runtime, managed LLM, external QuantLib runtime,
  provider call, credential access, artifact content indexing, broker routing,
  or live trading path is added.
- Verification is tracked in
  `docs/planning/M23_ADVANCED_OUTPUT_IO_CONTRACT.md`.

## M23.29 QuantLib Fixed-Income Calculator Slice

This later implementation slice deepens QuantLib calculator breadth without
expanding runtime scope:

- Adds `bond-duration` as a deterministic stdlib fixed-income quick action.
- Computes bond price, Macaulay duration, modified duration, convexity,
  basis-point value, periods, and payment frequency.
- Reuses the existing QuantLib request/response/context/manifest/report/error
  artifact bundle and safety validators.
- Updates frontend fallback visibility and Command Center milestone provenance.
- Keeps external QuantLib runtime, providers, notebook/workflow execution,
  artifact content indexing, credentials, broker routing, real balances,
  derivatives execution, orders, and live/private behavior disabled.
- Verification is tracked in
  `docs/planning/M23_QUANTLIB_FIXED_INCOME_CALCULATOR.md`.

## M23.30 Code Static Outline Slice

This later implementation slice deepens Code workspace static analysis without
adding notebook execution:

- Adds AST-only `static_outline` metadata to `POST /api/code/analyze`.
- Reports imports, definitions, calls, syntax-error markers, and safety flags in
  `analysis_result`, `last_analysis`, `analysis.json`, and
  `analysis_manifest.json`.
- Extends `analysis_report.md` and the Code UI supervision panel with compact
  outline counts and first imports/definitions.
- Updates the AI Agent contract and advanced-output IO contract so agents know
  the outline is available before deciding whether Code artifacts are useful.
- Keeps notebook execution, kernel processes, providers, artifact content reads,
  source return, credential access, broker routing, real balances, derivatives
  execution, orders, and live/private behavior disabled.
- Verification is tracked in `docs/planning/M23_CODE_STATIC_OUTLINE.md`.

## M23.31 Bank of Canada FX Reference Slice

This later implementation slice deepens FX reference breadth without
mislabeling reference data as tradable quotes:

- Adds `bank_of_canada_valet_fx_reference_public` as a public no-key provider.
- Normalizes bounded Valet observations for `USD/CAD`, `EUR/CAD`, `GBP/CAD`,
  `JPY/CAD`, and `CHF/CAD` into local CAD reference-rate rows.
- Adds local cache/storage/public-refresh/provider-registry/provider-acquisition
  coverage under `market_data/fx/bank_of_canada/`.
- Adds Markets `cad_reference_rates` source coverage and a Bank of Canada CAD
  Reference UI panel with Provider Stack and Source Contract visibility.
- Updates the AI Agent contract and Command Center provenance for `fx.boc`.
- Keeps BoC rows reference-only: no executable FX quote claim, broker/exchange
  binding, balances, order routing, derivatives execution, payment, cloud, or
  credential path is added.
- Verification is tracked in
  `docs/planning/M23_BANK_OF_CANADA_FX_REFERENCE.md`.

## M23.32 Backtest Volatility Reversion Slice

This later implementation slice deepens Backtest/Algo local strategy breadth
without expanding execution scope:

- Adds `volatility_reversion` as a fourth local closed-candle Backtest strategy.
- Keeps the strategy long/flat with next-open fills after closed-candle signals.
- Records `local_volatility_reversion_v1`, volatility-band indicators, signals,
  trades, returns, schema, constraints, and provenance in the existing artifact
  bundle.
- Lets Algo saved strategies run the new strategy through the existing
  `/api/algo/run-backtest` handoff.
- Updates frontend fallback/E2E visibility and Command Center milestone
  provenance.
- Keeps optimize, deployment, broker routing, shorts, derivatives, real orders,
  real balances, credentials, destructive lifecycle actions, and live/private
  behavior disabled.
- Verification is tracked in
  `docs/planning/M23_BACKTEST_VOLATILITY_REVERSION.md`.

## M23.44 Backtest Momentum Continuation Slice

This later implementation slice deepens Backtest/Algo local strategy breadth
without expanding execution scope:

- Adds `momentum_continuation` as a fifth local closed-candle Backtest strategy.
- Keeps the strategy long/flat with signals on close and next-open fills.
- Records `local_momentum_continuation_v1`, momentum-reference indicators,
  signals, trades, returns, schema, constraints, and provenance in the existing
  artifact bundle.
- Lets Algo saved strategies run the new strategy through the existing
  `/api/algo/run-backtest` handoff.
- Updates frontend fallback/E2E visibility and Command Center milestone
  provenance.
- Keeps optimize, deployment, broker routing, shorts, derivatives, real orders,
  real balances, credentials, destructive lifecycle actions, and live/private
  behavior disabled.
- Verification is tracked in
  `docs/planning/M23_BACKTEST_MOMENTUM_CONTINUATION.md`.

## M23.63 Backtest RSI Reversion Slice

This later implementation slice deepens Backtest/Algo local strategy breadth
without expanding execution scope:

- Adds `rsi_reversion` as another local closed-candle Backtest strategy.
- Keeps the strategy long/flat with signals on close and next-open fills.
- Records `local_rsi_reversion_v1`, RSI indicator rows, signals, trades,
  returns, schema, constraints, and provenance in the existing artifact bundle.
- Lets Algo saved strategies run the new strategy through the existing
  `/api/algo/run-backtest` handoff.
- Updates frontend fallback/E2E visibility and Command Center milestone
  provenance.
- Keeps optimize, deployment, provider calls, broker routing, shorts,
  derivatives, real orders, real balances, credentials, destructive lifecycle
  actions, and live/private behavior disabled.
- Verification is tracked in
  `docs/planning/M23_BACKTEST_RSI_REVERSION.md`.

## M23.33 Portfolio Report Index Slice

This later implementation slice deepens Portfolio artifact lifecycle
supervision without reading report contents or enabling lifecycle mutation:

- Adds `GET /api/portfolio/reports` as a read-only local report artifact index.
- Embeds `report_index` in `/api/portfolio` for AI Agent route-state discovery.
- Reports active/latest report ids, expected artifact paths, file presence,
  missing counts, and advisory recovery queue rows.
- Adds Portfolio UI selector `portfolio-report-index` and AI Agent
  `portfolio_report_index` contract coverage.
- Keeps report content reads, artifact content indexing, automatic repair,
  archive/prune/delete/move/restore execution, credential access, real balances,
  optimizer execution, broker routing, and live/private behavior disabled.
- Verification is tracked in
  `docs/planning/M23_PORTFOLIO_REPORT_INDEX.md`.

## M23.34 Finnhub Equity Quote Watchlist Slice

This later implementation slice adds a bounded optional-key equity quote lane
without changing orderability or live-trading exclusions:

- Adds Finnhub `/quote` normalization for `AAPL/MSFT/NVDA/SPY` using an already
  stored local data-provider key.
- Writes local quote caches under `market_data/quotes/finnhub/{symbol}.json`.
- Adds `/api/finnhub/quotes`, `/api/markets/finnhub/quotes/refresh`, Markets
  `finnhub_quotes` source coverage, provider/source registry rows, and AI Agent
  `markets_finnhub_quote_watchlist_refresh`.
- Keeps quotes non-orderable and outside public no-key refresh jobs, provider
  signup, credential output, broker/exchange connectivity, balances, orders,
  and live/private behavior.
- Verification is tracked in
  `docs/planning/M23_FINNHUB_EQUITY_QUOTE_WATCHLIST.md`.

## M23.35 Advanced Output State-File Classification Slice

This later implementation slice tightens advanced-route recovery semantics
without creating new outputs or execution paths:

- Separates root-level route state files such as `chat_state.json`,
  `nodes_state.json`, `code_state.json`, `quant_lab_state.json`, and
  `quantlib_state.json` from real advanced output artifacts.
- Extends `GET /api/advanced-workflows/output-packet` with
  `state_artifact_file_count`, route-level `state_artifact_count`, and latest
  state-artifact paths while keeping output health based on real output files.
- Surfaces the same state/output split through Command Center and the AI Agent
  advanced-output index contract.
- Keeps recovery advisory and metadata-only; no artifact content read, route
  execution, notebook/workflow runtime, managed LLM call, external QuantLib
  runtime, route-output mutation, credential access, or destructive recovery
  path is enabled.
- Verification is tracked in
  `docs/planning/M23_ADVANCED_OUTPUT_STATE_FILE_CLASSIFICATION.md`.

## M23.36 Cboe Delayed Quote Gate Slice

This later implementation slice deepens provider-entry discipline without
adding a data adapter:

- Adds `cboe_delayed_quotes_gate` to `GET /api/provider-acquisition-gate`.
- Classifies Cboe delayed quote pages as `blocked_official_terms` with
  `quote_blocked_by_terms`, no cache path, and no actionable next candidate.
- Updates the provider research matrix and Command Center current milestone so
  AI Agents can see the source was evaluated and must not be retried as a
  page-crawling shortcut.
- Keeps Cboe out of source coverage, quote/reference lanes, provider refresh,
  caches, credentials, broker/exchange connectivity, and live/private behavior.
- Verification is tracked in
  `docs/planning/M23_CBOE_DELAYED_QUOTE_GATE.md`.

## M23.42 IEX TOPS Market Data Gate Slice

This later implementation slice deepens provider-entry discipline without
adding a data adapter:

- Adds `iex_tops_market_data_gate` to `GET /api/provider-acquisition-gate`.
- Classifies IEX TOPS/DEEP real-time market data as `blocked_official_terms`
  with subscriber-agreement auth mode, no cache path, and no actionable next
  candidate.
- Updates the provider research matrix and Command Center current milestone so
  AI Agents can see the source was evaluated and must not be retried through
  legacy IEX Cloud/no-key assumptions.
- Keeps IEX out of source coverage, quote/reference lanes, provider refresh,
  caches, credentials, broker/exchange connectivity, and live/private behavior.
- Verification is tracked in
  `docs/planning/M23_IEX_TOPS_MARKET_DATA_GATE.md`.

## M23.43 Provider Gate Candidate Detail Slice

This later implementation slice deepens command-center supervision without
adding provider behavior:

- Exposes existing provider acquisition candidates, rules, and stop gates in the
  Settings Command Center frontend type/UI.
- Shows blocked provider-entry rows first so human supervisors and AI Agents can
  see IEX/Cboe are blocked by terms instead of treating them as retryable
  provider work.
- Adds stable candidate selectors for the blocked rows and Playwright coverage
  for IEX `blocked_official_terms`, `subscriber_agreement_required`, and
  `quote_blocked_by_terms`.
- Keeps provider adapters, source coverage rows, provider refreshes, caches,
  credentials, broker/exchange connectivity, orderability, and live/private
  behavior unchanged.
- Verification is tracked in
  `docs/planning/M23_PROVIDER_GATE_CANDIDATE_DETAIL.md`.

## M21.8 Artifact Archive Plan Slice

The eighth implementation slice is non-destructive artifact archive/prune planning:

- Directly addresses the cross-route lifecycle gap left after M21.1 metadata-only
  inventory, M20.19 Forum repair, and M20.23 provider refresh lifecycle visibility.
- Adds `/api/artifact-lifecycle/archive-plan`, which writes a local plan bundle under
  `artifacts/diagnostics/artifact-lifecycle-plan-*` from metadata only.
- Keeps real archive, prune, delete, move, restore, content reads, credential reads,
  external network calls, live trading, broker mutation, installed-source reads,
  branding, and commercial mechanics disabled.
- Updates Settings and the AI Agent contract so agents can request and inspect a
  lifecycle plan without guessing from filesystem paths or UI text.
- Verification is tracked in `docs/planning/M21_ARTIFACT_ARCHIVE_PLAN.md`.

## M21.9 BLS Macro Provider Slice

The ninth implementation slice is BLS public macro/labor provider breadth:

- Directly addresses the non-crypto provider breadth priority with an official
  public no-key U.S. government source.
- Adds BLS latest unemployment, payroll, and CPI series to the shared research
  macro payload and Markets Indexes/Regional context panels.
- Keeps Index and Regional quote rows disabled behind provider gates; BLS values are
  macro context, not executable market quotes.
- Updates provider freshness, manual public refresh manifests, Markets UI, and the
  AI Agent contract for stable refresh/inspection.
- Verification is tracked in `docs/planning/M21_BLS_MACRO_PROVIDER.md`.

## M23.50 Eurostat HICP Macro Context Slice

This later implementation slice deepens Markets macro provider breadth with an
official public no-key Eurostat source:

- Adds `eurostat_hicp_public` as bounded EA20 all-items HICP monthly macro
  context from the Eurostat Statistics API dataset `prc_hicp_midx`.
- Writes local cache state to
  `market_data/macro/eurostat/hicp_ea20_cp00_i15.json`.
- Adds `/api/eurostat/hicp`, `/api/eurostat/hicp/refresh`, public provider
  refresh coverage, provider/source registry rows, and provider-acquisition
  status.
- Keeps Eurostat rows `not_quote`, non-orderable, and outside broker/exchange,
  balance, trade-signal, credential, and live/private semantics.
- Verification is tracked in
  `docs/planning/M23_EUROSTAT_HICP_CONTEXT.md`.

## M21.10 Macro Aggregation Contract Slice

The tenth implementation slice is the macro aggregation headline contract:

- Directly closes the M21.9 architecture watch by replacing implicit provider-order
  latest/headline behavior with explicit `primary_provider`, `headline_series`,
  `headline_series_id`, `headline_rule`, and `provider_summaries` fields.
- Keeps DBnomics, FRED, and BLS as macro/reference context for Indexes and Regional;
  executable index/regional quotes remain disabled behind provider gates.
- Adds dense terminal rows for `HEADLINE`, `PRIMARY`, `RULE`, `PROVIDERS`, and
  `HEADLINE ID` so AI Agents can inspect the selected macro context without
  scraping list order.
- Verification is tracked in
  `docs/planning/M21_MACRO_AGGREGATION_CONTRACT.md`.

## M21.11 Markets Macro Panel Split Slice

The eleventh implementation slice is the Markets macro source/provider panel
split:

- Directly closes the M21.10 watch by separating macro provider-stack state from
  quote/source contract state before adding more macro provider breadth.
- Adds stable `markets-{tab}-macro-provider-stack` and
  `markets-{tab}-macro-source-contract` selectors for AI Agent operation.
- Adds `macro_provider_stack` to the Markets route state fields in the agent
  contract.
- Keeps DBnomics, FRED, and BLS as macro/reference context only; executable
  index/regional quotes remain disabled behind provider gates.
- Verification is tracked in
  `docs/planning/M21_MARKETS_MACRO_PANEL_SPLIT.md`.

## M21.12 Markets Provider Source Contract Slice

The twelfth implementation slice extends the source/provider split to non-macro
Markets provider families:

- Adds Provider Stack and Source Contract panels for Stocks, ETF, FX,
  Commodities, and Bonds/Rates.
- Adds stable selectors for each new panel so AI Agents can inspect provider state,
  cache/source contracts, quote gates, and reference-only use without guessing from
  ad hoc source rows.
- Adds `provider_stack_panels` and `source_contract_panels` to the Markets route
  state contract.
- Keeps all provider safety classes unchanged: Alpha Vantage remains optional-key
  and local-secret-gated; SEC, ECB, Treasury, World Bank, and EIA remain reference
  or context sources as previously contracted.
- Verification is tracked in
  `docs/planning/M21_MARKETS_PROVIDER_SOURCE_CONTRACTS.md`.

## M21.13 SEC Company Ticker Registry Slice

The thirteenth implementation slice expands Markets Stocks issuer-reference
depth:

- Adds `sec_company_ticker_registry_public` as public no-key SEC company ticker,
  CIK, and company-name reference data.
- Separates issuer registry rows from SEC companyfacts and optional-key Alpha
  Vantage quote state.
- Keeps registry rows reference-only and non-executable; no quote prices, broker
  keys, live trading, paid data, account/cloud mechanics, or installed-source reads
  were added.
- Verification is tracked in
  `docs/planning/M21_SEC_COMPANY_TICKER_REGISTRY.md`.

## M21.14 Algo Provider Cache Scan Slice

The fourteenth implementation slice deepens Algo scanner workflow and artifacts:

- Directly addresses the Algo route gap by making scans provider/cache-aware,
  artifact-backed, and AI-agent-operable.
- Adds per-row source/cache evidence and `source_contract` fields so agents can
  distinguish provider-cache signals from no-data states without scraping UI text.
- Writes `scan.json`, `scan_report.md`, and `manifest.json` under
  `artifacts/algo/scans/{scan_id}/`.
- Keeps outputs signal-only and non-actionable; no live deploy, broker routing,
  private API, real balance, margin, leverage, short, derivatives, paid data,
  fixture-primary runtime, or installed-source reads were added.
- Verification is tracked in
  `docs/planning/M21_ALGO_PROVIDER_CACHE_SCAN.md`.

## M21.15 Algo Scan Artifact Lifecycle Slice

The fifteenth implementation slice hardens Algo scan artifact lifecycle repair:

- Directly closes the M21.14 architecture watch by moving scan artifact mirror
  writes behind dedicated `write_algo_scan_artifacts` and
  `algo_scan_artifact_health` storage boundaries.
- Adds health/status reporting for the latest scan artifact mirror, including
  expected/present/missing counts and per-file state for `scan.json`,
  `scan_report.md`, and `manifest.json`.
- Preserves corrupted latest-scan evidence with `invalid_scan_state` instead of
  collapsing invalid state into `no_scan`.
- Adds safe read and repair endpoints under `/api/algo/scan-artifacts` and
  `/api/algo/scan-artifacts/repair`; repair rewrites only expected files from
  normalized local scan state.
- Updates the Algo UI and AI Agent contract so agents can inspect and repair the
  latest scan artifact mirror without guessing filesystem paths or relying on
  text scraping.
- Keeps archive, replay, prune, delete, restore, live deployment, broker routing,
  private provider keys, paid data, fixture-primary runtime, and installed-source
  reads out of scope.
- Verification is tracked in
  `docs/planning/M21_ALGO_SCAN_ARTIFACT_LIFECYCLE.md`.

## M23.40 Algo Scan Readiness Slice

This later implementation slice deepens Algo AI Agent operability before
artifact-writing scanner actions:

- Adds metadata-only `GET /api/algo/scan-readiness` and embedded Algo
  `scan_readiness`.
- Reports active strategy readiness, provider/cache usefulness, per-symbol
  expected signal state, source-row counts, latest scan artifact health,
  Backtest handoff readiness, and safe recommended actions.
- Adds UI selector `algo-scan-readiness` and AI Agent action
  `algo_scan_readiness`.
- Keeps scan execution, provider refresh, artifact writes/repair, optimizer,
  deployment, broker routing, credentials, balances, orders, and live/private
  behavior disabled.
- Verification is tracked in `docs/planning/M23_ALGO_SCAN_READINESS.md`.

## M21.16 SEC Company Submissions Slice

The sixteenth implementation slice expands Markets Stocks filing-reference depth:

- Adds `sec_company_submissions_public` as public no-key SEC recent filing
  metadata from the official EDGAR submissions API.
- Separates filing rows from SEC companyfacts, SEC company ticker registry rows,
  and optional-key Alpha Vantage quote state.
- Adds a dense Recent Filings panel and `stock_company_filings` route state so AI
  Agents can inspect form/date/accession/source/cache fields without treating
  filings as quote or order signals.
- Keeps filings reference-only and non-executable; no quote prices, broker keys,
  live trading, paid data, account/cloud mechanics, fixture-primary runtime, or
  installed-source reads were added.
- Verification is tracked in
  `docs/planning/M21_SEC_COMPANY_SUBMISSIONS.md`.
