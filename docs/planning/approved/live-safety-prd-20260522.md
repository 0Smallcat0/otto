# Live Safety PRD

Date: 2026-05-22

## Purpose

M16 defines the safety contract that must exist before any local live-trading parity path can become reachable. This milestone is a contract and gated-surface milestone only: no reachable live execution code is added, no broker adapter is added, no private API credential flow is enabled, and no real account balance is read.

## Authority

1. `AGENTS.md`
2. `docs/planning/approved/prd-fincept-local-terminal-longrun-20260522.md`
3. `docs/planning/approved/test-spec-fincept-local-terminal-longrun-20260522.md`
4. `docs/planning/approved/execution-plan-fincept-local-terminal-longrun-20260522.md`
5. `docs/reference/` evidence and safe UI observation

## User Need

The local terminal should eventually expose live trading parity without confusing it with paper trading. Until safety is independently implemented and reviewed, the product must show that live mode is unavailable and explain the missing gates in local, non-brand-specific language.

## M16 Scope

- Add a read-only safety payload that reports live mode as disabled.
- Add a Settings surface that shows the live safety contract, required gates, blocked capabilities, and disabled actions.
- Add disabled backend endpoints for live opt-in, private API storage, real balance read, real order submission, margin, leverage, short exposure, and derivatives execution.
- Add tests proving disabled endpoints return rejection responses and do not create live artifacts or secret-storage files.
- Add this PRD and the companion test spec as the future implementation gate.

## Out Of Scope

- Real order submission.
- Private API credential persistence.
- Real balance reads.
- Margin, leverage, short exposure, or derivatives execution.
- Broker adapters, exchange SDK integration, live order routers, or background live workers.
- Any cloud account, subscription, billing, credit, or managed-account requirement.

## Required Future Gates

Every gate below must pass before any live path becomes reachable:

- local secret storage design with local-only encryption or OS-backed storage decision record
- explicit live-mode opt-in that cannot be triggered accidentally or by import
- confirmation gates for order submission and balance reads
- audit logs and reject logs with redaction rules
- kill switch behavior that defaults to engaged and can block all live actions
- paper/live isolation with separate state roots, order routers, ledgers, and tests
- static reachability checks that prove disabled surfaces cannot bypass the safety layer
- unit, integration, and E2E coverage for every live entry point
- code review and security review approval

## Acceptance Criteria

- `/api/live-safety` returns `disabled_no_safety_contract`.
- The payload reports `contract_reviewed=false`, `security_reviewed=false`, `live_mode_enabled=false`, and `paper_mode_enabled=true`.
- All required gates are present and marked missing.
- Every forbidden capability is reported as false.
- Disabled live endpoints return 403 and do not write live or secret artifacts.
- The Settings UI renders the disabled live safety surface and disabled action controls.
- Paper trading remains usable and isolated from the live safety surface.

## Future Implementation Warning

Do not change any disabled live endpoint into a working endpoint in a mixed feature milestone. Live trading requires a separate PRD/test-spec implementation milestone with explicit safety review, security review, and paper/live isolation evidence.
