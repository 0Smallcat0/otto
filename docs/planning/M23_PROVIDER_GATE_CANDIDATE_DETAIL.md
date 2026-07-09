# M23.43 Provider Gate Candidate Detail

## Scope

M23.43 makes the existing provider acquisition gate more usable for AI Agent
supervision by exposing candidate-level provider rows in the Settings Command
Center panel. The backend already returned `candidates`, `rules`, and
`stop_gates`; this slice wires those fields into the frontend type contract and
human-visible command-center rows without changing provider behavior.

## Completed Behavior

- Command Center current milestone now points to
  `M23.43 Provider gate candidate detail`.
- `CommandCenterProviderAcquisitionGate` includes candidate, rule, and stop-gate
  fields that match `/api/provider-acquisition-gate`.
- Settings Command Center shows a compact provider-gate candidate list with
  blocked candidates first.
- Stable selectors expose individual candidate rows, including
  `command-center-provider-gate-candidate-iex_tops_market_data_gate` and
  `command-center-provider-gate-candidate-cboe_delayed_quotes_gate`.
- Playwright coverage verifies that IEX remains visible as
  `blocked_official_terms`, `subscriber_agreement_required`, and
  `quote_blocked_by_terms`.

## Boundaries

- No provider adapter, cache, endpoint, source coverage row, refresh job, signup,
  credential flow, agreement acceptance, or external fetch was added.
- No Fincept branding, assets, commercial copy, runtime binaries, or installed
  source were read or copied.
- Live trading, broker/exchange binding, real balances, real orders, margin,
  leverage, short exposure, derivatives, payment, subscription, CR/credits,
  cloud sync, and destructive artifact actions remain disabled or excluded.

## Verification

Verification evidence is recorded in `docs/planning/M22_MISSION_LEDGER.md` under
the M23.43 verification log and in `PROJECT_STATE.md`.
