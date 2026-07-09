# M20 ECB FX Reference Provider

Date: 2026-05-23

## Purpose

M20.2 adds the first no-key public FX provider so the Markets `FX` workspace no
longer stays at a setup-only state. The implementation is clean-room and
independent: it uses European Central Bank public reference-rate XML behavior and
local cache/state contracts, not Fincept code, runtime, assets, branding, or
commercial copy.

## Provider Entry Gate

| Field | Value |
| --- | --- |
| Provider id | `ecb_fx_reference_public` |
| Coverage | FX, EUR-base daily reference rates, currency-pair rows |
| Official docs | `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-xml.html` |
| Feed | `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml` |
| Auth mode | `no-key` |
| Rate limit | Use daily local cache; public read-only XML feed |
| Terms risk | Reference rates are information-only; do not present as executable spot quotes |
| Cache path | `market_data/fx/ecb/eurofxref_daily.json` |
| TTL | `86400` seconds |
| Schema | ECB eurofxref XML to normalized EUR-base pair rows and FX summary |
| Fallback | Show stale local reference rates or explicit unavailable state with refresh guidance |
| UI attribution | Markets source diagnostics and FX panel show provider id, cache, docs, auth, and reference-only status |
| Safety class | `public_read_only_fx_reference` |
| Secret gate | Not required; no key entry or local secret file is created |

## Runtime Scope

- `POST /api/markets/fx/refresh` refreshes the ECB cache and returns the Markets
  payload with a route-specific FX panel.
- `GET /api/fx` returns public FX state without exposing the raw cache wrapper.
- Provider health includes `fx_ecb_reference_rates` in `/api/providers` and
  `/api/providers/cache`.
- Advanced local context can index the ECB FX cache for read-only AI Chat,
  Nodes, Code, Quant Lab, and QuantLib context.

## Boundaries

- ECB reference rates are not treated as executable trading quotes.
- No optional-key provider is enabled.
- No paid provider is enabled.
- No real order, private API key, real balance, margin, leverage, short, or
  derivatives path is added.
- No credentials, PINs, tokens, API keys, or private keys are stored, logged,
  screenshot, or committed.
