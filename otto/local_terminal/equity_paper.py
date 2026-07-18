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

EQUITY_QUOTE_MAX_AGE_SECONDS = 900
EQUITY_ORDER_TYPES = ("MARKET",)
EQUITY_FEE_NOTE = "zero-commission assumption; no slippage model"
TW_FEE_NOTE = (
    "0.1425% brokerage per side (NT$20 minimum), 0.3% transaction tax on sells; "
    "no slippage model"
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
            "Equity paper v1 supports MARKET orders only; LIMIT/STOP are not implemented yet"
        )
    if config.lot_size and quantity % config.lot_size != 0:
        raise EquityOrderError(
            f"{config.currency} shares trade in {config.lot_size}-share board lots; "
            f"quantity must be a multiple of {config.lot_size} (odd-lot trading is "
            "not implemented, and quantities are never silently rounded)"
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
    notional = (quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fee = _trade_fee(notional, side, config)
    tax = _sell_tax(notional, side, config)
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
    order = {
        "order_id": f"equity-{uuid4().hex[:12]}",
        "symbol": symbol,
        "side": side,
        "type": order_type,
        "quantity": _amount(quantity),
        "status": "FILLED",
        "reason": f"Equity paper market fill ({config.fee_note})",
        "created_at": now,
        **quote_fields,
    }
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

    paper_state["orders"].append(order)
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
    paper_state["account"]["updated_at"] = now
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
    }
    if config.lot_size:
        scope["lot_size"] = config.lot_size
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
