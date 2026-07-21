"""Strict local backtest engine with closed-candle artifacts."""

from __future__ import annotations

import csv
import copy
import hashlib
import itertools
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from uuid import uuid4

from otto.local_terminal.crypto_data import crypto_detail_payload
from otto.local_terminal.research_lineage import (
    ResearchLineageError,
    normalize_research_lineage,
    with_backtest_lineage,
)


DEFAULT_BACKTEST_CONFIG: dict[str, Any] = {
    "symbol": "BTCUSDT",
    "timeframe": "15m",
    "strategy": "sma_cross",
    "fast_window": 3,
    "slow_window": 5,
    "initial_cash": "100000.00",
    "fee_rate": "0.001",
    "slippage_bps": "2",
    "data_provider": "deterministic_local_closed_candle",
}
BACKTEST_PROVIDER = "deterministic_local_closed_candle"
PUBLIC_BACKTEST_PROVIDER = "public_crypto_closed_candle_cache"
BACKTEST_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
BACKTEST_TIMEFRAMES = ("15m",)
DEFAULT_BACKTEST_RUN_INDEX_LIMIT = 8
BACKTEST_RUN_HEALTH_EXPECTED_FILES = (
    "config.json",
    "data_snapshot.json",
    "summary.json",
    "trades.csv",
    "signals.csv",
    "indicators.json",
    "returns_analysis.json",
    "returns_curve.csv",
    "provenance.json",
    "report.md",
    "manifest.json",
)


def _strategy_catalog_entry(
    *,
    strategy_id: str,
    label: str,
    description: str,
    fast_label: str,
    slow_label: str,
) -> dict[str, Any]:
    parameters = [
        {
            "key": "fast_window",
            "label": fast_label,
            "kind": "integer",
            "default": 3,
            "minimum": 2,
            "maximum": 100,
            "role": "signal_window",
        },
        {
            "key": "slow_window",
            "label": slow_label,
            "kind": "integer",
            "default": 5,
            "minimum": 3,
            "maximum": 200,
            "role": "confirmation_window",
            "must_be_greater_than": "fast_window",
        },
    ]
    return {
        "strategy_id": strategy_id,
        "label": label,
        "description": description,
        "fast_label": fast_label,
        "slow_label": slow_label,
        "risk_model": "long_flat_next_open",
        "parameter_schema_version": "strategy-parameters-v1",
        "parameters": parameters,
        "constraints": [
            {
                "left": "slow_window",
                "operator": "greater_than",
                "right": "fast_window",
                "message": "Slow window must be greater than fast window",
            }
        ],
        "artifact_contract": "local_closed_candle_backtest_artifacts_v1",
        "execution_safety": {
            "positioning": "long_flat",
            "fills": "next_open",
            "live_orders": False,
            "broker_routing": False,
            "short": False,
            "derivatives": False,
        },
    }


STRATEGY_CATALOG: tuple[dict[str, Any], ...] = (
    _strategy_catalog_entry(
        strategy_id="sma_cross",
        label="SMA Cross",
        description="Long/flat moving-average crossover with next-open fills.",
        fast_label="Fast SMA",
        slow_label="Slow SMA",
    ),
    _strategy_catalog_entry(
        strategy_id="channel_breakout",
        label="Channel Breakout",
        description="Long/flat breakout above prior channel highs with channel-low exits.",
        fast_label="Exit Window",
        slow_label="Breakout Window",
    ),
    _strategy_catalog_entry(
        strategy_id="sma_mean_reversion",
        label="SMA Mean Reversion",
        description="Long/flat pullback entry below the prior mean with recovery exits.",
        fast_label="Exit SMA",
        slow_label="Mean SMA",
    ),
    _strategy_catalog_entry(
        strategy_id="volatility_reversion",
        label="Volatility Reversion",
        description="Long/flat pullback entry below the rolling volatility band with SMA exits.",
        fast_label="Exit SMA",
        slow_label="Band Window",
    ),
    _strategy_catalog_entry(
        strategy_id="momentum_continuation",
        label="Momentum Continuation",
        description="Long/flat continuation entry above the prior momentum close with SMA exits.",
        fast_label="Exit SMA",
        slow_label="Momentum Lookback",
    ),
    _strategy_catalog_entry(
        strategy_id="rsi_reversion",
        label="RSI Reversion",
        description="Long/flat oversold RSI entry with recovery exits.",
        fast_label="Exit SMA",
        slow_label="RSI Lookback",
    ),
)
STRATEGY_IDS = {str(strategy["strategy_id"]) for strategy in STRATEGY_CATALOG}
STRATEGY_LABELS = {
    str(strategy["strategy_id"]): str(strategy["label"]) for strategy in STRATEGY_CATALOG
}


class BacktestError(ValueError):
    """Raised when a backtest request violates local closed-candle rules."""


def default_backtest_config() -> dict[str, Any]:
    return dict(DEFAULT_BACKTEST_CONFIG)


def backtest_strategy_catalog() -> list[dict[str, Any]]:
    return copy.deepcopy(list(STRATEGY_CATALOG))


def normalize_strategy_parameters(strategy: str, source: dict[str, Any]) -> dict[str, int]:
    entry = _strategy_entry(strategy)
    values = {}
    for parameter in entry["parameters"]:
        values[parameter["key"]] = _bounded_int_parameter(
            source.get(parameter["key"], parameter["default"]),
            parameter,
        )
    _validate_strategy_constraints(entry, values)
    return values


def run_backtest(
    config: dict[str, Any],
    artifact_root: Path,
    provider_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized, candles, provenance = _normalized_config_and_candles(config, provider_cache)
    result = run_strategy(normalized, candles, provenance)
    return write_backtest_artifacts(artifact_root, normalized, candles, result, provenance)


def run_walk_forward(
    config: dict[str, Any],
    artifact_root: Path,
    provider_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized, candles, provenance = _normalized_config_and_candles(config, provider_cache)
    fold_count = _bounded_walk_forward_folds(config.get("fold_count", 3))
    windows = walk_forward_windows(candles, normalized, fold_count)
    folds = []
    total_trades = 0
    total_signals = 0
    fold_returns: list[Decimal] = []
    for index, window in enumerate(windows, start=1):
        result = run_strategy(normalized, window["test_candles"], provenance)
        fold_return = Decimal(result["summary"]["return_pct"])
        fold_returns.append(fold_return)
        total_trades += int(result["metrics"]["trade_count"])
        total_signals += int(result["metrics"]["signal_count"])
        folds.append(
            {
                "fold_id": f"fold-{index}",
                "fold_index": index,
                "train_candle_count": window["train_candle_count"],
                "test_candle_count": window["test_candle_count"],
                "train_first_opened_at": window["train_first_opened_at"],
                "train_last_closed_at": window["train_last_closed_at"],
                "test_first_opened_at": window["test_first_opened_at"],
                "test_last_closed_at": window["test_last_closed_at"],
                "initial_cash": result["summary"]["initial_cash"],
                "final_equity": result["summary"]["final_equity"],
                "return_pct": result["summary"]["return_pct"],
                "max_drawdown_pct": result["metrics"]["max_drawdown_pct"],
                "best_period_return_pct": result["returns_analysis"]["best_period_return_pct"],
                "worst_period_return_pct": result["returns_analysis"]["worst_period_return_pct"],
                "trade_count": result["metrics"]["trade_count"],
                "signal_count": result["metrics"]["signal_count"],
                "lookahead_guard": result["summary"]["lookahead_guard"],
                "same_candle_fills": result["summary"]["same_candle_fills"],
                "data_source": result["summary"]["data_source"],
                "data_state": result["summary"]["data_state"],
            }
        )
    # The whole point of walk-forward is comparing the full-window headline a
    # plain backtest would show against how the same parameters hold up on
    # out-of-sample slices — so compute both and say what the gap means.
    full_window = run_strategy(normalized, candles, provenance)
    full_window_return = Decimal(full_window["summary"]["return_pct"])
    average_return = (
        sum(fold_returns, Decimal("0")) / Decimal(len(fold_returns))
        if fold_returns
        else Decimal("0")
    )
    positive_folds = sum(1 for value in fold_returns if value > 0)
    consistency, consistency_note = _walk_forward_consistency(
        full_window_return, average_return, positive_folds, len(fold_returns)
    )
    summary = {
        "symbol": normalized["symbol"],
        "strategy": normalized["strategy"],
        "strategy_label": _strategy_label(normalized["strategy"]),
        "timeframe": normalized["timeframe"],
        "run_state": "complete",
        "mode": "fixed_parameter_walk_forward",
        "train_usage": "metadata_only_no_fit_no_warmup",
        "fold_count": len(folds),
        "completed_folds": len(folds),
        "average_return_pct": _decimal_percent_average(fold_returns),
        "best_fold_return_pct": str(max(fold_returns).quantize(Decimal("0.01"))),
        "worst_fold_return_pct": str(min(fold_returns).quantize(Decimal("0.01"))),
        "positive_folds": positive_folds,
        "full_window_return_pct": str(full_window_return.quantize(Decimal("0.01"))),
        "in_sample_oos_gap_pct": str(
            (full_window_return - average_return).quantize(Decimal("0.01"))
        ),
        "consistency": consistency,
        "consistency_note": consistency_note,
        "total_trade_count": total_trades,
        "total_signal_count": total_signals,
        "closed_candles": len(candles),
        "lookahead_guard": "signals_on_close_fills_next_open",
        "same_candle_fills": False,
        "optimization": "disabled_fixed_parameters_only",
        "data_provider": normalized.get("data_provider", provenance["provider"]),
        "data_source": provenance["source"],
        "data_state": provenance["state"],
        "data_retrieved_at": provenance["retrieved_at"],
        "cache_snapshot_hash": provenance["cache_snapshot_hash"],
        "source_first_opened_at": provenance["source_first_opened_at"],
        "source_last_closed_at": provenance["source_last_closed_at"],
        "deterministic_fallback": provenance["deterministic_fallback"],
    }
    return write_walk_forward_artifacts(
        artifact_root,
        {**normalized, "fold_count": fold_count},
        candles,
        summary,
        folds,
        provenance,
    )


OPTIMIZE_MAX_COMBINATIONS = 24
OPTIMIZE_MAX_VALUES_PER_PARAM = 8
_OPTIMIZE_DEFAULT_GRID: dict[str, tuple[int, ...]] = {
    "fast_window": (3, 5, 8, 13),
    "slow_window": (21, 34, 55),
}


def run_optimize(
    config: dict[str, Any],
    artifact_root: Path,
    provider_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Local, deterministic parameter grid search over one strategy's own schema.

    Runs the same closed-candle strategy for each bounded parameter combination on a
    single shared data snapshot, ranks by return, and writes local artifacts. It never
    optimizes-then-deploys, routes orders, shorts, or touches live/broker paths.
    """

    requested_objective = str(config.get("objective") or "return_pct")
    if requested_objective != "return_pct":
        raise BacktestError(
            f"Unsupported optimize objective '{requested_objective}'; supported objectives: return_pct"
        )

    normalized, candles, provenance = _normalized_config_and_candles(config, provider_cache)
    entry = _strategy_entry(normalized["strategy"])
    grid = _resolve_optimize_grid(entry, config.get("parameter_grid"))
    combinations = _optimize_combinations(entry, grid)
    if not combinations:
        raise BacktestError("No valid parameter combinations to optimize")

    rows: list[dict[str, Any]] = []
    for parameters in combinations:
        result = run_strategy({**normalized, **parameters}, candles, provenance)
        rows.append(
            {
                "parameters": parameters,
                "fast_window": parameters["fast_window"],
                "slow_window": parameters["slow_window"],
                "return_pct": result["summary"]["return_pct"],
                "final_equity": result["summary"]["final_equity"],
                "max_drawdown_pct": result["metrics"]["max_drawdown_pct"],
                "trade_count": result["metrics"]["trade_count"],
                "signal_count": result["metrics"]["signal_count"],
            }
        )

    ranked = sorted(rows, key=lambda row: Decimal(str(row["return_pct"] or "0")), reverse=True)
    for index, row in enumerate(ranked, start=1):
        row["rank"] = index
    best = ranked[0]
    summary = {
        "symbol": normalized["symbol"],
        "strategy": normalized["strategy"],
        "strategy_label": _strategy_label(normalized["strategy"]),
        "timeframe": normalized["timeframe"],
        "run_state": "complete",
        "mode": "local_grid_search",
        "objective": "return_pct",
        "objective_direction": "maximize",
        "evaluated_count": len(ranked),
        "requested_grid": grid,
        "best_parameters": best["parameters"],
        "best_return_pct": best["return_pct"],
        "best_final_equity": best["final_equity"],
        "best_max_drawdown_pct": best["max_drawdown_pct"],
        "initial_cash": normalized.get("initial_cash", DEFAULT_BACKTEST_CONFIG["initial_cash"]),
        "closed_candles": len(candles),
        "lookahead_guard": "signals_on_close_fills_next_open",
        "same_candle_fills": False,
        "optimization": "local_grid_search_v1",
        "data_provider": normalized.get("data_provider", provenance["provider"]),
        "data_source": provenance["source"],
        "data_state": provenance["state"],
        "data_retrieved_at": provenance["retrieved_at"],
        "cache_snapshot_hash": provenance["cache_snapshot_hash"],
        "deterministic_fallback": provenance["deterministic_fallback"],
    }
    return write_optimize_artifacts(artifact_root, normalized, summary, ranked, grid, provenance)


def _resolve_optimize_grid(
    entry: dict[str, Any], override: Any
) -> dict[str, list[int]]:
    override_map = override if isinstance(override, dict) else {}
    grid: dict[str, list[int]] = {}
    for parameter in entry["parameters"]:
        key = str(parameter["key"])
        minimum = int(parameter["minimum"])
        maximum = int(parameter["maximum"])
        source = override_map.get(key)
        if isinstance(source, (list, tuple)) and source:
            candidates: tuple[Any, ...] = tuple(source)
        else:
            candidates = _OPTIMIZE_DEFAULT_GRID.get(key, (parameter["default"],))
        cleaned: list[int] = []
        for raw in candidates:
            value = _safe_optimize_int(raw)
            if value is not None and minimum <= value <= maximum:
                cleaned.append(value)
        values = sorted(set(cleaned)) or [int(parameter["default"])]
        grid[key] = values[:OPTIMIZE_MAX_VALUES_PER_PARAM]
    return grid


def _optimize_combinations(
    entry: dict[str, Any], grid: dict[str, list[int]]
) -> list[dict[str, int]]:
    keys = [str(parameter["key"]) for parameter in entry["parameters"]]
    value_lists = [grid[key] for key in keys]
    combinations: list[dict[str, int]] = []
    for values in itertools.product(*value_lists):
        candidate = dict(zip(keys, values, strict=True))
        try:
            resolved = normalize_strategy_parameters(str(entry["strategy_id"]), candidate)
        except BacktestError:
            continue  # skip combinations that break the strategy's own constraints
        combinations.append(resolved)
        if len(combinations) >= OPTIMIZE_MAX_COMBINATIONS:
            break
    return combinations


def _safe_optimize_int(raw: Any) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def write_optimize_artifacts(
    artifact_root: Path,
    config: dict[str, Any],
    summary: dict[str, Any],
    ranked: list[dict[str, Any]],
    grid: dict[str, list[int]],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    now = datetime.now(tz=UTC)
    optimize_id = f"btopt-{now.strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    artifact_dir = artifact_root / "artifacts" / "backtests" / "optimizations" / optimize_id
    safety = {
        "optimization": "local_grid_search_v1",
        "positioning": "long_flat",
        "fills": "next_open",
        "live_orders": False,
        "broker_routing": False,
        "deploy": False,
        "short": False,
        "derivatives": False,
        "same_candle_fills": False,
    }
    payload = {
        "optimize_id": optimize_id,
        "artifact_dir": artifact_dir.relative_to(artifact_root).as_posix(),
        "config": {
            key: config.get(key)
            for key in (
                "symbol",
                "timeframe",
                "strategy",
                "initial_cash",
                "fee_rate",
                "slippage_bps",
                "data_provider",
            )
        },
        "summary": summary,
        "parameter_grid": grid,
        "ranked": ranked,
        "best": ranked[0],
        # run artifacts always record where their candles came from; the
        # optimization artifact accepted provenance but silently dropped it
        "provenance": provenance,
        "safety": safety,
    }
    manifest = {
        "optimize_id": optimize_id,
        "artifact_kind": "local_backtest_optimization_v1",
        "generated_at": now.isoformat(),
        "evaluated_count": summary["evaluated_count"],
        "files": ["optimize.json", "rows.csv", "report.md", "manifest.json"],
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifact_dir / "optimize.json", payload)
    _write_optimize_rows(artifact_dir / "rows.csv", ranked)
    _write_optimize_report(artifact_dir / "report.md", summary, ranked, safety)
    _write_json(artifact_dir / "manifest.json", manifest)
    return payload


def _write_optimize_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = (
        "rank",
        "fast_window",
        "slow_window",
        "return_pct",
        "final_equity",
        "max_drawdown_pct",
        "trade_count",
        "signal_count",
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row.get(column, "") for column in columns])


def _write_optimize_report(
    path: Path,
    summary: dict[str, Any],
    ranked: list[dict[str, Any]],
    safety: dict[str, Any],
) -> None:
    lines = [
        f"# Backtest Optimization — {summary['strategy_label']} "
        f"({summary['symbol']} {summary['timeframe']})",
        "",
        f"- Objective: {summary['objective_direction']} {summary['objective']}",
        f"- Evaluated combinations: {summary['evaluated_count']}",
        f"- Best parameters: {summary['best_parameters']}",
        f"- Best return: {summary['best_return_pct']}% "
        f"(final equity {summary['best_final_equity']})",
        f"- Lookahead guard: {summary['lookahead_guard']}",
        "",
        "## Top results",
        "",
        "| rank | fast | slow | return_pct | max_drawdown_pct | trades |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in ranked[:10]:
        lines.append(
            f"| {row['rank']} | {row['fast_window']} | {row['slow_window']} "
            f"| {row['return_pct']} | {row['max_drawdown_pct']} | {row['trade_count']} |"
        )
    lines += ["", f"Safety: {safety}", ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_backtest_comparison_packet(
    artifact_root: Path,
    *,
    max_runs: int = 4,
) -> dict[str, Any]:
    run_rows, skipped_count = _latest_backtest_run_rows(
        artifact_root,
        max_runs=_bounded_comparison_run_count(max_runs),
    )
    if len(run_rows) < 2:
        raise BacktestError("At least two local backtest runs are required for comparison")
    ranked_rows = sorted(
        run_rows,
        key=lambda row: Decimal(str(row["return_pct"] or "0")),
        reverse=True,
    )
    best = ranked_rows[0]
    worst = ranked_rows[-1]
    comparison_id = f"btcmp-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    artifact_dir = artifact_root / "artifacts" / "backtests" / "comparisons" / comparison_id
    resolved = artifact_dir.resolve()
    if not resolved.is_relative_to(artifact_root.resolve()):
        raise BacktestError("Refusing to write outside repository")
    artifacts = {
        "comparison": f"artifacts/backtests/comparisons/{comparison_id}/comparison.json",
        "rows": f"artifacts/backtests/comparisons/{comparison_id}/rows.csv",
        "manifest": f"artifacts/backtests/comparisons/{comparison_id}/manifest.json",
        "report": f"artifacts/backtests/comparisons/{comparison_id}/report.md",
    }
    summary = {
        "comparison_id": comparison_id,
        "run_count": len(run_rows),
        "skipped_count": skipped_count,
        "best_run_id": str(best["run_id"]),
        "best_strategy": str(best["strategy"]),
        "best_strategy_label": str(best["strategy_label"]),
        "best_return_pct": str(best["return_pct"]),
        "worst_run_id": str(worst["run_id"]),
        "worst_return_pct": str(worst["return_pct"]),
        "return_spread_pct": _decimal_difference(best["return_pct"], worst["return_pct"]),
        "max_drawdown_worst_pct": str(
            max(Decimal(str(row["max_drawdown_pct"] or "0")) for row in run_rows).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        ),
        "strategies": ",".join(sorted({str(row["strategy"]) for row in run_rows})),
        "artifact_contract": "local_backtest_comparison_packet_v1",
        "comparison_mode": "latest_local_backtest_runs",
    }
    safety = {
        "local_only": True,
        "reads_existing_backtest_artifacts": True,
        "writes_comparison_artifacts": True,
        "optimization": False,
        "live_orders": False,
        "broker_routing": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives": False,
    }
    manifest = {
        "comparison_id": comparison_id,
        "artifact_contract": "local_backtest_comparison_packet_v1",
        "source_run_ids": [row["run_id"] for row in run_rows],
        "source_manifest_paths": [row["manifest_path"] for row in run_rows],
        "row_count": len(run_rows),
        "skipped_count": skipped_count,
        "created_at": _utc_now(),
        "artifact_files": artifacts,
        "safety": safety,
    }
    payload = {
        "comparison_id": comparison_id,
        "artifact_dir": artifact_dir.relative_to(artifact_root).as_posix(),
        "summary": summary,
        "rows": run_rows,
        "ranked_rows": ranked_rows,
        "artifacts": artifacts,
        "manifest": manifest,
        "safety": safety,
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifact_dir / "comparison.json", payload)
    _write_comparison_rows(artifact_dir / "rows.csv", run_rows)
    _write_json(artifact_dir / "manifest.json", manifest)
    _write_comparison_report(artifact_dir / "report.md", summary, ranked_rows, safety)
    return payload


def backtest_run_index_payload(
    artifact_root: Path,
    *,
    max_runs: int = DEFAULT_BACKTEST_RUN_INDEX_LIMIT,
) -> dict[str, Any]:
    """Return known local Backtest run metadata for agent selection."""

    bounded_max_runs = _bounded_run_index_count(max_runs)
    run_rows, skipped_count = _latest_backtest_run_rows(
        artifact_root,
        max_runs=bounded_max_runs,
    )
    comparison_ready = len(run_rows) >= 2
    latest = run_rows[0] if run_rows else {}
    return {
        "generated_at": _utc_now(),
        "mode": "local_backtest_run_index",
        "summary": {
            "run_count": len(run_rows),
            "skipped_count": skipped_count,
            "max_returned_runs": bounded_max_runs,
            "comparison_ready": comparison_ready,
            "comparison_candidate_count": min(len(run_rows), 4),
            "latest_run_id": str(latest.get("run_id") or ""),
            "latest_manifest_path": str(latest.get("manifest_path") or ""),
            "strategy_count": len({str(row.get("strategy") or "") for row in run_rows}),
            "strategies": ",".join(
                sorted({str(row.get("strategy") or "") for row in run_rows if row.get("strategy")})
            ),
        },
        "runs": run_rows,
        "recommended_actions": [
            {
                "action_id": "backtest_comparison_packet",
                "endpoint": "/api/backtest/comparison-packet",
                "method": "POST",
                "ready": comparison_ready,
                "reason": (
                    "At least two indexed local runs are available for comparison."
                    if comparison_ready
                    else "Run at least two local closed-candle backtests before comparison."
                ),
            }
        ],
        "safety": {
            "local_only": True,
            "known_backtest_metadata_read": True,
            "artifact_content_indexing": False,
            "writes_local_artifacts": False,
            "optimization": False,
            "live_orders": False,
            "broker_routing": False,
            "real_balance": False,
            "margin": False,
            "leverage": False,
            "short": False,
            "derivatives": False,
        },
    }


def backtest_artifact_health_payload(
    artifact_root: Path,
    *,
    max_runs: int = DEFAULT_BACKTEST_RUN_INDEX_LIMIT,
) -> dict[str, Any]:
    """Return metadata-only health for local closed-candle Backtest artifacts."""

    bounded_max_runs = _bounded_run_index_count(max_runs)
    rows, skipped_count = _latest_backtest_artifact_health_rows(
        artifact_root,
        max_runs=bounded_max_runs,
    )
    complete_count = sum(1 for row in rows if row["health_state"] == "complete")
    partial_count = sum(1 for row in rows if row["health_state"] != "complete")
    missing_artifact_count = sum(int(row["missing_count"]) for row in rows)
    supervision_ready_count = sum(1 for row in rows if row["supervision_ready"])
    latest = rows[0] if rows else {}
    return {
        "generated_at": _utc_now(),
        "mode": "metadata_only_backtest_artifact_health",
        "summary": {
            "run_count": len(rows),
            "complete_count": complete_count,
            "partial_count": partial_count,
            "missing_artifact_count": missing_artifact_count,
            "supervision_ready_count": supervision_ready_count,
            "expected_artifact_count": len(BACKTEST_RUN_HEALTH_EXPECTED_FILES),
            "skipped_count": skipped_count,
            "max_returned_runs": bounded_max_runs,
            "latest_run_id": str(latest.get("run_id") or ""),
            "destructive_action_count": 0,
        },
        "runs": rows,
        "recommended_actions": [
            {
                "action_id": "backtest_run_index",
                "endpoint": "/api/backtest/runs",
                "method": "GET",
                "ready": complete_count > 0,
                "reason": (
                    "At least one complete local Backtest run can be indexed."
                    if complete_count > 0
                    else "Run a local closed-candle Backtest before using the run index."
                ),
            },
            {
                "action_id": "backtest_run_closed_candle",
                "endpoint": "/api/backtest/run",
                "method": "POST",
                "ready": True,
                "reason": "Create a new local run; existing run directories are not repaired.",
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
            "optimization": False,
            "live_orders": False,
            "broker_routing": False,
            "real_balance": False,
            "margin": False,
            "leverage": False,
            "short": False,
            "derivatives": False,
        },
    }


def backtest_data_readiness_payload(
    provider_cache: dict[str, Any] | None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return closed-candle dataset readiness before an agent runs a Backtest."""

    selected_config = normalize_backtest_config({**DEFAULT_BACKTEST_CONFIG, **(config or {})})
    datasets = [
        _backtest_data_readiness_row(
            provider_cache,
            symbol=symbol,
            timeframe=timeframe,
            selected=(
                symbol == selected_config["symbol"]
                and timeframe == selected_config["timeframe"]
            ),
        )
        for symbol in BACKTEST_SYMBOLS
        for timeframe in BACKTEST_TIMEFRAMES
    ]
    selected = next((row for row in datasets if row["selected"]), datasets[0])
    public_ready_count = sum(
        1
        for row in datasets
        if row["data_mode"] == "public_closed_candle_cache" and row["run_ready"]
    )
    fallback_ready_count = sum(
        1
        for row in datasets
        if row["data_mode"] == "deterministic_local_fallback" and row["run_ready"]
    )
    return {
        "generated_at": _utc_now(),
        "mode": "local_backtest_data_readiness",
        "contract": "backtest_data_readiness_v1",
        "selected_config": {
            "symbol": selected_config["symbol"],
            "timeframe": selected_config["timeframe"],
            "strategy": selected_config["strategy"],
            "fast_window": selected_config["fast_window"],
            "slow_window": selected_config["slow_window"],
            "data_provider": selected_config["data_provider"],
        },
        "summary": {
            "dataset_count": len(datasets),
            "symbol_count": len(BACKTEST_SYMBOLS),
            "timeframe_count": len(BACKTEST_TIMEFRAMES),
            "public_cache_ready_count": public_ready_count,
            "deterministic_fallback_ready_count": fallback_ready_count,
            "selected_symbol": selected["symbol"],
            "selected_timeframe": selected["timeframe"],
            "selected_data_mode": selected["data_mode"],
            "selected_run_ready": selected["run_ready"],
            "selected_closed_candle_count": selected["effective_closed_candle_count"],
            "selected_source": selected["source"],
            "selected_state": selected["state"],
            "selected_cache_path": selected["cache_path"],
            "deterministic_fallback_required": selected[
                "deterministic_fallback_required"
            ],
        },
        "datasets": datasets,
        "recommended_actions": [
            {
                "action_id": "backtest_run_closed_candle",
                "endpoint": "/api/backtest/run",
                "method": "POST",
                "ready": bool(selected["run_ready"]),
                "reason": (
                    "Selected closed-candle dataset is ready for the local Backtest runner."
                    if selected["run_ready"]
                    else "Selected closed-candle dataset is not ready."
                ),
            },
            {
                "action_id": "markets_refresh_public",
                "endpoint": "/api/markets/refresh",
                "method": "POST",
                "ready": bool(selected["deterministic_fallback_required"]),
                "reason": (
                    "Refresh public crypto cache to replace deterministic fallback when network access is acceptable."
                    if selected["deterministic_fallback_required"]
                    else "Public closed-candle cache is already available for the selected dataset."
                ),
            },
        ],
        "safety": {
            "local_only": True,
            "read_only": True,
            "metadata_only": True,
            "writes_local_artifacts": False,
            "provider_refresh_performed": False,
            "secret_values_returned": False,
            "live_orders": False,
            "broker_routing": False,
            "real_balance": False,
            "margin": False,
            "leverage": False,
            "short": False,
            "derivatives": False,
        },
    }


def normalize_backtest_config(config: dict[str, Any]) -> dict[str, Any]:
    payload = {**DEFAULT_BACKTEST_CONFIG, **config}
    symbol = "".join(ch for ch in str(payload["symbol"]).upper() if ch.isalnum())
    if symbol not in BACKTEST_SYMBOLS:
        raise BacktestError("Unsupported backtest symbol")
    timeframe = str(payload["timeframe"])
    if timeframe not in BACKTEST_TIMEFRAMES:
        raise BacktestError("Backtesting currently supports 15m closed candles only")
    strategy = str(payload.get("strategy") or "sma_cross")
    if strategy not in STRATEGY_IDS:
        raise BacktestError("Unsupported backtest strategy")
    parameters = normalize_strategy_parameters(strategy, payload)
    initial_cash = _bounded_decimal(
        payload["initial_cash"],
        label="Initial cash",
        minimum=Decimal("0.01"),
        maximum=Decimal("1000000000"),
        inclusive_minimum=True,
    )
    fee_rate = _bounded_decimal(
        payload["fee_rate"],
        label="Fee rate",
        minimum=Decimal("0"),
        maximum=Decimal("0.1"),
        inclusive_minimum=True,
    )
    slippage_bps = _bounded_decimal(
        payload["slippage_bps"],
        label="Slippage bps",
        minimum=Decimal("0"),
        maximum=Decimal("1000"),
        inclusive_minimum=True,
    )
    normalized = {
        "symbol": symbol,
        "timeframe": timeframe,
        "strategy": strategy,
        "fast_window": parameters["fast_window"],
        "slow_window": parameters["slow_window"],
        "initial_cash": _money(initial_cash),
        "fee_rate": str(fee_rate),
        "slippage_bps": str(slippage_bps),
        "decision_rule": "Signals use candle N close; fills execute at candle N+1 open.",
        "data_provider": BACKTEST_PROVIDER,
    }
    if isinstance(payload.get("research_lineage"), dict):
        try:
            normalized["research_lineage"] = normalize_research_lineage(
                payload["research_lineage"]
            )
        except ResearchLineageError as exc:
            raise BacktestError(str(exc)) from exc
    return normalized


def _backtest_data_readiness_row(
    provider_cache: dict[str, Any] | None,
    *,
    symbol: str,
    timeframe: str,
    selected: bool,
) -> dict[str, Any]:
    snapshot = backtest_data_snapshot(provider_cache, symbol=symbol, timeframe=timeframe)
    provenance = snapshot["provenance"]
    closed_candle_count = int(provenance.get("closed_candle_count") or 0)
    fallback_candle_count = 0
    fallback_candles: list[dict[str, str]] = []
    deterministic_fallback_required = bool(provenance.get("deterministic_fallback"))
    if deterministic_fallback_required:
        fallback_candles = generate_closed_candles(symbol)
        fallback_candle_count = len(fallback_candles)
    effective_closed_candle_count = closed_candle_count or fallback_candle_count
    run_ready = effective_closed_candle_count >= 10
    data_mode = (
        "deterministic_local_fallback"
        if deterministic_fallback_required
        else "public_closed_candle_cache"
    )
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "selected": selected,
        "data_mode": data_mode,
        "run_ready": run_ready,
        "source": str(provenance.get("source") or ""),
        "state": str(provenance.get("state") or ""),
        "provider": str(provenance.get("provider") or ""),
        "provider_id": str(provenance.get("provider_id") or ""),
        "cache_path": str(provenance.get("cache_path") or ""),
        "cache_snapshot_hash": str(provenance.get("cache_snapshot_hash") or ""),
        "data_hash": str(
            provenance.get("data_hash")
            or (_hash_json({"candles": fallback_candles}) if fallback_candles else "")
        ),
        "retrieved_at": str(provenance.get("retrieved_at") or ""),
        "source_first_opened_at": str(
            provenance.get("source_first_opened_at")
            or (fallback_candles[0]["opened_at"] if fallback_candles else "")
        ),
        "source_last_closed_at": str(
            provenance.get("source_last_closed_at")
            or (fallback_candles[-1]["closed_at"] if fallback_candles else "")
        ),
        "closed_candle_count": closed_candle_count,
        "fallback_candle_count": fallback_candle_count,
        "effective_closed_candle_count": effective_closed_candle_count,
        "deterministic_fallback_required": deterministic_fallback_required,
        "fallback_reason": str(provenance.get("fallback_reason") or ""),
        "auth_mode": str(provenance.get("auth_mode") or ""),
        "safety_class": str(provenance.get("safety_class") or ""),
        "source_contract": "closed_candles_only",
        "lookahead_guard": "signals_on_close_fills_next_open",
        "same_candle_fills": False,
        "recommended_next": (
            "run_local_backtest"
            if run_ready and not deterministic_fallback_required
            else "refresh_public_crypto_or_accept_local_fallback"
            if run_ready
            else "refresh_public_crypto_cache"
        ),
    }


def _normalized_config_and_candles(
    config: dict[str, Any],
    provider_cache: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, Any]]:
    normalized = normalize_backtest_config(config)
    data_snapshot = backtest_data_snapshot(
        provider_cache,
        symbol=normalized["symbol"],
        timeframe=normalized["timeframe"],
    )
    candles = data_snapshot["candles"]
    provenance = data_snapshot["provenance"]
    if not provenance["deterministic_fallback"]:
        normalized = {
            **normalized,
            "data_provider": PUBLIC_BACKTEST_PROVIDER,
            "data_source": provenance["source"],
            "data_state": provenance["state"],
            "data_retrieved_at": provenance["retrieved_at"],
            "data_cache_hash": provenance["cache_snapshot_hash"],
        }
    else:
        candles = generate_closed_candles(normalized["symbol"])
        provenance = deterministic_data_provenance(
            normalized["symbol"],
            normalized["timeframe"],
            candles,
            reason=provenance["fallback_reason"],
        )
        normalized = {
            **normalized,
            "data_source": provenance["source"],
            "data_state": provenance["state"],
            "data_retrieved_at": provenance["retrieved_at"],
            "data_cache_hash": provenance["cache_snapshot_hash"],
        }
    return normalized, candles, provenance


def run_strategy(
    config: dict[str, Any],
    candles: list[dict[str, str]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    strategy = str(config.get("strategy") or "sma_cross")
    if strategy == "sma_cross":
        return run_sma_cross(config, candles, provenance)
    if strategy == "channel_breakout":
        return run_channel_breakout(config, candles, provenance)
    if strategy == "sma_mean_reversion":
        return run_sma_mean_reversion(config, candles, provenance)
    if strategy == "volatility_reversion":
        return run_volatility_reversion(config, candles, provenance)
    if strategy == "momentum_continuation":
        return run_momentum_continuation(config, candles, provenance)
    if strategy == "rsi_reversion":
        return run_rsi_reversion(config, candles, provenance)
    raise BacktestError("Unsupported backtest strategy")


def generate_closed_candles(symbol: str) -> list[dict[str, str]]:
    base = Decimal("67000") if symbol == "BTCUSDT" else Decimal("3500")
    if symbol == "SOLUSDT":
        base = Decimal("150")
    start = datetime(2026, 1, 1, tzinfo=UTC)
    candles: list[dict[str, str]] = []
    close = base
    for index in range(40):
        drift = Decimal(index % 9 - 3) * Decimal("12")
        if index > 18:
            drift += Decimal("45")
        open_price = close
        close = open_price + drift
        high = max(open_price, close) + Decimal("20")
        low = min(open_price, close) - Decimal("20")
        opened_at = start + timedelta(minutes=15 * index)
        candles.append(
            {
                "opened_at": opened_at.isoformat(timespec="seconds"),
                "closed_at": (opened_at + timedelta(minutes=15)).isoformat(timespec="seconds"),
                "open": _money(open_price),
                "high": _money(high),
                "low": _money(low),
                "close": _money(close),
                "volume": str(Decimal("10") + Decimal(index)),
                "closed": True,
            }
        )
    return candles


def candles_from_provider_cache(
    provider_cache: dict[str, Any] | None,
    *,
    symbol: str,
    timeframe: str,
) -> list[dict[str, str]]:
    return backtest_data_snapshot(provider_cache, symbol=symbol, timeframe=timeframe)["candles"]


def backtest_data_snapshot(
    provider_cache: dict[str, Any] | None,
    *,
    symbol: str,
    timeframe: str,
) -> dict[str, Any]:
    if not isinstance(provider_cache, dict):
        return {
            "candles": [],
            "provenance": unavailable_data_provenance(
                symbol, timeframe, "No public closed-candle cache."
            ),
        }
    detail = crypto_detail_payload(provider_cache, symbol=symbol, interval=timeframe)
    status = detail["status"]
    provider = detail["provider"]
    candles = detail["candles"]
    if status.get("source") not in {"binance_public", "kraken_public", "coinbase_public"}:
        return {
            "candles": [],
            "provenance": unavailable_data_provenance(
                symbol, timeframe, "No public provider source."
            ),
        }

    normalized = []
    for candle in candles:
        if not isinstance(candle, dict) or candle.get("closed") is not True:
            continue
        normalized.append(
            {
                "opened_at": str(candle.get("opened_at", "")),
                "closed_at": str(candle.get("closed_at", "")),
                "open": str(candle.get("open", "")),
                "high": str(candle.get("high", "")),
                "low": str(candle.get("low", "")),
                "close": str(candle.get("close", "")),
                "volume": str(candle.get("volume", "")),
                "closed": True,
            }
        )
    if len(normalized) < 10:
        return {
            "candles": [],
            "provenance": unavailable_data_provenance(
                symbol, timeframe, "Fewer than 10 closed public candles."
            ),
        }
    return {
        "candles": normalized,
        "provenance": {
            "provider": PUBLIC_BACKTEST_PROVIDER,
            "source": str(status.get("source") or ""),
            "state": str(status.get("state") or ""),
            "provider_id": str(status.get("provider_id") or provider.get("provider_id") or ""),
            "symbol": symbol,
            "timeframe": timeframe,
            "cache_path": str(
                provider.get("cache_path") or f"market_data/crypto/{symbol}/{timeframe}.json"
            ),
            "cache_snapshot_hash": _hash_json(provider_cache),
            "data_hash": _hash_json({"candles": normalized}),
            "retrieved_at": str(status.get("last_update") or provider.get("retrieved_at") or ""),
            "source_first_opened_at": normalized[0]["opened_at"],
            "source_last_closed_at": normalized[-1]["closed_at"],
            "closed_candle_count": len(normalized),
            "deterministic_fallback": False,
            "fallback_reason": "",
            "auth_mode": str(provider.get("auth_mode") or "no-key"),
            "safety_class": str(provider.get("safety_class") or "public_read_only_market_data"),
        },
    }


def walk_forward_windows(
    candles: list[dict[str, str]],
    config: dict[str, Any],
    fold_count: int,
) -> list[dict[str, Any]]:
    if any(candle.get("closed") is not True for candle in candles):
        raise BacktestError("Walk-forward requires closed candles")
    minimum_train = max(int(config["slow_window"]) * 2, 10)
    minimum_test = max(int(config["slow_window"]) + 3, 8)
    available_for_tests = len(candles) - minimum_train
    if available_for_tests < minimum_test * fold_count:
        raise BacktestError("Not enough closed candles for walk-forward folds")
    test_size = available_for_tests // fold_count
    windows = []
    for fold_index in range(fold_count):
        test_start = minimum_train + fold_index * test_size
        test_end = len(candles) if fold_index == fold_count - 1 else test_start + test_size
        train_candles = candles[:test_start]
        test_candles = candles[test_start:test_end]
        if len(test_candles) < minimum_test:
            raise BacktestError("Not enough closed candles for walk-forward folds")
        windows.append(
            {
                "train_candle_count": len(train_candles),
                "test_candle_count": len(test_candles),
                "train_first_opened_at": train_candles[0]["opened_at"],
                "train_last_closed_at": train_candles[-1]["closed_at"],
                "test_first_opened_at": test_candles[0]["opened_at"],
                "test_last_closed_at": test_candles[-1]["closed_at"],
                "test_candles": test_candles,
            }
        )
    return windows


def unavailable_data_provenance(symbol: str, timeframe: str, reason: str) -> dict[str, Any]:
    return {
        "provider": BACKTEST_PROVIDER,
        "source": "deterministic_local_closed_candle",
        "state": "offline_fallback",
        "provider_id": "local_deterministic_candle_generator",
        "symbol": symbol,
        "timeframe": timeframe,
        "cache_path": "",
        "cache_snapshot_hash": "",
        "data_hash": "",
        "retrieved_at": "generated locally",
        "source_first_opened_at": "",
        "source_last_closed_at": "",
        "closed_candle_count": 0,
        "deterministic_fallback": True,
        "fallback_reason": reason,
        "auth_mode": "none",
        "safety_class": "test_offline_fallback",
    }


def deterministic_data_provenance(
    symbol: str,
    timeframe: str,
    candles: list[dict[str, str]],
    *,
    reason: str,
) -> dict[str, Any]:
    provenance = unavailable_data_provenance(symbol, timeframe, reason)
    return {
        **provenance,
        "data_hash": _hash_json({"candles": candles}),
        "source_first_opened_at": candles[0]["opened_at"] if candles else "",
        "source_last_closed_at": candles[-1]["closed_at"] if candles else "",
        "closed_candle_count": len(candles),
    }


def run_sma_cross(
    config: dict[str, Any],
    candles: list[dict[str, str]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def signal_fn(index: int, position: Decimal) -> str | None:
        fast_window = config["fast_window"]
        slow_window = config["slow_window"]
        if index + 1 < slow_window or index + 1 >= len(candles):
            return None
        closes = [Decimal(item["close"]) for item in candles[: index + 1]]
        fast = sum(closes[-fast_window:]) / Decimal(fast_window)
        slow = sum(closes[-slow_window:]) / Decimal(slow_window)
        if fast > slow and position == 0:
            return "BUY"
        if fast < slow and position > 0:
            return "SELL"
        return None

    def indicator_fn(index: int) -> dict[str, str]:
        fast_window = config["fast_window"]
        slow_window = config["slow_window"]
        closes = [Decimal(item["close"]) for item in candles[: index + 1]]
        fast = _rolling_average(closes, fast_window)
        slow = _rolling_average(closes, slow_window)
        return {
            "fast_sma": _money(fast) if fast is not None else "",
            "slow_sma": _money(slow) if slow is not None else "",
            "spread_pct": _percent((fast / slow) - Decimal("1"))
            if fast is not None and slow not in {None, Decimal("0")}
            else "",
        }

    return _run_long_flat_strategy(config, candles, provenance, signal_fn, indicator_fn)


def run_channel_breakout(
    config: dict[str, Any],
    candles: list[dict[str, str]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def signal_fn(index: int, position: Decimal) -> str | None:
        exit_window = config["fast_window"]
        breakout_window = config["slow_window"]
        if index < breakout_window or index + 1 >= len(candles):
            return None
        close_price = Decimal(candles[index]["close"])
        prior_channel = candles[index - breakout_window : index]
        exit_channel = candles[index - exit_window : index]
        prior_high = max(Decimal(item["high"]) for item in prior_channel)
        exit_low = min(Decimal(item["low"]) for item in exit_channel)
        if close_price > prior_high and position == 0:
            return "BUY"
        if close_price < exit_low and position > 0:
            return "SELL"
        return None

    def indicator_fn(index: int) -> dict[str, str]:
        exit_window = config["fast_window"]
        breakout_window = config["slow_window"]
        if index < breakout_window:
            return {"prior_high": "", "exit_low": "", "breakout_distance_pct": ""}
        close_price = Decimal(candles[index]["close"])
        prior_channel = candles[index - breakout_window : index]
        exit_channel = candles[index - exit_window : index]
        prior_high = max(Decimal(item["high"]) for item in prior_channel)
        exit_low = min(Decimal(item["low"]) for item in exit_channel)
        return {
            "prior_high": _money(prior_high),
            "exit_low": _money(exit_low),
            "breakout_distance_pct": _percent((close_price / prior_high) - Decimal("1"))
            if prior_high
            else "",
        }

    return _run_long_flat_strategy(config, candles, provenance, signal_fn, indicator_fn)


def run_sma_mean_reversion(
    config: dict[str, Any],
    candles: list[dict[str, str]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def signal_fn(index: int, position: Decimal) -> str | None:
        exit_window = config["fast_window"]
        mean_window = config["slow_window"]
        if index + 1 < mean_window or index + 1 >= len(candles):
            return None
        closes = [Decimal(item["close"]) for item in candles[: index + 1]]
        close_price = Decimal(candles[index]["close"])
        exit_sma = sum(closes[-exit_window:]) / Decimal(exit_window)
        mean_sma = sum(closes[-mean_window:]) / Decimal(mean_window)
        if close_price < mean_sma and position == 0:
            return "BUY"
        if close_price > exit_sma and position > 0:
            return "SELL"
        return None

    def indicator_fn(index: int) -> dict[str, str]:
        exit_window = config["fast_window"]
        mean_window = config["slow_window"]
        closes = [Decimal(item["close"]) for item in candles[: index + 1]]
        exit_sma = _rolling_average(closes, exit_window)
        mean_sma = _rolling_average(closes, mean_window)
        close_price = Decimal(candles[index]["close"])
        return {
            "exit_sma": _money(exit_sma) if exit_sma is not None else "",
            "mean_sma": _money(mean_sma) if mean_sma is not None else "",
            "mean_distance_pct": _percent((close_price / mean_sma) - Decimal("1"))
            if mean_sma is not None and mean_sma != Decimal("0")
            else "",
        }

    return _run_long_flat_strategy(config, candles, provenance, signal_fn, indicator_fn)


def run_volatility_reversion(
    config: dict[str, Any],
    candles: list[dict[str, str]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def signal_fn(index: int, position: Decimal) -> str | None:
        exit_window = config["fast_window"]
        band_window = config["slow_window"]
        if index + 1 < band_window or index + 1 >= len(candles):
            return None
        closes = [Decimal(item["close"]) for item in candles[: index + 1]]
        close_price = Decimal(candles[index]["close"])
        exit_sma = sum(closes[-exit_window:]) / Decimal(exit_window)
        band_mid = sum(closes[-band_window:]) / Decimal(band_window)
        band_std = _rolling_stddev(closes, band_window)
        if band_std is None:
            return None
        lower_band = band_mid - band_std
        if close_price < lower_band and position == 0:
            return "BUY"
        if close_price > exit_sma and position > 0:
            return "SELL"
        return None

    def indicator_fn(index: int) -> dict[str, str]:
        exit_window = config["fast_window"]
        band_window = config["slow_window"]
        closes = [Decimal(item["close"]) for item in candles[: index + 1]]
        close_price = Decimal(candles[index]["close"])
        exit_sma = _rolling_average(closes, exit_window)
        band_mid = _rolling_average(closes, band_window)
        band_std = _rolling_stddev(closes, band_window)
        lower_band = (
            band_mid - band_std
            if band_mid is not None and band_std is not None
            else None
        )
        upper_band = (
            band_mid + band_std
            if band_mid is not None and band_std is not None
            else None
        )
        return {
            "exit_sma": _money(exit_sma) if exit_sma is not None else "",
            "band_mid": _money(band_mid) if band_mid is not None else "",
            "lower_band": _money(lower_band) if lower_band is not None else "",
            "upper_band": _money(upper_band) if upper_band is not None else "",
            "lower_band_distance_pct": _percent((close_price / lower_band) - Decimal("1"))
            if lower_band is not None and lower_band != Decimal("0")
            else "",
        }

    return _run_long_flat_strategy(config, candles, provenance, signal_fn, indicator_fn)


def run_momentum_continuation(
    config: dict[str, Any],
    candles: list[dict[str, str]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def signal_fn(index: int, position: Decimal) -> str | None:
        exit_window = config["fast_window"]
        momentum_window = config["slow_window"]
        if index < momentum_window or index + 1 >= len(candles):
            return None
        closes = [Decimal(item["close"]) for item in candles[: index + 1]]
        close_price = Decimal(candles[index]["close"])
        exit_sma = sum(closes[-exit_window:]) / Decimal(exit_window)
        momentum_reference = Decimal(candles[index - momentum_window]["close"])
        if close_price > momentum_reference and close_price > exit_sma and position == 0:
            return "BUY"
        if close_price < exit_sma and position > 0:
            return "SELL"
        return None

    def indicator_fn(index: int) -> dict[str, str]:
        exit_window = config["fast_window"]
        momentum_window = config["slow_window"]
        closes = [Decimal(item["close"]) for item in candles[: index + 1]]
        close_price = Decimal(candles[index]["close"])
        exit_sma = _rolling_average(closes, exit_window)
        momentum_reference = (
            Decimal(candles[index - momentum_window]["close"])
            if index >= momentum_window
            else None
        )
        return {
            "exit_sma": _money(exit_sma) if exit_sma is not None else "",
            "momentum_reference": _money(momentum_reference)
            if momentum_reference is not None
            else "",
            "momentum_return_pct": _percent((close_price / momentum_reference) - Decimal("1"))
            if momentum_reference is not None and momentum_reference != Decimal("0")
            else "",
        }

    return _run_long_flat_strategy(config, candles, provenance, signal_fn, indicator_fn)


def run_rsi_reversion(
    config: dict[str, Any],
    candles: list[dict[str, str]],
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    def signal_fn(index: int, position: Decimal) -> str | None:
        exit_window = config["fast_window"]
        rsi_window = config["slow_window"]
        if index + 1 <= rsi_window or index + 1 >= len(candles):
            return None
        closes = [Decimal(item["close"]) for item in candles[: index + 1]]
        close_price = Decimal(candles[index]["close"])
        exit_sma = sum(closes[-exit_window:]) / Decimal(exit_window)
        rsi = _rolling_rsi(closes, rsi_window)
        if rsi is None:
            return None
        if rsi < Decimal("40") and position == 0:
            return "BUY"
        if (rsi > Decimal("55") or close_price > exit_sma) and position > 0:
            return "SELL"
        return None

    def indicator_fn(index: int) -> dict[str, str]:
        exit_window = config["fast_window"]
        rsi_window = config["slow_window"]
        closes = [Decimal(item["close"]) for item in candles[: index + 1]]
        exit_sma = _rolling_average(closes, exit_window)
        rsi = _rolling_rsi(closes, rsi_window)
        rsi_distance = rsi - Decimal("40") if rsi is not None else None
        return {
            "exit_sma": _money(exit_sma) if exit_sma is not None else "",
            "rsi": _money(rsi) if rsi is not None else "",
            "rsi_entry_threshold": "40.00",
            "rsi_exit_threshold": "55.00",
            "rsi_distance": _money(rsi_distance) if rsi_distance is not None else "",
        }

    return _run_long_flat_strategy(config, candles, provenance, signal_fn, indicator_fn)


def _run_long_flat_strategy(
    config: dict[str, Any],
    candles: list[dict[str, str]],
    provenance: dict[str, Any] | None,
    signal_fn: Callable[[int, Decimal], str | None],
    indicator_fn: Callable[[int], dict[str, str]],
) -> dict[str, Any]:
    if any(candle.get("closed") is not True for candle in candles):
        raise BacktestError("Backtest requires closed candles")
    cash = Decimal(config["initial_cash"])
    fee_rate = Decimal(config["fee_rate"])
    slippage = Decimal(config["slippage_bps"]) / Decimal("10000")
    position = Decimal("0")
    trades: list[dict[str, str]] = []
    signal_rows: list[dict[str, str]] = []
    indicator_rows: list[dict[str, str]] = []
    equity_curve: list[dict[str, str]] = []
    pending_signal: str | None = None

    for index, candle in enumerate(candles):
        open_price = Decimal(candle["open"])
        close_price = Decimal(candle["close"])
        if pending_signal:
            fill_side = pending_signal
            fill_price = open_price * (
                Decimal("1") + slippage if fill_side == "BUY" else Decimal("1") - slippage
            )
            if fill_side == "BUY" and position == 0:
                quantity = (cash / (fill_price * (Decimal("1") + fee_rate))).quantize(
                    Decimal("0.00000001"),
                    rounding=ROUND_HALF_UP,
                )
                notional = quantity * fill_price
                fee = notional * fee_rate
                cash -= notional + fee
                position = quantity
                trades.append(
                    _trade(
                        config,
                        index - 1,
                        index,
                        candles[index - 1],
                        candle,
                        fill_side,
                        quantity,
                        fill_price,
                        fee,
                    )
                )
            elif fill_side == "SELL" and position > 0:
                quantity = position
                notional = quantity * fill_price
                fee = notional * fee_rate
                cash += notional - fee
                position = Decimal("0")
                trades.append(
                    _trade(
                        config,
                        index - 1,
                        index,
                        candles[index - 1],
                        candle,
                        fill_side,
                        quantity,
                        fill_price,
                        fee,
                    )
                )
            pending_signal = None

        equity = cash + position * close_price
        equity_curve.append({"closed_at": candle["closed_at"], "equity": _money(equity)})
        indicator_rows.append(
            {
                "closed_at": candle["closed_at"],
                "close": candle["close"],
                **indicator_fn(index),
            }
        )

        signal = signal_fn(index, position)
        if signal in {"BUY", "SELL"} and index + 1 < len(candles):
            signal_rows.append(
                {
                    "symbol": config["symbol"],
                    "strategy": config["strategy"],
                    "side": signal,
                    "signal_candle_index": str(index),
                    "signal_closed_at": candle["closed_at"],
                    "signal_close": candle["close"],
                    "fill_candle_index": str(index + 1),
                    "fill_rule": "next_open",
                    "same_candle_fill": "false",
                }
            )
            pending_signal = signal

    final_equity = cash + position * Decimal(candles[-1]["close"])
    drawdown = _drawdown_curve(equity_curve)
    max_drawdown = max(
        (abs(Decimal(row["drawdown_pct"])) for row in drawdown), default=Decimal("0")
    )
    provenance = provenance or unavailable_data_provenance(
        config["symbol"], config["timeframe"], "No provenance supplied."
    )
    summary = {
        "symbol": config["symbol"],
        "strategy": config["strategy"],
        "strategy_label": _strategy_label(config["strategy"]),
        "timeframe": config["timeframe"],
        "run_state": "complete",
        "initial_cash": config["initial_cash"],
        "final_equity": _money(final_equity),
        "return_pct": _percent((final_equity / Decimal(config["initial_cash"])) - Decimal("1")),
        "trade_count": len(trades),
        "closed_candles": len(candles),
        "lookahead_guard": "signals_on_close_fills_next_open",
        "same_candle_fills": False,
        "data_provider": config.get("data_provider", provenance["provider"]),
        "data_source": provenance["source"],
        "data_state": provenance["state"],
        "data_retrieved_at": provenance["retrieved_at"],
        "cache_snapshot_hash": provenance["cache_snapshot_hash"],
        "source_first_opened_at": provenance["source_first_opened_at"],
        "source_last_closed_at": provenance["source_last_closed_at"],
        "deterministic_fallback": provenance["deterministic_fallback"],
    }
    returns_curve = _returns_curve(equity_curve)
    returns_analysis = _returns_analysis(returns_curve, summary["return_pct"], max_drawdown)
    risk_metrics = _risk_metrics(returns_curve, trades, len(candles), config["timeframe"])
    metrics = {
        "total_return_pct": summary["return_pct"],
        "max_drawdown_pct": _percent(max_drawdown / Decimal("100")),
        "best_period_return_pct": returns_analysis["best_period_return_pct"],
        "worst_period_return_pct": returns_analysis["worst_period_return_pct"],
        **risk_metrics,
        "trade_count": len(trades),
        "signal_count": len(signal_rows),
        "closed_candles": len(candles),
        "gross_fees": _money(sum((Decimal(trade["fee"]) for trade in trades), Decimal("0"))),
        "data_provider": summary["data_provider"],
        "data_source": summary["data_source"],
        "data_state": summary["data_state"],
        "cache_snapshot_hash": summary["cache_snapshot_hash"],
        "strategy": config["strategy"],
    }
    return {
        "summary": summary,
        "metrics": metrics,
        "trades": trades,
        "signals": signal_rows,
        "indicators": indicator_rows,
        "returns_analysis": returns_analysis,
        "returns_curve": returns_curve,
        "equity_curve": equity_curve,
        "drawdown": drawdown,
        "provenance": provenance,
    }


def write_backtest_artifacts(
    artifact_root: Path,
    config: dict[str, Any],
    candles: list[dict[str, str]],
    result: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    run_id = f"bt-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    run_dir = artifact_root / "artifacts" / "backtests" / run_id
    resolved = run_dir.resolve()
    if not resolved.is_relative_to(artifact_root.resolve()):
        raise BacktestError("Refusing to write outside repository")
    artifacts = {
        "config": f"artifacts/backtests/{run_id}/config.json",
        "data_snapshot": f"artifacts/backtests/{run_id}/data_snapshot.json",
        "summary": f"artifacts/backtests/{run_id}/summary.json",
        "trades": f"artifacts/backtests/{run_id}/trades.csv",
        "signals": f"artifacts/backtests/{run_id}/signals.csv",
        "indicators": f"artifacts/backtests/{run_id}/indicators.json",
        "returns_analysis": f"artifacts/backtests/{run_id}/returns_analysis.json",
        "returns_curve": f"artifacts/backtests/{run_id}/returns_curve.csv",
        "provenance": f"artifacts/backtests/{run_id}/provenance.json",
        "report": f"artifacts/backtests/{run_id}/report.md",
        "manifest": f"artifacts/backtests/{run_id}/manifest.json",
    }
    strategy_entry = _strategy_entry(config["strategy"])
    config_hash = _hash_json(_config_hash_payload(config))
    data_hash = _hash_json({"candles": candles})
    research_lineage = _final_backtest_lineage(
        config.get("research_lineage"),
        run_id=run_id,
        config_hash=config_hash,
        data_hash=data_hash,
        manifest_path=artifacts["manifest"],
    )
    saved_config = {**config}
    saved_provenance = {**provenance}
    if research_lineage:
        saved_config["research_lineage"] = research_lineage
        saved_provenance["research_lineage"] = research_lineage
    manifest = {
        "run_id": run_id,
        "engine": f"local_{config['strategy']}_v1",
        "strategy": config["strategy"],
        "strategy_label": _strategy_label(config["strategy"]),
        "strategy_parameter_schema": strategy_entry["parameters"],
        "strategy_constraints": strategy_entry["constraints"],
        "strategy_artifact_contract": strategy_entry["artifact_contract"],
        "provider": config["data_provider"],
        "provider_id": provenance["provider_id"],
        "data_source": provenance["source"],
        "data_state": provenance["state"],
        "data_retrieved_at": provenance["retrieved_at"],
        "cache_path": provenance["cache_path"],
        "cache_snapshot_hash": provenance["cache_snapshot_hash"],
        "source_timestamps": {
            "first_opened_at": provenance["source_first_opened_at"],
            "last_closed_at": provenance["source_last_closed_at"],
            "retrieved_at": provenance["retrieved_at"],
        },
        "deterministic_fallback": provenance["deterministic_fallback"],
        "fallback_reason": provenance["fallback_reason"],
        "closed_candle_count": provenance["closed_candle_count"],
        "config_hash": config_hash,
        "data_hash": data_hash,
        "research_lineage": research_lineage,
        "artifact_files": artifacts,
        "created_at": _utc_now(),
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_dir / "config.json", saved_config)
    _write_json(run_dir / "data_snapshot.json", {"provenance": saved_provenance, "candles": candles})
    _write_json(run_dir / "summary.json", result["summary"])
    _write_json(run_dir / "indicators.json", {"rows": result["indicators"]})
    _write_json(run_dir / "returns_analysis.json", result["returns_analysis"])
    _write_json(run_dir / "provenance.json", saved_provenance)
    _write_json(run_dir / "manifest.json", manifest)
    _write_trades(run_dir / "trades.csv", result["trades"])
    _write_signals(run_dir / "signals.csv", result["signals"])
    _write_returns_curve(run_dir / "returns_curve.csv", result["returns_curve"])
    _write_report(
        run_dir / "report.md",
        result["summary"],
        result["trades"],
        result["returns_analysis"],
        saved_provenance,
        result.get("metrics", {}),
    )
    return {
        "run_id": run_id,
        "artifact_dir": run_dir.relative_to(artifact_root).as_posix(),
        "config": saved_config,
        "summary": result["summary"],
        "metrics": result["metrics"],
        "trades": result["trades"],
        "signals": result["signals"],
        "indicators": result["indicators"],
        "returns_analysis": result["returns_analysis"],
        "returns_curve": result["returns_curve"],
        "equity_curve": result["equity_curve"],
        "drawdown": result["drawdown"],
        "provenance": saved_provenance,
        "manifest": manifest,
        "artifacts": artifacts,
        "research_lineage": research_lineage,
    }


def write_walk_forward_artifacts(
    artifact_root: Path,
    config: dict[str, Any],
    candles: list[dict[str, str]],
    summary: dict[str, Any],
    folds: list[dict[str, Any]],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    run_id = f"wfa-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    run_dir = artifact_root / "artifacts" / "backtests" / run_id
    resolved = run_dir.resolve()
    if not resolved.is_relative_to(artifact_root.resolve()):
        raise BacktestError("Refusing to write outside repository")
    artifacts = {
        "config": f"artifacts/backtests/{run_id}/config.json",
        "data_snapshot": f"artifacts/backtests/{run_id}/data_snapshot.json",
        "walk_forward_summary": f"artifacts/backtests/{run_id}/walk_forward_summary.json",
        "walk_forward_folds": f"artifacts/backtests/{run_id}/walk_forward_folds.csv",
        "walk_forward_folds_json": f"artifacts/backtests/{run_id}/walk_forward_folds.json",
        "provenance": f"artifacts/backtests/{run_id}/provenance.json",
        "report": f"artifacts/backtests/{run_id}/report.md",
        "manifest": f"artifacts/backtests/{run_id}/manifest.json",
    }
    strategy_entry = _strategy_entry(config["strategy"])
    manifest = {
        "run_id": run_id,
        "engine": f"local_{config['strategy']}_walk_forward_v1",
        "strategy": config["strategy"],
        "strategy_label": _strategy_label(config["strategy"]),
        "analysis_mode": "fixed_parameter_walk_forward",
        "train_usage": "metadata_only_no_fit_no_warmup",
        "strategy_parameter_schema": strategy_entry["parameters"],
        "strategy_constraints": strategy_entry["constraints"],
        "strategy_artifact_contract": "local_closed_candle_walk_forward_artifacts_v1",
        "provider": config["data_provider"],
        "provider_id": provenance["provider_id"],
        "data_source": provenance["source"],
        "data_state": provenance["state"],
        "data_retrieved_at": provenance["retrieved_at"],
        "cache_path": provenance["cache_path"],
        "cache_snapshot_hash": provenance["cache_snapshot_hash"],
        "source_timestamps": {
            "first_opened_at": provenance["source_first_opened_at"],
            "last_closed_at": provenance["source_last_closed_at"],
            "retrieved_at": provenance["retrieved_at"],
        },
        "deterministic_fallback": provenance["deterministic_fallback"],
        "fallback_reason": provenance["fallback_reason"],
        "closed_candle_count": provenance["closed_candle_count"],
        "config_hash": _hash_json(config),
        "data_hash": _hash_json({"candles": candles}),
        "artifact_files": artifacts,
        "created_at": _utc_now(),
        "safety": _walk_forward_safety(),
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_dir / "config.json", config)
    _write_json(run_dir / "data_snapshot.json", {"provenance": provenance, "candles": candles})
    _write_json(run_dir / "walk_forward_summary.json", summary)
    _write_json(run_dir / "walk_forward_folds.json", {"rows": folds})
    _write_json(run_dir / "provenance.json", provenance)
    _write_json(run_dir / "manifest.json", manifest)
    _write_walk_forward_folds(run_dir / "walk_forward_folds.csv", folds)
    _write_walk_forward_report(run_dir / "report.md", summary, folds, provenance)
    return {
        "run_id": run_id,
        "artifact_dir": run_dir.relative_to(artifact_root).as_posix(),
        "config": config,
        "summary": summary,
        "folds": folds,
        "provenance": provenance,
        "manifest": manifest,
        "artifacts": artifacts,
        "safety": _walk_forward_safety(),
    }


def _trade(
    config: dict[str, Any],
    signal_index: int,
    fill_index: int,
    signal_candle: dict[str, str],
    fill_candle: dict[str, str],
    side: str,
    quantity: Decimal,
    price: Decimal,
    fee: Decimal,
) -> dict[str, str]:
    return {
        "symbol": config["symbol"],
        "side": side,
        "quantity": _amount(quantity),
        "price": _money(price),
        "fee": _money(fee),
        "signal_candle_index": str(signal_index),
        "fill_candle_index": str(fill_index),
        "signal_closed_at": signal_candle["closed_at"],
        "filled_at": fill_candle["opened_at"],
        "same_candle_fill": str(signal_index == fill_index).lower(),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_trades(path: Path, trades: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "symbol",
            "side",
            "quantity",
            "price",
            "fee",
            "signal_candle_index",
            "fill_candle_index",
            "signal_closed_at",
            "filled_at",
            "same_candle_fill",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trades)


def _write_signals(path: Path, signals: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "symbol",
            "strategy",
            "side",
            "signal_candle_index",
            "signal_closed_at",
            "signal_close",
            "fill_candle_index",
            "fill_rule",
            "same_candle_fill",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(signals)


def _write_returns_curve(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["closed_at", "equity", "period_return_pct"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_walk_forward_folds(path: Path, folds: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "fold_id",
            "fold_index",
            "train_candle_count",
            "test_candle_count",
            "train_first_opened_at",
            "train_last_closed_at",
            "test_first_opened_at",
            "test_last_closed_at",
            "initial_cash",
            "final_equity",
            "return_pct",
            "max_drawdown_pct",
            "best_period_return_pct",
            "worst_period_return_pct",
            "trade_count",
            "signal_count",
            "lookahead_guard",
            "same_candle_fills",
            "data_source",
            "data_state",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(folds)


def _write_comparison_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "run_id",
            "artifact_dir",
            "strategy",
            "strategy_label",
            "symbol",
            "timeframe",
            "final_equity",
            "return_pct",
            "max_drawdown_pct",
            "trade_count",
            "signal_count",
            "data_source",
            "data_state",
            "cache_snapshot_hash",
            "manifest_path",
            "created_at",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _drawdown_curve(equity_curve: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    peak = Decimal(equity_curve[0]["equity"]) if equity_curve else Decimal("0")
    for point in equity_curve:
        equity = Decimal(point["equity"])
        if equity > peak:
            peak = equity
        drawdown = (equity / peak) - Decimal("1") if peak else Decimal("0")
        rows.append(
            {
                "closed_at": point["closed_at"],
                "equity": point["equity"],
                "peak": _money(peak),
                "drawdown_pct": _percent(drawdown),
            }
        )
    return rows


def _write_report(
    path: Path,
    summary: dict[str, Any],
    trades: list[dict[str, str]],
    returns_analysis: dict[str, str],
    provenance: dict[str, Any],
    metrics: dict[str, Any] | None = None,
) -> None:
    metrics = metrics or {}
    lines = [
        "# Backtest Report",
        "",
        f"- Symbol: {summary['symbol']}",
        f"- Strategy: {summary['strategy']}",
        f"- Data source: {provenance['source']} ({provenance['state']})",
        f"- Cache hash: {provenance['cache_snapshot_hash'] or 'none'}",
        f"- Final equity: {summary['final_equity']}",
        f"- Return: {summary['return_pct']}%",
        f"- Best period return: {returns_analysis['best_period_return_pct']}%",
        f"- Worst period return: {returns_analysis['worst_period_return_pct']}%",
        f"- Trades: {len(trades)}",
        f"- Guard: {summary['lookahead_guard']}",
        "",
    ]
    if metrics.get("sharpe_ratio") or metrics.get("round_trip_count"):
        lines += [
            "## Reliability",
            "",
            f"- Sharpe (annualized): {metrics.get('sharpe_ratio') or 'n/a'}",
            f"- Sortino (annualized): {metrics.get('sortino_ratio') or 'n/a'}",
            f"- Win rate: {metrics.get('win_rate_pct') or 'n/a'}%",
            f"- Profit factor: {metrics.get('profit_factor') or 'n/a'}",
            f"- Avg round-trip P&L: {metrics.get('avg_trade_pnl') or 'n/a'}",
            f"- Round trips: {metrics.get('round_trip_count') or '0'}",
            f"- Time in market: {metrics.get('exposure_pct') or 'n/a'}%",
            f"- Overfit check: {metrics.get('overfit_warning') or 'none'}",
            "",
            "_A single backtest window proves little; run walk-forward before trusting any figure above._",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_comparison_report(
    path: Path,
    summary: dict[str, Any],
    ranked_rows: list[dict[str, Any]],
    safety: dict[str, Any],
) -> None:
    lines = [
        "# Backtest Comparison Packet",
        "",
        f"- Comparison: {summary['comparison_id']}",
        f"- Runs compared: {summary['run_count']}",
        f"- Best run: {summary['best_run_id']} ({summary['best_strategy_label']})",
        f"- Best return: {summary['best_return_pct']}%",
        f"- Return spread: {summary['return_spread_pct']}%",
        f"- Local only: `{str(safety['local_only']).lower()}`",
        f"- Optimize enabled: `{str(safety['optimization']).lower()}`",
        f"- Live orders: `{str(safety['live_orders']).lower()}`",
        "",
        "| Rank | Run | Strategy | Return % | Max DD % | Trades | Source |",
        "| ---: | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for rank, row in enumerate(ranked_rows, start=1):
        lines.append(
            "| {rank} | {run_id} | {strategy_label} | {return_pct} | "
            "{max_drawdown_pct} | {trade_count} | {data_source} |".format(
                rank=rank,
                **row,
            )
        )
    lines.append("")
    lines.append("This packet compares existing local artifacts only; no optimize, deploy, broker, balance, or live order path is enabled.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_walk_forward_report(
    path: Path,
    summary: dict[str, Any],
    folds: list[dict[str, Any]],
    provenance: dict[str, Any],
) -> None:
    lines = [
        "# Walk-Forward Report",
        "",
        f"- Symbol: {summary['symbol']}",
        f"- Strategy: {summary['strategy']}",
        f"- Mode: {summary['mode']}",
        f"- Data source: {provenance['source']} ({provenance['state']})",
        f"- Cache hash: {provenance['cache_snapshot_hash'] or 'none'}",
        f"- Folds: {summary['completed_folds']}",
        f"- Average fold return: {summary['average_return_pct']}%",
        f"- Best fold return: {summary['best_fold_return_pct']}%",
        f"- Worst fold return: {summary['worst_fold_return_pct']}%",
        f"- Trades: {summary['total_trade_count']}",
        f"- Guard: {summary['lookahead_guard']}",
        "",
        "| Fold | Train candles | Test candles | Return % | Trades | Signals |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for fold in folds:
        lines.append(
            "| {fold_id} | {train_candle_count} | {test_candle_count} | {return_pct} | "
            "{trade_count} | {signal_count} |".format(**fold)
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _strategy_entry(strategy: str) -> dict[str, Any]:
    for entry in STRATEGY_CATALOG:
        if entry["strategy_id"] == strategy:
            return entry
    raise BacktestError("Unsupported backtest strategy")


def _bounded_int_parameter(raw_value: Any, parameter: dict[str, Any]) -> int:
    label = str(parameter["label"])
    try:
        value = int(str(raw_value))
    except (TypeError, ValueError) as exc:
        raise BacktestError(f"{label} must be an integer") from exc
    minimum = int(parameter["minimum"])
    maximum = int(parameter["maximum"])
    if value < minimum:
        raise BacktestError(f"{label} is below minimum")
    if value > maximum:
        raise BacktestError(f"{label} is too large")
    return value


def _validate_strategy_constraints(entry: dict[str, Any], values: dict[str, int]) -> None:
    for constraint in entry["constraints"]:
        if constraint["operator"] != "greater_than":
            raise BacktestError("Unsupported strategy parameter constraint")
        if values[str(constraint["left"])] <= values[str(constraint["right"])]:
            raise BacktestError(str(constraint["message"]))


def _rolling_average(values: list[Decimal], window: int) -> Decimal | None:
    if len(values) < window:
        return None
    return sum(values[-window:]) / Decimal(window)


def _rolling_stddev(values: list[Decimal], window: int) -> Decimal | None:
    if len(values) < window:
        return None
    sample = values[-window:]
    mean = sum(sample) / Decimal(window)
    variance = sum((value - mean) * (value - mean) for value in sample) / Decimal(window)
    return variance.sqrt()


def _rolling_rsi(values: list[Decimal], window: int) -> Decimal | None:
    if len(values) <= window:
        return None
    sample = values[-(window + 1) :]
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for previous, current in zip(sample[:-1], sample[1:], strict=True):
        change = current - previous
        gains.append(max(change, Decimal("0")))
        losses.append(max(-change, Decimal("0")))
    average_gain = sum(gains) / Decimal(window)
    average_loss = sum(losses) / Decimal(window)
    if average_loss == Decimal("0"):
        return Decimal("100") if average_gain > Decimal("0") else Decimal("50")
    relative_strength = average_gain / average_loss
    return Decimal("100") - (Decimal("100") / (Decimal("1") + relative_strength))


def _returns_curve(equity_curve: list[dict[str, str]]) -> list[dict[str, str]]:
    rows = []
    previous: Decimal | None = None
    for point in equity_curve:
        equity = Decimal(point["equity"])
        if previous is None or previous == 0:
            period_return = Decimal("0")
        else:
            period_return = (equity / previous) - Decimal("1")
        rows.append(
            {
                "closed_at": point["closed_at"],
                "equity": point["equity"],
                "period_return_pct": _percent(period_return),
            }
        )
        previous = equity
    return rows


def _returns_analysis(
    returns_curve: list[dict[str, str]],
    total_return_pct: str,
    max_drawdown: Decimal,
) -> dict[str, str]:
    returns = [Decimal(row["period_return_pct"]) for row in returns_curve[1:]]
    if not returns:
        returns = [Decimal("0")]
    positive = [value for value in returns if value > 0]
    negative = [value for value in returns if value < 0]
    average = sum(returns, Decimal("0")) / Decimal(len(returns))
    return {
        "period_count": str(len(returns)),
        "positive_periods": str(len(positive)),
        "negative_periods": str(len(negative)),
        "best_period_return_pct": str(
            max(returns).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ),
        "worst_period_return_pct": str(
            min(returns).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ),
        "average_period_return_pct": str(average.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "total_return_pct": total_return_pct,
        "max_drawdown_pct": _percent(max_drawdown / Decimal("100")),
    }


def _walk_forward_consistency(
    full_window_return: Decimal,
    average_fold_return: Decimal,
    positive_folds: int,
    fold_count: int,
) -> tuple[str, str]:
    """Grade how the full-window headline survives out-of-sample slices."""

    if fold_count == 0:
        return "inconsistent", "No folds were evaluated."
    positive_ratio = Decimal(positive_folds) / Decimal(fold_count)
    gap = full_window_return - average_fold_return
    if full_window_return > 0 and average_fold_return <= 0:
        return (
            "inconsistent",
            (
                f"The full window shows {full_window_return.quantize(Decimal('0.01'))}% "
                f"but folds average {average_fold_return.quantize(Decimal('0.01'))}% — "
                "the edge does not survive out-of-sample slices."
            ),
        )
    if positive_ratio < Decimal("0.5"):
        return (
            "inconsistent",
            f"Only {positive_folds} of {fold_count} folds were profitable — results depend on the window.",
        )
    tolerated_gap = max(Decimal("1"), abs(full_window_return) / 2)
    if positive_ratio >= Decimal("0.67") and gap <= tolerated_gap:
        return (
            "consistent",
            f"{positive_folds} of {fold_count} folds profitable and the out-of-sample average holds near the full window.",
        )
    return (
        "mixed",
        (
            f"{positive_folds} of {fold_count} folds profitable with a "
            f"{gap.quantize(Decimal('0.01'))}pp gap to the full window — treat the headline with care."
        ),
    )


# Crypto candles run 24/7, so annualization is calendar-based per timeframe.
_PERIODS_PER_YEAR = {
    "1m": 525600,
    "5m": 105120,
    "15m": 35040,
    "1h": 8760,
    "4h": 2190,
    "1d": 365,
}


def _risk_metrics(
    returns_curve: list[dict[str, str]],
    trades: list[dict[str, str]],
    closed_candles: int,
    timeframe: str,
) -> dict[str, str]:
    """Risk-adjusted statistics plus explicit overfitting red flags.

    Retail backtests routinely report a bare return; research shows the Sharpe
    ratio alone barely predicts out-of-sample results, and implausibly strong
    stats (Sharpe > 3, profit factor > 2 on few trades) are the classic
    overfitting tell — so those cases are flagged in plain words instead of
    being presented as achievements.
    """

    returns = [Decimal(row["period_return_pct"]) for row in returns_curve[1:]]
    period_count = len(returns)
    annualization = Decimal(_PERIODS_PER_YEAR.get(timeframe, 35040)).sqrt()

    sharpe: Decimal | None = None
    sortino: Decimal | None = None
    if period_count > 1:
        mean = sum(returns, Decimal("0")) / Decimal(period_count)
        variance = sum(((value - mean) ** 2 for value in returns), Decimal("0")) / Decimal(
            period_count - 1
        )
        std = variance.sqrt()
        if std > 0:
            sharpe = mean / std * annualization
        downside = [value for value in returns if value < 0]
        if downside:
            downside_variance = sum((value**2 for value in downside), Decimal("0")) / Decimal(
                len(downside)
            )
            downside_std = downside_variance.sqrt()
            if downside_std > 0:
                sortino = mean / downside_std * annualization

    # Long/flat next-open fills alternate BUY (open) and SELL (close).
    round_trips: list[Decimal] = []
    entry: dict[str, str] | None = None
    held_candles = 0
    open_entry_index: int | None = None
    for trade in trades:
        fill_index = int(trade["fill_candle_index"])
        if trade["side"] == "BUY":
            entry = trade
            open_entry_index = fill_index
        elif trade["side"] == "SELL" and entry is not None:
            quantity = Decimal(trade["quantity"])
            pnl = (
                (Decimal(trade["price"]) - Decimal(entry["price"])) * quantity
                - Decimal(trade["fee"])
                - Decimal(entry["fee"])
            )
            round_trips.append(pnl)
            entry = None
            if open_entry_index is not None:
                held_candles += max(0, fill_index - open_entry_index)
                open_entry_index = None
    if open_entry_index is not None and closed_candles > 0:
        held_candles += max(0, closed_candles - 1 - open_entry_index)

    wins = [pnl for pnl in round_trips if pnl > 0]
    losses = [pnl for pnl in round_trips if pnl < 0]
    gross_profit = sum(wins, Decimal("0"))
    gross_loss = -sum(losses, Decimal("0"))
    profit_factor: Decimal | None = None
    if gross_loss > 0:
        profit_factor = gross_profit / gross_loss
    win_rate: Decimal | None = None
    avg_trade_pnl: Decimal | None = None
    if round_trips:
        win_rate = Decimal(len(wins)) / Decimal(len(round_trips)) * Decimal("100")
        avg_trade_pnl = sum(round_trips, Decimal("0")) / Decimal(len(round_trips))
    exposure: Decimal | None = None
    if closed_candles > 1:
        exposure = Decimal(held_candles) / Decimal(closed_candles - 1) * Decimal("100")

    def _two(value: Decimal | None) -> str:
        if value is None:
            return ""
        return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    flags: list[str] = []
    if len(round_trips) < 5:
        flags.append(
            f"only {len(round_trips)} completed round trips — far too few for any statistic to mean much"
        )
    if sharpe is not None and sharpe > 3:
        flags.append(
            f"annualized Sharpe {_two(sharpe)} is implausibly high — a classic overfitting tell"
        )
    if profit_factor is not None and profit_factor > 2 and len(round_trips) < 30:
        flags.append(
            f"profit factor {_two(profit_factor)} on only {len(round_trips)} trades — "
            "validate with walk-forward before trusting it"
        )

    return {
        "sharpe_ratio": _two(sharpe),
        "sortino_ratio": _two(sortino),
        "win_rate_pct": _two(win_rate),
        "profit_factor": _two(profit_factor),
        "avg_trade_pnl": _two(avg_trade_pnl),
        "round_trip_count": str(len(round_trips)),
        "exposure_pct": _two(exposure),
        "overfit_warning": "; ".join(flags) if flags else "none",
    }


def _hash_json(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _config_hash_payload(config: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in config.items() if key != "research_lineage"}


def _final_backtest_lineage(
    raw_lineage: Any,
    *,
    run_id: str,
    config_hash: str,
    data_hash: str,
    manifest_path: str,
) -> dict[str, Any] | None:
    if raw_lineage in (None, "", {}):
        return None
    try:
        return with_backtest_lineage(
            normalize_research_lineage(raw_lineage),
            backtest_run_id=run_id,
            backtest_config_hash=config_hash,
            data_snapshot_hash=data_hash,
            manifest_path=manifest_path,
        )
    except ResearchLineageError as exc:
        raise BacktestError(str(exc)) from exc


def _bounded_walk_forward_folds(raw_value: Any) -> int:
    try:
        value = int(str(raw_value))
    except (TypeError, ValueError) as exc:
        raise BacktestError("Fold count must be an integer") from exc
    if value < 2 or value > 8:
        raise BacktestError("Fold count must be between 2 and 8")
    return value


def _bounded_comparison_run_count(raw_value: Any) -> int:
    try:
        value = int(str(raw_value))
    except (TypeError, ValueError) as exc:
        raise BacktestError("Comparison run count must be an integer") from exc
    if value < 2 or value > 8:
        raise BacktestError("Comparison run count must be between 2 and 8")
    return value


def _bounded_run_index_count(raw_value: Any) -> int:
    try:
        value = int(str(raw_value))
    except (TypeError, ValueError) as exc:
        raise BacktestError("Backtest run index count must be an integer") from exc
    if value < 1:
        raise BacktestError("Backtest run index count is below minimum")
    if value > DEFAULT_BACKTEST_RUN_INDEX_LIMIT:
        raise BacktestError("Backtest run index count is too large")
    return value


def _latest_backtest_run_rows(
    artifact_root: Path,
    *,
    max_runs: int,
) -> tuple[list[dict[str, Any]], int]:
    backtests_root = artifact_root / "artifacts" / "backtests"
    if not backtests_root.exists():
        return [], 0
    rows: list[dict[str, Any]] = []
    skipped_count = 0
    for run_dir in sorted(
        (path for path in backtests_root.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ):
        if len(rows) >= max_runs:
            break
        if not run_dir.name.startswith("bt-"):
            continue
        row = _backtest_run_row(artifact_root, run_dir)
        if row is None:
            skipped_count += 1
            continue
        rows.append(row)
    return rows, skipped_count


def _latest_backtest_artifact_health_rows(
    artifact_root: Path,
    *,
    max_runs: int,
) -> tuple[list[dict[str, Any]], int]:
    backtests_root = artifact_root / "artifacts" / "backtests"
    if not backtests_root.exists():
        return [], 0
    rows: list[dict[str, Any]] = []
    skipped_count = 0
    for run_dir in sorted(
        (path for path in backtests_root.iterdir() if path.is_dir()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ):
        if len(rows) >= max_runs:
            break
        if not run_dir.name.startswith("bt-"):
            skipped_count += 1
            continue
        row = _backtest_artifact_health_row(artifact_root, run_dir)
        if row is None:
            skipped_count += 1
            continue
        rows.append(row)
    return rows, skipped_count


def _backtest_artifact_health_row(artifact_root: Path, run_dir: Path) -> dict[str, Any] | None:
    root = artifact_root.resolve()
    resolved = run_dir.resolve()
    if not resolved.is_relative_to(root):
        return None
    present: list[str] = []
    present_mtimes: list[tuple[str, float]] = []
    for filename in BACKTEST_RUN_HEALTH_EXPECTED_FILES:
        path = run_dir / filename
        if not path.is_file():
            continue
        present.append(filename)
        try:
            present_mtimes.append((filename, path.stat().st_mtime))
        except OSError:
            continue
    missing = [filename for filename in BACKTEST_RUN_HEALTH_EXPECTED_FILES if filename not in present]
    latest_artifact = ""
    if present_mtimes:
        latest_name = max(present_mtimes, key=lambda item: item[1])[0]
        latest_artifact = f"artifacts/backtests/{run_dir.name}/{latest_name}"
    health_state = "complete" if not missing else "partial_missing_artifacts"
    recovery_hint = (
        "ready_for_run_index_or_comparison"
        if not missing
        else "rerun_closed_candle_backtest_or_review_local_run_dir"
    )
    return {
        "run_id": run_dir.name,
        "artifact_dir": run_dir.relative_to(artifact_root).as_posix(),
        "health_state": health_state,
        "expected_count": len(BACKTEST_RUN_HEALTH_EXPECTED_FILES),
        "present_count": len(present),
        "missing_count": len(missing),
        "present_artifacts": present,
        "missing_artifacts": missing,
        "latest_artifact_path": latest_artifact,
        "manifest_path": f"artifacts/backtests/{run_dir.name}/manifest.json",
        "supervision_ready": not missing,
        "recovery_hint": recovery_hint,
        "destructive_actions_enabled": False,
    }


def _backtest_run_row(artifact_root: Path, run_dir: Path) -> dict[str, Any] | None:
    root = artifact_root.resolve()
    resolved = run_dir.resolve()
    if not resolved.is_relative_to(root):
        return None
    summary = _read_json_file(run_dir / "summary.json")
    manifest = _read_json_file(run_dir / "manifest.json")
    returns_analysis = _read_json_file(run_dir / "returns_analysis.json")
    provenance = _read_json_file(run_dir / "provenance.json")
    if not all(isinstance(item, dict) for item in (summary, manifest, returns_analysis, provenance)):
        return None
    artifacts = manifest.get("artifact_files") if isinstance(manifest.get("artifact_files"), dict) else {}
    manifest_path = str(artifacts.get("manifest") or f"artifacts/backtests/{run_dir.name}/manifest.json")
    return {
        "run_id": str(manifest.get("run_id") or run_dir.name),
        "artifact_dir": run_dir.relative_to(artifact_root).as_posix(),
        "strategy": str(summary.get("strategy") or manifest.get("strategy") or ""),
        "strategy_label": str(
            summary.get("strategy_label")
            or manifest.get("strategy_label")
            or summary.get("strategy")
            or ""
        ),
        "symbol": str(summary.get("symbol") or ""),
        "timeframe": str(summary.get("timeframe") or ""),
        "final_equity": str(summary.get("final_equity") or ""),
        "return_pct": _decimal_text(summary.get("return_pct")),
        "max_drawdown_pct": _decimal_text(returns_analysis.get("max_drawdown_pct")),
        "trade_count": int(summary.get("trade_count") or 0),
        "signal_count": int(manifest.get("signal_count") or 0),
        "data_source": str(summary.get("data_source") or provenance.get("source") or ""),
        "data_state": str(summary.get("data_state") or provenance.get("state") or ""),
        "cache_snapshot_hash": str(
            summary.get("cache_snapshot_hash") or manifest.get("cache_snapshot_hash") or ""
        ),
        "manifest_path": manifest_path,
        "created_at": str(manifest.get("created_at") or ""),
    }


def _read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _decimal_text(raw_value: Any) -> str:
    try:
        return str(Decimal(str(raw_value or "0")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        return "0.00"


def _decimal_difference(left: Any, right: Any) -> str:
    return str(
        (Decimal(str(left or "0")) - Decimal(str(right or "0"))).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    )


def _decimal_percent_average(values: list[Decimal]) -> str:
    if not values:
        return "0.00"
    average = sum(values, Decimal("0")) / Decimal(len(values))
    return str(average.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _walk_forward_safety() -> dict[str, bool | str]:
    return {
        "local_only": True,
        "fixed_parameters": True,
        "optimization": False,
        "real_orders": False,
        "broker_routing": False,
        "private_api_required": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives": False,
        "lookahead_guard": "signals_on_close_fills_next_open",
    }


def _bounded_decimal(
    raw_value: Any,
    *,
    inclusive_minimum: bool,
    label: str,
    maximum: Decimal,
    minimum: Decimal,
) -> Decimal:
    try:
        value = Decimal(str(raw_value))
    except InvalidOperation as exc:
        raise BacktestError(f"{label} must be numeric") from exc
    if not value.is_finite():
        raise BacktestError(f"{label} must be finite")
    if inclusive_minimum:
        if minimum > 0 and value <= 0:
            raise BacktestError(f"{label} must be positive")
        if value < minimum:
            raise BacktestError(f"{label} is below minimum")
    elif value <= minimum:
        raise BacktestError(f"{label} must be positive")
    if value > maximum:
        raise BacktestError(f"{label} is too large")
    return value


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _amount(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP).normalize())


def _percent(value: Decimal) -> str:
    return str((value * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _strategy_label(strategy: str) -> str:
    return STRATEGY_LABELS.get(strategy, strategy)
