# M21 Tooling Governance Preflight

Date: 2026-05-24

## Scope

This preflight covers the M21 tooling and governance slice for `D:\FinceptLocalTerminal`.
It is not a product-runtime milestone and it does not change any Fincept parity claim by
itself.

## Current State

- Branch: `main`.
- Latest implementation milestone in project state: M20.27.
- Current modified file before M21 edits: `AGENTS.md`.
- Current untracked tooling directory before M21 edits: `.codegraph/`.
- M21 baseline plan: `.omx/plans/ralplan-m21-parity-depth-20260524T093313Z.md`.
- CodeGraph status: available, 95 indexed files, 2654 nodes, 6707 edges.

## Governance Decision

CodeGraph is approved as a repo-local semantic lookup index for the clean-room rebuild.
The `.codegraph/` database is local tooling state. It must not become product state,
runtime artifact state, user data, or a tracked product artifact.

## Actions

- Keep the user-provided `AGENTS.md` CodeGraph rules.
- Add `.codegraph/` to `.gitignore` so the local database is excluded from reviewable
  product artifacts.
- Use CodeGraph before broad repository exploration for architecture, route, call-flow,
  symbol, and impact analysis.
- Treat `D:\FinceptTerminal` as an observation-only source and do not use CodeGraph or
  source inspection on installed Fincept implementation paths.

## Verification Evidence

- `git status --short --branch` showed `AGENTS.md` modified and `.codegraph/`
  untracked before this preflight.
- `git diff -- AGENTS.md` confirmed the user-added CodeGraph governance block.
- `.gitignore` now excludes `.codegraph/`.

## Open Risk

The working tree includes user-owned `AGENTS.md` changes. M21 work must preserve them
and avoid reverting or rewriting that file unless the user explicitly asks.
