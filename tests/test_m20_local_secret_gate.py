import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.local_terminal import server
from src.local_terminal.local_secrets import (
    LOCAL_SECRET_CONSENT,
    forget_local_data_provider_secret,
    read_local_data_provider_secret,
    store_local_data_provider_secret,
)
from src.local_terminal.providers import providers_payload
from src.local_terminal.secret_gate import (
    REDACTION_MARKER,
    contains_secret_material,
    redact_secret_material,
    secret_gate_payload,
)
from src.local_terminal.storage import LocalStateStore


ROOT = Path(__file__).resolve().parents[1]


def _synthetic_provider_value() -> str:
    return "fred-" + "local-" + "provider"


@pytest.mark.skipif(sys.platform != "win32", reason="Local secret store uses Windows DPAPI")
def test_secret_gate_contract_enables_local_data_provider_storage_without_default_file(
    tmp_path: Path,
) -> None:
    store = LocalStateStore(root=tmp_path)
    payload = secret_gate_payload(
        tmp_path,
        providers_payload(store),
        design_doc_root=ROOT,
    )

    assert payload["state"] == "local_secret_store_ready"
    assert payload["writes_enabled"] is True
    assert payload["reads_enabled"] is False
    assert payload["api_secret_value_reads_enabled"] is False
    assert payload["internal_provider_reads_enabled"] is True
    assert payload["key_entry_forms_enabled"] is True
    assert payload["secret_persistence_enabled"] is True
    assert payload["planned_store_exists"] is False
    assert "fred_optional_local_key" in payload["eligible_provider_ids"]
    assert "alphavantage_global_quote_optional_key" in payload["eligible_provider_ids"]
    assert "eia_open_data_optional_key" in payload["eligible_provider_ids"]
    assert "bea_regional_optional_key" in payload["eligible_provider_ids"]
    assert "census_api_optional_key" in payload["eligible_provider_ids"]
    assert "fmp_stock_quote_optional_key" in payload["eligible_provider_ids"]
    assert "premium_market_data_option" in payload["blocked_provider_ids"]
    assert payload["redaction_probe"]["api_key"] == REDACTION_MARKER
    assert REDACTION_MARKER in payload["redaction_probe"]["note"]
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


def test_secret_redactor_handles_nested_values_without_persisting() -> None:
    raw = {
        "provider": "example",
        "api_key": "abc123",
        "nested": [{"note": "token=abc123"}, {"private_key": "abc123"}],
    }

    redacted = redact_secret_material(raw)

    assert contains_secret_material(raw) is True
    assert redacted["api_key"] == REDACTION_MARKER
    assert redacted["nested"][0]["note"] == f"token: {REDACTION_MARKER}"
    assert redacted["nested"][1]["private_key"] == REDACTION_MARKER
    assert "abc123" not in str(redacted)


@pytest.mark.skipif(sys.platform != "win32", reason="Local secret store uses Windows DPAPI")
def test_local_secret_store_seals_and_reads_only_inside_provider_boundary(
    tmp_path: Path,
) -> None:
    store = LocalStateStore(root=tmp_path)
    provider_state = providers_payload(store)
    value = _synthetic_provider_value()

    stored = store_local_data_provider_secret(
        tmp_path,
        provider_state,
        provider_id="fred_optional_local_key",
        secret_value=value,
        consent=LOCAL_SECRET_CONSENT,
    )

    store_path = tmp_path / "settings" / "local_secrets.json"
    raw_store = store_path.read_text(encoding="utf-8")
    assert stored["action"] == "stored"
    assert stored["stored_provider_ids"] == ["fred_optional_local_key"]
    assert stored["planned_store_exists"] is True
    assert "protected_value" in raw_store
    assert value not in raw_store
    assert read_local_data_provider_secret(
        tmp_path,
        provider_state,
        provider_id="fred_optional_local_key",
    ) == value

    forgotten = forget_local_data_provider_secret(
        tmp_path,
        provider_state,
        provider_id="fred_optional_local_key",
    )
    assert forgotten["action"] == "forgotten"
    assert forgotten["stored_provider_ids"] == []
    assert not store_path.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Local secret store uses Windows DPAPI")
def test_secret_gate_api_and_governance_store_only_redacted_status(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())
    value = _synthetic_provider_value()

    gate_response = client.get("/api/secret-gate")
    store_response = client.post(
        "/api/local-secrets",
        json={
            "provider_id": "fred_optional_local_key",
            "secret_value": value,
            "consent": LOCAL_SECRET_CONSENT,
        },
    )
    governance_response = client.get("/api/governance")
    help_response = client.get("/api/help")

    assert gate_response.status_code == 200
    assert gate_response.json()["state"] == "local_secret_store_ready"
    assert store_response.status_code == 200
    assert value not in store_response.text
    stored = store_response.json()
    assert stored["stored_provider_ids"] == ["fred_optional_local_key"]
    assert stored["api_secret_value_reads_enabled"] is False
    governance = governance_response.json()
    fred_row = next(
        row
        for row in governance["provider_setup"]
        if row["provider_id"] == "fred_optional_local_key"
    )
    assert fred_row["form_enabled"] is True
    assert fred_row["secret_persistence_enabled"] is True
    assert fred_row["secret_stored"] is True
    assert value not in governance_response.text
    assert help_response.json()["governance"]["secret_gate_state"] == "local_secret_store_ready"
    assert value not in help_response.text
    assert (tmp_path / "settings" / "local_secrets.json").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Local secret store uses Windows DPAPI")
def test_secret_gate_api_requires_explicit_consent(tmp_path: Path, monkeypatch) -> None:
    store = LocalStateStore(root=tmp_path)
    monkeypatch.setattr(server, "STORE", store)
    client = TestClient(server.create_app())

    response = client.post(
        "/api/local-secrets",
        json={
            "provider_id": "fred_optional_local_key",
            "secret_value": _synthetic_provider_value(),
        },
    )

    assert response.status_code == 400
    assert "consent" in response.json()["detail"].lower()
    assert not (tmp_path / "settings" / "local_secrets.json").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Local secret store uses Windows DPAPI")
def test_secret_store_rejects_paid_provider_and_wrong_consent(tmp_path: Path) -> None:
    store = LocalStateStore(root=tmp_path)
    provider_state = providers_payload(store)
    value = _synthetic_provider_value()

    with pytest.raises(ValueError, match="not eligible"):
        store_local_data_provider_secret(
            tmp_path,
            provider_state,
            provider_id="premium_market_data_option",
            secret_value=value,
            consent=LOCAL_SECRET_CONSENT,
        )

    with pytest.raises(ValueError, match="consent"):
        store_local_data_provider_secret(
            tmp_path,
            provider_state,
            provider_id="fred_optional_local_key",
            secret_value=value,
            consent="no",
        )

    assert not (tmp_path / "settings" / "local_secrets.json").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Local secret store uses Windows DPAPI")
def test_secret_store_fails_closed_on_malformed_store(tmp_path: Path) -> None:
    store = LocalStateStore(root=tmp_path)
    provider_state = providers_payload(store)
    store_path = tmp_path / "settings" / "local_secrets.json"
    store_path.parent.mkdir(parents=True)
    store_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="could not be read"):
        store_local_data_provider_secret(
            tmp_path,
            provider_state,
            provider_id="fred_optional_local_key",
            secret_value=_synthetic_provider_value(),
            consent=LOCAL_SECRET_CONSENT,
        )

    assert store_path.read_text(encoding="utf-8") == "{not json"
