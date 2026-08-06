"""The first six lines an operator reads have to run as printed.

`terminal_status` ends with `getting_started.try_first`, which is the first
instruction any agent receives after connecting. Three of the five lines did
not work (2026-08-06):

  run_action research_scan?refresh=true   -> unknown action_id
  "markets_quote_lookup with a symbol"    -> 422, body field `symbols` required
  "open the dashboard at the health url"  -> health carried no url

The action ids and the health keys both come from the running terminal here,
so the guard cannot drift from what the terminal actually offers.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.mcp_server import TOOLS, _getting_started


class _StubClient:
    """Answers the two calls _getting_started makes, one branch at a time."""

    def __init__(self, *, calls: int, books: int) -> None:
        self._calls = calls
        self._books = books

    def call(self, _method: str, path: str) -> tuple[int, dict[str, Any]]:
        if path == "/api/research/ledger":
            return 200, {"call_count_total": self._calls}
        return 200, {"portfolios": {f"p{i}": {} for i in range(self._books)}}


def _both_branches() -> list[str]:
    fresh = _getting_started(_StubClient(calls=0, books=0))
    seasoned = _getting_started(_StubClient(calls=13, books=1))
    assert fresh["looks_like_a_fresh_install"] is True
    assert seasoned["looks_like_a_fresh_install"] is False
    return [*fresh["try_first"], *seasoned["try_first"]]


def _contract_actions() -> dict[str, dict[str, Any]]:
    client = TestClient(server.create_app())
    contract = client.get("/api/agent-contract").json()
    return {action["action_id"]: action for action in contract["actions"]}


def test_every_action_it_names_is_an_action_that_exists() -> None:
    actions = _contract_actions()
    named = [
        match.group(1)
        for line in _both_branches()
        for match in re.finditer(r"run_action ([^\s,]+)", line)
    ]

    assert named, "the guard found no instructions to check"
    unknown = [action_id for action_id in named if action_id not in actions]
    assert not unknown, (
        "getting_started names action ids the terminal does not have; an id "
        f"carrying its own query string is the usual cause: {unknown}"
    )


def test_a_post_is_not_described_as_if_it_took_a_bare_value() -> None:
    """`with a symbol` on an action whose body is a `symbols` array is a 422."""
    actions = _contract_actions()
    for line in _both_branches():
        for match in re.finditer(r"run_action ([^\s,]+)", line):
            action = actions[match.group(1)]
            if action["method"] == "POST":
                assert "body" in line, (
                    f"{action['action_id']} is a POST and the instruction never "
                    f"mentions a body: {line}"
                )


def test_every_identifier_it_names_is_a_tool_or_an_action() -> None:
    """Prose carries no underscores; anything that does is meant to be typed."""
    offered = {tool["name"] for tool in TOOLS}
    actions = _contract_actions()
    seen: list[str] = []
    for line in _both_branches():
        for candidate in re.findall(r"(?<![\w.\"])([a-z][a-z0-9]*(?:_[a-z0-9]+)+)", line):
            seen.append(candidate)
            assert candidate in offered or candidate in actions, (
                f"getting_started names {candidate!r}, which is neither an MCP "
                f"tool nor a contract action: {line}"
            )

    assert seen, "the guard found no identifiers to check"
    assert {"refresh_public_data", "list_actions", "run_action"} <= offered


def test_a_payload_field_it_points_at_is_a_field_that_exists() -> None:
    client = TestClient(server.create_app())
    health = client.get("/api/health").json()
    referenced = {
        match.group(1)
        for line in _both_branches()
        for match in re.finditer(r"health\.(\w+)", line)
    }

    assert referenced, "nothing points into the health payload any more"
    missing = referenced - set(health)
    assert not missing, f"getting_started points at health fields that do not exist: {missing}"


def test_the_dashboard_url_is_an_address_and_not_a_hint() -> None:
    client = TestClient(server.create_app())
    url = client.get("/api/health").json().get("url", "")

    assert url.startswith("http://"), url
    assert url.endswith("/"), "the dashboard is served at the root, not a bare origin"
