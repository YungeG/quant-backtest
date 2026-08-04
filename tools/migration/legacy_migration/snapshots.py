from __future__ import annotations

import gzip
import hashlib
import io
import json
import stat
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .source_maps import SNAPSHOT_MANIFEST_SCHEMA_VERSION, SourceDefinition, SourceMapError


@dataclass(frozen=True)
class FileEvidence:
    path: str
    sha256: str
    size: int
    mode: str


@dataclass(frozen=True)
class SnapshotResult:
    snapshot_id: str
    archive: Path
    manifest: Path


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_mode(path: Path) -> int:
    return 0o755 if path.stat().st_mode & 0o111 else 0o644


def capture_files(source_root: Path, source: SourceDefinition) -> list[tuple[FileEvidence, bytes]]:
    captured: list[tuple[FileEvidence, bytes]] = []
    source_root = source_root.resolve()
    for relative in source.include_files:
        pure = PurePosixPath(relative)
        if pure.is_absolute() or ".." in pure.parts:
            raise SourceMapError("undeclared-source-path", f"Unsafe source path: {relative}")
        path = source_root.joinpath(*pure.parts)
        try:
            resolved_path = path.resolve(strict=True)
            if not resolved_path.is_relative_to(source_root):
                raise SourceMapError(
                    "unsafe-archive-member", f"Declared source escapes source root: {relative}"
                )
            metadata = path.lstat()
        except FileNotFoundError as error:
            raise SourceMapError(
                "missing-source-member", f"Missing declared source file: {relative}"
            ) from error
        if not stat.S_ISREG(metadata.st_mode):
            raise SourceMapError(
                "unsafe-archive-member", f"Declared source must be a regular file: {relative}"
            )
        value = path.read_bytes()
        mode = normalized_mode(path)
        evidence = FileEvidence(
            path=relative,
            sha256=sha256_bytes(value),
            size=len(value),
            mode=f"{mode:04o}",
        )
        captured.append((evidence, value))
    return captured


def deterministic_archive(captured: list[tuple[FileEvidence, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for evidence, value in captured:
                member = tarfile.TarInfo(evidence.path)
                member.size = len(value)
                member.mode = int(evidence.mode, 8)
                member.mtime = 0
                member.uid = 0
                member.gid = 0
                member.uname = ""
                member.gname = ""
                member.type = tarfile.REGTYPE
                archive.addfile(member, io.BytesIO(value))
    return buffer.getvalue()


def atomic_write(path: Path, value: bytes) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(value)
    temporary.replace(path)


def freeze_snapshot(
    source_root: Path, source: SourceDefinition, output_dir: Path
) -> SnapshotResult:
    captured = capture_files(source_root.resolve(), source)
    archive_bytes = deterministic_archive(captured)
    archive_hash = sha256_bytes(archive_bytes)
    snapshot_id = f"sha256:{archive_hash}"
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{source.id}-{archive_hash}.tar.gz"
    atomic_write(archive_path, archive_bytes)

    files = [asdict(evidence) for evidence, _ in captured]
    content_tree_hash = sha256_bytes(canonical_json_bytes(files))
    manifest_payload = {
        "archive_file": archive_path.name,
        "archive_sha256": archive_hash,
        "content_tree_sha256": content_tree_hash,
        "files": files,
        "provenance": source.provenance,
        "schema_version": SNAPSHOT_MANIFEST_SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "source_id": source.id,
    }
    manifest_path = output_dir / f"{source.id}-{archive_hash}.manifest.json"
    atomic_write(manifest_path, pretty_json_bytes(manifest_payload))
    return SnapshotResult(snapshot_id, archive_path.resolve(), manifest_path.resolve())
