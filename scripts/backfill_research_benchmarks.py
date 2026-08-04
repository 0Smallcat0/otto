"""One-shot: give the calls struck before 2026-07-30 an index level to be judged against.

Benchmark stamping landed on 2026-07-30. Every call journaled before it carries
no index level on either end, so `vs_benchmark` reported the entire existing
record as unmeasured — the ledger could state a hit rate and could not state the
thing it was built to state. This walks the ledger once, fills what a published
daily close can recover, and re-grades the calls already scored.

It is a migration, not a capability: the record path has fetched the benchmark
live since 2026-07-30, so no future call needs this. Nothing new is added to the
agent contract.

    python scripts/backfill_research_benchmarks.py            # report only
    python scripts/backfill_research_benchmarks.py --apply    # write

Writing goes through LocalStateStore, so the pre-change ledger lands in the
backup rotation before anything is overwritten.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from otto.local_terminal.research_ledger import (  # noqa: E402
    BENCHMARK_BY_MARKET,
    backfill_benchmarks,
    research_ledger_payload,
)
from otto.local_terminal.storage import LocalStateStore, state_root_from_env  # noqa: E402
from otto.local_terminal.yahoo_data import fetch_yahoo_daily_closes  # noqa: E402


def _window(calls: list[dict]) -> tuple[str, str]:
    """Earliest strike to latest scoring, padded back a week.

    The pad is not cosmetic: a call struck on a Saturday, or after a run of
    holidays, needs the previous session, and that session can sit several days
    before the call's own date.
    """
    days = [str(c.get("as_of") or "")[:10] for c in calls]
    days += [str(c.get("scored_at") or "")[:10] for c in calls]
    days = sorted(d for d in days if d)
    if not days:
        raise SystemExit("ledger has no dated calls")
    first = f"{days[0][:8]}01"
    return first, days[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write the ledger (default: report)")
    args = parser.parse_args()

    store = LocalStateStore(root=state_root_from_env())
    state = store.read_research_ledger_state()
    calls = state.get("calls") or []
    print(f"ledger: {len(calls)} calls")

    start, end = _window(calls)
    needed = sorted({BENCHMARK_BY_MARKET[m] for m in BENCHMARK_BY_MARKET})
    closes: dict[str, dict[str, str]] = {}
    for symbol in needed:
        series = fetch_yahoo_daily_closes(symbol=symbol, start=start, end=end)
        closes[symbol] = series
        print(f"  {symbol}: {len(series)} sessions {start}..{end}")

    state, report = backfill_benchmarks(state, closes)
    print(json.dumps(report, indent=2, ensure_ascii=False))

    card = research_ledger_payload(state)["scorecard"]
    print("\nscorecard after backfill:")
    print(json.dumps({"hit": card["hit_rate_pct"], **card["vs_benchmark"]}, indent=2))

    if not args.apply:
        print("\nreport only. re-run with --apply to write.")
        return 0
    store.write_research_ledger_state(state)
    print(f"\nwritten to {store.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
