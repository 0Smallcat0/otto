# M20 Treasury Rates Provider

Date: 2026-05-23

## Purpose

M20.1 adds the first no-key public rates provider so the Markets `Bonds/Rates`
workspace no longer stays at a planned/setup-only state. The implementation is
clean-room and independent: it uses U.S. Treasury public XML feed behavior and
local cache/state contracts, not Fincept code, runtime, assets, branding, or
commercial copy.

## Provider Entry Gate

| Field | Value |
| --- | --- |
| Provider id | `us_treasury_yield_public` |
| Coverage | Bonds/rates, U.S. Treasury daily yield curve tenors |
| Official docs | `https://home.treasury.gov/treasury-daily-interest-rate-xml-feed` |
| Auth mode | `no-key` |
| Rate limit | Use daily local cache; public read-only XML feed |
| Terms risk | Public government rate data; preserve source attribution and retrieval date |
| Cache path | `market_data/rates/treasury/daily_yield_curve.json` |
| TTL | `86400` seconds |
| Schema | Atom XML feed to normalized daily tenor rows and rates summary |
| Fallback | Show stale local curve or explicit unavailable state with refresh guidance |
| UI attribution | Markets source diagnostics and Bonds/Rates panel show provider id, cache, docs, and auth mode |
| Safety class | `public_read_only_rates` |
| Secret gate | Not required; no key entry or local secret file is created |

## Runtime Scope

- `POST /api/markets/rates/refresh` refreshes the Treasury cache and returns the
  Markets payload with a route-specific rates panel.
- `GET /api/rates` returns public rates state without exposing the raw cache
  wrapper.
- Provider health includes `rates_treasury_yield_curve` in `/api/providers`
  and `/api/providers/cache`.
- Advanced local context can index the Treasury rates cache for read-only
  AI Chat, Nodes, Code, Quant Lab, and QuantLib context.

## Boundaries

- No optional-key provider is enabled.
- No paid provider is enabled.
- No real order, private API key, real balance, margin, leverage, short, or
  derivatives path is added.
- No credentials, PINs, tokens, API keys, or private keys are stored, logged,
  screenshot, or committed.
