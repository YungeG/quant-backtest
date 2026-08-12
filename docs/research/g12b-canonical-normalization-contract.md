# G12B Synthetic JSONL v1 Normalization Contract

## Scope

G12B freezes one deliberately synthetic, provider-neutral normalization grammar to prove the generic mechanics between a verified G12A SourceSnapshot and canonical Domain/Market Data values. It does not claim that real provider data uses this grammar.

The seam reads one selected verified source member, parses strict canonical JSON Lines, maps finite Instrument and PricePurpose aliases, emits `MarketEvent` values in physical line order, preserves revision fields, and records exact bidirectional source-record provenance atomically.

## Primary authorities

- `crypto_quant_bundle_builder.SourceSnapshot.member_bytes()` is the only raw-member input.
- `crypto_quant_domain.InstrumentId`, `UtcInstant`, `Scale`, `PricePurpose`, `TimelinePhase`, `SourceSequence`, `canonical_bytes`, and `canonical_sha256` are the public canonical mapping authorities.
- `crypto_quant_market_data.MarketBundleCapability` and `MarketEvent` are the output envelope authority.
- G12C owns stream duplicate/order/capability validation; G12I owns revision-chain/coverage validation.

## Public seam

One module: `crypto_quant_bundle_builder.synthetic_jsonl`.

Root exports:

- `SyntheticJsonlV1Config`;
- `SyntheticJsonlV1RecordLocator`;
- `SyntheticJsonlV1SourceTrace`;
- `SyntheticJsonlV1NormalizationResult`;
- `SyntheticJsonlV1NormalizationFailureCode`;
- `SyntheticJsonlV1NormalizationFailure`;
- `SyntheticJsonlV1NormalizationOutcome`;
- `normalize_synthetic_jsonl_v1`.

No generic normalizer, protocol, callback, registry, field DSL, parser plug-in, cache, or provider adapter.

## Config

`SyntheticJsonlV1Config` contains only:

- `member_key`;
- `stream_key`;
- `MarketBundleCapability`;
- `TimelinePhase`;
- `instrument_bindings: tuple[tuple[str, InstrumentId], ...]`;
- `price_purpose_bindings: tuple[tuple[str, PricePurpose], ...]`.

Bindings are nonempty, canonicalized by source alias, and reject duplicate aliases. Binding input order does not affect identity. Instrument aliases match `[A-Z][A-Z0-9._-]{0,63}`; Purpose aliases match `[a-z][a-z0-9_.-]{0,63}`.

`config_hash` derives from the fixed config body. The fixed normalizer identity is `synthetic_jsonl@1`; `normalizer_spec_hash` derives from `{type="synthetic_jsonl_v1_normalizer_spec",schema_version=1,normalizer_id="synthetic_jsonl@1"}`. Grammar changes require a new version; G12B does not fabricate a runtime source-code hash.

## Selected-member and layout rules

Normalization first verifies the entire SourceSnapshot, selects exactly `config.member_key` from verified metadata, then reads only through `member_bytes()`.

A zero-byte selected member succeeds with empty Event/trace tuples and no coverage claim.

Nonempty bytes must:

- be strict UTF-8;
- contain no leading UTF-8 BOM;
- contain no raw carriage return byte;
- end in exactly one LF record delimiter;
- contain no empty physical record.

Physical line number is 1-based provenance identity. SourceSequence is exact zero-based physical line position.

## JSON rules

Each line is exactly one JSON object. Parsing rejects:

- duplicate keys at any nesting level;
- float/exponent/decimal/nonfinite tokens;
- process-global integer-limit mutation;
- noncanonical JSON bytes.

The original UTF-8 line must exact-equal `crypto_quant_domain.canonical_bytes(parsed_object)`. This freezes NFC strings, sorted keys, compact separators, canonical escaping, and integer spelling.

## Fixed record grammar

Each record has exactly these keys:

```text
available_time_epoch_nanoseconds
event_time_epoch_nanoseconds
instrument
price_scale
price_units
purpose
record_key
revision_id
schema_version
supersedes_revision_id
type
```

Rules:

- `type == "synthetic_price_point"`;
- `schema_version == 1`, non-bool integer;
- record/revision IDs match `[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}`;
- instrument and purpose use the config alias grammars;
- times are non-bool integers accepted by `UtcInstant`;
- availability is not before event time;
- `price_units` is a positive non-bool integer;
- `price_scale` is a non-bool integer accepted by `Scale`;
- `supersedes_revision_id` is null or a different valid revision ID.

## Event mapping

For physical line `n`, emit:

- Event type `synthetic_price_point.v1`;
- configured stream/capability/phase;
- mapped InstrumentId;
- exact Utc event/availability instants;
- `SourceSequence(n - 1)`;
- source revision/supersession fields unchanged;
- source key = Snapshot provenance source key;
- source hash = selected member content hash;
- primitive payload:
  - `synthetic_record_key`;
  - `price_units`;
  - `price_scale` as `Scale.places`;
  - `price_purpose` as `PricePurpose.value`.

G12B intentionally does not construct typed Price/currency, Rule, CorporateAction, Bar, or provider-specific values.

## Locator and event identity

Locator body:

```text
{type="synthetic_jsonl_line_locator",schema_version=1,member_key,line_number}
```

Event ID:

```text
"synthetic-jsonl-v1:" + canonical_sha256({
  type="synthetic_jsonl_v1_event_identity",
  schema_version=1,
  normalizer_spec_hash,
  config_hash,
  snapshot_id,
  source_key,
  locator
})
```

Events/traces retain physical-line order. G12B does not sort or deduplicate and does not certify stream order or revision legality.

## Source trace and result

One trace binds:

- snapshot ID;
- provenance hash;
- source key;
- selected member content hash;
- locator;
- Event ID/hash.

The selected member hash plus locator identifies the source record; no redundant raw-line hash is needed.

Result binds immutable config, normalizer/config identity, snapshot/provenance/source/member identities, Event tuple, exact-cover trace tuple, normalization hash, and false qualification flags.

`event_for_source_record(locator)` and `trace_for_event(event_id)` are deterministic linear lookups returning a value or None. No stored indexes/caches.

Provenance-only changes with unchanged source key preserve Event identity but change trace/result identity. Source-key, selected content, or semantic config changes affect Event/result identity.

## Failure outcome

Outcome is XOR result/failure and never returns partial Events/traces.

Failure payload contains only code, optional member key, optional locator, optional field, and derived failure hash. It does not expose raw bytes/values, exception text, path, URL, headers, or credentials.

Precedence:

1. invalid normalization input;
2. source snapshot invalid;
3. selected member missing;
4. member encoding invalid;
5. JSONL layout invalid;
6. lowest failing physical line, then:
   - JSON invalid;
   - noncanonical JSON;
   - record shape invalid;
   - unsupported record schema;
   - record field invalid in fixed field/relation order;
   - Instrument unmapped;
   - PricePurpose unmapped;
   - Event envelope invalid.

## Package boundary

G12B deliberately adds Builder → Trading Domain public-root dependency. Production imports are limited to stdlib, sibling G12A public values, `crypto_quant_domain`, and `crypto_quant_market_data`. No Domain internals, Kernel, Runtime, archive parsing, filesystem/network/process/current clock.

## Explicit exclusions

- provider acquisition or real provider schema;
- generic parser/normalizer extension system;
- manifest/schema/capability/partition/count/stream-hash validation or duplicate/order classification (G12C);
- Bar aggregation (G12G);
- rule/corporate-action economic semantics or coverage (G12H/K);
- revision-chain selection/coverage (G12I);
- publishing/repository/Reader (G12D–F);
- typed Price/currency, source completeness, decision grade, live, or deployment authorization.
