---
id: G12M-BHA-09
status: DRAFT_WAITING
owner: provider-specific G12M assessor writer
produces:
  - read-only Binance funding-history G12M assessment
  - canonical success/non-qualified/failure/supersession artifacts
consumes:
  - G12M-BHA-02
  - G12M-BHA-03
  - G12M-BHA-05
  - G12M-BHA-06
  - G12M-BHA-08
depends_on:
  contract: [G12M-BHA-02, G12M-BHA-03, G12M-BHA-05, G12M-BHA-06, G12M-BHA-08]
  evidence: [canonical Run and source receipts]
  write_conflict: []
fan_in: G12M-BHA-10
---

# BHA-09 Assess the exact source-to-Run qualification

## Outcome

Implement one off-root, pure, read-only Runtime assessor for the exact Binance
funding-history v3 source case. It reports qualification from existing canonical
identities and never constructs execution authority.

## Inputs

Exact canonical bytes for:

- v3 source report and BHA-02 availability authority;
- completed publication and Integrity report;
- execution-Bundle manifest and exact funding-stream payload;
- BHA-06 adapter crosswalk;
- required receipt bytes and direct predecessor assessment.

## Interface and invariants

No filesystem, network, repository, Reader, Builder, or provider-client I/O. Rebuild
exact types deeply and verify provider/dataset/scope/instrument/funding times, v2→v3
lineage, Bundle membership, Run/Integrity/publication identity, timeline consumption,
adapter crosswalk, accounting disposition, assessment time, and direct supersession.

Copy requested/result grade from Integrity. A Development Result produces a canonical
non-qualified assessment. Never mint, upgrade, or downgrade grade.

## Failure precedence

1. malformed canonical bytes;
2. invalid availability authority;
3. source-row/v2→v3 mismatch;
4. execution-Bundle membership mismatch;
5. causal availability mismatch;
6. unsupported executable source correction;
7. adapter-crosswalk mismatch;
8. missing timeline trace;
9. invalid accounting disposition;
10. invalid Run/Integrity/publication identity;
11. invalid direct assessment supersession.

Failure artifacts contain identifiers only, never raw bytes, object repr, or exception
text.

## Expected write set

- One provider-specific off-root Runtime assessor module.
- Dedicated success/non-qualified/failure/supersession tests and golden fixtures.
- Architecture test proving Runtime assessor does not import Builder or perform I/O.

No shared resolver/registry, Builder, Kernel, canonical Run fixture mutation, Runtime
root export, or governance registry edit.

## Acceptance

- Exact success and Development non-qualified reconstruction.
- One adversarial test per failure-precedence class.
- Direct assessment-correction edge and null initial predecessor tests; a non-null
  source-Event predecessor cannot qualify through the current G10E path.
- ResultGrade identity copied exactly from Integrity.
- Focused/adjacent Runtime and architecture tests, Ruff/LSP/diff/secret scan.
- Independent authority, identity, and secret-safety review.

## Exclusions

- Profile grade creation.
- Run execution or evidence publication.
- Live/deployment/legal/finality qualification.
