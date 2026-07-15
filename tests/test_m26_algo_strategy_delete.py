"""M26 S1.2 — delete a saved strategy from the user library.

The strategy library could only grow before this slice. Deletion is
confirmation-gated, touches only the user library (bundled catalog templates
are a separate read-only list), and moves the active pointer to the most
recently updated remaining strategy — same semantics as portfolio delete.
"""

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def _save(client: TestClient, name: str) -> str:
    response = client.post(
        "/api/algo/strategy",
        json={
            "name": name,
            "entry_conditions": ["fast SMA crosses above slow SMA"],
            "exit_conditions": ["fast SMA crosses below slow SMA"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["active_strategy_id"]


def test_delete_requires_confirmation(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    strategy_id = _save(client, "Keep Me")
    denied = client.post("/api/algo/strategy/delete", json={"strategy_id": strategy_id})
    assert denied.status_code == 400
    assert "confirmation" in denied.json()["detail"].lower()
    still = client.get("/api/algo").json()
    assert any(row["strategy_id"] == strategy_id for row in still["strategies"])


def test_delete_removes_strategy_and_moves_active_pointer(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    first_id = _save(client, "Older Strategy")
    second_id = _save(client, "Newer Strategy")
    assert client.get("/api/algo").json()["active_strategy_id"] == second_id

    deleted = client.post(
        "/api/algo/strategy/delete", json={"strategy_id": second_id, "confirm": True}
    )
    assert deleted.status_code == 200
    body = deleted.json()
    ids = {row["strategy_id"] for row in body["strategies"]}
    assert second_id not in ids
    assert body["active_strategy_id"] == first_id


def test_delete_last_strategy_clears_active_pointer(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    only_id = _save(client, "Only One")
    body = client.post(
        "/api/algo/strategy/delete", json={"strategy_id": only_id, "confirm": True}
    ).json()
    assert body["strategies"] == []
    assert body["active_strategy_id"] is None


def test_delete_unknown_id_is_rejected_and_catalog_untouchable(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    _save(client, "Real Strategy")
    catalog = client.get("/api/algo").json()["catalog"]
    assert catalog, "catalog templates expected"
    catalog_key = str(
        catalog[0].get("strategy_id") or catalog[0].get("template_id") or "catalog-template"
    )
    for bogus in ("algo-does-not-exist", catalog_key):
        rejected = client.post(
            "/api/algo/strategy/delete", json={"strategy_id": bogus, "confirm": True}
        )
        assert rejected.status_code == 400, bogus
        assert "not found" in rejected.json()["detail"].lower()
    assert client.get("/api/algo").json()["catalog"] == catalog


def test_delete_action_registered_in_agent_contract(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    contract = client.get("/api/agent-contract").json()
    actions = {action["action_id"]: action for action in contract["actions"]}
    entry = actions["algo_delete_strategy"]
    assert entry["method"] == "POST"
    assert entry["endpoint"] == "/api/algo/strategy/delete"
    assert entry["requires_confirmation"] is True
    assert entry["safety_class"] == "local_strategy_library_only"
