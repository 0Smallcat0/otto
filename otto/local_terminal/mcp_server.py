"""Zero-dependency MCP (Model Context Protocol) stdio server for the Local Terminal.

This lets an AI operator (Claude Code, Codex, or any MCP client) drive the local
terminal through a small, safe tool surface instead of scraping the UI or guessing
HTTP endpoints. It speaks newline-delimited JSON-RPC 2.0 over stdin/stdout and uses
only the Python standard library, so it stays aligned with the terminal's
minimal-dependency, offline-first, clean-room design.

Design:

- Tools are derived from the terminal's own ``/api/agent-contract`` (the single
  source of truth). ``run_action`` refuses any action that is disabled by a safety
  contract or that touches local secrets, so live trading, credential entry, and
  disabled runtimes stay unreachable through this surface.
- The terminal HTTP API is reached through an injectable transport. At runtime it is
  stdlib ``urllib`` against ``http://127.0.0.1:8765``; tests inject an in-process
  Starlette ``TestClient`` transport, so no network or running server is required.

Usage (registered in an MCP client, e.g. Claude Code ``.mcp.json``):

    python -m otto.local_terminal.mcp_server

On startup the server auto-starts the local terminal if it is not already reachable
(disable with ``LOCAL_TERMINAL_MCP_AUTOSTART=0``). If the terminal is unavailable and
auto-start is off, tools return a clear "start the terminal first" message.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from importlib.metadata import PackageNotFoundError, version as _dist_version
from pathlib import Path
from typing import Any


DIST_NAME = "otto-terminal"


def _package_version() -> str:
    """Single-source the version: installed dist metadata, else pyproject.

    The distribution is otto-terminal, never `otto`: an unrelated project owns
    that name on PyPI, so asking for `otto` here would report a stranger's
    version number on any machine that happens to have it installed.
    """
    try:
        return _dist_version(DIST_NAME)
    except PackageNotFoundError:
        pass
    try:
        import tomllib

        raw = (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        return str(tomllib.loads(raw)["project"]["version"])
    except (OSError, KeyError, ValueError):
        return "0.0.0+unknown"


SERVER_NAME = "otto"
SERVER_VERSION = _package_version()

# Every released protocol version whose wire surface this server actually
# implements. The claim is narrow on purpose: the tool surface is inputSchema
# plus `content: [{type: "text"}]` and isError, with no outputSchema, no
# structuredContent, no resources, prompts or logging — the common core of all
# three, so all three are honest. A version added to this tuple without the
# features it introduced is the same lie the negotiation bug below produced.
SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18")
DEFAULT_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[-1]
DEFAULT_BASE_URL = os.environ.get("LOCAL_TERMINAL_URL", "http://127.0.0.1:8765")
MAX_RESULT_CHARS = 40000

# Transport is a callable: (method, path, body) -> (status_code, parsed_json_or_text).
Transport = Callable[[str, str, "dict[str, Any] | None"], "tuple[int, Any]"]


class TerminalUnavailable(RuntimeError):
    """Raised when the local terminal HTTP API cannot be reached."""


def http_transport(base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0) -> Transport:
    """Build a urllib-based transport against a running terminal."""

    def _call(method: str, path: str, body: dict[str, Any] | None) -> tuple[int, Any]:
        url = base_url.rstrip("/") + path
        data = None
        headers = {"Accept": "application/json"}
        if method.upper() == "POST":
            data = json.dumps(body or {}).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return response.status, _parse_json(raw)
        except urllib.error.HTTPError as exc:  # 4xx/5xx carry a JSON error body
            raw = exc.read().decode("utf-8", errors="replace")
            return exc.code, _parse_json(raw)
        except urllib.error.URLError as exc:  # connection refused / DNS / timeout
            raise TerminalUnavailable(
                f"Cannot reach the local terminal at {base_url}. "
                "Start it with: python -m otto.local_terminal"
            ) from exc

    return _call


def _parse_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


class TerminalClient:
    """Thin client over the terminal API with a cached agent contract."""

    def __init__(self, transport: Transport) -> None:
        self._transport = transport
        self._contract: dict[str, Any] | None = None

    def call(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        return self._transport(method, path, body)

    def agent_contract(self, *, refresh: bool = False) -> dict[str, Any]:
        if self._contract is None or refresh:
            status, payload = self.call("GET", "/api/agent-contract")
            if status != 200 or not isinstance(payload, dict):
                raise TerminalUnavailable("agent-contract endpoint returned an unexpected response")
            self._contract = payload
        return self._contract

    def actions(self) -> list[dict[str, Any]]:
        return list(self.agent_contract().get("actions", []))

    def routes(self) -> list[dict[str, Any]]:
        return list(self.agent_contract().get("routes", []))


def is_mcp_safe(action: dict[str, Any]) -> bool:
    """Only expose actions that cannot reach live/secret/disabled surfaces.

    The backend enforces these gates too; this is defence in depth so the MCP tool
    surface never advertises a disabled runtime or a secret-entry path.
    """

    if action.get("disabled_by_safety"):
        return False
    safety_class = str(action.get("safety_class", ""))
    endpoint = str(action.get("endpoint", ""))
    return not ("secret" in safety_class or "/local-secrets" in endpoint)


# --- Tool definitions -------------------------------------------------------

TOOLS: list[dict[str, Any]] = [
    {
        "name": "terminal_status",
        "description": (
            "Orientation entry point. Returns terminal health, the risk gates "
            "(live trading / secrets), whether this install has any positions or "
            "journaled calls yet, and what is worth doing first. Call this "
            "before operating."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_routes",
        "description": (
            "List the 15 terminal routes with their route_id, label, category, and "
            "primary endpoint. Use route_id with get_route."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_route",
        "description": (
            "Fetch the current state of one route (e.g. dashboard, markets, "
            "portfolio, backtest, command center is under settings). Returns the "
            "route's primary read-only payload."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "route_id": {
                    "type": "string",
                    "description": "Route id from list_routes, e.g. 'markets'.",
                }
            },
            "required": ["route_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_actions",
        "description": (
            "List the safe operable actions (from the terminal agent-contract). "
            "Called with no route_id this is an index — action_id, route, method "
            "and write/confirm flags — and returns route_ids to drill into. Pass "
            "route_id to get endpoints, request contracts and safety classes for "
            "that route only. Excludes safety-disabled and secret actions. Use "
            "action_id with run_action."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "route_id": {
                    "type": "string",
                    "description": "Optional route id filter, e.g. 'backtest'.",
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "run_action",
        "description": (
            "Execute one safe terminal action by action_id (from list_actions). "
            "Refuses safety-disabled and secret actions. For POST actions pass 'body'; "
            "for endpoints with {placeholders} pass 'path_params'; optional 'query'. "
            "If the action requires confirmation, pass confirm=true."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action_id": {"type": "string", "description": "Action id from list_actions."},
                "body": {"type": "object", "description": "JSON body for POST actions (optional)."},
                "path_params": {
                    "type": "object",
                    "description": "Values for {name} segments in the endpoint (optional).",
                },
                "query": {"type": "object", "description": "Query string parameters (optional)."},
                "confirm": {
                    "type": "boolean",
                    "description": "Set true for actions that require confirmation.",
                },
            },
            "required": ["action_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "refresh_public_data",
        "description": (
            "Convenience: start the public no-key provider refresh job and return its "
            "result summary (written / available / reused cache counts). This is the "
            "common 'load fresh public data' operation; no keys or private accounts."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


# --- Tool handlers ----------------------------------------------------------


def _tool_terminal_status(client: TerminalClient, _args: dict[str, Any]) -> Any:
    """Orient whoever just connected — not this project's own build backlog.

    This used to return the Command Center's milestone tracker: "M23.68 Final
    non-live completion audit", a mission-ledger path under docs/planning/, a
    do_not_redo count, and a resume_rule instructing the reader to go and read
    PROJECT_STATE.md. Someone who has just installed a financial terminal calls
    this first — the tool description tells them to — and receives the
    maintainer's development state, pointing at files a wheel does not even
    contain. Setup friction is the most-cited reason people abandon MCP servers
    before seeing what one does; handing them somebody else's backlog at the
    entry point is friction of our own making.

    What a first call should answer: is it alive, what is switched off, is there
    anything here yet, and what is worth doing next.
    """
    _, health = client.call("GET", "/api/health")
    _, center = client.call("GET", "/api/command-center")
    summary: dict[str, Any] = {"health": health}
    if isinstance(center, dict):
        summary["risk_gates"] = center.get("risk_gates")
        summary["recovery_queue_count"] = _safe_len(center.get("recovery_queue"))
    summary["getting_started"] = _getting_started(client)
    return summary


def _getting_started(client: TerminalClient) -> dict[str, Any]:
    """Whether this install has anything in it yet, and what to do about it.

    A fresh install has no positions, no journaled calls and an empty quote
    cache. Reporting that plainly is the difference between "there is nothing
    here" and a reader concluding the terminal is broken — and it is the same
    honesty rule the rest of this codebase runs on: absent data is said out
    loud, never rendered as a zero.
    """
    status, ledger = client.call("GET", "/api/research/ledger")
    status_p, portfolio = client.call("GET", "/api/portfolio")
    calls = ledger.get("call_count_total") if isinstance(ledger, dict) else None
    books = _safe_len(portfolio.get("portfolios")) if isinstance(portfolio, dict) else None
    fresh = not calls and not books
    return {
        "journaled_calls": calls if status == 200 else None,
        "portfolios": books if status_p == 200 else None,
        "looks_like_a_fresh_install": fresh,
        "no_account_needed": (
            "Public market data, backtests, paper books and the judgment ledger "
            "all work with no API key and no sign-up. Optional keys only widen "
            "data coverage; nothing here is gated behind one."
        ),
        "try_first": (
            [
                "refresh_public_data, then run_action markets_quote_lookup with a "
                "symbol you care about — TSLA, 2330.TW and BTC-USD all resolve",
                "run_action research_scan to see the research universe ranked by "
                "today's move",
                "list_actions to see everything operable, or open the dashboard at "
                "the health url",
            ]
            if fresh
            else [
                "run_action research_ledger_read for the journaled calls and their "
                "scorecard",
                "run_action research_scan?refresh=true for today's movers and any "
                "holding with no journaled view",
            ]
        ),
        "note": (
            "Live trading, credential entry and code execution are not switched "
            "off — they are unreachable through this tool surface."
        ),
    }


def _tool_list_routes(client: TerminalClient, _args: dict[str, Any]) -> Any:
    rows = []
    for route in client.routes():
        rows.append(
            {
                "route_id": route.get("route_id"),
                "label": route.get("label"),
                "category": route.get("category"),
                "primary_endpoint": route.get("primary_endpoint"),
                "recommended_actions": route.get("recommended_actions"),
            }
        )
    return {"routes": rows, "count": len(rows)}


def _tool_get_route(client: TerminalClient, args: dict[str, Any]) -> Any:
    route_id = str(args.get("route_id", "")).strip()
    if not route_id:
        raise ValueError("route_id is required")
    route = next((r for r in client.routes() if r.get("route_id") == route_id), None)
    if route is None:
        known = ", ".join(str(r.get("route_id")) for r in client.routes())
        raise ValueError(f"unknown route_id '{route_id}'. Known routes: {known}")
    endpoint = route.get("primary_endpoint")
    status, payload = client.call("GET", endpoint)
    return {"route_id": route_id, "endpoint": endpoint, "status": status, "state": payload}


def _tool_list_actions(client: TerminalClient, args: dict[str, Any]) -> Any:
    """The action catalogue, in two depths.

    Unfiltered, this used to return every field of all 139 actions: 40,106
    characters, about 10,000 tokens — five percent of a 200k window on the
    second call an agent makes — and past MAX_RESULT_CHARS, so it was cut
    mid-structure and arrived as prose that no longer parsed as JSON. An agent
    trying to find out what the terminal can do got a mangled blob and had to
    guess.

    So the unfiltered call is an index: enough to choose, nothing to read.
    Filtering by route_id returns the full contract for that route, which is
    the only point at which the request shape matters. This is the progressive
    disclosure the token-bloat literature recommends, applied to responses
    rather than to tool definitions — those are already cheap here, six tools
    for 686 tokens against a reported norm of 200-500 tokens each.
    """
    route_filter = args.get("route_id")
    detail = bool(route_filter)
    rows = []
    for action in client.actions():
        if not is_mcp_safe(action):
            continue
        if route_filter and action.get("route_id") != route_filter:
            continue
        row = {
            "action_id": action.get("action_id"),
            "route_id": action.get("route_id"),
            "label": action.get("label"),
            "method": action.get("method"),
        }
        if action.get("local_mutation"):
            row["local_mutation"] = True
        if action.get("requires_confirmation"):
            row["requires_confirmation"] = True
        if detail:
            row["endpoint"] = action.get("endpoint")
            row["request_contract"] = action.get("request_contract")
            row["safety_class"] = action.get("safety_class")
        rows.append(row)
    result: dict[str, Any] = {"actions": rows, "count": len(rows)}
    if not detail:
        routes = sorted({str(r.get("route_id")) for r in rows})
        result["route_ids"] = routes
        result["detail_hint"] = (
            "This is the index — action_id, route and method only, plus flags for "
            "the actions that write state or need confirmation. Call again with "
            "route_id=<one of route_ids> for endpoints, request contracts and "
            "safety classes; the full catalogue in one response ran past the "
            "result limit and arrived truncated."
        )
    return result


def _tool_run_action(client: TerminalClient, args: dict[str, Any]) -> Any:
    action_id = str(args.get("action_id", "")).strip()
    if not action_id:
        raise ValueError("action_id is required")
    action = next((a for a in client.actions() if a.get("action_id") == action_id), None)
    if action is None:
        raise ValueError(f"unknown action_id '{action_id}'. Use list_actions to discover actions.")
    if not is_mcp_safe(action):
        raise ValueError(
            f"action '{action_id}' is not operable through MCP "
            "(safety-disabled or secret-related). It stays human-only by design."
        )
    if action.get("requires_confirmation") and not args.get("confirm"):
        raise ValueError(f"action '{action_id}' requires confirm=true before it runs.")

    method = str(action.get("method", "GET")).upper()
    endpoint = str(action.get("endpoint", ""))
    path = _resolve_path(endpoint, args.get("path_params") or {}, args.get("query") or {})
    body = args.get("body") if method == "POST" else None
    status, payload = client.call(method, path, body)
    return {
        "action_id": action_id,
        "method": method,
        "path": path,
        "status": status,
        "response": payload,
    }


def _tool_refresh_public_data(client: TerminalClient, _args: dict[str, Any]) -> Any:
    status, job = client.call("POST", "/api/providers/refresh-public/jobs", {})
    if not isinstance(job, dict):
        return {"status": status, "job": job}
    run_id = job.get("run_id")
    result: dict[str, Any] = {"status": status, "run_id": run_id, "job": _compact(job)}
    if run_id:
        # Report the current job snapshot; the refresh itself runs server-side.
        _, snapshot = client.call("GET", f"/api/providers/refresh-public/jobs/{run_id}")
        result["snapshot"] = _compact(snapshot)
    return result


TOOL_HANDLERS: dict[str, Callable[[TerminalClient, dict[str, Any]], Any]] = {
    "terminal_status": _tool_terminal_status,
    "list_routes": _tool_list_routes,
    "get_route": _tool_get_route,
    "list_actions": _tool_list_actions,
    "run_action": _tool_run_action,
    "refresh_public_data": _tool_refresh_public_data,
}


# --- Helpers ----------------------------------------------------------------


def _resolve_path(endpoint: str, path_params: dict[str, Any], query: dict[str, Any]) -> str:
    path = endpoint
    for key, value in path_params.items():
        path = path.replace("{" + str(key) + "}", urllib.parse.quote(str(value), safe=""))
    if "{" in path:
        missing = path[path.index("{") :]
        raise ValueError(f"endpoint '{endpoint}' still has unfilled path params: {missing}")
    if query:
        path = f"{path}?{urllib.parse.urlencode(query, doseq=True)}"
    return path


def _compact(value: Any) -> Any:
    """Shrink a nested payload so status summaries stay small."""

    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                out[key] = _shape(item)
            else:
                out[key] = item
        return out
    if isinstance(value, list):
        return _shape(value)
    return value


def _shape(value: Any) -> Any:
    if isinstance(value, list):
        return f"[{len(value)} items]"
    if isinstance(value, dict):
        return {"keys": list(value.keys())}
    return value


def _safe_len(value: Any) -> int:
    try:
        return len(value)
    except TypeError:
        return 0


# --- JSON-RPC / MCP protocol ------------------------------------------------


def _result(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _text_content(payload: Any, is_error: bool = False) -> dict[str, Any]:
    """Serialise a tool result for the model.

    Compact, not pretty-printed. Indentation carries no information and, measured
    across this terminal's own payloads, cost 13.5% to 22.4% of every response —
    80,282 characters of pure whitespace on the markets page alone, roughly
    20,000 tokens. Tool responses are read by a model with a finite context
    window, and the reported failure mode of MCP servers in practice is filling
    that window before the agent has done anything useful; spending a fifth of
    every response on line breaks is a straightforward way to contribute to it.
    Separators are pinned rather than left to the default, which pads with a
    space after each comma and colon.
    """
    if isinstance(payload, str):
        text = payload
        if len(text) > MAX_RESULT_CHARS:
            original = len(text)
            text = (
                text[:MAX_RESULT_CHARS]
                + f"\n... [truncated {original - MAX_RESULT_CHARS} of {original} chars]"
            )
        return {"content": [{"type": "text", "text": text}], "isError": is_error}

    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    if len(text) > MAX_RESULT_CHARS:
        text = json.dumps(
            _oversize_notice(payload, len(text)),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def _keys_by_size(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Each top-level key and what it weighs, largest first."""
    rows: list[dict[str, Any]] = []
    for key, value in payload.items():
        chars = len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str))
        row: dict[str, Any] = {"key": str(key), "chars": chars}
        if isinstance(value, list):
            row["list_length"] = len(value)
        rows.append(row)
    rows.sort(key=lambda r: -int(r["chars"]))
    return rows


def _oversize_notice(payload: Any, original: int) -> dict[str, Any]:
    """A response too big to send, described in JSON that still parses.

    Cutting the serialised string at a character count guarantees the result is
    no longer valid JSON — it ends mid-key or mid-escape. Measured across the
    core surface, that was happening to 7 of 16 routes through get_route
    (markets, crypto, paper, news, quant_lab, settings, profile) and to two more
    actions besides, so an agent asking what a route holds got a severed blob it
    could not parse and had to read as prose.

    A truncation notice is the one response that must never be malformed,
    because it is what the agent has to act on to recover. So instead of a
    prefix of the payload, this returns its shape: which keys exist and how
    large each one is, sorted by size, so the next call can be narrower on
    purpose rather than by guesswork.
    """
    notice: dict[str, Any] = {
        "truncated": True,
        "reason": "response exceeded the tool result limit and was replaced by this summary",
        "original_chars": original,
        "limit_chars": MAX_RESULT_CHARS,
    }
    if isinstance(payload, dict):
        sizes = _keys_by_size(payload)
        notice["keys_by_size"] = sizes
        # A wrapper whose whole weight sits in one key describes nothing:
        # get_route returns {route_id, endpoint, status, state}, so naming
        # `state` as the large one tells the agent what it already knew.
        # Descend once, into the key that is actually the payload.
        if sizes and sizes[0]["chars"] > original * 0.8:
            inner = payload.get(sizes[0]["key"])
            if isinstance(inner, dict):
                notice["largest_key"] = sizes[0]["key"]
                notice["inner_keys_by_size"] = _keys_by_size(inner)
        notice["hint"] = (
            "The keys above are this payload's own top level, largest first. Call "
            "a narrower action from list_actions (route_id filter), or one that "
            "targets the single key you need, rather than re-requesting the whole "
            "response."
        )
    elif isinstance(payload, list):
        notice["list_length"] = len(payload)
        notice["hint"] = "A list too long to send; request a narrower action or a filtered view."
    else:
        notice["hint"] = "Request a narrower action from list_actions."
    return notice


def _wrapped_http_failure(payload: Any) -> int | None:
    """The upstream HTTP status a tool wrapped, when that status was a failure.

    run_action and refresh_public_data hand back the terminal's own response
    with its status inside. Every one of them was reported to the client as
    isError=false, so a 422 for a malformed argument, a 404 for a mistyped
    action, or a 400 refusing a stale-quote order all arrived as *successful*
    tool calls with the failure buried in JSON the model had to notice on its
    own. That is the single most-cited complaint about this whole category of
    server — the protocol works, the data does not — and it is the difference
    between an agent retrying with corrected arguments and an agent confidently
    continuing on a result it never got.

    Only an integer status counts: a job payload whose `status` is the string
    "queued" is a queued job, not a failure.
    """
    if isinstance(payload, dict):
        status = payload.get("status")
        if isinstance(status, int) and not 200 <= status < 300:
            return status
    return None


def handle_request(message: dict[str, Any], client: TerminalClient) -> dict[str, Any] | None:
    """Handle one JSON-RPC message. Returns a response, or None for notifications."""

    method = message.get("method")
    request_id = message.get("id")
    is_notification = "id" not in message

    if method == "initialize":
        requested = None
        if isinstance(message.get("params"), dict):
            requested = message["params"].get("protocolVersion")
        # The spec: "If the server supports the requested protocol version, it
        # MUST respond with the same version. Otherwise, the server MUST respond
        # with another protocol version it supports." This used to echo whatever
        # was asked for, so a client requesting a version this server does not
        # implement was told yes and carried on — the client never gets its
        # chance to disconnect, and the mismatch surfaces later as some
        # unrelated call behaving strangely. That is the shape of the most
        # common complaint about MCP servers in the wild: works with one client,
        # fails inexplicably with another.
        negotiated = (
            requested if requested in SUPPORTED_PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
        )
        return _result(
            request_id,
            {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Operate the local financial terminal. Start with terminal_status, "
                    "then list_routes / get_route to inspect and list_actions / run_action "
                    "to act. Live trading, credentials, and disabled runtimes are gated off."
                ),
            },
        )

    if method in ("notifications/initialized", "initialized"):
        return None

    if method == "ping":
        return _result(request_id, {})

    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})

    if method == "tools/call":
        params = message.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            return _result(request_id, _text_content(f"unknown tool '{name}'", is_error=True))
        try:
            output = handler(client, arguments)
            failed = _wrapped_http_failure(output)
            return _result(request_id, _text_content(output, is_error=failed is not None))
        except TerminalUnavailable as exc:
            return _result(request_id, _text_content(str(exc), is_error=True))
        except ValueError as exc:
            return _result(request_id, _text_content(str(exc), is_error=True))
        except Exception as exc:
            return _result(request_id, _text_content(f"tool error: {exc}", is_error=True))

    if is_notification:
        return None
    return _error(request_id, -32601, f"method not found: {method}")


def serve(client: TerminalClient, stdin: Any = None, stdout: Any = None) -> None:
    """Read newline-delimited JSON-RPC messages until stdin closes."""

    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    for raw_line in stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        messages = message if isinstance(message, list) else [message]
        responses = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            response = handle_request(item, client)
            if response is not None:
                responses.append(response)
        for response in responses:
            stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            stdout.flush()


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _spawn_cwd() -> Path:
    """Working directory for the auto-started backend.

    A repo checkout runs from the repo root, as always. Installed as a wheel
    (pip/uvx) there is no repo; the backend keeps its state under ~/.otto
    (see storage.default_state_root), so run from there — it always exists.
    """
    root = _repo_root()
    if (root / "pyproject.toml").is_file():
        return root
    fallback = Path.home() / ".otto"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _backend_reachable(base_url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/health", timeout=timeout) as resp:
            return resp.status == 200
    except OSError:
        return False


def _spawn_backend() -> None:
    kwargs: dict[str, Any] = {
        "cwd": str(_spawn_cwd()),
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        # Detach so the backend survives after this MCP process exits.
        kwargs["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([sys.executable, "-m", "otto.local_terminal"], **kwargs)


def ensure_backend(
    base_url: str = DEFAULT_BASE_URL,
    *,
    timeout: float = 20.0,
    reachable: Callable[[str], bool] = _backend_reachable,
    spawn: Callable[[], None] = _spawn_backend,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Best-effort: ensure a local terminal is reachable, auto-starting it if allowed.

    Only a local (loopback) terminal is auto-started, and only when
    ``LOCAL_TERMINAL_MCP_AUTOSTART`` is not ``"0"``. Never raises.
    """

    if reachable(base_url):
        return True
    if os.environ.get("LOCAL_TERMINAL_MCP_AUTOSTART", "1") == "0":
        return False
    host = (urllib.parse.urlparse(base_url).hostname or "").lower()
    if host not in ("127.0.0.1", "localhost", "::1"):
        return False
    try:
        spawn()
    except OSError:
        return False
    waited = 0.0
    while waited < timeout:
        sleep(0.5)
        waited += 0.5
        if reachable(base_url):
            return True
    return False


def main() -> None:
    ensure_backend(DEFAULT_BASE_URL)
    client = TerminalClient(http_transport(DEFAULT_BASE_URL))
    serve(client)


if __name__ == "__main__":
    main()
