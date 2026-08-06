"""Every command the README prints has to work for the reader it prints it to.

The front page tells a stranger to install with `uvx --from git+...`, which
gives them a wheel and no repository. It then printed two commands that cannot
run from a wheel: `python evals/run_eval.py` to reproduce the eval table, and
`python -m pytest -q` under Under the hood. `[tool.setuptools.packages.find]`
ships `otto` and nothing else, so both fail on the first line with a file that
does not exist (2026-08-06).

A command that only works from a clone is fine. A command that only works from
a clone, printed to someone the same page just told to install a package, is a
broken promise on the front page.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"

# Commands that need the repository even though they name no directory.
DEV_TOOLCHAIN = ("pytest", "ruff check", "npm ")


def _shipped_top_level() -> set[str]:
    """Top-level directories that survive into an installed wheel."""
    config = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    include = config["tool"]["setuptools"]["packages"]["find"]["include"]
    return {pattern.split(".")[0].rstrip("*") for pattern in include}


def _fenced_blocks(text: str) -> list[tuple[int, str]]:
    """(offset of the block, its body) for every fenced code block."""
    return [(match.start(), match.group(1)) for match in re.finditer(r"```\w*\n(.*?)```", text, re.S)]


def _needs_the_repository(block: str, shipped: set[str]) -> bool:
    referenced = {match.group(1) for match in re.finditer(r"(?<![\w./-])([a-zA-Z][\w-]*)/", block)}
    if referenced - shipped - {"https:", "github.com"}:
        return True
    return any(tool in block for tool in DEV_TOOLCHAIN)


def _addresses_a_package_reader(text: str) -> bool:
    """Does this README tell anyone to install rather than clone?

    A developer README whose every command assumes a checkout is not lying to
    anyone — its reader already has the repository. The defect only exists on a
    page that hands someone a package and then prints repository commands.
    """
    return any(marker in text for marker in ("uvx ", "pip install", "mcp add"))


def test_no_command_needs_a_clone_without_saying_so() -> None:
    text = README.read_text(encoding="utf-8")
    if not _addresses_a_package_reader(text):
        return
    shipped = _shipped_top_level()
    offenders: list[str] = []
    for offset, block in _fenced_blocks(text):
        if not _needs_the_repository(block, shipped):
            continue
        # The block itself, or the prose introducing it, has to say so.
        preamble = text[max(0, offset - 500) : offset]
        if "clone" not in (block + preamble).lower():
            offenders.append(block.strip().splitlines()[0])
    assert not offenders, (
        "README prints commands that only run from a clone, with nothing telling "
        "a reader who installed the package that they need one:\n  "
        + "\n  ".join(offenders)
    )


def test_the_install_command_itself_needs_no_clone() -> None:
    """The one command a stranger runs first must not be caught by the rule above.

    If the install line ever starts referencing a repo path, the fix is the
    install line, not an exemption.
    """
    text = README.read_text(encoding="utf-8")
    shipped = _shipped_top_level()
    install = [block for _, block in _fenced_blocks(text) if "uvx" in block or "-m otto" in block]
    for block in install:
        assert not _needs_the_repository(block, shipped), block


def test_the_rule_can_actually_see_a_repo_only_command() -> None:
    """Without this the suite passes on a README with no code blocks at all."""
    shipped = _shipped_top_level()

    assert _needs_the_repository("python evals/run_eval.py --model claude-sonnet-5", shipped)
    assert _needs_the_repository("python -m pytest -q", shipped)
    assert _needs_the_repository("npm --prefix frontend run build", shipped)
    assert not _needs_the_repository(
        "claude mcp add otto -- uvx --from git+https://github.com/0Smallcat0/otto otto-terminal",
        shipped,
    )
    assert not _needs_the_repository("python -m otto.local_terminal", shipped)
