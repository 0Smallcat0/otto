"""M26 Phase 2 — confirm-gated restore endpoint closes the backup loop.

S0.1/S0.2 gave every user-state file rotating backups plus a metadata-only
index; undoing a bad write still meant stopping the server and copying files
by hand. `POST /api/local-state/restore` finishes the loop under the same
iron rules as the 2026-07-07 incident lessons: only the protected list is
restorable, an unreadable backup aborts with zero writes, confirm is
mandatory, and the pre-restore version rotates into slot 1 so a restore is
itself undoable.
"""

import json

import pytest
from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.storage import (
    STATE_BACKUP_COUNT,
    LocalStateStore,
    StateRestoreError,
)


def _read(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _bak(path, index: int):
    return path.with_name(f"{path.name}.bak{index}")


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_restore_brings_back_previous_version_and_stays_undoable(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_profile({"display_name": "First"})
    store.write_profile({"display_name": "Second"})

    result = store.restore_state_backup("profile", 1)

    assert store.read_profile()["display_name"] == "First"
    assert result["kind"] == "profile"
    assert result["restored_from"]["slot"] == 1
    assert result["restored_from"]["path"].endswith("local_profile.json.bak1")
    # the pre-restore version ("Second") rotated into slot 1: restore is undoable
    assert result["undo"]["available"] is True
    assert _read(_bak(store.profile_path, 1))["display_name"] == "Second"

    undo = store.restore_state_backup("profile", 1)
    assert store.read_profile()["display_name"] == "Second"
    assert undo["undo"]["available"] is True


def test_restore_unknown_kind_is_refused(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    with pytest.raises(StateRestoreError, match="Unknown protected state kind"):
        store.restore_state_backup("market_cache", 1)


def test_restore_empty_slot_is_refused(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_profile({"display_name": "Only"})
    with pytest.raises(StateRestoreError, match="No backup in slot 1"):
        store.restore_state_backup("profile", 1)
    with pytest.raises(StateRestoreError, match=f"1..{STATE_BACKUP_COUNT}"):
        store.restore_state_backup("profile", STATE_BACKUP_COUNT + 1)


def test_unreadable_backup_aborts_with_zero_writes(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_profile({"display_name": "First"})
    store.write_profile({"display_name": "Second"})
    _bak(store.profile_path, 1).write_text("{not json", encoding="utf-8")

    with pytest.raises(StateRestoreError, match="zero writes"):
        store.restore_state_backup("profile", 1)
    assert store.read_profile()["display_name"] == "Second"

    _bak(store.profile_path, 1).write_text('["not", "an", "object"]', encoding="utf-8")
    with pytest.raises(StateRestoreError, match="not a JSON object"):
        store.restore_state_backup("profile", 1)
    assert store.read_profile()["display_name"] == "Second"


def test_restore_endpoint_requires_confirm(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    store = server.STORE
    store.write_profile({"display_name": "First"})
    store.write_profile({"display_name": "Second"})

    refused = client.post("/api/local-state/restore", json={"kind": "profile", "slot": 1})
    assert refused.status_code == 400
    assert "confirmation" in refused.json()["detail"].lower()
    assert store.read_profile()["display_name"] == "Second"

    accepted = client.post(
        "/api/local-state/restore",
        json={"kind": "profile", "slot": 1, "confirm": True},
    )
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["kind"] == "profile"
    assert body["undo"]["available"] is True
    assert body["safety"]["confirm_required"] is True
    assert store.read_profile()["display_name"] == "First"


def test_restore_endpoint_maps_refusals_to_400(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    unknown = client.post(
        "/api/local-state/restore",
        json={"kind": "not_a_kind", "confirm": True},
    )
    assert unknown.status_code == 400
    assert "Unknown protected state kind" in unknown.json()["detail"]

    out_of_range = client.post(
        "/api/local-state/restore",
        json={"kind": "profile", "slot": STATE_BACKUP_COUNT + 1, "confirm": True},
    )
    assert out_of_range.status_code == 422  # pydantic slot bound

    extra_field = client.post(
        "/api/local-state/restore",
        json={"kind": "profile", "confirm": True, "force": True},
    )
    assert extra_field.status_code == 422  # extra="forbid"


def test_backup_index_advertises_the_restore_endpoint(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    safety = client.get("/api/local-state/backups").json()["safety"]
    assert safety["restore_endpoint_available"] is True
    assert safety["restore_endpoint"] == "/api/local-state/restore"


def test_restore_action_registered_in_agent_contract(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    contract = client.get("/api/agent-contract").json()
    actions = {action["action_id"]: action for action in contract["actions"]}
    entry = actions["local_state_restore"]
    assert entry["method"] == "POST"
    assert entry["endpoint"] == "/api/local-state/restore"
    assert entry["safety_class"] == "confirm_gated_state_backup_restore"
    assert entry["requires_confirmation"] is True
    assert entry["disabled_by_safety"] is False
    assert entry["local_mutation"] is True

    settings_route = next(r for r in contract["routes"] if r["route_id"] == "settings")
    assert "local_state_restore" in settings_route["recommended_actions"]
