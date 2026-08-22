---
id: G12M-GENERIC-EXECUTION-INPUT-CATALOG-V4
status: CONTRACT_FROZEN
owner: Backtest Runtime execution-input successor
status_authority: ../../acceptance-matrix.md
predecessor: g12m-tushare-fixed-singleton-qualification-v2.md
---

# G12M generic execution-input catalog v4

## Outcome

Add one generic, additive execution-input/request schema that carries the exact
`InstrumentCatalog` bodies already authorized by each target validation context.
This removes the schema-3 cash-only reconstruction ceiling for non-cash instruments
without modifying schema-3 bytes, behavior, failure precedence, fixtures, or public
facade shape.

The sole execution entry remains:

```text
BacktestRuntime.run(request)
```

A successful decision-grade schema-4 request with an exact retained Local Reader
continues through the accepted durable proof, Integrity, and canonical-v3 publication
path and returns `BacktestCanonicalPublicationRefV2`. Schema 4 is an execution-input
transport successor; it does not create canonical-v4 results, a second facade, a
provider framework, or a new catalog authority.

For the Tushare v2 route, this contract supersedes only the literal schema-3 transport
requirements at `g12m-tushare-fixed-singleton-qualification-v2.md:23` and `:141`.
V2-03 must use schema 4 after this contract is accepted. Every other V2 clause,
identity, write boundary, failure stop, canonical-v3 output, and nonclaim remains in
force.

## Blocker being repaired

The accepted Tushare route requires exact target instrument `xshe:000001`. A zero
notional target still requires one exact `InstrumentSizingInput`; therefore the
validation context cannot use empty sizing inputs. Existing schema-3 decoding then
fails closed in `_read_validation_catalog` because it reconstructs only
`cash:<base>-<quote>` SPOT catalogs from sizing inputs.

The deterministic red loop is:

```text
schema-3 materialization succeeds
  -> BacktestRuntime.run
  -> execution_input_decode_failed
  -> execution case plan v1 supports exact cash instrument catalogs
```

Changing the target identity, using a cash alias, inferring EQUITY from `xshe`,
omitting sizing inputs, bypassing the decoder, or silently widening schema 3 is
forbidden.

## Immutable boundaries

- `BacktestRuntime.run(request)` remains the sole successful schema-4 execution entry;
  existing `run_with_cancellation` rejects schema 4 before artifact I/O.
- `BacktestExecutionRequest` remains the public request type; accepting exact schema
  version 4 is additive.
- Execution-input v1/v2/v3 canonical bytes, fixtures, refs, decoders, hydration
  outcomes, error codes, and failure precedence remain immutable.
- Canonical-v1/v2/v3 publication bytes and APIs remain immutable.
- Existing durable proof, Integrity, attempt, evidence, cache, analysis, and
  repository schemas remain unchanged.
- Builder, Runtime, and Kernel import boundaries remain unchanged.
- Runtime imports no provider module and infers no instrument type, base currency,
  settlement currency, or symbol lifecycle from an `InstrumentId` string.
- No second catalog registry, resolver, repository, cache, or provider policy is
  introduced.

## Schema-4 payload

`backtest_execution_input_bundle@4` contains the exact schema-3 payload fields plus
one field:

```text
validation_instrument_catalogs
```

It is a canonical tuple ordered by `catalog_hash`. Each entry contains exactly:

```text
{
  type: "validation_instrument_catalog_binding_v1",
  schema_version: 1,
  catalog_hash: sha256(catalog),
  catalog: <complete canonical InstrumentCatalog>
}
```

The table is a transport closure, not a registry. It is created solely from the
`StrategyOutputValidationContext.instrument_catalog` values already present in the
resolved execution-case plan before serialization.

Rules:

1. every catalog and all nested values are exact reconstructed domain types;
2. `catalog_hash == canonical_sha256(catalog)`;
3. equal hashes require byte-identical catalogs;
4. entries are unique and strictly sorted by hash;
5. every decision schedule validation-context catalog hash resolves exactly once;
6. every table entry is used by at least one validation context;
7. each context universe is exact-covered by its selected catalog;
8. sizing inputs exact-cover every target instrument as required by existing sizing;
9. no caller mapping, callback, string-prefix inference, fallback, or default catalog
   is accepted.

Schema 3 continues to use its existing cash-only reconstruction unchanged. Schema 4
uses only the exact catalog table.

## Decoder and hydration design

The schema-4 decoder may reuse existing pure scalar, instrument-definition,
financial-state, execution-plan, PREP, and semantic-spec readers. The minimum shared
refactor is to let schedule/decision-cycle plan readers receive an exact decoded
catalog lookup. Schema-3 callers pass no lookup and retain the current cash-only path;
schema-4 callers pass the closed table and may not fall back to cash inference.

The schema-4 decoder returns the existing exact common decoded execution-input value.
No v4-specific hydration model, PREP model, composition model, Engine, or durable
proof implementation is created.

Schema-4 read/hydration preserves the schema-3 failure taxonomy and redaction:
malformed request, wrong ref, unavailable, tampered, decode failed, request/build/
target/binding/PREP/semantic mismatch. Wrong request/ref type and version checks occur
before artifact I/O.

## Facade and durable proof fan-in

`BacktestRuntime.run` accepts exact schema versions 1, 2, 3, and 4.

Schema 4 is accepted only on the same durable lane required by this repair:

- no cancellation;
- requested grade is `DECISION_GRADE`;
- market reader is exact `LocalMarketBundleReader` with repository-open provenance.

Any schema-4 request outside that lane fails before execution-input artifact I/O with
exact existing outcome `execution input hydration failed: malformed_execution_request`.
There is no legacy, cancellation, or non-durable fallback.

The existing durable lane is generalized only where it currently asserts input
schema 3:

- execution-input source read dispatches by exact request/ref schema 3 or 4;
- binding verification accepts the matching exact request/ref schema;
- durable recomputation decodes the same schema again from fresh source bytes;
- static proof replay reconstructs the execution request from the proof-bound input
  ref schema;
- proof structure accepts input ref schema 3 or 4 and changes no other proof field.

All later Resolution, PREP replay, composition, two-attempt execution, independent
recomputation, proof publication, read-back, cache verification, Integrity, and
canonical-v3 publication logic is shared unchanged.

## Execution DAG

```text
C4-00 contract freeze
  -> C4-01 schema-4 catalog closure and pure round trip
       -> C4-02 durable facade/proof fan-in
            -> Tushare V2-03 route resumes
```

| Node | Outcome | Exact write set |
| --- | --- | --- |
| C4-00 | this frozen contract | `docs/implementation/plans/g12/g12m-generic-execution-input-catalog-v4.md` |
| C4-01 | schema-4 materialization, catalog decode, hydration | `packages/backtest-runtime/src/crypto_quant_backtest/execution_inputs.py`; `tests/runtime/execution_inputs/test_execution_input_bundle_v4.py`; `tests/fixtures/runtime/execution-input-bundle-v4/` |
| C4-02 | sole-facade durable proof and canonical-v3 fan-in | `packages/backtest-runtime/src/crypto_quant_backtest/facade.py`; `packages/backtest-runtime/src/crypto_quant_backtest/_durable_rebuild.py`; `tests/runtime/test_durable_rebuild_facade_v4.py`; `tests/architecture/test_execution_input_bundle_v4_boundary.py` |

C4-01 and C4-02 may be one implementation candidate after this contract is accepted,
but their write sets and acceptance assertions remain distinct. The Tushare route
file, route tests, assessment, governance registries, and acceptance matrix are not
part of this repair candidate.

## Required validation

### Protected regression locks

- exact historical v1/v2/v3 execution-input fixtures and canonical hashes unchanged;
- all existing v3 malformed/tamper/wrong-ref precedence tests unchanged;
- canonical-v1/v2/v3 publication fixtures and repository behavior unchanged;
- no new root exports or facade operations.

### Schema-4 focused tests

- deterministic cash and `xshe:000001` EQUITY catalogs round-trip exactly;
- symbol timelines, nullable base currency, quote currency, settlement currency, and
  instrument type deep-reconstruct exactly;
- duplicate, unsorted, unused, missing, hash-mismatched, context-mismatched, and
  universe-incomplete catalogs fail closed;
- nested subclasses, constructor bypass, duplicate keys, noncanonical scalars, and
  source-byte/envelope/ref tampering fail closed;
- v4 materialization rejects catalogs not already present in execution-case validation
  contexts;
- v3 materialization and decode bytes remain byte-identical.

### Durable journey

- one exact schema-4 equity request enters only `BacktestRuntime.run`;
- fresh Local Reader reopen/provenance and exact Build/Profile resolution succeed;
- two attempts, independent recomputation, proof publication/read-back, Integrity,
  cache replay, canonical-v3 ref V2, repository static replay, and analysis v2 pass;
- schema-4 cancellation, non-decision-grade, or non-Local Reader use fails with no
  fallback;
- proof/static replay rejects a v4 input ref/body/source mismatch;
- no direct Engine/Runner production call is introduced.

Run focused schema-4 tests first, then adjacent execution-input/facade/durable proof/
repository tests, then the full Backtest suite because shared Runtime files change.
Ruff, Pyright/LSP, compileall, diff checks, and gitleaks must pass or match an exact
pre-existing diagnostic baseline.

## Nonclaims

This repair does not qualify Tushare G12M by itself, authorize live/deployment, change
result grade authority, prove provider finality/completeness, provide historical
Provider Availability Time, create a general security master, or authorize any
catalog not explicitly embedded and hash-bound in its exact execution input.
