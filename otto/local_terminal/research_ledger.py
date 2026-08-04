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

# "size_down" is a risk view, not a directional one: it says a position is too
# large for the book, without claiming to know which way it goes. It exists
# because the owner's real book held one name at 63.5% while every directional
# stance would have misrepresented that as a bearish call (2026-07-25).
STANCES = ("accumulate", "reduce", "avoid", "hold", "size_down")

# A concentration warning is not a prediction, so it is never graded right or
# wrong by direction. It is only asked, at horizon: did the oversized position
# actually inflict a material drawdown on the book?
RISK_MATERIAL_DROP_PCT = Decimal("10")

# When an open call deserves a fresh look rather than silent drift toward its
# horizon: the market left the price it was struck at, the invalidation is
# closing in, or the clock has nearly run out.
REVIEW_DRIFT_PCT = Decimal("5")
REVIEW_INVALIDATION_PROXIMITY_PCT = Decimal("25")
REVIEW_HORIZON_ELAPSED_PCT = Decimal("80")

# Scoring reads the price at the moment it runs, so a call scored long after it
# matured is measured over a window its thesis never claimed. Nothing guarantees
# a run happens on the day a call comes due — the scheduler is session-bound and
# has silently missed days before — so late scoring is the normal case, not the
# exception. Beyond this share of the horizon the measured window is not the
# stated one, and grading it as a hit or a miss would put a number on something
# the call never said.
LATE_SCORE_TOLERANCE = Decimal("0.2")
CONVICTIONS = ("low", "medium", "high")
MARKETS = ("crypto", "us_equity", "tw_equity")

# "Did the judgment beat owning the market" is the question the owner actually
# asked, and a hit rate cannot answer it: 2330 was graded a pure loss at -6.58%
# over a window the index fell further, while a hold that loses less than the
# alternative is not a failure. Same three symbols the paper books already
# benchmark against, so one convention covers both ledgers.
BENCHMARK_BY_MARKET: dict[str, str] = {
    "tw_equity": "0050.TW",
    "us_equity": "SPY",
    "crypto": "BTC-USD",
}

# How a benchmark level got onto a call. Stamped at strike time from the same
# live quote path as ref_price, or reconstructed afterwards from the published
# daily close. The two are not the same measurement and a scorecard that mixes
# them without saying so is overstating what it knows: a close is the market's
# level at the end of that session, not at the minute the judgment was struck,
# and for a call struck on a non-trading day it is the previous session's.
BENCHMARK_SOURCE_LIVE = "stamped_live"
BENCHMARK_SOURCE_BACKFILL = "backfill_daily_close"
# A call ON its own benchmark needs no reconstruction at all: the index leg and
# the instrument leg are the same instrument at the same instant, so the call's
# own prices ARE the benchmark's. Taking a daily close here instead would price
# the two legs off different clocks and manufacture an excess return for a thing
# against itself — 64,098 (close) against 65,338 (strike) is 1.9% of nothing.
BENCHMARK_SOURCE_SELF = "same_instrument"

# Whether beating the benchmark means outrunning it or lagging it. A call that
# means to own something wins by outperforming; one that means to stay out wins
# when the thing it avoided lagged the market. size_down is absent on purpose:
# a concentration warning makes no claim about relative return.
_BENCHMARK_WIN_ABOVE = {"accumulate": True, "hold": True, "reduce": False, "avoid": False}

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

    # Sizing views carry the numbers that justify them: what share of the book
    # the position is, and the cap it breaches. A size_down call without a
    # weight is just an opinion, so it is refused.
    weight_pct = _decimal(payload.get("weight_pct"))
    cap_pct = _decimal(payload.get("cap_pct"))
    if stance == "size_down" and weight_pct is None:
        raise ResearchLedgerError("size_down requires weight_pct — the position's share of the book")

    # Replacing a view was only ever a convention in the operating prompt, so a
    # revised call simply piled up next to the old one: the owner's largest
    # holding ended up listed three times with three different invalidation
    # levels, which reads as a broken ledger rather than a changed mind. A
    # supersede is now recorded on both sides.
    supersedes = str(payload.get("supersedes") or "").strip()
    superseded: dict[str, Any] | None = None
    if supersedes:
        superseded = next(
            (c for c in ledger["calls"] if str(c.get("call_id")) == supersedes), None
        )
        if superseded is None:
            raise ResearchLedgerError(f"supersedes: no call {supersedes} in the ledger")
        if superseded.get("status") != "open":
            raise ResearchLedgerError(
                f"supersedes: call {supersedes} is {superseded.get('status')}, not open"
            )

    name = payload.get("name")
    if not name and symbol in DEFAULT_UNIVERSE:
        name = DEFAULT_UNIVERSE[symbol][1]

    evidence = payload.get("evidence")
    evidence = evidence if isinstance(evidence, dict) else None

    benchmark_symbol = BENCHMARK_BY_MARKET.get(market)
    benchmark_ref = _decimal(payload.get("benchmark_price"))
    if benchmark_ref is not None and benchmark_ref <= 0:
        benchmark_ref = None

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
        "weight_pct": f"{weight_pct:.2f}" if weight_pct is not None else None,
        "cap_pct": f"{cap_pct:.2f}" if cap_pct is not None else None,
        "horizon_days": horizon_days,
        "matures_at": (now + timedelta(days=horizon_days)).isoformat(timespec="seconds"),
        "evidence": evidence,
        "supersedes": supersedes or None,
        # The market's price at the same instant, so scoring can answer "did
        # this beat owning the index" rather than only "did it go up". It has
        # to be stamped now: a benchmark level for a past date cannot be
        # recovered from a live quote later.
        "benchmark_symbol": benchmark_symbol,
        "benchmark_ref_price": str(benchmark_ref) if benchmark_ref is not None else None,
        "benchmark_ref_source": BENCHMARK_SOURCE_LIVE if benchmark_ref is not None else None,
        "status": "open",
        "scored_at": None,
        "score_price": None,
        "realized_pct": None,
        "favor_pct": None,
        "benchmark_score_price": None,
        "benchmark_pct": None,
        "excess_pct": None,
        "beat_benchmark": None,
        "outcome": None,
    }
    if superseded is not None:
        # Withdrawn, not judged: the thesis was replaced because its premise
        # changed, so scoring it later would grade a view no longer held. It
        # stays in the ledger — the record of having changed one's mind is part
        # of the track record — but leaves the open list and the scorecard.
        superseded["status"] = "superseded"
        superseded["superseded_by"] = call["call_id"]
        superseded["superseded_at"] = call["as_of"]
    ledger["calls"].append(call)
    return normalize_research_ledger_state(ledger), call


def _favor_pct(stance: str, ref: Decimal, price: Decimal) -> Decimal | None:
    """Return the move in the call's favor, in %.

    accumulate: right when price rises. reduce/avoid: right when price falls.
    hold: the *absolute* move (small = the range-bound thesis held).
    size_down: None — a concentration warning makes no directional claim, so
    grading it by price direction would invent an edge it never asserted.
    """
    raw = (price / ref - 1) * 100
    if stance == "accumulate":
        return raw
    if stance in ("reduce", "avoid"):
        return -raw
    if stance == "size_down":
        return None
    return abs(raw)  # hold


def _invalidation_breached(
    stance: str,
    invalidation: Decimal | None,
    price: Decimal,
    ref_price: Decimal | None = None,
) -> bool:
    """Whether the market has crossed the level the call named as "I was wrong".

    A hold used to be exempt, on the reasoning that holding has no single
    side. In practice every hold written here named a one-sided level —
    00982A below 19.5, 2330 below 2200, AAPL below 315 — and the wall renders
    them as 跌破 X, inferring the side from where the level sits against the
    price it was struck at. Only the scorer disagreed, so on 2026-07-29 the
    00982A hold traded through the 19.5 it had named and the ledger settled
    nothing: the call would have drifted to its 08-27 horizon and scored on
    whatever price happened to be there, measuring a window its thesis never
    claimed. A promise shown on screen has to be kept by the engine.

    The side comes from the same inference the UI already makes, so no new
    field and no disagreement between what is displayed and what is scored.
    """
    if invalidation is None:
        return False
    if stance == "accumulate":
        return price <= invalidation  # fell through the stop
    if stance in ("reduce", "avoid"):
        return price >= invalidation  # rose through the level it "wouldn't"
    if stance == "hold":
        if ref_price is None:
            return False  # nothing to infer the side from — never guess
        if invalidation < ref_price:
            return price <= invalidation  # a floor: falling through it is the miss
        if invalidation > ref_price:
            return price >= invalidation  # a ceiling
        return False  # struck exactly at its own invalidation: no side to read
    return False  # size_down is scored on realised risk, not on a level


def _outcome(
    stance: str, favor: Decimal | None, breached: bool, realized: Decimal | None = None
) -> str:
    if breached:
        return "invalidated"
    if stance == "size_down":
        # Never right/wrong by direction — only whether the oversized position
        # actually inflicted a material drawdown while it stayed oversized.
        if realized is not None and realized <= -RISK_MATERIAL_DROP_PCT:
            return "risk_realized"
        return "risk_not_realized"
    band = SCORE_FLAT_BAND_PCT
    if favor is None:
        return "flat"
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


def _scoring_lateness(
    call: dict[str, Any], now: datetime, *, breached: bool
) -> tuple[int, bool]:
    """How late this scoring run is, and whether the stated window still holds.

    An invalidation breach is an event, not a deadline: it is scored whenever
    price crosses the level, so it is never "late". A horizon call is different
    — scored days after it matured, it measures a window the thesis never
    claimed, and that must be visible instead of quietly counted.
    """
    if breached:
        return 0, True
    try:
        matured = datetime.fromisoformat(str(call.get("matures_at")))
    except (TypeError, ValueError):
        return 0, True
    matured = matured if matured.tzinfo else matured.replace(tzinfo=UTC)
    late_days = max((now - matured).total_seconds() / 86400, 0)
    horizon = call.get("horizon_days")
    try:
        horizon_days = Decimal(str(int(horizon)))
    except (TypeError, ValueError):
        return int(late_days), True
    if horizon_days <= 0:
        return int(late_days), True
    honored = Decimal(str(late_days)) / horizon_days <= LATE_SCORE_TOLERANCE
    return int(late_days), honored


def _score_against_benchmark(
    call: dict[str, Any], marks: dict[str, Decimal | None], realized: Decimal
) -> None:
    """Measure the call against owning the market over the same window.

    Everything stays None unless both benchmark prices are real: a window with
    no benchmark is reported unmeasured, never scored as if the market had been
    flat. A call ON the benchmark itself gets its excess (zero by construction)
    but no beat_benchmark verdict — 0050 cannot outperform 0050.
    """
    symbol = str(call.get("benchmark_symbol") or "")
    bench_ref = _decimal(call.get("benchmark_ref_price"))
    bench_now = marks.get(symbol) if symbol else None
    if not symbol or bench_ref is None or bench_ref <= 0 or bench_now is None or bench_now <= 0:
        return
    bench_pct = (bench_now / bench_ref - 1) * 100
    excess = realized - bench_pct
    call["benchmark_score_price"] = str(bench_now)
    call["benchmark_pct"] = f"{bench_pct:.2f}"
    call["excess_pct"] = f"{excess:.2f}"
    win_above = _BENCHMARK_WIN_ABOVE.get(str(call.get("stance")))
    if win_above is None or str(call.get("symbol")) == symbol:
        return
    call["beat_benchmark"] = excess > 0 if win_above else excess < 0


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
        breached = _invalidation_breached(stance, invalidation, price, ref)
        if not breached and not _is_mature(call, now):
            continue  # still running, thesis intact
        favor = _favor_pct(stance, ref, price)
        realized = (price / ref - 1) * 100
        late_days, window_honored = _scoring_lateness(call, now, breached=breached)
        call["status"] = "scored"
        call["scored_at"] = now.isoformat(timespec="seconds")
        call["score_price"] = str(price)
        call["realized_pct"] = f"{realized:.2f}"
        call["favor_pct"] = f"{favor:.2f}" if favor is not None else None
        call["outcome"] = _outcome(stance, favor, breached, realized)
        call["scored_late_days"] = late_days
        call["window_honored"] = window_honored
        _score_against_benchmark(call, marks, realized)
        scored.append(call)
    return normalize_research_ledger_state(ledger), scored


def _close_on_or_before(series: dict[str, Any], day: str) -> tuple[str, Decimal] | None:
    """The last published close up to and including `day`.

    A call struck on a Saturday, or before an exchange holiday, has no close of
    its own; the level it was actually struck against is the previous session's.
    Returning the date alongside the price is what lets the caller record which
    session it really used instead of implying the call's own date.
    """
    usable = [(d, _decimal(p)) for d, p in series.items() if d <= day]
    usable = [(d, p) for d, p in usable if p is not None and p > 0]
    if not usable:
        return None
    return max(usable, key=lambda row: row[0])


def backfill_benchmarks(
    state: dict[str, Any],
    closes: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconstruct benchmark levels for calls struck before they were stamped.

    Benchmark stamping shipped on 2026-07-30; every call journaled before it
    carries no index level on either end, so the question the ledger exists to
    answer — did this beat owning the market — was structurally unanswerable for
    the whole existing record. A live quote genuinely cannot recover a past
    level, which is what the record path warns about, but a published daily
    close can: it is a fact the exchange printed, not a reconstruction.

    What it will not do: overwrite a level stamped live (that measurement is
    strictly better), touch a superseded call (withdrawn views are never
    scored), or leave the result indistinguishable from a live stamp — every
    filled call carries benchmark_ref_source and the date of the session
    actually used.
    """
    ledger = normalize_research_ledger_state(state)
    filled: list[dict[str, Any]] = []
    unfilled: list[dict[str, Any]] = []
    skipped_stamped = 0
    skipped_superseded = 0
    for call in ledger["calls"]:
        status = str(call.get("status"))
        if status not in ("open", "scored"):
            skipped_superseded += 1
            continue
        if call.get("benchmark_ref_price") is not None:
            skipped_stamped += 1
            continue
        symbol = call.get("benchmark_symbol") or BENCHMARK_BY_MARKET.get(
            str(call.get("market") or "")
        )
        if symbol is not None and str(call.get("symbol")) == str(symbol):
            # Identity, not reconstruction. Both legs are already on the call.
            call["benchmark_symbol"] = symbol
            call["benchmark_ref_price"] = call.get("ref_price")
            call["benchmark_ref_source"] = BENCHMARK_SOURCE_SELF
            realized_self = _decimal(call.get("realized_pct"))
            score_price = _decimal(call.get("score_price"))
            if status == "scored" and realized_self is not None and score_price is not None:
                _score_against_benchmark(call, {symbol: score_price}, realized_self)
            filled.append(
                {
                    "call_id": call.get("call_id"),
                    "symbol": call.get("symbol"),
                    "status": status,
                    "benchmark_symbol": symbol,
                    "source": BENCHMARK_SOURCE_SELF,
                    "ref_price": call.get("ref_price"),
                    "excess_pct": call.get("excess_pct"),
                    "beat_benchmark": call.get("beat_benchmark"),
                }
            )
            continue
        series = closes.get(str(symbol or ""))
        as_of = str(call.get("as_of") or "")[:10]
        found = _close_on_or_before(series, as_of) if series and as_of else None
        if symbol is None or found is None:
            unfilled.append(
                {
                    "call_id": call.get("call_id"),
                    "symbol": call.get("symbol"),
                    "reason": "no benchmark for market" if symbol is None else "no close at or before as_of",
                }
            )
            continue
        ref_day, ref_price = found
        call["benchmark_symbol"] = symbol
        call["benchmark_ref_price"] = str(ref_price)
        call["benchmark_ref_source"] = BENCHMARK_SOURCE_BACKFILL
        call["benchmark_ref_session"] = ref_day
        row = {
            "call_id": call.get("call_id"),
            "symbol": call.get("symbol"),
            "status": status,
            "benchmark_symbol": symbol,
            "ref_session": ref_day,
            "ref_price": str(ref_price),
        }
        realized = _decimal(call.get("realized_pct"))
        scored_day = str(call.get("scored_at") or "")[:10]
        if status == "scored" and realized is not None and scored_day:
            scored_found = _close_on_or_before(series, scored_day)
            if scored_found is None:
                row["score_note"] = "no close at or before scored_at; verdict left unmeasured"
            else:
                score_day, score_price = scored_found
                # Same arithmetic the live path uses, fed a historical close
                # instead of a live mark, so a backfilled verdict and a stamped
                # one can never disagree about what beating the index means.
                _score_against_benchmark(call, {symbol: score_price}, realized)
                call["benchmark_score_session"] = score_day
                row["score_session"] = score_day
                row["excess_pct"] = call.get("excess_pct")
                row["beat_benchmark"] = call.get("beat_benchmark")
        filled.append(row)
    report = {
        "filled_count": len(filled),
        "filled": filled,
        "unfilled_count": len(unfilled),
        "unfilled": unfilled,
        "skipped_already_stamped": skipped_stamped,
        "skipped_superseded": skipped_superseded,
        "source": BENCHMARK_SOURCE_BACKFILL,
        "note": (
            "A daily close is the market's level at the end of that session, not "
            "at the minute the call was struck; a call struck on a non-trading "
            "day uses the previous session, named in benchmark_ref_session. "
            "Every filled call is marked so the scorecard can say how much of "
            "its verdict rests on reconstruction rather than a live stamp."
        ),
    }
    return normalize_research_ledger_state(ledger), report


def _review_reasons(
    call: dict[str, Any],
    price: Decimal | None,
    now: datetime,
    weight: Decimal | None = None,
) -> list[str]:
    """Why an open call deserves a fresh look before its horizon runs out.

    A view recorded once and never revisited quietly rots: the price it was
    struck at stops resembling the market, the invalidation creeps closer, or
    the horizon nearly elapses and the call scores on a thesis nobody
    re-examined. These flags make the daily round a review instead of a
    read-out. They say "think again", never "the call is wrong".
    """
    reasons: list[str] = []
    ref = _decimal(call.get("ref_price"))
    if price is not None and ref is not None and ref > 0:
        drift = abs((price / ref - 1) * 100)
        if drift >= REVIEW_DRIFT_PCT:
            reasons.append(f"price moved {drift:.1f}% from the {ref} it was struck at")
        invalidation = _decimal(call.get("invalidation"))
        stance = str(call.get("stance"))
        if invalidation is not None and stance in ("accumulate", "reduce", "avoid"):
            span = abs(ref - invalidation)
            if span > 0:
                left = abs(price - invalidation) / span * 100
                if left <= REVIEW_INVALIDATION_PROXIMITY_PCT and not _invalidation_breached(
                    stance, invalidation, price
                ):
                    reasons.append(f"within {left:.0f}% of its invalidation at {invalidation}")
    # A call that means to transact names the band it would transact in. Once
    # the market leaves it the instruction is void, and none of the rules above
    # notice: 0050 sat at 97.15 against a 98-101 accumulate band for days at
    # 4.3% drift and 33% of its invalidation span, under both thresholds, and
    # would have scored on an instruction nobody could have followed.
    #
    # Only for stances that intend to act. On a hold or an avoid the band is a
    # conditional "if it comes back to here" — AAPL said hold, do not chase,
    # look for a pullback to 320-328, and the pullback never came. Nothing
    # about that view went stale, but unlike drift, invalidation proximity and
    # elapsed horizon, a passed band never un-passes: the flag would have sat
    # amber for the twenty-six days to maturity, which is how a warning stops
    # being read (2026-07-28, narrowing the rule shipped the round before).
    # A sizing call names the weight it was struck at; the risk it warns about
    # is the weight now. 2834 was 63.5% of the book when the warning was written
    # and 67.2% four days later — the concentration moved further from the cap
    # while nothing flagged it, and none of the rules above can see it: a sizing
    # call has no invalidation and no entry band, so only the horizon could ever
    # fire. Growth only: a position shrinking back toward the cap is the warning
    # working, not a reason to re-examine it. Same REVIEW_DRIFT_PCT as the price
    # rule, so "drifted materially from where it was struck" means one thing on
    # this board.
    if str(call.get("stance")) == "size_down":
        struck_weight = _decimal(call.get("weight_pct"))
        if weight is not None and struck_weight is not None and struck_weight > 0:
            growth = (weight / struck_weight - 1) * 100
            if growth >= REVIEW_DRIFT_PCT:
                reasons.append(
                    f"the position grew to {weight:.2f}% of the book, {growth:.1f}% "
                    f"above the {struck_weight}% the warning was struck at"
                )
    low, high = _decimal(call.get("entry_low")), _decimal(call.get("entry_high"))
    if price is not None and str(call.get("stance")) in ("accumulate", "reduce"):
        if low is not None and price < low:
            reasons.append(f"price {price} is below its {low} entry, so the staged entry is void")
        elif high is not None and price > high:
            reasons.append(f"price {price} ran past its {high} entry, so the staged entry is void")
    matures_at, as_of = call.get("matures_at"), call.get("as_of")
    try:
        end = datetime.fromisoformat(str(matures_at))
        start = datetime.fromisoformat(str(as_of))
    except (TypeError, ValueError):
        return reasons
    end = end if end.tzinfo else end.replace(tzinfo=UTC)
    start = start if start.tzinfo else start.replace(tzinfo=UTC)
    total = (end - start).total_seconds()
    if total > 0:
        elapsed = (now - start).total_seconds() / total * 100
        if elapsed >= REVIEW_HORIZON_ELAPSED_PCT:
            reasons.append(f"{elapsed:.0f}% of its horizon has elapsed")
    return reasons


def _open_view(
    call: dict[str, Any],
    price: Decimal | None,
    now: datetime | None = None,
    weight: Decimal | None = None,
) -> dict[str, Any]:
    row = dict(call)
    reasons = _review_reasons(call, price, now or datetime.now(tz=UTC), weight)
    row["needs_review"] = bool(reasons)
    row["review_reasons"] = reasons
    # A sizing call's weight_pct is what the position weighed when the warning
    # was written; the risk it warns about is what the position weighs now. The
    # board showed only the first, in the present tense, so a concentration that
    # had grown since read as if it had not moved. Same shape as ref_price vs
    # mark_price, for the one stance that makes a claim about size.
    row["mark_weight_pct"] = f"{weight:.2f}" if weight is not None else None
    ref = _decimal(call.get("ref_price"))
    if price is not None and ref is not None and ref > 0:
        favor = _favor_pct(str(call.get("stance")), ref, price)
        row["mark_price"] = str(price)
        row["unrealized_pct"] = f"{(price / ref - 1) * 100:.2f}"
        row["unrealized_favor_pct"] = f"{favor:.2f}" if favor is not None else None
    else:
        row["mark_price"] = None
        row["unrealized_pct"] = None
        row["unrealized_favor_pct"] = None
    return row


DECIDED_OUTCOMES = ("worked", "failed", "invalidated", "moved")


def _benchmark_scorecard(timely: list[dict[str, Any]]) -> dict[str, Any]:
    """Did the judgments beat owning the index — the question a hit rate can't answer.

    Only calls carrying a verdict count. A call struck before the benchmark was
    stamped, or one whose benchmark quote was missing at scoring, is unmeasured
    and counted as such rather than scored as a draw; a call on the benchmark
    itself is excluded because 0050 cannot outperform 0050. avg_excess_pct is
    the plain average of (instrument return - index return), so a negative
    average on a book of avoid calls is the point, not a failure — read it with
    beat_count, which already knows which direction each stance wins in.
    """
    judged = [c for c in timely if c.get("beat_benchmark") is not None]
    excesses = [_decimal(c.get("excess_pct")) for c in timely]
    excesses = [e for e in excesses if e is not None]
    beat = sum(1 for c in judged if c.get("beat_benchmark"))
    backfilled = sum(
        1 for c in judged if c.get("benchmark_ref_source") == BENCHMARK_SOURCE_BACKFILL
    )
    return {
        "symbols": BENCHMARK_BY_MARKET,
        "judged_count": len(judged),
        "beat_count": beat,
        "beat_rate_pct": f"{(beat / len(judged) * 100):.1f}" if judged else None,
        "avg_excess_pct": f"{(sum(excesses) / len(excesses)):.2f}" if excesses else None,
        "unmeasured_count": len(timely) - len(judged),
        "backfilled_count": backfilled,
        "note": (
            "excess_pct is the instrument's return minus its market's return "
            "over the same window. A call that means to own something beats the "
            "benchmark by outrunning it; one that means to stay out beats it "
            "when the thing avoided lagged. Calls with no benchmark on both ends "
            "are counted in unmeasured_count, never scored as a draw. "
            "backfilled_count is how many of these verdicts rest on a "
            "reconstructed daily close rather than a level stamped live at "
            "strike time — a weaker measurement, and read the rate as provisional "
            "while it is most of the base."
        ),
    }


def _scorecard(scored: list[dict[str, Any]]) -> dict[str, Any]:
    """Honest hit rate.

    Flat/range calls are excluded from the win/loss base so noise cannot
    inflate it, and sizing calls are excluded entirely: a concentration warning
    made no directional claim, so counting it as a win or a loss would
    manufacture an edge. Sizing is reported on its own terms instead.
    """
    directional = [c for c in scored if str(c.get("stance")) != "size_down"]
    sizing = [c for c in scored if str(c.get("stance")) == "size_down"]
    # A call scored long after it matured measured a different window than its
    # thesis stated; counting it would put a number on something never claimed.
    timely = [c for c in directional if c.get("window_honored", True)]
    stale = [c for c in directional if not c.get("window_honored", True)]
    decided = [c for c in timely if c.get("outcome") in DECIDED_OUTCOMES]
    wins = sum(1 for c in decided if c.get("outcome") == "worked")
    favors = [_decimal(c.get("favor_pct")) for c in timely]
    favors = [f for f in favors if f is not None]
    by_stance: dict[str, dict[str, int]] = {}
    for c in scored:
        bucket = by_stance.setdefault(str(c.get("stance")), {})
        outcome = str(c.get("outcome"))
        bucket[outcome] = bucket.get(outcome, 0) + 1
    return {
        "scored_count": len(scored),
        "decided_count": len(decided),
        "win_count": wins,
        "hit_rate_pct": f"{(wins / len(decided) * 100):.1f}" if decided else None,
        "avg_favor_pct": f"{(sum(favors) / len(favors)):.2f}" if favors else None,
        "by_stance": by_stance,
        "vs_benchmark": _benchmark_scorecard(timely),
        "stale_scored_count": len(stale),
        "stale_note": (
            "calls scored more than "
            f"{LATE_SCORE_TOLERANCE * 100:.0f}% of their horizon late are excluded "
            "from hit_rate_pct: scoring reads the price at the moment it runs, so a "
            "late score measures a window the thesis never claimed. A non-zero count "
            "means rounds were missed, not that the calls were bad."
        ),
        "sizing": {
            "scored_count": len(sizing),
            "risk_realized_count": sum(1 for c in sizing if c.get("outcome") == "risk_realized"),
            "material_drop_pct": str(RISK_MATERIAL_DROP_PCT),
            "note": (
                "sizing calls are excluded from hit_rate_pct: a concentration "
                "warning is not a directional prediction. risk_realized counts the "
                "ones where the oversized position went on to drop at least "
                f"{RISK_MATERIAL_DROP_PCT}% — i.e. the warning had teeth."
            ),
        },
    }


def scan_universe(
    owned: dict[str, tuple[str, str]] | None = None,
) -> dict[str, tuple[str, str]]:
    """The names to research: the default universe PLUS what the owner owns.

    The owner trades his own money by hand; a research loop that never looks at
    his actual holdings is researching the wrong list. His positions are merged
    in (and win on name collision, since his book knows the real name).
    """
    return {**DEFAULT_UNIVERSE, **(owned or {})}


def scan_candidates(
    quotes: dict[str, dict[str, Any]] | None,
    open_symbols: tuple[str, ...] | list[str] = (),
    owned: dict[str, tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """Rank the research universe: owner's holdings first, then biggest movers.

    `quotes` maps symbol→{price, change_pct, currency}. A big move only *flags*
    a name worth researching — it is not itself a call. `has_open_call` marks
    names already in the ledger so a scan does not invite duplicate calls, and
    `owned` marks the owner's real positions, which sort first regardless of
    move size: a name holding his actual money always deserves a view, and an
    owned name with no open call is the loudest gap in the ledger. Rows with no
    usable change sink to the bottom of their group (missing data, not "no
    move").
    """
    quotes = quotes or {}
    open_set = {str(symbol).strip().upper() for symbol in open_symbols}
    owned = owned or {}
    rows: list[dict[str, Any]] = []
    for symbol, (market, name) in scan_universe(owned).items():
        quote = quotes.get(symbol) if isinstance(quotes.get(symbol), dict) else {}
        price = _decimal(quote.get("price"))
        change = _decimal(quote.get("change_pct"))
        rows.append(
            {
                "symbol": symbol,
                "name": name,
                "market": market,
                "price": str(price) if price is not None else None,
                "change_pct": f"{change:.2f}" if change is not None else None,
                "currency": quote.get("currency") or None,
                "has_open_call": symbol in open_set,
                "owned": symbol in owned,
                "_abs": abs(change) if change is not None else None,
            }
        )
    rows.sort(
        key=lambda row: (
            not row["owned"],  # the owner's real positions first
            row["_abs"] is None,
            -(row["_abs"] or Decimal(0)),
        )
    )
    for row in rows:
        row.pop("_abs", None)
    return rows


def research_scan_payload(
    quotes: dict[str, dict[str, Any]] | None,
    open_symbols: tuple[str, ...] | list[str] = (),
    owned: dict[str, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    candidates = scan_candidates(quotes, open_symbols, owned)
    priced = [row for row in candidates if row["change_pct"] is not None]
    uncovered = [
        row["symbol"] for row in candidates if row["owned"] and not row["has_open_call"]
    ]
    return {
        "as_of": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "universe_size": len(scan_universe(owned)),
        "owned_count": sum(1 for row in candidates if row["owned"]),
        "owned_without_call": uncovered,
        "priced_count": len(priced),
        "candidates": candidates,
        "quote_source": "yahoo_finance_public_quote_snapshot",
        "record_action": "research_call_record",
        "note": (
            "1-day change is the only signal here — a large move flags a name to "
            "research, it is NOT a call; form a thesis (with news/context) before "
            "recording one. has_open_call marks names already journaled. owned "
            "marks the owner's real positions: they sort first and any listed in "
            "owned_without_call is a holding of his real money with no journaled "
            "view — the highest-priority gap. A null change_pct is missing data, "
            "not a flat tape; run with refresh=true to fetch current marks."
        ),
        "safety": {"paper_only": True, "live_execution": "disabled"},
    }


def research_ledger_payload(
    state: dict[str, Any],
    marks: dict[str, Decimal | None] | None = None,
    *,
    weights: dict[str, Decimal | None] | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    ledger = normalize_research_ledger_state(state)
    calls = ledger["calls"]
    marks = marks or {}
    weights = weights or {}
    open_calls = [c for c in calls if c.get("status") == "open"]
    scored_calls = [c for c in calls if c.get("status") == "scored"]
    superseded_calls = [c for c in calls if c.get("status") == "superseded"]
    if limit is not None:
        limit = max(1, int(limit))
        scored_view = scored_calls[-limit:]
    else:
        scored_view = scored_calls
    now = datetime.now(tz=UTC)
    open_view = [
        _open_view(
            c,
            marks.get(str(c.get("symbol", ""))),
            now,
            weights.get(str(c.get("symbol", ""))),
        )
        for c in open_calls
    ]
    to_review = [row["symbol"] for row in open_view if row["needs_review"]]
    return {
        "needs_review_count": len(to_review),
        "needs_review": to_review,
        "review_note": (
            "these open calls drifted from the price they were struck at, are "
            "closing on their invalidation, have left the entry band they named, "
            "or are near the end of their horizon — re-examine the thesis rather "
            "than letting it score untouched; a flag means think again, not that "
            "the call is wrong"
        ),
        "as_of": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "call_count_total": len(calls),
        "open_count": len(open_calls),
        "scored_count": len(scored_calls),
        "superseded_count": len(superseded_calls),
        "superseded_note": (
            "a superseded call was replaced because its premise changed; it is kept "
            "as the record of a changed mind but is never scored and never counted "
            "in the hit rate, since grading it would judge a view no longer held"
        ),
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
