# M23.51 Provider Refresh Schedule Plan

Date: 2026-05-27

## Scope

M23.51 closes one lifecycle-supervision gap left by the manual public provider
refresh workflow. It adds a read-only schedule plan so an AI Agent can inspect
which public no-key provider caches are due, stale, missing, or still within TTL
before deciding whether a human-approved manual refresh job is useful.

This is not an automatic scheduler and not a refresh executor.

## Implemented Behavior

- `GET /api/providers/refresh-public/schedule-plan` returns
  `read_only_provider_refresh_schedule_plan`.
- `/api/providers` embeds `refresh_schedule_plan` beside
  `refresh_lifecycle`.
- `/api/providers/cache` and `/api/governance` expose the same read-only plan
  for Settings and diagnostics consumers.
- The plan includes only providers already covered by the manual public no-key
  refresh job and excludes optional-key, paid, private, broker, live, and
  safety-disabled providers.
- Each row exposes provider id, cache id/path, state, retrieved time, age, TTL,
  `seconds_until_due`, `due`, `due_reason`, and the safe manual action id
  `provider_refresh_public_start`.
- Provider Freshness shows compact schedule counts so a human supervisor can see
  due/stale/missing state while watching an AI Agent.
- The AI Agent contract advertises
  `provider_refresh_schedule_plan_inspect` for Settings.
- Command Center provenance now points at this milestone and the action matrix
  includes 65 actions.

## Safety Contract

- Read-only endpoint only.
- No external network call.
- No provider refresh job is started.
- No cache write, repair, stale-job mutation, archive, prune, delete, or restore
  path is added.
- No optional-key provider is included in the schedule plan.
- No secret value is read or returned.
- No broker/exchange binding, order routing, real balance read, margin,
  leverage, short exposure, derivatives execution, payment, subscription,
  cloud sync, Fincept branding/assets/source copying, or live/private behavior
  is enabled.

## Verification

Fresh verification for this milestone is recorded in
`docs/planning/M22_MISSION_LEDGER.md` under the M23.51 verification log.
