# Daily paper decision round: one headless Claude Code run that grades the
# open calls, scans for gaps, records reasoned calls, places paper orders and
# snapshots the books. It registers nothing by itself — the README's "Run a
# round every day" has the one-time scheduled-task registration.
#
# Works from a clone or as a single downloaded file. The terminal is reached
# through its own MCP server (the installed `otto-terminal`, else uvx straight
# from GitHub), and that server starts the backend if it is not running yet.

param(
    # The language the theses are written in. Defaults to the Windows display
    # language: a judgment its owner has to translate is one that does not land.
    [string]$Language = (Get-UICulture).EnglishName
)

$ErrorActionPreference = "Stop"

# claude reads and writes UTF-8; Windows PowerShell 5.1 defaults to the console
# codepage, which turns a Chinese thesis into question marks.
$utf8 = New-Object System.Text.UTF8Encoding $false
$OutputEncoding = $utf8
try { [Console]::OutputEncoding = $utf8 } catch { }

# Where an installed terminal keeps its state (storage.default_state_root), so
# the round's log and report sit beside the books they describe.
$stateRoot = if ($env:LOCAL_TERMINAL_STATE_ROOT) { $env:LOCAL_TERMINAL_STATE_ROOT } else { Join-Path $HOME ".otto" }
$loopDir = Join-Path $stateRoot "artifacts\loop"
New-Item -ItemType Directory -Force -Path $loopDir | Out-Null

# 1) The MCP server this run talks to, written to a file for --mcp-config.
$installed = Get-Command otto-terminal -ErrorAction SilentlyContinue
if ($installed) {
    $server = @{ command = $installed.Source; args = @() }
} else {
    $server = @{ command = "uvx"; args = @("--from", "git+https://github.com/0Smallcat0/otto", "otto-terminal") }
}
$mcpConfig = Join-Path $loopDir "mcp.json"
[IO.File]::WriteAllText($mcpConfig, (@{ mcpServers = @{ otto = $server } } | ConvertTo-Json -Depth 4), $utf8)

# 2) One headless agent run of the full round.
$prompt = @'
Run one full Otto decision round on the local terminal (paper-only; live
execution is structurally disabled). The point of the round is the journaled
judgment ledger, not activity.

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
   entries <=10%. Validate a repeated crypto signal with POST
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
$prompt += @"

Write every thesis and the final report in $Language. Ticker symbols, numbers
and price levels stay as they are.
"@

# 3) Run it, and record what the round cost. A daily unattended agent spends
# real money, so every run appends its own duration, turn count and dollar cost
# to runs.jsonl — the owner should never have to guess whether this schedule is
# affordable — and keeps its report, which would otherwise vanish with the
# scheduled task's console.
# Headless runs get no interactive permission prompts: the first real run died
# on "Blocked on permission grant" after 8 turns and $1.10, having done nothing.
# So the terminal's own MCP server is loaded explicitly and its tools are
# pre-allowed, scoped to exactly what a round needs. Read-only inspection is
# included so a round can diagnose; editing, tests and git are deliberately NOT
# allowed, because an unattended agent should report a problem, not rewrite
# anything while nobody is watching.
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
Push-Location $stateRoot
try {
    # The prompt goes in on stdin: Windows PowerShell 5.1 does not escape the
    # double quotes inside a native argument, so passed as one it arrives split.
    $raw = $prompt | claude -p --max-turns 40 --output-format json `
        --mcp-config $mcpConfig --strict-mcp-config --allowedTools $allowed
} finally {
    Pop-Location
}
$ended = Get-Date

$cost = $null; $turns = $null; $text = $raw -join "`n"; $failed = $null
try {
    $parsed = $text | ConvertFrom-Json
    $cost = $parsed.total_cost_usd
    $turns = $parsed.num_turns
    $text = $parsed.result
    $failed = $parsed.is_error
} catch {
    $failed = $true
}

$report = Join-Path $loopDir ("round-" + $started.ToString("yyyy-MM-dd-HHmm") + ".md")
[IO.File]::WriteAllText($report, [string]$text, $utf8)

$entry = [ordered]@{
    started_at = $started.ToString("o")
    seconds    = [math]::Round(($ended - $started).TotalSeconds)
    cost_usd   = $cost
    turns      = $turns
    is_error   = $failed
    report     = $report
}
[IO.File]::AppendAllText((Join-Path $loopDir "runs.jsonl"), ($entry | ConvertTo-Json -Compress) + "`n", $utf8)

Write-Output $text

# The script never registers itself, because a standing scheduled task is a
# persistent change to the owner's machine and theirs to authorize. Without
# one nothing runs between chat sessions: an in-session scheduler dies with
# the process, which is how 2026-07-23/24 silently produced no rounds at all.
