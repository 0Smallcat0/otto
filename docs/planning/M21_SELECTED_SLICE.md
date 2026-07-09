# M21 Selected Slice

Date: 2026-05-24

## Selected Scope

Implement the first bounded M21 slice as:

1. Tooling governance: keep CodeGraph as local tooling and exclude `.codegraph/`.
2. Planning evidence: route gap report, provider research matrix, observation protocol.
3. Product slice: read-only artifact/provider lifecycle visibility for AI Agent use.

## Why This Slice

- It moves the app toward the M21 objective without pretending all 15 route gaps are
  closed.
- It is cross-route and supports every future route/provider milestone.
- It is local-only, credential-free, and live-trading-safe.
- It improves AI Agent operability by exposing explicit lifecycle state rather than
  forcing agents to infer artifact health from scattered file paths.

## Product Requirements

- Add a read-only artifact lifecycle payload.
- Include root-level counts, bytes, newest update, missing/present root state, and
  route ownership.
- Include provider refresh diagnostic bundle status.
- Include explicit lifecycle actions with destructive prune/archive/delete disabled.
- Expose the payload through governance/help diagnostics and a direct API endpoint.
- Do not read artifact contents; inspect metadata only.
- Do not delete, prune, archive, mutate, or upload artifacts.

## Acceptance Criteria

- API returns machine-readable lifecycle rows for major artifact roots.
- Safety payload proves read-only behavior, no destructive actions, no external network,
  no credentials, no live trading, and no content reads.
- Tests cover metadata-only lifecycle reporting, missing roots, diagnostics bundle output,
  and local path boundaries.
- Handoff docs record M21 selected slice and verification.

## Implementation Result

- Added `src/local_terminal/artifact_lifecycle.py`.
- Added `/api/artifact-lifecycle`.
- Added artifact lifecycle state to governance, Help diagnostics, governance diagnostic
  bundles, Settings UI, and E2E coverage.
- Added `tests/test_m21_artifact_lifecycle.py`.
- Kept all lifecycle mutation actions disabled: prune, archive, delete, recover, and
  content reads remain unavailable in this slice.

## Verification

- Focused artifact lifecycle/governance tests: 8 passed.
- Full pytest with repo-local TEMP/TMP: 208 passed.
- Ruff: passed.
- Frontend lint/build: passed.
- Playwright E2E: 15 passed.
- Screenshot evidence: `artifacts/screenshots/m21-artifact-lifecycle-settings.png`
  (ignored local artifact).
- Provider research matrix source refresh: official/primary docs checked.
- `git diff --check`: passed with Git CRLF working-copy warnings only.
- Exact sensitive-literal scan: no known account credential/PIN literals found.
- Code-review gate: no CRITICAL/HIGH/BLOCK findings.

## Next Selected Slice

M21.2 selects News route GDELT DOC metadata enrichment. The governing artifact is
`docs/planning/M21_NEWS_GDELT_DOC.md`.

This slice is chosen because live Fincept observation confirmed that News parity depth
depends on more than a headline list: the route exposes a dense command strip, FEEDS /
ARTS / CLST / SRCS / SENT / WATCHES counters, clustered feed mode, provider/source
state, selected-item metadata, and disabled/gated AI/refresh actions.

## M21.3 Selected Slice

M21.3 selects Markets Commodities EIA Open Data energy context. The governing
artifact is `docs/planning/M21_EIA_ENERGY_CONTEXT.md`.

This slice is chosen because M21 prioritizes non-crypto provider breadth, and EIA is
an official public energy-data source that fits the existing optional local-key
provider model. It remains reference-only and cannot be used for executable
commodity quotes, futures, real orders, balances, margin, leverage, shorts, or
derivatives.

## M21.4 Selected Slice

M21.4 selects the AI Agent operability contract. The governing artifact is
`docs/planning/M21_AGENT_OPERABILITY_CONTRACT.md`.

This slice is chosen because the local terminal is intended to be operated by an AI
Agent through stable local APIs, state fields, selectors, artifacts, and safety/error
contracts. The slice adds `/api/agent-contract`, governance/help diagnostics coverage,
and a Settings surface without adding provider credentials, cloud/account behavior,
commercial mechanics, live trading, external execution, or destructive artifact actions.

## M21.5 Selected Slice

M21.5 selects provider refresh lifecycle visibility. The governing artifact is
`docs/planning/M21_PROVIDER_REFRESH_LIFECYCLE.md`.

This slice is chosen because M20.23 left a concrete lifecycle watch item: manual
public refresh jobs are pollable, but interrupted queued/running jobs, manifest-only
history, failed runs, and stale recovery guidance were not yet machine-readable. The
slice adds a read-only lifecycle endpoint, Provider Freshness summary, Settings panel,
Help/governance diagnostics coverage, and AI Agent contract action. It does not add
automatic scheduling, cache mutation, status rewrite, prune/archive/delete actions,
provider credentials, optional-key refreshes, live trading, or installed-source reads.

## M21.6 Selected Slice

M21.6 selects Alpha Vantage quote watchlist depth for Markets Stocks and ETF. The
governing artifact is `docs/planning/M21_ALPHA_VANTAGE_QUOTE_WATCHLIST.md`.

This slice is chosen because the sanitized Markets evidence shows dense multi-symbol
quote grids, while the current local route only exposed one Alpha Vantage stock
symbol and one ETF symbol. The implementation keeps the provider optional-key and
local-secret-gated, uses the official one-symbol `GLOBAL_QUOTE` endpoint through
bounded per-symbol caches, and does not activate Alpha Vantage premium bulk quotes,
paid entitlements, broker/exchange credentials, live orders, balances, margin,
leverage, short exposure, derivatives, cloud behavior, or installed-source reads.

## M21.7 Selected Slice

M21.7 selects Backtest walk-forward workflow depth. The governing artifact is
`docs/planning/M21_BACKTEST_WALK_FORWARD.md`.

This slice is chosen because sanitized Fincept Backtest evidence shows `Walk-Forward`
as an enabled command, while the local route previously listed it but kept it disabled.
The implementation makes it a real local fixed-parameter, closed-candle validation
workflow with fold artifacts and agent-contract coverage. Optimize, live trading,
private provider keys, broker routing, real balances, margin, leverage, short
exposure, derivatives, paid data, cloud behavior, and installed-source reads remain
out of scope.

## M21.8 Selected Slice

M21.8 selects non-destructive artifact archive/prune planning. The governing
artifact is `docs/planning/M21_ARTIFACT_ARCHIVE_PLAN.md`.

This slice is chosen because the current terminal already exposes metadata-only
artifact lifecycle state, but agents still need a repeatable local plan artifact
before any future reviewed archive/prune/recovery UX can exist. The implementation
writes `artifacts/diagnostics/artifact-lifecycle-plan-*` bundles from metadata only
and keeps real archive, prune, delete, move, restore, content reads, credentials,
network calls, live trading, installed-source reads, branding, and commercial
mechanics disabled.

## M21.9 Selected Slice

M21.9 selects BLS public macro/labor provider breadth. The governing artifact is
`docs/planning/M21_BLS_MACRO_PROVIDER.md`.

This slice is chosen because M21 prioritizes official/public non-crypto provider
breadth and the Markets Indexes/Regional panels still need richer no-key context
without pretending to have executable index or regional quotes. The implementation
uses the official BLS Public Data API latest-series endpoint for a bounded set of
labor/inflation series, writes a local cache under
`market_data/macro/bls/latest_series.json`, and exposes a Markets `BLS` refresh
action plus AI Agent contract coverage. It does not add provider signup, credentials,
paid data, account/cloud mechanics, live trading, broker/exchange keys, real
balances, margin, leverage, short exposure, derivatives, installed-source reads,
branding, or fixture-primary runtime claims.

Verification is tracked in `docs/planning/M21_BLS_MACRO_PROVIDER.md` and
`docs/planning/FINAL_HANDOFF.md`. Code-review gate approved the slice after fixing
DBnomics/BLS refresh attribution; the remaining watch is to formalize macro
aggregation headline semantics before adding more macro provider breadth.

## M21.10 Selected Slice

M21.10 selects the macro aggregation headline contract. The governing artifact is
`docs/planning/M21_MACRO_AGGREGATION_CONTRACT.md`.

This slice is chosen because M21.9 deliberately left a concrete architecture watch:
Markets Indexes/Regional headline/latest fields were still derived from provider
list order after BLS joined DBnomics and FRED. The implementation makes
`primary_provider`, `headline_series`, `headline_series_id`, `headline_rule`, and
`provider_summaries` explicit across the research payload, Markets payload, UI rows,
TypeScript contracts, and regression tests. It does not add provider signup,
credentials, paid data, live trading, broker/exchange keys, real balances, margin,
leverage, short exposure, derivatives, installed-source reads, branding, or
fixture-primary runtime claims.

## M21.11 Selected Slice

M21.11 selects the Markets macro panel split. The governing artifact is
`docs/planning/M21_MARKETS_MACRO_PANEL_SPLIT.md`.

This slice is chosen because M21.10 deliberately left a concrete architecture
watch: the macro source/provider attribution surface was too dense to keep adding
provider breadth safely. The implementation splits the Indexes/Regional macro
`SOURCE` column into `Provider Stack` and `Source Contract` panels, adds stable
test ids for AI-agent operation, and exposes `macro_provider_stack` in the Markets
route state contract. It does not add provider signup, credentials, paid data, live
trading, broker/exchange keys, real balances, margin, leverage, short exposure,
derivatives, installed-source reads, branding, or fixture-primary runtime claims.

## M21.12 Selected Slice

M21.12 selects Markets provider/source contract panels for non-macro provider
families. The governing artifact is
`docs/planning/M21_MARKETS_PROVIDER_SOURCE_CONTRACTS.md`.

This slice is chosen because M21.11 created the split source/provider pattern for
macro panels only, while Stocks, ETF, FX, Commodities, and Bonds/Rates still carried
route-specific source rows that were harder for an AI Agent to operate uniformly.
The implementation adds stable Provider Stack and Source Contract surfaces across
those non-macro panels without adding provider signup, credentials, paid data, live
trading, broker/exchange keys, real balances, margin, leverage, short exposure,
derivatives, installed-source reads, branding, or fixture-primary runtime claims.

## M21.17 Selected Slice

M21.17 selects provider refresh result semantics. The governing artifact is
`docs/planning/M21_PROVIDER_REFRESH_RESULT_SEMANTICS.md`.

This slice is chosen because M21.16 deliberately left a concrete architecture
watch: `cache_written` in public provider refresh results was too easy for an AI
Agent to interpret as "this run wrote fresh data" even when the result only proved
that stale cache was available. The implementation separates
`cache_written_this_run`, `cache_available`, and `cache_reused`, updates Provider
Freshness summary text, and exposes the result semantics through the Settings
agent contract. It does not add automatic scheduling, destructive recovery,
credential handling, optional-key refreshes, paid data, live trading, broker flows,
installed-source reads, branding, or fixture-primary runtime claims.

## M21.18 Selected Slice

M21.18 selects Markets Stocks status lane separation. The governing artifact is
`docs/planning/M21_STOCK_STATUS_LANES.md`.

This slice is chosen because M21.16/M21.17 left a concrete Stocks route depth gap:
registry, filings, fundamentals, and optional quotes were implemented as separate
data paths, but route headline/gateway behavior still collapsed them into a single
provider state. The implementation adds `stocks.status_lanes`, updates the Stocks
gateway to report lane availability, adds a dense Status Lanes panel, and exposes
the lane contract to AI Agents. It does not add provider signup, credentials, paid
data, live trading, broker/exchange keys, real balances, margin, leverage, short
exposure, derivatives, installed-source reads, branding, or fixture-primary runtime
claims.

## M21.19 Selected Slice

M21.19 selects the Markets Stocks SEC filings watchlist. The governing artifact is
`docs/planning/M21_STOCK_FILINGS_WATCHLIST.md`.

This slice is chosen because M21.18 made the filings lane visible, but M21.16 still
persisted recent submissions as a single default-company cache. The implementation
expands SEC recent filing metadata to bounded `AAPL/MSFT/NVDA` per-CIK caches,
adds watchlist filing summaries/columns, and exposes a filings-watchlist state
field for AI Agents. It does not add provider signup, credentials, paid data, live
trading, broker/exchange keys, real balances, margin, leverage, short exposure,
derivatives, installed-source reads, branding, commercial copy, or fixture-primary
runtime claims.

## M21.20 Selected Slice

M21.20 selects the Markets Source Coverage Matrix / Provider Entry Gate. The
governing ralplan artifact is
`.omx/plans/ralplan-m21-20-markets-provider-source-state-20260524T235845Z.md`.

This slice is chosen because Markets already has many provider/source lanes, but
future breadth work needed one AI-agent-readable contract before adding another
adapter. The implementation adds `source_coverage_matrix` to `/api/markets`,
the Markets AI Agent state/action contracts, and the dense Markets Provider Entry
Gate table so Stocks, ETF, FX, Commodities, Indexes/Regional, and Bonds/Rates can
be compared by provider ID, auth mode, cache state, TTL, docs URL, quote
semantics, gated reason, safe action, and next safe action.

M21.20 deliberately does not add a new provider adapter. It does not add provider
signup, key acquisition, paid/bulk data, live trading, broker/exchange keys, real
balances, order paths, margin, leverage, short exposure, derivatives,
installed-source reads, Fincept branding, commercial copy, or fixture-primary
runtime claims.

## M21.21 Selected Slice

M21.21 selects Backtest + Algo research loop depth. The governing ralplan artifact
is `.omx/plans/ralplan-m21-21-backtest-algo-research-loop-20260525.md`.

This slice is chosen because M21.20 made Markets source/provider/cache state
agent-readable, but the local terminal still needed a larger Fincept-style research
workflow: Markets source row -> Algo scan artifact -> scan-seeded Backtest
provenance -> artifact manifests -> AI Agent contracts -> browser evidence.

The implementation adds deterministic Markets source-row identity, a canonical
`research_lineage` contract, Algo scan source-row binding, scan report/manifest
lineage, Backtest config/provenance/manifest lineage, frontend lineage panels, and
E2E coverage for the loop. Direct Backtest lineage is accepted only when it matches
the latest local Algo scan seed.

M21.21 deliberately does not add a new provider adapter. It does not add provider
signup, credential/key acquisition, secret-storage changes, paid/bulk data, live
trading, broker/exchange keys, real balances, order paths, margin, leverage, short
exposure, derivatives, optimize/live deployment, archive/prune/delete/restore
execution, installed-source reads, Fincept branding, commercial copy, or
fixture-primary runtime claims.

## M21.22 Selected Slice

M21.22 selects Karpathy cleanup/refactor for the accumulated M0-M21 surface. The
governing artifact is `docs/planning/M21_KARPATHY_CLEANUP.md`, based on
`.omx/plans/ralplan-m21-22-karpathy-cleanup-20260525.md`.

This slice is chosen because M21.21 completed a larger route workflow but left
frontend maintainability pressure in large Markets/type surfaces. The
implementation keeps product behavior unchanged while extracting Markets
source-state panels, low-churn frontend contracts, and focused regression tests.
It also hardens existing Playwright selector/wait behavior and the narrow Algo
initial-load race discovered during verification.

M21.22 deliberately does not add a provider adapter, provider expansion, new
feature, UI redesign, server/storage/agent-contract broad rewrite, credential/key
flow, secret-storage change, live trading, broker/exchange key flow, real balance,
order path, margin, leverage, short exposure, derivatives, destructive artifact
lifecycle action, installed-source read, Fincept branding, commercial copy, or
fixture-primary runtime claim.

## M21.23 Selected Slice

M21.23 selects a second bounded Karpathy cleanup/refactor pass. The governing
artifact remains `docs/planning/M21_KARPATHY_CLEANUP.md`.

This slice is chosen because M21.22 reduced Markets route complexity but
`frontend/src/types.ts` still carried provider/governance/artifact/agent-contract
and live-safety type families in the same central file. The implementation keeps
`frontend/src/types.ts` as the compatibility barrel while extracting those
low-churn route-family contracts into `frontend/src/types/governance.ts` and
`frontend/src/types/liveSafety.ts`.

M21.23 deliberately does not add a provider adapter, provider expansion, new
feature, UI redesign, backend route change, payload-field change, selector change,
credential/key flow, secret-storage change, live trading, broker/exchange key
flow, real balance, order path, margin, leverage, short exposure, derivatives,
destructive artifact lifecycle action, installed-source read, Fincept branding,
commercial copy, or fixture-primary runtime claim.
