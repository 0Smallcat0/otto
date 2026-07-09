# ADR-0001: Local Web App Stack

Status: Accepted
Date: 2026-05-22

## Context

M1 must choose the foundation before product implementation. The app needs local
workflow parity with the observed terminal shape, browser and Playwright verification,
local storage, public read-only data adapters, paper-first execution, and future gated
live-trading safety work.

The repo already has Python contracts and tests. Node and npm are available locally.

## Decision

Use a local web app stack:

- Backend: Python 3.12, FastAPI, Uvicorn.
- Frontend: React, TypeScript, Vite.
- Runtime split: backend serves local APIs and domain services; frontend owns the
  terminal shell and route/workspace UI.
- Verification: pytest and ruff for Python, TypeScript build for frontend, Playwright
  and browser checks after route UI exists.

M1 adds only a minimal boot path. Route implementation starts in M2.

## Scored Options

Scores are 1 to 5, where 5 is strongest.

| Option | Delivery speed | UI/workflow parity | Local runtime | Testability | Packaging path | Maintainability | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| FastAPI + React/TypeScript/Vite | 4 | 5 | 5 | 5 | 4 | 4 | 27 |
| FastAPI + Jinja/static HTML | 5 | 3 | 5 | 4 | 5 | 4 | 26 |
| PySide/Qt desktop app | 3 | 5 | 5 | 3 | 3 | 3 | 22 |
| Single-process Python stdlib HTTP | 4 | 2 | 5 | 3 | 5 | 3 | 22 |

## Rejected Alternatives

- FastAPI + Jinja/static HTML: good for a small local dashboard, but the observed terminal
  shape needs dense route/workspace state, modals, quick switch, panels, and repeated
  browser-based visual checks.
- PySide/Qt desktop app: closest to native terminal feel, but slower to test and automate
  with Playwright/browser workflows.
- Single-process Python stdlib HTTP: useful for a smoke server, but would defer too much
  structure and make later API/frontend separation harder.
- Reuse `D:\Crypto-Trading`: explicitly forbidden by the project contract.

## Consequences

- Frontend package scripts are part of M1.
- Backend APIs must remain local and safe by default.
- Development uses two local processes until packaging is designed.
- No live trading path is introduced by this decision.

## M1 Verification

- Backend health endpoint starts on localhost.
- Frontend build succeeds.
- Existing pytest and ruff gates continue to pass.
- No product routes are implemented beyond foundation status surfaces.
