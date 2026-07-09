"""Local research lineage helpers for Markets -> Algo -> Backtest handoff."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


LINEAGE_SOURCE_FIELDS: tuple[str, ...] = (
    "asset_family",
    "runtime_role",
    "provider_id",
    "auth_mode",
    "state",
    "cache_path",
    "retrieved_at",
    "row_count",
    "freshness_ttl_seconds",
    "docs_url",
    "quote_semantics",
    "gated_reason",
    "safe_action_id",
    "next_safe_action",
)
CONTEXT_ONLY_QUOTE_SEMANTICS = {"reference_only", "not_quote"}
FORBIDDEN_LINEAGE_TERMS = (
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "private_key",
    "secret_key",
    "password",
    "passphrase",
    "pin:",
    "bearer ",
    "broker",
    "real_order",
    "real_balance",
    "live_deployment",
    "margin",
    "leverage",
    "short_exposure",
    "derivatives",
)


class ResearchLineageError(ValueError):
    """Raised when local research lineage references are unsafe or invalid."""


def enrich_source_coverage_row(row: dict[str, Any]) -> dict[str, Any]:
    """Add deterministic identity fields to a safe Markets source row."""

    enriched = dict(row)
    enriched["markets_source_row_id"] = markets_source_row_id(enriched)
    enriched["markets_source_row_hash"] = markets_source_row_hash(enriched)
    enriched["research_context_eligible"] = True
    enriched["backtest_data_eligible"] = False
    enriched["context_only"] = str(enriched.get("quote_semantics") or "") in (
        CONTEXT_ONLY_QUOTE_SEMANTICS
    )
    enriched["live_action_enabled"] = False
    return enriched


def markets_source_row_id(row: dict[str, Any]) -> str:
    parts = (
        row.get("asset_family"),
        row.get("runtime_role"),
        row.get("provider_id"),
        row.get("auth_mode"),
        row.get("quote_semantics"),
    )
    return "-".join(_slug(str(part or "")) for part in parts if str(part or "").strip())


def markets_source_row_hash(row: dict[str, Any]) -> str:
    return stable_hash({key: row.get(key, "") for key in LINEAGE_SOURCE_FIELDS})


def stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def select_markets_source_row(
    rows: list[dict[str, Any]],
    *,
    row_id: Any = None,
    expected_hash: Any = None,
) -> dict[str, Any]:
    enriched = [enrich_source_coverage_row(row) for row in rows if isinstance(row, dict)]
    selected_id = str(row_id or "").strip()
    if selected_id:
        matches = [row for row in enriched if row["markets_source_row_id"] == selected_id]
        if not matches:
            raise ResearchLineageError("Unknown Markets source row")
        selected = matches[0]
    elif enriched:
        selected = enriched[0]
    else:
        raise ResearchLineageError("Markets source coverage matrix is unavailable")
    _validate_source_row(selected)
    expected = str(expected_hash or "").strip()
    if expected and expected != selected["markets_source_row_hash"]:
        raise ResearchLineageError("Markets source row hash mismatch")
    return selected


def lineage_from_source_row(row: dict[str, Any]) -> dict[str, Any]:
    selected = enrich_source_coverage_row(row)
    _validate_source_row(selected)
    return {
        "markets_source_row_id": selected["markets_source_row_id"],
        "markets_source_row_hash": selected["markets_source_row_hash"],
        "asset_family": str(selected.get("asset_family") or ""),
        "runtime_role": str(selected.get("runtime_role") or ""),
        "provider_id": str(selected.get("provider_id") or ""),
        "auth_mode": str(selected.get("auth_mode") or ""),
        "quote_semantics": str(selected.get("quote_semantics") or ""),
        "cache_path": str(selected.get("cache_path") or ""),
        "retrieved_at": str(selected.get("retrieved_at") or ""),
        "scan_id": "",
        "scan_artifact_path": "",
        "scan_artifact_hash": "",
        "backtest_run_id": "",
        "backtest_config_hash": "",
        "data_snapshot_hash": "",
        "manifest_path": "",
        "live_action_enabled": False,
    }


def normalize_research_lineage(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    lineage = {
        "markets_source_row_id": _safe_text(source.get("markets_source_row_id"), 160),
        "markets_source_row_hash": _hash_text(source.get("markets_source_row_hash")),
        "asset_family": _safe_text(source.get("asset_family"), 80),
        "runtime_role": _safe_text(source.get("runtime_role"), 80),
        "provider_id": _safe_text(source.get("provider_id"), 120),
        "auth_mode": _safe_text(source.get("auth_mode"), 80),
        "quote_semantics": _safe_text(source.get("quote_semantics"), 80),
        "cache_path": _safe_path_text(source.get("cache_path"), 240),
        "retrieved_at": _safe_text(source.get("retrieved_at"), 80),
        "scan_id": _safe_text(source.get("scan_id"), 80),
        "scan_artifact_path": _safe_path_text(source.get("scan_artifact_path"), 240),
        "scan_artifact_hash": _hash_text(source.get("scan_artifact_hash")),
        "backtest_run_id": _safe_text(source.get("backtest_run_id"), 80),
        "backtest_config_hash": _hash_text(source.get("backtest_config_hash")),
        "data_snapshot_hash": _hash_text(source.get("data_snapshot_hash")),
        "manifest_path": _safe_path_text(source.get("manifest_path"), 240),
        "live_action_enabled": False,
    }
    if not lineage["markets_source_row_id"]:
        raise ResearchLineageError("Research lineage source row id is required")
    if not lineage["markets_source_row_hash"]:
        raise ResearchLineageError("Research lineage source row hash is required")
    _validate_lineage(lineage)
    return lineage


def with_scan_artifact_lineage(
    lineage: dict[str, Any],
    *,
    scan_id: str,
    scan_artifact_path: str,
    scan_artifact_hash: str,
) -> dict[str, Any]:
    normalized = normalize_research_lineage(
        {
            **lineage,
            "scan_id": scan_id,
            "scan_artifact_path": scan_artifact_path,
            "scan_artifact_hash": scan_artifact_hash,
            "live_action_enabled": False,
        }
    )
    return normalized


def with_backtest_lineage(
    lineage: dict[str, Any],
    *,
    backtest_run_id: str,
    backtest_config_hash: str,
    data_snapshot_hash: str,
    manifest_path: str,
) -> dict[str, Any]:
    return normalize_research_lineage(
        {
            **lineage,
            "backtest_run_id": backtest_run_id,
            "backtest_config_hash": backtest_config_hash,
            "data_snapshot_hash": data_snapshot_hash,
            "manifest_path": manifest_path,
            "live_action_enabled": False,
        }
    )


def scan_artifact_hash(scan: dict[str, Any]) -> str:
    payload = {
        "scan_id": scan.get("scan_id"),
        "strategy_id": scan.get("strategy_id"),
        "preset": scan.get("preset"),
        "symbols": scan.get("symbols"),
        "timeframe": scan.get("timeframe"),
        "lookback_days": scan.get("lookback_days"),
        "results": scan.get("results"),
        "status": scan.get("status"),
        "source_contract": scan.get("source_contract"),
        "artifact_dir": scan.get("artifact_dir"),
        "artifacts": scan.get("artifacts"),
        "created_at": scan.get("created_at"),
        "research_lineage": {
            key: value
            for key, value in dict(scan.get("research_lineage") or {}).items()
            if key not in {"scan_artifact_hash", "backtest_run_id", "backtest_config_hash", "data_snapshot_hash", "manifest_path"}
        },
    }
    return stable_hash(payload)


def _validate_source_row(row: dict[str, Any]) -> None:
    _validate_lineage_text(row)
    if row.get("live_action_enabled") not in (False, None):
        raise ResearchLineageError("Markets source row live action must be disabled")
    if not row.get("markets_source_row_id") or not row.get("markets_source_row_hash"):
        raise ResearchLineageError("Markets source row identity is required")


def _validate_lineage(lineage: dict[str, Any]) -> None:
    _validate_lineage_text(lineage)
    if lineage.get("live_action_enabled") is not False:
        raise ResearchLineageError("Research lineage live action must be disabled")
    for key in ("cache_path", "scan_artifact_path", "manifest_path"):
        path = str(lineage.get(key) or "")
        if path and _unsafe_path(path):
            raise ResearchLineageError("Research lineage artifact path is invalid")


def _validate_lineage_text(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True, default=str).lower()
    if any(term in text for term in FORBIDDEN_LINEAGE_TERMS):
        raise ResearchLineageError("Research lineage contains forbidden runtime material")


def _safe_text(raw: Any, max_length: int) -> str:
    value = str(raw or "").strip()[:max_length]
    if _looks_secret_like(value):
        raise ResearchLineageError("Research lineage contains credential material")
    return value


def _safe_path_text(raw: Any, max_length: int) -> str:
    value = _safe_text(raw, max_length).replace("\\", "/")
    if value and _unsafe_path(value):
        raise ResearchLineageError("Research lineage artifact path is invalid")
    return value


def _hash_text(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ResearchLineageError("Research lineage hash is invalid")
    return value


def _unsafe_path(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    return path.startswith("/") or ":" in path or ".." in parts


def _looks_secret_like(value: str) -> bool:
    lowered = value.lower()
    return any(term in lowered for term in FORBIDDEN_LINEAGE_TERMS)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"
