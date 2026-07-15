"""M24.4 — local backtest parameter optimization (grid search).

Verifies the optimizer ranks bounded parameter combinations on a shared closed-candle
snapshot, respects the strategy schema (bounds + constraints), caps combination count,
writes local artifacts, and stays behind the non-live safety gates. Also checks the
endpoint wiring and that the action is discoverable + safe in the agent contract.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import backtest
from otto.local_terminal.server import create_app


def test_run_optimize_default_grid_ranks_and_writes(tmp_path: Path) -> None:
    result = backtest.run_optimize({"strategy": "sma_cross"}, tmp_path)

    assert result["summary"]["mode"] == "local_grid_search"
    assert result["summary"]["evaluated_count"] >= 2

    ranked = result["ranked"]
    returns = [Decimal(str(row["return_pct"])) for row in ranked]
    assert returns == sorted(returns, reverse=True)  # ranked by return, descending
    assert [row["rank"] for row in ranked] == list(range(1, len(ranked) + 1))
    assert result["best"] == ranked[0]

    artifact_dir = tmp_path / result["artifact_dir"]
    for name in ("optimize.json", "rows.csv", "report.md", "manifest.json"):
        assert (artifact_dir / name).is_file()

    assert result["safety"]["live_orders"] is False
    assert result["safety"]["broker_routing"] is False
    assert result["safety"]["deploy"] is False
    assert result["summary"]["lookahead_guard"] == "signals_on_close_fills_next_open"


def test_run_optimize_respects_bounds_and_constraint(tmp_path: Path) -> None:
    result = backtest.run_optimize(
        {
            "strategy": "sma_cross",
            "parameter_grid": {"fast_window": [3, 5, 999], "slow_window": [10, 20]},
        },
        tmp_path,
    )
    grid = result["parameter_grid"]
    assert 999 not in grid["fast_window"]  # above the schema maximum (100) → dropped
    assert grid["fast_window"] == [3, 5]
    for row in result["ranked"]:
        assert row["slow_window"] > row["fast_window"]  # strategy constraint upheld


def test_run_optimize_caps_combinations(tmp_path: Path) -> None:
    result = backtest.run_optimize(
        {
            "strategy": "sma_cross",
            "parameter_grid": {
                "fast_window": list(range(2, 20)),
                "slow_window": list(range(21, 40)),
            },
        },
        tmp_path,
    )
    assert result["summary"]["evaluated_count"] <= backtest.OPTIMIZE_MAX_COMBINATIONS
    for key in ("fast_window", "slow_window"):
        assert len(result["parameter_grid"][key]) <= backtest.OPTIMIZE_MAX_VALUES_PER_PARAM


def test_optimize_endpoint_and_agent_contract() -> None:
    client = TestClient(create_app())

    response = client.post("/api/backtest/optimize", json={"strategy": "sma_cross"})
    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["mode"] == "local_grid_search"
    assert body["best"]["rank"] == 1

    contract = client.get("/api/agent-contract").json()
    actions = {action["action_id"]: action for action in contract["actions"]}
    assert "backtest_optimize" in actions
    assert actions["backtest_optimize"]["disabled_by_safety"] is False
    assert actions["backtest_optimize"]["method"] == "POST"
    assert actions["backtest_optimize"]["safety_class"] == "closed_candle_local_research"
