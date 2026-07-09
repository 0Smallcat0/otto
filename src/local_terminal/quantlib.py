"""Local QuantLib-style calculator presets and artifacts."""

from __future__ import annotations

import copy
import json
import math
import random
import re
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any
from uuid import uuid4

from src.local_terminal.advanced_context import context_for_artifact, sanitize_advanced_context


MAX_CALCULATIONS = 80
MAX_JSON_LENGTH = 8000
QUANT = 6
DEFAULT_MODULE = "core"
DEFAULT_ACTION = "bs-price"

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
    re.compile(r"\bcreate_order\s*\(", re.IGNORECASE),
    re.compile(r"\bplace_order\s*\(", re.IGNORECASE),
    re.compile(r"\bfetch_balance\s*\(", re.IGNORECASE),
    re.compile(r"\bset_leverage\s*\(", re.IGNORECASE),
    re.compile(r"\bset_margin_mode\s*\(", re.IGNORECASE),
    re.compile(r"\b(real|live)[_\s-]*(order|balance|execution|trading)\b", re.IGNORECASE),
    re.compile(r"\b(private|broker)[_\s-]*(api|key|route|mutation)\b", re.IGNORECASE),
)


class QuantLibError(ValueError):
    """Raised when a QuantLib request violates local calculator rules."""


MODULE_TREE: tuple[dict[str, str | int], ...] = (
    {"module_id": "core", "label": "CORE", "endpoint_count": 51},
    {"module_id": "analysis", "label": "ANALYSIS", "endpoint_count": 122},
    {"module_id": "curves", "label": "CURVES", "endpoint_count": 31},
    {"module_id": "economics", "label": "ECONOMICS", "endpoint_count": 25},
    {"module_id": "instruments", "label": "INSTRUMENTS", "endpoint_count": 26},
    {"module_id": "machine-learning", "label": "MACHINE LEARNING", "endpoint_count": 48},
    {"module_id": "models", "label": "MODELS", "endpoint_count": 14},
    {"module_id": "numerical", "label": "NUMERICAL", "endpoint_count": 28},
    {"module_id": "physics", "label": "PHYSICS", "endpoint_count": 24},
    {"module_id": "portfolio", "label": "PORTFOLIO", "endpoint_count": 15},
    {"module_id": "pricing", "label": "PRICING", "endpoint_count": 29},
    {"module_id": "regulatory", "label": "REGULATORY", "endpoint_count": 11},
    {"module_id": "risk", "label": "RISK", "endpoint_count": 25},
    {"module_id": "scheduling", "label": "SCHEDULING", "endpoint_count": 14},
    {"module_id": "solver", "label": "SOLVER", "endpoint_count": 25},
    {"module_id": "statistics", "label": "STATISTICS", "endpoint_count": 52},
    {"module_id": "stochastic", "label": "STOCHASTIC", "endpoint_count": 36},
    {"module_id": "volatility", "label": "VOLATILITY", "endpoint_count": 14},
)
MODULE_IDS = {str(module["module_id"]) for module in MODULE_TREE}

QUICK_ACTIONS: dict[str, dict[str, Any]] = {
    "bs-price": {
        "label": "BS Price",
        "module_id": "core",
        "endpoint_combo_value": "core/types/currencies",
        "request_body": {
            "spot": 100,
            "strike": 105,
            "risk_free_rate": 0.05,
            "volatility": 0.2,
            "time_to_maturity": 1.0,
            "option_type": "call",
        },
    },
    "gbm-sim": {
        "label": "GBM Sim",
        "module_id": "stochastic",
        "endpoint_combo_value": "core/types/currencies",
        "request_body": {
            "S0": 100,
            "mu": 0.05,
            "sigma": 0.2,
            "T": 1.0,
            "n_steps": 52,
            "n_paths": 5,
        },
    },
    "var": {
        "label": "VaR",
        "module_id": "risk",
        "endpoint_combo_value": "core/types/currencies",
        "request_body": {
            "portfolio_value": 1000000,
            "volatility": 0.02,
            "confidence": 0.99,
            "horizon": 1,
        },
    },
    "bond-duration": {
        "label": "Bond Duration",
        "module_id": "instruments",
        "endpoint_combo_value": "instruments/bonds/duration",
        "request_body": {
            "face_value": 1000,
            "coupon_rate": 0.045,
            "yield_rate": 0.04,
            "years_to_maturity": 5,
            "payments_per_year": 2,
        },
    },
    "implied-volatility": {
        "label": "Implied Vol",
        "module_id": "volatility",
        "endpoint_combo_value": "volatility/options/implied-volatility",
        "request_body": {
            "spot": 100,
            "strike": 105,
            "risk_free_rate": 0.05,
            "time_to_maturity": 1.0,
            "option_type": "call",
            "market_price": 8.021352,
        },
    },
    "option-scenario-grid": {
        "label": "Scenario Grid",
        "module_id": "pricing",
        "endpoint_combo_value": "pricing/options/scenario-grid",
        "request_body": {
            "spot": 100,
            "strike": 105,
            "risk_free_rate": 0.05,
            "volatility": 0.2,
            "time_to_maturity": 1.0,
            "option_type": "call",
            "scenario_shocks": [-0.2, -0.1, 0, 0.1, 0.2],
        },
    },
    "heston": {
        "label": "Heston",
        "module_id": "models",
        "endpoint_combo_value": "core/types/currencies",
        "request_body": {
            "spot": 100,
            "strike": 105,
            "r": 0.05,
            "T": 1.0,
            "v0": 0.04,
            "kappa": 1.5,
            "theta": 0.04,
            "sigma_v": 0.3,
            "rho": -0.7,
            "option_type": "call",
        },
    },
}


def default_quantlib_state() -> dict[str, Any]:
    return {
        "active_module": DEFAULT_MODULE,
        "active_action": DEFAULT_ACTION,
        "active_request_body": copy.deepcopy(QUICK_ACTIONS[DEFAULT_ACTION]["request_body"]),
        "calculations": {},
        "last_calculation_id": None,
        "updated_at": "not started",
    }


def quantlib_safety_payload() -> dict[str, bool | str]:
    return {
        "local_artifacts_only": True,
        "external_quantlib_runtime": False,
        "external_api_required": False,
        "cloud_account_required": False,
        "subscription_required": False,
        "private_api_required": False,
        "external_network": False,
        "broker_mutation": False,
        "real_orders": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives_execution": False,
        "output": "local_request_response_artifacts",
    }


def normalize_quantlib_state(state: dict[str, Any], *, strict: bool = True) -> dict[str, Any]:
    default = default_quantlib_state()
    invalid_calculations = (
        {str(key): str(value) for key, value in state.get("invalid_calculations", {}).items()}
        if isinstance(state.get("invalid_calculations"), dict)
        else {}
    )
    if strict and invalid_calculations:
        first_key, first_value = next(iter(invalid_calculations.items()))
        raise QuantLibError(f"QuantLib state is invalid: {first_key}: {first_value}")

    active_module = _module_id_or_default(state.get("active_module"))
    active_action = _action_id_or_default(state.get("active_action"))
    raw_calculations = state.get("calculations")
    calculations: dict[str, dict[str, Any]] = {}
    if isinstance(raw_calculations, dict):
        if len(raw_calculations) > MAX_CALCULATIONS:
            raise QuantLibError(f"QuantLib calculations exceed limit of {MAX_CALCULATIONS}")
        for calculation_id, raw_calculation in raw_calculations.items():
            if not isinstance(raw_calculation, dict):
                if strict:
                    raise QuantLibError(f"Stored calculation {calculation_id} must be an object")
                invalid_calculations[str(calculation_id)] = "Stored calculation must be an object"
                continue
            try:
                calculation = normalize_calculation_record(
                    raw_calculation, fallback_id=str(calculation_id)
                )
            except QuantLibError as exc:
                if strict:
                    raise QuantLibError(
                        f"Stored calculation {calculation_id} is invalid: {exc}"
                    ) from exc
                invalid_calculations[str(calculation_id)] = str(exc)
                continue
            calculations[calculation["calculation_id"]] = calculation
    elif raw_calculations not in (None, {}):
        if strict:
            raise QuantLibError("Stored calculations must be an object")
        invalid_calculations["calculations"] = "Stored calculations must be an object"

    last_calculation_id = str(state.get("last_calculation_id") or "")
    if last_calculation_id not in calculations:
        last_calculation_id = _latest_calculation_id(calculations)
    active_request_body = _active_request_body(
        state.get("active_request_body"),
        active_action=active_action,
        calculations=calculations,
        last_calculation_id=last_calculation_id,
        invalid_calculations=invalid_calculations,
        strict=strict,
    )

    return {
        **default,
        "active_module": active_module,
        "active_action": active_action,
        "calculations": calculations,
        "last_calculation_id": last_calculation_id or None,
        "active_request_body": active_request_body,
        "invalid_calculations": invalid_calculations,
        "updated_at": str(state.get("updated_at") or default["updated_at"]),
    }


def quantlib_calculation_health_payload(state: dict[str, Any], root: Path) -> dict[str, Any]:
    """Return metadata-only health for local QuantLib calculation artifacts."""

    quant_state = normalize_quantlib_state(state, strict=False)
    rows = [
        _calculation_health_row(root, calculation)
        for calculation in sorted(
            quant_state["calculations"].values(),
            key=lambda calculation: str(calculation.get("created_at", "")),
            reverse=True,
        )
    ]
    recovery_queue = _calculation_health_recovery_queue(rows)
    latest = rows[0] if rows else {}
    return {
        "mode": "metadata_only_quantlib_calculation_health",
        "contract": "quantlib_calculation_health_v1",
        "generated_at": _utc_now(),
        "root": "artifacts/quantlib",
        "summary": {
            "calculation_count": len(rows),
            "complete_count": sum(1 for row in rows if row["health_state"] == "complete"),
            "partial_count": sum(
                1 for row in rows if row["health_state"].startswith("partial")
            ),
            "failed_count": sum(
                1 for row in rows if row["health_state"] == "failed_calculation"
            ),
            "missing_artifact_count": sum(int(row["missing_count"]) for row in rows),
            "supervision_ready_count": sum(1 for row in rows if row["supervision_ready"]),
            "invalid_calculation_count": len(quant_state["invalid_calculations"]),
            "active_action": str(quant_state.get("active_action") or ""),
            "active_module": str(quant_state.get("active_module") or ""),
            "latest_calculation_id": str(latest.get("calculation_id") or ""),
            "recovery_queue_count": len(recovery_queue),
            "destructive_action_count": 0,
        },
        "calculations": rows,
        "recovery_queue": recovery_queue,
        "recommended_actions": [
            {
                "action_id": "quantlib_compute",
                "endpoint": "/api/quantlib/compute",
                "method": "POST",
                "ready": True,
                "reason": "Run a deterministic local calculation to create or refresh QuantLib artifacts.",
            }
        ],
        "safety": {
            "local_only": True,
            "read_only": True,
            "metadata_only": True,
            "external_quantlib_runtime": False,
            "external_runtime": False,
            "external_api_required": False,
            "provider_calls": False,
            "external_network": False,
            "artifact_content_read": False,
            "artifact_content_indexing": False,
            "writes_local_artifacts": False,
            "automatic_repair_enabled": False,
            "destructive_actions_enabled": False,
            "secret_values_returned": False,
            "credentials_persisted": False,
            "broker_mutation": False,
            "real_orders": False,
            "real_balance": False,
            "margin": False,
            "leverage": False,
            "short": False,
            "derivatives_execution": False,
            "live_trading": False,
        },
    }


def quantlib_payload(
    state: dict[str, Any],
    context: dict[str, Any] | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    quant_state = normalize_quantlib_state(state, strict=False)
    active_action = QUICK_ACTIONS[quant_state["active_action"]]
    safe_context = sanitize_advanced_context(context)
    resolved_root = root or Path.cwd()
    return {
        "active_module": quant_state["active_module"],
        "active_action": quant_state["active_action"],
        "module_tree": [copy.deepcopy(module) for module in MODULE_TREE],
        "quick_actions": [
            {"action_id": action_id, **copy.deepcopy(action)}
            for action_id, action in QUICK_ACTIONS.items()
        ],
        "stats": {
            "modules": len(MODULE_TREE),
            "endpoint_count": sum(int(module["endpoint_count"]) for module in MODULE_TREE),
            "quick_actions": len(QUICK_ACTIONS),
            "local_runtime": "deterministic_stdlib_math",
        },
        "endpoint_combo_value": active_action["endpoint_combo_value"],
        "request_body": _request_with_context_defaults(
            quant_state["active_action"],
            copy.deepcopy(quant_state["active_request_body"]),
            safe_context,
        ),
        "calculations": _calculation_list(quant_state),
        "last_calculation": copy.deepcopy(
            quant_state["calculations"].get(quant_state["last_calculation_id"] or "")
        ),
        "invalid_calculations": quant_state["invalid_calculations"],
        "artifact_root": "artifacts/quantlib",
        "safety": quantlib_safety_payload(),
        "context": safe_context,
        "calculation_health": quantlib_calculation_health_payload(quant_state, resolved_root),
    }


def select_quantlib_module(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    quant_state = normalize_quantlib_state(copy.deepcopy(state))
    quant_state["active_module"] = _safe_module_id(request.get("module_id"))
    quant_state["updated_at"] = _utc_now()
    return quant_state


def select_quantlib_action(state: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    quant_state = normalize_quantlib_state(copy.deepcopy(state))
    action_id = _safe_action_id(request.get("action_id"))
    quant_state["active_action"] = action_id
    quant_state["active_module"] = str(QUICK_ACTIONS[action_id]["module_id"])
    quant_state["active_request_body"] = copy.deepcopy(QUICK_ACTIONS[action_id]["request_body"])
    quant_state["updated_at"] = _utc_now()
    return quant_state


def run_quantlib_calculation(
    state: dict[str, Any],
    request: dict[str, Any],
    root: Path,
    context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    quant_state = normalize_quantlib_state(copy.deepcopy(state))
    if len(quant_state["calculations"]) >= MAX_CALCULATIONS:
        raise QuantLibError(f"QuantLib calculations exceed limit of {MAX_CALCULATIONS}")
    action_id = _safe_action_id(request.get("action_id") or quant_state["active_action"])
    raw_request_body = (
        QUICK_ACTIONS[action_id]["request_body"]
        if request.get("request_body") is None
        else request.get("request_body")
    )
    request_body = _safe_request_body(raw_request_body)
    safe_context = sanitize_advanced_context(context)
    if request.get("request_body") is None:
        request_body = _request_with_context_defaults(action_id, request_body, safe_context)
    response_body = _compute_action(action_id, request_body)
    response_body["context"] = context_for_artifact(safe_context)
    response_body["source_provenance"] = _source_provenance_for_output(safe_context)
    response_body["artifact_inputs"] = _artifact_inputs_for_output(safe_context)
    response_body["output_mode"] = "local_context_calculation"
    now = _utc_now()
    calculation_id = f"qlib-{datetime.now(tz=UTC).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    artifact_dir = f"artifacts/quantlib/{calculation_id}"
    calculation = normalize_calculation_record(
        {
            "calculation_id": calculation_id,
            "action_id": action_id,
            "action_label": QUICK_ACTIONS[action_id]["label"],
            "status": "computed",
            "endpoint_combo_value": QUICK_ACTIONS[action_id]["endpoint_combo_value"],
            "request_body": request_body,
            "response_body": response_body,
            "artifact_dir": artifact_dir,
            "artifacts": {
                "request": f"{artifact_dir}/request.json",
                "response": f"{artifact_dir}/response.json",
                "context": f"{artifact_dir}/context.json",
                "manifest": f"{artifact_dir}/manifest.json",
                "report": f"{artifact_dir}/report.md",
                "error_log": f"{artifact_dir}/error.log",
            },
            "created_at": now,
        }
    )
    _write_calculation_artifacts(root, calculation)
    quant_state["calculations"][calculation_id] = calculation
    quant_state["last_calculation_id"] = calculation_id
    quant_state["active_request_body"] = request_body
    quant_state["active_action"] = action_id
    quant_state["active_module"] = str(QUICK_ACTIONS[action_id]["module_id"])
    quant_state["updated_at"] = now
    return quant_state, calculation


def disabled_quantlib_response(action: str) -> dict[str, Any]:
    return {
        "action": action,
        "state": "disabled",
        "reason": "External QuantLib or external API execution is not enabled in the local calculator.",
        "safety": quantlib_safety_payload(),
    }


def normalize_calculation_record(raw: dict[str, Any], fallback_id: str | None = None) -> dict[str, Any]:
    calculation_id = _safe_id(raw.get("calculation_id") or fallback_id, "Calculation id")
    action_id = _safe_action_id(raw.get("action_id"))
    status = _safe_text(raw.get("status"), "Calculation status", 40)
    if status != "computed":
        raise QuantLibError("Calculation status is not allowed")
    artifacts = raw.get("artifacts")
    if not isinstance(artifacts, dict):
        raise QuantLibError("Calculation artifacts must be an object")
    normalized_artifacts = {
        "request": _safe_artifact_path(
            artifacts.get("request"), calculation_id, suffix="request.json"
        ),
        "response": _safe_artifact_path(
            artifacts.get("response"), calculation_id, suffix="response.json"
        ),
        "report": _safe_artifact_path(
            artifacts.get("report"), calculation_id, suffix="report.md"
        ),
        "error_log": _safe_artifact_path(
            artifacts.get("error_log"), calculation_id, suffix="error.log"
        ),
    }
    for key, suffix in {"context": "context.json", "manifest": "manifest.json"}.items():
        if artifacts.get(key):
            normalized_artifacts[key] = _safe_artifact_path(
                artifacts.get(key), calculation_id, suffix=suffix
            )

    return {
        "calculation_id": calculation_id,
        "action_id": action_id,
        "action_label": _safe_text(raw.get("action_label"), "Action label", 80),
        "status": status,
        "endpoint_combo_value": _safe_text(
            raw.get("endpoint_combo_value"), "Endpoint combo", 120
        ),
        "request_body": _safe_request_body(raw.get("request_body", {})),
        "response_body": _safe_response_body(raw.get("response_body", {})),
        "artifact_dir": _safe_artifact_path(raw.get("artifact_dir"), calculation_id),
        "artifacts": normalized_artifacts,
        "created_at": _safe_text(raw.get("created_at"), "Calculation timestamp", 80),
    }


def _compute_action(action_id: str, request_body: dict[str, Any]) -> dict[str, Any]:
    if action_id == "bs-price":
        return _black_scholes(request_body)
    if action_id == "gbm-sim":
        return _gbm_simulation(request_body)
    if action_id == "var":
        return _value_at_risk(request_body)
    if action_id == "bond-duration":
        return _bond_duration(request_body)
    if action_id == "implied-volatility":
        return _implied_volatility(request_body)
    if action_id == "option-scenario-grid":
        return _option_scenario_grid(request_body)
    if action_id == "heston":
        return _heston_proxy(request_body)
    raise QuantLibError("Unsupported QuantLib action")


def _request_with_context_defaults(
    action_id: str,
    request_body: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    payload = copy.deepcopy(request_body)
    latest_price = str(context.get("summary", {}).get("latest_price") or "")
    try:
        price = float(latest_price)
    except (TypeError, ValueError):
        return payload
    if price <= 0 or not math.isfinite(price):
        return payload
    if action_id in {"bs-price", "heston", "option-scenario-grid"} and "spot" in payload:
        payload["spot"] = price
    if action_id == "gbm-sim" and "S0" in payload:
        payload["S0"] = price
    if action_id == "var" and "portfolio_value" in payload:
        payload["portfolio_value"] = price * 10
    payload["context_source"] = str(context.get("summary", {}).get("primary_cache_path") or "provider_cache")
    return payload


def _black_scholes(request_body: dict[str, Any]) -> dict[str, Any]:
    spot = _positive_float(request_body, "spot")
    strike = _positive_float(request_body, "strike")
    rate = _bounded_float(request_body, "risk_free_rate", -1.0, 1.0)
    volatility = _positive_float(request_body, "volatility", upper=5.0)
    maturity = _positive_float(request_body, "time_to_maturity", upper=100.0)
    option_type = _option_type(request_body.get("option_type"))
    d1 = (math.log(spot / strike) + (rate + volatility**2 / 2) * maturity) / (
        volatility * math.sqrt(maturity)
    )
    d2 = d1 - volatility * math.sqrt(maturity)
    normal = NormalDist()
    if option_type == "call":
        price = spot * normal.cdf(d1) - strike * math.exp(-rate * maturity) * normal.cdf(d2)
        delta = normal.cdf(d1)
    else:
        price = strike * math.exp(-rate * maturity) * normal.cdf(-d2) - spot * normal.cdf(-d1)
        delta = normal.cdf(d1) - 1
    gamma = normal.pdf(d1) / (spot * volatility * math.sqrt(maturity))
    vega = spot * normal.pdf(d1) * math.sqrt(maturity) / 100
    return {
        "kind": "black_scholes_price",
        "option_type": option_type,
        "price": _rounded(price),
        "delta": _rounded(delta),
        "gamma": _rounded(gamma),
        "vega_per_1pct": _rounded(vega),
        "d1": _rounded(d1),
        "d2": _rounded(d2),
        "runtime": "local_stdlib_math",
    }


def _gbm_simulation(request_body: dict[str, Any]) -> dict[str, Any]:
    spot = _positive_float(request_body, "S0")
    mu = _bounded_float(request_body, "mu", -2.0, 2.0)
    sigma = _positive_float(request_body, "sigma", upper=5.0)
    total_time = _positive_float(request_body, "T", upper=100.0)
    n_steps = _bounded_int(request_body, "n_steps", 1, 512)
    n_paths = _bounded_int(request_body, "n_paths", 1, 20)
    dt = total_time / n_steps
    rng = random.Random(42)
    paths: list[list[str]] = []
    terminal_values: list[float] = []
    for _ in range(n_paths):
        current = spot
        path = [_rounded(current)]
        for _ in range(n_steps):
            shock = rng.gauss(0, 1)
            current *= math.exp((mu - sigma**2 / 2) * dt + sigma * math.sqrt(dt) * shock)
            path.append(_rounded(current))
        paths.append(path)
        terminal_values.append(current)
    return {
        "kind": "gbm_simulation",
        "seed": 42,
        "path_count": n_paths,
        "step_count": n_steps,
        "terminal_mean": _rounded(sum(terminal_values) / len(terminal_values)),
        "terminal_min": _rounded(min(terminal_values)),
        "terminal_max": _rounded(max(terminal_values)),
        "paths": paths,
        "runtime": "local_stdlib_math",
    }


def _value_at_risk(request_body: dict[str, Any]) -> dict[str, Any]:
    portfolio_value = _positive_float(request_body, "portfolio_value")
    volatility = _positive_float(request_body, "volatility", upper=5.0)
    confidence = _bounded_float(request_body, "confidence", 0.5, 0.9999)
    horizon = _positive_float(request_body, "horizon", upper=3650.0)
    z_score = NormalDist().inv_cdf(confidence)
    var_amount = portfolio_value * volatility * math.sqrt(horizon) * z_score
    return {
        "kind": "parametric_var",
        "confidence": _rounded(confidence),
        "z_score": _rounded(z_score),
        "horizon": _rounded(horizon),
        "var": _rounded(var_amount),
        "var_pct": _rounded(var_amount / portfolio_value),
        "runtime": "local_stdlib_math",
    }


def _bond_duration(request_body: dict[str, Any]) -> dict[str, Any]:
    face_value = _positive_float(request_body, "face_value")
    coupon_rate = _bounded_float(request_body, "coupon_rate", 0.0, 1.0)
    yield_rate = _bounded_float(request_body, "yield_rate", -0.99, 1.0)
    years_to_maturity = _positive_float(request_body, "years_to_maturity", upper=100.0)
    payments_per_year = _bounded_int(request_body, "payments_per_year", 1, 12)
    periods = _bounded_int(
        {"periods": years_to_maturity * payments_per_year},
        "periods",
        1,
        1200,
    )
    period_yield = yield_rate / payments_per_year
    if period_yield <= -1:
        raise QuantLibError("yield_rate is outside allowed range")
    coupon = face_value * coupon_rate / payments_per_year
    cashflows = [coupon for _ in range(periods)]
    cashflows[-1] += face_value
    present_values = [
        cashflow / ((1 + period_yield) ** period)
        for period, cashflow in enumerate(cashflows, start=1)
    ]
    price = sum(present_values)
    weighted_time = sum(
        (period / payments_per_year) * present_value
        for period, present_value in enumerate(present_values, start=1)
    )
    macaulay_duration = weighted_time / price
    modified_duration = macaulay_duration / (1 + period_yield)
    convexity = (
        sum(
            period * (period + 1) * present_value
            for period, present_value in enumerate(present_values, start=1)
        )
        / (price * (payments_per_year**2) * ((1 + period_yield) ** 2))
    )
    return {
        "kind": "fixed_income_duration",
        "price": _rounded(price),
        "macaulay_duration_years": _rounded(macaulay_duration),
        "modified_duration_years": _rounded(modified_duration),
        "convexity_years": _rounded(convexity),
        "basis_point_value": _rounded(price * modified_duration * 0.0001),
        "periods": periods,
        "payments_per_year": payments_per_year,
        "runtime": "local_stdlib_math",
    }


def _implied_volatility(request_body: dict[str, Any]) -> dict[str, Any]:
    spot = _positive_float(request_body, "spot")
    strike = _positive_float(request_body, "strike")
    rate = _bounded_float(request_body, "risk_free_rate", -1.0, 1.0)
    maturity = _positive_float(request_body, "time_to_maturity", upper=100.0)
    option_type = _option_type(request_body.get("option_type"))
    market_price = _positive_float(request_body, "market_price", upper=max(spot, strike) * 10)

    lower_vol = 1e-6
    upper_vol = 5.0
    lower_price = _black_scholes_price(
        spot=spot,
        strike=strike,
        rate=rate,
        volatility=lower_vol,
        maturity=maturity,
        option_type=option_type,
    )
    upper_price = _black_scholes_price(
        spot=spot,
        strike=strike,
        rate=rate,
        volatility=upper_vol,
        maturity=maturity,
        option_type=option_type,
    )
    if market_price < lower_price or market_price > upper_price:
        raise QuantLibError("market_price is outside local implied-volatility bounds")

    midpoint = lower_vol
    model_price = lower_price
    iterations = 0
    for iterations in range(1, 81):
        midpoint = (lower_vol + upper_vol) / 2
        model_price = _black_scholes_price(
            spot=spot,
            strike=strike,
            rate=rate,
            volatility=midpoint,
            maturity=maturity,
            option_type=option_type,
        )
        if abs(model_price - market_price) <= 1e-8:
            break
        if model_price < market_price:
            lower_vol = midpoint
        else:
            upper_vol = midpoint

    pricing_error = model_price - market_price
    if abs(pricing_error) < 0.5 * 10**-QUANT:
        pricing_error = 0.0

    return {
        "kind": "black_scholes_implied_volatility",
        "option_type": option_type,
        "market_price": _rounded(market_price),
        "model_price": _rounded(model_price),
        "pricing_error": _rounded(pricing_error),
        "implied_volatility": _rounded(midpoint),
        "iterations": iterations,
        "runtime": "local_stdlib_math",
    }


def _option_scenario_grid(request_body: dict[str, Any]) -> dict[str, Any]:
    spot = _positive_float(request_body, "spot")
    strike = _positive_float(request_body, "strike")
    rate = _bounded_float(request_body, "risk_free_rate", -1.0, 1.0)
    volatility = _positive_float(request_body, "volatility", upper=5.0)
    maturity = _positive_float(request_body, "time_to_maturity", upper=100.0)
    option_type = _option_type(request_body.get("option_type"))
    shocks = _scenario_shocks(request_body.get("scenario_shocks"))
    base_price = _black_scholes_price(
        spot=spot,
        strike=strike,
        rate=rate,
        volatility=volatility,
        maturity=maturity,
        option_type=option_type,
    )
    rows = []
    scenario_prices = []
    for shock in shocks:
        scenario_spot = spot * (1 + shock)
        scenario_price = _black_scholes_price(
            spot=scenario_spot,
            strike=strike,
            rate=rate,
            volatility=volatility,
            maturity=maturity,
            option_type=option_type,
        )
        scenario_prices.append(scenario_price)
        rows.append(
            {
                "shock_pct": _rounded(shock),
                "scenario_spot": _rounded(scenario_spot),
                "model_price": _rounded(scenario_price),
                "model_pnl": _rounded(scenario_price - base_price),
            }
        )
    return {
        "kind": "black_scholes_scenario_grid",
        "option_type": option_type,
        "base_spot": _rounded(spot),
        "base_price": _rounded(base_price),
        "scenario_count": len(rows),
        "min_model_price": _rounded(min(scenario_prices)),
        "max_model_price": _rounded(max(scenario_prices)),
        "rows": rows,
        "runtime": "local_stdlib_math",
    }


def _heston_proxy(request_body: dict[str, Any]) -> dict[str, Any]:
    spot = _positive_float(request_body, "spot")
    strike = _positive_float(request_body, "strike")
    rate = _bounded_float(request_body, "r", -1.0, 1.0)
    maturity = _positive_float(request_body, "T", upper=100.0)
    v0 = _positive_float(request_body, "v0", upper=25.0)
    kappa = _positive_float(request_body, "kappa", upper=50.0)
    theta = _positive_float(request_body, "theta", upper=25.0)
    sigma_v = _positive_float(request_body, "sigma_v", upper=10.0)
    rho = _bounded_float(request_body, "rho", -0.999, 0.999)
    option_type = _option_type(request_body.get("option_type"))
    effective_variance = max(1e-8, theta + (v0 - theta) * math.exp(-kappa * maturity))
    effective_vol = math.sqrt(effective_variance) * max(0.25, 1 + rho * sigma_v * 0.1)
    bs_request = {
        "spot": spot,
        "strike": strike,
        "risk_free_rate": rate,
        "volatility": effective_vol,
        "time_to_maturity": maturity,
        "option_type": option_type,
    }
    proxy = _black_scholes(bs_request)
    return {
        "kind": "heston_proxy",
        "price": proxy["price"],
        "effective_volatility": _rounded(effective_vol),
        "variance_proxy": _rounded(effective_variance),
        "note": "local deterministic proxy; not external QuantLib runtime",
        "runtime": "local_stdlib_math",
    }


def _black_scholes_price(
    *,
    spot: float,
    strike: float,
    rate: float,
    volatility: float,
    maturity: float,
    option_type: str,
) -> float:
    d1 = (math.log(spot / strike) + (rate + volatility**2 / 2) * maturity) / (
        volatility * math.sqrt(maturity)
    )
    d2 = d1 - volatility * math.sqrt(maturity)
    normal = NormalDist()
    if option_type == "call":
        return spot * normal.cdf(d1) - strike * math.exp(-rate * maturity) * normal.cdf(d2)
    return strike * math.exp(-rate * maturity) * normal.cdf(-d2) - spot * normal.cdf(-d1)


def _write_calculation_artifacts(root: Path, calculation: dict[str, Any]) -> None:
    artifact_dir = root / calculation["artifact_dir"]
    if not artifact_dir.resolve().is_relative_to(root.resolve()):
        raise QuantLibError("Artifact path must stay inside repository")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json_artifact(root, Path(calculation["artifacts"]["request"]), calculation["request_body"])
    _write_json_artifact(root, Path(calculation["artifacts"]["response"]), calculation["response_body"])
    if calculation["artifacts"].get("context"):
        _write_json_artifact(
            root,
            Path(calculation["artifacts"]["context"]),
            _context_artifact_payload(calculation),
        )
    if calculation["artifacts"].get("manifest"):
        _write_json_artifact(
            root,
            Path(calculation["artifacts"]["manifest"]),
            _manifest_artifact_payload(calculation),
        )
    report = [
        f"# {calculation['action_label']} Local QuantLib Calculation",
        "",
        f"- Calculation: `{calculation['calculation_id']}`",
        f"- Endpoint preset: `{calculation['endpoint_combo_value']}`",
        f"- Output mode: `{calculation['response_body'].get('output_mode', 'local_request_response')}`",
        f"- Context sources: `{len(calculation['response_body'].get('source_provenance', []))}`",
        f"- Artifact inputs: `{len(calculation['response_body'].get('artifact_inputs', []))}`",
        "- External QuantLib runtime: `false`",
        "- External API required: `false`",
        "- Broker mutation: `false`",
        "",
        "This artifact is generated by the clean-room local calculator.",
    ]
    _write_text_artifact(root, Path(calculation["artifacts"]["report"]), "\n".join(report) + "\n")
    _write_text_artifact(root, Path(calculation["artifacts"]["error_log"]), "")


def _calculation_health_row(root: Path, calculation: dict[str, Any]) -> dict[str, Any]:
    calculation_id = str(calculation["calculation_id"])
    file_rows: list[dict[str, Any]] = []
    mtimes: list[float] = []
    artifact_bytes = 0
    for name, relative_path in _calculation_artifact_files(calculation).items():
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
    if str(calculation.get("status") or "") != "computed":
        health_state = "failed_calculation"
    elif missing:
        health_state = "partial_missing_artifacts"
    else:
        health_state = "complete"
    return {
        "calculation_id": calculation_id,
        "action_id": str(calculation.get("action_id") or ""),
        "action_label": str(calculation.get("action_label") or ""),
        "status": str(calculation.get("status") or ""),
        "endpoint_combo_value": str(calculation.get("endpoint_combo_value") or ""),
        "artifact_dir": str(calculation.get("artifact_dir") or ""),
        "created_at": str(calculation.get("created_at") or ""),
        "health_state": health_state,
        "expected_count": len(file_rows),
        "present_count": len(present),
        "missing_count": len(missing),
        "present_artifacts": present,
        "missing_artifacts": missing,
        "files": file_rows,
        "request_artifact_path": str(by_name["request"]["path"]),
        "request_artifact_exists": bool(by_name["request"]["exists"]),
        "response_artifact_path": str(by_name["response"]["path"]),
        "response_artifact_exists": bool(by_name["response"]["exists"]),
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
        "supervision_ready": not missing and calculation["status"] == "computed",
        "recovery_hint": (
            "ready_for_agent_supervision"
            if not missing and calculation["status"] == "computed"
            else "rerun_local_calculation_to_regenerate_missing_artifacts"
        ),
        "artifact_content_read": False,
        "external_quantlib_runtime": False,
        "destructive_actions_enabled": False,
    }


def _calculation_health_recovery_queue(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return [
            {
                "queue_id": "quantlib_calculation_health:none",
                "calculation_id": "",
                "artifact_path": "artifacts/quantlib",
                "recommended_action": "quantlib_compute",
                "endpoint": "/api/quantlib/compute",
                "method": "POST",
                "reason": "No local QuantLib calculations exist; run a deterministic local calculation first.",
                "destructive_action_required": False,
                "writes_local_artifacts": True,
            }
        ]
    queue = []
    for row in rows:
        if int(row["missing_count"]) == 0 and row["status"] == "computed":
            continue
        queue.append(
            {
                "queue_id": f"quantlib_calculation_health:{row['calculation_id']}:artifacts",
                "calculation_id": row["calculation_id"],
                "artifact_path": row["artifact_dir"],
                "recommended_action": "quantlib_compute",
                "endpoint": "/api/quantlib/compute",
                "method": "POST",
                "reason": "Rerun the local deterministic calculation to regenerate missing calculation artifacts.",
                "destructive_action_required": False,
                "writes_local_artifacts": True,
            }
        )
    return queue


def _calculation_artifact_files(calculation: dict[str, Any]) -> dict[str, str]:
    calculation_id = str(calculation["calculation_id"])
    artifacts = calculation.get("artifacts") if isinstance(calculation.get("artifacts"), dict) else {}
    return {
        "request": str(
            artifacts.get("request") or f"artifacts/quantlib/{calculation_id}/request.json"
        ),
        "response": str(
            artifacts.get("response") or f"artifacts/quantlib/{calculation_id}/response.json"
        ),
        "context": str(
            artifacts.get("context") or f"artifacts/quantlib/{calculation_id}/context.json"
        ),
        "manifest": str(
            artifacts.get("manifest") or f"artifacts/quantlib/{calculation_id}/manifest.json"
        ),
        "report": str(
            artifacts.get("report") or f"artifacts/quantlib/{calculation_id}/report.md"
        ),
        "error_log": str(
            artifacts.get("error_log") or f"artifacts/quantlib/{calculation_id}/error.log"
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
    artifacts = context.get("artifacts", [])
    if not isinstance(artifacts, list):
        artifacts = []
    focused_artifacts = sorted(
        (artifact for artifact in artifacts if isinstance(artifact, dict)),
        key=_artifact_input_priority,
    )[:8]
    for artifact in focused_artifacts:
        rows.append(
            {
                "artifact_id": artifact.get("artifact_id", ""),
                "kind": artifact.get("kind", ""),
                "path": artifact.get("path", ""),
                "bytes": artifact.get("bytes", 0),
            }
        )
    return rows


def _artifact_input_priority(artifact: dict[str, Any]) -> tuple[int, int, str]:
    kind_priority = {
        "backtest": 0,
        "portfolio": 1,
        "paper": 2,
        "news": 3,
        "nodes": 4,
        "code": 5,
        "quant_lab": 6,
        "quantlib": 7,
    }
    file_priority = {
        "summary.json": 0,
        "manifest.json": 1,
        "report.md": 2,
        "trades.csv": 3,
        "orders.jsonl": 4,
        "fills.jsonl": 5,
        "ledger.jsonl": 6,
    }
    kind = str(artifact.get("kind") or "")
    path = str(artifact.get("path") or "")
    filename = path.rsplit("/", 1)[-1]
    return (kind_priority.get(kind, 99), file_priority.get(filename, 50), path)


def _context_artifact_payload(calculation: dict[str, Any]) -> dict[str, Any]:
    return {
        "calculation_id": calculation["calculation_id"],
        "action_id": calculation["action_id"],
        "action_label": calculation["action_label"],
        "generated_at": calculation["created_at"],
        "context": calculation["response_body"].get("context", {}),
        "source_provenance": calculation["response_body"].get("source_provenance", []),
        "artifact_inputs": calculation["response_body"].get("artifact_inputs", []),
        "output_mode": calculation["response_body"].get(
            "output_mode", "local_request_response"
        ),
    }


def _manifest_artifact_payload(calculation: dict[str, Any]) -> dict[str, Any]:
    return {
        "calculation_id": calculation["calculation_id"],
        "action_id": calculation["action_id"],
        "action_label": calculation["action_label"],
        "status": calculation["status"],
        "created_at": calculation["created_at"],
        "endpoint_combo_value": calculation["endpoint_combo_value"],
        "artifact_contract": calculation["artifacts"],
        "source_provenance": calculation["response_body"].get("source_provenance", []),
        "artifact_inputs": calculation["response_body"].get("artifact_inputs", []),
        "safety": quantlib_safety_payload(),
        "clean_room": {
            "external_quantlib_runtime": False,
            "external_api_required": False,
            "external_network": False,
            "broker_mutation": False,
            "credential_material": False,
        },
    }


def _write_json_artifact(root: Path, relative_path: Path, payload: dict[str, Any]) -> None:
    path = root / relative_path
    if not path.resolve().is_relative_to(root.resolve()):
        raise QuantLibError("Artifact path must stay inside repository")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def _write_text_artifact(root: Path, relative_path: Path, payload: str) -> None:
    path = root / relative_path
    if not path.resolve().is_relative_to(root.resolve()):
        raise QuantLibError("Artifact path must stay inside repository")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")


def _calculation_list(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "calculation_id": calculation["calculation_id"],
            "action_id": calculation["action_id"],
            "action_label": calculation["action_label"],
            "status": calculation["status"],
            "artifact_dir": calculation["artifact_dir"],
            "created_at": calculation["created_at"],
        }
        for calculation in sorted(
            state["calculations"].values(),
            key=lambda calculation: str(calculation.get("created_at", "")),
            reverse=True,
        )
    ]


def _active_request_body(
    raw: Any,
    *,
    active_action: str,
    calculations: dict[str, dict[str, Any]],
    last_calculation_id: str,
    invalid_calculations: dict[str, str],
    strict: bool,
) -> dict[str, Any]:
    if raw is not None:
        try:
            return _safe_request_body(raw)
        except QuantLibError as exc:
            if strict:
                raise QuantLibError(f"Active request body is invalid: {exc}") from exc
            invalid_calculations["active_request_body"] = str(exc)
    if (
        last_calculation_id in calculations
        and calculations[last_calculation_id]["action_id"] == active_action
    ):
        return copy.deepcopy(calculations[last_calculation_id]["request_body"])
    return copy.deepcopy(QUICK_ACTIONS[active_action]["request_body"])


def _safe_request_body(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        if len(raw) > MAX_JSON_LENGTH:
            raise QuantLibError("Request body exceeds limit")
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise QuantLibError("Request body must be valid JSON") from exc
    if not isinstance(raw, dict):
        raise QuantLibError("Request body must be an object")
    for key in raw:
        safe_key = _safe_text(key, "Request key", 80)
        if _looks_like_secret_key(safe_key):
            raise QuantLibError("Request key appears to request credential material")
    text = json.dumps(raw, sort_keys=True)
    if len(text) > MAX_JSON_LENGTH:
        raise QuantLibError("Request body exceeds limit")
    if _contains_secret(text):
        raise QuantLibError("Request body appears to contain credential material")
    if _contains_forbidden_runtime_intent(text):
        raise QuantLibError("Request body contains forbidden runtime intent")
    return copy.deepcopy(raw)


def _safe_response_body(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise QuantLibError("Response body must be an object")
    text = json.dumps(raw, sort_keys=True)
    if _contains_secret(text) or _contains_forbidden_runtime_intent(text):
        raise QuantLibError("Response body contains unsafe material")
    return copy.deepcopy(raw)


def _positive_float(payload: dict[str, Any], key: str, *, upper: float = 1_000_000_000.0) -> float:
    value = _numeric(payload, key)
    if value <= 0:
        raise QuantLibError(f"{key} must be positive")
    if value > upper:
        raise QuantLibError(f"{key} exceeds limit")
    return value


def _bounded_float(payload: dict[str, Any], key: str, lower: float, upper: float) -> float:
    value = _numeric(payload, key)
    if value < lower or value > upper:
        raise QuantLibError(f"{key} is outside allowed range")
    return value


def _bounded_int(payload: dict[str, Any], key: str, lower: int, upper: int) -> int:
    value = _numeric(payload, key)
    if not float(value).is_integer():
        raise QuantLibError(f"{key} must be an integer")
    number = int(value)
    if number < lower or number > upper:
        raise QuantLibError(f"{key} is outside allowed range")
    return number


def _numeric(payload: dict[str, Any], key: str) -> float:
    if key not in payload:
        raise QuantLibError(f"{key} is required")
    try:
        value = float(payload[key])
    except (TypeError, ValueError):
        raise QuantLibError(f"{key} must be numeric") from None
    if not math.isfinite(value):
        raise QuantLibError(f"{key} must be finite")
    return value


def _option_type(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value not in {"call", "put"}:
        raise QuantLibError("option_type must be call or put")
    return value


def _scenario_shocks(raw: Any) -> list[float]:
    if raw is None:
        raw = [-0.2, -0.1, 0, 0.1, 0.2]
    if not isinstance(raw, list):
        raise QuantLibError("scenario_shocks must be an array")
    if len(raw) < 3 or len(raw) > 9:
        raise QuantLibError("scenario_shocks must contain 3 to 9 values")
    shocks: list[float] = []
    for item in raw:
        try:
            shock = float(item)
        except (TypeError, ValueError):
            raise QuantLibError("scenario_shocks must contain numeric values") from None
        if not math.isfinite(shock) or shock <= -1.0 or shock > 3.0:
            raise QuantLibError("scenario_shocks values are outside allowed range")
        shocks.append(shock)
    return shocks


def _safe_artifact_path(raw: Any, calculation_id: str, suffix: str | None = None) -> str:
    value = str(raw or "").strip().replace("\\", "/")
    if not value:
        value = f"artifacts/quantlib/{calculation_id}/{suffix}" if suffix else f"artifacts/quantlib/{calculation_id}"
    if value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise QuantLibError("Artifact path must be repository-local")
    if ".." in value.split("/"):
        raise QuantLibError("Artifact path cannot traverse directories")
    base = f"artifacts/quantlib/{calculation_id}"
    if value != base and not value.startswith(f"{base}/"):
        raise QuantLibError("Artifact path must stay under its calculation directory")
    return value


def _safe_action_id(raw: Any) -> str:
    value = str(raw or "").strip()
    if value not in QUICK_ACTIONS:
        raise QuantLibError("QuantLib action is not allowed")
    return value


def _action_id_or_default(raw: Any) -> str:
    value = str(raw or "").strip()
    return value if value in QUICK_ACTIONS else DEFAULT_ACTION


def _safe_module_id(raw: Any) -> str:
    value = str(raw or "").strip()
    if value not in MODULE_IDS:
        raise QuantLibError("QuantLib module is not allowed")
    return value


def _module_id_or_default(raw: Any) -> str:
    value = str(raw or "").strip()
    return value if value in MODULE_IDS else DEFAULT_MODULE


def _safe_id(raw: Any, label: str) -> str:
    value = str(raw or "").strip()
    if not value or len(value) > 80:
        raise QuantLibError(f"{label} is required")
    if not all(ch.isalnum() or ch in {"-", "_"} for ch in value):
        raise QuantLibError(f"{label} is invalid")
    return value


def _safe_text(raw: Any, label: str, max_length: int) -> str:
    value = str(raw or "").strip()
    if not value:
        raise QuantLibError(f"{label} is required")
    if len(value) > max_length:
        raise QuantLibError(f"{label} exceeds limit")
    if _contains_secret(value):
        raise QuantLibError(f"{label} appears to contain credential material")
    return value


def _latest_calculation_id(calculations: dict[str, dict[str, Any]]) -> str:
    if not calculations:
        return ""
    return max(calculations.values(), key=lambda item: str(item.get("created_at", "")))[
        "calculation_id"
    ]


def _rounded(value: float) -> str:
    return f"{value:.{QUANT}f}"


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
    return datetime.now(tz=UTC).isoformat(timespec="seconds")
