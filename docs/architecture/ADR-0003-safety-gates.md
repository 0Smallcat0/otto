# ADR-0003: Structural Safety Gates for an AI-Operated Trading Surface

Status: Accepted
Date: 2026-07-10 (documents the boundary enforced since project start)

## Context

An AI agent with tool access to a financial terminal is a hazard if any tool can
reach real money, real credentials, or destructive state loss. Prompt-level
rules ("please don't trade live") are not a safety mechanism.

## Decision

Safety is enforced by construction, in layers that an agent cannot talk its way
past:

1. **No live execution paths exist.** Order flow terminates in a local paper
   ledger. There is no code path that signs or transmits a real order; live
   parity requires a separate reviewed safety contract before it may be built.
2. **Secrets never transit the agent surface.** Optional data-provider keys are
   sealed locally (Windows DPAPI); the MCP server refuses secret-class actions,
   so keys cannot be read or written through agent tools.
3. **Destructive actions require explicit confirmation flags** declared in the
   agent contract (e.g. paper-account reset), turning "are you sure" into a
   typed protocol step instead of UI copy.
4. **State mutations are recoverable.** Protected state files keep rotating
   backups; artifact lifecycle actions are metadata-only plans, never deletes.
5. **The eval suite regression-tests refusal.** Safety-category tasks assert
   that gated requests leave state unchanged, so a gate that silently weakens
   fails the benchmark.

## Consequences

- The agent can be given broad autonomy (full watchlist/portfolio/backtest
  control) because the blast radius is bounded by construction.
- Live trading, if ever built, arrives as a new reviewed contract with opt-in,
  kill-switch, and audit requirements — not as a flag flip.
