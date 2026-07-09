# M19 Screenshot and Observation Index

This index records comparison evidence for the planning phase. It is not a product asset manifest.

## Safe Reference Evidence

| Evidence | Path | Use |
| --- | --- | --- |
| Reference dashboard | `D:\FinceptTerminal\screenshots\dashboard.png` | Low-contrast dense dashboard layout, menu/status/ticker/panel structure |
| Reference markets | `D:\FinceptTerminal\screenshots\markets.png` | Multi-asset table density, panel grid, refresh/action controls |
| Reference crypto | `D:\FinceptTerminal\screenshots\crypto.png` | Watchlist/chart/order-book/order-ticket workspace layout |
| Reference backtest | `D:\FinceptTerminal\screenshots\backtest.png` | Provider tabs, command panel, strategy inputs, results area |
| Reference backtest run | `D:\FinceptTerminal\screenshots\backtest-ui-run-btc-sma-12-48.png` | Backtest run result workflow |
| Reference route screenshots | `docs/reference/fincept-platform-test/screenshots/` | Route and subfeature workflow evidence |
| Reference JSON logs | `docs/reference/fincept-platform-test/evidence/` | Navigation, menu, flow, and subfeature inventories |

## Local Baseline Screenshots Captured For M19 Planning

| Evidence | Path | Planning observation |
| --- | --- | --- |
| Local dashboard | `artifacts/screenshots/m19-planning/local-dashboard.png` | High-contrast shell, sparse panels, visible `Not connected` states |
| Local markets | `artifacts/screenshots/m19-planning/local-markets.png` | Offline fixture state, crypto-only data path, non-crypto gated panels |
| Local crypto | `artifacts/screenshots/m19-planning/local-crypto.png` | Paper broker surface exists, but chart/data density and provider state lag reference |

## M19 Route Evidence

These screenshots are ignored local artifacts, not committed product assets. They are safe local evidence for route workflow/style review and contain no credentials, tokens, provider keys, billing, credits, subscription copy, or personal account details.

| Route | Evidence screenshot | Workflow covered |
| --- | --- | --- |
| Dashboard | `artifacts/screenshots/m3-dashboard-e2e.png`; `artifacts/screenshots/m19-4-dashboard-aggregator.png` | provider/cache/local artifact dashboard aggregation |
| Markets | `artifacts/screenshots/m4-markets-e2e.png`; `artifacts/screenshots/m19-5-markets-provider-expansion.png` | watchlist, asset tabs, public crypto provider/cache state |
| Crypto | `artifacts/screenshots/m5-crypto-paper-e2e.png`; `artifacts/screenshots/m19-6-crypto-workspace-depth.png` | provider-backed quote/depth/candles and paper order workflow |
| Portfolio | `artifacts/screenshots/m7-portfolio-e2e.png`; `artifacts/screenshots/m19-8-portfolio-provider-pricing.png` | local portfolio import/export and provider pricing provenance |
| News | `artifacts/screenshots/m8-news-e2e.png`; `artifacts/screenshots/m19-9-news-macro-fundamentals.png` | public RSS, SEC fundamentals, DBnomics macro cache surfaces |
| AI Chat | `artifacts/screenshots/m9-ai-chat-e2e.png` | local sessions, artifact links, provider/cache context |
| Backtest | `artifacts/screenshots/m6-backtest-e2e.png`; `artifacts/screenshots/m19-7-backtest-provider-provenance.png` | closed-candle run, provider/cache provenance, artifacts |
| Algo | `artifacts/screenshots/m10-algo-e2e.png` | local strategy builder, backtest handoff, dry-run scanner |
| Nodes | `artifacts/screenshots/m11-nodes-e2e.png` | template, import/export, provider-context dry run |
| Code | `artifacts/screenshots/m12-code-e2e.png` | local notebook edit/import/export and provider context notebook |
| Quant Lab | `artifacts/screenshots/m13-quant-lab-e2e.png` | local module preview artifacts and gated execution |
| QuantLib | `artifacts/screenshots/m14-quantlib-e2e.png` | local calculator request/response/report artifacts |
| Forum | `artifacts/screenshots/m15-forum-help-e2e.png`; `artifacts/screenshots/m19-11-forum-help-governance.png` | local journal, replies, artifact links, help governance |
| Settings | `artifacts/screenshots/m19-11-settings-governance.png`; `artifacts/screenshots/m16-live-safety-e2e.png` | provider setup, cache controls, source-wall, local secret status, safety gates |
| Profile | `artifacts/screenshots/m19-11-profile-governance.png` | local persona/preferences and no cloud/billing/private identity dependency |

## Post-M19 Provider Evidence

| Milestone | Evidence screenshot | Workflow covered |
| --- | --- | --- |
| M20.1 Treasury rates provider | `artifacts/screenshots/m20-1-markets-rates-provider.png` | Markets Bonds/Rates tab, public no-key Treasury refresh, provider freshness, local cache/source attribution, and populated yield curve rows |
| M20.2 ECB FX reference provider | `artifacts/screenshots/m20-2-markets-fx-provider.png` | Markets FX tab, public no-key ECB reference-rate refresh, provider freshness sync, local cache/source attribution, and populated EUR-base reference-rate rows |
| M20.3 World Bank commodities provider | `artifacts/screenshots/m20-3-markets-commodities-provider.png` | Markets Commodities tab, public no-key World Bank Pink Sheet refresh, provider freshness sync, local cache/source attribution, and populated monthly reference rows |
| M20.4 SEC stocks fundamentals | `artifacts/screenshots/m20-4-markets-stocks-fundamentals.png` | Markets Stocks tab, public no-key SEC companyfacts refresh/cache, company/fact tables, source attribution, and quote-provider safety gate |
| M21.13 SEC company ticker registry | `artifacts/screenshots/m21-sec-company-ticker-registry-stocks.png` | Markets Stocks tab, public no-key SEC company ticker registry cache, issuer rows, fundamentals, Provider Stack, Source Contract, and optional-key quote gate |
| M21.16 SEC company submissions | `artifacts/screenshots/m21-sec-company-submissions-stocks.png` | Markets Stocks tab, public no-key SEC recent filing metadata, Recent Filings panel, Provider Stack, Source Contract, and optional-key quote gate |
| M21.18 Stock status lanes | `artifacts/screenshots/m21-stock-status-lanes.png` | Markets Stocks tab, Stock Status Lanes panel, `stock_lanes_available` gateway state, Provider Stack lane rows, Source Contract lane counts, and optional-key quote gate |
| M21.19 SEC filings watchlist | `artifacts/screenshots/m21-stock-filings-watchlist.png` | Markets Stocks tab, SEC Recent Filings watchlist rows for bounded symbols, symbol column, Stock Status Lanes filing summary, Provider Stack, Source Contract, and optional-key quote gate |
| M20.5 DBnomics index/regional macro context | `artifacts/screenshots/m20-5-markets-index-regional-macro.png` | Markets Regional and Indexes tabs, public no-key DBnomics macro cache, macro series/context/source panels, source attribution, and quote-provider safety gate |
| M20.6 SEC fund ticker registry | `artifacts/screenshots/m20-6-markets-etf-fund-registry.png` | Markets ETF tab, public no-key SEC fund ticker registry refresh/cache, CIK/series/class/ticker rows, source attribution, and quote-provider safety gate |
| M20.7 local secret gate contract | `artifacts/screenshots/m20-7-settings-secret-gate.png` | Settings Local Secret Status panel, `contract_ready_disabled`, redaction policy version, blocked optional-key provider count, and disabled persistence gate |
| M20.8 Backtest strategy catalog | `artifacts/screenshots/m20-8-backtest-strategy-catalog.png` | Backtest Strategy Catalog panel, Channel Breakout selection, local closed-candle run, artifacts/provenance tabs, and no same-candle fill guard |
| M20.9 Algo backtest strategy handoff | `artifacts/screenshots/m20-9-algo-backtest-strategy-handoff.png` | Algo Backtest Strategy selector, Channel Breakout saved strategy handoff, Backtest artifacts, dry-run Scanner, and signal-only safety status |
| M20.10 strategy parameter schema | `artifacts/screenshots/m20-10-backtest-strategy-parameter-schema.png`; `artifacts/screenshots/m20-10-algo-strategy-parameter-schema.png` | Backtest and Algo schema-driven strategy parameter labels/defaults/bounds, validation constraint, artifact contract, and local closed-candle safety context |
| M21.14 Algo provider cache scan | `artifacts/screenshots/m21-algo-provider-cache-scan.png` | Algo Scanner tab, provider/cache source contract, local scan artifact links, signal-only rows, and no-live-action state |
| M21.15 Algo scan artifact lifecycle | `artifacts/screenshots/m21-algo-scan-artifact-lifecycle.png` | Algo Scanner tab, latest scan artifact health, complete expected-file mirror, non-destructive repair action, and no-live-action state |
| M20.11 Backtest indicator/signals/returns artifacts | `artifacts/screenshots/m20-11-backtest-indicator-signals-returns.png` | Backtest Indicators, Signals, Returns Analysis tabs, new artifact files, and closed-candle result inspection |
| M20.12 Portfolio Backtest context | `artifacts/screenshots/m20-12-portfolio-backtest-context.png` | Portfolio Backtest tab, linked Backtest signal/indicator/returns artifacts, read-only local context, and cross-route artifact provenance |
| M20.13 Portfolio report/risk workflow | `artifacts/screenshots/m20-13-portfolio-report-risk.png` | Portfolio Performance/Risk/Report workflow, local report artifacts, and safe toolbar routing |
| M20.14 AI Chat local context brief | `artifacts/screenshots/m20-14-ai-chat-context-brief.png` | AI Chat local context brief, focused provider/cache source summary, linked artifact metadata, and context artifact index |
| M20.15 Nodes dry-run output bundle | `artifacts/screenshots/m20-15-nodes-dry-run-output.png` | Nodes provider-context dry-run output summary, local report/manifest artifacts, and disabled deploy/execute safety |
| M20.16 Code static analysis artifacts | `artifacts/screenshots/m20-16-code-analysis-artifacts.png` | Code notebook static analysis workflow, local analysis/report/manifest artifacts, provider context, and disabled run safety |
| M20.17 Quant Lab context bundle | `artifacts/screenshots/m20-17-quant-lab-context-bundle.png` | Quant Lab safe preview bundle, provider/cache source provenance, local artifact inputs, context/manifest artifacts, and gated runtime safety |
| M20.18 QuantLib provenance bundle | `artifacts/screenshots/m20-18-quantlib-provenance-bundle.png` | QuantLib deterministic calculator result, provider/cache source provenance, local artifact inputs, context/manifest artifacts, and gated external runtime/API safety |
| M20.19 Forum artifact health | `artifacts/screenshots/m20-19-forum-artifact-health.png` | Forum local research thread artifact health, non-destructive repair action, missing/orphan counts, and cloud/community safety disabled |
| M20.20 Settings governance diagnostics | `artifacts/screenshots/m20-20-settings-governance-diagnostics.png` | Settings read-only governance diagnostics action, local `gov-*` artifact bundle path, manifest path, source-wall verification, and cache/secret safety disabled |
| M20.21 Profile local usage stats | `artifacts/screenshots/m20-21-profile-local-usage-stats.png` | Profile local build channel, artifact-root usage stats, latest activity, billing/credits disabled state, and content-read safety |
| M20.22 global public provider refresh | `artifacts/screenshots/m20-22-provider-refresh-public.png` | Provider Freshness global no-key refresh action, local `provider-refresh-*` artifact path, active/unavailable/gated provider states, and disabled optional-key/live/private paths |
| M20.23 provider refresh job | `artifacts/screenshots/m20-23-provider-refresh-job.png` | Provider Freshness manual job start/poll/completion flow, local `job_status.json`/refresh artifact path, refreshed public no-key source summary, and disabled optional-key/live/private paths |
| M20.24 local secret store enablement | `artifacts/screenshots/m20-24-settings-local-secret-store.png` | Settings Local Secret Status panel, `local_secret_store_ready`, eligible/stored/blocked optional providers, local-only opt-in form, API value reads disabled, and paid/live/private provider blocks |
| M20.25 FRED optional-key provider | `artifacts/screenshots/m20-25-fred-optional-provider.png` | Markets/News FRED action surface, optional-key `key_required` or cached macro state, source/cache attribution, no visible key material, and paid/live/private provider blocks |
| M20.26 Alpha Vantage optional stock quote | `artifacts/screenshots/m20-26-alpha-vantage-stock-quote.png` | Markets Stocks `QUOTE` action surface, optional-key `key_required` or cached `AAPL` quote state, source/cache attribution, no visible key material, and paid/live/private provider blocks |
| M20.27 Alpha Vantage optional ETF quote | `artifacts/screenshots/m20-27-alpha-vantage-etf-quote.png` | Markets ETF `ETF QTE` action surface, optional-key `key_required` or cached `SPY` quote state, SEC fund registry separation, source/cache attribution, no visible key material, and paid/live/private provider blocks |
| M21.2 News intel strip | `artifacts/screenshots/m21-news-intel-strip.png` | News FEEDS/ARTS/CLST/SRCS/SENT/WATCHES strip, GDELT DOC provider state, metadata-only selected item fields, and no full-article-copy safety |
| M21.3 EIA energy context | `artifacts/screenshots/m21-eia-energy-context.png` | Markets Commodities `ENERGY` action surface, optional-key EIA `key_required` or cached WTI/Brent/Henry Hub context, source/cache attribution, no visible key material, and live/private trading blocks |
| M21.4 Agent operability contract | `artifacts/screenshots/m21-agent-operability-settings.png` | Settings Agent Operability panel, read-only agent contract mode, route/action/selector counts, advanced workflow action rows, and no secret/live/destructive actions |
| M21.5 Provider refresh lifecycle | `artifacts/screenshots/m21-provider-refresh-lifecycle-settings.png` | Settings Provider Refresh Lifecycle panel, read-only lifecycle mode, stale interrupted/recovery counts, non-mutating status writes, Provider Freshness lifecycle summary, and no secret/live/destructive actions |
| M21.17 Provider refresh result semantics | `artifacts/screenshots/m21-provider-refresh-result-semantics.png` | Provider Freshness manual refresh summary showing separate written, available, and reused cache counts, public no-key refresh artifact path, and disabled optional-key/live/private paths |
| M21.6 Alpha Vantage quote watchlists | `artifacts/screenshots/m21-alpha-vantage-watchlist-stocks.png`; `artifacts/screenshots/m21-alpha-vantage-watchlist-etf.png` | Markets Stocks and ETF Alpha Vantage watchlist panels, `AAPL/MSFT/NVDA` and `SPY/QQQ/IWM` optional-key quote gates, cache/state/source rows, no visible key material, and no live/private trading controls |

## Live Observation Safety Note

The installed app was launched for safe UI observation. It opened to a sensitive account/billing-like surface, so the temporary screenshot was deleted and is not referenced as evidence. Future live observation must avoid saving screenshots that include personal account details, credentials, billing, credits, subscription, or other sensitive/commercial surfaces.

For M21.19, the installed app was launched again for sanitized observation only.
The retained evidence is count-only (`window_present=true`, `button_count=4`,
`table_count=1`) with no raw UI text, screenshots, credentials, account data,
billing/subscription copy, or personal data recorded.

## Future Screenshot Requirements

- Capture the local route after every visual/workflow milestone.
- Prefer ignored `artifacts/screenshots/...` paths unless a sanitized screenshot is intentionally approved for docs.
- Never commit screenshots containing personal info, account identifiers, credentials, tokens, billing, credits, subscription, or commercial copy.
- Use visual-verdict for layout/workflow/style parity, not pixel-perfect or brand parity.
