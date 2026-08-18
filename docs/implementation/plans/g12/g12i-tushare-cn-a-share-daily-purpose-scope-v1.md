---
id: G12I-TUSHARE-CN-A-SHARE-DAILY-PURPOSE-SCOPE-V1
readiness: PASSED
gate_status: PASSED
owner: market-bundle-builder Tushare daily purpose-scope evidence
produces:
  - two development-only PricePurposeRequirement values
  - one test-only canonical publication-purpose binding fixture
consumes:
  - G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V1
  - existing G12I coverage declaration values
depends_on:
  contract: [G12I, G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V1]
  evidence:
    - cn-a-share-daily-bundle-v1.expected.json
    - cn-a-share-daily-purpose-scope-v1.expected.json
fan_out: []
---

# G12I Tushare China A-share Daily Purpose Scope v1

## Outcome

Freeze exactly two passive, development-only `PricePurposeRequirement` values for
the accepted `000001.SZ / 2024-01-02` Tushare daily publication: one
`EXECUTION_REFERENCE` requirement and one `VALUATION` requirement.

This is a finite provider-specific purpose-scope sub-slice. It reuses the existing
G12I declaration types and the PASSED G12C/D publication without production code,
new exports, or a resolver/analyzer.

## Status

`PASSED`. The static fixture freezes the two exact requirement values and one
canonical test-only binding to the accepted publication. Requirement hashes are:

- execution reference: `sha256:eedbfd66e6b4b0d63e5bab9c1bd239bc307b8a8571b027157eb825985d5d8066`;
- valuation: `sha256:8d410aad09e114cda8cd3beccc6cc551a2493983901c9d78ac59f5b3d1775dc3`.

Publication-purpose binding hash:
`sha256:4f14022355362ad536fe67794a4d9d0143c7987870d2abf8dadbcb9f16b9ebbc`.

This status applies only to this finite development-purpose declaration fixture and
does not change G12I, G12L, decision-grade, or deployment readiness.

## Accepted publication binding

Both requirements bind exactly to:

- event ID: `tushare-cn-a-share-daily-v1:sha256:d01518de64eb48c9b796b83bb72eeb53fe6645d4dbcc00e88311148f23adb16c`;
- event hash: `sha256:ab872662754a286bf9f41e722e739fe8f961d387d4d6cfa95e13888e0c8e8b0f`;
- bundle key: `tushare-cn-a-share-daily-000001-20240102`;
- manifest hash: `sha256:f343a0d9e4d86659ad0b1c73c888d050886f9713acedc77fc31fc16202fbce3f`;
- manifest content hash: `sha256:7d87625e9fce5b3f668a8f1ba9a3e302a09dc334b28b61760a8212a6818f80fc`;
- stream content hash: `sha256:27bb8945601e9a869e609bb8c146a998fca06878061950f294c2a0dabacd426c`;
- stream: `tushare_cn_a_share.daily.publication.xshe.000001.v1`;
- event type: `tushare_cn_a_share_daily_publication.v1`;
- capability: `tushare_cn_a_share.daily-publications@1`;
- instrument: `InstrumentId(VenueId("xshe"), "000001")`;
- coverage: `[1704158100000000000, 1704178800000000000)` UTC nanoseconds;
- source key: `tushare.pro.daily_listing.000001.sz.20240102`;
- source hash: `sha256:c2950a35c093b983e538f97830b7b3fcb0bba1a7dac98a17bd20f6db9296f846`.

The provider-specific capability remains unchanged. This slice must not substitute
or claim generic `price_bars@1` capability.

## Canonical test-only binding

The fixture freezes one canonical body with type
`tushare_cn_a_share_daily_publication_purpose_binding`, schema version `1`, the
accepted Event ID/hash, complete frozen `MarketBundleRef`, manifest content hash,
stream content hash, and the ordered `(price_purpose, requirement_hash)` pair for
`EXECUTION_REFERENCE` and `VALUATION`. Its binding hash is recomputed with
`canonical_sha256`.

Tests reconstruct this body only from the accepted publication fixture and the two
exact `PricePurposeRequirement` values. Replacing either the publication Event hash
or either requirement hash changes the binding hash. This is test evidence only,
not a production or generic artifact/API.

## Frozen requirements

### Execution reference

- requirement key: `tushare_cn_a_share.daily.execution-reference.xshe.000001.20240102.v1`;
- scope key: `tushare_cn_a_share.daily.purpose-scope.xshe.000001.20240102.execution-reference.v1`;
- purpose: `EXECUTION_REFERENCE`;
- stale policy key: `tushare_cn_a_share.daily.execution-reference.exact-bucket.v1`;
- stale policy version: `1`;
- maximum age: `0` nanoseconds;
- forward fill: `false`.

### Valuation

- requirement key: `tushare_cn_a_share.daily.valuation.xshe.000001.20240102.v1`;
- scope key: `tushare_cn_a_share.daily.purpose-scope.xshe.000001.20240102.valuation.v1`;
- purpose: `VALUATION`;
- stale policy key: `tushare_cn_a_share.daily.valuation.exact-close.v1`;
- stale policy version: `1`;
- maximum age: `0` nanoseconds;
- forward fill: `false`.

Zero age and no forward fill keep both declarations exact and conservative. They do
not resolve a mark or prove that any requested instant is available.

## Test-first evidence

1. Add a RED provider test that reconstructs both values with existing
   `BuilderStaleMarkPolicy` and `PricePurposeRequirement` and requires one missing
   static fixture.
2. Add the fixture with exact canonical values and hashes.
3. Assert the canonical binding body/hash matches the accepted G12C/D Event,
   bundle/manifest identity, and both exact requirement hashes.
4. Mutate publication and requirement identities independently and prove neither
   replacement retains the frozen binding hash.
5. Assert all excluded qualification claims remain false.
6. Run focused provider/G12I tests, the full suite, import-boundary tests, static
   type/LSP-equivalent checks available in the repository, and secret scanning.

## Explicit non-claims

This slice does not claim or produce:

- market availability closure or gap classification;
- revision terminal-set closure or correction finality;
- generic `price_bars@1` capability;
- G12I analyzer/report readiness;
- G12L/provider qualification;
- historical listing or corporate-action qualification;
- decision-grade eligibility;
- deployment authorization.

It does not edit the Acceptance Matrix, shared plans README, G12I analyzer status,
or production code, and it adds no generic binding artifact.
