---
id: MARKET-ENGINE-JOURNEY-01
status: PASSED
owner: backtest-runtime execution-input and engine integration
status_authority: ../acceptance-matrix.md
---

# Market-backed DeterministicBarEngine journey v1

## Outcome

Prove one complete development-grade market-backed semantic journey through the sole
successful interface:

```text
BacktestRuntime.run(request)
  -> exact one-Bundle PREP execution/valuation replay
  -> DeterministicBarEngine target/order/fill/accounting/valuation
  -> locked first/retry equality
  -> existing canonical-v2 publication and repository replay
  -> analysis v1 and same-request cache replay
```

The journey exact-reuses the accepted 19 G12I Tushare source Events and 19 G12M
`bar_open@1` projections. One additive precomputed target and one additive canonical
`price_bars@1` valuation projection are test authorities only. The result has one
nonzero order/fill, an explicit zero development fee assessment, one open position,
and a source-bound final valuation. It remains development-only, non-live, and
non-deployment and does not change the accepted G12M zero-target/no-trade
qualification scope.

## Blocker and transport decision

Schema 3 cannot decode `xshe:000001`; its immutable v1 plan reader reconstructs only
`cash:<base>-<quote>` SPOT catalogs. Schema 4 carries exact validation catalogs but is
immutably decision-grade durable-only and rejects non-decision-grade requests before
artifact I/O. Neither contract may be widened in place.

Add `backtest_execution_input_bundle@5` and request schema 5. Schema 5 uses the exact
schema-4 payload fields and catalog grammar without adding another catalog or model.
Its only new semantic is the execution lane:

- no cancellation;
- requested grade is exactly `DEVELOPMENT`;
- reader is exact `LocalMarketBundleReader` with repository-open provenance;
- success uses the existing schema-3 PREP, locked two-attempt, canonical-v2 path.

Any other schema-5 request fails before artifact I/O with the existing
`execution input hydration failed: malformed_execution_request`. Schema 4 retains its
existing decision-grade-only lane and exact failure behavior.

## Exact write set

- `packages/backtest-runtime/src/crypto_quant_backtest/execution_inputs.py`
- `packages/backtest-runtime/src/crypto_quant_backtest/facade.py`
- `tests/runtime/engine/test_g12m_tushare_market_engine_journey.py`
- `tests/runtime/execution_inputs/test_multi_resolution_bundle_v3.py`
- `tests/architecture/test_bt_gap02a_composition_boundary.py`
- `tests/architecture/test_bt_gap02b_execution_input_boundary.py`
- `tests/architecture/test_bt_gap02c_execution_closure_boundary.py`
- `tests/fixtures/runtime/engine/g12m-tushare-market-engine-journey-v1.json`
- `docs/implementation/acceptance-matrix.md`
- this contract

## Symbol plan

| Symbol | Change |
| --- | --- |
| `BacktestExecutionRequest` | accept exact schema 5/ref 5 additively |
| execution-input schema constants/catalog | register schema 5 in the existing sole catalog |
| v4 catalog decoder/materializer helpers | share exact explicit-catalog grammar with v5 wrappers |
| schema snapshot/read/hydrate helpers | add exact v5 wrappers; no fallback to schema 3 inference |
| `BacktestRuntime._run` | select schema 5 only on the fixed development Local Reader lane |
| `BacktestRuntime._run_v3` | dispatch schema 3 or 5 through the unchanged shared execution body |

## Journey roles and timing

- Bundle: exact accepted source/projection tuples plus one target and one valuation Bar.
- Decision/valuation: after the penultimate accepted source is available and before
  the final accepted `bar_open` projection.
- Target: fixed 9.024% allocation, which sizes exactly to 800 shares at CNY 11.28
  under the fixed 100-share buy lot.
- Execution: the final accepted `bar_open` projection, one full BUY at CNY 11.28.
- Accounting: CNY 100,000 initial cash, one fill, one zero-fee assessment, deterministic
  Journal/Ledger/Lot replay.
- Final valuation: the exact penultimate source close, explicitly and boundedly
  forward-filled to run end; final equity remains CNY 100,000.

## Failure precedence

Schema-5 type/ref/version and lane selection precede artifact I/O. After admission,
existing precedence is unchanged:

1. execution-input availability/tamper/decode/request/build/target;
2. PREP Bundle/binding/manifest/profile/valuation/cycle replay;
3. Resolution and Runner contract;
4. Engine target/allocation/risk/sizing/rebalance/admission/pretrade/bar/financial/
   snapshot/run-end;
5. attempt evidence, Integrity, canonical-v2 publication, repository, and analysis.

## Immutable boundaries and nonclaims

- schema 1-4 bytes, fixtures, refs, decoders, APIs, and failure behavior stay exact;
- no new facade method, root export, catalog, registry, repository, cache, provider,
  Builder inference, Runtime resampling, or instrument-ID inference;
- accepted G12M route/profile/assessment/Bundle/Run identities remain unchanged;
- G12H D6 remains the authority for current-selected A-share fee economics; this
  journey intentionally uses explicit zero development fees;
- no provider finality/completeness, A-share rule qualification, decision grade,
  live, or deployment claim.

## Acceptance

`PASSED` at implementation commit `2edd82b37f96b0d1ddad9c917993e11dc0d9074a`.
The schema-5 journey and adjacent execution-input/PREP/facade/provider/architecture
set passed `83` tests; import boundaries passed across `134` files; primary Python
LSP reported zero diagnostics; `uv lock --check`, compile, diff, and gitleaks checks
passed. The full repository passed `2389` tests. The first full rerun in the recreated
`/tmp` worktree exposed only three missing external Platform fixture paths; after
restoring the existing sibling fixture path through `/tmp/tests`, those ten exact
contract tests and the complete full suite passed without repository changes.

Independent review found the initial architecture schema-count locks and missing
non-Local/read-count sentinels; both were fixed before the accepted commit. A final
review must confirm no remaining blocker. Protected main-worktree hashes/status must
remain exact before governance close.
