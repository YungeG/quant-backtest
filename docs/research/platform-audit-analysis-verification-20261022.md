# Platform audit analysis verification addendum — 2026-10-22

This is the authorized AR-03/04 D3 semantic-strengthening addendum. It does not rewrite the accepted historical G07 contract, receipts, examples, or golden payloads.

## Verified analysis acceptance

The historical G07 link-only analysis-verification claim is no longer sufficient for current repository acceptance. `load_analysis` and `load_analysis_v2` now require all of:

1. The existing accepted `simple_period_return.fill_count.v1` metric profile.
2. An authentic, retained completed publication with the existing exact source-ref, execution-result-hash, result-grade, and version linkage.
3. `trade_count` equal to the completed execution summary's fill count, and `simple_period_return` equal to the existing package-internal `analysis_derivation._simple_period_return` result for that completed source.

The repository reuses the derivation's pure calculation, including its canonical decimal string and `None` conventions. It introduces no financial formula, float tolerance, execution, repair, publication, or CAS write. A source-derived metric disagreement uses the existing `PORT_ANALYSIS_LINK_MISMATCH` failure. Source retention, type, version, and existing profile/link validation retain their precedence.

`BacktestAnalysis@1/@2`, public signatures/return types, accepted metric-profile identity, derivation arithmetic, and all valid artifact bytes/refs remain unchanged. Previously accepted artifacts whose metrics do not match their sources are rejected, not repaired or republished.

## Bounded regression evidence

- Both loaders reject real-linked analyses with `trade_count=999999` or `simple_period_return="999"`, and reject a missing return when the retained source derives a return. Legitimately derived analyses still load; unavailable source retention wins over metric disagreement; verification performs no writes.
- CN portfolio values are integer shares: registrations, pending position quantities, sell reservations, directly constructed sellability snapshots, and proposals are checked without conversion or rounding. The synthetic holiday T+1, zero, mature, and reserved cases remain covered.
- Model-bound preparation checks selected model availability against the actual target event's complete simulation instant before writes. UTC, phase, and sequence violations are rejected; equality and an honest later target decision are accepted; hidden future revisions remain hidden.
- Representative valid sellability snapshots and plans were compared byte-for-byte and hash-for-hash with baseline `3ab6bfd8` for pending holiday T+1, mature shares, and reserved shares.

The focused suite includes existing frozen analysis-byte fixtures. A separate baseline architecture allowlist failure in `test_settlement_availability.py::test_concrete_profile_source_is_pure_and_not_root_reexported` (`KeyError: portfolio_open_risk_development_v1.py`) was reproduced from baseline source and is not changed by this addendum or implementation. Parent review and independent validation remain required before merge.
