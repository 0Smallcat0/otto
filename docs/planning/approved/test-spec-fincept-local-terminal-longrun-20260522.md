# Test Spec: Fincept Local Terminal Longrun

Status: Approved by RALPLAN Critic.

## Baseline Commands

- `.\.venv\Scripts\python.exe -m pytest -q`
- `.\.venv\Scripts\python.exe -m ruff check .`
- Frontend lint/test/build from `package.json` after frontend exists.
- Playwright/browser checks after UI exists.
- `git diff --check`

## Unit Gates

- Route set exactly matches Dashboard, Markets, Crypto, Portfolio, News, AI Chat, Backtest, Algo, Nodes, Code, Quant Lab, QuantLib, Forum, Settings, Profile.
- File/Navigate/View/Help expose minimum local command contracts.
- Storage paths reject absolute paths, URLs, `~`, and `..`.
- Local profile never requires cloud account, billing, subscription, CR, credits, or private API.
- Public data adapters require no private credentials.
- Paper broker rejects oversell, negative cash, negative position, short exposure, and unsupported live execution.
- Backtest rejects still-open candles, lookahead, and same-candle fills.
- Artifact writers create expected schemas and avoid secrets.

## Integration Gates

- App boot and config load.
- Public market data fetch, cache, stale fallback, and visible freshness.
- Dashboard aggregates local/public/paper/backtest state.
- Crypto order ticket writes paper orders/fills/account snapshots.
- Backtest run writes `config.json`, `data_snapshot.json`, `summary.json`, `trades.csv`, and `report.md`.
- Portfolio create/import/demo/export and artifact linking.
- AI Chat and Code read local artifacts only through safe read-only paths.
- Nodes dry-run cannot reach live broker paths.

## E2E / UI Gates

- Open all 15 routes.
- Navigate through side/top nav and Navigate menu.
- File layout save/open/export/import.
- View quick switch, screenshot, focus/fullscreen state where applicable.
- Dashboard add widget, alerts drawer, save layout, reset template.
- Markets add panel, column chooser, edit modal, delete confirmation.
- Crypto paper buy/sell validation, accepted paper order, and reject flows.
- Backtest run and result tabs.
- Portfolio create/import/demo/export.
- AI Chat new/rename/delete confirmation.
- Nodes template load and disabled deploy/execute.
- Code notebook open/save/add cell/sidebar.
- QuantLib local preset computation.
- Forum new local post.

## Visual Gates

- Use `browser:browser` or Playwright to capture route screenshots.
- Use `$visual-verdict` for semantic layout/workflow/category comparison against reference screenshots.
- Numeric score is a signal, not a pixel-perfect requirement.
- Exact branding, commercial copy, logo, icon identity, color identity, and assets must be ignored or replaced.
- Persist verdict JSON in `.omx/state/{scope}/ralph-progress.json`.

## Clean-Room / Source-Wall Gate

M0 must introduce an executable gate, either a test file or script such as `tests/test_clean_room_source_wall.py` or `scripts/check_clean_room_source_wall.py`.

Minimum forbidden-pattern list:

- `D:\FinceptTerminal\app\scripts`
- `D:/FinceptTerminal/app/scripts`
- executable imports or reads from installed Fincept package source
- copied Fincept runtime binaries or installed assets
- copied Fincept branding, logo references, trademarks, or commercial copy
- `D:\Crypto-Trading` or `D:/Crypto-Trading` in active implementation-routing docs
- `FINCEPT_TO_CRYPTO_TRADING_HANDOFF` as active roadmap
- `Large Liquid Trend 15 from D:\Crypto-Trading`
- credential, PIN, token, private key, account email, or secret literals

The gate should scan changed executable/config/docs surfaces while avoiding destructive rewrites of raw evidence under `docs/reference/`.

## Screenshot / Evidence Redaction

- Before committing screenshot evidence, redact account/email/CR regions.
- Inspect or strip screenshot metadata when practical.
- Do not commit raw credential, account, PIN, token, private key, or personal information.
- If a raw reference image contains sensitive areas and must remain as historical evidence, do not reuse it as public handoff proof; capture a masked derivative.

## Live Safety Gate

No live execution path may be reachable before a separate live safety PRD/test spec passes review. That future gate must prove:

- local secret storage design
- explicit live-mode opt-in
- confirmation gates
- audit/reject logs
- kill switch behavior
- paper/live environment isolation
- static reachability checks
- unit/integration/e2e coverage
- code-review and security-review approval

## Milestone Verification Shape

Every milestone must report:

- commands run
- tests/lint/build/e2e status
- screenshots or JSON artifacts produced
- visual-verdict status when UI is involved
- clean-room/source-wall status
- secrets/redaction status
- code-review status
- changed files
- remaining disabled/gated scopes
