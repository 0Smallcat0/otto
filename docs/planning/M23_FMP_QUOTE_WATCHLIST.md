# M23.37 FMP Quote Watchlist

Date: 2026-05-26

## Objective

M23.37 deepens Markets quote breadth with another bounded optional-key stock
quote lane. It adds FMP stable quote support for `AAPL/MSFT/NVDA/SPY` while
preserving the local-secret gate, clean-room boundary, and non-orderable quote
semantics.

This is not a broad market-data parity claim. It does not add broker/exchange
binding, real balances, real orders, realtime entitlement activation, account
access, public no-key FMP refreshes, payment, subscription, cloud sync, FMP MCP
account integration, or live/private behavior.

## Implementation

- Added `src/local_terminal/fmp_data.py` with bounded symbol normalization,
  stable quote fetch/normalize logic, stale/key-required/rate-limited states,
  source attribution, and cache-safe payloads that never return the local
  credential.
- Added per-symbol local caches under `market_data/quotes/fmp/{symbol}.json`
  and provider freshness/cache registry entries for `AAPL/MSFT/NVDA/SPY`.
- Exposed `GET /api/fmp/quotes`, `POST /api/fmp/quotes/refresh`, and
  `POST /api/markets/fmp/quotes/refresh`.
- Added Markets `research_summary.fmp_quotes`, source coverage row
  `stock_quote_watchlist_tertiary`, and quote/reference coverage visibility
  while keeping `quote_not_orderable`.
- Added AI Agent action contract `markets_fmp_quote_watchlist_refresh` and
  route state `fmp_stock_quote_watchlist`.
- Added an `FMP` Markets toolbar action for human supervision of the bounded
  optional-key lane.
- Updated provider acquisition and Command Center provenance so future agents
  can identify the current slice and avoid repeating it.

## Official-Source Gate

- Official FMP stable quote documentation returned HTTP 200 on 2026-05-26 at
  `https://site.financialmodelingprep.com/developer/docs/stable/quote`.
- The page identified the endpoint as
  `https://financialmodelingprep.com/stable/quote?symbol=AAPL`.
- The official documentation states API-key authorization is required. The local
  adapter therefore stays optional-local-key only and never joins public no-key
  refresh jobs.
- A no-key/demo smoke of the stable endpoint returned HTTP 401, so no adapter
  path assumes bundled credentials or fixture quote fallback.

## Safety

- FMP remains optional-local-key only through the existing local secret gate.
- The implementation does not create, display, log, or commit credential values.
- The provider is excluded from manual public no-key refresh jobs.
- Quote rows are non-orderable, not broker-routable, and have
  `live_action_enabled=false`.
- No provider signup, CAPTCHA/2FA handling, payment flow, identity verification,
  account/private API access, MCP account integration, or destructive action was
  attempted.

## Verification

Fresh verification is tracked in `docs/planning/M22_MISSION_LEDGER.md` under
the M23.37 verification log.

## Resume Guidance

Do not redo this provider lane. Future Markets quote work should choose a new
provider-entry gate or a concrete route workflow gap, keep quote/reference
semantics explicit, and avoid collecting unused optional keys.
