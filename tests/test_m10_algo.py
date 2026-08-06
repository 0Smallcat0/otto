import json
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.markets import default_markets_layout, markets_payload
from otto.local_terminal.research_lineage import scan_artifact_hash
from otto.local_terminal.storage import LocalStateStore
from market_fixtures import fake_binance_tickers as _fake_tickers


def _strategy() -> dict[str, object]:
    return {
        "name": "Local Breakout",
        "description": "Dry-run closed-candle strategy",
        "symbol": "BTCUSDT",
        "timeframe": "15m",
        "entry_conditions": ["close above 20 period high"],
        "exit_conditions": ["fast SMA crosses below slow SMA"],
        "risk_settings": {
            "stop_loss_pct": "4",
            "take_profit_pct": "10",
            "trailing_stop_pct": "0",
        },
        "backtest": {
            "initial_cash": "50000",
            "fast_window": 3,
            "slow_window": 5,
            "fee_rate": "0.001",
            "slippage_bps": "2",
        },
    }


def _channel_breakout_strategy() -> dict[str, object]:
    strategy = _strategy()
    backtest = dict(strategy["backtest"]) if isinstance(strategy["backtest"], dict) else {}
    strategy["backtest"] = {
        **backtest,
        "strategy": "channel_breakout",
    }
    return strategy


def _mean_reversion_strategy() -> dict[str, object]:
    strategy = _strategy()
    strategy["name"] = "Local Mean Reversion"
    strategy["entry_conditions"] = ["close below mean SMA"]
    strategy["exit_conditions"] = ["close recovers above exit SMA"]
    backtest = dict(strategy["backtest"]) if isinstance(strategy["backtest"], dict) else {}
    strategy["backtest"] = {
        **backtest,
        "strategy": "sma_mean_reversion",
    }
    return strategy


def _volatility_reversion_strategy() -> dict[str, object]:
    strategy = _strategy()
    strategy["name"] = "Local Volatility Reversion"
    strategy["entry_conditions"] = ["close below lower volatility band"]
    strategy["exit_conditions"] = ["close recovers above exit SMA"]
    backtest = dict(strategy["backtest"]) if isinstance(strategy["backtest"], dict) else {}
    strategy["backtest"] = {
        **backtest,
        "strategy": "volatility_reversion",
    }
    return strategy


def _momentum_continuation_strategy() -> dict[str, object]:
    strategy = _strategy()
    strategy["name"] = "Local Momentum Continuation"
    strategy["entry_conditions"] = ["close above momentum lookback close"]
    strategy["exit_conditions"] = ["close falls below exit SMA"]
    backtest = dict(strategy["backtest"]) if isinstance(strategy["backtest"], dict) else {}
    strategy["backtest"] = {
        **backtest,
        "strategy": "momentum_continuation",
    }
    return strategy


def _rsi_reversion_strategy() -> dict[str, object]:
    strategy = _strategy()
    strategy["name"] = "Local RSI Reversion"
    strategy["entry_conditions"] = ["RSI below oversold threshold"]
    strategy["exit_conditions"] = ["RSI recovers or close crosses exit SMA"]
    backtest = dict(strategy["backtest"]) if isinstance(strategy["backtest"], dict) else {}
    strategy["backtest"] = {
        **backtest,
        "strategy": "rsi_reversion",
    }
    return strategy


def test_algo_saves_strategy_locally_and_reports_safety(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    initial = client.get("/api/algo")
    saved = client.post("/api/algo/strategy", json=_strategy())
    local_state = client.get("/api/local-state")

    assert initial.status_code == 200
    assert initial.json()["first_use"] is True
    assert initial.json()["engine"]["live_count"] == 0
    assert saved.status_code == 200
    assert saved.json()["active_strategy"]["name"] == "Local Breakout"
    assert saved.json()["active_strategy"]["entry_conditions"] == ["close above 20 period high"]
    assert saved.json()["active_strategy"]["backtest"]["strategy"] == "sma_cross"
    assert {strategy["strategy_id"] for strategy in saved.json()["backtest_strategies"]} == {
        "sma_cross",
        "channel_breakout",
        "sma_mean_reversion",
        "volatility_reversion",
        "momentum_continuation",
        "rsi_reversion",
    }
    channel = next(
        strategy
        for strategy in saved.json()["backtest_strategies"]
        if strategy["strategy_id"] == "channel_breakout"
    )
    assert channel["parameter_schema_version"] == "strategy-parameters-v1"
    assert channel["parameters"][0]["label"] == "Exit Window"
    assert channel["constraints"][0]["left"] == "slow_window"
    assert saved.json()["safety"] == {
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
    assert (tmp_path / "artifacts" / "algo" / "algo_state.json").is_file()
    assert local_state.json()["storage"]["algo_state"] == "artifacts/algo/algo_state.json"


def test_algo_runs_backtest_from_saved_strategy_and_writes_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post("/api/algo/strategy", json=_strategy()).json()["active_strategy_id"]

    response = client.post("/api/algo/run-backtest", json={"strategy_id": strategy_id})

    payload = response.json()
    run_dir = tmp_path / payload["backtest_result"]["artifact_dir"]
    assert response.status_code == 200
    assert payload["backtest_result"]["strategy_definition"]["strategy_id"] == strategy_id
    assert payload["backtest_result"]["strategy_definition"]["backtest_strategy"] == "sma_cross"
    assert payload["backtest_result"]["summary"]["lookahead_guard"] == (
        "signals_on_close_fills_next_open"
    )
    assert payload["backtest_result"]["safety"]["broker_routing"] is False
    assert (run_dir / "config.json").is_file()
    assert (run_dir / "summary.json").is_file()
    assert (run_dir / "trades.csv").is_file()
    assert (run_dir / "report.md").is_file()
    assert payload["last_backtest"]["artifact_dir"] == payload["backtest_result"]["artifact_dir"]
    assert payload["last_backtest"]["backtest_strategy"] == "sma_cross"


def test_algo_runs_channel_breakout_backtest_from_saved_strategy(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post(
        "/api/algo/strategy",
        json=_channel_breakout_strategy(),
    ).json()["active_strategy_id"]

    response = client.post("/api/algo/run-backtest", json={"strategy_id": strategy_id})

    payload = response.json()
    run_dir = tmp_path / payload["backtest_result"]["artifact_dir"]
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert response.status_code == 200
    assert payload["backtest_result"]["summary"]["strategy"] == "channel_breakout"
    assert payload["backtest_result"]["summary"]["strategy_label"] == "Channel Breakout"
    assert (
        payload["backtest_result"]["strategy_definition"]["backtest_strategy"] == "channel_breakout"
    )
    assert payload["last_backtest"]["backtest_strategy_label"] == "Channel Breakout"
    assert config["strategy"] == "channel_breakout"
    assert manifest["engine"] == "local_channel_breakout_v1"


def test_algo_runs_mean_reversion_backtest_from_saved_strategy(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post(
        "/api/algo/strategy",
        json=_mean_reversion_strategy(),
    ).json()["active_strategy_id"]

    response = client.post("/api/algo/run-backtest", json={"strategy_id": strategy_id})

    payload = response.json()
    run_dir = tmp_path / payload["backtest_result"]["artifact_dir"]
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert response.status_code == 200
    assert payload["backtest_result"]["summary"]["strategy"] == "sma_mean_reversion"
    assert payload["backtest_result"]["summary"]["strategy_label"] == "SMA Mean Reversion"
    assert payload["backtest_result"]["strategy_definition"]["backtest_strategy"] == (
        "sma_mean_reversion"
    )
    assert payload["last_backtest"]["backtest_strategy_label"] == "SMA Mean Reversion"
    assert config["strategy"] == "sma_mean_reversion"
    assert manifest["engine"] == "local_sma_mean_reversion_v1"


def test_algo_runs_volatility_reversion_backtest_from_saved_strategy(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post(
        "/api/algo/strategy",
        json=_volatility_reversion_strategy(),
    ).json()["active_strategy_id"]

    response = client.post("/api/algo/run-backtest", json={"strategy_id": strategy_id})

    payload = response.json()
    run_dir = tmp_path / payload["backtest_result"]["artifact_dir"]
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert response.status_code == 200
    assert payload["backtest_result"]["summary"]["strategy"] == "volatility_reversion"
    assert payload["backtest_result"]["summary"]["strategy_label"] == "Volatility Reversion"
    assert payload["backtest_result"]["strategy_definition"]["backtest_strategy"] == (
        "volatility_reversion"
    )
    assert payload["last_backtest"]["backtest_strategy_label"] == "Volatility Reversion"
    assert config["strategy"] == "volatility_reversion"
    assert manifest["engine"] == "local_volatility_reversion_v1"


def test_algo_runs_momentum_continuation_backtest_from_saved_strategy(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post(
        "/api/algo/strategy",
        json=_momentum_continuation_strategy(),
    ).json()["active_strategy_id"]

    response = client.post("/api/algo/run-backtest", json={"strategy_id": strategy_id})

    payload = response.json()
    run_dir = tmp_path / payload["backtest_result"]["artifact_dir"]
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert response.status_code == 200
    assert payload["backtest_result"]["summary"]["strategy"] == "momentum_continuation"
    assert payload["backtest_result"]["summary"]["strategy_label"] == (
        "Momentum Continuation"
    )
    assert payload["backtest_result"]["strategy_definition"]["backtest_strategy"] == (
        "momentum_continuation"
    )
    assert payload["last_backtest"]["backtest_strategy_label"] == "Momentum Continuation"
    assert config["strategy"] == "momentum_continuation"
    assert manifest["engine"] == "local_momentum_continuation_v1"


def test_algo_runs_rsi_reversion_backtest_from_saved_strategy(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post(
        "/api/algo/strategy",
        json=_rsi_reversion_strategy(),
    ).json()["active_strategy_id"]

    response = client.post("/api/algo/run-backtest", json={"strategy_id": strategy_id})

    payload = response.json()
    run_dir = tmp_path / payload["backtest_result"]["artifact_dir"]
    config = json.loads((run_dir / "config.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert response.status_code == 200
    assert payload["backtest_result"]["summary"]["strategy"] == "rsi_reversion"
    assert payload["backtest_result"]["summary"]["strategy_label"] == "RSI Reversion"
    assert payload["backtest_result"]["strategy_definition"]["backtest_strategy"] == (
        "rsi_reversion"
    )
    assert payload["last_backtest"]["backtest_strategy_label"] == "RSI Reversion"
    assert config["strategy"] == "rsi_reversion"
    assert manifest["engine"] == "local_rsi_reversion_v1"


def test_algo_rejects_backtest_strategy_override_mismatch_without_backtest_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post(
        "/api/algo/strategy",
        json=_channel_breakout_strategy(),
    ).json()["active_strategy_id"]

    response = client.post(
        "/api/algo/run-backtest",
        json={
            "strategy_id": strategy_id,
            "backtest": {
                "strategy": "sma_cross",
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Backtest strategy override must match saved strategy"
    assert not (tmp_path / "artifacts" / "backtests").exists()


def test_algo_backtest_rejects_timeframes_without_closed_candle_provider(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post(
        "/api/algo/strategy",
        json={**_strategy(), "timeframe": "1h"},
    ).json()["active_strategy_id"]

    response = client.post("/api/algo/run-backtest", json={"strategy_id": strategy_id})

    assert response.status_code == 400
    assert response.json()["detail"] == "Backtesting currently supports 15m closed candles only"
    assert not (tmp_path / "artifacts" / "backtests").exists()


def test_algo_rejects_unknown_backtest_strategy_without_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.post(
        "/api/algo/strategy",
        json={
            **_strategy(),
            "backtest": {
                "strategy": "does_not_exist",
                "fast_window": 3,
                "slow_window": 5,
                "initial_cash": "100000",
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported algo backtest strategy"
    assert not (tmp_path / "artifacts" / "algo").exists()
    assert not (tmp_path / "artifacts" / "backtests").exists()


def test_algo_scan_readiness_is_read_only_without_strategy(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/algo/scan-readiness")
    embedded = client.get("/api/algo").json()["scan_readiness"]

    payload = response.json()
    assert response.status_code == 200
    assert payload["contract"] == "algo_scan_readiness_v1"
    assert payload["state"] == "no_active_strategy"
    assert payload["active_strategy_ready"] is False
    assert payload["provider_cache"]["data_mode"] == "no_provider_data"
    assert payload["safety"] == {
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
    }
    assert embedded["state"] == payload["state"]
    assert embedded["safety"]["writes_local_artifacts"] is False
    assert not (tmp_path / "artifacts" / "algo").exists()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_algo_scan_readiness_reports_provider_cache_without_scan_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    live = markets_payload(
        default_markets_layout(),
        {},
        fetcher=_fake_tickers,
        refresh=True,
    )
    store.write_market_cache({**live["cache"], "status": {**live["cache"]["status"], "last_update": "2026-05-23T00:00:00+00:00"}})
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())
    strategy_id = client.post("/api/algo/strategy", json=_strategy()).json()["active_strategy_id"]

    response = client.get("/api/algo/scan-readiness")

    payload = response.json()
    actions = {row["action_id"]: row for row in payload["recommended_actions"]}
    assert response.status_code == 200
    assert payload["state"] == "ready"
    assert payload["active_strategy"]["strategy_id"] == strategy_id
    assert payload["provider_cache"]["source"] == "binance_public"
    assert payload["provider_cache"]["state"] == "stale"
    assert payload["provider_cache"]["data_mode"] == "provider_cache"
    assert payload["provider_cache"]["source_row_count"] > 0
    assert {row["symbol"] for row in payload["symbol_readiness"]} == {
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
    }
    assert all(row["data_available"] is True for row in payload["symbol_readiness"])
    assert actions["algo_scan"]["ready"] is True
    assert actions["algo_scan"]["safe"] is True
    assert actions["markets_refresh_public"]["ready"] is False
    assert payload["backtest_handoff"]["ready"] is False
    assert payload["scan_artifact_health"]["status"] == "no_scan"
    assert payload["safety"]["scan_executed"] is False
    assert payload["safety"]["provider_refresh_performed"] is False
    assert not (tmp_path / "artifacts" / "algo" / "scans").exists()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_algo_scanner_without_provider_data_is_dry_run_and_non_actionable(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post("/api/algo/strategy", json=_strategy()).json()["active_strategy_id"]

    response = client.post(
        "/api/algo/scan",
        json={
            "strategy_id": strategy_id,
            "symbols": "BTCUSDT, ETHUSDT, SOLUSDT",
            "timeframe": "15m",
            "lookback_days": 30,
            "preset": "crypto-majors",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["scan_result"]["status"]["dry_run"] is True
    assert payload["scan_result"]["status"]["live_deployment"] is False
    assert payload["scan_result"]["status"]["source"] == "public_provider_unavailable"
    assert payload["scan_result"]["status"]["state"] == "unavailable"
    assert len(payload["scan_result"]["results"]) == 3
    assert {row["symbol"] for row in payload["scan_result"]["results"]} == {
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
    }
    assert {row["signal"] for row in payload["scan_result"]["results"]} == {"NO_DATA"}
    assert {row["match"] for row in payload["scan_result"]["results"]} == {0}
    assert payload["last_scan"]["preset"] == "crypto-majors"


def test_algo_scanner_uses_stale_public_cache_for_signals(tmp_path: Path, monkeypatch) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    live = markets_payload(
        default_markets_layout(),
        {},
        fetcher=_fake_tickers,
        refresh=True,
    )
    store.write_market_cache({**live["cache"], "status": {**live["cache"]["status"], "last_update": "2026-05-23T00:00:00+00:00"}})
    client = TestClient(server.create_app())
    strategy_id = client.post("/api/algo/strategy", json=_strategy()).json()["active_strategy_id"]

    response = client.post(
        "/api/algo/scan",
        json={
            "strategy_id": strategy_id,
            "symbols": "BTCUSDT, ETHUSDT",
            "timeframe": "15m",
            "lookback_days": 30,
            "preset": "crypto-majors",
        },
    )

    payload = response.json()
    artifact_dir = tmp_path / payload["scan_result"]["artifact_dir"]
    scan_row = payload["scan_result"]["results"][0]
    assert response.status_code == 200
    assert payload["scan_result"]["status"]["source"] == "binance_public"
    assert payload["scan_result"]["status"]["state"] == "complete"
    assert payload["scan_result"]["status"]["provider_id"] == "binance_spot_public"
    assert payload["scan_result"]["source_contract"] == {
        "source": "binance_public",
        "state": "stale",
        "provider_id": "binance_spot_public",
        "cache_path": "market_data/crypto_latest.json",
        "retrieved_at": payload["scan_result"]["source_contract"]["retrieved_at"],
        "data_mode": "provider_cache",
        "fixture_primary_runtime": False,
        "result_use": "local_research_signal_only",
        "live_action_enabled": False,
        "markets_source_row_id": payload["scan_result"]["research_lineage"][
            "markets_source_row_id"
        ],
        "quote_semantics": payload["scan_result"]["research_lineage"][
            "quote_semantics"
        ],
    }
    assert scan_row["data_source"] == "binance_public"
    assert scan_row["data_state"] == "stale"
    assert scan_row["provider_id"] == "binance_spot_public"
    assert scan_row["cache_path"] == "market_data/crypto_latest.json"
    assert scan_row["actionable"] is False
    assert {row["signal"] for row in payload["scan_result"]["results"]} <= {
        "LONG",
        "WATCH",
        "FLAT",
    }
    assert {row["match"] for row in payload["scan_result"]["results"]} != {0}
    assert payload["scan_result"]["artifacts"]["scan"].endswith("/scan.json")
    assert payload["scan_result"]["artifacts"]["report"].endswith("/scan_report.md")
    assert payload["scan_result"]["artifacts"]["manifest"].endswith("/manifest.json")
    assert (artifact_dir / "scan.json").is_file()
    assert (artifact_dir / "scan_report.md").is_file()
    assert (artifact_dir / "manifest.json").is_file()
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifact_type"] == "algo_provider_cache_scan"
    assert manifest["source_contract"]["data_mode"] == "provider_cache"
    assert manifest["research_lineage"]["markets_source_row_id"] == (
        payload["scan_result"]["research_lineage"]["markets_source_row_id"]
    )
    assert manifest["research_lineage"]["scan_artifact_hash"] == (
        payload["scan_result"]["research_lineage"]["scan_artifact_hash"]
    )
    assert manifest["live_action_enabled"] is False
    assert manifest["fixture_primary_runtime"] is False


def test_algo_scan_accepts_markets_source_row_and_persists_lineage(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post("/api/algo/strategy", json=_strategy()).json()["active_strategy_id"]
    source_row = next(
        row
        for row in client.get("/api/markets").json()["source_coverage_matrix"]
        if row["asset_family"] == "FX"
    )

    response = client.post(
        "/api/algo/scan",
        json={
            "strategy_id": strategy_id,
            "symbols": "BTCUSDT",
            "timeframe": "15m",
            "markets_source_row_id": source_row["markets_source_row_id"],
            "markets_source_row_hash": source_row["markets_source_row_hash"],
        },
    )

    payload = response.json()
    lineage = payload["scan_result"]["research_lineage"]
    artifact_dir = tmp_path / payload["scan_result"]["artifact_dir"]
    report = (artifact_dir / "scan_report.md").read_text(encoding="utf-8")
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert response.status_code == 200
    assert lineage["markets_source_row_id"] == source_row["markets_source_row_id"]
    assert lineage["markets_source_row_hash"] == source_row["markets_source_row_hash"]
    assert lineage["quote_semantics"] == "reference_only"
    assert lineage["live_action_enabled"] is False
    assert lineage["scan_artifact_path"].endswith("/scan.json")
    assert len(lineage["scan_artifact_hash"]) == 64
    assert lineage["scan_artifact_hash"] == scan_artifact_hash(payload["scan_result"])
    assert payload["scan_result"]["source_contract"]["markets_source_row_id"] == (
        source_row["markets_source_row_id"]
    )
    assert "Markets source row:" in report
    assert manifest["research_lineage"] == lineage


def test_algo_scan_rejects_unknown_markets_source_row_without_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post("/api/algo/strategy", json=_strategy()).json()["active_strategy_id"]

    response = client.post(
        "/api/algo/scan",
        json={
            "strategy_id": strategy_id,
            "symbols": "BTCUSDT",
            "markets_source_row_id": "unknown-source-row",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown Markets source row"
    assert not (tmp_path / "artifacts" / "algo" / "scans").exists()


def test_algo_run_backtest_accepts_latest_scan_seed_lineage(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    live = markets_payload(
        default_markets_layout(),
        {},
        fetcher=_fake_tickers,
        refresh=True,
    )
    store.write_market_cache(live["cache"])
    client = TestClient(server.create_app())
    strategy_id = client.post("/api/algo/strategy", json=_strategy()).json()["active_strategy_id"]
    scan = client.post(
        "/api/algo/scan",
        json={"strategy_id": strategy_id, "symbols": "BTCUSDT", "timeframe": "15m"},
    ).json()["scan_result"]

    response = client.post(
        "/api/algo/run-backtest",
        json={
            "strategy_id": strategy_id,
            "scan_seed": {
                "scan_id": scan["scan_id"],
                "scan_artifact_hash": scan["research_lineage"]["scan_artifact_hash"],
            },
        },
    )

    payload = response.json()
    lineage = payload["backtest_result"]["research_lineage"]
    run_dir = tmp_path / payload["backtest_result"]["artifact_dir"]
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    provenance = json.loads((run_dir / "provenance.json").read_text(encoding="utf-8"))
    assert response.status_code == 200
    assert lineage["scan_id"] == scan["scan_id"]
    assert lineage["scan_artifact_hash"] == scan["research_lineage"]["scan_artifact_hash"]
    assert lineage["backtest_run_id"] == payload["backtest_result"]["run_id"]
    assert lineage["manifest_path"] == payload["backtest_result"]["artifacts"]["manifest"]
    assert lineage["live_action_enabled"] is False
    assert payload["last_backtest"]["research_lineage"] == lineage
    assert manifest["research_lineage"] == lineage
    assert provenance["research_lineage"] == lineage
    assert payload["backtest_result"]["provenance"]["source"] != lineage["provider_id"]


def test_algo_run_backtest_rejects_tampered_scan_seed_without_backtest_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post("/api/algo/strategy", json=_strategy()).json()["active_strategy_id"]
    scan = client.post(
        "/api/algo/scan",
        json={"strategy_id": strategy_id, "symbols": "BTCUSDT", "timeframe": "15m"},
    ).json()["scan_result"]

    response = client.post(
        "/api/algo/run-backtest",
        json={
            "strategy_id": strategy_id,
            "scan_seed": {
                "scan_id": scan["scan_id"],
                "scan_artifact_hash": "0" * 64,
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Scan seed artifact hash mismatch"
    assert not (tmp_path / "artifacts" / "backtests").exists()


def test_algo_scanner_marks_missing_cached_symbol_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    live = markets_payload(
        default_markets_layout(),
        {},
        fetcher=lambda _symbols: _fake_tickers(["BTCUSDT"]),
        refresh=True,
    )
    cache = dict(live["cache"])
    cache["rows"] = [row for row in live["cache"]["rows"] if row["symbol"] == "BTCUSDT"]
    cache["status"] = {**cache["status"], "last_update": "2026-05-23T00:00:00+00:00"}
    store.write_market_cache(cache)
    client = TestClient(server.create_app())
    strategy_id = client.post("/api/algo/strategy", json=_strategy()).json()["active_strategy_id"]

    response = client.post(
        "/api/algo/scan",
        json={
            "strategy_id": strategy_id,
            "symbols": "BTCUSDT, SOLUSDT",
            "timeframe": "15m",
        },
    )

    payload = response.json()
    rows = {row["symbol"]: row for row in payload["scan_result"]["results"]}
    assert response.status_code == 200
    assert rows["BTCUSDT"]["data_state"] == "stale"
    assert rows["BTCUSDT"]["match"] > 0
    assert rows["SOLUSDT"]["signal"] == "NO_DATA"
    assert rows["SOLUSDT"]["match"] == 0
    assert rows["SOLUSDT"]["data_state"] == "unavailable"
    assert rows["SOLUSDT"]["actionable"] is False


def test_algo_scan_artifact_health_repairs_missing_expected_file(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())
    strategy_id = client.post("/api/algo/strategy", json=_strategy()).json()["active_strategy_id"]
    scan = client.post(
        "/api/algo/scan",
        json={
            "strategy_id": strategy_id,
            "symbols": "BTCUSDT",
            "timeframe": "15m",
        },
    ).json()["scan_result"]
    report_path = tmp_path / scan["artifacts"]["report"]
    report_path.unlink()

    health = client.get("/api/algo/scan-artifacts").json()["scan_artifact_health"]
    repair = client.post("/api/algo/scan-artifacts/repair").json()

    assert health["status"] == "repairable_missing"
    assert health["missing_count"] == 1
    assert any(file["kind"] == "report" and file["state"] == "missing" for file in health["files"])
    assert repair["scan_artifact_repair"] == {
        "state": "rewritten",
        "mode": "non_destructive_expected_files_only",
        "missing_before": 1,
        "missing_after": 0,
    }
    assert repair["scan_artifact_health"]["status"] == "complete"
    assert repair["scan_artifact_health"]["destructive_actions_enabled"] is False
    assert report_path.is_file()
    assert not (tmp_path / "outside").exists()


def test_algo_scan_artifact_repair_without_scan_is_rejected(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    health = client.get("/api/algo/scan-artifacts")
    repair = client.post("/api/algo/scan-artifacts/repair")

    assert health.status_code == 200
    assert health.json()["scan_artifact_health"]["status"] == "no_scan"
    assert health.json()["scan_artifact_health"]["repair_available"] is False
    assert repair.status_code == 400
    assert repair.json()["detail"] == "No scan artifacts are available to repair"
    assert not (tmp_path / "artifacts" / "algo" / "scans").exists()


def test_algo_rejects_unsafe_strategy_inputs_without_artifacts(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    secret = client.post(
        "/api/algo/strategy",
        json={**_strategy(), "name": "api key: abc123"},
    )
    description_secret = client.post(
        "/api/algo/strategy",
        json={**_strategy(), "description": "private_key=abc123"},
    )
    condition_secret = client.post(
        "/api/algo/strategy",
        json={**_strategy(), "entry_conditions": ["bearer abcdefgh"]},
    )
    unsupported_symbol = client.post(
        "/api/algo/strategy",
        json={**_strategy(), "symbol": "DOGEUSDT"},
    )
    invalid_windows = client.post(
        "/api/algo/strategy",
        json={
            **_strategy(),
            "backtest": {
                "fast_window": 10,
                "slow_window": 5,
                "initial_cash": "100000",
            },
        },
    )

    assert secret.status_code == 400
    assert secret.json()["detail"] == "Name appears to contain credential material"
    assert description_secret.status_code == 400
    assert description_secret.json()["detail"] == (
        "Description appears to contain credential material"
    )
    assert condition_secret.status_code == 400
    # Named as the key the caller sends, not as prose it would have to convert.
    assert condition_secret.json()["detail"] == (
        "entry_conditions appears to contain credential material"
    )
    assert unsupported_symbol.status_code == 400
    assert unsupported_symbol.json()["detail"] == "Unsupported algo symbol"
    assert invalid_windows.status_code == 400
    assert invalid_windows.json()["detail"] == "Slow window must be greater than fast window"
    assert not (tmp_path / "artifacts" / "algo").exists()
    assert not (tmp_path / "artifacts" / "backtests").exists()


def test_algo_rejects_corrupt_existing_state_without_overwrite(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    state_path = tmp_path / "artifacts" / "algo" / "algo_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not-json", encoding="utf-8")
    client = TestClient(server.create_app())

    readonly = client.get("/api/algo")
    response = client.post("/api/algo/strategy", json=_strategy())

    assert readonly.status_code == 200
    assert readonly.json()["first_use"] is True
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Algo state is invalid: algo_state.json: Invalid algo state JSON"
    )
    assert state_path.read_text(encoding="utf-8") == "{not-json"


def test_algo_rejects_tampered_existing_strategy_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    saved = client.post("/api/algo/strategy", json=_strategy())
    strategy_id = saved.json()["active_strategy_id"]
    state_path = tmp_path / "artifacts" / "algo" / "algo_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["strategies"][strategy_id]["symbol"] = "DOGEUSDT"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    readonly = client.get("/api/algo")
    response = client.post(
        "/api/algo/select",
        json={"strategy_id": strategy_id},
    )

    assert readonly.status_code == 200
    assert readonly.json()["invalid_strategies"][strategy_id] == "Unsupported algo symbol"
    assert response.status_code == 400
    assert response.json()["detail"] == (
        f"Stored strategy {strategy_id} is invalid: Unsupported algo symbol"
    )


def test_algo_drops_malformed_results_and_blocks_mutation_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    saved = client.post("/api/algo/strategy", json=_strategy())
    strategy_id = saved.json()["active_strategy_id"]
    state_path = tmp_path / "artifacts" / "algo" / "algo_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["last_scan"] = {}
    state["last_backtest"] = {
        "strategy_id": strategy_id,
        "run_id": "run-private",
        "artifact_dir": "C:/private/path",
        "return_pct": "0.00",
        "trade_count": 0,
        "created_at": "2026-05-22T00:00:00Z",
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")

    readonly = client.get("/api/algo")
    response = client.post(
        "/api/algo/select",
        json={"strategy_id": strategy_id},
    )

    assert readonly.status_code == 200
    assert readonly.json()["last_scan"] is None
    assert readonly.json()["last_backtest"] is None
    assert readonly.json()["invalid_strategies"]["last_scan"] == ("Last scan status is required")
    assert readonly.json()["invalid_strategies"]["last_backtest"] == (
        "Last backtest artifact path is invalid"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Stored last scan is invalid: Last scan status is required"
    )
    assert json.loads(state_path.read_text(encoding="utf-8"))["last_scan"] == {}


def test_algo_rejects_tampered_scan_artifact_path_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    strategy_id = client.post("/api/algo/strategy", json=_strategy()).json()["active_strategy_id"]
    response = client.post(
        "/api/algo/scan",
        json={
            "strategy_id": strategy_id,
            "symbols": "BTCUSDT",
            "timeframe": "15m",
        },
    )
    assert response.status_code == 200
    state_path = tmp_path / "artifacts" / "algo" / "algo_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["last_scan"]["artifact_dir"] = "../outside"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    readonly = client.get("/api/algo")
    health_response = client.get("/api/algo/scan-artifacts")
    repair = client.post("/api/algo/scan-artifacts/repair")
    mutation = client.post("/api/algo/select", json={"strategy_id": strategy_id})

    assert readonly.status_code == 200
    assert readonly.json()["last_scan"] is None
    assert readonly.json()["invalid_strategies"]["last_scan"] == (
        "Last scan artifact directory is invalid"
    )
    assert health_response.status_code == 200
    health = health_response.json()["scan_artifact_health"]
    assert health["status"] == "invalid_scan_state"
    assert health["validation_error"] == "Last scan artifact directory is invalid"
    assert health["repair_available"] is False
    assert health["state_is_source"] is False
    assert repair.status_code == 400
    assert repair.json()["detail"] == (
        "Scan artifacts cannot be repaired because last scan state is invalid"
    )
    assert mutation.status_code == 400
    assert mutation.json()["detail"] == (
        "Stored last scan is invalid: Last scan artifact directory is invalid"
    )
    assert not (tmp_path / "outside").exists()
