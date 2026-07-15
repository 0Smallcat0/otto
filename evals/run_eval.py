"""Agent-operability eval harness for Otto.

Measures how well an LLM agent operates the terminal through the MCP tool
surface (`otto.local_terminal.mcp_server`). Each task runs in a throwaway
sandbox: a fresh `LOCAL_TERMINAL_STATE_ROOT`, a dedicated server port, and a
strict per-run MCP config, so runs never touch the operator's real local state
and cannot inherit user-level Claude configuration.

Success is judged programmatically (HTTP state assertions, artifact globs,
answer substrings) — never by an LLM judge.

Usage:

    python evals/run_eval.py --smoke
    python evals/run_eval.py --model claude-haiku-4-5-20251001 --report
    python evals/run_eval.py --model claude-sonnet-5 --task-id backtest_run_sma

Stdlib only, matching the repo's minimal-dependency tooling rule.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
EVALS_DIR = REPO_ROOT / "evals"
DEFAULT_TASKS_FILE = EVALS_DIR / "tasks" / "core_tasks.json"
SANDBOX_ROOT = EVALS_DIR / ".sandbox"
RESULTS_ROOT = EVALS_DIR / "results"
REPORT_PATH = EVALS_DIR / "EVAL.md"

CATEGORIES = ("read", "mutate", "artifact", "multi_step", "safety")
CHECK_KINDS = (
    "answer_contains",
    "answer_not_contains",
    "state_contains",
    "state_not_contains",
    "state_unchanged",
    "artifact_glob",
    "http_ok",
)
# Characters that survive both subprocess argv quoting and a cmd.exe hop on Windows.
FORBIDDEN_PROMPT_CHARS = ('"', "%", "^", "&", "|", "<", ">", "\n", "\r")
DEFAULT_MAX_TURNS = 16
DEFAULT_TIMEOUT_S = 300
SERVER_BOOT_TIMEOUT_S = 60

_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?"
)
_EPOCH_RE = re.compile(r"\b\d{10,13}\b")


class TaskFileError(ValueError):
    """Raised when the task suite file is malformed."""


# ---------------------------------------------------------------------------
# Task loading / validation
# ---------------------------------------------------------------------------


def load_suite(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        suite = json.load(handle)
    validate_suite(suite)
    return suite


def validate_suite(suite: dict[str, Any]) -> None:
    if not isinstance(suite, dict):
        raise TaskFileError("Suite must be a JSON object")
    tasks = suite.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise TaskFileError("Suite must define a non-empty tasks list")
    seen: set[str] = set()
    for task in tasks:
        validate_task(task)
        task_id = task["task_id"]
        if task_id in seen:
            raise TaskFileError(f"Duplicate task_id: {task_id}")
        seen.add(task_id)


def validate_task(task: dict[str, Any]) -> None:
    if not isinstance(task, dict):
        raise TaskFileError("Task must be an object")
    task_id = task.get("task_id")
    if not isinstance(task_id, str) or not re.fullmatch(r"[a-z0-9_]{3,64}", task_id):
        raise TaskFileError(f"Bad task_id: {task_id!r}")
    if task.get("category") not in CATEGORIES:
        raise TaskFileError(f"{task_id}: bad category {task.get('category')!r}")
    prompt = task.get("prompt")
    if not isinstance(prompt, str) or not 10 <= len(prompt) <= 1200:
        raise TaskFileError(f"{task_id}: prompt missing or out of bounds")
    for char in FORBIDDEN_PROMPT_CHARS:
        if char in prompt:
            raise TaskFileError(f"{task_id}: prompt contains forbidden char {char!r}")
    max_turns = task.get("max_turns", DEFAULT_MAX_TURNS)
    if not isinstance(max_turns, int) or not 2 <= max_turns <= 60:
        raise TaskFileError(f"{task_id}: max_turns out of bounds")
    checks = task.get("checks")
    if not isinstance(checks, list) or not checks:
        raise TaskFileError(f"{task_id}: checks missing")
    for check in checks:
        validate_check(task_id, check)
    for step in task.get("setup", []):
        if step.get("method") not in {"GET", "POST"}:
            raise TaskFileError(f"{task_id}: setup method must be GET or POST")
        _require_api_endpoint(task_id, step.get("endpoint"))


def validate_check(task_id: str, check: dict[str, Any]) -> None:
    if not isinstance(check, dict):
        raise TaskFileError(f"{task_id}: check must be an object")
    kind = check.get("kind")
    if kind not in CHECK_KINDS:
        raise TaskFileError(f"{task_id}: unknown check kind {kind!r}")
    if kind in {"answer_contains", "answer_not_contains"}:
        if not (isinstance(check.get("value"), str) or isinstance(check.get("any_of"), list)):
            raise TaskFileError(f"{task_id}: {kind} needs value or any_of")
    if kind in {"state_contains", "state_not_contains", "state_unchanged", "http_ok"}:
        _require_api_endpoint(task_id, check.get("endpoint"))
    if kind in {"state_contains", "state_not_contains"} and not isinstance(
        check.get("value"), str
    ):
        raise TaskFileError(f"{task_id}: {kind} needs a string value")
    if kind == "artifact_glob":
        pattern = check.get("pattern")
        if not isinstance(pattern, str) or pattern.startswith(("/", "\\")) or ".." in pattern:
            raise TaskFileError(f"{task_id}: artifact_glob pattern must be sandbox-relative")
        if check.get("expect", "exists") not in {"exists", "absent"}:
            raise TaskFileError(f"{task_id}: artifact_glob expect must be exists|absent")


def _require_api_endpoint(task_id: str, endpoint: Any) -> None:
    if not isinstance(endpoint, str) or not endpoint.startswith("/api/"):
        raise TaskFileError(f"{task_id}: endpoint must start with /api/: {endpoint!r}")


# ---------------------------------------------------------------------------
# HTTP + state helpers
# ---------------------------------------------------------------------------


def http_request(
    base_url: str,
    endpoint: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> tuple[int, str]:
    request = urllib.request.Request(
        base_url + endpoint,
        method=method,
        headers={"Content-Type": "application/json"},
        data=json.dumps(body or {}).encode("utf-8") if method == "POST" else None,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", errors="replace")


def normalize_state(text: str) -> str:
    """Strip volatile timestamps so state_unchanged does not flag clock noise."""
    text = _TIMESTAMP_RE.sub("<TS>", text)
    return _EPOCH_RE.sub("<EPOCH>", text)


def evaluate_check(
    check: dict[str, Any],
    *,
    answer: str,
    base_url: str,
    state_root: Path,
    pre_snapshots: dict[str, str],
) -> tuple[bool, str]:
    kind = check["kind"]
    if kind in {"answer_contains", "answer_not_contains"}:
        needles = check.get("any_of") or [check["value"]]
        haystack = answer.lower()
        hit = any(str(needle).lower() in haystack for needle in needles)
        if kind == "answer_contains":
            return hit, f"answer contains {needles!r}" if hit else f"answer missing {needles!r}"
        return not hit, f"answer avoids {needles!r}" if not hit else f"answer contains {needles!r}"
    if kind in {"state_contains", "state_not_contains"}:
        status, text = http_request(base_url, check["endpoint"])
        if status != 200:
            return False, f"GET {check['endpoint']} -> {status}"
        hit = check["value"].lower() in text.lower()
        if kind == "state_contains":
            return hit, f"{check['endpoint']} contains {check['value']!r}: {hit}"
        return not hit, f"{check['endpoint']} free of {check['value']!r}: {not hit}"
    if kind == "state_unchanged":
        status, text = http_request(base_url, check["endpoint"])
        if status != 200:
            return False, f"GET {check['endpoint']} -> {status}"
        before = pre_snapshots.get(check["endpoint"], "")
        unchanged = normalize_state(text) == normalize_state(before)
        return unchanged, f"{check['endpoint']} unchanged: {unchanged}"
    if kind == "http_ok":
        status, _ = http_request(base_url, check["endpoint"])
        return status == 200, f"GET {check['endpoint']} -> {status}"
    if kind == "artifact_glob":
        matches = [path for path in state_root.glob(check["pattern"]) if path.is_file()]
        minimum = int(check.get("min_count", 1))
        if check.get("expect", "exists") == "exists":
            ok = len(matches) >= minimum
            return ok, f"{check['pattern']}: {len(matches)} file(s), need >= {minimum}"
        return not matches, f"{check['pattern']}: {len(matches)} file(s), expected none"
    return False, f"unhandled check kind {kind}"


def red_baseline_kinds() -> set[str]:
    """Checks that must FAIL on fresh state, proving the task demands real work."""
    return {"answer_contains", "state_contains"}


# ---------------------------------------------------------------------------
# Sandbox server lifecycle
# ---------------------------------------------------------------------------


def free_port(start: int) -> int:
    for candidate in range(start, start + 200):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", candidate))
            except OSError:
                continue
            return candidate
    raise RuntimeError("No free port found")


def start_sandbox_server(sandbox: Path, port: int) -> subprocess.Popen[bytes]:
    env = dict(**_clean_env())
    env["LOCAL_TERMINAL_STATE_ROOT"] = str(sandbox)
    env["LOCAL_TERMINAL_PORT"] = str(port)
    env["LOCAL_TERMINAL_HOST"] = "127.0.0.1"
    return subprocess.Popen(
        [sys.executable, "-m", "otto.local_terminal"],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _clean_env() -> dict[str, str]:
    import os

    return {key: value for key, value in os.environ.items() if not key.startswith("LOCAL_TERMINAL_")}


def wait_for_health(base_url: str, timeout_s: float = SERVER_BOOT_TIMEOUT_S) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            status, _ = http_request(base_url, "/api/health", timeout=3.0)
            if status == 200:
                return True
        except OSError:
            pass
        time.sleep(0.5)
    return False


def write_mcp_config(sandbox: Path, port: int) -> Path:
    config = {
        "mcpServers": {
            "otto": {
                "command": sys.executable,
                "args": ["-m", "otto.local_terminal.mcp_server"],
                "env": {
                    "LOCAL_TERMINAL_URL": f"http://127.0.0.1:{port}",
                    "LOCAL_TERMINAL_MCP_AUTOSTART": "0",
                    "PYTHONPATH": str(REPO_ROOT),
                },
            }
        }
    }
    path = sandbox / "mcp-config.json"
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Claude headless invocation
# ---------------------------------------------------------------------------


def resolve_claude() -> list[str]:
    executable = shutil.which("claude")
    if executable is None:
        raise RuntimeError("claude CLI not found on PATH")
    if executable.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", executable]
    return [executable]


def run_claude(
    *,
    prompt: str,
    model: str,
    max_turns: int,
    mcp_config: Path,
    cwd: Path,
    timeout_s: int,
    setting_sources: str,
) -> dict[str, Any]:
    command = resolve_claude() + [
        "-p",
        prompt,
        "--output-format",
        "json",
        "--model",
        model,
        "--max-turns",
        str(max_turns),
        "--mcp-config",
        str(mcp_config),
        "--strict-mcp-config",
        "--allowedTools",
        "mcp__otto",
        "--setting-sources",
        setting_sources,
    ]
    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd),
            env=_clean_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {"harness_error": f"claude timed out after {timeout_s}s"}
    elapsed_ms = int((time.monotonic() - started) * 1000)
    stdout = (completed.stdout or "").strip()
    if not stdout:
        return {
            "harness_error": f"claude produced no stdout (exit {completed.returncode})",
            "stderr_tail": (completed.stderr or "")[-800:],
        }
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "harness_error": f"claude stdout was not JSON (exit {completed.returncode})",
            "stdout_tail": stdout[-800:],
            "stderr_tail": (completed.stderr or "")[-800:],
        }
    payload.setdefault("duration_ms", elapsed_ms)
    return payload


# ---------------------------------------------------------------------------
# Task execution
# ---------------------------------------------------------------------------


def run_setup(task: dict[str, Any], base_url: str) -> str | None:
    for step in task.get("setup", []):
        status, text = http_request(
            base_url, step["endpoint"], method=step["method"], body=step.get("body")
        )
        if status >= 400:
            return f"setup {step['method']} {step['endpoint']} -> {status}: {text[:200]}"
    return None


def take_pre_snapshots(task: dict[str, Any], base_url: str) -> dict[str, str]:
    snapshots: dict[str, str] = {}
    for check in task["checks"]:
        if check["kind"] == "state_unchanged":
            _, text = http_request(base_url, check["endpoint"])
            snapshots[check["endpoint"]] = text
    return snapshots


def run_task(
    task: dict[str, Any],
    *,
    model: str,
    run_dir: Path,
    port: int,
    setting_sources: str,
    keep_sandbox: bool,
) -> dict[str, Any]:
    task_id = task["task_id"]
    sandbox = run_dir / "sandboxes" / f"{task_id}--{model.replace(':', '_')}"
    sandbox.mkdir(parents=True, exist_ok=True)
    base_url = f"http://127.0.0.1:{port}"
    row: dict[str, Any] = {
        "task_id": task_id,
        "category": task["category"],
        "model": model,
        "success": False,
        "checks": [],
    }
    server = start_sandbox_server(sandbox, port)
    try:
        if not wait_for_health(base_url):
            row["harness_error"] = "sandbox server did not become healthy"
            return row
        setup_error = run_setup(task, base_url)
        if setup_error:
            row["harness_error"] = setup_error
            return row
        pre_snapshots = take_pre_snapshots(task, base_url)
        mcp_config = write_mcp_config(sandbox, port)
        outcome = run_claude(
            prompt=task["prompt"],
            model=model,
            max_turns=task.get("max_turns", DEFAULT_MAX_TURNS),
            mcp_config=mcp_config,
            cwd=sandbox,
            timeout_s=task.get("timeout_s", DEFAULT_TIMEOUT_S),
            setting_sources=setting_sources,
        )
        (sandbox / "claude-output.json").write_text(
            json.dumps(outcome, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        if "harness_error" in outcome:
            row["harness_error"] = outcome["harness_error"]
            return row
        answer = str(outcome.get("result") or "")
        row.update(
            {
                "num_turns": outcome.get("num_turns"),
                "duration_ms": outcome.get("duration_ms"),
                "total_cost_usd": outcome.get("total_cost_usd"),
                "usage": outcome.get("usage"),
                "agent_is_error": bool(outcome.get("is_error")),
                "answer_excerpt": answer[:600],
            }
        )
        all_ok = True
        for check in task["checks"]:
            ok, note = evaluate_check(
                check,
                answer=answer,
                base_url=base_url,
                state_root=sandbox,
                pre_snapshots=pre_snapshots,
            )
            row["checks"].append({"kind": check["kind"], "ok": ok, "note": note})
            all_ok = all_ok and ok
        row["success"] = all_ok and not row["agent_is_error"]
        return row
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        if not keep_sandbox and row.get("success"):
            shutil.rmtree(sandbox, ignore_errors=True)


def run_smoke(task: dict[str, Any], *, run_dir: Path, port: int) -> dict[str, Any]:
    """Boot the sandbox, run setup, and confirm red-baseline checks start red."""
    task_id = task["task_id"]
    sandbox = run_dir / "sandboxes" / f"smoke--{task_id}"
    sandbox.mkdir(parents=True, exist_ok=True)
    base_url = f"http://127.0.0.1:{port}"
    row: dict[str, Any] = {"task_id": task_id, "ok": False, "notes": []}
    server = start_sandbox_server(sandbox, port)
    try:
        if not wait_for_health(base_url):
            row["notes"].append("server did not boot")
            return row
        setup_error = run_setup(task, base_url)
        if setup_error:
            row["notes"].append(setup_error)
            return row
        pre_snapshots = take_pre_snapshots(task, base_url)
        ok = True
        for check in task["checks"]:
            passed, note = evaluate_check(
                check,
                answer="",
                base_url=base_url,
                state_root=sandbox,
                pre_snapshots=pre_snapshots,
            )
            if (
                check["kind"] in red_baseline_kinds()
                and check.get("red_baseline", True)
                and passed
            ):
                ok = False
                row["notes"].append(f"VACUOUS (already green before agent): {note}")
            if check["kind"] in {"http_ok", "state_unchanged"} and not passed:
                ok = False
                row["notes"].append(f"broken baseline: {note}")
            if check["kind"] in {"state_contains", "state_not_contains"} and "-> 4" in note:
                ok = False
                row["notes"].append(f"endpoint error: {note}")
        row["ok"] = ok
        return row
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        shutil.rmtree(sandbox, ignore_errors=True)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    models = sorted({row["model"] for row in rows})
    summary: dict[str, Any] = {"models": {}, "task_count": len({r["task_id"] for r in rows})}
    for model in models:
        model_rows = [row for row in rows if row["model"] == model]
        successes = [row for row in model_rows if row["success"]]
        turns = [row["num_turns"] for row in model_rows if isinstance(row.get("num_turns"), int)]
        durations = [
            row["duration_ms"] for row in model_rows if isinstance(row.get("duration_ms"), int)
        ]
        by_category: dict[str, dict[str, int]] = {}
        for row in model_rows:
            bucket = by_category.setdefault(row["category"], {"total": 0, "passed": 0})
            bucket["total"] += 1
            bucket["passed"] += 1 if row["success"] else 0
        summary["models"][model] = {
            "tasks": len(model_rows),
            "passed": len(successes),
            "success_rate": round(len(successes) / len(model_rows), 4) if model_rows else 0.0,
            "avg_turns": round(sum(turns) / len(turns), 1) if turns else None,
            "avg_duration_ms": int(sum(durations) / len(durations)) if durations else None,
            "harness_errors": sum(1 for row in model_rows if row.get("harness_error")),
            "by_category": by_category,
        }
    return summary


def render_report(
    *,
    suite: dict[str, Any],
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    generated_at: str,
) -> str:
    models = sorted(summary["models"])
    lines: list[str] = []
    lines.append("# Otto Agent-Operability Eval")
    lines.append("")
    lines.append(
        "How reliably can an LLM agent operate Otto end-to-end through the MCP tool "
        "surface? Every task below is judged by programmatic checks against terminal "
        "state, produced artifacts, or required answer facts — no LLM judge."
    )
    lines.append("")
    lines.append(f"- Suite: `{suite.get('suite_id', 'unknown')}` ({summary['task_count']} tasks)")
    lines.append(f"- Generated: {generated_at}")
    lines.append("- Harness: `evals/run_eval.py` (sandboxed state root + per-task server)")
    lines.append(
        "- Agent: `claude -p` headless, MCP tools only, isolated from user-level settings"
    )
    lines.append("")
    lines.append("## Headline results")
    lines.append("")
    lines.append("| Model | Tasks | Passed | Success rate | Avg turns | Avg duration |")
    lines.append("|---|---|---|---|---|---|")
    for model in models:
        stats = summary["models"][model]
        duration = (
            f"{stats['avg_duration_ms'] / 1000:.0f}s" if stats["avg_duration_ms"] else "n/a"
        )
        lines.append(
            f"| `{model}` | {stats['tasks']} | {stats['passed']} | "
            f"{stats['success_rate'] * 100:.0f}% | {stats['avg_turns'] or 'n/a'} | {duration} |"
        )
    lines.append("")
    lines.append("## By category")
    lines.append("")
    categories = [c for c in CATEGORIES if any(r["category"] == c for r in rows)]
    header = "| Category | " + " | ".join(f"`{m}`" for m in models) + " |"
    lines.append(header)
    lines.append("|---" * (len(models) + 1) + "|")
    for category in categories:
        cells = []
        for model in models:
            bucket = summary["models"][model]["by_category"].get(category)
            cells.append(f"{bucket['passed']}/{bucket['total']}" if bucket else "—")
        lines.append(f"| {category} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Per-task matrix")
    lines.append("")
    lines.append("| Task | Category | " + " | ".join(f"`{m}`" for m in models) + " |")
    lines.append("|---|---" + "|---" * len(models) + "|")
    task_ids = sorted({row["task_id"] for row in rows})
    by_key = {(row["task_id"], row["model"]): row for row in rows}
    for task_id in task_ids:
        category = next(row["category"] for row in rows if row["task_id"] == task_id)
        cells = []
        for model in models:
            row = by_key.get((task_id, model))
            if row is None:
                cells.append("—")
            elif row.get("harness_error"):
                cells.append("⚠ harness")
            else:
                cells.append("✅" if row["success"] else "❌")
        lines.append(f"| {task_id} | {category} | " + " | ".join(cells) + " |")
    lines.append("")
    failures = [row for row in rows if not row["success"]]
    if failures:
        lines.append("## Failure notes")
        lines.append("")
        for row in failures:
            reason = row.get("harness_error")
            if not reason:
                failed = [c["note"] for c in row["checks"] if not c["ok"]]
                reason = "; ".join(failed) or "agent error"
            lines.append(f"- `{row['task_id']}` × `{row['model']}`: {reason}")
        lines.append("")
    lines.append("## Method and limitations")
    lines.append("")
    lines.append(
        "- Each task boots a fresh sandboxed terminal (isolated `LOCAL_TERMINAL_STATE_ROOT`, "
        "dedicated port), so results are order-independent and never touch real user state."
    )
    lines.append(
        "- Checks are objective: HTTP state substrings, artifact-file globs, and required "
        "facts in the final answer. A smoke mode verifies every graded check starts red on "
        "fresh state, so tasks cannot pass vacuously."
    )
    lines.append(
        "- Safety tasks grade refusal: the gated request must leave state unchanged."
    )
    lines.append(
        "- Single run per task per model (no retries); sample sizes are small and "
        "results will vary run to run. Token/cost fields come from the Claude CLI."
    )
    lines.append(
        "- Tasks use the deterministic offline data provider wherever possible; "
        "no market-data API keys are required to reproduce."
    )
    lines.append("")
    lines.append("## Reproduce")
    lines.append("")
    lines.append("```bash")
    lines.append("python evals/run_eval.py --smoke")
    lines.append("python evals/run_eval.py --model <model-id> --report")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Otto agent-operability eval harness")
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS_FILE)
    parser.add_argument("--model", action="append", default=[], help="Model id (repeatable)")
    parser.add_argument("--task-id", action="append", default=[], help="Only run these tasks")
    parser.add_argument("--limit", type=int, default=0, help="Run at most N tasks")
    parser.add_argument("--port-base", type=int, default=8790)
    parser.add_argument("--smoke", action="store_true", help="Validate tasks without an agent")
    parser.add_argument("--report", action="store_true", help="Write evals/EVAL.md after the run")
    parser.add_argument("--keep-sandboxes", action="store_true")
    parser.add_argument(
        "--setting-sources",
        default="",
        help="claude --setting-sources value (default: none, for isolation)",
    )
    args = parser.parse_args(argv)

    suite = load_suite(args.tasks)
    tasks = suite["tasks"]
    if args.task_id:
        wanted = set(args.task_id)
        tasks = [task for task in tasks if task["task_id"] in wanted]
        missing = wanted - {task["task_id"] for task in tasks}
        if missing:
            print(f"Unknown task ids: {sorted(missing)}", file=sys.stderr)
            return 2
    if args.limit:
        tasks = tasks[: args.limit]

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RESULTS_ROOT / stamp
    run_dir.mkdir(parents=True, exist_ok=True)

    if args.smoke:
        port = args.port_base
        failures = 0
        for task in tasks:
            port = free_port(port + 1)
            row = run_smoke(task, run_dir=run_dir, port=port)
            status = "ok" if row["ok"] else "FAIL"
            print(f"[smoke] {task['task_id']}: {status} {'; '.join(row['notes'])}")
            failures += 0 if row["ok"] else 1
        print(f"[smoke] {len(tasks) - failures}/{len(tasks)} tasks have a sound red baseline")
        return 1 if failures else 0

    if not args.model:
        print("Provide --model at least once (or use --smoke).", file=sys.stderr)
        return 2

    rows: list[dict[str, Any]] = []
    results_path = run_dir / "results.jsonl"
    port = args.port_base
    with results_path.open("a", encoding="utf-8") as sink:
        for model in args.model:
            for index, task in enumerate(tasks, start=1):
                port = free_port(port + 1)
                print(f"[{model}] ({index}/{len(tasks)}) {task['task_id']} ...", flush=True)
                row = run_task(
                    task,
                    model=model,
                    run_dir=run_dir,
                    port=port,
                    setting_sources=args.setting_sources,
                    keep_sandbox=args.keep_sandboxes,
                )
                verdict = "PASS" if row["success"] else "fail"
                print(f"[{model}] ({index}/{len(tasks)}) {task['task_id']} -> {verdict}")
                rows.append(row)
                sink.write(json.dumps(row, ensure_ascii=False) + "\n")
                sink.flush()

    summary = summarize(rows)
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    (run_dir / "summary.json").write_text(
        json.dumps({"suite_id": suite.get("suite_id"), "generated_at": generated_at, **summary},
                   indent=2),
        encoding="utf-8",
    )
    for model, stats in summary["models"].items():
        print(
            f"{model}: {stats['passed']}/{stats['tasks']} "
            f"({stats['success_rate'] * 100:.0f}%), avg turns {stats['avg_turns']}"
        )
    if args.report:
        REPORT_PATH.write_text(
            render_report(suite=suite, rows=rows, summary=summary, generated_at=generated_at),
            encoding="utf-8",
        )
        print(f"Report written to {REPORT_PATH}")
    print(f"Raw results: {results_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
