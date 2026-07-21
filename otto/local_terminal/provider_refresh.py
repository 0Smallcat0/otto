"""Manual public provider refresh service and local job artifacts."""

from __future__ import annotations

import json
import re
import urllib.error
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from otto.local_terminal.storage import LocalStateStore

RUN_ID_PATTERN = re.compile(r"^provider-refresh-[0-9a-f]{12}$")
JOB_STATUS_FILE = "job_status.json"
REFRESH_MODE = "manual_public_no_key_provider_refresh"
QUEUED_STALE_AFTER_SECONDS = 15 * 60
RUNNING_STALE_AFTER_SECONDS = 60 * 60
PUBLIC_REFRESH_SCHEDULE_PROVIDER_IDS = (
    "binance_spot_public",
    "public_rss_news",
    "gdelt_doc_public",
    "sec_edgar_public",
    "sec_xbrl_frames_public",
    "sec_company_ticker_registry_public",
    "sec_company_submissions_public",
    "dbnomics_public",
    "bls_public_macro",
    "eurostat_hicp_public",
    "us_treasury_yield_public",
    "nyfed_sofr_public",
    "ecb_fx_reference_public",
    "federal_reserve_h10_ddp_public",
    "bank_of_canada_valet_fx_reference_public",
    "world_bank_commodity_monthly_public",
    "cftc_cot_legacy_public",
    "sec_fund_ticker_registry_public",
    "stooq_public_quote_snapshot",
    "moex_iss_delayed_quote_snapshot",
    "twse_openapi_daily_quote_snapshot",
    "nasdaq_trader_symbol_directory_public",
    "openfigi_identifier_mapping_public",
)
_REFRESH_JOB_LOCK = Lock()


@dataclass(frozen=True)
class PublicProviderRefreshCallbacks:
    """Route-specific refresh callbacks owned by the API layer."""

    market_payload: Callable[[], dict[str, Any]]
    crypto_detail_payload: Callable[[], dict[str, Any]]
    news_payload: Callable[[], dict[str, Any]]
    research_payload: Callable[[], dict[str, Any]]
    rates_payload: Callable[[], dict[str, Any]]
    fx_payload: Callable[[], dict[str, Any]]
    commodity_payload: Callable[[], dict[str, Any]]
    fund_payload: Callable[[], dict[str, Any]]
    stooq_quote_payload: Callable[[], dict[str, Any]]
    moex_quote_payload: Callable[[], dict[str, Any]]
    twse_quote_payload: Callable[[], dict[str, Any]]
    nasdaq_symbol_payload: Callable[[], dict[str, Any]]
    openfigi_mapping_payload: Callable[[], dict[str, Any]]
    provider_state_payload: Callable[[], dict[str, Any]]


def new_provider_refresh_run_id() -> str:
    return f"provider-refresh-{uuid4().hex[:12]}"


def run_public_provider_refresh(
    store: LocalStateStore,
    callbacks: PublicProviderRefreshCallbacks,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Refresh public no-key provider caches and write the refresh bundle."""

    run_id = run_id or new_provider_refresh_run_id()
    _validate_run_id(run_id)
    started_at = _utc_now()
    results: list[dict[str, Any]] = []

    market_payload = callbacks.market_payload()
    market_cache_written = False
    if market_payload.get("cache"):
        store.write_market_cache(market_payload["cache"])
        market_cache_written = True
    market_status = market_payload.get("status")
    results.append(
        provider_refresh_result(
            "binance_spot_public",
            "Crypto ticker cache",
            market_status,
            cache_written=market_cache_written and status_has_fresh_runtime_cache(market_status),
            cache_path="market_data/crypto_latest.json",
        )
    )

    detail_payload = callbacks.crypto_detail_payload()
    detail_cache_written = False
    if detail_payload.get("cache"):
        store.write_crypto_detail_cache(detail_payload["cache"])
        detail_cache_written = True
    detail_status = detail_payload.get("status")
    provider_id = "binance_spot_public"
    if isinstance(detail_status, dict):
        provider_id = str(detail_status.get("provider_id") or provider_id)
    results.append(
        provider_refresh_result(
            provider_id,
            "Crypto depth/candles cache",
            detail_status,
            cache_written=detail_cache_written and status_has_fresh_runtime_cache(detail_status),
            cache_path="market_data/crypto/BTCUSDT/15m.json",
        )
    )

    stooq_payload = callbacks.stooq_quote_payload()
    stooq_status = stooq_payload.get("status") if isinstance(stooq_payload, dict) else {}
    results.append(
        provider_refresh_result(
            "stooq_public_quote_snapshot",
            "Stooq public quote snapshots",
            stooq_status,
            cache_written=status_has_fresh_runtime_cache(stooq_status),
            cache_path="market_data/quotes/stooq/AAPLUS.json",
        )
    )

    moex_payload = callbacks.moex_quote_payload()
    moex_status = moex_payload.get("status") if isinstance(moex_payload, dict) else {}
    results.append(
        provider_refresh_result(
            "moex_iss_delayed_quote_snapshot",
            "MOEX ISS delayed quote snapshots",
            moex_status,
            cache_written=status_has_fresh_runtime_cache(moex_status),
            cache_path="market_data/quotes/moex/SBER.json",
        )
    )

    twse_payload = callbacks.twse_quote_payload()
    twse_status = twse_payload.get("status") if isinstance(twse_payload, dict) else {}
    results.append(
        provider_refresh_result(
            "twse_openapi_daily_quote_snapshot",
            "TWSE OpenAPI daily quote snapshots",
            twse_status,
            cache_written=status_has_fresh_runtime_cache(twse_status),
            cache_path="market_data/quotes/twse/2330.json",
        )
    )

    nasdaq_payload = callbacks.nasdaq_symbol_payload()
    nasdaq_status = nasdaq_payload.get("status") if isinstance(nasdaq_payload, dict) else {}
    results.append(
        provider_refresh_result(
            "nasdaq_trader_symbol_directory_public",
            "Nasdaq Trader symbol directory",
            nasdaq_status,
            cache_written=status_has_fresh_runtime_cache(nasdaq_status),
            cache_path="market_data/reference/nasdaq_trader/symbol_directory.json",
        )
    )

    openfigi_payload = callbacks.openfigi_mapping_payload()
    openfigi_status = (
        openfigi_payload.get("status") if isinstance(openfigi_payload, dict) else {}
    )
    results.append(
        provider_refresh_result(
            "openfigi_identifier_mapping_public",
            "OpenFIGI identifier mapping",
            openfigi_status,
            cache_written=status_has_fresh_runtime_cache(openfigi_status),
            cache_path="market_data/reference/openfigi/mapping.json",
        )
    )

    try:
        news = callbacks.news_payload()
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        news = {
            "status": {
                "source": "public_rss_news",
                "state": "unavailable",
                "last_update": "",
                "message": f"Public RSS refresh failed: {exc.__class__.__name__}.",
                "source_errors": [_safe_error_message(exc)],
            },
            "cache": None,
        }
    news_cache_written = False
    if news.get("cache"):
        store.write_news_cache(news["cache"])
        news_cache_written = True
    news_status = news.get("status")
    results.append(
        provider_refresh_result(
            "public_rss_news",
            "Public news cache",
            news_status,
            cache_written=news_cache_written and status_has_fresh_runtime_cache(news_status),
            cache_path="artifacts/news/news_cache.json",
        )
    )
    gdelt_status = _news_provider_status(news, "gdelt_doc_public")
    if gdelt_status:
        results.append(
            provider_refresh_result(
                "gdelt_doc_public",
                "GDELT DOC ArticleList metadata",
                gdelt_status,
                cache_written=news_cache_written and status_has_fresh_runtime_cache(gdelt_status),
                cache_path="artifacts/news/news_cache.json",
            )
        )

    research = callbacks.research_payload()
    fundamentals = research.get("fundamentals") if isinstance(research, dict) else {}
    sec_frames = research.get("sec_frames") if isinstance(research, dict) else {}
    equity_registry = research.get("equity_registry") if isinstance(research, dict) else {}
    filings = research.get("filings") if isinstance(research, dict) else {}
    macro = research.get("macro") if isinstance(research, dict) else {}
    bls = research.get("bls") if isinstance(research, dict) else {}
    fundamentals_status = fundamentals.get("status") if isinstance(fundamentals, dict) else {}
    sec_frames_status = sec_frames.get("status") if isinstance(sec_frames, dict) else {}
    equity_registry_status = (
        equity_registry.get("status") if isinstance(equity_registry, dict) else {}
    )
    filings_status = filings.get("status") if isinstance(filings, dict) else {}
    filings_summary = filings.get("summary") if isinstance(filings, dict) else {}
    filings_cache_path = ""
    if isinstance(filings_summary, dict):
        filings_cache_path = str(filings_summary.get("cache_paths") or "")
    if not filings_cache_path and isinstance(filings_status, dict):
        filings_cache_path = str(filings_status.get("cache_path") or "")
    macro_status = macro.get("status") if isinstance(macro, dict) else {}
    dbnomics_status = research_cache_status(
        research,
        cache_key="dbnomics",
        provider_id="dbnomics_public",
        fallback_status=macro_status,
    )
    bls_status = bls.get("status") if isinstance(bls, dict) else {}
    eurostat = research.get("eurostat") if isinstance(research, dict) else {}
    eurostat_status = eurostat.get("status") if isinstance(eurostat, dict) else {}
    results.append(
        provider_refresh_result(
            "sec_edgar_public",
            "SEC fundamentals cache",
            fundamentals_status,
            cache_written=status_has_fresh_runtime_cache(fundamentals_status),
            cache_path="market_data/fundamentals/sec/0000320193/companyfacts.json",
        )
    )
    results.append(
        provider_refresh_result(
            "sec_xbrl_frames_public",
            "SEC XBRL frames cache",
            sec_frames_status,
            cache_written=status_has_fresh_runtime_cache(sec_frames_status),
            cache_path="market_data/fundamentals/sec/frames/us-gaap/Assets/USD/CY2023Q4I.json",
        )
    )
    results.append(
        provider_refresh_result(
            "sec_company_ticker_registry_public",
            "SEC company ticker registry cache",
            equity_registry_status,
            cache_written=status_has_fresh_runtime_cache(equity_registry_status),
            cache_path="market_data/fundamentals/sec/company_tickers.json",
        )
    )
    results.append(
        provider_refresh_result(
            "sec_company_submissions_public",
            "SEC company submissions cache",
            filings_status,
            cache_written=status_has_fresh_runtime_cache(filings_status),
            cache_path=filings_cache_path
            or "market_data/fundamentals/sec/0000320193/submissions.json",
        )
    )
    results.append(
        provider_refresh_result(
            "dbnomics_public",
            "DBnomics macro cache",
            dbnomics_status,
            cache_written=status_has_fresh_runtime_cache(dbnomics_status),
            cache_path=(
                "market_data/macro/dbnomics/INSEE/IPC-2015/"
                "A.IPC.SO.00.00.INDICE.ENSEMBLE.FE.SO.BRUT.2015.FALSE.json"
            ),
        )
    )
    results.append(
        provider_refresh_result(
            "bls_public_macro",
            "BLS public macro/labor cache",
            bls_status,
            cache_written=status_has_fresh_runtime_cache(bls_status),
            cache_path="market_data/macro/bls/latest_series.json",
        )
    )
    results.append(
        provider_refresh_result(
            "eurostat_hicp_public",
            "Eurostat HICP macro cache",
            eurostat_status,
            cache_written=status_has_fresh_runtime_cache(eurostat_status),
            cache_path="market_data/macro/eurostat/hicp_ea20_cp00_i15.json",
        )
    )

    rates = callbacks.rates_payload()
    treasury = rates.get("treasury") if isinstance(rates, dict) else {}
    if isinstance(rates, dict) and not treasury and isinstance(rates.get("status"), dict):
        treasury = rates
    sofr = rates.get("sofr") if isinstance(rates, dict) else {}
    rates_status = treasury.get("status") if isinstance(treasury, dict) else {}
    sofr_status = sofr.get("status") if isinstance(sofr, dict) else {}
    results.append(
        provider_refresh_result(
            "us_treasury_yield_public",
            "Treasury rates cache",
            rates_status,
            cache_written=status_has_fresh_runtime_cache(rates_status),
            cache_path="market_data/rates/treasury/daily_yield_curve.json",
        )
    )
    results.append(
        provider_refresh_result(
            "nyfed_sofr_public",
            "NY Fed SOFR reference cache",
            sofr_status,
            cache_written=status_has_fresh_runtime_cache(sofr_status),
            cache_path="market_data/rates/nyfed/sofr.json",
        )
    )

    fx = callbacks.fx_payload()
    fx_status = fx.get("status") if isinstance(fx, dict) else {}
    h10 = fx.get("h10") if isinstance(fx.get("h10"), dict) else {}
    h10_status = h10.get("status") if isinstance(h10.get("status"), dict) else {}
    boc = fx.get("boc") if isinstance(fx.get("boc"), dict) else {}
    boc_status = boc.get("status") if isinstance(boc.get("status"), dict) else {}
    results.append(
        provider_refresh_result(
            "ecb_fx_reference_public",
            "ECB FX reference cache",
            fx_status,
            cache_written=status_has_fresh_runtime_cache(fx_status),
            cache_path="market_data/fx/ecb/eurofxref_daily.json",
        )
    )
    results.append(
        provider_refresh_result(
            "federal_reserve_h10_ddp_public",
            "Federal Reserve H.10 FX reference cache",
            h10_status,
            cache_written=status_has_fresh_runtime_cache(h10_status),
            cache_path="market_data/fx/federal_reserve/h10_reference_rates.json",
        )
    )
    results.append(
        provider_refresh_result(
            "bank_of_canada_valet_fx_reference_public",
            "Bank of Canada Valet FX reference cache",
            boc_status,
            cache_written=status_has_fresh_runtime_cache(boc_status),
            cache_path="market_data/fx/bank_of_canada/valet_fx_reference_rates.json",
        )
    )

    commodities = callbacks.commodity_payload()
    commodity_status = commodities.get("status") if isinstance(commodities, dict) else {}
    cftc = commodities.get("cftc") if isinstance(commodities, dict) else {}
    cftc_status = cftc.get("status") if isinstance(cftc, dict) else {}
    results.append(
        provider_refresh_result(
            "world_bank_commodity_monthly_public",
            "World Bank commodities cache",
            commodity_status,
            cache_written=status_has_fresh_runtime_cache(commodity_status),
            cache_path="market_data/commodities/world_bank/pink_sheet_monthly.json",
        )
    )
    results.append(
        provider_refresh_result(
            "cftc_cot_legacy_public",
            "CFTC COT commodity positioning cache",
            cftc_status,
            cache_written=status_has_fresh_runtime_cache(cftc_status),
            cache_path="market_data/commodities/cftc/cot_legacy_futures.json",
        )
    )

    funds = callbacks.fund_payload()
    fund_status = funds.get("status") if isinstance(funds, dict) else {}
    results.append(
        provider_refresh_result(
            "sec_fund_ticker_registry_public",
            "SEC fund ticker cache",
            fund_status,
            cache_written=status_has_fresh_runtime_cache(fund_status),
            cache_path="market_data/funds/sec/company_tickers_mf.json",
        )
    )

    provider_state = callbacks.provider_state_payload()
    completed_at = _utc_now()
    summary = provider_refresh_summary(results)
    artifact_dir = f"artifacts/diagnostics/{run_id}"
    manifest = {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": completed_at,
        "output_mode": "public_no_key_provider_refresh",
        "refresh_mode": REFRESH_MODE,
        "artifact_dir": artifact_dir,
        "summary": summary,
        "results": results,
        "provider_summary_after": provider_state["summary"],
        "safety": _safety_payload(),
        "artifacts": {
            "manifest": f"{artifact_dir}/manifest.json",
            "results": f"{artifact_dir}/results.json",
            "providers_after": f"{artifact_dir}/providers_after.json",
            "job_status": f"{artifact_dir}/{JOB_STATUS_FILE}",
            "report": f"{artifact_dir}/report.md",
            "error_log": f"{artifact_dir}/error.log",
        },
    }
    write_provider_refresh_artifacts(store, run_id, manifest, provider_state)
    provider_payload = {**provider_state, "last_refresh": manifest}
    _write_job_status(
        store,
        run_id,
        _job_payload(
            run_id,
            status="completed",
            created_at=started_at,
            started_at=started_at,
            completed_at=completed_at,
            message="Public no-key provider refresh completed.",
            summary=summary,
            last_refresh=manifest,
            provider_payload=provider_payload,
        ),
    )
    return provider_payload


def create_public_provider_refresh_job(
    store: LocalStateStore,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    run_id = run_id or new_provider_refresh_run_id()
    _validate_run_id(run_id)
    now = _utc_now()
    job = _job_payload(
        run_id,
        status="queued",
        created_at=now,
        started_at="",
        completed_at="",
        message="Manual public no-key provider refresh is queued.",
    )
    _write_job_status(store, run_id, job)
    return job


def complete_public_provider_refresh_job(
    store: LocalStateStore,
    callbacks: PublicProviderRefreshCallbacks,
    run_id: str,
) -> dict[str, Any]:
    _validate_run_id(run_id)
    created_at = _read_job_status(store, run_id).get("created_at") or _utc_now()
    running = _job_payload(
        run_id,
        status="running",
        created_at=str(created_at),
        started_at=_utc_now(),
        completed_at="",
        message="Refreshing public no-key provider caches.",
    )
    _write_job_status(store, run_id, running)
    if not _REFRESH_JOB_LOCK.acquire(blocking=False):
        failed = _failed_job_payload(
            run_id,
            str(created_at),
            running["started_at"],
            RuntimeError("another public provider refresh job is already running"),
        )
        failed["message"] = "Public no-key provider refresh is already running."
        _write_job_status(store, run_id, failed)
        _write_failure_log(store, run_id, failed)
        return failed
    try:
        provider_payload = run_public_provider_refresh(store, callbacks, run_id=run_id)
    except Exception as exc:  # pragma: no cover - defensive local artifact path
        try:
            failed = _failed_job_payload(run_id, str(created_at), running["started_at"], exc)
            _write_job_status(store, run_id, failed)
            _write_failure_log(store, run_id, failed)
            return failed
        finally:
            _REFRESH_JOB_LOCK.release()
    else:
        _REFRESH_JOB_LOCK.release()

    manifest = provider_payload["last_refresh"]
    completed = _job_payload(
        run_id,
        status="completed",
        created_at=str(created_at),
        started_at=manifest["started_at"],
        completed_at=manifest["completed_at"],
        message="Public no-key provider refresh completed.",
        summary=manifest["summary"],
        last_refresh=manifest,
        provider_payload=provider_payload,
    )
    _write_job_status(store, run_id, completed)
    return completed


def read_public_provider_refresh_job(store: LocalStateStore, run_id: str) -> dict[str, Any] | None:
    _validate_run_id(run_id)
    job = _read_job_status(store, run_id)
    if job:
        return job
    manifest = _read_manifest(store, run_id)
    if not manifest:
        return None
    return _job_payload(
        run_id,
        status="completed",
        created_at=str(manifest.get("started_at") or ""),
        started_at=str(manifest.get("started_at") or ""),
        completed_at=str(manifest.get("completed_at") or ""),
        message="Public no-key provider refresh completed.",
        summary=manifest.get("summary") if isinstance(manifest.get("summary"), dict) else {},
        last_refresh=manifest,
    )


def latest_public_provider_refresh_manifest(store: LocalStateStore) -> dict[str, Any] | None:
    diagnostics_root = store.diagnostics_root_path
    if not diagnostics_root.exists():
        return None
    manifests: list[dict[str, Any]] = []
    for candidate in diagnostics_root.glob("provider-refresh-*"):
        if not RUN_ID_PATTERN.match(candidate.name):
            continue
        manifest = _read_manifest(store, candidate.name)
        if manifest:
            manifests.append(manifest)
    if not manifests:
        return None
    return max(manifests, key=lambda item: str(item.get("completed_at") or ""))


def provider_refresh_lifecycle_payload(
    store: LocalStateStore,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return read-only lifecycle/recovery state for public provider refresh jobs."""

    diagnostics_root = store.diagnostics_root_path
    now = now or datetime.now(tz=UTC)
    runs: list[dict[str, Any]] = []
    if diagnostics_root.exists():
        for candidate in sorted(diagnostics_root.glob("provider-refresh-*")):
            if not candidate.is_dir() or not RUN_ID_PATTERN.match(candidate.name):
                continue
            runs.append(_provider_refresh_lifecycle_row(candidate, now=now))

    runs.sort(key=lambda row: str(row.get("updated_at") or ""), reverse=True)
    latest = runs[0] if runs else {}
    stale_count = sum(1 for row in runs if bool(row.get("stale_interrupted")))
    failed_count = sum(1 for row in runs if row.get("status") == "failed")
    active_count = sum(
        1
        for row in runs
        if row.get("status") in {"queued", "running"}
        and not bool(row.get("stale_interrupted"))
    )
    manifest_only_count = sum(
        1 for row in runs if row.get("lifecycle_state") == "manifest_only_completed"
    )
    corrupt_count = sum(
        1 for row in runs if row.get("lifecycle_state") == "corrupt_status_metadata"
    )
    recovery_count = sum(
        1
        for row in runs
        if row.get("lifecycle_state")
        in {
            "stale_interrupted_queued",
            "stale_interrupted_running",
            "failed_retry_available",
            "corrupt_status_metadata",
            "manifest_only_completed",
        }
    )
    return {
        "generated_at": _utc_now(),
        "mode": "read_only_provider_refresh_lifecycle",
        "refresh_mode": REFRESH_MODE,
        "stale_after_seconds": {
            "queued": QUEUED_STALE_AFTER_SECONDS,
            "running": RUNNING_STALE_AFTER_SECONDS,
        },
        "summary": {
            "run_count": len(runs),
            "active_job_count": active_count,
            "completed_count": sum(1 for row in runs if row.get("status") == "completed"),
            "failed_count": failed_count,
            "stale_interrupted_count": stale_count,
            "manifest_only_count": manifest_only_count,
            "corrupt_status_count": corrupt_count,
            "recovery_recommended_count": recovery_count,
            "latest_run_id": str(latest.get("run_id") or ""),
            "latest_status": str(latest.get("status") or ""),
            "latest_lifecycle_state": str(latest.get("lifecycle_state") or ""),
            "latest_artifact_dir": str(latest.get("artifact_dir") or ""),
        },
        "runs": runs,
        "actions": {
            "inspect_job_status": True,
            "inspect_manifest": True,
            "start_manual_refresh_elsewhere": True,
            "retry_failed_by_new_manual_job": True,
            "mark_stale_complete_enabled": False,
            "recover_status_write_enabled": False,
            "prune_enabled": False,
            "archive_enabled": False,
            "delete_enabled": False,
        },
        "safety": {
            "read_only": True,
            "metadata_files_read": True,
            "provider_cache_mutation": False,
            "job_status_mutation": False,
            "destructive_actions_enabled": False,
            "external_network": False,
            "credentials_required": False,
            "secret_values_returned": False,
            "optional_key_providers_refreshed": False,
            "private_api_key_flow": False,
            "live_trading": False,
            "real_order_path": False,
            "real_balance_read": False,
            "installed_source_read": False,
        },
    }


def provider_refresh_schedule_plan_payload(
    store: LocalStateStore,
    *,
    provider_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return read-only due/stale state for manual public refresh planning."""

    if provider_payload is None:
        from otto.local_terminal.providers import providers_payload

        provider_payload = providers_payload(store)
    provider_payload = provider_payload if isinstance(provider_payload, dict) else {}
    providers = provider_payload.get("providers")
    providers = providers if isinstance(providers, list) else []
    rows = [
        _provider_refresh_schedule_row(provider)
        for provider in providers
        if _public_refresh_schedule_eligible(provider)
    ]
    active_count = sum(1 for row in rows if row["state"] == "active")
    stale_count = sum(1 for row in rows if row["state"] == "stale_cache")
    missing_count = sum(1 for row in rows if row["state"] == "unavailable")
    rate_limited_count = sum(1 for row in rows if row["state"] == "rate_limited")
    due_rows = [row for row in rows if row["due"]]
    future_rows = [
        row
        for row in rows
        if not row["due"] and isinstance(row.get("seconds_until_due"), int)
    ]
    next_due = due_rows[0] if due_rows else min(
        future_rows,
        key=lambda row: int(row.get("seconds_until_due") or 0),
        default={},
    )
    next_due_in = 0 if due_rows else next_due.get("seconds_until_due")
    return {
        "generated_at": _utc_now(),
        "mode": "read_only_provider_refresh_schedule_plan",
        "refresh_mode": REFRESH_MODE,
        "summary": {
            "eligible_provider_count": len(rows),
            "active_count": active_count,
            "due_count": len(due_rows),
            "stale_count": stale_count,
            "missing_count": missing_count,
            "rate_limited_count": rate_limited_count,
            "next_due_provider_id": str(next_due.get("provider_id") or ""),
            "next_due_in_seconds": next_due_in,
            "public_no_key_only": True,
        },
        "providers": rows,
        "actions": {
            "schedule_plan_endpoint": "/api/providers/refresh-public/schedule-plan",
            "manual_refresh_action_id": "provider_refresh_public_start",
            "start_manual_refresh_endpoint": "/api/providers/refresh-public/jobs",
            "automatic_scheduler_enabled": False,
            "job_started": False,
            "provider_cache_mutation": False,
            "destructive_cleanup_enabled": False,
        },
        "safety": {
            "read_only": True,
            "external_network": False,
            "job_started": False,
            "provider_cache_mutation": False,
            "secret_values_returned": False,
            "optional_key_providers_included": False,
            "private_api_key_flow": False,
            "destructive_actions_enabled": False,
            "live_trading": False,
            "real_order_path": False,
            "real_balance_read": False,
            "installed_source_read": False,
        },
    }


def provider_refresh_result(
    provider_id: str,
    label: str,
    status: Any,
    *,
    cache_written: bool,
    cache_path: str,
) -> dict[str, Any]:
    status = status if isinstance(status, dict) else {}
    source_errors = status.get("source_errors")
    source_errors = source_errors if isinstance(source_errors, list) else []
    state = str(status.get("state") or "unavailable")
    cache_available = status_has_runtime_cache(status)
    cache_written = bool(cache_written) and status_has_fresh_runtime_cache(status)
    cache_reused = cache_available and not cache_written
    if cache_written:
        cache_write_status = "written_this_run"
    elif cache_available:
        cache_write_status = "available_from_cache"
    else:
        cache_write_status = "not_available"
    return {
        "provider_id": provider_id,
        "label": label,
        "state": state,
        "source": str(status.get("source") or provider_id),
        "retrieved_at": str(status.get("last_update") or ""),
        "message": str(status.get("message") or "No provider status message returned."),
        "cache_path": str(status.get("cache_path") or cache_path),
        "cache_written": cache_written,
        "cache_written_this_run": cache_written,
        "cache_available": cache_available,
        "cache_reused": cache_reused,
        "cache_write_status": cache_write_status,
        "source_errors": [_safe_error_message(error) for error in source_errors[:5]],
        "usable_runtime": cache_available,
    }


def status_has_runtime_cache(status: Any) -> bool:
    if not isinstance(status, dict):
        return False
    return str(status.get("state") or "") in runtime_cache_states()


def status_has_fresh_runtime_cache(status: Any) -> bool:
    if not isinstance(status, dict):
        return False
    return str(status.get("state") or "") in {"live", "partial"}


def runtime_cache_states() -> set[str]:
    return {"live", "partial", "stale", "stale_cache"}


def research_cache_status(
    research: Any,
    *,
    cache_key: str,
    provider_id: str,
    fallback_status: Any = None,
) -> dict[str, Any]:
    cache = research.get("cache") if isinstance(research, dict) else {}
    payload = cache.get(cache_key) if isinstance(cache, dict) else {}
    status = payload.get("status") if isinstance(payload, dict) else {}
    if isinstance(status, dict) and status:
        return status
    if isinstance(fallback_status, dict) and fallback_status.get("provider_id") == provider_id:
        return fallback_status
    return {
        "source": provider_id,
        "state": "unavailable",
        "last_update": "",
        "message": f"{provider_id} did not return provider-specific refresh status.",
        "provider_id": provider_id,
    }


def _news_provider_status(news: dict[str, Any], provider_id: str) -> dict[str, Any] | None:
    intel = news.get("intel") if isinstance(news, dict) else {}
    provider_states = intel.get("provider_states") if isinstance(intel, dict) else []
    if not isinstance(provider_states, list):
        return None
    news_status = news.get("status") if isinstance(news.get("status"), dict) else {}
    for provider in provider_states:
        if not isinstance(provider, dict) or provider.get("provider_id") != provider_id:
            continue
        state = str(provider.get("state") or "unavailable")
        return {
            "source": provider_id,
            "state": state,
            "last_update": news_status.get("last_update") or "",
            "message": provider.get("message") or "No provider status message returned.",
            "cache_path": provider.get("cache_path") or "artifacts/news/news_cache.json",
            "source_errors": [provider.get("message")] if provider.get("failed") else [],
        }
    return None


def provider_refresh_summary(results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "result_count": len(results),
        "provider_count": len({result["provider_id"] for result in results}),
        "refreshed": sum(1 for result in results if result["state"] in {"live", "partial"}),
        "stale_or_cached": sum(1 for result in results if result["state"] in {"stale", "stale_cache"}),
        "unavailable": sum(1 for result in results if result["usable_runtime"] is False),
        "cache_written": sum(1 for result in results if result["cache_written"]),
        "cache_written_this_run": sum(
            1 for result in results if result.get("cache_written_this_run") is True
        ),
        "cache_available": sum(1 for result in results if result.get("cache_available") is True),
        "cache_reused": sum(1 for result in results if result.get("cache_reused") is True),
        "source_error_count": sum(len(result["source_errors"]) for result in results),
    }


def write_provider_refresh_artifacts(
    store: LocalStateStore,
    run_id: str,
    manifest: dict[str, Any],
    provider_state: dict[str, Any],
) -> None:
    _validate_run_id(run_id)
    artifact_dir = _artifact_dir(store, run_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifact_dir / "manifest.json", manifest)
    _write_json(artifact_dir / "results.json", manifest["results"])
    _write_json(artifact_dir / "providers_after.json", provider_state)
    (artifact_dir / "report.md").write_text(_provider_refresh_report(manifest), encoding="utf-8")
    (artifact_dir / "error.log").write_text(_provider_refresh_error_log(manifest), encoding="utf-8")


def _job_payload(
    run_id: str,
    *,
    status: str,
    created_at: str,
    started_at: str,
    completed_at: str,
    message: str,
    summary: dict[str, Any] | None = None,
    last_refresh: dict[str, Any] | None = None,
    provider_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact_dir = f"artifacts/diagnostics/{run_id}"
    payload: dict[str, Any] = {
        "run_id": run_id,
        "status": status,
        "mode": REFRESH_MODE,
        "created_at": created_at,
        "started_at": started_at,
        "completed_at": completed_at,
        "message": message,
        "artifact_dir": artifact_dir,
        "poll_after_seconds": 1,
        "summary": summary or {
            "result_count": 0,
            "provider_count": 0,
            "refreshed": 0,
            "stale_or_cached": 0,
            "unavailable": 0,
            "cache_written": 0,
            "cache_written_this_run": 0,
            "cache_available": 0,
            "cache_reused": 0,
            "source_error_count": 0,
        },
        "safety": _safety_payload(),
        "artifacts": {
            "job_status": f"{artifact_dir}/{JOB_STATUS_FILE}",
            "manifest": f"{artifact_dir}/manifest.json",
            "error_log": f"{artifact_dir}/error.log",
        },
    }
    if last_refresh is not None:
        payload["last_refresh"] = last_refresh
    if provider_payload is not None:
        payload["provider_payload"] = provider_payload
    return payload


def _failed_job_payload(run_id: str, created_at: str, started_at: str, exc: Exception) -> dict[str, Any]:
    completed_at = _utc_now()
    payload = _job_payload(
        run_id,
        status="failed",
        created_at=created_at,
        started_at=started_at,
        completed_at=completed_at,
        message=f"Public no-key provider refresh failed: {exc.__class__.__name__}.",
        summary={
            "result_count": 0,
            "provider_count": 0,
            "refreshed": 0,
            "stale_or_cached": 0,
            "unavailable": 1,
            "cache_written": 0,
            "cache_written_this_run": 0,
            "cache_available": 0,
            "cache_reused": 0,
            "source_error_count": 1,
        },
    )
    payload["error"] = {
        "type": exc.__class__.__name__,
        "message": _safe_error_message(exc),
    }
    return payload


def _safety_payload() -> dict[str, bool]:
    return {
        "public_no_key_only": True,
        "optional_key_providers_refreshed": False,
        "private_api_key_flow": False,
        "secret_reads_enabled": False,
        "secret_writes_enabled": False,
        "live_execution_reachable": False,
        "real_order_path": False,
        "real_balance_read": False,
        "installed_source_read": False,
    }


def _read_job_status(store: LocalStateStore, run_id: str) -> dict[str, Any]:
    path = _artifact_dir(store, run_id) / JOB_STATUS_FILE
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _write_job_status(store: LocalStateStore, run_id: str, payload: dict[str, Any]) -> None:
    _validate_run_id(run_id)
    artifact_dir = _artifact_dir(store, run_id)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _write_json(artifact_dir / JOB_STATUS_FILE, payload)


def _read_manifest(store: LocalStateStore, run_id: str) -> dict[str, Any]:
    path = _artifact_dir(store, run_id) / "manifest.json"
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _provider_refresh_lifecycle_row(path: Path, *, now: datetime) -> dict[str, Any]:
    run_id = path.name
    job_status, job_corrupt = _read_json_document(path / JOB_STATUS_FILE)
    manifest, manifest_corrupt = _read_json_document(path / "manifest.json")
    status = _refresh_lifecycle_status(job_status, manifest, job_corrupt=job_corrupt)
    timestamp = _refresh_lifecycle_timestamp(path, job_status, manifest, now=now)
    age_seconds = max(0, int((now - timestamp).total_seconds())) if timestamp else 0
    stale_after = _stale_after_seconds(status)
    stale_interrupted = bool(stale_after and age_seconds > stale_after)
    lifecycle_state = _refresh_lifecycle_state(
        status,
        stale_interrupted=stale_interrupted,
        job_present=bool(job_status),
        manifest_present=bool(manifest),
        job_corrupt=job_corrupt,
        manifest_corrupt=manifest_corrupt,
    )
    return {
        "run_id": run_id,
        "artifact_dir": f"artifacts/diagnostics/{run_id}",
        "status": status,
        "lifecycle_state": lifecycle_state,
        "created_at": str(job_status.get("created_at") or manifest.get("started_at") or ""),
        "started_at": str(job_status.get("started_at") or manifest.get("started_at") or ""),
        "completed_at": str(job_status.get("completed_at") or manifest.get("completed_at") or ""),
        "updated_at": _mtime_to_utc(_safe_mtime(path)),
        "age_seconds": age_seconds,
        "stale_after_seconds": stale_after or 0,
        "stale_interrupted": stale_interrupted,
        "job_status_present": bool(job_status),
        "manifest_present": bool(manifest),
        "job_status_corrupt": job_corrupt,
        "manifest_corrupt": manifest_corrupt,
        "summary": _refresh_lifecycle_summary(job_status, manifest),
        "artifacts": _refresh_lifecycle_artifacts(run_id, path, job_status, manifest),
        "recovery": _refresh_lifecycle_recovery(lifecycle_state),
        "safety": {
            "read_only": True,
            "job_status_write_enabled": False,
            "destructive_cleanup_enabled": False,
            "external_network": False,
            "secret_values_returned": False,
            "live_trading": False,
        },
    }


def _read_json_document(path: Path) -> tuple[dict[str, Any], bool]:
    if not path.exists():
        return {}, False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, True
    return (value, False) if isinstance(value, dict) else ({}, True)


def _refresh_lifecycle_status(
    job_status: dict[str, Any],
    manifest: dict[str, Any],
    *,
    job_corrupt: bool,
) -> str:
    if job_corrupt:
        return "unknown"
    status = str(job_status.get("status") or "")
    if status in {"queued", "running", "completed", "failed"}:
        return status
    if manifest:
        return "completed"
    return "unknown"


def _refresh_lifecycle_timestamp(
    path: Path,
    job_status: dict[str, Any],
    manifest: dict[str, Any],
    *,
    now: datetime,
) -> datetime | None:
    for key in ("completed_at", "started_at", "created_at"):
        parsed = _parse_utc_timestamp(job_status.get(key))
        if parsed:
            return parsed
    for key in ("completed_at", "started_at"):
        parsed = _parse_utc_timestamp(manifest.get(key))
        if parsed:
            return parsed
    mtime = _safe_mtime(path)
    if mtime > 0:
        return datetime.fromtimestamp(mtime, UTC)
    return now


def _parse_utc_timestamp(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def _mtime_to_utc(value: float) -> str:
    if value <= 0:
        return ""
    return datetime.fromtimestamp(value, UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def _stale_after_seconds(status: str) -> int | None:
    if status == "queued":
        return QUEUED_STALE_AFTER_SECONDS
    if status == "running":
        return RUNNING_STALE_AFTER_SECONDS
    return None


def _refresh_lifecycle_state(
    status: str,
    *,
    stale_interrupted: bool,
    job_present: bool,
    manifest_present: bool,
    job_corrupt: bool,
    manifest_corrupt: bool,
) -> str:
    if job_corrupt or manifest_corrupt:
        return "corrupt_status_metadata"
    if status == "queued":
        return "stale_interrupted_queued" if stale_interrupted else "queued"
    if status == "running":
        return "stale_interrupted_running" if stale_interrupted else "running"
    if status == "failed":
        return "failed_retry_available"
    if status == "completed":
        if manifest_present and not job_present:
            return "manifest_only_completed"
        return "completed"
    if manifest_present:
        return "manifest_only_completed"
    return "unknown_artifact_state"


def _refresh_lifecycle_summary(
    job_status: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, int]:
    summary = job_status.get("summary")
    if not isinstance(summary, dict):
        summary = manifest.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    return {
        "result_count": _int(summary.get("result_count")),
        "provider_count": _int(summary.get("provider_count")),
        "refreshed": _int(summary.get("refreshed")),
        "stale_or_cached": _int(summary.get("stale_or_cached")),
        "unavailable": _int(summary.get("unavailable")),
        "cache_written": _int(summary.get("cache_written")),
        "cache_written_this_run": _int(
            summary.get("cache_written_this_run", summary.get("cache_written"))
        ),
        "cache_available": _int(summary.get("cache_available")),
        "cache_reused": _int(summary.get("cache_reused")),
        "source_error_count": _int(summary.get("source_error_count")),
    }


def _refresh_lifecycle_artifacts(
    run_id: str,
    path: Path,
    job_status: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, str]:
    del job_status, manifest
    artifacts: dict[str, str] = {}
    for name in ("job_status", "manifest", "results", "providers_after", "report", "error_log"):
        file_name = JOB_STATUS_FILE if name == "job_status" else f"{name}.json"
        if name == "report":
            file_name = "report.md"
        if name == "error_log":
            file_name = "error.log"
        if (path / file_name).exists() and name not in artifacts:
            artifacts[name] = f"artifacts/diagnostics/{run_id}/{file_name}"
    return artifacts


def _refresh_lifecycle_recovery(lifecycle_state: str) -> dict[str, Any]:
    if lifecycle_state in {"queued", "running"}:
        action = "wait_and_poll_job_status"
        message = "Job is still within the bounded poll window."
    elif lifecycle_state.startswith("stale_interrupted"):
        action = "start_new_manual_refresh_job"
        message = "Previous job is stale; leave artifacts intact and start a new manual refresh."
    elif lifecycle_state == "failed_retry_available":
        action = "inspect_error_log_then_start_new_manual_refresh_job"
        message = "Read the sanitized error log and retry with a new manual public refresh."
    elif lifecycle_state == "manifest_only_completed":
        action = "treat_manifest_as_completed_history"
        message = "Historical refresh has a manifest; no status rewrite is performed."
    elif lifecycle_state == "corrupt_status_metadata":
        action = "inspect_artifact_directory_manually"
        message = "Lifecycle metadata is corrupt; no automatic repair or deletion is performed."
    else:
        action = "inspect_artifact_directory_manually"
        message = "No automatic recovery action is enabled for this state."
    return {
        "recommended_action": action,
        "message": message,
        "read_endpoint": "/api/providers/refresh-public/lifecycle",
        "mutation_required": False,
        "destructive_cleanup_enabled": False,
    }


def _public_refresh_schedule_eligible(provider: Any) -> bool:
    if not isinstance(provider, dict):
        return False
    provider_id = str(provider.get("provider_id") or "")
    if provider_id not in PUBLIC_REFRESH_SCHEDULE_PROVIDER_IDS:
        return False
    auth_mode = str(provider.get("auth_mode") or "").lower()
    if "no-key" not in auth_mode or "optional" in auth_mode or "paid" in auth_mode:
        return False
    safety_class = str(provider.get("safety_class") or "").lower()
    return "live" not in safety_class and "private" not in safety_class


def _provider_refresh_schedule_row(provider: dict[str, Any]) -> dict[str, Any]:
    health = provider.get("health")
    health = health if isinstance(health, dict) else {}
    state = str(health.get("state") or "unavailable")
    age_seconds = _optional_int(health.get("age_seconds"))
    ttl_seconds = _optional_int(health.get("stale_after_seconds")) or 0
    due, seconds_until_due, due_reason = _provider_refresh_due_state(
        state,
        age_seconds=age_seconds,
        ttl_seconds=ttl_seconds,
    )
    return {
        "provider_id": str(provider.get("provider_id") or ""),
        "label": str(provider.get("label") or ""),
        "cache_id": str(health.get("cache_id") or ""),
        "cache_path": str(health.get("cache_path") or ""),
        "state": state,
        "retrieved_at": str(health.get("retrieved_at") or ""),
        "age_seconds": age_seconds,
        "ttl_seconds": ttl_seconds,
        "seconds_until_due": seconds_until_due,
        "due": due,
        "due_reason": due_reason,
        "safe_action_id": "provider_refresh_public_start",
        "manual_refresh_endpoint": "/api/providers/refresh-public/jobs",
        "auth_mode": str(provider.get("auth_mode") or ""),
        "safety_class": str(provider.get("safety_class") or ""),
        "message": str(health.get("message") or ""),
    }


def _provider_refresh_due_state(
    state: str,
    *,
    age_seconds: int | None,
    ttl_seconds: int,
) -> tuple[bool, int | None, str]:
    if state == "active":
        if age_seconds is None:
            return True, 0, "active_cache_timestamp_missing"
        seconds_until_due = max(0, ttl_seconds - age_seconds)
        if seconds_until_due == 0:
            return True, 0, "ttl_due"
        return False, seconds_until_due, "fresh_within_ttl"
    if state == "stale_cache":
        return True, 0, "stale_cache"
    if state == "unavailable":
        return True, 0, "missing_cache"
    if state == "rate_limited":
        return False, None, "rate_limited_backoff"
    return False, None, f"{state}_not_scheduled"


def _optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _write_failure_log(store: LocalStateStore, run_id: str, payload: dict[str, Any]) -> None:
    error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
    line = (
        f"{payload['completed_at']} provider_refresh_job failed "
        f"{error.get('type', 'Error')} {error.get('message', '')}\n"
    )
    (_artifact_dir(store, run_id) / "error.log").write_text(line, encoding="utf-8")


def _provider_refresh_report(manifest: dict[str, Any]) -> str:
    rows = [
        (
            f"- {result['provider_id']}: {result['state']} / "
            f"{result.get('cache_write_status', 'unknown_cache_status')} / {result['message']}"
        )
        for result in manifest["results"]
    ]
    return "\n".join(
        [
            "# Public Provider Refresh",
            "",
            f"- Run: `{manifest['run_id']}`",
            f"- Output mode: `{manifest['output_mode']}`",
            f"- Refresh mode: `{manifest['refresh_mode']}`",
            f"- Completed: `{manifest['completed_at']}`",
            f"- Refreshed: `{manifest['summary']['refreshed']}`",
            f"- Unavailable: `{manifest['summary']['unavailable']}`",
            f"- Cache written this run: `{manifest['summary'].get('cache_written_this_run', manifest['summary'].get('cache_written', 0))}`",
            f"- Cache available: `{manifest['summary'].get('cache_available', 0)}`",
            f"- Cache reused: `{manifest['summary'].get('cache_reused', 0)}`",
            "",
            "## Results",
            "",
            *rows,
            "",
            "## Safety",
            "",
            "- Public no-key provider refresh only.",
            "- Optional-key providers, private API flows, live execution, real orders, and real balances remain disabled.",
        ]
    )


def _provider_refresh_error_log(manifest: dict[str, Any]) -> str:
    lines: list[str] = []
    for result in manifest["results"]:
        if result["usable_runtime"] is False:
            lines.append(
                f"{manifest['completed_at']} {result['provider_id']} {result['state']} {result['message']}"
            )
        for error in result["source_errors"]:
            lines.append(f"{manifest['completed_at']} {result['provider_id']} source_error {error}")
    return "\n".join(lines) + ("\n" if lines else "")


def _safe_error_message(raw: object) -> str:
    text = str(raw or raw.__class__.__name__)[:240]
    text = re.sub(r"(?i)(api[_-]?key|token|secret|password)=([^&\s]+)", r"\1=<redacted>", text)
    return text


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_dir(store: LocalStateStore, run_id: str) -> Path:
    _validate_run_id(run_id)
    return store.diagnostics_root_path / run_id


def _validate_run_id(run_id: str) -> None:
    if not RUN_ID_PATTERN.match(run_id):
        raise ValueError("Provider refresh run id is invalid")


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _int(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(number, 0)
