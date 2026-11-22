"""Durable execution claims for the isolated, opt-in referenced run layout."""
from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
from tempfile import NamedTemporaryFile

from crypto_quant_domain import (ArtifactEnvelope, ArtifactIntegrityError, ArtifactNotFoundError,
    ArtifactReadResult, ArtifactRef, canonical_bytes)

from ._publication import canonical_hash, ensure_directory, fsync_directory
from ._segmented_economic_result import _VerifiedPagedResult, verify_economic_paged_result
from .runner import AttemptIdentity


_RUN = re.compile(r"run_[a-f0-9]{64}")
_MAX_CLAIM = 16 * 1024
_CLAIM = "started.json"
_LOCK = ".referenced-publication.lock"
_LAYOUT_MARKER = ".backtest-evidence-layout"
_LAYOUT_BYTES = b"backtest.referenced_v1.segmented\n"


def _plain_directory(path: Path) -> None:
    # The publication tree is controlled and local; no symlinked ancestor may be used.
    if path.absolute() != path.resolve():
        raise ArtifactIntegrityError("referenced evidence directory must not traverse symlinks")
    ensure_directory(path)


class _ReferencedRunLock:
    """Linux local filesystem lock; stable inode survives death of the owner."""

    def __init__(self, *, root: Path, semantic_run_id: str) -> None:
        if not isinstance(root, Path) or type(semantic_run_id) is not str or not _RUN.fullmatch(semantic_run_id):
            raise ValueError("invalid referenced run lock coordinates")
        self.run_directory = root / "runs" / semantic_run_id
        self.semantic_run_id = semantic_run_id
        self._fd = None

    def __enter__(self):
        if self._fd is not None:
            raise RuntimeError("referenced run lock is not reentrant")
        _plain_directory(self.run_directory)
        path = self.run_directory / _LOCK
        fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ArtifactIntegrityError("referenced run lock needs a private regular inode")
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            linked = path.stat(follow_symlinks=False)
            if (linked.st_dev, linked.st_ino) != (info.st_dev, info.st_ino):
                raise ArtifactIntegrityError("referenced run lock inode changed")
            fsync_directory(self.run_directory)
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        return self

    def __exit__(self, exc_type, exc, traceback):
        fd, self._fd = self._fd, None
        if fd is not None:
            os.close(fd)

    def claim_directory(self, attempt: AttemptIdentity) -> Path:
        if self._fd is None:
            raise RuntimeError("referenced claim needs a held run lock")
        if type(attempt) is not AttemptIdentity or attempt.semantic_run_id != self.semantic_run_id:
            raise ArtifactIntegrityError("referenced claim Attempt outside locked run")
        return self.run_directory / "attempts" / attempt.attempt_id


@dataclass(frozen=True, slots=True)
class _ReferencedAttemptClaimV1:
    attempt: AttemptIdentity
    request_ref: ArtifactRef
    input_ref: ArtifactRef
    case_hash: str

    def __post_init__(self) -> None:
        if type(self.attempt) is not AttemptIdentity:
            raise TypeError("referenced claim requires exact Attempt identity")
        first = AttemptIdentity.first(self.attempt.semantic_run_id)
        if self.attempt not in (first, AttemptIdentity.retry(first, next_ordinal=2)):
            raise ValueError("referenced claim requires the first or its exact second Attempt")
        for ref, kind, version in ((self.request_ref, "backtest_request", 1),
                                    (self.input_ref, "backtest_execution_input_bundle", 9)):
            if type(ref) is not ArtifactRef or (ref.artifact_type, ref.schema_version) != (kind, version):
                raise ValueError("referenced claim source coordinate mismatch")
        canonical_hash("claim case_hash", self.case_hash)

    def to_canonical_dict(self):
        return {"type": "backtest_referenced_attempt_started", "schema_version": 1,
                "attempt": self.attempt, "request_ref": self.request_ref, "input_ref": self.input_ref,
                "case_hash": self.case_hash, "input_origin": "precomputed_target_stream"}


def _native_bytes(path: Path, cap: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as file:
        info = os.fstat(file.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_mode & 0o222
                or not 0 < info.st_size <= cap):
            raise ArtifactIntegrityError("invalid native referenced evidence file")
        data = file.read(info.st_size + 1)
        if len(data) != info.st_size:
            raise ArtifactIntegrityError("native referenced evidence size changed")
        return data


def _note_write_failure(error: Exception, *, stage: str, role: str, file: str, byte_count: int) -> None:
    # Keep the original infrastructure error and include only controlled coordinates.
    with suppress(Exception):
        kind = f"{type(error).__module__}.{type(error).__qualname__}"
        if not re.fullmatch(r"[A-Za-z0-9_.]{1,128}", kind):
            kind = "other"
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", role):
            role = "other"
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", file):
            file = "other"
        errno = error.errno if isinstance(error, OSError) else None
        if type(errno) is not int or not 0 <= errno < 2**31:
            errno = None
        error.add_note(f"Referenced artifact write: stage={stage} role={role} file={file} "
                       f"exception_type={kind} errno={errno} byte_count={byte_count}")


def _put_referenced(publisher, envelope: ArtifactEnvelope, source: bytes) -> ArtifactRef:
    try:
        return publisher.put(envelope=envelope)
    except Exception as error:
        _note_write_failure(error, stage="cas_put", role=envelope.artifact_type, file="none", byte_count=len(source))
        raise


def _publish_native(path: Path, source: bytes, *, role: str = "native_evidence") -> None:
    """Only while holding this run's lock. Never make a writable final name visible."""
    if os.path.lexists(path):
        raise FileExistsError(str(path))
    temp = None
    stage = "file_write"
    try:
        with NamedTemporaryFile(dir=path.parent, prefix=".staging-", delete=False) as file:
            temp = Path(file.name)
            file.write(source)
            file.flush()
            os.fchmod(file.fileno(), 0o444)
            stage = "file_fsync"
            os.fsync(file.fileno())
        stage = "rename"
        temp.rename(path)
        temp = None
        stage = "directory_fsync"
        fsync_directory(path.parent)
    except OSError as error:
        _note_write_failure(error, stage=stage, role=role, file=path.name, byte_count=len(source))
        raise
    finally:
        if temp is not None:
            with suppress(OSError):
                temp.unlink(missing_ok=True)


def _validate_evidence_layout(layout) -> None:
    if type(layout) is not str or layout not in ("legacy", "referenced_v1"):
        raise ValueError("unsupported Backtest evidence_layout")


def _check_legacy_layout(root: Path) -> None:
    if os.path.lexists(root / _LAYOUT_MARKER):
        raise ArtifactIntegrityError("legacy Backtest cannot write to a marked referenced root")


def _require_referenced_layout(root: Path, *, initialize: bool) -> None:
    if not isinstance(root, Path) or root.absolute() != root.resolve():
        raise ArtifactIntegrityError("referenced publication root must be a plain directory path")
    marker = root / _LAYOUT_MARKER
    if not os.path.lexists(marker):
        if not initialize:
            raise FileNotFoundError("referenced publication root is not marked")
        _plain_directory(root)
        if next(root.iterdir(), None) is not None:
            raise ArtifactIntegrityError("referenced publication requires a marked or empty root")
        _publish_native(marker, _LAYOUT_BYTES, role="layout_marker")
    if _native_bytes(marker, 128) != _LAYOUT_BYTES:
        raise ArtifactIntegrityError("unknown referenced publication layout marker")


def _verify_attempt_claim(lock: _ReferencedRunLock, claim: _ReferencedAttemptClaimV1) -> None:
    directory = lock.claim_directory(claim.attempt)
    if directory.absolute() != directory.resolve():
        raise ArtifactIntegrityError("referenced claim path must not traverse symlinks")
    if _native_bytes(directory / _CLAIM, _MAX_CLAIM) != canonical_bytes(claim):
        raise ArtifactIntegrityError("referenced started claim does not match expected bytes")


def _write_attempt_claim(lock: _ReferencedRunLock, claim: _ReferencedAttemptClaimV1) -> None:
    directory = lock.claim_directory(claim.attempt)
    _plain_directory(directory)
    path = directory / _CLAIM
    if os.path.lexists(path):
        raise FileExistsError("referenced Attempt already started; do not execute again")
    _publish_native(path, canonical_bytes(claim), role="attempt_claim")
    _verify_attempt_claim(lock, claim)


_RESULT_CAPS = {"backtest_economic_evidence_page": 8 * 1024 * 1024,
                "backtest_economic_paged_result": 16 * 1024 * 1024}


class _ReferencedResultObjects:
    """Artifact ports over immutable native objects plus the existing CAS."""

    def __init__(self, *, lock: _ReferencedRunLock, reader, publisher):
        self._lock = lock
        self._directory = lock.run_directory / "objects"
        self._reader = reader
        self._publisher = publisher

    def _location(self, ref: ArtifactRef) -> tuple[Path, int]:
        if self._lock._fd is None:
            raise RuntimeError("referenced object transport requires a held run lock")
        if type(ref) is not ArtifactRef or ref.artifact_type not in _RESULT_CAPS or ref.schema_version != 1:
            raise ArtifactIntegrityError("unsupported referenced object coordinates")
        digest = canonical_hash("result content hash", ref.content_hash).split(":", 1)[1]
        if self._directory.absolute() != self._directory.resolve():
            raise ArtifactIntegrityError("referenced object directory must not traverse symlinks")
        return self._directory / (digest + ".json"), _RESULT_CAPS[ref.artifact_type]

    def read(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        path, cap = self._location(ref)
        data = _native_bytes(path, cap)
        result = self._reader.read(ref=ref)
        if (type(result) is not ArtifactReadResult or ArtifactRef.from_envelope(result.envelope) != ref
                or result.source_bytes != data):
            raise ArtifactIntegrityError("referenced result CAS/native bytes mismatch")
        return result

    def read_native(self, *, ref: ArtifactRef) -> ArtifactReadResult:
        path, cap = self._location(ref)
        source = _native_bytes(path, cap)
        envelope = ArtifactEnvelope(**json.loads(source))
        if ArtifactRef.from_envelope(envelope) != ref or canonical_bytes(envelope) != source:
            raise ArtifactIntegrityError("native object does not bind its canonical result coordinate")
        return ArtifactReadResult(envelope, envelope.payload, source, "sha256:" + sha256(source).hexdigest())

    def put(self, *, envelope: ArtifactEnvelope) -> ArtifactRef:
        return self._put_source(envelope=envelope, source=None)

    def _put_encoded_page(self, *, envelope: ArtifactEnvelope, encoded: bytes) -> ArtifactRef:
        # The page codec passes the canonical bytes of this exact new envelope.
        return self._put_source(envelope=envelope, source=encoded)

    def _put_source(self, *, envelope: ArtifactEnvelope, source: bytes | None) -> ArtifactRef:
        if type(envelope) is not ArtifactEnvelope:
            raise TypeError("referenced object put needs an exact envelope")
        ref = ArtifactRef.from_envelope(envelope)
        path, cap = self._location(ref)
        if source is None:
            source = canonical_bytes(envelope)
        if not 0 < len(source) <= cap:
            raise ValueError("referenced result object exceeds byte cap")
        _plain_directory(path.parent)
        if not os.path.lexists(path):
            if self._publisher is None:
                raise FileNotFoundError(str(path))
            _publish_native(path, source, role=envelope.artifact_type)
        if _native_bytes(path, cap) != source:
            raise ArtifactIntegrityError("referenced result native source differs from newly encoded bytes")
        try:
            stored = self._reader.read(ref=ref)
        except ArtifactNotFoundError:
            if self._publisher is None:
                raise
            if _put_referenced(self._publisher, envelope, source) != ref:
                raise ArtifactIntegrityError("referenced CAS put returned a different ref")
            stored = self._reader.read(ref=ref)
        if (type(stored) is not ArtifactReadResult or ArtifactRef.from_envelope(stored.envelope) != ref
                or stored.source_bytes != source):
            raise ArtifactIntegrityError("referenced result CAS source differs from native source")
        return ref


_RECORD_TYPE = "attempt_execution_record"
_RECORD_FILE = "referenced-attempt.json"
_MANIFEST_FILE = "referenced-attempt-manifest.json"


@dataclass(frozen=True, slots=True)
class _ReferencedEntry:
    role: str
    artifact_ref: ArtifactRef
    source_hash: str
    byte_count: int

    def to_canonical_dict(self):
        return {"role": self.role, "artifact_ref": self.artifact_ref,
                "source_hash": self.source_hash, "byte_count": self.byte_count}


def _entry(role, ref, source):
    return _ReferencedEntry(role, ref, "sha256:" + sha256(source).hexdigest(), len(source))


def _mirror_exact(envelope, source, *, reader, publisher):
    ref = ArtifactRef.from_envelope(envelope)
    try:
        read = reader.read(ref=ref)
    except ArtifactNotFoundError:
        if publisher is None:
            raise
        if _put_referenced(publisher, envelope, source) != ref:
            raise ArtifactIntegrityError("referenced CAS put returned a wrong ref")
        read = reader.read(ref=ref)
    if (type(read) is not ArtifactReadResult or ArtifactRef.from_envelope(read.envelope) != ref
            or read.source_bytes != source or read.source_hash != "sha256:" + sha256(source).hexdigest()):
        raise ArtifactIntegrityError("referenced CAS source does not match committed evidence")
    return ref


def _ensure_metadata_file(path, source, *, write):
    if not 0 < len(source) <= _MAX_CLAIM:
        raise ValueError("referenced metadata exceeds byte cap")
    if write and not os.path.lexists(path):
        _publish_native(path, source, role=path.stem.replace("-", "_"))
    if _native_bytes(path, _MAX_CLAIM) != source:
        raise ArtifactIntegrityError("referenced metadata disagrees with committed native evidence")


def _bind_attempt_sources(claim, resolved, *, reader, publisher):
    values = (("request", "backtest_request", resolved.request),
              ("build", "build_artifact_manifest", resolved.build_artifact_manifest),
              ("environment", "resolved_backtest_environment", resolved.environment),
              ("market", "market_bundle_ref", resolved.environment.market_bundle_ref),
              ("compatibility", "environment_compatibility_report", resolved.environment.compatibility_report))
    entries = []
    for role, kind, value in values:
        envelope = ArtifactEnvelope.create(kind, 1, value)
        source = canonical_bytes(envelope)
        ref = _mirror_exact(envelope, source, reader=reader, publisher=None if role == "request" else publisher)
        if role == "request" and ref != claim.request_ref:
            raise ArtifactIntegrityError("referenced Attempt request coordinate mismatch")
        entries.append(_entry(role, ref, source))
    inp = reader.read(ref=claim.input_ref)
    if (type(inp) is not ArtifactReadResult or ArtifactRef.from_envelope(inp.envelope) != claim.input_ref
            or inp.source_bytes != canonical_bytes(inp.envelope)):
        raise ArtifactIntegrityError("referenced Attempt input9 source mismatch")
    entries.append(_entry("input", claim.input_ref, inp.source_bytes))
    return tuple(entries)


def _require_fresh_attempt_tree(lock: _ReferencedRunLock, first: _ReferencedAttemptClaimV1) -> None:
    if first.attempt.ordinal != 1:
        raise ArtifactIntegrityError("referenced run must start with Attempt one")
    lock.claim_directory(first.attempt)  # Require this run's held lock before inspecting any state.
    for name in ("attempts", "objects", "canonical", "canonical-v2", "canonical-v3", "referenced-publication", ".publication.lock"):
        if os.path.lexists(lock.run_directory / name):
            raise FileExistsError("referenced run already has evidence; use recovery, not re-execution")


@dataclass(frozen=True, slots=True)
class _BoundReferencedAttempt:
    claim: _ReferencedAttemptClaimV1
    record: _ReferencedEntry
    manifest: _ReferencedEntry
    sources: tuple[_ReferencedEntry, ...]
    result: _VerifiedPagedResult

    @property
    def record_ref(self) -> ArtifactRef:
        return self.record.artifact_ref


def _attempt_record(claim, result, sources):
    return ArtifactEnvelope.create(_RECORD_TYPE, 2, {
        "type": _RECORD_TYPE, "schema_version": 2, "status": "READY_TO_FINALIZE",
        "started": claim, "build_manifest_ref": sources[1].artifact_ref,
        "resolved_environment_ref": sources[2].artifact_ref,
        "result_ref": result.ref, "result_source_hash": result.source_hash,
        "result_byte_count": result.byte_count, "execution_result_hash": result.execution_result_hash,
        "target_stream_digest": result.target_stream_digest, "trace_hash": result.trace_hash,
    })


def _attempt_manifest(claim, result, sources, record):
    return ArtifactEnvelope.create("evidence_manifest", 2, {
        "type": "evidence_manifest", "schema_version": 2, "status": "READY_FOR_INTEGRITY",
        "attempt": claim.attempt,
        "artifacts": (*sources, record, _ReferencedEntry("paged_result", result.ref, result.source_hash, result.byte_count)),
    })


def _close_verified_attempt(lock, claim, result, *, sources, reader, publisher) -> _BoundReferencedAttempt:
    if type(result) is not _VerifiedPagedResult or result.case_hash != claim.case_hash:
        raise ArtifactIntegrityError("referenced Attempt result Case differs from started claim")
    _verify_attempt_claim(lock, claim)
    directory = lock.claim_directory(claim.attempt)
    envelope = _attempt_record(claim, result, sources)
    source = canonical_bytes(envelope)
    _ensure_metadata_file(directory / _RECORD_FILE, source, write=publisher is not None)
    record = _entry("record", _mirror_exact(envelope, source, reader=reader, publisher=publisher), source)
    envelope = _attempt_manifest(claim, result, sources, record)
    source = canonical_bytes(envelope)
    _ensure_metadata_file(directory / _MANIFEST_FILE, source, write=publisher is not None)
    manifest = _entry("manifest", _mirror_exact(envelope, source, reader=reader, publisher=publisher), source)
    return _BoundReferencedAttempt(claim, record, manifest, sources, result)


def _recover_verified_attempt(lock, claim, *, objects, reader, publisher, source_reader, case, sources):
    """Finish mirroring an intact record, never run the engine or infer an Attempt from a result ref."""
    _verify_attempt_claim(lock, claim)
    try:
        source = _native_bytes(lock.claim_directory(claim.attempt) / _RECORD_FILE, _MAX_CLAIM)
    except FileNotFoundError:
        if os.path.lexists(lock.claim_directory(claim.attempt) / _MANIFEST_FILE):
            raise ArtifactIntegrityError("committed Attempt manifest lost its record") from None
        return None  # A started claim without a committed record is in doubt.
    envelope = ArtifactEnvelope(**json.loads(source))
    if ((envelope.artifact_type, envelope.schema_version) != (_RECORD_TYPE, 2)
            or canonical_bytes(envelope) != source
            or canonical_bytes(envelope.payload["started"]) != canonical_bytes(claim)):
        raise ArtifactIntegrityError("referenced Attempt record does not bind its started claim")
    value = envelope.payload["result_ref"]
    ref = ArtifactRef(value["artifact_type"], value["schema_version"], value["content_hash"])
    checked_refs = {}

    class RecoveryReader:
        def read(self, *, ref):
            record = objects.read_native(ref=ref)
            checked_refs[ref] = record.source_hash
            return record

    result = verify_economic_paged_result(reader=RecoveryReader(), source_reader=source_reader, result_ref=ref, case=case)
    if canonical_bytes(_attempt_record(claim, result, sources)) != source:
        raise ArtifactIntegrityError("referenced Attempt record does not exactly cover the verified result")
    record = _entry("record", ArtifactRef.from_envelope(envelope), source)
    manifest_path = lock.claim_directory(claim.attempt) / _MANIFEST_FILE
    if os.path.lexists(manifest_path):
        _ensure_metadata_file(manifest_path, canonical_bytes(_attempt_manifest(claim, result, sources, record)), write=False)
    # Do not put anything until the native evidence graph has passed full strict verification.
    # Children first, then result index, then Attempt record. A failure leaves the original proof.
    for coord in (*[child for child in checked_refs if child != ref], ref):
        file = objects.read_native(ref=coord)
        if file.source_hash != checked_refs[coord]:
            raise ArtifactIntegrityError("referenced result object changed during recovery")
        objects.put(envelope=file.envelope)
    return _close_verified_attempt(lock, claim, result, sources=sources, reader=reader, publisher=publisher)


@dataclass(frozen=True, slots=True)
class _ReferencedClosedAttemptSetV1:
    """An explicitly closed ref-only set; one member is insufficient."""
    first: _BoundReferencedAttempt
    second: _BoundReferencedAttempt | None

    @property
    def attempts(self) -> tuple[_BoundReferencedAttempt, ...]:
        return (self.first,) if self.second is None else (self.first, self.second)

    @property
    def consistent(self) -> bool:
        # _VerifiedPagedResult equality also binds source hash, source length and trace/Case.
        return self.second is not None and self.first.result == self.second.result

    def to_canonical_dict(self):
        return {"type": "backtest_referenced_closed_attempt_set", "schema_version": 1,
                "semantic_run_id": self.first.claim.attempt.semantic_run_id,
                "request_ref": self.first.claim.request_ref, "input_ref": self.first.claim.input_ref,
                "case_hash": self.first.claim.case_hash,
                "build_manifest_ref": self.first.sources[1].artifact_ref,
                "resolved_environment_ref": self.first.sources[2].artifact_ref,
                "attempts": tuple({"attempt": a.claim.attempt, "record": a.record, "manifest": a.manifest,
                    "execution_result_hash": a.result.execution_result_hash, "result_ref": a.result.ref,
                    "result_source_hash": a.result.source_hash, "result_byte_count": a.result.byte_count,
                    "target_stream_digest": a.result.target_stream_digest, "trace_hash": a.result.trace_hash}
                    for a in self.attempts)}


def _bind_referenced_closed_set(lock, first, second) -> _ReferencedClosedAttemptSetV1:
    if type(first) is not _BoundReferencedAttempt or (second is not None and type(second) is not _BoundReferencedAttempt):
        raise ArtifactIntegrityError("referenced close needs exact bound Attempts")
    a = first.claim
    if a.attempt.ordinal != 1:
        raise ArtifactIntegrityError("referenced close needs the first Attempt")
    if second is not None:
        b = second.claim
        if (b.attempt != AttemptIdentity.retry(a.attempt, next_ordinal=2)
                or (a.request_ref, a.input_ref, a.case_hash) != (b.request_ref, b.input_ref, b.case_hash)
                or first.sources != second.sources or first.record_ref == second.record_ref):
            raise ArtifactIntegrityError("referenced close Attempt identity or source mismatch")
    closed = _ReferencedClosedAttemptSetV1(first, second)
    directory = lock.claim_directory(a.attempt).parent
    if (directory.absolute() != directory.resolve()
            or {path.name for path in directory.iterdir()} != {value.claim.attempt.attempt_id for value in closed.attempts}):
        raise ArtifactIntegrityError("referenced close does not cover all eligible Attempts")
    for bound in closed.attempts:
        _verify_attempt_claim(lock, bound.claim)
        record = _attempt_record(bound.claim, bound.result, bound.sources)
        manifest = _attempt_manifest(bound.claim, bound.result, bound.sources, bound.record)
        for value, role, filename, entry in ((record, "record", _RECORD_FILE, bound.record),
                                             (manifest, "manifest", _MANIFEST_FILE, bound.manifest)):
            source = canonical_bytes(value)
            if _entry(role, ArtifactRef.from_envelope(value), source) != entry:
                raise ArtifactIntegrityError("referenced close metadata is not the exact bound Attempt")
            _ensure_metadata_file(lock.claim_directory(bound.claim.attempt) / filename, source, write=False)
    return closed
