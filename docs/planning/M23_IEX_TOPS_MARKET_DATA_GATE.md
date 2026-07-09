# M23.42 IEX TOPS Market Data Gate

Date: 2026-05-26

## Objective

M23.42 closes another provider-entry ambiguity in the remaining Markets quote
breadth gap. Current IEX TOPS/DEEP materials describe real-time exchange market
data products, not an unattended public no-key REST quote source for the local
terminal.

The purpose is to make AI Agent provider selection safer: agents can see that
IEX market data was inspected, why it is not an approved local adapter source,
and which implemented quote/reference lanes should be used instead.

## Official Evidence

- IEX Exchange market data materials:
  `https://www.iexexchange.io/resources/trading/market-data`
- IEX market-data connectivity product page:
  `https://www.iex.io/products/market-data-connectivity`
- IEX trading fee schedule:
  `https://www.iex.io/resources/trading/fee-schedule`

The official materials route real-time TOPS/DEEP access through market-data
agreements, forms, connectivity, and fee-schedule terms. This is not the same as
a current public no-key quote API.

## Implementation

- Added `iex_tops_market_data_gate` to the read-only provider acquisition gate.
- Classified the candidate as `blocked_official_terms`.
- Recorded official IEX market-data URLs, subscriber-agreement auth mode,
  quote-blocked semantics, no-cache policy, and a non-automation implementation
  gate.
- Kept `summary.next_candidate_id` empty because blocked candidates are not
  actionable next implementation work.
- Updated Command Center provenance so supervisors see M23.42 as the current
  provider-entry milestone.

## Safety

- No IEX adapter, cache, endpoint, refresh job, source coverage row, UI quote
  lane, or provider registration was added.
- No legacy IEX Cloud/no-key assumption, TOPS/DEEP feed decoder, HIST PCAP
  parser, web scraping, credential flow, provider signup, agreement acceptance,
  paid-data activation, broker/exchange connection, orderability, balance read,
  live trading, or destructive action was added.

## Verification

Fresh verification is tracked in `docs/planning/M22_MISSION_LEDGER.md` under
the M23.42 verification log.

## Resume Guidance

Do not redo IEX TOPS/DEEP adapter investigation unless a future milestone starts
from a licensed, agreement-backed data contract. Continue quote breadth through
implemented public no-key snapshots, optional personal-key lanes behind the
local secret gate, or another provider-entry gate with official documentation.
