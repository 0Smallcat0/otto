# M21.18 Stock Status Lanes

Date: 2026-05-25

## Scope

This slice deepens the Markets Stocks route by separating the four current stock
provider/workflow lanes into machine-readable route state:

- `quotes`: optional-key Alpha Vantage quote watchlist.
- `registry`: public SEC company ticker registry.
- `filings`: public SEC recent filing metadata.
- `fundamentals`: public SEC companyfacts context.

The goal is to prevent a single gateway/headline state from hiding the other
Stocks lanes. An AI Agent can now inspect lane availability, gating, provider,
cache path, action id, and row counts without inferring them from panel text.

## Sanitized Observation

The installed app was opened from `D:\FinceptTerminal\app\FinceptTerminal.exe`
for behavior observation only. The recover-session prompt was skipped, and the
terminal shell exposed a dense route rail plus market/data-source controls.
Sensitive account, credential, billing, credit, user, and commercial text was
excluded from retained notes. No screenshot from the installed app was retained
for this slice.

Relevant abstract observations:

- The terminal presents route-level navigation and data-source controls in dense
  adjacent panes.
- Market operation is not represented as one provider state only; the UI exposes
  multiple source/data controls near the active route.
- Local replication should therefore show Stocks provider families as separate
  operational lanes rather than letting quote, filings, registry, or fundamentals
  overwrite each other as the single route headline.

## Implementation

- `src/local_terminal/markets.py` adds `stocks.status_lanes` and summary fields:
  `status_lane_count`, `available_lane_count`, `gated_lane_count`,
  `primary_lane`, and `available_lanes`.
- The Stocks asset gateway now reports `stock_lanes_available` when any stock
  lane has runtime cache/state evidence, instead of selecting quote, filings,
  registry, or fundamentals as the only gateway state.
- `frontend/src/components/Markets.tsx` uses the lane summary for the active
  Markets status and adds a `markets-stocks-status-lanes` panel.
- `src/local_terminal/agent_contract.py` exposes `stock_status_lanes` as a
  Markets state field and includes `stocks.status_lanes` in Stocks refresh action
  response contracts.

## Boundaries

- No new provider adapter was added.
- No provider key, password, PIN, private key, token, or personal data is stored,
  logged, committed, or returned.
- No live order path, broker/exchange key flow, real balance read, margin,
  leverage, short exposure, derivative execution, or live trading control was
  added.
- No Fincept branding, logo, commercial copy, asset, runtime binary, installed
  source, billing/subscription, CR/credits, or cloud-account behavior was copied
  into the local product.
- Fixtures remain test/offline fallback only.

## Verification

Initial focused verification:

- `.\.venv\Scripts\python.exe -m pytest tests\test_m20_sec_stocks_fundamentals.py tests\test_m20_alpha_vantage_quote_provider.py tests\test_m19_news_macro_fundamentals.py tests\test_m21_agent_operability_contract.py -q`
  -> 21 passed. Pytest emitted a Windows temp cleanup permission warning after
  completion, but exited successfully.
- `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\markets.py src\local_terminal\agent_contract.py tests\test_m20_sec_stocks_fundamentals.py tests\test_m20_alpha_vantage_quote_provider.py tests\test_m19_news_macro_fundamentals.py tests\test_m21_agent_operability_contract.py`
  -> passed.
- `npm run lint` -> passed.
- `npm run build` -> passed.

Completion verification:

- `.\.venv\Scripts\python.exe -m pytest -q --basetemp .tmp\pytest-m21-18-full`
  with repo-local TEMP/TMP -> 241 passed.
- `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py -q --basetemp .tmp\pytest-m21-18-safety`
  with repo-local TEMP/TMP -> 12 passed.
- `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- `npm run e2e` -> 15 passed after the Stocks lane locator was narrowed to the
  dedicated heading/source-contract panel and the lane table was compacted.
- Browser/Playwright screenshot:
  `artifacts/screenshots/m21-stock-status-lanes.png`.
- Visual verdict: pass, score 90, stored at
  `.omx/state/m21-stock-status-lanes/ralph-progress.json`.
- Generic high-risk secret scan -> no secret-like patterns in changed text files.
- `git diff --check` -> passed with Git CRLF working-copy warnings only.
- Local code-review gate -> APPROVE, no blocking findings.
