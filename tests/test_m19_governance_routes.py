from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.local_secrets import dpapi_available
from otto.local_terminal.storage import LocalStateStore


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def _market_cache() -> dict[str, object]:
    return {
        "status": {
            "source": "binance_public",
            "state": "live",
            "last_update": "2026-05-23T00:00:00Z",
            "message": "Public ticker cache ready.",
            "provider_id": "binance_spot_public",
            "cache_path": "market_data/crypto_latest.json",
        },
        "rows": [
            {
                "symbol": "BTCUSDT",
                "price": 100000.0,
                "change_24h": 1.2,
                "volume": 1234.0,
                "source": "binance_public",
                "state": "live",
                "retrieved_at": "2026-05-23T00:00:00Z",
                "provider_id": "binance_spot_public",
                "cache_path": "market_data/crypto_latest.json",
            }
        ],
    }


@pytest.mark.skipif(
    not dpapi_available(), reason="Secret-store-enabled governance truths need Windows DPAPI"
)
def test_governance_payload_exposes_settings_contract_without_default_secret_file(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_market_cache())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    response = client.get("/api/governance")

    payload = response.json()
    optional_key_rows = [
        row for row in payload["provider_setup"] if row["auth_mode"] == "optional-local-key"
    ]
    assert response.status_code == 200
    assert payload["summary"]["status"] == "local_governance_ready"
    assert payload["summary"]["provider_count"] >= 8
    assert payload["source_wall"]["state"] == "configured"
    assert payload["source_wall"]["installed_source_read"] is False
    assert payload["local_secret_status"]["design_doc_exists"] is True
    assert payload["local_secret_status"]["api_secret_value_reads_enabled"] is False
    assert payload["local_secret_status"]["planned_store_exists"] is False
    assert optional_key_rows
    assert any(row["form_enabled"] is True for row in optional_key_rows)
    assert any(row["secret_persistence_enabled"] is True for row in optional_key_rows)
    assert all(
        row["form_enabled"] is False
        for row in optional_key_rows
        if row["provider_id"] == "premium_market_data_option"
    )
    assert any(row["cache_id"] == "market_crypto_latest" for row in payload["cache_controls"])
    assert any(row["key"] == "settings" for row in payload["storage_paths"])
    assert payload["safety_gates"]["live_mode_enabled"] is False
    assert any(link["path"] == "market_data/crypto_latest.json" for link in payload["artifact_links"])
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


@pytest.mark.skipif(
    not dpapi_available(), reason="Secret-store-enabled governance truths need Windows DPAPI"
)
def test_help_diagnostics_include_governance_summary(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    help_response = client.get("/api/help")
    diagnostics_response = client.post("/api/help/diagnostics")

    help_payload = help_response.json()
    diagnostics = diagnostics_response.json()
    assert help_response.status_code == 200
    assert help_payload["governance"]["status"] == "local_governance_ready"
    assert help_payload["governance"]["secret_writes_enabled"] is True
    assert diagnostics_response.status_code == 200
    assert diagnostics["checks"]["governance_loaded"] is True
    assert diagnostics["checks"]["secret_value_api_reads_disabled"] is True
    assert diagnostics["checks"]["source_wall_configured"] is True
    assert diagnostics["governance"]["source_wall_state"] == "configured"
    assert (tmp_path / diagnostics["artifacts"]["diagnostics"]).is_file()


@pytest.mark.skipif(
    not dpapi_available(), reason="Secret-store-enabled governance truths need Windows DPAPI"
)
def test_governance_diagnostics_write_read_only_local_bundle(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_market_cache())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    response = client.post("/api/governance/diagnostics")

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "saved_locally"
    assert payload["output_mode"] == "local_governance_cache_diagnostics"
    assert payload["artifact_dir"].startswith("artifacts/diagnostics/gov-")
    assert payload["checks"]["governance_loaded"] is True
    assert payload["checks"]["provider_setup_rows_present"] is True
    assert payload["checks"]["cache_controls_present"] is True
    assert payload["checks"]["source_wall_configured"] is True
    assert payload["checks"]["secret_value_api_reads_disabled"] is True
    assert payload["checks"]["secret_writes_data_provider_scoped"] is True
    assert payload["checks"]["key_forms_data_provider_scoped"] is True
    assert payload["checks"]["installed_source_not_read"] is True
    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["external_network"] is False
    assert payload["safety"]["cache_delete_enabled"] is False
    assert payload["safety"]["secret_value_api_reads_enabled"] is False
    assert payload["safety"]["data_provider_secret_writes_enabled"] is True
    assert payload["safety"]["private_api_key_flow"] is False
    assert payload["safety"]["real_order_path"] is False
    assert payload["source_wall"]["installed_source_read"] is False
    assert payload["local_secret_status"]["planned_store_exists"] is False
    assert "provider_setup" in payload["provider_cache"]
    assert "cache_controls" in payload["provider_cache"]
    assert (tmp_path / payload["artifacts"]["governance"]).is_file()
    assert (tmp_path / payload["artifacts"]["provider_cache"]).is_file()
    assert (tmp_path / payload["artifacts"]["source_wall"]).is_file()
    assert (tmp_path / payload["artifacts"]["manifest"]).is_file()
    assert (tmp_path / payload["artifacts"]["report"]).is_file()
    assert (tmp_path / payload["artifacts"]["error_log"]).is_file()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_governance_payload_exposes_profile_local_usage_without_account_identity(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "artifacts" / "backtests" / "run-1").mkdir(parents=True)
    (tmp_path / "artifacts" / "backtests" / "run-1" / "summary.json").write_text(
        '{"status":"complete"}',
        encoding="utf-8",
    )
    (tmp_path / "artifacts" / "portfolio" / "reports" / "report-1").mkdir(parents=True)
    (tmp_path / "artifacts" / "portfolio" / "reports" / "report-1" / "report.md").write_text(
        "# Local report",
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    client = TestClient(server.create_app())

    response = client.get("/api/governance")

    payload = response.json()
    usage = payload["profile_usage"]
    rows = {row["usage_id"]: row for row in usage["usage_rows"]}
    assert response.status_code == 200
    assert usage["mode"] == "local_usage_stats"
    assert usage["build_channel"] == "local_git_worktree"
    assert usage["cloud_account_required"] is False
    assert usage["billing_identity"] is False
    assert usage["subscription_required"] is False
    assert usage["credits_enabled"] is False
    assert usage["private_api_identity"] is False
    assert usage["total_files"] >= 2
    assert usage["total_bytes"] > 0
    assert rows["backtests"]["file_count"] == 1
    assert rows["portfolio_reports"]["file_count"] == 1
    assert usage["safety"]["content_read"] is False
    assert usage["safety"]["external_network"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_forum_can_link_governance_artifact_suggestions_and_code_artifacts(
    tmp_path: Path, monkeypatch
) -> None:
    store = LocalStateStore(root=tmp_path)
    store.write_market_cache(_market_cache())
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    forum = client.get("/api/forum").json()
    response = client.post(
        "/api/forum/post",
        json={
            "title": "Provider cache issue note",
            "content": "Review provider cache provenance before the next route QA pass.",
            "channel_id": "market-analysis",
            "tags": "m19, governance",
            "linked_artifacts": (
                "market_data/crypto_latest.json,"
                "artifacts/code_workspace/provider_context.ipynb"
            ),
        },
    )

    post = response.json()["post_result"]
    assert any(item["path"] == "market_data/crypto_latest.json" for item in forum["artifact_suggestions"])
    assert response.status_code == 200
    assert post["linked_artifacts"] == [
        "market_data/crypto_latest.json",
        "artifacts/code_workspace/provider_context.ipynb",
    ]
