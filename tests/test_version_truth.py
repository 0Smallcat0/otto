"""The version the app reports must be the version the project declares.

Health and the MCP serverInfo used to hard-code / mis-resolve "0.1.0" while
pyproject said 1.0.0 — a small lie that undermines every other truthfulness
claim. Both now single-source from installed dist metadata with a pyproject
fallback for checkout runs.
"""

import tomllib
from pathlib import Path

from otto.local_terminal import mcp_server, server
from otto.local_terminal.server import _package_version

PYPROJECT = tomllib.loads(
    (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
)["project"]
PYPROJECT_VERSION = PYPROJECT["version"]
PYPROJECT_NAME = PYPROJECT["name"]


def test_health_version_matches_pyproject() -> None:
    assert _package_version() == PYPROJECT_VERSION


def test_mcp_server_version_matches_pyproject() -> None:
    assert mcp_server.SERVER_VERSION == PYPROJECT_VERSION
    assert mcp_server.SERVER_VERSION != "0.1.0"


def test_dist_name_matches_pyproject() -> None:
    """Both version lookups must ask PyPI-metadata for the name we actually ship.

    `otto` and `otto-mcp` are owned on PyPI by unrelated projects. Looking up
    either would report a stranger's version on a machine that has it
    installed — a silent lie rather than a PackageNotFoundError. mcp_server is
    standalone by design and cannot import this constant, so the two copies are
    pinned here instead.
    """
    assert PYPROJECT_NAME == "otto-terminal"
    assert server.DIST_NAME == PYPROJECT_NAME
    assert mcp_server.DIST_NAME == PYPROJECT_NAME


def test_console_script_named_after_the_distribution() -> None:
    """`uvx otto-terminal` only works if a console script carries that exact name.

    Both the README one-liner and the MCP registry entry run the package with
    no --from and no explicit command, which resolves to the console script
    matching the distribution name. Rename the distribution without renaming
    the script and the published install instructions break for everyone while
    every test still passes.
    """
    scripts = PYPROJECT["scripts"]
    assert scripts[PYPROJECT_NAME] == "otto.local_terminal.mcp_server:main"
