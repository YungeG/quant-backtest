# G12H current-selected development authority v1

## Decision and scope

ADR 0007 applies user-selected option B only to this finite target:

```text
UTC:           [2026-07-05T16:00:00Z, 2026-07-30T16:00:00Z)
Asia/Shanghai: [2026-07-06 00:00:00+08:00, 2026-07-31 00:00:00+08:00)
venue: XSHE
route/product: DOMESTIC + ORDINARY_A_SHARE
instrument/currency/mechanism: EQUITY, CNY/CNY, AUCTION
basis: trade_notional
```

The captured current official selections may produce a development projection. They do not establish complete official successor closure or `official_record_as_of`.

## Selected development economics

| Lineage | Development evidence | Target state |
|---|---|---|
| `exchange_handling` | SZSE current selector `raw sha256:34ce00d7302d79f7779c1774ba75db6775caf3d1772c5d60fe85eeeb0a1f0400` selects document JSON `sha256:e64eb8ad2692722a9ba8dbf633fea63c94ccba12aac14826211df72a3cdce3e0`; observed 2026-08-20 | applies bilateral, `Rate(units=341, scale=7)` = 0.0341‰ |
| `securities_regulatory` | NDRC/MOF 2018 No.917 `sha256:4c8c8426c7cc797a99a86f8d8bea21fef8f1a944d1ef14857286c9784085b3c8` plus the same SZSE current selected collection table | applies bilateral, `Rate(units=2, scale=5)` = 0.02‰ |
| `chinaclear_transfer` | ChinaClear current Shenzhen fee-list/PDF `sha256:dff4a06ce20e180f4a85ddae138211dcf7dd3246fb84775453cfd21cbaec6573`; observed 2026-08-20 | applies bilateral, `Rate(units=1, scale=5)` = 0.01‰ |
| `hkscc_transfer` | HKSCC current index `sha256:e1889113aaa223569d7348665da25314a92aca4ae3401de3e2c0ad9b0b604fd9`, Definitions `sha256:e597cef3adc516f089d834c1723c60be568ccdf3b6d361f0ac4d69964ba13e83`, and §21 `sha256:e69a75cf278195766539f79d8288cc6294497e5c80adccba23a7c70a527a914c` scope transfer fees to China Connect/HKSCC participation | not applicable to `DOMESTIC`; zero rate with nonempty authority ref |
| `stamp_duty` | NPC exact Law status `sxx=3`; NPC search `sha256:9b380f51f753df85cc0868f37c1817620affdca2da979c773a9d2b519e30c6b3`, detail `sha256:36d9986df1c05debef0c7d60ad7c112f1349d46aea7ac005cdcc751067df3fdd`, MOF No.39 `sha256:64783f48ef9b4a0650d058cec330268431f28b7ffad527add1a047a1b0184b36`, and STA exact record `sha256:214628eb5c32c3dcaecc9661c1a86a6c1731286d118f9bc98844468358f365bf` | applies seller-only, `Rate(units=5, scale=4)` = 0.5‰ |

The target contains one constant band for market fees and one constant band for stamp duty. Commission, minimum commission, broker rebates, rounding, account fees, instruction fees, settlement-message fees, safekeeping, and portfolio charges remain outside the RuleBooks.

## Identity and availability

The development snapshot binds every selected source receipt and uses:

- component-specific `observed_at` from the exact capture receipt;
- `development_evidence_available_at` equal to the latest bound receipt time;
- no `official_record_as_of` field;
- separate snapshot, declaration, event, stream, manifest, Bundle, and publication identities;
- execution RuleBook bytes derived only from finite target economics and stable target-economic authority refs.

A later capture with unchanged target economics changes snapshot/publication identity but may leave RuleBook bytes unchanged. Changed economics create new RuleBook hashes. Existing v1 and V2A compatibility bytes remain unchanged.

## Authorized delivery

ADR 0007 authorizes an additive development path:

1. freeze one current-selected development snapshot;
2. construct one finite v2 market-fee RuleBook and one finite v2 stamp-duty RuleBook with existing Kernel value types;
3. publish a new five-dimension development declaration through one off-root Builder function;
4. run the G12H analyzer against that declaration.

All official successor closure, provider authority/completeness, decision-grade, live, and deployment qualifications remain false. Strict ADR 0004 closure stays blocked and is not re-labelled as passed.
