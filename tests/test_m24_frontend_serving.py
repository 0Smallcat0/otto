"""M24.1 — the backend serves the built frontend for single-process self-use.

The UI mount is a catch-all at ``/`` that must not shadow the ``/api`` routes,
and the terminal must still run (API only) when the frontend has not been built.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal.server import create_app


def _write_fake_dist(dist: Path) -> None:
    dist.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text(
        "<!doctype html><title>Local Terminal</title>"
        "<div id=\"root\">LOCAL TERMINAL UI</div>",
        encoding="utf-8",
    )
    assets = dist / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('ui');", encoding="utf-8")


def test_serves_ui_when_dist_present(tmp_path: Path) -> None:
    _write_fake_dist(tmp_path)
    client = TestClient(create_app(frontend_dist=tmp_path))

    root = client.get("/")
    assert root.status_code == 200
    assert "LOCAL TERMINAL UI" in root.text

    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "console.log" in asset.text

    # API endpoints keep precedence over the catch-all UI mount.
    health = client.get("/api/health")
    assert health.status_code == 200
    body = health.json()
    assert body["route_count"] == 16
    assert body["clean_room"] is True

    shell = client.get("/api/shell-contract")
    assert shell.status_code == 200
    assert len(shell.json()["routes"]) == 16


def test_redirects_to_health_when_dist_absent(tmp_path: Path) -> None:
    client = TestClient(create_app(frontend_dist=tmp_path / "missing"))

    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (307, 308)
    assert resp.headers["location"] == "/api/health"

    # API remains fully available even without a built UI.
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["route_count"] == 16
