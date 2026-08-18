---
id: G12CD-CN-A-SHARE-DEVELOPMENT-RULE-AUTHORITIES-V1
readiness: READY
gate_status: READY
owner: market-bundle-builder internal A-share development rule publication
produces:
  - five development-only MarketEvents preserving the frozen G08H rule authorities
  - one unchanged G12C/D rule-authority Bundle publication
consumes:
  - G08H immutable development profile fixture and five typed rule authorities
  - unchanged G12C validation and G12D local publication seams
depends_on:
  contract: [G08H, G12C, G12D]
  evidence: [cn-a-share-resolved-profile-composition-v1, g12h-rule-coverage]
fan_out: [G12H]
---

# G12C/D China A-share Development Rule Authorities v1

## Status

`READY`. This is the smallest prerequisite for G12H: freeze one exact,
development-only G12C/D publication of the five rule authorities already accepted
by G08H. It does not claim provider truth, historical external completeness,
G12H coverage qualification, decision grade, live use, or deployment authority.

The user instruction to continue authorizes implementation only at the internal
seam below. G08H production modules, G12C/D APIs, Builder root exports, and all
previously PASSED fixtures remain unchanged.

## Single internal seam

```text
project_cn_a_share_development_rule_authority_events_v1(
  declaration: Mapping[str, object], /
) -> tuple[MarketEvent, ...]
```

The function belongs only in
`crypto_quant_bundle_builder.cn_a_share_development_rule_bundle`. It accepts one
exact canonical mapping rather than Runtime or Trading Kernel objects, so Builder
production code imports neither package. It adds no class, Protocol, adapter,
registry, resolver, factory, repository wrapper, Reader, HTTP path, or root export.

## Declaration schema

The declaration is exact schema v1:

```text
type = cn_a_share_development_rule_publication_declaration
schema_version = 1
profile = {
  profile_key,
  profile_version,
  profile_request_hash,
  market_profile_digest,
  component_manifest_hash,
  source_manifest_hash
}
target_coverage = {
  start_epoch_nanoseconds,
  end_exclusive_epoch_nanoseconds,
  available_at_epoch_nanoseconds
}
authorities = {
  calendar,
  order_rules,
  market_fees,
  stamp_duty,
  corporate_action_entitlements
}
qualification = {
  provider_authority_qualified=false,
  revision_closure_complete=false,
  rule_coverage_qualified=false,
  decision_grade_eligible=false,
  deployment_authorized=false
}
```

Each authority entry is exactly `{authority_hash, body}`. `body` is the canonical
G08 authority body and must have schema version `1`, the exact dimension-specific
type below, and `canonical_sha256(body) == authority_hash`:

| Dimension | Canonical body type |
| --- | --- |
| `calendar` | `cn_a_share_frozen_calendar` |
| `order_rules` | `cn_a_share_order_rule_book` |
| `market_fees` | `cn_a_share_market_fee_rule_book` |
| `stamp_duty` | `cn_a_share_stamp_duty_rule_book` |
| `corporate_action_entitlements` | `cn_a_share_corporate_action_entitlement_rule_book` |

The accepted fixture must bind the existing G08H development profile exactly:

- profile key/version: `equity.cn_a_share.v1` / `1`;
- request hash: `sha256:90daf7523375d75c80745f204d5ebc05e499c73c20fbc2d956fc2c4ec1cdec54`;
- market-profile digest: `sha256:96e4ad0eb29a8900c681a7d5749e7965a968b1d475566083874f838e972206ec`;
- component-manifest hash: `sha256:cdb1a733f80fea1222bdad43d5455d21401a8b804bdf9dea563faff6f1266daa`;
- source-manifest hash: `sha256:cbe00cafd2822c127c489fb73eb1b7e513e3dd5b72fb7e0918112e7df6560e1a`;
- target coverage: `[1783267200000000000, 1785427200000000000)` ns;
- available at: `1784541600000000000` ns.

The committed declaration fixture is compared test-only against exact canonical
bytes from `build_cn_a_share_resolved_request()` and `CnAShareProfileComposer`.
No Builder production import crosses into Runtime or Trading Kernel.

## Event contract

The output tuple uses this immutable order:

1. `calendar`
2. `order_rules`
3. `market_fees`
4. `stamp_duty`
5. `corporate_action_entitlements`

All events have:

- capability `cn_a_share.development-rule-authorities@1`;
- `instrument_id=None`;
- `event_time=target_coverage.start`;
- `available_time=target_coverage.available_at`;
- phase `market_data` rank `0`;
- no superseded revision;
- source sequence equal to the dimension index;
- revision/source hash equal to that dimension's authority hash.

For dimension `<dimension>`:

```text
stream_key = cn_a_share.development.rule_authority.<dimension>.v1
event_type = cn_a_share_development_<dimension>_authority.v1
event_id = cn-a-share-development-rule-authority-v1:<dimension>:<authority_hash>
source_key = equity.cn_a_share.v1/<dimension>
```

Each payload is exact:

```text
{
  declaration_hash,
  profile,
  target_coverage,
  dimension,
  authority_hash,
  authority,
  qualification
}
```

The function deep-rebuilds canonical input before projection and rejects any
missing/extra field, noncanonical value, wrong exact type/version/hash, invalid
coverage/availability, incomplete authority set, or non-`false` qualification.
Failure returns no partial tuple.

## G12C/D composition

Tests pass all five events unchanged to `validate_market_bundle_v1`, serialize
each one-event stream with `canonical_bytes`, and publish through the unchanged
`LocalMarketBundleRepository`. The fixed Bundle key is
`cn-a-share-development-rule-authorities-20260706-20260731-v1`; the required
opaque development `instrument_catalog_hash` is all-zero SHA-256 and grants no
G12K catalog authority. Retention policy is
`retention.g12cd-cn-a-share-development-rule-authorities-v1`.

## RED and acceptance

Fixture IDs:

- `cn-a-share-development-rule-publication-declaration-v1`;
- `cn-a-share-development-rule-publication-v1`.

Focused commands:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --locked pytest -q \
  tests/bundle_builder/rule_authorities/test_cn_a_share_development_rule_bundle.py \
  tests/architecture/test_g12cd_cn_a_share_development_rule_bundle_boundary.py

uv run --locked python tools/architecture/check_import_boundaries.py \
  --root . --policy architecture/import-boundaries.toml \
  --report build/acceptance/g12cd-cn-a-share-rule-authorities-import-boundaries.json
```

Acceptance additionally requires full repository tests, clean LSP/lens/secret
checks, immutable event/stream/manifest/retention hashes, clean detached-worktree
replay, and independent review `NONE`.

## Explicit non-goals

No generic rule schema, rule evaluator, coverage analyzer, profile resolver,
provider adapter, source acquisition, calendar inference, revision repair,
Runtime/Kernel production import, G12H/I/K/L/M qualification, decision-grade
claim, live use, or deployment authorization.
