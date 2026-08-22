---
id: DRP-01
owner: market-data-contracts
status_authority: README.md
produces:
  - exact private repository reopen/read result from LocalMarketBundleReader.open provenance
  - exact current G12D publication/retention bodies and hashes
consumes:
  - DRP-00 H1 contract
  - existing G12D local Bundle repository bytes
depends_on:
  contract: [DRP-00-H1]
  evidence: [g12d-local-publication-fixtures]
  write_conflict: [local-market-bundle-reader-private-provenance]
---

# DRP-01 minimal repository provenance on the existing Local Reader

## Vertical outcome

Preserve `LocalMarketBundleReader.__init__(delegate)`,
`LocalMarketBundleReader.open(*, repository_root, bundle_ref)`, Reader behavior,
`__all__`, and package-root exports. Add only the DRP-00-frozen private provenance
retention to Readers returned by `open` and one exact versioned package-internal
read/reopen interface used by backtest-runtime.

No `LocalMarketBundleAttestedOpenV2`, public token, new Reader protocol, registry,
framework, constructor parameter, overloaded `open`, or root export is added.

## Required behavior

- `open` continues to execute the current immutable-tree, manifest, publication,
  retention, stream coverage, payload, canonical-byte, and read-only checks.
- Its returned exact Local Reader privately retains only the normalized absolute root,
  exact Bundle ref, and minimum verified values needed to repeat those checks.
- The direct constructor creates a normal Reader with no repository-open provenance
  and therefore remains on the current non-attested/blocked path.
- Lane selection may inspect only exact Reader type and presence of this private
  provenance; it does not invoke the fresh interface or trust retained body values.
- After selection, the versioned package-internal interface freshly reopens through
  the existing `open`, exact-decodes the current G12D publication and retention bodies,
  verifies their hashes and all referenced local files, and returns the exact private
  result frozen by DRP-00. Failure or tamper is pre-Integrity with no legacy fallback.
- Absolute root/path state is operational only and never enters canonical bytes,
  equality used for artifacts, repr-derived content, or an ArtifactEnvelope.

The captured claim is current retrievability of the exact verified local tree under
the cooperative filesystem model. It does not claim future retention policy truth,
trusted root identity, remote durability, copied-tree detection, or hostile-process
resistance.

## Rejection contract

Tests prove that subclasses, lookalikes, `InMemoryMarketBundleReader`, arbitrary
`MarketBundleReader` implementations, direct Local Reader construction, and absent
private provenance never select the lane. For an exact `open`-created Reader, stale
provenance, relative-root drift, wrong refs, path escape, and every tree/body/hash
mutation are detected by the post-selection fresh reopen and fail pre-Integrity without
falling back.

Non-selected values continue through their existing Reader paths. A selected value
never downgrades merely because fresh verification fails.

## Acceptance

- existing Local Reader tests/goldens and constructor/open signature snapshots pass;
- one focused test proves selection uses provenance presence only, then freshly reopens
  and obtains byte-identical typed G12D bodies/hashes;
- mutation tests prove selected-lane pre-Integrity failure/no fallback, and copied-
  valid-tree tests enforce the exact claim ceiling;
- no path enters canonical serialization;
- package root exports are byte-identical; and
- architecture checks show no Runtime, Builder, registry, or generic Reader dependency.
