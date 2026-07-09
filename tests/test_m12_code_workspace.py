import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.storage import LocalStateStore


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(server, "STORE", LocalStateStore(root=tmp_path))
    return TestClient(server.create_app())


def test_code_initial_payload_reports_notebook_shell_and_safety(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    response = client.get("/api/code")

    payload = response.json()
    assert response.status_code == 200
    assert payload["first_use"] is True
    assert payload["title"] == "PYTHON NOTEBOOK"
    assert payload["toolbar"] == [
        "NEW",
        "OPEN",
        "SAVE",
        "+ CELL",
        "CONTEXT NB",
        "ANALYZE",
        "CLEAR OUT",
        "RUN ALL",
        "SIDEBAR",
    ]
    assert payload["cell_controls"] == ["RUN", "TYPE", "UP", "DN", "DEL"]
    assert payload["notebook_draft"]["cells"][0]["cell_type"] == "code"
    assert payload["engine"]["engine_id"] == "local_code_v1"
    assert payload["engine"]["kernel_status"] == "idle"
    assert payload["analysis_health"]["mode"] == "metadata_only_code_analysis_health"
    assert payload["analysis_health"]["summary"]["notebook_count"] == 0
    assert payload["analysis_health"]["summary"]["recovery_queue_count"] == 1
    assert payload["analysis_health"]["safety"]["notebook_execution"] is False
    assert payload["analysis_health"]["safety"]["source_returned"] is False
    assert payload["analysis_health"]["safety"]["artifact_content_read"] is False
    assert payload["analysis_health"]["safety"]["automatic_repair_enabled"] is False
    assert payload["safety"] == {
        "local_files_only": True,
        "execution_enabled": False,
        "run_enabled": False,
        "run_all_enabled": False,
        "kernel_process_enabled": False,
        "cloud_execution": False,
        "external_network": False,
        "private_api_required": False,
        "credentials_persisted": False,
        "broker_mutation": False,
        "real_orders": False,
        "real_balance": False,
        "margin": False,
        "leverage": False,
        "short": False,
        "derivatives": False,
        "output": "edit_only",
        "runtime_state": "disabled_no_sandbox_contract",
    }


def test_code_new_add_save_export_and_ipynb_artifact(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    created = client.post("/api/code/new", json={"name": "M12 Research Notebook"})
    added = client.post(
        "/api/code/add-cell",
        json={"cell_type": "markdown", "source": "## Local research note"},
    )
    notebook = added.json()["active_notebook"]
    notebook["cells"][0]["source"] = "prices = [1, 2, 3]\nprint(sum(prices))"
    saved = client.post("/api/code/notebook", json={"notebook": notebook})
    exported = client.post(
        "/api/code/export",
        json={"notebook_id": saved.json()["active_notebook_id"]},
    )
    local_state = client.get("/api/local-state")

    notebook_id = saved.json()["active_notebook_id"]
    assert created.status_code == 200
    assert added.status_code == 200
    assert saved.status_code == 200
    assert saved.json()["active_notebook"]["name"] == "M12 Research Notebook"
    assert saved.json()["engine"]["cell_count"] == 2
    assert exported.status_code == 200
    assert exported.json()["format"] == "ipynb"
    assert exported.json()["ipynb"]["nbformat"] == 4
    assert (tmp_path / "artifacts" / "code_workspace" / "code_state.json").is_file()
    assert (tmp_path / "artifacts" / "code_workspace" / f"{notebook_id}.ipynb").is_file()
    assert local_state.json()["storage"]["code_state"] == "artifacts/code_workspace/code_state.json"


def test_code_analyze_writes_static_report_artifacts_without_execution(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)

    created = client.post("/api/code/new", json={"name": "Artifact Review Notebook"})
    notebook = created.json()["active_notebook"]
    notebook["cells"][0]["source"] = (
        "import math\n"
        "from pathlib import Path\n\n"
        "def load_summary():\n"
        "    return Path('artifacts/backtests/local-run/summary.json')\n\n"
        "summary_path = load_summary()\n"
        "report_path = 'artifacts/portfolio/reports/local/report.md'\n"
        "duration = math.sqrt(16)"
    )
    saved = client.post("/api/code/notebook", json={"notebook": notebook})
    analyzed = client.post(
        "/api/code/analyze",
        json={"notebook_id": saved.json()["active_notebook_id"]},
    )

    assert created.status_code == 200
    assert saved.status_code == 200
    assert analyzed.status_code == 200
    payload = analyzed.json()
    analysis = payload["analysis_result"]
    assert payload["last_analysis"]["analysis_id"] == analysis["analysis_id"]
    assert analysis["output_mode"] == "local_static_notebook_report"
    assert analysis["summary"]["cell_count"] == 1
    assert analysis["summary"]["execution_enabled"] is False
    assert analysis["summary"]["mutation"] is False
    assert analysis["summary"]["import_count"] == 2
    assert analysis["summary"]["definition_count"] == 1
    assert analysis["summary"]["call_count"] == 3
    assert analysis["summary"]["syntax_error_count"] == 0
    assert analysis["static_outline"]["imports"] == ["math", "pathlib.Path"]
    assert analysis["static_outline"]["definitions"] == [
        {"kind": "function", "name": "load_summary"}
    ]
    assert analysis["static_outline"]["calls"] == ["Path", "load_summary", "math.sqrt"]
    assert analysis["static_outline"]["safety"] == {
        "static_parse_only": True,
        "execution_enabled": False,
        "source_returned": False,
    }
    assert "artifacts/backtests/local-run/summary.json" in analysis["referenced_artifacts"]
    assert analysis["artifact_files"]["report"].endswith("/analysis_report.md")
    assert analysis["artifact_files"]["manifest"].endswith("/analysis_manifest.json")
    for artifact in analysis["artifact_files"].values():
        assert (tmp_path / artifact).is_file()
    report_text = (tmp_path / analysis["artifact_files"]["report"]).read_text(encoding="utf-8")
    assert "Code Notebook Static Report" in report_text
    assert "static analysis only" in report_text
    manifest = json.loads(
        (tmp_path / analysis["artifact_files"]["manifest"]).read_text(encoding="utf-8")
    )
    assert manifest["safety"]["static_analysis_only"] is True
    assert manifest["safety"]["execution_enabled"] is False
    assert manifest["safety"]["real_orders"] is False
    assert manifest["static_outline"]["imports"] == ["math", "pathlib.Path"]
    assert manifest["static_outline"]["safety"]["source_returned"] is False
    assert "Imports: 2" in report_text
    assert "function: load_summary" in report_text


def test_code_analysis_health_is_metadata_only(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    created = client.post("/api/code/new", json={"name": "Health Matrix Notebook"})
    notebook = created.json()["active_notebook"]
    notebook["cells"][0]["source"] = "import math\nresult = math.sqrt(25)"
    saved = client.post("/api/code/notebook", json={"notebook": notebook})

    notebook_id = saved.json()["active_notebook_id"]
    saved_health = client.get("/api/code/analysis-health")

    assert saved_health.status_code == 200
    health_payload_text = saved_health.text
    health = saved_health.json()
    assert health["mode"] == "metadata_only_code_analysis_health"
    assert health["summary"]["notebook_count"] == 1
    assert health["summary"]["partial_count"] == 1
    assert health["summary"]["missing_artifact_count"] == 3
    assert health["summary"]["recovery_queue_count"] == 1
    assert "Code Notebook Static Report" not in health_payload_text
    row = health["notebooks"][0]
    assert row["notebook_id"] == notebook_id
    assert row["health_state"] == "partial_missing_analysis"
    assert row["notebook_artifact_exists"] is True
    assert row["analysis_artifact_exists"] is False
    assert row["report_artifact_exists"] is False
    assert row["manifest_artifact_exists"] is False
    assert row["present_count"] == 1
    assert row["missing_count"] == 3
    assert row["source_returned"] is False
    assert row["artifact_content_read"] is False
    assert health["recovery_queue"][0]["recommended_action"] == "code_analyze"
    assert health["safety"]["metadata_only"] is True
    assert health["safety"]["notebook_execution"] is False
    assert health["safety"]["source_returned"] is False
    assert health["safety"]["artifact_content_read"] is False

    analyzed = client.post("/api/code/analyze", json={"notebook_id": notebook_id})

    assert analyzed.status_code == 200
    embedded_health = analyzed.json()["analysis_health"]
    analyzed_row = embedded_health["notebooks"][0]
    assert embedded_health["summary"]["complete_count"] == 1
    assert embedded_health["summary"]["recovery_queue_count"] == 0
    assert analyzed_row["health_state"] == "complete"
    assert analyzed_row["present_count"] == 4
    assert analyzed_row["missing_count"] == 0
    assert analyzed_row["artifact_bytes"] > 0
    assert analyzed_row["last_analysis_id"] == analyzed.json()["analysis_result"]["analysis_id"]

    report_path = tmp_path / analyzed_row["report_artifact_path"]
    report_path.unlink()
    missing_report = client.get("/api/code/analysis-health").json()

    assert missing_report["summary"]["partial_count"] == 1
    assert missing_report["summary"]["recovery_queue_count"] == 1
    assert missing_report["notebooks"][0]["health_state"] == "partial_missing_analysis"
    assert missing_report["notebooks"][0]["report_artifact_exists"] is False
    assert "Code Notebook Static Report" not in json.dumps(missing_report)


def test_code_imports_exported_ipynb_without_execution(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    client.post("/api/code/new", json={"name": "Import Source"})
    exported = client.post("/api/code/export", json={}).json()["ipynb"]
    exported["metadata"]["local_terminal"]["name"] = "Imported Local Notebook"

    imported = client.post("/api/code/import", json={"notebook": json.dumps(exported)})

    assert imported.status_code == 200
    payload = imported.json()
    assert payload["active_notebook"]["name"] == "Imported Local Notebook"
    assert payload["active_notebook"]["kernel_status"] == "idle"
    assert payload["safety"]["execution_enabled"] is False
    assert payload["safety"]["cloud_execution"] is False


def test_code_selects_notebooks_and_clear_output_is_id_only(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    first = client.post("/api/code/new", json={"name": "First Notebook"})
    first_id = first.json()["active_notebook_id"]
    second = client.post("/api/code/new", json={"name": "Second Notebook"})
    second_id = second.json()["active_notebook_id"]

    selected = client.post("/api/code/select-notebook", json={"notebook_id": first_id})
    side_effect = client.post(
        "/api/code/clear-output",
        json={
            "notebook": {
                "notebook_id": "notebook-side-effect",
                "name": "Should Not Be Created",
                "cells": [{"cell_type": "code", "source": "print('local')"}],
            }
        },
    )
    cleared = client.post("/api/code/clear-output", json={"notebook_id": second_id})

    assert selected.status_code == 200
    assert selected.json()["active_notebook_id"] == first_id
    assert selected.json()["active_notebook"]["name"] == "First Notebook"
    assert side_effect.status_code == 422
    assert cleared.status_code == 200
    assert cleared.json()["active_notebook_id"] == second_id
    assert {item["notebook_id"] for item in cleared.json()["notebooks"]} == {
        first_id,
        second_id,
    }


def test_code_runtime_run_and_run_all_are_disabled(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    run = client.post("/api/code/run")
    run_all = client.post("/api/code/run-all")

    assert run.status_code == 403
    assert run.json()["detail"]["state"] == "disabled"
    assert run.json()["detail"]["safety"]["run_enabled"] is False
    assert run_all.status_code == 403
    assert run_all.json()["detail"]["state"] == "disabled"
    assert run_all.json()["detail"]["safety"]["run_all_enabled"] is False
    assert run_all.json()["detail"]["safety"]["real_orders"] is False


def test_code_rejects_secret_live_runtime_and_path_traversal(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)

    secret = client.post(
        "/api/code/import",
        json={
            "notebook": {
                "name": "Secret Notebook",
                "cells": [{"cell_type": "code", "source": "api_key = 'abc123'"}],
            }
        },
    )
    live_runtime = client.post(
        "/api/code/import",
        json={
            "notebook": {
                "name": "Live Notebook",
                "cells": [{"cell_type": "code", "source": "client.create_order('BTC/USDT')"}],
            }
        },
    )
    traversal = client.post(
        "/api/code/notebook",
        json={
            "notebook": {
                "name": "Bad Path",
                "path": "../outside.ipynb",
                "cells": [{"cell_type": "code", "source": "print('local')"}],
            }
        },
    )

    assert secret.status_code == 400
    assert secret.json()["detail"] == "Cell source appears to contain credential material"
    assert live_runtime.status_code == 400
    assert live_runtime.json()["detail"] == "Cell source contains forbidden live runtime intent"
    assert traversal.status_code == 400
    assert traversal.json()["detail"] == "Notebook path cannot traverse directories"
    assert not (tmp_path / "artifacts" / "code_workspace").exists()


def test_code_corrupt_existing_state_blocks_mutation_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    state_path = tmp_path / "artifacts" / "code_workspace" / "code_state.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not-json", encoding="utf-8")

    readonly = client.get("/api/code")
    response = client.post("/api/code/new", json={"name": "Blocked"})

    assert readonly.status_code == 200
    assert readonly.json()["invalid_notebooks"]["code_state.json"] == ("Invalid code state JSON")
    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Code state is invalid: code_state.json: Invalid code state JSON"
    )
    assert state_path.read_text(encoding="utf-8") == "{not-json"


def test_code_tampered_running_cell_blocks_mutation_without_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    created = client.post("/api/code/new", json={"name": "Tamper Guard"})
    state_path = tmp_path / "artifacts" / "code_workspace" / "code_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    notebook_id = created.json()["active_notebook_id"]
    state["notebooks"][notebook_id]["cells"][0]["execution_state"] = "running"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    readonly = client.get("/api/code")
    response = client.post("/api/code/add-cell", json={"cell_type": "code"})

    assert readonly.status_code == 200
    assert readonly.json()["invalid_notebooks"][notebook_id] == (
        "Cell execution state is not allowed"
    )
    assert response.status_code == 400
    assert response.json()["detail"] == (
        f"Stored notebook {notebook_id} is invalid: Cell execution state is not allowed"
    )
