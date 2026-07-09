# M21 Markets Provider Source Contracts

Date: 2026-05-25

## Scope

M21.12 extends the M21.11 Provider Stack / Source Contract pattern beyond macro
Indexes/Regional into the non-macro Markets provider families:

- Stocks
- ETF
- FX
- Commodities
- Bonds/Rates

The slice is UI/agent-contract depth only. It does not add a provider adapter,
provider credential flow, paid/bulk quote endpoint, background refresh behavior,
or executable market/trading path.

## Observation Evidence

Safe observation used the installed Fincept app and existing reference evidence as
workflow evidence only:

- `D:\FinceptTerminal\app\FinceptTerminal.exe` was launched on 2026-05-25,
  confirmed responsive, and stopped.
- No credential or PIN was entered.
- No new Fincept screenshot was retained.
- Existing sanitized Markets evidence was used:
  - `docs/reference/fincept-platform-test/screenshots/subfeatures/markets/main-visual.png`
  - `docs/reference/fincept-platform-test/logs/markets-deep-ui-elements.json`

The extracted reference behavior is dense multi-panel Markets layout with
`[COLS]`, `[EDIT]`, `[DEL]`, table headers such as `SYMBOL`, `LAST`, `CHG`,
`CHG%`, `HIGH`, `LOW`, and panels for Stock Indices, Forex, Commodities, Bonds,
ETFs, Cryptocurrencies, India, China, and United States. The local implementation
copies no source, branding, assets, commercial copy, account state, billing, or
credit mechanics.

## Implementation

- Added reusable `ProviderStackPanel` and `SourceContractPanel` components in
  `frontend/src/components/Markets.tsx`.
- Stocks now separates:
  - `markets-stocks-provider-stack`
  - `markets-stocks-quote-watchlist`
  - `markets-stocks-source-contract`
- ETF now separates:
  - `markets-etf-provider-stack`
  - `markets-etf-quote-watchlist`
  - `markets-etf-source-contract`
- FX, Commodities, and Bonds/Rates now expose:
  - `markets-fx-provider-stack`
  - `markets-fx-source-contract`
  - `markets-commodities-provider-stack`
  - `markets-commodities-source-contract`
  - `markets-rates-provider-stack`
  - `markets-rates-source-contract`
- The Markets route AI Agent contract now includes `provider_stack_panels` and
  `source_contract_panels`.
- Playwright assertions cover the new stable selectors for Stocks, ETF, FX,
  Commodities, and Bonds/Rates.

## Safety Boundaries

- No Fincept branding, logo, trademark, commercial copy, assets, runtime binary,
  installed package source, or `D:\FinceptTerminal\app\scripts` source was read or
  copied.
- No provider signup, API-key capture, account/cloud behavior, paid data,
  billing, subscription, CR/credits, or personal data path was added.
- No live order path, broker/exchange key flow, real balance read, margin,
  leverage, short exposure, derivatives execution, or live trading control was
  added.
- Existing providers keep their previous safety class:
  - SEC fundamentals/fund registry remain public reference data.
  - Alpha Vantage quotes remain optional-local-key and local-secret-gated.
  - ECB FX and Treasury rates remain no-key reference data.
  - World Bank commodities and EIA energy remain reference/context data.

## Verification

Current evidence:

- Focused agent contract gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m21_agent_operability_contract.py -q`
  with repo-local TEMP/TMP -> 4 passed.
- Focused Markets provider/source gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m21_agent_operability_contract.py tests\test_m20_sec_stocks_fundamentals.py tests\test_m20_sec_fund_etf_provider.py tests\test_m20_ecb_fx_provider.py tests\test_m20_treasury_rates_provider.py tests\test_m20_world_bank_commodities_provider.py -q`
  with repo-local TEMP/TMP -> 18 passed.
- Full backend:
  `.\.venv\Scripts\python.exe -m pytest -q` with repo-local TEMP/TMP -> 234
  passed.
- Source-wall/live-safety:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q`
  with repo-local TEMP/TMP -> 12 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Targeted ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\agent_contract.py tests\test_m21_agent_operability_contract.py`
  -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; E2E
  includes scoped Provider Stack and Source Contract assertions for Stocks, ETF,
  FX, Commodities, and Bonds/Rates.
- Browser smoke opened local Markets and confirmed representative Stocks and
  Commodities split panels.
- Screenshot evidence:
  - `artifacts/screenshots/m21-markets-provider-source-contracts-stocks.png`
  - `artifacts/screenshots/m21-markets-provider-source-contracts-focused.png`
- Visual verdict: pass, score 92, recorded under ignored
  `.omx/state/m21-markets-provider-source-contracts/ralph-progress.json`.
- Sensitive-literal scan for known account credential/PIN literals -> no matches.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Code-review gate -> APPROVE with no CRITICAL/HIGH/MEDIUM/LOW findings.
  Review confirmed the slice changes UI/agent-contract inspection surfaces only and
  adds no provider adapter, credential path, live trading path, paid data path, or
  installed-source dependency.

## Remaining Watch

The source/provider split is now available across macro and non-macro Markets
panels. Future provider work should reuse these components rather than adding
another ad hoc source table to `Markets.tsx`. A future UI cleanup can decide
whether quote watchlists should be folded into provider-stack rows or remain
separate detail panels.
