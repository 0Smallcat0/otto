# M21 Markets Macro Panel Split

Date: 2026-05-25

## Scope

M21.11 addresses the M21.10 architecture watch by splitting Markets
Indexes/Regional macro source attribution into two machine-operable panels:

- `Provider Stack`
- `Source Contract`

The slice is intentionally narrow. It does not add a new provider, refresh path,
credential path, quote feed, or live trading capability.

## Observation Evidence

Safe observation used the installed Fincept app as workflow evidence only:

- Installed app process was launched and confirmed responsive, then stopped.
- No credential or PIN was entered.
- No screenshot containing account, billing, credit, login, or personal state was
  retained.
- Existing sanitized evidence was used:
  - `docs/reference/fincept-platform-test/screenshots/subfeatures/markets/main-visual.png`
  - `docs/reference/fincept-platform-test/logs/markets-deep-ui-elements.json`

The relevant observed behavior is dense Markets routing with many panels,
source/status strips, action controls, and tabular provider/source state. This
slice copies none of the installed source, branding, assets, account mechanics,
or commercial text.

## Implementation

- `frontend/src/components/Markets.tsx` now renders the macro `SOURCE` column as
  two compact panels:
  - `markets-{tab}-macro-provider-stack`
  - `markets-{tab}-macro-source-contract`
- `Provider Stack` exposes provider id, state, series count, latest value/period,
  and headline-provider marker.
- `Source Contract` keeps headline id, cache, docs, auth mode, quote state, and
  quote-provider gate separate from provider-stack rows.
- `frontend/src/styles.css` and `frontend/src/terminal-components.css` add a
  compact panel modifier for the split source column.
- `/api/agent-contract` Markets route state fields now include
  `macro_provider_stack`.
- Playwright and backend contract tests assert the new panels and state field.

## Safety Boundaries

- No Fincept branding, logo, trademark, commercial copy, assets, runtime binary,
  installed package source, or `D:\FinceptTerminal\app\scripts` source was read or
  copied.
- No provider signup, API-key capture, account/cloud behavior, paid data,
  billing, subscription, CR/credits, or personal data path was added.
- No live order path, broker/exchange key flow, real balance read, margin,
  leverage, short exposure, derivatives execution, or live trading control was
  added.
- DBnomics, FRED, and BLS remain macro/reference context only. Indexes and
  Regional quotes remain disabled behind quote-provider gates.

## Verification

- Focused macro/agent gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m21_agent_operability_contract.py tests\test_m20_dbnomics_markets_macro_context.py tests\test_m21_bls_macro_provider.py -q`
  -> 10 passed.
- Full backend:
  `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 234
  passed.
- Source-wall/live-safety:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q`
  with repo-local TEMP/TMP -> 12 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; E2E
  includes scoped Indexes and Regional assertions for `Provider Stack` and
  `Source Contract`.
- Browser smoke opened the local Markets route and confirmed
  `markets-indexes-macro-provider-stack` plus
  `markets-indexes-macro-source-contract` are visible.
- Screenshot evidence:
  - `artifacts/screenshots/m21-markets-macro-panel-split.png`
  - `artifacts/screenshots/m21-markets-macro-source-panels.png`
- Visual verdict: pass, score 92, recorded under ignored
  `.omx/state/m21-markets-macro-panel-split/ralph-progress.json`.
- Sensitive-literal scan for known account credential/PIN literals -> no matches.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Code-review gate -> COMMENT with no CRITICAL/HIGH/MEDIUM findings. LOW
  follow-ups were addressed before commit by adding Regional selector E2E
  coverage and recording the finalized review status.

## Remaining Watch

The macro source/provider split is now complete for Indexes and Regional. M21.12
extends the same pattern to Stocks, ETF, FX, Commodities, and Bonds/Rates. Future
Markets provider breadth should reuse these split-panel contracts before adding
more dense provider families to `Markets.tsx`.
