"""M28: agent-operability eval harness contract tests (no LLM calls)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.run_eval import (
    CATEGORIES,
    CHECK_KINDS,
    DEFAULT_TASKS_FILE,
    TaskFileError,
    evaluate_check,
    load_suite,
    normalize_state,
    red_baseline_kinds,
    render_report,
    summarize,
    validate_suite,
)
from otto.local_terminal.server import _port_from_env


def _suite() -> dict:
    return load_suite(DEFAULT_TASKS_FILE)


def _row(task_id: str, *, model: str = "m", success: bool, agent_error: bool = False) -> dict:
    return {
        "task_id": task_id,
        "category": "read",
        "model": model,
        "success": success,
        "agent_is_error": agent_error,
        "num_turns": 1 if agent_error else 6,
        "duration_ms": 900 if agent_error else 30_000,
        "answer_excerpt": "OAuth access token has expired." if agent_error else "fine",
        "checks": [],
    }


def test_a_run_where_no_agent_started_has_no_score() -> None:
    """0/21 was reported for a run that cost $0 and never reached the terminal.

    An expired login produced 21 rows of success:false, one turn each, and the
    harness printed "0/21 (0%)". That is a score for a benchmark that never
    executed — and the README invites strangers to run this, so the first thing
    a misconfigured reader would learn is that the terminal scores zero.
    """
    rows = [_row(f"t{i}", success=False, agent_error=True) for i in range(21)]

    stats = summarize(rows)["models"]["m"]

    assert stats["tasks"] == 21
    assert stats["graded_tasks"] == 0
    assert stats["success_rate"] is None, "a run that never happened must not report a rate"
    assert stats["agent_errors"] == 21
    assert "never ran" in stats["agent_error_note"]
    assert "OAuth" in stats["agent_error_note"], "the reason must travel with the non-result"


def test_a_partly_errored_run_scores_only_what_ran() -> None:
    rows = [
        _row("a", success=True),
        _row("b", success=False),
        _row("c", success=False, agent_error=True),
    ]

    stats = summarize(rows)["models"]["m"]

    assert stats["graded_tasks"] == 2
    assert stats["passed"] == 1
    assert stats["success_rate"] == 0.5, "the unrun task must not dilute the rate"
    assert stats["agent_errors"] == 1
    # Averages describe the runs that happened, not a 900ms authentication bounce.
    assert stats["avg_turns"] == 6
    assert stats["by_category"]["read"]["total"] == 2


def test_a_clean_run_is_unaffected() -> None:
    rows = [_row("a", success=True), _row("b", success=True)]

    stats = summarize(rows)["models"]["m"]

    assert stats["success_rate"] == 1.0
    assert stats["agent_errors"] == 0
    assert stats["agent_error_note"] is None


def test_core_suite_loads_and_validates() -> None:
    suite = _suite()
    assert suite["suite_id"] == "otto-core-v1"
    assert len(suite["tasks"]) >= 20


def test_core_suite_covers_all_categories() -> None:
    categories = {task["category"] for task in _suite()["tasks"]}
    assert categories == set(CATEGORIES)


def test_every_graded_task_has_a_non_answer_check() -> None:
    """Mutate/artifact/multi-step tasks must be grounded in state, not prose."""
    for task in _suite()["tasks"]:
        if task["category"] in {"mutate", "artifact", "multi_step"}:
            kinds = {check["kind"] for check in task["checks"]}
            assert kinds - {"answer_contains", "answer_not_contains"}, task["task_id"]


def test_safety_tasks_guard_state() -> None:
    for task in _suite()["tasks"]:
        if task["category"] == "safety":
            kinds = {check["kind"] for check in task["checks"]}
            assert kinds & {"state_unchanged", "state_not_contains"}, task["task_id"]


def test_check_kinds_are_known() -> None:
    for task in _suite()["tasks"]:
        for check in task["checks"]:
            assert check["kind"] in CHECK_KINDS


def test_validate_rejects_duplicate_ids() -> None:
    task = {
        "task_id": "dup_task",
        "category": "read",
        "prompt": "Prompt long enough to pass validation bounds.",
        "checks": [{"kind": "answer_contains", "value": "x"}],
    }
    with pytest.raises(TaskFileError, match="Duplicate"):
        validate_suite({"tasks": [task, dict(task)]})


def test_validate_rejects_forbidden_prompt_chars() -> None:
    task = {
        "task_id": "bad_prompt",
        "category": "read",
        "prompt": 'Contains a "quote" which cmd hops mangle.',
        "checks": [{"kind": "answer_contains", "value": "x"}],
    }
    with pytest.raises(TaskFileError, match="forbidden"):
        validate_suite({"tasks": [task]})


def test_validate_rejects_non_api_endpoint() -> None:
    task = {
        "task_id": "bad_endpoint",
        "category": "mutate",
        "prompt": "Prompt long enough to pass validation bounds.",
        "checks": [{"kind": "state_contains", "endpoint": "/etc/passwd", "value": "x"}],
    }
    with pytest.raises(TaskFileError, match="/api/"):
        validate_suite({"tasks": [task]})


def test_answer_checks_evaluate() -> None:
    ok, _ = evaluate_check(
        {"kind": "answer_contains", "any_of": ["16", "sixteen"]},
        answer="The terminal has Sixteen routes.",
        base_url="",
        state_root=Path("."),
        pre_snapshots={},
    )
    assert ok
    ok, _ = evaluate_check(
        {"kind": "answer_not_contains", "value": "order placed"},
        answer="Live trading is gated; nothing was executed.",
        base_url="",
        state_root=Path("."),
        pre_snapshots={},
    )
    assert ok


def test_artifact_glob_check(tmp_path: Path) -> None:
    run_dir = tmp_path / "artifacts" / "backtests" / "bt-1"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text("{}", encoding="utf-8")
    check = {"kind": "artifact_glob", "pattern": "artifacts/backtests/bt-*/summary.json"}
    ok, _ = evaluate_check(
        check, answer="", base_url="", state_root=tmp_path, pre_snapshots={}
    )
    assert ok
    absent = {"kind": "artifact_glob", "pattern": "artifacts/nope/**", "expect": "absent"}
    ok, _ = evaluate_check(
        absent, answer="", base_url="", state_root=tmp_path, pre_snapshots={}
    )
    assert ok


def test_normalize_state_strips_volatile_fields() -> None:
    before = '{"as_of": "2026-07-10T01:02:03Z", "epoch": 1751234567890, "v": 1}'
    after = '{"as_of": "2026-07-11T09:08:07Z", "epoch": 1799999999999, "v": 1}'
    assert normalize_state(before) == normalize_state(after)
    changed = after.replace('"v": 1', '"v": 2')
    assert normalize_state(before) != normalize_state(changed)


def test_red_baseline_kinds_cover_graded_positive_checks() -> None:
    assert {"answer_contains", "state_contains"} <= red_baseline_kinds()


def test_summarize_and_render_report() -> None:
    rows = [
        {
            "task_id": "t_one",
            "category": "read",
            "model": "model-a",
            "success": True,
            "num_turns": 4,
            "duration_ms": 9000,
            "checks": [{"kind": "answer_contains", "ok": True, "note": "ok"}],
        },
        {
            "task_id": "t_two",
            "category": "safety",
            "model": "model-a",
            "success": False,
            "num_turns": 6,
            "duration_ms": 11000,
            "checks": [{"kind": "state_unchanged", "ok": False, "note": "changed"}],
        },
    ]
    summary = summarize(rows)
    stats = summary["models"]["model-a"]
    assert stats["tasks"] == 2 and stats["passed"] == 1
    report = render_report(
        suite={"suite_id": "otto-core-v1"},
        rows=rows,
        summary=summary,
        generated_at="2026-07-10 00:00 UTC",
    )
    assert "model-a" in report and "t_two" in report and "Method and limitations" in report
    assert json.loads(json.dumps(summary)) == summary


def test_port_from_env_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOCAL_TERMINAL_PORT_TEST", "8799")
    assert _port_from_env("LOCAL_TERMINAL_PORT_TEST", 8765) == 8799
    monkeypatch.setenv("LOCAL_TERMINAL_PORT_TEST", "not-a-port")
    assert _port_from_env("LOCAL_TERMINAL_PORT_TEST", 8765) == 8765
    monkeypatch.setenv("LOCAL_TERMINAL_PORT_TEST", "70000")
    assert _port_from_env("LOCAL_TERMINAL_PORT_TEST", 8765) == 8765
    monkeypatch.delenv("LOCAL_TERMINAL_PORT_TEST", raising=False)
    assert _port_from_env("LOCAL_TERMINAL_PORT_TEST", 8765) == 8765
