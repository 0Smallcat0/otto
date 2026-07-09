"""AI-written headline digest (M27-R2).

Raw feeds arrive in whatever language the source publishes. The operating AI
translates/summarizes headlines into the system language and stores them here
(metadata only, bounded); the UI merges by item_id and falls back to the
original title when no digest entry exists. No external calls happen in this
module — the intelligence lives in the operator, not the terminal.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

MAX_DIGEST_ENTRIES = 200
MAX_ITEMS_PER_WRITE = 50
MAX_TITLE_CHARS = 200
MAX_SUMMARY_CHARS = 400
_MAX_ITEM_ID_CHARS = 80


class NewsDigestError(ValueError):
    """Raised when a digest write cannot be applied safely."""


MAX_SECTIONS = 12


def _looks_corrupted(text: str) -> bool:
    """True when text carries U+FFFD — the marker of a decode failure.

    Digest entries are authored by the operating AI; a replacement char means
    the source bytes were mis-decoded before the write (e.g. big5 read as
    utf-8). Such an entry is never what the operator meant, so it is dropped on
    both read and write instead of being shown as mojibake.
    """

    return "�" in text


def default_news_digest_state() -> dict[str, Any]:
    return {"items": {}, "sections": [], "updated_at": "not started"}


def normalize_news_digest_state(state: dict[str, Any] | None) -> dict[str, Any]:
    source = state if isinstance(state, dict) else {}
    raw_items = source.get("items") if isinstance(source.get("items"), dict) else {}
    items: dict[str, dict[str, str]] = {}
    for item_id, entry in raw_items.items():
        clean_id = _clean_item_id(item_id)
        if not clean_id or not isinstance(entry, dict):
            continue
        title = str(entry.get("title_zh") or "")[:MAX_TITLE_CHARS].strip()
        if not title or _looks_corrupted(title):
            continue
        summary = str(entry.get("summary_zh") or "")[:MAX_SUMMARY_CHARS].strip()
        items[clean_id] = {
            "title_zh": title,
            "summary_zh": "" if _looks_corrupted(summary) else summary,
            "written_at": str(entry.get("written_at") or ""),
        }
    raw_sections = source.get("sections") if isinstance(source.get("sections"), list) else []
    sections: list[dict[str, str]] = []
    for entry in raw_sections[:MAX_SECTIONS]:
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title_zh") or "")[:MAX_TITLE_CHARS].strip()
        if not title or _looks_corrupted(title):
            continue
        summary = str(entry.get("summary_zh") or "")[:MAX_SUMMARY_CHARS].strip()
        sections.append(
            {
                "category": str(entry.get("category") or "")[:24].strip(),
                "title_zh": title,
                "summary_zh": "" if _looks_corrupted(summary) else summary,
            }
        )
    return {
        "items": items,
        "sections": sections,
        "updated_at": str(source.get("updated_at") or "not started"),
    }


def write_news_digest(state: dict[str, Any], items: Any, sections: Any = None) -> dict[str, Any]:
    """Merge AI-written digest entries; oldest entries are pruned past the cap.

    `sections` replaces the whole 今日速覽 block when provided — it summarizes
    the feed by category, so it stays stable while item_ids roll over.
    """

    items = items if isinstance(items, list) else []
    sections = sections if isinstance(sections, list) else []
    if not items and not sections:
        raise NewsDigestError("Provide items and/or sections")
    if len(items) > MAX_ITEMS_PER_WRITE:
        raise NewsDigestError(f"At most {MAX_ITEMS_PER_WRITE} items per write")
    now = datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    next_state = normalize_news_digest_state(copy.deepcopy(state))
    accepted = 0
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item_id = _clean_item_id(raw.get("item_id"))
        title = str(raw.get("title_zh") or "").strip()[:MAX_TITLE_CHARS]
        if not item_id or not title or _looks_corrupted(title):
            continue
        summary = str(raw.get("summary_zh") or "").strip()[:MAX_SUMMARY_CHARS]
        next_state["items"][item_id] = {
            "title_zh": title,
            "summary_zh": "" if _looks_corrupted(summary) else summary,
            "written_at": now,
        }
        accepted += 1
    if items and accepted == 0 and not sections:
        raise NewsDigestError("No valid digest entries (need item_id and title_zh)")
    if sections:
        next_state["sections"] = normalize_news_digest_state({"items": {}, "sections": sections})["sections"]
        if not next_state["sections"]:
            raise NewsDigestError("No valid sections (need title_zh)")
    if len(next_state["items"]) > MAX_DIGEST_ENTRIES:
        ordered = sorted(
            next_state["items"].items(),
            key=lambda pair: pair[1].get("written_at", ""),
            reverse=True,
        )
        next_state["items"] = dict(ordered[:MAX_DIGEST_ENTRIES])
    next_state["updated_at"] = now
    return next_state


_CATEGORY_ZH = {
    "TWN": "台股", "CRPT": "加密", "ECO": "總經", "MKT": "市場",
    "TECH": "科技", "EARN": "財報", "NRG": "能源", "GEO": "地緣", "ALL": "綜合",
}
_CATEGORY_ORDER = ("TWN", "CRPT", "ECO", "MKT", "TECH", "EARN", "NRG", "GEO", "ALL")


def build_live_sections(items: Any) -> list[dict[str, str]]:
    """A deterministic 今日速覽 straight from the current feed.

    The operator's hand-written sections are richer, but until they land this
    keeps the roll-up moving with the news instead of showing yesterday's take.
    One section per category: its freshest headline plus how many it leads.
    """

    buckets: dict[str, list[dict[str, Any]]] = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        if not str(item.get("title") or "").strip():
            continue
        category = str(item.get("category") or "ALL").upper()
        buckets.setdefault(category, []).append(item)

    def freshness(entry: dict[str, Any]) -> float:
        age = entry.get("age_minutes")
        return float(age) if isinstance(age, (int, float)) else 9e9

    ordered = [c for c in _CATEGORY_ORDER if c in buckets]
    ordered += [c for c in buckets if c not in _CATEGORY_ORDER]
    sections: list[dict[str, str]] = []
    for category in ordered[:MAX_SECTIONS]:
        group = sorted(buckets[category], key=freshness)
        label = _CATEGORY_ZH.get(category, category or "其他")
        title = str(group[0].get("title") or "")[:MAX_TITLE_CHARS].strip()
        # The lead plus one more real headline per section — a "what's on top"
        # index, not a "共 N 則" tally (which read as a statistic, not a brief).
        # A genuine synthesized 速覽 is the operator's to write; this is the floor.
        second = str(group[1].get("title") or "")[:MAX_TITLE_CHARS].strip() if len(group) > 1 else ""
        sections.append({"category": label, "title_zh": title, "summary_zh": second})
    return sections


def is_digest_fresh(updated_at: Any, today: str) -> bool:
    """True when the curated digest was written on `today` (YYYY-MM-DD).

    A hand-written 速覽 from an earlier day has frozen — the caller should roll
    up a live one instead of showing yesterday's take.
    """

    return bool(today) and str(updated_at or "")[:10] == today


def news_digest_payload(state: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_news_digest_state(state)
    return {
        "items": normalized["items"],
        "sections": normalized["sections"],
        "entry_count": len(normalized["items"]),
        "updated_at": normalized["updated_at"],
        "limits": {
            "max_entries": MAX_DIGEST_ENTRIES,
            "max_items_per_write": MAX_ITEMS_PER_WRITE,
            "max_title_chars": MAX_TITLE_CHARS,
            "max_summary_chars": MAX_SUMMARY_CHARS,
        },
        "write_action": {
            "action_id": "news_digest_write",
            "method": "POST",
            "endpoint": "/api/news/digest",
            "request_contract": '{"items":[{"item_id":"...","title_zh":"...","summary_zh":"..."}]}',
        },
        "safety": {
            "safety_class": "local_news_digest_state_only",
            "mutates_local_state": True,
            "external_calls": False,
        },
    }


def _clean_item_id(value: Any) -> str:
    item_id = str(value or "").strip()
    if not item_id or len(item_id) > _MAX_ITEM_ID_CHARS:
        return ""
    if not all(ch.isalnum() or ch in {"-", "_", "."} for ch in item_id):
        return ""
    return item_id
