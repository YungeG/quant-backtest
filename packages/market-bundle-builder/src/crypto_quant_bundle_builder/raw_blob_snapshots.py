from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Protocol

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    RawBlobRef,
    canonical_bytes,
)

RAW_BLOB_SNAPSHOT_MANIFEST_ARTIFACT_TYPE = "raw_blob_snapshot_manifest"
RAW_BLOB_SNAPSHOT_SCHEMA_VERSION = 1
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SEGMENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*\Z")
_MANIFEST_FIELDS = frozenset(
    {
        "type",
        "schema_version",
        "snapshot_id",
        "members",
        "content_tree_hash",
        "provenance",
        "provenance_hash",
    }
)
_MEMBER_FIELDS = frozenset({"member_key", "raw_blob_ref", "mode"})


class RawBlobPathReader(Protocol):
    """Returns the verified local path for one published RawBlobRef."""

    def raw_blob_path(self, *, ref: RawBlobRef) -> Path: ...


def _digest(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be sha256:<64 lowercase hex>")
    return value


def _member_key(value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError("member_key must be canonical non-empty text")
    if value != unicodedata.normalize("NFC", value):
        raise ValueError("member_key must be NFC text")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as error:
        raise ValueError("member_key must be portable ASCII") from error
    parts = value.split("/")
    if (
        not 1 <= len(encoded) <= 100
        or value.startswith("/")
        or value.endswith("/")
        or "\\" in value
        or any(not part or not _SEGMENT.fullmatch(part) for part in parts)
    ):
        raise ValueError("member_key must be a safe portable relative path")
    return value


def _mode(value: object) -> str:
    if value not in {"0644", "0755"}:
        raise ValueError("mode must be 0644 or 0755")
    return value  # type: ignore[return-value]


def _freeze_json(value: object) -> object:
    if type(value) is dict:
        return MappingProxyType(
            {key: _freeze_json(item) for key, item in value.items()}
        )
    if type(value) is list:
        return tuple(_freeze_json(item) for item in value)
    return value


def _plain_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: _plain_json(item) for key, item in value.items()}
    if type(value) is tuple:
        return [_plain_json(item) for item in value]
    return value


def _frozen_object(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{name} must be a non-empty canonical object")
    try:
        decoded = json.loads(canonical_bytes(value).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} must be canonical JSON") from error
    if type(decoded) is not dict or canonical_bytes(decoded) != canonical_bytes(value):
        raise ValueError(f"{name} must be a canonical object")
    frozen = _freeze_json(decoded)
    if not isinstance(frozen, Mapping):  # pragma: no cover - decoded is an object
        raise TypeError(f"{name} must be a canonical object")
    return frozen


@dataclass(frozen=True, slots=True)
class RawBlobSnapshotSourceMember:
    member_key: str
    raw_bytes: bytes = field(repr=False)
    mode: str

    def __post_init__(self) -> None:
        _member_key(self.member_key)
        if type(self.raw_bytes) is not bytes:
            raise TypeError("raw_bytes must be bytes")
        _mode(self.mode)

    @property
    def raw_blob_ref(self) -> RawBlobRef:
        return RawBlobRef.from_bytes(self.raw_bytes)


@dataclass(frozen=True, slots=True)
class RawBlobSnapshotMember:
    member_key: str
    raw_blob_ref: RawBlobRef
    mode: str

    def __post_init__(self) -> None:
        _member_key(self.member_key)
        if type(self.raw_blob_ref) is not RawBlobRef:
            raise TypeError("raw_blob_ref must be a RawBlobRef")
        _mode(self.mode)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "member_key": self.member_key,
            "raw_blob_ref": self.raw_blob_ref.to_canonical_dict(),
            "mode": self.mode,
        }

    @classmethod
    def from_canonical_dict(cls, value: object) -> RawBlobSnapshotMember:
        if type(value) is not dict or set(value) != _MEMBER_FIELDS:
            raise ValueError("raw snapshot member must have exactly canonical fields")
        return cls(
            value["member_key"],
            RawBlobRef.from_canonical_dict(value["raw_blob_ref"]),
            value["mode"],
        )


def _content_tree_hash(members: tuple[RawBlobSnapshotMember, ...]) -> str:
    return _digest(
        canonical_bytes(
            {
                "type": "raw_blob_snapshot_content_tree",
                "schema_version": RAW_BLOB_SNAPSHOT_SCHEMA_VERSION,
                "members": [member.to_canonical_dict() for member in members],
            }
        )
    )


def _provenance_hash(snapshot_id: str, provenance: Mapping[str, object]) -> str:
    return _digest(
        canonical_bytes(
            {
                "type": "raw_blob_snapshot_provenance",
                "schema_version": RAW_BLOB_SNAPSHOT_SCHEMA_VERSION,
                "snapshot_id": snapshot_id,
                "provenance": provenance,
            }
        )
    )


@dataclass(frozen=True, slots=True)
class RawBlobSnapshotManifest:
    snapshot_id: str
    members: tuple[RawBlobSnapshotMember, ...]
    content_tree_hash: str
    provenance: Mapping[str, object]
    provenance_hash: str

    def __post_init__(self) -> None:
        _hash("snapshot_id", self.snapshot_id)
        if type(self.members) is not tuple or not self.members or any(
            type(member) is not RawBlobSnapshotMember for member in self.members
        ):
            raise TypeError(
                "members must be a non-empty tuple of RawBlobSnapshotMember"
            )
        keys = tuple(member.member_key for member in self.members)
        if keys != tuple(sorted(keys)):
            raise ValueError("members must be sorted by member_key")
        if len(keys) != len(set(keys)):
            raise ValueError("members must have unique member_key values")
        _hash("content_tree_hash", self.content_tree_hash)
        provenance = _frozen_object(self.provenance, "provenance")
        object.__setattr__(self, "provenance", provenance)
        _hash("provenance_hash", self.provenance_hash)
        expected_tree = _content_tree_hash(self.members)
        if self.content_tree_hash != expected_tree:
            raise ValueError("content_tree_hash does not match members")
        if self.snapshot_id != expected_tree:
            raise ValueError("snapshot_id does not match content tree")
        if self.provenance_hash != _provenance_hash(self.snapshot_id, provenance):
            raise ValueError("provenance_hash does not match provenance")

    @classmethod
    def create(
        cls,
        *,
        members: Iterable[RawBlobSnapshotSourceMember],
        provenance: Mapping[str, object],
    ) -> RawBlobSnapshotManifest:
        source_members = tuple(members)
        if not source_members or any(
            type(member) is not RawBlobSnapshotSourceMember for member in source_members
        ):
            raise TypeError(
                "members must be non-empty RawBlobSnapshotSourceMember values"
            )
        keys = tuple(member.member_key for member in source_members)
        if len(keys) != len(set(keys)):
            raise ValueError("members must have unique member_key values")
        frozen_provenance = _frozen_object(provenance, "provenance")
        frozen_members = tuple(
            RawBlobSnapshotMember(member.member_key, member.raw_blob_ref, member.mode)
            for member in sorted(source_members, key=lambda item: item.member_key)
        )
        content_tree_hash = _content_tree_hash(frozen_members)
        return cls(
            content_tree_hash,
            frozen_members,
            content_tree_hash,
            frozen_provenance,
            _provenance_hash(content_tree_hash, frozen_provenance),
        )

    @property
    def schema_version(self) -> int:
        return RAW_BLOB_SNAPSHOT_SCHEMA_VERSION

    @property
    def envelope(self) -> ArtifactEnvelope:
        return ArtifactEnvelope.create(
            RAW_BLOB_SNAPSHOT_MANIFEST_ARTIFACT_TYPE,
            RAW_BLOB_SNAPSHOT_SCHEMA_VERSION,
            self.to_canonical_dict(),
        )

    @property
    def artifact_ref(self) -> ArtifactRef:
        return ArtifactRef.from_envelope(self.envelope)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "raw_blob_snapshot_manifest",
            "schema_version": RAW_BLOB_SNAPSHOT_SCHEMA_VERSION,
            "snapshot_id": self.snapshot_id,
            "members": [member.to_canonical_dict() for member in self.members],
            "content_tree_hash": self.content_tree_hash,
            "provenance": _plain_json(self.provenance),
            "provenance_hash": self.provenance_hash,
        }

    @classmethod
    def from_canonical_dict(cls, value: object) -> RawBlobSnapshotManifest:
        if type(value) is not dict or set(value) != _MANIFEST_FIELDS:
            raise ValueError(
                "raw blob snapshot manifest must have exactly canonical fields"
            )
        if (
            value["type"] != "raw_blob_snapshot_manifest"
            or type(value["schema_version"]) is not int
            or value["schema_version"] != RAW_BLOB_SNAPSHOT_SCHEMA_VERSION
            or type(value["members"]) is not list
            or type(value["provenance"]) is not dict
        ):
            raise ValueError("raw blob snapshot manifest has the wrong schema")
        return cls(
            value["snapshot_id"],
            tuple(
                RawBlobSnapshotMember.from_canonical_dict(item)
                for item in value["members"]
            ),
            value["content_tree_hash"],
            value["provenance"],
            value["provenance_hash"],
        )

    @classmethod
    def from_envelope(cls, envelope: ArtifactEnvelope) -> RawBlobSnapshotManifest:
        if type(envelope) is not ArtifactEnvelope:
            raise TypeError("envelope must be an ArtifactEnvelope")
        if (
            envelope.artifact_type != RAW_BLOB_SNAPSHOT_MANIFEST_ARTIFACT_TYPE
            or type(envelope.schema_version) is not int
            or envelope.schema_version != RAW_BLOB_SNAPSHOT_SCHEMA_VERSION
        ):
            raise ValueError("envelope is not a raw blob snapshot manifest@1")
        try:
            payload = json.loads(canonical_bytes(envelope.payload).decode("utf-8"))
        except (
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise ValueError("manifest envelope payload is not canonical") from error
        manifest = cls.from_canonical_dict(payload)
        if manifest.envelope != envelope:
            raise ValueError("manifest envelope does not match canonical manifest")
        return manifest


def create_raw_blob_snapshot_manifest(
    *,
    members: Iterable[RawBlobSnapshotSourceMember],
    provenance: Mapping[str, object],
) -> RawBlobSnapshotManifest:
    return RawBlobSnapshotManifest.create(members=members, provenance=provenance)


def _read_verified(path: Path, ref: RawBlobRef) -> bytes:
    if not isinstance(path, Path) or not hasattr(os, "O_NOFOLLOW"):
        raise ValueError("raw blob snapshot member unavailable")
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as error:
        raise ValueError("raw blob snapshot member unavailable") from error
    try:
        with os.fdopen(descriptor, "rb") as file:
            before = os.fstat(file.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("raw blob snapshot member unavailable")
            source = file.read()
            after = os.fstat(file.fileno())
    except OSError as error:
        raise ValueError("raw blob snapshot member unavailable") from error
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or len(source) != ref.byte_count
        or _digest(source) != ref.content_hash
    ):
        raise ValueError("raw blob snapshot member unavailable")
    return source


@dataclass(frozen=True, slots=True)
class RawBlobSnapshotView:
    manifest: RawBlobSnapshotManifest
    _reader: RawBlobPathReader = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if type(self.manifest) is not RawBlobSnapshotManifest:
            raise TypeError("manifest must be a RawBlobSnapshotManifest")
        if not callable(getattr(self._reader, "raw_blob_path", None)):
            raise TypeError("reader must expose raw_blob_path(ref=RawBlobRef)")
        for member in self.manifest.members:
            self._path_and_bytes(member)

    @classmethod
    def open(
        cls, manifest: RawBlobSnapshotManifest, reader: RawBlobPathReader
    ) -> RawBlobSnapshotView:
        return cls(manifest, reader)

    def _member(self, member_key: str) -> RawBlobSnapshotMember:
        key = _member_key(member_key)
        for member in self.manifest.members:
            if member.member_key == key:
                return member
        raise ValueError("raw blob snapshot member unavailable")

    def _path_and_bytes(self, member: RawBlobSnapshotMember) -> tuple[Path, bytes]:
        try:
            path = self._reader.raw_blob_path(ref=member.raw_blob_ref)
        except Exception as error:
            raise ValueError("raw blob snapshot member unavailable") from error
        if not isinstance(path, Path):
            raise TypeError("raw blob snapshot member unavailable")
        return path, _read_verified(path, member.raw_blob_ref)

    def member_path(self, member_key: str) -> Path:
        path, _ = self._path_and_bytes(self._member(member_key))
        return path

    def member_bytes(self, member_key: str) -> bytes:
        _, source = self._path_and_bytes(self._member(member_key))
        return source
