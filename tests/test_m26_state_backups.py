"""M26 S0.1 — pre-write backup rotation for user state files.

Every user-state write (portfolio, paper ledger, algo, layouts, ...) must leave
rotating `<name>.json.bak1..N` siblings so one bad mutation can be undone by
hand. Market caches are regenerable and intentionally keep no backups.
"""

import json

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.storage import STATE_BACKUP_COUNT, LocalStateStore


def _read(path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _bak(path, index: int):
    return path.with_name(f"{path.name}.bak{index}")


def test_first_write_creates_no_backup(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_portfolio_state({"active_portfolio_id": None, "portfolios": {}})
    assert store.portfolio_state_path.is_file()
    assert not _bak(store.portfolio_state_path, 1).exists()


def test_second_write_backs_up_previous_version(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    first = store.write_portfolio_state({"active_portfolio_id": None, "portfolios": {}})
    store.write_portfolio_state(
        {
            "active_portfolio_id": None,
            "portfolios": {},
            "updated_at": "2026-07-07T00:00:00Z",
        }
    )
    backup = _bak(store.portfolio_state_path, 1)
    assert backup.is_file()
    assert _read(backup) == first
    assert _read(store.portfolio_state_path) != first


def test_rotation_keeps_at_most_n_backups_in_order(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    versions = []
    for index in range(STATE_BACKUP_COUNT + 2):
        versions.append(
            store.write_settings({"data_refresh_seconds": 5 + index})
        )
    # bak1 is the newest pre-write copy, bakN the oldest surviving one
    for offset in range(1, STATE_BACKUP_COUNT + 1):
        backup = _bak(store.settings_path, offset)
        assert backup.is_file(), f"missing bak{offset}"
        assert _read(backup) == versions[-1 - offset]
    assert not _bak(store.settings_path, STATE_BACKUP_COUNT + 1).exists()


def test_read_path_returns_newest_not_backup(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_profile({"display_name": "First"})
    store.write_profile({"display_name": "Second"})
    assert store.read_profile()["display_name"] == "Second"
    assert _read(_bak(store.profile_path, 1))["display_name"] == "First"


def test_market_cache_writes_keep_no_backups(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache({"rows": [1]})
    store.write_market_cache({"rows": [2]})
    assert not _bak(store.market_cache_path, 1).exists()


def test_backups_do_not_match_json_globs(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_portfolio_state({"active_portfolio_id": None, "portfolios": {}})
    store.write_portfolio_state({"active_portfolio_id": None, "portfolios": {}, "updated_at": "x"})
    parent = store.portfolio_state_path.parent
    json_names = {path.name for path in parent.glob("*.json")}
    assert json_names == {"portfolio_state.json"}


def test_forum_orphan_scan_ignores_backups(tmp_path) -> None:
    from src.local_terminal.forum import _orphan_post_dirs

    store = LocalStateStore(root=tmp_path)
    store.write_forum_state({})
    store.write_forum_state({"active_channel_id": "crypto-corner"})
    assert _bak(store.forum_state_path, 1).is_file()
    assert _orphan_post_dirs(tmp_path, {}) == []


def test_all_user_state_writers_leave_backups(tmp_path) -> None:
    store = LocalStateStore(root=tmp_path)
    cases = [
        (store.write_settings, {"data_refresh_seconds": 30}, store.settings_path),
        (store.write_profile, {"display_name": "HC"}, store.profile_path),
        (store.write_layout, {"sidebar_collapsed": True}, store.layout_path),
        (store.write_dashboard_layout, {}, store.dashboard_path),
        (store.write_markets_layout, {}, store.markets_path),
        (store.write_news_layout, {}, store.news_path),
        (store.write_chat_state, {}, store.chat_state_path),
        (store.write_algo_state, {}, store.algo_state_path),
        (store.write_nodes_state, {}, store.nodes_state_path),
        (store.write_code_state, {}, store.code_state_path),
        (store.write_quant_lab_state, {}, store.quant_lab_state_path),
        (store.write_quantlib_state, {}, store.quantlib_state_path),
        (store.write_forum_state, {}, store.forum_state_path),
        (store.write_paper_state, {}, store.paper_state_path),
        (
            store.write_portfolio_state,
            {"active_portfolio_id": None, "portfolios": {}},
            store.portfolio_state_path,
        ),
    ]
    for writer, payload, path in cases:
        writer(payload)
        writer(payload)
        assert _bak(path, 1).is_file(), f"no backup for {path.name}"


def test_backup_index_endpoint_is_metadata_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    empty = client.get("/api/local-state/backups")
    assert empty.status_code == 200
    body = empty.json()
    assert body["summary"]["protected_file_count"] == 17  # 15 + watchlist + news digest (M27-R2)
    assert body["summary"]["backup_file_count"] == 0
    assert body["summary"]["keep_backups"] == STATE_BACKUP_COUNT
    assert body["safety"]["restore_endpoint_available"] is False
    assert body["safety"]["mutates_local_state"] is False

    store = server.STORE
    store.write_profile({"display_name": "First"})
    store.write_profile({"display_name": "Second"})

    populated = client.get("/api/local-state/backups").json()
    assert populated["summary"]["backup_file_count"] == 1
    row = next(r for r in populated["rows"] if r["kind"] == "profile")
    assert row["state_exists"] is True
    assert row["backup_count"] == 1
    slot = row["backups"][0]
    assert slot["slot"] == 1
    assert slot["path"].endswith("local_profile.json.bak1")
    assert slot["size_bytes"] > 0
    assert slot["modified_at"]


def test_backup_index_action_registered_in_agent_contract(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())
    contract = client.get("/api/agent-contract").json()
    actions = {action["action_id"]: action for action in contract["actions"]}
    entry = actions["local_state_backup_index"]
    assert entry["method"] == "GET"
    assert entry["endpoint"] == "/api/local-state/backups"
    assert entry["safety_class"] == "metadata_only_state_backup_index"
    assert entry["disabled_by_safety"] is False
    assert entry["requires_confirmation"] is False
