"""TWSE serves one session and keeps no history, so a day nobody fetched is gone.

Every other cache here can be rebuilt by asking again. This one cannot. Measured
on 2026-08-06 the store held 2026-08-04 while TWSE was already serving 375
filings dated 2026-08-05 — a whole session hours from being lost, with nothing
having failed and no error anywhere.

Leaving that to a scheduled task means it is lost whenever the schedule is not
running, which is most of the time. Catching up on the refresh a decision round
already makes turns "somebody must remember" into "it happens whenever the
terminal is used".
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore
from otto.local_terminal.twse_announcements import (
    TwseAnnouncementError,
    merge_announcements,
    normalize_twse_announcements,
)


def _row(code: str, day: str, time: str = "160532") -> dict[str, str]:
    return {
        "出表日期": day,
        "發言日期": day,
        "發言時間": time,
        "公司代號": code,
        "公司名稱": "鴻海",
        "主旨 ": f"公告 {code} {day} {time}",
        "符合條款": "第11款",
        "事實發生日": day,
        "說明": "detail",
    }


def _client(tmp_path, monkeypatch, fetcher):
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    monkeypatch.setattr(server, "fetch_twse_announcements", fetcher)
    return TestClient(server.create_app())


def _seed_yesterday(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    rows = normalize_twse_announcements([_row("2317", "1150804")])
    state, _ = merge_announcements(store.read_tw_announcement_state(), rows)
    store.write_tw_announcement_state(state)


def test_a_refresh_captures_the_session_that_would_otherwise_be_lost(
    tmp_path, monkeypatch
) -> None:
    _seed_yesterday(tmp_path)
    served: list[dict[str, Any]] = normalize_twse_announcements([_row("2317", "1150805")])
    client = _client(tmp_path, monkeypatch, lambda **_kw: served)

    response = client.post(
        "/api/news/packet", json={"symbols": ["2317.TW"], "refresh": True}
    )

    assert response.status_code == 200
    held = client.get("/api/research/tw-announcements").json()
    assert held["sessions_held"] == ["2026-08-04", "2026-08-05"]
    assert held["stored_count"] == 2


def test_a_packet_without_refresh_does_not_reach_for_the_network(tmp_path, monkeypatch) -> None:
    """A plain read stays a plain read; only the declared refresh goes out."""
    _seed_yesterday(tmp_path)
    calls: list[int] = []

    def _fetch(**_kw):
        calls.append(1)
        return []

    client = _client(tmp_path, monkeypatch, _fetch)

    client.post("/api/news/packet", json={"symbols": ["2317.TW"], "refresh": False})

    assert calls == []


def test_a_store_already_current_is_not_refetched(tmp_path, monkeypatch) -> None:
    """Cheap local check first, so a burst of rounds cannot hammer TWSE."""
    from datetime import UTC, datetime

    store = LocalStateStore(root=tmp_path)
    today = datetime.now(tz=UTC)
    roc_today = f"{today.year - 1911}{today.month:02d}{today.day:02d}"
    rows = normalize_twse_announcements([_row("2317", roc_today)])
    state, _ = merge_announcements(store.read_tw_announcement_state(), rows)
    store.write_tw_announcement_state(state)

    calls: list[int] = []

    def _fetch(**_kw):
        calls.append(1)
        return []

    client = _client(tmp_path, monkeypatch, _fetch)
    client.post("/api/news/packet", json={"symbols": ["2317.TW"], "refresh": True})

    assert calls == [], "the store already holds today; nothing to catch up"


def test_an_unreachable_twse_degrades_to_what_is_stored(tmp_path, monkeypatch) -> None:
    """The packet must still answer, and sessions_held must still tell the truth."""
    _seed_yesterday(tmp_path)

    def _boom(**_kw):
        raise TwseAnnouncementError("TWSE announcement fetch failed: timed out")

    client = _client(tmp_path, monkeypatch, _boom)

    response = client.post(
        "/api/news/packet", json={"symbols": ["2317.TW"], "refresh": True}
    )

    assert response.status_code == 200
    assert response.json()["summary"]["filing_count"] == 1  # yesterday's, still there
    held = client.get("/api/research/tw-announcements").json()
    assert held["sessions_held"] == ["2026-08-04"], "a gap must read as a gap"


def test_a_packet_with_no_taiwan_symbols_never_fetches(tmp_path, monkeypatch) -> None:
    _seed_yesterday(tmp_path)
    calls: list[int] = []

    def _fetch(**_kw):
        calls.append(1)
        return []

    client = _client(tmp_path, monkeypatch, _fetch)
    client.post("/api/news/packet", json={"symbols": ["AAPL"], "refresh": True})

    assert calls == []
