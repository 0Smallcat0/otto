import json
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.quant_lab import MODULE_CATALOG, RUNNABLE_PRIORITIES
from otto.local_terminal.storage import LocalStateStore


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_quant_lab_initial_payload_reports_catalog_and_safety(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/quant-lab")

    payload = response.json()
    assert response.status_code == 200
    assert payload["active_module"]["slug"] == "feature-engineering"
    assert payload["stats"] == {
        "modules": 24,
        "observed_subpages": 2,
        "catalog_entries": 26,
        "runnable_local_modules": 9,
        "deferred_modules": 7,
    }
    assert {item["category"] for item in payload["categories"]} == {
        "core",
        "ai_ml",
        "advanced",
        "analytics",
        "observed_subpage",
    }
    assert payload["controls"]["action"] == "COMPUTE INDICATOR"
    assert payload["module_info"]["observed_script_label"] == (
        "ai_quant_lab/qlib_feature_engineering.py"
    )
    assert payload["preview_health"]["mode"] == "metadata_only_quant_lab_preview_health"
    assert payload["preview_health"]["summary"]["run_count"] == 0
    assert payload["preview_health"]["summary"]["recovery_queue_count"] == 1
    assert payload["preview_health"]["safety"]["script_execution"] is False
    assert payload["preview_health"]["safety"]["artifact_content_read"] is False
    assert payload["preview_health"]["safety"]["automatic_repair_enabled"] is False
    assert payload["safety"] == {
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


def test_quant_lab_selects_feature_module_and_writes_preview_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    selected = client.post(
        "/api/quant-lab/select", json={"module_slug": "portfolio-optimization"}
    )
    preview = client.post(
        "/api/quant-lab/run-preview",
        json={
            "module_slug": "feature-engineering",
            "inputs": {
                "price_data": "100,101,102,104",
                "indicator": "moving_average",
                "window": "2",
            },
        },
    )
    local_state = client.get("/api/local-state")

    payload = preview.json()
    result = payload["preview_result"]
    run_id = result["run_id"]
    artifact_dir = tmp_path / "artifacts" / "quant_lab" / run_id
    assert selected.status_code == 200
    assert selected.json()["active_module"]["slug"] == "portfolio-optimization"
    assert preview.status_code == 200
    assert payload["active_module"]["slug"] == "feature-engineering"
    assert result["output"]["kind"] == "indicator_preview"
    assert result["output"]["last_value"] == "103.0000"
    assert result["artifacts"] == {
        "input": f"artifacts/quant_lab/{run_id}/input.json",
        "output": f"artifacts/quant_lab/{run_id}/output.json",
        "context": f"artifacts/quant_lab/{run_id}/context.json",
        "manifest": f"artifacts/quant_lab/{run_id}/manifest.json",
        "report": f"artifacts/quant_lab/{run_id}/report.md",
        "error_log": f"artifacts/quant_lab/{run_id}/error.log",
    }
    assert result["output"]["output_mode"] == "local_context_bundle"
    assert (artifact_dir / "input.json").is_file()
    assert json.loads((artifact_dir / "output.json").read_text(encoding="utf-8"))[
        "kind"
    ] == "indicator_preview"
    context = json.loads((artifact_dir / "context.json").read_text(encoding="utf-8"))
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert context["output_mode"] == "local_context_bundle"
    assert manifest["artifact_contract"]["context"] == (
        f"artifacts/quant_lab/{run_id}/context.json"
    )
    assert manifest["clean_room"] == {
        "script_execution": False,
        "external_runtime": False,
        "broker_mutation": False,
        "credential_material": False,
    }
    assert "Script execution: `false`" in (artifact_dir / "report.md").read_text(
        encoding="utf-8"
    )
    assert (artifact_dir / "error.log").read_text(encoding="utf-8") == ""
    assert (
        local_state.json()["storage"]["quant_lab_state"]
        == "artifacts/quant_lab/quant_lab_state.json"
    )
    assert payload["preview_health"]["summary"]["complete_count"] == 1
    assert payload["preview_health"]["runs"][0]["health_state"] == "complete"
    assert payload["preview_health"]["runs"][0]["present_count"] == 6


def test_quant_lab_preview_health_is_metadata_only(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    initial = client.get("/api/quant-lab/preview-health")
    preview = client.post(
        "/api/quant-lab/run-preview",
        json={
            "module_slug": "feature-engineering",
            "inputs": {"price_data": "100,101,102", "window": "2"},
        },
    )

    assert initial.status_code == 200
    assert initial.json()["mode"] == "metadata_only_quant_lab_preview_health"
    assert initial.json()["summary"]["run_count"] == 0
    assert initial.json()["summary"]["recovery_queue_count"] == 1
    assert preview.status_code == 200

    health = client.get("/api/quant-lab/preview-health")
    health_text = health.text
    health_payload = health.json()
    run_id = preview.json()["preview_result"]["run_id"]

    assert health.status_code == 200
    assert health_payload["summary"]["run_count"] == 1
    assert health_payload["summary"]["complete_count"] == 1
    assert health_payload["summary"]["partial_count"] == 0
    assert health_payload["summary"]["recovery_queue_count"] == 0
    assert "Feature Engineering Local Preview" not in health_text
    row = health_payload["runs"][0]
    assert row["run_id"] == run_id
    assert row["health_state"] == "complete"
    assert row["expected_count"] == 6
    assert row["present_count"] == 6
    assert row["missing_count"] == 0
    assert row["input_artifact_exists"] is True
    assert row["output_artifact_exists"] is True
    assert row["context_artifact_exists"] is True
    assert row["manifest_artifact_exists"] is True
    assert row["report_artifact_exists"] is True
    assert row["error_log_artifact_exists"] is True
    assert row["artifact_bytes"] > 0
    assert row["supervision_ready"] is True
    assert row["artifact_content_read"] is False
    assert row["script_execution"] is False
    assert health_payload["safety"]["metadata_only"] is True
    assert health_payload["safety"]["script_execution"] is False
    assert health_payload["safety"]["artifact_content_read"] is False
    assert health_payload["safety"]["automatic_repair_enabled"] is False

    report_path = tmp_path / row["report_artifact_path"]
    report_path.unlink()
    partial = client.get("/api/quant-lab/preview-health").json()

    assert partial["summary"]["complete_count"] == 0
    assert partial["summary"]["partial_count"] == 1
    assert partial["summary"]["recovery_queue_count"] == 1
    assert partial["runs"][0]["health_state"] == "partial_missing_artifacts"
    assert partial["runs"][0]["report_artifact_exists"] is False
    assert partial["recovery_queue"][0]["recommended_action"] == "quant_lab_run_preview"
    assert "Feature Engineering Local Preview" not in json.dumps(partial)


def test_quant_lab_deferred_and_runtime_paths_are_disabled(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    deferred = client.post(
        "/api/quant-lab/run-preview",
        json={"module_slug": "deep-agent", "inputs": {"prompt": "research"}},
    )
    execute = client.post("/api/quant-lab/execute")
    deep_agent = client.post("/api/quant-lab/deep-agent")

    assert deferred.status_code == 403
    assert deferred.json()["detail"] == (
        "Quant Lab module is catalog-only until a safety contract exists"
    )
    assert execute.status_code == 403
    assert execute.json()["detail"]["state"] == "disabled"
    assert execute.json()["detail"]["safety"]["broker_mutation"] is False
    assert deep_agent.status_code == 403
    assert deep_agent.json()["detail"]["safety"]["deep_agent_execution"] is False


def test_quant_lab_all_runnable_modules_accept_default_preview_inputs(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    runnable_slugs = [
        str(module["slug"])
        for module in MODULE_CATALOG
        if module["local_priority"] in RUNNABLE_PRIORITIES
    ]

    results = [
        client.post("/api/quant-lab/run-preview", json={"module_slug": slug})
        for slug in runnable_slugs
    ]

    assert runnable_slugs == [
        "backtesting",
        "feature-engineering",
        "portfolio-optimization",
        "factor-evaluation",
        "strategy-builder",
        "data-processors",
        "quant-reporting",
        "fetch-data",
        "calendar",
    ]
    assert [result.status_code for result in results] == [200] * len(runnable_slugs)
    assert results[0].json()["preview_result"]["output"]["kind"] == "backtest_handoff"


def test_quant_lab_rejects_secret_and_live_runtime_intent_without_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    secret = client.post(
        "/api/quant-lab/run-preview",
        json={
            "module_slug": "feature-engineering",
            "inputs": {"price_data": "100,101", "api_key": "abc123"},
        },
    )
    secret_value = client.post(
        "/api/quant-lab/run-preview",
        json={
            "module_slug": "feature-engineering",
            "inputs": {"price_data": "100,101", "notes": "api_key = abc123"},
        },
    )
    live = client.post(
        "/api/quant-lab/run-preview",
        json={
            "module_slug": "strategy-builder",
            "inputs": {"rules": "client.create_order('BTC/USDT')"},
        },
    )
    forbidden_word = client.post(
        "/api/quant-lab/run-preview",
        json={
            "module_slug": "strategy-builder",
            "inputs": {"rules": "enable leverage later"},
        },
    )

    assert secret.status_code == 400
    assert secret.json()["detail"] == "Input key appears to request credential material"
    assert secret_value.status_code == 400
    assert secret_value.json()["detail"] == (
        "Input value appears to contain credential material"
    )
    assert live.status_code == 400
    assert live.json()["detail"] == "Input contains forbidden runtime intent"
    assert forbidden_word.status_code == 400
    assert forbidden_word.json()["detail"] == "Input contains forbidden runtime intent"
    assert not (tmp_path / "artifacts" / "quant_lab").exists()


def test_quant_lab_corrupt_existing_state_blocks_mutation_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    state_path = tmp_path / "artifacts" / "quant_lab" / "quant_lab_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not-json", encoding="utf-8")

    readonly = client.get("/api/quant-lab")
    response = client.post(
        "/api/quant-lab/select", json={"module_slug": "feature-engineering"}
    )

    assert readonly.status_code == 200
    assert readonly.json()["invalid_runs"]["quant_lab_state.json"] == (
        "Invalid Quant Lab state JSON"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Quant Lab state is invalid: quant_lab_state.json: Invalid Quant Lab state JSON"
    )
    assert state_path.read_text(encoding="utf-8") == "{not-json"


def test_quant_lab_tampered_run_blocks_mutation_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    created = client.post("/api/quant-lab/run-preview", json={})
    state_path = tmp_path / "artifacts" / "quant_lab" / "quant_lab_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    run_id = created.json()["preview_result"]["run_id"]
    state["runs"][run_id]["status"] = "running"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    readonly = client.get("/api/quant-lab")
    response = client.post(
        "/api/quant-lab/run-preview",
        json={"module_slug": "feature-engineering"},
    )

    assert readonly.status_code == 200
    assert readonly.json()["invalid_runs"][run_id] == "Run status is not allowed"
    assert response.status_code == 400
    assert response.json()["detail"] == (
        f"Stored run {run_id} is invalid: Run status is not allowed"
    )


def test_quant_lab_run_limit_rejects_before_writing_orphan_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    for _ in range(80):
        response = client.post("/api/quant-lab/run-preview", json={})
        assert response.status_code == 200

    blocked = client.post("/api/quant-lab/run-preview", json={})
    artifact_dirs = [
        path
        for path in (tmp_path / "artifacts" / "quant_lab").iterdir()
        if path.is_dir()
    ]

    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "Quant Lab runs exceed limit of 80"
    assert len(artifact_dirs) == 80
