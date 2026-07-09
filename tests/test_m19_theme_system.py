"""Theme-system contract (M19 origin, retargeted at the M27 AI-first shell).

M27 replaced styles.css/theme.css/terminal-components.css with a single
`ui/tokens.css` design system (instrument aesthetic: muted surfaces, one amber
accent, hairline rules, dark default + light override). These tests keep the
original principles — muted terminal surfaces, both themes present, component
coverage — pointed at the current implementation.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_SRC = ROOT / "frontend" / "src"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_theme_tokens_are_loaded_by_the_shell_entrypoint() -> None:
    main = _read(FRONTEND_SRC / "main.tsx")
    assert 'import "./ui/tokens.css";' in main


def test_theme_tokens_use_muted_terminal_surfaces_in_both_themes() -> None:
    tokens = _read(FRONTEND_SRC / "ui" / "tokens.css")

    required_tokens = (
        "--bg",
        "--bg2",
        "--line",
        "--txt",
        "--dim",
        "--faint",
        "--up",
        "--down",
        "--amber",
        "--mono",
    )
    for token in required_tokens:
        assert token in tokens, f"missing design token {token}"

    # Both themes ship: dark defaults on :root, light overrides behind the
    # data-theme attribute the top-strip toggle flips.
    assert ":root" in tokens
    assert '[data-theme="light"]' in tokens

    # Muted surfaces, not harsh extremes.
    forbidden_high_contrast_values = ("#000;", "#000000", "#ffffff")
    lowered = tokens.lower()
    for value in forbidden_high_contrast_values:
        assert value not in lowered, f"harsh contrast value {value} in tokens.css"


def test_component_styles_cover_shell_wall_tables_and_docs() -> None:
    tokens = _read(FRONTEND_SRC / "ui" / "tokens.css")

    required_selectors = (
        ".ft-shell",
        ".ft-side",
        ".ft-top",
        ".ft-alerts",
        ".ft-book",
        ".ft-wall",
        ".ft-q",
        ".ft-ev",
        ".ft-nw",
        ".ft-table th",
        ".ft-doc",
        ".ft-kpi",
    )
    for selector in required_selectors:
        assert selector in tokens, f"missing component selector {selector}"
