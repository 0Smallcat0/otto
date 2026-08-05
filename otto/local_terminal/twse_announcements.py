"""Taiwan single-name company announcements — the information layer nobody carries.

Asked for context on the owner's two Taiwan holdings, this terminal's news layer
returned `matched_count: 0` against 120 available stories, all of them Federal
Reserve orders and CoinDesk. The agent was, on the only two names holding his
real money, blind — and when a 7% "crash" turned out to be an ex-dividend, it
was found by reading TWSE's raw API by hand, not by anything the terminal knew.

Surveying what already exists says why. The finance MCP field is crowded — 116
servers on one directory alone — and every comparison of the leading ones
(Alpha Vantage, FMP, Financial Datasets, EODHD, Polygon, Yahoo) describes the
same shape: an API passthrough, and "no discussion of Taiwan, Asia-specific
data, portfolio tracking, paper trading functionality, or AI agents making
investment judgments — only data retrieval".
    https://shibui.finance/guide-best-mcp-server-stock-data

Taiwan is uncovered for a reason that is visible in the data rather than in
anyone's opinion: TWSE's open endpoints "serve only the current period so
historical data must be accumulated over time".
    https://blog.itick.org/en/stock-api/taiwan-stock-api-comparison-guide

t187ap04_L is exactly that. One fetch returns one session — 345 announcements
across 241 companies on 2026-08-04, and nothing from the day before. A
passthrough server asking it "what has 2834 announced lately" gets silence on
every day the company happened not to file. Accumulating turns the same free
endpoint into a history no passthrough can answer from, which is the whole
point: this is not a better wrapper, it is the part a wrapper structurally
cannot do.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

TWSE_ANNOUNCEMENT_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
TWSE_ANNOUNCEMENT_DOCS_URL = "https://openapi.twse.com.tw/"
TWSE_ANNOUNCEMENT_DOCS_CHECKED_AT = "2026-08-05"
TWSE_ANNOUNCEMENT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# How many announcements the local store keeps. A year of filings for a watched
# book is a few thousand rows; the cap stops an unattended daily fetch growing
# without bound.
MAX_ANNOUNCEMENTS = 4000

# TWSE ships this column name with a trailing space — "主旨 ", not "主旨".
# Reading the obvious key raises KeyError, and a normaliser that catches the
# error and moves on would drop the subject line of every announcement while
# reporting a full row count. Both spellings are accepted, and a test pins the
# real one.
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "code": ("公司代號",),
    "name": ("公司名稱",),
    "subject": ("主旨 ", "主旨"),
    "spoken_date": ("發言日期",),
    "spoken_time": ("發言時間",),
    "occurred_date": ("事實發生日",),
    "clause": ("符合條款",),
    "detail": ("說明",),
}


class TwseAnnouncementError(RuntimeError):
    """TWSE announcements could not be read."""


def _pick(row: dict[str, Any], key: str) -> str:
    for alias in _FIELD_ALIASES[key]:
        if alias in row:
            return str(row[alias] or "").strip()
    return ""


def roc_date_to_iso(value: str) -> str | None:
    """`1150804` → `2026-08-04`; anything else → None rather than a guess."""
    text = str(value or "").strip()
    if not text.isdigit() or len(text) not in (6, 7):
        return None
    year = int(text[:-4]) + 1911
    month = int(text[-4:-2])
    day = int(text[-2:])
    try:
        return datetime(year, month, day, tzinfo=UTC).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _announcement_id(row: dict[str, str]) -> str:
    """Stable identity for de-duplication across daily fetches.

    Company, session and subject together: a company can file more than once in
    a day, and the same filing reappears in every fetch made that day.
    """
    return "|".join(
        (row["code"], row["spoken_date"], row["spoken_time"], row["subject"][:80])
    )


def normalize_twse_announcements(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise TwseAnnouncementError("TWSE announcement response was not a list")
    out: list[dict[str, Any]] = []
    for raw in payload:
        if not isinstance(raw, dict):
            continue
        row = {key: _pick(raw, key) for key in _FIELD_ALIASES}
        if not row["code"] or not row["subject"]:
            continue
        out.append(
            {
                "announcement_id": _announcement_id(row),
                "symbol": f"{row['code']}.TW",
                "code": row["code"],
                "name": row["name"],
                "subject": row["subject"],
                "clause": row["clause"],
                "spoken_at": roc_date_to_iso(row["spoken_date"]),
                "occurred_at": roc_date_to_iso(row["occurred_date"]),
                "detail": row["detail"],
                "source": "twse_openapi_t187ap04",
            }
        )
    return out


def fetch_twse_announcements(*, timeout: float = 25.0) -> list[dict[str, Any]]:
    """Today's filings. One session only — this endpoint has no history."""
    request = Request(
        TWSE_ANNOUNCEMENT_URL,
        headers={"User-Agent": TWSE_ANNOUNCEMENT_USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (TimeoutError, URLError, OSError, json.JSONDecodeError) as exc:
        raise TwseAnnouncementError(f"TWSE announcement fetch failed: {exc}") from exc
    return normalize_twse_announcements(payload)


def default_announcement_state() -> dict[str, Any]:
    return {"announcements": [], "last_fetch_at": None, "fetched_sessions": []}


def normalize_announcement_state(payload: Any) -> dict[str, Any]:
    state = payload if isinstance(payload, dict) else {}
    rows = state.get("announcements")
    sessions = state.get("fetched_sessions")
    return {
        "announcements": [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else [],
        "last_fetch_at": state.get("last_fetch_at") or None,
        "fetched_sessions": sorted({str(s) for s in sessions}) if isinstance(sessions, list) else [],
    }


def merge_announcements(
    state: dict[str, Any],
    fetched: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fold one session's filings into the accumulated store.

    Existing rows are never rewritten — a filing is a published fact, and a
    re-fetch that "updated" one would quietly change history. `fetched_sessions`
    records which days this store has actually seen, so a gap is visible as a
    gap instead of reading like a quiet company.
    """
    store = normalize_announcement_state(state)
    known = {str(row.get("announcement_id")) for row in store["announcements"]}
    added = [row for row in fetched if str(row.get("announcement_id")) not in known]
    store["announcements"].extend(added)
    store["announcements"].sort(key=lambda row: (str(row.get("spoken_at") or ""), row.get("code", "")))
    dropped = max(0, len(store["announcements"]) - MAX_ANNOUNCEMENTS)
    if dropped:
        store["announcements"] = store["announcements"][dropped:]
    sessions = {str(row.get("spoken_at")) for row in fetched if row.get("spoken_at")}
    store["fetched_sessions"] = sorted(set(store["fetched_sessions"]) | sessions)
    store["last_fetch_at"] = (now or datetime.now(tz=UTC)).isoformat(timespec="seconds")
    report = {
        "fetched_count": len(fetched),
        "new_count": len(added),
        "already_known_count": len(fetched) - len(added),
        "dropped_oldest_count": dropped,
        "stored_count": len(store["announcements"]),
        "sessions_held": store["fetched_sessions"],
    }
    return store, report


def announcements_for(
    state: dict[str, Any], symbols: list[str] | tuple[str, ...], *, limit: int = 10
) -> dict[str, Any]:
    """Accumulated filings for the given symbols, newest first.

    An empty list for a symbol means this store has seen no filing from it on
    the sessions it holds — not that the company is quiet, which is why
    sessions_held travels with the answer.
    """
    store = normalize_announcement_state(state)
    wanted = {str(s).strip().upper() for s in symbols if str(s).strip()}
    by_symbol: dict[str, list[dict[str, Any]]] = {symbol: [] for symbol in sorted(wanted)}
    for row in reversed(store["announcements"]):
        symbol = str(row.get("symbol") or "").upper()
        if symbol in by_symbol and len(by_symbol[symbol]) < limit:
            by_symbol[symbol].append(row)
    return {
        "by_symbol": by_symbol,
        "matched_count": sum(len(rows) for rows in by_symbol.values()),
        "sessions_held": store["fetched_sessions"],
        "stored_count": len(store["announcements"]),
        "last_fetch_at": store["last_fetch_at"],
        "note": (
            "TWSE publishes one session at a time, so this store only knows the "
            "days it has actually fetched — listed in sessions_held. An empty "
            "list for a symbol means no filing on those sessions, never that "
            "the company said nothing. Filings are the company's own words: "
            "material events, dividends, capital changes, board decisions."
        ),
        "source": "twse_openapi_t187ap04",
    }
