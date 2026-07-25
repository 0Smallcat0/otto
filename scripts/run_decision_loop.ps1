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
Run one full Otto decision round against the local terminal at
http://127.0.0.1:8765 (paper-only; live execution is structurally disabled).
The point of the round is the journaled judgment ledger, not activity.

1. GET /api/market/sessions. If all_equity_closed is true, keep the round
   lean: skip quote/news churn and only do steps 2-3.
2. GET /api/research/ledger?refresh=true and act on needs_review FIRST. Each
   flagged call drifted from its reference price, is closing on its
   invalidation, or is near the end of its horizon. Re-examine the thesis: say
   plainly that it still holds, or record a NEW call that supersedes it. Never
   rewrite an existing call - it scores on the thesis it was written with.
3. POST /api/research/score {"refresh":true}. Scoring reads the price at the
   moment it runs, so a call scored long after it matured is marked
   window_honored=false and kept out of the hit rate. If stale_scored_count is
   above zero, say so: it means rounds were missed, not that the calls failed.
4. GET /api/research/scan?refresh=true. owned_without_call lists the owner's
   real positions with no journaled view - that is the highest-priority gap and
   must be closed. Otherwise work down the movers.
5. For a name worth a view, POST /api/news/packet {"symbols":[..],
   "refresh":true} for context. Yahoo only returns stories it itself relates to
   a symbol, and it cannot resolve Taiwan listings at all, so an empty result
   means no company news was found - never substitute an index headline for a
   single-name catalyst. With a real thesis, POST /api/research/call
   (stance/thesis/conviction/invalidation/horizon_days). Without one, record
   nothing and say so.
   Use stance "size_down" with weight_pct/cap_pct when a position exceeds 40%
   of its book: that is a risk view, carries no directional claim, and is
   excluded from the hit rate by design.
6. Paper books: GET /api/equity/summary?refresh=true, /api/equity/tw/summary
   ?refresh=true and the crypto summary. Enforce the discipline - single
   position <=40% of the book, staged trims <=10% of the book per round, new
   entries <=10%. Validate a repeated signal with POST
   /api/backtest/walk-forward before sizing up. Every order carries a rationale
   prefixed "loop YYYY-MM-DD:" showing the weight arithmetic, then POST the
   three orders/process endpoints so resting orders can fill.
7. POST /api/paper/snapshot then GET /api/paper/history?limit=30 and report
   each book against its benchmark.

Reach the terminal through the otto MCP tools (run_action / list_actions);
plain HTTP clients are not available in this run.

If a data or behavior problem appears, diagnose it precisely - the action, the
inputs, the wrong output, and the file you believe is at fault - and say so at
the end of the round. This run cannot edit code, run tests, commit, push, or
change scheduled tasks: nobody is reviewing it. Naming the defect exactly is
the deliverable; an attended session fixes it.
'@

# 3) Run it, and record what the round cost. A daily unattended agent spends
# real money, so every run appends its own duration, turn count and dollar cost
# to artifacts/loop/runs.jsonl — the owner should never have to guess whether
# this schedule is affordable.
# Headless runs get no interactive permission prompts: the first real run died
# on "Blocked on permission grant" after 8 turns and $1.10, having done nothing.
# So the terminal's own MCP server is loaded explicitly and its tools are
# pre-allowed, scoped to exactly what a round needs. Read-only inspection is
# included so a round can diagnose; editing, tests and git are deliberately NOT
# allowed, because an unattended agent should report a code problem, not
# rewrite the repo while nobody is watching.
$allowed = @(
    "mcp__otto__run_action",
    "mcp__otto__list_actions",
    "mcp__otto__list_routes",
    "mcp__otto__get_route",
    "mcp__otto__terminal_status",
    "mcp__otto__refresh_public_data",
    "Read", "Grep", "Glob"
) -join " "

$started = Get-Date
Push-Location $repo
try {
    $raw = claude -p $prompt --max-turns 40 --output-format json `
        --mcp-config (Join-Path $repo ".mcp.json") --strict-mcp-config `
        --allowedTools $allowed
} finally {
    Pop-Location
}
$ended = Get-Date

$log = Join-Path $repo "artifacts\loop\runs.jsonl"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

$cost = $null; $turns = $null; $text = $raw; $failed = $null
try {
    $parsed = $raw | ConvertFrom-Json
    $cost = $parsed.total_cost_usd
    $turns = $parsed.num_turns
    $text = $parsed.result
    $failed = $parsed.is_error
} catch {
    $failed = $true
}

$entry = [ordered]@{
    started_at = $started.ToString("o")
    seconds    = [math]::Round(($ended - $started).TotalSeconds)
    cost_usd   = $cost
    turns      = $turns
    is_error   = $failed
}
($entry | ConvertTo-Json -Compress) | Add-Content -Path $log -Encoding utf8

Write-Output $text

# --- One-time registration. The owner authorizes this; the script never
# registers itself, because a standing scheduled task is a persistent change
# to their machine. Without it nothing runs between chat sessions: the
# in-session scheduler dies with the process, which is how 2026-07-23/24
# silently produced no rounds at all.
#
# schtasks /Create /TN "OttoDecisionLoop" /SC DAILY /ST 11:07 /TR "powershell -NoProfile -ExecutionPolicy Bypass -File D:\Otto\scripts\run_decision_loop.ps1"
