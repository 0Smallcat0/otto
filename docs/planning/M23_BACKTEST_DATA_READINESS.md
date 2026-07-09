# M23.39 Backtest Data Readiness

## Scope

M23.39 adds a read-only Backtest data readiness contract so an AI Agent can
inspect closed-candle dataset state before running local Backtest actions.

This milestone does not add a provider adapter, perform public refreshes, write
Backtest artifacts, optimize strategies, deploy strategies, read balances,
route broker/exchange orders, enable live trading, access credentials, or use
installed Fincept source/assets.

## Product Behavior

- `GET /api/backtest/data-readiness` returns `backtest_data_readiness_v1`.
- `GET /api/backtest` embeds the same `data_readiness` payload next to the
  existing provider status, strategy catalog, config, and run index.
- The payload reports each supported local Backtest dataset (`BTCUSDT`,
  `ETHUSDT`, `SOLUSDT`, `15m`) with source, state, provider/cache metadata,
  closed-candle count, deterministic fallback status, and the safe next action.
- The Backtest UI exposes selector `backtest-data-readiness`.
- The AI Agent contract exposes state field `data_readiness` and action
  `backtest_data_readiness`.
- Command Center current milestone points to this document.

## Safety Contract

- Read-only and metadata-only.
- No provider refresh is performed by the readiness endpoint.
- No artifact directory or secret store is created.
- Deterministic fallback remains explicit and visible when the public
  closed-candle cache is unavailable.
- Live orders, broker routing, real balances, margin, leverage, short exposure,
  and derivatives remain disabled.

## Verification

- Focused Backtest/agent/Command Center gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m6_backtest.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-39-focused`
  -> 33 passed.
- Focused ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\backtest.py src\local_terminal\server.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py tests\test_m6_backtest.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Frontend build:
  `npm run build` in `frontend/` -> passed with the existing Vite chunk-size
  warning.
- Frontend lint/e2e:
  `npm run lint` -> passed; `npm run e2e` -> 15 passed.
- Safety gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-39-safety`
  -> 23 passed.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-39-full-final`
  -> 343 passed.
- Full ruff:
  `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Local smoke/browser:
  backend health and frontend root returned 200; `/api/backtest/data-readiness`
  returned `backtest_data_readiness_v1`; in-app browser verified the Backtest
  route selector `backtest-data-readiness` and shell milestone `M23.39 Backtest
  data readiness`.

## Resume Rule

Do not redo the Backtest strategy catalog, run index, comparison packet,
walk-forward runner, Portfolio report index, or provider acquisition gate.
Resume by selecting another concrete residual partial from
`docs/planning/M22_FINAL_NON_LIVE_PARITY_AUDIT.md`, with provider work still
requiring a fresh official-doc provider-entry gate.
