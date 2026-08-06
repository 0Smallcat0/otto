"""The parameter names an action advertises have to be the ones it accepts.

`request_contract` is the only thing an agent reads before calling an action.
`algo_save_strategy` printed

    {"name":"...","strategy_id" optional,"timeframe":"15m","entry":"...","exit":"...","parameters":{...}}

and the body takes `entry_conditions` and `exit_conditions`, as lists. Sent
exactly as printed it answered 400, "Entry conditions are required" — naming a
field that never appeared in the contract, to a caller that believed it had
just supplied them (2026-08-06).

Both sides come from the running app: the advertised names off the agent
contract, the accepted ones off the OpenAPI schema FastAPI derives from the
endpoint signatures. Neither can drift without the other noticing.
"""

from __future__ import annotations

import re
from typing import Any

import pytest
from fastapi.testclient import TestClient

from otto.local_terminal import server


@pytest.fixture(scope="module")
def api() -> TestClient:
    return TestClient(server.create_app())


def _spec(api: TestClient) -> dict[str, Any]:
    return api.get("/openapi.json").json()


def _actions(api: TestClient) -> list[dict[str, Any]]:
    return api.get("/api/agent-contract").json()["actions"]


def _query_params(spec: dict[str, Any], endpoint: str, method: str) -> set[str] | None:
    operation = (spec["paths"].get(endpoint) or {}).get(method.lower())
    if operation is None:
        return None
    return {p["name"] for p in operation.get("parameters", []) if p.get("in") == "query"}


def _body_properties(spec: dict[str, Any], endpoint: str, method: str) -> set[str] | None:
    operation = (spec["paths"].get(endpoint) or {}).get(method.lower())
    if operation is None or "requestBody" not in operation:
        return None
    schema = operation["requestBody"]["content"].get("application/json", {}).get("schema", {})

    def resolve(node: dict[str, Any]) -> dict[str, Any]:
        if "$ref" in node:
            return spec["components"]["schemas"][node["$ref"].split("/")[-1]]
        for option in node.get("anyOf", []):
            if "$ref" in option:
                return resolve(option)
        return node

    return set((resolve(schema).get("properties") or {}).keys())


def _top_level_keys(example: str) -> set[str]:
    """Quoted keys at the outermost brace only.

    `portfolio_import` nests `name` and `positions` inside `portfolio`; those
    are the inner model's business, and counting them would flag a contract
    that is telling the truth.
    """
    keys: set[str] = set()
    depth = 0
    for match in re.finditer(r'[{}]|"([a-zA-Z_][a-zA-Z0-9_]*)"\s*:', example):
        marker = match.group(0)
        if marker == "{":
            depth += 1
        elif marker == "}":
            depth -= 1
        elif depth == 1:
            keys.add(match.group(1))
    return keys


def test_the_scan_reaches_every_action(api: TestClient) -> None:
    """Guards the guard: an empty sweep would pass without checking anything."""
    spec, actions = _spec(api), _actions(api)

    assert len(actions) > 100, f"only {len(actions)} actions; the contract read is broken"
    unroutable = [a["action_id"] for a in actions if a["endpoint"] not in spec["paths"]]
    assert not unroutable, f"contract advertises endpoints the app does not serve: {unroutable}"


def test_no_action_advertises_a_query_parameter_it_rejects(api: TestClient) -> None:
    spec = _spec(api)
    ghosts: dict[str, list[str]] = {}
    for action in _actions(api):
        accepted = _query_params(spec, action["endpoint"], action["method"])
        if accepted is None:
            continue
        named = set(re.findall(r"[?&]([a-zA-Z_][a-zA-Z0-9_]*)=", action.get("request_contract") or ""))
        if named - accepted:
            ghosts[action["action_id"]] = sorted(named - accepted)

    assert not ghosts, f"request_contract names query parameters the endpoint rejects: {ghosts}"


def test_no_action_advertises_a_body_field_it_rejects(api: TestClient) -> None:
    spec = _spec(api)
    ghosts: dict[str, list[str]] = {}
    checked = 0
    for action in _actions(api):
        properties = _body_properties(spec, action["endpoint"], action["method"])
        if properties is None:
            continue
        example = re.search(r"\{.*\}", action.get("request_contract") or "", re.S)
        if not example:
            continue
        checked += 1
        named = _top_level_keys(example.group(0))
        if named - properties:
            ghosts[action["action_id"]] = sorted(named - properties)

    assert checked > 10, f"only {checked} body examples inspected; the extractor is broken"
    assert not ghosts, (
        "request_contract names body fields the endpoint rejects, so a caller "
        f"following it exactly is refused for sending what it was told to send: {ghosts}"
    )


def test_the_key_reader_ignores_nested_models() -> None:
    example = '{"mode":"create_new","portfolio":{"name":"...","positions":[{"symbol":"AAPL"}]}}'

    assert _top_level_keys(example) == {"mode", "portfolio"}
