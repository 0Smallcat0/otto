"""Local algorithm strategy builder and dry-run scanner."""

from __future__ import annotations

import copy
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import uuid4

from otto.local_terminal.backtest import (
    BacktestError,
    backtest_strategy_catalog,
    normalize_strategy_parameters,
    run_backtest,
)
from otto.local_terminal.markets import default_markets_layout, markets_payload
from otto.local_terminal.research_lineage import (
    ResearchLineageError,
    lineage_from_source_row,
    normalize_research_lineage,
    scan_artifact_hash,
    select_markets_source_row,
    with_scan_artifact_lineage,
)


SUPPORTED_ALGO_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
SUPPORTED_TIMEFRAMES = ("15m", "1h", "4h", "1d")
MAX_STRATEGIES = 120
MAX_CONDITIONS = 12
MAX_SCAN_SYMBOLS = 30
LOCAL_ALGO_ENGINE = "local_algo_v1"
ALGO_SCAN_ARTIFACT_ROOT = "artifacts/algo/scans"
ALGO_SECRET_PATTERNS = (
    re.compile(
        r"[\"']?(api[\s_-]*key|apikey|access[\s_-]*token|refresh[\s_-]*token|"
        r"secret[\s_-]*key|client[\s_-]*secret|private[\s_-]*key|password|"
        r"passphrase|pin|token|secret)[\"']?\s*[:=]\s*[\"']?[^\"'\s,}]+",
        re.IGNORECASE,
    ),
    re.compile(r"\bauthorization\s*:\s*[^,\s]+", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bprivate[\s_-]+key\b", re.IGNORECASE),
)
# backtest_ready is honest labeling: the closed-candle backtester currently
# runs 15m only, so non-15m templates scan but cannot be backtested yet.
LOCAL_STRATEGY_CATALOG = (
    {
        "strategy_id": "template-trend-sma",
        "name": "SMA Trend Follow",
        "category": "Trend",
        "timeframe": "15m",
        "description": "Long/flat moving-average crossover template for closed candles.",
        "backtest_ready": True,
    },
    {
        "strategy_id": "template-breakout-volume",
        "name": "Volume Breakout",
        "category": "Breakout",
        "timeframe": "1h",
        "description": "Dry-run signal template combining range breakout and volume filter.",
        "backtest_ready": False,
    },
    {
        "strategy_id": "template-mean-rsi",
        "name": "RSI Mean Reversion",
        "category": "Mean Reversion",
        "timeframe": "4h",
        "description": "Research-only oversold/exit band template.",
        "backtest_ready": False,
    },
    {
        "strategy_id": "template-risk-cash",
        "name": "Cash Risk Guard",
        "category": "Risk Management",
        "timeframe": "1d",
        "description": "Template emphasizing stop, take-profit, and no-live-routing controls.",
        "backtest_ready": False,
    },
)
BACKTEST_STRATEGIES = tuple(backtest_strategy_catalog())
BACKTEST_STRATEGY_BY_ID = {strategy["strategy_id"]: strategy for strategy in BACKTEST_STRATEGIES}


class AlgoError(ValueError):
    """Raised when an Algo request violates local strategy rules."""


def default_algo_state() -> dict[str, Any]:
    return {
        "active_strategy_id": None,
        "strategies": {},
        "last_scan": None,
        "last_backtest": None,
        "updated_at": "not started",
    }


def default_strategy_request() -> dict[str, Any]:
    return {
        "name": "Local SMA Trend",
        "description": "Closed-candle long/flat strategy for local research.",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "entry_conditions": ["fast SMA crosses above slow SMA"],
        "exit_conditions": ["fast SMA crosses below slow SMA"],
        "risk_settings": {
            "stop_loss_pct": "5",
            "take_profit_pct": "12",
            "trailing_stop_pct": "0",
        },
        "backtest": {
            "strategy": "sma_cross",
            "initial_cash": "100000.00",
            "fast_window": 3,
            "slow_window": 5,
            "fee_rate": "0.001",
            "slippage_bps": "2",
        },
    }


def normalize_algo_state(state: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    default = default_algo_state()
    invalid_strategies = (
        {str(key): str(value) for key, value in state.get("invalid_strategies", {}).items()}
        if isinstance(state.get("invalid_strategies"), dict)
        else {}
    )
    if strict and invalid_strategies:
        first_key, first_value = next(iter(invalid_strategies.items()))
        raise AlgoError(f"Algo state is invalid: {first_key}: {first_value}")

    raw_strategies = state.get("strategies")
    strategies: dict[str, dict[str, Any]] = {}
    if isinstance(raw_strategies, dict):
        if len(raw_strategies) > MAX_STRATEGIES:
            raise AlgoError(f"Strategies exceed limit of {MAX_STRATEGIES}")
        for strategy_id, raw_strategy in raw_strategies.items():
            if not isinstance(raw_strategy, dict):
                if strict:
                    raise AlgoError(f"Stored strategy {strategy_id} must be an object")
                invalid_strategies[str(strategy_id)] = "Stored strategy must be an object"
                continue
            try:
                strategy = normalize_strategy(raw_strategy, fallback_id=str(strategy_id))
            except AlgoError as exc:
                if strict:
                    raise AlgoError(f"Stored strategy {strategy_id} is invalid: {exc}") from exc
                invalid_strategies[str(strategy_id)] = str(exc)
                continue
            strategies[strategy["strategy_id"]] = strategy
    elif raw_strategies not in (None, {}):
        if strict:
            raise AlgoError("Stored strategies must be an object")
        invalid_strategies["strategies"] = "Stored strategies must be an object"

    active_id = str(state.get("active_strategy_id") or "")
    if active_id not in strategies:
        active_id = _latest_strategy_id(strategies)

    try:
        last_scan = _normalize_last_scan(state.get("last_scan"))
    except AlgoError as exc:
        if strict:
            raise AlgoError(f"Stored last scan is invalid: {exc}") from exc
        invalid_strategies["last_scan"] = str(exc)
        last_scan = None
    try:
        last_backtest = _normalize_last_backtest(state.get("last_backtest"))
    except AlgoError as exc:
        if strict:
            raise AlgoError(f"Stored last backtest is invalid: {exc}") from exc
        invalid_strategies["last_backtest"] = str(exc)
        last_backtest = None
    return {
        **default,
        "active_strategy_id": active_id or None,
        "strategies": strategies,
        "invalid_strategies": invalid_strategies,
        "last_scan": last_scan,
        "last_backtest": last_backtest,
        "updated_at": str(state.get("updated_at") or default["updated_at"]),
    }


def algo_payload(state: dict[str, Any]) -> dict[str, Any]:
    algo_state = normalize_algo_state(state, strict=False)
    active_id = algo_state["active_strategy_id"]
    active_strategy = copy.deepcopy(algo_state["strategies"].get(active_id)) if active_id else None
    return {
        "active_strategy_id": active_id,
        "first_use": active_strategy is None,
        "tabs": ["Builder", "My Strategies", "Scanner", "Dashboard"],
        "catalog": list(LOCAL_STRATEGY_CATALOG),
        "backtest_strategies": list(BACKTEST_STRATEGIES),
        "strategies": _strategy_list(algo_state),
        "active_strategy": active_strategy,
        "strategy_draft": active_strategy or default_strategy_request(),
        "last_scan": algo_state["last_scan"],
        "last_backtest": algo_state["last_backtest"],
        "invalid_strategies": algo_state["invalid_strategies"],
        "engine": {
            "engine_id": LOCAL_ALGO_ENGINE,
            "state": "idle",
            "live_count": 0,
            "strategy_count": len(algo_state["strategies"]),
            "catalog_count": len(LOCAL_STRATEGY_CATALOG),
        },
        "safety": algo_safety_payload(),
    }


def algo_safety_payload() -> dict[str, bool | str]:
    return {
        "live_deployment": False,
        "broker_routing": False,
        "real_orders": False,
        "private_api_required": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives": False,
        "output": "signals_only",
    }


def algo_scan_readiness_payload(
    state: dict[str, Any],
    market_cache: dict[str, Any] | None,
    provider_context: dict[str, Any] | None = None,
    *,
    scan_artifact_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return read-only scanner readiness metadata without running a scan."""

    algo_state = normalize_algo_state(state, strict=False)
    active_id = algo_state["active_strategy_id"]
    active_strategy = copy.deepcopy(algo_state["strategies"].get(active_id)) if active_id else None
    context = provider_context or {}
    market = markets_payload(
        default_markets_layout(),
        market_cache or {},
        research_data=context.get("research_data"),
        rates_data=context.get("rates_data"),
        fx_data=context.get("fx_data"),
        commodity_data=context.get("commodity_data"),
        fund_data=context.get("fund_data"),
        equity_quote_data=context.get("equity_quote_data"),
        etf_quote_data=context.get("etf_quote_data"),
    )
    market_status = market["status"]
    no_provider_data = market_status["source"] == "offline_fixture" or market_status["state"] in {
        "offline",
        "unavailable",
    }
    rows = market.get("rows") if isinstance(market.get("rows"), list) else []
    row_by_symbol = {
        str(row.get("symbol") or ""): row for row in rows if isinstance(row, dict)
    }
    symbols = list(SUPPORTED_ALGO_SYMBOLS)
    source_rows = [
        row
        for row in market.get("source_coverage_matrix", [])
        if isinstance(row, dict)
    ]
    artifact_health = scan_artifact_health or _empty_scan_artifact_health()
    last_scan = algo_state["last_scan"] if isinstance(algo_state.get("last_scan"), dict) else None
    invalid_state = algo_state.get("invalid_strategies", {})
    if invalid_state.get("last_scan"):
        readiness_state = "invalid_scan_state"
    elif active_strategy is None:
        readiness_state = "no_active_strategy"
    elif no_provider_data:
        readiness_state = "provider_cache_missing"
    else:
        readiness_state = "ready"

    return {
        "contract": "algo_scan_readiness_v1",
        "mode": "metadata_only_scan_preflight",
        "state": readiness_state,
        "active_strategy_ready": active_strategy is not None,
        "active_strategy": _readiness_strategy(active_strategy),
        "strategy_count": len(algo_state["strategies"]),
        "default_scan_symbols": symbols,
        "symbol_readiness": [
            _symbol_readiness(symbol, row_by_symbol.get(symbol), market_status, no_provider_data)
            for symbol in symbols
        ],
        "provider_cache": {
            "state": str(market_status.get("state") or "unavailable"),
            "source": str(market_status.get("source") or "public_provider_unavailable"),
            "provider_id": str(market_status.get("provider_id") or ""),
            "cache_path": str(market_status.get("cache_path") or ""),
            "retrieved_at": str(market_status.get("last_update") or ""),
            "data_mode": "no_provider_data" if no_provider_data else "provider_cache",
            "source_row_count": len(source_rows),
            "market_row_count": len(rows),
        },
        "default_source_row": _readiness_source_row(source_rows[0] if source_rows else None),
        "latest_scan": _readiness_latest_scan(last_scan),
        "scan_artifact_health": {
            "status": str(artifact_health.get("status") or "no_scan"),
            "scan_id": str(artifact_health.get("scan_id") or ""),
            "present_count": int(artifact_health.get("present_count") or 0),
            "missing_count": int(artifact_health.get("missing_count") or 0),
            "repair_available": bool(artifact_health.get("repair_available")),
            "repair_action": str(
                artifact_health.get("repair_action") or "algo_scan_artifacts_repair"
            ),
            "destructive_actions_enabled": bool(
                artifact_health.get("destructive_actions_enabled")
            ),
        },
        "backtest_handoff": _readiness_backtest_handoff(last_scan, artifact_health),
        "recommended_actions": [
            _readiness_action(
                "algo_save_strategy",
                ready=active_strategy is None,
                safe=True,
                reason="Create a local strategy before state-only scanner supervision can identify the active strategy.",
            ),
            _readiness_action(
                "markets_refresh_public",
                ready=active_strategy is not None and no_provider_data,
                safe=True,
                reason="Refresh public market cache before expecting meaningful scan signals.",
            ),
            _readiness_action(
                "algo_scan",
                ready=active_strategy is not None and not no_provider_data,
                safe=True,
                reason=(
                    "Scanner is signal-only and non-actionable; current provider cache can emit research signals."
                    if active_strategy is not None and not no_provider_data
                    else "Scanner can run safely, but current data would produce no-provider-data signals."
                ),
            ),
            _readiness_action(
                "algo_scan_artifacts_repair",
                ready=bool(artifact_health.get("repair_available"))
                and str(artifact_health.get("status") or "") == "repairable_missing",
                safe=True,
                reason="Rewrite only expected latest scan mirror files from local scan state.",
            ),
            _readiness_action(
                "algo_run_backtest",
                ready=bool(_scan_seed_hash(last_scan)),
                safe=True,
                reason="Run local closed-candle Backtest only from the latest scan seed hash.",
            ),
        ],
        "safety": {
            "read_only": True,
            "metadata_only": True,
            "scan_executed": False,
            "provider_refresh_performed": False,
            "writes_local_artifacts": False,
            "secret_values_returned": False,
            "live_deployment": False,
            "broker_routing": False,
            "real_orders": False,
            "real_balance": False,
            "margin": False,
            "leverage": False,
            "short": False,
            "derivatives": False,
            "destructive_actions_enabled": False,
        },
    }


def save_strategy(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    algo_state = normalize_algo_state(copy.deepcopy(state))
    if len(algo_state["strategies"]) >= MAX_STRATEGIES and not request.get("strategy_id"):
        raise AlgoError(f"Strategies exceed limit of {MAX_STRATEGIES}")
    now = _utc_now()
    strategy = normalize_strategy(
        {
            **request,
            "strategy_id": request.get("strategy_id") or f"algo-{uuid4().hex[:12]}",
            "created_at": request.get("created_at") or now,
            "updated_at": now,
            "version": "1.0",
        }
    )
    algo_state["strategies"][strategy["strategy_id"]] = strategy
    algo_state["active_strategy_id"] = strategy["strategy_id"]
    algo_state["updated_at"] = now
    return algo_state


def select_strategy(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    algo_state = normalize_algo_state(copy.deepcopy(state))
    strategy_id = _strategy_id(request.get("strategy_id"))
    if strategy_id not in algo_state["strategies"]:
        raise AlgoError("Strategy not found")
    algo_state["active_strategy_id"] = strategy_id
    algo_state["updated_at"] = _utc_now()
    return algo_state


def delete_strategy(state: dict[str, Any], strategy_id: str) -> dict[str, Any]:
    """Remove one user-library strategy; bundled catalog templates live elsewhere."""
    algo_state = normalize_algo_state(copy.deepcopy(state))
    target_id = _strategy_id(strategy_id)
    if not target_id:
        raise AlgoError("Strategy id is required")
    if target_id not in algo_state["strategies"]:
        raise AlgoError("Strategy not found")
    del algo_state["strategies"][target_id]
    if algo_state.get("active_strategy_id") == target_id:
        remaining = sorted(
            algo_state["strategies"].values(),
            key=lambda item: str(item.get("updated_at") or ""),
            reverse=True,
        )
        algo_state["active_strategy_id"] = (
            remaining[0]["strategy_id"] if remaining else None
        )
    algo_state["updated_at"] = _utc_now()
    return algo_state


def run_strategy_backtest(
    state: dict[str, Any],
    request: dict[str, Any],
    artifact_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    algo_state = normalize_algo_state(copy.deepcopy(state))
    strategy = _strategy_from_request_or_state(algo_state, request)
    config = _backtest_config_from_strategy(strategy, request)
    scan_seed_lineage = _lineage_from_scan_seed(request.get("scan_seed"), algo_state)
    if scan_seed_lineage:
        config["research_lineage"] = scan_seed_lineage
    try:
        result = run_backtest(config, artifact_root)
    except BacktestError as exc:
        raise AlgoError(str(exc)) from exc
    result["strategy_definition"] = {
        "strategy_id": strategy["strategy_id"],
        "name": strategy["name"],
        "timeframe": strategy["timeframe"],
        "backtest_strategy": config["strategy"],
        "backtest_strategy_label": result["summary"]["strategy_label"],
    }
    result["safety"] = algo_safety_payload()
    now = _utc_now()
    algo_state["last_backtest"] = {
        "strategy_id": strategy["strategy_id"],
        "run_id": result["run_id"],
        "artifact_dir": result["artifact_dir"],
        "return_pct": result["summary"]["return_pct"],
        "trade_count": result["summary"]["trade_count"],
        "backtest_strategy": result["summary"]["strategy"],
        "backtest_strategy_label": result["summary"]["strategy_label"],
        "created_at": now,
    }
    if result.get("research_lineage"):
        algo_state["last_backtest"]["research_lineage"] = result["research_lineage"]
    algo_state["active_strategy_id"] = strategy["strategy_id"]
    algo_state["updated_at"] = now
    return algo_state, result


def scan_market(
    state: dict[str, Any],
    request: dict[str, Any],
    market_cache: dict[str, Any] | None,
    provider_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    algo_state = normalize_algo_state(copy.deepcopy(state))
    strategy = _strategy_from_request_or_state(algo_state, request)
    symbols = _scan_symbols(request.get("symbols") or strategy["symbol"])
    timeframe = _timeframe(request.get("timeframe") or strategy["timeframe"])
    context = provider_context or {}
    market = markets_payload(
        default_markets_layout(),
        market_cache or {},
        research_data=context.get("research_data"),
        rates_data=context.get("rates_data"),
        fx_data=context.get("fx_data"),
        commodity_data=context.get("commodity_data"),
        fund_data=context.get("fund_data"),
        equity_quote_data=context.get("equity_quote_data"),
        etf_quote_data=context.get("etf_quote_data"),
    )
    source_row = _selected_source_row(request, market["source_coverage_matrix"])
    research_lineage = lineage_from_source_row(source_row)
    row_by_symbol = {row["symbol"]: row for row in market["rows"]}
    market_status = market["status"]
    no_provider_data = market_status["source"] == "offline_fixture" or market_status["state"] in {
        "offline",
        "unavailable",
    }
    results = []
    for symbol in symbols:
        row = row_by_symbol.get(symbol)
        if no_provider_data:
            match = 0
            signal = "NO_DATA"
            price = ""
            change_pct = ""
        else:
            signal, match = _provider_cache_signal(row)
            price = str(row.get("price") or "") if row else ""
            change_pct = str(row.get("chg_pct") or "") if row else ""
        provenance = _scan_row_provenance(row, market_status)
        results.append(
            {
                "symbol": symbol,
                "signal": signal,
                "match": match,
                "timeframe": timeframe,
                "details": _scan_details(strategy, row, market_status),
                "price": price,
                "change_pct": change_pct,
                "data_source": provenance["source"],
                "data_state": provenance["state"],
                "provider_id": provenance["provider_id"],
                "cache_path": provenance["cache_path"],
                "actionable": False,
            }
        )
    results = sorted(results, key=lambda result: result["match"], reverse=True)
    scan_id = f"scan-{uuid4().hex[:12]}"
    artifact_dir = f"{ALGO_SCAN_ARTIFACT_ROOT}/{scan_id}"
    scan = {
        "scan_id": scan_id,
        "strategy_id": strategy["strategy_id"],
        "preset": str(request.get("preset") or "custom"),
        "symbols": symbols,
        "timeframe": timeframe,
        "lookback_days": _bounded_int(request.get("lookback_days", 30), "Lookback days", 1, 1095),
        "results": results,
        "status": {
            "state": str(market_status["state"]) if no_provider_data else "complete",
            "source": market_status["source"],
            "provider_id": str(market_status.get("provider_id") or ""),
            "cache_path": str(market_status.get("cache_path") or ""),
            "dry_run": True,
            "live_deployment": False,
        },
        "source_contract": _scan_source_contract(market_status, no_provider_data),
        "artifact_dir": artifact_dir,
        "artifacts": {
            "scan": f"{artifact_dir}/scan.json",
            "report": f"{artifact_dir}/scan_report.md",
            "manifest": f"{artifact_dir}/manifest.json",
        },
        "research_lineage": research_lineage,
        "created_at": _utc_now(),
    }
    scan["research_lineage"] = with_scan_artifact_lineage(
        research_lineage,
        scan_id=scan_id,
        scan_artifact_path=scan["artifacts"]["scan"],
        scan_artifact_hash="",
    )
    scan["source_contract"]["markets_source_row_id"] = scan["research_lineage"][
        "markets_source_row_id"
    ]
    scan["source_contract"]["quote_semantics"] = scan["research_lineage"]["quote_semantics"]
    scan["research_lineage"] = with_scan_artifact_lineage(
        research_lineage,
        scan_id=scan_id,
        scan_artifact_path=scan["artifacts"]["scan"],
        scan_artifact_hash=scan_artifact_hash(scan),
    )
    algo_state["last_scan"] = scan
    algo_state["active_strategy_id"] = strategy["strategy_id"]
    algo_state["updated_at"] = scan["created_at"]
    return algo_state, scan


def _selected_source_row(
    request: dict[str, Any],
    source_coverage_matrix: list[dict[str, Any]],
) -> dict[str, Any]:
    row_id = request.get("markets_source_row_id")
    expected_hash = request.get("markets_source_row_hash")
    if not str(row_id or "").strip() and not str(expected_hash or "").strip():
        # Scans read the public crypto ticker cache, so default lineage to that
        # lane instead of whatever row happens to lead the coverage matrix
        # (previously an unrelated never-refreshed stocks row).
        for row in source_coverage_matrix:
            if str(row.get("provider_id") or "") == "binance_spot_public":
                row_id = row.get("markets_source_row_id")
                break
    try:
        return select_markets_source_row(
            source_coverage_matrix,
            row_id=row_id,
            expected_hash=expected_hash,
        )
    except ResearchLineageError as exc:
        raise AlgoError(str(exc)) from exc


def _lineage_from_scan_seed(
    raw_seed: Any,
    algo_state: dict[str, Any],
) -> dict[str, Any] | None:
    if raw_seed in (None, "", {}):
        return None
    if not isinstance(raw_seed, dict):
        raise AlgoError("Scan seed must be an object")
    last_scan = algo_state.get("last_scan")
    if not isinstance(last_scan, dict):
        raise AlgoError("Scan seed requires a local scan artifact")
    seed_scan_id = _scan_id(raw_seed.get("scan_id"))
    if seed_scan_id != last_scan.get("scan_id"):
        raise AlgoError("Scan seed does not match latest local scan")
    try:
        lineage = normalize_research_lineage(last_scan.get("research_lineage"))
    except ResearchLineageError as exc:
        raise AlgoError(str(exc)) from exc
    expected_hash = str(raw_seed.get("scan_artifact_hash") or "").strip()
    if expected_hash and expected_hash != lineage["scan_artifact_hash"]:
        raise AlgoError("Scan seed artifact hash mismatch")
    if not lineage["scan_artifact_hash"]:
        raise AlgoError("Scan seed artifact hash is required")
    return lineage


def normalize_strategy(raw: dict[str, Any], fallback_id: str | None = None) -> dict[str, Any]:
    strategy_id = _strategy_id(raw.get("strategy_id") or fallback_id)
    symbol = _symbol(raw.get("symbol", "BTCUSDT"))
    timeframe = _timeframe(raw.get("timeframe", "15m"))
    backtest = _normalize_backtest_settings(raw.get("backtest", {}))
    return {
        "strategy_id": strategy_id,
        "name": _safe_text(raw.get("name"), "Name", 80),
        "description": _optional_text(raw.get("description"), "", 240),
        "symbol": symbol,
        "timeframe": timeframe,
        "entry_conditions": _conditions(raw.get("entry_conditions", []), "Entry conditions"),
        "exit_conditions": _conditions(raw.get("exit_conditions", []), "Exit conditions"),
        "risk_settings": _risk_settings(raw.get("risk_settings", {})),
        "backtest": backtest,
        "version": str(raw.get("version") or "1.0")[:12],
        "created_at": str(raw.get("created_at") or _utc_now()),
        "updated_at": str(raw.get("updated_at") or _utc_now()),
    }


def _strategy_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    strategies = list(state["strategies"].values())
    return sorted(
        strategies, key=lambda strategy: str(strategy.get("updated_at", "")), reverse=True
    )


def _latest_strategy_id(strategies: dict[str, dict[str, Any]]) -> str:
    if not strategies:
        return ""
    return max(strategies.values(), key=lambda strategy: str(strategy.get("updated_at", "")))[
        "strategy_id"
    ]


def _strategy_from_request_or_state(
    state: dict[str, Any],
    request: dict[str, Any],
) -> dict[str, Any]:
    if isinstance(request.get("strategy"), dict):
        return normalize_strategy(request["strategy"])
    strategy_id = str(request.get("strategy_id") or state.get("active_strategy_id") or "")
    if not strategy_id:
        raise AlgoError("Strategy is required")
    strategy_id = _strategy_id(strategy_id)
    if strategy_id not in state["strategies"]:
        raise AlgoError("Strategy not found")
    return state["strategies"][strategy_id]


def _backtest_config_from_strategy(
    strategy: dict[str, Any], request: dict[str, Any]
) -> dict[str, Any]:
    request_backtest = request.get("backtest") if isinstance(request.get("backtest"), dict) else {}
    saved_strategy = _backtest_strategy(strategy["backtest"].get("strategy", "sma_cross"))
    if "strategy" in request_backtest:
        requested_strategy = _backtest_strategy(request_backtest.get("strategy"))
        if requested_strategy != saved_strategy:
            raise AlgoError("Backtest strategy override must match saved strategy")
    settings = {**strategy["backtest"], **request_backtest, "strategy": saved_strategy}
    return {
        "symbol": strategy["symbol"],
        "timeframe": strategy["timeframe"],
        "strategy": settings["strategy"],
        "fast_window": int(settings["fast_window"]),
        "slow_window": int(settings["slow_window"]),
        "initial_cash": settings["initial_cash"],
        "fee_rate": settings["fee_rate"],
        "slippage_bps": settings["slippage_bps"],
    }


def _normalize_backtest_settings(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    strategy = _backtest_strategy(source.get("strategy", "sma_cross"))
    try:
        parameters = normalize_strategy_parameters(strategy, source)
    except BacktestError as exc:
        raise AlgoError(str(exc)) from exc
    return {
        "strategy": strategy,
        "initial_cash": _money(
            _bounded_decimal(
                source.get("initial_cash", "100000.00"),
                "Initial cash",
                Decimal("0.01"),
                Decimal("1000000000"),
            )
        ),
        **parameters,
        "fee_rate": str(
            _bounded_decimal(
                source.get("fee_rate", "0.001"), "Fee rate", Decimal("0"), Decimal("0.1")
            )
        ),
        "slippage_bps": str(
            _bounded_decimal(
                source.get("slippage_bps", "2"),
                "Slippage bps",
                Decimal("0"),
                Decimal("1000"),
            )
        ),
    }


def _risk_settings(raw: Any) -> dict[str, str]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "stop_loss_pct": _ratio(source.get("stop_loss_pct", "5"), "Stop loss percent"),
        "take_profit_pct": _ratio(source.get("take_profit_pct", "12"), "Take profit percent"),
        "trailing_stop_pct": _ratio(source.get("trailing_stop_pct", "0"), "Trailing stop percent"),
    }


def _conditions(raw: Any, label: str) -> list[str]:
    if isinstance(raw, str):
        raw = [line.strip() for line in raw.splitlines() if line.strip()]
    if not isinstance(raw, list):
        raise AlgoError(f"{label} must be a list")
    if len(raw) > MAX_CONDITIONS:
        raise AlgoError(f"{label} exceed limit of {MAX_CONDITIONS}")
    conditions = [_safe_text(condition, label, 120) for condition in raw if str(condition).strip()]
    if not conditions:
        raise AlgoError(f"{label} are required")
    return conditions


def _scan_symbols(raw: Any) -> list[str]:
    if isinstance(raw, str):
        raw = raw.replace("\n", ",").split(",")
    if not isinstance(raw, list):
        raise AlgoError("Symbols must be a list or string")
    symbols = [_symbol(symbol) for symbol in raw if str(symbol).strip()]
    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        raise AlgoError("At least one symbol is required")
    if len(symbols) > MAX_SCAN_SYMBOLS:
        raise AlgoError(f"Symbols exceed limit of {MAX_SCAN_SYMBOLS}")
    return symbols


def _scan_details(
    strategy: dict[str, Any],
    row: dict[str, str] | None,
    market_status: dict[str, str],
) -> str:
    if market_status["source"] == "offline_fixture" or market_status["state"] in {
        "offline",
        "unavailable",
    }:
        return "Public or stale market cache required before scan signals are emitted."
    if row and not _is_unavailable_market_row(row):
        return (
            f"{strategy['name']} checked {row['symbol']} at {row['price']} "
            f"using {market_status['source']} dry-run data."
        )
    return f"{strategy['name']} has no current market row; dry-run only."


def _scan_row_provenance(
    row: dict[str, str] | None,
    market_status: dict[str, Any],
) -> dict[str, str]:
    row_source = row or {}
    if _is_unavailable_market_row(row):
        return {
            "source": str(row_source.get("source") or market_status.get("source") or ""),
            "state": str(row_source.get("state") or market_status.get("state") or ""),
            "provider_id": str(row_source.get("provider_id") or market_status.get("provider_id") or ""),
            "cache_path": str(row_source.get("cache_path") or market_status.get("cache_path") or ""),
        }
    return {
        "source": str(market_status.get("source") or row_source.get("source") or ""),
        "state": str(market_status.get("state") or row_source.get("state") or ""),
        "provider_id": str(market_status.get("provider_id") or row_source.get("provider_id") or ""),
        "cache_path": str(market_status.get("cache_path") or row_source.get("cache_path") or ""),
    }


def _is_unavailable_market_row(row: dict[str, str] | None) -> bool:
    if not row:
        return True
    return str(row.get("state") or "").lower() == "unavailable" or str(
        row.get("price") or "N/A"
    ) == "N/A"


def _provider_cache_signal(row: dict[str, str] | None) -> tuple[str, int]:
    if row is None or str(row.get("price") or "N/A") == "N/A":
        return "NO_DATA", 0
    change_pct = _optional_decimal(row.get("chg_pct"))
    price = _optional_decimal(row.get("price"))
    high = _optional_decimal(row.get("high"))
    low = _optional_decimal(row.get("low"))
    volume = _optional_decimal(row.get("vol"))
    if price is None or change_pct is None:
        return "NO_DATA", 0

    trend_score = max(Decimal("-20"), min(Decimal("25"), change_pct * Decimal("4")))
    range_score = Decimal("0")
    if high is not None and low is not None and high > low:
        location = (price - low) / (high - low)
        range_score = max(Decimal("-8"), min(Decimal("12"), (location - Decimal("0.5")) * 24))
    liquidity_score = Decimal("0")
    if volume is not None and volume > 0:
        liquidity_score = min(Decimal("8"), volume.adjusted() + Decimal("1"))
    match_decimal = Decimal("55") + trend_score + range_score + liquidity_score
    match = int(max(Decimal("0"), min(Decimal("100"), match_decimal)).quantize(Decimal("1")))
    if change_pct <= Decimal("-1.0"):
        return "FLAT", max(20, min(match, 58))
    if match >= 72:
        return "LONG", match
    return "WATCH", match


def _optional_decimal(raw: Any) -> Decimal | None:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    if not value.is_finite():
        return None
    return value


def _scan_source_contract(
    market_status: dict[str, Any],
    no_provider_data: bool,
) -> dict[str, Any]:
    return {
        "source": str(market_status.get("source") or "public_provider_unavailable"),
        "state": str(market_status.get("state") or "unavailable"),
        "provider_id": str(market_status.get("provider_id") or ""),
        "cache_path": str(market_status.get("cache_path") or ""),
        "retrieved_at": str(market_status.get("last_update") or ""),
        "data_mode": "no_provider_data" if no_provider_data else "provider_cache",
        "fixture_primary_runtime": False,
        "result_use": "local_research_signal_only",
        "live_action_enabled": False,
    }


def _empty_scan_artifact_health() -> dict[str, Any]:
    return {
        "status": "no_scan",
        "scan_id": "",
        "present_count": 0,
        "missing_count": 0,
        "repair_available": False,
        "repair_action": "algo_scan_artifacts_repair",
        "destructive_actions_enabled": False,
    }


def _readiness_strategy(strategy: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(strategy, dict):
        return {
            "strategy_id": "",
            "name": "",
            "symbol": "",
            "timeframe": "",
            "backtest_strategy": "",
            "entry_condition_count": 0,
            "exit_condition_count": 0,
        }
    return {
        "strategy_id": str(strategy.get("strategy_id") or ""),
        "name": str(strategy.get("name") or ""),
        "symbol": str(strategy.get("symbol") or ""),
        "timeframe": str(strategy.get("timeframe") or ""),
        "backtest_strategy": str(_dict(strategy.get("backtest")).get("strategy") or ""),
        "entry_condition_count": len(_list(strategy.get("entry_conditions"))),
        "exit_condition_count": len(_list(strategy.get("exit_conditions"))),
    }


def _symbol_readiness(
    symbol: str,
    row: dict[str, Any] | None,
    market_status: dict[str, Any],
    no_provider_data: bool,
) -> dict[str, Any]:
    signal, match = ("NO_DATA", 0) if no_provider_data else _provider_cache_signal(row)
    provenance = _scan_row_provenance(row, market_status)
    return {
        "symbol": symbol,
        "data_available": not no_provider_data and not _is_unavailable_market_row(row),
        "expected_signal": signal,
        "expected_match": match,
        "source": provenance["source"],
        "state": provenance["state"],
        "provider_id": provenance["provider_id"],
        "cache_path": provenance["cache_path"],
        "actionable": False,
    }


def _readiness_source_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(row, dict):
        return {
            "markets_source_row_id": "",
            "asset_family": "",
            "runtime_role": "",
            "provider_id": "",
            "state": "missing",
            "quote_semantics": "",
            "cache_path": "",
            "live_action_enabled": False,
        }
    return {
        "markets_source_row_id": str(row.get("markets_source_row_id") or ""),
        "asset_family": str(row.get("asset_family") or ""),
        "runtime_role": str(row.get("runtime_role") or ""),
        "provider_id": str(row.get("provider_id") or ""),
        "state": str(row.get("state") or "unknown"),
        "quote_semantics": str(row.get("quote_semantics") or ""),
        "cache_path": str(row.get("cache_path") or ""),
        "live_action_enabled": bool(row.get("live_action_enabled")),
    }


def _readiness_latest_scan(scan: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(scan, dict):
        return {
            "scan_id": "",
            "state": "none",
            "source": "",
            "provider_id": "",
            "artifact_dir": "",
            "scan_seed_ready": False,
        }
    status = _dict(scan.get("status"))
    return {
        "scan_id": str(scan.get("scan_id") or ""),
        "state": str(status.get("state") or "unknown"),
        "source": str(status.get("source") or ""),
        "provider_id": str(status.get("provider_id") or ""),
        "artifact_dir": str(scan.get("artifact_dir") or ""),
        "scan_seed_ready": bool(_scan_seed_hash(scan)),
    }


def _readiness_backtest_handoff(
    scan: dict[str, Any] | None,
    artifact_health: dict[str, Any],
) -> dict[str, Any]:
    seed_hash = _scan_seed_hash(scan)
    return {
        "ready": bool(seed_hash),
        "action_id": "algo_run_backtest",
        "scan_id": str(scan.get("scan_id") or "") if isinstance(scan, dict) else "",
        "scan_artifact_hash": seed_hash,
        "artifact_mirror_complete": str(artifact_health.get("status") or "") == "complete",
        "live_action_enabled": False,
        "broker_routing": False,
    }


def _readiness_action(
    action_id: str,
    *,
    ready: bool,
    safe: bool,
    reason: str,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "ready": ready,
        "safe": safe,
        "reason": reason,
    }


def _scan_seed_hash(scan: dict[str, Any] | None) -> str:
    if not isinstance(scan, dict):
        return ""
    lineage = scan.get("research_lineage")
    if not isinstance(lineage, dict):
        return ""
    return str(lineage.get("scan_artifact_hash") or "")


def _dict(raw: Any) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _list(raw: Any) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _normalize_last_scan(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise AlgoError("Last scan must be an object")
    status = raw.get("status")
    if not isinstance(status, dict):
        raise AlgoError("Last scan status is required")
    if status.get("dry_run") is not True:
        raise AlgoError("Last scan must be dry-run")
    if status.get("live_deployment") not in (False, None):
        raise AlgoError("Last scan must not be live deployment")
    raw_results = raw.get("results")
    if not isinstance(raw_results, list):
        raise AlgoError("Last scan results must be a list")
    normalized = {
        "scan_id": _scan_id(raw.get("scan_id")),
        "strategy_id": _strategy_id(raw.get("strategy_id")),
        "preset": _optional_text(raw.get("preset"), "custom", 80),
        "symbols": _scan_symbols(raw.get("symbols")),
        "timeframe": _timeframe(raw.get("timeframe")),
        "lookback_days": _bounded_int(raw.get("lookback_days"), "Lookback days", 1, 1095),
        "results": _normalize_scan_results(raw_results),
        "status": {
            "state": _safe_text(status.get("state"), "Last scan state", 40),
            "source": _safe_text(status.get("source"), "Last scan source", 80),
            "provider_id": _optional_text(status.get("provider_id"), "", 80),
            "cache_path": _optional_text(status.get("cache_path"), "", 160),
            "dry_run": True,
            "live_deployment": False,
        },
        "source_contract": _normalize_scan_source_contract(raw.get("source_contract")),
        "artifact_dir": _scan_artifact_dir(raw.get("artifact_dir"), raw.get("scan_id")),
        "artifacts": _normalize_scan_artifacts(raw.get("artifacts"), raw.get("scan_id")),
        "created_at": _safe_text(raw.get("created_at"), "Last scan timestamp", 80),
    }
    research_lineage = _normalize_optional_research_lineage(raw.get("research_lineage"))
    if research_lineage:
        normalized["research_lineage"] = research_lineage
    return normalized


def _normalize_scan_results(raw_results: list[Any]) -> list[dict[str, Any]]:
    results = []
    for raw_result in raw_results[:MAX_SCAN_SYMBOLS]:
        if not isinstance(raw_result, dict):
            continue
        try:
            signal = str(raw_result.get("signal") or "")
            if signal not in {"LONG", "WATCH", "FLAT", "NO_DATA"}:
                raise AlgoError("Last scan signal is invalid")
            results.append(
                {
                    "symbol": _symbol(raw_result.get("symbol")),
                    "signal": signal,
                    "match": _bounded_int(raw_result.get("match"), "Match", 0, 100),
                    "timeframe": _timeframe(raw_result.get("timeframe")),
                    "details": _optional_text(raw_result.get("details"), "", 240),
                    "price": _optional_text(raw_result.get("price"), "", 40),
                    "change_pct": _optional_text(raw_result.get("change_pct"), "", 40),
                    "data_source": _optional_text(raw_result.get("data_source"), "", 80),
                    "data_state": _optional_text(raw_result.get("data_state"), "", 40),
                    "provider_id": _optional_text(raw_result.get("provider_id"), "", 80),
                    "cache_path": _optional_text(raw_result.get("cache_path"), "", 160),
                    "actionable": False,
                }
            )
        except AlgoError:
            continue
    return results


def _normalize_scan_source_contract(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "source": _optional_text(source.get("source"), "", 80),
        "state": _optional_text(source.get("state"), "", 40),
        "provider_id": _optional_text(source.get("provider_id"), "", 80),
        "cache_path": _optional_text(source.get("cache_path"), "", 160),
        "retrieved_at": _optional_text(source.get("retrieved_at"), "", 80),
        "data_mode": _optional_text(source.get("data_mode"), "no_provider_data", 80),
        "fixture_primary_runtime": False,
        "result_use": "local_research_signal_only",
        "live_action_enabled": False,
        "markets_source_row_id": _optional_text(source.get("markets_source_row_id"), "", 160),
        "quote_semantics": _optional_text(source.get("quote_semantics"), "", 80),
    }


def _normalize_optional_research_lineage(raw: Any) -> dict[str, Any] | None:
    if raw in (None, "", {}):
        return None
    try:
        return normalize_research_lineage(raw)
    except ResearchLineageError as exc:
        raise AlgoError(str(exc)) from exc


def _normalize_scan_artifacts(raw: Any, scan_id: Any) -> dict[str, str]:
    normalized_scan_id = _scan_id(scan_id)
    artifact_dir = f"{ALGO_SCAN_ARTIFACT_ROOT}/{normalized_scan_id}"
    source = raw if isinstance(raw, dict) else {}
    defaults = {
        "scan": f"{artifact_dir}/scan.json",
        "report": f"{artifact_dir}/scan_report.md",
        "manifest": f"{artifact_dir}/manifest.json",
    }
    return {
        key: _scan_artifact_path(source.get(key), default)
        for key, default in defaults.items()
    }


def _scan_artifact_dir(raw: Any, scan_id: Any) -> str:
    default = f"{ALGO_SCAN_ARTIFACT_ROOT}/{_scan_id(scan_id)}"
    value = str(raw or default).strip().replace("\\", "/")
    if value != default:
        raise AlgoError("Last scan artifact directory is invalid")
    return value


def _scan_artifact_path(raw: Any, default: str) -> str:
    value = str(raw or default).strip().replace("\\", "/")
    if value != default:
        raise AlgoError("Last scan artifact path is invalid")
    return value


def _scan_id(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value or len(value) > 64:
        raise AlgoError("Last scan id is required")
    if not all(ch.isalnum() or ch in {"-", "_"} for ch in value):
        raise AlgoError("Last scan id is invalid")
    return value


def scan_report_text(scan: dict[str, Any]) -> str:
    status = scan.get("status") if isinstance(scan.get("status"), dict) else {}
    lineage = scan.get("research_lineage") if isinstance(scan.get("research_lineage"), dict) else {}
    lines = [
        "# Algo Scan Report",
        "",
        f"- Scan: {scan.get('scan_id', '')}",
        f"- Strategy: {scan.get('strategy_id', '')}",
        f"- Source: {status.get('source', '')}",
        f"- State: {status.get('state', '')}",
        f"- Markets source row: {lineage.get('markets_source_row_id', '')}",
        f"- Quote semantics: {lineage.get('quote_semantics', '')}",
        "- Use: local research signals only",
        "- Live action enabled: false",
        "",
        "| Symbol | Signal | Match | Source | State | Price | Change % |",
        "| --- | --- | ---: | --- | --- | ---: | ---: |",
    ]
    for row in scan.get("results", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            "| {symbol} | {signal} | {match} | {source} | {state} | {price} | {chg} |".format(
                symbol=row.get("symbol", ""),
                signal=row.get("signal", ""),
                match=row.get("match", ""),
                source=row.get("data_source", ""),
                state=row.get("data_state", ""),
                price=row.get("price", ""),
                chg=row.get("change_pct", ""),
            )
        )
    lines.append("")
    return "\n".join(lines)


def scan_artifact_manifest(scan: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_type": "algo_provider_cache_scan",
        "scan_id": str(scan.get("scan_id") or ""),
        "created_at": str(scan.get("created_at") or ""),
        "source_contract": dict(scan.get("source_contract") or {}),
        "research_lineage": dict(scan.get("research_lineage") or {}),
        "artifacts": dict(scan.get("artifacts") or {}),
        "safety": algo_safety_payload(),
        "result_count": len(scan.get("results", [])) if isinstance(scan.get("results"), list) else 0,
        "live_action_enabled": False,
        "fixture_primary_runtime": False,
    }


def _normalize_last_backtest(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise AlgoError("Last backtest must be an object")
    normalized = {
        "strategy_id": _strategy_id(raw.get("strategy_id")),
        "run_id": _safe_text(raw.get("run_id"), "Last backtest run id", 80),
        "artifact_dir": _artifact_dir(raw.get("artifact_dir")),
        "return_pct": _safe_text(raw.get("return_pct"), "Last backtest return", 40),
        "trade_count": _bounded_int(raw.get("trade_count"), "Trade count", 0, 1_000_000),
        "backtest_strategy": _backtest_strategy(raw.get("backtest_strategy") or "sma_cross"),
        "backtest_strategy_label": _optional_text(
            raw.get("backtest_strategy_label"),
            _backtest_strategy_label(raw.get("backtest_strategy") or "sma_cross"),
            80,
        ),
        "created_at": _safe_text(raw.get("created_at"), "Last backtest timestamp", 80),
    }
    research_lineage = _normalize_optional_research_lineage(raw.get("research_lineage"))
    if research_lineage:
        normalized["research_lineage"] = research_lineage
    return normalized


def _artifact_dir(raw: Any) -> str:
    value = str(raw or "").strip().replace("\\", "/")
    parts = value.split("/")
    if (
        not value
        or value.startswith("/")
        or ":" in value
        or ".." in parts
        or not value.startswith("artifacts/backtests/")
    ):
        raise AlgoError("Last backtest artifact path is invalid")
    return value


def _symbol(raw: Any) -> str:
    symbol = "".join(ch for ch in str(raw or "").upper() if ch.isalnum())
    if symbol not in SUPPORTED_ALGO_SYMBOLS:
        raise AlgoError("Unsupported algo symbol")
    return symbol


def _timeframe(raw: Any) -> str:
    timeframe = str(raw or "15m")
    if timeframe not in SUPPORTED_TIMEFRAMES:
        raise AlgoError("Unsupported algo timeframe")
    return timeframe


def _strategy_id(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value or len(value) > 48:
        raise AlgoError("Strategy id is required")
    if not all(ch.isalnum() or ch in {"-", "_"} for ch in value):
        raise AlgoError("Strategy id is invalid")
    return value


def _backtest_strategy(raw: Any) -> str:
    value = str(raw or "").strip()
    if value not in BACKTEST_STRATEGY_BY_ID:
        raise AlgoError("Unsupported algo backtest strategy")
    return value


def _backtest_strategy_label(strategy_id: Any) -> str:
    strategy = BACKTEST_STRATEGY_BY_ID.get(str(strategy_id or ""))
    return str(strategy["label"]) if strategy else str(strategy_id or "")


def _safe_text(raw: Any, label: str, max_length: int) -> str:
    value = str(raw or "").strip()
    if not value:
        raise AlgoError(f"{label} is required")
    if _looks_like_secret(value):
        raise AlgoError(f"{label} appears to contain credential material")
    return value[:max_length]


def _optional_text(raw: Any, default: str, max_length: int) -> str:
    value = str(raw or default).strip()
    if value and _looks_like_secret(value):
        raise AlgoError("Description appears to contain credential material")
    return value[:max_length]


def _looks_like_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in ALGO_SECRET_PATTERNS)


def _bounded_decimal(raw: Any, label: str, minimum: Decimal, maximum: Decimal) -> Decimal:
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise AlgoError(f"{label} must be numeric") from None
    if not value.is_finite():
        raise AlgoError(f"{label} must be finite")
    if value < minimum:
        raise AlgoError(f"{label} is below minimum")
    if value > maximum:
        raise AlgoError(f"{label} is too large")
    return value


def _bounded_int(raw: Any, label: str, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise AlgoError(f"{label} must be numeric") from None
    if value < minimum:
        raise AlgoError(f"{label} is below minimum")
    if value > maximum:
        raise AlgoError(f"{label} is too large")
    return value


def _ratio(raw: Any, label: str) -> str:
    return str(
        _bounded_decimal(raw, label, Decimal("0"), Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
