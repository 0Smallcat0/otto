"""Public read-only crypto market-data adapters and cache normalization."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


SUPPORTED_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
SUPPORTED_INTERVALS = ("1m", "5m", "15m", "1h", "4h", "1d")
DEFAULT_SYMBOL = "BTCUSDT"
DEFAULT_INTERVAL = "15m"
DEFAULT_DEPTH_LIMIT = 20
DEFAULT_TRADE_LIMIT = 20
DEFAULT_KLINE_LIMIT = 80

BINANCE_DOCS = "https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints"
KRAKEN_DOCS = "https://docs.kraken.com/api/docs/rest-api/get-ohlc-data/"
COINBASE_DOCS = "https://docs.cdp.coinbase.com/coinbase-business/advanced-trade-apis/rest-api"
BINANCE_BASE_URL = "https://api.binance.com/api/v3"
KRAKEN_BASE_URL = "https://api.kraken.com/0/public"
COINBASE_BASE_URL = "https://api.coinbase.com/api/v3/brokerage/market"

KRAKEN_PAIRS = {"BTCUSDT": "XBTUSDT", "ETHUSDT": "ETHUSDT", "SOLUSDT": "SOLUSDT"}
COINBASE_PRODUCTS = {"BTCUSDT": "BTC-USDT", "ETHUSDT": "ETH-USDT", "SOLUSDT": "SOL-USDT"}
KRAKEN_INTERVALS = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}
COINBASE_GRANULARITIES = {
    "1m": "ONE_MINUTE",
    "5m": "FIVE_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "1h": "ONE_HOUR",
    "4h": "FOUR_HOUR",
    "1d": "ONE_DAY",
}
INTERVAL_SECONDS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}


class CryptoDataError(ValueError):
    """Raised when a public crypto provider cannot produce normalized data."""


def empty_crypto_detail(symbol: str = DEFAULT_SYMBOL, interval: str = DEFAULT_INTERVAL) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    interval = normalize_interval(interval)
    return {
        "status": {
            "source": "public_provider_unavailable",
            "state": "unavailable",
            "last_update": "not refreshed",
            "message": "No public crypto detail cache is available yet.",
            "symbol": symbol,
            "timeframe": interval,
            "provider_id": "",
            "fallback_used": False,
        },
        "provider": _provider_meta(
            provider_id="",
            label="No public crypto provider cache",
            source="public_provider_unavailable",
            docs_url="",
            state="unavailable",
            message="Refresh public data to populate depth, trades, and candles.",
            symbol=symbol,
            interval=interval,
        ),
        "depth": {"bids": [], "asks": []},
        "trades": [],
        "candles": [],
    }


def crypto_detail_payload(
    cache: dict[str, Any] | None = None,
    *,
    fetcher: Any | None = None,
    refresh: bool = False,
    symbol: str = DEFAULT_SYMBOL,
    interval: str = DEFAULT_INTERVAL,
) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    interval = normalize_interval(interval)
    cache = cache if isinstance(cache, dict) else {}

    if refresh and fetcher is not None:
        try:
            payload = normalize_crypto_detail_cache(fetcher(symbol=symbol, interval=interval))
            return {**payload, "cache": payload}
        except (CryptoDataError, OSError, URLError, HTTPError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            cached = normalize_cached_crypto_detail(cache, symbol=symbol, interval=interval)
            if cached["status"]["state"] != "unavailable":
                cached["status"] = {
                    **cached["status"],
                    "state": "stale",
                    "message": f"Using stale public crypto cache; refresh failed: {type(exc).__name__}.",
                    "fallback_used": True,
                }
                cached["provider"] = {**cached["provider"], "state": "stale", "fallback_used": True}
                return {**cached, "cache": None}
            unavailable = empty_crypto_detail(symbol, interval)
            unavailable["status"]["message"] = f"Public crypto refresh failed: {type(exc).__name__}."
            unavailable["provider"]["message"] = unavailable["status"]["message"]
            return {**unavailable, "cache": None}

    cached = normalize_cached_crypto_detail(cache, symbol=symbol, interval=interval)
    return {**cached, "cache": None}


def normalize_cached_crypto_detail(
    cache: dict[str, Any],
    *,
    symbol: str = DEFAULT_SYMBOL,
    interval: str = DEFAULT_INTERVAL,
) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    interval = normalize_interval(interval)
    if not isinstance(cache, dict):
        return empty_crypto_detail(symbol, interval)

    status = cache.get("status")
    if not isinstance(status, dict):
        return empty_crypto_detail(symbol, interval)
    if status.get("symbol") != symbol or status.get("timeframe") != interval:
        return empty_crypto_detail(symbol, interval)

    depth = cache.get("depth")
    provider = cache.get("provider")
    trades = cache.get("trades")
    candles = cache.get("candles")
    if not isinstance(depth, dict) or not isinstance(provider, dict):
        return empty_crypto_detail(symbol, interval)
    cached_state = _cached_state(status)
    return {
        "status": {
            **status,
            "state": cached_state,
            "fallback_used": cached_state != "live",
        },
        "provider": {
            **provider,
            "state": cached_state,
            "fallback_used": cached_state != "live",
        },
        "depth": {
            "bids": _levels(depth.get("bids")),
            "asks": _levels(depth.get("asks")),
        },
        "trades": _trade_rows(trades),
        "candles": _candle_rows(candles),
    }


def normalize_crypto_detail_cache(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CryptoDataError("Crypto detail payload must be an object")
    status = payload.get("status")
    provider = payload.get("provider")
    depth = payload.get("depth")
    if not isinstance(status, dict) or not isinstance(provider, dict) or not isinstance(depth, dict):
        raise CryptoDataError("Crypto detail payload missing status/provider/depth")
    symbol = normalize_symbol(status.get("symbol"))
    interval = normalize_interval(status.get("timeframe"))
    normalized = {
        "status": {
            **status,
            "source": str(status.get("source") or provider.get("source") or provider.get("provider_id")),
            "state": str(status.get("state") or "live"),
            "last_update": str(status.get("last_update") or _utc_now()),
            "message": str(status.get("message") or "Public crypto data refreshed."),
            "symbol": symbol,
            "timeframe": interval,
            "provider_id": str(status.get("provider_id") or provider.get("provider_id") or ""),
            "fallback_used": bool(status.get("fallback_used", False)),
        },
        "provider": {
            **provider,
            "state": str(provider.get("state") or "live"),
            "symbol": symbol,
            "timeframe": interval,
            "fallback_used": bool(provider.get("fallback_used", False)),
        },
        "depth": {"bids": _levels(depth.get("bids")), "asks": _levels(depth.get("asks"))},
        "trades": _trade_rows(payload.get("trades")),
        "candles": _candle_rows(payload.get("candles")),
    }
    if not normalized["depth"]["bids"] or not normalized["depth"]["asks"]:
        raise CryptoDataError("Crypto detail payload missing book levels")
    if not normalized["candles"]:
        raise CryptoDataError("Crypto detail payload missing closed candles")
    return normalized


def fetch_public_crypto_detail(
    *,
    symbol: str = DEFAULT_SYMBOL,
    interval: str = DEFAULT_INTERVAL,
    timeout: float = 4.0,
) -> dict[str, Any]:
    errors: list[str] = []
    for fetcher in (fetch_binance_crypto_detail, fetch_kraken_crypto_detail, fetch_coinbase_crypto_detail):
        try:
            return fetcher(symbol=symbol, interval=interval, timeout=timeout)
        except (CryptoDataError, OSError, URLError, HTTPError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{fetcher.__name__}: {type(exc).__name__}")
    raise CryptoDataError("; ".join(errors) or "No public crypto provider succeeded")


def fetch_binance_crypto_detail(
    *,
    symbol: str = DEFAULT_SYMBOL,
    interval: str = DEFAULT_INTERVAL,
    timeout: float = 4.0,
) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    interval = normalize_interval(interval)
    depth = _read_json_url(
        f"{BINANCE_BASE_URL}/depth?{urlencode({'symbol': symbol, 'limit': DEFAULT_DEPTH_LIMIT})}",
        timeout,
    )
    trades = _read_json_url(
        f"{BINANCE_BASE_URL}/trades?{urlencode({'symbol': symbol, 'limit': DEFAULT_TRADE_LIMIT})}",
        timeout,
    )
    klines = _read_json_url(
        f"{BINANCE_BASE_URL}/klines?{urlencode({'symbol': symbol, 'interval': interval, 'limit': DEFAULT_KLINE_LIMIT})}",
        timeout,
    )
    now = _utc_now()
    return normalize_crypto_detail_cache(
        {
            "status": _status(
                source="binance_public",
                provider_id="binance_spot_public",
                symbol=symbol,
                interval=interval,
                last_update=now,
                message="Public read-only Binance depth, trades, and closed candles refreshed.",
            ),
            "provider": _provider_meta(
                provider_id="binance_spot_public",
                label="Binance Spot public market data",
                source="binance_public",
                docs_url=BINANCE_DOCS,
                state="live",
                message="No-key public market-data endpoints only.",
                symbol=symbol,
                interval=interval,
            ),
            "depth": normalize_binance_depth(depth),
            "trades": normalize_binance_trades(trades),
            "candles": normalize_binance_klines(klines, interval=interval),
        }
    )


def fetch_kraken_crypto_detail(
    *,
    symbol: str = DEFAULT_SYMBOL,
    interval: str = DEFAULT_INTERVAL,
    timeout: float = 4.0,
) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    interval = normalize_interval(interval)
    pair = KRAKEN_PAIRS[symbol]
    depth = _kraken_result(
        _read_json_url(f"{KRAKEN_BASE_URL}/Depth?{urlencode({'pair': pair, 'count': DEFAULT_DEPTH_LIMIT})}", timeout)
    )
    trades = _kraken_result(_read_json_url(f"{KRAKEN_BASE_URL}/Trades?{urlencode({'pair': pair})}", timeout))
    ohlc = _kraken_result(
        _read_json_url(f"{KRAKEN_BASE_URL}/OHLC?{urlencode({'pair': pair, 'interval': KRAKEN_INTERVALS[interval]})}", timeout)
    )
    now = _utc_now()
    return normalize_crypto_detail_cache(
        {
            "status": _status(
                source="kraken_public",
                provider_id="kraken_public_market_data",
                symbol=symbol,
                interval=interval,
                last_update=now,
                message="Public read-only Kraken book, trades, and closed candles refreshed.",
            ),
            "provider": _provider_meta(
                provider_id="kraken_public_market_data",
                label="Kraken public market data",
                source="kraken_public",
                docs_url=KRAKEN_DOCS,
                state="live",
                message="No-key public market-data endpoints only.",
                symbol=symbol,
                interval=interval,
            ),
            "depth": normalize_kraken_depth(_first_result(depth)),
            "trades": normalize_kraken_trades(_first_result(trades)),
            "candles": normalize_kraken_ohlc(_first_result(ohlc), interval=interval),
        }
    )


def fetch_coinbase_crypto_detail(
    *,
    symbol: str = DEFAULT_SYMBOL,
    interval: str = DEFAULT_INTERVAL,
    timeout: float = 4.0,
) -> dict[str, Any]:
    symbol = normalize_symbol(symbol)
    interval = normalize_interval(interval)
    product_id = COINBASE_PRODUCTS[symbol]
    now_dt = datetime.now(tz=UTC)
    start_dt = now_dt - timedelta(seconds=INTERVAL_SECONDS[interval] * DEFAULT_KLINE_LIMIT)
    depth = _read_json_url(
        f"{COINBASE_BASE_URL}/product_book?{urlencode({'product_id': product_id, 'limit': DEFAULT_DEPTH_LIMIT})}",
        timeout,
    )
    trades = _read_json_url(
        f"{COINBASE_BASE_URL}/products/{product_id}/ticker?{urlencode({'limit': DEFAULT_TRADE_LIMIT})}",
        timeout,
    )
    candles = _read_json_url(
        f"{COINBASE_BASE_URL}/products/{product_id}/candles?"
        f"{urlencode({'start': int(start_dt.timestamp()), 'end': int(now_dt.timestamp()), 'granularity': COINBASE_GRANULARITIES[interval], 'limit': DEFAULT_KLINE_LIMIT})}",
        timeout,
    )
    now = _utc_now()
    return normalize_crypto_detail_cache(
        {
            "status": _status(
                source="coinbase_public",
                provider_id="coinbase_public_market_data",
                symbol=symbol,
                interval=interval,
                last_update=now,
                message="Public read-only Coinbase book, trades, and closed candles refreshed.",
            ),
            "provider": _provider_meta(
                provider_id="coinbase_public_market_data",
                label="Coinbase public market data",
                source="coinbase_public",
                docs_url=COINBASE_DOCS,
                state="live",
                message="No-key public market-data endpoints only.",
                symbol=symbol,
                interval=interval,
            ),
            "depth": normalize_coinbase_book(depth),
            "trades": normalize_coinbase_trades(trades),
            "candles": normalize_coinbase_candles(candles, interval=interval),
        }
    )


def normalize_binance_depth(payload: Any) -> dict[str, list[dict[str, str]]]:
    if not isinstance(payload, dict):
        raise CryptoDataError("Binance depth response must be an object")
    return {"bids": _levels_from_pairs(payload.get("bids")), "asks": _levels_from_pairs(payload.get("asks"))}


def normalize_binance_trades(payload: Any) -> list[dict[str, str]]:
    if not isinstance(payload, list):
        raise CryptoDataError("Binance trades response must be a list")
    rows = []
    for trade in payload[:DEFAULT_TRADE_LIMIT]:
        if not isinstance(trade, dict):
            continue
        rows.append(
            {
                "trade_id": str(trade.get("id", "")),
                "price": _clean_number(trade.get("price")),
                "quantity": _clean_number(trade.get("qty")),
                "quote_quantity": _clean_number(trade.get("quoteQty", "")),
                "traded_at": _iso_from_ms(trade.get("time")),
                "side": "SELL" if trade.get("isBuyerMaker") is True else "BUY",
                "source": "binance_public",
            }
        )
    return rows


def normalize_binance_klines(payload: Any, *, interval: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise CryptoDataError("Binance kline response must be a list")
    now_ms = int(datetime.now(tz=UTC).timestamp() * 1000)
    candles = []
    for row in payload:
        if not isinstance(row, list) or len(row) < 7:
            continue
        close_ms = int(row[6])
        if close_ms >= now_ms:
            continue
        candles.append(_candle(row[0], row[6], row[1], row[2], row[3], row[4], row[5], interval=interval))
    return candles


def normalize_kraken_depth(payload: Any) -> dict[str, list[dict[str, str]]]:
    if not isinstance(payload, dict):
        raise CryptoDataError("Kraken depth response must be an object")
    return {"bids": _levels_from_pairs(payload.get("bids")), "asks": _levels_from_pairs(payload.get("asks"))}


def normalize_kraken_trades(payload: Any) -> list[dict[str, str]]:
    if not isinstance(payload, list):
        raise CryptoDataError("Kraken trades response must be a list")
    rows = []
    for index, trade in enumerate(payload[:DEFAULT_TRADE_LIMIT]):
        if not isinstance(trade, list) or len(trade) < 4:
            continue
        timestamp = float(trade[2])
        rows.append(
            {
                "trade_id": str(trade[6] if len(trade) > 6 else index),
                "price": _clean_number(trade[0]),
                "quantity": _clean_number(trade[1]),
                "quote_quantity": "",
                "traded_at": datetime.fromtimestamp(timestamp, tz=UTC).isoformat(timespec="seconds"),
                "side": "BUY" if trade[3] == "b" else "SELL",
                "source": "kraken_public",
            }
        )
    return rows


def normalize_kraken_ohlc(payload: Any, *, interval: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise CryptoDataError("Kraken OHLC response must be a list")
    candles = []
    for row in payload[:-1]:
        if not isinstance(row, list) or len(row) < 7:
            continue
        open_ms = int(float(row[0]) * 1000)
        close_ms = open_ms + INTERVAL_SECONDS[interval] * 1000
        candles.append(_candle(open_ms, close_ms, row[1], row[2], row[3], row[4], row[6], interval=interval))
    return candles


def normalize_coinbase_book(payload: Any) -> dict[str, list[dict[str, str]]]:
    if not isinstance(payload, dict):
        raise CryptoDataError("Coinbase book response must be an object")
    pricebook = payload.get("pricebook")
    if not isinstance(pricebook, dict):
        raise CryptoDataError("Coinbase book missing pricebook")
    return {
        "bids": _levels_from_objects(pricebook.get("bids")),
        "asks": _levels_from_objects(pricebook.get("asks")),
    }


def normalize_coinbase_trades(payload: Any) -> list[dict[str, str]]:
    trades = payload.get("trades") if isinstance(payload, dict) else None
    if not isinstance(trades, list):
        raise CryptoDataError("Coinbase trades response missing trades")
    rows = []
    for index, trade in enumerate(trades[:DEFAULT_TRADE_LIMIT]):
        if not isinstance(trade, dict):
            continue
        rows.append(
            {
                "trade_id": str(trade.get("trade_id") or trade.get("tradeId") or index),
                "price": _clean_number(trade.get("price")),
                "quantity": _clean_number(trade.get("size")),
                "quote_quantity": "",
                "traded_at": str(trade.get("time") or trade.get("trade_time") or ""),
                "side": str(trade.get("side") or "").upper(),
                "source": "coinbase_public",
            }
        )
    return rows


def normalize_coinbase_candles(payload: Any, *, interval: str) -> list[dict[str, Any]]:
    candles = payload.get("candles") if isinstance(payload, dict) else None
    if not isinstance(candles, list):
        raise CryptoDataError("Coinbase candle response missing candles")
    rows = []
    for candle in candles:
        if not isinstance(candle, dict):
            continue
        open_ms = int(candle["start"]) * 1000
        close_ms = open_ms + INTERVAL_SECONDS[interval] * 1000
        if close_ms >= int(datetime.now(tz=UTC).timestamp() * 1000):
            continue
        rows.append(
            _candle(
                open_ms,
                close_ms,
                candle.get("open"),
                candle.get("high"),
                candle.get("low"),
                candle.get("close"),
                candle.get("volume"),
                interval=interval,
            )
        )
    return sorted(rows, key=lambda item: item["opened_at"])


def normalize_symbol(raw_symbol: Any) -> str:
    symbol = "".join(ch for ch in str(raw_symbol or DEFAULT_SYMBOL).upper() if ch.isalnum())[:20]
    if symbol not in SUPPORTED_SYMBOLS:
        raise CryptoDataError("Unsupported public crypto symbol")
    return symbol


def normalize_interval(raw_interval: Any) -> str:
    interval = str(raw_interval or DEFAULT_INTERVAL)
    if interval not in SUPPORTED_INTERVALS:
        raise CryptoDataError("Unsupported public crypto interval")
    return interval


def _read_json_url(url: str, timeout: float) -> Any:
    request = Request(url, headers={"User-Agent": "LocalTerminalCleanRoom/0.1"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _status(
    *,
    source: str,
    provider_id: str,
    symbol: str,
    interval: str,
    last_update: str,
    message: str,
) -> dict[str, Any]:
    return {
        "source": source,
        "state": "live",
        "last_update": last_update,
        "message": message,
        "symbol": symbol,
        "timeframe": interval,
        "provider_id": provider_id,
        "fallback_used": False,
    }


def _provider_meta(
    *,
    provider_id: str,
    label: str,
    source: str,
    docs_url: str,
    state: str,
    message: str,
    symbol: str,
    interval: str,
) -> dict[str, Any]:
    return {
        "provider_id": provider_id,
        "label": label,
        "source": source,
        "state": state,
        "retrieved_at": _utc_now() if state == "live" else "",
        "docs_url": docs_url,
        "cache_path": f"market_data/crypto/{symbol}/{interval}.json" if provider_id else "",
        "message": message,
        "symbol": symbol,
        "timeframe": interval,
        "fallback_used": False,
        "auth_mode": "no-key" if provider_id else "",
        "safety_class": "public_read_only_market_data" if provider_id else "",
    }


def _kraken_result(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CryptoDataError("Kraken response must be an object")
    errors = payload.get("error")
    if isinstance(errors, list) and errors:
        raise CryptoDataError("; ".join(str(error) for error in errors))
    result = payload.get("result")
    if not isinstance(result, dict):
        raise CryptoDataError("Kraken response missing result")
    return result


def _first_result(payload: dict[str, Any]) -> Any:
    for key, value in payload.items():
        if key != "last":
            return value
    raise CryptoDataError("Provider result is empty")


def _levels_from_pairs(payload: Any) -> list[dict[str, str]]:
    levels = []
    if isinstance(payload, list):
        for row in payload[:DEFAULT_DEPTH_LIMIT]:
            if isinstance(row, list) and len(row) >= 2:
                levels.append({"price": _clean_number(row[0]), "quantity": _clean_number(row[1])})
    return levels


def _levels_from_objects(payload: Any) -> list[dict[str, str]]:
    levels = []
    if isinstance(payload, list):
        for row in payload[:DEFAULT_DEPTH_LIMIT]:
            if isinstance(row, dict):
                levels.append({"price": _clean_number(row.get("price")), "quantity": _clean_number(row.get("size"))})
    return levels


def _levels(payload: Any) -> list[dict[str, str]]:
    levels = []
    if isinstance(payload, list):
        for row in payload:
            if isinstance(row, dict) and "price" in row and "quantity" in row:
                levels.append({"price": _clean_number(row["price"]), "quantity": _clean_number(row["quantity"])})
    return levels


def _trade_rows(payload: Any) -> list[dict[str, str]]:
    rows = []
    if isinstance(payload, list):
        for row in payload[:DEFAULT_TRADE_LIMIT]:
            if not isinstance(row, dict):
                continue
            rows.append(
                {
                    "trade_id": str(row.get("trade_id", "")),
                    "price": _clean_number(row.get("price")),
                    "quantity": _clean_number(row.get("quantity")),
                    "quote_quantity": _clean_number(row.get("quote_quantity", "")),
                    "traded_at": str(row.get("traded_at", "")),
                    "side": str(row.get("side", "")),
                    "source": str(row.get("source", "")),
                }
            )
    return rows


def _candle_rows(payload: Any) -> list[dict[str, Any]]:
    rows = []
    if isinstance(payload, list):
        for row in payload:
            if not isinstance(row, dict):
                continue
            rows.append(
                {
                    "opened_at": str(row.get("opened_at", "")),
                    "closed_at": str(row.get("closed_at", "")),
                    "open": _clean_number(row.get("open")),
                    "high": _clean_number(row.get("high")),
                    "low": _clean_number(row.get("low")),
                    "close": _clean_number(row.get("close")),
                    "volume": _clean_number(row.get("volume")),
                    "interval": str(row.get("interval", "")),
                    "closed": row.get("closed") is True,
                }
            )
    return rows


def _candle(
    open_ms: Any,
    close_ms: Any,
    open_price: Any,
    high: Any,
    low: Any,
    close: Any,
    volume: Any,
    *,
    interval: str,
) -> dict[str, Any]:
    return {
        "opened_at": _iso_from_ms(open_ms),
        "closed_at": _iso_from_ms(close_ms),
        "open": _clean_number(open_price),
        "high": _clean_number(high),
        "low": _clean_number(low),
        "close": _clean_number(close),
        "volume": _clean_number(volume),
        "interval": interval,
        "closed": True,
    }


def _clean_number(raw: Any) -> str:
    return str(raw if raw is not None else "").strip()


def _iso_from_ms(raw: Any) -> str:
    return datetime.fromtimestamp(int(raw) / 1000, tz=UTC).isoformat(timespec="seconds")


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _cached_state(status: dict[str, Any]) -> str:
    if status.get("state") != "live":
        return str(status.get("state") or "stale")
    raw = status.get("last_update")
    if not isinstance(raw, str):
        return "stale"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return "stale"
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    age = datetime.now(tz=UTC) - parsed.astimezone(UTC)
    return "live" if age.total_seconds() <= 30 else "stale"
