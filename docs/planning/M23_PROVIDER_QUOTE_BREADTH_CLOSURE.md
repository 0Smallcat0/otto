# M23.67 Provider Quote Breadth Closure

## Scope

M23.67 closes the current provider quote-breadth loop for the non-live,
no-subscription product boundary. It adds a machine-readable closure contract to
the provider acquisition gate so AI Agents can distinguish finite reviewed
provider evidence from work that should be retried.

This slice does not add a provider adapter, call external providers, sign up,
collect or store credentials, write market-data caches, add source coverage
rows, add broker/exchange binding, read real balances, route orders, or enable
live/private behavior.

## Product Delta

- Adds `quote_breadth_closure` to `GET /api/provider-acquisition-gate`.
- Records `status=closed_until_new_official_provider_gate`.
- Records candidate count `21`, implemented-or-blocked count `21`, approved
  next count `0`, blocked count `5`, and the five blocked provider-entry ids.
- Exposes the closure through Command Center and the Settings supervision UI.
- Moves Command Center current milestone/provenance to this document.

## Agent Contract

AI Agents must treat the provider backlog as finite evidence, not an instruction
to keep retrying blocked providers. Broad executable or orderable quote parity is
outside the current non-live/no-subscription boundary unless a future
provider-entry gate approves a concrete official source with auth mode, route
need, cache schema, quote semantics, display/retention terms, and tests.

The current product still exposes useful non-orderable quote lanes, reference
rows, context rows, quote/reference coverage, and a quote snapshot board. It does
not expose executable quotes, orderable quote lanes, broker routing, real
balances, or live orders.

## Safety Contract

- Keep Cboe, IEX, Nasdaq Data Link, JPX/J-Quants, and Yahoo Finance as blocked
  provider-entry evidence until a separate official-doc gate changes that state.
- Do not add signup, key prompts, crawlers, chart/query scrapers, portal
  crawlers, CSV bulk downloaders, cache writers, provider refresh rows, or
  source coverage rows while `resume_state=backlog_exhausted_needs_research`.
- Any future provider work must start with official docs and preserve the local
  secret gate, source wall, no-subscription boundary, and non-live safety gates.

## Verification

- Focused provider/Command Center/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_m22_provider_acquisition_gate.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py --basetemp .omx\pytest-tmp\m23-67-focused`
  -> 10 passed.
- Full backend:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-67-full`
  -> 380 passed.
- Ruff:
  `.\.venv\Scripts\python.exe -m ruff check .`
  -> passed.
- Frontend `npm run lint` -> passed.
- Frontend `npm run build` -> passed with the existing Vite chunk-size warning.
- Focused shell E2E `npm run e2e -- --grep "opens all routes"` -> 1 passed.
- Frontend full E2E `npm run e2e` -> 15 passed.
- Source-wall/live-safety/local-secret/provider safety gate:
  `.\.venv\Scripts\python.exe -m pytest -q tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_provider_acquisition_gate.py --basetemp .omx\pytest-tmp\m23-67-safety`
  -> 22 passed.
- FastAPI smoke confirmed `quote_breadth_closure.mode`,
  `closed_until_new_official_provider_gate`, candidate count `21`,
  implemented-or-blocked count `21`, blocked count `5`, approved next count `0`,
  blocked ids for Cboe/IEX/Nasdaq Data Link/JPX-J-Quants/Yahoo Finance,
  Command Center milestone `M23.67 Provider quote breadth closure`, milestone
  path `docs/planning/M23_PROVIDER_QUOTE_BREADTH_CLOSURE.md`, action count
  `73`, preflight rows `73`, and no local secret-store creation.
