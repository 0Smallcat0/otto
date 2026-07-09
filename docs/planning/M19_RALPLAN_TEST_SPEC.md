# M19 Test Spec

This test spec is for the next long-running implementation goal. It assumes the implementation will be staged by milestone and will run verification after each milestone.

## Test Layers

| Layer | Purpose | Required examples |
| --- | --- | --- |
| Unit tests | Lock provider/cache/domain contracts | Provider payload normalization, freshness math, cache TTL, disabled provider states, paper ledger invariants |
| Integration tests | Prove backend endpoints use real provider/cache/state flow | Dashboard aggregation, Markets provider registry, Crypto quote/orderbook/candle chain, Backtest provider provenance, Portfolio valuation |
| Source-wall tests | Prevent clean-room boundary drift | No references to `D:\FinceptTerminal\app\scripts`, no installed source path reads, no copied assets, no secrets in tracked docs/code |
| Safety tests | Keep live/private functions unreachable | Private API key path disabled unless safety contract exists; no real order/balance/margin/leverage/short/derivatives endpoints reachable |
| Frontend component tests | Prove route-specific rendering and disabled/gated clarity | Freshness strips, provider cards, route action toolbars, low-contrast theme tokens |
| Playwright E2E | Prove local browser workflows | 15-route navigation, Dashboard refresh, Markets refresh/tabs, Crypto paper order, Backtest run, Portfolio import/export, Settings provider setup disabled state |
| Browser screenshots | Human visual evidence | Representative before/after screenshots for key routes each milestone |
| Visual verdict | Compare style/workflow parity | Dashboard, Markets, Crypto, Backtest, Settings, and one dense advanced route per visual milestone |
| Provider tests | Prove adapter behavior without leaking keys | Network-disabled contract fixtures, optional live public-data smoke tests, local cache fallback tests |
| Artifact tests | Prove local outputs | Backtest files, portfolio exports, chat logs, node graph saves, code notebooks, quant outputs |

## Required Commands

Run after every milestone unless the milestone is explicitly docs-only:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
git diff --check
```

If frontend exists or was touched:

```powershell
npm run build
npm run lint
npm run test:e2e
```

Use actual repo package scripts if names differ.

## Provider Test Contract

Every provider adapter must have:

- `capabilities`: asset classes, endpoints, auth mode, live/private status.
- `fetch`: network path isolated behind an adapter interface.
- `normalize`: deterministic internal schema.
- `cache`: local JSON cache with provenance and TTL.
- `fixture`: test-only payloads that do not appear as primary runtime data.
- `error_state`: rate-limited, auth-required, plan-required, unavailable, stale-cache.
- `source_attribution`: provider name, URL/doc reference, retrieved time.
- `terms_gate`: official docs URL, retrieval date, rate-limit policy, license/display-risk note, and implementation approval status.
- `secret_gate`: optional-key providers cannot persist credentials until local secret-storage tests pass.

## Route E2E Minimums

| Route | Minimum E2E |
| --- | --- |
| Dashboard | Load route, refresh aggregator, verify provider freshness and at least 5 populated panels |
| Markets | Switch asset tabs, refresh crypto/no-key provider, verify non-crypto provider state is key-gated not placeholder |
| Crypto | Load public quote/order book/candles, submit paper order, verify orders/fills/positions/history update |
| Portfolio | Create manual portfolio, import CSV, price holdings from provider/cache, export artifact |
| News | Fetch provider/source-attributed feed or key-gated setup state, filter by topic/symbol |
| AI Chat | Ask local artifact/provider-cache question, verify safe local response and no broker mutation |
| Backtest | Run strategy on provider-backed closed candles, verify artifacts and provenance |
| Algo | Run scan from provider cache, verify explanations and no live order action |
| Nodes | Run dry-run provider/cache graph, verify saved graph and output artifact |
| Code | Open workspace, run safe snippet against local artifact/provider cache, verify output saved |
| Quant Lab | Execute one local module using provider/artifact input, verify output |
| QuantLib | Run calculator, save result, verify route state |
| Forum | Create local note/issue linked to route artifact, export/read back |
| Settings | Toggle theme/layout/cache settings and verify persistence; provider secret setup remains local/gated |
| Profile | Edit local profile/preferences and verify no cloud/billing/account dependency |

## Visual Acceptance

Visual checks should reject:

- Pure black/white high-contrast theme as the default.
- Sparse route cards where Fincept evidence shows dense panels/tables.
- Hero/marketing layouts.
- Placeholder or route-name-only main content.
- Text overflow, overlapping controls, unstable panel dimensions, and hidden route controls.

Visual checks should accept:

- Muted dark gray surfaces with readable but lower contrast.
- Compact data tables and pane grids.
- Route-specific action bars and status/freshness strips.
- Clear disabled/gated controls with useful local equivalents.

## Source-Wall Verification

Add or maintain tests that assert:

- No executable product code references `D:\FinceptTerminal\app\scripts`.
- No tracked file embeds user credentials, PINs, API keys, tokens, or private keys.
- No Fincept images/assets/logos are copied into product assets.
- Reference evidence paths are read only from docs/evidence planning surfaces, not product runtime.

## Milestone Gate

Before any milestone commit:

1. Run applicable tests and fix failures.
2. Capture browser/playwright evidence for changed workflows.
3. Run code review and fix CRITICAL/HIGH/BLOCK findings.
4. Update `PROJECT_STATE.md` or equivalent handoff state.
5. Commit with Lore protocol and `Co-authored-by: OmX <omx@oh-my-codex.dev>`.

## Non-Carry-Forward Rule

Do not carry failed gates forward as "known issues" while marking a milestone complete. A milestone that fails source-wall, safety, provider-primary-runtime, frontend build/e2e, visual readability, or CRITICAL/HIGH/BLOCK review remains incomplete until fixed or explicitly re-scoped in a new planning artifact.
