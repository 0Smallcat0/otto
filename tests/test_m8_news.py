import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.news import (
    NewsError,
    fetch_gdelt_doc_articles,
    news_research_brief_index,
    news_payload,
    news_topic_entity_map_payload,
    normalize_news_layout,
)
from src.local_terminal.storage import LocalStateStore


def _published(hours_ago: int) -> str:
    return (
        datetime.now(tz=UTC)
        - timedelta(hours=hours_ago)
    ).isoformat(timespec="seconds").replace("+00:00", "Z")


def _fake_news() -> list[dict[str, object]]:
    return [
        {
            "item_id": "mkt-1",
            "title": "Breaking market breadth improves into the open",
            "source": "Public Wire",
            "category": "MKT",
            "published_at": _published(2),
            "url": "https://example.test/mkt",
            "summary": "SPY and QQQ breadth watch.",
            "tags": ["SPY", "QQQ"],
        },
        {
            "item_id": "crpt-1",
            "title": "Crypto liquidity desk tracks BTC and ETH",
            "source": "Public Wire",
            "category": "CRPT",
            "published_at": _published(3),
            "url": "https://example.test/crpt",
            "summary": "BTC market watch.",
            "tags": ["BTC", "ETH"],
        },
        {
            "item_id": "old-1",
            "title": "Older energy note rolls out of the one day window",
            "source": "Public Wire",
            "category": "NRG",
            "published_at": _published(80),
            "url": "https://example.test/nrg",
            "summary": "Oil note.",
            "tags": ["OIL"],
        },
    ]


def _failing_fetcher() -> list[dict[str, object]]:
    raise NewsError("offline")


def _partial_fetcher() -> dict[str, object]:
    return {
        "items": _fake_news()[:1],
        "errors": ["coindesk: timeout"],
        "source_count": 2,
        "failed_source_count": 1,
        "providers": [
            {
                "provider_id": "public_rss_news",
                "label": "Public RSS",
                "state": "partial",
                "source_count": 2,
                "item_count": 1,
                "failed": True,
                "docs_url": "https://example.test/docs",
                "message": "One feed failed.",
            }
        ],
    }


def test_news_payload_filters_time_category_sort_and_watch() -> None:
    layout = normalize_news_layout(
        {
            "category": "CRPT",
            "time_filter": "24H",
            "sort": "REL",
            "feed_type": "WIRE",
            "watch_terms": ["BTC"],
            "watch_only": True,
        }
    )

    payload = news_payload(layout, {}, fetcher=_fake_news, refresh=True)

    assert payload["status"]["state"] == "live"
    assert payload["layout"]["category"] == "CRPT"
    assert payload["items"][0]["title"] == "Crypto liquidity desk tracks BTC and ETH"
    assert payload["items"][0]["watched"] is True
    assert payload["summary"]["visible"] == 1
    assert payload["summary"]["watched"] == 1
    assert payload["intel"]["article_count"] == 1
    assert payload["intel"]["source_count"] == 1
    assert payload["intel"]["contract"]["full_article_body"] is False
    assert payload["cache"]["items"]


def test_news_api_refresh_writes_local_cache_and_layout(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    monkeypatch.setattr(server, "NEWS_FETCHER", _fake_news)
    monkeypatch.setattr(server, "RESEARCH_FETCHER", lambda: {"errors": []})
    client = TestClient(server.create_app())

    saved = client.post(
        "/api/news/layout",
        json={
            "auto_refresh": False,
            "category": "MKT",
            "time_filter": "24H",
            "sort": "NEW",
            "feed_type": "CLST",
            "watch_terms": ["SPY", "BTC", "SPY"],
        },
    )
    refreshed = client.post("/api/news/refresh")
    state = client.get("/api/local-state")

    assert saved.status_code == 200
    assert saved.json()["layout"]["watch_terms"] == ["SPY", "BTC"]
    assert refreshed.status_code == 200
    assert refreshed.json()["status"]["state"] == "live"
    assert "cache" not in saved.json()
    assert "cache" not in refreshed.json()
    assert (tmp_path / "artifacts" / "news" / "news_cache.json").is_file()
    assert (tmp_path / "workspace_layouts" / "news.json").is_file()
    assert state.json()["storage"]["news"] == "workspace_layouts/news.json"
    assert state.json()["storage"]["news_cache"] == "artifacts/news/news_cache.json"
    assert "api_key=" not in refreshed.text.lower()
    assert refreshed.json()["safety"]["subscription_required"] is False
    assert refreshed.json()["safety"]["full_article_copy_enabled"] is False
    assert refreshed.json()["intel"]["contract"]["mode"] == "metadata_only_news_intel"


def test_news_research_brief_writes_metadata_only_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    monkeypatch.setattr(server, "NEWS_FETCHER", _fake_news)
    monkeypatch.setattr(server, "RESEARCH_FETCHER", lambda: {"errors": []})
    client = TestClient(server.create_app())
    client.post("/api/news/refresh")

    response = client.post("/api/news/research-brief")

    assert response.status_code == 200
    payload = response.json()
    brief_state = payload["research_brief"]
    artifact_dir = tmp_path / brief_state["artifact_dir"]
    assert brief_state["status"] == "generated"
    assert brief_state["summary"]["item_count"] >= 1
    assert brief_state["summary"]["topic_count"] >= 1
    assert brief_state["safety"]["full_article_copy_enabled"] is False
    assert brief_state["safety"]["article_body_storage_enabled"] is False
    for artifact in brief_state["artifacts"].values():
        assert (tmp_path / artifact).is_file()
    brief = json.loads((artifact_dir / "brief.json").read_text(encoding="utf-8"))
    source_health = json.loads(
        (artifact_dir / "source_health.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))
    assert brief["contract"] == "news_research_brief_v1"
    assert brief["safety"]["metadata_only"] is True
    assert source_health["contract"] == "news_source_health_v1"
    assert source_health["safety"]["destructive_actions_enabled"] is False
    assert manifest["artifact_contract"] == "news_research_brief_artifacts_v1"
    artifact_text = json.dumps(brief)
    assert "this field must not be copied" not in artifact_text
    assert "api_key=" not in response.text.lower()


def test_news_research_brief_index_tracks_local_artifacts_without_content_reads(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    monkeypatch.setattr(server, "NEWS_FETCHER", _fake_news)
    monkeypatch.setattr(server, "RESEARCH_FETCHER", lambda: {"errors": []})
    client = TestClient(server.create_app())

    empty = client.get("/api/news/research-briefs")
    client.post("/api/news/refresh")
    written = client.post("/api/news/research-brief")
    indexed = client.get("/api/news/research-briefs")

    assert empty.status_code == 200
    assert empty.json()["summary"]["brief_count"] == 0
    assert empty.json()["recovery_queue"][0]["recommended_action"] == "news_research_brief"
    assert empty.json()["safety"]["file_content_read"] is False
    assert written.status_code == 200
    assert written.json()["research_brief_index"]["summary"]["brief_count"] == 1
    assert indexed.status_code == 200
    payload = indexed.json()
    assert payload["mode"] == "metadata_only_news_research_brief_index"
    assert payload["contract"] == "news_research_brief_index_v1"
    assert payload["summary"]["brief_count"] == 1
    assert payload["summary"]["complete_brief_count"] == 1
    assert payload["summary"]["missing_artifact_count"] == 0
    assert payload["summary"]["recovery_queue_count"] == 0
    assert payload["briefs"][0]["brief_id"] == written.json()["research_brief"]["brief_id"]
    assert payload["briefs"][0]["artifact_count"] == 4
    assert sorted(payload["briefs"][0]["artifacts"]) == [
        "brief",
        "manifest",
        "report",
        "source_health",
    ]
    assert payload["briefs"][0]["complete"] is True
    assert payload["briefs"][0]["total_bytes"] > 0
    assert payload["safety"]["article_body_read"] is False
    assert payload["safety"]["destructive_actions_enabled"] is False
    assert "api_key=" not in indexed.text.lower()


def test_news_research_brief_index_reports_missing_artifact_recovery(
    tmp_path: Path,
) -> None:
    brief_dir = tmp_path / "artifacts" / "news" / "research_briefs" / "news-brief-test"
    brief_dir.mkdir(parents=True)
    for filename in ("brief.json", "manifest.json", "brief.md"):
        (brief_dir / filename).write_text("{}", encoding="utf-8")

    payload = news_research_brief_index(tmp_path)

    assert payload["summary"]["brief_count"] == 1
    assert payload["summary"]["complete_brief_count"] == 0
    assert payload["summary"]["missing_artifact_count"] == 1
    assert payload["briefs"][0]["complete"] is False
    assert payload["recovery_queue"][0]["artifact_path"].endswith("/source_health.json")
    assert payload["recovery_queue"][0]["recommended_action"] == "news_research_brief"
    assert payload["recovery_queue"][0]["destructive_action_required"] is False


def test_news_topic_entity_map_is_metadata_only_from_payload() -> None:
    payload = news_payload(
        normalize_news_layout({"time_filter": "30D", "watch_terms": ["BTC"]}),
        {},
        fetcher=_fake_news,
        refresh=True,
    )

    topic_map = news_topic_entity_map_payload(payload)

    assert topic_map["mode"] == "metadata_only_news_topic_entity_map"
    assert topic_map["contract"] == "news_topic_entity_map_v1"
    assert topic_map["summary"]["topic_count"] >= 2
    assert topic_map["summary"]["entity_count"] >= 3
    assert topic_map["summary"]["edge_count"] >= 3
    assert {row["label"] for row in topic_map["entities"]} >= {"BTC", "ETH", "SPY"}
    assert any(row["kind"] == "watch_term" for row in topic_map["entities"])
    assert topic_map["topics"][0]["sample_item_ids"]
    assert topic_map["edges"][0]["topic_id"].startswith("topic:")
    assert topic_map["safety"]["metadata_only"] is True
    assert topic_map["safety"]["article_body_read"] is False
    assert topic_map["safety"]["writes_local_artifacts"] is False
    assert topic_map["safety"]["provider_refresh_performed"] is False


def test_news_topic_entity_map_endpoint_does_not_refresh_or_write(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    live = news_payload(
        normalize_news_layout({"time_filter": "30D", "watch_terms": ["BTC"]}),
        {},
        fetcher=_fake_news,
        refresh=True,
    )
    store.write_news_cache(live["cache"])
    monkeypatch.setattr(server, "STORE", store)
    monkeypatch.setattr(server, "NEWS_FETCHER", _failing_fetcher)
    client = TestClient(server.create_app())

    response = client.get("/api/news/topic-entity-map")
    embedded = client.get("/api/news").json()["topic_entity_map"]

    payload = response.json()
    assert response.status_code == 200
    assert payload["contract"] == "news_topic_entity_map_v1"
    assert payload["summary"]["entity_count"] >= 3
    assert payload["safety"]["file_content_read"] is False
    assert payload["safety"]["article_body_storage_enabled"] is False
    assert payload["safety"]["secret_values_returned"] is False
    assert embedded["contract"] == payload["contract"]
    assert embedded["summary"]["entity_count"] == payload["summary"]["entity_count"]
    assert not (tmp_path / "artifacts" / "news" / "research_briefs").exists()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_news_uses_stale_cache_then_offline_fallback() -> None:
    live = news_payload(
        normalize_news_layout({"time_filter": "30D"}),
        {},
        fetcher=_fake_news,
        refresh=True,
    )

    stale = news_payload(
        normalize_news_layout({"time_filter": "30D"}),
        live["cache"],
        fetcher=_failing_fetcher,
        refresh=True,
    )
    offline = news_payload(
        normalize_news_layout({"time_filter": "30D"}),
        {},
        fetcher=_failing_fetcher,
        refresh=True,
    )

    assert stale["status"]["state"] == "stale"
    assert stale["items"]
    assert offline["status"]["state"] == "offline"
    assert offline["items"]


def test_news_malformed_cache_falls_back_and_default_offline_stays_visible() -> None:
    malformed_cache = {"fetched_at": "2026-05-22T00:00:00Z", "items": [{"category": "MKT"}]}

    malformed = news_payload(
        normalize_news_layout({"time_filter": "24H"}),
        malformed_cache,
        fetcher=_failing_fetcher,
        refresh=True,
    )
    default_offline = news_payload(
        normalize_news_layout({}),
        {},
        fetcher=_failing_fetcher,
        refresh=True,
    )

    assert malformed["status"]["state"] == "offline"
    assert malformed["items"]
    assert default_offline["layout"]["time_filter"] == "24H"
    assert default_offline["summary"]["visible"] > 0


def test_news_partial_public_refresh_reports_degraded_status() -> None:
    payload = news_payload(
        normalize_news_layout({"time_filter": "30D"}),
        {},
        fetcher=_partial_fetcher,
        refresh=True,
    )

    assert payload["status"]["state"] == "partial"
    assert payload["status"]["failed_source_count"] == 1
    assert payload["status"]["source_errors"] == ["coindesk: timeout"]
    assert payload["intel"]["provider_states"][0]["provider_id"] == "public_rss_news"
    assert payload["intel"]["provider_states"][0]["failed"] is True
    assert payload["items"]


def test_news_layout_caps_watch_terms() -> None:
    layout = normalize_news_layout(
        {"watch_terms": [f"SYM{index}" for index in range(20)], "category": "bad"}
    )

    assert layout["category"] == "ALL"
    assert len(layout["watch_terms"]) == 12


def test_gdelt_doc_articles_are_metadata_only() -> None:
    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return (
                b'{"articles":[{"url":"https://example.test/energy","title":"Oil gains as energy desks track supply risk",'
                b'"domain":"example.test","sourcecountry":"United States","language":"English","seendate":"20260524163000",'
                b'"body":"this field must not be copied"}]}'
            )

    def opener(request: object, timeout: int) -> Response:
        assert timeout == 8
        assert "mode=artlist" in request.full_url.lower()
        assert "format=json" in request.full_url.lower()
        return Response()

    items = fetch_gdelt_doc_articles(opener=opener)

    assert len(items) == 1
    assert items[0]["provider_id"] == "gdelt_doc_public"
    assert items[0]["category"] == "NRG"
    assert items[0]["domain"] == "example.test"
    assert items[0]["source_country"] == "United States"
    assert items[0]["language"] == "English"
    assert "this field must not be copied" not in str(items[0])
    assert items[0]["summary"] == "GDELT DOC metadata-only article hit; no full article body is stored."


def test_unparseable_news_date_stays_unknown_not_now() -> None:
    """A garbled date must never be stamped 'now' — that floats junk to the top."""
    from src.local_terminal.news import _age_minutes, _normalize_item, _parse_date

    assert _parse_date("") == ""
    assert _parse_date("not a real date") == ""
    assert _age_minutes("") > 60 * 24  # unknown → treated as very old, not fresh

    item = _normalize_item({"title": "Garbled", "published_at": "??/??", "category": "MKT"})
    assert item["published_at"] == ""
    assert item["age_minutes"] > 60 * 24
