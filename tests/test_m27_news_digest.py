"""M27-R2 — operator-written headline digest (system-language titles/summaries)."""

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.storage import LocalStateStore


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_digest_write_merges_and_persists_with_backup(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    first = client.post("/api/news/digest", json={"items": [
        {"item_id": "coindesk-abc123", "title_zh": "比特幣測試標題", "summary_zh": "一句話摘要"}
    ]})
    assert first.status_code == 200
    assert first.json()["entry_count"] == 1

    second = client.post("/api/news/digest", json={"items": [
        {"item_id": "fed-xyz789", "title_zh": "聯準會測試標題"}
    ]})
    assert second.status_code == 200
    body = second.json()
    assert body["entry_count"] == 2
    assert body["items"]["coindesk-abc123"]["title_zh"] == "比特幣測試標題"
    assert body["items"]["fed-xyz789"]["summary_zh"] == ""

    read_back = client.get("/api/news/digest").json()
    assert read_back["entry_count"] == 2
    backup = server.STORE.news_digest_state_path.with_name("news_digest_state.json.bak1")
    assert backup.is_file()


def test_digest_rejects_invalid_writes(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.post("/api/news/digest", json={"items": []}).status_code == 400
    assert client.post("/api/news/digest", json={"items": [{"title_zh": "無 id"}]}).status_code == 400
    assert client.post(
        "/api/news/digest", json={"items": [{"item_id": "../escape", "title_zh": "壞 id"}]}
    ).status_code == 400


def test_digest_sections_replace_the_daily_overview(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    first = client.post("/api/news/digest", json={"sections": [
        {"category": "CRPT", "title_zh": "加密", "summary_zh": "整體回穩"},
        {"category": "MACRO", "title_zh": "總經", "summary_zh": "降息預期修正"}
    ]})
    assert first.status_code == 200
    assert len(first.json()["sections"]) == 2

    replaced = client.post("/api/news/digest", json={"sections": [
        {"category": "ALL", "title_zh": "今日一句話", "summary_zh": "市場靜"}
    ]})
    assert replaced.status_code == 200
    body = replaced.json()
    assert len(body["sections"]) == 1
    assert body["sections"][0]["title_zh"] == "今日一句話"
    # sections alone must not require items
    assert body["entry_count"] == 0


def test_item_ids_are_stable_across_refreshes() -> None:
    """The digest is keyed by item_id; ids must not change for the same article."""
    from src.local_terminal.news import _parse_rss

    body = (
        b"<rss><channel>"
        b"<item><title>Same story</title><link>https://example.com/a</link>"
        b"<description>d</description></item>"
        b"</channel></rss>"
    )
    source = {"source_id": "testfeed", "label": "Test", "category": "MKT"}
    first = _parse_rss(body, source)
    second = _parse_rss(body, source)
    assert first[0]["item_id"] == second[0]["item_id"]
    assert first[0]["item_id"].startswith("testfeed-")
    assert len(first[0]["item_id"].split("-")[-1]) == 10


def test_digest_actions_registered_in_contract(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    contract = client.get("/api/agent-contract").json()
    actions = {action["action_id"]: action for action in contract["actions"]}
    assert actions["news_digest_index"]["method"] == "GET"
    assert actions["news_digest_write"]["safety_class"] == "local_news_digest_state_only"


# ── R7: relevance gate + live auto roll-up ──────────────────────────────────


def test_finance_relevance_gate_drops_noise_keeps_finance() -> None:
    from src.local_terminal.news import _is_finance_relevant

    assert _is_finance_relevant({"title": "AI stocks sink and drag markets lower"})
    assert _is_finance_relevant({"title": "10-year yield seen slipping as Fed bets ease"})
    assert _is_finance_relevant({"title": "廣達營收寫三高 單季首度破兆"})
    # pure lifestyle / regional-crime noise the GDELT firehose drags in
    assert not _is_finance_relevant({"title": "高級女人都自帶「鬆弛感」5個習慣輕鬆養出來"})
    assert not _is_finance_relevant({"title": "Helô Pinheiro completa 83 anos e ganha homenagem"})


def test_build_live_sections_buckets_by_category_freshest_first() -> None:
    from src.local_terminal.news_digest import build_live_sections

    sections = build_live_sections([
        {"category": "CRPT", "title": "BTC older", "age_minutes": 90},
        {"category": "CRPT", "title": "BTC freshest", "age_minutes": 5},
        {"category": "TWN", "title": "台積電領漲", "age_minutes": 20},
    ])
    by_cat = {s["category"]: s for s in sections}
    assert by_cat["加密"]["title_zh"] == "BTC freshest"  # newest wins
    assert by_cat["加密"]["summary_zh"] == "BTC older"  # the runner-up headline, not a tally
    assert by_cat["台股"]["title_zh"] == "台積電領漲"
    assert by_cat["台股"]["summary_zh"] == ""  # single item → no runner-up
    # TWN is ordered ahead of CRPT
    assert [s["category"] for s in sections] == ["台股", "加密"]


def test_is_digest_fresh_only_today() -> None:
    from src.local_terminal.news_digest import is_digest_fresh

    assert is_digest_fresh("2026-07-08T09:00:00Z", "2026-07-08") is True
    assert is_digest_fresh("2026-07-07T23:59:00Z", "2026-07-08") is False
    assert is_digest_fresh("", "2026-07-08") is False


def _seed_live_news(monkeypatch) -> None:
    monkeypatch.setattr(server, "_news_payload_from_store", lambda **_: {
        "items": [
            {"category": "TWN", "title": "台積電領漲", "age_minutes": 5},
            {"category": "CRPT", "title": "BTC steady near 64k", "age_minutes": 12},
        ],
        "status": {"last_update": "2026-07-08T01:00:00Z"},
    })


def test_stale_curated_digest_rolls_up_live(tmp_path, monkeypatch) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    store.write_news_digest_state({
        "items": {},
        "sections": [{"category": "CRPT", "title_zh": "昨天寫的話", "summary_zh": ""}],
        "updated_at": "2020-01-01T00:00:00Z",
    })
    _seed_live_news(monkeypatch)
    body = TestClient(server.create_app()).get("/api/news/digest").json()
    assert body["origin"] == "auto"
    titles = [s["title_zh"] for s in body["sections"]]
    assert "昨天寫的話" not in titles
    assert any("台積" in title for title in titles)


def test_fresh_curated_digest_is_kept(tmp_path, monkeypatch) -> None:
    from datetime import UTC, datetime

    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    today = datetime.now(tz=UTC).date().isoformat()
    store.write_news_digest_state({
        "items": {},
        "sections": [{"category": "CRPT", "title_zh": "今天的話", "summary_zh": "整體回穩"}],
        "updated_at": f"{today}T09:00:00Z",
    })
    _seed_live_news(monkeypatch)
    body = TestClient(server.create_app()).get("/api/news/digest").json()
    assert body["origin"] == "ai"
    assert body["sections"][0]["title_zh"] == "今天的話"


def test_digest_guard_drops_mojibake_entries() -> None:
    """U+FFFD in a digest entry marks a decode failure — it must never render."""
    from src.local_terminal.news_digest import (
        normalize_news_digest_state,
        write_news_digest,
    )

    bad = "�[�K��"  # big5-as-utf-8 mojibake, like the stored garbage

    # pre-existing garbage is filtered on read/normalize; clean entries survive
    normalized = normalize_news_digest_state({
        "items": {
            "coindesk-good1": {"title_zh": "比特幣回穩", "summary_zh": "小幅反彈"},
            "coindesk-bad1": {"title_zh": bad, "summary_zh": bad},
        },
        "sections": [
            {"category": "加密", "title_zh": "加密", "summary_zh": "整體回穩"},
            {"category": "台股", "title_zh": bad, "summary_zh": "正常摘要"},
        ],
    })
    assert set(normalized["items"]) == {"coindesk-good1"}
    assert [s["title_zh"] for s in normalized["sections"]] == ["加密"]

    # a clean title with a garbled summary keeps the title, drops only the summary
    kept = normalize_news_digest_state({"items": {"x-1": {"title_zh": "正常標題", "summary_zh": bad}}})
    assert kept["items"]["x-1"]["summary_zh"] == ""

    # garbage can't be written, and pre-existing garbage is pruned on the next write
    result = write_news_digest(
        {"items": {"coindesk-bad1": {"title_zh": bad, "summary_zh": ""}}, "sections": []},
        items=[
            {"item_id": "coindesk-bad2", "title_zh": bad, "summary_zh": "x"},
            {"item_id": "coindesk-good2", "title_zh": "乾淨標題", "summary_zh": "乾淨摘要"},
        ],
    )
    assert set(result["items"]) == {"coindesk-good2"}
