"""The version the app reports must be the version the project declares.

Health and the MCP serverInfo used to hard-code / mis-resolve "0.1.0" while
pyproject said 1.0.0 — a small lie that undermines every other truthfulness
claim. Both now single-source from installed dist metadata with a pyproject
fallback for checkout runs.
"""

import tomllib
from pathlib import Path

from src.local_terminal import mcp_server
from src.local_terminal.server import _package_version

PYPROJECT_VERSION = tomllib.loads(
    (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
)["project"]["version"]


def test_health_version_matches_pyproject() -> None:
    assert _package_version() == PYPROJECT_VERSION


def test_mcp_server_version_matches_pyproject() -> None:
    assert mcp_server.SERVER_VERSION == PYPROJECT_VERSION
    assert mcp_server.SERVER_VERSION != "0.1.0"
