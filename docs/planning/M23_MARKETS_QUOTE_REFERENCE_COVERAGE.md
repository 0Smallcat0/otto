# M23.26 Markets Quote Reference Coverage

Date: 2026-05-26

## Scope

M23.26 turns the existing Markets `source_coverage_matrix` into a smaller
AI-agent-readable quote/reference supervision view. The slice does not add a
provider adapter, does not fetch external data, and does not change quote
orderability. It only classifies existing source rows so an AI Agent and human
operator can see which lanes are non-orderable quotes, reference data, or
context-only data.

## Product Behavior

- `GET /api/markets` now includes `quote_reference_coverage`.
- `GET /api/markets/quote-reference-coverage` returns the same read-only
  coverage view without triggering provider refresh.
- The coverage view summarizes source-row count, quote lane count, cached quote
  rows, public quote lanes, optional-key quote lanes, reference lanes,
  context-only lanes, executable quote count, orderable lane count, and live
  action count.
- Markets UI now exposes stable selector `markets-quote-reference-coverage`
  before the full Provider Entry Gate matrix.
- AI Agent contract now exposes route state `quote_reference_coverage` and action
  `markets_quote_reference_coverage`.

## Current Baseline Evidence

With an empty local test store after M23.49, the derived coverage reports:

- 25 source coverage rows.
- 9 non-orderable quote lanes.
- 3 public no-key quote lanes: Stooq, MOEX, and TWSE delayed/daily snapshots.
- 6 optional local-key quote lanes: Alpha Vantage Stocks, ETF, FX, Twelve
  Data secondary quotes, Finnhub, and FMP.
- 8 reference-only lanes.
- 8 context-only lanes.
- 0 executable quote lanes, 0 orderable lanes, and 0 live-action-enabled lanes.

This keeps broad executable quote parity `partial`: the system can supervise
quote/reference breadth more clearly, but it still does not provide broad
orderable market data or live trading.

## Clean-Room And Safety Boundaries

- No Fincept branding, assets, commercial copy, runtime binaries, installed
  source, or `D:\FinceptTerminal\app\scripts` were used.
- No provider signup, CAPTCHA bypass, payment, identity verification, or
  credential flow was started.
- No secret value is read or returned, and the endpoint does not create
  `settings/local_secrets.json`.
- No live trading, broker/exchange binding, real balances, margin, leverage,
  short exposure, derivatives, order submission, or destructive artifact
  lifecycle action is reachable.

## Verification Plan

- Focused backend: Markets source coverage, AI Agent contract, Command Center
  contract.
- Frontend: TypeScript build, lint, and E2E selector checks.
- Safety: source wall, live safety, local secret gate, mission ledger.
- Full sweep: full backend pytest, full ruff, frontend build/lint/e2e,
  API smoke, diff check, and changed-diff secret scan.

## Handoff

Future Markets provider work should use this coverage view before adding more
providers. Reference-only and context-only rows must not be re-labeled as
quotes. Delayed quote snapshots must remain non-orderable until a separate
provider-entry and live-safety review proves otherwise.
