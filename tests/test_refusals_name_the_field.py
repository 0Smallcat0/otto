"""A refusal has to name the key the caller must fix.

`algo_save_strategy` answered 400 "Entry conditions are required" to a body
whose field is `entry_conditions`. The previous round corrected the contract
that mis-taught the name; this is the other half — a caller who got the name
wrong anyway is told about "Entry conditions" and has to guess that the key is
`entry_conditions` (2026-08-06).

Replaying every POST action with an empty body found seventeen refusals that
named no body field. Thirteen were fine: "Workflow is required" against a
`workflow` key, "Title is required" against `title` — a difference of
capitalisation, which anyone can map. "No complete backtest artifacts to link"
is about state, not a field, and naming one would be wrong. Four needed the
caller to turn prose into snake_case:

    Entry conditions are required   -> entry_conditions
    Strategy id is required         -> strategy_id
    Module slug is required         -> module_slug
    Forum post id is invalid        -> post_id

So the rule below fires only when a message spells a real body key out as
prose. State messages never trip it, and capitalisation alone never trips it.
"""

from __future__ import annotations

import pathlib
import shutil
import tempfile
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore


@pytest.fixture(scope="module")
def fresh_api() -> Iterator[TestClient]:
    """A terminal with nothing in it, so refusals are about the request."""
    root = pathlib.Path(tempfile.mkdtemp(prefix="refusal-"))
    previous = server.STORE
    server.STORE = LocalStateStore(root=root)
    try:
        yield TestClient(server.create_app())
    finally:
        server.STORE = previous
        shutil.rmtree(root, ignore_errors=True)


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


def spelled_out_keys(message: str, properties: set[str]) -> list[str]:
    """Keys the message writes as prose instead of as the key.

    `entry_conditions` written "Entry conditions" is a name the caller has to
    reconstruct. `workflow` written "Workflow" is the same word.
    """
    lowered = message.lower()
    return sorted(
        key
        for key in properties
        if "_" in key and key.replace("_", " ") in lowered and key not in lowered
    )


def test_the_replay_actually_reaches_refusals(fresh_api: TestClient) -> None:
    """Guards the guard: no refusals collected would pass without checking."""
    assert len(_refusals(fresh_api)) > 5, "the empty-body replay produced almost no refusals"


def _refusals(api: TestClient) -> list[tuple[str, str, set[str]]]:
    spec = api.get("/openapi.json").json()
    out: list[tuple[str, str, set[str]]] = []
    for action in api.get("/api/agent-contract").json()["actions"]:
        if action["method"] != "POST" or action["disabled_by_safety"]:
            continue
        properties = _body_properties(spec, action["endpoint"], action["method"])
        if not properties:
            continue
        response = api.post(action["endpoint"], json={})
        if response.status_code != 400:
            continue
        detail = response.json().get("detail")
        if isinstance(detail, str):
            out.append((action["action_id"], detail, properties))
    return out


def test_no_refusal_spells_a_field_out_instead_of_naming_it(fresh_api: TestClient) -> None:
    offenders = {
        action_id: (detail, spelled)
        for action_id, detail, properties in _refusals(fresh_api)
        if (spelled := spelled_out_keys(detail, properties))
    }

    assert not offenders, (
        "these refusals describe a body field in prose, leaving the caller to "
        f"reconstruct the key it must send: {offenders}"
    )


def test_the_rule_ignores_capitalisation_and_state_messages() -> None:
    assert spelled_out_keys("Workflow is required", {"workflow", "workflow_id"}) == []
    assert spelled_out_keys("Title is required", {"title"}) == []
    assert spelled_out_keys("No complete backtest artifacts to link", {"artifact_dir"}) == []
    assert spelled_out_keys("Entry conditions are required", {"entry_conditions"}) == [
        "entry_conditions"
    ]
