---
id: G12I-TUSHARE-CN-A-SHARE-DAILY-PURPOSE-SCOPE-V1
readiness: DRAFT
gate_status: DRAFT
owner: market-bundle-builder Tushare daily purpose-scope evidence
produces:
  - two development-only PricePurposeRequirement values
consumes:
  - G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V1
  - existing G12I coverage declaration values
depends_on:
  contract: [G12I, G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V1]
  evidence: [cn-a-share-daily-bundle-v1.expected.json]
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

## Accepted publication binding

Both requirements bind exactly to:

- event ID: `tushare-cn-a-share-daily-v1:sha256:d01518de64eb48c9b796b83bb72eeb53fe6645d4dbcc00e88311148f23adb16c`;
- event hash: `sha256:ab872662754a286bf9f41e722e739fe8f961d387d4d6cfa95e13888e0c8e8b0f`;
- stream: `tushare_cn_a_share.daily.publication.xshe.000001.v1`;
- event type: `tushare_cn_a_share_daily_publication.v1`;
- capability: `tushare_cn_a_share.daily-publications@1`;
- instrument: `InstrumentId(VenueId("xshe"), "000001")`;
- coverage: `[1704158100000000000, 1704178800000000000)` UTC nanoseconds;
- source key: `tushare.pro.daily_listing.000001.sz.20240102`;
- source hash: `sha256:c2950a35c093b983e538f97830b7b3fcb0bba1a7dac98a17bd20f6db9296f846`.

The provider-specific capability remains unchanged. This slice must not substitute
or claim generic `price_bars@1` capability.

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
3. Assert the fixture binding matches the accepted G12C/D publication fixture and
   that all excluded qualification claims remain false.
4. Run focused provider/G12I tests, the full suite, import-boundary tests, static
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
or production code.
