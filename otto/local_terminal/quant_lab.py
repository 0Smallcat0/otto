"""Local Quant Lab catalog and safe preview artifacts."""

from __future__ import annotations

import copy
import csv
import json
import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import mean
from typing import Any
from uuid import uuid4

from otto.local_terminal.advanced_context import context_for_artifact, sanitize_advanced_context


MAX_RUNS = 80
MAX_INPUT_LENGTH = 6000
RUNNABLE_PRIORITIES = {"P0", "P1"}
SECRET_PATTERNS = (
    re.compile(
        r"[\"']?(api[\s_-]*key|apikey|access[\s_-]*token|refresh[\s_-]*token|"
        r"secret[\s_-]*key|client[\s_-]*secret|private[\s_-]*key|password|"
        r"passphrase|pin|token|secret)[\"']?\s*[:=]\s*[\"']?[^\"'\s,}]+",
        re.IGNORECASE,
    ),
    re.compile(r"\bauthorization\s*:\s*[^,\s]+", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
)
FORBIDDEN_RUNTIME_PATTERNS = (
    re.compile(r"\bdeep[_\s-]*agent\b", re.IGNORECASE),
    re.compile(r"\blive[_\s-]*signals?\b", re.IGNORECASE),
    re.compile(r"\bcreate_order\s*\(", re.IGNORECASE),
    re.compile(r"\bplace_order\s*\(", re.IGNORECASE),
    re.compile(r"\bfetch_balance\s*\(", re.IGNORECASE),
    re.compile(r"\bset_leverage\s*\(", re.IGNORECASE),
    re.compile(r"\bset_margin_mode\s*\(", re.IGNORECASE),
    re.compile(r"\b(real|live)[_\s-]*(order|balance|execution|trading)\b", re.IGNORECASE),
    re.compile(r"\b(margin|leverage|short|derivatives?|futures?|perpetuals?)\b", re.IGNORECASE),
)


class QuantLabError(ValueError):
    """Raised when a Quant Lab request violates local preview rules."""


class QuantLabDisabledError(QuantLabError):
    """Raised when a module is intentionally unavailable for local execution."""


def _module(
    slug: str,
    title: str,
    category: str,
    local_priority: str,
    local_action: str,
    script: str,
) -> dict[str, str | bool]:
    return {
        "slug": slug,
        "title": title,
        "category": category,
        "local_priority": local_priority,
        "local_action": local_action,
        "script": script,
        "observed": True,
    }


MODULE_CATALOG: tuple[dict[str, str | bool], ...] = (
    _module("factor-discovery", "Factor Discovery", "core", "P2", "catalog_shell", "ai_quant_lab/qlib_service.py"),
    _module("model-library", "Model Library", "core", "P2", "catalog_shell", "ai_quant_lab/qlib_service.py"),
    _module("backtesting", "Backtesting", "core", "P0", "connect_to_local_backtest_contract", "ai_quant_lab/qlib_advanced_backtest.py"),
    _module("live-signals", "Live Signals", "core", "P2", "read_only_signal_view", "ai_quant_lab/qlib_service.py"),
    _module("deep-agent", "Deep Agent", "ai_ml", "defer", "do_not_execute_in_mvp", "agents/rdagents/cli.py"),
    _module("rl-trading", "RL Trading", "ai_ml", "defer", "research_only_later", "ai_quant_lab/qlib_rl.py"),
    _module("online-learning", "Online Learning", "ai_ml", "defer", "research_only_later", "ai_quant_lab/qlib_online_learning.py"),
    _module("meta-learning", "Meta Learning", "ai_ml", "defer", "research_only_later", "ai_quant_lab/qlib_meta_learning.py"),
    _module("pattern-intelligence", "Pattern Intelligence", "ai_ml", "P2", "technical_pattern_tool", "Analytics/technical_indicators.py"),
    _module("high-frequency-trading", "High Frequency Trading", "advanced", "defer", "exclude_from_crypto_mvp", "ai_quant_lab/qlib_high_frequency.py"),
    _module("rolling-retraining", "Rolling Retraining", "advanced", "defer", "research_only_later", "ai_quant_lab/qlib_rolling_retraining.py"),
    _module("advanced-models", "Advanced Models", "advanced", "defer", "research_only_later", "ai_quant_lab/qlib_advanced_models.py"),
    _module("feature-engineering", "Feature Engineering", "advanced", "P1", "local_indicator_feature_tools", "ai_quant_lab/qlib_feature_engineering.py"),
    _module("portfolio-optimization", "Portfolio Optimization", "advanced", "P1", "local_optimizer_research_tool", "ai_quant_lab/qlib_portfolio_opt.py"),
    _module("factor-evaluation", "Factor Evaluation", "advanced", "P1", "local_ic_and_factor_report", "ai_quant_lab/qlib_evaluation.py"),
    _module("strategy-builder", "Strategy Builder", "advanced", "P1", "config_editor_only", "ai_quant_lab/qlib_strategy.py"),
    _module("data-processors", "Data Processors", "advanced", "P1", "local_pipeline_editor", "ai_quant_lab/qlib_data_processors.py"),
    _module("quant-reporting", "Quant Reporting", "analytics", "P1", "local_report_generator", "ai_quant_lab/qlib_reporting.py"),
    _module("cfa-quant", "CFA Quant", "analytics", "P2", "analytics_shell", "Analytics/quant_analytics_cli.py"),
    _module("gs-quant", "GS Quant", "analytics", "P2", "analytics_shell", "Analytics/gs_quant_wrapper/gs_quant_service.py"),
    _module("statsmodels", "Statsmodels", "analytics", "P2", "local_statsmodels_tool", "Analytics/statsmodels_wrapper/statsmodels_service.py"),
    _module("functime", "Functime", "analytics", "P2", "forecasting_tool_shell", "Analytics/functime_wrapper/functime_service.py"),
    _module("fortitudo", "Fortitudo", "analytics", "P2", "portfolio_risk_tool_shell", "Analytics/fortitudo_tech_wrapper/fortitudo_service.py"),
    _module("gluonts", "GluonTS", "analytics", "P2", "probabilistic_forecast_shell", "Analytics/gluonts_wrapper/gluonts_service.py"),
    _module("fetch-data", "Fetch Data", "observed_subpage", "P1", "data_fetch_subpage", ""),
    _module("calendar", "Calendar", "observed_subpage", "P1", "calendar_subpage", ""),
)
MODULE_BY_SLUG = {str(module["slug"]): module for module in MODULE_CATALOG}
DEFAULT_ACTIVE_MODULE = "feature-engineering"


MODULE_CONTROLS: dict[str, dict[str, Any]] = {
    "feature-engineering": {
        "controls": ["Price Data", "Indicator", "Window", "Feature Selection", "Expression Engine"],
        "action": "COMPUTE INDICATOR",
        "defaults": {"price_data": "100,101,102,104,103,105", "indicator": "moving_average", "window": "3"},
    },
    "portfolio-optimization": {
        "controls": ["Assets", "Covariance Matrix", "Risk-Free Rate", "HRP", "Min Variance", "Max Sharpe"],
        "action": "RUN HRP",
        "defaults": {"assets": "BTC,ETH,SOL", "risk_free_rate": "2.00", "method": "hrp"},
    },
    "factor-evaluation": {
        "controls": ["Predictions", "Returns", "Method", "IC Metrics", "Risk Metrics"],
        "action": "CALCULATE IC METRICS",
        "defaults": {"predictions": "0.1,0.2,-0.1,0.4", "returns": "0.02,0.01,-0.03,0.05", "method": "pearson"},
    },
    "data-processors": {
        "controls": ["List All Processors", "Browse", "Create Pipeline", "Process Data"],
        "action": "BUILD LOCAL PIPELINE",
        "defaults": {"pipeline": "dropna,zscore,clip", "dataset": "local_artifact"},
    },
    "quant-reporting": {
        "controls": ["Predictions", "Returns", "IC Method", "Rolling Window", "IC Analysis", "Factor Quantiles"],
        "action": "RUN IC ANALYSIS",
        "defaults": {"report_type": "both", "rolling_window": "20", "ic_method": "pearson"},
    },
    "backtesting": {
        "controls": ["Local Backtest Contract", "Config", "Artifacts", "Summary"],
        "action": "OPEN BACKTEST HANDOFF",
        "defaults": {"artifact_dir": "artifacts/backtests/latest", "contract": "local_closed_candle"},
    },
    "strategy-builder": {
        "controls": ["Name", "Universe", "Rules", "Risk Settings"],
        "action": "SAVE CONFIG DRAFT",
        "defaults": {"name": "Local factor draft", "universe": "BTCUSDT,ETHUSDT", "rules": "rank factor; long paper only"},
    },
    "fetch-data": {
        "controls": ["Source", "Symbols", "Timeframe", "Cache"],
        "action": "PLAN LOCAL FETCH",
        "defaults": {"source": "public_read_only", "symbols": "BTCUSDT,ETHUSDT", "timeframe": "15m"},
    },
    "calendar": {
        "controls": ["Events", "Range", "Timezone"],
        "action": "BUILD LOCAL CALENDAR",
        "defaults": {"range": "30d", "timezone": "local", "events": "macro,earnings,crypto"},
    },
}


def default_quant_lab_state() -> dict[str, Any]:
    return {
        "active_module": DEFAULT_ACTIVE_MODULE,
        "runs": {},
        "last_run_id": None,
        "updated_at": "not started",
    }


def quant_lab_safety_payload() -> dict[str, bool | str]:
    return {
        "local_artifacts_only": True,
        "script_execution": False,
        "external_runtime": False,
        "cloud_account_required": False,
        "subscription_required": False,
        "private_api_required": False,
        "external_network": False,
        "deep_agent_execution": False,
        "model_training": False,
        "live_signals": False,
        "broker_mutation": False,
        "real_orders": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives": False,
        "output": "local_preview_artifacts",
    }


def normalize_quant_lab_state(state: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    default = default_quant_lab_state()
    invalid_runs = (
        {str(key): str(value) for key, value in state.get("invalid_runs", {}).items()}
        if isinstance(state.get("invalid_runs"), dict)
        else {}
    )
    if strict and invalid_runs:
        first_key, first_value = next(iter(invalid_runs.items()))
        raise QuantLabError(f"Quant Lab state is invalid: {first_key}: {first_value}")

    active_module = str(state.get("active_module") or DEFAULT_ACTIVE_MODULE)
    if active_module not in MODULE_BY_SLUG:
        active_module = DEFAULT_ACTIVE_MODULE

    raw_runs = state.get("runs")
    runs: dict[str, dict[str, Any]] = {}
    if isinstance(raw_runs, dict):
        if len(raw_runs) > MAX_RUNS:
            raise QuantLabError(f"Quant Lab runs exceed limit of {MAX_RUNS}")
        for run_id, raw_run in raw_runs.items():
            if not isinstance(raw_run, dict):
                if strict:
                    raise QuantLabError(f"Stored run {run_id} must be an object")
                invalid_runs[str(run_id)] = "Stored run must be an object"
                continue
            try:
                run = normalize_run_record(raw_run, fallback_id=str(run_id))
            except QuantLabError as exc:
                if strict:
                    raise QuantLabError(f"Stored run {run_id} is invalid: {exc}") from exc
                invalid_runs[str(run_id)] = str(exc)
                continue
            runs[run["run_id"]] = run
    elif raw_runs not in (None, {}):
        if strict:
            raise QuantLabError("Stored runs must be an object")
        invalid_runs["runs"] = "Stored runs must be an object"

    last_run_id = str(state.get("last_run_id") or "")
    if last_run_id not in runs:
        last_run_id = _latest_run_id(runs)

    return {
        **default,
        "active_module": active_module,
        "runs": runs,
        "last_run_id": last_run_id or None,
        "invalid_runs": invalid_runs,
        "updated_at": str(state.get("updated_at") or default["updated_at"]),
    }


def quant_lab_payload(
    state: dict[str, Any],
    context: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    quant_state = normalize_quant_lab_state(state, strict=False)
    active_module = MODULE_BY_SLUG[quant_state["active_module"]]
    safe_context = sanitize_advanced_context(context)
    return {
        "active_module": copy.deepcopy(active_module),
        "catalog": [module_payload(module) for module in MODULE_CATALOG],
        "categories": _category_payload(),
        "priority_summary": _priority_summary(),
        "stats": {
            "modules": 24,
            "observed_subpages": 2,
            "catalog_entries": len(MODULE_CATALOG),
            "runnable_local_modules": sum(
                1 for module in MODULE_CATALOG if module["local_priority"] in RUNNABLE_PRIORITIES
            ),
            "deferred_modules": sum(
                1 for module in MODULE_CATALOG if module["local_priority"] == "defer"
            ),
        },
        "module_info": module_payload(active_module),
        "controls": _controls_with_context(
            str(active_module["slug"]),
            MODULE_CONTROLS.get(str(active_module["slug"]), default_module_controls(active_module)),
            safe_context,
        ),
        "runs": _run_list(quant_state),
        "last_run": copy.deepcopy(quant_state["runs"].get(quant_state["last_run_id"] or "")),
        "invalid_runs": quant_state["invalid_runs"],
        "artifact_root": "artifacts/quant_lab",
        "safety": quant_lab_safety_payload(),
        "context": safe_context,
        "preview_health": quant_lab_preview_health_payload(quant_state, root or Path.cwd()),
    }


def quant_lab_preview_health_payload(state: dict[str, Any], root: Path) -> dict[str, Any]:
    """Return metadata-only health for local Quant Lab preview artifacts."""

    quant_state = normalize_quant_lab_state(state, strict=False)
    rows = [
        _preview_health_row(root, run)
        for run in sorted(
            quant_state["runs"].values(),
            key=lambda run: str(run.get("created_at", "")),
            reverse=True,
        )
    ]
    recovery_queue = _preview_health_recovery_queue(rows)
    latest = rows[0] if rows else {}
    return {
        "mode": "metadata_only_quant_lab_preview_health",
        "contract": "quant_lab_preview_health_v1",
        "generated_at": _utc_now(),
        "root": "artifacts/quant_lab",
        "summary": {
            "run_count": len(rows),
            "complete_count": sum(1 for row in rows if row["health_state"] == "complete"),
            "partial_count": sum(
                1 for row in rows if row["health_state"].startswith("partial")
            ),
            "failed_count": sum(1 for row in rows if row["health_state"] == "failed_preview"),
            "missing_artifact_count": sum(int(row["missing_count"]) for row in rows),
            "supervision_ready_count": sum(1 for row in rows if row["supervision_ready"]),
            "invalid_run_count": len(quant_state["invalid_runs"]),
            "active_module": str(quant_state.get("active_module") or ""),
            "latest_run_id": str(latest.get("run_id") or ""),
            "recovery_queue_count": len(recovery_queue),
            "destructive_action_count": 0,
        },
        "runs": rows,
        "recovery_queue": recovery_queue,
        "recommended_actions": [
            {
                "action_id": "quant_lab_run_preview",
                "endpoint": "/api/quant-lab/run-preview",
                "method": "POST",
                "ready": True,
                "reason": "Run a local preview to create or refresh Quant Lab artifacts.",
            }
        ],
        "safety": {
            "local_only": True,
            "read_only": True,
            "metadata_only": True,
            "script_execution": False,
            "external_runtime": False,
            "deep_agent_execution": False,
            "model_training": False,
            "live_signals": False,
            "artifact_content_read": False,
            "artifact_content_indexing": False,
            "writes_local_artifacts": False,
            "automatic_repair_enabled": False,
            "destructive_actions_enabled": False,
            "provider_calls": False,
            "external_network": False,
            "secret_values_returned": False,
            "credentials_persisted": False,
            "broker_mutation": False,
            "real_orders": False,
            "real_balance": False,
            "live_trading": False,
        },
    }


def select_module(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    quant_state = normalize_quant_lab_state(copy.deepcopy(state))
    slug = _safe_slug(request.get("module_slug"))
    if slug not in MODULE_BY_SLUG:
        raise QuantLabError("Quant Lab module not found")
    quant_state["active_module"] = slug
    quant_state["updated_at"] = _utc_now()
    return quant_state


def run_local_preview(
    state: dict[str, Any],
    request: dict[str, Any],
    root: Path,
    context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    quant_state = normalize_quant_lab_state(copy.deepcopy(state))
    module_slug = _safe_slug(request.get("module_slug") or quant_state["active_module"])
    if module_slug not in MODULE_BY_SLUG:
        raise QuantLabError("Quant Lab module not found")
    module = MODULE_BY_SLUG[module_slug]
    if module["local_priority"] not in RUNNABLE_PRIORITIES:
        raise QuantLabDisabledError("Quant Lab module is catalog-only until a safety contract exists")
    if len(quant_state["runs"]) >= MAX_RUNS:
        raise QuantLabError(f"Quant Lab runs exceed limit of {MAX_RUNS}")
    safe_context = sanitize_advanced_context(context)
    default_controls = _controls_with_context(
        module_slug,
        MODULE_CONTROLS.get(module_slug, default_module_controls(module)),
        safe_context,
    )
    inputs = _safe_inputs(request.get("inputs") or default_controls.get("defaults", {}))
    output = _preview_for_module(module_slug, inputs)
    output["context"] = context_for_artifact(safe_context)
    output["source_provenance"] = _source_provenance_for_output(safe_context)
    output["artifact_inputs"] = _artifact_inputs_for_output(safe_context)
    output["output_mode"] = "local_context_bundle"
    now = _utc_now()
    run_id = f"qlab-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    artifact_dir = f"artifacts/quant_lab/{run_id}"
    run = normalize_run_record(
        {
            "run_id": run_id,
            "module_slug": module_slug,
            "module_title": module["title"],
            "status": "preview_complete",
            "inputs": inputs,
            "output": output,
            "artifact_dir": artifact_dir,
            "artifacts": {
                "input": f"{artifact_dir}/input.json",
                "output": f"{artifact_dir}/output.json",
                "context": f"{artifact_dir}/context.json",
                "manifest": f"{artifact_dir}/manifest.json",
                "report": f"{artifact_dir}/report.md",
                "error_log": f"{artifact_dir}/error.log",
            },
            "created_at": now,
        }
    )
    _write_run_artifacts(root, run)
    quant_state["runs"][run_id] = run
    quant_state["last_run_id"] = run_id
    quant_state["active_module"] = module_slug
    quant_state["updated_at"] = now
    return quant_state, run


def disabled_quant_lab_response(action: str) -> dict[str, Any]:
    return {
        "action": action,
        "state": "disabled",
        "reason": "Quant Lab execution is limited to local previews until a dedicated safety contract exists.",
        "safety": quant_lab_safety_payload(),
    }


def module_payload(module: dict[str, str | bool]) -> dict[str, Any]:
    priority = str(module["local_priority"])
    slug = str(module["slug"])
    return {
        "slug": slug,
        "title": str(module["title"]),
        "category": str(module["category"]),
        "observed_script_label": str(module["script"]),
        "script_path": str(module["script"]),
        "local_priority": priority,
        "local_action": str(module["local_action"]),
        "observed": bool(module["observed"]),
        "runnable": priority in RUNNABLE_PRIORITIES,
        "state": "local_preview" if priority in RUNNABLE_PRIORITIES else "catalog_only",
        "summary": _module_summary(slug),
        "controls": MODULE_CONTROLS.get(slug, default_module_controls(module))["controls"],
    }


def normalize_run_record(raw: dict[str, Any], fallback_id: str | None = None) -> dict[str, Any]:
    run_id = _safe_id(raw.get("run_id") or fallback_id, "Run id")
    module_slug = _safe_slug(raw.get("module_slug"))
    if module_slug not in MODULE_BY_SLUG:
        raise QuantLabError("Run module is not allowed")
    status = _safe_text(raw.get("status"), "Run status", 40)
    if status not in {"preview_complete", "preview_failed"}:
        raise QuantLabError("Run status is not allowed")
    artifacts = raw.get("artifacts")
    if not isinstance(artifacts, dict):
        raise QuantLabError("Run artifacts must be an object")
    normalized_artifacts = {
        "input": _safe_artifact_path(artifacts.get("input"), run_id, suffix="input.json"),
        "output": _safe_artifact_path(artifacts.get("output"), run_id, suffix="output.json"),
        "report": _safe_artifact_path(artifacts.get("report"), run_id, suffix="report.md"),
        "error_log": _safe_artifact_path(artifacts.get("error_log"), run_id, suffix="error.log"),
    }
    for key, suffix in {"context": "context.json", "manifest": "manifest.json"}.items():
        if artifacts.get(key):
            normalized_artifacts[key] = _safe_artifact_path(artifacts.get(key), run_id, suffix=suffix)

    return {
        "run_id": run_id,
        "module_slug": module_slug,
        "module_title": _safe_text(raw.get("module_title"), "Module title", 80),
        "status": status,
        "inputs": _safe_inputs(raw.get("inputs", {})),
        "output": _safe_output(raw.get("output", {})),
        "artifact_dir": _safe_artifact_path(raw.get("artifact_dir"), run_id),
        "artifacts": normalized_artifacts,
        "created_at": _safe_text(raw.get("created_at"), "Run timestamp", 80),
    }


def _category_payload() -> list[dict[str, Any]]:
    categories: dict[str, list[dict[str, Any]]] = {}
    for module in MODULE_CATALOG:
        categories.setdefault(str(module["category"]), []).append(module_payload(module))
    return [
        {
            "category": category,
            "count": len(items),
            "modules": items,
        }
        for category, items in categories.items()
    ]


def _priority_summary() -> dict[str, int]:
    priorities: dict[str, int] = {}
    for module in MODULE_CATALOG:
        key = str(module["local_priority"])
        priorities[key] = priorities.get(key, 0) + 1
    return priorities


def default_module_controls(module: dict[str, str | bool]) -> dict[str, Any]:
    return {
        "controls": ["Module Info", "Local Notes", "Artifact Plan"],
        "action": "CATALOG ONLY",
        "defaults": {"notes": f"{module['title']} is catalog-only in the local MVP."},
    }


def _module_summary(slug: str) -> str:
    summaries = {
        "feature-engineering": "Local indicator and feature scratchpad.",
        "portfolio-optimization": "Local optimizer preview without broker or live balances.",
        "factor-evaluation": "Local IC and factor report preview.",
        "data-processors": "Local pipeline draft for artifact data cleaning.",
        "quant-reporting": "Local report generator for factor and model artifacts.",
        "backtesting": "Handoff surface for the existing local closed-candle backtest contract.",
    }
    return summaries.get(slug, "Catalog entry preserved for route and module parity.")


def _controls_with_context(
    module_slug: str,
    controls: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    next_controls = copy.deepcopy(controls)
    defaults = next_controls.get("defaults")
    if not isinstance(defaults, dict):
        return next_controls
    price_series = str(context.get("summary", {}).get("price_series") or "")
    latest_price = str(context.get("summary", {}).get("latest_price") or "")
    primary_path = str(context.get("summary", {}).get("primary_cache_path") or "")
    if module_slug == "feature-engineering" and price_series:
        defaults["price_data"] = price_series
        defaults["dataset"] = primary_path or "provider_cache"
    if module_slug == "portfolio-optimization" and latest_price and "assets" in defaults:
        defaults["provider_price_reference"] = latest_price
    if module_slug == "data-processors" and primary_path:
        defaults["dataset"] = primary_path
    if module_slug == "backtesting" and primary_path:
        defaults["provider_cache"] = primary_path
    next_controls["defaults"] = defaults
    return next_controls


def _preview_for_module(module_slug: str, inputs: dict[str, str]) -> dict[str, Any]:
    if module_slug == "feature-engineering":
        prices = _number_list(inputs.get("price_data", ""))
        window = max(1, int(_decimal(inputs.get("window", "3"))))
        moving = [
            str(_quantized(mean(prices[index + 1 - window : index + 1])))
            for index in range(window - 1, len(prices))
        ]
        return {
            "kind": "indicator_preview",
            "indicator": inputs.get("indicator", "moving_average"),
            "window": str(window),
            "observations": len(prices),
            "values": moving,
            "last_value": moving[-1] if moving else "n/a",
        }
    if module_slug == "portfolio-optimization":
        assets = [asset.strip().upper() for asset in inputs.get("assets", "").split(",") if asset.strip()]
        if not assets:
            raise QuantLabError("Assets are required")
        weight = _quantized(Decimal("100") / Decimal(len(assets)))
        return {
            "kind": "optimizer_preview",
            "method": inputs.get("method", "hrp"),
            "risk_free_rate": inputs.get("risk_free_rate", "2.00"),
            "weights": [{"symbol": asset, "weight_pct": str(weight)} for asset in assets],
            "broker_mutation": False,
        }
    if module_slug == "factor-evaluation":
        predictions = _number_list(inputs.get("predictions", ""))
        returns = _number_list(inputs.get("returns", ""))
        if len(predictions) != len(returns):
            raise QuantLabError("Predictions and returns must have the same length")
        return {
            "kind": "factor_evaluation_preview",
            "method": inputs.get("method", "pearson"),
            "count": len(predictions),
            "ic": str(_quantized(_correlation(predictions, returns))),
            "risk_report": "local_preview_only",
        }
    if module_slug == "data-processors":
        pipeline = [step.strip() for step in inputs.get("pipeline", "").split(",") if step.strip()]
        return {
            "kind": "pipeline_preview",
            "dataset": inputs.get("dataset", "local_artifact"),
            "steps": pipeline,
            "mutation": False,
        }
    if module_slug == "quant-reporting":
        return {
            "kind": "report_preview",
            "sections": ["IC Analysis", "Cumulative Returns", "Model Performance", "Factor Quantiles"],
            "report_type": inputs.get("report_type", "both"),
            "rolling_window": inputs.get("rolling_window", "20"),
        }
    if module_slug == "backtesting":
        return {
            "kind": "backtest_handoff",
            "contract": "local_closed_candle",
            "route": "/backtest",
            "execution": "use_existing_backtest_workspace",
        }
    if module_slug == "strategy-builder":
        return {
            "kind": "strategy_config_preview",
            "name": inputs.get("name", "Local factor draft"),
            "universe": inputs.get("universe", ""),
            "rules": inputs.get("rules", ""),
            "live_deployment": False,
        }
    if module_slug == "fetch-data":
        return {
            "kind": "fetch_plan_preview",
            "source": inputs.get("source", "public_read_only"),
            "symbols": inputs.get("symbols", ""),
            "timeframe": inputs.get("timeframe", "15m"),
            "external_network": False,
        }
    if module_slug == "calendar":
        return {
            "kind": "calendar_preview",
            "range": inputs.get("range", "30d"),
            "timezone": inputs.get("timezone", "local"),
            "events": inputs.get("events", ""),
        }
    return {"kind": "local_preview", "module": module_slug}


def _write_run_artifacts(root: Path, run: dict[str, Any]) -> None:
    artifact_dir = root / run["artifact_dir"]
    if not artifact_dir.resolve().is_relative_to(root.resolve()):
        raise QuantLabError("Artifact path must stay inside repository")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json_artifact(root, Path(run["artifacts"]["input"]), run["inputs"])
    _write_json_artifact(root, Path(run["artifacts"]["output"]), run["output"])
    if run["artifacts"].get("context"):
        _write_json_artifact(root, Path(run["artifacts"]["context"]), _context_artifact_payload(run))
    if run["artifacts"].get("manifest"):
        _write_json_artifact(root, Path(run["artifacts"]["manifest"]), _manifest_artifact_payload(run))
    report = [
        f"# {run['module_title']} Local Preview",
        "",
        f"- Run: `{run['run_id']}`",
        f"- Module: `{run['module_slug']}`",
        f"- Output mode: `{run['output'].get('output_mode', 'local_preview')}`",
        f"- Context sources: `{len(run['output'].get('source_provenance', []))}`",
        f"- Artifact inputs: `{len(run['output'].get('artifact_inputs', []))}`",
        "- Script execution: `false`",
        "- External runtime: `false`",
        "- Broker mutation: `false`",
        "",
        "This artifact is generated by the local clean-room preview runner.",
    ]
    _write_text_artifact(root, Path(run["artifacts"]["report"]), "\n".join(report) + "\n")
    _write_text_artifact(root, Path(run["artifacts"]["error_log"]), "")


def _source_provenance_for_output(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in context.get("sources", [])[:6]:
        if not isinstance(source, dict):
            continue
        rows.append(
            {
                "source_id": source.get("source_id", ""),
                "state": source.get("state", ""),
                "provider_id": source.get("provider_id", ""),
                "cache_path": source.get("cache_path", ""),
                "record_count": source.get("record_count", 0),
            }
        )
    return rows


def _artifact_inputs_for_output(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in context.get("artifacts", [])[:8]:
        if not isinstance(artifact, dict):
            continue
        rows.append(
            {
                "artifact_id": artifact.get("artifact_id", ""),
                "kind": artifact.get("kind", ""),
                "path": artifact.get("path", ""),
                "bytes": artifact.get("bytes", 0),
            }
        )
    return rows


def _context_artifact_payload(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run["run_id"],
        "module_slug": run["module_slug"],
        "module_title": run["module_title"],
        "generated_at": run["created_at"],
        "context": run["output"].get("context", {}),
        "source_provenance": run["output"].get("source_provenance", []),
        "artifact_inputs": run["output"].get("artifact_inputs", []),
        "output_mode": run["output"].get("output_mode", "local_preview"),
    }


def _manifest_artifact_payload(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run["run_id"],
        "module_slug": run["module_slug"],
        "module_title": run["module_title"],
        "status": run["status"],
        "created_at": run["created_at"],
        "artifact_contract": run["artifacts"],
        "source_provenance": run["output"].get("source_provenance", []),
        "artifact_inputs": run["output"].get("artifact_inputs", []),
        "safety": quant_lab_safety_payload(),
        "clean_room": {
            "script_execution": False,
            "external_runtime": False,
            "broker_mutation": False,
            "credential_material": False,
        },
    }


def _write_json_artifact(root: Path, relative_path: Path, payload: dict[str, Any]) -> None:
    path = root / relative_path
    if not path.resolve().is_relative_to(root.resolve()):
        raise QuantLabError("Artifact path must stay inside repository")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text_artifact(root: Path, relative_path: Path, payload: str) -> None:
    path = root / relative_path
    if not path.resolve().is_relative_to(root.resolve()):
        raise QuantLabError("Artifact path must stay inside repository")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")


def _run_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "run_id": run["run_id"],
            "module_slug": run["module_slug"],
            "module_title": run["module_title"],
            "status": run["status"],
            "artifact_dir": run["artifact_dir"],
            "created_at": run["created_at"],
        }
        for run in sorted(
            state["runs"].values(),
            key=lambda run: str(run.get("created_at", "")),
            reverse=True,
        )
    ]


def _preview_health_row(root: Path, run: dict[str, Any]) -> dict[str, Any]:
    run_id = str(run["run_id"])
    file_rows: list[dict[str, Any]] = []
    mtimes: list[float] = []
    artifact_bytes = 0
    for name, relative_path in _preview_artifact_files(run).items():
        exists, size, mtime = _artifact_stat(root, relative_path)
        if mtime is not None:
            mtimes.append(mtime)
        artifact_bytes += size
        file_rows.append(
            {
                "name": name,
                "path": relative_path,
                "exists": exists,
                "bytes": size,
                "updated_at": _timestamp_text(mtime),
            }
        )
    by_name = {row["name"]: row for row in file_rows}
    present = [row["name"] for row in file_rows if row["exists"]]
    missing = [row["name"] for row in file_rows if not row["exists"]]
    if run["status"] == "preview_failed":
        health_state = "failed_preview"
    elif missing:
        health_state = "partial_missing_artifacts"
    else:
        health_state = "complete"
    return {
        "run_id": run_id,
        "module_slug": str(run.get("module_slug") or ""),
        "module_title": str(run.get("module_title") or ""),
        "status": str(run.get("status") or ""),
        "artifact_dir": str(run.get("artifact_dir") or ""),
        "created_at": str(run.get("created_at") or ""),
        "health_state": health_state,
        "expected_count": len(file_rows),
        "present_count": len(present),
        "missing_count": len(missing),
        "present_artifacts": present,
        "missing_artifacts": missing,
        "files": file_rows,
        "input_artifact_path": str(by_name["input"]["path"]),
        "input_artifact_exists": bool(by_name["input"]["exists"]),
        "output_artifact_path": str(by_name["output"]["path"]),
        "output_artifact_exists": bool(by_name["output"]["exists"]),
        "context_artifact_path": str(by_name["context"]["path"]),
        "context_artifact_exists": bool(by_name["context"]["exists"]),
        "manifest_artifact_path": str(by_name["manifest"]["path"]),
        "manifest_artifact_exists": bool(by_name["manifest"]["exists"]),
        "report_artifact_path": str(by_name["report"]["path"]),
        "report_artifact_exists": bool(by_name["report"]["exists"]),
        "error_log_artifact_path": str(by_name["error_log"]["path"]),
        "error_log_artifact_exists": bool(by_name["error_log"]["exists"]),
        "artifact_bytes": artifact_bytes,
        "latest_artifact_updated_at": _timestamp_text(max(mtimes) if mtimes else None),
        "supervision_ready": not missing and run["status"] == "preview_complete",
        "recovery_hint": (
            "ready_for_agent_supervision"
            if not missing and run["status"] == "preview_complete"
            else "rerun_local_preview_to_regenerate_missing_artifacts"
        ),
        "artifact_content_read": False,
        "script_execution": False,
        "destructive_actions_enabled": False,
    }


def _preview_health_recovery_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return [
            {
                "queue_id": "quant_lab_preview_health:none",
                "run_id": "",
                "artifact_path": "artifacts/quant_lab",
                "recommended_action": "quant_lab_run_preview",
                "endpoint": "/api/quant-lab/run-preview",
                "method": "POST",
                "reason": "No local Quant Lab preview runs exist; run a local preview first.",
                "destructive_action_required": False,
                "writes_local_artifacts": True,
            }
        ]
    queue = []
    for row in rows:
        if int(row["missing_count"]) == 0 and row["status"] == "preview_complete":
            continue
        queue.append(
            {
                "queue_id": f"quant_lab_preview_health:{row['run_id']}:artifacts",
                "run_id": row["run_id"],
                "artifact_path": row["artifact_dir"],
                "recommended_action": "quant_lab_run_preview",
                "endpoint": "/api/quant-lab/run-preview",
                "method": "POST",
                "reason": "Rerun the local preview to regenerate missing preview artifacts.",
                "destructive_action_required": False,
                "writes_local_artifacts": True,
            }
        )
    return queue


def _preview_artifact_files(run: dict[str, Any]) -> dict[str, str]:
    run_id = str(run["run_id"])
    artifacts = run.get("artifacts") if isinstance(run.get("artifacts"), dict) else {}
    return {
        "input": str(artifacts.get("input") or f"artifacts/quant_lab/{run_id}/input.json"),
        "output": str(artifacts.get("output") or f"artifacts/quant_lab/{run_id}/output.json"),
        "context": str(
            artifacts.get("context") or f"artifacts/quant_lab/{run_id}/context.json"
        ),
        "manifest": str(
            artifacts.get("manifest") or f"artifacts/quant_lab/{run_id}/manifest.json"
        ),
        "report": str(artifacts.get("report") or f"artifacts/quant_lab/{run_id}/report.md"),
        "error_log": str(
            artifacts.get("error_log") or f"artifacts/quant_lab/{run_id}/error.log"
        ),
    }


def _artifact_stat(root: Path, relative_path: str) -> tuple[bool, int, float | None]:
    try:
        resolved_root = root.resolve()
        resolved_path = (root / relative_path).resolve()
    except OSError:
        return False, 0, None
    if not resolved_path.is_relative_to(resolved_root) or not resolved_path.is_file():
        return False, 0, None
    try:
        stat = resolved_path.stat()
    except OSError:
        return False, 0, None
    return True, stat.st_size, stat.st_mtime


def _timestamp_text(timestamp: float | None) -> str:
    if timestamp is None:
        return ""
    return (
        datetime.fromtimestamp(timestamp, UTC)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _safe_inputs(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise QuantLabError("Inputs must be an object")
    if len(raw) > 32:
        raise QuantLabError("Inputs exceed limit")
    inputs = {}
    for key, value in raw.items():
        safe_key = _safe_text(key, "Input key", 60)
        if _looks_like_secret_key(safe_key):
            raise QuantLabError("Input key appears to request credential material")
        text = _safe_text(value, "Input value", MAX_INPUT_LENGTH)
        if _contains_secret(text):
            raise QuantLabError("Input appears to contain credential material")
        if _contains_forbidden_runtime_intent(text):
            raise QuantLabError("Input contains forbidden runtime intent")
        inputs[safe_key] = text
    return inputs


def _safe_output(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise QuantLabError("Output must be an object")
    text = json.dumps(raw, sort_keys=True)
    if _contains_secret(text) or _contains_forbidden_runtime_intent(text):
        raise QuantLabError("Output contains unsafe material")
    return raw


def _safe_artifact_path(raw: Any, run_id: str, suffix: str | None = None) -> str:
    value = str(raw or "").strip().replace("\\", "/")
    if not value:
        value = f"artifacts/quant_lab/{run_id}/{suffix}" if suffix else f"artifacts/quant_lab/{run_id}"
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise QuantLabError("Artifact path must be repository-local")
    if ".." in value.split("/"):
        raise QuantLabError("Artifact path cannot traverse directories")
    if not value.startswith(f"artifacts/quant_lab/{run_id}"):
        raise QuantLabError("Artifact path must stay under its run directory")
    return value


def _safe_slug(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value or len(value) > 80:
        raise QuantLabError("Module slug is required")
    if not all(ch.isalnum() or ch == "-" for ch in value):
        raise QuantLabError("Module slug is invalid")
    return value


def _safe_id(raw: Any, label: str) -> str:
    value = str(raw or "").strip()
    if not value or len(value) > 80:
        raise QuantLabError(f"{label} is required")
    if not all(ch.isalnum() or ch in {"-", "_"} for ch in value):
        raise QuantLabError(f"{label} is invalid")
    return value


def _safe_text(raw: Any, label: str, max_length: int) -> str:
    value = str(raw or "").strip()
    if not value:
        raise QuantLabError(f"{label} is required")
    if len(value) > max_length:
        raise QuantLabError(f"{label} exceeds limit")
    if _contains_secret(value):
        raise QuantLabError(f"{label} appears to contain credential material")
    return value


def _number_list(raw: str) -> list[Decimal]:
    reader = csv.reader([raw])
    try:
        values = next(reader)
    except StopIteration:
        values = []
    numbers = [_decimal(value) for value in values if value.strip()]
    if not numbers:
        raise QuantLabError("Numeric input is required")
    if len(numbers) > 200:
        raise QuantLabError("Numeric input exceeds limit")
    return numbers


def _decimal(raw: Any) -> Decimal:
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError):
        raise QuantLabError("Numeric input is invalid") from None
    if not value.is_finite():
        raise QuantLabError("Numeric input must be finite")
    if abs(value) > Decimal("1000000000"):
        raise QuantLabError("Numeric input is too large")
    return value


def _correlation(left: list[Decimal], right: list[Decimal]) -> Decimal:
    left_mean = mean(left)
    right_mean = mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=True))
    left_var = sum((x - left_mean) ** 2 for x in left)
    right_var = sum((y - right_mean) ** 2 for y in right)
    if left_var == 0 or right_var == 0:
        return Decimal("0")
    return numerator / (left_var * right_var).sqrt()


def _quantized(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))


def _latest_run_id(runs: dict[str, dict[str, Any]]) -> str:
    if not runs:
        return ""
    return max(runs.values(), key=lambda run: str(run.get("created_at", "")))["run_id"]


def _contains_secret(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _looks_like_secret_key(value: str) -> bool:
    normalized = re.sub(r"[\s_-]+", "", value).lower()
    return normalized in {
        "apikey",
        "accesstoken",
        "refreshtoken",
        "secretkey",
        "clientsecret",
        "privatekey",
        "password",
        "passphrase",
        "pin",
        "token",
        "secret",
    }


def _contains_forbidden_runtime_intent(value: str) -> bool:
    return any(pattern.search(value) for pattern in FORBIDDEN_RUNTIME_PATTERNS)


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
