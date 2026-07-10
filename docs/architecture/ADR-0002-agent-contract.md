# ADR-0002: Machine-Readable Agent Contract as the Single Operator Surface

Status: Accepted
Date: 2026-07-10 (documents a decision practiced since M24-M26)

## Context

Otto's premise is conversation-as-interface: an AI operator, not a human, drives
the terminal. An agent that scrapes the UI or guesses HTTP endpoints is brittle,
unverifiable, and unsafe — nothing stops it from finding a path the safety review
never considered.

## Decision

All agent operation flows through one typed, versioned contract
(`src/local_terminal/agent_contract.py`, served at `/api/agent-contract`):

- Every route and action declares its endpoint, request/response contract,
  mutation flags, artifact roots, confirmation requirement, safety class, and
  expected error codes.
- The MCP server (`src/local_terminal/mcp_server.py`) derives its tool surface
  from this contract at runtime and **refuses** any action that is
  safety-disabled or touches local secrets. New endpoints are unreachable by
  agents until they are contractually declared.
- The frontend capability catalog and the Command Center preflight matrix are
  generated from the same contract, so human documentation cannot drift from
  what agents can actually do.
- The agent-operability eval suite (`evals/`) grades agents against contract
  promises (artifact paths, state endpoints), making the contract testable in
  both directions: the app must honor it, and agents must be able to follow it.

## Consequences

- Adding a feature means declaring it; the contract diff *is* the operator
  changelog, and contract tests (113+ actions) gate regressions.
- Safety gating is structural, not behavioral: live trading and secret entry
  are absent from the operable surface rather than merely discouraged.
- The contract adds boilerplate per endpoint; accepted as the cost of a
  verifiable operator surface.
