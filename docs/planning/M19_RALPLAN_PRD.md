# M19 PRD: Local Fincept Parity Rebuild

## Product Goal

Build a local self-use financial terminal with clean-room functional, workflow, and visual style parity to the observed Fincept Terminal experience across all 15 entries:

Dashboard, Markets, Crypto, Portfolio, News, AI Chat, Backtest, Algo, Nodes, Code, Quant Lab, QuantLib, Forum, Settings, Profile.

The goal is not another route shell pass. The product must feel like a working terminal: route-specific data, local state, artifacts, provider provenance, and workflows must visibly change as the user interacts with the app.

## Non-Goals

- No Fincept branding, logo, trademarks, commercial copy, assets, code, runtime, or installed implementation source.
- No subscription, billing, CR/credits, or cloud account requirement.
- No reachable live order path, private broker/exchange API key flow, real balance read, margin, leverage, short exposure, or derivatives execution before a dedicated safety contract is implemented and reviewed.
- No user-visible primary experience that depends on mock/default/offline fixtures.
- No D:\Crypto-Trading roadmap contamination.

## User Problems To Solve

1. The local app currently looks too high-contrast and unlike the observed terminal.
2. The local app often feels empty because important panels say `Not connected`, `offline_fixture`, demo, dry-run, or gated without enough real equivalent behavior.
3. Route changes often feel like renaming the same surface rather than entering distinct workspaces.
4. Public no-key data limitations have been used too passively; the app needs a proactive provider strategy with local opt-in keys where appropriate.
5. Safety gating is necessary, but the gated surfaces need useful local substitutes.

## Product Principles

- Evidence first: every route milestone starts from reference screenshots/logs/specs or safe live observation.
- Real data by default: prefer public read-only data, then optional local-key providers, then explicit gated states. Fixtures are for tests/offline fallback only.
- Low-contrast dense terminal style: compact tables/panels, muted dark grays, restrained accent states, high information density, and readable contrast.
- Local-first artifacts: settings, layouts, logs, reports, backtests, caches, and screenshots stay local by default.
- Safety surfaces are useful: disabled live trading does not mean blank screens; it means paper/dry-run/local equivalents with explicit boundaries.

## Core Product Requirements

### Shell and Style

- Global menus, route rail, command/status strip, provider freshness strip, and route-specific action toolbar.
- Low-contrast dark gray theme inspired by observed terminal density, not pure black/white.
- Dense tables and panels with stable dimensions, readable hierarchy, and compact controls.
- All route screenshots must be visually comparable to reference evidence at the workflow/layout level.

### Data and Providers

- Provider registry with capabilities, auth mode, rate limits, local cache policy, source attribution, and health.
- Public no-key adapters first: crypto market data, SEC fundamentals, DBnomics macro where feasible.
- Optional local-key adapters later: FRED, Alpha Vantage, Twelve Data, FMP, Finnhub, Polygon/Massive, Nasdaq Data Link, NewsAPI/GDELT.
- Secrets stay in a local secret store, never in repo, logs, screenshots, docs, or commit messages.
- Provider failures show stale cache, source, last successful fetch, retry, and fallback. They do not collapse into generic empty panels.

### Artifacts and State

- Backtests write reproducible artifacts with provider provenance.
- Portfolio import/export writes local artifacts and reads provider prices where available.
- AI Chat, Code, Nodes, Quant Lab, and QuantLib can read local artifacts/provider cache safely.
- Dashboard aggregates state from providers, paper broker, portfolio, backtests, news, and local diagnostics.

### Route Requirements

- Dashboard: public market pulse, local portfolio/paper broker state, news, macro calendar/series, watchlist, freshness diagnostics.
- Markets: multi-asset tabs/panels with provider/gated states, watchlists, columns, refresh, cache, and non-crypto provider path.
- Crypto: provider-backed quotes/order book/candles/trades, paper ticket, positions/orders/fills/history, ledger safety.
- Portfolio: create/import/export/manual holdings, valuation with provider prices, allocation/performance.
- News: source-attributed feed, filters/search/topics/saved metadata.
- AI Chat: local artifact and provider-cache context, safe dry-run; optional external LLM only after local secret gate.
- Backtest: real closed-candle provider path, strategy templates, run/optimize/walk-forward artifacts.
- Algo: provider-backed scans, dry-run signal explanations, backtest handoff, no live execution.
- Nodes: provider/cache/artifact nodes, local dry-run execution, saved graphs.
- Code: local notebooks/scripts, safe execution, provider/artifact browser.
- Quant Lab: module outputs backed by provider/cache/artifacts.
- QuantLib: calculator suite with saved outputs and route handoff.
- Forum: local notes/issue/research log tied to artifacts and routes.
- Settings: provider setup, cache, storage, appearance, key/security status, source-wall diagnostics.
- Profile: local persona/layout/preferences, no cloud account or billing identity.

## Success Metrics

- All 15 routes have route-specific backend data and at least one verified workflow.
- Dashboard, Markets, Crypto, Backtest, and Portfolio no longer present fixtures as the normal runtime path.
- Provider health/freshness is visible and accurate on data routes.
- Visual verdict passes for representative routes against reference screenshots with style/workflow parity, not pixel or brand parity.
- Playwright E2E tests prove route navigation, provider status, state mutation, artifact creation, and paper/live isolation.

## Risks

- Provider licensing and rate limits may constrain default non-crypto data.
- Optional-key providers can create secret-handling risks if implemented before the secret contract.
- Broad CSS changes can regress readability and maintainability.
- Live observation can land on sensitive account/billing surfaces; any such screenshots must be deleted and not documented beyond sanitized safety notes.
