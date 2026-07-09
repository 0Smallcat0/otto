import csv
import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.backtest import (
    BacktestError,
    backtest_artifact_health_payload,
    backtest_data_readiness_payload,
    backtest_run_index_payload,
    backtest_strategy_catalog,
    default_backtest_config,
    generate_closed_candles,
    normalize_strategy_parameters,
    run_channel_breakout,
    run_momentum_continuation,
    run_rsi_reversion,
    run_sma_mean_reversion,
    run_sma_cross,
    run_volatility_reversion,
    write_backtest_comparison_packet,
    walk_forward_windows,
)
from src.local_terminal.storage import LocalStateStore


def test_backtest_api_writes_required_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/backtest/run",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "fast_window": 3,
            "slow_window": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    run_dir = tmp_path / payload["artifact_dir"]
    assert (run_dir / "config.json").is_file()
    assert (run_dir / "data_snapshot.json").is_file()
    assert (run_dir / "summary.json").is_file()
    assert (run_dir / "trades.csv").is_file()
    assert (run_dir / "signals.csv").is_file()
    assert (run_dir / "indicators.json").is_file()
    assert (run_dir / "returns_analysis.json").is_file()
    assert (run_dir / "returns_curve.csv").is_file()
    assert (run_dir / "provenance.json").is_file()
    assert (run_dir / "report.md").is_file()
    assert (run_dir / "manifest.json").is_file()
    assert payload["summary"]["lookahead_guard"] == "signals_on_close_fills_next_open"
    assert payload["summary"]["same_candle_fills"] is False
    assert payload["summary"]["strategy"] == "sma_cross"
    assert payload["manifest"]["provider"] == "deterministic_local_closed_candle"
    assert payload["manifest"]["engine"] == "local_sma_cross_v1"
    assert payload["manifest"]["deterministic_fallback"] is True
    assert payload["manifest"]["artifact_files"]["signals"].endswith("/signals.csv")
    assert payload["manifest"]["artifact_files"]["indicators"].endswith("/indicators.json")
    assert payload["manifest"]["artifact_files"]["returns_analysis"].endswith(
        "/returns_analysis.json"
    )
    assert payload["provenance"]["safety_class"] == "test_offline_fallback"
    assert payload["signals"]
    assert payload["signals"][0]["fill_rule"] == "next_open"
    assert payload["signals"][0]["same_candle_fill"] == "false"
    assert payload["indicators"][-1]["fast_sma"]
    assert payload["returns_analysis"]["period_count"] == "39"
    assert payload["returns_curve"][-1]["period_return_pct"]
    data_snapshot = json.loads((run_dir / "data_snapshot.json").read_text(encoding="utf-8"))
    assert data_snapshot["provenance"]["deterministic_fallback"] is True
    saved_summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert saved_summary == payload["summary"]
    saved_indicators = json.loads((run_dir / "indicators.json").read_text(encoding="utf-8"))
    assert saved_indicators["rows"] == payload["indicators"]
    saved_returns = json.loads((run_dir / "returns_analysis.json").read_text(encoding="utf-8"))
    assert saved_returns == payload["returns_analysis"]


def test_backtest_run_index_reports_local_runs_for_agent_selection(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    first = client.post("/api/backtest/run", json={"strategy": "sma_cross"}).json()
    second = client.post("/api/backtest/run", json={"strategy": "sma_mean_reversion"}).json()
    response = client.get("/api/backtest/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local_backtest_run_index"
    assert payload["summary"]["run_count"] == 2
    assert payload["summary"]["comparison_ready"] is True
    assert payload["summary"]["comparison_candidate_count"] == 2
    assert {row["run_id"] for row in payload["runs"]} == {
        first["run_id"],
        second["run_id"],
    }
    assert all(row["manifest_path"].endswith("/manifest.json") for row in payload["runs"])
    assert all(row["artifact_dir"].startswith("artifacts/backtests/bt-") for row in payload["runs"])
    assert payload["recommended_actions"][0]["action_id"] == "backtest_comparison_packet"
    assert payload["recommended_actions"][0]["ready"] is True
    assert payload["safety"]["writes_local_artifacts"] is False
    assert payload["safety"]["optimization"] is False
    assert payload["safety"]["live_orders"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_backtest_artifact_health_reports_expected_run_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    run = client.post("/api/backtest/run", json={"strategy": "sma_cross"}).json()

    response = client.get("/api/backtest/artifact-health")
    defaults = client.get("/api/backtest").json()

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "metadata_only_backtest_artifact_health"
    assert payload["summary"]["run_count"] == 1
    assert payload["summary"]["complete_count"] == 1
    assert payload["summary"]["partial_count"] == 0
    assert payload["summary"]["missing_artifact_count"] == 0
    assert payload["summary"]["supervision_ready_count"] == 1
    assert payload["summary"]["destructive_action_count"] == 0
    assert defaults["artifact_health"]["summary"] == payload["summary"]
    row = payload["runs"][0]
    assert row["run_id"] == run["run_id"]
    assert row["artifact_dir"] == run["artifact_dir"]
    assert row["health_state"] == "complete"
    assert row["expected_count"] == 11
    assert row["present_count"] == 11
    assert row["missing_count"] == 0
    assert row["missing_artifacts"] == []
    assert row["manifest_path"].endswith("/manifest.json")
    assert row["supervision_ready"] is True
    assert row["destructive_actions_enabled"] is False
    assert payload["recommended_actions"][0]["action_id"] == "backtest_run_index"
    assert payload["recommended_actions"][0]["ready"] is True
    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["file_content_read"] is False
    assert payload["safety"]["writes_local_artifacts"] is False
    assert payload["safety"]["destructive_actions_enabled"] is False
    assert payload["safety"]["live_orders"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()

    (tmp_path / run["artifact_dir"] / "returns_curve.csv").unlink()
    partial = client.get("/api/backtest/artifact-health").json()

    assert partial["summary"]["complete_count"] == 0
    assert partial["summary"]["partial_count"] == 1
    assert partial["summary"]["missing_artifact_count"] == 1
    assert partial["runs"][0]["health_state"] == "partial_missing_artifacts"
    assert partial["runs"][0]["missing_artifacts"] == ["returns_curve.csv"]
    assert partial["runs"][0]["supervision_ready"] is False
    assert partial["safety"]["automatic_repair_enabled"] is False


def test_backtest_data_readiness_reports_local_fallback_without_writes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/backtest/data-readiness")
    defaults = client.get("/api/backtest").json()

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "local_backtest_data_readiness"
    assert payload["contract"] == "backtest_data_readiness_v1"
    assert payload["summary"]["selected_symbol"] == "BTCUSDT"
    assert payload["summary"]["selected_data_mode"] == "deterministic_local_fallback"
    assert payload["summary"]["selected_run_ready"] is True
    assert payload["summary"]["selected_closed_candle_count"] == 40
    assert payload["summary"]["deterministic_fallback_required"] is True
    assert payload["recommended_actions"][0]["action_id"] == "backtest_run_closed_candle"
    assert payload["recommended_actions"][0]["ready"] is True
    assert payload["recommended_actions"][1]["action_id"] == "markets_refresh_public"
    assert payload["recommended_actions"][1]["ready"] is True
    assert payload["safety"]["writes_local_artifacts"] is False
    assert payload["safety"]["provider_refresh_performed"] is False
    assert payload["safety"]["secret_values_returned"] is False
    assert defaults["data_readiness"]["summary"] == payload["summary"]
    assert not (tmp_path / "artifacts" / "backtests").exists()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_backtest_data_readiness_helper_accepts_selected_config() -> None:
    payload = backtest_data_readiness_payload(
        None,
        {
            "symbol": "ETHUSDT",
            "strategy": "channel_breakout",
            "fast_window": 3,
            "slow_window": 6,
        },
    )

    assert payload["selected_config"]["symbol"] == "ETHUSDT"
    assert payload["selected_config"]["strategy"] == "channel_breakout"
    assert payload["summary"]["selected_symbol"] == "ETHUSDT"
    assert payload["summary"]["selected_run_ready"] is True
    assert [row["selected"] for row in payload["datasets"]].count(True) == 1
    assert payload["safety"]["live_orders"] is False


def test_backtest_run_index_is_read_only_when_runs_are_missing(tmp_path: Path) -> None:
    payload = backtest_run_index_payload(tmp_path)
    health = backtest_artifact_health_payload(tmp_path)

    assert payload["summary"]["run_count"] == 0
    assert payload["summary"]["comparison_ready"] is False
    assert payload["recommended_actions"][0]["ready"] is False
    assert health["summary"]["run_count"] == 0
    assert health["summary"]["complete_count"] == 0
    assert health["recommended_actions"][0]["ready"] is False
    assert health["safety"]["read_only"] is True
    assert not (tmp_path / "artifacts" / "backtests").exists()


def test_backtest_comparison_packet_writes_local_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    first = client.post("/api/backtest/run", json={"strategy": "sma_cross"})
    second = client.post("/api/backtest/run", json={"strategy": "channel_breakout"})
    response = client.post("/api/backtest/comparison-packet", json={"max_runs": 4})

    assert first.status_code == 200
    assert second.status_code == 200
    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["run_count"] == 2
    assert payload["summary"]["artifact_contract"] == "local_backtest_comparison_packet_v1"
    assert payload["summary"]["comparison_mode"] == "latest_local_backtest_runs"
    assert payload["safety"]["optimization"] is False
    assert payload["safety"]["live_orders"] is False
    assert payload["safety"]["broker_routing"] is False
    assert {row["run_id"] for row in payload["rows"]} == {
        first.json()["run_id"],
        second.json()["run_id"],
    }
    assert [row["return_pct"] for row in payload["ranked_rows"]] == sorted(
        [row["return_pct"] for row in payload["rows"]],
        key=lambda value: float(value),
        reverse=True,
    )
    artifact_files = payload["artifacts"]
    assert artifact_files["comparison"].endswith("/comparison.json")
    assert artifact_files["rows"].endswith("/rows.csv")
    assert artifact_files["manifest"].endswith("/manifest.json")
    assert artifact_files["report"].endswith("/report.md")
    manifest = json.loads((tmp_path / artifact_files["manifest"]).read_text(encoding="utf-8"))
    report = (tmp_path / artifact_files["report"]).read_text(encoding="utf-8")
    assert manifest["source_run_ids"] == [row["run_id"] for row in payload["rows"]]
    assert manifest["safety"]["live_orders"] is False
    assert "no optimize, deploy, broker, balance, or live order path" in report


def test_backtest_comparison_requires_two_local_runs(tmp_path: Path) -> None:
    try:
        write_backtest_comparison_packet(tmp_path)
    except BacktestError as exc:
        assert str(exc) == "At least two local backtest runs are required for comparison"
    else:
        raise AssertionError("comparison without runs should reject")
    assert not (tmp_path / "artifacts" / "backtests" / "comparisons").exists()


def test_backtest_preserves_scan_seeded_research_lineage_separate_from_data_provenance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post(
        "/api/algo/strategy",
        json={
            "name": "Lineage Seed",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "entry_conditions": ["fast SMA crosses above slow SMA"],
            "exit_conditions": ["fast SMA crosses below slow SMA"],
            "risk_settings": {},
            "backtest": {"fast_window": 3, "slow_window": 5},
        },
    ).json()["active_strategy_id"]
    scan = client.post(
        "/api/algo/scan",
        json={"strategy_id": strategy_id, "symbols": "BTCUSDT", "timeframe": "15m"},
    ).json()["scan_result"]
    lineage = scan["research_lineage"]

    response = client.post(
        "/api/backtest/run",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "fast_window": 3,
            "slow_window": 5,
            "research_lineage": lineage,
        },
    )

    payload = response.json()
    run_dir = tmp_path / payload["artifact_dir"]
    saved_config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    saved_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    saved_provenance = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    saved_data = json.loads((run_dir / "data_snapshot.json").read_text(encoding="utf-8"))
    assert response.status_code == 200
    assert payload["research_lineage"]["scan_id"] == scan["scan_id"]
    assert payload["research_lineage"]["backtest_run_id"] == payload["run_id"]
    assert payload["research_lineage"]["manifest_path"] == payload["artifacts"]["manifest"]
    assert payload["research_lineage"]["live_action_enabled"] is False
    assert payload["research_lineage"]["provider_id"] == lineage["provider_id"]
    assert payload["provenance"]["source"] == "deterministic_local_closed_candle"
    assert payload["provenance"]["provider_id"] == "local_deterministic_candle_generator"
    assert payload["provenance"]["provider_id"] != payload["research_lineage"]["provider_id"]
    assert saved_config["research_lineage"] == payload["research_lineage"]
    assert saved_manifest["research_lineage"] == payload["research_lineage"]
    assert saved_provenance["research_lineage"] == payload["research_lineage"]
    assert saved_data["provenance"]["research_lineage"] == payload["research_lineage"]


def test_backtest_rejects_unsafe_research_lineage_without_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/backtest/run",
        json={
            "research_lineage": {
                "markets_source_row_id": "fx-reference",
                "markets_source_row_hash": "a" * 64,
                "cache_path": "../outside.json",
                "live_action_enabled": False,
            }
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Research lineage artifact path is invalid"
    assert not (tmp_path / "artifacts" / "backtests").exists()


def test_backtest_rejects_tampered_research_lineage_without_backtest_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post(
        "/api/algo/strategy",
        json={
            "name": "Lineage Seed",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "entry_conditions": ["fast SMA crosses above slow SMA"],
            "exit_conditions": ["fast SMA crosses below slow SMA"],
            "risk_settings": {},
            "backtest": {"fast_window": 3, "slow_window": 5},
        },
    ).json()["active_strategy_id"]
    scan = client.post(
        "/api/algo/scan",
        json={"strategy_id": strategy_id, "symbols": "BTCUSDT", "timeframe": "15m"},
    ).json()["scan_result"]

    response = client.post(
        "/api/backtest/run",
        json={
            "research_lineage": {
                **scan["research_lineage"],
                "markets_source_row_id": "tampered-row",
            }
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Research lineage source row id mismatch"
    assert not (tmp_path / "artifacts" / "backtests").exists()


def test_backtest_rejects_open_candles_and_prevents_same_candle_fills() -> None:
    config = default_backtest_config()
    candles = generate_closed_candles("BTCUSDT")
    result = run_sma_cross(config, candles)

    assert result["trades"]
    assert all(trade["same_candle_fill"] == "false" for trade in result["trades"])
    first_trade = result["trades"][0]
    assert int(first_trade["fill_candle_index"]) == int(first_trade["signal_candle_index"]) + 1

    candles[10]["closed"] = False
    try:
        run_sma_cross(config, candles)
    except BacktestError as exc:
        assert str(exc) == "Backtest requires closed candles"
    else:
        raise AssertionError("open candle should reject")


def test_backtest_does_not_emit_unfillable_final_signal() -> None:
    config = {**default_backtest_config(), "fast_window": 2, "slow_window": 3}
    candles = [
        {
            "opened_at": "2026-01-01T00:00:00+00:00",
            "closed_at": "2026-01-01T00:15:00+00:00",
            "open": "1",
            "high": "1",
            "low": "1",
            "close": "1",
            "volume": "1",
            "closed": True,
        },
        {
            "opened_at": "2026-01-01T00:15:00+00:00",
            "closed_at": "2026-01-01T00:30:00+00:00",
            "open": "1",
            "high": "1",
            "low": "1",
            "close": "1",
            "volume": "1",
            "closed": True,
        },
        {
            "opened_at": "2026-01-01T00:30:00+00:00",
            "closed_at": "2026-01-01T00:45:00+00:00",
            "open": "10",
            "high": "10",
            "low": "10",
            "close": "10",
            "volume": "1",
            "closed": True,
        },
    ]

    result = run_sma_cross(config, candles)

    assert result["signals"] == []
    assert result["trades"] == []


def test_backtest_trades_csv_schema(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    payload = client.post("/api/backtest/run", json={}).json()
    run_dir = tmp_path / payload["artifact_dir"]
    with (run_dir / "trades.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows
    assert set(rows[0]) == {
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
    }

    with (run_dir / "signals.csv").open("r", encoding="utf-8", newline="") as handle:
        signal_rows = list(csv.DictReader(handle))

    assert signal_rows
    assert set(signal_rows[0]) == {
        "symbol",
        "strategy",
        "side",
        "signal_candle_index",
        "signal_closed_at",
        "signal_close",
        "fill_candle_index",
        "fill_rule",
        "same_candle_fill",
    }


def test_backtest_rejects_invalid_economics_without_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    invalid_cases = [
        ({"initial_cash": "0"}, "Initial cash must be positive"),
        ({"initial_cash": "-100"}, "Initial cash must be positive"),
        ({"initial_cash": "0.001"}, "Initial cash is below minimum"),
        ({"initial_cash": "0.004"}, "Initial cash is below minimum"),
        ({"initial_cash": "NaN"}, "Initial cash must be finite"),
        ({"initial_cash": "Infinity"}, "Initial cash must be finite"),
        ({"fee_rate": "-1"}, "Fee rate is below minimum"),
        ({"fee_rate": "1"}, "Fee rate is too large"),
        ({"slippage_bps": "-1"}, "Slippage bps is below minimum"),
        ({"slippage_bps": "20000"}, "Slippage bps is too large"),
    ]

    for patch, message in invalid_cases:
        response = client.post("/api/backtest/run", json=patch)
        assert response.status_code == 400
        assert response.json()["detail"] == message

    assert not (tmp_path / "artifacts" / "backtests").exists()


def test_backtest_defaults_expose_strategy_catalog(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/backtest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["strategy"] == "sma_cross"
    assert {strategy["strategy_id"] for strategy in payload["strategies"]} == {
        "sma_cross",
        "channel_breakout",
        "sma_mean_reversion",
        "volatility_reversion",
        "momentum_continuation",
        "rsi_reversion",
    }
    channel = backtest_strategy_catalog()[1]
    assert channel["parameters"][0] == {
        "key": "fast_window",
        "label": "Exit Window",
        "kind": "integer",
        "default": 3,
        "minimum": 2,
        "maximum": 100,
        "role": "signal_window",
    }
    assert channel["parameters"][1]["must_be_greater_than"] == "fast_window"
    assert channel["constraints"][0]["message"] == "Slow window must be greater than fast window"
    assert channel["artifact_contract"] == "local_closed_candle_backtest_artifacts_v1"
    assert channel["execution_safety"]["live_orders"] is False


def test_backtest_strategy_parameter_schema_is_deep_copied_and_validated() -> None:
    catalog = backtest_strategy_catalog()
    catalog[1]["parameters"][0]["label"] = "mutated"

    assert backtest_strategy_catalog()[1]["parameters"][0]["label"] == "Exit Window"
    assert normalize_strategy_parameters(
        "channel_breakout",
        {"fast_window": 4, "slow_window": 8},
    ) == {"fast_window": 4, "slow_window": 8}

    try:
        normalize_strategy_parameters("channel_breakout", {"fast_window": 8, "slow_window": 4})
    except BacktestError as exc:
        assert str(exc) == "Slow window must be greater than fast window"
    else:
        raise AssertionError("parameter schema should reject invalid window relationship")


def test_channel_breakout_strategy_writes_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/backtest/run",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "strategy": "channel_breakout",
            "fast_window": 3,
            "slow_window": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["strategy"] == "channel_breakout"
    assert payload["summary"]["strategy_label"] == "Channel Breakout"
    assert payload["manifest"]["engine"] == "local_channel_breakout_v1"
    assert payload["manifest"]["strategy"] == "channel_breakout"
    assert payload["summary"]["same_candle_fills"] is False
    assert all(trade["same_candle_fill"] == "false" for trade in payload["trades"])

    run_dir = tmp_path / payload["artifact_dir"]
    saved_config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    saved_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert saved_config["strategy"] == "channel_breakout"
    assert saved_manifest["strategy_label"] == "Channel Breakout"
    assert saved_manifest["strategy_parameter_schema"][0]["label"] == "Exit Window"
    assert saved_manifest["strategy_constraints"][0]["operator"] == "greater_than"
    assert (
        saved_manifest["strategy_artifact_contract"] == "local_closed_candle_backtest_artifacts_v1"
    )
    assert payload["indicators"][-1]["prior_high"]
    assert payload["returns_analysis"]["total_return_pct"] == payload["summary"]["return_pct"]


def test_sma_mean_reversion_strategy_writes_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/backtest/run",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "strategy": "sma_mean_reversion",
            "fast_window": 3,
            "slow_window": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    run_dir = tmp_path / payload["artifact_dir"]
    saved_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert payload["summary"]["strategy"] == "sma_mean_reversion"
    assert payload["summary"]["strategy_label"] == "SMA Mean Reversion"
    assert payload["manifest"]["engine"] == "local_sma_mean_reversion_v1"
    assert saved_manifest["strategy_parameter_schema"][0]["label"] == "Exit SMA"
    assert saved_manifest["strategy_parameter_schema"][1]["label"] == "Mean SMA"
    assert payload["signals"]
    assert payload["trades"]
    assert all(trade["same_candle_fill"] == "false" for trade in payload["trades"])
    assert payload["indicators"][-1]["mean_sma"]
    assert payload["indicators"][-1]["mean_distance_pct"]
    assert payload["returns_analysis"]["total_return_pct"] == payload["summary"]["return_pct"]


def test_volatility_reversion_strategy_writes_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/backtest/run",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "strategy": "volatility_reversion",
            "fast_window": 3,
            "slow_window": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    run_dir = tmp_path / payload["artifact_dir"]
    saved_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert payload["summary"]["strategy"] == "volatility_reversion"
    assert payload["summary"]["strategy_label"] == "Volatility Reversion"
    assert payload["manifest"]["engine"] == "local_volatility_reversion_v1"
    assert saved_manifest["strategy_parameter_schema"][0]["label"] == "Exit SMA"
    assert saved_manifest["strategy_parameter_schema"][1]["label"] == "Band Window"
    assert payload["signals"]
    assert payload["trades"]
    assert all(trade["same_candle_fill"] == "false" for trade in payload["trades"])
    assert payload["indicators"][-1]["band_mid"]
    assert payload["indicators"][-1]["lower_band"]
    assert payload["indicators"][-1]["upper_band"]
    assert payload["indicators"][-1]["lower_band_distance_pct"]
    assert payload["returns_analysis"]["total_return_pct"] == payload["summary"]["return_pct"]


def test_momentum_continuation_strategy_writes_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/backtest/run",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "strategy": "momentum_continuation",
            "fast_window": 3,
            "slow_window": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    run_dir = tmp_path / payload["artifact_dir"]
    saved_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert payload["summary"]["strategy"] == "momentum_continuation"
    assert payload["summary"]["strategy_label"] == "Momentum Continuation"
    assert payload["manifest"]["engine"] == "local_momentum_continuation_v1"
    assert saved_manifest["strategy_parameter_schema"][0]["label"] == "Exit SMA"
    assert saved_manifest["strategy_parameter_schema"][1]["label"] == "Momentum Lookback"
    assert payload["signals"]
    assert payload["trades"]
    assert all(trade["same_candle_fill"] == "false" for trade in payload["trades"])
    assert payload["indicators"][-1]["exit_sma"]
    assert payload["indicators"][-1]["momentum_reference"]
    assert payload["indicators"][-1]["momentum_return_pct"]


def test_rsi_reversion_strategy_writes_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/backtest/run",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "strategy": "rsi_reversion",
            "fast_window": 3,
            "slow_window": 5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    run_dir = tmp_path / payload["artifact_dir"]
    saved_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert payload["summary"]["strategy"] == "rsi_reversion"
    assert payload["summary"]["strategy_label"] == "RSI Reversion"
    assert payload["manifest"]["engine"] == "local_rsi_reversion_v1"
    assert saved_manifest["strategy_parameter_schema"][0]["label"] == "Exit SMA"
    assert saved_manifest["strategy_parameter_schema"][1]["label"] == "RSI Lookback"
    assert payload["signals"]
    assert payload["trades"]
    assert all(trade["same_candle_fill"] == "false" for trade in payload["trades"])
    assert payload["indicators"][-1]["exit_sma"]
    assert payload["indicators"][-1]["rsi"]
    assert payload["indicators"][-1]["rsi_entry_threshold"] == "40.00"
    assert payload["indicators"][-1]["rsi_exit_threshold"] == "55.00"
    assert payload["indicators"][-1]["rsi_distance"]


def test_walk_forward_api_writes_fold_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/backtest/walk-forward",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "strategy": "channel_breakout",
            "fast_window": 3,
            "slow_window": 5,
            "fold_count": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    run_dir = tmp_path / payload["artifact_dir"]
    assert payload["run_id"].startswith("wfa-")
    assert payload["summary"]["mode"] == "fixed_parameter_walk_forward"
    assert payload["summary"]["train_usage"] == "metadata_only_no_fit_no_warmup"
    assert payload["summary"]["fold_count"] == 3
    assert payload["summary"]["same_candle_fills"] is False
    assert payload["summary"]["optimization"] == "disabled_fixed_parameters_only"
    assert payload["manifest"]["engine"] == "local_channel_breakout_walk_forward_v1"
    assert payload["manifest"]["train_usage"] == "metadata_only_no_fit_no_warmup"
    assert (
        payload["manifest"]["strategy_artifact_contract"]
        == "local_closed_candle_walk_forward_artifacts_v1"
    )
    assert payload["safety"]["real_orders"] is False
    assert payload["safety"]["broker_routing"] is False
    assert len(payload["folds"]) == 3
    assert payload["folds"][0]["fold_id"] == "fold-1"
    assert payload["folds"][0]["same_candle_fills"] is False
    assert payload["folds"][0]["lookahead_guard"] == "signals_on_close_fills_next_open"
    assert (run_dir / "config.json").is_file()
    assert (run_dir / "data_snapshot.json").is_file()
    assert (run_dir / "walk_forward_summary.json").is_file()
    assert (run_dir / "walk_forward_folds.csv").is_file()
    assert (run_dir / "walk_forward_folds.json").is_file()
    assert (run_dir / "provenance.json").is_file()
    assert (run_dir / "report.md").is_file()
    assert (run_dir / "manifest.json").is_file()
    saved_summary = json.loads(
        (run_dir / "walk_forward_summary.json").read_text(encoding="utf-8")
    )
    saved_folds = json.loads((run_dir / "walk_forward_folds.json").read_text(encoding="utf-8"))
    assert saved_summary == payload["summary"]
    assert saved_folds["rows"] == payload["folds"]
    with (run_dir / "walk_forward_folds.csv").open("r", encoding="utf-8", newline="") as handle:
        fold_rows = list(csv.DictReader(handle))
    assert fold_rows[0]["fold_id"] == "fold-1"
    assert fold_rows[0]["same_candle_fills"] == "False"


def test_walk_forward_rejects_invalid_fold_requests_without_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    too_many = client.post("/api/backtest/walk-forward", json={"fold_count": 8})
    too_few = client.post("/api/backtest/walk-forward", json={"fold_count": 1})

    assert too_many.status_code == 400
    assert too_many.json()["detail"] == "Not enough closed candles for walk-forward folds"
    assert too_few.status_code == 400
    assert too_few.json()["detail"] == "Fold count must be between 2 and 8"
    assert not (tmp_path / "artifacts" / "backtests").exists()


def test_walk_forward_rejects_open_candles() -> None:
    config = {**default_backtest_config(), "fold_count": 3}
    candles = generate_closed_candles("BTCUSDT")
    candles[12]["closed"] = False

    try:
        walk_forward_windows(candles, config, 3)
    except BacktestError as exc:
        assert str(exc) == "Walk-forward requires closed candles"
    else:
        raise AssertionError("open candle should reject")


def test_channel_breakout_rejects_open_candles_and_prevents_same_candle_fills() -> None:
    config = {**default_backtest_config(), "strategy": "channel_breakout"}
    candles = generate_closed_candles("BTCUSDT")
    result = run_channel_breakout(config, candles)

    assert result["trades"]
    assert all(trade["same_candle_fill"] == "false" for trade in result["trades"])
    first_trade = result["trades"][0]
    assert int(first_trade["fill_candle_index"]) == int(first_trade["signal_candle_index"]) + 1

    candles[10]["closed"] = False
    try:
        run_channel_breakout(config, candles)
    except BacktestError as exc:
        assert str(exc) == "Backtest requires closed candles"
    else:
        raise AssertionError("open candle should reject")


def test_sma_mean_reversion_rejects_open_candles_and_prevents_same_candle_fills() -> None:
    config = {**default_backtest_config(), "strategy": "sma_mean_reversion"}
    candles = generate_closed_candles("BTCUSDT")
    result = run_sma_mean_reversion(config, candles)

    assert result["trades"]
    assert all(trade["same_candle_fill"] == "false" for trade in result["trades"])
    first_trade = result["trades"][0]
    assert int(first_trade["fill_candle_index"]) == int(first_trade["signal_candle_index"]) + 1

    candles[10]["closed"] = False
    try:
        run_sma_mean_reversion(config, candles)
    except BacktestError as exc:
        assert str(exc) == "Backtest requires closed candles"
    else:
        raise AssertionError("open candle should reject")


def test_volatility_reversion_rejects_open_candles_and_prevents_same_candle_fills() -> None:
    config = {**default_backtest_config(), "strategy": "volatility_reversion"}
    candles = generate_closed_candles("BTCUSDT")
    result = run_volatility_reversion(config, candles)

    assert result["trades"]
    assert all(trade["same_candle_fill"] == "false" for trade in result["trades"])
    first_trade = result["trades"][0]
    assert int(first_trade["fill_candle_index"]) == int(first_trade["signal_candle_index"]) + 1

    candles[10]["closed"] = False
    try:
        run_volatility_reversion(config, candles)
    except BacktestError as exc:
        assert str(exc) == "Backtest requires closed candles"
    else:
        raise AssertionError("open candle should reject")


def test_momentum_continuation_rejects_open_candles_and_prevents_same_candle_fills() -> None:
    config = {**default_backtest_config(), "strategy": "momentum_continuation"}
    candles = generate_closed_candles("BTCUSDT")
    result = run_momentum_continuation(config, candles)

    assert result["trades"]
    assert all(trade["same_candle_fill"] == "false" for trade in result["trades"])
    first_trade = result["trades"][0]
    assert int(first_trade["fill_candle_index"]) == int(first_trade["signal_candle_index"]) + 1

    candles[10]["closed"] = False
    try:
        run_momentum_continuation(config, candles)
    except BacktestError as exc:
        assert str(exc) == "Backtest requires closed candles"
    else:
        raise AssertionError("open candle should reject")


def test_rsi_reversion_rejects_open_candles_and_prevents_same_candle_fills() -> None:
    config = {**default_backtest_config(), "strategy": "rsi_reversion"}
    candles = generate_closed_candles("BTCUSDT")
    result = run_rsi_reversion(config, candles)

    assert result["trades"]
    assert all(trade["same_candle_fill"] == "false" for trade in result["trades"])
    first_trade = result["trades"][0]
    assert int(first_trade["fill_candle_index"]) == int(first_trade["signal_candle_index"]) + 1

    candles[10]["closed"] = False
    try:
        run_rsi_reversion(config, candles)
    except BacktestError as exc:
        assert str(exc) == "Backtest requires closed candles"
    else:
        raise AssertionError("open candle should reject")


def test_backtest_rejects_unknown_strategy_without_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post("/api/backtest/run", json={"strategy": "does_not_exist"})

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported backtest strategy"
    assert not (tmp_path / "artifacts" / "backtests").exists()


def test_backtest_metrics_include_risk_stats_and_overfit_flags(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/backtest/run",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "fast_window": 3,
            "slow_window": 5,
        },
    )

    assert response.status_code == 200
    metrics = response.json()["metrics"]
    for key in (
        "sharpe_ratio",
        "sortino_ratio",
        "win_rate_pct",
        "profit_factor",
        "avg_trade_pnl",
        "round_trip_count",
        "exposure_pct",
        "overfit_warning",
    ):
        assert key in metrics
    # The deterministic fallback window yields very few round trips, and the
    # reliability layer must say so instead of presenting the run as solid.
    assert int(metrics["round_trip_count"]) < 5
    assert "round trips" in metrics["overfit_warning"]

    report = (tmp_path / response.json()["artifact_dir"] / "report.md").read_text(
        encoding="utf-8"
    )
    assert "## Reliability" in report
    assert "walk-forward" in report


def test_walk_forward_reports_in_sample_vs_oos_consistency(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/backtest/walk-forward",
        json={
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "fast_window": 3,
            "slow_window": 5,
            "fold_count": 3,
        },
    )

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert "full_window_return_pct" in summary
    assert "in_sample_oos_gap_pct" in summary
    assert summary["consistency"] in {"consistent", "mixed", "inconsistent"}
    assert summary["consistency_note"]
    # The gap must be the arithmetic difference of the two figures it cites.
    gap = float(summary["full_window_return_pct"]) - float(summary["average_return_pct"])
    assert abs(gap - float(summary["in_sample_oos_gap_pct"])) < 0.02
