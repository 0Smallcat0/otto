"""Journaled recommendation ledger — the owner's stated goal, made concrete.

The owner trades real money by hand and wants the terminal to *collect, think,
and hand back a reasoned judgment he can reference* — not to manage toy paper
books that mostly sit in cash and "beat" a dipping index by not participating.

This module is that ledger. Each entry is a dated, reasoned call on one
instrument: a stance (accumulate / reduce / avoid / hold), the thesis behind
it, an entry zone, the price level that would prove it wrong, a conviction and
a horizon. The call records the instrument's price at the moment it was made.
Later, once the horizon elapses (or the invalidation level is breached first),
the call is scored against the *real* subsequent price — so the ledger builds
an honest track record of whether the judgments were any good, per stance and
overall. The owner reads it and decides with his own money; nothing here places
an order or touches real funds.

Honesty rules, carried over from the fill/snapshot paths:
- a call stores the exact price it was struck at; scoring uses real marks, and
  a call with no usable mark is reported as unscored, never graded as zero
- moves inside a flat band are graded "flat"/"range", not counted as skill, so
  noise cannot inflate the hit rate
- a breached invalidation closes the call as "invalidated" regardless of where
  price lands later — being stopped out is not retroactively a win
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

# Cap on stored calls; oldest are dropped first and reads report the retained
# window so truncation is never silent.
MAX_CALLS = 2000

# Moves smaller than this (in %) are noise, not a correct call. A stance that
# "wins" by 0.3% over its horizon proves nothing; grading it as skill would be
# the cash-artifact "win" all over again.
SCORE_FLAT_BAND_PCT = Decimal("1.5")

THESIS_MAX_CHARS = 800

STANCES = ("accumulate", "reduce", "avoid", "hold")
CONVICTIONS = ("low", "medium", "high")
MARKETS = ("crypto", "us_equity", "tw_equity")

# Self-sourced universe: the terminal decides what to look at, so the owner is
# never asked to feed tickers. Yahoo-style symbols throughout (crypto as -USD)
# so a single quote path prices every entry. Liquid, well-known names only.
DEFAULT_UNIVERSE: dict[str, tuple[str, str]] = {
    # TW equity
    "2330.TW": ("tw_equity", "TSMC"),
    "2317.TW": ("tw_equity", "Hon Hai"),
    "2454.TW": ("tw_equity", "MediaTek"),
    "2308.TW": ("tw_equity", "Delta Electronics"),
    "2412.TW": ("tw_equity", "Chunghwa Telecom"),
    "0050.TW": ("tw_equity", "Yuanta Taiwan 50 ETF"),
    # US equity
    "AAPL": ("us_equity", "Apple"),
    "MSFT": ("us_equity", "Microsoft"),
    "NVDA": ("us_equity", "NVIDIA"),
    "GOOGL": ("us_equity", "Alphabet"),
    "AMZN": ("us_equity", "Amazon"),
    "SPY": ("us_equity", "S&P 500 ETF"),
    "QQQ": ("us_equity", "Nasdaq 100 ETF"),
    # crypto
    "BTC-USD": ("crypto", "Bitcoin"),
    "ETH-USD": ("crypto", "Ethereum"),
    "SOL-USD": ("crypto", "Solana"),
}


class ResearchLedgerError(ValueError):
    """Raised when a call cannot be recorded (bad stance, missing price, ...)."""


def clean_thesis(value: Any) -> str | None:
    """Normalize an agent-supplied thesis (strip, cap, empty→None)."""
    if value is None:
        return None
    text = str(value).strip()
    return text[:THESIS_MAX_CHARS] or None


def default_research_ledger_state() -> dict[str, Any]:
    return {"calls": []}


def normalize_research_ledger_state(payload: Any) -> dict[str, Any]:
    state = payload if isinstance(payload, dict) else {}
    raw = state.get("calls")
    calls = [entry for entry in raw if isinstance(entry, dict)] if isinstance(raw, list) else []
    return {"calls": calls[-MAX_CALLS:]}


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        dec = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return dec if dec.is_finite() else None


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def record_call(state: dict[str, Any], payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate and append one reasoned call. Requires a real reference price."""
    ledger = normalize_research_ledger_state(state)

    symbol = str(payload.get("symbol", "")).strip().upper()
    if not symbol:
        raise ResearchLedgerError("symbol is required")

    stance = str(payload.get("stance", "")).strip().lower()
    if stance not in STANCES:
        raise ResearchLedgerError(f"stance must be one of {STANCES}")

    conviction = str(payload.get("conviction", "medium")).strip().lower()
    if conviction not in CONVICTIONS:
        raise ResearchLedgerError(f"conviction must be one of {CONVICTIONS}")

    market = payload.get("market")
    if market is None and symbol in DEFAULT_UNIVERSE:
        market = DEFAULT_UNIVERSE[symbol][0]
    market = str(market or "").strip().lower()
    if market not in MARKETS:
        raise ResearchLedgerError(f"market must be one of {MARKETS}")

    thesis = clean_thesis(payload.get("thesis"))
    if not thesis:
        raise ResearchLedgerError("thesis is required — a call with no reasoning is not a call")

    ref_price = _decimal(payload.get("ref_price"))
    if ref_price is None or ref_price <= 0:
        raise ResearchLedgerError("ref_price (a live mark at call time) is required")

    invalidation = _decimal(payload.get("invalidation"))
    entry_low = _decimal(payload.get("entry_low"))
    entry_high = _decimal(payload.get("entry_high"))
    horizon_days = _positive_int(payload.get("horizon_days"), default=30)

    name = payload.get("name")
    if not name and symbol in DEFAULT_UNIVERSE:
        name = DEFAULT_UNIVERSE[symbol][1]

    evidence = payload.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else None

    now = datetime.now(tz=UTC)
    call = {
        "call_id": f"call-{uuid4().hex[:12]}",
        "as_of": now.isoformat(timespec="seconds"),
        "symbol": symbol,
        "name": str(name) if name else None,
        "market": market,
        "stance": stance,
        "conviction": conviction,
        "thesis": thesis,
        "ref_price": str(ref_price),
        "entry_low": str(entry_low) if entry_low is not None else None,
        "entry_high": str(entry_high) if entry_high is not None else None,
        "invalidation": str(invalidation) if invalidation is not None else None,
        "horizon_days": horizon_days,
        "matures_at": (now + timedelta(days=horizon_days)).isoformat(timespec="seconds"),
        "evidence": evidence,
        "status": "open",
        "scored_at": None,
        "score_price": None,
        "realized_pct": None,
        "favor_pct": None,
        "outcome": None,
    }
    ledger["calls"].append(call)
    return normalize_research_ledger_state(ledger), call


def _favor_pct(stance: str, ref: Decimal, price: Decimal) -> Decimal:
    """Return the move in the call's favor, in %.

    accumulate: right when price rises. reduce/avoid: right when price falls.
    hold: the *absolute* move (small = the range-bound thesis held).
    """
    raw = (price / ref - 1) * 100
    if stance == "accumulate":
        return raw
    if stance in ("reduce", "avoid"):
        return -raw
    return abs(raw)  # hold


def _invalidation_breached(stance: str, invalidation: Decimal | None, price: Decimal) -> bool:
    if invalidation is None:
        return False
    if stance == "accumulate":
        return price <= invalidation  # fell through the stop
    if stance in ("reduce", "avoid"):
        return price >= invalidation  # rose through the level it "wouldn't"
    return False  # hold has no single-sided invalidation here


def _outcome(stance: str, favor: Decimal, breached: bool) -> str:
    if breached:
        return "invalidated"
    band = SCORE_FLAT_BAND_PCT
    if stance == "hold":
        # favor is the absolute move; the thesis was "stays put".
        return "worked" if favor <= band else "moved"
    if favor > band:
        return "worked"
    if favor < -band:
        return "failed"
    return "flat"


def _is_mature(call: dict[str, Any], now: datetime) -> bool:
    matures_at = call.get("matures_at")
    try:
        stamp = datetime.fromisoformat(str(matures_at))
    except (TypeError, ValueError):
        return False
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return now >= stamp


def score_calls(
    state: dict[str, Any],
    marks: dict[str, Decimal | None],
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Close every open call that has matured or been invalidated.

    `marks` maps symbol→current price. A matured call with no usable mark is
    left open (reported unscored), never graded. An open call whose
    invalidation is breached is closed early even before its horizon.
    """
    ledger = normalize_research_ledger_state(state)
    now = now or datetime.now(tz=UTC)
    scored: list[dict[str, Any]] = []
    for call in ledger["calls"]:
        if call.get("status") != "open":
            continue
        price = marks.get(str(call.get("symbol", "")))
        ref = _decimal(call.get("ref_price"))
        if price is None or ref is None or ref <= 0 or price <= 0:
            continue
        stance = str(call.get("stance"))
        invalidation = _decimal(call.get("invalidation"))
        breached = _invalidation_breached(stance, invalidation, price)
        if not breached and not _is_mature(call, now):
            continue  # still running, thesis intact
        favor = _favor_pct(stance, ref, price)
        call["status"] = "scored"
        call["scored_at"] = now.isoformat(timespec="seconds")
        call["score_price"] = str(price)
        call["realized_pct"] = f"{(price / ref - 1) * 100:.2f}"
        call["favor_pct"] = f"{favor:.2f}"
        call["outcome"] = _outcome(stance, favor, breached)
        scored.append(call)
    return normalize_research_ledger_state(ledger), scored


def _open_view(call: dict[str, Any], price: Decimal | None) -> dict[str, Any]:
    row = dict(call)
    ref = _decimal(call.get("ref_price"))
    if price is not None and ref is not None and ref > 0:
        favor = _favor_pct(str(call.get("stance")), ref, price)
        row["mark_price"] = str(price)
        row["unrealized_pct"] = f"{(price / ref - 1) * 100:.2f}"
        row["unrealized_favor_pct"] = f"{favor:.2f}"
    else:
        row["mark_price"] = None
        row["unrealized_pct"] = None
        row["unrealized_favor_pct"] = None
    return row


def _scorecard(scored: list[dict[str, Any]]) -> dict[str, Any]:
    """Honest hit rate: flat/range calls are excluded from the win/loss base."""
    graded = [c for c in scored if c.get("outcome") in ("worked", "failed", "invalidated", "moved")]
    wins = sum(1 for c in graded if c.get("outcome") == "worked")
    decided = [c for c in graded if c.get("outcome") in ("worked", "failed", "invalidated", "moved")]
    favors = [_decimal(c.get("favor_pct")) for c in scored]
    favors = [f for f in favors if f is not None]
    by_stance: dict[str, dict[str, int]] = {}
    for c in scored:
        st = str(c.get("stance"))
        bucket = by_stance.setdefault(st, {"worked": 0, "failed": 0, "invalidated": 0, "flat": 0, "moved": 0})
        outcome = str(c.get("outcome"))
        if outcome in bucket:
            bucket[outcome] += 1
    return {
        "scored_count": len(scored),
        "decided_count": len(decided),
        "win_count": wins,
        "hit_rate_pct": f"{(wins / len(decided) * 100):.1f}" if decided else None,
        "avg_favor_pct": f"{(sum(favors) / len(favors)):.2f}" if favors else None,
        "by_stance": by_stance,
    }


def research_ledger_payload(
    state: dict[str, Any],
    marks: dict[str, Decimal | None] | None = None,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    ledger = normalize_research_ledger_state(state)
    calls = ledger["calls"]
    marks = marks or {}
    open_calls = [c for c in calls if c.get("status") == "open"]
    scored_calls = [c for c in calls if c.get("status") == "scored"]
    if limit is not None:
        limit = max(1, int(limit))
        scored_view = scored_calls[-limit:]
    else:
        scored_view = scored_calls
    open_view = [_open_view(c, marks.get(str(c.get("symbol", "")))) for c in open_calls]
    return {
        "as_of": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "call_count_total": len(calls),
        "open_count": len(open_calls),
        "scored_count": len(scored_calls),
        "max_calls_retained": MAX_CALLS,
        "open_calls": open_view,
        "scored_calls": scored_view,
        "scorecard": _scorecard(scored_calls),
        "universe_size": len(DEFAULT_UNIVERSE),
        "score_flat_band_pct": str(SCORE_FLAT_BAND_PCT),
        "record_action": "research_call_record",
        "score_action": "research_calls_score",
        "purpose": (
            "Reasoned, journaled judgments for the owner to reference for his own "
            "manual trades. Analysis, not licensed advice; nothing here executes."
        ),
        "safety": {"paper_only": True, "live_execution": "disabled"},
    }
