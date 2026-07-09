# M20.4 SEC Stocks Fundamentals

Date: 2026-05-23

## Scope

M20.4 turns the existing public no-key SEC EDGAR fundamentals provider into a route-specific Markets Stocks workflow. This is a Markets depth milestone, not a new quote-provider milestone.

## Provider Entry

| Field | Value |
| --- | --- |
| Provider | `sec_edgar_public` |
| Official docs | `https://www.sec.gov/search-filings/edgar-application-programming-interfaces` |
| Auth mode | no-key |
| Coverage | U.S. company XBRL companyfacts fundamentals; default cache covers AAPL by CIK |
| Rate limit | SEC fair access guidance, no more than 10 requests per second |
| Terms/display risk | Public SEC data with attribution and respectful User-Agent |
| Cache path | `market_data/fundamentals/sec/0000320193/companyfacts.json` |
| TTL | daily local cache through the existing provider registry |
| Schema | `companyfacts -> companies[] -> facts[]` |
| Fallback | unavailable/stale SEC cache state; never fake stock quotes |
| Safety class | public read-only fundamentals |

## Implementation Notes

- Markets now exposes top-level `stocks` payload state with provider status, company rows, normalized fact rows, and quote-gate status.
- `/api/markets/stocks/refresh` refreshes the existing research provider cache and returns the full Markets payload.
- The Markets Stocks tab is selectable and renders a dedicated three-column workflow: companies, latest facts, and source/quote gate.
- Stock quote feeds remain disabled until a separate provider and local secret-storage/safety gate exists.

## Verification Plan

- Backend tests prove the Stocks view is derived from SEC companyfacts, includes source/cache/docs metadata, and keeps quote state disabled.
- Refresh tests prove `/api/markets/stocks/refresh` writes the SEC cache and activates the `sec_edgar_public` provider health state without leaking credential terms.
- Frontend build/lint/e2e and browser screenshot verify the new route workflow remains readable in the low-contrast dense terminal style.

## Boundary

No live trading, real order path, private API key flow, real balance read, margin, leverage, short exposure, derivatives execution, billing, subscription, cloud account, Fincept branding, installed source, or quote-provider credential surface is added.
