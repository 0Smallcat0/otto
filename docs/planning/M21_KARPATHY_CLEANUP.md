# M21.22-M21.23 Karpathy Cleanup

Date: 2026-05-25

## Scope

M21.22 and M21.23 are behavior-preserving cleanup/refactor slices for the current M0-M21 local Fincept-like terminal implementation. They reduce frontend complexity without changing product behavior, provider semantics, route contracts, visible workflow, or clean-room/live-safety boundaries.

## Completed Cleanup

### M21.22

- Moved the Markets workspace implementation to `frontend/src/components/markets/MarketsWorkspace.tsx` to avoid Windows case conflicts with the new `markets/` folder.
- Extracted Markets source-state panels into:
  - `frontend/src/components/markets/SourceCoverageMatrixPanel.tsx`
  - `frontend/src/components/markets/ProviderStackPanel.tsx`
  - `frontend/src/components/markets/SourceContractPanel.tsx`
  - `frontend/src/components/markets/sourceCoverage.ts`
  - `frontend/src/components/markets/marketText.ts`
- Extracted low-churn frontend contracts into `frontend/src/types/markets.ts` and `frontend/src/types/researchLoop.ts`.
- Preserved `frontend/src/types.ts` re-exports so existing imports keep working.
- Added source-row hash regression coverage for Markets source contract fields.
- Hardened Algo initial-load behavior so stale `/api/algo` responses cannot overwrite a user-edited draft.
- Tightened existing Playwright selectors/waits for Dashboard offline fallback, Crypto paper-order status variance, and Algo form editing.

### M21.23

- Extracted provider freshness, governance, artifact lifecycle, local-secret status, profile usage, and AI Agent contract TypeScript types into `frontend/src/types/governance.ts`.
- Extracted live-safety TypeScript types into `frontend/src/types/liveSafety.ts`.
- Preserved `frontend/src/types.ts` as the compatibility barrel so existing `../types` imports keep working.
- Kept the slice type-only: no API path, backend route, payload field, data-testid selector, panel order, provider behavior, local-secret behavior, live-safety behavior, visible workflow, or CSS changed.

## Non-Goals

- No provider adapter or provider expansion.
- No UI redesign or visual parity sweep.
- No server, storage, or agent-contract broad rewrite.
- No Fincept branding, assets, commercial copy, runtime binaries, billing, subscription, CR/credits, cloud-account behavior, or installed-source copying.
- No credentials, key acquisition, account creation, provider signup, or secret storage changes.
- No real orders, broker/exchange key flows, real balances, margin, leverage, short exposure, derivatives execution, live deployment, optimize/live controls, or destructive artifact lifecycle actions.

## Verification

### M21.23

- Frontend type compatibility gate: passed.
- Frontend build: passed.
- Frontend E2E: 15 passed.
- Full backend pytest: 255 passed.
- Source-wall/live-safety: 12 passed.
- Ruff: passed.
- Changed-file secret scan: schema field-name matches only; no credential values, provider keys, bearer tokens, PIN assignments, or private key blocks.
- `git diff --check`: passed with Git CRLF warnings only.
- Code-review gate: APPROVE, no unresolved findings.
- Browser screenshot and visual-verdict were skipped because this was a type-only cleanup with no visible UI workflow, selector, CSS, or layout change.

### M21.22

- Focused regression gate: 51 passed.
- Full backend pytest: 255 passed.
- Source-wall/live-safety: 12 passed.
- Ruff: passed.
- Frontend lint/build/e2e: passed; E2E result was 15 passed.
- Changed-file secret scan: zero credential-like matches.
- `git diff --check`: passed with Git CRLF warnings only.
- Code-review gate: APPROVE, architecture CLEAR.

## Handoff

Future provider or Markets route work should extend the extracted Markets source-state modules instead of adding route-local source tables back into `MarketsWorkspace.tsx`. Larger cleanup targets such as `server.py`, `storage.py`, and `agent_contract.py` remain valid future slices, but should be split into separate behavior-locked refactor goals.
