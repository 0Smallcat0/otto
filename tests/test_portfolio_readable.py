"""The holdings must be readable through the action catalogue, not only the route.

"What do you make of my holdings?" is one of three prompts the README offers a
newcomer. Run against an empty install, the portfolio route exposed twelve
actions and not one of them read the portfolio: create, load_demo, select,
import, delete, link_backtest, link_paper and report all mutate;
report_index and report_health describe reports rather than positions; export
and book_detail either need an active portfolio or a {portfolio_id} that can
only be obtained by reading the portfolio first.

The state was reachable — get_route returns it — but an agent looking for what
it can *do* looks at list_actions, and there the holdings had no reader.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.mcp_server import is_mcp_safe
from otto.local_terminal.storage import LocalStateStore


def _actions(client: TestClient, route_id: str) -> list[dict]:
    contract = client.get("/api/agent-contract").json()
    return [a for a in contract["actions"] if a["route_id"] == route_id]


def test_the_holdings_have_a_reader_that_needs_nothing_to_call(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    readers = [
        a
        for a in _actions(client, "portfolio")
        if a["method"] == "GET" and "{" not in a["endpoint"] and is_mcp_safe(a)
    ]

    # export exists but 400s without an active portfolio, and the report
    # endpoints describe reports rather than positions, so the reader has to be
    # one that answers on a fresh install.
    assert any(a["action_id"] == "portfolio_read" for a in readers), (
        "an agent asked about holdings finds no way to read them"
    )


def test_reading_holdings_on_a_fresh_install_answers_rather_than_failing(
    tmp_path, monkeypatch
) -> None:
    """A terminal with no portfolio is fresh, not broken."""
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/portfolio")

    assert response.status_code == 200
    body = response.json()
    assert body["first_use"] is True
    assert body["portfolios"] == []
    # And it must say what to do next, or "no holdings" is a dead end.
    assert [a["action_id"] for a in body["actions"]] == ["create", "import", "demo"]


def test_the_contract_describes_what_that_reader_returns(tmp_path, monkeypatch) -> None:
    """Response keys are a promise; the truth test checks them against reality."""
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    entry = next(
        a for a in _actions(client, "portfolio") if a["action_id"] == "portfolio_read"
    )

    assert entry["endpoint"] == "/api/portfolio"
    assert "first_use" in entry["response_contract"]
    assert "positions" in entry["response_contract"]
    assert entry["local_mutation"] is False
