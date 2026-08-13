from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PurePosixPath

from crypto_quant_domain import canonical_bytes, canonical_sha256
from crypto_quant_market_data import MarketBundleManifest, MarketBundleRef


_SCHEMA_VERSION = 1
_HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RETENTION_POLICY_REF = re.compile(r"[a-z][a-z0-9._-]*\Z")


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical text")
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if _HASH_PATTERN.fullmatch(text) is None:
        raise ValueError(f"{name} must be canonical sha256 digest")
    return text


def _relative_path(name: str, value: object) -> str:
    text = _text(name, value)
    if "\\" in text:
        raise ValueError(f"{name} must be POSIX path")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"{name} must be canonical relative path")
    canonical = path.as_posix()
    if text != canonical:
        raise ValueError(f"{name} must be canonical relative path")
    return canonical


def _relative_subject(root: Path, value: Path) -> str:
    return _relative_path(
        "relative_subject", PurePosixPath(value.relative_to(root)).as_posix()
    )


def _content_hash(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _canonical_json_bytes(value: object) -> bytes:
    return canonical_bytes(value)


def _write_file(path: Path, source_bytes: bytes) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("xb") as file:
        file.write(source_bytes)
        file.flush()
        os.fsync(file.fileno())
    temporary.replace(path)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _is_symlink(path: Path) -> bool:
    try:
        return stat.S_ISLNK(path.lstat().st_mode)
    except OSError:
        return False


def _is_directory(path: Path) -> bool:
    try:
        return stat.S_ISDIR(path.lstat().st_mode)
    except OSError:
        return False


def _walk_paths(root: Path) -> tuple[Path, ...]:
    entries: list[Path] = []
    for child in sorted(root.iterdir()):
        if _is_directory(child):
            entries.extend(_walk_paths(child))
            entries.append(child)
        else:
            entries.append(child)
    return tuple(entries)


def _make_read_only_tree(root: Path) -> None:
    for path in _walk_paths(root):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("unsupported publication entry")
        if stat.S_ISDIR(mode):
            os.chmod(path, 0o555, follow_symlinks=False)
        elif stat.S_ISREG(mode):
            os.chmod(path, 0o444, follow_symlinks=False)
        else:
            raise ValueError("unsupported publication entry")

    mode = root.lstat().st_mode
    if stat.S_ISLNK(mode):
        raise ValueError("unsupported publication entry")
    os.chmod(root, 0o555, follow_symlinks=False)


def _verify_read_only_tree(root: Path) -> None:
    mode = root.lstat().st_mode
    if stat.S_ISLNK(mode):
        raise ValueError("symlinks are unsupported in publication")
    if mode & 0o222:
        raise ValueError("publication path is writable")

    for path in _walk_paths(root):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError("symlinks are unsupported in publication")
        if stat.S_ISDIR(mode) or stat.S_ISREG(mode):
            if mode & 0o222:
                raise ValueError("publication path is writable")
            continue
        raise ValueError("unsupported publication entry")


def _force_remove(path: Path) -> bool:
    if not os.path.lexists(path):
        return True

    try:
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            path.unlink()
            return True

        if stat.S_ISDIR(mode):
            os.chmod(path, 0o755, follow_symlinks=False)
            for child in sorted(path.iterdir(), reverse=True):
                if not _force_remove(child):
                    return False
            path.rmdir()
            return True

        os.chmod(path, 0o644, follow_symlinks=False)
        path.unlink()
        return True
    except OSError:
        return False


def _hide_and_remove(path: Path) -> bool:
    if not os.path.lexists(path):
        return True

    hidden = path.with_name(f".{path.name}.rollback")
    if os.path.lexists(hidden) and not _force_remove(hidden):
        return False
    try:
        os.replace(path, hidden)
    except OSError:
        return False
    return _force_remove(hidden) and not os.path.lexists(path)


class MarketBundlePublicationFailureCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    STREAM_PAYLOAD_MISMATCH = "stream_payload_mismatch"
    LOCK_UNAVAILABLE = "lock_unavailable"
    FINAL_DESTINATION_CONFLICT = "final_destination_conflict"
    STAGING_PREPARE_FAILED = "staging_prepare_failed"
    STAGING_WRITE_FAILED = "staging_write_failed"
    STAGING_VERIFICATION_FAILED = "staging_verification_failed"
    IMMUTABILITY_FAILED = "immutability_failed"
    ATOMIC_FINALIZE_FAILED = "atomic_finalize_failed"
    UNMANAGED_PUBLICATION_STATE = "unmanaged_publication_state"


@dataclass(frozen=True, slots=True)
class LocalMarketBundleRepositoryConfig:
    root: Path

    def __post_init__(self) -> None:
        if not isinstance(self.root, Path):
            raise TypeError("root must be pathlib.Path")
        if not self.root.is_absolute():
            raise ValueError("root must be an absolute Path")


@dataclass(frozen=True, slots=True)
class MarketBundleRepositoryPath:
    bundle_ref: MarketBundleRef
    final_directory_relative_path: str
    manifest_relative_path: str
    stream_relative_paths: tuple[str, ...]
    publication_relative_path: str
    retention_proof_relative_path: str

    def __post_init__(self) -> None:
        if type(self.bundle_ref) is not MarketBundleRef:
            raise TypeError("bundle_ref must be MarketBundleRef")
        _relative_path("final_directory_relative_path", self.final_directory_relative_path)
        _relative_path("manifest_relative_path", self.manifest_relative_path)
        _relative_path("publication_relative_path", self.publication_relative_path)
        _relative_path("retention_proof_relative_path", self.retention_proof_relative_path)
        if type(self.stream_relative_paths) is not tuple or any(
            type(value) is not str for value in self.stream_relative_paths
        ):
            raise TypeError("stream_relative_paths must be tuple[str, ...]")
        normalized = tuple(
            _relative_path(f"stream_relative_paths[{index}]", value)
            for index, value in enumerate(self.stream_relative_paths)
        )
        if normalized != self.stream_relative_paths:
            object.__setattr__(self, "stream_relative_paths", normalized)


@dataclass(frozen=True, slots=True)
class LocalMarketBundleRetentionProof:
    bundle_ref: MarketBundleRef
    retention_policy_ref: str
    manifest_relative_path: str
    manifest_source_hash: str
    stream_relative_paths: tuple[str, ...]
    stream_payload_hashes: tuple[str, ...]
    publication_relative_path: str

    def __post_init__(self) -> None:
        if type(self.bundle_ref) is not MarketBundleRef:
            raise TypeError("bundle_ref must be MarketBundleRef")
        if (
            re.fullmatch(_RETENTION_POLICY_REF, _text("retention_policy_ref", self.retention_policy_ref))
            is None
        ):
            raise ValueError("retention_policy_ref must be canonical reference")
        _hash("manifest_source_hash", self.manifest_source_hash)
        _relative_path("manifest_relative_path", self.manifest_relative_path)
        _relative_path("publication_relative_path", self.publication_relative_path)
        if (
            type(self.stream_relative_paths) is not tuple
            or type(self.stream_payload_hashes) is not tuple
            or len(self.stream_relative_paths) != len(self.stream_payload_hashes)
            or any(type(path) is not str for path in self.stream_relative_paths)
            or any(type(value) is not str for value in self.stream_payload_hashes)
        ):
            raise TypeError("stream evidence must be aligned tuple data")
        normalized_paths = tuple(
            _relative_path(f"stream_relative_paths[{index}]", value)
            for index, value in enumerate(self.stream_relative_paths)
        )
        if normalized_paths != self.stream_relative_paths:
            object.__setattr__(self, "stream_relative_paths", normalized_paths)
        for index, value in enumerate(self.stream_payload_hashes):
            _hash(f"stream_payload_hashes[{index}]", value)

    @property
    def proof_body(self) -> dict[str, object]:
        return {
            "type": "market_bundle_retention_proof",
            "schema_version": _SCHEMA_VERSION,
            "bundle_ref": self.bundle_ref.to_canonical_dict(),
            "retention_policy_ref": self.retention_policy_ref,
            "manifest_relative_path": self.manifest_relative_path,
            "manifest_source_hash": self.manifest_source_hash,
            "stream_relative_paths": self.stream_relative_paths,
            "stream_payload_hashes": self.stream_payload_hashes,
            "publication_relative_path": self.publication_relative_path,
        }

    @property
    def proof_hash(self) -> str:
        return canonical_sha256(self.proof_body)

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self.proof_body, "proof_hash": self.proof_hash}


@dataclass(frozen=True, slots=True)
class MarketBundlePublicationFailure:
    code: MarketBundlePublicationFailureCode
    bundle_ref: MarketBundleRef | None
    relative_subject: str

    def __post_init__(self) -> None:
        if type(self.code) is not MarketBundlePublicationFailureCode:
            raise TypeError("code must be MarketBundlePublicationFailureCode")
        if self.bundle_ref is not None and type(self.bundle_ref) is not MarketBundleRef:
            raise TypeError("bundle_ref must be MarketBundleRef")
        _relative_path("relative_subject", self.relative_subject)


@dataclass(frozen=True, slots=True)
class MarketBundlePublicationResult:
    bundle_ref: MarketBundleRef
    repository_path: MarketBundleRepositoryPath
    retention_proof: LocalMarketBundleRetentionProof
    already_published: bool

    def __post_init__(self) -> None:
        if type(self.bundle_ref) is not MarketBundleRef:
            raise TypeError("bundle_ref must be MarketBundleRef")
        if type(self.repository_path) is not MarketBundleRepositoryPath:
            raise TypeError("repository_path must be MarketBundleRepositoryPath")
        if type(self.retention_proof) is not LocalMarketBundleRetentionProof:
            raise TypeError("retention_proof must be LocalMarketBundleRetentionProof")
        if type(self.already_published) is not bool:
            raise TypeError("already_published must be bool")
        if self.bundle_ref != self.repository_path.bundle_ref:
            raise ValueError("repository_path bundle_ref mismatch")
        if self.bundle_ref != self.retention_proof.bundle_ref:
            raise ValueError("retention_proof bundle_ref mismatch")


@dataclass(frozen=True, slots=True)
class MarketBundlePublicationOutcome:
    result: MarketBundlePublicationResult | None
    failure: MarketBundlePublicationFailure | None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one branch")
        if self.result is not None and type(self.result) is not MarketBundlePublicationResult:
            raise TypeError("result must be MarketBundlePublicationResult")
        if self.failure is not None and type(self.failure) is not MarketBundlePublicationFailure:
            raise TypeError("failure must be MarketBundlePublicationFailure")


class _ManifestLock:
    def __init__(self, root: Path, relative_path: Path) -> None:
        self._path = root / relative_path
        self._descriptor: int | None = None

    def __enter__(self) -> "_ManifestLock":
        self._path.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(self._path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
        try:
            os.write(descriptor, b"local_market_bundle_repository_lock\n")
            os.fsync(descriptor)
        except OSError:
            os.close(descriptor)
            with contextlib.suppress(OSError):
                self._path.unlink()
            raise
        self._descriptor = descriptor
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:  # noqa: ANN001, ANN201
        if self._descriptor is not None:
            os.close(self._descriptor)
            self._descriptor = None
        with contextlib.suppress(OSError):
            self._path.unlink()


class LocalMarketBundleRepository:
    def __init__(self, *, config: LocalMarketBundleRepositoryConfig) -> None:
        if type(config) is not LocalMarketBundleRepositoryConfig:
            raise TypeError("config must be LocalMarketBundleRepositoryConfig")
        self._config = config

    def _failure(
        self,
        bundle_ref: MarketBundleRef | None,
        code: MarketBundlePublicationFailureCode,
        relative_subject: str,
    ) -> MarketBundlePublicationOutcome:
        return MarketBundlePublicationOutcome(
            result=None,
            failure=MarketBundlePublicationFailure(
                code=code,
                bundle_ref=bundle_ref,
                relative_subject=relative_subject,
            ),
        )

    def publish_market_bundle_v1(
        self,
        *,
        manifest: MarketBundleManifest,
        stream_payloads: Mapping[str, bytes],
        retention_policy_ref: str,
    ) -> MarketBundlePublicationOutcome:
        if type(manifest) is not MarketBundleManifest:
            return self._failure(
                None,
                MarketBundlePublicationFailureCode.INVALID_INPUT,
                "manifest",
            )

        try:
            canonical_manifest = MarketBundleManifest.build(
                bundle_key=manifest.bundle_key,
                schema_version=manifest.schema_version,
                coverage_start=manifest.coverage_start,
                coverage_end_exclusive=manifest.coverage_end_exclusive,
                instrument_catalog_hash=manifest.instrument_catalog_hash,
                capabilities=manifest.capabilities,
                streams=manifest.streams,
            )
            if manifest != canonical_manifest:
                return self._failure(
                    None,
                    MarketBundlePublicationFailureCode.INVALID_INPUT,
                    "manifest",
                )
        except (AttributeError, TypeError, ValueError):
            return self._failure(
                None,
                MarketBundlePublicationFailureCode.INVALID_INPUT,
                "manifest",
            )

        bundle_ref = MarketBundleRef.from_manifest(manifest)

        try:
            if re.fullmatch(_RETENTION_POLICY_REF, _text("retention_policy_ref", retention_policy_ref)) is None:
                return self._failure(
                    bundle_ref,
                    MarketBundlePublicationFailureCode.INVALID_INPUT,
                    "retention_policy_ref",
                )
            if type(stream_payloads) is not dict:
                raise TypeError("stream_payloads must be an exact dict")

            expected_keys = tuple(stream.stream_key for stream in manifest.streams)
            provided_keys = tuple(stream_payloads.keys())
            if set(provided_keys) != set(expected_keys):
                return self._failure(
                    bundle_ref,
                    MarketBundlePublicationFailureCode.STREAM_PAYLOAD_MISMATCH,
                    "streams",
                )

            stream_file_names = tuple(
                f"streams/{index:03d}.payload" for index in range(len(manifest.streams))
            )
            stream_payload_values: list[bytes] = []
            stream_payload_hashes: list[str] = []
            for stream in manifest.streams:
                payload = stream_payloads[stream.stream_key]
                if type(payload) is not bytes:
                    return self._failure(
                        bundle_ref,
                        MarketBundlePublicationFailureCode.STREAM_PAYLOAD_MISMATCH,
                        "streams",
                    )
                digest = _content_hash(payload)
                if digest != stream.content_hash:
                    return self._failure(
                        bundle_ref,
                        MarketBundlePublicationFailureCode.STREAM_PAYLOAD_MISMATCH,
                        "streams",
                    )
                stream_payload_values.append(payload)
                stream_payload_hashes.append(digest)
        except (KeyError, TypeError, ValueError):
            return self._failure(
                bundle_ref,
                MarketBundlePublicationFailureCode.STREAM_PAYLOAD_MISMATCH,
                "streams",
            )

        manifest_directory = (
            f"bundles/{bundle_ref.bundle_key}/{bundle_ref.manifest_hash.removeprefix('sha256:')}"
        )
        manifest_relative_path = f"{manifest_directory}/manifest.json"
        publication_relative_path = f"{manifest_directory}/publication.json"
        retention_proof_relative_path = f"{manifest_directory}/retention-proof.json"
        stream_relative_paths = tuple(
            f"{manifest_directory}/{filename}" for filename in stream_file_names
        )

        manifest_source_hash = canonical_sha256(manifest.to_canonical_dict())
        retention_proof = LocalMarketBundleRetentionProof(
            bundle_ref=bundle_ref,
            retention_policy_ref=retention_policy_ref,
            manifest_relative_path=manifest_relative_path,
            manifest_source_hash=manifest_source_hash,
            stream_relative_paths=stream_relative_paths,
            stream_payload_hashes=tuple(stream_payload_hashes),
            publication_relative_path=publication_relative_path,
        )

        publication_body = {
            "type": "market_bundle_publication",
            "schema_version": _SCHEMA_VERSION,
            "bundle_ref": bundle_ref.to_canonical_dict(),
            "manifest_relative_path": manifest_relative_path,
            "stream_relative_paths": tuple(stream_relative_paths),
            "stream_payload_hashes": tuple(stream_payload_hashes),
            "retention_proof_relative_path": retention_proof_relative_path,
            "retention_proof_hash": retention_proof.proof_hash,
            "retention_policy_ref": retention_policy_ref,
        }
        publication_hash = canonical_sha256(publication_body)
        publication_payload = _canonical_json_bytes(
            {**publication_body, "publication_hash": publication_hash}
        )

        manifest_payload = _canonical_json_bytes(manifest.to_canonical_dict())
        retention_payload = _canonical_json_bytes(retention_proof.to_canonical_dict())

        repository_path = MarketBundleRepositoryPath(
            bundle_ref=bundle_ref,
            final_directory_relative_path=manifest_directory,
            manifest_relative_path=manifest_relative_path,
            stream_relative_paths=stream_relative_paths,
            publication_relative_path=publication_relative_path,
            retention_proof_relative_path=retention_proof_relative_path,
        )

        final_path = self._config.root / manifest_directory
        staging_path = (
            self._config.root
            / ".staging"
            / bundle_ref.bundle_key
            / bundle_ref.manifest_hash.removeprefix("sha256:")
        )
        lock_path = (
            Path(".locks")
            / bundle_ref.bundle_key
            / f"{bundle_ref.manifest_hash.removeprefix('sha256:')}.lock"
        )

        try:
            with _ManifestLock(self._config.root, lock_path):
                if os.path.lexists(final_path):
                    if self._verify_final(
                        final_path,
                        manifest_source_hash=manifest_source_hash,
                        stream_relative_paths=stream_relative_paths,
                        stream_payload_values=tuple(stream_payload_values),
                        stream_payload_hashes=tuple(stream_payload_hashes),
                        publication_payload=publication_payload,
                        retention_payload=retention_payload,
                        retention_proof=retention_proof,
                    ):
                        return MarketBundlePublicationOutcome(
                            result=MarketBundlePublicationResult(
                                bundle_ref=bundle_ref,
                                repository_path=repository_path,
                                retention_proof=retention_proof,
                                already_published=True,
                            ),
                            failure=None,
                        )
                    return self._failure(
                        bundle_ref,
                        MarketBundlePublicationFailureCode.FINAL_DESTINATION_CONFLICT,
                        repository_path.final_directory_relative_path,
                    )

                if os.path.lexists(staging_path):
                    return self._failure(
                        bundle_ref,
                        MarketBundlePublicationFailureCode.STAGING_PREPARE_FAILED,
                        _relative_subject(self._config.root, staging_path),
                    )

                try:
                    final_path.parent.mkdir(parents=True, exist_ok=True)
                    _fsync_directory(final_path.parent.parent)
                    staging_path.mkdir(parents=True, exist_ok=False)
                    (staging_path / "streams").mkdir()
                    for filename, payload in zip(
                        stream_file_names, stream_payload_values
                    ):
                        _write_file(staging_path / filename, payload)
                    _fsync_directory(staging_path / "streams")
                    _write_file(staging_path / "manifest.json", manifest_payload)
                    _write_file(staging_path / "publication.json", publication_payload)
                    _write_file(
                        staging_path / "retention-proof.json", retention_payload
                    )
                    _fsync_directory(staging_path)
                except OSError:
                    if not _force_remove(staging_path):
                        return self._failure(
                            bundle_ref,
                            MarketBundlePublicationFailureCode.UNMANAGED_PUBLICATION_STATE,
                            _relative_subject(self._config.root, staging_path),
                        )
                    return self._failure(
                        bundle_ref,
                        MarketBundlePublicationFailureCode.STAGING_WRITE_FAILED,
                        _relative_subject(self._config.root, staging_path),
                    )

                try:
                    self._verify_staging(
                        staging_path,
                        manifest_source_hash=manifest_source_hash,
                        stream_file_names=stream_file_names,
                        stream_payload_values=tuple(stream_payload_values),
                        stream_payload_hashes=tuple(stream_payload_hashes),
                        publication_payload=publication_payload,
                        retention_payload=retention_payload,
                    )
                except (OSError, ValueError, json.JSONDecodeError):
                    if not _force_remove(staging_path):
                        return self._failure(
                            bundle_ref,
                            MarketBundlePublicationFailureCode.UNMANAGED_PUBLICATION_STATE,
                            _relative_subject(self._config.root, staging_path),
                        )
                    return self._failure(
                        bundle_ref,
                        MarketBundlePublicationFailureCode.STAGING_VERIFICATION_FAILED,
                        _relative_subject(self._config.root, staging_path),
                    )

                try:
                    _make_read_only_tree(staging_path)
                    _verify_read_only_tree(staging_path)
                    _fsync_directory(staging_path)
                except ValueError:
                    if not _force_remove(staging_path):
                        return self._failure(
                            bundle_ref,
                            MarketBundlePublicationFailureCode.UNMANAGED_PUBLICATION_STATE,
                            _relative_subject(self._config.root, staging_path),
                        )
                    return self._failure(
                        bundle_ref,
                        MarketBundlePublicationFailureCode.IMMUTABILITY_FAILED,
                        _relative_subject(self._config.root, staging_path),
                    )
                except OSError:
                    if not _force_remove(staging_path):
                        return self._failure(
                            bundle_ref,
                            MarketBundlePublicationFailureCode.UNMANAGED_PUBLICATION_STATE,
                            _relative_subject(self._config.root, staging_path),
                        )
                    return self._failure(
                        bundle_ref,
                        MarketBundlePublicationFailureCode.IMMUTABILITY_FAILED,
                        _relative_subject(self._config.root, staging_path),
                    )

                try:
                    # This host denies renaming a non-writable directory even when both
                    # parents are writable. Payload files remain read-only throughout;
                    # restore the directory mode immediately after atomic rename.
                    staging_path.chmod(0o755)
                    staging_path.rename(final_path)
                    final_path.chmod(0o555)
                except OSError:
                    if not _force_remove(staging_path):
                        return self._failure(
                            bundle_ref,
                            MarketBundlePublicationFailureCode.UNMANAGED_PUBLICATION_STATE,
                            _relative_subject(self._config.root, final_path),
                        )
                    if not _hide_and_remove(final_path):
                        return self._failure(
                            bundle_ref,
                            MarketBundlePublicationFailureCode.UNMANAGED_PUBLICATION_STATE,
                            _relative_subject(self._config.root, final_path),
                        )
                    return self._failure(
                        bundle_ref,
                        MarketBundlePublicationFailureCode.ATOMIC_FINALIZE_FAILED,
                        _relative_subject(self._config.root, final_path),
                    )

                try:
                    _fsync_directory(final_path.parent)
                    if not self._verify_final(
                        final_path,
                        manifest_source_hash=manifest_source_hash,
                        stream_relative_paths=stream_relative_paths,
                        stream_payload_values=tuple(stream_payload_values),
                        stream_payload_hashes=tuple(stream_payload_hashes),
                        publication_payload=publication_payload,
                        retention_payload=retention_payload,
                        retention_proof=retention_proof,
                    ):
                        if not _hide_and_remove(final_path):
                            return self._failure(
                                bundle_ref,
                                MarketBundlePublicationFailureCode.UNMANAGED_PUBLICATION_STATE,
                                _relative_subject(self._config.root, final_path),
                            )
                        return self._failure(
                            bundle_ref,
                            MarketBundlePublicationFailureCode.ATOMIC_FINALIZE_FAILED,
                            _relative_subject(self._config.root, final_path),
                        )
                except OSError:
                    if not _hide_and_remove(final_path):
                        return self._failure(
                            bundle_ref,
                            MarketBundlePublicationFailureCode.UNMANAGED_PUBLICATION_STATE,
                            _relative_subject(self._config.root, final_path),
                        )
                    return self._failure(
                        bundle_ref,
                        MarketBundlePublicationFailureCode.ATOMIC_FINALIZE_FAILED,
                        _relative_subject(self._config.root, final_path),
                    )

                return MarketBundlePublicationOutcome(
                    result=MarketBundlePublicationResult(
                        bundle_ref=bundle_ref,
                        repository_path=repository_path,
                        retention_proof=retention_proof,
                        already_published=False,
                    ),
                    failure=None,
                )
        except FileExistsError:
            return self._failure(
                bundle_ref,
                MarketBundlePublicationFailureCode.LOCK_UNAVAILABLE,
                _relative_subject(
                    self._config.root,
                    self._config.root
                    / ".locks"
                    / bundle_ref.bundle_key
                    / f"{bundle_ref.manifest_hash.removeprefix('sha256:')}.lock",
                ),
            )
        except OSError:
            return self._failure(
                bundle_ref,
                MarketBundlePublicationFailureCode.STAGING_PREPARE_FAILED,
                "bundles",
            )

    @staticmethod
    def _verify_staging(
        staging: Path,
        *,
        manifest_source_hash: str,
        stream_file_names: tuple[str, ...],
        stream_payload_values: tuple[bytes, ...],
        stream_payload_hashes: tuple[str, ...],
        publication_payload: bytes,
        retention_payload: bytes,
    ) -> None:
        expected_root = {
            "manifest.json",
            "publication.json",
            "retention-proof.json",
            "streams",
        }
        if {entry.name for entry in staging.iterdir()} != expected_root:
            raise ValueError("staging root mismatch")

        streams = staging / "streams"
        if not streams.is_dir():
            raise ValueError("missing staging streams directory")

        expected_stream_files = tuple(Path(path).name for path in stream_file_names)
        observed_stream_files = tuple(sorted(path.name for path in streams.iterdir()))
        if observed_stream_files != expected_stream_files:
            raise ValueError("staging stream files mismatch")

        for filename, expected_payload, expected_hash in zip(
            expected_stream_files,
            stream_payload_values,
            stream_payload_hashes,
        ):
            payload = (streams / filename).read_bytes()
            if payload != expected_payload:
                raise ValueError("staging payload mismatch")
            if _content_hash(payload) != expected_hash:
                raise ValueError("staging payload hash mismatch")

        manifest_source = (staging / "manifest.json").read_bytes()
        try:
            manifest_value = json.loads(manifest_source)
        except (ValueError, json.JSONDecodeError) as error:
            raise ValueError("staging manifest is invalid") from error
        if manifest_source != canonical_bytes(manifest_value):
            raise ValueError("staging manifest is not canonical")
        if canonical_sha256(manifest_value) != manifest_source_hash:
            raise ValueError("staging manifest mismatch")

        publication_source = (staging / "publication.json").read_bytes()
        if publication_source != publication_payload:
            raise ValueError("staging publication mismatch")

        retention_source = (staging / "retention-proof.json").read_bytes()
        if retention_source != retention_payload:
            raise ValueError("staging retention mismatch")

    @staticmethod
    def _verify_final(
        final: Path,
        *,
        manifest_source_hash: str,
        stream_relative_paths: tuple[str, ...],
        stream_payload_values: tuple[bytes, ...],
        stream_payload_hashes: tuple[str, ...],
        publication_payload: bytes,
        retention_payload: bytes,
        retention_proof: LocalMarketBundleRetentionProof,
    ) -> bool:
        try:
            if not final.is_dir() or not final.exists():
                return False

            expected_root = {
                "manifest.json",
                "publication.json",
                "retention-proof.json",
                "streams",
            }
            entries = tuple(entry.name for entry in final.iterdir())
            if set(entries) != expected_root:
                return False

            streams = final / "streams"
            if not streams.is_dir():
                return False

            expected_stream_files = tuple(
                Path(path).name for path in stream_relative_paths
            )
            observed_stream_files = tuple(sorted(path.name for path in streams.iterdir()))
            if observed_stream_files != expected_stream_files:
                return False

            for expected_path, expected_payload, expected_hash in zip(
                expected_stream_files,
                stream_payload_values,
                stream_payload_hashes,
            ):
                payload = (streams / expected_path).read_bytes()
                if payload != expected_payload:
                    return False
                if _content_hash(payload) != expected_hash:
                    return False

            manifest_source = (final / "manifest.json").read_bytes()
            manifest_value = json.loads(manifest_source)
            if manifest_source != canonical_bytes(manifest_value):
                return False
            if canonical_sha256(manifest_value) != manifest_source_hash:
                return False

            publication_source = (final / "publication.json").read_bytes()
            if publication_source != publication_payload:
                return False

            retention_source_bytes = (final / "retention-proof.json").read_bytes()
            if retention_source_bytes != retention_payload:
                return False
            retention_source = json.loads(retention_source_bytes)

            if retention_source.get("type") != "market_bundle_retention_proof":
                return False
            if retention_source.get("bundle_ref") != retention_proof.bundle_ref.to_canonical_dict():
                return False
            if retention_source.get("retention_policy_ref") != retention_proof.retention_policy_ref:
                return False
            if retention_source.get("manifest_relative_path") != retention_proof.manifest_relative_path:
                return False
            if retention_source.get("manifest_source_hash") != manifest_source_hash:
                return False
            if retention_source.get("stream_relative_paths") != list(stream_relative_paths):
                return False
            if retention_source.get("stream_payload_hashes") != list(stream_payload_hashes):
                return False
            if retention_source.get("publication_relative_path") != retention_proof.publication_relative_path:
                return False

            if any(entry.is_symlink() for entry in final.iterdir()) or any(
                path.is_symlink() for path in final.rglob("*")
            ):
                return False

            for entry in final.iterdir():
                if entry.is_file() and (entry.stat().st_mode & 0o222):
                    return False
                if entry.is_dir() and (entry.stat().st_mode & 0o222):
                    return False

            return True
        except (OSError, ValueError, json.JSONDecodeError):
            return False


__all__ = [
    "LocalMarketBundleRepository",
    "LocalMarketBundleRepositoryConfig",
    "MarketBundlePublicationFailureCode",
    "MarketBundlePublicationFailure",
    "MarketBundlePublicationOutcome",
    "MarketBundlePublicationResult",
    "MarketBundleRepositoryPath",
    "LocalMarketBundleRetentionProof",
]
