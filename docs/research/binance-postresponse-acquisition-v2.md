# Binance USD-M post-response acquisition v2

`tools.acquisition.binance_usdm_v2` is the explicit current entry point for
post-response local acquisition timestamps. The protected v1 module
`tools.acquisition.binance_usdm` and its original tests remain byte-identical to
`3ab6bfd8`. Its CLI samples time **before** the requests: this is retained legacy
behavior, not an accurate post-response timestamp or causal-availability claim.
No historical receipt, G12L protected hash/signature, schema, or artifact is changed.
The acquisition-tool version here is distinct from the historical G12L
funding-history source-bounded v2 artifacts, which remain immutable.

## Commands (documentation only; not executed against providers)

From the Backtest checkout with its source packages available on `PYTHONPATH`:

```sh
python -m tools.acquisition.binance_usdm_v2 archive \
  --symbol ETHUSDT --kind aggTrades --date 2024-03-01 \
  --output-dir /tmp/binance-archive-v2-new

python -m tools.acquisition.binance_usdm_v2 funding \
  --symbol ETHUSDT --start-ms 1709251200000 --end-ms 1709337599999 \
  --limit 1000 --output-dir /tmp/binance-funding-v2-new
```

These commands perform real requests when explicitly run; validation uses only
synthetic in-memory transports. Output must not exist. Existing or concurrently
claimed directories are never replaced. Failed requests, invalid clocks, malformed
responses, or checksum failures do not publish a receipt or partial capture.

## Time and compatibility contract

- Both v2 acquisition functions require exactly one of an explicit fixed
  `acquired_at_epoch_nanoseconds` or a callable `clock`. The CLI supplies
  `time.time_ns` as a callable, never a pre-request sample.
- Values must be exact, nonnegative Python integers (not booleans or floats).
  A callable is sampled only after each successful response body returns,
  including all retries and retry delays, never after a failed attempt.
- Archive checksum and archive members retain their own response times. The
  aggregate receipt time is their maximum. Equal samples are valid; a backward
  sample fails before publication. Funding has one response/member time.
- Explicit fixed time is for deterministic replay or caller-supplied compatibility
  evidence, not an assertion that a live response was received at that time.
  For identical bytes, request, attempts, and fixed time, v1 and v2 produce
  identical canonical receipt bytes, snapshot identities, and published files.
- V2 reuses same-package v1 request validation, response parsing, retry policy,
  HTTPS transport, checksum validation, and CLI parser; shared publication helpers
  retain their existing atomic-output behavior. No provider limit, receipt field,
  financial semantics, or grade policy changes.

Local acquisition time is not provider availability time; see
[ADR 0009](../adr/0009-historical-provider-availability-is-distinct-from-local-acquisition.md).
This correction grants no decision-grade, causal historical, deployment, or live
qualification. Receipts continue to set `decision_grade_eligible` and
`deployment_authorized` to false.

## Synthetic regression checks

`tests/tools/acquisition/test_binance_usdm_acquisition_v2.py` targets v2 directly,
including monkeypatched v2 CLI transport and clock, per-response/retry timing,
invalid and backward clocks, fixed/clock exclusivity, zero/equal samples,
failure-before-publication, and fixed-receipt parity against protected v1.
The original acquisition tests and G12L boundary checks still target v1 unchanged.
