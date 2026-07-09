# M23.47 Markets Quote Snapshot Board

Date: 2026-05-26

## Scope

Add a read-only AI Agent supervision board for existing Markets quote lanes.
This milestone does not add a provider, refresh data, write artifacts, collect
keys, or make any quote orderable. It turns the existing
`source_coverage_matrix` / `quote_reference_coverage` contracts into a compact
board that an AI Agent can inspect before deciding whether a safe local refresh
or optional-key setup is even relevant.

## Implemented Behavior

- `GET /api/markets/quote-snapshot-board` returns
  `read_only_markets_quote_snapshot_board`.
- `/api/markets` and `/api/markets/quote-reference-coverage` include the same
  `snapshot_board` payload.
- Each board row contains asset family, runtime role, provider ID, auth mode,
  readiness, supervision state, row count, cache path, safe action ID,
  preflight endpoint, and explicit `orderable: false`, `executable: false`, and
  `live_action_enabled: false`.
- Markets UI exposes selector `markets-quote-snapshot-board` plus per-row
  `markets-quote-snapshot-row-*` selectors.
- `/api/agent-contract` exposes route state `quote_snapshot_board` and action
  `markets_quote_snapshot_board`.
- Command Center action matrix surfaces the new action through the existing
  read-only route/action contract.

## Clean-Room And Safety Boundaries

- No Fincept branding, assets, commercial copy, source, runtime binaries, or
  installed-source paths are used.
- No external provider call is made by the board endpoint.
- No artifact or cache is written.
- No credential or secret value is read, returned, logged, stored, or required.
- No broker/exchange binding, real balance, real order, margin, leverage, short,
  derivatives, payment, subscription, CR/credits, cloud sync, or live/private
  trading behavior is enabled.
- Reference, macro, fundamental, symbol-directory, and context rows remain
  excluded from the quote board and are not described as executable quotes.

## Verification Plan

- Focused backend contract tests for Markets, Agent Contract, and Command Center.
- Frontend typecheck and targeted Playwright Markets assertions.
- Source-wall, live-safety, local secret gate, mission-ledger, and command-center
  safety tests.
- FastAPI smoke for the new endpoint, action contract, and safety flags.
- Secret scans for known user credential literals before commit.
