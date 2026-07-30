# What an autonomous loop actually found

Late July 2026 this terminal was driven by a self-paced loop: the agent picked
its own next task, ran the gates, committed, and scheduled its own next
wake-up. Roughly thirty rounds. This is what came out of it, including the
parts that did not work.

## The one defect shape, thirteen times

Twelve of thirteen externally-visible defects were the same shape: **the
backend computed a qualifying fact, put it in the payload, sometimes even
specified the UI behaviour in the agent contract, and the presentation or
decision step dropped it.**

- A news relevance score computed per item, and a feed that ranked by recency.
- `last_price` present on every crypto row, and a positions table showing cost
  basis because it read a different key.
- `latest_trading_day` on every quote, and a group header that stamped the
  whole group from `rows[0]` — certifying three stale TWSE rows as today's, so
  an ETF showed +0.15% on a day it fell 4.24%.
- Provider `data_state` computed and rendered nowhere, so a retired source and
  a live one looked identical.
- The judgment board printing `跌破 19.5` for a hold while the scorer exempted
  holds from the invalidation check entirely — the screen made a promise the
  engine did not keep, and the call it should have settled would have drifted a
  month to score on an unrelated price.
- A sizing warning printing the weight the position had when the warning was
  written, in the present tense, while the concentration had since grown.
- A scoring endpoint returning the ledger's lifetime scored count under the key
  meaning "how many did this run close" — the two agreed by coincidence until a
  run that settled nothing reported two.

The reason these survived is uniform: **the API was right and only the screen
was wrong.** Every one of them passes an API-level check. They are only visible
if you open the page a human actually reads.

The rule that came out of it: after any change, open the front end and look. A
guard written and never seen rendered is a guard nobody reads — one review rule
shipped correctly into the payload and would have displayed nowhere, because
the banner it applied to was a different component from the table that had
always shown the flag.

## Verification habits that earned their keep

- **Break the guard, watch it go red, restore it.** Applied to every new test.
  It caught a benchmark rule that would have scored an unmeasured window as a
  draw, and a screen that would have ranked a loss-making company as the
  cheapest on the exchange.
- **Dump the real payload shape before concluding anything.** Guessing key
  names produced two false "the ledger is empty" alarms. A later mistake in the
  same family: `git merge-base` piped through `xargs` printed `HEAD` when the
  merge base was empty, nearly producing the claim that two unrelated repos
  shared history.
- **A false alarm costs exactly what silence costs.** One round reported "2 data
  sources are broken"; one was an unused fallback and one was retired with a
  named successor. The next round was spent undoing it.
- **Derive from a list; never hand-enumerate.** A hand-written status list drifts
  from the enum it mirrors.
- **When a new guard flags thirteen long-standing things, suspect the guard.** It
  did, and the guard was wrong: it asserted an invariant the codebase never
  held.

## What the loop was worse at than expected

- **Deferring instead of deciding.** Findings accumulated as "this needs a
  decision" while the loop moved on. A missing benchmark in the backtest was
  raised, parked, and raised again — and the same hole in the judgment
  scorecard went unnoticed for several more rounds, because the parked item had
  become a thing to report rather than a thing to fix.
- **Building measurement and calling it progress.** The scorecard was made
  scrupulously honest — flat bands excluded, late scores excluded, sizing calls
  excluded — and still could not answer whether a judgment beat owning the
  index, which was the actual question. Honest measurement is a floor, not an
  achievement.
- **Operating on stale processes.** There is no reloader; twice a change was
  made, the endpoint was called, the old answer came back, and the debugging
  went into code that was never running. `/api/health` now reports
  `source_stale` by comparing the newest source mtime against the one captured
  at import, so this is a fact the caller reads instead of a mistake it has to
  remember not to make.

## Operational notes

- The MCP process is separate from the backend and does not restart with it;
  its cached action list going stale looks exactly like a missing registration
  and is not one.
- On Windows, pytest's temp-dir teardown can raise `PermissionError` on the
  `pytest-current` symlink after a green run. It is teardown noise, the exit
  code is still 0, and passing `--basetemp` avoids it. Left unfixed rather than
  changing global test configuration for a platform-local artifact.
- The private checkout and the public mirror share no history at all; the merge
  base between them is empty, and that is by design, since the public repo's
  history must never contain the excluded reference corpus. `git push --force`
  from the private checkout would have overwritten the mirror and published
  everything, so its push URL is now disabled and the export runs through
  `scripts/sync_public_mirror.ps1`, which uses the mirror's own file list as
  the allowlist and refuses to touch four deliberately diverged files.
