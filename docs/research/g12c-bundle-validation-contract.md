# G12C Bundle Validation and Manifest Contract

## Decision

G12C validates a caller-supplied immutable tuple of canonical `MarketEvent` values and derives the existing `MarketBundleManifest`. It does not add a second manifest schema, a Reader, a repository, or a generic validation framework.

This is the narrowest truthful vertical seam after G12B:

- each nonempty caller-order subsequence sharing one `stream_key` is one logical in-memory partition;
- its existing `MarketStreamManifest` is the partition evidence and content hash;
- provenance at this Gate is the typed `MarketEvent.source_key` and `source_hash` transitively committed by the event tuple and stream hash;
- physical file/chunk partition layout, authenticated SourceSnapshot replay, publication, retention, Reader construction, and coverage qualification remain later Gates.

An empty Event tuple is structurally valid and yields an empty stream/capability manifest. It makes no claim about coverage completeness, publication eligibility, decision grade, or deployment authorization.

## Reused authority

G12C reuses public Market Data contracts without modifying them:

- `MarketEvent.ordering_key`;
- `MarketStreamManifest.from_events()` for event count and tuple content hash;
- `MarketBundleManifest.build()` for canonical stream ordering, derived capability declarations, and Bundle content identity;
- `MarketBundleRef.from_manifest()` as an external repeat-parity assertion only.

`InMemoryMarketBundleReader` is not used because it sorts events and would conceal reversed caller input.

## Public seam

The Builder root adds exactly:

- `BundleValidationFailureCode`;
- `BundleValidationFailure`;
- `BundleValidationOutcome`;
- `validate_market_bundle_v1`.

```python
validate_market_bundle_v1(
    *,
    bundle_key: str,
    schema_version: int,
    coverage_start: UtcInstant,
    coverage_end_exclusive: UtcInstant,
    instrument_catalog_hash: str,
    events: tuple[MarketEvent, ...],
) -> BundleValidationOutcome
```

The function accepts no caller-declared capabilities, stream manifests, physical partition IDs, paths, refs, Snapshot, normalization result, callback, protocol, registry, or plugin.

## Success derivation

For each distinct `stream_key`, retain the unchanged caller-order subsequence `E_s`. After validation:

1. derive `MarketStreamManifest.from_events(s, E_s)`;
2. derive Bundle capabilities exactly from the resulting stream manifests;
3. call `MarketBundleManifest.build(...)` with the caller header and derived values.

The existing manifest hash is the only success identity. Source key/hash changes must change the affected Event, stream, and Bundle identities.

## Structured failures

`BundleValidationOutcome` contains exactly one of `manifest` or `failure`. A failure never carries a partial manifest, stream, Event, payload, trace, raw record, path, or exception text.

Failure codes are exactly:

1. `invalid_input`;
2. `duplicate_event_id`;
3. `event_outside_coverage`;
4. `stream_classification_mismatch`;
5. `duplicate_stream_ordering_key`;
6. `stream_order_regression`.

`BundleValidationFailure` contains `{code, stream_key, input_position}`. Positions are zero-based and refer to the original caller tuple. Its canonical body is:

```json
{"code":"...","input_position":null,"schema_version":1,"stream_key":null,"type":"market_bundle_v1_validation_failure"}
```

`failure_hash = canonical_sha256(body)`.

## Validation precedence

Precedence is global by category, then earliest original input position inside that category:

1. invalid header, non-tuple input, non-exact `MarketEvent`, or malformed/tampered Event envelope;
2. duplicate Bundle-wide Event ID;
3. Event time outside `coverage_start <= event_time < coverage_end_exclusive`;
4. mixed `(event_type, capability)` within one stream;
5. duplicate `ordering_key` within one stream;
6. decreasing `ordering_key` within one stream.

Validation inspects original order and never sorts to repair input. Duplicate ordering key wins over order regression. Non-contiguous `SourceSequence` is valid. Equal ordering keys across different streams remain WP-06B `DeterministicTimeline` authority.

## Explicit exclusions

G12C does not own:

- changes to `crypto_quant_market_data` public schemas;
- physical partitions, file paths, chunks, Parquet, Arrow, or memory mapping;
- atomic publication, content-addressed repository, concurrent deduplication, or retention;
- Reader/Cursor construction or page/batch parity;
- global cross-stream Timeline ordering;
- SourceSnapshot authenticity or re-running a G12B normalizer;
- normalization/config/trace tables beyond provenance already committed in Events;
- Instrument catalog membership validation;
- Bars, Rule, Universe, corporate-action, availability, revision, or gap coverage;
- provider acquisition, decision-grade qualification, or deployment authorization.

## Frozen evidence

Fixture ID: `synthetic-jsonl-bundle-validation-v1`.

The fixture starts from the frozen G12B Synthetic JSONL v1 normalization result and freezes:

- exact stream/event count/hash and derived capabilities;
- Bundle manifest/ref repeat parity;
- source-field sensitivity;
- every structured failure and precedence;
- atomic no-manifest failure;
- non-contiguous sequence success;
- cross-stream equal-key handoff to WP-06B;
- empty structural success without qualification claims.
