# M19 Master Goal Prompt

Paste this into the next long-running `/goal` execution after reviewing the planning artifacts.

```text
/goal
[$karpathy-guidelines](C:\Users\Administrator\.codex\skills\karpathy-guidelines\SKILL.md)

Work in D:\FinceptLocalTerminal. Run a long, autonomous, low-interaction rebuild of the clean-room local Fincept Terminal replacement. Do not stop after a small CSS fix or a few route patches. The goal is to move the app from the current "15 routes shell / empty-shell / mock-like / Not connected" state to true local clean-room functional, workflow, data, state, artifact, and style parity with observed Fincept Terminal evidence across all 15 entries.

Authority and boundaries:
- AGENTS.md is the highest project contract.
- D:\FinceptTerminal is installed app/evidence only.
- D:\FinceptLocalTerminal is the clean-room rebuild repo.
- D:\Crypto-Trading is historical residue and must not shape the roadmap.
- Do not read, copy, port, adapt, or modify D:\FinceptTerminal\app\scripts or installed package source/code/assets/runtime.
- Use only docs/reference evidence, screenshots, JSON logs, public documentation, safe live UI observation, and independent implementation.
- Do not copy Fincept branding, logo, trademarks, commercial copy, assets, or UI text.
- Do not implement subscription, billing, CR/credits, or cloud-account-required flows.
- Do not create reachable real orders, private broker/exchange API key flow, real balance read, margin, leverage, short exposure, or derivatives live execution until a full safety contract, local secret storage, explicit opt-in, confirmation gates, audit logs, kill switch, paper/live isolation tests, code review, and security review exist.
- Do not include, save, output, log, screenshot, or commit credentials, PINs, tokens, API keys, private keys, or personal account details.

Use these planning artifacts as the execution contract:
- docs/planning/M19_RALPLAN_PRD.md
- docs/planning/M19_RALPLAN_TEST_SPEC.md
- docs/planning/M19_PARITY_GAP_REPORT.md
- docs/planning/M19_PROVIDER_RESEARCH_MATRIX.md
- docs/planning/M19_RALPLAN_EXECUTION_PLAN.md
- docs/planning/FINAL_HANDOFF.md
- PROJECT_STATE.md
- AGENTS.md
- docs/reference/fincept-platform-test/LOCAL_TERMINAL_PRODUCT_SPEC.md
- docs/reference/fincept-platform-test/LOCAL_TERMINAL_ENGINEERING_SPEC.md

Core principles:
- Evidence before implementation: each route milestone starts by reading relevant reference evidence and, when needed, safely observing the installed app UI without touching source or sensitive flows.
- No empty shells: every route must have route-specific backend state, route-specific UI, and at least one verifiable workflow.
- No user-visible mock/default/offline fixture as primary runtime: fixtures are tests/offline fallback only.
- Real provider strategy: actively implement no-key public adapters first, then optional local-key providers behind secret storage and explicit opt-in. Do not stop at "public no-key data is limited."
- Low-contrast dense terminal style: repair the current high-contrast black/white look into muted dark gray, compact, table/panel-heavy terminal style comparable to observed evidence without copying brand/assets/copy.
- Local-first: settings, layouts, caches, reports, backtests, screenshots, logs, notebooks, and artifacts remain local by default.
- Safety gates are useful surfaces, not blank pages: where live/private/cloud behavior is forbidden, implement paper, local, read-only, dry-run, or disabled equivalents with source/risk explanation.

Execution sequence:
1. Baseline audit: confirm clean tree, current services/tests, screenshots, and route/API state. Update a short M19 working state file.
2. Theme/layout repair: split M18 broad CSS into stable theme tokens/components; lower contrast; densify panels/tables; verify dashboard/markets/crypto/backtest screenshots.
3. Provider/cache/freshness core: implement provider registry, cache metadata, freshness/state schemas, source attribution, error states, and UI freshness strip.
4. Public crypto providers: replace visible crypto offline_fixture states with Binance/Kraken/Coinbase public adapter chain for ticker/orderbook/candles/trades.
5. Dashboard aggregation: connect dashboard to provider registry, watchlist, paper broker, portfolio, backtest artifacts, news/macro placeholders with real provider/gated states.
6. Markets parity: implement multi-asset tab/panel model, crypto live public data, and key-gated non-crypto provider surfaces; no placeholder route cards.
7. Crypto workspace parity: richer chart/order book/trades/order ticket/positions/orders/fills/history/depth/stats tied to provider data and paper ledger.
8. Backtest provider provenance: add public closed-candle provider path and artifact provenance; keep deterministic fixtures test-only/offline fallback.
9. Portfolio pricing: manual/import/export portfolios with provider-priced valuation, allocation/performance, local artifacts.
10. News and macro: implement no-key/public where feasible (DBnomics/SEC/RSS-safe sources) and optional key-gated providers with local secret gate.
11. AI Chat/Code/Nodes/Quant Lab/QuantLib: connect each to provider cache/local artifacts and produce route-specific local outputs while keeping unsafe execution disabled/dry-run.
12. Settings/Profile/Forum/Help: provider setup, local secret status, cache controls, source-wall diagnostics, local profile/preferences, local notes/support.
13. Full visual/workflow parity pass: use browser/playwright screenshots and visual-verdict across representative routes, prioritizing style/workflow/function parity over pixel/brand parity.
14. Full QA and cleanup: run ultraqa-equivalent loops, code-review, source-wall, safety tests, frontend build/e2e, and remove slop only in changed files.

Milestone policy:
- Each milestone must start by reading the route-specific evidence.
- Each milestone must produce a visible workflow improvement and update local state/artifacts.
- Each milestone must run targeted tests plus the standard verification gate.
- Each milestone must update PROJECT_STATE.md or an equivalent handoff file.
- Each milestone must create a Lore-format commit with:
  Co-authored-by: OmX <omx@oh-my-codex.dev>

Standard verification gate:
- .\.venv\Scripts\python.exe -m pytest -q
- .\.venv\Scripts\python.exe -m ruff check .
- git diff --check
- If frontend exists/touched: npm run build, npm run lint, npm run test:e2e or the repo-equivalent scripts.
- Browser/playwright workflow verification for changed routes.
- Screenshot evidence for changed visual surfaces.
- Code review before commit; fix CRITICAL/HIGH/BLOCK findings.
- Source-wall and secret-leak checks before final milestone completion.

Stop condition:
- Stop only after all 15 routes have route-specific data/state/workflow, Dashboard/Markets/Crypto/Backtest/Portfolio no longer present fixtures as normal runtime, visual style is low-contrast dense terminal-like, tests/e2e/build/source-wall pass, and every completed milestone has a commit and handoff update.
```
