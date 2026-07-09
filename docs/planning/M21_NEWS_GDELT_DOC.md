# M21.2 News GDELT DOC Slice

Date: 2026-05-24

## Selected Scope

Implement News route depth by adding no-key GDELT DOC 2.0 ArticleList metadata as a
public read-only source beside the existing public RSS feeds.

This is a bounded News workflow slice, not an all-route M21 completion claim.

## Fincept Observation Record

- `route`: News
- `source_evidence`: live installed Fincept UI via Windows UI Automation plus existing
  sanitized reference logs under `docs/reference/fincept-platform-test/logs/`.
- `observation_time`: 2026-05-24 Asia/Taipei
- `navigation_path`: launched `D:\FinceptTerminal\app\FinceptTerminal.exe`, skipped
  the recover dialog using `SKIP` because the dialog stated skipping does not delete
  snapshots, then opened `NEWS`.
- `interaction_steps`: selected `NEWS`, observed command strip, clicked `NRG`, clicked
  `CLST`, selected the first visible list item.
- `state_transitions`: global News list moved from broad feed view to energy cluster
  view; visible counters changed to energy-specific article and cluster counts.
- `inputs`: category pill `NRG`; feed mode pill `CLST`; first list row selection.
- `outputs`: News retained category/time/sort/feed controls, intel counters, provider
  counts, source counts, sentiment score, list rows, and an AI action button.
- `errors_or_empty_states`: none observed during filter/cluster selection.
- `data_sources_visible`: feed count, article count, cluster count, source count, and
  sentiment score are visible as route state. Provider/source names appear on item rows.
- `artifact_or_export_behavior`: no export artifact observed in this slice.
- `terminal_density_notes`: low-radius dense controls, route rail, compact counters,
  and a narrow intelligence strip are more important than large card copy.
- `panel_structure_notes`: command strip first, intel strip second, feed/list panel
  plus detail/selection behavior. `AI` and `REFRESH` are distinct actions.
- `agent_operable_contract`: the local route should expose stable state fields for
  feed count, article count, cluster count, source count, sentiment, provider states,
  selected item metadata, and no-full-article-copy safety flags.
- `clean_room_exclusions`: no Fincept source, app scripts, assets, branding, commercial
  copy, account data, credits, screenshots, credentials, or runtime binaries were used
  as implementation inputs.
- `local_gap`: existing local News exposed RSS rows and research provider cards but did
  not expose Fincept-like FEEDS/ARTS/CLST/SRCS/SENT/WATCHES state or global news
  metadata breadth.
- `verification_plan`: unit tests for GDELT metadata-only parsing and News intel
  contract; frontend typecheck/build/e2e; no-full-article-copy safety assertion;
  browser screenshot of the local News intel strip.

## Provider Source Gate

Official GDELT DOC 2.0 documentation was refreshed on 2026-05-24:

- Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
- Endpoint: `https://api.gdeltproject.org/api/v2/doc/doc`
- Selected mode: `mode=artlist`
- Selected format: `format=json`
- Auth mode: no-key public endpoint
- Local behavior: metadata only; store title, link, domain/source, source country,
  language, provider id, category, tags, and timestamps.
- Forbidden behavior: no article body fetch, no full-article copy, no login, no
  credential storage, no paid GDELT Cloud API, no AI summary call.

The live endpoint returned HTTP 429 during one manual shape probe, so implementation
must treat GDELT as a partial/degraded source and continue to use stale cache, RSS
items, or explicit local fallback when the public endpoint is unavailable.

## Implementation Result

- `src/local_terminal/news.py` now fetches GDELT DOC ArticleList metadata as part of
  the public News refresh path.
- News payload now exposes an `intel` contract with `feed_count`, `article_count`,
  `cluster_count`, `source_count`, `sentiment`, `watch_count`, `provider_states`, and
  metadata-only safety flags.
- Frontend News now renders a dense FEEDS / ARTS / CLST / SRCS / SENT / WATCHES strip
  and provider-state cards before the existing research cards.
- News detail rows expose provider/domain/locale metadata for AI Agent operation.
- `CLST` now clusters by tag/topic/source rather than only by broad category.

## Safety

- No Fincept source or installed package source was inspected.
- No Fincept screenshot was retained for this slice because the running app includes
  account and credit surfaces in the global toolbar.
- The local implementation does not store article bodies and does not fetch full
  article pages.
- `REFRESH` and `AI` were not clicked in Fincept observation to avoid cloud/credit
  side effects.
- Live trading, broker keys, real balances, margin, leverage, short exposure, and
  derivatives remain untouched.
