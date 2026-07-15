import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from otto.local_terminal import server
from otto.local_terminal.provider_refresh import (
    provider_refresh_lifecycle_payload,
    provider_refresh_schedule_plan_payload,
)
from otto.local_terminal.storage import LocalStateStore


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_provider_refresh_lifecycle_classifies_stale_failed_manifest_and_corrupt_runs(
    tmp_path: Path,
) -> None:
    diagnostics = tmp_path / "artifacts" / "diagnostics"
    _write_json(
        diagnostics / "provider-refresh-000000000001" / "job_status.json",
        {
            "run_id": "provider-refresh-000000000001",
            "status": "running",
            "created_at": "2026-05-24T10:00:00Z",
            "started_at": "2026-05-24T10:00:00Z",
            "completed_at": "",
            "summary": {"result_count": 0, "provider_count": 0},
            "artifacts": {
                "job_status": (
                    "artifacts/diagnostics/provider-refresh-000000000001/job_status.json"
                )
            },
        },
    )
    _write_json(
        diagnostics / "provider-refresh-000000000002" / "job_status.json",
        {
            "run_id": "provider-refresh-000000000002",
            "status": "failed",
            "created_at": "2026-05-24T11:00:00Z",
            "started_at": "2026-05-24T11:00:00Z",
            "completed_at": "2026-05-24T11:01:00Z",
            "summary": {"unavailable": 1, "source_error_count": 1},
            "artifacts": {
                "report": "C:/unsafe/outside/report.md",
                "error_log": "artifacts/diagnostics/provider-refresh-000000000002/error.log?credential=redacted",
            },
        },
    )
    _write_json(
        diagnostics / "provider-refresh-000000000003" / "manifest.json",
        {
            "run_id": "provider-refresh-000000000003",
            "started_at": "2026-05-24T11:10:00Z",
            "completed_at": "2026-05-24T11:11:00Z",
            "summary": {"result_count": 2, "provider_count": 2, "refreshed": 2},
            "artifacts": {
                "manifest": "artifacts/diagnostics/provider-refresh-000000000003/manifest.json",
                "secret_note": "../outside/value.txt",
            },
        },
    )
    corrupt_dir = diagnostics / "provider-refresh-000000000004"
    corrupt_dir.mkdir(parents=True)
    (corrupt_dir / "job_status.json").write_text("{not-json", encoding="utf-8")

    payload = provider_refresh_lifecycle_payload(
        LocalStateStore(root=tmp_path),
        now=datetime(2026, 5, 24, 12, 30, tzinfo=UTC),
    )
    rows = {row["run_id"]: row for row in payload["runs"]}

    assert payload["mode"] == "read_only_provider_refresh_lifecycle"
    assert payload["summary"]["run_count"] == 4
    assert payload["summary"]["stale_interrupted_count"] == 1
    assert payload["summary"]["failed_count"] == 1
    assert payload["summary"]["manifest_only_count"] == 1
    assert payload["summary"]["corrupt_status_count"] == 1
    assert payload["summary"]["recovery_recommended_count"] == 4
    assert rows["provider-refresh-000000000001"]["lifecycle_state"] == (
        "stale_interrupted_running"
    )
    assert rows["provider-refresh-000000000001"]["recovery"]["recommended_action"] == (
        "start_new_manual_refresh_job"
    )
    assert rows["provider-refresh-000000000002"]["lifecycle_state"] == (
        "failed_retry_available"
    )
    assert rows["provider-refresh-000000000002"]["recovery"]["read_endpoint"] == (
        "/api/providers/refresh-public/lifecycle"
    )
    assert "safe_endpoint" not in rows["provider-refresh-000000000002"]["recovery"]
    assert rows["provider-refresh-000000000003"]["lifecycle_state"] == (
        "manifest_only_completed"
    )
    assert rows["provider-refresh-000000000004"]["lifecycle_state"] == (
        "corrupt_status_metadata"
    )
    assert payload["actions"]["recover_status_write_enabled"] is False
    assert payload["actions"]["delete_enabled"] is False
    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["job_status_mutation"] is False
    assert payload["safety"]["destructive_actions_enabled"] is False
    assert payload["safety"]["secret_values_returned"] is False
    encoded = json.dumps(payload)
    assert "C:/unsafe" not in encoded
    assert "credential=" not in encoded
    assert "../outside" not in encoded
    for row in payload["runs"]:
        for artifact_path in row["artifacts"].values():
            assert artifact_path.startswith(f"artifacts/diagnostics/{row['run_id']}/")
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_provider_refresh_schedule_plan_is_read_only_public_no_key_only(
    tmp_path: Path,
) -> None:
    provider_payload = {
        "providers": [
            {
                "provider_id": "public_rss_news",
                "label": "Public RSS news feeds",
                "auth_mode": "no-key",
                "safety_class": "public_read_only_news",
                "health": {
                    "state": "active",
                    "cache_id": "news_public_rss",
                    "cache_path": "artifacts/news/news_cache.json",
                    "retrieved_at": "2026-05-27T08:00:00Z",
                    "age_seconds": 120,
                    "stale_after_seconds": 900,
                    "message": "Provider cache is within TTL.",
                },
            },
            {
                "provider_id": "sec_edgar_public",
                "label": "SEC EDGAR data APIs",
                "auth_mode": "no-key",
                "safety_class": "public_read_only_fundamentals",
                "health": {
                    "state": "stale_cache",
                    "cache_id": "sec_companyfacts",
                    "cache_path": (
                        "market_data/fundamentals/sec/0000320193/companyfacts.json"
                    ),
                    "retrieved_at": "2026-05-25T08:00:00Z",
                    "age_seconds": 172800,
                    "stale_after_seconds": 86400,
                    "message": "Provider cache exists but is older than TTL.",
                },
            },
            {
                "provider_id": "eurostat_hicp_public",
                "label": "Eurostat HICP",
                "auth_mode": "no-key",
                "safety_class": "public_read_only_macro",
                "health": {
                    "state": "unavailable",
                    "cache_id": "eurostat_hicp",
                    "cache_path": "market_data/macro/eurostat/hicp_ea20_cp00_i15.json",
                    "retrieved_at": "",
                    "age_seconds": None,
                    "stale_after_seconds": 86400,
                    "message": "No provider cache timestamp is available yet.",
                },
            },
            {
                "provider_id": "fmp_stock_quote_optional_key",
                "label": "FMP stable quote",
                "auth_mode": "optional-local-key",
                "safety_class": "optional_local_secret_data_provider",
                "health": {"state": "key_required"},
            },
        ],
    }

    payload = provider_refresh_schedule_plan_payload(
        LocalStateStore(root=tmp_path),
        provider_payload=provider_payload,
    )
    rows = {row["provider_id"]: row for row in payload["providers"]}

    assert payload["mode"] == "read_only_provider_refresh_schedule_plan"
    assert payload["summary"]["eligible_provider_count"] == 3
    assert payload["summary"]["active_count"] == 1
    assert payload["summary"]["due_count"] == 2
    assert payload["summary"]["stale_count"] == 1
    assert payload["summary"]["missing_count"] == 1
    assert payload["summary"]["next_due_provider_id"] == "sec_edgar_public"
    assert rows["public_rss_news"]["due"] is False
    assert rows["public_rss_news"]["seconds_until_due"] == 780
    assert rows["sec_edgar_public"]["due_reason"] == "stale_cache"
    assert rows["eurostat_hicp_public"]["due_reason"] == "missing_cache"
    assert "fmp_stock_quote_optional_key" not in rows
    assert payload["actions"]["automatic_scheduler_enabled"] is False
    assert payload["actions"]["job_started"] is False
    assert payload["safety"]["read_only"] is True
    assert payload["safety"]["external_network"] is False
    assert payload["safety"]["provider_cache_mutation"] is False
    assert payload["safety"]["optional_key_providers_included"] is False
    assert payload["safety"]["secret_values_returned"] is False
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_provider_refresh_lifecycle_api_and_diagnostics_are_agent_operable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_json(
        tmp_path
        / "artifacts"
        / "diagnostics"
        / "provider-refresh-000000000005"
        / "job_status.json",
        {
            "run_id": "provider-refresh-000000000005",
            "status": "queued",
            "created_at": "2026-05-24T11:59:00Z",
            "started_at": "",
            "completed_at": "",
        },
    )
    client = _client(tmp_path, monkeypatch)

    lifecycle = client.get("/api/providers/refresh-public/lifecycle").json()
    schedule_plan = client.get("/api/providers/refresh-public/schedule-plan").json()
    providers = client.get("/api/providers").json()
    provider_cache = client.get("/api/providers/cache").json()
    governance = client.get("/api/governance").json()
    help_diagnostics = client.post("/api/help/diagnostics").json()
    governance_diagnostics = client.post("/api/governance/diagnostics").json()

    assert lifecycle["summary"]["run_count"] == 1
    assert lifecycle["safety"]["read_only"] is True
    assert schedule_plan["mode"] == "read_only_provider_refresh_schedule_plan"
    assert schedule_plan["summary"]["eligible_provider_count"] > 0
    assert schedule_plan["safety"]["read_only"] is True
    assert schedule_plan["safety"]["job_started"] is False
    assert schedule_plan["safety"]["provider_cache_mutation"] is False
    assert providers["refresh_lifecycle"]["summary"]["run_count"] == 1
    assert providers["refresh_schedule_plan"]["summary"]["eligible_provider_count"] > 0
    assert provider_cache["refresh_schedule_plan"]["summary"]["eligible_provider_count"] > 0
    assert governance["provider_refresh_lifecycle"]["summary"]["run_count"] == 1
    assert governance["provider_refresh_schedule_plan"]["safety"]["read_only"] is True
    assert governance["summary"]["provider_refresh_run_count"] == 1
    assert help_diagnostics["checks"]["provider_refresh_lifecycle_read_only"] is True
    assert help_diagnostics["checks"]["provider_refresh_stale_recovery_non_mutating"] is True
    assert governance_diagnostics["checks"]["provider_refresh_lifecycle_rows_present"] is True
    assert governance_diagnostics["checks"]["provider_refresh_lifecycle_read_only"] is True
    assert governance_diagnostics["safety"]["provider_refresh_status_recovery_writes_enabled"] is False
    assert (tmp_path / governance_diagnostics["artifacts"]["provider_refresh_lifecycle"]).is_file()
    assert "api_key=" not in json.dumps(lifecycle).lower()
    assert "password" not in json.dumps(lifecycle).lower()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()
