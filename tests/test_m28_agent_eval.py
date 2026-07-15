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
