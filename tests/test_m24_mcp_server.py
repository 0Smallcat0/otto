"""M24.2 — the zero-dependency MCP server exposes a safe operator surface.

The MCP layer is driven in-process through a Starlette ``TestClient`` transport so
these tests need no network and no running server. They assert the JSON-RPC/MCP
handshake, the tool catalogue, and — most importantly — that safety-disabled and
secret actions are never operable through ``run_action``.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from otto.local_terminal import mcp_server, server
from otto.local_terminal.server import create_app
from otto.local_terminal.storage import LocalStateStore


def _make_client() -> mcp_server.TerminalClient:
    app_client = TestClient(create_app())

    def transport(method: str, path: str, body: dict[str, Any] | None) -> tuple[int, Any]:
        if method.upper() == "GET":
            response = app_client.get(path)
        else:
            response = app_client.post(path, json=body or {})
        content_type = response.headers.get("content-type", "")
        payload = response.json() if content_type.startswith("application/json") else response.text
        return response.status_code, payload

    return mcp_server.TerminalClient(transport)


def _rpc(client: mcp_server.TerminalClient, method: str, params: dict[str, Any] | None = None,
         request_id: Any = 1) -> dict[str, Any] | None:
    message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
    if request_id is not None:
        message["id"] = request_id
    if params is not None:
        message["params"] = params
    return mcp_server.handle_request(message, client)


def _call_tool(client: mcp_server.TerminalClient, name: str,
               arguments: dict[str, Any] | None = None) -> tuple[dict[str, Any], Any]:
    response = _rpc(client, "tools/call", {"name": name, "arguments": arguments or {}}, request_id=9)
    assert response is not None
    result = response["result"]
    text = result["content"][0]["text"]
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError:
        # Large payloads are truncated by design and are no longer valid JSON.
        parsed = text
    return result, parsed


def test_every_route_answers_with_parseable_json() -> None:
    """Measured: 7 of 16 routes came back severed.

    get_route hands the route's own page to the model, and cutting the
    serialised string at a character count guarantees the tail is invalid JSON.
    markets, crypto, paper, news, quant_lab, settings and profile all arrived
    that way — 44% of the routes, through one of only six tools — so an agent
    asking what a route holds got a blob it could not parse.
    """
    client = _make_client()

    for route in mcp_server._tool_list_routes(client, {})["routes"]:
        result = mcp_server._text_content(
            mcp_server._tool_get_route(client, {"route_id": route["route_id"]})
        )
        text = result["content"][0]["text"]
        json.loads(text)  # raises if the truncation severed the structure


def test_an_oversize_response_becomes_a_map_of_where_the_weight_is() -> None:
    """The truncation notice is the one response that must never be malformed.

    It is what the agent has to act on to recover, so instead of a prefix of the
    payload it returns the payload's shape — which keys exist, how big each is,
    largest first — so the next call can be narrower on purpose.
    """
    payload = {"small": "x", "huge": {"a": "y" * 60_000, "b": "z" * 10}}

    text = mcp_server._text_content(payload)["content"][0]["text"]
    notice = json.loads(text)

    assert notice["truncated"] is True
    assert notice["original_chars"] > mcp_server.MAX_RESULT_CHARS
    assert len(text) < mcp_server.MAX_RESULT_CHARS
    assert [row["key"] for row in notice["keys_by_size"]] == ["huge", "small"]
    # One key holding nearly everything describes nothing, so it descends once.
    assert notice["largest_key"] == "huge"
    assert [row["key"] for row in notice["inner_keys_by_size"]] == ["a", "b"]


def test_a_list_payload_reports_its_length_rather_than_a_severed_prefix() -> None:
    text = mcp_server._text_content([{"x": "y" * 100} for _ in range(2_000)])["content"][0]["text"]
    notice = json.loads(text)

    assert notice["truncated"] is True
    assert notice["list_length"] == 2_000


def test_a_spread_out_payload_is_not_wrongly_descended_into() -> None:
    """Descending is only right when one key really is the payload."""
    payload = {"a": "x" * 20_000, "b": "y" * 20_000, "c": "z" * 20_000}

    notice = json.loads(mcp_server._text_content(payload)["content"][0]["text"])

    assert notice["truncated"] is True
    assert "inner_keys_by_size" not in notice


def test_an_oversize_plain_string_still_truncates_as_text() -> None:
    """Error messages are already prose; there is no structure to preserve."""
    text = mcp_server._text_content("e" * 60_000)["content"][0]["text"]

    assert text.startswith("eeee")
    assert "[truncated" in text


def test_the_action_catalogue_fits_in_the_result_limit_and_still_parses() -> None:
    """The regression that matters: it used to arrive truncated into prose.

    list_actions is the second call an agent makes — the one where it finds out
    what the terminal can do. Unfiltered it returned every field of all 134
    actions: 40,106 characters, past MAX_RESULT_CHARS, cut mid-structure. The
    agent got a mangled blob that no longer parsed and had to guess.

    Each MCP tool definition is reported to cost 200-500 tokens and a handful of
    connected servers can burn 30,000-60,000 before the first user message; a
    single response spending 10,000 on a catalogue is the same disease.
    https://thenewstack.io/how-to-reduce-mcp-token-bloat/
    """
    client = _make_client()

    result, parsed = _call_tool(client, "list_actions")

    text = result["content"][0]["text"]
    assert "[truncated" not in text, "the catalogue no longer fits in one response"
    assert len(text) < mcp_server.MAX_RESULT_CHARS
    assert isinstance(parsed, dict), "truncation left it as prose instead of JSON"
    assert parsed["count"] > 100


def test_the_unfiltered_catalogue_is_an_index_and_says_how_to_drill_in() -> None:
    client = _make_client()

    _, index = _call_tool(client, "list_actions")
    row = index["actions"][0]

    # Enough to choose with...
    assert set(row) >= {"action_id", "route_id", "label", "method"}
    # ...and nothing to read.
    assert "request_contract" not in row
    assert "safety_class" not in row
    assert "endpoint" not in row
    assert index["route_ids"], "an index with no way to drill in is a dead end"
    assert "route_id=" in index["detail_hint"]

    _, detail = _call_tool(client, "list_actions", {"route_id": index["route_ids"][0]})
    assert "request_contract" in detail["actions"][0]
    assert "endpoint" in detail["actions"][0]
    assert "detail_hint" not in detail  # already drilled in


def test_write_and_confirm_flags_survive_the_index() -> None:
    """The index may drop detail; it must not drop the safety-relevant bits.

    Which actions write state and which need confirmation is exactly what an
    agent needs before choosing, not after.
    """
    client = _make_client()

    _, index = _call_tool(client, "list_actions")

    assert any(row.get("local_mutation") for row in index["actions"])
    assert any(row.get("requires_confirmation") for row in index["actions"])


def test_tool_results_are_serialised_compactly() -> None:
    """Indentation is 13.5-22.4% of every payload and carries no information."""
    payload = {"a": 1, "b": [1, 2], "c": {"d": "e"}}

    text = mcp_server._text_content(payload)["content"][0]["text"]

    assert text == '{"a":1,"b":[1,2],"c":{"d":"e"}}'
    assert "\n" not in text


def test_a_failed_action_is_reported_as_a_failed_tool_call() -> None:
    """Every failure used to arrive as a successful tool call.

    run_action hands back the terminal's own response with its HTTP status
    inside, and isError was hardcoded false — so a 422 for malformed arguments,
    a 404 for a mistyped action id, or a 400 refusing an order all looked like
    successes with the failure buried in JSON the model had to spot unaided.
    That is the difference between an agent retrying with corrected arguments
    and an agent confidently building on a result it never received, and it is
    the most-cited complaint about this category of server: the protocol works,
    the data does not.
    https://shibui.finance/guide-best-mcp-server-stock-data
    """
    client = _make_client()

    # A real mistake an agent makes: POST body fields passed as query params.
    result, parsed = _call_tool(
        client, "run_action", {"action_id": "markets_quote_lookup", "query": {"symbols": "2330.TW"}}
    )
    assert parsed["status"] == 422
    assert result["isError"] is True, "a 422 was reported to the client as success"

    # And a real success stays a success.
    result, parsed = _call_tool(client, "run_action", {"action_id": "market_sessions"})
    assert parsed["status"] == 200
    assert result["isError"] is False


def test_a_queued_job_is_not_mistaken_for_a_failure() -> None:
    """`status` is an int for HTTP and a string for job state.

    refresh_public_data returns {"status": 200, "job": {"status": "queued"}}.
    Reading the wrong one would report every backgrounded refresh as a failed
    call — the mirror image of the bug, and just as misleading.
    """
    assert mcp_server._wrapped_http_failure({"status": "queued"}) is None
    assert mcp_server._wrapped_http_failure({"status": 200}) is None
    assert mcp_server._wrapped_http_failure({"status": 204}) is None
    assert mcp_server._wrapped_http_failure({"status": 404}) == 404
    assert mcp_server._wrapped_http_failure({"status": 502}) == 502
    assert mcp_server._wrapped_http_failure("plain text") is None


def test_the_entry_point_orients_a_stranger_not_the_maintainer(tmp_path, monkeypatch) -> None:
    """The first call anyone makes, and what it used to hand them.

    terminal_status told the reader to call it first and then returned this
    project's own build tracker: "M23.68 Final non-live completion audit", a
    mission-ledger path under docs/planning/, a do_not_redo count, and a
    resume_rule instructing them to go read PROJECT_STATE.md — files a wheel
    does not contain. Setup friction is the most-cited reason people abandon MCP
    servers before seeing what one does.
    https://mbsamuel.substack.com/p/how-can-the-model-context-protocol
    """
    # A virgin state root, because "fresh install" is the case under test and
    # the developer's own checkout is full of positions and journaled calls.
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = _make_client()

    payload = mcp_server._tool_terminal_status(client, {})

    assert "mission_ledger" not in payload
    assert "current_milestone" not in payload
    assert "final_goal_audit" not in payload
    flat = json.dumps(payload, ensure_ascii=False)
    assert "docs/planning" not in flat, "still pointing at files an install does not have"
    assert "PROJECT_STATE" not in flat

    start = payload["getting_started"]
    assert start["looks_like_a_fresh_install"] is True  # nothing has been created here
    assert start["journaled_calls"] == 0
    assert start["try_first"], "a fresh install must be told what to do first"
    assert "no API key" in start["no_account_needed"]
    # The safety line stays: it is the reason to trust the thing, not noise.
    assert payload["risk_gates"] is not None


def test_an_unsupported_protocol_version_is_answered_with_one_we_speak() -> None:
    """The spec's MUST, and the most common way an MCP server fails in the wild.

    "If the server supports the requested protocol version, it MUST respond with
    the same version. Otherwise, the server MUST respond with another protocol
    version it supports." — and then, "if the client does not support the
    version in the server's response, it SHOULD disconnect."

    This used to echo whatever was asked for. A client on a version this server
    does not implement was told yes, never got its chance to disconnect, and hit
    the mismatch later as some unrelated call misbehaving — which is exactly the
    reported shape: works with one client, fails inexplicably with another.
    https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle
    """
    client = _make_client()

    for version in mcp_server.SUPPORTED_PROTOCOL_VERSIONS:
        echoed = _rpc(client, "initialize", {"protocolVersion": version})
        assert echoed is not None
        assert echoed["result"]["protocolVersion"] == version

    for unsupported in ("1.0.0", "2099-01-01", "", "not-a-version"):
        answered = _rpc(client, "initialize", {"protocolVersion": unsupported})
        assert answered is not None
        got = answered["result"]["protocolVersion"]
        assert got != unsupported, f"claimed to speak {unsupported!r}"
        assert got == mcp_server.DEFAULT_PROTOCOL_VERSION

    # A client that omits the field entirely still gets a real version back.
    missing = _rpc(client, "initialize", {})
    assert missing is not None
    assert missing["result"]["protocolVersion"] == mcp_server.DEFAULT_PROTOCOL_VERSION


def test_the_default_is_the_latest_version_we_claim() -> None:
    """The spec says the fallback SHOULD be the latest the server supports."""
    assert mcp_server.DEFAULT_PROTOCOL_VERSION == mcp_server.SUPPORTED_PROTOCOL_VERSIONS[-1]
    assert list(mcp_server.SUPPORTED_PROTOCOL_VERSIONS) == sorted(
        mcp_server.SUPPORTED_PROTOCOL_VERSIONS
    )


def test_initialize_and_tools_list() -> None:
    client = _make_client()

    init = _rpc(client, "initialize", {"protocolVersion": "2025-06-18"})
    assert init is not None
    assert init["result"]["serverInfo"]["name"] == "otto"
    assert "tools" in init["result"]["capabilities"]
    assert init["result"]["protocolVersion"] == "2025-06-18"

    # An initialized notification (no id) yields no response.
    assert _rpc(client, "notifications/initialized", request_id=None) is None

    listed = _rpc(client, "tools/list", request_id=2)
    assert listed is not None
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert {
        "terminal_status",
        "list_routes",
        "get_route",
        "list_actions",
        "run_action",
        "refresh_public_data",
    } <= names


def test_terminal_status_and_routes() -> None:
    client = _make_client()

    result, parsed = _call_tool(client, "terminal_status")
    assert result["isError"] is False
    assert parsed["health"]["route_count"] == 16
    # The milestone tracker used to be here; the entry point now orients the
    # caller instead. See test_the_entry_point_orients_a_stranger_not_the_maintainer.
    assert parsed["risk_gates"] is not None
    assert parsed["getting_started"]["try_first"]

    result, parsed = _call_tool(client, "list_routes")
    assert parsed["count"] == 16
    assert any(row["route_id"] == "markets" for row in parsed["routes"])


def test_get_route_returns_state() -> None:
    # Assert at the handler level: a full route payload can exceed the MCP text cap,
    # so the JSON-RPC text may be truncated by design; the handler returns the object.
    client = _make_client()
    parsed = mcp_server._tool_get_route(client, {"route_id": "markets"})
    assert parsed["status"] == 200
    assert parsed["route_id"] == "markets"
    assert isinstance(parsed["state"], dict)

    # The protocol path still succeeds (no error) even when the text is truncated.
    result, _ = _call_tool(client, "get_route", {"route_id": "markets"})
    assert result["isError"] is False


def test_get_route_rejects_unknown_route() -> None:
    client = _make_client()
    result, text = _call_tool(client, "get_route", {"route_id": "nope"})
    assert result["isError"] is True
    assert "unknown route_id" in text


def test_is_mcp_safe_filters_disabled_and_secret() -> None:
    assert mcp_server.is_mcp_safe(
        {"disabled_by_safety": False, "safety_class": "public_read_only", "endpoint": "/api/markets"}
    )
    assert not mcp_server.is_mcp_safe(
        {"disabled_by_safety": True, "safety_class": "x", "endpoint": "/api/nodes/execute"}
    )
    assert not mcp_server.is_mcp_safe(
        {
            "disabled_by_safety": False,
            "safety_class": "optional_data_provider_secret_local_only",
            "endpoint": "/api/local-secrets",
        }
    )


def test_list_actions_excludes_disabled_and_secret() -> None:
    client = _make_client()
    parsed = mcp_server._tool_list_actions(client, {})
    ids = {action["action_id"] for action in parsed["actions"]}
    assert "markets_quote_reference_coverage" in ids
    assert "nodes_execute_disabled" not in ids
    # safety_class only rides on the detailed view, so the filter is checked
    # there — across every route, so nothing hides in one the index skipped.
    checked = 0
    for route_id in parsed["route_ids"]:
        detail = mcp_server._tool_list_actions(client, {"route_id": route_id})
        for action in detail["actions"]:
            assert "secret" not in (action["safety_class"] or "")
            checked += 1
    assert checked == parsed["count"], "a route in the index returned no detail"


def test_run_action_refuses_disabled_action() -> None:
    client = _make_client()
    result, text = _call_tool(client, "run_action", {"action_id": "nodes_execute_disabled"})
    assert result["isError"] is True
    assert "not operable" in text


def test_run_action_executes_safe_get() -> None:
    client = _make_client()
    parsed = mcp_server._tool_run_action(
        client, {"action_id": "markets_quote_reference_coverage"}
    )
    assert parsed["status"] == 200
    assert parsed["method"] == "GET"


def test_unavailable_terminal_reports_clean_error() -> None:
    def dead_transport(method: str, path: str, body: dict[str, Any] | None) -> tuple[int, Any]:
        raise mcp_server.TerminalUnavailable(
            "Cannot reach the local terminal at http://127.0.0.1:8765. "
            "Start it with: python -m otto.local_terminal"
        )

    client = mcp_server.TerminalClient(dead_transport)
    result, text = _call_tool(client, "terminal_status")
    assert result["isError"] is True
    assert "Start it with" in text


def test_unknown_method_returns_error() -> None:
    client = _make_client()
    response = _rpc(client, "does/not/exist", request_id=42)
    assert response is not None
    assert response["error"]["code"] == -32601


def test_ensure_backend_noop_when_reachable() -> None:
    spawned = {"n": 0}
    ok = mcp_server.ensure_backend(
        "http://127.0.0.1:8765",
        reachable=lambda _url: True,
        spawn=lambda: spawned.__setitem__("n", spawned["n"] + 1),
        sleep=lambda _s: None,
    )
    assert ok is True
    assert spawned["n"] == 0


def test_ensure_backend_disabled_by_env(monkeypatch) -> None:
    monkeypatch.setenv("LOCAL_TERMINAL_MCP_AUTOSTART", "0")
    spawned = {"n": 0}
    ok = mcp_server.ensure_backend(
        "http://127.0.0.1:8765",
        reachable=lambda _url: False,
        spawn=lambda: spawned.__setitem__("n", spawned["n"] + 1),
        sleep=lambda _s: None,
    )
    assert ok is False
    assert spawned["n"] == 0


def test_ensure_backend_refuses_non_local(monkeypatch) -> None:
    monkeypatch.delenv("LOCAL_TERMINAL_MCP_AUTOSTART", raising=False)
    spawned = {"n": 0}
    ok = mcp_server.ensure_backend(
        "http://10.0.0.5:8765",
        reachable=lambda _url: False,
        spawn=lambda: spawned.__setitem__("n", spawned["n"] + 1),
        sleep=lambda _s: None,
    )
    assert ok is False
    assert spawned["n"] == 0


def test_ensure_backend_spawns_then_reachable(monkeypatch) -> None:
    monkeypatch.delenv("LOCAL_TERMINAL_MCP_AUTOSTART", raising=False)
    state = {"spawned": False, "polls": 0}

    def reachable(_url: str) -> bool:
        return state["spawned"] and state["polls"] >= 2

    def spawn() -> None:
        state["spawned"] = True

    def sleep(_s: float) -> None:
        state["polls"] += 1

    ok = mcp_server.ensure_backend(
        "http://127.0.0.1:8765", timeout=5.0, reachable=reachable, spawn=spawn, sleep=sleep
    )
    assert ok is True
    assert state["spawned"] is True
