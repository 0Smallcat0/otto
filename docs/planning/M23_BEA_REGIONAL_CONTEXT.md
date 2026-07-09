# M23.5 BEA Regional Context

Date: 2026-05-25

## Purpose

This milestone adds a bounded optional-key BEA Regional data provider for the
Markets Regional macro context. It continues the M23 provider-breadth work
without reopening completed Twelve Data, Alpha Vantage, H.10, BLS, FRED,
DBnomics, or SEC workflows.

The provider is official macro context only. It is not a quote provider, not a
balance source, not a broker/exchange integration, and not usable for live
orders.

## Official Source Evidence

- BEA API signup/API page: `https://apps.bea.gov/API/signup/`
- BEA Web Service API User Guide:
  `https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf`
- Official Regional `GetData` examples use `datasetname=Regional`,
  `TableName=SAGDP9N`, `LineCode`, `GeoFips=STATE`, and `Year=ALL`.

No provider signup, CAPTCHA, payment, identity verification, security alert,
or key creation was attempted for this milestone.

## Implementation

- New adapter: `src/local_terminal/bea_data.py`.
- Provider id: `bea_regional_optional_key`.
- Source: `bea_regional_api`.
- Cache: `market_data/regional/bea/SAGDP9N_LINE1_STATE.json`.
- Endpoints:
  - `GET /api/bea/regional`
  - `POST /api/bea/regional/refresh`
  - `POST /api/markets/bea/refresh`
- Markets action: `BEA`.
- AI Agent action: `markets_bea_refresh`.
- Command Center provenance now points to this milestone while keeping the
  command-center payload read-only.

## Safety Contract

- Uses a user-owned BEA UserID only if it is already stored through the local
  secret gate.
- Returns `key_required` without a stored local key.
- Does not expose secret values over HTTP.
- Does not create `settings/local_secrets.json` during no-key reads.
- Does not join public no-key refresh jobs.
- Normalized rows carry `quote_semantics: not_quote`.
- Live trading, broker/exchange binding, real balances, margin, leverage,
  short exposure, derivatives, payment, subscription, CR/credits, cloud sync,
  Fincept branding/assets/commercial copy/runtime binaries, and installed
  source reads remain excluded.

## Verification

- Focused gate:
  `.\.venv\Scripts\python.exe -m pytest tests\test_m23_bea_regional_provider.py tests\test_m21_bls_macro_provider.py tests\test_m22_provider_acquisition_gate.py tests\test_m21_agent_operability_contract.py tests\test_m2_local_state.py tests\test_m21_markets_source_coverage_matrix.py tests\test_m19_provider_registry.py tests\test_m20_local_secret_gate.py -q --basetemp .omx\pytest-tmp\m23-5-focused-rerun`
  -> 49 passed.

## Residuals

- A live BEA key refresh is not verified because no signup/key creation was
  performed.
- Census Regional context remains deferred until a concrete bounded dataset is
  selected.
- Broad market quote parity remains partial; this milestone deepens Regional
  macro context, not executable quote breadth.
