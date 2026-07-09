from fastapi.testclient import TestClient

from src.local_terminal.server import create_app


def test_live_safety_disabled_response_handles_unknown_actions() -> None:
    from src.local_terminal.live_safety import disabled_live_action_response

    response = disabled_live_action_response("unexpected_live_path")

    assert response["status"] == "disabled_no_safety_contract"
    assert response["action"]["action_id"] == "unexpected_live_path"
    assert response["safety"]["live_mode_enabled"] is False
    assert response["safety"]["forbidden_capabilities"]["reachable_live_execution"] is False


def test_live_safety_contract_is_disabled_and_gate_complete() -> None:
    client = TestClient(create_app())

    response = client.get("/api/live-safety")

    payload = response.json()
    gate_ids = {gate["gate_id"] for gate in payload["required_gates"]}
    assert response.status_code == 200
    assert payload["status"] == "disabled_no_safety_contract"
    assert payload["contract_reviewed"] is False
    assert payload["security_reviewed"] is False
    assert payload["live_mode_enabled"] is False
    assert payload["paper_mode_enabled"] is True
    assert gate_ids == {
        "local_secret_storage",
        "explicit_live_mode_opt_in",
        "confirmation_gates",
        "balance_read_confirmation_gate",
        "audit_logs",
        "kill_switch",
        "paper_live_isolation",
        "static_reachability",
        "security_review",
        "unit_integration_e2e_coverage",
        "code_review_security_review",
    }
    assert all(gate["state"] == "missing" for gate in payload["required_gates"])
    assert payload["forbidden_capabilities"] == {
        "reachable_live_execution": False,
        "real_orders": False,
        "private_api_keys": False,
        "real_balance_reads": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives_execution": False,
        "broker_mutation": False,
        "external_network_required": False,
    }
    assert payload["paper_live_isolation"]["shared_order_router"] is False
    assert payload["secret_storage"]["writes_enabled"] is False
    assert payload["kill_switch"]["state"] == "engaged"


def test_live_safety_action_endpoints_are_rejected_without_side_effects(tmp_path, monkeypatch) -> None:
    from src.local_terminal import server
    from src.local_terminal.live_safety import DISABLED_ENDPOINTS
    from src.local_terminal.storage import LocalStateStore

    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    responses = [client.post(route["endpoint"]) for route in DISABLED_ENDPOINTS]

    assert [response.status_code for response in responses] == [403] * len(DISABLED_ENDPOINTS)
    assert [response.json()["detail"]["status"] for response in responses] == [
        "disabled_no_safety_contract"
    ] * len(DISABLED_ENDPOINTS)
    assert [
        response.json()["detail"]["action"]["action_id"] for response in responses
    ] == [route["action_id"] for route in DISABLED_ENDPOINTS]
    assert responses[0].json()["detail"]["safety"]["live_mode_enabled"] is False
    assert responses[1].json()["detail"]["safety"]["secret_storage"]["writes_enabled"] is False
    assert responses[2].json()["detail"]["safety"]["forbidden_capabilities"][
        "real_balance_reads"
    ] is False
    assert responses[3].json()["detail"]["safety"]["forbidden_capabilities"][
        "real_orders"
    ] is False
    assert responses[4].json()["detail"]["safety"]["forbidden_capabilities"]["margin"] is False
    assert responses[5].json()["detail"]["safety"]["forbidden_capabilities"]["leverage"] is False
    assert responses[6].json()["detail"]["safety"]["forbidden_capabilities"]["short"] is False
    assert responses[7].json()["detail"]["safety"]["forbidden_capabilities"][
        "derivatives_execution"
    ] is False
    assert not (tmp_path / "artifacts" / "live").exists()
    assert not (tmp_path / "artifacts" / "live_orders").exists()
    assert not (tmp_path / "settings" / "live_secrets.json").exists()


def test_live_safety_disabled_endpoint_registry_covers_all_actions() -> None:
    from src.local_terminal.live_safety import DISABLED_ACTIONS, DISABLED_ENDPOINTS

    action_ids = {action["action_id"] for action in DISABLED_ACTIONS}
    endpoint_action_ids = {route["action_id"] for route in DISABLED_ENDPOINTS}

    assert endpoint_action_ids == action_ids
    assert len({route["endpoint"] for route in DISABLED_ENDPOINTS}) == len(DISABLED_ENDPOINTS)
    assert all(route["endpoint"].startswith("/api/live-safety/") for route in DISABLED_ENDPOINTS)


def test_live_safety_prd_and_test_spec_exist_with_required_gates() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    prd = root / "docs" / "planning" / "approved" / "live-safety-prd-20260522.md"
    spec = root / "docs" / "planning" / "approved" / "live-safety-test-spec-20260522.md"
    required_terms = (
        "local secret storage",
        "explicit live-mode opt-in",
        "confirmation gates",
        "audit logs",
        "kill switch",
        "paper/live isolation",
        "static reachability",
        "unit, integration, and e2e coverage",
        "code review and security review",
        "security review",
    )

    assert prd.is_file()
    assert spec.is_file()
    prd_text = prd.read_text(encoding="utf-8").lower()
    spec_text = spec.read_text(encoding="utf-8").lower()

    assert all(term in prd_text for term in required_terms)
    assert all(term in spec_text for term in required_terms)
    assert "no reachable live execution code is added" in prd_text
