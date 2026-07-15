"""Local-only secret persistence for optional data-provider credentials."""

from __future__ import annotations

import base64
import ctypes
import json
import os
import stat
import sys
import time
from ctypes import wintypes
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


LOCAL_SECRET_STORE = "settings/local_secrets.json"
LOCAL_SECRET_CONSENT = "STORE_LOCAL_DATA_PROVIDER_SECRET"
LOCAL_SECRET_STORE_VERSION = 1
LOCAL_SECRET_STORAGE_MODE = "windows_dpapi_current_user"
LOCAL_SECRET_UNAVAILABLE_MODE = "unavailable"
ALLOWED_PROVIDER_SAFETY_CLASS = "optional_local_secret_data_provider"
_MAX_SECRET_LENGTH = 4096
_MIN_SECRET_LENGTH = 8
_DPAPI_ENTROPY = b"local-terminal-data-provider-secret-v1"
_CRYPTPROTECT_UI_FORBIDDEN = 0x01


class LocalSecretError(ValueError):
    """Raised when a local data-provider secret request violates the gate."""


@dataclass(frozen=True)
class LocalSecretProvider:
    provider_id: str
    label: str
    auth_mode: str
    safety_class: str
    eligible: bool
    blocked_reason: str


def local_secret_status(root: Path, provider_state: dict[str, Any]) -> dict[str, Any]:
    """Return redacted local secret-store state for optional data providers."""

    providers = local_secret_provider_catalog(provider_state)
    eligible = [provider for provider in providers if provider.eligible]
    blocked = [provider for provider in providers if not provider.eligible]
    store_path = _store_path(root)
    envelope = _read_store(store_path)
    records = envelope.get("providers") if isinstance(envelope.get("providers"), dict) else {}
    available = dpapi_available()
    stored_ids = [
        provider_id
        for provider_id in records
        if isinstance(provider_id, str)
        and any(provider.provider_id == provider_id for provider in eligible)
    ]
    rows = []
    for provider in providers:
        record = records.get(provider.provider_id) if isinstance(records, dict) else None
        record = record if isinstance(record, dict) else {}
        rows.append(
            {
                "provider_id": provider.provider_id,
                "label": provider.label,
                "eligible": provider.eligible,
                "blocked_reason": provider.blocked_reason,
                "stored": provider.provider_id in stored_ids,
                "sealed_id": str(record.get("sealed_id") or ""),
                "updated_at": str(record.get("updated_at") or ""),
                "storage_mode": str(record.get("storage_mode") or LOCAL_SECRET_STORAGE_MODE),
            }
        )

    enabled = available and bool(eligible)
    return {
        "store_path": LOCAL_SECRET_STORE,
        "store_exists": store_path.is_file(),
        "planned_store_path": LOCAL_SECRET_STORE,
        "planned_store_exists": store_path.is_file(),
        "store_version": LOCAL_SECRET_STORE_VERSION,
        "storage_mode": LOCAL_SECRET_STORAGE_MODE if available else LOCAL_SECRET_UNAVAILABLE_MODE,
        "storage_available": available,
        "consent_phrase": LOCAL_SECRET_CONSENT,
        "writes_enabled": enabled,
        "key_entry_forms_enabled": enabled,
        "secret_persistence_enabled": enabled,
        "reads_enabled": False,
        "api_secret_value_reads_enabled": False,
        "internal_provider_reads_enabled": enabled,
        "allowed_provider_class": ALLOWED_PROVIDER_SAFETY_CLASS,
        "eligible_provider_ids": [provider.provider_id for provider in eligible],
        "blocked_provider_ids": [provider.provider_id for provider in blocked],
        "stored_provider_ids": stored_ids,
        "stored_provider_count": len(stored_ids),
        "provider_secrets": rows,
        "safety": {
            "provider_scope": "optional local-key data providers only",
            "broker_exchange_private_use": False,
            "live_trading_use": False,
            "real_balance_read": False,
            "http_value_read_endpoint": False,
            "tracked_file_allowed": False,
            "screenshots_may_contain_values": False,
            "logs_may_contain_values": False,
        },
    }


def local_secret_provider_catalog(provider_state: dict[str, Any]) -> list[LocalSecretProvider]:
    """Return optional-key provider rows classified for local-secret eligibility."""

    providers = provider_state.get("providers") if isinstance(provider_state.get("providers"), list) else []
    rows: list[LocalSecretProvider] = []
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        auth_mode = str(provider.get("auth_mode") or "")
        if "optional-local-key" not in auth_mode:
            continue
        safety_class = str(provider.get("safety_class") or "")
        provider_id = str(provider.get("provider_id") or "")
        paid_gated = "paid" in auth_mode or "plan" in str(provider.get("capability_state") or "")
        eligible = safety_class == ALLOWED_PROVIDER_SAFETY_CLASS and not paid_gated
        if eligible:
            blocked_reason = ""
        elif paid_gated:
            blocked_reason = "paid_or_plan_gated"
        else:
            blocked_reason = "not_optional_data_provider"
        rows.append(
            LocalSecretProvider(
                provider_id=provider_id,
                label=str(provider.get("label") or provider_id),
                auth_mode=auth_mode,
                safety_class=safety_class,
                eligible=eligible,
                blocked_reason=blocked_reason,
            )
        )
    return [row for row in rows if row.provider_id]


def store_local_data_provider_secret(
    root: Path,
    provider_state: dict[str, Any],
    *,
    provider_id: str,
    secret_value: str,
    consent: str,
) -> dict[str, Any]:
    """Seal a user-owned optional data-provider secret without returning it."""

    provider = _require_eligible_provider(provider_state, provider_id)
    if consent != LOCAL_SECRET_CONSENT:
        raise LocalSecretError("Explicit local data-provider secret consent is required")
    value = str(secret_value or "").strip()
    if not (_MIN_SECRET_LENGTH <= len(value) <= _MAX_SECRET_LENGTH):
        raise LocalSecretError("Provider secret length is outside the allowed local range")
    if not dpapi_available():
        raise LocalSecretError("Windows DPAPI storage is unavailable in this runtime")

    now = _utc_now()
    store_path = _store_path(root)
    envelope = _read_store(store_path, strict=True)
    records = envelope.get("providers") if isinstance(envelope.get("providers"), dict) else {}
    sealed_id = f"sealed-{uuid4().hex[:12]}"
    records[provider.provider_id] = {
        "provider_id": provider.provider_id,
        "label": provider.label,
        "sealed_id": sealed_id,
        "storage_mode": LOCAL_SECRET_STORAGE_MODE,
        "protected_value": base64.b64encode(_dpapi_protect(value.encode("utf-8"))).decode("ascii"),
        "created_at": str(records.get(provider.provider_id, {}).get("created_at") or now),
        "updated_at": now,
        "value_length": len(value),
    }
    envelope = {
        "version": LOCAL_SECRET_STORE_VERSION,
        "storage_mode": LOCAL_SECRET_STORAGE_MODE,
        "created_at": str(envelope.get("created_at") or now),
        "updated_at": now,
        "providers": records,
    }
    _write_store(store_path, envelope, root)
    status = local_secret_status(root, provider_state)
    status["action"] = "stored"
    status["provider_id"] = provider.provider_id
    return status


def forget_local_data_provider_secret(
    root: Path,
    provider_state: dict[str, Any],
    *,
    provider_id: str,
) -> dict[str, Any]:
    """Remove a stored optional data-provider secret without exposing values."""

    provider = _require_eligible_provider(provider_state, provider_id)
    store_path = _store_path(root)
    envelope = _read_store(store_path, strict=True)
    records = envelope.get("providers") if isinstance(envelope.get("providers"), dict) else {}
    records.pop(provider.provider_id, None)
    if records:
        envelope["providers"] = records
        envelope["updated_at"] = _utc_now()
        _write_store(store_path, envelope, root)
    else:
        store_path.unlink(missing_ok=True)
    status = local_secret_status(root, provider_state)
    status["action"] = "forgotten"
    status["provider_id"] = provider.provider_id
    return status


def read_local_data_provider_secret(
    root: Path,
    provider_state: dict[str, Any],
    *,
    provider_id: str,
) -> str:
    """Read a sealed value for future provider adapters; never expose this over HTTP."""

    provider = _require_eligible_provider(provider_state, provider_id)
    store_path = _store_path(root)
    envelope = _read_store(store_path, strict=True)
    records = envelope.get("providers") if isinstance(envelope.get("providers"), dict) else {}
    record = records.get(provider.provider_id) if isinstance(records, dict) else None
    if not isinstance(record, dict):
        raise LocalSecretError("No local provider secret is stored")
    protected = str(record.get("protected_value") or "")
    if not protected:
        raise LocalSecretError("Stored provider secret is missing sealed material")
    try:
        decrypted = _dpapi_unprotect(base64.b64decode(protected.encode("ascii")))
    except (OSError, ValueError) as exc:
        raise LocalSecretError("Stored provider secret could not be opened") from exc
    return decrypted.decode("utf-8")


def dpapi_available() -> bool:
    """Return True when Windows current-user DPAPI can be called."""

    return sys.platform == "win32" and hasattr(ctypes, "WinDLL")


def _require_eligible_provider(provider_state: dict[str, Any], provider_id: str) -> LocalSecretProvider:
    requested_id = str(provider_id or "").strip()
    for provider in local_secret_provider_catalog(provider_state):
        if provider.provider_id != requested_id:
            continue
        if provider.eligible:
            return provider
        raise LocalSecretError(f"Provider is not eligible for local secret storage: {provider.blocked_reason}")
    raise LocalSecretError("Unknown optional local-key data provider")


def _store_path(root: Path) -> Path:
    path = root / LOCAL_SECRET_STORE
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise LocalSecretError("Local secret store path escaped the workspace")
    return path


def _read_store(path: Path, *, strict: bool = False) -> dict[str, Any]:
    if not path.is_file():
        return {"version": LOCAL_SECRET_STORE_VERSION, "providers": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        if strict:
            raise LocalSecretError("Local secret store could not be read")
        return {"version": LOCAL_SECRET_STORE_VERSION, "providers": {}}
    if isinstance(payload, dict):
        return payload
    if strict:
        raise LocalSecretError("Local secret store must be a JSON object")
    return {"version": LOCAL_SECRET_STORE_VERSION, "providers": {}}


def _write_store(path: Path, payload: dict[str, Any], root: Path) -> None:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise LocalSecretError("Refusing to write local secret store outside the workspace")

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{time.monotonic_ns()}.tmp")
    with tmp_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    for attempt in range(5):
        try:
            tmp_path.replace(path)
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)
            return
        except PermissionError:
            if attempt == 4:
                tmp_path.unlink(missing_ok=True)
                raise
            time.sleep(0.05 * (attempt + 1))


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _dpapi_protect(payload: bytes) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    in_blob, in_buffer = _blob_from_bytes(payload)
    entropy_blob, entropy_buffer = _blob_from_bytes(_DPAPI_ENTROPY)
    out_blob = _DataBlob()
    _configure_cryptprotect(crypt32)
    ok = crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "Local data provider secret",
        ctypes.byref(entropy_blob),
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    _keep_buffers_alive(in_buffer, entropy_buffer)
    if not ok:
        raise OSError(ctypes.get_last_error(), "CryptProtectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        _local_free(out_blob.pbData)


def _dpapi_unprotect(payload: bytes) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    in_blob, in_buffer = _blob_from_bytes(payload)
    entropy_blob, entropy_buffer = _blob_from_bytes(_DPAPI_ENTROPY)
    out_blob = _DataBlob()
    _configure_cryptunprotect(crypt32)
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(entropy_blob),
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    )
    _keep_buffers_alive(in_buffer, entropy_buffer)
    if not ok:
        raise OSError(ctypes.get_last_error(), "CryptUnprotectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        _local_free(out_blob.pbData)


def _configure_cryptprotect(crypt32: Any) -> None:
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL


def _configure_cryptunprotect(crypt32: Any) -> None:
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL


def _blob_from_bytes(payload: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
    buffer = ctypes.create_string_buffer(payload, len(payload))
    blob = _DataBlob(
        len(payload),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def _local_free(pointer: Any) -> None:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
    kernel32.LocalFree.restype = wintypes.HLOCAL
    kernel32.LocalFree(ctypes.cast(pointer, wintypes.HLOCAL))


def _keep_buffers_alive(*_buffers: Any) -> None:
    return None


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
