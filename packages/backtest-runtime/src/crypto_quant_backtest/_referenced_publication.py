"""Ref-only Integrity and canonical commit for the private paged evidence graph."""
from __future__ import annotations

from dataclasses import dataclass
import os

from crypto_quant_domain import (
    ArtifactEnvelope, ArtifactIntegrityError, ArtifactReadResult, ArtifactRef, canonical_bytes, canonical_sha256,
)

from ._referenced_evidence import (
    _BoundReferencedAttempt, _MAX_CLAIM, _ReferencedAttemptClaimV1, _ReferencedClosedAttemptSetV1,
    _attempt_manifest, _attempt_record, _bind_attempt_sources, _bind_referenced_closed_set,
    _ensure_metadata_file, _entry, _mirror_exact, _plain_directory,
)
from .integrity import (
    DeterministicRebuildEvidence, IntegrityIssue, IntegrityIssueCode, IntegrityIssueSeverity,
    IntegrityTraceLevel, ResultGrade, _rebuild_integrity_issues,
)
from .resolution import RequestedResultGrade


_DIRECTORY = "referenced-publication"
_ROOT = "canonical-publication-manifest.json"
_INTEGRITY_FILE = "integrity-report.json"


@dataclass(frozen=True, slots=True)
class _ReferencedPublicationPlan:
    outcome: str
    children: tuple[tuple[str, ArtifactEnvelope], ...]
    manifest: ArtifactEnvelope


def _plan_publication(closed, *, resolved, case):
    first = closed.first
    run_id = first.claim.attempt.semantic_run_id
    if (run_id != resolved.semantic_run_id or first.claim.case_hash != case.case_hash
            or any(value.result.target_stream_digest != resolved.request.target_stream_digest for value in closed.attempts)
            or resolved.request.result_grade_requested is not RequestedResultGrade.DEVELOPMENT):
        raise ArtifactIntegrityError("referenced Integrity does not bind the original DEVELOPMENT Case")
    build = resolved.build_artifact_manifest
    env = resolved.environment
    rebuild = DeterministicRebuildEvidence(run_id, canonical_sha256(resolved.request), env.environment_hash,
        build.manifest_hash, env.market_bundle_ref.manifest_hash, None, resolved.request.target_stream_digest,
        resolved.request.execution_case_semantic_hash, case.case_hash, first.result.trace_hash,
        IntegrityTraceLevel.FULL_TRACE, first.result.execution_result_hash, None)
    engine_context_binding = {
        "case_hash": case.case_hash, "semantic_spec_hash": case.semantic_spec_hash,
        "identity_manifest_hash": canonical_sha256(case.identity_manifest),
        "initial_financial_state_hash": canonical_sha256(case.financial_state),
        "target_stream_digest": case.target_stream.target_stream_digest,
    }
    children = []

    def artifact(kind, version, fields):
        return ArtifactEnvelope.create(kind, version, {"type": kind, "schema_version": version, **fields})

    def child(kind, version, fields):
        envelope = artifact(kind, version, fields)
        children.append((kind, envelope))
        return ArtifactRef.from_envelope(envelope)

    common = {"semantic_run_id": run_id, "closed_attempt_set_hash": canonical_sha256(closed)}
    canonical = None
    blocking = ()
    if closed.second is None:
        blocking = (IntegrityIssue(IntegrityIssueCode.INSUFFICIENT_ATTEMPTS, IntegrityIssueSeverity.BLOCKING, (run_id,)),)
    elif closed.consistent:
        canonical = child("canonical_attempt_ref", 3, {**common, "attempt": first.claim.attempt,
            "attempt_manifest": first.manifest, "execution_result_hash": first.result.execution_result_hash,
            "result_ref": first.result.ref})
    else:
        blocking = (IntegrityIssue(IntegrityIssueCode.EXECUTION_HASH_MISMATCH, IntegrityIssueSeverity.BLOCKING,
                                   (first.claim.attempt.attempt_id, closed.second.claim.attempt.attempt_id),
                                   (common["closed_attempt_set_hash"],)),)
    issues = (*blocking, *_rebuild_integrity_issues(resolved, rebuild, IntegrityIssueSeverity.LIMITATION))
    grade = ResultGrade.DEVELOPMENT.value if canonical is not None else None
    integrity = child("integrity_report", 3, {**common, "result_grade": grade, "issues": issues,
        "rebuild_evidence": rebuild, "canonical_attempt_ref": canonical, "deployment_authorized": False})
    if canonical is not None:
        outcome = "COMPLETED"
        child("completed_backtest_result", 4, {**common, "result_grade": grade, "integrity_ref": integrity,
            "canonical_attempt_ref": canonical, "execution_result_hash": first.result.execution_result_hash,
            "result_ref": first.result.ref, "request_ref": first.claim.request_ref,
            "execution_input_ref": first.claim.input_ref, "engine_context_binding": engine_context_binding})
    else:
        outcome = "BLOCKED" if closed.second is None else "FAILED"
        child("integrity_evaluation_record", 3, {**common, "outcome": outcome, "integrity_ref": integrity,
            "request_ref": first.claim.request_ref, "execution_input_ref": first.claim.input_ref})
    root = artifact("canonical_publication_manifest", 3, {**common, "outcome": outcome,
        "closed_attempt_set": closed, "engine_context_binding": engine_context_binding,
        "artifacts": tuple(_entry(role, ArtifactRef.from_envelope(env), canonical_bytes(env)) for role, env in children)})
    return _ReferencedPublicationPlan(outcome, tuple(children), root)


def _commit_referenced_publication(lock, closed, *, resolved, case, reader, publisher):
    """Commit or reverify a closed graph. No result or Attempt can be invented here."""
    closed = _bind_referenced_closed_set(lock, closed.first, closed.second)
    plan = _plan_publication(closed, resolved=resolved, case=case)
    directory = lock.run_directory / _DIRECTORY
    planned = tuple((role.replace("_", "-") + ".json", env) for role, env in plan.children)
    planned = (*planned, (_ROOT, plan.manifest))
    if directory.absolute() != directory.resolve():
        raise ArtifactIntegrityError("referenced publication directory must not traverse symlinks")
    if directory.exists():
        files = {path.name for path in directory.iterdir() if not path.name.startswith(".staging-")}
        filenames = {name for name, _ in planned}
        committed = _ROOT in files
        if files - filenames or (committed and files != filenames):
            raise ArtifactIntegrityError("referenced publication metadata exact cover mismatch")
        for name, env in planned:
            if name in files:
                _ensure_metadata_file(directory / name, canonical_bytes(env), write=False)
    elif publisher is not None:
        _plain_directory(directory)
    for name, env in planned:  # Native children, CAS children, native root, CAS root last.
        source = canonical_bytes(env)
        _ensure_metadata_file(directory / name, source, write=publisher is not None)
        ref = _mirror_exact(env, source, reader=reader, publisher=publisher)
    return ref, plan.outcome


def _read_reference_metadata(reader, ref, kind, version):
    if (ref.artifact_type, ref.schema_version) != (kind, version):
        raise ValueError("referenced metadata coordinate mismatch")
    read = reader.read(ref=ref)
    if (type(read) is not ArtifactReadResult or ArtifactRef.from_envelope(read.envelope) != ref
            or read.source_bytes != canonical_bytes(read.envelope)):
        raise ArtifactIntegrityError("referenced metadata source does not match ref")
    if not 0 < len(read.source_bytes) <= _MAX_CLAIM:
        raise ValueError("referenced metadata outside byte cap")
    return read


def _cold_case(reader, market_reader, claim, *, with_bound_sources=False):
    from . import execution_inputs as x
    from .cn_a_share_portfolio_economic_case_v1 import (
        _bind_economic_case_coordinates_v1, _economic_opening_proof_version_v1,
        _verify_economic_action_and_target_sources_v1,
    )
    from .cn_a_share_portfolio_economic_result_v1 import (
        _compose_profile_portfolio_economic_execution_case, _native_initial_economic_financial_state_v1,
        _read_cn_a_share_cash_dividend_action_set_v1, _read_economic_definition_v1,
        _read_economic_definition_v2, _read_exact_economic_source_v1, _registry, _request_v1,
    )
    from .cn_a_share_portfolio_economic_prepare_v2 import _registry_v2
    from .resolution import ProfileResolver
    from .target_repository import BacktestTargetStreamRef

    if market_reader is None:
        raise ValueError("referenced completion requires explicit matching MarketBundleReader")
    retained = _read_reference_metadata(reader, claim.request_ref, "backtest_request", 1)
    request = _request_v1(retained.envelope.payload, market_reader)
    read = reader.read(ref=claim.input_ref)
    if (type(read) is not ArtifactReadResult or ArtifactRef.from_envelope(read.envelope) != claim.input_ref
            or read.source_bytes != canonical_bytes(read.envelope)):
        raise ArtifactIntegrityError("referenced Input9 does not match source bytes")
    bundle = x._read_execution_input_payload_v9(read.envelope.payload)
    del read
    if bundle.request_hash != request.request_hash or bundle.semantic_run_id != claim.attempt.semantic_run_id:
        raise ValueError("referenced Input9 request or semantic run mismatch")
    plan = bundle.execution_case_plan
    definition = plan.definition
    refs = dict(plan.source_refs)
    if _read_exact_economic_source_v1(reader, refs["definition"]) != definition:
        raise ValueError("referenced Input9 definition differs from retained source")
    actions = _read_cn_a_share_cash_dividend_action_set_v1(
        _read_exact_economic_source_v1(reader, refs["cash_dividend_action_set"]).payload)
    target_ref = BacktestTargetStreamRef.from_artifact_ref(refs["target_stream"])
    version = bundle.execution_case_semantic_spec.spec_version
    if definition.schema_version == 3:
        inputs = _read_economic_definition_v2(definition, target_ref, actions, bundle.target_stream)
        registry = _registry_v2(inputs, spec_version=version)
    else:
        inputs = _read_economic_definition_v1(definition, target_ref, actions, source_reader=reader)
        registry = _registry(inputs, spec_version=version)
    initial = _native_initial_economic_financial_state_v1(inputs)
    if initial != (plan.financial_state, plan.initial_dividend_state, plan.initial_economic_projection):
        raise ValueError("referenced Input9 initial state differs from original definition")
    resolved = ProfileResolver().resolve(request=request, registry=registry, market_bundle_manifest=market_reader.manifest,
        build_artifact_manifest=bundle.build_artifact_manifest).resolved
    if resolved is None or resolved.semantic_run_id != claim.attempt.semantic_run_id:
        raise ValueError("referenced original economic Case no longer resolves")
    case = _compose_profile_portfolio_economic_execution_case(resolved_request=resolved, market_reader=market_reader,
        semantic_spec=bundle.execution_case_semantic_spec, target_stream=bundle.target_stream,
        timeline_stream_keys=bundle.timeline_stream_keys, timeline_batch_size=bundle.timeline_batch_size,
        execution_case_plan=plan)
    if case.case_hash != claim.case_hash:
        raise ValueError("referenced reconstructed Case differs from closed set")
    if not with_bound_sources:
        return resolved, case

    bound = None

    def bind_fixed_sources():
        # Finish at the strict verifier's existing source-binding point, not
        # before its result metadata checks. This closure never leaves one load.
        nonlocal bound
        if bound is None:
            _economic_opening_proof_version_v1(definition=definition, spec=case.semantic_spec)
            _verify_economic_action_and_target_sources_v1(reader, refs, actions, case.target_stream)
            bound = _bind_economic_case_coordinates_v1(case, reader, inputs)
        return bound

    return resolved, case, bind_fixed_sources


def _read_referenced_graph(reader, root, *, market_reader, observe_fact=None, observe_header=None):
    """Independently verify a CAS graph, without native paths, writer, engine or cache."""
    from ._segmented_economic_result import verify_economic_paged_result
    from .runner import AttemptIdentity
    from .target_repository import _artifact_ref

    def exact(value, keys):
        from collections.abc import Mapping
        if not isinstance(value, Mapping) or set(value) != set(keys.split()):
            raise ValueError("referenced graph fields mismatch")
        return value

    def child(row, role, kind, version):
        row = exact(row, "role artifact_ref source_hash byte_count")
        if row["role"] != role or type(row["byte_count"]) is not int or not 0 < row["byte_count"] <= _MAX_CLAIM:
            raise ValueError("referenced child role or length mismatch")
        ref = _artifact_ref(row["artifact_ref"])
        loaded = _read_reference_metadata(reader, ref, kind, version)
        expected = _entry(role, ref, loaded.source_bytes)
        if canonical_bytes(row) != canonical_bytes(expected):
            raise ArtifactIntegrityError("referenced child digest or length mismatch")
        return loaded, expected

    raw = exact(root.envelope.payload,
        "type schema_version semantic_run_id closed_attempt_set_hash outcome closed_attempt_set engine_context_binding artifacts")
    if raw["type"] != "canonical_publication_manifest" or type(raw["schema_version"]) is not int or raw["schema_version"] != 3:
        raise ValueError("referenced canonical manifest payload version mismatch")
    negative_roles = (("integrity_report", 3), ("integrity_evaluation_record", 3))
    publication_roles = {"COMPLETED": (("canonical_attempt_ref", 3), ("integrity_report", 3), ("completed_backtest_result", 4)),
                         "FAILED": negative_roles, "BLOCKED": negative_roles}
    roles = publication_roles.get(raw["outcome"])
    if roles is None or type(raw["artifacts"]) is not tuple or len(raw["artifacts"]) != len(roles):
        raise ValueError("referenced canonical manifest does not cover its outcome")
    publication_children = tuple(child(row, role, role, version)[0]
        for row, (role, version) in zip(raw["artifacts"], roles, strict=True))
    group = exact(raw["closed_attempt_set"],
        "type schema_version semantic_run_id request_ref input_ref case_hash build_manifest_ref resolved_environment_ref attempts")
    first = AttemptIdentity.first(raw["semantic_run_id"])
    identities = ((first,) if raw["outcome"] == "BLOCKED"
                  else (first, AttemptIdentity.retry(first, next_ordinal=2)))
    if type(group["attempts"]) is not tuple or len(group["attempts"]) != len(identities):
        raise ValueError("referenced publication Attempt count disagrees with outcome")
    read_attempts = []
    for row, identity in zip(group["attempts"], identities, strict=True):
        row = exact(row, "attempt record manifest execution_result_hash result_ref result_source_hash result_byte_count target_stream_digest trace_hash")
        claim = _ReferencedAttemptClaimV1(identity, _artifact_ref(group["request_ref"]),
            _artifact_ref(group["input_ref"]), group["case_hash"])
        if canonical_bytes(row["attempt"]) != canonical_bytes(identity):
            raise ValueError("referenced publication Attempt identity or order mismatch")
        record, record_entry = child(row["record"], "record", "attempt_execution_record", 2)
        manifest, manifest_entry = child(row["manifest"], "manifest", "evidence_manifest", 2)
        if canonical_bytes(record.envelope.payload["started"]) != canonical_bytes(claim):
            raise ValueError("referenced Attempt has a foreign claim")
        read_attempts.append((claim, record, record_entry, manifest, manifest_entry))
    resolved, case, fixed_sources = _cold_case(reader, market_reader, read_attempts[0][0], with_bound_sources=True)
    sources = _bind_attempt_sources(read_attempts[0][0], resolved, reader=reader, publisher=None)
    verified_results = {}
    bound = []
    for claim, record, record_entry, manifest, manifest_entry in read_attempts:
        ref = _artifact_ref(record.envelope.payload["result_ref"])
        # Per-call only, on the same verified Case. Independently bind each exact Attempt.
        if ref not in verified_results:
            verified_results[ref] = verify_economic_paged_result(reader=reader, source_reader=reader, result_ref=ref, case=case,
                bound_sources=fixed_sources,
                observe_fact=observe_fact if not bound and raw["outcome"] == "COMPLETED" else None,
                observe_header=observe_header if not bound and raw["outcome"] == "COMPLETED" else None)
        result = verified_results[ref]
        if (canonical_bytes(_attempt_record(claim, result, sources)) != record.source_bytes
                or canonical_bytes(_attempt_manifest(claim, result, sources, record_entry)) != manifest.source_bytes):
            raise ValueError("referenced Attempt record or manifest does not cover original sources")
        bound.append(_BoundReferencedAttempt(claim, record_entry, manifest_entry, sources, result))
    closed = _ReferencedClosedAttemptSetV1(bound[0], bound[1] if len(bound) == 2 else None)
    plan = _plan_publication(closed, resolved=resolved, case=case)
    if (canonical_bytes(plan.manifest) != root.source_bytes
            or tuple(canonical_bytes(env) for _, env in plan.children) != tuple(r.source_bytes for r in publication_children)):
        raise ValueError("referenced publication does not bind reverified Integrity decision")
    return plan, resolved, case, closed
