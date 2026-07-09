# M19 Ralplan Execution Plan

This is the formal long-running plan for the next rebuild. It is planning-only and contains no product implementation.

## Planning Verdict

The current app is not blocked by missing routes. It is blocked by parity depth:

- Visual style still reads too high-contrast and sparse compared with observed low-contrast dense terminal evidence.
- Main route panels still expose `Not connected`, `offline_fixture`, demo, dry-run, and gated states as normal user-facing experience.
- Provider/data/cache architecture is not yet strong enough to support Fincept-like Dashboard, Markets, Crypto, Backtest, Portfolio, News, and analytics workflows.
- Many advanced routes exist as safe local shells, but they are not yet connected to route-specific data/artifact workflows.

The next `/goal` should therefore be a long rebuild, not a small patch.

## Engineering Plan

### Backend

1. Add a provider registry with capability metadata:
   - asset classes
   - endpoint names
   - auth mode
   - freshness TTL
   - rate-limit policy
   - local cache path
   - safety class: public-read-only, optional-local-key, paid-gated, forbidden-private-live
2. Normalize provider payloads into internal schemas:
   - quote
   - candle
   - order book
   - trade
   - company fact
   - macro series
   - news item
   - provider error
3. Add cache/provenance metadata to every data API:
   - provider
   - source URL/doc reference
   - retrieved_at
   - stale_after
   - cache_path
   - fallback_used
   - user_action_needed
4. Make Dashboard and route APIs aggregate from provider/cache/artifact contracts rather than static fallback catalogs.
5. Keep all private/live broker endpoints unreachable until the separate safety contract is complete.

### Frontend

1. Split broad M18 CSS into:
   - theme tokens
   - shell/layout tokens
   - dense table/panel components
   - route-specific component styles
2. Replace pure black/white contrast with muted dark gray terminal palette.
3. Add consistent provider freshness/status strips and route action bars.
4. Make every route visibly distinct:
   - route-specific table/panel layout
   - route-specific workflow controls
   - route-specific state and artifact outputs
5. Use explicit setup/gated cards only for missing local configuration, not as the main content.

### Data and Cache

1. Public no-key first:
   - Binance/Kraken/Coinbase for crypto market data.
   - SEC EDGAR for US company facts.
   - DBnomics for macro/economic data.
2. Optional local-key later:
   - FRED, Alpha Vantage, Twelve Data, FMP, Finnhub, Polygon/Massive, Nasdaq Data Link, NewsAPI/GDELT.
3. Cache policy:
   - write provider payload snapshots under local cache folders
   - keep provenance
   - show stale data when provider fails
   - never silently substitute test fixtures for user-visible data
4. Test fixtures:
   - live under tests only
   - generated from provider schemas
   - never presented as default runtime data except explicit offline fallback with visible source state

### Provider Implementation Entry Template

No provider adapter may be implemented until its milestone records:

- official documentation URL and retrieval date
- asset/workflow coverage
- auth mode: no-key, optional-local-key, paid-gated, or forbidden-live/private
- terms/license/display-risk note
- rate-limit or request-weight policy
- local cache path and TTL
- normalized internal schema
- provider error states
- test-only fixture plan
- source attribution shown in UI
- clean-room and safety implications

For optional-key providers, implementation is blocked until local secret storage is designed and tested. The UI may show provider capability and setup-required state before key entry exists, but it must not collect or persist a key until the secret-storage milestone is complete.

### Artifacts

Backtest, Portfolio, AI Chat, Nodes, Code, Quant Lab, and QuantLib must write/read local artifacts with manifests. Artifacts must include source provenance and safety metadata when they depend on provider data.

## Clean-Room Allowed and Forbidden Scope

Allowed:

- Read `AGENTS.md`, repo docs, repo tests, repo product code, local planning artifacts, and `docs/reference/` evidence.
- Use sanitized reference screenshots, JSON logs, captured UI behavior, and safe live installed-app observation as requirements evidence.
- Use public/official provider documentation and independently implemented adapters.
- Persist local settings, caches, artifacts, screenshots, logs, notebooks, reports, and layouts under local project/user storage.

Forbidden:

- Reading, copying, porting, adapting, or modifying `D:\FinceptTerminal\app\scripts` or installed package source/code/assets/runtime.
- Copying Fincept branding, logo, trademarks, commercial copy, assets, screenshots as product assets, or exact UI text.
- Adding subscription, billing, CR/credits, cloud-account-required flows, or commercial account surfaces.
- Creating reachable live order, private broker/exchange API key, real balance, margin, leverage, short, or derivatives execution paths before the dedicated live-safety gate is complete.
- Saving, printing, logging, screenshotting, documenting, or committing credentials, PINs, tokens, private keys, API keys, or personal account details.

## Stale-Document Correction Plan

- Treat `AGENTS.md` as the highest repo contract.
- Before implementation, scan planning/spec docs for conflicts with the local Fincept parity goal and clean-room boundaries.
- Do not use `FINCEPT_TO_CRYPTO_TRADING_HANDOFF.md` as roadmap material.
- If older documents imply `D:\Crypto-Trading` work, billing/credits, cloud-required behavior, or unrestricted live trading, update those documents before relying on them.
- Record stale-doc corrections in the milestone handoff and commit them separately from product behavior when practical.

## Milestones

### M19.0 Planning Baseline and Source Wall

Definition of Done:
- Confirm repo state and current app state.
- Add the M19 planning artifacts.
- Add or identify source-wall tests that prevent installed source/code/assets reads.
- Add or update a screenshot/reference index for the M19 comparison evidence.
- Identify stale planning/spec conflicts and schedule corrections before dependent implementation.
- Commit planning-only artifacts.

### M19.1 Theme Token and Dense Shell Repair

Definition of Done:
- Split M18 broad CSS into stable tokens/components.
- Default theme becomes muted dark gray, lower contrast, dense terminal style.
- Dashboard, Markets, Crypto, Backtest, Settings screenshots show denser panel/table hierarchy.
- No product data changes required in this milestone.
- Visual verdict does not require pixel-perfect or brand parity.
- This milestone must not expand route workflows. It prepares maintainable theme/layout primitives for M19.2+ provider and workflow work.

### M19.2 Provider Registry, Cache, and Freshness Contract

Definition of Done:
- M19.1 theme tokens and component-level style rules are complete enough that provider/freshness UI does not add another broad CSS layer.
- Backend exposes provider registry and cache state endpoints.
- UI displays provider freshness/source strip globally or per route.
- Provider errors distinguish unavailable, rate-limited, key-required, plan-required, stale-cache, and disabled-by-safety.
- Tests prove no fixture is used as primary runtime when network/provider data exists.
- Provider implementation entry template exists in code/docs and is used by every new adapter.

### M19.3 Public Crypto Data Chain

Definition of Done:
- Binance public adapter refreshes ticker/order book/klines where available.
- Kraken/Coinbase public adapters are added as fallback or alternate sources.
- Crypto and Markets no longer show `offline_fixture` as the normal state when public data is reachable.
- Cache fallback shows stale public source and timestamp.

### M19.4 Dashboard Aggregator

Definition of Done:
- Dashboard reads provider registry, crypto market pulse, watchlist, paper broker, portfolio, backtest artifacts, news/macro capability states, and local diagnostics.
- Main dashboard has no generic `Not connected` values for data that can be derived locally.
- Missing optional providers are shown as setup-required cards with useful context.

### M19.5 Markets Multi-Asset Workspace

Definition of Done:
- Markets supports route-specific panels for crypto, equities/ETFs, FX, commodities, bonds/rates, indexes, and regional groups.
- Crypto panels use live public provider data.
- Non-crypto panels use no-key public sources where implemented or optional-key setup states with provider choices.
- Watchlist, column, panel edit/delete, refresh, auto-refresh, and source states are verified in browser.

### M19.6 Crypto Workspace Depth

Definition of Done:
- Crypto route shows richer watchlist, candle chart, order book, trades, paper order ticket, positions, orders, fills, history, fees/stats/depth tabs.
- Paper orders use current provider quote snapshots and write ledger/fill artifacts.
- No real order or private API path is reachable.

### M19.7 Backtest Provider Provenance

Definition of Done:
- Backtest can run on public closed-candle provider data with cached provenance.
- Deterministic candles remain available only as tests/offline fallback.
- Artifacts include provider, cache snapshot hash, and source timestamps.
- Results tabs are richer and visually closer to reference workflow.

### M19.8 Portfolio Pricing and Artifacts

Definition of Done:
- Portfolio supports create/import/export/manual holdings.
- Holdings are priced from provider/cache where possible.
- Allocation, performance, transactions, and risk summary panels are populated from local state.
- Exports include provenance and local manifest.

### M19.9 News, Macro, and Fundamentals

Definition of Done:
- Add SEC company facts and DBnomics macro provider paths where feasible.
- Add optional local-key setup surfaces for FRED/news providers only after the local secret-storage design gate is complete.
- News route shows source-attributed headlines/items and topic/symbol filters.
- Dashboard and Markets can consume macro/fundamental/news summaries.

### M19.10 Advanced Routes Data Connection

Definition of Done:
- AI Chat can answer from local artifacts/provider cache without broker mutation.
- Nodes can run provider/cache/artifact dry-run workflows.
- Code workspace can read local datasets/artifacts and save outputs.
- Quant Lab modules consume provider/artifact inputs and write outputs.
- QuantLib calculators save results and can use provider/artifact inputs where relevant.

### M19.11 Local Governance Routes

Definition of Done:
- Settings includes provider setup, local secret status, cache controls, source-wall diagnostics, appearance tokens, storage paths, and safety gates.
- Local secret-storage design is documented and tested before any optional-key provider form can persist credentials.
- Profile is local preferences/persona/layout only.
- Forum/Help become local notes/support/research/diagnostic surfaces tied to artifacts.
- No billing/cloud/account copy or flow exists.

### M19.12 Full Parity QA and Cleanup

Definition of Done:
- All 15 routes have screenshots/evidence.
- Playwright E2E covers the 15-route workflow matrix.
- Unit/integration/source-wall/safety tests pass.
- Frontend build/lint/e2e pass.
- Visual verdict passes for representative routes.
- Code-review finds no CRITICAL/HIGH/BLOCK issues.
- Slop cleanup is limited to changed files after behavior is tested.
- Final handoff documents exact commands, URLs, artifacts, remaining risks, and commits.

## Verification Matrix

| Capability | Unit | Integration | E2E/browser | Screenshot/visual | Source-wall/safety |
| --- | --- | --- | --- | --- | --- |
| Theme/layout | token/component checks | route render smoke | browser route walkthrough | visual-verdict | no brand/assets copy |
| Provider registry | provider schema tests | API aggregation tests | settings/provider UI | provider status screenshots | no secrets/log leaks |
| Crypto data | adapter normalization | quote/orderbook/candle APIs | crypto paper workflow | crypto screenshot | no private exchange endpoints |
| Markets | panel/table state tests | refresh/cache APIs | tabs/watchlist/columns | markets screenshot | provider terms/source notes |
| Dashboard | aggregation tests | route API | dashboard refresh | dashboard screenshot | no fake balances |
| Backtest | strategy/provider/artifact tests | run API | run workflow | backtest screenshot | deterministic fixture not primary |
| Portfolio | import/export/valuation tests | route API | import/export workflow | portfolio screenshot | no real balance reads |
| Advanced routes | module/output tests | artifact APIs | route workflows | route screenshots | dangerous execution gated |

## Per-Milestone Screenshot Checklist

Every UI-affecting milestone must capture or report:

- before/after local route screenshots for changed routes
- reference screenshot(s) or evidence file(s) used for comparison
- browser or Playwright workflow evidence for at least one route-specific interaction
- visual-verdict result when layout/style/workflow parity is materially changed
- a note that screenshots contain no credentials, personal account details, billing, credits, subscription copy, private keys, tokens, or provider keys
- screenshot artifact paths in `PROJECT_STATE.md` or the milestone handoff

Planning-only or backend-only milestones may skip screenshots only if the handoff explains why there is no UI surface change.

## Hard Milestone Stop Gates

A milestone may not be committed as complete when any of these are true:

- source-wall or clean-room checks fail
- safety tests show reachable live order, private API, real balance, margin, leverage, short, or derivatives path
- provider tests show fixtures/mock/default data as normal runtime when a provider/cache path should be active
- optional-key work stores or logs secrets before the local secret-storage gate is complete
- frontend build/e2e fails for a touched UI milestone
- visual changes cannot produce readable non-overlapping screenshots on the required viewport set
- code-review returns CRITICAL, HIGH, or BLOCK findings

If a gate fails, the milestone remains incomplete. The handoff may record the blocker, but it must not claim completion.

## Fincept Live Observation Protocol

1. Launch only the installed app UI, never installed source folders.
2. Avoid billing, subscription, CR purchase, private API, real trading, account deletion, deploy, publish, or destructive actions.
3. If a view contains credentials, personal info, or billing/account details, do not save the screenshot. Delete accidental captures immediately.
4. Record observations as abstract requirements:
   - layout structure
   - control types
   - state transitions
   - data density
   - error/empty states
   - workflow sequence
5. Do not copy wording, images, logos, icons, colors exactly, or assets.
6. Store only sanitized notes and screenshot indexes.

## Local App Comparison Protocol

1. Start backend/frontend using `docs/planning/FINAL_HANDOFF.md`.
2. Open localhost in browser.
3. Capture Dashboard, Markets, Crypto, Backtest, Settings, and each changed route.
4. Compare against reference screenshots for:
   - panel density
   - route-specific controls
   - data flow
   - state/freshness clarity
   - visual contrast
   - workflow completeness
5. Write route gap notes before editing.
6. Use Playwright for repeatable E2E and browser for manual interaction.

## Anti-Empty-Shell Plan

- Replace generic `Not connected` with structured states:
  - public data active
  - stale cache active
  - setup required
  - plan/key required
  - disabled by safety
  - unavailable with error
- Every route must have at least one meaningful local workflow before it can be called complete.
- Every data panel must show source and timestamp or a precise reason it cannot.
- Demo/sample rows cannot be the default main runtime state.
- Fixtures must be test-only or explicit offline fallback, with visible labeling.

## Route-by-Route Acceptance Checklist

Each route is incomplete until all route-specific items below are true:

| Route | Acceptance condition |
| --- | --- |
| Dashboard | At least five populated panels derive from provider/cache/local artifacts, and the freshness strip explains every missing optional provider. |
| Markets | Every asset tab has either real provider data or a concrete provider setup path; crypto uses public provider data, not a fixture, when reachable. |
| Crypto | Quote, order book, candles/trades, paper ticket, positions, orders, fills, and history all update from provider-backed paper runtime state. |
| Portfolio | Manual/imported holdings are locally persisted, priced from provider/cache where available, and export with provenance. |
| News | News items are source-attributed and filterable; key-gated sources show setup state, not placeholder content. |
| AI Chat | Responses can reference local artifacts/provider cache and cannot mutate broker/ledger state. |
| Backtest | Runs can use provider-backed closed candles and artifacts include provider/cache provenance. |
| Algo | Scans consume provider/cache data and output dry-run explanations with no live-order action. |
| Nodes | A saved dry-run graph consumes provider/cache/artifact nodes and writes a local output. |
| Code | A safe local snippet/notebook can read provider/artifact data and save output. |
| Quant Lab | At least one module per priority group produces a local output from provider/artifact input. |
| QuantLib | Calculators save results and show input/output provenance when using market/artifact data. |
| Forum | Local notes/issues can link to route artifacts and be exported/read back. |
| Settings | Provider setup, cache, theme, source-wall, safety, and local secret status are inspectable without exposing secrets. |
| Profile | Local preferences/layout/persona persist without cloud, billing, or account identity dependencies. |

## Visual Style Repair Plan

- Move from pure black/white contrast to muted dark gray surfaces.
- Use compact top bars, command/status strips, dense tables, thin panel borders, and stable pane grids.
- Keep accents restrained and stateful: active, success, warning, danger, info.
- Avoid landing-page/card-heavy design, hero sections, decorative gradients, or oversized typography.
- Make typography hierarchy small and terminal-like, with readable spacing and no overlap.
- Use visual-verdict against reference screenshots for style/workflow parity, not pixel or brand parity.

## Live-Trading and Credential Safety Gate

No live trading implementation may start until all exist:

- Dedicated safety contract document.
- Local secret storage design and tests.
- Explicit live-mode opt-in UX.
- Confirmation gates for every live side effect.
- Audit log and kill switch.
- Paper/live isolation tests.
- Source-wall, code-review, and security-review pass.
- User explicitly authorizes moving from disabled/gated UI to implementation.

Until then:

- Broker/private exchange API surfaces are disabled or paper/dry-run only.
- API keys for data providers are optional local secrets only.
- Real balances and real orders are not read or submitted.
- Margin, leverage, short, and derivatives execution remain unreachable.

## Architect Review Entry Checklist

Before starting implementation from this plan, the execution owner should verify:

- provider/cache/freshness contracts are implemented before route clusters depend on them
- M19.1 style work is limited to tokens/components and does not become another broad one-off CSS layer
- optional-key provider work cannot begin before local secret storage is designed, tested, and reviewed
- route clusters have disjoint enough write scopes before any team/parallel execution is used
- every route DoD has data/state/workflow acceptance, not only screenshot acceptance
- source-wall and safety gates are part of every milestone, not only final QA

## Commit and Handoff Policy

- Each milestone gets one focused commit unless a larger milestone requires several reviewable commits.
- Use the Lore commit protocol from `AGENTS.md`.
- Include:
  - `Tested: ...`
  - `Not-tested: ...`
  - `Co-authored-by: OmX <omx@oh-my-codex.dev>`
- Update `PROJECT_STATE.md` or an equivalent handoff file after each milestone.
- Do not commit screenshots if they are ignored or contain sensitive info.
- Do not commit credentials, local secrets, provider keys, or personal account details.

## Consensus Notes

The consensus path for implementation should be:

1. Repair the style system enough that later route work does not inherit the high-contrast shell.
2. Build provider/cache/freshness primitives before adding more route-specific widgets.
3. Prove the primitives on Dashboard, Markets, Crypto, Backtest, and Portfolio.
4. Connect advanced routes to provider/cache/artifact flows.
5. Run full visual, workflow, source-wall, and safety QA.
