# ADR 0008: Decision Grade Is Source-Bounded for Historical Research

- Status: Accepted
- Date: 2026-08-21
- Scope: G12M

## Context

The supported historical market-data boundary is finite: Tushare and Binance are
the sole providers. Neither provider can supply every form of external finality
that a stricter abstract evidence model might request. Depending on the dataset,
the unavailable assurances include a provider-declared permanent checksum, proof
that bytes will never be revised, a complete correction/supersession lineage, a
provider-complete universe, and an immutable joined Binance funding-rate plus
funding-mark archive.

Treating those unavailable provider assurances as ordinary backtest blockers
would make decision-grade historical research unattainable even when every
property controlled by this system is exact, immutable, deterministic, causal,
and auditable. It would also invite a second grading framework beside the
existing `RequestedResultGrade` and `ResultGrade` values.

## Decision

Tushare (`tushare.pro`) and Binance (`binance.public_data` or an exact declared
Binance API source) are the only market-data providers accepted by G12M. No
provider registry, generic source policy, or open-ended provider extension is
authorized by this decision.

G12M may make a `SOURCE_BOUNDED_DECISION_GRADE` qualification only for an
already verified completed result whose exact existing `IntegrityReport` has
`RequestedResultGrade.DECISION_GRADE` and `ResultGrade.DECISION_GRADE`, and when
all source-specific controllable requirements pass for the exact historical
claim:

- the provider and finite request scope are declared exactly;
- verified upstream evidence binds retained raw bytes, acquisition receipt or
  observed-as-of time, and local content identity;
- verified upstream reports prove no-lookahead, fail-closed missing-data
  classification, deterministic normalization/publication/replay, and exact run
  binding; and
- limitations are explicit in the additive assessment.

`SOURCE_BOUNDED_DECISION_GRADE` is not a new enum value or grade tier. G12M
copies and binds the existing Integrity request/result grade, semantic run,
context hash, report hash, and verified completed publication identity. It never
mints, derives, upgrades, or downgrades `ResultGrade`. `DEVELOPMENT` remains the
only other grade. No L0-L4 scale, second registry, or new global grade framework
is permitted.

The following unavailable provider assurances are limitations or optional
assurance targets, not ordinary blockers for source-bounded decision grade:

- a provider-declared permanent checksum;
- proof of no future provider revision;
- complete provider correction/supersession lineage;
- a provider-complete market universe; and
- an immutable provider archive joining Binance funding rates and funding marks.

Provider completeness and revision finality may therefore be `unknown`. Strict
official or legal closure may also be `unknown` for normal historical research.
Legal, tax, or compliance certification is a separate claim outside G12M; G12M
has no strict-closure request or check, and source-bounded decision grade alone
must not be presented as legal closure.

Resolution and Integrity remain authoritative for Bundle, Build, Profile,
Environment, deterministic-run, blocking-issue, and result-grade decisions. G12M
does not duplicate them. Its real blockers are source-specific: unsupported
provider; malformed or missing finite scope; missing verified upstream refs;
source/scope/run binding mismatch; observed-as-of after evidence use;
unclassified missing data; or invalid direct supersession. A non-decision-grade
bound result simply is not source-bounded-qualified; it is not a new G12M
failure. Live/deployment authorization remains independent, false in G12M, and
owned only by Promotion/operations.

Correction handling is append-only. Discovery of corrected provider data creates
a new source snapshot and a new v2 qualification assessment. Prior snapshots,
runs, results, canonical bytes, hashes, flags, and assessments remain immutable
and auditable. A new assessment may name one directly superseded assessment and
must bind a new source snapshot identity. Repository/consumer policy, not G12M,
owns graph conflicts and must treat the prior assessment as not current for new
decisions after correction discovery.

The future G12M implementation remains additive and read-only, but its exact seam
is not frozen by this ADR. Upcoming provider slices must first publish accepted
canonical source artifacts, verifiers, and hashes; the later G12M contract will
bind those exact finite artifacts and policies rather than a generic caller
mapping or `ArtifactRef` framework. Naked hashes and caller-controlled booleans
cannot qualify. G12M performs no provider, filesystem, network, Reader,
repository, or Builder I/O and imports no Builder package. Builder and provider
lanes produce source evidence only; they do not assign Runtime result grade.

## Compatibility and authority boundaries

- Existing v1 artifacts, APIs, canonical bytes, hashes, and qualification flags
  remain unchanged. The new meaning is expressed only by an additive v2
  assessment.
- A legacy false provider/completeness/finality flag is not rewritten. The v2
  assessment binds the underlying evidence and records unavailable external
  assurance as a limitation where this ADR permits it.
- The exact bound `IntegrityReport` remains the sole requested/result-grade
  authority; G12M copies its grade and cannot upgrade a development result.
- This ADR does not modify, reinterpret, or retroactively rehash
  [ADR 0004](0004-official-rules-effective-until-authoritatively-superseded.md),
  [ADR 0007](0007-current-official-selection-supports-development-projection.md),
  or any frozen G12H artifact. Their historical status, bytes, hashes, and claims
  remain exactly as accepted.
- No existing G12L or G12H status changes merely because this ADR is accepted.
  Only a separately implemented and accepted G12M v2 assessment can make the
  source-bounded qualification for its exact run and evidence set.

## Consequences

Decision-grade historical research is attainable within the actual provider
boundary without claiming provider-global completeness or future finality. The
qualification remains fail-closed for properties this system can control and
prove. Stronger provider assurance can be added later as evidence and may remove
limitations, but it does not require a new grade system or mutation of prior
artifacts.
