# AR09 baseline integration compatibility addendum

The parent-ratified public package is
`crypto_quant_trading.profiles.cn_a_share.portfolio_v1`. Its literal exports, in
order, are:

1. `CnASharePortfolioOrderPlanV1`
2. `CnASharePortfolioOrderProposalV1`
3. `CnASharePortfolioOpenRiskApprovalDevelopmentV1`
4. `CnAShareRebalanceExecutionPolicyV1`
5. `CnASharePortfolioSellabilitySnapshotV1`
6. `project_cn_a_share_portfolio_sellability_v1`
7. `CnAShareSharedCnyCashSnapshotV1`
8. `project_cn_a_share_shared_cny_cash_v1`

These are direct re-exports of the existing implementation objects, not wrappers
or new types. Constructors, exact-type checks, projector return types, canonical
payloads/hashes, failures and financial behavior are unchanged. Visibility does
not qualify DEVELOPMENT approvals for trading: `trade_authorized=False` remains.
The generic Trading root and existing CN profile root retain their exact bytes
and do not acquire these exports.

Runtime uses this public package for these identities, and existing generic/CN
roots for already-public identities. The import policy adds only this exact
public module. Its implementation leaves and deeper paths remain private;
generic Kernel code still cannot import concrete profiles. No boundary-checker
implementation or dependency direction changes.

Test-only integration repairs:

- Exact inventory tests recognize the existing single execution-input catalog
  versions 1–8 and public base/v2/v6/v7 materializers. They do not authorize v9 or
  a public v8 materializer; old payload/rejection contracts remain intact.
- Retained month-authority replay copies the existing publication bytes into a
  temporary repository and hardens that copy. Publisher locks and mutations are
  confined to temporary storage. Protected evidence remains unchanged, and
  corrupted or writable copies must still fail final verification. This is not
  a claim about new retention duration or qualification of the original tree.
- `calendar-source-v1.py` archives the exact historical local-Git blob
  `941898893a4194fb9da02ebf5540287f2bb27e08` from commit
  `cafd55d80b4e686dc6ad779f1bd03d2f6092b119`, SHA-256
  `0382ec521bb5d716064304faabdf976d9fe8f72eb7858eb03a673f5881b69532`.
  Tests verify that digest before loading and compare archived/current ordinary
  phase results, component references and the frozen daily bucket. The current
  calendar's additive close-bar behavior is not reverted or relabeled as
  historical bytes.

Historical JSON, receipts, golden hashes and acceptance claims are not amended.
Native Binance acquisition compatibility, business arithmetic, production
repository verification, current calendar source, provider access, market
expansion, financial sources and AR10 readiness are outside this addendum.
The parent owns independent review and the shared full-suite gate after fan-in.
