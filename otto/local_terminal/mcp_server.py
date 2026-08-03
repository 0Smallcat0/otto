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
DEFAULT_PROTOCOL_VERSION = "2025-06-18"
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
            "Situational awareness entry point. Returns terminal health plus the "
            "Command Center summary: current milestone, goal status, active task, "
            "risk gates (live/secrets), recovery count, and provider freshness. "
            "Call this first before operating."
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
            "Excludes safety-disabled and secret actions. Each row shows action_id, "
            "route_id, label, method, endpoint, request_contract, safety_class, "
            "whether it mutates local state, and whether it needs confirmation. "
            "Use action_id with run_action."
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
    _, health = client.call("GET", "/api/health")
    _, center = client.call("GET", "/api/command-center")
    summary: dict[str, Any] = {"health": health}
    if isinstance(center, dict):
        summary["command_center"] = {
            "current_milestone": center.get("current_milestone"),
            "mission_ledger": _compact(center.get("mission_ledger")),
            "final_goal_audit": _compact(center.get("final_goal_audit")),
            "active_task": center.get("active_task"),
            "risk_gates": center.get("risk_gates"),
            "recovery_queue_count": _safe_len(center.get("recovery_queue")),
        }
    return summary


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
    route_filter = args.get("route_id")
    rows = []
    for action in client.actions():
        if not is_mcp_safe(action):
            continue
        if route_filter and action.get("route_id") != route_filter:
            continue
        rows.append(
            {
                "action_id": action.get("action_id"),
                "route_id": action.get("route_id"),
                "label": action.get("label"),
                "method": action.get("method"),
                "endpoint": action.get("endpoint"),
                "request_contract": action.get("request_contract"),
                "safety_class": action.get("safety_class"),
                "local_mutation": action.get("local_mutation"),
                "requires_confirmation": action.get("requires_confirmation"),
            }
        )
    return {"actions": rows, "count": len(rows)}


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
    if isinstance(payload, str):
        text = payload
    else:
        text = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    if len(text) > MAX_RESULT_CHARS:
        original = len(text)
        text = (
            text[:MAX_RESULT_CHARS]
            + f"\n... [truncated {original - MAX_RESULT_CHARS} of {original} chars; use a more "
            "specific action from list_actions to narrow the response]"
        )
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def handle_request(message: dict[str, Any], client: TerminalClient) -> dict[str, Any] | None:
    """Handle one JSON-RPC message. Returns a response, or None for notifications."""

    method = message.get("method")
    request_id = message.get("id")
    is_notification = "id" not in message

    if method == "initialize":
        requested = None
        if isinstance(message.get("params"), dict):
            requested = message["params"].get("protocolVersion")
        return _result(
            request_id,
            {
                "protocolVersion": requested or DEFAULT_PROTOCOL_VERSION,
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
            return _result(request_id, _text_content(output))
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
