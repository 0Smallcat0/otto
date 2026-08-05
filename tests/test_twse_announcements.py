"""Taiwan single-name filings, accumulated because TWSE only serves today.

The news layer returned matched_count 0 against 120 stories for both of the
owner's Taiwan holdings. Every finance MCP server surveyed is an API
passthrough with "no discussion of Taiwan, Asia-specific data" — and TWSE's own
endpoints "serve only the current period so historical data must be accumulated
over time", which is precisely what a passthrough cannot do.

  https://shibui.finance/guide-best-mcp-server-stock-data
  https://blog.itick.org/en/stock-api/taiwan-stock-api-comparison-guide
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from otto.local_terminal import twse_announcements as ann

# Shaped exactly like the live rows, trailing space in "主旨 " included.
ROW_2317 = {
    "出表日期": "1150805",
    "發言日期": "1150804",
    "發言時間": "160532",
    "公司代號": "2317",
    "公司名稱": "鴻海",
    "主旨 ": "公告本公司董事會決議通過買回庫藏股",
    "符合條款": "第11款",
    "事實發生日": "1150804",
    "說明": "1.事實發生日:115/08/04",
}
ROW_3711 = {
    "出表日期": "1150805",
    "發言日期": "1150804",
    "發言時間": "050214",
    "公司代號": "3711",
    "公司名稱": "日月光投控",
    "主旨 ": "公告本公司民國115年度海外第一次無擔保轉換公司債完成訂價",
    "符合條款": "第51款",
    "事實發生日": "1150803",
    "說明": "1.事實發生日:115/08/03",
}


def test_the_subject_column_has_a_trailing_space_and_is_read_anyway() -> None:
    """TWSE ships "主旨 ", not "主旨".

    Reading the obvious key raises KeyError. A normaliser that swallowed that
    would drop the subject line of every filing while still reporting a full
    row count — announcements with no content, which reads as "nothing
    important was said".
    """
    assert "主旨" not in ROW_2317  # the obvious key genuinely is not there
    rows = ann.normalize_twse_announcements([ROW_2317])
    assert rows[0]["subject"] == "公告本公司董事會決議通過買回庫藏股"


def test_roc_dates_become_gregorian_and_refuse_to_guess() -> None:
    assert ann.roc_date_to_iso("1150804") == "2026-08-04"
    assert ann.roc_date_to_iso("") is None
    assert ann.roc_date_to_iso("garbage") is None
    assert ann.roc_date_to_iso("1159904") is None  # month 99


def test_a_row_without_a_subject_is_dropped_not_stored_blank() -> None:
    blank = dict(ROW_2317)
    blank["主旨 "] = ""
    assert ann.normalize_twse_announcements([blank]) == []


def test_merging_accumulates_and_never_double_counts() -> None:
    """The same session fetched twice must not become two filings."""
    fetched = ann.normalize_twse_announcements([ROW_2317, ROW_3711])
    now = datetime(2026, 8, 5, tzinfo=UTC)

    state, first = ann.merge_announcements(ann.default_announcement_state(), fetched, now=now)
    state, second = ann.merge_announcements(state, fetched, now=now)

    assert first["new_count"] == 2
    assert second["new_count"] == 0
    assert second["already_known_count"] == 2
    assert second["stored_count"] == 2


def test_a_second_filing_the_same_day_is_its_own_row() -> None:
    later = dict(ROW_2317)
    later["發言時間"] = "170000"
    later["主旨 "] = "公告本公司取得資產"

    rows = ann.normalize_twse_announcements([ROW_2317, later])
    state, report = ann.merge_announcements(ann.default_announcement_state(), rows)

    assert report["new_count"] == 2
    assert len({r["announcement_id"] for r in state["announcements"]}) == 2


def test_sessions_held_makes_a_gap_visible_as_a_gap() -> None:
    """An empty answer must be distinguishable from a quiet company.

    Without the list of sessions actually fetched, "no filings for 2834" reads
    identically whether the store has watched every session this month or was
    started this morning.
    """
    fetched = ann.normalize_twse_announcements([ROW_2317])
    state, _ = ann.merge_announcements(ann.default_announcement_state(), fetched)

    answer = ann.announcements_for(state, ["2834.TW", "2317.TW"])

    assert answer["by_symbol"]["2834.TW"] == []
    assert answer["sessions_held"] == ["2026-08-04"]
    assert "never that the company said nothing" in answer["note"]


def test_lookup_matches_the_owner_symbol_format() -> None:
    fetched = ann.normalize_twse_announcements([ROW_2317])
    state, _ = ann.merge_announcements(ann.default_announcement_state(), fetched)

    answer = ann.announcements_for(state, ["2317.tw"])

    assert answer["matched_count"] == 1
    assert answer["by_symbol"]["2317.TW"][0]["name"] == "鴻海"


def test_the_store_is_capped_and_says_what_it_dropped(monkeypatch) -> None:
    monkeypatch.setattr(ann, "MAX_ANNOUNCEMENTS", 2)
    rows = []
    for i in range(4):
        row = dict(ROW_2317)
        row["發言時間"] = f"1000{i}0"
        row["主旨 "] = f"公告 {i}"
        rows.append(row)
    fetched = ann.normalize_twse_announcements(rows)

    state, report = ann.merge_announcements(ann.default_announcement_state(), fetched)

    assert report["dropped_oldest_count"] == 2
    assert report["stored_count"] == 2


def test_a_fetch_failure_raises_rather_than_reading_as_no_filings(monkeypatch) -> None:
    """Silence and an outage must not look the same.

    "The free tier silently returns incomplete data without an error" is the
    single most-cited complaint about this whole category of server; returning
    [] here would reproduce it exactly.
    """

    def _boom(*_args, **_kwargs):
        raise TimeoutError("connection timed out")

    monkeypatch.setattr(ann, "urlopen", _boom)

    with pytest.raises(ann.TwseAnnouncementError, match="fetch failed"):
        ann.fetch_twse_announcements()


def test_a_non_list_response_raises() -> None:
    with pytest.raises(ann.TwseAnnouncementError, match="was not a list"):
        ann.normalize_twse_announcements({"stat": "error"})


def test_live_twse_still_serves_the_columns_this_reads() -> None:
    """Contract check against the real endpoint, skipped when offline."""
    try:
        rows = ann.fetch_twse_announcements()
    except ann.TwseAnnouncementError as exc:  # pragma: no cover - network dependent
        pytest.skip(f"TWSE unreachable: {exc}")
    assert rows, "TWSE returned no announcements at all"
    first = rows[0]
    assert first["symbol"].endswith(".TW")
    assert first["subject"], "the trailing-space subject column moved again"
    assert first["spoken_at"], "發言日期 no longer parses as an ROC date"
