# M21 Macro Aggregation Contract

Date: 2026-05-24

## Scope

M21.10 formalizes the shared macro aggregation contract for Markets Indexes and
Regional before adding more macro provider breadth.

The slice fixes the M21.9 architecture watch: headline/latest macro fields no
longer depend on incidental provider list order. The runtime now exposes an
explicit `primary_provider`, `headline_series`, `headline_series_id`, and
`provider_summaries` contract across research data, Markets payloads, UI rows,
and tests.

## Contract

Macro headline selection follows this deterministic priority:

1. `dbnomics_public`
2. `fred_optional_local_key`
3. `bls_public_macro`
4. first available provider row only if none of the priority providers match

`provider_count` counts providers with at least one usable series. Provider
summaries remain visible even when a provider has zero rows so AI Agents can
distinguish active, key-required, unavailable, and stale states without guessing
from list position.

The Markets UI surfaces the contract in dense terminal rows:

- `HEADLINE`
- `PRIMARY`
- `RULE`
- `PROVIDERS`
- `HEADLINE ID`

## Implementation

- Added explicit macro headline constants and helper functions in
  `src/local_terminal/research_data.py`.
- Extended `research_data_payload` with `headline_series`,
  `provider_summaries`, `provider_count`, `primary_provider`,
  `headline_series_id`, `headline_label`, and `headline_rule`.
- Propagated the same contract through `src/local_terminal/markets.py` for
  Indexes and Regional.
- Updated frontend type contracts and fallback payloads in `frontend/src/types.ts`,
  `frontend/src/components/Markets.tsx`, and `frontend/src/components/News.tsx`.
- Added Playwright assertions that the macro panel exposes the headline/provider
  rows for AI-agent operation.

## Safety Boundaries

- No new provider, signup, credential, API-key, account, paid-data, billing,
  subscription, CR/credits, cloud, or broker/exchange path was added.
- No live order path, real balance read, margin, leverage, short exposure,
  derivatives execution, or live trading control was added.
- DBnomics, FRED, and BLS remain macro/reference context only. Indexes and
  Regional quote rows remain disabled behind provider gates.
- No Fincept branding, assets, commercial copy, installed source, package source,
  or runtime binary was copied or adapted.
- Tests use synthetic provider payloads only as tests; user-visible runtime uses
  public/provider caches or explicit unavailable/key-required states.

## Verification

Current evidence:

- Focused macro/provider gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m20_dbnomics_markets_macro_context.py tests\test_m21_bls_macro_provider.py tests\test_m19_news_macro_fundamentals.py tests\test_m4_markets.py -q`
  -> 17 passed.
- Full backend:
  `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 234
  passed.
- Source-wall/live-safety:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q`
  with repo-local TEMP/TMP -> 12 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; E2E
  now asserts `HEADLINE`, `PRIMARY`, `PROVIDERS`, and `HEADLINE ID` on the
  Indexes macro panel.
- Browser/Playwright smoke opened Markets Indexes and confirmed headline/provider
  rows with zero visible `LIVE` controls.
- Screenshot evidence:
  `artifacts/screenshots/m21-macro-aggregation-contract-detail.png`.
- Visual verdict: pass, score 91, recorded under ignored
  `.omx/state/m21-macro-aggregation-contract/ralph-progress.json`.
- Code-review gate -> COMMENT with no CRITICAL/HIGH/MEDIUM/LOW findings.
  Architecture WATCH: split the dense Markets macro/provider panel before adding
  another macro provider family.

## Remaining Watch

Macro aggregation headline semantics are now explicit. M21.11 addressed the dense
Markets macro/provider panel split for Indexes and Regional by adding separate
Provider Stack and Source Contract panels, and M21.12 extends that split to
non-macro Markets provider families. Future macro/provider breadth should reuse
that split and should keep `cache_written` versus `cache_available` semantics
separate in refresh automation.
