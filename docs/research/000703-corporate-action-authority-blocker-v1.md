# 000703 corporate-action authority blocker v1

## Verdict

**BLOCKED — fail closed.** No finite `000703.SZ` corporate-action, register, and identity declaration is produced.

Ticket #27 needs finite coverage of the discovery and OOS windows, explicit action/revision/cancellation facts, registered-position evidence, and one immutable source-manifest identity. The retained January smoke intentionally sets `corporate_action_absence_claimed=false`; it cannot be relabelled as an empty action history.

## Evidence

- `tools/acquisition/cn_a_share_tushare_authority.py` can retain one candidate capture of `stock_basic`, `namechange`, adjacent `adj_factor`, and `dividend(ex_date=target)`. Its receipt fixes `provider_revision_id=null`, `revision_closure_complete=false`, and `corporate_action_lifecycle_qualified=false`.
- `tools/acquisition/cn_a_share_tushare_000703_202401_month_smoke_v1.py` captures daily/status/limit evidence only and explicitly preserves `corporate_action_absence_claimed=false`.
- `docs/research/g12l-tushare-listing-corporate-action-revision-authority-v1.md` and `docs/research/tushare-cn-a-share-listing-history-primary-sources.md` establish that `dividend` and `adj_factor` do not expose a revision/cancellation lineage, terminal completeness, or authoritative zero-row absence.

## Existing fail-closed route

`CnAShareProfileComposer` already returns existing structured failures before profile construction:

1. `MISSING_ANNOUNCEMENT_REVISION_SET`;
2. `MISSING_REGISTER_REVISION_SET`;
3. `MISSING_IDENTITY_HISTORY`;
4. `REVISION_CLOSURE_MISMATCH` for an open or cancelled revision chain.

Creating empty declarations, inferring no action from a zero-row `dividend` response, or treating an adjustment-factor series as an action ledger would bypass those controls.

## Required to unblock

Retain, for every target action, authoritative final implementation-announcement bytes with revision/replacement/cancellation lineage, an authoritative registered-position snapshot at the record boundary, and identity declarations sharing the same finite source-manifest coverage. Until then, keep the existing structured composition blocker and do not emit a corporate-action RuleBook, entitlement, cash payment, or share-delivery evidence for `000703.SZ`.
