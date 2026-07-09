# M19 Route-by-Route Parity Gap Report

This is a planning gap model for the next long-running implementation goal. It is based on current repo state, existing reference evidence, local screenshots captured under `artifacts/screenshots/m19-planning/`, and safe live-app observation. It does not copy Fincept code, assets, branding, or commercial copy.

## Evidence Index

Reference evidence:
- `docs/reference/fincept-platform-test/LOCAL_TERMINAL_PRODUCT_SPEC.md`
- `docs/reference/fincept-platform-test/LOCAL_TERMINAL_ENGINEERING_SPEC.md`
- `docs/reference/fincept-platform-test/LOCAL_VERSION_IMPLEMENTATION_BACKLOG.md`
- `docs/reference/fincept-platform-test/FEATURE_MATRIX.md`
- `docs/reference/fincept-platform-test/EVIDENCE_INDEX.md`
- `docs/reference/fincept-platform-test/screenshots/`
- `D:\FinceptTerminal\screenshots\dashboard.png`
- `D:\FinceptTerminal\screenshots\markets.png`
- `D:\FinceptTerminal\screenshots\crypto.png`
- `D:\FinceptTerminal\screenshots\backtest.png`
- `D:\FinceptTerminal\screenshots\backtest-ui-run-btc-sma-12-48.png`

Current local planning screenshots:
- `artifacts/screenshots/m19-planning/local-dashboard.png`
- `artifacts/screenshots/m19-planning/local-markets.png`
- `artifacts/screenshots/m19-planning/local-crypto.png`

Live observation safety note:
- The installed app launched successfully, but the first live surface contained sensitive account/billing-like information. The temporary screenshot was deleted. No sensitive details are retained in this report.

## Cross-Cutting Gap Themes

1. Visual style is still too high contrast and sparse. Fincept evidence reads as low-contrast dark gray terminal with dense panels, muted borders, compact table rows, and restrained accent color. The local app reads more like black/white route cards.
2. Route parity is broad but shallow. All 15 entries exist, but many routes expose static/local catalogs instead of active route-specific workflows.
3. User-visible runtime data still falls back to `Not connected`, `offline_fixture`, demo, or gated states too often.
4. Frontend and backend contracts exist, but many UI panels do not show route-specific source freshness, provenance, cache state, and interaction results.
5. Provider strategy is incomplete. Crypto has a first public adapter; stocks/ETF/FX/commodities/news/macro/fundamentals are not yet connected to a real provider plan.
6. Safety boundaries are correctly conservative, but disabled/gated states need better user-facing equivalents so the product does not feel empty.

## Route Gap Model

| Route | Fincept-observed target | Current local gap | Next parity target |
| --- | --- | --- | --- |
| Dashboard | Dense terminal dashboard with indices, performance/risk, market pulse, watchlist, news, economic calendar, live/status strips, command bar | Visible `Not connected` and public-data-not-connected states; sparse widgets | Build provider-backed dashboard aggregator: crypto market pulse, macro calendar, watchlist, local portfolio summary, paper broker summary, news headlines, freshness/source strip |
| Markets | Multi-asset panel grid with stocks, indices, FX, commodities, bonds, ETFs, crypto, regional tables, refresh/auto-refresh/columns/edit/delete | Crypto-only public path; non-crypto tabs gated; offline fixture visible | Provider registry plus no-key crypto and key-gated multi-asset providers; all tabs show real provider/gated capability rows, not placeholders |
| Crypto | Watchlist, chart, order book, order ticket, exchange selector, positions/orders/history/fills/depth/stats tabs | Paper broker exists; data often reports offline fixture; chart and depth are sparse | Multi-provider public crypto data chain, richer order book/trade feed, candle chart, paper fills tied to live public quote snapshots and local ledger |
| Portfolio | Portfolio workspace with holdings, allocation, performance, import/export, account-like local views | Demo/sample local data only; no market pricing integration | Local portfolio engine with CSV import, manual holdings, provider-priced valuation, allocation/performance charts, export artifacts |
| News | Market/news feed panels with categories and search/filter behavior | Offline/public RSS-like fallback only | Provider-backed news route with source attribution, search, tickers/topics, saved local articles metadata, no full-copy article scraping |
| AI Chat | Chat workspace with sessions and provider status | Local dry-run only; safe but feels disconnected | Local assistant can answer from local artifacts, provider cache, docs, and route state; external LLM optional key-gated later |
| Backtest | Provider tabs, strategy/input panel, run/optimize/walk-forward commands, results artifacts | Works but deterministic local candles; provider parity missing | Public closed-candle provider integration, provider provenance in artifacts, strategy templates, richer result tabs |
| Algo | Scanner/strategy workflow linked to market data and backtest | Dry-run scanner depends on stale/public cache, offline fixture non-actionable | Use real provider cache, route-specific scans, alerts, backtest handoff, no live-order reachability |
| Nodes | Visual/local workflow templates for data and analysis | Dry-run/local templates | Make workflows consume provider/cache/artifact nodes; execution stays dry-run/local with provenance |
| Code | Local notebook/workspace with artifacts | Local-only workspace exists | Add data-provider snippets, artifact browser, route-aware read-only datasets, safe execution gates |
| Quant Lab | 24-module catalog and subpages | Catalog/preview surfaces exist; many modules are preview-only | Connect modules to provider cache/artifacts and produce local outputs, keeping dangerous execution gated |
| QuantLib | Calculator suite and examples | Local deterministic calculators exist | Expand input/output density, examples, saved calculations, comparison to provider/artifact data where relevant |
| Forum | Local-only notes/support/community equivalent | Local forum/support surfaces exist | Improve as local research notebook and issue log tied to routes/artifacts, no cloud/community dependency |
| Settings | Data sources, credentials, appearance, security, storage/cache, LLM/MCP/python env surfaces | Settings exist but provider setup is not complete | Add local provider registry UI, secret storage status, source-wall policy, cache controls, low-contrast theme controls |
| Profile | Local profile/account-like settings | Local profile exists; must avoid cloud/billing identity | Profile becomes local persona/layout/workspace preferences, no cloud/account/billing copy |

## Priority Gap Order

1. Theme/layout system: remove high-contrast pure black/white and set dense low-contrast terminal tokens.
2. Provider/cache/freshness core: stop exposing generic `Not connected` as the normal state.
3. Dashboard/Markets/Crypto: first routes to prove live provider data and state flow.
4. Backtest/Portfolio: first routes to prove data/artifact flow.
5. News/AI/Algo/Nodes/Code/Quant Lab/QuantLib: connect to provider/cache/artifact primitives instead of standalone shells.
6. Settings/Profile/Forum/Help: make local-first governance, provider setup, and diagnostics clear.

## Exit Criteria For This Gap Class

- No route's main panel is a route-name-only shell.
- No route's main user-visible state depends on offline fixtures when network/provider data is available.
- Any gated state names the missing local setup step, provider/source, risk reason, and fallback behavior.
- Route screenshots show dense, low-contrast terminal panels comparable in structure to reference evidence without copying branding/assets/copy.
- Playwright route workflows prove that backend state changes are reflected in route-specific UI.
