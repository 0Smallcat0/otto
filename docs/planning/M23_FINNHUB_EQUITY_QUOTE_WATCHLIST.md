# M23.34 Finnhub Equity Quote Watchlist

Date: 2026-05-26

## Objective

M23.34 deepens Markets quote breadth with a second bounded optional-key equity
quote lane. It adds Finnhub `/quote` support for `AAPL/MSFT/NVDA/SPY` while
preserving the local-secret gate, clean-room boundary, and non-orderable quote
semantics.

This is not a broad market-data parity claim. It does not add broker/exchange
binding, real balances, real orders, realtime entitlement activation, account
access, public no-key Finnhub refreshes, payment, subscription, cloud sync, or
live/private behavior.

## Implementation

- Added `src/local_terminal/finnhub_data.py` with bounded symbol normalization,
  `/quote` fetch/normalize logic, stale/key-required/rate-limited states,
  source attribution, and cache-safe payloads that never return the local
  credential.
- Added per-symbol local caches under `market_data/quotes/finnhub/{symbol}.json`
  and provider freshness/cache registry entries for `AAPL/MSFT/NVDA/SPY`.
- Exposed `GET /api/finnhub/quotes`, `POST /api/finnhub/quotes/refresh`, and
  `POST /api/markets/finnhub/quotes/refresh`.
- Added Markets `research_summary.finnhub_quotes`,
  `source_coverage_matrix` row `equity_quote_watchlist_secondary`, and
  `quote_reference_coverage` visibility while keeping `quote_not_orderable`.
- Added AI Agent action contract
  `markets_finnhub_quote_watchlist_refresh` and route state
  `finnhub_equity_quote_watchlist`.
- Added a `FINNHUB` Markets toolbar action for human supervision of the bounded
  optional-key lane.
- Updated provider acquisition and Command Center provenance so future agents
  can identify the current slice and avoid repeating it.

## Safety

- Finnhub remains optional-local-key only through the existing local secret
  gate.
- The implementation does not create, display, log, or commit credential values.
- The provider is excluded from manual public no-key refresh jobs.
- Quote rows are non-orderable, not broker-routable, and have
  `live_action_enabled=false`.
- No provider signup, CAPTCHA/2FA handling, payment flow, identity verification,
  account/private API access, or destructive action was attempted.

## Verification

Fresh verification is tracked in `docs/planning/M22_MISSION_LEDGER.md` under
the M23.34 verification log.

## Resume Guidance

Do not redo this provider lane. Future Markets quote work should choose a new
provider-entry gate or a concrete route workflow gap, keep quote/reference
semantics explicit, and avoid collecting unused optional keys.
