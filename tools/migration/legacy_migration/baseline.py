from __future__ import annotations

import json
import string
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from .snapshots import canonical_json_bytes, sha256_bytes, sha256_file
from .source_maps import (
    MIGRATION_MODES,
    SNAPSHOT_MANIFEST_SCHEMA_VERSION,
    SourceDefinition,
    SourceMap,
    SourceMapError,
    safe_relative_path,
)


@dataclass(frozen=True)
class BaselineViolation:
    rule: str
    source_id: str
    path: str
    message: str


def safe_repository_path(root: Path, value: Any, field: str) -> Path:
    relative = safe_relative_path(value, field)
    return root.joinpath(*PurePosixPath(relative).parts)


def violation(rule: str, source_id: str, path: str, message: str) -> BaselineViolation:
    return BaselineViolation(rule, source_id, path, message)


def verify_source(root: Path, source: SourceDefinition) -> list[BaselineViolation]:
    violations: list[BaselineViolation] = []
    if source.snapshot is None:
        return [
            violation(
                "missing-source-member", source.id, "<snapshot>", "Snapshot reference is missing"
            )
        ]
    snapshot = source.snapshot
    try:
        snapshot_id = snapshot["id"]
        archive = safe_repository_path(root, snapshot["archive"], "snapshot.archive")
        manifest_path = safe_repository_path(root, snapshot["manifest"], "snapshot.manifest")
        expected_manifest_hash = snapshot["manifest_sha256"]
    except (KeyError, TypeError, SourceMapError) as error:
        return [
            violation(
                "missing-source-member", source.id, "<snapshot>", f"Invalid snapshot reference: {error}"
            )
        ]
    if not archive.is_file() or not manifest_path.is_file():
        missing = archive if not archive.is_file() else manifest_path
        return [
            violation(
                "missing-source-member", source.id, str(missing), "Snapshot artifact is missing"
            )
        ]
    actual_manifest_hash = sha256_file(manifest_path)
    if actual_manifest_hash != expected_manifest_hash:
        violations.append(
            violation(
                "manifest-hash-mismatch",
                source.id,
                str(manifest_path.relative_to(root)),
                "Snapshot manifest hash does not match source map",
            )
        )
        return violations
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return [
            violation(
                "manifest-hash-mismatch", source.id, str(manifest_path), f"Invalid manifest: {error}"
            )
        ]
    if manifest.get("schema_version") != SNAPSHOT_MANIFEST_SCHEMA_VERSION:
        violations.append(
            violation(
                "unsupported-source-map-schema",
                source.id,
                str(manifest_path.relative_to(root)),
                "Unsupported snapshot manifest schema",
            )
        )
        return violations
    if (
        manifest.get("source_id") != source.id
        or manifest.get("provenance") != source.provenance
        or manifest.get("archive_file") != archive.name
    ):
        violations.append(
            violation(
                "manifest-hash-mismatch",
                source.id,
                str(manifest_path.relative_to(root)),
                "Manifest identity/provenance does not match source map",
            )
        )
        return violations

    archive_hash = sha256_file(archive)
    expected_archive_hash = str(snapshot_id).removeprefix("sha256:")
    if (
        archive_hash != expected_archive_hash
        or manifest.get("archive_sha256") != archive_hash
        or manifest.get("snapshot_id") != snapshot_id
    ):
        violations.append(
            violation(
                "snapshot-hash-mismatch",
                source.id,
                str(archive.relative_to(root)),
                "Snapshot archive identity does not match",
            )
        )
        return violations

    file_rows = manifest.get("files")
    if not isinstance(file_rows, list) or not all(
        isinstance(row, dict)
        and set(row) == {"mode", "path", "sha256", "size"}
        and isinstance(row["path"], str)
        and isinstance(row["sha256"], str)
        and len(row["sha256"]) == 64
        and all(character in string.hexdigits for character in row["sha256"])
        and isinstance(row["size"], int)
        and not isinstance(row["size"], bool)
        and row["size"] >= 0
        and row["mode"] in {"0644", "0755"}
        for row in file_rows
    ):
        return [
            violation(
                "manifest-hash-mismatch", source.id, str(manifest_path), "Invalid manifest files"
            )
        ]
    manifest_paths = [row["path"] for row in file_rows]
    if manifest_paths != list(source.include_files):
        violations.append(
            violation(
                "undeclared-source-path",
                source.id,
                str(manifest_path.relative_to(root)),
                "Manifest paths do not exactly match declared include_files",
            )
        )
        return violations
    if len(set(manifest_paths)) != len(manifest_paths):
        violations.append(
            violation(
                "duplicate-source-member",
                source.id,
                str(manifest_path.relative_to(root)),
                "Manifest contains duplicate paths",
            )
        )
        return violations

    evidence_by_path = {row["path"]: row for row in file_rows}
    observed_rows: list[dict[str, Any]] = []
    try:
        with tarfile.open(archive, mode="r:gz") as tar:
            members = tar.getmembers()
            names = [member.name for member in members]
            if len(set(names)) != len(names):
                violations.append(
                    violation(
                        "duplicate-source-member",
                        source.id,
                        str(archive.relative_to(root)),
                        "Archive members must be unique",
                    )
                )
                return violations
            for member in members:
                pure = PurePosixPath(member.name)
                if (
                    pure.is_absolute()
                    or ".." in pure.parts
                    or "\\" in member.name
                    or not member.isfile()
                    or member.mtime != 0
                    or member.uid != 0
                    or member.gid != 0
                    or member.uname != ""
                    or member.gname != ""
                    or member.mode not in {0o644, 0o755}
                ):
                    violations.append(
                        violation(
                            "unsafe-archive-member",
                            source.id,
                            member.name,
                            "Archive member metadata is unsafe or non-deterministic",
                        )
                    )
                    return violations
            if names != sorted(names):
                violations.append(
                    violation(
                        "unsafe-archive-member",
                        source.id,
                        str(archive.relative_to(root)),
                        "Archive members must be sorted",
                    )
                )
                return violations
            if names != manifest_paths:
                violations.append(
                    violation(
                        "undeclared-source-path",
                        source.id,
                        str(archive.relative_to(root)),
                        "Archive members do not match manifest",
                    )
                )
                return violations
            for member in members:
                extracted = tar.extractfile(member)
                if extracted is None:
                    violations.append(
                        violation(
                            "unsafe-archive-member", source.id, member.name, "Cannot read member"
                        )
                    )
                    return violations
                value = extracted.read()
                expected = evidence_by_path[member.name]
                observed = {
                    "mode": f"{member.mode:04o}",
                    "path": member.name,
                    "sha256": sha256_bytes(value),
                    "size": len(value),
                }
                observed_rows.append(observed)
                if observed != expected:
                    violations.append(
                        violation(
                            "manifest-hash-mismatch",
                            source.id,
                            member.name,
                            "Archive member differs from manifest",
                        )
                    )
                    return violations
    except (OSError, tarfile.TarError) as error:
        violations.append(
            violation(
                "unsafe-archive-member", source.id, str(archive), f"Cannot read archive: {error}"
            )
        )
        return violations

    content_tree_hash = sha256_bytes(canonical_json_bytes(observed_rows))
    if manifest.get("content_tree_sha256") != content_tree_hash:
        violations.append(
            violation(
                "manifest-hash-mismatch",
                source.id,
                str(manifest_path.relative_to(root)),
                "Content tree hash does not match",
            )
        )
    return violations


def verify_migration_units(root: Path, source_map: SourceMap) -> list[BaselineViolation]:
    violations: list[BaselineViolation] = []
    source_by_id = {source.id: source for source in source_map.sources}
    unit_ids: set[str] = set()
    for index, unit in enumerate(source_map.migration_units):
        if not isinstance(unit, dict):
            violations.append(
                violation("invalid-source-map", "<migration>", str(index), "Unit must be mapping")
            )
            continue
        allowed_unit_fields = {
            "adr",
            "comparator_contract",
            "id",
            "mode",
            "qualification_gate",
            "source_id",
            "source_paths",
            "status",
            "target_module",
            "target_owner",
        }
        if not set(unit).issubset(allowed_unit_fields):
            violations.append(
                violation(
                    "invalid-source-map",
                    "<migration>",
                    str(index),
                    "Unknown migration unit fields",
                )
            )
            continue
        unit_id = unit.get("id")
        if not isinstance(unit_id, str) or not unit_id or unit_id in unit_ids:
            violations.append(
                violation(
                    "duplicate-source-member", "<migration>", str(index), "Invalid unit id"
                )
            )
            continue
        unit_ids.add(unit_id)
        source_id = unit.get("source_id")
        source = source_by_id.get(source_id) if isinstance(source_id, str) else None
        if source is None:
            violations.append(
                violation("missing-source-member", str(source_id), unit_id, "Unknown source")
            )
            continue
        mode = unit.get("mode")
        if mode not in MIGRATION_MODES:
            violations.append(
                violation("unsupported-migration-mode", source.id, unit_id, f"Mode: {mode}")
            )
        paths = unit.get("source_paths")
        if not isinstance(paths, list) or not paths:
            violations.append(
                violation("missing-source-member", source.id, unit_id, "source_paths missing")
            )
        else:
            for path in paths:
                if path not in source.include_files:
                    violations.append(
                        violation(
                            "undeclared-source-path", source.id, str(path), "Path not in snapshot"
                        )
                    )
        for field in ("target_owner", "target_module"):
            if not isinstance(unit.get(field), str) or not unit[field]:
                violations.append(
                    violation("missing-source-member", source.id, unit_id, f"{field} missing")
                )
        status = unit.get("status")
        comparator = unit.get("comparator_contract")
        if status == "planned":
            if comparator is not None or not isinstance(unit.get("qualification_gate"), str):
                violations.append(
                    violation(
                        "missing-source-member",
                        source.id,
                        unit_id,
                        "Planned unit requires qualification_gate and null comparator_contract",
                    )
                )
        elif status == "active":
            if not isinstance(comparator, str):
                violations.append(
                    violation(
                        "missing-source-member", source.id, unit_id, "Active comparator missing"
                    )
                )
            else:
                try:
                    comparator_path = safe_repository_path(
                        root, comparator, "comparator_contract"
                    )
                    if not comparator_path.is_file():
                        violations.append(
                            violation(
                                "missing-source-member",
                                source.id,
                                comparator,
                                "Comparator missing",
                            )
                        )
                except SourceMapError as error:
                    violations.append(violation(error.rule, source.id, comparator, error.message))
        else:
            violations.append(
                violation(
                    "missing-source-member",
                    source.id,
                    unit_id,
                    "Migration unit status must be planned/active",
                )
            )
        if mode == "intentional_semantic_change":
            adr = unit.get("adr")
            if not isinstance(adr, str):
                violations.append(
                    violation(
                        "intentional-change-without-adr", source.id, unit_id, "ADR is required"
                    )
                )
            else:
                try:
                    adr_path = safe_repository_path(root, adr, "adr")
                    if not adr.startswith("docs/adr/") or not adr_path.is_file():
                        violations.append(
                            violation(
                                "intentional-change-without-adr",
                                source.id,
                                adr,
                                "Committed docs/adr reference required",
                            )
                        )
                except SourceMapError as error:
                    violations.append(violation(error.rule, source.id, adr, error.message))
    return violations


def verify_baseline(root: Path, source_map: SourceMap) -> tuple[int, list[BaselineViolation]]:
    violations: list[BaselineViolation] = []
    verified = 0
    for source in source_map.sources:
        source_violations = verify_source(root, source)
        violations.extend(source_violations)
        if not source_violations:
            verified += 1
    violations.extend(verify_migration_units(root, source_map))
    return verified, sorted(
        violations,
        key=lambda item: (item.rule, item.source_id, item.path, item.message),
    )


def report_payload(
    source_map_path: Path,
    source_map: SourceMap,
    sources_verified: int,
    violations: list[BaselineViolation],
) -> dict[str, Any]:
    return {
        "source_map_sha256": sha256_file(source_map_path),
        "source_repository_reads": 0,
        "source_snapshot_ids": [
            source.snapshot["id"] for source in source_map.sources if source.snapshot
        ],
        "sources_verified": sources_verified,
        "status": "failed" if violations else "passed",
        "violations": [asdict(item) for item in violations],
    }
