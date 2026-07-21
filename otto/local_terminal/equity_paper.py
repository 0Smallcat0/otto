"""Equity paper ledgers — the cross-asset half of the decision loop.

The crypto paper engine proved the pattern (2026-07-17/18 dogfood): honest
fills need a fresh quote, explicit refusals, and an auditable ledger. This
module applies it to equities with one structural improvement: the fill
price is fetched live at submit time (Yahoo public chart quote), so there is
no separate refresh step and no stale-fill window at all — if the quote
cannot be fetched fresh, the order is refused.

Two books, one engine, per-market rules carried by a BookConfig instead of
being implied:

- US book (USD): MARKET-only, zero commission (US retail reality), no
  slippage model — both stated on every fill record.
- TW book (TWD): 1000-share board lots (odd lots refused, not silently
  rounded), 0.1425% brokerage per side with the NT$20 minimum, 0.3%
  securities transaction tax on sells, and a ±10% daily-limit sanity guard
  against the previous close (a quote outside the band is treated as a data
  anomaly, not filled).

Both books are long-only: no margin, short, leverage, derivatives.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any
from uuid import uuid4

from otto.local_terminal.paper_history import clean_rationale

EQUITY_QUOTE_MAX_AGE_SECONDS = 900
EQUITY_ORDER_TYPES = ("MARKET", "LIMIT")
EQUITY_FEE_NOTE = "zero-commission assumption; no slippage model"
TW_FEE_NOTE = (
    "0.1425% brokerage per side (NT$20 minimum), 0.3% transaction tax on sells; "
    "no slippage model"
)
ODD_LOT_NOTE = (
    "intraday odd-lot session pricing is not modeled; filled at the "
    "regular-session live quote with the same fee rules"
)


class EquityOrderError(ValueError):
    """A refused equity paper order (validation, staleness, or scope)."""


@dataclass(frozen=True)
class BookConfig:
    book_id: str
    asset_class: str
    currency: str
    initial_cash: Decimal
    fee_note: str
    lot_size: int | None = None
    odd_lot_allowed: bool = False
    buy_fee_rate: Decimal = Decimal("0")
    sell_fee_rate: Decimal = Decimal("0")
    min_fee: Decimal = Decimal("0")
    sell_tax_rate: Decimal = Decimal("0")
    daily_limit_pct: Decimal | None = None
    symbol_hint: str = ""


US_BOOK = BookConfig(
    book_id="equity-paper-default",
    asset_class="us_equity",
    currency="USD",
    initial_cash=Decimal("100000.00"),
    fee_note=EQUITY_FEE_NOTE,
)

TW_BOOK = BookConfig(
    book_id="tw-equity-paper-default",
    asset_class="tw_equity",
    currency="TWD",
    initial_cash=Decimal("3000000.00"),
    fee_note=TW_FEE_NOTE,
    lot_size=1000,
    odd_lot_allowed=True,
    buy_fee_rate=Decimal("0.001425"),
    sell_fee_rate=Decimal("0.001425"),
    min_fee=Decimal("20"),
    sell_tax_rate=Decimal("0.003"),
    daily_limit_pct=Decimal("10"),
    symbol_hint="use the .TW suffix, e.g. 2330.TW",
)

EQUITY_INITIAL_CASH = US_BOOK.initial_cash  # kept for existing imports/tests


def default_equity_paper_state(config: BookConfig = US_BOOK) -> dict[str, Any]:
    return {
        "account": {
            "account_id": config.book_id,
            "mode": "paper",
            "quote_asset": config.currency,
            "initial_cash": _money(config.initial_cash),
            "cash": _money(config.initial_cash),
            "equity": _money(config.initial_cash),
            "updated_at": "",
        },
        "positions": {},
        "orders": [],
        "fills": [],
        "ledger": [],
    }


def default_tw_equity_paper_state() -> dict[str, Any]:
    return default_equity_paper_state(TW_BOOK)


def normalize_equity_paper_state(
    payload: dict[str, Any], config: BookConfig = US_BOOK
) -> dict[str, Any]:
    default = default_equity_paper_state(config)
    if not isinstance(payload, dict):
        return default
    state = copy.deepcopy(default)
    account = payload.get("account")
    if isinstance(account, dict):
        state["account"].update({k: str(v) for k, v in account.items() if k in state["account"]})
    positions = payload.get("positions")
    if isinstance(positions, dict):
        for symbol, position in positions.items():
            if isinstance(position, dict) and position.get("quantity"):
                state["positions"][str(symbol)] = {
                    "symbol": str(symbol),
                    "quantity": str(position.get("quantity", "0")),
                    "avg_price": str(position.get("avg_price", "0")),
                    "realized_pnl": str(position.get("realized_pnl", "0.00")),
                }
    for key in ("orders", "fills", "ledger"):
        rows = payload.get(key)
        if isinstance(rows, list):
            state[key] = [dict(row) for row in rows if isinstance(row, dict)]
    return state


def normalize_tw_equity_paper_state(payload: dict[str, Any]) -> dict[str, Any]:
    return normalize_equity_paper_state(payload, TW_BOOK)


def place_equity_paper_order(
    state: dict[str, Any],
    request: dict[str, Any],
    quote_row: dict[str, Any] | None,
    config: BookConfig = US_BOOK,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fill a MARKET order against a just-fetched Yahoo quote row.

    The caller fetches the quote live at submit time; this function still
    re-checks freshness so a cached row can never sneak through, and applies
    the book's market rules (currency, lot size, fees/taxes, limit band).
    """
    paper_state = normalize_equity_paper_state(copy.deepcopy(state), config)
    symbol = str(request.get("symbol", "")).strip().upper()
    side = str(request.get("side", "")).upper()
    order_type = str(request.get("order_type", "MARKET")).upper()
    quantity = _positive_decimal(request.get("quantity"))
    if not symbol:
        raise EquityOrderError("Symbol is required")
    if side not in {"BUY", "SELL"}:
        raise EquityOrderError("Side must be BUY or SELL")
    if order_type not in EQUITY_ORDER_TYPES:
        raise EquityOrderError(
            "Equity paper supports MARKET and LIMIT orders; STOP is not implemented yet"
        )
    limit_price: Decimal | None = None
    if order_type == "LIMIT":
        if request.get("limit_price") is None:
            raise EquityOrderError("Limit price is required for LIMIT orders")
        limit_price = _positive_decimal(request.get("limit_price"), label="Limit price")
    lot_type: str | None = None
    if config.lot_size:
        if quantity != quantity.to_integral_value():
            raise EquityOrderError(
                f"{config.currency} equities trade in whole shares; fractional "
                "quantities are refused, never rounded"
            )
        if quantity % config.lot_size == 0:
            lot_type = "board_lot"
        elif config.odd_lot_allowed:
            lot_type = "odd_lot"
        else:
            raise EquityOrderError(
                f"{config.currency} shares trade in {config.lot_size}-share board "
                f"lots; quantity must be a multiple of {config.lot_size} (odd-lot "
                "trading is not enabled for this book, and quantities are never "
                "silently rounded)"
            )
    if not isinstance(quote_row, dict) or str(quote_row.get("symbol", "")).upper() != symbol:
        hint = f" ({config.symbol_hint})" if config.symbol_hint else ""
        raise EquityOrderError(
            f"No live quote available for {symbol}; the order was refused rather than "
            f"filled at a guessed price{hint}"
        )
    currency = str(quote_row.get("currency", "")).upper()
    if currency != config.currency:
        raise EquityOrderError(
            f"{symbol} is quoted in {currency or 'an unknown currency'}; this book "
            f"fills {config.currency}-quoted symbols only (no silent FX conversion)"
        )
    age = _age_seconds(str(quote_row.get("retrieved_at", "")))
    if age is None or age > EQUITY_QUOTE_MAX_AGE_SECONDS:
        age_text = "unknown" if age is None else f"{int(age)}s"
        raise EquityOrderError(
            f"Quote for {symbol} is not fresh (age {age_text}, limit "
            f"{EQUITY_QUOTE_MAX_AGE_SECONDS}s); refusing to fill"
        )
    price = _positive_decimal(quote_row.get("price"), label="Quote price")
    if config.daily_limit_pct is not None:
        previous = _optional_decimal(quote_row.get("previous_close"))
        if previous is not None and previous > 0:
            move_pct = abs(price / previous - 1) * 100
            if move_pct > config.daily_limit_pct:
                raise EquityOrderError(
                    f"Quote for {symbol} is {move_pct:.1f}% away from the previous "
                    f"close, outside the ±{config.daily_limit_pct}% daily limit band; "
                    "treating it as a data anomaly and refusing to fill"
                )

    cash = Decimal(paper_state["account"]["cash"])
    position = paper_state["positions"].get(symbol)
    held = Decimal(position["quantity"]) if position else Decimal("0")
    if side == "SELL" and quantity > held:
        raise EquityOrderError("Cannot sell more than the long paper position")
    # A resting BUY is checked against the limit price (its worst case);
    # cash is NOT reserved while resting — processing re-checks it.
    exposure_price = limit_price if (order_type == "LIMIT" and side == "BUY") else price
    notional = (quantity * exposure_price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fee = _trade_fee(notional, side, config)
    if side == "BUY" and notional + fee > cash:
        raise EquityOrderError("Insufficient paper cash")

    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    quote_fields = {
        "quote_price": str(quote_row.get("price", "")),
        "quote_currency": currency,
        "quote_source": str(quote_row.get("source", "")),
        "quote_provider_id": str(quote_row.get("provider_id", "")),
        "quote_retrieved_at": str(quote_row.get("retrieved_at", "")),
        "quote_age_seconds": int(age),
    }
    lot_fields: dict[str, Any] = {}
    if lot_type is not None:
        lot_fields["lot_type"] = lot_type
        if lot_type == "odd_lot":
            lot_fields["odd_lot_note"] = ODD_LOT_NOTE
    crossed = order_type == "MARKET" or _limit_satisfied(side, price, limit_price)
    if crossed:
        reason = (
            f"Equity paper market fill ({config.fee_note})"
            if order_type == "MARKET"
            else (
                f"LIMIT satisfied at submit: market {_money(price)} at or better "
                f"than limit {_money(limit_price)} ({config.fee_note})"
            )
        )
    else:
        reason = (
            "Resting LIMIT order accepted; fills at the live quote when it is at "
            "or better than the limit at processing time (equity_process_paper_orders)"
        )
    order = {
        "order_id": f"equity-{uuid4().hex[:12]}",
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": _amount(quantity),
        "limit_price": _money(limit_price) if limit_price is not None else None,
        "status": "FILLED" if crossed else "WORKING",
        "reason": reason,
        "rationale": clean_rationale(request.get("rationale")),
        "created_at": now,
        **lot_fields,
        **quote_fields,
    }
    paper_state["orders"].append(order)
    if crossed:
        _apply_equity_fill(
            paper_state, order, quantity, price, config, now, quote_fields, lot_fields
        )
    else:
        paper_state["ledger"].append(
            {
                "event_id": f"eledger-{uuid4().hex[:12]}",
                "order_id": order["order_id"],
                "event": "WORKING",
                "recorded_at": now,
                **quote_fields,
            }
        )
    paper_state["account"]["updated_at"] = now
    return paper_state, order


def _limit_satisfied(side: str, price: Decimal, limit_price: Decimal | None) -> bool:
    if limit_price is None:
        return False
    return price <= limit_price if side == "BUY" else price >= limit_price


def _apply_equity_fill(
    paper_state: dict[str, Any],
    order: dict[str, Any],
    quantity: Decimal,
    price: Decimal,
    config: BookConfig,
    now: str,
    quote_fields: dict[str, Any],
    lot_fields: dict[str, Any],
) -> dict[str, Any]:
    """Execute one fill at `price` (always the live market, never the limit)."""
    cash = Decimal(paper_state["account"]["cash"])
    symbol = str(order["symbol"])
    side = str(order["side"])
    position = paper_state["positions"].get(symbol)
    held = Decimal(position["quantity"]) if position else Decimal("0")
    notional = (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fee = _trade_fee(notional, side, config)
    tax = _sell_tax(notional, side, config)

    fill = {
        "fill_id": f"efill-{uuid4().hex[:12]}",
        "order_id": order["order_id"],
        "symbol": symbol,
        "side": side,
        "quantity": _amount(quantity),
        "price": _money(price),
        "fee": _money(fee),
        "tax": _money(tax),
        "fee_note": config.fee_note,
        "filled_at": now,
        **lot_fields,
        **quote_fields,
    }

    if side == "BUY":
        new_quantity = held + quantity
        if position:
            prior_cost = Decimal(position["avg_price"]) * held
            avg_price = (prior_cost + notional) / new_quantity
            realized = position["realized_pnl"]
        else:
            avg_price = price
            realized = "0.00"
        paper_state["positions"][symbol] = {
            "symbol": symbol,
            "quantity": _amount(new_quantity),
            "avg_price": _money(avg_price),
            "realized_pnl": realized,
        }
        paper_state["account"]["cash"] = _money(cash - notional - fee)
    else:
        proceeds = notional - fee - tax
        realized_gain = (price - Decimal(position["avg_price"])) * quantity - fee - tax
        remaining = held - quantity
        if remaining > 0:
            paper_state["positions"][symbol] = {
                **position,
                "quantity": _amount(remaining),
                "realized_pnl": _money(Decimal(position["realized_pnl"]) + realized_gain),
            }
        else:
            paper_state["positions"].pop(symbol, None)
        paper_state["account"]["cash"] = _money(cash + proceeds)

    order["status"] = "FILLED"
    paper_state["fills"].append(fill)
    paper_state["ledger"].append(
        {
            "event_id": f"eledger-{uuid4().hex[:12]}",
            "order_id": order["order_id"],
            "event": "FILLED",
            "recorded_at": now,
            **quote_fields,
        }
    )
    return fill


EQUITY_PROCESS_NOTE = (
    "Resting LIMIT orders fill at the CURRENT live quote when it is at or "
    "better than the limit at processing time — never at the limit price "
    "itself; price paths between processing runs are not simulated. Quote "
    "guards (currency, freshness, daily-limit band) apply per symbol, and an "
    "order that cannot fill safely stays WORKING with the reason reported."
)


def _quote_guard_reason(
    symbol: str,
    quote_row: dict[str, Any] | None,
    config: BookConfig,
) -> tuple[Decimal | None, dict[str, Any] | None, str | None]:
    """Same guards as submit, but returned as a skip reason instead of raised."""
    if not isinstance(quote_row, dict) or str(quote_row.get("symbol", "")).upper() != symbol:
        return None, None, "no live quote at processing time; the order stays WORKING"
    currency = str(quote_row.get("currency", "")).upper()
    if currency != config.currency:
        return None, None, (
            f"quote currency {currency or 'unknown'} does not match the "
            f"{config.currency} book"
        )
    age = _age_seconds(str(quote_row.get("retrieved_at", "")))
    if age is None or age > EQUITY_QUOTE_MAX_AGE_SECONDS:
        age_text = "unknown" if age is None else f"{int(age)}s"
        return None, None, (
            f"quote is not fresh (age {age_text}, limit "
            f"{EQUITY_QUOTE_MAX_AGE_SECONDS}s)"
        )
    try:
        price = _positive_decimal(quote_row.get("price"), label="Quote price")
    except EquityOrderError as exc:
        return None, None, str(exc)
    if config.daily_limit_pct is not None:
        previous = _optional_decimal(quote_row.get("previous_close"))
        if previous is not None and previous > 0:
            move_pct = abs(price / previous - 1) * 100
            if move_pct > config.daily_limit_pct:
                return None, None, (
                    f"quote is {move_pct:.1f}% from the previous close, outside "
                    f"the ±{config.daily_limit_pct}% daily limit band"
                )
    quote_fields = {
        "quote_price": str(quote_row.get("price", "")),
        "quote_currency": currency,
        "quote_source": str(quote_row.get("source", "")),
        "quote_provider_id": str(quote_row.get("provider_id", "")),
        "quote_retrieved_at": str(quote_row.get("retrieved_at", "")),
        "quote_age_seconds": int(age),
    }
    return price, quote_fields, None


def process_equity_paper_orders(
    state: dict[str, Any],
    quote_rows: list[dict[str, Any]] | None,
    config: BookConfig = US_BOOK,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Check every WORKING LIMIT order against a just-fetched quote row."""
    paper_state = normalize_equity_paper_state(copy.deepcopy(state), config)
    marks = {
        str(row["symbol"]).upper(): row
        for row in quote_rows or []
        if isinstance(row, dict) and row.get("symbol")
    }
    filled: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    for order in paper_state["orders"]:
        if str(order.get("status")) != "WORKING":
            continue
        symbol = str(order.get("symbol"))
        price, quote_fields, guard = _quote_guard_reason(symbol, marks.get(symbol), config)
        if guard is not None:
            skipped.append({"order_id": order["order_id"], "reason": guard})
            continue
        limit = _optional_decimal(order.get("limit_price"))
        side = str(order.get("side"))
        if not _limit_satisfied(side, price, limit):
            continue
        quantity = Decimal(order["quantity"])
        held = Decimal(paper_state["positions"].get(symbol, {}).get("quantity", "0"))
        if side == "SELL" and quantity > held:
            skipped.append(
                {
                    "order_id": order["order_id"],
                    "reason": (
                        "position is smaller than the resting quantity; order "
                        "stays WORKING"
                    ),
                }
            )
            continue
        notional = (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        fee = _trade_fee(notional, side, config)
        if side == "BUY" and notional + fee > Decimal(paper_state["account"]["cash"]):
            skipped.append(
                {
                    "order_id": order["order_id"],
                    "reason": (
                        "insufficient paper cash at processing time; order stays "
                        "WORKING"
                    ),
                }
            )
            continue
        lot_fields = {
            key: order[key] for key in ("lot_type", "odd_lot_note") if key in order
        }
        _apply_equity_fill(
            paper_state, order, quantity, price, config, now, quote_fields, lot_fields
        )
        order["reason"] = (
            f"Resting LIMIT filled: market {_money(price)} at or better than "
            f"limit {_money(limit)} ({config.fee_note})"
        )
        filled.append(
            {
                "order_id": order["order_id"],
                "symbol": symbol,
                "side": side,
                "quantity": order["quantity"],
                "fill_price": _money(price),
                "limit_price": order.get("limit_price"),
            }
        )
    paper_state["account"]["updated_at"] = now
    still_working = sum(
        1 for order in paper_state["orders"] if order["status"] == "WORKING"
    )
    report = {
        "as_of": now,
        "filled": filled,
        "skipped": skipped,
        "open_orders_remaining": still_working,
        "note": EQUITY_PROCESS_NOTE,
        "safety": {"paper_only": True, "live_execution": "disabled"},
    }
    return paper_state, report


def cancel_equity_paper_order(
    state: dict[str, Any],
    order_id: str,
    config: BookConfig = US_BOOK,
) -> tuple[dict[str, Any], dict[str, Any]]:
    paper_state = normalize_equity_paper_state(copy.deepcopy(state), config)
    order_key = str(order_id or "").strip()
    if not order_key:
        raise EquityOrderError("Order id is required")
    order = next(
        (
            entry
            for entry in paper_state["orders"]
            if str(entry.get("order_id")) == order_key
        ),
        None,
    )
    if order is None:
        raise EquityOrderError("Unknown equity paper order id")
    if str(order.get("status")) != "WORKING":
        raise EquityOrderError("Only WORKING equity paper orders can be cancelled")
    now = datetime.now(tz=UTC).isoformat(timespec="seconds")
    order["status"] = "CANCELLED"
    order["reason"] = "Cancelled locally"
    paper_state["account"]["updated_at"] = now
    paper_state["ledger"].append(
        {
            "event_id": f"eledger-{uuid4().hex[:12]}",
            "order_id": order_key,
            "event": "CANCELLED",
            "recorded_at": now,
        }
    )
    return paper_state, order


def equity_summary_payload(
    state: dict[str, Any],
    quote_rows: list[dict[str, Any]] | None = None,
    config: BookConfig = US_BOOK,
) -> dict[str, Any]:
    """~1KB decision-loop view of one equity book, marked to supplied quotes."""
    paper_state = normalize_equity_paper_state(state, config)
    marks: dict[str, dict[str, Any]] = {}
    for row in quote_rows or []:
        if isinstance(row, dict) and row.get("symbol"):
            marks[str(row["symbol"]).upper()] = row

    positions = []
    equity = Decimal(paper_state["account"]["cash"])
    for symbol, position in paper_state["positions"].items():
        quantity = Decimal(position["quantity"])
        avg_price = Decimal(position["avg_price"])
        mark = marks.get(symbol)
        last = None
        age = None
        if mark:
            last = _optional_decimal(mark.get("price"))
            age = _age_seconds(str(mark.get("retrieved_at", "")))
        mark_price = last if last is not None else avg_price
        equity += quantity * mark_price
        positions.append(
            {
                "symbol": symbol,
                "quantity": position["quantity"],
                "avg_price": position["avg_price"],
                "last_price": _money(last) if last is not None else "N/A",
                "unrealized_pnl": (
                    _money(quantity * (last - avg_price)) if last is not None else "N/A"
                ),
                "realized_pnl": position["realized_pnl"],
                "quote_age_seconds": None if age is None else int(age),
            }
        )

    initial = Decimal(paper_state["account"]["initial_cash"])
    scope: dict[str, Any] = {
        "order_types": list(EQUITY_ORDER_TYPES),
        "currency": f"{config.currency} symbols only",
        "fees": config.fee_note,
        "quote_max_age_seconds": EQUITY_QUOTE_MAX_AGE_SECONDS,
        "unmarked_positions_use_avg_price": True,
        "resting_limit_orders": (
            "fill at the live quote when at or better than the limit "
            "(equity_process_paper_orders); resting BUY cash is not reserved — "
            "re-checked at processing"
        ),
    }
    if config.lot_size:
        scope["lot_size"] = config.lot_size
        scope["odd_lot"] = (
            f"allowed — {ODD_LOT_NOTE}" if config.odd_lot_allowed else "not enabled"
        )
    if config.daily_limit_pct is not None:
        scope["daily_limit_pct"] = str(config.daily_limit_pct)
    return {
        "mode": "paper",
        "asset_class": config.asset_class,
        "as_of": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "account": {
            **paper_state["account"],
            "equity": _money(equity),
            "total_pnl": _money(equity - initial),
        },
        "positions": positions,
        "order_count": len(paper_state["orders"]),
        "recent_orders": [
            {
                "order_id": order.get("order_id"),
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "quantity": order.get("quantity"),
                "status": order.get("status"),
                "created_at": order.get("created_at"),
                "rationale": order.get("rationale"),
            }
            for order in paper_state["orders"][-3:]
        ],
        "scope": scope,
        "safety": {
            "paper_only": True,
            "live_execution": "disabled",
            "real_orders": False,
            "margin": False,
            "short": False,
        },
    }


def _trade_fee(notional: Decimal, side: str, config: BookConfig) -> Decimal:
    rate = config.buy_fee_rate if side == "BUY" else config.sell_fee_rate
    if rate <= 0:
        return Decimal("0.00")
    fee = (notional * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return max(fee, config.min_fee)


def _sell_tax(notional: Decimal, side: str, config: BookConfig) -> Decimal:
    if side != "SELL" or config.sell_tax_rate <= 0:
        return Decimal("0.00")
    return (notional * config.sell_tax_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _age_seconds(retrieved_at: str) -> float | None:
    raw = str(retrieved_at or "").strip()
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return (datetime.now(tz=UTC) - stamp).total_seconds()


def _positive_decimal(value: Any, label: str = "Quantity") -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise EquityOrderError(f"{label} must be a positive number") from None
    if parsed <= 0:
        raise EquityOrderError(f"{label} must be a positive number")
    return parsed


def _optional_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _amount(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral_value():
        return str(normalized.quantize(Decimal("1")))  # 1000, not "1E+3"
    return str(normalized)
