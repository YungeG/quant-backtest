from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import tarfile
import unicodedata
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Mapping, cast


_SCHEMA_VERSION = 1
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REF = re.compile(r"[a-z][a-z0-9._-]*\Z")
_SEGMENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*\Z")


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    if value != unicodedata.normalize("NFC", value):
        raise ValueError(f"{name} must be NFC text")
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if not _HASH.fullmatch(text):
        raise ValueError(f"{name} must be sha256 content hash")
    return text


def _member_key(value: object) -> str:
    text = _text("member_key", value)
    try:
        encoded = text.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("member_key must be portable ASCII USTAR key") from error
    parts = text.split("/")
    if (
        not 1 <= len(encoded) <= 100
        or text.startswith("/")
        or text.endswith("/")
        or "\\" in text
        or any(not part or not _SEGMENT.fullmatch(part) for part in parts)
    ):
        raise ValueError("member_key must be portable ASCII USTAR key")
    return text


def _ref(name: str, value: object) -> str:
    text = _text(name, value)
    if not _REF.fullmatch(text):
        raise ValueError(f"{name} must be canonical reference key")
    return text


def _canonical(value: object) -> bytes:
    def normalize(item: object, active: set[int]) -> object:
        if item is None or type(item) in (bool, int):
            return item
        if type(item) is str:
            return _text("canonical string", item)
        identity = id(item)
        if identity in active:
            raise ValueError("cyclic canonical value")
        if type(item) in (list, tuple):
            active.add(identity)
            try:
                sequence = cast(list[object] | tuple[object, ...], item)
                return [normalize(child, active) for child in sequence]
            finally:
                active.remove(identity)
        if isinstance(item, Mapping):
            active.add(identity)
            try:
                result: dict[str, object] = {}
                for key, child in item.items():
                    if type(key) is not str:
                        raise ValueError("canonical mapping keys must be strings")
                    result[_text("canonical key", key)] = normalize(child, active)
                return result
            finally:
                active.remove(identity)
        raise ValueError(f"unsupported canonical type {type(item).__name__}")

    return json.dumps(
        normalize(value, set()),
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class RawSourceMember:
    member_key: str
    raw_bytes: bytes | None = field(repr=False)
    mode: str
    acquired_at_epoch_nanoseconds: int
    declared_sha256: str | None

    def __post_init__(self) -> None:
        _member_key(self.member_key)
        if self.raw_bytes is not None and type(self.raw_bytes) is not bytes:
            raise TypeError("raw_bytes must be bytes or None")
        if self.mode not in {"0644", "0755"}:
            raise ValueError("mode must be 0644 or 0755")
        if type(self.acquired_at_epoch_nanoseconds) is not int:
            raise TypeError("acquisition time must be integer")
        if self.declared_sha256 is not None:
            _hash("declared_sha256", self.declared_sha256)


@dataclass(frozen=True, slots=True)
class SourceSnapshotProvenance:
    vendor_key: str
    source_key: str
    license_ref: str
    retention_policy_ref: str

    def __post_init__(self) -> None:
        for name, value in (
            ("vendor_key", self.vendor_key),
            ("source_key", self.source_key),
            ("license_ref", self.license_ref),
            ("retention_policy_ref", self.retention_policy_ref),
        ):
            _ref(name, value)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "vendor_key": self.vendor_key,
            "source_key": self.source_key,
            "license_ref": self.license_ref,
            "retention_policy_ref": self.retention_policy_ref,
        }


@dataclass(frozen=True, slots=True)
class SourceSnapshotMember:
    member_key: str
    content_hash: str
    byte_count: int
    mode: str
    acquired_at_epoch_nanoseconds: int
    declared_sha256: str | None

    def __post_init__(self) -> None:
        _member_key(self.member_key)
        _hash("content_hash", self.content_hash)
        if type(self.byte_count) is not int or self.byte_count < 0:
            raise ValueError("byte_count must be nonnegative integer")
        if self.mode not in {"0644", "0755"}:
            raise ValueError("mode must be 0644 or 0755")
        if type(self.acquired_at_epoch_nanoseconds) is not int:
            raise TypeError("acquisition time must be integer")
        if self.declared_sha256 is not None:
            _hash("declared_sha256", self.declared_sha256)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "member_key": self.member_key,
            "content_hash": self.content_hash,
            "byte_count": self.byte_count,
            "mode": self.mode,
            "acquired_at_epoch_nanoseconds": self.acquired_at_epoch_nanoseconds,
            "declared_sha256": self.declared_sha256,
        }


class SourceSnapshotFailureCode(str, Enum):
    INVALID_SNAPSHOT_INPUT = "invalid_snapshot_input"
    UNSAFE_MEMBER = "unsafe_member"
    DUPLICATE_MEMBER = "duplicate_member"
    ACQUISITION_FAILED = "acquisition_failed"
    DECLARED_SOURCE_HASH_MISMATCH = "declared_source_hash_mismatch"
    ARCHIVE_INVALID = "archive_invalid"
    SNAPSHOT_ID_MISMATCH = "snapshot_id_mismatch"
    CONTENT_TREE_HASH_MISMATCH = "content_tree_hash_mismatch"
    PROVENANCE_HASH_MISMATCH = "provenance_hash_mismatch"


@dataclass(frozen=True, slots=True)
class SourceSnapshotFailure:
    code: SourceSnapshotFailureCode
    member_key: str | None

    def __post_init__(self) -> None:
        if type(self.code) is not SourceSnapshotFailureCode:
            raise TypeError("code must be SourceSnapshotFailureCode")
        if self.member_key is not None:
            _member_key(self.member_key)

    @property
    def failure_hash(self) -> str:
        return _digest(_canonical(self.to_canonical_dict()))

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "source_snapshot_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "member_key": self.member_key,
        }


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    snapshot_id: str
    archive_bytes: bytes = field(repr=False)
    content_tree_hash: str
    members: tuple[SourceSnapshotMember, ...]
    provenance: SourceSnapshotProvenance
    provenance_hash: str
    decision_grade_eligible: bool
    deployment_authorized: bool

    def __post_init__(self) -> None:
        _hash("snapshot_id", self.snapshot_id)
        if type(self.archive_bytes) is not bytes:
            raise TypeError("archive_bytes must be bytes")
        _hash("content_tree_hash", self.content_tree_hash)
        if type(self.members) is not tuple or any(
            type(member) is not SourceSnapshotMember for member in self.members
        ):
            raise TypeError("members must be tuple of SourceSnapshotMember")
        keys = tuple(member.member_key for member in self.members)
        if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
            raise ValueError("members must use canonical unique order")
        if type(self.provenance) is not SourceSnapshotProvenance:
            raise TypeError("provenance must be SourceSnapshotProvenance")
        _hash("provenance_hash", self.provenance_hash)
        if (
            type(self.decision_grade_eligible) is not bool
            or type(self.deployment_authorized) is not bool
        ):
            raise TypeError("G12A qualification flags must be exact bools")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("G12A qualification flags must remain false")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "source_snapshot",
            "schema_version": _SCHEMA_VERSION,
            "snapshot_id": self.snapshot_id,
            "content_tree_hash": self.content_tree_hash,
            "members": [member.to_canonical_dict() for member in self.members],
            "provenance": self.provenance.to_canonical_dict(),
            "provenance_hash": self.provenance_hash,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    def member_bytes(self, member_key: str) -> bytes:
        if verify_source_snapshot(self).snapshot is None:
            raise ValueError("source snapshot member unavailable")
        try:
            with tarfile.open(fileobj=io.BytesIO(self.archive_bytes), mode="r:gz") as archive:
                extracted = archive.extractfile(member_key)
                if extracted is None:
                    raise ValueError
                return extracted.read()
        except (KeyError, OSError, tarfile.TarError, ValueError) as error:
            raise ValueError("source snapshot member unavailable") from error


@dataclass(frozen=True, slots=True)
class SourceSnapshotOutcome:
    snapshot: SourceSnapshot | None
    failure: SourceSnapshotFailure | None

    def __post_init__(self) -> None:
        if (self.snapshot is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")


def _archive(captured: tuple[tuple[SourceSnapshotMember, bytes], ...]) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(
        fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=9
    ) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for evidence, value in captured:
                member = tarfile.TarInfo(evidence.member_key)
                member.size = len(value)
                member.mode = int(evidence.mode, 8)
                member.mtime = member.uid = member.gid = 0
                member.uname = member.gname = ""
                member.type = tarfile.REGTYPE
                archive.addfile(member, io.BytesIO(value))
    return buffer.getvalue()


def _content_tree_hash(members: tuple[SourceSnapshotMember, ...]) -> str:
    body = {
        "type": "source_snapshot_content_tree",
        "schema_version": _SCHEMA_VERSION,
        "members": [
            {
                "member_key": member.member_key,
                "content_hash": member.content_hash,
                "byte_count": member.byte_count,
                "mode": member.mode,
            }
            for member in members
        ],
    }
    return _digest(_canonical(body))


def _provenance_hash(
    snapshot_id: str,
    provenance: SourceSnapshotProvenance,
    members: tuple[SourceSnapshotMember, ...],
) -> str:
    body = {
        "type": "source_snapshot_provenance",
        "schema_version": _SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        **provenance.to_canonical_dict(),
        "members": [
            {
                "member_key": member.member_key,
                "acquired_at_epoch_nanoseconds": member.acquired_at_epoch_nanoseconds,
                "declared_sha256": member.declared_sha256,
            }
            for member in members
        ],
    }
    return _digest(_canonical(body))


def _failed(
    code: SourceSnapshotFailureCode, member_key: str | None = None
) -> SourceSnapshotOutcome:
    return SourceSnapshotOutcome(None, SourceSnapshotFailure(code, member_key))


def freeze_source_snapshot(
    *,
    members: Iterable[RawSourceMember],
    provenance: SourceSnapshotProvenance,
) -> SourceSnapshotOutcome:
    try:
        values = tuple(members)
    except (TypeError, ValueError):
        return _failed(SourceSnapshotFailureCode.INVALID_SNAPSHOT_INPUT)
    if not values or type(provenance) is not SourceSnapshotProvenance or any(
        type(value) is not RawSourceMember for value in values
    ):
        return _failed(SourceSnapshotFailureCode.INVALID_SNAPSHOT_INPUT)
    keys = tuple(value.member_key for value in values)
    if len(keys) != len(set(keys)):
        return _failed(SourceSnapshotFailureCode.DUPLICATE_MEMBER, min(keys))
    ordered = tuple(sorted(values, key=lambda value: value.member_key))
    missing = [value.member_key for value in ordered if value.raw_bytes is None]
    if missing:
        return _failed(SourceSnapshotFailureCode.ACQUISITION_FAILED, missing[0])
    mismatched = [
        value.member_key
        for value in ordered
        if value.declared_sha256 is not None
        and value.declared_sha256 != _digest(value.raw_bytes or b"")
    ]
    if mismatched:
        return _failed(
            SourceSnapshotFailureCode.DECLARED_SOURCE_HASH_MISMATCH, mismatched[0]
        )
    captured = tuple(
        (
            SourceSnapshotMember(
                value.member_key,
                _digest(value.raw_bytes or b""),
                len(value.raw_bytes or b""),
                value.mode,
                value.acquired_at_epoch_nanoseconds,
                value.declared_sha256,
            ),
            value.raw_bytes or b"",
        )
        for value in ordered
    )
    evidence = tuple(value for value, _ in captured)
    archive_bytes = _archive(captured)
    snapshot_id = _digest(archive_bytes)
    return SourceSnapshotOutcome(
        SourceSnapshot(
            snapshot_id=snapshot_id,
            archive_bytes=archive_bytes,
            content_tree_hash=_content_tree_hash(evidence),
            members=evidence,
            provenance=provenance,
            provenance_hash=_provenance_hash(snapshot_id, provenance, evidence),
            decision_grade_eligible=False,
            deployment_authorized=False,
        ),
        None,
    )


def verify_source_snapshot(snapshot: SourceSnapshot) -> SourceSnapshotOutcome:
    if type(snapshot) is not SourceSnapshot:
        return _failed(SourceSnapshotFailureCode.INVALID_SNAPSHOT_INPUT)
    try:
        with tarfile.open(fileobj=io.BytesIO(snapshot.archive_bytes), mode="r:gz") as archive:
            tar_members = archive.getmembers()
            if any(
                not member.isfile()
                or member.name != _member_key(member.name)
                or member.mode not in {0o644, 0o755}
                or member.mtime != 0
                or member.uid != 0
                or member.gid != 0
                or member.uname != ""
                or member.gname != ""
                for member in tar_members
            ):
                return _failed(SourceSnapshotFailureCode.ARCHIVE_INVALID)
            keys = tuple(member.name for member in tar_members)
            if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
                return _failed(SourceSnapshotFailureCode.ARCHIVE_INVALID)
            extracted: list[tuple[SourceSnapshotMember, bytes]] = []
            by_key = {member.member_key: member for member in snapshot.members}
            if keys != tuple(by_key):
                return _failed(SourceSnapshotFailureCode.CONTENT_TREE_HASH_MISMATCH)
            for member in tar_members:
                stream = archive.extractfile(member)
                if stream is None:
                    return _failed(SourceSnapshotFailureCode.ARCHIVE_INVALID)
                value = stream.read()
                evidence = by_key[member.name]
                if (
                    evidence.content_hash != _digest(value)
                    or evidence.byte_count != len(value)
                    or evidence.mode != f"{member.mode:04o}"
                ):
                    return _failed(SourceSnapshotFailureCode.CONTENT_TREE_HASH_MISMATCH)
                extracted.append((evidence, value))
    except (OSError, tarfile.TarError, ValueError):
        return _failed(SourceSnapshotFailureCode.ARCHIVE_INVALID)
    rebuilt = _archive(tuple(extracted))
    if rebuilt != snapshot.archive_bytes:
        return _failed(SourceSnapshotFailureCode.ARCHIVE_INVALID)
    if _digest(snapshot.archive_bytes) != snapshot.snapshot_id:
        return _failed(SourceSnapshotFailureCode.SNAPSHOT_ID_MISMATCH)
    if _content_tree_hash(snapshot.members) != snapshot.content_tree_hash:
        return _failed(SourceSnapshotFailureCode.CONTENT_TREE_HASH_MISMATCH)
    if (
        _provenance_hash(snapshot.snapshot_id, snapshot.provenance, snapshot.members)
        != snapshot.provenance_hash
    ):
        return _failed(SourceSnapshotFailureCode.PROVENANCE_HASH_MISMATCH)
    return SourceSnapshotOutcome(snapshot, None)
