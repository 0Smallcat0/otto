import json
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.quantlib import QUICK_ACTIONS
from otto.local_terminal.storage import LocalStateStore


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_quantlib_initial_payload_reports_module_tree_presets_and_safety(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/quantlib")

    payload = response.json()
    assert response.status_code == 200
    assert payload["stats"] == {
        "modules": 18,
        "endpoint_count": 590,
        "quick_actions": 7,
        "local_runtime": "deterministic_stdlib_math",
    }
    assert [action["action_id"] for action in payload["quick_actions"]] == [
        "bs-price",
        "gbm-sim",
        "var",
        "bond-duration",
        "implied-volatility",
        "option-scenario-grid",
        "heston",
    ]
    assert payload["request_body"] == QUICK_ACTIONS["bs-price"]["request_body"]
    assert payload["calculation_health"]["mode"] == (
        "metadata_only_quantlib_calculation_health"
    )
    assert payload["calculation_health"]["summary"]["calculation_count"] == 0
    assert payload["calculation_health"]["summary"]["recovery_queue_count"] == 1
    assert payload["calculation_health"]["safety"]["external_quantlib_runtime"] is False
    assert payload["calculation_health"]["safety"]["artifact_content_read"] is False
    assert payload["safety"] == {
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


def test_quantlib_selects_action_and_writes_request_response_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    selected = client.post("/api/quantlib/select-action", json={"action_id": "bs-price"})
    computed = client.post(
        "/api/quantlib/compute",
        json={
            "action_id": "bs-price",
            "request_body": {
                "spot": 100,
                "strike": 105,
                "risk_free_rate": 0.05,
                "volatility": 0.2,
                "time_to_maturity": 1.0,
                "option_type": "call",
            },
        },
    )
    local_state = client.get("/api/local-state")

    payload = computed.json()
    result = payload["calculation_result"]
    calculation_id = result["calculation_id"]
    artifact_dir = tmp_path / "artifacts" / "quantlib" / calculation_id
    assert selected.status_code == 200
    assert selected.json()["active_action"] == "bs-price"
    assert computed.status_code == 200
    assert result["response_body"]["kind"] == "black_scholes_price"
    assert result["response_body"]["price"] == "8.021352"
    assert result["artifacts"] == {
        "request": f"artifacts/quantlib/{calculation_id}/request.json",
        "response": f"artifacts/quantlib/{calculation_id}/response.json",
        "context": f"artifacts/quantlib/{calculation_id}/context.json",
        "manifest": f"artifacts/quantlib/{calculation_id}/manifest.json",
        "report": f"artifacts/quantlib/{calculation_id}/report.md",
        "error_log": f"artifacts/quantlib/{calculation_id}/error.log",
    }
    assert result["response_body"]["output_mode"] == "local_context_calculation"
    assert json.loads((artifact_dir / "response.json").read_text(encoding="utf-8"))[
        "kind"
    ] == "black_scholes_price"
    context = json.loads((artifact_dir / "context.json").read_text(encoding="utf-8"))
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert context["output_mode"] == "local_context_calculation"
    assert manifest["artifact_contract"]["manifest"] == (
        f"artifacts/quantlib/{calculation_id}/manifest.json"
    )
    assert manifest["clean_room"] == {
        "external_quantlib_runtime": False,
        "external_api_required": False,
        "external_network": False,
        "broker_mutation": False,
        "credential_material": False,
    }
    assert "External QuantLib runtime: `false`" in (
        artifact_dir / "report.md"
    ).read_text(encoding="utf-8")
    assert "External API required: `false`" in (
        artifact_dir / "report.md"
    ).read_text(encoding="utf-8")
    assert "Fincept API" not in (artifact_dir / "report.md").read_text(encoding="utf-8")
    assert (artifact_dir / "error.log").read_text(encoding="utf-8") == ""
    assert local_state.json()["storage"]["quantlib_state"] == (
        "artifacts/quantlib/quantlib_state.json"
    )


def test_quantlib_custom_request_remains_visible_after_compute(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/quantlib/compute",
        json={
            "action_id": "bs-price",
            "request_body": {
                "spot": 120,
                "strike": 100,
                "risk_free_rate": 0.03,
                "volatility": 0.25,
                "time_to_maturity": 0.5,
                "option_type": "put",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["request_body"]["spot"] == 120
    assert payload["request_body"]["option_type"] == "put"
    assert payload["calculation_result"]["request_body"] == payload["request_body"]
    assert payload["calculation_result"]["response_body"]["option_type"] == "put"


def test_quantlib_select_action_resets_request_body_after_prior_compute(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    computed = client.post(
        "/api/quantlib/compute",
        json={
            "action_id": "bs-price",
            "request_body": {
                "spot": 120,
                "strike": 100,
                "risk_free_rate": 0.03,
                "volatility": 0.25,
                "time_to_maturity": 0.5,
                "option_type": "put",
            },
        },
    )

    selected = client.post("/api/quantlib/select-action", json={"action_id": "var"})

    assert computed.status_code == 200
    assert selected.status_code == 200
    assert selected.json()["active_action"] == "var"
    assert selected.json()["request_body"] == QUICK_ACTIONS["var"]["request_body"]


def test_quantlib_bond_duration_preset_writes_fixed_income_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    selected = client.post(
        "/api/quantlib/select-action",
        json={"action_id": "bond-duration"},
    )
    computed = client.post("/api/quantlib/compute", json={"action_id": "bond-duration"})

    payload = computed.json()
    result = payload["calculation_result"]
    calculation_id = result["calculation_id"]
    artifact_dir = tmp_path / "artifacts" / "quantlib" / calculation_id
    response_body = result["response_body"]
    assert selected.status_code == 200
    assert selected.json()["request_body"] == QUICK_ACTIONS["bond-duration"]["request_body"]
    assert computed.status_code == 200
    assert result["action_label"] == "Bond Duration"
    assert response_body["kind"] == "fixed_income_duration"
    assert response_body["price"] == "1022.456463"
    assert response_body["macaulay_duration_years"] == "4.539108"
    assert response_body["modified_duration_years"] == "4.450106"
    assert response_body["convexity_years"] == "23.204683"
    assert response_body["basis_point_value"] == "0.455004"
    assert response_body["runtime"] == "local_stdlib_math"
    assert payload["safety"]["external_quantlib_runtime"] is False
    assert payload["safety"]["external_network"] is False
    assert payload["safety"]["broker_mutation"] is False
    assert json.loads((artifact_dir / "response.json").read_text(encoding="utf-8"))[
        "kind"
    ] == "fixed_income_duration"
    assert (artifact_dir / "error.log").read_text(encoding="utf-8") == ""


def test_quantlib_implied_volatility_preset_writes_local_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    selected = client.post(
        "/api/quantlib/select-action",
        json={"action_id": "implied-volatility"},
    )
    computed = client.post(
        "/api/quantlib/compute",
        json={"action_id": "implied-volatility"},
    )

    payload = computed.json()
    result = payload["calculation_result"]
    calculation_id = result["calculation_id"]
    artifact_dir = tmp_path / "artifacts" / "quantlib" / calculation_id
    response_body = result["response_body"]
    assert selected.status_code == 200
    assert selected.json()["request_body"] == QUICK_ACTIONS["implied-volatility"][
        "request_body"
    ]
    assert selected.json()["active_module"] == "volatility"
    assert computed.status_code == 200
    assert result["action_label"] == "Implied Vol"
    assert response_body["kind"] == "black_scholes_implied_volatility"
    assert response_body["market_price"] == "8.021352"
    assert response_body["model_price"] == "8.021352"
    assert response_body["pricing_error"] == "0.000000"
    assert response_body["implied_volatility"] == "0.200000"
    assert response_body["runtime"] == "local_stdlib_math"
    assert result["endpoint_combo_value"] == "volatility/options/implied-volatility"
    assert payload["safety"]["external_quantlib_runtime"] is False
    assert payload["safety"]["derivatives_execution"] is False
    assert json.loads((artifact_dir / "response.json").read_text(encoding="utf-8"))[
        "kind"
    ] == "black_scholes_implied_volatility"
    assert (artifact_dir / "error.log").read_text(encoding="utf-8") == ""


def test_quantlib_option_scenario_grid_preset_writes_local_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    selected = client.post(
        "/api/quantlib/select-action",
        json={"action_id": "option-scenario-grid"},
    )
    computed = client.post(
        "/api/quantlib/compute",
        json={"action_id": "option-scenario-grid"},
    )

    payload = computed.json()
    result = payload["calculation_result"]
    calculation_id = result["calculation_id"]
    artifact_dir = tmp_path / "artifacts" / "quantlib" / calculation_id
    response_body = result["response_body"]
    assert selected.status_code == 200
    assert selected.json()["request_body"] == QUICK_ACTIONS["option-scenario-grid"][
        "request_body"
    ]
    assert selected.json()["active_module"] == "pricing"
    assert computed.status_code == 200
    assert result["action_label"] == "Scenario Grid"
    assert response_body["kind"] == "black_scholes_scenario_grid"
    assert response_body["base_spot"] == "100.000000"
    assert response_body["base_price"] == "8.021352"
    assert response_body["scenario_count"] == 5
    assert response_body["rows"][0] == {
        "shock_pct": "-0.200000",
        "scenario_spot": "80.000000",
        "model_price": "1.199547",
        "model_pnl": "-6.821805",
    }
    assert response_body["rows"][2]["model_pnl"] == "0.000000"
    assert response_body["runtime"] == "local_stdlib_math"
    assert result["endpoint_combo_value"] == "pricing/options/scenario-grid"
    assert payload["safety"]["external_quantlib_runtime"] is False
    assert payload["safety"]["derivatives_execution"] is False
    assert json.loads((artifact_dir / "response.json").read_text(encoding="utf-8"))[
        "kind"
    ] == "black_scholes_scenario_grid"
    assert (artifact_dir / "error.log").read_text(encoding="utf-8") == ""


def test_quantlib_all_quick_action_defaults_compute_locally(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    results = [
        client.post("/api/quantlib/compute", json={"action_id": action_id})
        for action_id in QUICK_ACTIONS
    ]

    assert [result.status_code for result in results] == [200] * len(QUICK_ACTIONS)
    kinds = [
        result.json()["calculation_result"]["response_body"]["kind"]
        for result in results
    ]
    assert kinds == [
        "black_scholes_price",
        "gbm_simulation",
        "parametric_var",
        "fixed_income_duration",
        "black_scholes_implied_volatility",
        "black_scholes_scenario_grid",
        "heston_proxy",
    ]


def test_quantlib_explicit_empty_request_bodies_do_not_fallback_to_defaults(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    empty_object = client.post(
        "/api/quantlib/compute",
        json={"action_id": "bs-price", "request_body": {}},
    )
    empty_string = client.post(
        "/api/quantlib/compute",
        json={"action_id": "bs-price", "request_body": ""},
    )

    assert empty_object.status_code == 400
    assert empty_object.json()["detail"] == "spot is required"
    assert empty_string.status_code == 400
    assert empty_string.json()["detail"] == "Request body must be valid JSON"


def test_quantlib_rejects_secret_live_runtime_and_external_execution(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    credential_key_response = client.post(
        "/api/quantlib/compute",
        json={"action_id": "bs-price", "request_body": {"api" + "_key": "abc123"}},
    )
    live_order = client.post(
        "/api/quantlib/compute",
        json={
            "action_id": "bs-price",
            "request_body": {
                "spot": 100,
                "strike": 105,
                "risk_free_rate": 0.05,
                "volatility": 0.2,
                "time_to_maturity": 1.0,
                "option_type": "call",
                "note": "client.create_order('BTC/USDT')",
            },
        },
    )
    external = client.post("/api/quantlib/external-execute")

    assert credential_key_response.status_code == 400
    assert credential_key_response.json()["detail"] == (
        "Request key appears to request credential material"
    )
    assert live_order.status_code == 400
    assert live_order.json()["detail"] == "Request body contains forbidden runtime intent"
    assert external.status_code == 403
    assert external.json()["detail"]["safety"]["external_quantlib_runtime"] is False
    assert not (tmp_path / "artifacts" / "quantlib").exists()


def test_quantlib_corrupt_existing_state_blocks_mutation_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    state_path = tmp_path / "artifacts" / "quantlib" / "quantlib_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not-json", encoding="utf-8")

    readonly = client.get("/api/quantlib")
    response = client.post("/api/quantlib/compute", json={"action_id": "bs-price"})

    assert readonly.status_code == 200
    assert readonly.json()["invalid_calculations"]["quantlib_state.json"] == (
        "Invalid QuantLib state JSON"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "QuantLib state is invalid: quantlib_state.json: Invalid QuantLib state JSON"
    )
    assert state_path.read_text(encoding="utf-8") == "{not-json"


def test_quantlib_tampered_artifact_sibling_prefix_blocks_mutation_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    created = client.post("/api/quantlib/compute", json={"action_id": "bs-price"})
    state_path = tmp_path / "artifacts" / "quantlib" / "quantlib_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    calculation_id = created.json()["calculation_result"]["calculation_id"]
    state["calculations"][calculation_id]["artifacts"]["request"] = (
        f"artifacts/quantlib/{calculation_id}-extra/request.json"
    )
    state_path.write_text(json.dumps(state), encoding="utf-8")

    readonly = client.get("/api/quantlib")
    response = client.post("/api/quantlib/compute", json={"action_id": "bs-price"})

    assert readonly.status_code == 200
    assert readonly.json()["invalid_calculations"][calculation_id] == (
        "Artifact path must stay under its calculation directory"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        f"Stored calculation {calculation_id} is invalid: "
        "Artifact path must stay under its calculation directory"
    )


def test_quantlib_run_limit_rejects_before_writing_orphan_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    for _ in range(80):
        response = client.post("/api/quantlib/compute", json={"action_id": "bs-price"})
        assert response.status_code == 200

    blocked = client.post("/api/quantlib/compute", json={"action_id": "bs-price"})
    artifact_dirs = [
        path
        for path in (tmp_path / "artifacts" / "quantlib").iterdir()
        if path.is_dir()
    ]

    assert blocked.status_code == 400
    assert blocked.json()["detail"] == "QuantLib calculations exceed limit of 80"
    assert len(artifact_dirs) == 80


def test_quantlib_calculation_health_is_metadata_only(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    initial = client.get("/api/quantlib/calculation-health")

    assert initial.status_code == 200
    assert initial.json()["mode"] == "metadata_only_quantlib_calculation_health"
    assert initial.json()["summary"]["calculation_count"] == 0
    assert initial.json()["summary"]["recovery_queue_count"] == 1
    assert initial.json()["safety"]["read_only"] is True
    assert initial.json()["safety"]["external_quantlib_runtime"] is False
    assert initial.json()["safety"]["artifact_content_read"] is False
    assert initial.json()["safety"]["automatic_repair_enabled"] is False

    computed = client.post("/api/quantlib/compute", json={"action_id": "bs-price"})
    calculation_id = computed.json()["calculation_result"]["calculation_id"]
    health = client.get("/api/quantlib/calculation-health")
    embedded = client.get("/api/quantlib")

    assert computed.status_code == 200
    assert health.status_code == 200
    payload = health.json()
    row = payload["calculations"][0]
    assert payload["summary"]["calculation_count"] == 1
    assert payload["summary"]["complete_count"] == 1
    assert payload["summary"]["missing_artifact_count"] == 0
    assert payload["summary"]["supervision_ready_count"] == 1
    assert row["calculation_id"] == calculation_id
    assert row["health_state"] == "complete"
    assert row["expected_count"] == 6
    assert row["present_count"] == 6
    assert row["report_artifact_exists"] is True
    assert row["artifact_content_read"] is False
    assert row["external_quantlib_runtime"] is False
    assert "External QuantLib runtime: `false`" not in str(payload)
    assert embedded.json()["calculation_health"]["summary"] == payload["summary"]

    report_path = tmp_path / "artifacts" / "quantlib" / calculation_id / "report.md"
    report_path.unlink()
    partial = client.get("/api/quantlib/calculation-health").json()
    partial_row = partial["calculations"][0]

    assert partial["summary"]["complete_count"] == 0
    assert partial["summary"]["partial_count"] == 1
    assert partial["summary"]["missing_artifact_count"] == 1
    assert partial["summary"]["recovery_queue_count"] == 1
    assert partial_row["health_state"] == "partial_missing_artifacts"
    assert partial_row["missing_artifacts"] == ["report"]
    assert partial["recovery_queue"][0]["recommended_action"] == "quantlib_compute"
    assert partial["recovery_queue"][0]["destructive_action_required"] is False
