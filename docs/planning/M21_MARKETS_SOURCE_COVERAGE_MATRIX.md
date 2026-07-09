# M21 Markets Source Coverage Matrix

Date: 2026-05-25

## Purpose

M21.20 creates a provider-entry/source-state contract for the Markets route before
adding another data adapter. The goal is to make existing non-crypto provider
lanes inspectable by an AI Agent across asset family, runtime role, provider ID,
auth mode, cache state, TTL, docs URL, quote semantics, gated reason, safe action
ID, and next safe action.

## Scope

- Add `source_coverage_matrix` to `/api/markets`.
- Cover Stocks, ETF, FX, Commodities, Indexes, Regional, and Bonds/Rates.
- Expose public no-key, optional-local-key, reference-only, not-quote, and
  quote-not-orderable distinctions explicitly.
- Add the matrix to Markets AI Agent route state and refresh action response
  contracts.
- Add a dense Markets Provider Entry Gate table with stable
  `markets-source-coverage-*` selectors.

## Non-Goals

- No new provider adapter.
- No provider signup, key acquisition, key entry, or secret persistence.
- No paid/bulk quote provider.
- No broker/exchange key flow, real balance read, order path, margin, leverage,
  short exposure, derivatives, or live trading control.
- No Fincept branding, commercial copy, installed-source read, or copied assets.
- No fixture/default/offline data as the primary user-visible runtime.

## Contract

Each matrix row includes:

- `asset_family`
- `runtime_role`
- `provider_id`
- `auth_mode`
- `state`
- `cache_path`
- `retrieved_at`
- `row_count`
- `freshness_ttl_seconds`
- `docs_url`
- `quote_semantics`
- `gated_reason`
- `safe_action_id`
- `next_safe_action`

`quote_semantics` is intentionally limited to `reference_only`,
`quote_not_orderable`, or `not_quote` so AI Agents do not treat macro, filings,
fundamentals, FX reference rates, commodity monthly reference prices, or energy
context as executable quotes.

## Verification Plan

- Backend matrix shape/cache/safety tests.
- Agent contract tests for route state and action response contracts.
- Source-wall and live-safety tests.
- Frontend lint/build/E2E with a Markets screenshot.
- Visual verdict for the dense Provider Entry Gate panel.
- Secret scan and `git diff --check`.
