"""Local portfolio workspace contracts and calculations."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import uuid4

from .research_lineage import ResearchLineageError, normalize_research_lineage


SUPPORTED_CURRENCIES = ("USD", "USDT", "TWD", "EUR", "JPY")
PORTFOLIO_TOOLBAR = (
    "BUY",
    "SELL",
    "DIV",
    "SECTORS",
    "PERF/RISK",
    "OPTIMIZE",
    "QUANTSTATS",
    "REPORTS",
    "INDICES",
    "RISK",
    "PLANNING",
    "ECONOMICS",
    "AI",
    "AGENT",
)
PORTFOLIO_TABS = (
    "Performance",
    "Positions",
    "Exposure",
    "Pricing",
    "Risk",
    "Allocation",
    "Correlation",
    "Transactions",
    "Report",
    "Artifacts",
)
BACKTEST_PORTFOLIO_TAB = "Backtest"
ALLOWED_SOURCES = {"manual", "import_json", "demo", "paper_ledger", "backtest"}
PORTFOLIO_REPORT_ROOT = "artifacts/portfolio/reports"
PORTFOLIO_REPORT_FILES = (
    "summary.json",
    "risk.json",
    "performance.csv",
    "allocation.csv",
    "exposure.csv",
    "lineage.json",
    "artifact_health.json",
    "report.md",
    "manifest.json",
)
PORTFOLIO_REPORT_ARTIFACT_KEYS = {
    "summary.json": "summary",
    "risk.json": "risk",
    "performance.csv": "performance",
    "allocation.csv": "allocation",
    "exposure.csv": "exposure",
    "lineage.json": "lineage",
    "artifact_health.json": "artifact_health",
    "report.md": "report",
    "manifest.json": "manifest",
}
DEFAULT_PORTFOLIO_REPORT_INDEX_LIMIT = 8
MAX_POSITIONS = 250
MAX_TRANSACTIONS = 500
FORBIDDEN_ARTIFACT_PATH_TERMS = (
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "secret",
    "private_key",
    "secret_key",
    "password",
    "passphrase",
    "pin:",
    "bearer ",
    "broker",
    "real_order",
    "real_balance",
)
AMOUNT_QUANT = Decimal("0.000001")
MONEY_QUANT = Decimal("0.01")
PCT_QUANT = Decimal("0.01")


class PortfolioError(ValueError):
    """Raised when a local portfolio request violates portfolio rules."""


def default_portfolio_state() -> dict[str, Any]:
    return {
        "active_portfolio_id": None,
        "portfolios": {},
        "updated_at": "not started",
    }


def normalize_portfolio_state(state: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    default = default_portfolio_state()
    portfolios: dict[str, Any] = {}
    invalid_portfolios: dict[str, str] = (
        {str(key): str(value) for key, value in state.get("invalid_portfolios", {}).items()}
        if isinstance(state.get("invalid_portfolios"), dict)
        else {}
    )
    if strict and invalid_portfolios:
        first_key, first_value = next(iter(invalid_portfolios.items()))
        raise PortfolioError(f"Portfolio state is invalid: {first_key}: {first_value}")
    raw_portfolios = state.get("portfolios")
    if isinstance(raw_portfolios, dict):
        for portfolio_id, raw_portfolio in raw_portfolios.items():
            if isinstance(raw_portfolio, dict):
                try:
                    portfolio = _normalize_portfolio(raw_portfolio, source=None)
                except PortfolioError as exc:
                    if strict:
                        raise PortfolioError(
                            f"Stored portfolio {portfolio_id} is invalid: {exc}"
                        ) from exc
                    invalid_portfolios[str(portfolio_id)] = str(exc)
                    continue
                portfolios[portfolio_id] = {**portfolio, "portfolio_id": portfolio_id}
            elif strict:
                raise PortfolioError(f"Stored portfolio {portfolio_id} must be an object")
            else:
                invalid_portfolios[str(portfolio_id)] = "Stored portfolio must be an object"
    elif raw_portfolios not in (None, {}):
        if strict:
            raise PortfolioError("Stored portfolios must be an object")
        invalid_portfolios["portfolios"] = "Stored portfolios must be an object"

    active_id = state.get("active_portfolio_id")
    if active_id not in portfolios:
        active_id = next(iter(portfolios), None)
    return {
        **default,
        "active_portfolio_id": active_id,
        "portfolios": portfolios,
        "invalid_portfolios": invalid_portfolios,
        "updated_at": str(state.get("updated_at") or default["updated_at"]),
    }


def portfolio_payload(
    state: dict[str, Any],
    market_cache: dict[str, Any] | None = None,
    crypto_detail_cache: dict[str, Any] | None = None,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    portfolio_state = normalize_portfolio_state(state, strict=False)
    active = _active_portfolio(portfolio_state)
    priced_active, pricing = _priced_portfolio(active, market_cache, crypto_detail_cache)
    summary = _summary(priced_active)
    allocation = _allocation(priced_active)
    exposure_map = _exposure_map(priced_active)
    performance = _performance(priced_active)
    correlation = _correlation(priced_active)
    risk = _risk_rows(priced_active, summary, allocation)
    report_index = (
        portfolio_report_index(artifact_root, portfolio_state)
        if artifact_root is not None
        else _empty_portfolio_report_index()
    )
    return {
        "active_portfolio_id": portfolio_state["active_portfolio_id"],
        "first_use": active is None,
        "actions": [
            {"action_id": "create", "label": "Create New", "accent": "amber"},
            {"action_id": "import", "label": "Import JSON", "accent": "cyan"},
            {"action_id": "demo", "label": "Load Demo", "accent": "green"},
        ],
        "toolbar": list(PORTFOLIO_TOOLBAR),
        "tabs": _portfolio_tabs(active),
        "portfolios": _portfolio_list(portfolio_state),
        "invalid_portfolios": portfolio_state["invalid_portfolios"],
        "portfolio": priced_active,
        "summary": summary,
        "positions": _position_views(priced_active),
        "transactions": _transactions(priced_active),
        "allocation": allocation,
        "exposure_map": exposure_map,
        "performance": performance,
        "correlation": correlation,
        "risk": risk,
        "report": _report_state(priced_active),
        "report_index": report_index,
        "report_health": _portfolio_report_health_from_index(report_index),
        "pricing": pricing,
        "demo_template": demo_portfolio(),
        "safety": {
            "real_orders": False,
            "private_api_required": False,
            "real_balance": False,
            "margin": False,
            "leverage": False,
            "short": False,
            "derivatives": False,
            "buy_sell_route": "crypto_paper",
        },
    }


def create_portfolio(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    portfolio_state = normalize_portfolio_state(copy.deepcopy(state))
    now = _utc_now()
    portfolio = _normalize_portfolio(
        {
            "portfolio_id": f"portfolio-{uuid4().hex[:12]}",
            "name": _required_text(request.get("name"), "Name", max_length=80),
            "owner": _required_text(request.get("owner"), "Owner", max_length=80),
            "currency": _currency(request.get("currency", "USD")),
            "positions": request.get("positions") or [],
            "transactions": [],
            "source": "manual",
            "created_at": now,
            "updated_at": now,
        },
        source="manual",
    )
    portfolio_state["portfolios"][portfolio["portfolio_id"]] = portfolio
    portfolio_state["active_portfolio_id"] = portfolio["portfolio_id"]
    portfolio_state["updated_at"] = now
    return portfolio_state


def load_demo_portfolio(state: dict[str, Any]) -> dict[str, Any]:
    portfolio_state = normalize_portfolio_state(copy.deepcopy(state))
    portfolio = demo_portfolio()
    portfolio_state["portfolios"][portfolio["portfolio_id"]] = portfolio
    portfolio_state["active_portfolio_id"] = portfolio["portfolio_id"]
    portfolio_state["updated_at"] = portfolio["updated_at"]
    return portfolio_state


def select_portfolio(state: dict[str, Any], portfolio_id: str) -> dict[str, Any]:
    """Point the active-book pointer at an existing portfolio without mutating holdings."""
    portfolio_state = normalize_portfolio_state(copy.deepcopy(state))
    target_id = str(portfolio_id or "").strip()
    if not target_id:
        raise PortfolioError("Portfolio id is required")
    if target_id not in portfolio_state["portfolios"]:
        raise PortfolioError("Unknown portfolio id")
    portfolio_state["active_portfolio_id"] = target_id
    portfolio_state["updated_at"] = _utc_now()
    return portfolio_state


def import_portfolio(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    portfolio_state = normalize_portfolio_state(copy.deepcopy(state))
    mode = str(request.get("mode") or "create_new")
    imported = _normalize_portfolio(request.get("portfolio"), source="import_json")
    now = _utc_now()

    if mode == "create_new":
        imported = {
            **imported,
            "portfolio_id": f"portfolio-{uuid4().hex[:12]}",
            "source": "import_json",
            "updated_at": now,
        }
        portfolio_state["portfolios"][imported["portfolio_id"]] = imported
        portfolio_state["active_portfolio_id"] = imported["portfolio_id"]
    elif mode == "merge":
        target_id = str(
            request.get("target_portfolio_id") or portfolio_state["active_portfolio_id"] or ""
        )
        if target_id not in portfolio_state["portfolios"]:
            raise PortfolioError("Merge target portfolio is required")
        target = copy.deepcopy(portfolio_state["portfolios"][target_id])
        merged = _merge_portfolios(target, imported, now)
        portfolio_state["portfolios"][target_id] = merged
        portfolio_state["active_portfolio_id"] = target_id
    else:
        raise PortfolioError("Import mode must be create_new or merge")

    portfolio_state["updated_at"] = now
    return portfolio_state


def link_paper_portfolio(state: dict[str, Any], paper_state: dict[str, Any]) -> dict[str, Any]:
    portfolio_state = normalize_portfolio_state(copy.deepcopy(state))
    portfolio = _portfolio_from_paper_state(paper_state)
    portfolio_state["portfolios"][portfolio["portfolio_id"]] = portfolio
    portfolio_state["active_portfolio_id"] = portfolio["portfolio_id"]
    portfolio_state["updated_at"] = portfolio["updated_at"]
    return portfolio_state


def delete_portfolio(state: dict[str, Any], portfolio_id: str) -> dict[str, Any]:
    portfolio_state = normalize_portfolio_state(copy.deepcopy(state))
    target_id = str(portfolio_id or "").strip()
    if not target_id:
        raise PortfolioError("Portfolio id is required")
    if target_id not in portfolio_state["portfolios"]:
        raise PortfolioError("Unknown portfolio id")
    del portfolio_state["portfolios"][target_id]
    if portfolio_state.get("active_portfolio_id") == target_id:
        remaining = sorted(
            portfolio_state["portfolios"].values(),
            key=lambda item: str(item.get("updated_at") or ""),
            reverse=True,
        )
        portfolio_state["active_portfolio_id"] = (
            remaining[0]["portfolio_id"] if remaining else None
        )
    portfolio_state["updated_at"] = _utc_now()
    return portfolio_state


def link_backtest_portfolio(
    state: dict[str, Any],
    artifact_root: Path,
    artifact_dir: str | None = None,
) -> dict[str, Any]:
    portfolio_state = normalize_portfolio_state(copy.deepcopy(state))
    portfolio = _portfolio_from_backtest_artifact(artifact_root, artifact_dir)
    portfolio_state["portfolios"][portfolio["portfolio_id"]] = portfolio
    portfolio_state["active_portfolio_id"] = portfolio["portfolio_id"]
    portfolio_state["updated_at"] = portfolio["updated_at"]
    return portfolio_state


def export_active_portfolio(
    state: dict[str, Any],
    artifact_root: Path,
    market_cache: dict[str, Any] | None = None,
    crypto_detail_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active = _active_portfolio(normalize_portfolio_state(state))
    if active is None:
        raise PortfolioError("No active portfolio to export")
    priced_active, pricing = _priced_portfolio(active, market_cache, crypto_detail_cache)
    export_id = (
        f"portfolio-export-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    )
    export_dir = artifact_root / "artifacts" / "portfolio" / "exports" / export_id
    resolved = export_dir.resolve()
    if not resolved.is_relative_to(artifact_root.resolve()):
        raise PortfolioError("Refusing to write portfolio export outside repository")
    artifacts = {
        "portfolio": f"artifacts/portfolio/exports/{export_id}/portfolio.json",
        "manifest": f"artifacts/portfolio/exports/{export_id}/manifest.json",
    }
    manifest = {
        "export_id": export_id,
        "portfolio_id": priced_active["portfolio_id"],
        "source": priced_active["source"],
        "pricing": pricing["status"],
        "position_count": len(priced_active["positions"]),
        "transaction_count": len(priced_active["transactions"]),
        "portfolio_hash": _hash_json(priced_active),
        "created_at": _utc_now(),
        "artifact_files": artifacts,
    }
    export_dir.mkdir(parents=True, exist_ok=True)
    _write_json(export_dir / "portfolio.json", priced_active)
    _write_json(export_dir / "manifest.json", manifest)
    return {
        **priced_active,
        "export_manifest": manifest,
        "export_artifacts": artifacts,
    }


def write_portfolio_report(
    state: dict[str, Any],
    artifact_root: Path,
    market_cache: dict[str, Any] | None = None,
    crypto_detail_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    portfolio_state = normalize_portfolio_state(copy.deepcopy(state))
    active_id = portfolio_state["active_portfolio_id"]
    active = _active_portfolio(portfolio_state)
    if active is None or active_id is None:
        raise PortfolioError("No active portfolio to report")
    priced_active, pricing = _priced_portfolio(active, market_cache, crypto_detail_cache)
    summary = _summary(priced_active)
    allocation = _allocation(priced_active)
    exposure_map = _exposure_map(priced_active)
    performance = _performance(priced_active)
    risk = _risk_rows(priced_active, summary, allocation)
    report_id = (
        f"portfolio-report-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    )
    created_at = _utc_now()
    report_dir = artifact_root / "artifacts" / "portfolio" / "reports" / report_id
    resolved = report_dir.resolve()
    if not resolved.is_relative_to(artifact_root.resolve()):
        raise PortfolioError("Refusing to write portfolio report outside repository")
    artifacts = {
        "summary": f"artifacts/portfolio/reports/{report_id}/summary.json",
        "risk": f"artifacts/portfolio/reports/{report_id}/risk.json",
        "performance": f"artifacts/portfolio/reports/{report_id}/performance.csv",
        "allocation": f"artifacts/portfolio/reports/{report_id}/allocation.csv",
        "exposure": f"artifacts/portfolio/reports/{report_id}/exposure.csv",
        "lineage": f"artifacts/portfolio/reports/{report_id}/lineage.json",
        "artifact_health": f"artifacts/portfolio/reports/{report_id}/artifact_health.json",
        "report": f"artifacts/portfolio/reports/{report_id}/report.md",
        "manifest": f"artifacts/portfolio/reports/{report_id}/manifest.json",
    }
    lineage = _portfolio_report_lineage(report_id, priced_active, pricing, created_at)
    artifact_health = _portfolio_report_artifact_health(
        artifact_root,
        report_id,
        priced_active.get("linked_artifacts", []),
        created_at,
    )
    manifest = {
        "report_id": report_id,
        "artifact_contract": "local_portfolio_report_artifacts_v3",
        "portfolio_id": priced_active["portfolio_id"],
        "source": priced_active["source"],
        "pricing": pricing["status"],
        "position_count": len(priced_active["positions"]),
        "transaction_count": len(priced_active["transactions"]),
        "exposure_row_count": len(exposure_map),
        "risk_row_count": len(risk),
        "performance_points": len(performance),
        "lineage_summary": lineage["summary"],
        "artifact_health": {"status": artifact_health["status"], **artifact_health["summary"]},
        "safety": {
            "local_artifact_only": True,
            "linked_artifacts_read_only": True,
            "real_orders": False,
            "private_api_required": False,
            "real_balance": False,
            "optimizer_execution": False,
            "live_action_enabled": False,
        },
        "created_at": created_at,
        "artifact_files": artifacts,
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    _write_json(report_dir / "summary.json", summary)
    _write_json(report_dir / "risk.json", {"rows": risk})
    _write_csv(
        report_dir / "performance.csv", performance, ["period", "value", "period_return_pct"]
    )
    _write_csv(report_dir / "allocation.csv", allocation, ["sector", "value", "weight_pct"])
    _write_csv(
        report_dir / "exposure.csv",
        exposure_map,
        [
            "symbol",
            "sector",
            "market_value",
            "weight_pct",
            "pnl",
            "pnl_pct",
            "beta_contribution",
            "volatility_contribution_pct",
            "concentration_state",
            "price_source",
            "pricing_state",
        ],
    )
    _write_json(report_dir / "lineage.json", lineage)
    _write_json(report_dir / "artifact_health.json", artifact_health)
    _write_text_report(
        report_dir / "report.md", priced_active, summary, risk, exposure_map, pricing, manifest
    )
    _write_json(report_dir / "manifest.json", manifest)
    updated = copy.deepcopy(portfolio_state["portfolios"][str(active_id)])
    updated["last_report"] = manifest
    portfolio_state["portfolios"][str(active_id)] = _normalize_portfolio(
        updated,
        source=str(updated.get("source") or "manual"),
    )
    portfolio_state["updated_at"] = manifest["created_at"]
    return portfolio_state


def portfolio_report_index(
    artifact_root: Path,
    state: dict[str, Any] | None = None,
    *,
    max_reports: int = DEFAULT_PORTFOLIO_REPORT_INDEX_LIMIT,
) -> dict[str, Any]:
    """Return metadata-only local Portfolio report inventory for agent selection."""

    root = artifact_root.resolve()
    report_root = (artifact_root / PORTFOLIO_REPORT_ROOT).resolve()
    if not report_root.is_relative_to(root):
        raise PortfolioError("Refusing to inspect Portfolio reports outside repository")
    limit = _bounded_report_index_limit(max_reports)
    report_dirs: list[Path] = []
    if report_root.exists():
        report_dirs = [
            path
            for path in report_root.iterdir()
            if path.is_dir() and path.name.startswith("portfolio-report-")
        ]
    report_dirs = sorted(report_dirs, key=lambda path: path.stat().st_mtime, reverse=True)[:limit]
    active_report = _active_report_metadata(state)
    rows = [
        _portfolio_report_index_row(root, report_dir, active_report)
        for report_dir in report_dirs
    ]
    recovery_queue = _portfolio_report_index_recovery_queue(rows)
    latest = rows[0] if rows else {}
    return {
        "mode": "local_portfolio_report_index",
        "contract": "portfolio_report_index_v1",
        "generated_at": _utc_now(),
        "root": PORTFOLIO_REPORT_ROOT,
        "summary": {
            "report_count": len(rows),
            "complete_report_count": sum(1 for row in rows if bool(row.get("complete"))),
            "incomplete_report_count": sum(
                1 for row in rows if not bool(row.get("complete"))
            ),
            "missing_artifact_count": sum(
                int(row.get("missing_artifact_count") or 0) for row in rows
            ),
            "active_report_id": str(active_report.get("report_id") or ""),
            "latest_report_id": str(latest.get("report_id") or ""),
            "recovery_queue_count": len(recovery_queue),
        },
        "reports": rows,
        "recovery_queue": recovery_queue,
        "recommended_actions": [
            {
                "action_id": "portfolio_report",
                "endpoint": "/api/portfolio/report",
                "method": "POST",
                "ready": True,
                "reason": "Regenerate the active local Portfolio report when report artifacts are missing or stale.",
            }
        ],
        "safety": {
            "metadata_only": True,
            "file_content_read": False,
            "writes_local_artifacts": False,
            "destructive_actions_enabled": False,
            "real_orders": False,
            "real_balance": False,
            "broker_routing": False,
            "live_trading": False,
            "secret_values_returned": False,
        },
    }


def portfolio_report_health_payload(
    artifact_root: Path,
    state: dict[str, Any] | None = None,
    *,
    max_reports: int = DEFAULT_PORTFOLIO_REPORT_INDEX_LIMIT,
) -> dict[str, Any]:
    """Return metadata-only health for local Portfolio report artifacts."""

    return _portfolio_report_health_from_index(
        portfolio_report_index(artifact_root, state, max_reports=max_reports)
    )


def demo_portfolio() -> dict[str, Any]:
    now = "2026-05-22T00:00:00Z"
    positions = [
        _demo_position(
            "AAPL", "Apple Inc.", "Technology", "18", "170.25", "188.10", "0.42", "1.18", "24.0"
        ),
        _demo_position(
            "MSFT",
            "Microsoft Corp.",
            "Technology",
            "14",
            "390.10",
            "423.45",
            "0.28",
            "1.05",
            "22.0",
        ),
        _demo_position(
            "NVDA", "NVIDIA Corp.", "Technology", "9", "820.00", "965.25", "0.90", "1.42", "38.0"
        ),
        _demo_position(
            "GOOGL",
            "Alphabet Inc.",
            "Communication",
            "20",
            "136.50",
            "154.80",
            "0.21",
            "1.09",
            "25.0",
        ),
        _demo_position(
            "AMZN", "Amazon.com Inc.", "Consumer", "16", "145.40", "178.65", "0.35", "1.16", "28.0"
        ),
        _demo_position(
            "META",
            "Meta Platforms",
            "Communication",
            "7",
            "428.75",
            "482.20",
            "0.31",
            "1.24",
            "30.0",
        ),
        _demo_position(
            "JPM", "JPMorgan Chase", "Financials", "22", "160.80", "195.50", "0.16", "1.02", "18.0"
        ),
        _demo_position(
            "V", "Visa Inc.", "Financials", "12", "236.00", "274.40", "0.19", "0.96", "17.0"
        ),
        _demo_position(
            "XOM", "Exxon Mobil", "Energy", "28", "103.30", "118.70", "-0.12", "0.88", "21.0"
        ),
        _demo_position(
            "COST", "Costco Wholesale", "Consumer", "4", "690.00", "812.10", "0.24", "0.84", "16.0"
        ),
        _demo_position(
            "UNH",
            "UnitedHealth Group",
            "Healthcare",
            "5",
            "465.30",
            "501.25",
            "-0.08",
            "0.78",
            "15.0",
        ),
        _demo_position(
            "AVGO", "Broadcom Inc.", "Technology", "3", "1210.00", "1435.80", "0.55", "1.31", "34.0"
        ),
    ]
    return _normalize_portfolio(
        {
            "portfolio_id": "portfolio-demo",
            "name": "Demo Portfolio",
            "owner": "Local User",
            "currency": "USD",
            "source": "demo",
            "positions": positions,
            "transactions": [_buy_transaction(position, now) for position in positions],
            "created_at": now,
            "updated_at": now,
        },
        source="demo",
    )


def _active_portfolio(state: dict[str, Any]) -> dict[str, Any] | None:
    active_id = state.get("active_portfolio_id")
    if active_id is None:
        return None
    portfolio = state.get("portfolios", {}).get(active_id)
    return copy.deepcopy(portfolio) if isinstance(portfolio, dict) else None


def _portfolio_list(state: dict[str, Any]) -> list[dict[str, str]]:
    portfolios = []
    for portfolio in state.get("portfolios", {}).values():
        if not isinstance(portfolio, dict):
            continue
        portfolios.append(
            {
                "portfolio_id": str(portfolio.get("portfolio_id")),
                "name": str(portfolio.get("name")),
                "owner": str(portfolio.get("owner")),
                "currency": str(portfolio.get("currency")),
                "source": str(portfolio.get("source")),
            }
        )
    return portfolios


def _priced_portfolio(
    portfolio: dict[str, Any] | None,
    market_cache: dict[str, Any] | None,
    crypto_detail_cache: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    price_book, status = _provider_price_book(market_cache, crypto_detail_cache)
    if portfolio is None:
        return None, _pricing_payload(status, [])
    priced = copy.deepcopy(portfolio)
    positions = []
    for position in priced.get("positions", []):
        row = dict(position)
        quote = price_book.get(str(row.get("symbol", "")))
        if quote:
            row["last_price"] = quote["price"]
            row["day_change_pct"] = quote["chg_pct"]
            row["price_source"] = quote["source"]
            row["price_state"] = quote["state"]
            row["price_provider_id"] = quote["provider_id"]
            row["price_retrieved_at"] = quote["retrieved_at"]
            row["price_cache_path"] = quote["cache_path"]
        else:
            fallback_source = (
                "provider_unavailable"
                if row.get("asset_class") == "Crypto"
                else "portfolio_snapshot"
            )
            fallback_state = (
                "unavailable" if row.get("asset_class") == "Crypto" else "local_snapshot"
            )
            row["price_source"] = fallback_source
            row["price_state"] = fallback_state
            row["price_provider_id"] = ""
            row["price_retrieved_at"] = str(priced.get("updated_at") or "not refreshed")
            row["price_cache_path"] = ""
        positions.append(row)
    priced["positions"] = positions
    priced["pricing"] = _pricing_payload(status, positions)
    return priced, priced["pricing"]


def _provider_price_book(
    market_cache: dict[str, Any] | None,
    crypto_detail_cache: dict[str, Any] | None,
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    price_book: dict[str, dict[str, str]] = {}
    status = {
        "source": "provider_unavailable",
        "state": "unavailable",
        "provider_id": "",
        "retrieved_at": "not refreshed",
        "cache_path": "",
        "cache_hash": "",
    }
    if isinstance(market_cache, dict):
        market_status = (
            market_cache.get("status") if isinstance(market_cache.get("status"), dict) else {}
        )
        rows = market_cache.get("rows") if isinstance(market_cache.get("rows"), list) else []
        market_source = str(market_status.get("source") or "")
        market_rows_allowed = bool(market_source) and market_source not in {
            "offline_fixture",
            "public_provider_unavailable",
        }
        if market_rows_allowed:
            status = {
                "source": str(market_status.get("source") or "market_cache"),
                "state": str(market_status.get("state") or "stale"),
                "provider_id": str(market_status.get("provider_id") or ""),
                "retrieved_at": str(market_status.get("last_update") or "not refreshed"),
                "cache_path": str(
                    market_status.get("cache_path") or "market_data/crypto_latest.json"
                ),
                "cache_hash": _hash_json(market_cache),
            }
            for row in rows:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("symbol") or "")
                price = str(row.get("price") or "")
                if symbol and price and price != "N/A":
                    try:
                        provider_price = _money(_positive_decimal(price, "Provider price"))
                        provider_change = _ratio_text(
                            _finite_decimal(row.get("chg_pct", "0"), "Provider change percent")
                        )
                    except PortfolioError:
                        continue
                    price_book[symbol] = {
                        "price": provider_price,
                        "chg_pct": provider_change,
                        "source": str(row.get("source") or status["source"]),
                        "state": str(row.get("state") or status["state"]),
                        "provider_id": str(row.get("provider_id") or status["provider_id"]),
                        "retrieved_at": str(row.get("retrieved_at") or status["retrieved_at"]),
                        "cache_path": str(row.get("cache_path") or status["cache_path"]),
                    }
    if isinstance(crypto_detail_cache, dict):
        detail_status = (
            crypto_detail_cache.get("status")
            if isinstance(crypto_detail_cache.get("status"), dict)
            else {}
        )
        candles = (
            crypto_detail_cache.get("candles")
            if isinstance(crypto_detail_cache.get("candles"), list)
            else []
        )
        symbol = str(detail_status.get("symbol") or "")
        if (
            symbol
            and symbol not in price_book
            and detail_status.get("source")
            in {"binance_public", "kraken_public", "coinbase_public"}
        ):
            last_candle = next(
                (
                    row
                    for row in reversed(candles)
                    if isinstance(row, dict) and row.get("closed") is True
                ),
                None,
            )
            close_price = ""
            if last_candle:
                try:
                    close_price = _money(
                        _positive_decimal(last_candle.get("close"), "Provider close")
                    )
                except PortfolioError:
                    close_price = ""
            if last_candle and close_price:
                source = str(detail_status.get("source") or "crypto_detail_cache")
                price_book[symbol] = {
                    "price": close_price,
                    "chg_pct": "0.00",
                    "source": source,
                    "state": str(detail_status.get("state") or "stale"),
                    "provider_id": str(detail_status.get("provider_id") or ""),
                    "retrieved_at": str(detail_status.get("last_update") or "not refreshed"),
                    "cache_path": f"market_data/crypto/{symbol}/{detail_status.get('timeframe') or '15m'}.json",
                }
                status = {
                    "source": source,
                    "state": str(detail_status.get("state") or "stale"),
                    "provider_id": str(detail_status.get("provider_id") or ""),
                    "retrieved_at": str(detail_status.get("last_update") or "not refreshed"),
                    "cache_path": f"market_data/crypto/{symbol}/{detail_status.get('timeframe') or '15m'}.json",
                    "cache_hash": _hash_json(crypto_detail_cache),
                }
    return price_book, status


def _pricing_payload(status: dict[str, str], positions: list[dict[str, Any]]) -> dict[str, Any]:
    provider_count = sum(
        1
        for position in positions
        if position.get("price_source") in {"binance_public", "kraken_public", "coinbase_public"}
    )
    local_count = sum(
        1 for position in positions if position.get("price_source") == "portfolio_snapshot"
    )
    unavailable_count = sum(
        1 for position in positions if position.get("price_source") == "provider_unavailable"
    )
    return {
        "status": {
            **status,
            "provider_price_count": str(provider_count),
            "local_snapshot_count": str(local_count),
            "unavailable_count": str(unavailable_count),
            "priced_position_count": str(len(positions)),
        },
        "sources": [
            {
                "symbol": str(position.get("symbol", "")),
                "source": str(position.get("price_source", "")),
                "state": str(position.get("price_state", "")),
                "provider_id": str(position.get("price_provider_id", "")),
                "retrieved_at": str(position.get("price_retrieved_at", "")),
                "cache_path": str(position.get("price_cache_path", "")),
            }
            for position in positions
        ],
    }


def _portfolio_tabs(portfolio: dict[str, Any] | None) -> list[str]:
    tabs = list(PORTFOLIO_TABS)
    if portfolio and portfolio.get("source") == "backtest" and portfolio.get("backtest_context"):
        tabs.insert(-1, BACKTEST_PORTFOLIO_TAB)
    return tabs


def _backtest_context(raw_context: Any) -> dict[str, Any]:
    if not isinstance(raw_context, dict):
        return {}
    artifact_files = raw_context.get("artifact_files")
    context: dict[str, Any] = {
        "run_id": _optional_text(raw_context.get("run_id"), "", max_length=80),
        "strategy": _optional_text(raw_context.get("strategy"), "", max_length=80),
        "strategy_label": _optional_text(raw_context.get("strategy_label"), "", max_length=120),
        "engine": _optional_text(raw_context.get("engine"), "", max_length=120),
        "provider": _optional_text(raw_context.get("provider"), "", max_length=120),
        "data_state": _optional_text(raw_context.get("data_state"), "", max_length=80),
        "final_equity": _optional_text(raw_context.get("final_equity"), "", max_length=40),
        "total_return_pct": _optional_text(raw_context.get("total_return_pct"), "", max_length=40),
        "max_drawdown_pct": _optional_text(raw_context.get("max_drawdown_pct"), "", max_length=40),
        "best_period_return_pct": _optional_text(
            raw_context.get("best_period_return_pct"), "", max_length=40
        ),
        "worst_period_return_pct": _optional_text(
            raw_context.get("worst_period_return_pct"), "", max_length=40
        ),
        "period_count": _optional_text(raw_context.get("period_count"), "", max_length=20),
        "trade_count": _optional_text(raw_context.get("trade_count"), "", max_length=20),
        "signal_count": _optional_text(raw_context.get("signal_count"), "", max_length=20),
        "returns_curve_rows": _optional_text(
            raw_context.get("returns_curve_rows"), "", max_length=20
        ),
        "source": "local_backtest_artifacts",
        "safety": "read_only_no_live_order",
        "artifact_files": {
            _optional_text(key, "", max_length=80): _optional_text(value, "", max_length=240)
            for key, value in artifact_files.items()
            if isinstance(artifact_files, dict) and str(key).strip() and str(value).strip()
        }
        if isinstance(artifact_files, dict)
        else {},
    }
    research_lineage = _optional_research_lineage(raw_context.get("research_lineage"))
    if research_lineage:
        context["research_lineage"] = research_lineage
    return context


def _last_report(raw_report: Any) -> dict[str, Any]:
    if not isinstance(raw_report, dict):
        return {}
    artifact_files = raw_report.get("artifact_files")
    if not raw_report.get("report_id") and not artifact_files:
        return {}
    raw_safety = raw_report.get("safety") if isinstance(raw_report.get("safety"), dict) else {}
    return {
        "report_id": _optional_text(raw_report.get("report_id"), "", max_length=100),
        "portfolio_id": _optional_text(raw_report.get("portfolio_id"), "", max_length=100),
        "source": _optional_text(raw_report.get("source"), "", max_length=80),
        "created_at": _optional_text(raw_report.get("created_at"), "", max_length=80),
        "position_count": _optional_text(raw_report.get("position_count"), "", max_length=20),
        "transaction_count": _optional_text(raw_report.get("transaction_count"), "", max_length=20),
        "risk_row_count": _optional_text(raw_report.get("risk_row_count"), "", max_length=20),
        "performance_points": _optional_text(
            raw_report.get("performance_points"), "", max_length=20
        ),
        "exposure_row_count": _optional_text(
            raw_report.get("exposure_row_count"), "", max_length=20
        ),
        "lineage_summary": _report_string_dict(raw_report.get("lineage_summary")),
        "artifact_health": _report_artifact_health_summary(raw_report.get("artifact_health")),
        "safety": {
            key: bool(raw_safety.get(key))
            for key in (
                "local_artifact_only",
                "linked_artifacts_read_only",
                "real_orders",
                "private_api_required",
                "real_balance",
                "optimizer_execution",
                "live_action_enabled",
            )
        },
        "artifact_files": {
            _optional_text(key, "", max_length=80): _safe_portfolio_report_artifact(value)
            for key, value in artifact_files.items()
            if isinstance(artifact_files, dict)
            and str(key).strip()
            and _safe_portfolio_report_artifact(value)
        }
        if isinstance(artifact_files, dict)
        else {},
    }


def _safe_portfolio_report_artifact(raw_path: Any) -> str:
    path = _optional_text(raw_path, "", max_length=240)
    if not path.startswith("artifacts/portfolio/reports/"):
        return ""
    if ".." in Path(path).parts:
        return ""
    return path


def _optional_research_lineage(raw: Any) -> dict[str, Any]:
    if raw in (None, "", {}):
        return {}
    try:
        return normalize_research_lineage(raw)
    except ResearchLineageError as exc:
        raise PortfolioError(str(exc)) from exc


def _report_string_dict(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {
        _optional_text(key, "", max_length=80): _optional_text(value, "", max_length=240)
        for key, value in raw.items()
        if str(key).strip()
    }


def _report_artifact_health_summary(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else raw
    result = _report_string_dict(summary)
    if raw.get("status"):
        result["status"] = _optional_text(raw.get("status"), "", max_length=80)
    return result


def _normalize_portfolio(raw: Any, source: str | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise PortfolioError("Portfolio JSON object is required")

    transactions = _normalize_transactions(raw.get("transactions", []))
    raw_positions = raw.get("positions", [])
    if raw_positions:
        positions = _normalize_positions(raw_positions)
        if transactions:
            _assert_positions_match_transactions(positions, transactions)
    elif transactions:
        positions = _positions_from_transactions(transactions)
    else:
        positions = []

    portfolio_source = source or str(raw.get("source") or "manual")
    if portfolio_source not in ALLOWED_SOURCES:
        portfolio_source = "manual"
    now = _utc_now()
    portfolio_id = str(raw.get("portfolio_id") or f"portfolio-{uuid4().hex[:12]}")
    return {
        "portfolio_id": portfolio_id,
        "name": _required_text(raw.get("name"), "portfolio.name", max_length=80),
        "owner": _optional_text(raw.get("owner"), "Local User", max_length=80),
        "currency": _currency(raw.get("currency", "USD")),
        "positions": positions,
        "transactions": transactions,
        "source": portfolio_source,
        "linked_artifacts": _linked_artifacts(raw.get("linked_artifacts", [])),
        "backtest_context": _backtest_context(raw.get("backtest_context"))
        if portfolio_source == "backtest"
        else {},
        "last_report": _last_report(raw.get("last_report")),
        "created_at": str(raw.get("created_at") or now),
        "updated_at": str(raw.get("updated_at") or now),
    }


def _normalize_position(raw: dict[str, Any]) -> dict[str, str]:
    symbol = _symbol(raw.get("symbol"))
    quantity = _positive_decimal(raw.get("quantity"), "Position quantity", allow_zero=False)
    avg_cost = _positive_decimal(raw.get("avg_cost", raw.get("cost", "0")), "Average cost")
    last_price = _positive_decimal(raw.get("last_price", avg_cost), "Last price")
    return {
        "symbol": symbol,
        "name": _optional_text(raw.get("name"), symbol, max_length=120),
        "asset_class": _optional_text(raw.get("asset_class"), "Equity", max_length=40),
        "sector": _optional_text(raw.get("sector"), "Unclassified", max_length=60),
        "quantity": _amount(quantity),
        "avg_cost": _money(avg_cost),
        "last_price": _money(last_price),
        "currency": _currency(raw.get("currency", "USD")),
        "day_change_pct": _pct_value(raw.get("day_change_pct", "0")),
        "beta": _ratio_value(raw.get("beta", "1")),
        "volatility_pct": _pct_value(raw.get("volatility_pct", "20")),
    }


def _normalize_positions(raw_positions: Any) -> list[dict[str, str]]:
    if not isinstance(raw_positions, list):
        raise PortfolioError("Positions must be a list")
    if len(raw_positions) > MAX_POSITIONS:
        raise PortfolioError(f"Positions exceed limit of {MAX_POSITIONS}")
    positions = []
    for raw in raw_positions:
        if not isinstance(raw, dict):
            raise PortfolioError("Position rows must be objects")
        positions.append(_normalize_position(raw))
    return positions


def _normalize_transactions(raw_transactions: Any) -> list[dict[str, str]]:
    if raw_transactions in (None, ""):
        return []
    if not isinstance(raw_transactions, list):
        raise PortfolioError("Transactions must be a list")
    if len(raw_transactions) > MAX_TRANSACTIONS:
        raise PortfolioError(f"Transactions exceed limit of {MAX_TRANSACTIONS}")
    transactions: list[dict[str, str]] = []
    running: dict[str, Decimal] = {}
    for raw in raw_transactions:
        if not isinstance(raw, dict):
            raise PortfolioError("Transaction rows must be objects")
        side = str(raw.get("side") or "BUY").upper()
        if side not in {"BUY", "SELL", "DIV"}:
            raise PortfolioError("Transaction side must be BUY, SELL, or DIV")
        symbol = _symbol(raw.get("symbol"))
        quantity = _positive_decimal(raw.get("quantity", "0"), "Transaction quantity")
        price = _positive_decimal(raw.get("price", "0"), "Transaction price")
        if side == "BUY":
            running[symbol] = running.get(symbol, Decimal("0")) + quantity
        elif side == "SELL":
            held = running.get(symbol, Decimal("0"))
            if quantity > held:
                raise PortfolioError("Transaction sell exceeds current holding")
            running[symbol] = held - quantity
        transactions.append(
            {
                "transaction_id": str(raw.get("transaction_id") or f"txn-{uuid4().hex[:12]}"),
                "date": str(raw.get("date") or _utc_now()),
                "symbol": symbol,
                "side": side,
                "quantity": _amount(quantity),
                "price": _money(price),
                "amount": _money(quantity * price),
                "source": _optional_text(raw.get("source"), "import_json", max_length=40),
            }
        )
    return transactions


def _assert_positions_match_transactions(
    positions: list[dict[str, str]],
    transactions: list[dict[str, str]],
) -> None:
    position_quantities = {
        position["symbol"]: Decimal(position["quantity"]) for position in positions
    }
    transaction_positions = _positions_from_transactions(transactions)
    transaction_quantities = {
        position["symbol"]: Decimal(position["quantity"]) for position in transaction_positions
    }
    if position_quantities != transaction_quantities:
        raise PortfolioError("Positions do not match transaction holdings")


def _positions_from_transactions(transactions: list[dict[str, str]]) -> list[dict[str, str]]:
    positions: dict[str, dict[str, Decimal | str]] = {}
    for transaction in transactions:
        symbol = transaction["symbol"]
        side = transaction["side"]
        quantity = Decimal(transaction["quantity"])
        price = Decimal(transaction["price"])
        current = positions.get(
            symbol,
            {
                "symbol": symbol,
                "quantity": Decimal("0"),
                "avg_cost": price,
                "last_price": price,
            },
        )
        held = current["quantity"]
        if not isinstance(held, Decimal):
            raise PortfolioError("Invalid transaction state")
        if side == "BUY":
            new_quantity = held + quantity
            current["avg_cost"] = (
                (held * Decimal(str(current["avg_cost"]))) + (quantity * price)
            ) / new_quantity
            current["quantity"] = new_quantity
            current["last_price"] = price
            positions[symbol] = current
        elif side == "SELL":
            new_quantity = held - quantity
            if new_quantity < 0:
                raise PortfolioError("Transaction sell exceeds current holding")
            current["quantity"] = new_quantity
            current["last_price"] = price
            if new_quantity == 0:
                positions.pop(symbol, None)
            else:
                positions[symbol] = current
    return [
        _normalize_position(
            {
                "symbol": symbol,
                "quantity": state["quantity"],
                "avg_cost": state["avg_cost"],
                "last_price": state["last_price"],
            }
        )
        for symbol, state in positions.items()
        if isinstance(state.get("quantity"), Decimal) and state["quantity"] > 0
    ]


def _merge_portfolios(
    target: dict[str, Any], imported: dict[str, Any], updated_at: str
) -> dict[str, Any]:
    if target.get("positions") and not target.get("transactions"):
        raise PortfolioError("Merge target requires transaction history")
    if target.get("positions") and target.get("transactions"):
        _assert_positions_match_transactions(target["positions"], target["transactions"])
    merged_positions = {
        position["symbol"]: dict(position) for position in target.get("positions", [])
    }
    transaction_ids = {
        str(transaction.get("transaction_id"))
        for transaction in target.get("transactions", [])
        if isinstance(transaction, dict)
    }
    merged_transactions = list(target.get("transactions", []))
    for incoming in imported["positions"]:
        symbol = incoming["symbol"]
        if symbol not in merged_positions:
            merged_positions[symbol] = dict(incoming)
            continue
        current = merged_positions[symbol]
        current_quantity = Decimal(current["quantity"])
        incoming_quantity = Decimal(incoming["quantity"])
        total_quantity = current_quantity + incoming_quantity
        avg_cost = (
            (current_quantity * Decimal(current["avg_cost"]))
            + (incoming_quantity * Decimal(incoming["avg_cost"]))
        ) / total_quantity
        merged_positions[symbol] = {
            **current,
            "quantity": _amount(total_quantity),
            "avg_cost": _money(avg_cost),
            "last_price": incoming["last_price"],
            "sector": incoming.get("sector", current.get("sector", "Unclassified")),
        }
    for transaction in imported.get("transactions", []):
        merged_transaction = dict(transaction)
        if merged_transaction.get("transaction_id") in transaction_ids:
            merged_transaction["transaction_id"] = f"txn-{uuid4().hex[:12]}"
        transaction_ids.add(str(merged_transaction["transaction_id"]))
        merged_transactions.append(merged_transaction)
    return {
        **target,
        "positions": list(merged_positions.values()),
        "transactions": merged_transactions,
        "source": "import_json",
        "updated_at": updated_at,
    }


def _portfolio_from_paper_state(paper_state: dict[str, Any]) -> dict[str, Any]:
    account = paper_state.get("account") if isinstance(paper_state.get("account"), dict) else {}
    if account.get("mode") != "paper":
        raise PortfolioError("Paper ledger source must be paper mode")
    quote_asset = _currency(account.get("quote_asset", "USDT"))
    raw_positions = paper_state.get("positions")
    if not isinstance(raw_positions, dict):
        raise PortfolioError("Paper ledger positions must be an object")
    if len(raw_positions) > MAX_POSITIONS:
        raise PortfolioError(f"Paper ledger positions exceed limit of {MAX_POSITIONS}")
    positions = []
    for symbol, position in raw_positions.items():
        if not isinstance(position, dict):
            raise PortfolioError("Paper ledger position rows must be objects")
        positions.append(
            _normalize_position(
                {
                    "symbol": position.get("symbol", symbol),
                    "name": position.get("symbol", symbol),
                    "asset_class": "Crypto",
                    "sector": "Digital Assets",
                    "quantity": position.get("quantity"),
                    "avg_cost": position.get("avg_price"),
                    "last_price": position.get("avg_price"),
                    "currency": quote_asset,
                }
            )
        )
    fills = paper_state.get("fills")
    if not isinstance(fills, list):
        raise PortfolioError("Paper ledger fills must be a list")
    if len(fills) > MAX_TRANSACTIONS:
        raise PortfolioError(f"Paper ledger fills exceed limit of {MAX_TRANSACTIONS}")
    transactions = []
    for fill in fills:
        if not isinstance(fill, dict):
            raise PortfolioError("Paper ledger fill rows must be objects")
        transactions.append(_transaction_from_fill(fill, "paper_ledger"))
    if not positions and not transactions:
        raise PortfolioError("No paper ledger positions or fills to link")
    now = _utc_now()
    return _normalize_portfolio(
        {
            "portfolio_id": "portfolio-paper-ledger",
            "name": "Paper Ledger Portfolio",
            "owner": "Local User",
            "currency": quote_asset,
            "source": "paper_ledger",
            "positions": positions,
            "transactions": transactions,
            "linked_artifacts": _paper_linked_artifacts(paper_state),
            "created_at": now,
            "updated_at": now,
        },
        source="paper_ledger",
    )


def _portfolio_from_backtest_artifact(
    artifact_root: Path,
    artifact_dir: str | None,
) -> dict[str, Any]:
    run_dir = _resolve_backtest_run_dir(artifact_root, artifact_dir)
    manifest = _read_artifact_json(run_dir / "manifest.json")
    summary = _read_artifact_json(run_dir / "summary.json")
    trades = _read_backtest_trades(run_dir / "trades.csv")
    transactions = [_transaction_from_backtest_trade(trade) for trade in trades]
    positions = _positions_from_transactions(transactions)
    now = _utc_now()
    run_id = str(manifest.get("run_id") or run_dir.name)
    return _normalize_portfolio(
        {
            "portfolio_id": f"portfolio-backtest-{run_id}",
            "name": f"Backtest {run_id}",
            "owner": "Local User",
            "currency": "USDT",
            "source": "backtest",
            "positions": positions,
            "transactions": transactions,
            "linked_artifacts": _backtest_linked_artifacts(run_dir, artifact_root, manifest),
            "backtest_context": _backtest_artifact_context(
                run_dir,
                artifact_root,
                manifest,
                summary,
                trade_count=len(trades),
            ),
            "created_at": str(manifest.get("created_at") or now),
            "updated_at": now,
        },
        source="backtest",
    )


def _paper_linked_artifacts(paper_state: dict[str, Any]) -> list[str]:
    artifacts = ["artifacts/paper/paper_state.json"]
    dates = {
        str(fill.get("filled_at", ""))[:10]
        for fill in paper_state.get("fills", [])
        if isinstance(fill, dict) and len(str(fill.get("filled_at", ""))) >= 10
    }
    for date_key in sorted(dates):
        artifacts.extend(
            [
                f"artifacts/paper/{date_key}/orders.jsonl",
                f"artifacts/paper/{date_key}/fills.jsonl",
                f"artifacts/paper/{date_key}/ledger.jsonl",
                f"artifacts/paper/{date_key}/account_snapshots.jsonl",
            ]
        )
    return artifacts[:20]


def _backtest_linked_artifacts(
    run_dir: Path, artifact_root: Path, manifest: dict[str, Any]
) -> list[str]:
    artifact_files = _safe_backtest_artifact_files(run_dir, artifact_root, manifest)
    paths = [
        artifact_files.get("manifest"),
        artifact_files.get("summary"),
        artifact_files.get("trades"),
        artifact_files.get("signals"),
        artifact_files.get("indicators"),
        artifact_files.get("returns_analysis"),
        artifact_files.get("returns_curve"),
        artifact_files.get("data_snapshot"),
        artifact_files.get("provenance"),
    ]
    return [str(path) for path in paths if path]


def _safe_backtest_artifact_files(
    run_dir: Path, artifact_root: Path, manifest: dict[str, Any]
) -> dict[str, str]:
    raw_artifact_files = (
        manifest.get("artifact_files") if isinstance(manifest.get("artifact_files"), dict) else {}
    )
    expected = {
        "manifest": "manifest.json",
        "summary": "summary.json",
        "trades": "trades.csv",
        "signals": "signals.csv",
        "indicators": "indicators.json",
        "returns_analysis": "returns_analysis.json",
        "returns_curve": "returns_curve.csv",
        "data_snapshot": "data_snapshot.json",
        "provenance": "provenance.json",
    }
    safe_paths: dict[str, str] = {}
    resolved_root = artifact_root.resolve()
    resolved_run_dir = run_dir.resolve()
    for key, filename in expected.items():
        raw_path = raw_artifact_files.get(key)
        if raw_path:
            candidate = (artifact_root / str(raw_path)).resolve()
        else:
            candidate = (run_dir / filename).resolve()
        if not candidate.is_relative_to(resolved_run_dir) or not candidate.is_file():
            continue
        safe_paths[key] = candidate.relative_to(resolved_root).as_posix()
    return safe_paths


def _backtest_artifact_context(
    run_dir: Path,
    artifact_root: Path,
    manifest: dict[str, Any],
    summary: dict[str, Any],
    *,
    trade_count: int,
) -> dict[str, Any]:
    returns_analysis = _read_optional_artifact_json(run_dir / "returns_analysis.json")
    artifact_files = _safe_backtest_artifact_files(run_dir, artifact_root, manifest)
    context: dict[str, Any] = {
        "run_id": str(manifest.get("run_id") or run_dir.name),
        "strategy": str(manifest.get("strategy") or summary.get("strategy") or ""),
        "strategy_label": str(
            manifest.get("strategy_label") or summary.get("strategy_label") or ""
        ),
        "engine": str(manifest.get("engine") or ""),
        "provider": str(manifest.get("provider") or summary.get("data_provider") or ""),
        "data_state": str(summary.get("data_state") or ""),
        "final_equity": str(summary.get("final_equity") or ""),
        "total_return_pct": str(
            returns_analysis.get("total_return_pct") or summary.get("return_pct") or ""
        ),
        "max_drawdown_pct": str(returns_analysis.get("max_drawdown_pct") or ""),
        "best_period_return_pct": str(returns_analysis.get("best_period_return_pct") or ""),
        "worst_period_return_pct": str(returns_analysis.get("worst_period_return_pct") or ""),
        "period_count": str(returns_analysis.get("period_count") or ""),
        "trade_count": str(trade_count),
        "signal_count": str(_csv_row_count(run_dir / "signals.csv")),
        "returns_curve_rows": str(_csv_row_count(run_dir / "returns_curve.csv")),
        "artifact_files": {
            str(key): str(value)
            for key, value in artifact_files.items()
            if key in {"signals", "indicators", "returns_analysis", "returns_curve"}
        },
    }
    research_lineage = _optional_research_lineage(manifest.get("research_lineage"))
    if research_lineage:
        context["research_lineage"] = research_lineage
    return context


def _transaction_from_fill(fill: dict[str, Any], source: str) -> dict[str, str]:
    return {
        "transaction_id": str(fill.get("fill_id") or f"paper-{uuid4().hex[:12]}"),
        "date": str(fill.get("filled_at") or _utc_now()),
        "symbol": _symbol(fill.get("symbol")),
        "side": str(fill.get("side") or "BUY").upper(),
        "quantity": _amount(_positive_decimal(fill.get("quantity"), "Paper fill quantity")),
        "price": _money(_positive_decimal(fill.get("price"), "Paper fill price")),
        "source": source,
    }


def _transaction_from_backtest_trade(trade: dict[str, str]) -> dict[str, str]:
    return {
        "transaction_id": f"backtest-{uuid4().hex[:12]}",
        "date": str(trade.get("filled_at") or _utc_now()),
        "symbol": _symbol(trade.get("symbol")),
        "side": str(trade.get("side") or "BUY").upper(),
        "quantity": _amount(_positive_decimal(trade.get("quantity"), "Backtest trade quantity")),
        "price": _money(_positive_decimal(trade.get("price"), "Backtest trade price")),
        "source": "backtest",
    }


def _resolve_backtest_run_dir(artifact_root: Path, artifact_dir: str | None) -> Path:
    root = artifact_root.resolve()
    if artifact_dir:
        run_dir = (artifact_root / artifact_dir).resolve()
    else:
        backtest_root = (artifact_root / "artifacts" / "backtests").resolve()
        # Only complete runs qualify as "latest": a run mid-write may have its
        # manifest before summary/trades land, and linking it would fail.
        candidates = [
            path.parent
            for path in backtest_root.glob("*/manifest.json")
            if (path.parent / "summary.json").is_file() and (path.parent / "trades.csv").is_file()
        ]
        if not candidates:
            raise PortfolioError("No complete backtest artifacts to link")
        run_dir = max(candidates, key=lambda path: path.stat().st_mtime).resolve()
    if not run_dir.is_relative_to(root):
        raise PortfolioError("Backtest artifact must stay inside repository")
    if run_dir.parent.name != "backtests" or run_dir.parent.parent.name != "artifacts":
        raise PortfolioError("Backtest artifact must be under artifacts/backtests")
    return run_dir


def _read_artifact_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PortfolioError(
            f"Cannot read backtest artifact {path.name} in {path.parent.name}; "
            "pass artifact_dir to choose a specific run"
        ) from exc
    if not isinstance(payload, dict):
        raise PortfolioError(f"Backtest artifact {path.name} must be an object")
    return payload


def _read_optional_artifact_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return _read_artifact_json(path)


def _read_backtest_trades(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as exc:
        raise PortfolioError("Cannot read backtest trades") from exc
    if len(rows) > MAX_TRANSACTIONS:
        raise PortfolioError(f"Backtest trades exceed limit of {MAX_TRANSACTIONS}")
    return rows


def _csv_row_count(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return sum(1 for _row in csv.DictReader(handle))
    except OSError as exc:
        raise PortfolioError(f"Cannot read backtest artifact {path.name}") from exc


def _portfolio_report_lineage(
    report_id: str,
    portfolio: dict[str, Any],
    pricing: dict[str, Any],
    created_at: str,
) -> dict[str, Any]:
    backtest_context = (
        portfolio.get("backtest_context")
        if isinstance(portfolio.get("backtest_context"), dict)
        else {}
    )
    research_lineage = (
        backtest_context.get("research_lineage")
        if isinstance(backtest_context.get("research_lineage"), dict)
        else {}
    )
    linked_artifacts = [
        path
        for path in portfolio.get("linked_artifacts", [])
        if _safe_linked_artifact_for_health(path)
    ]
    summary = {
        "contract": "portfolio_report_lineage_v1",
        "portfolio_source": str(portfolio.get("source") or ""),
        "backtest_run_id": str(backtest_context.get("run_id") or ""),
        "markets_source_row_id": str(research_lineage.get("markets_source_row_id") or ""),
        "provider_id": str(research_lineage.get("provider_id") or ""),
        "quote_semantics": str(research_lineage.get("quote_semantics") or ""),
        "linked_artifact_count": str(len(linked_artifacts)),
        "live_action_enabled": "false",
    }
    return {
        "contract": "portfolio_report_lineage_v1",
        "report_id": report_id,
        "portfolio_id": str(portfolio.get("portfolio_id") or ""),
        "portfolio_source": str(portfolio.get("source") or ""),
        "created_at": created_at,
        "summary": summary,
        "pricing_source": pricing.get("status", {}),
        "backtest_context": backtest_context,
        "research_lineage": research_lineage,
        "linked_artifacts": linked_artifacts,
        "safety": {
            "local_artifact_only": True,
            "linked_artifacts_read_only": True,
            "live_action_enabled": False,
            "optimizer_execution": False,
            "real_orders": False,
            "real_balance": False,
        },
    }


def _portfolio_report_artifact_health(
    artifact_root: Path,
    report_id: str,
    linked_artifacts: Any,
    created_at: str,
) -> dict[str, Any]:
    paths = linked_artifacts if isinstance(linked_artifacts, list) else []
    rows = []
    recovery_queue = []
    available_count = 0
    missing_count = 0
    unsafe_count = 0
    root = artifact_root.resolve()
    for raw_path in paths[:20]:
        safe_path = _safe_linked_artifact_for_health(raw_path)
        if not safe_path:
            unsafe_count += 1
            recovery_queue.append(
                {
                    "path": "unsafe_linked_artifact",
                    "status": "unsafe_ignored",
                    "recovery_hint": "Relink from a repo-local artifacts/ path.",
                    "destructive_action_required": False,
                }
            )
            rows.append(
                {
                    "path": "unsafe_linked_artifact",
                    "status": "unsafe_ignored",
                    "exists": False,
                    "size_bytes": "0",
                    "sha256": "",
                    "recovery_hint": "Relink from a repo-local artifacts/ path.",
                }
            )
            continue
        candidate = (artifact_root / safe_path).resolve()
        exists = candidate.is_relative_to(root) and candidate.is_file()
        if exists:
            available_count += 1
            rows.append(
                {
                    "path": safe_path,
                    "status": "available",
                    "exists": True,
                    "size_bytes": str(candidate.stat().st_size),
                    "sha256": _sha256_file(candidate),
                    "recovery_hint": "available",
                }
            )
        else:
            missing_count += 1
            recovery_queue.append(
                {
                    "path": safe_path,
                    "status": "missing",
                    "recovery_hint": "Regenerate the upstream local artifact or relink the portfolio.",
                    "destructive_action_required": False,
                }
            )
            rows.append(
                {
                    "path": safe_path,
                    "status": "missing",
                    "exists": False,
                    "size_bytes": "0",
                    "sha256": "",
                    "recovery_hint": "Regenerate the upstream local artifact or relink the portfolio.",
                }
            )
    if not rows:
        status = "no_linked_artifacts"
    elif missing_count or unsafe_count:
        status = "recovery_queue"
    else:
        status = "complete"
    return {
        "contract": "portfolio_report_artifact_health_v1",
        "report_id": report_id,
        "created_at": created_at,
        "status": status,
        "summary": {
            "linked_artifact_count": str(len(rows)),
            "available_artifact_count": str(available_count),
            "missing_artifact_count": str(missing_count),
            "unsafe_artifact_count": str(unsafe_count),
            "recovery_queue_count": str(len(recovery_queue)),
        },
        "rows": rows,
        "recovery_queue": recovery_queue,
        "safety": {
            "read_only": True,
            "destructive_actions_enabled": False,
            "live_action_enabled": False,
            "secret_values_returned": False,
        },
    }


def _safe_linked_artifact_for_health(raw_path: Any) -> str:
    path = _optional_text(raw_path, "", max_length=240).replace("\\", "/")
    lowered = path.lower()
    if not path.startswith("artifacts/"):
        return ""
    if ".." in Path(path).parts:
        return ""
    if any(term in lowered for term in FORBIDDEN_ARTIFACT_PATH_TERMS):
        return ""
    return path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_text_report(
    path: Path,
    portfolio: dict[str, Any],
    summary: dict[str, str | int],
    risk: list[dict[str, str]],
    exposure_map: list[dict[str, str]],
    pricing: dict[str, Any],
    manifest: dict[str, Any],
) -> None:
    lines = [
        f"# Portfolio Report {manifest['report_id']}",
        "",
        f"- Portfolio: {portfolio['name']}",
        f"- Source: {portfolio['source']}",
        f"- Value: {summary['portfolio_value']} {portfolio['currency']}",
        f"- Unrealized P&L: {summary['unrealized_pnl']} ({summary['unrealized_pnl_pct']}%)",
        f"- Provider priced: {pricing['status']['provider_price_count']}",
        "- Safety: local artifact only, no live orders, no real balances",
        f"- Lineage: {manifest['lineage_summary'].get('contract', 'portfolio_report_lineage_v1')}",
        f"- Linked artifact health: {manifest['artifact_health'].get('status', 'unknown')}",
        "",
        "## Risk",
    ]
    lines.extend(f"- {row['metric']}: {row['value']} ({row['state']})" for row in risk)
    lines.append("")
    lines.append("## Exposure")
    lines.extend(
        f"- {row['symbol']}: {row['weight_pct']}% / {row['sector']} / {row['concentration_state']}"
        for row in exposure_map[:10]
    )
    lines.append("")
    lines.append("## Artifacts")
    lines.extend(f"- {name}: {artifact}" for name, artifact in manifest["artifact_files"].items())
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _hash_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _linked_artifacts(raw_artifacts: Any) -> list[str]:
    if raw_artifacts in (None, ""):
        return []
    if not isinstance(raw_artifacts, list):
        raise PortfolioError("Linked artifacts must be a list")
    if len(raw_artifacts) > 20:
        raise PortfolioError("Linked artifacts exceed limit of 20")
    return [_optional_text(path, "", max_length=240) for path in raw_artifacts if str(path).strip()]


def _summary(portfolio: dict[str, Any] | None) -> dict[str, str | int]:
    if portfolio is None:
        return {
            "portfolio_value": "0.00",
            "cost_basis": "0.00",
            "unrealized_pnl": "0.00",
            "unrealized_pnl_pct": "0.00",
            "today_pnl": "0.00",
            "today_pnl_pct": "0.00",
            "sharpe": "0.00",
            "concentration_pct": "0.00",
            "beta": "0.00",
            "volatility_pct": "0.00",
            "max_drawdown_pct": "0.00",
            "position_count": 0,
            "transaction_count": 0,
            "sector_count": 0,
        }
    positions = portfolio.get("positions", [])
    value = _portfolio_value(positions)
    cost_basis = sum(
        (Decimal(position["quantity"]) * Decimal(position["avg_cost"]) for position in positions),
        Decimal("0"),
    )
    unrealized = value - cost_basis
    today = sum(
        (
            Decimal(position["quantity"])
            * Decimal(position["last_price"])
            * Decimal(position.get("day_change_pct", "0"))
            / Decimal("100")
            for position in positions
        ),
        Decimal("0"),
    )
    concentration = max(
        (Decimal(position["quantity"]) * Decimal(position["last_price"]) for position in positions),
        default=Decimal("0"),
    )
    beta = _weighted_average(positions, "beta", value)
    volatility = _weighted_average(positions, "volatility_pct", value)
    unrealized_pct = _pct(unrealized, cost_basis)
    sharpe = (unrealized_pct / max(volatility, Decimal("1"))).quantize(
        PCT_QUANT, rounding=ROUND_HALF_UP
    )
    max_drawdown = (volatility * Decimal("0.42")).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)
    sectors = {position.get("sector", "Unclassified") for position in positions}
    return {
        "portfolio_value": _money(value),
        "cost_basis": _money(cost_basis),
        "unrealized_pnl": _money(unrealized),
        "unrealized_pnl_pct": _pct_text(unrealized, cost_basis),
        "today_pnl": _money(today),
        "today_pnl_pct": _pct_text(today, value),
        "sharpe": _ratio_text(sharpe),
        "concentration_pct": _pct_text(concentration, value),
        "beta": _ratio_text(beta),
        "volatility_pct": _ratio_text(volatility),
        "max_drawdown_pct": _ratio_text(max_drawdown),
        "position_count": len(positions),
        "transaction_count": len(portfolio.get("transactions", [])),
        "sector_count": len(sectors),
    }


def _position_views(portfolio: dict[str, Any] | None) -> list[dict[str, str]]:
    if portfolio is None:
        return []
    value = _portfolio_value(portfolio.get("positions", []))
    rows = []
    for position in portfolio.get("positions", []):
        quantity = Decimal(position["quantity"])
        last_price = Decimal(position["last_price"])
        avg_cost = Decimal(position["avg_cost"])
        market_value = quantity * last_price
        cost_basis = quantity * avg_cost
        pnl = market_value - cost_basis
        rows.append(
            {
                **position,
                "market_value": _money(market_value),
                "cost_basis": _money(cost_basis),
                "pnl": _money(pnl),
                "pnl_pct": _pct_text(pnl, cost_basis),
                "weight_pct": _pct_text(market_value, value),
                "trend": _trend(position["symbol"]),
            }
        )
    return rows


def _transactions(portfolio: dict[str, Any] | None) -> list[dict[str, str]]:
    if portfolio is None:
        return []
    return list(reversed(portfolio.get("transactions", [])))


def _allocation(portfolio: dict[str, Any] | None) -> list[dict[str, str]]:
    if portfolio is None:
        return []
    totals: dict[str, Decimal] = {}
    for position in portfolio.get("positions", []):
        sector = str(position.get("sector") or "Unclassified")
        totals[sector] = totals.get(sector, Decimal("0")) + Decimal(position["quantity"]) * Decimal(
            position["last_price"]
        )
    value = sum(totals.values(), Decimal("0"))
    return [
        {"sector": sector, "value": _money(total), "weight_pct": _pct_text(total, value)}
        for sector, total in sorted(totals.items(), key=lambda item: item[1], reverse=True)
    ]


def _exposure_map(portfolio: dict[str, Any] | None) -> list[dict[str, str]]:
    if portfolio is None:
        return []
    positions = portfolio.get("positions", [])
    value = _portfolio_value(positions)
    rows = []
    for position in positions:
        quantity = Decimal(position["quantity"])
        last_price = Decimal(position["last_price"])
        avg_cost = Decimal(position["avg_cost"])
        market_value = quantity * last_price
        cost_basis = quantity * avg_cost
        pnl = market_value - cost_basis
        weight = (market_value / value) if value else Decimal("0")
        weight_pct = (weight * Decimal("100")).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)
        beta_contribution = (Decimal(position.get("beta", "0")) * weight).quantize(
            PCT_QUANT, rounding=ROUND_HALF_UP
        )
        volatility_contribution = (
            Decimal(position.get("volatility_pct", "0")) * weight
        ).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)
        rows.append(
            {
                "symbol": str(position["symbol"]),
                "sector": str(position.get("sector") or "Unclassified"),
                "market_value": _money(market_value),
                "weight_pct": _ratio_text(weight_pct),
                "pnl": _money(pnl),
                "pnl_pct": _pct_text(pnl, cost_basis),
                "beta_contribution": _ratio_text(beta_contribution),
                "volatility_contribution_pct": _ratio_text(volatility_contribution),
                "concentration_state": _risk_state(weight_pct, Decimal("15"), Decimal("30")),
                "price_source": str(position.get("price_source") or "local_snapshot"),
                "pricing_state": str(position.get("pricing_state") or "local_snapshot"),
            }
        )
    return sorted(rows, key=lambda row: Decimal(row["weight_pct"]), reverse=True)


def _performance(portfolio: dict[str, Any] | None) -> list[dict[str, str]]:
    value = _portfolio_value(portfolio.get("positions", [])) if portfolio else Decimal("0")
    if value == 0:
        return []
    points = [
        ("2026-01", Decimal("0.86")),
        ("2026-02", Decimal("0.91")),
        ("2026-03", Decimal("0.96")),
        ("2026-04", Decimal("0.98")),
        ("2026-05", Decimal("1.00")),
    ]
    rows = []
    previous_value: Decimal | None = None
    for period, multiplier in points:
        point_value = value * multiplier
        if previous_value is None or previous_value == 0:
            period_return = Decimal("0")
        else:
            period_return = (point_value / previous_value) - Decimal("1")
        rows.append(
            {
                "period": period,
                "value": _money(point_value),
                "period_return_pct": _pct_text(period_return, Decimal("1")),
            }
        )
        previous_value = point_value
    return rows


def _correlation(portfolio: dict[str, Any] | None) -> dict[str, Any]:
    positions = portfolio.get("positions", [])[:6] if portfolio else []
    symbols = [position["symbol"] for position in positions]
    sectors = {position["symbol"]: position.get("sector", "") for position in positions}
    matrix = []
    for row_symbol in symbols:
        row = []
        for col_symbol in symbols:
            if row_symbol == col_symbol:
                row.append("1.00")
            elif sectors.get(row_symbol) == sectors.get(col_symbol):
                row.append("0.42")
            else:
                row.append("0.18")
        matrix.append({"symbol": row_symbol, "values": row})
    return {"symbols": symbols, "matrix": matrix}


def _risk_rows(
    portfolio: dict[str, Any] | None,
    summary: dict[str, str | int],
    allocation: list[dict[str, str]],
) -> list[dict[str, str]]:
    if portfolio is None:
        return []
    max_sector = allocation[0] if allocation else {"sector": "N/A", "weight_pct": "0.00"}
    return [
        {
            "metric": "concentration_pct",
            "value": f"{summary['concentration_pct']}%",
            "state": _risk_state(
                Decimal(str(summary["concentration_pct"])), Decimal("35"), Decimal("60")
            ),
            "source": "positions",
        },
        {
            "metric": "volatility_pct",
            "value": f"{summary['volatility_pct']}%",
            "state": _risk_state(
                Decimal(str(summary["volatility_pct"])), Decimal("25"), Decimal("40")
            ),
            "source": "position_volatility",
        },
        {
            "metric": "max_drawdown_pct",
            "value": f"{summary['max_drawdown_pct']}%",
            "state": _risk_state(
                Decimal(str(summary["max_drawdown_pct"])), Decimal("12"), Decimal("25")
            ),
            "source": "local_proxy",
        },
        {
            "metric": "beta",
            "value": str(summary["beta"]),
            "state": _risk_state(Decimal(str(summary["beta"])), Decimal("1.20"), Decimal("1.60")),
            "source": "position_weighted",
        },
        {
            "metric": "largest_sector",
            "value": f"{max_sector['sector']} {max_sector['weight_pct']}%",
            "state": _risk_state(Decimal(max_sector["weight_pct"]), Decimal("45"), Decimal("70")),
            "source": "allocation",
        },
        {
            "metric": "provider_pricing",
            "value": str(
                portfolio.get("pricing", {}).get("status", {}).get("provider_price_count", "0")
            ),
            "state": "context",
            "source": "provider_cache",
        },
    ]


def _risk_state(value: Decimal, watch: Decimal, high: Decimal) -> str:
    if value >= high:
        return "high"
    if value >= watch:
        return "watch"
    return "normal"


def _report_state(portfolio: dict[str, Any] | None) -> dict[str, Any]:
    if portfolio is None:
        return {"status": "not_started", "artifact_files": {}, "safety": "local_only"}
    last_report = (
        portfolio.get("last_report") if isinstance(portfolio.get("last_report"), dict) else {}
    )
    if not last_report:
        return {"status": "not_generated", "artifact_files": {}, "safety": "local_only"}
    return {
        "status": "generated",
        "report_id": str(last_report.get("report_id") or ""),
        "created_at": str(last_report.get("created_at") or ""),
        "artifact_files": last_report.get("artifact_files", {}),
        "exposure_row_count": str(last_report.get("exposure_row_count") or ""),
        "lineage_summary": last_report.get("lineage_summary", {}),
        "artifact_health": last_report.get("artifact_health", {}),
        "safety": "local_only_no_live_order",
    }


def _empty_portfolio_report_index() -> dict[str, Any]:
    return {
        "mode": "local_portfolio_report_index",
        "contract": "portfolio_report_index_v1",
        "generated_at": "not loaded",
        "root": PORTFOLIO_REPORT_ROOT,
        "summary": {
            "report_count": 0,
            "complete_report_count": 0,
            "incomplete_report_count": 0,
            "missing_artifact_count": 0,
            "active_report_id": "",
            "latest_report_id": "",
            "recovery_queue_count": 0,
        },
        "reports": [],
        "recovery_queue": [],
        "recommended_actions": [],
        "safety": {
            "metadata_only": True,
            "file_content_read": False,
            "writes_local_artifacts": False,
            "destructive_actions_enabled": False,
            "real_orders": False,
            "real_balance": False,
            "broker_routing": False,
            "live_trading": False,
            "secret_values_returned": False,
        },
    }


def _portfolio_report_health_from_index(index: dict[str, Any]) -> dict[str, Any]:
    reports = [
        _portfolio_report_health_row(row)
        for row in index.get("reports", [])
        if isinstance(row, dict)
    ]
    recovery_queue = [
        item for item in index.get("recovery_queue", []) if isinstance(item, dict)
    ]
    summary = index.get("summary") if isinstance(index.get("summary"), dict) else {}
    complete_count = sum(1 for row in reports if row["health_state"] == "complete")
    partial_count = sum(1 for row in reports if row["health_state"] != "complete")
    missing_artifact_count = sum(int(row["missing_count"]) for row in reports)
    supervision_ready_count = sum(1 for row in reports if row["supervision_ready"])
    latest = reports[0] if reports else {}
    return {
        "mode": "metadata_only_portfolio_report_health",
        "contract": "portfolio_report_health_v1",
        "generated_at": str(index.get("generated_at") or _utc_now()),
        "root": PORTFOLIO_REPORT_ROOT,
        "summary": {
            "report_count": len(reports),
            "complete_count": complete_count,
            "partial_count": partial_count,
            "missing_artifact_count": missing_artifact_count,
            "supervision_ready_count": supervision_ready_count,
            "expected_artifact_count": len(PORTFOLIO_REPORT_FILES),
            "active_report_id": str(summary.get("active_report_id") or ""),
            "latest_report_id": str(latest.get("report_id") or ""),
            "recovery_queue_count": len(recovery_queue),
            "destructive_action_count": 0,
        },
        "reports": reports,
        "recovery_queue": recovery_queue,
        "recommended_actions": [
            {
                "action_id": "portfolio_report_index",
                "endpoint": "/api/portfolio/reports",
                "method": "GET",
                "ready": len(reports) > 0,
                "reason": (
                    "Inspect indexed local Portfolio report metadata before selection."
                    if reports
                    else "Generate a local Portfolio report before using report health rows."
                ),
            },
            {
                "action_id": "portfolio_report",
                "endpoint": "/api/portfolio/report",
                "method": "POST",
                "ready": True,
                "reason": "Regenerate the active local Portfolio report; existing report directories are not repaired.",
            },
        ],
        "safety": {
            "local_only": True,
            "read_only": True,
            "metadata_only": True,
            "file_content_read": False,
            "artifact_content_indexing": False,
            "writes_local_artifacts": False,
            "automatic_repair_enabled": False,
            "destructive_actions_enabled": False,
            "real_orders": False,
            "real_balance": False,
            "broker_routing": False,
            "margin": False,
            "leverage": False,
            "short": False,
            "derivatives": False,
            "live_trading": False,
            "secret_values_returned": False,
        },
    }


def _portfolio_report_health_row(row: dict[str, Any]) -> dict[str, Any]:
    files = [item for item in row.get("files", []) if isinstance(item, dict)]
    missing_artifacts = [
        str(file_row.get("name") or "")
        for file_row in files
        if not bool(file_row.get("exists")) and str(file_row.get("name") or "")
    ]
    present_count = sum(1 for file_row in files if bool(file_row.get("exists")))
    health_state = "partial_missing_artifacts" if missing_artifacts else "complete"
    artifacts = row.get("artifacts") if isinstance(row.get("artifacts"), dict) else {}
    return {
        "report_id": str(row.get("report_id") or ""),
        "artifact_dir": str(row.get("artifact_dir") or ""),
        "active_portfolio_report": bool(row.get("active_portfolio_report")),
        "portfolio_id": str(row.get("portfolio_id") or ""),
        "created_at": str(row.get("created_at") or ""),
        "latest_updated_at": str(row.get("latest_updated_at") or ""),
        "health_state": health_state,
        "expected_count": len(PORTFOLIO_REPORT_FILES),
        "present_count": present_count,
        "missing_count": len(missing_artifacts),
        "missing_artifacts": missing_artifacts,
        "total_bytes": int(row.get("total_bytes") or 0),
        "manifest_path": str(artifacts.get("manifest") or ""),
        "lineage_path": str(artifacts.get("lineage") or ""),
        "artifact_health_path": str(artifacts.get("artifact_health") or ""),
        "supervision_ready": health_state == "complete",
        "recovery_hint": (
            "ready_for_agent_selection"
            if health_state == "complete"
            else "Regenerate the active local Portfolio report; do not repair files in place."
        ),
        "file_content_read": False,
        "destructive_actions_enabled": False,
    }


def _active_report_metadata(state: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    normalized = normalize_portfolio_state(state, strict=False)
    active = _active_portfolio(normalized)
    if not active or not isinstance(active.get("last_report"), dict):
        return {}
    report = _last_report(active.get("last_report"))
    return report if report.get("report_id") else {}


def _portfolio_report_index_row(
    root: Path,
    report_dir: Path,
    active_report: dict[str, Any],
) -> dict[str, Any]:
    resolved = report_dir.resolve()
    if not resolved.is_relative_to(root):
        raise PortfolioError("Refusing to inspect Portfolio report outside repository")
    report_id = report_dir.name
    artifacts = {
        PORTFOLIO_REPORT_ARTIFACT_KEYS[name]: f"{PORTFOLIO_REPORT_ROOT}/{report_id}/{name}"
        for name in PORTFOLIO_REPORT_FILES
    }
    file_rows = []
    total_bytes = 0
    latest_timestamp = 0.0
    for filename in PORTFOLIO_REPORT_FILES:
        path = report_dir / filename
        exists = path.is_file()
        stat = path.stat() if exists else None
        size = stat.st_size if stat else 0
        updated_at = stat.st_mtime if stat else 0.0
        total_bytes += size
        latest_timestamp = max(latest_timestamp, updated_at)
        file_rows.append(
            {
                "name": filename,
                "path": f"{PORTFOLIO_REPORT_ROOT}/{report_id}/{filename}",
                "exists": exists,
                "bytes": size,
            }
        )
    missing = [row for row in file_rows if not row["exists"]]
    is_active = str(active_report.get("report_id") or "") == report_id
    return {
        "report_id": report_id,
        "artifact_dir": f"{PORTFOLIO_REPORT_ROOT}/{report_id}",
        "artifacts": artifacts,
        "active_portfolio_report": is_active,
        "portfolio_id": str(active_report.get("portfolio_id") or "") if is_active else "",
        "source": str(active_report.get("source") or "") if is_active else "",
        "created_at": str(active_report.get("created_at") or "")
        if is_active
        else _timestamp_text(latest_timestamp),
        "lineage_contract": str(active_report.get("lineage_summary", {}).get("contract") or "")
        if is_active
        else "",
        "artifact_health_status": str(active_report.get("artifact_health", {}).get("status") or "")
        if is_active
        else "",
        "artifact_count": len(file_rows) - len(missing),
        "missing_artifact_count": len(missing),
        "total_bytes": total_bytes,
        "latest_updated_at": _timestamp_text(latest_timestamp),
        "complete": not missing,
        "files": file_rows,
    }


def _portfolio_report_index_recovery_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return [
            {
                "queue_id": "portfolio_report_index:none",
                "report_id": "",
                "artifact_path": PORTFOLIO_REPORT_ROOT,
                "recommended_action": "portfolio_report",
                "endpoint": "/api/portfolio/report",
                "reason": "No local Portfolio report artifacts found.",
                "destructive_action_required": False,
                "writes_local_artifacts": True,
            }
        ]
    queue = []
    for row in rows:
        for file_row in row["files"]:
            if bool(file_row.get("exists")):
                continue
            queue.append(
                {
                    "queue_id": f"portfolio_report_index:{row['report_id']}:{file_row['name']}",
                    "report_id": row["report_id"],
                    "artifact_path": file_row["path"],
                    "recommended_action": "portfolio_report",
                    "endpoint": "/api/portfolio/report",
                    "reason": f"Missing Portfolio report artifact {file_row['name']}.",
                    "destructive_action_required": False,
                    "writes_local_artifacts": True,
                }
            )
    return queue


def _bounded_report_index_limit(raw_value: Any) -> int:
    try:
        value = int(str(raw_value))
    except (TypeError, ValueError):
        return DEFAULT_PORTFOLIO_REPORT_INDEX_LIMIT
    if value < 1:
        return 1
    if value > DEFAULT_PORTFOLIO_REPORT_INDEX_LIMIT:
        return DEFAULT_PORTFOLIO_REPORT_INDEX_LIMIT
    return value


def _timestamp_text(timestamp: float) -> str:
    if timestamp <= 0:
        return ""
    return (
        datetime.fromtimestamp(timestamp, tz=UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _portfolio_value(positions: list[dict[str, Any]]) -> Decimal:
    return sum(
        (Decimal(position["quantity"]) * Decimal(position["last_price"]) for position in positions),
        Decimal("0"),
    )


def _weighted_average(positions: list[dict[str, str]], key: str, total_value: Decimal) -> Decimal:
    if total_value == 0:
        return Decimal("0")
    weighted = sum(
        (
            Decimal(position["quantity"])
            * Decimal(position["last_price"])
            * Decimal(position.get(key, "0"))
            / total_value
            for position in positions
        ),
        Decimal("0"),
    )
    return weighted.quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def _demo_position(
    symbol: str,
    name: str,
    sector: str,
    quantity: str,
    avg_cost: str,
    last_price: str,
    day_change_pct: str,
    beta: str,
    volatility_pct: str,
) -> dict[str, str]:
    return {
        "symbol": symbol,
        "name": name,
        "asset_class": "Equity",
        "sector": sector,
        "quantity": quantity,
        "avg_cost": avg_cost,
        "last_price": last_price,
        "currency": "USD",
        "day_change_pct": day_change_pct,
        "beta": beta,
        "volatility_pct": volatility_pct,
    }


def _buy_transaction(position: dict[str, str], date: str) -> dict[str, str]:
    quantity = Decimal(position["quantity"])
    price = Decimal(position["avg_cost"])
    return {
        "transaction_id": f"demo-buy-{position['symbol'].lower()}",
        "date": date,
        "symbol": position["symbol"],
        "side": "BUY",
        "quantity": _amount(quantity),
        "price": _money(price),
        "amount": _money(quantity * price),
        "source": "demo",
    }


def _symbol(raw: Any) -> str:
    symbol = "".join(ch for ch in str(raw or "").upper() if ch.isalnum())
    if not symbol or len(symbol) > 16:
        raise PortfolioError("Symbol is required")
    return symbol


def _required_text(raw: Any, label: str, max_length: int) -> str:
    value = str(raw or "").strip()
    if not value:
        raise PortfolioError(f"{label} is required")
    if len(value) > max_length:
        raise PortfolioError(f"{label} is too long")
    return value


def _optional_text(raw: Any, default: str, max_length: int) -> str:
    value = str(raw or default).strip()
    return value[:max_length] if value else default


def _currency(raw: Any) -> str:
    currency = "".join(ch for ch in str(raw or "USD").upper() if ch.isalnum())
    if currency not in SUPPORTED_CURRENCIES:
        raise PortfolioError("Unsupported portfolio currency")
    return currency


def _positive_decimal(raw: Any, label: str, allow_zero: bool = True) -> Decimal:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise PortfolioError(f"{label} must be numeric") from None
    if not value.is_finite():
        raise PortfolioError(f"{label} must be finite")
    if value < 0 or (not allow_zero and value == 0):
        raise PortfolioError(f"{label} must be positive")
    if value > Decimal("1000000000000"):
        raise PortfolioError(f"{label} is too large")
    return value


def _pct_value(raw: Any) -> str:
    value = _finite_decimal(raw, "Percent value")
    if abs(value) > Decimal("1000"):
        raise PortfolioError("Percent value is too large")
    return _ratio_text(value)


def _ratio_value(raw: Any) -> str:
    return _ratio_text(_positive_decimal(raw, "Ratio value"))


def _finite_decimal(raw: Any, label: str) -> Decimal:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise PortfolioError(f"{label} must be numeric") from None
    if not value.is_finite():
        raise PortfolioError(f"{label} must be finite")
    return value


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0.00")
    return ((numerator / denominator) * Decimal("100")).quantize(PCT_QUANT, rounding=ROUND_HALF_UP)


def _pct_text(numerator: Decimal, denominator: Decimal) -> str:
    return _ratio_text(_pct(numerator, denominator))


def _amount(value: Decimal) -> str:
    text = format(value.quantize(AMOUNT_QUANT, rounding=ROUND_HALF_UP), "f")
    return text.rstrip("0").rstrip(".") or "0"


def _money(value: Decimal) -> str:
    return str(value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP))


def _ratio_text(value: Decimal) -> str:
    return str(value.quantize(PCT_QUANT, rounding=ROUND_HALF_UP))


def _trend(symbol: str) -> str:
    seed = sum(ord(ch) for ch in symbol)
    return "".join("+" if (seed + index) % 3 else "-" for index in range(12))


def _utc_now() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
