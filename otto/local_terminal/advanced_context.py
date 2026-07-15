"""Read-only provider cache and local artifact context for advanced routes."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


MAX_CONTEXT_SOURCES = 12
MAX_CONTEXT_ARTIFACTS = 20
ARTIFACT_GLOBS: tuple[tuple[str, str], ...] = (
    ("backtest", "artifacts/backtests/**/*"),
    ("portfolio", "artifacts/portfolio/**/*"),
    ("paper", "artifacts/paper/**/*"),
    ("news", "artifacts/news/**/*"),
    ("nodes", "artifacts/workflows/**/*"),
    ("code", "artifacts/code_workspace/**/*"),
    ("quant_lab", "artifacts/quant_lab/**/*"),
    ("quantlib", "artifacts/quantlib/**/*"),
)
ARTIFACT_SUFFIXES = {".csv", ".json", ".jsonl", ".md", ".ipynb", ".txt"}


def empty_advanced_context() -> dict[str, Any]:
    return {
        "summary": {
            "source_count": 0,
            "ready_source_count": 0,
            "artifact_count": 0,
            "latest_price": "",
            "price_series": "",
            "primary_cache_path": "",
        },
        "sources": [],
        "artifacts": [],
        "safety": {
            "read_only": True,
            "external_network": False,
            "broker_mutation": False,
            "credential_material": False,
        },
    }


def advanced_context_payload(
    root: Path,
    *,
    market_cache: dict[str, Any] | None = None,
    crypto_detail_cache: dict[str, Any] | None = None,
    news_cache: dict[str, Any] | None = None,
    research_data: dict[str, Any] | None = None,
    rates_data: dict[str, Any] | None = None,
    fx_data: dict[str, Any] | None = None,
    commodity_data: dict[str, Any] | None = None,
    fund_data: dict[str, Any] | None = None,
    equity_quote_data: dict[str, Any] | None = None,
    etf_quote_data: dict[str, Any] | None = None,
    fx_quote_data: dict[str, Any] | None = None,
    twelve_data_quote_data: dict[str, Any] | None = None,
    finnhub_quote_data: dict[str, Any] | None = None,
    fmp_quote_data: dict[str, Any] | None = None,
    stooq_quote_data: dict[str, Any] | None = None,
    nasdaq_symbol_data: dict[str, Any] | None = None,
    moex_quote_data: dict[str, Any] | None = None,
    twse_quote_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    market_cache = market_cache if isinstance(market_cache, dict) else {}
    crypto_detail_cache = crypto_detail_cache if isinstance(crypto_detail_cache, dict) else {}
    news_cache = news_cache if isinstance(news_cache, dict) else {}
    research_data = research_data if isinstance(research_data, dict) else {}
    rates_data = rates_data if isinstance(rates_data, dict) else {}
    fx_data = fx_data if isinstance(fx_data, dict) else {}
    commodity_data = commodity_data if isinstance(commodity_data, dict) else {}
    fund_data = fund_data if isinstance(fund_data, dict) else {}
    equity_quote_data = equity_quote_data if isinstance(equity_quote_data, dict) else {}
    etf_quote_data = etf_quote_data if isinstance(etf_quote_data, dict) else {}
    fx_quote_data = fx_quote_data if isinstance(fx_quote_data, dict) else {}
    twelve_data_quote_data = (
        twelve_data_quote_data if isinstance(twelve_data_quote_data, dict) else {}
    )
    finnhub_quote_data = finnhub_quote_data if isinstance(finnhub_quote_data, dict) else {}
    fmp_quote_data = fmp_quote_data if isinstance(fmp_quote_data, dict) else {}
    stooq_quote_data = stooq_quote_data if isinstance(stooq_quote_data, dict) else {}
    nasdaq_symbol_data = nasdaq_symbol_data if isinstance(nasdaq_symbol_data, dict) else {}
    moex_quote_data = moex_quote_data if isinstance(moex_quote_data, dict) else {}
    twse_quote_data = twse_quote_data if isinstance(twse_quote_data, dict) else {}

    market_status = market_cache.get("status") if isinstance(market_cache.get("status"), dict) else {}
    market_rows = market_cache.get("rows") if isinstance(market_cache.get("rows"), list) else []
    if market_status or market_rows:
        sources.append(
            _source(
                "market_ticker_cache",
                "Crypto ticker cache",
                "provider_cache",
                market_status,
                record_count=len(market_rows),
                cache_path="market_data/crypto_latest.json",
                detail="Public crypto ticker rows for Markets/Crypto/Portfolio context.",
            )
        )

    detail_status = (
        crypto_detail_cache.get("status")
        if isinstance(crypto_detail_cache.get("status"), dict)
        else {}
    )
    candles = (
        crypto_detail_cache.get("candles")
        if isinstance(crypto_detail_cache.get("candles"), list)
        else []
    )
    if detail_status or candles:
        sources.append(
            _source(
                "crypto_detail_cache",
                "Crypto detail cache",
                "provider_cache",
                detail_status,
                record_count=len(candles),
                cache_path=_crypto_detail_path(detail_status),
                detail="Depth, trades, and closed candles for local analytics context.",
            )
        )

    news_items = news_cache.get("items") if isinstance(news_cache.get("items"), list) else []
    if news_items or news_cache.get("fetched_at"):
        sources.append(
            _source(
                "news_cache",
                "News cache",
                "local_artifact",
                {
                    "state": "cache_ready" if news_items else "cache_missing",
                    "source": "public_rss",
                    "last_update": news_cache.get("fetched_at"),
                },
                record_count=len(news_items),
                cache_path="artifacts/news/news_cache.json",
                detail="Source-attributed headline metadata cache.",
            )
        )

    fundamentals = (
        research_data.get("fundamentals")
        if isinstance(research_data.get("fundamentals"), dict)
        else {}
    )
    fundamentals_status = (
        fundamentals.get("status") if isinstance(fundamentals.get("status"), dict) else {}
    )
    companies = fundamentals.get("companies") if isinstance(fundamentals.get("companies"), list) else []
    if fundamentals_status or companies:
        sources.append(
            _source(
                "sec_fundamentals",
                "SEC fundamentals",
                "provider_cache",
                fundamentals_status,
                record_count=sum(
                    len(company.get("facts", []))
                    for company in companies
                    if isinstance(company, dict)
                ),
                cache_path=str(fundamentals_status.get("cache_path") or ""),
                detail="Public no-key company facts for research context.",
            )
        )

    equity_registry = (
        research_data.get("equity_registry")
        if isinstance(research_data.get("equity_registry"), dict)
        else {}
    )
    equity_registry_status = (
        equity_registry.get("status") if isinstance(equity_registry.get("status"), dict) else {}
    )
    equity_registry_rows = (
        equity_registry.get("rows") if isinstance(equity_registry.get("rows"), list) else []
    )
    if equity_registry_status or equity_registry_rows:
        sources.append(
            _source(
                "sec_company_ticker_registry",
                "SEC company ticker registry",
                "provider_cache",
                equity_registry_status,
                record_count=len(equity_registry_rows),
                cache_path=str(equity_registry_status.get("cache_path") or ""),
                detail="Public no-key issuer ticker/CIK reference rows for stock context.",
            )
        )

    quote_status = (
        equity_quote_data.get("status")
        if isinstance(equity_quote_data.get("status"), dict)
        else {}
    )
    quote_rows = (
        equity_quote_data.get("quotes")
        if isinstance(equity_quote_data.get("quotes"), list)
        else []
    )
    if quote_status or quote_rows:
        sources.append(
            _source(
                "alphavantage_equity_quote",
                "Alpha Vantage equity quote",
                "provider_cache",
                quote_status,
                record_count=len(quote_rows),
                cache_path=str(quote_status.get("cache_path") or ""),
                detail="Optional-key local equity quote cache for stock market context.",
            )
        )

    etf_quote_status = (
        etf_quote_data.get("status")
        if isinstance(etf_quote_data.get("status"), dict)
        else {}
    )
    etf_quote_rows = (
        etf_quote_data.get("quotes")
        if isinstance(etf_quote_data.get("quotes"), list)
        else []
    )
    if etf_quote_status or etf_quote_rows:
        sources.append(
            _source(
                "alphavantage_etf_quote",
                "Alpha Vantage ETF quote",
                "provider_cache",
                etf_quote_status,
                record_count=len(etf_quote_rows),
                cache_path=str(etf_quote_status.get("cache_path") or ""),
                detail="Optional-key local ETF quote cache for ETF market context.",
            )
        )

    fx_quote_status = (
        fx_quote_data.get("status")
        if isinstance(fx_quote_data.get("status"), dict)
        else {}
    )
    fx_quote_rows = (
        fx_quote_data.get("quotes")
        if isinstance(fx_quote_data.get("quotes"), list)
        else []
    )
    if fx_quote_status or fx_quote_rows:
        sources.append(
            _source(
                "alphavantage_fx_quote",
                "Alpha Vantage FX quote",
                "provider_cache",
                fx_quote_status,
                record_count=len(fx_quote_rows),
                cache_path=str(fx_quote_status.get("cache_path") or ""),
                detail="Optional-key local FX quote cache for non-orderable market context.",
            )
        )

    twelve_quote_status = (
        twelve_data_quote_data.get("status")
        if isinstance(twelve_data_quote_data.get("status"), dict)
        else {}
    )
    twelve_quote_rows = (
        twelve_data_quote_data.get("quotes")
        if isinstance(twelve_data_quote_data.get("quotes"), list)
        else []
    )
    if twelve_quote_status or twelve_quote_rows:
        sources.append(
            _source(
                "twelve_data_quote",
                "Twelve Data quote",
                "provider_cache",
                twelve_quote_status,
                record_count=len(twelve_quote_rows),
                cache_path=str(twelve_quote_status.get("cache_path") or ""),
                detail="Optional-key local multi-asset quote cache for non-orderable market context.",
            )
        )

    finnhub_quote_status = (
        finnhub_quote_data.get("status")
        if isinstance(finnhub_quote_data.get("status"), dict)
        else {}
    )
    finnhub_quote_rows = (
        finnhub_quote_data.get("quotes")
        if isinstance(finnhub_quote_data.get("quotes"), list)
        else []
    )
    if finnhub_quote_status or finnhub_quote_rows:
        sources.append(
            _source(
                "finnhub_equity_quote",
                "Finnhub equity quote",
                "provider_cache",
                finnhub_quote_status,
                record_count=len(finnhub_quote_rows),
                cache_path=str(finnhub_quote_status.get("cache_path") or ""),
                detail="Optional-key local equity/ETF quote cache for non-orderable market context.",
            )
        )

    fmp_quote_status = (
        fmp_quote_data.get("status") if isinstance(fmp_quote_data.get("status"), dict) else {}
    )
    fmp_quote_rows = (
        fmp_quote_data.get("quotes") if isinstance(fmp_quote_data.get("quotes"), list) else []
    )
    if fmp_quote_status or fmp_quote_rows:
        sources.append(
            _source(
                "fmp_stock_quote",
                "FMP stock quote",
                "provider_cache",
                fmp_quote_status,
                record_count=len(fmp_quote_rows),
                cache_path=str(fmp_quote_status.get("cache_path") or ""),
                detail="Optional-key local stock quote cache for non-orderable market context.",
            )
        )

    stooq_status = (
        stooq_quote_data.get("status")
        if isinstance(stooq_quote_data.get("status"), dict)
        else {}
    )
    stooq_rows = (
        stooq_quote_data.get("quotes")
        if isinstance(stooq_quote_data.get("quotes"), list)
        else []
    )
    if stooq_status or stooq_rows:
        sources.append(
            _source(
                "stooq_quote_snapshot",
                "Stooq quote snapshot",
                "provider_cache",
                stooq_status,
                record_count=len(stooq_rows),
                cache_path=str(stooq_status.get("cache_path") or ""),
                detail="Public no-key delayed quote snapshots; non-orderable market context only.",
            )
        )

    nasdaq_status = (
        nasdaq_symbol_data.get("status")
        if isinstance(nasdaq_symbol_data.get("status"), dict)
        else {}
    )
    nasdaq_rows = (
        nasdaq_symbol_data.get("symbols")
        if isinstance(nasdaq_symbol_data.get("symbols"), list)
        else []
    )
    if nasdaq_status or nasdaq_rows:
        sources.append(
            _source(
                "nasdaq_trader_symbol_directory",
                "Nasdaq Trader symbol directory",
                "provider_cache",
                nasdaq_status,
                record_count=len(nasdaq_rows),
                cache_path=str(nasdaq_status.get("cache_path") or ""),
                detail="Public no-key symbol reference rows; not quote or executable market data.",
            )
        )

    moex_status = (
        moex_quote_data.get("status")
        if isinstance(moex_quote_data.get("status"), dict)
        else {}
    )
    moex_rows = (
        moex_quote_data.get("quotes")
        if isinstance(moex_quote_data.get("quotes"), list)
        else []
    )
    if moex_status or moex_rows:
        sources.append(
            _source(
                "moex_iss_delayed_quote_snapshot",
                "MOEX ISS delayed quote snapshot",
                "provider_cache",
                moex_status,
                record_count=len(moex_rows),
                cache_path=str(moex_status.get("cache_path") or ""),
                detail="Public no-key delayed quote snapshots; non-orderable market context only.",
            )
        )

    twse_status = (
        twse_quote_data.get("status")
        if isinstance(twse_quote_data.get("status"), dict)
        else {}
    )
    twse_rows = (
        twse_quote_data.get("quotes")
        if isinstance(twse_quote_data.get("quotes"), list)
        else []
    )
    if twse_status or twse_rows:
        sources.append(
            _source(
                "twse_openapi_daily_quote_snapshot",
                "TWSE OpenAPI daily quote snapshot",
                "provider_cache",
                twse_status,
                record_count=len(twse_rows),
                cache_path=str(twse_status.get("cache_path") or ""),
                detail="Public no-key daily quote snapshots; non-orderable market context only.",
            )
        )

    macro = research_data.get("macro") if isinstance(research_data.get("macro"), dict) else {}
    macro_status = macro.get("status") if isinstance(macro.get("status"), dict) else {}
    series = macro.get("series") if isinstance(macro.get("series"), list) else []
    if macro_status or series:
        sources.append(
            _source(
                "macro_series",
                "Macro series cache",
                "provider_cache",
                macro_status,
                record_count=len(series),
                cache_path=str(macro_status.get("cache_path") or ""),
                detail="Source-attributed macro series for research context.",
            )
        )

    treasury = rates_data.get("treasury") if isinstance(rates_data.get("treasury"), dict) else {}
    treasury_status = treasury.get("status") if isinstance(treasury.get("status"), dict) else {}
    latest_curve = treasury.get("latest") if isinstance(treasury.get("latest"), dict) else {}
    tenors = latest_curve.get("tenors") if isinstance(latest_curve.get("tenors"), list) else []
    if treasury_status or tenors:
        sources.append(
            _source(
                "treasury_yield_curve",
                "Treasury yield curve",
                "provider_cache",
                treasury_status,
                record_count=len(tenors),
                cache_path=str(treasury_status.get("cache_path") or ""),
                detail="Public no-key Treasury rates for local rates and macro context.",
            )
        )

    ecb_fx = fx_data.get("ecb") if isinstance(fx_data.get("ecb"), dict) else {}
    ecb_fx_status = ecb_fx.get("status") if isinstance(ecb_fx.get("status"), dict) else {}
    fx_rows = ecb_fx.get("rows") if isinstance(ecb_fx.get("rows"), list) else []
    if ecb_fx_status or fx_rows:
        sources.append(
            _source(
                "ecb_fx_reference",
                "ECB FX reference rates",
                "provider_cache",
                ecb_fx_status,
                record_count=len(fx_rows),
                cache_path=str(ecb_fx_status.get("cache_path") or ""),
                detail="Public no-key EUR-base FX reference rates for local markets context.",
            )
        )

    world_bank = (
        commodity_data.get("world_bank")
        if isinstance(commodity_data.get("world_bank"), dict)
        else {}
    )
    commodity_status = (
        world_bank.get("status") if isinstance(world_bank.get("status"), dict) else {}
    )
    commodity_rows = world_bank.get("rows") if isinstance(world_bank.get("rows"), list) else []
    if commodity_status or commodity_rows:
        sources.append(
            _source(
                "world_bank_commodities",
                "World Bank monthly commodities",
                "provider_cache",
                commodity_status,
                record_count=len(commodity_rows),
                cache_path=str(commodity_status.get("cache_path") or ""),
                detail="Public no-key monthly commodity reference prices for local markets context.",
            )
        )
    eia_energy = (
        commodity_data.get("eia")
        if isinstance(commodity_data.get("eia"), dict)
        else {}
    )
    eia_status = eia_energy.get("status") if isinstance(eia_energy.get("status"), dict) else {}
    eia_series = eia_energy.get("series") if isinstance(eia_energy.get("series"), list) else []
    if eia_status or eia_series:
        sources.append(
            _source(
                "eia_energy_context",
                "EIA energy context",
                "provider_cache",
                eia_status,
                record_count=len(eia_series),
                cache_path=str(eia_status.get("cache_path") or ""),
                detail="Optional local-key EIA WTI, Brent, and Henry Hub context series.",
            )
        )

    sec_funds = (
        fund_data.get("sec_funds")
        if isinstance(fund_data.get("sec_funds"), dict)
        else {}
    )
    fund_status = sec_funds.get("status") if isinstance(sec_funds.get("status"), dict) else {}
    fund_rows = sec_funds.get("rows") if isinstance(sec_funds.get("rows"), list) else []
    if fund_status or fund_rows:
        sources.append(
            _source(
                "sec_fund_ticker_registry",
                "SEC fund ticker registry",
                "provider_cache",
                fund_status,
                record_count=len(fund_rows),
                cache_path=str(fund_status.get("cache_path") or ""),
                detail="Public no-key fund series/class identifiers for local ETF context.",
            )
        )

    latest_price = _latest_price(market_rows, candles)
    price_series = _price_series(candles)
    artifacts = _artifact_index(root)
    safe_sources = [sanitize_context_source(source) for source in sources[:MAX_CONTEXT_SOURCES]]
    return {
        "summary": {
            "source_count": len(safe_sources),
            "ready_source_count": sum(
                1 for source in safe_sources if source["state"] not in {"unavailable", "cache_missing"}
            ),
            "artifact_count": len(artifacts),
            "latest_price": latest_price,
            "price_series": price_series,
            "primary_cache_path": _first_cache_path(safe_sources),
        },
        "sources": safe_sources,
        "artifacts": artifacts,
        "safety": empty_advanced_context()["safety"],
    }


def sanitize_advanced_context(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return empty_advanced_context()
    sources = raw.get("sources") if isinstance(raw.get("sources"), list) else []
    artifacts = raw.get("artifacts") if isinstance(raw.get("artifacts"), list) else []
    summary = raw.get("summary") if isinstance(raw.get("summary"), dict) else {}
    return {
        "summary": {
            "source_count": _non_negative_int(summary.get("source_count")),
            "ready_source_count": _non_negative_int(summary.get("ready_source_count")),
            "artifact_count": _non_negative_int(summary.get("artifact_count")),
            "latest_price": _safe_text(summary.get("latest_price"), 40),
            "price_series": _safe_text(summary.get("price_series"), 600),
            "primary_cache_path": _safe_path_text(summary.get("primary_cache_path")),
        },
        "sources": [sanitize_context_source(source) for source in sources[:MAX_CONTEXT_SOURCES]],
        "artifacts": [
            sanitize_context_artifact(artifact)
            for artifact in artifacts[:MAX_CONTEXT_ARTIFACTS]
        ],
        "safety": empty_advanced_context()["safety"],
    }


def sanitize_context_source(raw: Any) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "source_id": _safe_text(raw.get("source_id"), 80),
        "label": _safe_text(raw.get("label"), 80),
        "kind": _safe_text(raw.get("kind"), 40),
        "state": _safe_text(raw.get("state"), 40),
        "provider_id": _safe_text(raw.get("provider_id"), 80),
        "cache_path": _safe_path_text(raw.get("cache_path")),
        "record_count": _non_negative_int(raw.get("record_count")),
        "updated_at": _safe_text(raw.get("updated_at"), 80),
        "detail": _safe_text(raw.get("detail"), 180),
    }


def sanitize_context_artifact(raw: Any) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    return {
        "artifact_id": _safe_text(raw.get("artifact_id"), 80),
        "label": _safe_text(raw.get("label"), 80),
        "kind": _safe_text(raw.get("kind"), 40),
        "path": _safe_path_text(raw.get("path")),
        "bytes": _non_negative_int(raw.get("bytes")),
        "updated_at": _safe_text(raw.get("updated_at"), 80),
    }


def context_for_artifact(context: dict[str, Any] | None) -> dict[str, Any]:
    context = sanitize_advanced_context(context)
    summary = context["summary"]
    return {
        "source_count": summary["source_count"],
        "ready_source_count": summary["ready_source_count"],
        "artifact_count": summary["artifact_count"],
        "latest_price": summary["latest_price"],
        "primary_cache_path": summary["primary_cache_path"],
        "sources": [
            {
                "source_id": source["source_id"],
                "state": source["state"],
                "cache_path": source["cache_path"],
                "record_count": source["record_count"],
            }
            for source in context["sources"][:6]
        ],
    }


def _source(
    source_id: str,
    label: str,
    kind: str,
    status: dict[str, Any],
    *,
    record_count: int,
    cache_path: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "label": label,
        "kind": kind,
        "state": str(status.get("state") or "unavailable"),
        "provider_id": str(status.get("provider_id") or status.get("source") or source_id),
        "cache_path": cache_path,
        "record_count": record_count,
        "updated_at": str(status.get("last_update") or "not refreshed"),
        "detail": detail,
    }


def _artifact_index(root: Path) -> list[dict[str, Any]]:
    root = root.resolve()
    rows: list[dict[str, Any]] = []
    for kind, pattern in ARTIFACT_GLOBS:
        for path in root.glob(pattern):
            if not path.is_file() or path.suffix.lower() not in ARTIFACT_SUFFIXES:
                continue
            try:
                relative = path.resolve().relative_to(root).as_posix()
                stat = path.stat()
            except (OSError, ValueError):
                continue
            rows.append(
                {
                    "artifact_id": f"{kind}-{len(rows) + 1}",
                    "label": path.name,
                    "kind": kind,
                    "path": relative,
                    "bytes": stat.st_size,
                    "updated_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                }
            )
    return [
        sanitize_context_artifact(row)
        for row in sorted(rows, key=lambda item: str(item["updated_at"]), reverse=True)[
            :MAX_CONTEXT_ARTIFACTS
        ]
    ]


def _crypto_detail_path(status: dict[str, Any]) -> str:
    symbol = str(status.get("symbol") or "BTCUSDT")
    timeframe = str(status.get("timeframe") or "15m")
    return f"market_data/crypto/{symbol}/{timeframe}.json"


def _latest_price(market_rows: list[Any], candles: list[Any]) -> str:
    for row in market_rows:
        if not isinstance(row, dict):
            continue
        price = str(row.get("price") or row.get("last_price") or "").replace(",", "")
        if _is_number(price):
            return price
    for candle in reversed(candles):
        if not isinstance(candle, dict):
            continue
        close = str(candle.get("close") or "").replace(",", "")
        if _is_number(close):
            return close
    return ""


def _price_series(candles: list[Any]) -> str:
    values = []
    for candle in candles[-12:]:
        if not isinstance(candle, dict):
            continue
        close = str(candle.get("close") or "").replace(",", "")
        if _is_number(close):
            values.append(close)
    return ",".join(values)


def _first_cache_path(sources: list[dict[str, Any]]) -> str:
    for source in sources:
        path = source.get("cache_path")
        if path:
            return str(path)
    return ""


def _is_number(raw: str) -> bool:
    try:
        float(raw)
    except (TypeError, ValueError):
        return False
    return True


def _safe_text(raw: Any, limit: int) -> str:
    value = str(raw or "").strip()
    return value[:limit]


def _safe_path_text(raw: Any) -> str:
    value = str(raw or "").strip().replace("\\", "/")
    if value.startswith(("/", "\\")) or ".." in Path(value).parts:
        return ""
    return value[:240]


def _non_negative_int(raw: Any) -> int:
    try:
        value = int(raw or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, value)
