# M22 Advanced Workflow Output Packet

Date: 2026-05-25

## Scope

M22.8 adds a metadata-only output packet for the advanced local workflow routes:
AI Chat, Nodes, Code, Quant Lab, and QuantLib.

The packet is not an execution runtime. It does not run notebooks, execute Nodes,
call managed LLMs, invoke external QuantLib runtimes, read artifact contents, call
providers, mutate route output roots, or enable live/private trading behavior.

## Product Behavior

- `GET /api/advanced-workflows/output-packet` returns a read-only packet over the
  five advanced routes.
- `POST /api/advanced-workflows/output-packet` writes
  `advanced_output_packet.json`, `manifest.json`, `advanced_output_packet.md`, and
  `error.log` under `artifacts/diagnostics/advanced-output-packet-*`.
- The packet lists each route's artifact root, latest local output artifact
  metadata, safe local output action, blocked runtime actions, and recovery queue
  entries for routes that do not yet have local output artifacts.
- Command Center now exposes an `advanced_outputs` supervision section and a
  `PACKET` action for human-visible AI Agent output auditing.
- The AI Agent contract advertises the Settings action
  `advanced_workflow_output_packet`.

## Safety Contract

- Metadata-only filesystem inspection.
- No artifact content reads or content copying.
- No execution, script runtime, kernel process, managed LLM call, external
  network call, provider signup, credential handling, or secret value return.
- No route output mutation beyond the diagnostics packet write.
- No live trading, broker/exchange binding, real balances, real orders, margin,
  leverage, short exposure, derivatives, payment, subscription, CR/credits, cloud
  sync, Fincept branding/assets/source copying, or installed-source reads.

## Verification

- Focused backend contract tests cover packet write behavior, Command Center
  supervision payload, and AI Agent action discovery.
- Frontend type lint covers the new Command Center section.
- Broader safety gates remain mandatory before the milestone is complete in the
  mission ledger.
