# G12M Tushare fixed-singleton qualification v2 H1 acceptance receipt

## Acceptance outcome

`ACCEPTED_H1`. On main/candidate
`2f2bc40cc5fcd06f4f47af9c5c6e691fee00f7a6`, V2-01 through V2-04 and the
qualification route are accepted H1; V2-05 is accepted H1 by this governance fan-in.
This H1 receipt is the sole v2 route receipt. The sibling H2 blocked receipt is absent.

| Node | Final status | Accepted meaning |
| --- | --- | --- |
| V2-00 | `CONTRACT_FROZEN` | Historical contract frozen at `3023865d87e9c1699b100d3dc50e25b6a2f49440`; file `sha256:6cee644f9482826fdea7791c8c0a23568e0517361c1517361490f57f96eb43b4`. |
| V2-01 | `ACCEPTED_H1` | Exact accepted prerequisite decision; no execution output or grade minted. |
| V2-02 | `ACCEPTED_H1` | Exact G12C/D-published Local Reader Bundle with 19 accepted source Events, 19 causal `bar_open@1` projections, and one exact target Event. |
| V2-03 | `ACCEPTED_H1` | Sole-facade schema-4 execution-input implementation, canonical-v3 completed publication, durable proof, repository static replay, and analysis v2. |
| V2-04 | `ACCEPTED_H1` | Pure schema-2 source-to-Run assessment. |
| V2-05 | `ACCEPTED_H1` | This receipt and the authoritative registry/plan fan-in. |
| route | `ACCEPTED_H1` | Exact fixed-singleton historical source-bounded no-trade qualification only. |

The accepted schema-4 implementation is additive. It does not silently rewrite the
frozen V2-00 text describing the then-current schema-3 entry contract; schema-4 adds
the execution-input catalog required by the accepted route while preserving the sole
`BacktestRuntime.run(request)` facade, PREP/Resolution, durable proof, Integrity grade,
canonical-v3 publication, repository replay, and analysis-v2 authority order.

## Immutable accepted identities

- main/candidate: `2f2bc40cc5fcd06f4f47af9c5c6e691fee00f7a6`;
- V2-01 decision file: `sha256:920bd2b2b10108ef4cbcb631215b571a0198e55e526de1147e56b49d67b71ff6`;
- V2-01 semantic decision: `sha256:7e8ca1ebf63aeb4f5f36ab72073d258db64083028e6e2f4c1662941bd46c7d62`;
- direct historical predecessor: `sha256:a7a6fff66a34f20031178d82fd7da424799ecbc2b3e2c887bdd149e98cc826bb`;
- G12I report/file: `sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029` / `sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6`;
- G12K report/file: `sha256:5a49065d87286a9673893337328ddbbab9a19cd3addf178bf96033b9b1babfd7` / `sha256:a386f4281374d1449c0b5ba4371b9e9d2de5b236bc8fc5b5cdd8de5e43c65956`;
- runnable authority: `sha256:3d19c05e552aa61a7f1ff33bc2451d2d0cc13e0d3ee30acde46462bdfa65becf`;
- Build: `sha256:26048a80c045b8c49ab4f09936ab6ea3ef31acd767d54365caa20c8e457f7f45`;
- MarketBundle manifest/content: `sha256:2ea4d3c58076312ff86ee175fac2f1173fb28f01e4e4d31ca372ca0d345e750b` / `sha256:a0b6319c07aaa810ba490924f2267ebb93f72d5037432b30dd6a0a5bbb3fb8ff`;
- accepted route: `sha256:49051c693cd2ea4c1822c6e8ac6f929e0e952ccba8cfa7d5d248e18d9b7eb0f2`;
- semantic Run: `run_1eebd60b81376e15fbe4b2496ed359ab24ed644c7416812d09eb3fb715f581a9`;
- assessment: `sha256:31f29b9ab70e7c8da267b6c17dcbe294503088850c894b066116313233dca8bb`;
- immutable Bundle fixture manifest file: `sha256:5725ad59d67e38aaae6ea3579cad3a36a279ceab37d31284bf78454fbadcc020`;
- immutable Run identity fixture file: `sha256:0855cea575b8ba8e4dcd601f839bf11a5594dab3b78d28f62829cb464591cb92`;
- immutable assessment identity fixture file: `sha256:69d74c9c4b5572b91dd71c09c7570c1468b58e8dedec3f19971a799b23e31d02`.

## Exact receipt semantics

The accepted Bundle and verified Timeline contain exactly 19 unchanged accepted G12I
source Events, 19 one-to-one causal `bar_open@1` projections, and one exact target
Event: 39 Timeline Events total. Every source and projection Timeline Event precedes
the target decision phase. The run has zero target effect, orders, admissions, fills,
trades, fees, settlements, lots, exposure, entitlement, and corporate-action dispatch.
The accounting disposition is
`ZERO_EXPOSURE_NO_ENTITLEMENT_NO_CORPORATE_ACTION_DISPATCH` and does not claim action
absence. Requested/result `decision_grade` is copied exactly from the accepted
Integrity result; G12M did not mint, promote, downgrade, or otherwise decide grade.
The assessment time is not earlier than `1787299622295499670`.

## Validation evidence

The governance candidate was checked with:

```text
python exact-write-set/hash/link/status sanity check                 PASS
python Markdown fence/heading/trailing-whitespace sanity check       PASS
git diff --check                                                     PASS
gitleaks protect --staged --no-banner                              PASS
git status --short after commit                                      PASS (no staged files)
```

The exact-write-set check permits only the five V2-05 governance paths, verifies the
frozen contract and accepted evidence/fixture hashes above, requires this H1 receipt,
requires the H2 receipt to be absent, and resolves every relative Markdown link in the
five changed files. Focused V2 tests were not rerun because V2-05 changes governance
Markdown only and binds the already accepted implementation at the immutable candidate.

## Preserved limits and nonclaims

Historical Tushare qualification v1 remains immutably `BLOCKED_H2`, including its H2
receipt and terminated nodes. Binance remains accepted H3 `NO_CAUSAL_AUTHORITY`; no
Binance qualification or prospective route is created.

This H1 does not establish historical provider availability, provider finality or
completeness, listing continuity or survivorship safety, corporate-action lifecycle
closure or action absence, strict official/legal/tax/compliance closure, nonzero
execution quality, live eligibility, or deployment authorization. Provider
qualification flags remain false or limited exactly as in the accepted upstream
evidence.
