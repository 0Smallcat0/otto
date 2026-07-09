# M21.8 Artifact Archive Plan

Date: 2026-05-24

## Selected Slice

M21.8 deepens the existing artifact lifecycle route by adding a non-destructive
archive/prune planning workflow for AI Agent operation.

The workflow writes a local plan bundle under
`artifacts/diagnostics/artifact-lifecycle-plan-*` from metadata only. It does not
move, delete, archive, prune, restore, read file contents, scan secrets, call
network providers, or touch installed Fincept source.

## Clean-Room Evidence

- M21 gap report identified artifact lifecycle/prune/archive/recovery as a cross-route gap.
- M20.19 and M21.1 intentionally left destructive prune/archive/delete disabled.
- Current Fincept parity target is dense local terminal workflow depth, not branding
  or implementation copying.

## Product Contract

- `GET /api/artifact-lifecycle` remains metadata inventory.
- `POST /api/artifact-lifecycle/archive-plan` writes a local plan bundle.
- Candidate rows include artifact root id, path, route ownership, file counts, bytes,
  newest metadata timestamp, age, proposed action, reasons, and manual-review flag.
- Proposed actions are advisory only: `archive_candidate`, `monitor`, `no_action`, or
  `blocked`.
- Real archive/prune/delete/recover execution remains disabled.
- Settings exposes a `WRITE ARCHIVE PLAN` command and shows the latest run, manifest,
  candidate count, and disabled mutation state.
- The AI Agent contract exposes `artifact_lifecycle_archive_plan` as a local
  artifact-writing, non-destructive action.

## Safety Boundary

- No file contents are read into the plan.
- No artifact roots are mutated.
- No files are moved or deleted.
- No credentials, provider keys, broker keys, private data, or live trading controls
  are requested or returned.
- No external network calls are made.
- No Fincept installed source, assets, branding, or commercial copy are read or copied.

## Verification

- Focused artifact lifecycle and agent-contract tests:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m21_artifact_lifecycle.py tests\test_m21_agent_operability_contract.py -q`
- Ruff:
  `.\.venv\Scripts\python.exe -m ruff check src\local_terminal\artifact_lifecycle.py src\local_terminal\server.py src\local_terminal\governance.py src\local_terminal\support.py src\local_terminal\agent_contract.py tests\test_m21_artifact_lifecycle.py`
- Frontend lint/build:
  `npm run lint`
  `npm run build`
- Full QA and browser evidence are recorded in `PROJECT_STATE.md` and
  `docs/planning/FINAL_HANDOFF.md` after the verification sweep.
