# G12B Canonical Normalization Contract Research

## Status

G12B remains DRAFT. G12A now provides deterministic verified source-member bytes and provenance, but the repository does not yet define a raw record grammar, selected-member rule, record locator, mapping-config schema, or normalization failure precedence. Choosing a provider format or parser framework without that authority would freeze invented behavior.

## Existing public contracts G12B can reuse

| Required concept | Existing authority | Notes |
| --- | --- | --- |
| Source input | `crypto_quant_bundle_builder.SourceSnapshot` | Raw bytes only through verified `member_bytes(member_key)` |
| Instrument identity | `crypto_quant_domain.InstrumentId` | `InstrumentDefinition`, `InstrumentCatalog`, and `SymbolTimeline` exist where required |
| UTC time | `crypto_quant_domain.UtcInstant` | Local/ambiguous time must use explicit supplied resolution policy |
| Numeric scale | `crypto_quant_domain.Scale` and fixed-point values | No float or implicit rounding |
| Price purpose | `crypto_quant_domain.PricePurpose` | Explicit mapping required |
| Event envelope | `crypto_quant_market_data.MarketEvent` | Canonical primitive payload only |
| Revision evidence | `MarketEvent.revision_id` / `supersedes_revision_id` | No generic public `Revision` class |
| Deterministic event order fields | `TimelinePhase`, `SourceSequence` | Generation rule must be frozen by the source grammar |

## Missing public contracts

- There is no generic public record class literally named `Instrument`; the existing identity/definition/catalog contracts must be used explicitly.
- There is no generic public `Rule` record.
- There is no generic public `CorporateAction` record.
- Kernel rule/corporate-action profile types are not Builder normalization contracts.

Until a separate public contract owns those typed semantics, G12B can only produce an explicitly classified `MarketEvent` envelope with canonical primitive payload and complete source provenance. It cannot claim that a Builder-local payload schema is the system-wide Rule or CorporateAction domain model.

## Smallest truthful eventual boundary

One verified `SourceSnapshot` plus one frozen, finite source grammar/config enters. G12B returns an atomic in-memory tuple of canonical `MarketEvent` values plus Builder-local bidirectional source trace and versioned normalization code/config identity for G12C.

Each source trace must bind:

- SourceSnapshot ID and provenance hash;
- member key and member content hash;
- grammar-defined logical record locator;
- emitted Event ID/hash.

Default event source evidence should reuse the snapshot provenance source key and exact member content hash. G12B must not inspect `archive_bytes`, parse tar/gzip, read filesystem/network/process/clock, or import Runtime/Kernel implementation modules.

## Rules that require a selected source contract

The first implementable grammar must freeze:

1. exact provider/member format and supported schema version;
2. member-selection rule;
3. logical-record locator grammar;
4. parser/config canonical identity preimage;
5. mapping table/config schema;
6. explicit UTC/offset or frozen-zone conversion;
7. exact scaled-integer conversion and rejection of inexact values;
8. Instrument mapping and unknown/ambiguous failure;
9. PricePurpose mapping;
10. Event type/payload mapping;
11. revision and supersession preservation;
12. Timeline phase/source-sequence generation;
13. structured failure precedence;
14. atomic no-partial-output behavior.

## Explicit exclusions

G12B does not own:

- manifest/schema/capability/partition/count/stream-hash validation, duplicate/order classification (G12C);
- Bar aggregation (G12G);
- price/availability/revision coverage or revision selection (G12I);
- rule/corporate-action coverage or economic lifecycle semantics (G12H/G12K);
- publishing/repository/Reader (G12D–F);
- provider acquisition/adapters (G12L);
- Kernel private state, Runtime views, decision-grade qualification, or deployment authorization.

## Package dependency

When a real grammar is frozen, G12B will need the target plan's explicit Builder → Trading Domain public-root dependency in addition to Market Data Contracts. That change must be deliberate in package metadata and import policy; Domain types must not be re-exported through Market Data merely to avoid the dependency.

## Recommended next step

Do not create `normalization.py` or a READY Acceptance Card yet. Select the first raw source contract, or explicitly authorize a synthetic-only v1 grammar whose only purpose is to freeze the generic normalization mechanics before provider adapters exist.
