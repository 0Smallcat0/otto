# M21.4 Agent Operability Contract

Date: 2026-05-24

## Scope

M21.4 adds a read-only machine-operable contract for the local terminal. The goal is
to let an AI Agent navigate, inspect, and safely operate local workflows with stable
route selectors, API endpoints, action contracts, artifact outputs, and error
recovery rules.

This is not a new provider, not a cloud account layer, not a subscription surface,
and not live trading. It is a local contract over existing clean-room workflows.

## Sanitized Fincept Observation

- `route`: Dashboard and advanced workflow routes, especially QuantLib.
- `source_evidence`: live installed-app UI Automation observation plus existing
  sanitized reference logs under `docs/reference/fincept-platform-test/`.
- `observation_time`: 2026-05-24.
- `navigation_path`: locked terminal -> local unlock -> commercial/account-like gate
  -> no-payment/free continuation -> route rail -> Dashboard -> advanced route rail.
- `interaction_steps`: selected advanced route buttons and inspected the resulting
  route-level control tree.
- `state_transitions`: locked, gated/account-like commercial surface, active local
  route shell, Dashboard live/status header, QuantLib module/calculation surface.
- `inputs`: previously authorized unlock PIN was used through UI Automation only;
  it was not echoed, saved, screenshotted, logged to artifacts, or committed.
- `outputs`: text-only sanitized notes. No Fincept screenshot was retained for this
  slice because account/commercial toolbar content was visible.
- `errors_or_empty_states`: commercial plan/payment mechanics and account/credit
  status were visible and are explicitly excluded from the local build.
- `data_sources_visible`: route rail, status header, News intel strip, QuantLib
  module tree and request/results panels. Brand/account/commercial details are not
  retained.
- `artifact_or_export_behavior`: no source or runtime files were inspected.
- `terminal_density_notes`: dense horizontal route rail, compact status/header rows,
  command strip, module tree, and side-by-side request/results panels.
- `panel_structure_notes`: advanced workflows favor explicit module/action selectors,
  JSON-like request bodies, result panels, and disabled/gated actions.
- `agent_operable_contract`: local implementation should expose stable selectors,
  machine-readable route/action/error contracts, artifact paths, and disabled safety
  gates so an AI Agent does not infer behavior from screenshots.
- `clean_room_exclusions`: no installed source, assets, branding, pricing copy,
  account identity, credit/subscription mechanics, runtime binaries, payment flow,
  credentials, or personal data.
- `local_gap`: advanced workflows already have local APIs, but agents lacked a
  consolidated contract describing which actions are safe, which are disabled, where
  artifacts appear, and which selectors are stable.
- `verification_plan`: `/api/agent-contract`, governance diagnostics bundle,
  Settings UI panel, Playwright selector checks, source-wall/live-safety tests,
  secret scan, and code-review gate.

## Product Contract

Add `GET /api/agent-contract` with:

- all 15 shell routes and their primary endpoints
- stable route-button and workspace selectors
- recommended safe local actions
- disabled safety-gated actions
- advanced workflow action contracts for AI Chat, Nodes, Code, Quant Lab, QuantLib,
  Backtest, Algo, and Settings diagnostics
- optional data-provider secret setup is represented as a confirmation-required
  local-only action, not as an autonomous agent credential step
- artifact roots and output contracts
- clear error catalog with recovery guidance
- sanitized observation evidence flags
- safety flags proving read-only contract behavior

Expose the same payload through Governance and diagnostics so an AI Agent can fetch
one settings/governance state and discover local workflow contracts.

M23.8 extends this contract with read-only action preflight discovery:

- `GET /api/agent-actions/{action_id}/preflight`
- Agent Contract top-level `preflight` metadata
- per-action readiness status: `ready`, `requires_confirmation`,
  `disabled_by_safety`, or `unknown_action`
- method, endpoint, request/response/output contract, safety class, expected
  error codes, local mutation flag, artifact-write flag, confirmation flag, and
  stop gates before an Agent attempts an action

The preflight endpoint does not execute the action, write artifacts, call
providers, read secrets, or mutate local state.

## Safety

- The contract endpoint is read-only.
- It does not read artifact contents.
- It does not create, prune, archive, delete, recover, or upload artifacts.
- It does not return secret values.
- It does not enable external network calls, code execution, live orders, broker
  mutation, real balance reads, margin, leverage, short exposure, or derivatives
  execution.
- It does not copy Fincept branding, commercial copy, assets, source, or binaries.

## Verification

Expected focused gate:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_m21_agent_operability_contract.py tests\test_m19_governance_routes.py tests\test_m21_artifact_lifecycle.py -q
```

Full gate remains the M21 standard: full pytest, ruff, frontend lint/build/e2e,
browser evidence, source-wall/live-safety tests, secret scan, diff check, and
code-review gate.
