# Live Safety Test Spec

Date: 2026-05-22

## Test Objective

Prove that M16 documents and exposes the live-trading safety gate without creating a reachable live execution path.

## Unit Tests

- `live_safety_payload()` returns `disabled_no_safety_contract`.
- Required gates include local secret storage, explicit live-mode opt-in, confirmation gates, audit logs, kill switch, paper/live isolation, static reachability, unit/integration/E2E coverage, and security review.
- Forbidden capabilities stay false for real orders, private API keys, real balance reads, margin, leverage, short exposure, derivatives execution, broker mutation, and external network requirements.
- `disabled_live_action_response()` returns a disabled response for each known live action and for unknown action IDs.

## API Tests

- `GET /api/live-safety` returns 200 with disabled status.
- `POST /api/live-safety/opt-in` returns 403.
- `POST /api/live-safety/store-secret` returns 403.
- `POST /api/live-safety/read-balance` returns 403.
- `POST /api/live-safety/submit-order` returns 403.
- `POST /api/live-safety/enable-margin` returns 403.
- `POST /api/live-safety/enable-leverage` returns 403.
- `POST /api/live-safety/enable-short` returns 403.
- `POST /api/live-safety/execute-derivatives` returns 403.
- Rejected API calls must not create `settings/live_secrets.json`, `artifacts/live/`, live order ledgers, or any live broker state.

## UI Tests

- Settings renders a `Live Safety Contract` region.
- The region shows `disabled_no_safety_contract`.
- Live opt-in and submit-order controls are visible and disabled.
- The UI does not post live actions from disabled controls.

## Isolation Tests

- Existing crypto paper order tests continue passing.
- Paper order submission continues to use the paper broker only.
- Paper state remains under `artifacts/paper/paper_state.json`.
- No live state root is created by safety-surface reads or disabled writes.

## Static Checks

- Source-wall scans continue to block installed source references and secret-like literals.
- `git diff --check` passes, aside from known Git CRLF working-copy warnings.
- No code references `D:\FinceptTerminal\app\scripts` or installed implementation source.

## Future Live Gate

Before any live implementation milestone can start, a separate reviewed PRD and test spec must prove:

- local secret storage design
- explicit live-mode opt-in
- confirmation gates for orders and balance reads
- audit logs and reject logs
- kill switch behavior
- paper/live isolation
- static reachability checks
- unit, integration, and E2E coverage
- code review and security review approval
