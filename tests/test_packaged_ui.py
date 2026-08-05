"""The wheel must carry the dashboard, or an installed user gets an API and no screen.

Until 2026-08-05 the built UI lived in frontend/dist, which is outside the
`otto` package and therefore absent from every wheel. `uvx --from git+https://…`
installed a working MCP server and a working API, served nothing at `/`, and
the README told the user to run `npm --prefix frontend install` in a directory
their install does not contain. Nothing failed: the API was right, there was
simply no screen and no test that noticed.

These pin the three things that have to hold together — the build writes into
the package, the packaging config ships what it writes, and the committed
bundle is internally consistent.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from otto.local_terminal import server

REPO_ROOT = Path(__file__).resolve().parents[1]
UI_DIR = REPO_ROOT / "otto" / "local_terminal" / "ui"


def test_the_build_writes_into_the_python_package() -> None:
    """vite's outDir has to sit under otto/, or setuptools cannot ship it."""
    config = (REPO_ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
    match = re.search(r'outDir:\s*"([^"]+)"', config)
    assert match, "vite.config.ts no longer declares an outDir"
    resolved = (REPO_ROOT / "frontend" / match.group(1)).resolve()
    assert resolved == UI_DIR.resolve(), f"vite builds to {resolved}, not the packaged UI dir"


def test_packaging_ships_the_ui_directory() -> None:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]
    assert "ui/**/*" in package_data["otto.local_terminal"]


def test_the_server_prefers_the_packaged_ui() -> None:
    """An installed run has no frontend/dist to fall back to."""
    assert server.PACKAGED_UI_DIST == UI_DIR
    if (UI_DIR / "index.html").is_file():
        assert server._resolve_frontend_dist() == UI_DIR
    else:  # a checkout that has not built yet still gets the legacy path
        assert server._resolve_frontend_dist() == server.LEGACY_FRONTEND_DIST


def test_the_committed_bundle_is_internally_consistent() -> None:
    """index.html must reference assets that are actually committed.

    A half-committed build — new index.html, old asset hash, or the reverse —
    installs cleanly and then serves a blank page, which is the failure mode
    that looks most like "the app is broken" and least like "a file is missing".
    """
    index = UI_DIR / "index.html"
    assert index.is_file(), "the dashboard is not built; run npm --prefix frontend run build"
    html = index.read_text(encoding="utf-8")
    referenced = re.findall(r'(?:src|href)="/(assets/[^"]+)"', html)
    assert referenced, "index.html references no bundled assets"
    for ref in referenced:
        assert (UI_DIR / ref).is_file(), f"index.html references {ref}, which is not committed"
    committed = {
        f"assets/{path.name}" for path in (UI_DIR / "assets").glob("*") if path.is_file()
    }
    orphans = committed - set(referenced)
    assert not orphans, f"stale assets from an earlier build are still committed: {sorted(orphans)}"
