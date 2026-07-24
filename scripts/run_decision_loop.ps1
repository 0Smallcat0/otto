# Daily paper decision-loop runner (owner cadence: run continuously, keep a
# real performance series). Registers nothing by itself — see the bottom for
# the one-line Task Scheduler registration the owner can run when ready.
#
# What one run does: ensure the backend is up, then drive one full cycle
# headlessly through Claude Code so the judgment step is a real agent run:
# refresh -> read all three books -> news packet -> reasoned orders with
# rationale -> process resting orders -> snapshot -> history readback.

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot

# 1) Backend up (idempotent: bind error just means it is already running).
$listening = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if (-not $listening) {
    Start-Process -FilePath (Join-Path $repo ".venv\Scripts\python.exe") `
        -ArgumentList "-m", "otto.local_terminal" -WorkingDirectory $repo -WindowStyle Hidden
    Start-Sleep -Seconds 6
}

# 2) One headless agent run of the full loop.
$prompt = @'
Run one full paper decision cycle against the local Otto terminal at
http://127.0.0.1:8765 (paper-only; live execution is structurally disabled).

Position discipline (adopted 2026-07-24 after the TW book lost to 0050 on
an oversized single name): no single position above 40% of its book's
equity; resize oversized positions in staged tranches of at most ~10% of
book equity per run; new positions at most 10% of book equity per entry;
on books without stop orders (TW) selling IS the risk tool — dose it in
proportion to the stated concern, token trims are not discipline.

1. POST /api/crypto/refresh {"view":"summary"} and read the crypto book.
2. GET /api/equity/summary?refresh=true and /api/equity/tw/summary?refresh=true;
   compute each position's weight against the 40% cap.
3. POST /api/news/packet with the symbols the three books hold.
4. Judge from what you actually read plus the discipline rules; every order
   carries a rationale prefixed "loop YYYY-MM-DD#N:" that shows the weight
   arithmetic. Then POST /api/crypto/orders/process,
   /api/equity/orders/process, and /api/equity/tw/orders/process so
   resting orders can fill.
5. POST /api/paper/snapshot {"refresh":true,"note":"loop YYYY-MM-DD#N"}.
6. GET /api/paper/history?limit=30 and report each book's window change vs
   the benchmarks. If any data or behavior problem appears, fix it in the
   same run instead of only reporting it.
'@

claude -p $prompt --max-turns 40

# --- One-time registration (owner runs this once, at their own decision): ---
# schtasks /Create /TN "OttoDecisionLoop" /SC DAILY /ST 09:23 /TR `
#   "powershell -NoProfile -ExecutionPolicy Bypass -File D:\Otto\scripts\run_decision_loop.ps1"
