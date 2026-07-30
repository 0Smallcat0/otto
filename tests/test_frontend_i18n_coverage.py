"""Every Chinese string the UI renders through t() must have an English entry.

The English UI shipped with the judgment board — the thing the whole loop
exists to produce — rendering entirely in Chinese. Every string was correctly
wrapped in `t()`; none had a dictionary entry, so `t()` fell through to its
key. 61 keys were missing across three files before anyone looked
(2026-07-27 dogfood).

Nothing in the build catches this: a missing entry is valid TypeScript and
valid at runtime, it just silently returns the Chinese. This test is the only
gate, so it also checks for duplicate keys — TypeScript does reject those, but
only once they land, and the first pass at this fix introduced five because
the audit script's own regex was anchored to line start and could not see the
keys packed several to a line.
"""

from __future__ import annotations

import re
from pathlib import Path

UI_DIR = Path(__file__).resolve().parents[1] / "frontend" / "src" / "ui"
I18N = UI_DIR / "i18n.tsx"

_CJK = re.compile(r"[一-鿿]")
# Keys may share a line, so this must not anchor to line start. The lookbehind
# keeps it from matching TypeScript type annotations like `foo: "bar"`.
_KEY = re.compile(r'(?<![A-Za-z0-9_])"((?:[^"\\]|\\.)*)"\s*:')
_CALL = re.compile(r't\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
# Lookup tables whose values reach t() indirectly — invisible to _CALL, and
# missing for exactly that reason (stance, conviction and outcome labels).
_LABEL_TABLE = re.compile(
    r"const\s+\w+_LABEL\s*:\s*Record<string,\s*string>\s*=\s*\{(.*?)\}", re.S
)
_TABLE_VALUE = re.compile(r':\s*"((?:[^"\\]|\\.)*)"')


def _dictionary_keys() -> list[str]:
    return _KEY.findall(I18N.read_text(encoding="utf-8"))


def _rendered_chinese() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in sorted(UI_DIR.glob("*.tsx")):
        if path.name == I18N.name:
            continue
        source = path.read_text(encoding="utf-8")
        literals = set(_CALL.findall(source))
        for table in _LABEL_TABLE.findall(source):
            literals.update(_TABLE_VALUE.findall(table))
        chinese = {text for text in literals if _CJK.search(text)}
        if chinese:
            found[path.name] = chinese
    return found


def test_the_english_ui_has_no_chinese_left_in_it() -> None:
    keys = set(_dictionary_keys())
    missing = {
        name: sorted(text for text in texts if text not in keys)
        for name, texts in _rendered_chinese().items()
    }
    missing = {name: texts for name, texts in missing.items() if texts}

    assert not missing, (
        "these render as Chinese in the English UI — add an entry to i18n.tsx:\n"
        + "\n".join(f"  {name}: {texts}" for name, texts in missing.items())
    )


def test_the_dictionary_has_no_duplicate_keys() -> None:
    keys = _dictionary_keys()
    dupes = sorted({key for key in keys if keys.count(key) > 1})

    assert not dupes, f"duplicate keys in i18n.tsx (the later one silently wins): {dupes}"


def test_the_audit_actually_reaches_the_judgment_board() -> None:
    """Guard the guard: a regex that finds nothing would pass both tests above."""
    rendered = _rendered_chinese()

    assert "wall.tsx" in rendered, "the sweep stopped seeing wall.tsx"
    # The board's own vocabulary — if these fall out of the sweep, the check
    # has gone blind to the screen it was written for.
    assert {"我的看法", "驗收日", "集中度提醒"} <= rendered["wall.tsx"]
    # A stance label, reachable only through the lookup-table branch.
    assert "續抱觀望" in rendered["wall.tsx"]
    assert len(_dictionary_keys()) > 300
