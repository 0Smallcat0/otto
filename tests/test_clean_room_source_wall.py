import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXECUTABLE_SURFACES = (
    ROOT / "src",
    ROOT / "frontend",
    ROOT / "configs",
    ROOT / "settings",
)

# Text surfaces scanned for leaked secrets. The private third-party observation
# corpus (docs/reference/fincept-platform-test) is intentionally not published, so
# it is not part of the public tree or this scan.
TEXT_SURFACES = (
    ROOT / "AGENTS.md",
    ROOT / "README.md",
    ROOT / "PROJECT_STATE.md",
    ROOT / "configs",
    ROOT / "frontend",
    ROOT / "settings",
    ROOT / "src",
    ROOT / "tests",
    ROOT / "docs" / "planning",
)

INSTALLED_SOURCE_PATTERNS = (
    "D:\\FinceptTerminal\\app\\scripts",
    "D:/FinceptTerminal/app/scripts",
)

SECRET_LITERAL_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(
        r"\b(?:password|passwd|api[_-]?key|secret[_-]?key|private[_-]?key|token)\b"
        r"\s*[:=]\s*[\"']?[A-Za-z0-9._~+/=-]{8,}",
        re.IGNORECASE,
    ),
    re.compile(r"\bpin\b\s*(?:is|[:=：是])\s*\d{4,8}\b", re.IGNORECASE),
    re.compile(
        r"\b[A-Za-z0-9._%+-]+@(?:gmail|outlook|hotmail|yahoo|icloud)\.[A-Za-z]{2,}\b",
        re.IGNORECASE,
    ),
)

TEXT_SUFFIXES = (
    ".cjs",
    ".css",
    ".csv",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".ts",
    ".tsx",
    ".toml",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
)

SKIP_DIR_PARTS = (
    ".git",
    ".mypy_cache",
    ".omx",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _iter_text_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    if root.is_file():
        return [root] if root.suffix.lower() in TEXT_SUFFIXES else []
    return [
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and not set(path.relative_to(ROOT).parts).intersection(SKIP_DIR_PARTS)
    ]


def test_executable_surfaces_do_not_reference_installed_source() -> None:
    scanned_paths = {
        path.relative_to(ROOT).as_posix()
        for root in EXECUTABLE_SURFACES
        for path in _iter_text_files(root)
    }
    failures: list[str] = []
    for root in EXECUTABLE_SURFACES:
        for path in _iter_text_files(root):
            text = _read(path)
            for pattern in INSTALLED_SOURCE_PATTERNS:
                if pattern in text:
                    failures.append(
                        f"{path.relative_to(ROOT)} references installed source: {pattern}"
                    )

    assert "frontend/src/main.tsx" in scanned_paths
    assert "frontend/vite.config.ts" in scanned_paths
    assert failures == []


def test_product_runtime_surfaces_do_not_expose_fincept_branding() -> None:
    failures: list[str] = []
    for root in (ROOT / "src", ROOT / "frontend" / "src"):
        for path in _iter_text_files(root):
            text = _read(path)
            if "Fincept" in text or "FINCEPT" in text or "fincept" in text:
                failures.append(
                    f"{path.relative_to(ROOT)} contains product runtime Fincept reference"
                )

    assert failures == []


def test_frontend_does_not_expose_cr_credit_labels() -> None:
    failures: list[str] = []
    for path in _iter_text_files(ROOT / "frontend" / "src"):
        text = _read(path)
        if re.search(r">\s*CR\b|[\"']CR\s", text):
            failures.append(f"{path.relative_to(ROOT)} exposes CR as runtime UI copy")

    assert failures == []


def test_text_surfaces_do_not_contain_high_confidence_secret_literals() -> None:
    failures: list[str] = []
    for root in TEXT_SURFACES:
        for path in _iter_text_files(root):
            text = _read(path)
            for pattern in SECRET_LITERAL_PATTERNS:
                if pattern.search(text):
                    failures.append(
                        f"{path.relative_to(ROOT)} contains secret-like pattern: {pattern.pattern}"
                    )

    assert failures == []
