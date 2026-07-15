"""Read-only detail payloads for finished research artifacts (M27 S3).

The mission wall shows that a backtest or news brief happened; these payloads
let a person open the finished document itself. Strictly local reads under the
validated artifact roots — no refresh, no mutation, no external calls.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any

_RUN_ID_PATTERN = re.compile(r"^bt-[a-z0-9]{8,32}-[a-z0-9]{4,16}$")
_BRIEF_ID_PATTERN = re.compile(r"^news-brief-[a-z0-9]{8,32}-[a-z0-9]{4,16}$")
_MAX_CSV_ROWS = 500
_MAX_TEXT_CHARS = 40_000


def backtest_run_detail_payload(root: Path, run_id: str) -> dict[str, Any] | None:
    """Return one finished backtest run's artifacts as a readable document."""

    run_dir = _validated_dir(root, "artifacts/backtests", run_id, _RUN_ID_PATTERN)
    if run_dir is None:
        return None
    return {
        "run_id": run_id,
        "artifact_dir": f"artifacts/backtests/{run_id}",
        "summary": _read_json_object(run_dir / "summary.json"),
        "config": _read_json_object(run_dir / "config.json"),
        "returns_analysis": _read_json_object(run_dir / "returns_analysis.json"),
        "provenance": _read_json_object(run_dir / "provenance.json"),
        "manifest": _read_json_object(run_dir / "manifest.json"),
        "trades": _read_csv_rows(run_dir / "trades.csv"),
        "equity_curve": _read_csv_rows(run_dir / "returns_curve.csv"),
        "report_md": _read_text(run_dir / "report.md"),
        "safety": _safety("read_only_backtest_run_artifact"),
    }


def news_brief_detail_payload(root: Path, brief_id: str) -> dict[str, Any] | None:
    """Return one finished news research brief as a readable document."""

    brief_dir = _validated_dir(root, "artifacts/news/research_briefs", brief_id, _BRIEF_ID_PATTERN)
    if brief_dir is None:
        return None
    return {
        "brief_id": brief_id,
        "artifact_dir": f"artifacts/news/research_briefs/{brief_id}",
        "brief": _read_json_object(brief_dir / "brief.json"),
        "brief_md": _read_text(brief_dir / "brief.md"),
        "source_health": _read_json_object(brief_dir / "source_health.json"),
        "safety": _safety("read_only_news_brief_artifact"),
    }


def _validated_dir(root: Path, base: str, artifact_id: str, pattern: re.Pattern[str]) -> Path | None:
    if not pattern.fullmatch(str(artifact_id or "")):
        return None
    candidate = root / base / artifact_id
    resolved = candidate.resolve()
    if not resolved.is_relative_to((root / base).resolve()):
        return None
    if not candidate.is_dir():
        return None
    return candidate


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            rows: list[dict[str, str]] = []
            for row in reader:
                rows.append({
                    str(key): "" if value is None else str(value)
                    for key, value in row.items()
                })
                if len(rows) >= _MAX_CSV_ROWS:
                    break
            return rows
    except OSError:
        return []


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")[:_MAX_TEXT_CHARS]
    except OSError:
        return ""


def _safety(safety_class: str) -> dict[str, Any]:
    return {
        "safety_class": safety_class,
        "reads_local_artifacts_only": True,
        "mutates_local_state": False,
        "external_calls": False,
    }
