"""Paper-only crypto workspace contracts and broker rules."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from uuid import uuid4

from otto.local_terminal.crypto_data import crypto_detail_payload
from otto.local_terminal.markets import default_markets_layout, markets_payload


SUPPORTED_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
TIMEFRAMES = ("1m", "5m", "15m", "1h", "4h", "1d")
ORDER_TYPES = ("MARKET", "LIMIT", "STOP", "STOP_LIMIT")
FEE_RATE = Decimal("0.001")
INITIAL_CASH = Decimal("100000.00")


class PaperOrderError(ValueError):
    """Raised when a paper order violates local broker safety rules."""


def default_paper_state() -> dict[str, Any]:
    return {
        "account": {
            "account_id": "paper-default",
            "mode": "paper",
            "quote_asset": "USDT",
            "initial_cash": _money(INITIAL_CASH),
            "cash": _money(INITIAL_CASH),
            "equity": _money(INITIAL_CASH),
            "updated_at": "",
        },
        "positions": {},
        "orders": [],
        "fills": [],
        "ledger": [],
    }


def normalize_paper_state(state: dict[str, Any]) -> dict[str, Any]:
    default = default_paper_state()
    account = {**default["account"], **state.get("account", {})}
    account.update({"mode": "paper", "quote_asset": "USDT"})
    return {
        "account": account,
        "positions": state.get("positions") if isinstance(state.get("positions"), dict) else {},
        "orders": state.get("orders") if isinstance(state.get("orders"), list) else [],
        "fills": state.get("fills") if isinstance(state.get("fills"), list) else [],
        "ledger": state.get("ledger") if isinstance(state.get("ledger"), list) else [],
    }


def crypto_payload(
    state: dict[str, Any],
    market_cache: dict[str, Any] | None = None,
    detail_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    paper_state = normalize_paper_state(state)
    detail = crypto_detail_payload(detail_cache or {})
    market = markets_payload(default_markets_layout(), market_cache or {}, detail)
    market = _market_with_detail_fallback(market, detail)
    prices = _prices_from_rows(market["rows"])
    active_symbol = str(detail["status"].get("symbol") or "BTCUSDT")
    quote = _quote_snapshot(active_symbol, market, detail)
    account = _account_with_equity(paper_state, prices)
    positions = list(paper_state["positions"].values())
    orders = list(reversed(paper_state["orders"]))
    fills = list(reversed(paper_state["fills"]))
    ledger = list(reversed(paper_state["ledger"]))
    return {
        "mode": "paper",
        "exchange": "binance_public",
        "active_symbol": active_symbol,
        "active_timeframe": str(detail["status"].get("timeframe") or "15m"),
        "symbols": list(SUPPORTED_SYMBOLS),
        "timeframes": list(TIMEFRAMES),
        "order_types": list(ORDER_TYPES),
        "fee_rate": str(FEE_RATE),
        "account": account,
        "positions": positions,
        "orders": orders,
        "history": orders,
        "fills": fills,
        "ledger": ledger,
        "fees": [{"fill_id": fill["fill_id"], "symbol": fill["symbol"], "fee": fill["fee"]} for fill in fills],
        "market": {"status": market["status"], "rows": market["rows"]},
        "watchlist": _watchlist_from_market_rows(market["rows"]),
        "quote": quote,
        "provider": detail["provider"],
        "depth": detail["depth"],
        "trades": detail["trades"],
        "candles": detail["candles"],
        "chart": _chart_from_candles(detail["candles"], detail),
        "artifacts": {
            "paper_state": "artifacts/paper/paper_state.json",
            "orders_jsonl": "artifacts/paper/{date}/orders.jsonl",
            "fills_jsonl": "artifacts/paper/{date}/fills.jsonl",
            "account_snapshots_jsonl": "artifacts/paper/{date}/account_snapshots.jsonl",
        },
        "stats": {
            "open_orders": sum(1 for order in paper_state["orders"] if order["status"] == "WORKING"),
            "filled_orders": sum(1 for order in paper_state["orders"] if order["status"] == "FILLED"),
            "fills": len(paper_state["fills"]),
            "ledger_events": len(paper_state["ledger"]),
            "provider_trades": len(detail["trades"]),
            "closed_candles": len(detail["candles"]),
            "watchlist_rows": len(market["rows"]),
            "quote_source": quote["source"],
            "quote_state": quote["state"],
            "quote_price": quote["price"],
            "last_fill_source": fills[0].get("quote_source", "") if fills else "",
            "detail_source": detail["status"]["source"],
            "detail_state": detail["status"]["state"],
            "paper_only": True,
            "live_execution": "disabled",
        },
        "safety": {
            "real_orders": False,
            "private_api_required": False,
            "margin": False,
            "leverage": False,
            "short": False,
            "derivatives": False,
        },
    }


def paper_summary_payload(
    state: dict[str, Any],
    market_cache: dict[str, Any] | None = None,
    detail_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Everything an agent needs to run the decision loop, in ~1KB.

    The full paper payload runs 74k+ chars (2026-07-17 dogfood P1) — order
    history, depth ladders, raw trades, candles — while the decision loop
    needs exactly: account, positions marked to the freshest known price,
    per-symbol quote freshness against the fill gate's TTL, and open orders.
    """
    paper_state = normalize_paper_state(state)
    detail = crypto_detail_payload(detail_cache or {})
    market = markets_payload(default_markets_layout(), market_cache or {}, detail)
    market = _market_with_detail_fallback(market, detail)
    prices = _prices_from_rows(market["rows"])
    account = _account_with_equity(paper_state, prices)

    quotes: list[dict[str, Any]] = []
    freshest_by_symbol: dict[str, dict[str, Any]] = {}
    for row in market["rows"]:
        symbol = str(row.get("symbol", ""))
        snapshot = _quote_snapshot(symbol, market, detail)
        age = _quote_age_seconds(snapshot["retrieved_at"])
        entry = {
            "symbol": symbol,
            "price": snapshot["price"],
            "chg_pct": str(row.get("chg_pct", "N/A")),
            "state": snapshot["state"],
            "retrieved_at": snapshot["retrieved_at"],
            "age_seconds": None if age is None else int(age),
        }
        quotes.append(entry)
        freshest_by_symbol[symbol] = entry

    positions = []
    for symbol, position in paper_state["positions"].items():
        quantity = Decimal(position["quantity"])
        avg_price = Decimal(position["avg_price"])
        last = prices.get(symbol)
        unrealized = (quantity * (last - avg_price)) if last is not None else None
        positions.append(
            {
                "symbol": symbol,
                "quantity": _amount(quantity),
                "avg_price": _money(avg_price),
                "last_price": _money(last) if last is not None else "N/A",
                "unrealized_pnl": _money(unrealized) if unrealized is not None else "N/A",
                "unrealized_pnl_pct": (
                    f"{(last / avg_price - 1) * 100:.2f}"
                    if last is not None and avg_price
                    else "N/A"
                ),
                "quote_age_seconds": freshest_by_symbol.get(symbol, {}).get("age_seconds"),
            }
        )

    open_orders = [
        {
            "order_id": order["order_id"],
            "symbol": order["symbol"],
            "side": order["side"],
            "type": order["type"],
            "quantity": order["quantity"],
            "limit_price": order.get("limit_price"),
            "created_at": order["created_at"],
        }
        for order in paper_state["orders"]
        if order["status"] == "WORKING"
    ]

    ages = [entry["age_seconds"] for entry in quotes]
    all_fresh = bool(ages) and all(
        age is not None and age <= QUOTE_FRESHNESS_TTL_SECONDS for age in ages
    )
    initial = Decimal(account.get("initial_cash", "0"))
    equity = Decimal(account["equity"])
    return {
        "mode": "paper",
        "as_of": _utc_now(),
        "account": {
            **account,
            "total_pnl": _money(equity - initial),
            "total_pnl_pct": f"{(equity / initial - 1) * 100:.3f}" if initial else "N/A",
        },
        "positions": positions,
        "open_orders": open_orders,
        "quotes": quotes,
        "freshness": {
            "ttl_seconds": QUOTE_FRESHNESS_TTL_SECONDS,
            "all_fresh": all_fresh,
            "refresh_action": "crypto_refresh_public",
            "note": "MARKET fills are refused when the symbol quote is older than ttl_seconds",
        },
        "safety": {
            "paper_only": True,
            "live_execution": "disabled",
            "real_orders": False,
        },
    }


def place_paper_order(
    state: dict[str, Any],
    request: dict[str, Any],
    market_cache: dict[str, Any] | None = None,
    detail_cache: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    paper_state = normalize_paper_state(copy.deepcopy(state))
    symbol = _normalize_symbol(request.get("symbol"))
    side = str(request.get("side", "")).upper()
    order_type = str(request.get("order_type", "")).upper()
    quantity = _positive_decimal(request.get("quantity"), "Quantity")
    limit_price = _optional_price(request.get("limit_price"))
    stop_price = _optional_price(request.get("stop_price"))
    if side not in {"BUY", "SELL"}:
        raise PaperOrderError("Side must be BUY or SELL")
    if order_type not in ORDER_TYPES:
        raise PaperOrderError("Order type must be Market, Limit, Stop, or Stop-Limit")
    if order_type in {"LIMIT", "STOP_LIMIT"} and limit_price is None:
        raise PaperOrderError("Limit price is required")
    if order_type in {"STOP", "STOP_LIMIT"} and stop_price is None:
        raise PaperOrderError("Stop price is required")

    cash = Decimal(paper_state["account"]["cash"])
    position = paper_state["positions"].get(symbol)
    held_quantity = Decimal(position["quantity"]) if position else Decimal("0")
    if side == "SELL" and quantity > held_quantity:
        raise PaperOrderError("Cannot sell more than long paper position")

    detail = crypto_detail_payload(detail_cache or {})
    market = markets_payload(default_markets_layout(), market_cache or {}, detail)
    market = _market_with_detail_fallback(market, detail)
    prices = _prices_from_rows(market["rows"])
    price = _paper_price(symbol, prices, limit_price)
    quote_snapshot = _quote_snapshot(symbol, market, detail)
    if order_type == "MARKET":
        age = _quote_age_seconds(quote_snapshot["retrieved_at"])
        if age is None or age > QUOTE_FRESHNESS_TTL_SECONDS:
            age_text = "unknown" if age is None else f"{int(age)}s"
            raise PaperOrderError(
                f"Refusing MARKET fill on a stale quote for {symbol}: quote age "
                f"{age_text} exceeds {QUOTE_FRESHNESS_TTL_SECONDS}s. "
                "Refresh public crypto data first (crypto_refresh_public)."
            )
    exposure_price = _exposure_price(order_type, price, limit_price, stop_price)
    notional = quantity * exposure_price
    fee = (notional * FEE_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if side == "BUY" and notional + fee > cash:
        raise PaperOrderError("Insufficient paper cash")

    now = _utc_now()
    order = {
        "order_id": f"paper-{uuid4().hex[:12]}",
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": _amount(quantity),
        "limit_price": _money(limit_price) if limit_price is not None else None,
        "stop_price": _money(stop_price) if stop_price is not None else None,
        "status": "WORKING",
        "reason": "Paper order accepted",
        "created_at": now,
        **_quote_event_fields(quote_snapshot),
    }
    paper_state["orders"].append(order)

    if order_type == "MARKET":
        fill_notional = quantity * price
        fill_fee = (fill_notional * FEE_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        _apply_fill(paper_state, order, quantity, price, fill_fee, now, quote_snapshot)

    paper_state["account"]["updated_at"] = now
    paper_state["ledger"].append(
        {
            "event_id": f"ledger-{uuid4().hex[:12]}",
            "order_id": order["order_id"],
            "event": order["status"],
            "recorded_at": now,
            **_quote_event_fields(quote_snapshot),
        }
    )
    paper_state["account"] = _account_with_equity(paper_state, prices)
    return paper_state, order


def cancel_paper_order(
    state: dict[str, Any],
    order_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    paper_state = normalize_paper_state(copy.deepcopy(state))
    order_key = str(order_id or "").strip()
    if not order_key:
        raise PaperOrderError("Order id is required")
    order = next(
        (entry for entry in paper_state["orders"] if str(entry.get("order_id")) == order_key),
        None,
    )
    if order is None:
        raise PaperOrderError("Unknown paper order id")
    if str(order.get("status")) != "WORKING":
        raise PaperOrderError("Only WORKING paper orders can be cancelled")
    now = _utc_now()
    order["status"] = "CANCELLED"
    order["reason"] = "Cancelled locally"
    paper_state["account"]["updated_at"] = now
    paper_state["ledger"].append(
        {
            "event_id": f"ledger-{uuid4().hex[:12]}",
            "order_id": order_key,
            "event": "CANCELLED",
            "recorded_at": now,
        }
    )
    return paper_state, order


def _apply_fill(
    state: dict[str, Any],
    order: dict[str, Any],
    quantity: Decimal,
    price: Decimal,
    fee: Decimal,
    filled_at: str,
    quote_snapshot: dict[str, str],
) -> None:
    symbol = order["symbol"]
    cash = Decimal(state["account"]["cash"])
    position = state["positions"].get(
        symbol,
        {"symbol": symbol, "quantity": "0", "avg_price": _money(price), "realized_pnl": "0.00"},
    )
    held_quantity = Decimal(position["quantity"])
    avg_price = Decimal(position["avg_price"])
    notional = quantity * price

    if order["side"] == "BUY":
        new_quantity = held_quantity + quantity
        new_avg = ((held_quantity * avg_price) + notional) / new_quantity
        state["account"]["cash"] = _money(cash - notional - fee)
        state["positions"][symbol] = {
            **position,
            "quantity": _amount(new_quantity),
            "avg_price": _money(new_avg),
        }
    else:
        new_quantity = held_quantity - quantity
        realized = (price - avg_price) * quantity
        state["account"]["cash"] = _money(cash + notional - fee)
        if new_quantity == 0:
            state["positions"].pop(symbol, None)
        else:
            state["positions"][symbol] = {
                **position,
                "quantity": _amount(new_quantity),
                "realized_pnl": _money(Decimal(position.get("realized_pnl", "0")) + realized),
            }

    order["status"] = "FILLED"
    order["reason"] = "Paper market fill"
    fill = {
        "fill_id": f"fill-{uuid4().hex[:12]}",
        "order_id": order["order_id"],
        "symbol": symbol,
        "side": order["side"],
        "quantity": _amount(quantity),
        "price": _money(price),
        "fee": _money(fee),
        "filled_at": filled_at,
        **_quote_event_fields(quote_snapshot),
    }
    state["fills"].append(fill)


def _account_with_equity(state: dict[str, Any], prices: dict[str, Decimal]) -> dict[str, Any]:
    account = dict(state["account"])
    equity = Decimal(account["cash"])
    for symbol, position in state["positions"].items():
        equity += Decimal(position["quantity"]) * prices.get(symbol, Decimal(position["avg_price"]))
    account["equity"] = _money(equity)
    return account


def _prices_from_rows(rows: list[dict[str, str]]) -> dict[str, Decimal]:
    prices: dict[str, Decimal] = {}
    for row in rows:
        try:
            prices[row["symbol"]] = Decimal(row["price"])
        except (InvalidOperation, KeyError):
            continue
    return prices


def _watchlist_from_market_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    watchlist = []
    for row in rows:
        watchlist.append(
            {
                "symbol": str(row.get("symbol", "")),
                "price": str(row.get("price", "N/A")),
                "chg": str(row.get("chg", "N/A")),
                "chg_pct": str(row.get("chg_pct", "N/A")),
                "source": str(row.get("source", "")),
                "state": str(row.get("state", "")),
                "provider_id": str(row.get("provider_id", "")),
                "retrieved_at": str(row.get("retrieved_at", "")),
            }
        )
    return watchlist


QUOTE_FRESHNESS_TTL_SECONDS = 900


def _quote_age_seconds(retrieved_at: str) -> float | None:
    """Seconds since the quote was captured; None when the stamp is unusable."""
    raw = str(retrieved_at or "").strip()
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return (datetime.now(tz=UTC) - stamp).total_seconds()


def _quote_snapshot(symbol: str, market: dict[str, Any], detail: dict[str, Any]) -> dict[str, str]:
    market_status = market.get("status") if isinstance(market.get("status"), dict) else {}
    detail_status = detail.get("status") if isinstance(detail.get("status"), dict) else {}
    row = next(
        (
            item
            for item in market.get("rows", [])
            if isinstance(item, dict) and str(item.get("symbol", "")).upper() == symbol
        ),
        {},
    )
    depth = detail.get("depth") if isinstance(detail.get("depth"), dict) else {}
    bids = [item for item in depth.get("bids", []) if isinstance(item, dict)] if isinstance(depth, dict) else []
    asks = [item for item in depth.get("asks", []) if isinstance(item, dict)] if isinstance(depth, dict) else []
    source = str(row.get("source") or detail_status.get("source") or market_status.get("source") or "")
    state = str(row.get("state") or detail_status.get("state") or market_status.get("state") or "")
    provider_id = str(row.get("provider_id") or detail_status.get("provider_id") or market_status.get("provider_id") or "")
    retrieved_at = str(
        row.get("retrieved_at")
        or detail_status.get("last_update")
        or market_status.get("last_update")
        or "not refreshed"
    )
    cache_path = str(
        row.get("cache_path")
        or market_status.get("cache_path")
        or f"market_data/crypto/{symbol}/{detail_status.get('timeframe') or '15m'}.json"
    )
    # A cached row keeps the state it had WHEN CAPTURED ("live"). Carrying
    # that forward past the freshness TTL is a lie an agent will act on
    # (2026-07-17 dogfood: a MARKET order filled at a 7-day-old "live" quote).
    age = _quote_age_seconds(retrieved_at)
    if state == "live" and (age is None or age > QUOTE_FRESHNESS_TTL_SECONDS):
        state = "stale_cache"
    return {
        "symbol": symbol,
        "price": str(row.get("price") or "N/A"),
        "bid": str(row.get("bid") or (bids[0].get("price") if bids else "N/A")),
        "ask": str(row.get("ask") or (asks[0].get("price") if asks else "N/A")),
        "source": source,
        "state": state,
        "provider_id": provider_id,
        "retrieved_at": retrieved_at,
        "cache_path": cache_path,
        "timeframe": str(detail_status.get("timeframe") or "15m"),
        "paper_only": "true",
    }


def _quote_event_fields(snapshot: dict[str, str]) -> dict[str, str]:
    return {
        "quote_price": snapshot["price"],
        "quote_source": snapshot["source"],
        "quote_state": snapshot["state"],
        "quote_provider_id": snapshot["provider_id"],
        "quote_retrieved_at": snapshot["retrieved_at"],
        "quote_cache_path": snapshot["cache_path"],
    }


def _chart_from_candles(candles: list[dict[str, Any]], detail: dict[str, Any]) -> dict[str, Any]:
    detail_status = detail.get("status") if isinstance(detail.get("status"), dict) else {}
    rows = [row for row in candles[-40:] if isinstance(row, dict)]
    closes: list[Decimal] = []
    for row in rows:
        try:
            closes.append(Decimal(str(row.get("close"))))
        except (InvalidOperation, ValueError):
            continue
    return {
        "symbol": str(detail_status.get("symbol") or "BTCUSDT"),
        "timeframe": str(detail_status.get("timeframe") or "15m"),
        "source": str(detail_status.get("source") or "public_provider_unavailable"),
        "state": str(detail_status.get("state") or "unavailable"),
        "provider_id": str(detail_status.get("provider_id") or ""),
        "retrieved_at": str(detail_status.get("last_update") or "not refreshed"),
        "point_count": len(rows),
        "min_close": _money(min(closes)) if closes else "N/A",
        "max_close": _money(max(closes)) if closes else "N/A",
        "candles": rows,
    }


def _market_with_detail_fallback(market: dict[str, Any], detail: dict[str, Any]) -> dict[str, Any]:
    status = market.get("status") if isinstance(market.get("status"), dict) else {}
    detail_status = detail.get("status") if isinstance(detail.get("status"), dict) else {}
    candles = detail.get("candles") if isinstance(detail.get("candles"), list) else []
    if (
        status.get("source") not in {"offline_fixture", "public_provider_unavailable"}
        and status.get("state") not in {"offline", "unavailable"}
    ) or not candles:
        return market

    latest = candles[-1]
    symbol = str(detail_status.get("symbol") or "BTCUSDT")
    rows = [dict(row) for row in market.get("rows", []) if isinstance(row, dict)]
    replacement = {
        "symbol": symbol,
        "price": str(latest.get("close", "")),
        "chg": "0",
        "chg_pct": "0",
        "high": str(latest.get("high", "")),
        "low": str(latest.get("low", "")),
        "vol": str(latest.get("volume", "")),
        "bid": str(latest.get("close", "")),
        "ask": str(latest.get("close", "")),
        "open": str(latest.get("open", "")),
        "name": symbol,
        "source": str(detail_status.get("source") or "public_crypto_detail"),
        "state": str(detail_status.get("state") or "stale"),
        "provider_id": str(detail_status.get("provider_id") or ""),
        "retrieved_at": str(detail_status.get("last_update") or "not refreshed"),
        "cache_path": f"market_data/crypto/{symbol}/{detail_status.get('timeframe') or '15m'}.json",
    }
    replaced = False
    for index, row in enumerate(rows):
        if row.get("symbol") == symbol:
            rows[index] = {**row, **replacement}
            replaced = True
            break
    if not replaced:
        rows.insert(0, replacement)
    return {
        **market,
        "status": {
            "source": str(detail_status.get("source") or "public_crypto_detail"),
            "state": str(detail_status.get("state") or "stale"),
            "last_update": str(detail_status.get("last_update") or "not refreshed"),
            "message": "Using public crypto detail cache for route price fallback.",
            "provider_id": str(detail_status.get("provider_id") or ""),
            "cache_path": f"market_data/crypto/{symbol}/{detail_status.get('timeframe') or '15m'}.json",
            "fallback_used": True,
        },
        "rows": rows,
    }


def _paper_price(
    symbol: str,
    prices: dict[str, Decimal],
    limit_price: Decimal | None,
) -> Decimal:
    if symbol in prices:
        return prices[symbol]
    if limit_price is not None:
        return limit_price
    raise PaperOrderError("No paper price available")


def _exposure_price(
    order_type: str,
    market_price: Decimal,
    limit_price: Decimal | None,
    stop_price: Decimal | None,
) -> Decimal:
    if order_type == "MARKET":
        return market_price
    if order_type in {"LIMIT", "STOP_LIMIT"} and limit_price is not None:
        return limit_price
    if order_type == "STOP" and stop_price is not None:
        return max(market_price, stop_price)
    return market_price


def _depth_from_prices(prices: dict[str, Decimal]) -> dict[str, list[dict[str, str]]]:
    btc_price = prices.get("BTCUSDT", Decimal("0"))
    if btc_price <= 0:
        return {"bids": [], "asks": []}
    return {
        "bids": [{"price": _money(btc_price * Decimal("0.999")), "quantity": "0.50"}],
        "asks": [{"price": _money(btc_price * Decimal("1.001")), "quantity": "0.50"}],
    }


def _normalize_symbol(raw_symbol: Any) -> str:
    symbol = "".join(ch for ch in str(raw_symbol).upper() if ch.isalnum())
    if symbol not in SUPPORTED_SYMBOLS:
        raise PaperOrderError("Unsupported paper symbol")
    return symbol


def _positive_decimal(raw_value: Any, label: str) -> Decimal:
    try:
        value = Decimal(str(raw_value))
    except InvalidOperation as exc:
        raise PaperOrderError(f"{label} must be numeric") from exc
    if not value.is_finite():
        raise PaperOrderError(f"{label} must be finite")
    if value <= 0:
        raise PaperOrderError(f"{label} must be positive")
    if value > Decimal("1000000000"):
        raise PaperOrderError(f"{label} is too large")
    return value


def _optional_price(raw_value: Any) -> Decimal | None:
    if raw_value in (None, ""):
        return None
    return _positive_decimal(raw_value, "Price")


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _amount(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP).normalize())


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")
