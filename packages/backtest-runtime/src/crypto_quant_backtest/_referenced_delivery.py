"""Opt-in online entry and engine-free delivery recovery."""
from __future__ import annotations

from hashlib import sha256
import json
import os

from crypto_quant_domain import ArtifactEnvelope, ArtifactIntegrityError, ArtifactReadResult, ArtifactRef, canonical_bytes

from ._referenced_evidence import (
    _CLAIM, _MANIFEST_FILE, _MAX_CLAIM, _RECORD_FILE,
    _ReferencedAttemptClaimV1, _ReferencedResultObjects, _ReferencedRunLock,
    _bind_attempt_sources, _bind_referenced_closed_set, _mirror_exact, _native_bytes,
    _recover_verified_attempt, _require_referenced_layout,
    _verify_attempt_claim,
)
from ._referenced_publication import _DIRECTORY, _INTEGRITY_FILE, _ROOT, _commit_referenced_publication
from .evidence import AttemptEvidenceWriter
from .evidence_repository import BacktestEvidenceRepository
from .publication_refs import BacktestCanonicalPublicationRefV3, BacktestDeliveryIncomplete
from .runner import AttemptExecutionRecord, AttemptIdentity, AuditableBacktestRunner


_TERMINALS = "referenced-terminals"
_TERMINAL_BRANCHES = {"BLOCKED": "blocked_report", "FAILED": "failed_report", "CANCELLED": "cancelled_report"}


def _load_native(path, cap):
    if path.absolute() != path.resolve():
        raise ArtifactIntegrityError("referenced native evidence path must not traverse symlinks")
    source = _native_bytes(path, cap)
    env = ArtifactEnvelope(**json.loads(source))
    if canonical_bytes(env) != source:
        raise ArtifactIntegrityError("referenced native evidence is not canonical")
    return env, source


def _terminal_directory(root, attempt):
    return root / _TERMINALS / "runs" / attempt.semantic_run_id / "attempts" / attempt.attempt_id


def _terminal_delivery(runtime, directory, claim, resolved, case, *, publisher):
    reader = runtime._artifact_reader
    root_env, root_source = _load_native(directory / "evidence-manifest.json", 512 * 1024)
    payload = root_env.payload
    status = payload["status"]
    if ((root_env.artifact_type, root_env.schema_version) != ("evidence_manifest", 1)
            or status not in _TERMINAL_BRANCHES or payload["semantic_run_id"] != resolved.semantic_run_id
            or payload["attempt_id"] != claim.attempt.attempt_id):
        raise ValueError("referenced terminal does not match original Attempt")
    root_ref = ArtifactRef.from_envelope(root_env)
    native = {}
    filenames = {"evidence-manifest.json"}
    for entry in runtime._manifest_artifacts(payload):
        name = runtime._manifest_relative_path(entry["relative_path"])
        if name in filenames or "/" in name:
            raise ValueError("referenced terminal native child path mismatch")
        filenames.add(name)
        env, source = _load_native(directory / name, 512 * 1024 * 1024)
        ref = ArtifactRef(entry["artifact_type"], entry["schema_version"], entry["content_hash"])
        if ref in native or ArtifactRef.from_envelope(env) != ref or len(source) != entry["byte_count"]:
            raise ArtifactIntegrityError("referenced terminal child coordinate mismatch")
        item = ArtifactReadResult(env, env.payload, source, "sha256:" + sha256(source).hexdigest())
        if item.source_hash != entry["source_hash"]:
            raise ArtifactIntegrityError("referenced terminal child source mismatch")
        native[ref] = item
    if {file.name for file in directory.iterdir()} != filenames:
        raise ValueError("referenced terminal native graph exact cover mismatch")
    record, = (v.envelope.payload for v in native.values() if v.envelope.artifact_type == "attempt_execution_record")
    branch = record[_TERMINAL_BRANCHES[status]]
    if (canonical_bytes(branch["resolved_request"]) != canonical_bytes(resolved)
            or canonical_bytes(branch["attempt"]) != canonical_bytes(claim.attempt)
            or branch["execution_case_hash"] != case.case_hash):
        raise ValueError("referenced terminal record does not bind request/Case/Attempt")
    root_read = ArtifactReadResult(root_env, payload, root_source, "sha256:" + sha256(root_source).hexdigest())

    class NativeTerminalReader:
        def read(self, *, ref):
            if ref == root_ref:
                return root_read
            if ref in native:
                return native[ref]
            return reader.read(ref=ref)

    # Reprove the original terminal before putting any missing CAS transport.
    terminal = BacktestEvidenceRepository(reader=NativeTerminalReader()).load_terminal(
        root_ref, economic_market_reader=case.timeline.reader)
    if terminal.durable_evidence_ref != root_ref:
        raise ArtifactIntegrityError("referenced terminal verified to a different ref")
    for item in (*native.values(), root_read):
        _mirror_exact(item.envelope, item.source_bytes, reader=reader, publisher=publisher)
    return root_ref


def _deliver(runtime, request, resolved, case, *, cancellation, resume, close_insufficient=False):
    """Only an explicit Backtest-owner call may start an insufficient closure."""
    if close_insufficient and (not resume or cancellation is not None):
        raise ValueError("referenced insufficient close cannot execute or cancel an Attempt")
    root = runtime._publication_root
    reader, publisher = runtime._artifact_reader, runtime._artifact_publisher
    _require_referenced_layout(root, initialize=not resume)
    run_id = resolved.semantic_run_id
    first = AttemptIdentity.first(run_id)
    req = ArtifactRef.from_envelope(ArtifactEnvelope.create("backtest_request", 1, resolved.request))
    input_ref = request.execution_input_bundle_ref
    claims = tuple(_ReferencedAttemptClaimV1(a, req, input_ref, case.case_hash)
                   for a in (first, AttemptIdentity.retry(first, next_ordinal=2)))
    lock = _ReferencedRunLock(root=root, semantic_run_id=run_id)
    pending = ("integrity", "canonical_publication_manifest")
    if resume and not os.path.lexists(lock.run_directory):
        if close_insufficient:
            raise ArtifactIntegrityError("referenced insufficient close requires a finalized first Attempt")
        return BacktestDeliveryIncomplete(run_id, "incomplete", (), (1, 2), pending)
    with lock:
        directory = lock.run_directory
        if any(os.path.lexists(directory / name) for name in ("canonical", "canonical-v2", "canonical-v3", ".publication.lock")):
            raise ArtifactIntegrityError("referenced run contains foreign publication evidence")
        attempts_dir = directory / "attempts"
        if attempts_dir.absolute() != attempts_dir.resolve():
            raise ArtifactIntegrityError("referenced Attempts must not traverse symlinks")
        existing = {p.name for p in attempts_dir.iterdir()} if attempts_dir.exists() else set()
        allowed = {c.attempt.attempt_id for c in claims}
        if existing - allowed or (claims[1].attempt.attempt_id in existing and first.attempt_id not in existing):
            raise ArtifactIntegrityError("referenced run contains foreign or non-contiguous Attempt evidence")
        started = set()
        for claim in claims:
            if claim.attempt.attempt_id not in existing:
                continue
            attempt_directory = lock.claim_directory(claim.attempt)
            if attempt_directory.absolute() != attempt_directory.resolve():
                raise ArtifactIntegrityError("referenced Attempt directory must not traverse symlinks")
            files = {p.name for p in attempt_directory.iterdir() if not p.name.startswith(".staging-")}
            if files and (_CLAIM not in files or files - {_CLAIM, _RECORD_FILE, _MANIFEST_FILE}):
                raise ArtifactIntegrityError("referenced Attempt metadata exact cover mismatch")
            if _CLAIM in files:
                _verify_attempt_claim(lock, claim)
                started.add(claim.attempt.attempt_id)
        publication = directory / _DIRECTORY
        canon = publication / _ROOT
        terminal_root = _terminal_directory(root, first).parent
        if terminal_root.absolute() != terminal_root.resolve():
            raise ArtifactIntegrityError("referenced terminal Attempt parent must not traverse symlinks")
        terminal_names = {p.name for p in terminal_root.iterdir()} if terminal_root.exists() else set()
        if terminal_names - allowed - {".staging"}:
            raise ArtifactIntegrityError("referenced run contains a foreign terminal Attempt")
        terminals = tuple((c, terminal_root / c.attempt.attempt_id) for c in claims
                          if c.attempt.attempt_id in terminal_names)
        if len(terminals) > 1 or (terminals and os.path.lexists(publication)):
            raise ArtifactIntegrityError("referenced run contains competing publications")
        lone_first = existing == {first.attempt_id}
        publication_files = set()
        if lone_first and os.path.lexists(publication):
            if publication.absolute() != publication.resolve():
                raise ArtifactIntegrityError("referenced publication directory must not traverse symlinks")
            publication_files = {p.name for p in publication.iterdir() if not p.name.startswith(".staging-")}
        close_lone_first = close_insufficient or _INTEGRITY_FILE in publication_files
        if close_lone_first and (not lone_first or terminals or first.attempt_id not in started
                or not os.path.lexists(lock.claim_directory(first) / _RECORD_FILE)
                or not os.path.lexists(lock.claim_directory(first) / _MANIFEST_FILE)):
            raise ArtifactIntegrityError("referenced insufficient close requires only the finalized first Attempt")
        mode_writer = publisher if resume else None
        if terminals:
            claim, path = terminals[0]
            _verify_attempt_claim(lock, claim)
            attempt_directory = lock.claim_directory(claim.attempt)
            if any(os.path.lexists(attempt_directory / name) for name in (_RECORD_FILE, _MANIFEST_FILE)):
                raise ArtifactIntegrityError("referenced Attempt has both terminal and successful records")
            if claim.attempt.ordinal == 1 and claims[1].attempt.attempt_id in existing:
                raise ArtifactIntegrityError("referenced retry followed a terminal Attempt")
            if claim.attempt.ordinal == 2:
                sources = _bind_attempt_sources(claims[0], resolved, reader=reader, publisher=None)
                original = _recover_verified_attempt(lock, claims[0],
                    objects=_ReferencedResultObjects(lock=lock, reader=reader, publisher=mode_writer),
                    reader=reader, publisher=mode_writer, source_reader=reader, case=case, sources=sources)
                if original is None:
                    raise ArtifactIntegrityError("referenced terminal retry lost its original successful Attempt")
            return _terminal_delivery(runtime, path, claim, resolved, case, publisher=mode_writer)

        if resume or os.path.lexists(canon):
            if (claims[1].attempt.attempt_id in started
                    and not os.path.lexists(lock.claim_directory(first) / _RECORD_FILE)):
                raise ArtifactIntegrityError("referenced retry is started without its finalized predecessor")
            if not resume and cancellation is not None:
                raise RuntimeError("completed referenced run cannot be cancelled")
            sources = _bind_attempt_sources(claims[0], resolved, reader=reader, publisher=None) if started else ()
            objects = _ReferencedResultObjects(lock=lock, reader=reader, publisher=mode_writer)
            bound = []
            missing = []
            in_doubt = False
            for claim in claims:
                if claim.attempt.attempt_id not in started:
                    missing.append(claim.attempt.ordinal)
                    continue
                value = _recover_verified_attempt(lock, claim, objects=objects, reader=reader,
                    publisher=mode_writer, source_reader=reader, case=case, sources=sources)
                if value is None:
                    missing.append(claim.attempt.ordinal)
                    in_doubt = True
                else:
                    bound.append(value)
            if close_lone_first:
                # Only the explicit call or the original native Integrity report opens
                # this branch. The publisher byte-checks that report before any new output.
                closed = _bind_referenced_closed_set(lock, bound[0], None)
            elif missing:
                has_publication = os.path.lexists(publication) and (not lone_first or bool(publication_files))
                if has_publication or (bound and bound[0].claim.attempt.ordinal == 2):
                    raise ArtifactIntegrityError("referenced publication lost an original Attempt")
                return BacktestDeliveryIncomplete(run_id, "in_doubt" if in_doubt else "incomplete",
                    tuple(a.manifest.artifact_ref for a in bound), tuple(missing), pending)
            else:
                closed = _bind_referenced_closed_set(lock, *bound)
        else:
            if existing or os.path.lexists(directory / "objects") or os.path.lexists(directory / _DIRECTORY):
                raise FileExistsError("referenced run already started; use resume_delivery")
            runner = AuditableBacktestRunner.for_v2(publication_root=root, engine=runtime._economic_case_engine(resolved, case))
            closed = runner._execute_referenced_pair_locked(lock=lock, claim=claims[0], resolved_request=resolved,
                execution_case=case, source_reader=reader, evidence_reader=reader, publisher=publisher, cancellation=cancellation)
            mode_writer = publisher
            if type(closed) is AttemptExecutionRecord:
                runtime._raise_runner_storage_failure(closed)
                outcome = AttemptEvidenceWriter(root=root / _TERMINALS)._publish_locked(closed)
                finalized = outcome.finalized
                if outcome.failure is not None or finalized is None:
                    error = RuntimeError("referenced terminal evidence could not be committed")
                    if outcome.failure is not None:
                        error.add_note(outcome.failure.code.value)
                    if outcome._artifact_write_note is not None:
                        error.add_note(outcome._artifact_write_note)
                    raise error
                path = (root / _TERMINALS / finalized.relative_directory)
                return _terminal_delivery(runtime, path, claims[closed.attempt.ordinal - 1], resolved, case, publisher=publisher)
        ref, outcome = _commit_referenced_publication(lock, closed, resolved=resolved, case=case,
                                                      reader=reader, publisher=mode_writer)
        return BacktestCanonicalPublicationRefV3(ref) if outcome == "COMPLETED" else ref
