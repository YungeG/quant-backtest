---
id: DRP-05
owner: backtest-runtime-governance
repository: Backtest
status_authority: README.md
produces:
  - one docs-only Backtest governance fan-in commit
  - unique Matrix row PASSED binding immutable Backtest and Platform commits
consumes:
  - immutable DRP-03 Backtest implementation candidate commit and validation
  - immutable DRP-04 Platform consumer-v2 commit and exact submodule-pin evidence
depends_on:
  contract: [DRP-03, DRP-04]
  evidence: [backtest-candidate-acceptance, platform-consumer-v2-acceptance, exact-submodule-pin]
  write_conflict: [unique-g07-durable-rebuild-proof-v2-matrix-row]
---

# DRP-05 docs-only governance fan-in

## Vertical outcome

Create one final Backtest docs-only commit that changes only the unique
`G07-DURABLE-REBUILD-PROOF-V2` row in
`docs/implementation/acceptance-matrix.md` and the DRP-04/DRP-05 status projection in
this DAG's `README.md`. Bind the immutable DRP-03 Backtest implementation-candidate
SHA, immutable DRP-04 Platform consumer-v2 SHA, exact Platform `backtest` gitlink SHA,
commands/results, and artifact hashes, then atomically record external DRP-04
acceptance, DRP-05 acceptance, and Matrix `PASSED`.

This node writes no code, tests, fixtures, other plan file, other Matrix row, Platform
file, or submodule pointer. Accepted historical `G07 PASSED`, all G12M facts and
receipts, provider status, Profile/Build registry, Resolution policy, and deployment
status remain unchanged.

## Immutable fan-in checks

Before editing status, verify:

1. the DRP-03 Backtest candidate commit is immutable and all recorded Backtest focused,
   full, architecture, compatibility, recovery, diff, and gitleaks checks pass;
2. the DRP-04 Platform commit is immutable and its `backtest` gitlink equals exactly
   the DRP-03 SHA;
3. Platform V1 bytes remain exact and consumer-v2 passes
   `run → load_completed_v3 → derive → load_analysis_v2` plus unchanged V1 operations;
4. mismatch→FAILED, Resolution-first, manifest v2, static-replay versus local-cache
   claims, and recovery refusal evidence match the DRP-00 contract; and
5. no blocker, uncommitted file, staged file, or cross-repository mixed commit remains.

The Matrix row records both immutable commits and the typed submodule-pin edge rather
than treating the Platform commit as mutable external prose.

## Why Platform remains on the code commit

DRP-05 changes only Backtest documentation/status. It changes no package byte, public
API, fixture, operation dispatch, or consumer behavior. Therefore Platform may remain
pinned to the exact DRP-03 Backtest code commit and is still correct; it must not
create a second pointer-only Platform commit merely to point at this DRP-05
governance descendant.

## Acceptance

- `git diff <DRP-03-sha>..HEAD -- docs/implementation/acceptance-matrix.md
  docs/implementation/plans/g07-durable-rebuild-proof-v2/README.md` shows only the
  unique row plus DRP-04/DRP-05 status governance closure after accounting for this
  commit;
- a row-uniqueness check finds exactly one `G07-DURABLE-REBUILD-PROOF-V2` registry row;
- Matrix/DAG authority, Markdown/frontmatter/local links, and acyclicity checks pass;
- `git diff --check`, docs-only/repository diff checks, and gitleaks pass;
- the commit contains only `docs/implementation/acceptance-matrix.md` and
  `docs/implementation/plans/g07-durable-rebuild-proof-v2/README.md`; and
- the Backtest working tree is clean after one commit.

Acceptance proves only the generic same-accepted-build local durable verification and
analysis-ready consumer seam. It does not qualify a provider, establish a trusted
root, guarantee future/remote durability, authorize live use, or authorize deployment.
