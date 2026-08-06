"""Two of the 87 links the terminal advertises as documentation were not.

Every `official_docs` / `docs_url` value in the package was fetched on
2026-08-06. Eighty-five answered. Two did not, and both failed the same way:
an API endpoint had been listed in a field that promises something a person
can read.

    https://data.sec.gov/api/xbrl/frames/     404
    https://api.openfigi.com/v3/mapping       405 (POST only)

The frames path resolves only with a taxonomy, tag, unit and period appended
(`.../us-gaap/Revenues/USD/CY2023Q1I.json` answers 200), and the OpenFIGI
mapping endpoint takes POST. Both entries already sat beside the real
documentation page, so the fix was to stop claiming the endpoint was one.

Fifteen more looked broken and were not: sec.gov and bls.gov answer 403 to an
unrecognised User-Agent and 200 to the terminal's own, FRED timed out once and
answered on retry, and ECB failed local certificate verification. A probe that
cannot tell "blocked" from "gone" is not evidence, so those were re-run before
anything was called dead. `api.census.gov` is unreachable from the machine this
ran on while `www.census.gov` answers, which is a network fact about that
machine rather than a fact about the link — its two entries were left alone.

There is no offline guard for the general case. Two attempts at deriving one
statically — is the doc URL a prefix of a request template, is it a request
target — both returned mostly false positives, because a documentation page and
an API endpoint are not distinguishable without asking the network. So this
pins the two that were measured rather than pretending to a rule.
"""

from __future__ import annotations

import ast
import pathlib

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "otto" / "local_terminal"

# Measured 2026-08-06: opening these answers 404 and 405 respectively.
NOT_DOCUMENTATION = {
    "https://data.sec.gov/api/xbrl/frames/",
    "https://api.openfigi.com/v3/mapping",
}


def _advertised_docs() -> dict[str, set[str]]:
    """Every URL the package offers under `official_docs` or `docs_url`."""
    found: dict[str, set[str]] = {}
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        consts = {
            target.id: node.value.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.Dict):
                continue
            for key, value in zip(node.keys, node.values):
                if not (isinstance(key, ast.Constant) and key.value in ("official_docs", "docs_url")):
                    continue
                items = value.elts if isinstance(value, ast.List | ast.Tuple) else [value]
                for item in items:
                    if isinstance(item, ast.Constant) and isinstance(item.value, str):
                        url = item.value
                    else:
                        url = consts.get(getattr(item, "id", ""), "")
                    if url.startswith("http"):
                        found.setdefault(url, set()).add(path.name)
    return found


def test_the_scan_still_finds_the_advertised_links() -> None:
    """Guards the guard: a broken extractor would pass everything silently."""
    docs = _advertised_docs()

    assert len(docs) > 50, f"only {len(docs)} advertised doc urls found; extractor is broken"
    assert "https://www.openfigi.com/api/documentation" in docs


def test_no_api_endpoint_is_offered_as_something_to_read() -> None:
    docs = _advertised_docs()
    offenders = {url: sorted(files) for url, files in docs.items() if url in NOT_DOCUMENTATION}

    assert not offenders, (
        "these answer 404/405 when opened and are listed where documentation is "
        f"promised: {offenders}"
    )
