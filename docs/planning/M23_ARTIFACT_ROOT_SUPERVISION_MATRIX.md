# M23.24 Artifact Root Supervision Matrix

Date: 2026-05-26

## Scope

M23.24 deepens the local artifact lifecycle surface for AI Agent and human
supervision. It does not add archive, prune, delete, move, restore, automatic
repair, artifact content indexing, provider signup, credential reads, live
trading, broker/exchange binding, or installed Fincept source access.

## Implementation

- `GET /api/artifact-lifecycle` now reports per-root
  `latest_artifact_path`, `supervision_ready`, and `recovery_hint` using file
  names, paths, timestamps, counts, and byte sizes only.
- `GET /api/command-center` now includes
  `artifact_recovery.artifact_root_health_matrix`, with per-root state,
  latest artifact path, supervision readiness, safe actions, lineage support,
  and destructive-action flags.
- Settings Command Center shows root health totals and the first artifact-root
  rows so a human can supervise whether AI Agent artifact paths are reviewable.
- `/api/agent-contract` advertises Settings state
  `artifact_root_health_matrix` and read-only action
  `artifact_lifecycle_root_health`.

## Clean-Room And Safety

- Filesystem inspection remains metadata-only; artifact contents are not read.
- Recovery hints are advisory and non-executing.
- Destructive artifact actions remain disabled.
- No credentials, local-secret values, provider signups, private accounts,
  payment/subscription/CR/cloud paths, broker mutation, real orders, balances,
  margin, leverage, short exposure, derivatives, branding/assets/commercial
  copy, runtime binaries, or installed-source reads are introduced.

## Verification

- Focused artifact-lifecycle/agent/command-center gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m21_artifact_lifecycle.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py -q --basetemp .omx\pytest-tmp\m23-24-focused-initial-rerun`
  -> 12 passed.
- Focused docs/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m21_artifact_lifecycle.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-24-docs`
  -> 16 passed.
- Focused ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\artifact_lifecycle.py src\local_terminal\agent_contract.py src\local_terminal\command_center.py tests\test_m21_artifact_lifecycle.py tests\test_m21_agent_operability_contract.py tests\test_m22_command_center_contract.py`
  -> passed.
- Full backend gate:
  `.\.venv\Scripts\python.exe -m pytest -q --basetemp .omx\pytest-tmp\m23-24-full-final`
  -> 318 passed.
- Full ruff: `.\.venv\Scripts\python.exe -m ruff check .` -> passed.
- Frontend `npm run lint`, `npm run build`, and `npm run e2e` -> passed; build
  kept only the existing Vite chunk-size warning and E2E result was 15 passed.
- Source-wall/live-safety/local-secret/ledger gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_clean_room_source_wall.py tests\test_m16_live_safety.py tests\test_m20_local_secret_gate.py tests\test_m22_mission_ledger.py -q --basetemp .omx\pytest-tmp\m23-24-safety-rerun`
  -> 23 passed.
- FastAPI smoke confirmed artifact lifecycle root readiness fields, Command
  Center M23.24 root health matrix, AI Agent action contract, and no local
  secret-store creation.
- Changed-diff secret scan and `git diff --check` passed.
