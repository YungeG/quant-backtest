---
id: G07-DURABLE-REBUILD-PROOF-V2-CONTRACT
status: ACCEPTED_H1
accepted_at_source: bcbeff8415f4768335934c3961349cc8568e7489
decision: CONTRACT_FROZEN
implements: ../implementation/plans/g07-durable-rebuild-proof-v2/drp-00-contract-and-hash-dag.md
---

# G07 durable rebuild proof v2 — frozen contract

## Decision

**H1 `CONTRACT_FROZEN`.** The base-HEAD contracts permit the complete change as an
additive implementation. No constructor or method parameter changes, new Runtime
operation, Local Reader root export, repository root argument, V1 reinterpretation,
policy change, or Platform production adapter is required. This document is the exact
implementation contract for DRP-01 through DRP-05; names, fields, layouts, codes, and
precedence below are not implementation choices.

The claim ceiling is **same-accepted-build reproducibility from currently retrievable
immutable local inputs in a cooperative Python/local-filesystem process**. It is not a
trusted-root, future-retention-policy, remote-durability, copied-tree-detection,
hostile-process, diverse-implementation, compiler, hardware, live, or deployment
claim.

## 1. Frozen source inventory and protected fingerprints

The source basis is Backtest `bcbeff8415f4768335934c3961349cc8568e7489`; the
source-bearing package files are byte-identical to parent base
`3ad3c42a971988db6712aff507ec630c90c0ea1e`. Line anchors are 1-indexed at that
source.

| Authority | SHA-256 | Exact protected anchor |
| --- | --- | --- |
| [`local_market_bundle_reader.py`](../../packages/market-data-contracts/src/crypto_quant_market_data/local_market_bundle_reader.py) | `sha256:bbca532a90789590b882fc3e9a259cce0bfbcb8c37bef6b97ee946f3e0b7a57a` | 394–414 constructor/open signatures; 422–577 complete G12D verification; 579–606 Reader methods; 609 root-local `__all__`. |
| [`bundles.py`](../../packages/market-data-contracts/src/crypto_quant_market_data/bundles.py) | `sha256:0d02d85c3571c071aec6090d245b066bb619caa1c0ae4ea4a7969ac43865a58d` | 371–392 exact `MarketBundleRef` nested wire. |
| market-data package [`__init__.py`](../../packages/market-data-contracts/src/crypto_quant_market_data/__init__.py) | `sha256:bcb6af06fbc830c6a656f44e84ac48f8585d4e7739a9bf1ac7683a8c92689eef` | 19 import and 23–39 package-root exports remain byte-exact in DRP-01. |
| [`facade.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/facade.py) | `sha256:df38483bb7b752d2b13a814e48ddf09a32735c83f2a5baed3892ee84384ac436` | 85–118 constructor/`run`/`run_with_cancellation`; 120–157 schema dispatch; 187–288 V3 flow; 417–530 locked V3; 822–925 cache/publication. Parameters remain exact. |
| [`execution_inputs.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/execution_inputs.py) | `sha256:66344060f875218dbf2cd2115fc7885da7ab35016ee72d58550d60af0c2a17c5` | 390–422 request; 2634–2686 schema-3 catalog; 3385–3479 fresh read/decode. Existing decoder is reused. |
| [`resolution.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/resolution.py) | `sha256:b984e1e0a816154dc85e2c399156ea539a64834bac695129efba5f6843036d44` | 913–958 resolved environment; 1083–1176 Resolution-first; 1268–1315 grade/limitation reachability; 1368–1378 compatible report. |
| [`integrity.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/integrity.py) | `sha256:bcb7030666367a9600077d50d6abf132cc12e0f11cdd7a3c23d8f2a6306872c5` | 57–81 enums; 240–305 legacy rebuild; 308–553 V1 context/report; 704–717 failure codes; 720–812 manifest V1; 838–1078 result V1/V2; 1081–1431 evaluation/finalized/outcome V1/V2; 1449–1465 catalog. Existing bytes/classes stay exact. |
| [`_publication.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/_publication.py) | `sha256:6855e2cef8bf7a6df3d7cbf70694cd6094152d72f440c353cb1c487450903986` | 42–95 lock; 98–154 mkdir/write/harden/fsync; 179–210 scoped removal primitives. |
| [`runner.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/runner.py) | `sha256:4ebfa969e88cd4485e60f92a3fc052230c662f404e429842ed55b5a9603e17b5` | 110–114 outcomes; 608–656 canonical-v1/v2 dispatch; 659–814 exact cache verification. |
| [`publication_refs.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/publication_refs.py) | `sha256:89782d266ceae919118310a94ff6075925e3c408d2595833b93d9562865dcd00` | 9–36 V1 nominal ref; 39 current union. |
| [`verified_publications.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/verified_publications.py) | `sha256:7a3380d9129fb4845fdd770cc4b70fc5c3852dff580796a952164326c3043796` | 26–32 exports; 64–140 V1; 162–249 V2 lean view. |
| [`analysis.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/analysis.py) | `sha256:187fd00f6248cd1c8ea71cc7b0ee62c0f14909e51bb5ff7a49e0bacf80269bcb` | 11–16 exports; 75–94 V1 ref; 134–179 V1 body; 182–244 V1 verified view. |
| [`analysis_derivation.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/analysis_derivation.py) | `sha256:de18451735edf8a05edbed6d8aeb65f1ea6d8ca0518478eb878b5b5897fe9a96` | 97–116 constructor/signature; 117–139 exact current dispatch and bytes. |
| [`evidence_repository.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/evidence_repository.py) | `sha256:617347b75b03c9717448e11dfa5a1d6c23503db1840b8c84c2fd28fa9d860e7d` | 96–103 failures; 1043–1047 constructor; 1220–1485 V1 completed; 1668–1728 V1 analysis. |
| backtest root [`__init__.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/__init__.py) | `sha256:b733cc32c765b366d8a2ae78a6918bb240bf4f712b3554436a544eab49f2ceeb` | 3–9 analysis, 77–81 repository, 129–154 Integrity, 226–233 publication exports. Additions are append-only imports. |
| [`artifacts.py`](../../packages/trading-domain/src/crypto_quant_domain/artifacts.py) | `sha256:1e8478efc44ee733af8382513900b7143e8d795af074fba04441e8d726a3e10e` | 19–52 `ArtifactRef`; 83–84 source hash; 104–157 `ArtifactEnvelope`; 193–205 source parity. |
| [`canonical.py`](../../packages/trading-domain/src/crypto_quant_domain/canonical.py) | `sha256:e2f7622ba6183620ee4e6b0a4b8f790337410f073fd92569d1721a5d6bab74ab` | 54–128 normalization; 145–185 canonical bytes/hash. |
| [`execution_hash.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/execution_hash.py) | `sha256:fc598b6a5394ee4fb8d29a37f6861d5a36c12ac8ad0277b23b2a96ab075ec701` | 47–126 canonical summary; 167–339 equality/mismatch values; 342–430 binding/check precedence. |
| [`artifact_envelope_reader.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/artifact_envelope_reader.py) | `sha256:86e155aef459c780ff902f23b16eca6ef3eb2b6dfcffa7ed11ab1ae7ea43bd23` | 8–9 existing static read port; no root/path argument. |
| [`artifact_envelope_publisher.py`](../../packages/backtest-runtime/src/crypto_quant_backtest/artifact_envelope_publisher.py) | `sha256:27e6c291e56366a0840433d5a2c766cd5c70d609749dc1df0f2267966929415d` | 8–9 generic mirror port; never durability authority. |
| Integrity fixture [`_fixtures.py`](../../tests/runtime/integrity/_fixtures.py) | `sha256:e1e086821590f999d23f4ce38ca370d01ab8b6b5c828b81beb251f826baf2fcb` | Protected legacy opaque-hash fixtures; additive fixtures only. |
| Integration fixture [`_fixtures.py`](../../tests/runtime/integration/_fixtures.py) | `sha256:47168826ff1c4baf71aab88862193bd8f9fddc8ade1ea007aa1f6ea69bbdbae6` | `completed_journey` deterministically supplies the valid existing `EngineExecutionContext` mapping embedded in section 10. |
| [ADR 0008](../adr/0008-source-bounded-decision-grade.md) | `sha256:a213f151393d23e264eaf90de5d6ac7a556548de84c420a3cb5a5bb703f3c3a8` | Naked hash/boolean non-authority; Integrity grade firewall. |
| Platform `tests/contracts/backtest-consumer-port-v1.json` | `sha256:5f9971573154a92aa83f6ac6edbb36024721ad5b54a35f0f14414c1e393f69fa` | Entire file protected. |
| Platform `tests/support/backtest_consumer_port.py` | `sha256:031a27f1231b0579c6852ea94cc510a9cdf07fa5a3453330b3ac0dba0176ad67` | 9–18 V1 operations/precedence; 76–236 V1 behavior; 272–321 exact V1 refs. |
| Platform `tests/architecture/test_backtest_consumer_port.py` | `sha256:bfe458ee36266ff0713d368f2c2f7bd6f171807ffc8e71aca47941cade30a1cd` | 53–91 V1 fingerprint; 94–392 V1 behavior; 439–493 test-only boundary. |

Protected API fingerprints are:

```text
LocalMarketBundleReader.__init__(self, delegate: InMemoryMarketBundleReader) -> None
LocalMarketBundleReader.open(*, repository_root: Path, bundle_ref: MarketBundleRef) -> LocalMarketBundleReader
BacktestRuntime.__init__(*, registry, artifact_reader, artifact_publisher, market_reader, publication_root) -> None
BacktestRuntime.run(self, request: BacktestExecutionRequest) -> BacktestCanonicalPublicationRef | ArtifactRef
BacktestRuntime.run_with_cancellation(self, request, cancellation) -> BacktestCanonicalPublicationRef | ArtifactRef
BacktestAnalysisRuntime.derive(self, completed, metric_profile_ref)
BacktestEvidenceRepository.__init__(self, reader: ArtifactEnvelopeReader) -> None
BacktestEvidenceRepository.load_completed(self, ref: BacktestCanonicalPublicationRef) -> VerifiedCompletedPublicationV2
BacktestEvidenceRepository.load_analysis(self, ref: AnalysisArtifactRef) -> VerifiedBacktestAnalysis
```

The protected source annotation on `run` is the direct
`BacktestCanonicalPublicationRef | ArtifactRef` union, not `RunPublicationRef`.
DRP-03 changes that method annotation additively and exactly to
`BacktestCanonicalPublicationRef | BacktestCanonicalPublicationRefV2 | ArtifactRef`.
`RunPublicationRef` may broaden to the same union where the alias is used, but the
facade does not use that alias. Parameters remain exact. `run_with_cancellation`
keeps its exact direct return annotation and never returns V2.

Protected byte fixtures, all unchanged, are:

| Fixture | SHA-256 |
| --- | --- |
| `tests/fixtures/runtime/integrity-canonical-result-publication-v1.json` | `sha256:e2c160f990f52ea1e67ff81934411a9e32dac92ae7bb55feb52c1b67ae866586` |
| `tests/fixtures/runtime/bt-gap03-completed-publication-v2.json` | `sha256:71c3ff2bfa71ef07eb8d95e80914db35549a1ba53d5c1f1ddf447d7a6265916b` |
| `tests/fixtures/runtime/bt-gap05-completed-analysis-v1.json` | `sha256:f988ca0d779c68a0f05e5b06caf20c68b578a6c1ff7210307816f0e4835b4f2e` |
| `tests/fixtures/runtime/bt-gap06-analysis-v1.json` | `sha256:7764e978cc530d1e518f4c4b4a714627b49b09dc2fe594eacf1633a9d8ba5ef1` |
| `tests/fixtures/runtime/canonical-execution-result-hash-v1.json` | `sha256:fd4e767129717564c320a5bc49282ac45be347406a27581dbd531c603be8c007` |

## 2. Exact Local Reader provenance and lane selection

### 2.1 Private state and reopen interface

DRP-01 adds two module-private `MarketBundleIntegrityError` subclasses, one
module-private sentinel, exactly one instance attribute, and two package-internal
methods to the exact existing class. The subclasses are not root-exported and carry
exact class marker `_durable_reopen_kind_v1` equal to `"unavailable"` or `"tampered"`;
classification never parses exception text.

```python
class _LocalReopenUnavailable(MarketBundleIntegrityError):
    _durable_reopen_kind_v1 = "unavailable"

class _LocalReopenTampered(MarketBundleIntegrityError):
    _durable_reopen_kind_v1 = "tampered"

_REPOSITORY_OPEN_PROVENANCE_V1 = object()

_repository_open_provenance_v1: tuple[
    object, Path, MarketBundleRef,
    bytes, str, str,  # publication bytes, source hash, publication_hash
    bytes, str, str,  # retention bytes, source hash, proof_hash
] | None

def _has_repository_open_provenance_v1(self) -> bool: ...

def _reopen_with_provenance_v1(
    self,
) -> tuple[
    LocalMarketBundleReader,
    bytes, str, str,  # publication source bytes, source hash, publication_hash
    bytes, str, str,  # retention source bytes, source hash, proof_hash
]: ...
```

`__init__` always sets `_repository_open_provenance_v1 = None`. Only
`LocalMarketBundleReader.open` with `cls is LocalMarketBundleReader` may publish
provenance. After every current path/body/mode/hash/ref check has succeeded, and
immediately before returning, exact `open`
stores the single nine-item tuple
`(_REPOSITORY_OPEN_PROVENANCE_V1, repository_root.resolve(strict=True), bundle_ref,
publication_bytes, publication_source_hash, publication_hash, retention_bytes,
retention_source_hash, proof_hash)`. The bytes and hashes are those obtained and
verified by that same successful open; no caller can assign merely `(Path, Ref)` and
attest. The root remains absolute and normalized; it is operational and never
serialized. A subclass returned by inherited `open`, direct construction, an in-memory
Reader, and an arbitrary Reader have no usable provenance.

`_has_repository_open_provenance_v1()` returns true only when
`type(self) is LocalMarketBundleReader`, the private attribute is an exact nine-item
tuple, element 0 `is _REPOSITORY_OPEN_PROVENANCE_V1`, element 1 satisfies
`isinstance(root, Path)`, element 2 has `type(ref) is MarketBundleRef`, elements 3 and
6 are exact `bytes`, elements 4, 5, 7, and 8 are exact canonical-hash `str` values,
the retained root is absolute with no `.` or `..` component, and
`self.bundle_ref == retained_ref`. This selection check is deliberately
filesystem-independent: it never calls `resolve`, `exists`, `lstat`, or reads bytes.
The strict resolved root was captured only by the successful original `open`; deletion,
replacement, or unreadability after that open cannot make the decision-grade request
fall back before fresh reopen. There is no truthiness, tuple-length-only, or
caller-supplied token substitute.

`_reopen_with_provenance_v1` first requires that same exact sentinel/type/state check.
It then calls
`LocalMarketBundleReader.open(repository_root=root, bundle_ref=retained_ref)` (never
`type(self).open`). It exact-checks the reopened instance's private provenance again,
then requires reopened root/ref and tuple elements 3–8 to equal the originally retained
root/ref and publication/retention bytes/source hashes/body hashes exactly. Any
difference, including a self-consistent whole-tree replacement under the same
`MarketBundleRef`, raises the private tampered kind; correction requires a newly opened
Reader and new assessment path. It returns the reopened Reader plus bytes/hashes taken
from that returned instance's provenance tuple. Therefore returned publication/
retention bytes and hashes are from the same verified reopen and equal the original
verified open, never a post-open reread and never extra state or API.
Source hashes are `sha256(raw canonical file bytes)`; `publication_hash` and
`proof_hash` are the current G12D body hashes defined below. Missing or unreadable
required root/file/tree state and underlying read/`lstat`/iteration `OSError` raise the
private unavailable subclass. Invalid sentinel/state and malformed decode, hash, ref,
path, coverage, mode, or tree content raise the private tampered subclass. Runtime
catches the public `MarketBundleIntegrityError` base and maps only the exact private
class marker; unknown/base errors fail closed as `LOCAL_REOPEN_TAMPERED`. Message text
is never classification authority.

The module-private sentinel is cooperative-process provenance only: hostile code in
the same Python process can introspect or mutate private state, and serialization,
copying to another process, subclassing, or caller assignment does not attest an open.
No provenance property, public token, protocol, dataclass, root export, public
constructor, or new Runtime method is added.

### 2.2 G12D body contract

The returned publication body has exactly, in declaration order:

```text
type, schema_version, bundle_ref, manifest_relative_path,
stream_relative_paths, stream_payload_hashes, retention_proof_relative_path,
retention_proof_hash, retention_policy_ref, publication_hash
```

`type="market_bundle_publication"`, `schema_version=1`. `publication_hash` is
`canonical_sha256(body without publication_hash)`. `publication_source_hash` is
`sha256(canonical_bytes(full body))`.

The retention body has exactly:

```text
type, schema_version, bundle_ref, retention_policy_ref, manifest_relative_path,
manifest_source_hash, stream_relative_paths, stream_payload_hashes,
publication_relative_path, proof_hash
```

`type="market_bundle_retention_proof"`, `schema_version=1`. `proof_hash` is
`canonical_sha256(body without proof_hash)`. `retention_source_hash` is
`sha256(canonical_bytes(full body))`. Relative paths obey the current lines 118–124
rule and the exact `bundles/<bundle-key>/<manifest-hex>/...` layout. The reopen verifies
manifest/body/ref linkage, stream exact-cover, payload hashes, read-only files/directories,
and current readability. The proof asserts no future policy truth, trusted root,
remote copy, hostile-process resistance, or copied-tree origin.

### 2.3 Lane predicate

`BacktestRuntime.run(request)` selects durable rebuild exactly when this predicate is
true, evaluated once after exact request/schema validation and before any execution
input read or fresh reopen:

```python
type(request) is BacktestExecutionRequest
and request.schema_version == 3
and request.request.result_grade_requested is RequestedResultGrade.DECISION_GRADE
and type(self._market_reader) is LocalMarketBundleReader
and self._market_reader._has_repository_open_provenance_v1() is True
```

The private method performs the exact sentinel/type/state identity check during
selection; the subsequent reopen repeats it and proves fresh current bytes.
`run_with_cancellation` never evaluates or enters this lane. A false predicate follows
the current path byte-for-byte. Once true, every later failure is a durable-lane
failure; canonical-v1/v2 is never queried, returned, rewritten, mirrored as success,
or used as fallback.

## 3. Exact symbol, artifact, wire, and export catalog

### 3.1 Public root additions

Only these symbols are added to `crypto_quant_backtest` root exports:

```text
BacktestCanonicalPublicationRefV2
AnalysisArtifactRefV2
BacktestAnalysisV2
VerifiedBacktestAnalysisV2
VerifiedCompletedPublicationV3
```

`RunPublicationRef` becomes
`BacktestCanonicalPublicationRef | BacktestCanonicalPublicationRefV2 | ArtifactRef`
for its existing alias consumers. Independently, the facade `run` method's direct
annotation becomes that exact three-member union; the facade does not use the alias.
Existing symbols remain exported and unchanged. Market-data root exports are unchanged.

### 3.2 Package-internal implementation symbols

These exact symbols are implementation-visible but not root-exported:

```text
_durable_rebuild.py:
  DeterministicRebuildVerificationV1
  DeterministicRebuildVerificationPublicationManifestV1
  RebuildComparisonV1
  RebuildComparisonOutcome
  RebuildDivergenceSubject
  VerifiedDurableRebuildObservationV1
  DurableRebuildFailureCode
  DurableRebuildError
  DurableRebuildPublisherV1
  DurableRebuildVerifierV1

integrity.py:
  CanonicalAttemptRefV2
  IntegrityEvaluationContextV2
  IntegrityReportV2
  CompletedBacktestResultV3
  IntegrityEvaluationRecordV2
  CanonicalPublicationManifestV2
```

No finalized-result/outcome V3 wrapper is added. The publisher returns existing raw
`ArtifactRef` for evaluation and the nominal V2 ref for completed success. Private
process values are never canonical artifacts.

### 3.3 Wire catalog

| Python value | Artifact/wire | Exact wire tag |
| --- | --- | --- |
| `DeterministicRebuildVerificationV1` | `deterministic_rebuild_verification@1` | `type="deterministic_rebuild_verification"`, `schema_version=1` |
| `DeterministicRebuildVerificationPublicationManifestV1` | `deterministic_rebuild_verification_publication_manifest@1` | same artifact type, `schema_version=1` |
| `CanonicalAttemptRefV2` | `canonical_attempt_ref@2` | `type="canonical_attempt_ref"`, `schema_version=2` |
| `IntegrityEvaluationContextV2` | nested `integrity_evaluation_context@2` | `type="integrity_evaluation_context"`, `schema_version=2` |
| `IntegrityReportV2` | `integrity_report@2` | `type="integrity_report"`, `schema_version=2` |
| `IntegrityEvaluationRecordV2` | `integrity_evaluation_record@2` | `type="integrity_evaluation_record"`, `schema_version=2` |
| `CompletedBacktestResultV3` | `completed_backtest_result@3` | `type="completed_backtest_result"`, `schema_version=3` |
| `CanonicalPublicationManifestV2` | `canonical_publication_manifest@2` | `type="canonical_publication_manifest"`, `schema_version=2` |
| `BacktestCanonicalPublicationRefV2` | nominal value | `type="backtest_canonical_publication_ref_v2"` plus exact manifest@2 `artifact_ref` |
| `BacktestAnalysisV2` | `backtest_analysis@2` | `type="backtest_analysis"`, `schema_version=2` |
| `AnalysisArtifactRefV2` | nominal value | `type="analysis_artifact_ref_v2"` plus exact analysis@2 `artifact_ref` |
| `VerifiedCompletedPublicationV3` | process view | no artifact wire |
| `VerifiedBacktestAnalysisV2` | process view | no artifact wire |

## 4. Canonical bodies, ordering, hashes, and DAG

Canonical encoding is repository `canonical_bytes`: UTF-8 JSON, recursively sorted
mapping keys, compact separators, no float/bytes/path. Tables list constructor and
`to_canonical_dict` declaration order; wire bytes use canonical key order. Every
artifact exact-decodes and rejects extra/missing keys. Every nested `ArtifactRef` has
exact keys `type, artifact_type, schema_version, content_hash` with
`type="artifact_ref"`; every nested `MarketBundleRef` has exact keys
`type, bundle_key, manifest_hash` with `type="market_bundle_ref"`; every nested
`IntegrityIssue` retains exact V1 keys `code, severity, subject_keys,
evidence_hashes`; `EngineExecutionContext` and `ResolvedFinancialState` retain their
exact existing canonical bodies at the protected source anchors and are never wrapped
or mapped generically.

### 4.1 Verification and comparison

`RebuildComparisonOutcome` values are exactly `EQUAL="equal"` and
`MISMATCH="mismatch"`. `RebuildDivergenceSubject` precedence is exactly:

```text
request_hash
normalized_request_hash
resolved_environment_hash
build_artifact_manifest_hash
execution_input_content_hash
execution_input_source_hash
market_bundle_publication_source_hash
market_bundle_retention_source_hash
preparation_hash
target_stream_digest
semantic_spec_hash
identity_manifest_hash
execution_case_hash
trace_hash
execution_result_hash
```

The first unequal item in that order is `first_divergence`; equality requires null.
`left_hash` and `right_hash` are the values at the divergence, or the equal
`execution_result_hash` when equal. Comparison order is exactly:

```text
attempt_1_vs_attempt_2
attempt_1_vs_rebuild
attempt_2_vs_rebuild
```

Subjects are exact Attempt IDs or literal `verifier_rebuild`.

`deterministic_rebuild_verification@1` exact fields are:

```text
type, schema_version, semantic_run_id,
request_hash, normalized_request_hash, resolved_environment_hash,
build_artifact_manifest_hash, execution_input_bundle_ref,
execution_input_source_hash, market_bundle_ref,
market_bundle_publication, market_bundle_publication_source_hash,
market_bundle_retention_proof, market_bundle_retention_source_hash,
retrievability, preparation_hash, target_stream_digest, semantic_spec_hash,
identity_manifest_hash, execution_case_hash, attempts, fresh_rebuild,
comparisons, claim
```

Constants are `retrievability="verified"` and
`claim="same_accepted_build_current_local_inputs"`. `attempts` is exactly two entries
ordered by `(attempt.ordinal, attempt.attempt_id)`, each with exact keys:

```text
attempt, evidence_manifest_ref, evidence_manifest_hash,
evidence_manifest_source_hash, evidence_publication_hash, engine_result_ref,
execution_case_hash, trace_hash, execution_result_hash
```

Each `attempt` is the complete exact `AttemptIdentity@1` canonical body with keys
`type, schema_version, semantic_run_id, ordinal, parent_attempt_id, attempt_id` and
tags `type="attempt_identity"`, `schema_version=1`. The only accepted pair is exactly
`AttemptIdentity.first(semantic_run_id)` at ordinal 1 and
`AttemptIdentity.retry(first, next_ordinal=2)` at ordinal 2. Decoding recomputes each
ID from the existing exact preimage
`{type="attempt_identity_v1", semantic_run_id, ordinal, parent_attempt_id}`; supplied
IDs, parent links, ordinals, or Run IDs never select identity.

Decoder precedence inside structural verification is exact: exact two-entry/field
coverage → exact AttemptIdentity tags/types → recomputed first identity → recomputed
retry identity → canonical ordering → evidence-manifest ref/body/source/hash → the
manifest's exact semantic-Run/attempt ID and attempt-record entry → the resolved
attempt-record's complete exact Attempt body → engine-result ref and case/trace/result
hash bindings → comparison subjects/order/content. The evidence manifest,
`FinalizedAttemptEvidence`, attempt execution record, and engine result must all bind
the corresponding complete identity; a matching bare `attempt_id` with different
Run/ordinal/parent is invalid. Any failure here is `PROOF_CONSTRUCTION_FAILED` after the selected lane's single
Run-lock acquisition and before proof publication.

`fresh_rebuild` exact keys are:

```text
preparation_hash, target_stream_digest, semantic_spec_hash,
identity_manifest_hash, execution_case_hash, trace_level, trace_hash,
execution_result_hash
```

`trace_level` is exactly `full_trace`. Each comparison exact keys are:

```text
comparison_id, left_subject, right_subject, outcome, first_divergence,
left_hash, right_hash
```

The artifact owns only each complete AttemptIdentity body; it contains no full
request, Build, PREP, case, attempt execution record, evidence manifest, trace, or
result body. Those remain resolver-backed transitive bodies. The two non-CAS G12D
bodies are included because no ArtifactRef resolves them; their canonical bytes are
reconstructed exactly and checked against their source hashes.

### 4.2 Artifact/content/source hashes and proof IDs

For every CAS artifact:

```text
content_hash = canonical_sha256({
  "artifact_type": artifact_type,
  "schema_version": schema_version,
  "payload": exact_payload
})
source_bytes = canonical_bytes({
  "artifact_type": artifact_type,
  "schema_version": schema_version,
  "payload": exact_payload,
  "content_hash": content_hash
})
source_hash = "sha256:" + sha256(source_bytes).hexdigest()
ArtifactRef = (artifact_type, schema_version, content_hash)
```

Proof identity is nonrecursive:

```text
proof_id_hash = canonical_sha256({
  "type": "deterministic_rebuild_proof_identity",
  "schema_version": 1,
  "semantic_run_id": semantic_run_id,
  "verification_ref": verification_ref
})
proof_id = "proof_" + proof_id_hash hex

publication_id_hash = canonical_sha256({
  "type": "deterministic_rebuild_proof_publication_identity",
  "schema_version": 1,
  "proof_id": proof_id,
  "verification_source_hash": verification_source_hash
})
publication_id = "proof_publication_" + publication_id_hash hex
```

The proof-publication manifest exact fields are:

```text
type, schema_version, semantic_run_id, proof_id, publication_id,
artifacts, deployment_authorized
```

`deployment_authorized=false`. `artifacts` is exactly one entry for
`verification.json`; every publication entry exact keys are:

```text
relative_path, artifact_type, schema_version, content_hash, source_hash, byte_count
```

Entries are sorted by `relative_path`. A manifest never lists itself.

### 4.3 Integrity v2 and canonical-v3

`CanonicalAttemptRefV2` exact fields are:

```text
type, schema_version, attempt, consistency_set_hash, execution_result_hash,
execution_case_semantic_hash, execution_case_hash, trace_hash, trace_level,
market_bundle_manifest_hash, rebuild_verification_ref,
rebuild_verification_source_hash, proof_publication_manifest_ref,
proof_publication_manifest_source_hash, deployment_authorized
```

`attempt` is the exact full ordinal-1 `AttemptIdentity@1` body from the verification
entry's `attempt` field, not the verification entry itself and not a copied evidence/
engine/trace/result body. With all comparisons equal, ordinal 1 is explicitly frozen
as canonical even though comparison values are equal; neither input order, hash order,
ordinal 2, nor an evidence entry may replace it. `trace_level="full_trace"`;
deployment is false.

`IntegrityEvaluationContextV2` exact fields are:

```text
type, schema_version, semantic_run_id, resolved_request_hash,
attempt_consistency_set_hash, execution_hash_check_hash,
rebuild_verification_ref, proof_publication_manifest_ref, comparison_outcome
```

`comparison_outcome` is `equal` only when all three persisted comparisons are equal,
else `mismatch`. The process value additionally holds resolved exact source objects for
validation, but they are not duplicated in the wire.

`IntegrityReportV2` exact fields are:

```text
type, schema_version, semantic_run_id, context, context_hash,
requested_grade, result_grade, issues, canonical_attempt_ref_hash,
deployment_authorized
```

`requested_grade="decision_grade"`. Issues reuse exact `IntegrityIssue` wire. The only
v2 issue codes are existing `EXECUTION_HASH_MISMATCH`, existing
`ENVIRONMENT_LIMITATION`, and additive
`DETERMINISTIC_REBUILD_MISMATCH="deterministic_rebuild_mismatch"`.

Grade/outcome rules are exact and ordered:

1. Before issue evaluation, require the exact first/retry identities, exact evidence/
   attempt-record/manifest bindings, canonical ordering, and comparison subject
   bindings frozen above; structural failure is pre-Integrity
   `PROOF_CONSTRUCTION_FAILED`.
2. Any `attempt_1_vs_attempt_2` mismatch adds blocking
   `EXECUTION_HASH_MISMATCH`; subjects are both Attempt IDs and evidence is the
   verification content hash.
3. Either Attempt-vs-rebuild mismatch adds one blocking
   `DETERMINISTIC_REBUILD_MISMATCH`; subjects are the mismatching comparison IDs in
   canonical order and evidence is the verification content hash.
4. Any mismatch means `result_grade=null`, no canonical Attempt ref, and
   `IntegrityEvaluationRecordV2.outcome="FAILED"`.
5. With all comparisons equal, nonempty `resolved_environment.limitations` adds
   blocking `ENVIRONMENT_LIMITATION`; subjects are the exact sorted limitations,
   evidence is the environment hash, grade is null, outcome is `BLOCKED`.
6. With equality and no limitations, issues are empty, grade is `decision_grade`, a
   `CanonicalAttemptRefV2` containing the exact ordinal-1 identity is required, and
   outcome is completed.
7. Deployment is always false. Observation fields never set grade.

BLOCKED is source-proven reachable: Resolution lines 1268–1315 permit exact
DECISION_GRADE/eligible Profile and Build registrations carrying nonempty limitations;
the report stays compatible and carries those limitations into the resolved
environment. Development/ineligible Profile/Build and incompatible inputs fail
Resolution before attempts and are never v2 BLOCKED fixtures.

`IntegrityEvaluationRecordV2` exact fields are:

```text
type, schema_version, evaluation_id, semantic_run_id, outcome,
integrity_report_hash, deployment_authorized
```

`outcome` is `FAILED` for either mismatch code, otherwise `BLOCKED`. Its ID preimage is
exactly:

```text
{"type":"integrity_evaluation_identity_v2","semantic_run_id":...,
 "integrity_report_hash":...,"outcome":...}
```

and `evaluation_id="evaluation_" + hash hex`.

`CompletedBacktestResultV3` exact fields are:

```text
type, schema_version, semantic_run_id, outcome, request_hash,
resolved_request_hash, execution_result_hash, consistency_set_hash, attempt_id,
evidence_manifest_ref, canonical_attempt_ref_hash, integrity_report_hash,
rebuild_verification_ref, proof_publication_manifest_ref, result_grade,
engine_execution_context, deployment_authorized
```

Constants are `outcome="COMPLETED"`, `result_grade="decision_grade"`, deployment
false. `attempt_id` must equal the exact ordinal-1 identity's `attempt_id`, and
`evidence_manifest_ref` must equal that identity's verification entry ref; the
canonical-attempt body must contain that same complete identity. It contains no
publication-manifest/result self hash.

`CanonicalPublicationManifestV2` exact fields are the V1 field names:

```text
type, schema_version, semantic_run_id, publication_kind, publication_id,
artifacts, deployment_authorized
```

For success: `publication_kind="canonical"`, `publication_id="canonical-v3"`, and
exact child coverage is:

```text
canonical-attempt-ref.json       canonical_attempt_ref@2
integrity.json                   integrity_report@2
proof-publication-manifest.json  deterministic_rebuild_verification_publication_manifest@1
rebuild-verification.json        deterministic_rebuild_verification@1
result.json                      completed_backtest_result@3
```

For evaluation: `publication_kind="integrity_evaluation"`, publication ID is the exact
evaluation ID, and coverage is:

```text
evaluation-outcome.json          integrity_evaluation_record@2
integrity.json                   integrity_report@2
proof-publication-manifest.json  deterministic_rebuild_verification_publication_manifest@1
rebuild-verification.json        deterministic_rebuild_verification@1
```

The first two proof files are byte-identical to the dedicated final. The canonical
manifest is the directory root and lists no self entry. A child references no Result
or canonical-manifest hash, so the DAG is acyclic.

### 4.4 Nominal completed and verified V3 values

```python
@dataclass(frozen=True, slots=True)
class BacktestCanonicalPublicationRefV2:
    artifact_ref: ArtifactRef  # exact canonical_publication_manifest@2

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "backtest_canonical_publication_ref_v2",
                "artifact_ref": self.artifact_ref}
```

`from_artifact_ref` and `to_artifact_ref` mirror V1 exact names. Raw
`ArtifactRef(canonical_publication_manifest,2,...)` is never accepted as completed.

`VerifiedCompletedPublicationV3` exact process fields, in order, are:

```text
source_publication_ref: BacktestCanonicalPublicationRefV2
semantic_run_id: str
source_execution_result_hash: str
result_grade: ResultGrade
reporting_currency: CurrencyId
engine_context: EngineExecutionContext
execution_summary: VerifiedExecutionSummary
rebuild_verification_ref: ArtifactRef  # verification@1
proof_publication_manifest_ref: ArtifactRef  # proof manifest@1
```

It preserves the V2 run-boundary Journal/Snapshot checks and additionally exact-binds
the two proof refs to result, report/context, and manifest.

### 4.5 Analysis v2

`BacktestAnalysisV2` exact fields and body are identical in order to V1 except source
nominality and schema:

```text
type="backtest_analysis", schema_version=2,
metric_profile_ref: exact backtest_metric_profile@1,
source_publication_ref: exact BacktestCanonicalPublicationRefV2,
source_execution_result_hash,
simple_period_return,
trade_count,
result_grade
```

Metric calculation, decimal encoding, accepted profile, and grades remain V1 exact.
`AnalysisArtifactRefV2` has one `artifact_ref` exact over `backtest_analysis@2` and wire
`{"type":"analysis_artifact_ref_v2","artifact_ref":...}`.
`VerifiedBacktestAnalysisV2` exact fields are `analysis_ref: AnalysisArtifactRefV2` and
`analysis: BacktestAnalysisV2`; properties and canonical view names mirror V1.

`BacktestAnalysisRuntime.derive(completed, metric_profile_ref)` dispatches by exact
process type only:

```text
exact VerifiedCompletedPublication or VerifiedCompletedPublicationV2
  -> existing BacktestAnalysis@1 -> AnalysisArtifactRef
exact VerifiedCompletedPublicationV3
  -> BacktestAnalysisV2@2 -> AnalysisArtifactRefV2
anything else -> TypeError
```

There is no payload/ref inspection, retry, downgrade, `derive_v2`, or new operation.
Its return annotation becomes `AnalysisArtifactRef | AnalysisArtifactRefV2`.

## 5. Execution, repository, facade, and Platform dispatch

### 5.1 Durable-lane sequence

The exact order is:

1. Validate exact request and evaluate the lane predicate once.
2. Freshly read/exact-decode execution-input@3 and retain its source hash.
3. Call `_reopen_with_provenance_v1`; exact-decode and retain current G12D bodies.
4. Run unchanged Resolution. Any failure returns the existing resolution raw ref.
5. Enter one existing `RunPublicationLock` for the semantic Run. Its unchanged
   `__enter__` pre-ensures the run directory before creating the in-directory lock;
   any entry failure is `RUN_LOCK_UNAVAILABLE`.
6. While holding that one lock, check only canonical-v3 cache. Exact local and static
   verification may select a cached completed result; no cached result is returned
   until the same lock exits successfully.
7. On a cache miss, run current PREP/composition and exactly two ordinary full-trace
   Attempts while continuing to hold the same lock.
8. Freshly repeat execution-input read, Local reopen, PREP, unchanged Resolution,
   target/spec/identity/case composition under that lock.
9. Execute one verifier-owned full-trace rebuild without an Attempt identity.
10. Build all three comparisons; inequality is accepted observation data.
11. Construct, publish, and read back the dedicated proof final under the same lock.
12. Mirror proof envelopes to the generic store; mirror failure is pre-Integrity and
    does not revoke the already durable proof directory.
13. Integrity v2 evaluates the read-back observation.
14. Publish canonical-v3 or evaluation-v2 and mirror its graph under the same lock.
15. Exit that one lock. A body failure retains precedence over release failure. After
    an otherwise successful cache/publication path, non-null `lock.release_error`
    maps to `RUN_LOCK_UNAVAILABLE`; no success is returned and any visible final is
    left untouched for cooperative recovery. Only successful release permits return.

A selected lane never queries canonical-v2 before or after reopen. A later cache call
uses only canonical-v3. There is no nested or repeated Run-lock acquisition in the
selected lane. The public facade method keeps its existing name and
parameters and changes its direct return annotation exactly to
`BacktestCanonicalPublicationRef | BacktestCanonicalPublicationRefV2 | ArtifactRef`;
it does not claim or use the `RunPublicationRef` alias.

### 5.2 Repository methods and guarantees

Add exactly:

```python
BacktestEvidenceRepository.load_completed_v3(
    self, ref: BacktestCanonicalPublicationRefV2
) -> VerifiedCompletedPublicationV3

BacktestEvidenceRepository.load_analysis_v2(
    self, ref: AnalysisArtifactRefV2
) -> VerifiedBacktestAnalysisV2
```

Both require exact nominal types before any read. `load_completed_v3` uses the existing
`ArtifactEnvelopeReader`, existing `_read_expected` mechanics, and additive catalog
decoders. It verifies manifest@2 exact coverage; all entry content/source/byte counts;
byte parity of mirrored proof children; verification/proof IDs; G12D body source/body
hashes; all transitive request/Build/PREP/case/Attempt/engine refs; exact first/retry
identity derivation and evidence/attempt-record/manifest binding; comparisons; context,
report, ordinal-1 canonical Attempt, result, grade, and manifest links. It makes only a
static graph claim. It has no root/path parameter and cannot assert current local durability.

`load_analysis_v2` exact-loads analysis@2 and metric-profile@1, calls
`load_completed_v3` for its exact nominal source, then checks source ref, execution
result hash, grade, and metric profile. `load_completed` and `load_analysis` reject V2
nominal values with `PORT_REF_TYPE_MISMATCH`; V2 methods reject V1 likewise. No method
retries through another version.

### 5.3 Facade/cache local guarantee

For a selected lane, cache success occurs only while holding the Run lock and only
when all are true:

1. exact `canonical-v3` final verifies locally;
2. its proof IDs derive the exact dedicated proof final and that final exact-verifies;
3. proof files are byte-identical across dedicated and canonical trees;
4. the currently configured exact Local Reader still freshly reopens and its current
   G12D body/source hashes equal the verification;
5. `load_completed_v3` verifies the mirrored static graph; and
6. both views return identical canonical manifest, proof manifest, verification refs,
   source hashes, run ID, and execution result hash.

Any failure is `CACHE_LOCAL_PROOF_MISMATCH` or `CACHE_STATIC_GRAPH_MISMATCH` as frozen
below. No canonical-v2 fallback occurs. Development schema-3 keeps current
canonical-v2 behavior.

### 5.4 Platform v2 contract and six-node order

DRP-03 produces one immutable Backtest candidate. DRP-04 changes only:

```text
../tests/contracts/backtest-consumer-port-v2.json
../tests/support/backtest_consumer_port.py
../tests/architecture/test_backtest_consumer_port.py
../backtest gitlink
```

The v1 fixture remains byte-exact. Platform v2 fixture has exact top-level keys in
this order:

```text
contract_id, schema_version, status, test_support_only, operations,
terminal_statuses, failure_precedence, encodings, cases
```

Constants are `contract_id="BT-PORT-02"`, `schema_version=2`, `status="frozen"`,
`test_support_only=true`; operations are exactly
`[run, derive, load_completed, load_completed_v3, load_terminal, load_analysis,
load_analysis_v2]`; terminal statuses and decimal encoding equal V1. V2 failure
precedence is exactly:

```text
PORT_REF_TYPE_MISMATCH
PORT_REF_NOT_FOUND
PORT_EVIDENCE_TAMPERED
PORT_MANIFEST_INVALID
PORT_STATIC_PROOF_MISMATCH
PORT_COMPLETED_VERSION_MISMATCH
PORT_ANALYSIS_VERSION_MISMATCH
PORT_RETENTION_UNAVAILABLE
PORT_TERMINAL_NOT_ANALYZABLE
PORT_ANALYSIS_LINK_MISMATCH
```

`cases` contains exactly one `decision_grade_completed_v3` mapping with exact keys
`case_id, request_spec, run, completed_v3, derive, analysis_v2`. `request_spec` is
`{"fixture_case":"decision_grade_completed_v3"}`. `run` exact keys are `kind, ref`
with `kind="completed_v3"` and exact nominal V2 ref. `completed_v3` exact keys are
`publication_ref, semantic_run_id, execution_result_hash, result_grade,
rebuild_verification_ref, proof_publication_manifest_ref`. `derive` exact keys are
`metric_profile_ref, analysis_ref`. `analysis_v2` exact keys are `analysis_ref,
metric_profile_ref, source_publication_ref, source_execution_result_hash,
simple_period_return, trade_count, result_grade`. Every ref uses the exact Backtest
wire tags from section 3.3; sample hashes are copied from the accepted Backtest golden,
not rederived by Platform.

Platform's test-only public contract observes the facade's exact direct three-member
return annotation; broadening `RunPublicationRef` elsewhere is compatible but is not
evidence for that method annotation. Exact dispatch is nominal V1 completed→
`load_completed`, nominal V2 completed→`load_completed_v3`, raw ref→terminal/
evaluation only; the same `derive`
operation receives the corresponding verified completed view; analysis nominal V1→
`load_analysis`, V2→`load_analysis_v2`. Unknown wrapper/type/version and raw
manifest@2-as-completed fail `PORT_REF_TYPE_MISMATCH`; no unwrap, fallback, or retry.

DRP-03's immutable handoff fields are exactly `backtest_candidate_sha`,
`backtest_parent_sha`, `changed_paths`, `commands_and_results`,
`protected_v1_v2_hashes`, and `verification_golden_hash`. DRP-04's immutable handoff
fields are exactly `platform_commit_sha`, `platform_parent_sha`,
`backtest_gitlink_sha`, `changed_paths`, `v1_fixture_hash`, `v2_fixture_hash`, and
`commands_and_results`. DRP-04 commits separately and requires
`backtest_gitlink_sha == backtest_candidate_sha`. DRP-05 then changes only the unique
Matrix row plus the DAG README's DRP-04/DRP-05 status projection and records
`backtest_candidate_sha`, `platform_commit_sha`, `backtest_gitlink_sha`, both command
records, and protected/contract hashes before PASSED. Platform remains pinned to DRP-03. The six-node order is immutable: DRP-00 →
01 → 02 → 03 → 04 → 05.

## 6. Dedicated publication layout, atomicity, and idempotence

All path components derive from validated canonical IDs; no absolute path, PID, host,
time, or recovery fact is serialized.

```text
run directory:    <publication_root>/runs/<semantic_run_id>
lock:             <run directory>/.publication.lock
proof parent:     <run directory>/rebuild-proofs
staging:          <proof parent>/.<proof_id>.staging
proof final:      <proof parent>/<proof_id>
proof files:      verification.json
                  proof-publication-manifest.json
canonical staging:<run directory>/.canonical-v3.staging
canonical final:  <run directory>/canonical-v3
eval staging:     <run directory>/integrity-evaluations-v2/.<evaluation_id>.staging
eval final:       <run directory>/integrity-evaluations-v2/<evaluation_id>
```

Relative directory values, where process values need them, use `/` and are exactly the
suffixes under `publication_root`; no artifact payload contains them. Files are `0444`;
final/staging directories after hardening are `0555`; mutable parents are normal
operator-owned directories. Symlinks, special files, extra names, path escape, and
writable final entries are malformed.

Dedicated proof publication begins at step 11 of section 5.1 while the selected lane
already holds its one `RunPublicationLock`. It neither acquires nor releases another
lock. The existing `CanonicalPublicationFailureCode` mapping is exact:

1. Exact-verify the already locked run directory, create/verify the proof parent, and
   fsync each parent created by `ensure_directory`. Any post-lock run-directory
   verification, proof-parent prepare, or prepare-fsync failure is
   `STAGING_PREPARE_FAILED`.
2. If staging lexists, fail `STAGING_EXISTS` before inspecting or accepting final;
   existing staging is untouched.
3. If final lexists, exact-verify its two files, IDs, refs, hashes, modes, and coverage.
   Decode, coverage, read-back, or final verification failure is
   `PUBLICATION_VERIFICATION_FAILED`; final is never removed. Exact success fsyncs the
   final directory and proof parent and returns the observation to the still-locked
   lane; either fsync failure is `ATOMIC_FINALIZE_FAILED` and final remains visible but
   untrusted until recovery.
4. Create the sibling staging directory exclusively as `0755` and fsync the proof
   parent. Any staging create or prepare-fsync failure is `STAGING_PREPARE_FAILED`.
5. Write `verification.json` and fsync that file. Write or file-fsync failure is
   `ARTIFACT_WRITE_FAILED`.
6. Write the already structurally validated `proof-publication-manifest.json` and
   fsync that file. Write or file-fsync failure is `MANIFEST_WRITE_FAILED`.
7. Read both files back; exact-decode and verify body/ref/source/ID/coverage parity.
   Any decode, coverage, read-back, or staged verification failure is
   `PUBLICATION_VERIFICATION_FAILED`.
8. Chmod both files `0444`, fsync both, chmod staging `0555`, verify modes/coverage,
   and fsync staging. Any chmod, read-only hardening, mode verification, or hardening
   fsync failure is `IMMUTABILITY_FAILED`.
9. Recheck final absence. If now present, fail `FINAL_DESTINATION_EXISTS` and leave
   staging untouched for cooperative recovery.
10. Under the held cooperative single-writer Run lock, perform same-filesystem
   `os.rename(staging, final)`. Any rename error is `ATOMIC_FINALIZE_FAILED` and uses
   the scoped cleanup rule below. The contract makes no no-replace guarantee against
   a hostile or noncooperative process racing an empty destination directory; such a
   process is outside the accepted filesystem model and must not share the trusted
   publication root.
11. Exact-decode/verify final. Failure is `PUBLICATION_VERIFICATION_FAILED` and final
    is left unmanaged. Fsync final, then fsync proof parent; either fsync failure is
    `ATOMIC_FINALIZE_FAILED` and final remains visible but untrusted.
12. Read final again through the exact decoder; decode/read-back/final verification
    failure is `PUBLICATION_VERIFICATION_FAILED`. Otherwise return
    `VerifiedDurableRebuildObservationV1` to the still-locked lane.

Cleanup is exact. After a failure in steps 1, 4, 5, 6, 7, 8, or step 10, if this call
created staging and staging still names that exact directory, perform best-effort
scoped removal followed by best-effort proof-parent fsync; never scan or remove
siblings or final. The original mapped failure has precedence over a cleanup error;
failed cleanup leaves residue, so the next normal call observes `STAGING_EXISTS`.
`STAGING_EXISTS` and step-9 `FINAL_DESTINATION_EXISTS` deliberately leave
pre-existing/current staging untouched. After a successful rename, every later failure
leaves final untouched.

Canonical/evaluation publication uses that same already-held Run lock and the same
parent/staging/final sequence, cleanup rule, modes, and existing-code mapping with its
frozen file set; it performs no nested lock acquisition or release. Generic-store
proof mirror starts only after proof step 12 and while the same lock remains held.
After the selected lane obtains its otherwise final cache/publication outcome, it calls
the unchanged `RunPublicationLock.__exit__`. A body failure already selected keeps
precedence over `release_error`. If the body otherwise succeeded and `release_error`
is non-null, the lane fails `RUN_LOCK_UNAVAILABLE`, returns no success, leaves every
final untouched and the stale lock visible, and requires section 7 operator recovery.

## 7. Cooperative operator recovery

No code recovery framework is required. Existing exact path derivation, `lstat`,
`force_remove`, unlink, and `fsync_directory` suffice under out-of-band exclusivity.
The sole runbook covers dedicated proof, canonical-v3, and evaluation-v2 publication:

1. Stop all cooperative writers and establish operator exclusivity outside the
   process. If exclusivity is not established, do nothing.
2. Validate the exact semantic Run ID and proof ID from immutable request/ref evidence.
   Determine the reached terminal branch as canonical-v3, evaluation-v2 with an exact
   derived evaluation ID, or not-yet-reached. Derive only the exact lock; proof parent,
   staging, and final; canonical staging and final; and, when applicable, evaluation
   parent, staging, and final paths from section 6. Do not use glob, age, PID liveness,
   broad recursive scan, sibling deletion, or a path supplied by artifact bytes. If a
   present evaluation tree cannot be bound to an exact derived evaluation ID, refuse.
3. `lstat` every applicable exact path. Direct-name listing is allowed only for the
   scoped proof and evaluation parents, whose names must be subsets of their exact
   `{.<id>.staging, <id>}` sets. At the run-directory level inspect only the exact lock,
   `.canonical-v3.staging`, and `canonical-v3` paths; unrelated managed Attempt/evidence
   children are neither classified nor mutated.
4. Refuse all mutation if an exact path escapes its derived parent, is a symlink or
   special file; if a scoped proof/evaluation parent has an unmanaged direct sibling;
   if staging and final coexist in any one scope; if canonical and evaluation finals
   coexist; if more than one terminal final is applicable; or if any visible final is
   malformed, partial, writable, or fails its exact decoder/coverage/hash checks.
   Never adopt/rename staging and never delete final.
5. Classify proof, canonical, and applicable evaluation scopes independently. A safe
   exact-final scope has no staging and a fully exact final. A safe absent-final scope
   may have only its exact staging residue. A not-yet-reached terminal scope must be
   absent. Any other combination refuses all mutation.
6. For every safe absent-final scope, remove only its exact staging residue if present,
   in order proof → canonical → evaluation, and fsync that staging's exact parent after
   each removal. Preserve every safe exact final unchanged.
7. Only after every applicable scope is safe and staging-free, unlink only the exact
   stale lock if present, fsync the run directory, and retry normally through
   `RunPublicationLock`. The later holder must full-verify every retained final and
   fsync its final and parent before idempotent acceptance.
8. Rename-before-parent-fsync may reappear absent or visible in any scope. Absent is an
   absent-final classification; visible exact is an exact-final classification. The
   crashed attempt itself is never trusted.
9. Cleanup failure stops immediately and leaves all remaining state. This initiative
   records no recovery receipt. Any independently created operator note is
   operational/noncanonical and excluded from CAS, proof, manifest, Integrity, Result,
   grade, and Matrix hashes.

Safe cleanup mutation order is exact proof staging removal/fsync → canonical staging
removal/run-directory fsync → evaluation staging removal/evaluation-parent fsync → lock
unlink/run-directory fsync, omitting absent steps. No final is ever removed.

## 8. Failure catalogs and global precedence

### 8.1 Private durable lane

`DurableRebuildFailureCode` adds only the non-publication lane values:

```text
EXECUTION_INPUT_UNAVAILABLE=execution_input_unavailable
EXECUTION_INPUT_TAMPERED=execution_input_tampered
EXECUTION_INPUT_DECODE_FAILED=execution_input_decode_failed
LOCAL_REOPEN_UNAVAILABLE=local_reopen_unavailable
LOCAL_REOPEN_TAMPERED=local_reopen_tampered
PREPARATION_MISMATCH=preparation_mismatch
RESOLUTION_MISMATCH=resolution_mismatch
COMPOSITION_MISMATCH=composition_mismatch
REBUILD_EXECUTION_FAILED=rebuild_execution_failed
PROOF_CONSTRUCTION_FAILED=proof_construction_failed
PROOF_MIRROR_FAILED=proof_mirror_failed
CACHE_LOCAL_PROOF_MISMATCH=cache_local_proof_mismatch
CACHE_STATIC_GRAPH_MISMATCH=cache_static_graph_mismatch
RECOVERY_UNSAFE=recovery_unsafe
RECOVERY_CLEANUP_FAILED=recovery_cleanup_failed
```

Proof, canonical-v3, and evaluation-v2 publication reuse the existing unchanged
`CanonicalPublicationFailureCode` values exactly:

```text
RUN_LOCK_UNAVAILABLE=run_lock_unavailable
STAGING_PREPARE_FAILED=staging_prepare_failed
STAGING_EXISTS=staging_exists
FINAL_DESTINATION_EXISTS=final_destination_exists
ARTIFACT_WRITE_FAILED=artifact_write_failed
MANIFEST_WRITE_FAILED=manifest_write_failed
PUBLICATION_VERIFICATION_FAILED=publication_verification_failed
IMMUTABILITY_FAILED=immutability_failed
ATOMIC_FINALIZE_FAILED=atomic_finalize_failed
```

Other existing `CanonicalPublicationFailureCode` members remain unchanged and are not
used to classify proof-directory filesystem steps. No duplicate publication members
are added to `DurableRebuildFailureCode`. `DurableRebuildError.code` accepts the exact
non-publication enum or the existing publication enum and carries a relative subject
only; Runtime exposes
`RuntimeError("Backtest durable rebuild failed: <value>")` without path or exception
text. Entry to the unchanged `RunPublicationLock`, including run-directory ensure and
lock create/write/file-fsync, maps to `RUN_LOCK_UNAVAILABLE`. A non-null lock
`release_error` after an otherwise successful body also maps to
`RUN_LOCK_UNAVAILABLE`; after a selected body failure, that original failure keeps
precedence. Post-lock run-directory verification and proof-parent/staging prepare map
to `STAGING_PREPARE_FAILED`; staging residue to `STAGING_EXISTS`; verification
artifact write/file-fsync to `ARTIFACT_WRITE_FAILED`;
manifest write/file-fsync to `MANIFEST_WRITE_FAILED`; decode, coverage,
read-back, and staged/final verification to `PUBLICATION_VERIFICATION_FAILED`; chmod,
mode, and hardening/fsync to `IMMUTABILITY_FAILED`; final presence at the pre-rename
recheck to `FINAL_DESTINATION_EXISTS`; rename error, final-directory fsync, or proof-
parent fsync after rename to `ATOMIC_FINALIZE_FAILED`. This mapping is exhaustive;
`ATOMIC_FINALIZE_FAILED` is not
limited to the rename syscall.

### 8.2 Repository additive codes

Append exactly to `BacktestEvidenceFailureCode`:

```text
PORT_STATIC_PROOF_MISMATCH
PORT_COMPLETED_VERSION_MISMATCH
PORT_ANALYSIS_VERSION_MISMATCH
```

Existing codes and order remain exact. Wrong nominal/raw/cross-version input is still
`PORT_REF_TYPE_MISMATCH`. `PORT_STATIC_PROOF_MISMATCH` is for a structurally readable
manifest whose mirrored proof/hash DAG disagrees. Completed/analysis version mismatch
inside an otherwise correctly nominal graph uses the corresponding additive code.
All other existing not-found/tampered/manifest/retention/link meanings remain exact.

### 8.3 Global precedence

The first applicable disposition wins:

1. Request exact-type/schema failure (existing hydration failure).
2. Evaluate the lane predicate once; a false predicate follows current behavior only.
3. Selected lane fresh execution-input read/tamper/decode.
4. Fresh Local reopen availability, then tamper/body/ref/tree mismatch.
5. Production Resolution failure: profile missing/incompatible, including ineligible
   decision grade; publish existing `backtest_resolution_failure@1`.
6. Enter the existing `RunPublicationLock`: run-directory ensure, lock
   create/write/fsync, or stale/existing lock failure is `RUN_LOCK_UNAVAILABLE`.
7. While holding that lock, facade cache checks local proof before repository static
   graph; any mismatch fails with no fallback, and a cache success is provisional until
   lock release succeeds.
8. On cache miss: PREP mismatch, Resolution replay mismatch, composition mismatch,
   Attempt/rebuild execution failure, then structural proof construction.
9. Comparison inequality is not a failure; persist it in the constructed observation.
10. Post-lock run-directory verification and proof-parent prepare/prepare-fsync are
    `STAGING_PREPARE_FAILED`.
11. Staging residue (`STAGING_EXISTS`), then existing final exact verification
    (idempotent success, `PUBLICATION_VERIFICATION_FAILED`, or
    `ATOMIC_FINALIZE_FAILED` for final/parent fsync).
12. Staging create/prepare-fsync → verification artifact write/file-fsync → manifest
    write/file-fsync → read-back/decode/coverage → hardening → destination recheck →
    rename → final verification → final-dir fsync → parent fsync → final decoder read,
    using the exhaustive mapping and cleanup precedence in section 6. Visible final
    remains untrusted after any post-rename failure.
13. Generic proof mirror.
14. Integrity maps Attempt mismatch before verifier mismatch, then environment
    limitation.
15. Canonical/evaluation publication and generic mirror use the same held-lock
    staging/final precedence.
16. Exit the one Run lock. A selected body failure keeps precedence; otherwise
    `release_error` is `RUN_LOCK_UNAVAILABLE` and no cache/publication success returns.
17. Repository public methods: exact nominal type → not found → tampered → manifest →
    static proof/version → retention → terminal → analysis link, preserving V1 order
    where additive checks do not apply.
18. Analysis derive exact completed type before metric profile; repository analysis
    exact nominal version before loading source completed.
19. Platform dispatch exact nominal/raw type before version, then calls exactly one
    versioned operation; operation failures propagate without retry.
20. Operator recovery: exclusivity and complete proof/canonical/evaluation scope
    classification before mutation; exact staging cleanup before lock cleanup; cleanup
    failure stops retry.

## 9. Exact implementation write sets and tests

DRP-01 writes only
`packages/market-data-contracts/src/crypto_quant_market_data/local_market_bundle_reader.py`,
`tests/market_data/test_local_market_bundle_reader_provenance.py`, and the DAG README's
DRP-01 accepted / DRP-02 Ready status projection; package root is hash-checked but not
edited.

DRP-02 writes only
`packages/backtest-runtime/src/crypto_quant_backtest/_durable_rebuild.py`,
`tests/runtime/durable_rebuild/test_verification.py`,
`tests/runtime/durable_rebuild/test_publication.py`,
`tests/runtime/durable_rebuild/test_recovery.py`,
`tests/fixtures/runtime/durable_rebuild/deterministic-rebuild-verification-v1.json`,
and the DAG README's DRP-02 accepted / DRP-03 Ready status projection. Existing
`execution_inputs.py` is reused unchanged; discovery proved its package-private
exact decoder is callable without duplication.

DRP-03 writes only the files already listed by the DAG plus focused
`tests/runtime/integrity/test_durable_rebuild_v2.py`,
`tests/runtime/evidence_repository/test_completed_v3.py`,
`tests/runtime/analysis/test_analysis_v2.py`,
`tests/runtime/test_durable_rebuild_facade.py`, and
`tests/architecture/test_durable_rebuild_boundary.py` plus the DAG README's DRP-03
accepted-candidate / DRP-04 Ready status projection. `runner.py` is required for
canonical-v3 cache recognition. No existing fixture is rewritten; DRP-02 owns the one
exact additive golden path above.

DRP-04 and DRP-05 use the exact write sets in section 5.4. DRP-04 cannot edit Backtest
status in its Platform commit; DRP-05 atomically records external DRP-04 acceptance and
its own closure in the DAG README while updating the Matrix. DRP-05 evidence fields in
the Matrix row are immutable DRP-03 SHA, DRP-04 SHA, Platform gitlink SHA, exact command
strings/results, v1 fixture hash, v2 fixture hash, and contract/proof golden hashes.

## 10. Runnable deterministic hash-DAG example

This stdlib-only block is a **wire/hash-DAG/ref-parity example for the proposed,
not-yet-implemented V3 schemas**. Every sample `ArtifactRef` is derived from a concrete
sample `ArtifactEnvelope` body, including execution input, both attempt records,
evidence manifests, engine results, metric profile, proof children, canonical
children, and analysis. It derives and validates the exact first/retry
`AttemptIdentity@1` pair, sorts by `(ordinal, attempt_id)`, and freezes ordinal 1 as
canonical when comparisons are equal.

The embedded `ENGINE_CONTEXT` mapping is the canonical mapping emitted by the existing
`EngineExecutionContext` from protected
`tests/runtime/integration/_fixtures.py::completed_journey` at the source hash in
section 1; it is not the body previously known invalid under the current financial-
state decoder. The stdlib block itself deliberately does **not** invoke repository or
domain decoders. Its acceptance proves only acyclicity and ref/body/source-byte parity,
plus the stated identity-selection and mismatch-rule arithmetic. Future DRP-03 tests
own exact domain hydration and repository reconstruction for the implemented schemas;
this example makes no current semantic-decoder, retention, or repository-acceptance
claim. Run with `python` after extracting the block.

```python
from __future__ import annotations
import hashlib, json


def cbytes(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def sha(value):
    raw = value if isinstance(value, bytes) else cbytes(value)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def H(label):
    return sha(label.encode())


def envelope(artifact_type, schema_version, payload):
    content_hash = sha({"artifact_type": artifact_type, "schema_version": schema_version, "payload": payload})
    value = {"artifact_type": artifact_type, "schema_version": schema_version, "payload": payload, "content_hash": content_hash}
    raw = cbytes(value)
    ref = {"type": "artifact_ref", "artifact_type": artifact_type, "schema_version": schema_version, "content_hash": content_hash}
    return value, ref, sha(raw), len(raw)


def entry(path, artifact_type, version, payload):
    _, ref, source_hash, byte_count = envelope(artifact_type, version, payload)
    return {"relative_path": path, "artifact_type": artifact_type, "schema_version": version, "content_hash": ref["content_hash"], "source_hash": source_hash, "byte_count": byte_count}


def attempt_identity(semantic_run_id, ordinal, parent_attempt_id):
    digest = sha({"type": "attempt_identity_v1", "semantic_run_id": semantic_run_id, "ordinal": ordinal, "parent_attempt_id": parent_attempt_id})
    return {
        "type": "attempt_identity", "schema_version": 1,
        "semantic_run_id": semantic_run_id, "ordinal": ordinal,
        "parent_attempt_id": parent_attempt_id,
        "attempt_id": "attempt_" + digest.removeprefix("sha256:"),
    }


ENGINE_CONTEXT = json.loads(r'''{"case_hash":"sha256:bdbcf92c176fedaf8fa89a056bc92fddeb9d70b75bcacb7cb6013b468374c87e","financial_state":{"initial_snapshot":{"account_id":"account:primary","cash":[{"amount":{"currency":"USD","scale":2,"type":"money","units":100000},"key":{"account_id":"account:primary","currency_id":{"type":"currency_id","value":"USD"},"type":"cash_balance_key","venue_id":{"type":"venue_id","value":"synthetic"}},"type":"cash_balance"}],"currency_valuation_graph_hash":"sha256:34f15030f21b3be7bee7373ddc6a659b4a6b50424b814710feeeac7753fa2e14","equity":{"currency":"USD","scale":2,"type":"money","units":100000},"fees":{"currency":"USD","scale":2,"type":"money","units":0},"financing":{"currency":"USD","scale":2,"type":"money","units":0},"journal_state_hash":"sha256:aec20b268ea42d2064f003be77ff18f6406774fd7bd31460055671d3f7315d23","positions":[],"realized_pnl":{"currency":"USD","scale":2,"type":"money","units":0},"reporting_currency":{"type":"currency_id","value":"USD"},"timestamp":{"epoch_nanoseconds":100,"type":"utc_instant"},"type":"portfolio_snapshot","unrealized_pnl":{"currency":"USD","scale":2,"type":"money","units":0},"valuation_mark_set_hash":"sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945","valuation_marks":[],"valuation_staleness_report_hash":"sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"},"journal":{"entries":[{"account_id":"account:primary","balance_changes":[{"key":{"account_id":"account:primary","currency_id":{"type":"currency_id","value":"USD"},"type":"cash_balance_key","venue_id":{"type":"venue_id","value":"synthetic"}},"type":"balance_change","value":{"currency":"USD","scale":2,"type":"money","units":100000}}],"effective_time":{"epoch_nanoseconds":0,"type":"utc_instant"},"entry_type":"capital_deposited","fees":[],"financing":[],"journal_entry_id":{"kind":"journal","type":"domain_id","value":"jnl_739084961dd691f617624422a7c07de553294c0f7ee15a06f5a19a29919da498"},"realized_pnl":[],"recorded_at":{"instant":{"epoch_nanoseconds":1,"type":"utc_instant"},"phase":{"code":"accounting","rank":90,"type":"timeline_phase"},"source_sequence":{"type":"source_sequence","value":1},"type":"simulation_instant"},"source_ids":["capital:engine-fixture"],"type":"accounting_journal_entry","venue_id":{"type":"venue_id","value":"synthetic"}}],"journal_hash":"sha256:0edc394dbb5d6f8da5b79ad7373786bc398340217eddd11bce720357b7739004","schema_version":1,"type":"accounting_journal"},"ledger_schema":{"registrations":[{"key":{"account_id":"account:primary","currency_id":{"type":"currency_id","value":"USD"},"type":"cash_balance_key","venue_id":{"type":"venue_id","value":"synthetic"}},"scale":2,"type":"ledger_balance_registration"},{"key":{"account_id":"account:primary","instrument_id":{"stable_key":"cash:btc-usd","type":"instrument_id","venue":"synthetic"},"type":"position_balance_key","venue_id":{"type":"venue_id","value":"synthetic"}},"scale":3,"type":"ledger_balance_registration"}],"schema_version":1,"type":"ledger_schema"},"lot_books":[{"lots":[],"position_key":{"account_id":"account:primary","instrument_id":{"stable_key":"cash:btc-usd","type":"instrument_id","venue":"synthetic"},"type":"position_balance_key","venue_id":{"type":"venue_id","value":"synthetic"}},"type":"position_lot_book"}],"order_admissions":[],"order_streams":[],"reservation_schedules":[],"settlement_book_hash":"sha256:5a8944efd7a6570c322ad411aea39c29bc3131afd45c3e8c8723020bbb9543ae","settlement_rules":{"account_id":"account:primary","cash_rules":[{"available_margin_reservation_uses":["margin"],"key":{"account_id":"account:primary","currency_id":{"type":"currency_id","value":"USD"},"type":"cash_balance_key","venue_id":{"type":"venue_id","value":"synthetic"}},"pending_receivable_margin_eligible":false,"pending_receivable_tradable":false,"pending_receivable_withdrawable":false,"tradable_reservation_uses":["cash","fee_reserve"],"type":"cash_availability_rule","withdrawable_reservation_uses":["cash","fee_reserve"]}],"config_hash":"sha256:b337e255741405539f1349bd60fff63818459a223bd8ea8f3cf27da02bfd6765","policy_key":"settlement.engine-fixture.v1","policy_version":1,"position_rules":[{"key":{"account_id":"account:primary","instrument_id":{"stable_key":"cash:btc-usd","type":"instrument_id","venue":"synthetic"},"type":"position_balance_key","venue_id":{"type":"venue_id","value":"synthetic"}},"pending_receivable_sellable":false,"type":"position_availability_rule"}],"schema_version":1,"type":"market_settlement_rules"},"settlement_state":{"account_id":"account:primary","applied_obligations":[],"cursor":{"position":0,"prefix_hash":"sha256:5a8944efd7a6570c322ad411aea39c29bc3131afd45c3e8c8723020bbb9543ae","type":"settlement_book_cursor"},"pending_obligations":[],"schema_version":1,"type":"settlement_book_state"},"type":"resolved_financial_state"},"identity_manifest_hash":"sha256:b9d575e5275aae0d4f3ac46dba4e5f8454ee639192b8881d2aa7833373f05e92","schema_version":1,"semantic_run_id":"run_39ab44a26d7f719fe1648f3ccbf7cbdcb874a9bc43e8c15d3a51ab5aca421591","semantic_spec_hash":"sha256:2592a4ee246b54632d3c63f3490ab68cdabb305406cc275eafabcc0fd5e8a690","target_stream_digest":"sha256:ead473aba908a5d2ace5745a648d357c16666c47a726743b86dbde42768a539f","type":"engine_execution_context"}''')
run = ENGINE_CONTEXT["semantic_run_id"]
first = attempt_identity(run, 1, None)
second = attempt_identity(run, 2, first["attempt_id"])
assert first == attempt_identity(run, 1, None)
assert second == attempt_identity(run, 2, first["attempt_id"])

bundle_ref = {"type":"market_bundle_ref","bundle_key":"sample-bundle","manifest_hash":H("bundle-manifest")}
relative_root = "bundles/sample-bundle/" + bundle_ref["manifest_hash"].removeprefix("sha256:")
retention_without_hash = {
    "type":"market_bundle_retention_proof","schema_version":1,"bundle_ref":bundle_ref,
    "retention_policy_ref":"local.readonly.v1","manifest_relative_path":relative_root+"/manifest.json",
    "manifest_source_hash":bundle_ref["manifest_hash"],
    "stream_relative_paths":[relative_root+"/streams/000.payload"],
    "stream_payload_hashes":[H("stream-payload")],
    "publication_relative_path":relative_root+"/publication.json",
}
retention = {**retention_without_hash, "proof_hash":sha(retention_without_hash)}
publication_without_hash = {
    "type":"market_bundle_publication","schema_version":1,"bundle_ref":bundle_ref,
    "manifest_relative_path":relative_root+"/manifest.json",
    "stream_relative_paths":[relative_root+"/streams/000.payload"],
    "stream_payload_hashes":[H("stream-payload")],
    "retention_proof_relative_path":relative_root+"/retention-proof.json",
    "retention_proof_hash":retention["proof_hash"],"retention_policy_ref":"local.readonly.v1",
}
publication = {**publication_without_hash, "publication_hash":sha(publication_without_hash)}

execution_input = {"type":"sample_backtest_execution_input_bundle","schema_version":3,"semantic_run_id":run,"fixture_case":"wire-parity"}
execution_input_env, execution_input_ref, execution_input_source_hash, _ = envelope("backtest_execution_input_bundle",3,execution_input)
metric_profile = {"type":"sample_backtest_metric_profile","schema_version":1,"metric_profile_key":"sample-return"}
metric_profile_env, metric_profile_ref, metric_profile_source_hash, _ = envelope("backtest_metric_profile",1,metric_profile)

common = {
    "request_hash":H("request"),"normalized_request_hash":H("normalized-request"),
    "resolved_environment_hash":H("environment"),"build_artifact_manifest_hash":H("build"),
    "execution_input_content_hash":execution_input_ref["content_hash"],
    "execution_input_source_hash":execution_input_source_hash,
    "market_bundle_publication_source_hash":sha(cbytes(publication)),
    "market_bundle_retention_source_hash":sha(cbytes(retention)),
    "preparation_hash":H("preparation"),"target_stream_digest":ENGINE_CONTEXT["target_stream_digest"],
    "semantic_spec_hash":ENGINE_CONTEXT["semantic_spec_hash"],"identity_manifest_hash":ENGINE_CONTEXT["identity_manifest_hash"],
    "case_hash":ENGINE_CONTEXT["case_hash"],"trace_hash":H("trace"),"execution_result_hash":H("result"),
}


def attempt_entry(identity, label):
    engine_result = {
        "type":"sample_engine_execution_result","schema_version":1,
        "attempt":identity,"case_hash":common["case_hash"],
        "trace_hash":common["trace_hash"],"execution_result_hash":common["execution_result_hash"],
    }
    engine_env, engine_ref, engine_source_hash, _ = envelope("engine_execution_result",1,engine_result)
    attempt_record = {
        "type":"sample_attempt_execution_record","schema_version":1,
        "attempt":identity,"engine_result_ref":engine_ref,
    }
    record_env, record_ref, record_source_hash, _ = envelope("attempt_execution_record",1,attempt_record)
    evidence_manifest = {
        "type":"sample_evidence_manifest","schema_version":1,
        "semantic_run_id":identity["semantic_run_id"],"attempt":identity,
        "attempt_record_ref":record_ref,"engine_result_ref":engine_ref,
    }
    evidence_env, evidence_ref, evidence_source_hash, _ = envelope("evidence_manifest",1,evidence_manifest)
    evidence_publication = {
        "type":"finalized_attempt_evidence","schema_version":1,
        "attempt":identity,"manifest_hash":sha(evidence_manifest),
        "manifest_source_hash":evidence_source_hash,
        "relative_directory":f"runs/{run}/attempts/{identity['attempt_id']}",
        "deployment_authorized":False,
    }
    return {
        "attempt":identity,
        "evidence_manifest_ref":evidence_ref,
        "evidence_manifest_hash":sha(evidence_manifest),
        "evidence_manifest_source_hash":evidence_source_hash,
        "evidence_publication_hash":sha(evidence_publication),
        "engine_result_ref":engine_ref,
        "execution_case_hash":common["case_hash"],"trace_hash":common["trace_hash"],
        "execution_result_hash":common["execution_result_hash"],
        "_bodies":{
            "engine":(engine_env,engine_result,engine_source_hash),
            "record":(record_env,attempt_record,record_source_hash),
            "manifest":(evidence_env,evidence_manifest,evidence_source_hash),
        },
    }


sample_attempts = [attempt_entry(second,"a2"), attempt_entry(first,"a1")]
for value in sample_attempts:
    bodies = value.pop("_bodies")
    assert bodies["record"][1]["attempt"] == value["attempt"]
    assert bodies["manifest"][1]["attempt"] == value["attempt"]
    assert bodies["manifest"][1]["attempt_record_ref"]["content_hash"] == bodies["record"][0]["content_hash"]
    assert bodies["manifest"][1]["engine_result_ref"] == value["engine_result_ref"]
attempts = sorted(sample_attempts, key=lambda value:(value["attempt"]["ordinal"], value["attempt"]["attempt_id"]))
assert [value["attempt"] for value in attempts] == [first, second]
canonical_identity = attempts[0]["attempt"]
assert canonical_identity["ordinal"] == 1

fresh = {
    "preparation_hash":common["preparation_hash"],"target_stream_digest":common["target_stream_digest"],
    "semantic_spec_hash":common["semantic_spec_hash"],"identity_manifest_hash":common["identity_manifest_hash"],
    "execution_case_hash":common["case_hash"],"trace_level":"full_trace","trace_hash":common["trace_hash"],
    "execution_result_hash":common["execution_result_hash"],
}


def equal(cid,left,right):
    return {"comparison_id":cid,"left_subject":left,"right_subject":right,"outcome":"equal","first_divergence":None,"left_hash":common["execution_result_hash"],"right_hash":common["execution_result_hash"]}


comparisons = [
    equal("attempt_1_vs_attempt_2",first["attempt_id"],second["attempt_id"]),
    equal("attempt_1_vs_rebuild",first["attempt_id"],"verifier_rebuild"),
    equal("attempt_2_vs_rebuild",second["attempt_id"],"verifier_rebuild"),
]
verification = {
    "type":"deterministic_rebuild_verification","schema_version":1,"semantic_run_id":run,
    "request_hash":common["request_hash"],"normalized_request_hash":common["normalized_request_hash"],
    "resolved_environment_hash":common["resolved_environment_hash"],"build_artifact_manifest_hash":common["build_artifact_manifest_hash"],
    "execution_input_bundle_ref":execution_input_ref,"execution_input_source_hash":common["execution_input_source_hash"],
    "market_bundle_ref":bundle_ref,"market_bundle_publication":publication,
    "market_bundle_publication_source_hash":common["market_bundle_publication_source_hash"],
    "market_bundle_retention_proof":retention,"market_bundle_retention_source_hash":common["market_bundle_retention_source_hash"],
    "retrievability":"verified","preparation_hash":common["preparation_hash"],
    "target_stream_digest":common["target_stream_digest"],"semantic_spec_hash":common["semantic_spec_hash"],
    "identity_manifest_hash":common["identity_manifest_hash"],"execution_case_hash":common["case_hash"],
    "attempts":attempts,"fresh_rebuild":fresh,"comparisons":comparisons,
    "claim":"same_accepted_build_current_local_inputs",
}
verification_env, verification_ref, verification_source_hash, _ = envelope("deterministic_rebuild_verification",1,verification)
proof_id_preimage = {"type":"deterministic_rebuild_proof_identity","schema_version":1,"semantic_run_id":run,"verification_ref":verification_ref}
proof_id = "proof_" + sha(proof_id_preimage).removeprefix("sha256:")
publication_id_preimage = {"type":"deterministic_rebuild_proof_publication_identity","schema_version":1,"proof_id":proof_id,"verification_source_hash":verification_source_hash}
proof_publication_id = "proof_publication_" + sha(publication_id_preimage).removeprefix("sha256:")
proof_manifest = {
    "type":"deterministic_rebuild_verification_publication_manifest","schema_version":1,
    "semantic_run_id":run,"proof_id":proof_id,"publication_id":proof_publication_id,
    "artifacts":[entry("verification.json","deterministic_rebuild_verification",1,verification)],
    "deployment_authorized":False,
}
proof_env, proof_ref, proof_source_hash, _ = envelope("deterministic_rebuild_verification_publication_manifest",1,proof_manifest)
canonical_attempt = {
    "type":"canonical_attempt_ref","schema_version":2,"attempt":canonical_identity,
    "consistency_set_hash":H("consistency-set"),"execution_result_hash":common["execution_result_hash"],
    "execution_case_semantic_hash":common["semantic_spec_hash"],"execution_case_hash":common["case_hash"],
    "trace_hash":common["trace_hash"],"trace_level":"full_trace","market_bundle_manifest_hash":bundle_ref["manifest_hash"],
    "rebuild_verification_ref":verification_ref,"rebuild_verification_source_hash":verification_source_hash,
    "proof_publication_manifest_ref":proof_ref,"proof_publication_manifest_source_hash":proof_source_hash,
    "deployment_authorized":False,
}
_, canonical_attempt_ref, _, _ = envelope("canonical_attempt_ref",2,canonical_attempt)
context = {
    "type":"integrity_evaluation_context","schema_version":2,"semantic_run_id":run,
    "resolved_request_hash":H("resolved-request"),"attempt_consistency_set_hash":H("consistency-set"),
    "execution_hash_check_hash":H("execution-hash-check"),"rebuild_verification_ref":verification_ref,
    "proof_publication_manifest_ref":proof_ref,"comparison_outcome":"equal",
}
context_hash = sha(context)
report = {
    "type":"integrity_report","schema_version":2,"semantic_run_id":run,"context":context,"context_hash":context_hash,
    "requested_grade":"decision_grade","result_grade":"decision_grade","issues":[],
    "canonical_attempt_ref_hash":sha(canonical_attempt),"deployment_authorized":False,
}
result = {
    "type":"completed_backtest_result","schema_version":3,"semantic_run_id":run,"outcome":"COMPLETED",
    "request_hash":common["request_hash"],"resolved_request_hash":H("resolved-request"),
    "execution_result_hash":common["execution_result_hash"],"consistency_set_hash":H("consistency-set"),
    "attempt_id":canonical_identity["attempt_id"],"evidence_manifest_ref":attempts[0]["evidence_manifest_ref"],
    "canonical_attempt_ref_hash":sha(canonical_attempt),"integrity_report_hash":sha(report),
    "rebuild_verification_ref":verification_ref,"proof_publication_manifest_ref":proof_ref,
    "result_grade":"decision_grade","engine_execution_context":ENGINE_CONTEXT,
    "deployment_authorized":False,
}
canonical_manifest = {
    "type":"canonical_publication_manifest","schema_version":2,"semantic_run_id":run,
    "publication_kind":"canonical","publication_id":"canonical-v3",
    "artifacts":sorted([
        entry("rebuild-verification.json","deterministic_rebuild_verification",1,verification),
        entry("proof-publication-manifest.json","deterministic_rebuild_verification_publication_manifest",1,proof_manifest),
        entry("canonical-attempt-ref.json","canonical_attempt_ref",2,canonical_attempt),
        entry("integrity.json","integrity_report",2,report),
        entry("result.json","completed_backtest_result",3,result),
    ], key=lambda x:x["relative_path"]),"deployment_authorized":False,
}
canonical_env, canonical_ref_raw, canonical_source_hash, _ = envelope("canonical_publication_manifest",2,canonical_manifest)
canonical_ref = {"type":"backtest_canonical_publication_ref_v2","artifact_ref":canonical_ref_raw}
analysis = {
    "type":"backtest_analysis","schema_version":2,
    "metric_profile_ref":metric_profile_ref,
    "source_publication_ref":canonical_ref,"source_execution_result_hash":common["execution_result_hash"],
    "simple_period_return":"0.125","trade_count":2,"result_grade":"decision_grade",
}
_, analysis_ref_raw, analysis_source_hash, _ = envelope("backtest_analysis",2,analysis)
analysis_ref = {"type":"analysis_artifact_ref_v2","artifact_ref":analysis_ref_raw}

# This checks only wire/hash-DAG/ref parity for proposed V3 schemas.
assert execution_input_ref["content_hash"] == execution_input_env["content_hash"]
assert metric_profile_ref["content_hash"] == metric_profile_env["content_hash"]
assert verification_ref["content_hash"] == sha({"artifact_type":"deterministic_rebuild_verification","schema_version":1,"payload":verification})
assert proof_manifest["artifacts"][0]["content_hash"] == verification_ref["content_hash"]
assert next(x for x in canonical_manifest["artifacts"] if x["relative_path"] == "proof-publication-manifest.json")["content_hash"] == proof_ref["content_hash"]
assert canonical_ref["artifact_ref"]["content_hash"] == sha({"artifact_type":"canonical_publication_manifest","schema_version":2,"payload":canonical_manifest})
assert canonical_attempt["attempt"] == first and canonical_attempt["attempt"] is not attempts[0]
assert result["attempt_id"] == first["attempt_id"] and result["evidence_manifest_ref"] == attempts[0]["evidence_manifest_ref"]
assert analysis["metric_profile_ref"] == metric_profile_ref and analysis["source_publication_ref"] == canonical_ref
assert "publication_manifest_hash" not in result and "result_hash" not in canonical_attempt and "analysis_ref" not in analysis

# Mismatch remains wire-valid observation data and maps to FAILED by the frozen rule.
mismatch = dict(verification)
mismatch_fresh = dict(fresh); mismatch_fresh["execution_result_hash"] = H("different-result")
mismatch["fresh_rebuild"] = mismatch_fresh
mismatch_comparisons = list(comparisons)
mismatch_comparisons[1] = {"comparison_id":"attempt_1_vs_rebuild","left_subject":first["attempt_id"],"right_subject":"verifier_rebuild","outcome":"mismatch","first_divergence":"execution_result_hash","left_hash":common["execution_result_hash"],"right_hash":mismatch_fresh["execution_result_hash"]}
mismatch_comparisons[2] = {"comparison_id":"attempt_2_vs_rebuild","left_subject":second["attempt_id"],"right_subject":"verifier_rebuild","outcome":"mismatch","first_divergence":"execution_result_hash","left_hash":common["execution_result_hash"],"right_hash":mismatch_fresh["execution_result_hash"]}
mismatch["comparisons"] = mismatch_comparisons
_, mismatch_ref, _, _ = envelope("deterministic_rebuild_verification",1,mismatch)
mismatch_report = {"requested_grade":"decision_grade","result_grade":None,"issues":["deterministic_rebuild_mismatch"],"outcome":"FAILED","rebuild_verification_ref":mismatch_ref}
assert mismatch_report["outcome"] == "FAILED" and mismatch_report["result_grade"] is None

outputs = {
    "attempt_1_id":first["attempt_id"],"attempt_2_id":second["attempt_id"],
    "execution_input_content_hash":execution_input_ref["content_hash"],"execution_input_source_hash":execution_input_source_hash,
    "metric_profile_content_hash":metric_profile_ref["content_hash"],"metric_profile_source_hash":metric_profile_source_hash,
    "publication_hash":publication["publication_hash"],"publication_source_hash":sha(cbytes(publication)),
    "retention_proof_hash":retention["proof_hash"],"retention_source_hash":sha(cbytes(retention)),
    "verification_content_hash":verification_ref["content_hash"],"verification_source_hash":verification_source_hash,
    "proof_id_preimage_hash":sha(proof_id_preimage),"proof_id":proof_id,
    "proof_publication_id_preimage_hash":sha(publication_id_preimage),"proof_publication_id":proof_publication_id,
    "proof_manifest_content_hash":proof_ref["content_hash"],"proof_manifest_source_hash":proof_source_hash,
    "canonical_attempt_content_hash":canonical_attempt_ref["content_hash"],
    "integrity_context_hash":context_hash,"integrity_report_hash":sha(report),"result_hash":sha(result),
    "canonical_manifest_content_hash":canonical_ref_raw["content_hash"],"canonical_manifest_source_hash":canonical_source_hash,
    "analysis_content_hash":analysis_ref_raw["content_hash"],"analysis_source_hash":analysis_source_hash,
    "mismatch_verification_content_hash":mismatch_ref["content_hash"],
}
print(json.dumps(outputs, indent=2, sort_keys=True))
```

Recorded output:

```json
{
  "analysis_content_hash": "sha256:75e4d92fc30bfa2edcd913d6378036d2a62f86d211226f114b89ed64b78b957c",
  "analysis_source_hash": "sha256:7953a9a67ed9aa211746f38867673b593bd271561ca2dcc200f6893be6fa62d4",
  "attempt_1_id": "attempt_3c478bbb5e7141603744fadfe484c4859fac39a56b525df8b5be0fb2a8e1cdfa",
  "attempt_2_id": "attempt_39000746f7552464b07d9a8e1b2035a6e9e0fbf341f34dc6bf02c4a87fe82d8c",
  "canonical_attempt_content_hash": "sha256:774c51b066c731387c47abb3f8f10e91a7a85839d9c720b5a4c0dc5716e5cfcd",
  "canonical_manifest_content_hash": "sha256:6551e7186d9412a99d5a2d31a35e453074c8d0ac2a4818d13208cd296b360300",
  "canonical_manifest_source_hash": "sha256:fe244d0ea95bec77e4c9d2c647b9cc0ad2611ba870e2feee57b0b2d1e0971e3d",
  "execution_input_content_hash": "sha256:799508604fdc53033bf8c63c9e2971e7e351d1dc4468ec14208bb2fb5d823dd0",
  "execution_input_source_hash": "sha256:e0c044edd90b421a91d3f2631189089cfdb4004e225a2057cb24a1c1121c89a8",
  "integrity_context_hash": "sha256:e4be3e84171514c5a974184e746dccee14dc00793974ee00d3c3a16ff9f0b10e",
  "integrity_report_hash": "sha256:d7a03e650ba4641e59aa67a64ce425b813658444e24536a0d065ba9d83015d70",
  "metric_profile_content_hash": "sha256:86901c38c4f7063f1275282e0ce6b252b78a76c4814cdb1c920e0e3edcbabc96",
  "metric_profile_source_hash": "sha256:d9e6099bb153e35bdd502943a5cbeddb4371a3b210243a589972d1dd5e85ed18",
  "mismatch_verification_content_hash": "sha256:c99b5df95fcc306b83749bb62c34649632df7bcc0816b9f7708e23d89904d731",
  "proof_id": "proof_9000688b5992377897a367be231a3c5970b95e2fe76799b720798ae24e50db55",
  "proof_id_preimage_hash": "sha256:9000688b5992377897a367be231a3c5970b95e2fe76799b720798ae24e50db55",
  "proof_manifest_content_hash": "sha256:fe1fd032c80337bad45ed53ee61dc88c3a7e3c15d4ce289e2cc1a51e085b6d35",
  "proof_manifest_source_hash": "sha256:b40268f9eb601bf8383d5b9af34bff5486e75e7a9f5953b4382c2b8a173b866f",
  "proof_publication_id": "proof_publication_c9be3c9296648ae0c401249af47fa84119dcd78305e5d154cd4fb61fe14ef31c",
  "proof_publication_id_preimage_hash": "sha256:c9be3c9296648ae0c401249af47fa84119dcd78305e5d154cd4fb61fe14ef31c",
  "publication_hash": "sha256:48793f72b1087bb676c543cb96b9e59abb3bdf3c3ec56fbe2051b9c8bca197a0",
  "publication_source_hash": "sha256:60305f64082f206a4672dae85e4f0610a71ccdac2178bc024e07b9b896b913e4",
  "result_hash": "sha256:1a42145f8495c3667a0146d36b3cd02d73405f6e5e4a042779c8174be41c1b02",
  "retention_proof_hash": "sha256:7162fce02f8de48e344ef32dd2ba5e961f2640eb04a4e77e469fef516cbcf929",
  "retention_source_hash": "sha256:e82f9e8927dad77e0607efae636d4087a54d3fe8cc84e890fe47876bb7c72a72",
  "verification_content_hash": "sha256:b4bd1939cda15bc4ba9a82ee9c27c8fa7f5b8782f52eb5694b7c90fab07e22e7",
  "verification_source_hash": "sha256:023c8e675743c8a844c9df768727f0c7249e740615c02b14855c8a2722d93dcc"
}
```

## 11. Runnable cooperative recovery classification

This stdlib-only simulation freezes safe mutation/refusal and ordering. It deliberately
models classification, not filesystem deletion.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class State:
    exclusive: bool = True
    lock: bool = True
    staging: bool = False
    final: str = "absent"  # absent, exact, malformed, partial, escaping
    unmanaged_sibling: bool = False


def recover(state: State) -> tuple[str, ...]:
    if not state.exclusive:
        return ("RECOVERY_UNSAFE",)
    if state.unmanaged_sibling or state.final in {"malformed", "partial", "escaping"}:
        return ("RECOVERY_UNSAFE",)
    if state.staging and state.final != "absent":
        return ("RECOVERY_UNSAFE",)
    actions = []
    if state.staging:
        actions += ["remove_exact_staging", "fsync_proof_parent"]
    if state.lock:
        actions += ["unlink_exact_lock", "fsync_run_parent"]
    actions.append("retry_normal_lock")
    if state.final == "exact":
        actions += ["verify_exact_final_under_lock", "fsync_final", "fsync_proof_parent"]
    return tuple(actions)

assert recover(State(staging=True)) == (
    "remove_exact_staging", "fsync_proof_parent",
    "unlink_exact_lock", "fsync_run_parent", "retry_normal_lock",
)
assert recover(State(final="exact")) == (
    "unlink_exact_lock", "fsync_run_parent", "retry_normal_lock",
    "verify_exact_final_under_lock", "fsync_final", "fsync_proof_parent",
)
assert recover(State(final="absent"))[-1] == "retry_normal_lock"
for unsafe in (
    State(exclusive=False), State(staging=True, final="exact"),
    State(final="malformed"), State(final="partial"), State(final="escaping"),
    State(unmanaged_sibling=True),
):
    assert recover(unsafe) == ("RECOVERY_UNSAFE",)
```

## 12. Acceptance and immediate successor

The field audit is closed: only the exact non-CAS G12D publication/retention bodies are
embedded; all request, Build, PREP, case, Attempt, trace, result, metric-profile, proof,
and canonical children use refs/hashes or one owning body. The hash direction is
inputs→verification→proof manifest→Integrity/canonical Attempt→result/evaluation→
canonical manifest→analysis; no child contains a descendant hash.

DRP-00 is `ACCEPTED_H1`; the Matrix row is `READY — DRP-00 CONTRACT_FROZEN`.
DRP-01 is the sole immediate Ready node. DRP-02 through DRP-05 remain blocked on their
predecessors.
