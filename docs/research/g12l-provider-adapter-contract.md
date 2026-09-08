# G12L Provider Qualification Contract

## Decision status

The provider-neutral G12L contract is frozen as documentation only. No market,
provider, dataset, request shape, transport, adapter interface, or raw fixture is
selected. Every concrete `G12L-<PROVIDER>-<DATASET>-<VERSION>` slice remains
`DRAFT / BLOCKED` until it supplies real provider evidence.

This note is the research authority for the common obligations. Gate status
remains authoritative only in `docs/implementation/acceptance-matrix.md`.

## Common obligations

A future concrete provider slice must satisfy all of these obligations without
adding meaning that only the provider can establish:

1. **Finite explicit scope.** Acquisition is bounded before execution by a
   provider-defined finite time, sequence, revision, or member scope. The slice
   rejects `latest`, `current`, `now`, open-ended polling, and scope expansion.
2. **Source authority and version.** Evidence identifies the authoritative
   provider publication, dataset, endpoint/archive contract, version or
   effective revision, and the exact documentation used to interpret it.
3. **Deterministic raw identity.** The slice freezes the authoritative byte
   boundary and a deterministic ordered `RawSourceMember` plan. Member keys,
   modes, exact bytes, declared hashes, and caller-supplied acquisition times
   obey G12A; parsing or normalization does not rewrite acquisition bytes.
4. **Exact G12A handoff.** Only a complete ordered member set and sanitized
   `SourceSnapshotProvenance` enter `freeze_source_snapshot()`. Success records
   the exact G12A `snapshot_id`, content-tree hash, and `provenance_hash`.
5. **Idempotent retry and resume evidence.** Offline fixtures prove that bounded
   retries and interruption/resume produce the same final member keys, modes,
   bytes, declared hashes, and G12A content identity as uninterrupted capture.
   The concrete slice documents how acquisition timestamps affect provenance.
6. **Atomic failure.** If any requested page, shard, member, revision, or
   correction cannot be acquired and closed, the slice returns one failure,
   calls no G12A freeze handoff, and exposes no partial snapshot or bundle.
7. **Secret redaction.** Credentials, signatures, cookies, tokens, private URLs,
   sensitive headers, and exception text enter neither raw members, canonical
   provenance, logs, failure values, fixture bytes, nor immutable evidence.
8. **Offline unit tests.** Unit and acceptance tests use sanitized real byte
   fixtures and injected provider-specific fakes. They perform no DNS, socket,
   HTTP, filesystem scan, dynamic import, or wall-clock fallback.
9. **No qualification claim.** All existing development/qualification flags
   remain false. G12L does not make G12H, G12I, G12K, any `G12L-*`, or G12M
   ready; it does not authorize decision-grade, live, or deployment use.
10. **Immutable evidence.** READY evidence records hashes for provider docs or
    archived references, every sanitized raw fixture, retry/resume and failure
    fixtures, the G12A snapshot/provenance outputs, downstream mapping fixtures,
    and generated acceptance reports.

## Exact failure precedence

Each concrete provider slice must expose these top-level codes in this order.
Provider error codes and multi-fault fixture cases must map to the earliest
applicable code; ties use the earliest item in the provider slice's frozen
request/member order:

1. `CONFIGURATION_INVALID`
2. `PROVIDER_UNAVAILABLE`
3. `AUTHENTICATION_REJECTED`
4. `RATE_LIMIT_EXHAUSTED`
5. `SOURCE_SCHEMA_MISMATCH`
6. `NORMALIZATION_FAILED`
7. `DATA_GAP_DETECTED`

Every failure is atomic and secret-free. This common ordering does not prescribe
provider retry counts, status-code semantics, cursor rules, or error payloads.

## Facts owned only by a concrete provider slice

The common contract does not invent or standardize:

- request parameters, authentication/signing, endpoint/archive paths, or
  transport libraries;
- dataset fields and exact mapping to already-frozen G12B schemas;
- page size, cursor/token/sequence behavior, ordering, or closure proof;
- correction, supersession, cancellation, terminal-revision, or archive
  retention semantics;
- exchange calendar, session, holiday, outage, availability, or gap claims;
- raw sample payloads, member naming, chunking, compression, or byte boundaries.

Each concrete slice owns and freezes those facts from real provider documents and
sanitized real fixtures. It may not fill historical gaps with a current endpoint,
forward-fill absent facts, or infer completeness from a locally valid subset.

## Why there is no executable common schema

A static providerless schema would validate invented field names rather than a
real acquisition contract. G12A and G12B already provide executable providerless
mechanics. G12L therefore adds no production code or synthetic fixture; the first
executable G12L contract belongs to the first selected provider slice.
