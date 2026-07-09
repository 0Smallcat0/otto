# M23 Command Center Preflight Matrix

## Objective

Expose the existing AI Agent action preflight contract as a single Command Center
matrix so an agent or human supervisor can inspect ready, confirmation-required,
and disabled-by-safety actions without probing every action endpoint one by one.

## Implemented Scope

- `GET /api/command-center` now includes
  `route_action_contract.preflight_status_matrix`.
- `GET /api/command-center/preflight-matrix` returns the same read-only matrix
  directly for AI Agent use.
- The Settings Command Center UI exposes selector
  `command-center-preflight-status-matrix`.
- The AI Agent contract advertises `command_center_preflight_matrix` as a
  read-only Settings action.

## Safety Boundary

The matrix is derived from existing action contract metadata only. It does not
execute actions, call providers, write artifacts, approve provider work, read or
return secrets, log request bodies, enable recovery automation, route broker or
exchange actions, read real balances, or enable live/private trading behavior.

## Verification

M23.48 verification is recorded in `docs/planning/M22_MISSION_LEDGER.md` and
`docs/planning/FINAL_HANDOFF.md`.
