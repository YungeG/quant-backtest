---
id: G12M-TUSHARE-LISTING-PRESENCE-BINDING-V1
readiness: ACCEPTED_POST_ASSESSMENT_BINDING
status: PASSED
owner: backtest-runtime additive post-assessment evidence binding
depends_on:
  contract: [ADR-0008, G12M-TUSHARE-FIXED-SINGLETON-QUALIFICATION-V2]
  evidence: [G12L-TUSHARE-CN-A-SHARE-LISTING-SOURCE-BOUNDED-V2]
---

# G12M Tushare listing-presence binding v1

## Outcome

Add one Runtime-owned, pure, off-root post-assessment binding between the accepted
G12M Tushare fixed-singleton assessment v2 and the accepted G12L listing-presence
report for `000001.SZ / 20240102`.

The binding states only that the same singleton/catalog identity has exact retained
Tushare evidence for one current identity row, one target-date historical-list row,
and one returned name interval covering `20240102`. The G12L observation occurred
after the July-2026 Run and assessment, so it is not causal execution input and does
not prove listing continuity into the Run window. Existing grade, assessment, route,
Run, Profile, Bundle, G12I/G12K, and G12L bytes remain immutable.

## Full implementation packet

**Status: READY**

### Authority

| ID | Source | Requirement or invariant |
| --- | --- | --- |
| A1 | user-approved continuation | Bind the accepted G12L report downstream to the fixed-singleton assessment without elevating grade, live eligibility, or deployment. |
| A2 | `docs/adr/0008-source-bounded-decision-grade.md` | Runtime may bind exact finite source evidence but never mint or change `ResultGrade`; it imports no Builder and performs no I/O. |
| A3 | `g12m-tushare-fixed-singleton-qualification-v2.md` | Accepted v2 route/assessment bytes, hashes, signatures, and H1 status remain unchanged. |
| A4 | `g12l-tushare-cn-a-share-listing-source-bounded-v2.md` | Exact accepted claim is only listing/name presence on `20240102`; completeness, lifecycle, authoritative absence, survivorship, grade, live, and deployment remain false. |
| A5 | accepted artifact times | G12L `observed_at=1787533249650679470` is later than G12M v2 `assessed_at=1787299622295499670`; therefore the listing report cannot be represented as causal Run evidence. |

### Ownership

- Owner/session: current single writer.
- Worktree/branch: `/tmp/backtest-g12m-listing-evidence-binding-v1` / `g12m-listing-evidence-binding-v1`.
- Exact write set:
  - `packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_listing_presence_binding_v1.py`
  - `tests/runtime/g12m/test_tushare_listing_presence_binding_v1.py`
  - `tests/architecture/test_g12m_tushare_listing_presence_binding_v1_boundary.py`
  - `tests/fixtures/runtime/g12m-tushare-listing-presence-binding-v1/identity.expected.json`
  - this plan
- Governance fan-in later owns only the G12 README and acceptance matrix.

### Flow and seam

Before:

```text
accepted G12M assessment v2                 accepted G12L listing report
              |                                          |
              +-------------- no binding ----------------+
```

After:

```text
exact G12M assessment object + exact canonical G12L report bytes + bound_at
  -> bind_g12m_tushare_listing_presence_v1(...)
  -> exactly one immutable binding or one structured failure
```

No route, facade, repository, Reader, Builder, Profile, Bundle, Run, Integrity, or
existing assessment call path changes.

### Symbol plan

| Symbol | Action | Exact responsibility | Consumer |
| --- | --- | --- | --- |
| `G12MTushareListingPresenceBindingFailureCodeV1` | add | Closed ordered failure enum. | focused tests |
| `G12MTushareListingPresenceBindingFailureV1` | add | Canonical code/subject-only failure. | outcome |
| `G12MTushareListingPresenceBindingV1` | add | Bind exact base assessment identity, accepted listing evidence, copied grades, limitations/nonclaims, and canonical binding hash. | governance/analysis only |
| `G12MTushareListingPresenceBindingOutcomeV1` | add | Carry exactly one binding or failure and reject constructor bypass. | focused tests |
| `bind_g12m_tushare_listing_presence_v1` | add | Pure exact-type/deep-canonical reconstruction and cross-binding. | no production caller yet |

### Exact value and identity closure

| Value | Exact identity |
| --- | --- |
| base assessment | `sha256:31f29b9ab70e7c8da267b6c17dcbe294503088850c894b066116313233dca8bb` |
| semantic Run | `run_1eebd60b81376e15fbe4b2496ed359ab24ed644c7416812d09eb3fb715f581a9` |
| G12L canonical file | `sha256:24122b0a68c87f7bdc5723640724733a2d1f25a7c1b62b0f02eb17bdad2d0205` |
| G12L report | `sha256:6d120c94b8d08fa00389d91894bc17d18ad4a6e0c1f9c42b859e7f1e26cc41c8` |
| G12L Snapshot | `sha256:3144690c004ea0b8a727d33943e47c00cecd257bf8c142f15982d70f745c25e8` |
| G12L request scope | `sha256:aaa6995714b99510137c667783d272010c848c40aa2ac4a359b6de04a4ac3dd0` |
| singleton catalog | `sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc` |
| instrument/date | `xshe:000001` / `20240102` |
| exact identity | `平安银行`, list date `19910403`, covering interval `[20120802, null]` |

The binding copies the base requested/result grades exactly and records them only as
base-assessment facts. It has no qualification-grade field and cannot alter the
existing assessment or Integrity result.

### Failure precedence

| Priority | Condition | Code |
| ---: | --- | --- |
| 1 | non-exact input type or subclass | `INVALID_EXACT_INPUT_TYPE` |
| 2 | base assessment reconstruction/hash mismatch | `BASE_ASSESSMENT_MISMATCH` |
| 3 | malformed, duplicate-key, invalid-number, or noncanonical G12L bytes | `MALFORMED_OR_NONCANONICAL_LISTING_REPORT` |
| 4 | accepted G12L file/report/schema/scope/flag or singleton/catalog/name/list-date/covering-interval mismatch | `LISTING_REPORT_IDENTITY_MISMATCH` |
| 5 | `bound_at` earlier than base assessment or G12L observation | `BINDING_TIME_INVALID` |
| 6 | non-null or invalid predecessor on this first accepted binding | `DIRECT_PREDECESSOR_INVALID` |
| 7 | final binding/body/hash reconstruction mismatch | `BINDING_RECONSTRUCTION_MISMATCH` |

### Security and trust boundaries

- Untrusted inputs are the assessment object, report bytes, time, and optional predecessor.
- G12L bytes must be possessed, canonical, duplicate-key safe, exact-type safe, and
  match the accepted file and semantic hashes; naked hashes or caller booleans are not accepted.
- No credential, network, filesystem, Reader, repository, Builder import, or side effect exists.

### Compatibility and preservation

- Existing G12M assessment module/signature/body/hash and root exports are untouched.
- Existing G12L report and all fixtures are read-only inputs.
- The new module is additive, off-root, and has no production caller.
- `supersedes_binding_hash` is null. Corrected G12L evidence requires a separately
  accepted successor/version; it cannot silently replace this binding.
- Strict v1 listing/lifecycle status remains blocked.

### Forbidden paths

| Authority | Forbidden change | Required route |
| --- | --- | --- |
| A2/A3 | edit route, Integrity grade, existing assessment, facade, or root exports | new off-root pure binding module |
| A2 | import Builder or accept a mapping/hash-only claim | consume exact bytes and deep canonical decode locally |
| A4/A5 | claim July-2026 listing continuity or causal availability | explicit post-assessment limitation/nonclaim |
| A3 | rerun or rehash accepted Run/assessment | bind immutable accepted identity only |

### Sentinel and validation

| Authority | Cheapest failing check |
| --- | --- |
| A2/A3 | architecture test forbids Builder/I/O/root export and protects accepted assessment/route hashes |
| A4 | focused golden test binds exact G12L rows/hashes and keeps every broader qualification false/nonclaimed |
| A5 | mutation test rejects `bound_at` below G12L observation and records non-causal limitation |
| correction policy | non-null predecessor fails closed |

Candidate validation: focused binding and architecture tests, existing G12M assessment
and G12L observer tests, import boundaries, LSP/lens, compile/lock/diff, and gitleaks.
Full acceptance: full repository plus independent blocker review and governance fan-in.

### Open decision

None. The date mismatch is resolved by making this a post-assessment evidence binding,
not a new causal qualification or replacement assessment.

## Acceptance closure

The contract freeze is `f55ad5e00ec706f6f23db13bf630de6fdf99798b` and the
accepted implementation is `b6c5e2a57fb537b6c8b10045df7632527d21be90`.

```text
binding: sha256:ab9b0b750e55e34ff6e8fe5fb9e388143b83aa5140357061dfc7fe4c11ee6f8c
implementation file: sha256:1f6efe379f18eb85205db6f21f209d8d3cdf74fcf428c26f11830d592c401c1e
identity fixture: sha256:c886434bad6c4acc4fcd4094593edcdda016c769715cf4ef8d234c28174e65ec
```

Focused and adjacent validation passed 20 tests, the full repository passed 2409
tests, the 136-file import boundary passed, LSP/lens and gitleaks were clean, and
independent implementation review returned `PASS`. The accepted G12M assessment,
route, grade, and Run remain byte-identical. This binding has no production caller,
causal-input status, listing-continuity claim, grade authority, live eligibility, or
deployment authorization.
