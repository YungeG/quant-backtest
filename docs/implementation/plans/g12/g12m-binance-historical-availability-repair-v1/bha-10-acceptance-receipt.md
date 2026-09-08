---
id: G12M-BHA-10-ACCEPTANCE-RECEIPT
status: ACCEPTED_H3
route: H3_NO_CAUSAL_AUTHORITY
source_tip: 600259a9f22e44102e5e60faab3176cbf5761e6e
---

# G12M-BHA-10 acceptance receipt

## Accepted route

`H3 — NO_CAUSAL_AUTHORITY` is final for the Binance 2024 historical repair.
BHA-03 through BHA-09 are permanently `TERMINATED_H3`; BHA-10 is accepted and no
Ready or prospective Binance route remains.

Accepted Binance v2 remains exact post-hoc upstream evidence. It is not causal input.
No historical-repair source v3, Profile input, Bundle, adapter, Run, assessment, or
prospective plan exists or is authorized. Tushare readiness and unrelated statuses
are unchanged.

## Accepted main commits

| Node | Commit |
| --- | --- |
| BHA-00 governance | `d9ec8631385247249fcd91bd814c1342948c53b5` |
| BHA-01A settlement authority | `7a808d3b7b7a58a354212e0da0fc67c3dcefd85c` |
| BHA-01B revision authority | `366575914cd4066ad6cfa593b8df219df7021c54` |
| BHA-02 H3 decision | `600259a9f22e44102e5e60faab3176cbf5761e6e` |

## Immutable artifact bindings

| Artifact | Identity |
| --- | --- |
| [H3 decision JSON](../../../../../evidence/g12m-binance-funding-availability-authority-decision-v1/decision.json) | file `sha256:a0f8fff9ed75db74abb9fd596ad6b3c79bd1a1c75e823e5bef5b5c63e0b2a3e2` |
| [H3 decision report](../../../../research/g12m-binance-funding-availability-authority-decision-v1.md) | file `sha256:130bfc81c8c97e47992a90354c64b28bebee8053fafc48eb63eb07c942f407af` |
| [H3 manifest](../../../../../evidence/g12m-binance-funding-availability-authority-decision-v1/manifest.sha256) | file `sha256:760d44f9a4b1627f7f2a176336ba74a2924f7eecaf44ac7ba72e78d93f99e6f6` |
| BHA-01A SourceSnapshot | Snapshot `sha256:ad5ee7b6981ffbd1048f3bd7b7966369e6cadc6654cde81aa670426f19d7c09f`; file `sha256:86ec9590cfc80239c16c93354d3d4428432454f2e1bdee31ad0846728b9c0bf0` |
| BHA-01B SourceSnapshot | Snapshot `sha256:e8faeb5a146c0ff85f5afca6f740ee9a925a3d47134c4d3495b26fdb5e4b8f25`; file `sha256:e938b07351d75c8a381ee7c9bef78e31ab96b65986e42a6b11a71ff26a7d612a` |
| Accepted v2 implementation | `024e5f209a94bb358946f5c468630108981f0329` |
| Accepted v2 response | `sha256:e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338` |
| Accepted v2 receipt | `sha256:a92989478047de7d744744aedeaf365f7d16240b536c1ccece749abe3b4efa36` |
| Accepted v2 SourceSnapshot | `sha256:a45d9acdcfb4d42d1c70af44969f6a5151fb260c4c3040943b3d961c1073aa3f` |
| Accepted v2 report | `sha256:29e639615c1e5f5fa05ffdff9bc77a630d56838c7b0e70230177922bdbffc37b` |
| Accepted v2 canonical report file | `sha256:850cf2b5b2f3caffd7afc1cb4f364e6224c4022417ae46bb01a406600e971951` |

The H3 decision manifest remains unchanged and records the pre-fan-in BHA-10 route
hash. This receipt records the accepted fan-in status without regenerating or
altering that accepted manifest.

## Validation record

| Command | Result |
| --- | --- |
| `python -m json.tool ...`, canonical sorted JSON `diff`, and `sha256sum -c` against `git archive 600259a9f22e44102e5e60faab3176cbf5761e6e` | PASS — 12 manifest entries replayed at the accepted H3 source tip |
| Inline Python local-link/final-status/write-set verifier over the six changed files | PASS |
| Markdown LSP diagnostics for all changed Markdown files | PASS — zero diagnostics |
| `git diff --check` | PASS |
| Protected package/evidence byte digest replay | PASS — pre/post `sha256:2b5309dcb4c629af21a09a13763e5cb6682f41317fb0d53a158ff1bd689fb666` |
| Accepted v1/v2 targeted byte digest replay | PASS — pre/post `sha256:d0d3c78a29d36fc373483e5f6331723c7e5b7f97a101848338c6f879d05c31ac` |
| `gitleaks detect --no-banner --redact --source .` | PASS — no leaks |
| `git status --porcelain=v1` plus protected-prefix/write-set assertions | PASS — six governance/status/receipt files only |

The starting worktree was clean; its porcelain-v1 byte stream was empty
(`sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`).
No user dirty file was present or modified. No executable node was integrated, so no
package, focused, architecture, or full repository test was applicable.

## Residual limitations

- The accepted v2 `available_time` remains the 2026 receipt instant and proves only
  post-hoc observation of the three 2024 rows.
- Exact settlement-time Provider Availability and settlement-visible revision
  identity are not established.
- Permanent provider identity/finality, complete correction lineage, and
  provider-global completeness remain limited.
- Legal closure, live eligibility, deployment authorization, and grade creation or
  change remain false and outside G12M authority.
