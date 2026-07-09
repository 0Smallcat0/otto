# Execution Plan: Fincept Local Terminal Longrun

Status: Approved by RALPLAN Critic.

## RALPLAN-DR Summary

Principles:

- Clean-room parity from observed behavior and independent implementation.
- `AGENTS.md` controls conflicts.
- Local-first storage and artifacts.
- Safety-gated execution.
- Small reviewable milestones.

Decision drivers:

- Avoid legal/clean-room contamination.
- Deliver useful terminal workflow parity.
- Keep long-running `/goal` execution verifiable.

Options:

- Option A: broad visual shell first. Fast visual feedback, higher hollow-page risk.
- Option B: contract-locked shell plus high-value workspaces. Recommended.
- Option C: domain engines first. Strong logic, delayed terminal parity.
- Option D: reuse `D:\Crypto-Trading`. Invalid by contract.

Pre-mortem:

- Hollow UI: require first-use states and evidence.
- Stale-doc drift: M0 scans and patches/quarantines conflicts.
- Live leakage: live safety PRD/test spec before any reachable path.

## Milestones

### M0: Governance, Source Wall, And Stale-Doc Correction

DoD:

- Current `AGENTS.md` policy update is committed if still uncommitted.
- Active docs no longer direct implementation to `D:\Crypto-Trading`.
- `FINCEPT_TO_CRYPTO_TRADING_HANDOFF.md` is clearly inactive.
- Public read-only runtime data preference and test/offline fixture policy are documented.
- Live parity is documented as gated by a separate safety contract.
- Executable clean-room/source-wall gate exists.
- No product implementation is mixed into this governance commit.

Minimum docs to inspect/patch:

- `LOCAL_TERMINAL_ENGINEERING_SPEC.md`
- `LOCAL_VERSION_IMPLEMENTATION_BACKLOG.md`
- `COVERAGE_AUDIT.md`
- `EVIDENCE_INDEX.md`
- `PLATFORM_RESEARCH_COMPLETION_AUDIT.md`
- `PLATFORM_TEST_REPORT.md`
- `LOCAL_VERSION_BLUEPRINT.md`

### M1: Foundation And Technology Decision

DoD:

- Stack ADR exists with scored criteria and rejected alternatives.
- Local app starts with localhost URL or equivalent local app entry.
- Existing Python tests/lint still pass.
- Frontend package scripts exist if frontend is added.

### M2: Shell, Menus, Layouts, Settings, Profile

DoD:

- All 15 routes open.
- Each route has a working first-use state or explicit local disabled/gated state.
- File/Navigate/View/Help menus work.
- Quick Switch exists.
- Layout/settings/profile save locally.
- Browser/playwright smoke and screenshots pass.

### M3: Dashboard

DoD:

- Account summary, positions, orders/fills, signals, data freshness, market pulse, alerts, widgets, layout save/reset work from local/public/paper state.
- Widget catalog/filter and notification drawer work.
- Screenshot and semantic visual-verdict evidence captured.

### M4: Markets Public Data And Watchlists

DoD:

- Public read-only crypto data works when network is available.
- Cache/offline fallback is deterministic and visibly stale.
- Panels, add-to-column, columns, edit, and delete confirmation work.
- No private API required.

### M5: Crypto Paper Workspace

DoD:

- Public market panels and paper order ticket work.
- Positions, orders, history, trades, fees, depth, market, stats are usable.
- Paper orders/fills/account snapshots write local artifacts.
- Safety tests prove no real order, no private API, no oversell, no negative cash/position, no short/margin/leverage/derivatives.

### M6: Backtest Workspace

DoD:

- At least one local strategy runs with closed-candle public data.
- Artifacts: `config.json`, `data_snapshot.json`, `summary.json`, `trades.csv`, `report.md`.
- Tests prove no lookahead and no same-candle fill.

### M7: Portfolio Workspace

DoD:

- Create/import/demo/export work.
- Portfolio can link paper/backtest artifacts.
- Portfolio cannot bypass order gates.

### M8: P1 Workbench Tools

DoD:

- News filters and feed source work.
- AI Chat local sessions and safe provider config work.
- Algo strategy definition and backtest-from-strategy work.
- Nodes canvas/template/library/import/export work with dry-run only.
- Code notebook open/save/add-cell/sidebar works; execution is disabled until sandbox policy.

### M9: Quant Lab, QuantLib, Forum, Help, Diagnostics

DoD:

- Quant Lab catalog uses normalized evidence.
- QuantLib local presets write request/response artifacts.
- Forum is local research journal.
- Help/About/diagnostics use local copy and no Fincept brand.

### M10: Live Trading Safety Contract

DoD:

- Separate live safety PRD/test spec exists and is reviewed.
- No reachable live execution code is added in this milestone.

### M11: Full QA, Visual Parity, Deslop, Final Handoff

DoD:

- Full backend/frontend/e2e gates pass or gaps are documented.
- Route screenshot evidence exists.
- Code review blockers are fixed.
- `$ai-slop-cleaner` is used only on changed files after behavior is locked.
- Final handoff is complete.

## Skill Strategy

- `/goal`: long-running execution after plan acceptance.
- `$ultraqa`: milestone QA loops.
- `$code-review`: before milestone commits; fix CRITICAL/HIGH/BLOCK.
- `browser:browser` and Playwright: localhost UI verification.
- `$visual-verdict`: semantic route-level visual comparison.
- `$analyze`: read-only diagnosis only when blocked or causal explanation is needed.
- Ask Claude/Gemini: second-opinion reviewer/critic only.
- `$ai-slop-cleaner`: changed-files cleanup after functionality and tests exist.
- `karpathy-guidelines`: constrain implementation to minimal, testable, non-speculative changes.

## Follow-Up Staffing

Available roles:

- explore
- researcher
- dependency-expert
- planner
- architect
- critic
- executor
- test-engineer
- verifier
- code-reviewer
- security-reviewer
- designer
- qa-tester
- build-fixer
- code-simplifier
- writer

Ralph path:

- Ralph/leader owns sequencing, integration, verification, commits.
- explore maps route evidence before each workspace.
- dependency-expert/researcher supports stack and public data adapter decisions.
- executor implements bounded slices.
- test-engineer/verifier proves gates.
- code-reviewer/security-reviewer review milestones.
- designer/visual-verdict checks UI parity.
- code-simplifier/ai-slop-cleaner cleans only changed files after tests lock behavior.

Team path, only in attached OMX tmux runtime:

- Shell/UI worker
- Domain/runtime worker
- Test/QA worker
- Evidence/visual worker
- Security/clean-room reviewer

Team verification path:

- Team proves tests, screenshots, artifacts, and clean-room checks.
- Ralph/leader verifies integrated tree and commits.

## Master `/goal` Prompt

```text
/goal
In D:\FinceptLocalTerminal, autonomously build the clean-room local self-use Fincept Terminal functional/workflow parity app from the approved ralplan PRD/test spec/milestone plan.

Authority:
1. AGENTS.md
2. docs/planning/approved PRD/test spec/milestone plan
3. docs/reference evidence and safe live Fincept UI observation
4. older planning/spec docs only where non-conflicting

Do not read, copy, port, or adapt D:\FinceptTerminal\app\scripts or installed package implementation source. Do not use D:\Crypto-Trading or FINCEPT_TO_CRYPTO_TRADING_HANDOFF.md as this repo roadmap. Do not include secrets, account email, PIN, tokens, private keys, or personal data in repo files, logs, screenshots metadata, commits, or handoffs.

Build sequence:
M0 governance/stale-doc correction -> M1 foundation/tech decision -> M2 shell/menus/layouts/settings/profile -> M3 dashboard -> M4 markets public data/watchlists -> M5 crypto paper workspace -> M6 backtest -> M7 portfolio -> M8 News/AI Chat/Algo/Nodes/Code -> M9 Quant Lab/QuantLib/Forum/Help/Diagnostics -> M10 live safety contract only -> M11 full QA/visual/deslop/final handoff.

For every milestone:
- read the relevant docs/reference evidence before implementation;
- use safe live Fincept observation only when evidence is insufficient;
- implement the smallest useful working slice, not placeholders;
- keep runtime public/read-only data preferred, using fixtures/cache only for tests/offline fallback;
- keep unsafe live capabilities disabled/gated until the dedicated safety contract exists;
- run tests/lint/build/e2e appropriate to the milestone;
- capture UI screenshot or JSON artifact evidence;
- redact account/email/CR regions and avoid screenshot metadata secrets before committing evidence;
- use browser:browser, playwright, visual-verdict, ultraqa, code-review, analyze, and ai-slop-cleaner according to the plan;
- update project state/handoff;
- commit with Lore protocol and Co-authored-by trailer.

Stop only for destructive, paid, credential-gated, real-trading, legal/product-boundary-changing, or authority-missing decisions.
```

## Review Record

- Planner lane: recommended Option B.
- Architect lane: WATCH; required broader stale-doc scan, broader source-wall gate, semantic visual-verdict, tech ADR criteria, and M2 first-use/gated clarification.
- Critic lane: APPROVE after Architect improvements; suggested executable source-wall gate, raw-evidence conflict rule, and screenshot redaction/metadata rule. These suggestions are incorporated in final plan artifacts.
