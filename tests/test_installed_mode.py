"""Installed (non-checkout) runs keep state in ~/.otto, never site-packages.

A repo checkout behaves exactly as before: state lives inside the repository
and LOCAL_TERMINAL_STATE_ROOT may not point outside it. Installed as a wheel
(pip/uvx) there is no repository — ``pyproject.toml`` is not beside the
package — so the default state root falls back to ``~/.otto`` and the MCP
autostart runs the backend from there.
"""

from pathlib import Path

from src.local_terminal import mcp_server, storage


def test_checkout_keeps_state_in_repo(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert storage.default_state_root(tmp_path) == tmp_path


def test_installed_run_falls_back_to_home_otto(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    bare = tmp_path / "site-packages-ish"
    bare.mkdir()
    assert storage.default_state_root(bare) == tmp_path / "home" / ".otto"


def test_repo_module_root_is_a_checkout() -> None:
    # This test runs from the repo, so the import-time default must be the repo
    # root itself — the historical behavior every other test depends on.
    assert storage.DEFAULT_STATE_ROOT == storage.ROOT
    assert (storage.ROOT / "pyproject.toml").is_file()


def test_env_root_outside_default_is_refused(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LOCAL_TERMINAL_STATE_ROOT", str(tmp_path / "elsewhere"))
    try:
        storage.state_root_from_env()
    except ValueError as exc:
        assert "LOCAL_TERMINAL_STATE_ROOT" in str(exc)
    else:  # pragma: no cover - guard must fire
        raise AssertionError("state root outside the default root must be refused")


def test_env_root_inside_default_is_accepted(monkeypatch) -> None:
    inside = storage.DEFAULT_STATE_ROOT / "evals" / ".sandbox-probe"
    monkeypatch.setenv("LOCAL_TERMINAL_STATE_ROOT", str(inside))
    assert storage.state_root_from_env() == inside.resolve()


def test_spawn_cwd_in_checkout_is_repo_root() -> None:
    assert mcp_server._spawn_cwd() == mcp_server._repo_root()


def test_spawn_cwd_installed_creates_home_otto(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    monkeypatch.setattr(mcp_server, "_repo_root", lambda: tmp_path / "bare")
    (tmp_path / "bare").mkdir()
    cwd = mcp_server._spawn_cwd()
    assert cwd == tmp_path / "home" / ".otto"
    assert cwd.is_dir()
