# M23.38 Provider Acquisition Resume Contract

Date: 2026-05-26

## Scope

M23.38 makes the provider-acquisition gate explicit about post-M23.37 resume
behavior. After the FMP quote lane, `GET /api/provider-acquisition-gate` has no
approved next candidate: all recorded candidates are either implemented or
blocked by a reviewed gate. This slice exposes that state as a machine-readable
resume contract so AI Agents do not stall, retry blocked candidates, or add
provider adapters without a fresh provider-entry research step.

## Product Behavior

- `GET /api/provider-acquisition-gate` now includes `resume_contract`.
- `summary.resume_state` reports `backlog_exhausted_needs_research` when no
  approved candidate remains.
- `summary.implementation_allowed=false` and
  `summary.requires_official_research=true` tell agents that the next safe step
  is research, not implementation.
- `GET /api/command-center` embeds the same provider-acquisition gate and adds
  an activity-timeline event for provider backlog state.
- The Command Center UI exposes a Provider Gate panel with candidate counts,
  next safe step, and the anti-stall rule.

## Non-Goals

- No provider adapter, signup flow, payment, provider account access, API key
  collection, public refresh job, or external network call.
- No live trading, broker/exchange binding, real balances, order routing,
  margin, leverage, short exposure, derivatives, cloud sync, or destructive
  artifact lifecycle action.
- No Fincept branding, assets, commercial copy, installed-source read, or
  runtime binary use.

## Verification Plan

- Focused provider/command-center tests prove the resume contract and UI-facing
  payload.
- Frontend lint/build/e2e prove the Command Center panel remains usable.
- Source-wall, live-safety, local-secret, and provider gate tests prove safety
  boundaries stay intact.
- Secret scans verify no credential-like literal was added.

## Handoff

Future provider work must first add or update a provider-entry candidate with
official docs, auth mode, route need, cache policy, quote semantics, and stop
gates. Only then should implementation start.
