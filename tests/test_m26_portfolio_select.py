"""M26 S1.1 — switch the active portfolio without touching holdings.

Before this slice every create/import/link call hijacked the active-book
pointer with no way to point it back; the AI operator could not recover from
that (root cause of the 2026-07-07 incident cleanup gap).
"""

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.storage import LocalStateStore


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_select_moves_only_the_active_pointer(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    first = client.post("/api/portfolio/create", json={"name": "Book A"}).json()
    first_id = first["active_portfolio_id"]
    second = client.post("/api/portfolio/create", json={"name": "Book B"}).json()
    second_id = second["active_portfolio_id"]
    assert first_id != second_id

    selected = client.post("/api/portfolio/select", json={"portfolio_id": first_id})
    assert selected.status_code == 200
    body = selected.json()
    assert body["active_portfolio_id"] == first_id
    assert body["portfolio"]["name"] == "Book A"
    names = {row["portfolio_id"]: row["name"] for row in body["portfolios"]}
    assert names == {first_id: "Book A", second_id: "Book B"}


def test_select_persists_across_reads(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    first_id = client.post("/api/portfolio/create", json={"name": "Book A"}).json()[
        "active_portfolio_id"
    ]
    client.post("/api/portfolio/create", json={"name": "Book B"})
    client.post("/api/portfolio/select", json={"portfolio_id": first_id})
    assert client.get("/api/portfolio").json()["active_portfolio_id"] == first_id


def test_select_unknown_or_blank_id_is_rejected(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    client.post("/api/portfolio/create", json={"name": "Book A"})
    unknown = client.post(
        "/api/portfolio/select", json={"portfolio_id": "portfolio-does-not-exist"}
    )
    assert unknown.status_code == 400
    assert "Unknown portfolio id" in unknown.json()["detail"]
    blank = client.post("/api/portfolio/select", json={"portfolio_id": ""})
    assert blank.status_code == 422
    extra = client.post(
        "/api/portfolio/select",
        json={"portfolio_id": "portfolio-x", "confirm": True},
    )
    assert extra.status_code == 422


def test_select_action_registered_in_agent_contract(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    contract = client.get("/api/agent-contract").json()
    actions = {action["action_id"]: action for action in contract["actions"]}
    entry = actions["portfolio_select"]
    assert entry["method"] == "POST"
    assert entry["endpoint"] == "/api/portfolio/select"
    assert entry["safety_class"] == "local_portfolio_state_only"
    assert entry["requires_confirmation"] is False
