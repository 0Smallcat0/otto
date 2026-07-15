from fastapi.testclient import TestClient

from otto.local_terminal.contracts import GLOBAL_MENUS, SHELL_ROUTES
from otto.local_terminal.server import create_app, health_payload, shell_contract_payload


def test_health_payload_exposes_local_foundation_state() -> None:
    payload = health_payload()

    assert payload["app"] == "Local Terminal"
    assert payload["mode"] == "local"
    assert payload["clean_room"] is True
    assert payload["route_count"] == len(SHELL_ROUTES)
    assert payload["menu_count"] == len(GLOBAL_MENUS)
    assert payload["live_execution"] == "disabled"


def test_shell_contract_payload_preserves_phase0_contracts() -> None:
    payload = shell_contract_payload()

    assert len(payload["routes"]) == 16
    assert [route["route_id"] for route in payload["routes"]] == [
        route.route_id for route in SHELL_ROUTES
    ]
    assert [menu["section_id"] for menu in payload["menus"]] == [
        menu.section_id for menu in GLOBAL_MENUS
    ]
    assert payload["safety"]["real_orders"] is False
    assert payload["profile_policy"]["cloud_account_required"] is False


def test_api_serves_health_and_shell_contract() -> None:
    client = TestClient(create_app())

    health_response = client.get("/api/health")
    assert health_response.status_code == 200
    assert health_response.json()["route_count"] == 16

    contract_response = client.get("/api/shell-contract")
    assert contract_response.status_code == 200
    assert contract_response.json()["routes"][0]["route_id"] == "dashboard"


def test_api_exposes_default_local_state() -> None:
    client = TestClient(create_app())

    response = client.get("/api/local-state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["settings"]["default_route"] == "dashboard"
    assert payload["profile"]["cloud_account_required"] is False
    assert payload["layout"]["active_route"] == "dashboard"
