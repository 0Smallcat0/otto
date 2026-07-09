# M20 World Bank Commodities Provider

Date: 2026-05-23

## Purpose

M20.3 adds the first no-key public commodity provider so the Markets
`Commodities` workspace no longer stays at a setup-only state. The
implementation is clean-room and independent: it uses World Bank Commodity
Markets Pink Sheet public monthly XLSX behavior and local cache/state contracts,
not Fincept code, runtime, assets, branding, or commercial copy.

## Provider Entry Gate

| Field | Value |
| --- | --- |
| Provider id | `world_bank_commodity_monthly_public` |
| Coverage | Commodities, energy, metals, agriculture, monthly reference prices |
| Official docs | `https://www.worldbank.org/en/research/commodity-markets` |
| Feed | `https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx` |
| Auth mode | `no-key` |
| Rate limit | Use weekly local cache; public monthly XLSX data file |
| Terms risk | Preserve World Bank attribution; do not present monthly values as executable spot or futures quotes |
| Cache path | `market_data/commodities/world_bank/pink_sheet_monthly.json` |
| TTL | `604800` seconds |
| Schema | Pink Sheet monthly XLSX to normalized latest monthly commodity rows and summary |
| Fallback | Show stale local monthly prices or explicit unavailable state with refresh guidance |
| UI attribution | Markets source diagnostics and Commodities panel show provider id, cache, docs, auth, and monthly-reference status |
| Safety class | `public_read_only_commodity_reference` |
| Secret gate | Not required; no key entry or local secret file is created |

## Runtime Scope

- `POST /api/markets/commodities/refresh` refreshes the World Bank cache and
  returns the Markets payload with a route-specific Commodities panel.
- `GET /api/commodities` returns public commodity state without exposing the
  raw cache wrapper.
- Provider health includes `commodities_world_bank_monthly` in `/api/providers`
  and `/api/providers/cache`.
- Advanced local context can index the commodity cache for read-only AI Chat,
  Nodes, Code, Quant Lab, and QuantLib context.

## Boundaries

- World Bank monthly values are not treated as executable spot or futures
  quotes.
- No optional-key provider is enabled.
- No paid provider is enabled.
- No real order, private API key, real balance, margin, leverage, short, or
  derivatives path is added.
- No credentials, PINs, tokens, API keys, or private keys are stored, logged,
  screenshot, or committed.
