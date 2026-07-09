# M20.5 DBnomics Index and Regional Macro Context

Date: 2026-05-23

## Purpose

M20.5 reduces the Markets `Indexes` and `Regional` shell gap by reusing the existing public no-key DBnomics macro provider as route-specific context. This does not claim to provide executable index, equity-region, futures, options, or regional exchange quotes.

## Provider Entry

| Field | Value |
| --- | --- |
| Provider | DBnomics public macro data, adapter id `dbnomics_public` |
| Coverage | Macro/economic series context for Markets `Indexes` and `Regional` tabs |
| Official source | `https://docs.db.nomics.world/` |
| Auth mode | `no-key` |
| Terms/license risk | DBnomics preserves original source terms; UI must show source provider/dataset and avoid implying quote rights |
| Rate limits | Daily local cache; broad provider expansion needs a fresh limit/terms check |
| Complexity | Low for reuse of existing M19.9 normalized series cache |
| Local cache strategy | `market_data/macro/dbnomics/INSEE/IPC-2015/A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE.json` |
| Test fixture strategy | Test-only DBnomics series response fixture with latest observation and source metadata |
| Fallback behavior | Empty macro panel with MACRO refresh guidance; no synthetic index/regional quotes |
| Safety class | Public read-only macro context; no account, credential, order, balance, margin, leverage, short, or derivatives path |

## Implementation Notes

- `markets_payload` now exposes top-level `indexes` and `regional` views from the DBnomics macro summary.
- Markets asset gateways mark `Indexes` and `Regional` as `macro_context_available` when DBnomics series are cached, or `no_key_provider_ready` before refresh.
- `/api/markets/macro/refresh`, `/api/markets/indexes/refresh`, and `/api/markets/regional/refresh` refresh only the DBnomics macro cache and return the normal Markets payload.
- The frontend makes `Indexes` and `Regional` selectable tabs with dense series/context/source panels.
- Quote rows stay disabled behind future provider/secret gates. The UI labels the content as macro context, not tradable quotes.

## Verification Targets

- Backend tests prove DBnomics macro series populate both `indexes` and `regional`.
- Endpoint tests prove refresh writes the DBnomics cache, does not create a SEC fundamentals cache, and keeps quote state disabled.
- Frontend build/lint proves the new payload schema and panels compile.
- Playwright E2E covers selecting `Indexes` and `Regional`.
- Screenshot evidence should be captured under `artifacts/screenshots/m20-5-markets-index-regional-macro.png`.

## Verification Results

- `.\.venv\Scripts\python.exe -m pytest tests\test_m20_dbnomics_markets_macro_context.py tests\test_m19_news_macro_fundamentals.py tests\test_m4_markets.py -q` with repo-local TEMP/TMP -> 13 passed.
- `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 161 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `npm run lint` -> passed.
- `npm run build` -> passed.
- `npm run e2e` -> 15 passed.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Browser/Playwright screenshot captured under `artifacts/screenshots/m20-5-markets-index-regional-macro.png`.
- Code-review gate -> pass, no CRITICAL/HIGH/BLOCK findings.

## Boundaries

- No Fincept branding, commercial copy, assets, installed source, or runtime code is used.
- No `D:\FinceptTerminal\app\scripts` read/copy/adapt path is added.
- No optional-key form, local secret store, private provider, paid provider, live order, real balance, margin, leverage, short, or derivatives path is added.
