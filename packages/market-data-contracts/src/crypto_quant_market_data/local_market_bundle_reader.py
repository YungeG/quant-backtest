from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Iterable
from pathlib import Path

from crypto_quant_domain import (
    InstrumentId,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)

from .bundles import (
    EventCursor,
    InMemoryMarketBundleReader,
    InputValidationFailure,
    MarketBundleCapability,
    MarketBundleError,
    MarketBundleIntegrityError,
    MarketBundleManifest,
    MarketBundleReader,
    MarketBundleRef,
    MarketEvent,
    MarketStreamManifest,
)


class _LocalReopenUnavailable(MarketBundleIntegrityError):
    _durable_reopen_kind_v1 = "unavailable"


class _LocalReopenTampered(MarketBundleIntegrityError):
    _durable_reopen_kind_v1 = "tampered"


_REPOSITORY_OPEN_PROVENANCE_V1 = object()
_REPOSITORY_OPEN_IDENTITY_CAPABILITY_V1 = object()

_HASH_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_POLICY_RE = re.compile(r"[a-z][a-z0-9._-]*\Z")
_MANIFEST_KEYS = {
    "type",
    "bundle_key",
    "schema_version",
    "coverage_start",
    "coverage_end_exclusive",
    "instrument_catalog_hash",
    "capabilities",
    "streams",
    "content_hash",
}
_PUBLICATION_KEYS = {
    "type",
    "schema_version",
    "bundle_ref",
    "manifest_relative_path",
    "stream_relative_paths",
    "stream_payload_hashes",
    "retention_proof_relative_path",
    "retention_proof_hash",
    "retention_policy_ref",
    "publication_hash",
}
_RETENTION_KEYS = {
    "type",
    "schema_version",
    "bundle_ref",
    "retention_policy_ref",
    "manifest_relative_path",
    "manifest_source_hash",
    "stream_relative_paths",
    "stream_payload_hashes",
    "publication_relative_path",
    "proof_hash",
}


def _malformed(name: str) -> MarketBundleIntegrityError:
    return MarketBundleIntegrityError(f"{name} is malformed")


def _mapping(
    name: str,
    value: object,
    *,
    keys: set[str] | None = None,
    type_name: str | None = None,
) -> dict[str, object]:
    if type(value) is not dict:
        raise _malformed(name)
    if keys is not None and set(value) != keys:
        raise _malformed(name)
    if type_name is not None and value.get("type") != type_name:
        raise _malformed(name)
    return value


def _sequence(name: str, value: object) -> list[object]:
    if type(value) is not list:
        raise _malformed(name)
    return value


def _integer(name: str, value: object) -> int:
    if type(value) is not int:
        raise _malformed(name)
    return value


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise _malformed(name)
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if _HASH_RE.fullmatch(text) is None:
        raise _malformed(name)
    return text


def _relative_path(name: str, value: object) -> str:
    text = _text(name, value)
    if "\\" in text or text.startswith("/"):
        raise _malformed(name)
    if any(part in {"", ".", ".."} for part in text.split("/")):
        raise _malformed(name)
    return text


def _path_component(name: str, value: str) -> str:
    if value in {".", ".."} or "/" in value or "\\" in value:
        raise _malformed(name)
    return value


def _string_sequence(name: str, value: object) -> tuple[str, ...]:
    return tuple(_text(f"{name}[{index}]", item) for index, item in enumerate(_sequence(name, value)))


def _hash_sequence(name: str, value: object) -> tuple[str, ...]:
    return tuple(_hash(f"{name}[{index}]", item) for index, item in enumerate(_sequence(name, value)))


def _read_bytes(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError:
        raise _LocalReopenUnavailable("required publication artifact is missing") from None


def _read_canonical_json(path: Path, name: str) -> tuple[bytes, object]:
    payload = _read_bytes(path)
    try:
        value = json.loads(payload)
        encoded = canonical_bytes(value)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        raise _malformed(name) from None
    if payload != encoded:
        raise _malformed(name)
    return payload, value


def _entry_mode(path: Path) -> int:
    try:
        return path.lstat().st_mode
    except OSError:
        raise _LocalReopenUnavailable("required publication artifact is missing") from None


def _assert_directory(path: Path, *, immutable: bool) -> None:
    mode = _entry_mode(path)
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise MarketBundleIntegrityError("required publication artifact is malformed")
    if immutable and mode & 0o222:
        raise MarketBundleIntegrityError("required publication artifact is not immutable")


def _assert_readonly_tree(path: Path, *, expected_names: set[str] | None = None) -> None:
    _assert_directory(path, immutable=True)
    try:
        entries = tuple(path.iterdir())
    except OSError:
        raise _LocalReopenUnavailable("required publication artifact is missing") from None

    if expected_names is not None:
        actual_names = {entry.name for entry in entries}
        if not expected_names.issubset(actual_names):
            raise _LocalReopenUnavailable("required publication artifact is missing")
        if actual_names != expected_names:
            raise MarketBundleIntegrityError("required publication artifact is malformed")

    for entry in entries:
        mode = _entry_mode(entry)
        if stat.S_ISLNK(mode):
            raise MarketBundleIntegrityError("required publication artifact is malformed")
        if mode & 0o222:
            raise MarketBundleIntegrityError("required publication artifact is not immutable")
        if stat.S_ISDIR(mode):
            _assert_readonly_tree(entry)
        elif not stat.S_ISREG(mode):
            raise MarketBundleIntegrityError("required publication artifact is malformed")


def _decode_capability(value: object) -> MarketBundleCapability:
    payload = _mapping(
        "capability",
        value,
        keys={"type", "key", "version"},
        type_name="market_bundle_capability",
    )
    try:
        return MarketBundleCapability(
            key=_text("capability key", payload["key"]),
            version=_integer("capability version", payload["version"]),
        )
    except (KeyError, TypeError, ValueError):
        raise _malformed("capability") from None


def _decode_instant(name: str, value: object) -> UtcInstant:
    payload = _mapping(
        name,
        value,
        keys={"type", "epoch_nanoseconds"},
        type_name="utc_instant",
    )
    try:
        return UtcInstant(_integer(name, payload["epoch_nanoseconds"]))
    except (KeyError, TypeError, ValueError):
        raise _malformed(name) from None


def _decode_phase(value: object) -> TimelinePhase:
    payload = _mapping(
        "event phase",
        value,
        keys={"type", "rank", "code"},
        type_name="timeline_phase",
    )
    try:
        return TimelinePhase(
            rank=_integer("phase rank", payload["rank"]),
            code=_text("phase code", payload["code"]),
        )
    except (KeyError, TypeError, ValueError):
        raise _malformed("event phase") from None


def _decode_source_sequence(value: object) -> SourceSequence:
    payload = _mapping(
        "event source_sequence",
        value,
        keys={"type", "value"},
        type_name="source_sequence",
    )
    try:
        return SourceSequence(_integer("source sequence", payload["value"]))
    except (KeyError, TypeError, ValueError):
        raise _malformed("event source_sequence") from None


def _decode_instrument_id(value: object) -> InstrumentId | None:
    if value is None:
        return None
    payload = _mapping(
        "event instrument_id",
        value,
        keys={"type", "venue", "stable_key"},
        type_name="instrument_id",
    )
    try:
        return InstrumentId(
            venue=VenueId(_text("instrument venue", payload["venue"])),
            stable_key=_text("instrument stable_key", payload["stable_key"]),
        )
    except (KeyError, TypeError, ValueError):
        raise _malformed("event instrument_id") from None


def _decode_stream_manifest(value: object) -> MarketStreamManifest:
    payload = _mapping(
        "stream manifest",
        value,
        keys={"type", "stream_key", "event_type", "capability", "event_count", "content_hash"},
        type_name="market_stream_manifest",
    )
    try:
        return MarketStreamManifest(
            stream_key=_text("stream key", payload["stream_key"]),
            event_type=_text("event type", payload["event_type"]),
            capability=_decode_capability(payload["capability"]),
            event_count=_integer("event count", payload["event_count"]),
            content_hash=_hash("stream content hash", payload["content_hash"]),
        )
    except (KeyError, TypeError, ValueError):
        raise _malformed("stream manifest") from None


def _decode_bundle_manifest(value: object) -> MarketBundleManifest:
    payload = _mapping(
        "bundle manifest",
        value,
        keys=_MANIFEST_KEYS,
        type_name="market_bundle_manifest",
    )
    try:
        manifest = MarketBundleManifest(
            bundle_key=_text("bundle key", payload["bundle_key"]),
            schema_version=_integer("schema version", payload["schema_version"]),
            coverage_start=_decode_instant("coverage start", payload["coverage_start"]),
            coverage_end_exclusive=_decode_instant(
                "coverage end", payload["coverage_end_exclusive"]
            ),
            instrument_catalog_hash=_hash(
                "instrument catalog hash", payload["instrument_catalog_hash"]
            ),
            capabilities=tuple(
                _decode_capability(item)
                for item in _sequence("manifest capabilities", payload["capabilities"])
            ),
            streams=tuple(
                _decode_stream_manifest(item)
                for item in _sequence("manifest streams", payload["streams"])
            ),
            content_hash=_hash("manifest content hash", payload["content_hash"]),
        )
    except (KeyError, TypeError, ValueError):
        raise _malformed("bundle manifest") from None

    if canonical_bytes(manifest) != canonical_bytes(payload):
        raise _malformed("bundle manifest")
    return manifest


def _decode_event(value: object, *, stream: MarketStreamManifest) -> MarketEvent:
    payload = _mapping(
        "stream event",
        value,
        keys={
            "type",
            "event_id",
            "stream_key",
            "event_type",
            "capability",
            "instrument_id",
            "event_time",
            "available_time",
            "phase",
            "source_sequence",
            "revision_id",
            "supersedes_revision_id",
            "source_key",
            "source_hash",
            "payload",
        },
        type_name="market_event",
    )
    stream_key = _text("stream key", payload["stream_key"])
    event_type = _text("event type", payload["event_type"])
    if stream_key != stream.stream_key or event_type != stream.event_type:
        raise _malformed("stream event")
    event_payload = _mapping("event payload", payload["payload"])
    supersedes = payload["supersedes_revision_id"]

    try:
        return MarketEvent(
            event_id=_text("event id", payload["event_id"]),
            stream_key=stream_key,
            event_type=event_type,
            capability=_decode_capability(payload["capability"]),
            instrument_id=_decode_instrument_id(payload["instrument_id"]),
            event_time=_decode_instant("event time", payload["event_time"]),
            available_time=_decode_instant("available time", payload["available_time"]),
            phase=_decode_phase(payload["phase"]),
            source_sequence=_decode_source_sequence(payload["source_sequence"]),
            revision_id=_text("revision id", payload["revision_id"]),
            supersedes_revision_id=(
                None if supersedes is None else _text("supersedes revision id", supersedes)
            ),
            source_key=_text("source key", payload["source_key"]),
            source_hash=_hash("source hash", payload["source_hash"]),
            payload=event_payload,
        )
    except (KeyError, TypeError, ValueError):
        raise _malformed("stream event") from None


def _content_hash(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _bundle_directory(repository_root: Path, bundle_ref: MarketBundleRef) -> Path:
    return (
        repository_root
        / "bundles"
        / _path_component("bundle key", bundle_ref.bundle_key)
        / bundle_ref.manifest_hash.removeprefix("sha256:")
    )


class LocalMarketBundleReader:
    """Verified reader over immutable local bundles produced by G12D."""

    def __init__(self, delegate: InMemoryMarketBundleReader) -> None:
        self._delegate = delegate
        self._repository_open_provenance_v1: tuple[
            object,
            Path,
            MarketBundleRef,
            bytes,
            str,
            str,
            bytes,
            str,
            str,
        ] | None = None
        self._repository_open_identity_capability_v1: object | None = None

    @property
    def bundle_ref(self) -> MarketBundleRef:
        return self._delegate.bundle_ref

    @property
    def manifest(self) -> MarketBundleManifest:
        return self._delegate.manifest

    @classmethod
    def open(
        cls,
        *,
        repository_root: Path,
        bundle_ref: MarketBundleRef,
    ) -> LocalMarketBundleReader:
        if not isinstance(repository_root, Path):
            raise MarketBundleIntegrityError("repository_root must be a Path")
        if not repository_root.is_absolute():
            raise MarketBundleIntegrityError("repository_root must be absolute")
        if type(bundle_ref) is not MarketBundleRef:
            raise MarketBundleIntegrityError("bundle_ref is invalid")

        final_directory = _bundle_directory(repository_root, bundle_ref)
        _assert_directory(repository_root, immutable=False)
        _assert_directory(repository_root / "bundles", immutable=False)
        _assert_directory(repository_root / "bundles" / bundle_ref.bundle_key, immutable=False)
        _assert_readonly_tree(
            final_directory,
            expected_names={
                "manifest.json",
                "publication.json",
                "retention-proof.json",
                "streams",
            },
        )

        manifest_bytes, manifest_value = _read_canonical_json(
            final_directory / "manifest.json", "bundle manifest"
        )
        manifest = _decode_bundle_manifest(manifest_value)
        if canonical_sha256(manifest_value) != bundle_ref.manifest_hash:
            raise MarketBundleIntegrityError("manifest hash mismatch")
        if MarketBundleRef.from_manifest(manifest) != bundle_ref:
            raise MarketBundleIntegrityError("bundle reference does not match manifest")
        if canonical_bytes(manifest) != manifest_bytes:
            raise _malformed("bundle manifest")

        publication_bytes, publication_value = _read_canonical_json(
            final_directory / "publication.json", "publication payload"
        )
        publication = _mapping(
            "publication payload",
            publication_value,
            keys=_PUBLICATION_KEYS,
            type_name="market_bundle_publication",
        )
        if _integer("publication schema version", publication["schema_version"]) != 1:
            raise _malformed("publication payload")
        publication_hash = _hash("publication hash", publication["publication_hash"])
        if canonical_sha256(
            {key: value for key, value in publication.items() if key != "publication_hash"}
        ) != publication_hash:
            raise _malformed("publication payload")
        if publication["bundle_ref"] != bundle_ref.to_canonical_dict():
            raise MarketBundleIntegrityError("publication bundle identity is invalid")

        relative_root = (
            f"bundles/{bundle_ref.bundle_key}/"
            f"{bundle_ref.manifest_hash.removeprefix('sha256:')}"
        )
        expected_stream_paths = tuple(
            f"{relative_root}/streams/{index:03d}.payload"
            for index in range(len(manifest.streams))
        )
        expected_stream_hashes = tuple(stream.content_hash for stream in manifest.streams)
        if _relative_path(
            "publication manifest path", publication["manifest_relative_path"]
        ) != f"{relative_root}/manifest.json":
            raise MarketBundleIntegrityError("publication manifest path is invalid")
        if _relative_path(
            "publication retention path", publication["retention_proof_relative_path"]
        ) != f"{relative_root}/retention-proof.json":
            raise MarketBundleIntegrityError("publication retention path is invalid")
        if _string_sequence(
            "publication stream paths", publication["stream_relative_paths"]
        ) != expected_stream_paths:
            raise MarketBundleIntegrityError("publication stream paths are invalid")
        if _hash_sequence(
            "publication stream hashes", publication["stream_payload_hashes"]
        ) != expected_stream_hashes:
            raise MarketBundleIntegrityError("publication stream hashes are invalid")
        retention_hash = _hash(
            "publication retention proof hash", publication["retention_proof_hash"]
        )
        retention_policy_ref = _text(
            "publication retention policy", publication["retention_policy_ref"]
        )
        if _POLICY_RE.fullmatch(retention_policy_ref) is None:
            raise _malformed("publication retention policy")

        retention_bytes, retention_value = _read_canonical_json(
            final_directory / "retention-proof.json", "retention proof"
        )
        retention = _mapping(
            "retention proof",
            retention_value,
            keys=_RETENTION_KEYS,
            type_name="market_bundle_retention_proof",
        )
        if _integer("retention schema version", retention["schema_version"]) != 1:
            raise _malformed("retention proof")
        proof_hash = _hash("retention proof hash", retention["proof_hash"])
        if proof_hash != retention_hash or canonical_sha256(
            {key: value for key, value in retention.items() if key != "proof_hash"}
        ) != proof_hash:
            raise _malformed("retention proof")
        if retention["bundle_ref"] != bundle_ref.to_canonical_dict():
            raise MarketBundleIntegrityError("retention proof identity is invalid")
        if _hash(
            "retention manifest hash", retention["manifest_source_hash"]
        ) != bundle_ref.manifest_hash:
            raise MarketBundleIntegrityError("retention proof manifest hash mismatch")
        if _text(
            "retention policy", retention["retention_policy_ref"]
        ) != retention_policy_ref:
            raise MarketBundleIntegrityError("retention policy linkage is invalid")
        if _relative_path(
            "retention manifest path", retention["manifest_relative_path"]
        ) != f"{relative_root}/manifest.json":
            raise MarketBundleIntegrityError("retention proof manifest path mismatch")
        if _relative_path(
            "retention publication path", retention["publication_relative_path"]
        ) != f"{relative_root}/publication.json":
            raise MarketBundleIntegrityError("retention proof publication path mismatch")
        if _string_sequence(
            "retention stream paths", retention["stream_relative_paths"]
        ) != expected_stream_paths:
            raise MarketBundleIntegrityError("retention stream paths are invalid")
        if _hash_sequence(
            "retention stream hashes", retention["stream_payload_hashes"]
        ) != expected_stream_hashes:
            raise MarketBundleIntegrityError("retention stream hashes are invalid")

        stream_directory = final_directory / "streams"
        _assert_readonly_tree(
            stream_directory,
            expected_names={f"{index:03d}.payload" for index in range(len(manifest.streams))},
        )

        stream_events: dict[str, tuple[MarketEvent, ...]] = {}
        for index, stream in enumerate(manifest.streams):
            stream_payload_bytes = _read_bytes(stream_directory / f"{index:03d}.payload")
            if _content_hash(stream_payload_bytes) != stream.content_hash:
                raise MarketBundleIntegrityError("stream payload hash is invalid")
            try:
                stream_values = json.loads(stream_payload_bytes)
                if type(stream_values) is not list:
                    raise _malformed("stream payload")
                if stream_payload_bytes != canonical_bytes(tuple(stream_values)):
                    raise _malformed("stream payload")
                events = tuple(_decode_event(value, stream=stream) for value in stream_values)
                if canonical_bytes(events) != stream_payload_bytes:
                    raise _malformed("stream payload")
            except MarketBundleIntegrityError:
                raise
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                raise _malformed("stream payload") from None
            stream_events[stream.stream_key] = events

        try:
            delegate = InMemoryMarketBundleReader(
                bundle_ref=bundle_ref,
                manifest=manifest,
                streams=stream_events,
            )
        except MarketBundleError:
            raise MarketBundleIntegrityError("published stream evidence is invalid") from None

        reader = cls(delegate)
        if cls is LocalMarketBundleReader:
            try:
                resolved_root = repository_root.resolve(strict=True)
            except OSError:
                raise _LocalReopenUnavailable(
                    "required publication artifact is missing"
                ) from None
            reader._repository_open_provenance_v1 = (
                _REPOSITORY_OPEN_PROVENANCE_V1,
                resolved_root,
                bundle_ref,
                publication_bytes,
                _content_hash(publication_bytes),
                publication_hash,
                retention_bytes,
                _content_hash(retention_bytes),
                proof_hash,
            )
            reader._repository_open_identity_capability_v1 = (
                _REPOSITORY_OPEN_IDENTITY_CAPABILITY_V1
            )
        return reader

    @staticmethod
    def validate_repository_open_reader_v1(
        reader: MarketBundleReader,
    ) -> LocalMarketBundleReader:
        """Validate an exact reader created by :meth:`open`."""
        if (
            type(reader) is not LocalMarketBundleReader
            or reader._repository_open_identity_capability_v1
            is not _REPOSITORY_OPEN_IDENTITY_CAPABILITY_V1
            or not reader._has_repository_open_provenance_v1()
        ):
            raise ValueError("reader must be an exact repository-open LocalMarketBundleReader")
        return reader

    def _has_repository_open_provenance_v1(self) -> bool:
        if type(self) is not LocalMarketBundleReader:
            return False
        provenance = self._repository_open_provenance_v1
        if type(provenance) is not tuple or len(provenance) != 9:
            return False
        (
            sentinel,
            root,
            ref,
            publication_bytes,
            publication_source_hash,
            publication_hash,
            retention_bytes,
            retention_source_hash,
            proof_hash,
        ) = provenance
        if sentinel is not _REPOSITORY_OPEN_PROVENANCE_V1:
            return False
        if not isinstance(root, Path) or not root.is_absolute():
            return False
        if any(part in {".", ".."} for part in root.parts):
            return False
        if type(ref) is not MarketBundleRef or type(publication_bytes) is not bytes:
            return False
        hashes = (
            publication_source_hash,
            publication_hash,
            retention_source_hash,
            proof_hash,
        )
        if type(retention_bytes) is not bytes or any(
            type(value) is not str or _HASH_RE.fullmatch(value) is None
            for value in hashes
        ):
            return False
        try:
            return self.bundle_ref == ref
        except (AttributeError, TypeError, ValueError):
            return False

    def _reopen_with_provenance_v1(
        self,
    ) -> tuple[
        LocalMarketBundleReader,
        bytes,
        str,
        str,
        bytes,
        str,
        str,
    ]:
        if not self._has_repository_open_provenance_v1():
            raise _LocalReopenTampered("repository-open provenance is invalid")
        original = self._repository_open_provenance_v1
        if type(original) is not tuple:
            raise _LocalReopenTampered("repository-open provenance is invalid")
        root = original[1]
        ref = original[2]
        if not isinstance(root, Path) or type(ref) is not MarketBundleRef:
            raise _LocalReopenTampered("repository-open provenance is invalid")

        try:
            reopened = LocalMarketBundleReader.open(
                repository_root=root,
                bundle_ref=ref,
            )
        except _LocalReopenUnavailable:
            raise
        except OSError:
            raise _LocalReopenUnavailable(
                "required publication artifact is missing"
            ) from None
        except MarketBundleIntegrityError:
            raise _LocalReopenTampered("repository-open evidence is invalid") from None

        if not reopened._has_repository_open_provenance_v1():
            raise _LocalReopenTampered("repository-open evidence is invalid")
        current = reopened._repository_open_provenance_v1
        if type(current) is not tuple or current[1:] != original[1:]:
            raise _LocalReopenTampered("repository-open evidence has changed")
        return (
            reopened,
            current[3],
            current[4],
            current[5],
            current[6],
            current[7],
            current[8],
        )

    def validate_requirements(
        self,
        *,
        required_capabilities: Iterable[MarketBundleCapability] = (),
        required_streams: Iterable[str] = (),
    ) -> InputValidationFailure | None:
        return self._delegate.validate_requirements(
            required_capabilities=required_capabilities,
            required_streams=required_streams,
        )

    def open_cursor(
        self, stream_key: str, *, batch_size: int
    ) -> EventCursor | InputValidationFailure:
        return self._delegate.open_cursor(stream_key, batch_size=batch_size)

    def read_batch(
        self, cursor: EventCursor
    ) -> tuple[tuple[MarketEvent, ...], EventCursor]:
        return self._delegate.read_batch(cursor)

    def resume_cursor(
        self,
        cursor: EventCursor,
        *,
        batch_size: int | None = None,
    ) -> EventCursor:
        return self._delegate.resume_cursor(cursor, batch_size=batch_size)


__all__ = ["LocalMarketBundleReader"]
