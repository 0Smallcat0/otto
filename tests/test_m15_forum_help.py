import json
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import LocalStateStore


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_forum_initial_payload_reports_channels_storage_and_safety(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/forum")
    local_state = client.get("/api/local-state")

    payload = response.json()
    assert response.status_code == 200
    assert [channel["label"] for channel in payload["channels"]] == [
        "Crypto Corner",
        "General Discussion",
        "Market Analysis",
        "Trading Strategies",
    ]
    assert payload["first_use"] is True
    assert payload["safety"] == {
        "local_posts_only": True,
        "cloud_publish": False,
        "external_network": False,
        "cloud_account_required": False,
        "subscription_required": False,
        "private_api_required": False,
        "credentials_persisted": False,
        "broker_mutation": False,
        "real_orders": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives_execution": False,
        "output": "local_research_journal",
    }
    assert local_state.json()["storage"]["forum_state"] == "artifacts/forum/forum_state.json"
    assert local_state.json()["storage"]["diagnostics_artifacts"] == "artifacts/diagnostics"


def test_forum_saves_local_post_reply_and_thread_artifacts(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    post_response = client.post(
        "/api/forum/post",
        json={
            "title": "M15 Strategy Journal",
            "content": "Paper SMA result needs another walk-forward check.",
            "channel_id": "trading-strategies",
            "tags": "paper, sma, btc",
            "linked_artifacts": [],
        },
    )
    post_payload = post_response.json()
    post = post_payload["post_result"]
    reply_response = client.post(
        "/api/forum/reply",
        json={
            "post_id": post["post_id"],
            "content": "Add a risk note before promoting this to live-gated work.",
        },
    )
    selected_response = client.post("/api/forum/select-post", json={"post_id": post["post_id"]})

    artifact_dir = tmp_path / post["artifact_dir"]
    assert post_response.status_code == 200
    assert post_payload["active_channel_id"] == "trading-strategies"
    assert post["status"] == "local_saved"
    assert post["cloud_published"] is False
    assert post["artifacts"]["post"].endswith("/post.json")
    assert (artifact_dir / "post.json").is_file()
    assert (artifact_dir / "replies.json").is_file()
    assert "Cloud published: false" in (artifact_dir / "thread.md").read_text(encoding="utf-8")
    assert reply_response.status_code == 200
    assert reply_response.json()["selected_post"]["reply_count"] == 1
    assert len(reply_response.json()["replies"]) == 1
    assert selected_response.status_code == 200
    assert selected_response.json()["selected_post"]["views"] == 1
    assert (tmp_path / "artifacts" / "forum" / "forum_state.json").is_file()


def test_forum_reports_and_repairs_missing_derivative_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    post_response = client.post(
        "/api/forum/post",
        json={
            "title": "Artifact repair note",
            "content": "Keep thread files aligned with forum_state before handoff.",
            "channel_id": "market-analysis",
            "tags": "artifacts, repair",
            "linked_artifacts": [],
        },
    )
    post = post_response.json()["post_result"]
    artifact_dir = tmp_path / post["artifact_dir"]
    thread = artifact_dir / "thread.md"
    thread.unlink()
    orphan_dir = tmp_path / "artifacts" / "forum" / "post-000000000abc"
    orphan_dir.mkdir()
    (orphan_dir / "thread.md").write_text("orphan", encoding="utf-8")

    forum_before = client.get("/api/forum").json()
    repair_response = client.post("/api/forum/repair-artifacts")
    repair_payload = repair_response.json()
    forum_after = client.get("/api/forum").json()

    assert forum_before["artifact_health"]["status"] == "repair_available"
    assert forum_before["artifact_health"]["summary"]["missing_artifact_count"] == 1
    assert forum_before["artifact_health"]["summary"]["orphan_dir_count"] == 1
    assert forum_before["artifact_health"]["missing"][0]["path"] == post["artifacts"]["thread"]
    assert repair_response.status_code == 200
    assert repair_payload["repair_result"]["status"] == "repaired"
    assert repair_payload["repair_result"]["missing_before"] == 1
    assert repair_payload["repair_result"]["missing_after"] == 0
    assert repair_payload["repair_result"]["destructive_actions_enabled"] is False
    assert thread.is_file()
    assert "Artifact repair note" in thread.read_text(encoding="utf-8")
    assert forum_after["artifact_health"]["status"] == "orphan_review"
    assert forum_after["artifact_health"]["summary"]["missing_artifact_count"] == 0
    assert forum_after["artifact_health"]["summary"]["orphan_dir_count"] == 1
    assert (orphan_dir / "thread.md").is_file()


def test_forum_artifact_repair_blocks_invalid_state_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    state_path = tmp_path / "artifacts" / "forum" / "forum_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not-json", encoding="utf-8")

    response = client.post("/api/forum/repair-artifacts")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Forum state is invalid: forum_state.json: Invalid forum state JSON"
    )
    assert state_path.read_text(encoding="utf-8") == "{not-json"


def test_forum_rejects_credentials_without_writing_artifacts(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.post(
        "/api/forum/post",
        json={
            "title": "Secret note",
            "content": "api_key: abc123",
            "channel_id": "crypto-corner",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Content appears to contain credential material"
    assert not (tmp_path / "artifacts" / "forum").exists()


def test_forum_corrupt_existing_state_blocks_mutation_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    state_path = tmp_path / "artifacts" / "forum" / "forum_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not-json", encoding="utf-8")

    readonly = client.get("/api/forum")
    response = client.post(
        "/api/forum/post",
        json={
            "title": "Blocked write",
            "content": "This should not overwrite corrupt state.",
            "channel_id": "crypto-corner",
        },
    )

    assert readonly.status_code == 200
    assert readonly.json()["invalid_posts"]["forum_state.json"] == "Invalid forum state JSON"
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Forum state is invalid: forum_state.json: Invalid forum state JSON"
    )
    assert state_path.read_text(encoding="utf-8") == "{not-json"


def test_forum_oversized_existing_state_is_readable_but_blocks_mutation(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    state_path = tmp_path / "artifacts" / "forum" / "forum_state.json"
    state_path.parent.mkdir(parents=True)
    posts = {
        f"post-{index:012x}": {
            "post_id": f"post-{index:012x}",
            "title": f"Local note {index}",
            "content": "Valid local content",
            "channel_id": "crypto-corner",
            "tags": [],
            "linked_artifacts": [],
            "author": "Local User",
            "status": "local_saved",
            "cloud_published": False,
            "views": 0,
            "reply_count": 0,
            "created_at": "2026-05-22T00:00:00Z",
            "updated_at": "2026-05-22T00:00:00Z",
        }
        for index in range(201)
    }
    state_path.write_text(json.dumps({"posts": posts, "replies": {}}), encoding="utf-8")

    readonly = client.get("/api/forum")
    response = client.post(
        "/api/forum/post",
        json={
            "title": "Blocked write",
            "content": "This should not overwrite oversized state.",
            "channel_id": "crypto-corner",
        },
    )

    assert readonly.status_code == 200
    assert readonly.json()["invalid_posts"]["posts"] == "Forum posts exceed limit of 200"
    assert readonly.json()["posts"] == []
    assert response.status_code == 400
    assert response.json()["detail"] == "Forum posts exceed limit of 200"
    assert json.loads(state_path.read_text(encoding="utf-8"))["posts"] == posts


def test_forum_oversized_replies_are_readable_but_invalid(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    state_path = tmp_path / "artifacts" / "forum" / "forum_state.json"
    state_path.parent.mkdir(parents=True)
    post_id = "post-000000000001"
    replies = {
        f"reply-{index:012x}": {
            "reply_id": f"reply-{index:012x}",
            "post_id": post_id,
            "content": "Valid local reply",
            "author": "Local User",
            "status": "local_saved",
            "created_at": "2026-05-22T00:00:00Z",
        }
        for index in range(801)
    }
    state_path.write_text(
        json.dumps(
            {
                "posts": {
                    post_id: {
                        "post_id": post_id,
                        "title": "Local note",
                        "content": "Valid local content",
                        "channel_id": "crypto-corner",
                        "tags": [],
                        "linked_artifacts": [],
                        "author": "Local User",
                        "status": "local_saved",
                        "cloud_published": False,
                        "views": 0,
                        "reply_count": 0,
                        "created_at": "2026-05-22T00:00:00Z",
                        "updated_at": "2026-05-22T00:00:00Z",
                    }
                },
                "replies": replies,
            }
        ),
        encoding="utf-8",
    )

    readonly = client.get("/api/forum")

    assert readonly.status_code == 200
    assert readonly.json()["invalid_replies"]["replies"] == "Forum replies exceed limit of 800"
    assert readonly.json()["replies"] == []


def test_help_payload_and_diagnostics_are_local_only(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    help_response = client.get("/api/help")
    diagnostics_response = client.post("/api/help/diagnostics")
    update_response = client.post("/api/help/check-updates")

    help_payload = help_response.json()
    diagnostics = diagnostics_response.json()
    update_status = update_response.json()
    serialized_help = json.dumps(help_payload)
    assert help_response.status_code == 200
    assert "Fincept" not in serialized_help
    assert {section["section_id"] for section in help_payload["sections"]}.issuperset(
        {"help_center", "diagnostics", "about", "privacy", "terms", "attributions", "updates"}
    )
    assert help_payload["safety"]["external_network"] is False
    assert help_payload["safety"]["margin"] is False
    assert help_payload["safety"]["leverage"] is False
    assert help_payload["safety"]["short"] is False
    assert help_payload["safety"]["derivatives_execution"] is False
    assert help_payload["diagnostics"]["checks"]["routes_complete"] is True
    assert help_payload["diagnostics"]["checks"]["menus_complete"] is True
    assert help_payload["diagnostics"]["checks"]["storage_repo_local"] is True
    assert help_payload["diagnostics"]["checks"]["forbidden_safety_disabled"] is True
    assert help_payload["diagnostics"]["checks"]["remote_profile_requirements_disabled"] is True
    assert help_payload["diagnostics"]["checks"]["forum_artifacts_repairable"] is True
    assert help_payload["diagnostics"]["checks"]["forum_prune_destructive_disabled"] is True
    assert help_payload["diagnostics"]["forum_artifact_health"]["status"] == "healthy"
    assert diagnostics_response.status_code == 200
    assert diagnostics["artifact_dir"].startswith("artifacts/diagnostics/diag-")
    assert diagnostics["artifacts"]["diagnostics"].endswith("/diagnostics.json")
    assert diagnostics["forum_artifact_health"]["status"] == "healthy"
    assert (tmp_path / diagnostics["artifacts"]["diagnostics"]).is_file()
    assert (tmp_path / diagnostics["artifacts"]["report"]).is_file()
    assert update_response.status_code == 200
    assert update_status["network_check"] is False
    assert update_status["external_update_server"] is False
    assert update_status["status"] == "local_manifest_only"
