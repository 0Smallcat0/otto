import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.storage import LocalStateStore


def test_ai_chat_session_lifecycle_writes_local_state_and_requires_delete_confirmation(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    initial = client.get("/api/ai-chat")
    created = client.post("/api/ai-chat/sessions", json={"name": "Research Notes"})
    session_id = created.json()["active_session_id"]
    created_dir_exists = (tmp_path / "artifacts" / "chat" / session_id).is_dir()
    renamed = client.post(
        "/api/ai-chat/rename",
        json={"session_id": session_id, "name": "Macro Watch"},
    )
    rejected_delete = client.post(
        "/api/ai-chat/delete",
        json={"session_id": session_id, "confirm": False},
    )
    deleted = client.post(
        "/api/ai-chat/delete",
        json={"session_id": session_id, "confirm": True},
    )
    local_state = client.get("/api/local-state")

    assert initial.status_code == 200
    assert initial.json()["first_use"] is True
    assert initial.json()["provider"]["cloud_account_required"] is False
    assert initial.json()["safety"]["cr_required"] is False
    assert created.status_code == 200
    assert created.json()["active_session"]["name"] == "Research Notes"
    assert (tmp_path / "artifacts" / "chat" / "chat_state.json").is_file()
    assert created_dir_exists is True
    assert renamed.status_code == 200
    assert renamed.json()["active_session"]["name"] == "Macro Watch"
    assert rejected_delete.status_code == 400
    assert rejected_delete.json()["detail"] == "Delete confirmation is required"
    assert deleted.status_code == 200
    assert deleted.json()["first_use"] is True
    assert not (tmp_path / "artifacts" / "chat" / session_id).exists()
    assert local_state.json()["storage"]["chat_state"] == "artifacts/chat/chat_state.json"


def test_ai_chat_message_appends_jsonl_and_links_local_artifact(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    artifact = tmp_path / "artifacts" / "backtests" / "run-1" / "summary.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"return_pct": "1.25"}), encoding="utf-8")
    client = TestClient(server.create_app())
    session_id = client.post("/api/ai-chat/sessions", json={"name": "Backtest Review"}).json()[
        "active_session_id"
    ]

    response = client.post(
        "/api/ai-chat/messages",
        json={
            "session_id": session_id,
            "content": "Summarize the local backtest artifact",
            "linked_artifacts": ["artifacts/backtests/run-1/summary.json"],
        },
    )

    payload = response.json()
    messages_path = tmp_path / "artifacts" / "chat" / session_id / "messages.jsonl"
    stored_messages = [
        json.loads(line) for line in messages_path.read_text(encoding="utf-8").splitlines()
    ]

    assert response.status_code == 200
    assert payload["active_session"]["message_count"] == 2
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][0]["linked_artifacts"][0]["read_mode"] == "read_only"
    assert payload["messages"][0]["linked_artifacts"][0]["path"] == (
        "artifacts/backtests/run-1/summary.json"
    )
    assert len(payload["messages"][0]["linked_artifacts"][0]["sha256"]) == 64
    assert payload["messages"][1]["role"] == "assistant"
    assert "Local context brief" in payload["messages"][1]["content"]
    assert (
        "Linked local artifacts: artifacts/backtests/run-1/summary.json"
        in payload["messages"][1]["content"]
    )
    assert "cannot place orders" in payload["messages"][1]["content"]
    assert payload["safety"]["broker_mutation"] is False
    assert payload["safety"]["linked_artifacts_read_only"] is True
    assert len(stored_messages) == 2
    assert "api_key" not in messages_path.read_text(encoding="utf-8").lower()


def test_ai_chat_context_contract_exposes_metadata_only_state(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(
        {
            "status": {
                "source": "binance_public",
                "state": "live",
                "last_update": "2026-05-26T00:00:00Z",
                "provider_id": "binance_spot_public",
            },
            "rows": [
                {
                    "symbol": "BTCUSDT",
                    "price": "65000.00",
                    "provider_id": "binance_spot_public",
                }
            ],
        }
    )
    monkeypatch.setattr(server, "STORE", store)
    artifact = tmp_path / "artifacts" / "backtests" / "run-1" / "summary.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"return_pct": "1.25"}), encoding="utf-8")
    client = TestClient(server.create_app())
    session_id = client.post("/api/ai-chat/sessions", json={"name": "Context Contract"}).json()[
        "active_session_id"
    ]

    message = client.post(
        "/api/ai-chat/messages",
        json={
            "session_id": session_id,
            "content": "Summarize the local context contract",
            "linked_artifacts": ["artifacts/backtests/run-1/summary.json"],
        },
    )
    response = client.get("/api/ai-chat/context-contract")

    payload = response.json()
    text = response.text.lower()
    assert message.status_code == 200
    assert response.status_code == 200
    assert payload["mode"] == "metadata_only_ai_chat_context_contract"
    assert payload["limits"]["max_prompt_chars"] == 4000
    assert payload["limits"]["max_linked_artifacts"] == 8
    assert payload["output_state"]["active_session_id"] == session_id
    assert payload["output_state"]["message_count"] == 2
    assert payload["output_state"]["assistant_message_count"] == 1
    assert payload["output_state"]["latest_message_role"] == "assistant"
    assert payload["output_state"]["messages_artifact_path"] == (
        f"artifacts/chat/{session_id}/messages.jsonl"
    )
    assert payload["output_state"]["assistant_output_mode"] == (
        "local_dry_run_context_brief"
    )
    assert payload["source_citations"][0]["citation_id"] == "ctx-source-1"
    assert payload["source_citations"][0]["source_id"] == "market_ticker_cache"
    assert payload["source_citations"][0]["cache_path"] == "market_data/crypto_latest.json"
    assert payload["context_summary"]["ready_source_count"] >= 1
    assert payload["artifact_provenance"]["linked_artifacts"] == [
        "artifacts/backtests/run-1/summary.json"
    ]
    assert payload["artifact_provenance"]["context_artifact_count"] >= 1
    assert any(
        row["path"] == "artifacts/backtests/run-1/summary.json"
        and row["read_mode"] == "metadata_only"
        for row in payload["artifact_provenance"]["context_artifacts"]
    )
    assert payload["safety"]["artifact_content_read"] is False
    assert payload["safety"]["artifact_content_indexing"] is False
    assert payload["safety"]["managed_llm"] is False
    assert payload["safety"]["provider_calls"] is False
    assert payload["safety"]["broker_mutation"] is False
    assert payload["safety"]["real_orders"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
    assert "api_key" not in text


def test_ai_chat_session_health_exposes_transcript_metadata_only(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    initial = client.get("/api/ai-chat/session-health")
    created = client.post("/api/ai-chat/sessions", json={"name": "Health Check"})
    session_id = created.json()["active_session_id"]
    empty_health = client.get("/api/ai-chat/session-health")

    message = client.post(
        "/api/ai-chat/messages",
        json={
            "session_id": session_id,
            "content": "Summarize the local transcript health",
            "linked_artifacts": [],
        },
    )
    complete_health = client.get("/api/ai-chat/session-health")
    embedded_health = client.get("/api/ai-chat").json()["session_health"]
    messages_path = tmp_path / "artifacts" / "chat" / session_id / "messages.jsonl"
    messages_path.unlink()
    partial_health = client.get("/api/ai-chat/session-health")

    initial_payload = initial.json()
    empty_payload = empty_health.json()
    complete_payload = complete_health.json()
    partial_payload = partial_health.json()
    complete_text = complete_health.text.lower()

    assert initial.status_code == 200
    assert initial_payload["mode"] == "metadata_only_ai_chat_session_health"
    assert initial_payload["summary"]["session_count"] == 0
    assert initial_payload["summary"]["recovery_queue_count"] == 1
    assert initial_payload["recovery_queue"][0]["recommended_action"] == (
        "ai_chat_create_session"
    )
    assert initial_payload["safety"]["message_content_read"] is False
    assert initial_payload["safety"]["request_response_replay"] is False
    assert initial_payload["safety"]["managed_llm"] is False
    assert initial_payload["safety"]["writes_local_artifacts"] is False

    assert created.status_code == 200
    assert empty_payload["summary"]["session_count"] == 1
    assert empty_payload["summary"]["empty_count"] == 1
    assert empty_payload["summary"]["missing_message_artifact_count"] == 0
    assert empty_payload["sessions"][0]["health_state"] == "empty_session"
    assert empty_payload["sessions"][0]["messages_artifact_exists"] is False
    assert empty_payload["sessions"][0]["supervision_ready"] is True

    assert message.status_code == 200
    assert complete_payload["summary"]["complete_count"] == 1
    assert complete_payload["summary"]["supervision_ready_count"] == 1
    assert complete_payload["sessions"][0]["health_state"] == "complete"
    assert complete_payload["sessions"][0]["messages_artifact_exists"] is True
    assert complete_payload["sessions"][0]["messages_bytes"] > 0
    assert complete_payload["sessions"][0]["declared_message_count"] == 2
    assert embedded_health["summary"] == complete_payload["summary"]
    assert "summarize the local transcript health" not in complete_text
    assert "local context brief" not in complete_text

    assert partial_payload["summary"]["partial_count"] == 1
    assert partial_payload["summary"]["missing_message_artifact_count"] == 1
    assert partial_payload["summary"]["recovery_queue_count"] == 1
    assert partial_payload["sessions"][0]["health_state"] == "partial_missing_messages"
    assert partial_payload["sessions"][0]["supervision_ready"] is False
    assert partial_payload["recovery_queue"][0]["destructive_action_required"] is False
    assert partial_payload["safety"]["destructive_actions_enabled"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_ai_chat_rejects_secrets_and_unsafe_artifact_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    session_id = client.post("/api/ai-chat/sessions", json={"name": "Safe Session"}).json()[
        "active_session_id"
    ]
    profile_path = tmp_path / "settings" / "local_profile.json"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text("{}", encoding="utf-8")

    secret_responses = [
        client.post(
            "/api/ai-chat/messages",
            json={"session_id": session_id, "content": secret},
        )
        for secret in (
            "api_key=abc123",
            "api key: abc123",
            "API Key = abc123",
            '"api_key": "abc123"',
            "secret key: abc123",
            "token: abc123",
            "private_key=abc123",
            "Authorization: Bearer abcdefghijk",
        )
    ]
    unsafe_artifact = client.post(
        "/api/ai-chat/messages",
        json={
            "session_id": session_id,
            "content": "Please inspect this profile",
            "linked_artifacts": ["settings/local_profile.json"],
        },
    )

    assert all(response.status_code == 400 for response in secret_responses)
    assert all(
        response.json()["detail"] == "Message appears to contain credential material"
        for response in secret_responses
    )
    assert unsafe_artifact.status_code == 400
    assert unsafe_artifact.json()["detail"] == (
        "Linked artifact must be under allowed local artifact paths"
    )
    assert not (tmp_path / "artifacts" / "chat" / session_id / "messages.jsonl").exists()


def test_ai_chat_rejects_corrupt_existing_state_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    state_path = tmp_path / "artifacts" / "chat" / "chat_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not-json", encoding="utf-8")
    client = TestClient(server.create_app())

    readonly = client.get("/api/ai-chat")
    response = client.post("/api/ai-chat/sessions", json={"name": "New Session"})

    assert readonly.status_code == 200
    assert readonly.json()["first_use"] is True
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Chat state is invalid: chat_state.json: Invalid chat state JSON"
    )
    assert state_path.read_text(encoding="utf-8") == "{not-json"


def test_ai_chat_rejects_tampered_session_linked_artifact_paths(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    created = client.post("/api/ai-chat/sessions", json={"name": "Unsafe Session Link"})
    session_id = created.json()["active_session_id"]
    state_path = tmp_path / "artifacts" / "chat" / "chat_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["sessions"][session_id]["linked_artifacts"] = ["settings/local_profile.json"]
    state_path.write_text(json.dumps(state), encoding="utf-8")

    readonly = client.get("/api/ai-chat")
    mutation = client.post(
        "/api/ai-chat/rename",
        json={"session_id": session_id, "name": "Should Fail"},
    )

    assert readonly.status_code == 200
    assert readonly.json()["first_use"] is True
    assert readonly.json()["invalid_sessions"][session_id] == (
        "Linked artifact must be under allowed local artifact paths"
    )
    assert mutation.status_code == 400
    assert mutation.json()["detail"] == (
        f"Stored chat session {session_id} is invalid: "
        "Linked artifact must be under allowed local artifact paths"
    )


def test_ai_chat_selects_session_and_loads_its_transcript(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    first_id = client.post("/api/ai-chat/sessions", json={"name": "First"}).json()[
        "active_session_id"
    ]
    client.post(
        "/api/ai-chat/messages",
        json={"session_id": first_id, "content": "First session prompt"},
    )
    second_id = client.post("/api/ai-chat/sessions", json={"name": "Second"}).json()[
        "active_session_id"
    ]
    client.post(
        "/api/ai-chat/messages",
        json={"session_id": second_id, "content": "Second session prompt"},
    )

    selected = client.post("/api/ai-chat/select", json={"session_id": first_id})

    assert selected.status_code == 200
    assert selected.json()["active_session_id"] == first_id
    assert selected.json()["messages"][0]["content"] == "First session prompt"
    assert "Second session prompt" not in selected.text


def test_ai_chat_rejects_tampered_stored_messages_on_read_and_write(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    artifact = tmp_path / "artifacts" / "backtests" / "run-1" / "summary.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"return_pct": "1.25"}), encoding="utf-8")
    client = TestClient(server.create_app())
    session_id = client.post("/api/ai-chat/sessions", json={"name": "Tamper Test"}).json()[
        "active_session_id"
    ]
    messages_path = tmp_path / "artifacts" / "chat" / session_id / "messages.jsonl"
    messages_path.write_text(
        json.dumps(
            {
                "message_id": "msg-tampered",
                "session_id": session_id,
                "role": "assistant",
                "content": "Tampered broker message",
                "effect": "broker_mutation",
                "broker_mutation": True,
                "linked_artifacts": [
                    {
                        "path": "settings/local_profile.json",
                        "bytes": 0,
                        "sha256": "",
                    }
                ],
                "created_at": "2026-05-22T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    readonly = client.get("/api/ai-chat")
    append = client.post(
        "/api/ai-chat/messages",
        json={"session_id": session_id, "content": "Append after tamper"},
    )

    assert readonly.status_code == 200
    assert readonly.json()["messages"] == []
    assert readonly.json()["message_errors"]["messages.jsonl:1"] == (
        "Chat message effect is not allowed"
    )
    assert append.status_code == 400
    assert append.json()["detail"] == (
        "Stored chat message line 1 is invalid: Chat message effect is not allowed"
    )


def test_ai_chat_rejects_stored_message_with_unsafe_artifact_path(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    session_id = client.post("/api/ai-chat/sessions", json={"name": "Unsafe Artifact"}).json()[
        "active_session_id"
    ]
    messages_path = tmp_path / "artifacts" / "chat" / session_id / "messages.jsonl"
    messages_path.write_text(
        json.dumps(
            {
                "message_id": "msg-unsafe-artifact",
                "session_id": session_id,
                "role": "user",
                "content": "Read profile",
                "effect": "read_only",
                "broker_mutation": False,
                "linked_artifacts": [{"path": "settings/local_profile.json"}],
                "created_at": "2026-05-22T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    readonly = client.get("/api/ai-chat")

    assert readonly.status_code == 200
    assert readonly.json()["messages"] == []
    assert readonly.json()["message_errors"]["messages.jsonl:1"] == (
        "Linked artifact must be under allowed local artifact paths"
    )
