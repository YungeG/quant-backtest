from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

import yaml


SOURCE_MAP_SCHEMA_VERSION = 1
SNAPSHOT_MANIFEST_SCHEMA_VERSION = 1
MIGRATION_MODES = frozenset(
    {
        "copy_with_parity",
        "intentional_semantic_change",
        "new_capability",
        "reimplement_with_reference",
    }
)


class UniqueKeySafeLoader(yaml.SafeLoader):
    pass


def construct_unique_mapping(
    loader: UniqueKeySafeLoader, node: yaml.nodes.MappingNode, deep: bool = False
) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in mapping:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_unique_mapping
)


class SourceMapError(ValueError):
    def __init__(self, rule: str, message: str) -> None:
        super().__init__(message)
        self.rule = rule
        self.message = message


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    provenance: dict[str, Any]
    include_files: tuple[str, ...]
    snapshot: dict[str, Any] | None


@dataclass(frozen=True)
class SourceMap:
    schema_version: int
    snapshot_manifest_schema_version: int
    allowed_migration_modes: frozenset[str]
    sources: tuple[SourceDefinition, ...]
    migration_units: tuple[dict[str, Any], ...]

    def source(self, source_id: str) -> SourceDefinition:
        matches = [source for source in self.sources if source.id == source_id]
        if len(matches) != 1:
            raise SourceMapError("missing-source-member", f"Unknown source id: {source_id}")
        return matches[0]


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceMapError("invalid-source-map", f"{field} must be a non-empty string")
    return value


def safe_relative_path(value: Any, field: str) -> str:
    path = require_string(value, field)
    pure = PurePosixPath(path)
    if pure.is_absolute() or ".." in pure.parts or "\\" in path or str(pure) != path:
        raise SourceMapError("undeclared-source-path", f"Unsafe relative path in {field}: {path}")
    return path


def load_source_map(path: Path) -> SourceMap:
    try:
        raw = yaml.load(
            path.read_text(encoding="utf-8"), Loader=UniqueKeySafeLoader
        )
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise SourceMapError("invalid-source-map", f"Cannot read source map: {error}") from error
    if not isinstance(raw, dict):
        raise SourceMapError("invalid-source-map", "Source map must be a mapping")
    if set(raw) != {
        "allowed_migration_modes",
        "migration_units",
        "schema_version",
        "snapshot_manifest_schema_version",
        "sources",
    }:
        raise SourceMapError("invalid-source-map", "Unknown or missing source map fields")
    if raw.get("schema_version") != SOURCE_MAP_SCHEMA_VERSION:
        raise SourceMapError(
            "unsupported-source-map-schema",
            f"Expected source map schema {SOURCE_MAP_SCHEMA_VERSION}",
        )
    if raw.get("snapshot_manifest_schema_version") != SNAPSHOT_MANIFEST_SCHEMA_VERSION:
        raise SourceMapError(
            "unsupported-source-map-schema",
            f"Expected snapshot manifest schema {SNAPSHOT_MANIFEST_SCHEMA_VERSION}",
        )
    modes = raw.get("allowed_migration_modes")
    if (
        not isinstance(modes, list)
        or not all(isinstance(mode, str) for mode in modes)
        or len(modes) != len(MIGRATION_MODES)
        or set(modes) != MIGRATION_MODES
    ):
        raise SourceMapError(
            "unsupported-migration-mode",
            "allowed_migration_modes must enumerate the v1 migration modes exactly",
        )

    rows = raw.get("sources")
    if not isinstance(rows, list) or not rows:
        raise SourceMapError("invalid-source-map", "sources must be a non-empty list")
    sources: list[SourceDefinition] = []
    ids: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise SourceMapError("invalid-source-map", f"sources[{index}] must be a mapping")
        if set(row) != {"id", "include_files", "provenance", "snapshot"}:
            raise SourceMapError(
                "invalid-source-map", f"Unknown or missing fields in sources[{index}]"
            )
        source_id = require_string(row.get("id"), f"sources[{index}].id")
        if re.fullmatch(r"[a-z0-9][a-z0-9-]*", source_id) is None:
            raise SourceMapError(
                "invalid-source-map", f"Unsafe source id: {source_id}"
            )
        if source_id in ids:
            raise SourceMapError("duplicate-source-member", f"Duplicate source id: {source_id}")
        ids.add(source_id)
        provenance = row.get("provenance")
        if not isinstance(provenance, dict):
            raise SourceMapError(
                "invalid-source-map", f"sources[{index}].provenance must be a mapping"
            )
        if set(provenance) != {"base_commit", "remote", "worktree_state"}:
            raise SourceMapError(
                "invalid-source-map", f"Invalid provenance fields in sources[{index}]"
            )
        require_string(provenance.get("base_commit"), f"sources[{index}].base_commit")
        if provenance.get("remote") is not None and not isinstance(
            provenance.get("remote"), str
        ):
            raise SourceMapError(
                "invalid-source-map", f"sources[{index}].remote must be string/null"
            )
        if provenance.get("worktree_state") not in {"clean", "dirty"}:
            raise SourceMapError(
                "invalid-source-map", f"sources[{index}].worktree_state must be clean/dirty"
            )
        include = row.get("include_files")
        if not isinstance(include, list) or not include:
            raise SourceMapError(
                "invalid-source-map", f"sources[{index}].include_files must be non-empty"
            )
        include_files = tuple(
            safe_relative_path(item, f"sources[{index}].include_files") for item in include
        )
        if len(set(include_files)) != len(include_files):
            raise SourceMapError(
                "duplicate-source-member", f"Duplicate source path in {source_id}"
            )
        if tuple(sorted(include_files)) != include_files:
            raise SourceMapError(
                "invalid-source-map", f"include_files must be sorted for {source_id}"
            )
        snapshot = row.get("snapshot")
        if snapshot is not None and not isinstance(snapshot, dict):
            raise SourceMapError(
                "invalid-source-map", f"sources[{index}].snapshot must be mapping/null"
            )
        if snapshot is not None and set(snapshot) != {
            "archive",
            "id",
            "manifest",
            "manifest_sha256",
        }:
            raise SourceMapError(
                "invalid-source-map", f"Invalid snapshot fields in sources[{index}]"
            )
        sources.append(SourceDefinition(source_id, provenance, include_files, snapshot))

    units = raw.get("migration_units")
    if not isinstance(units, list):
        raise SourceMapError("invalid-source-map", "migration_units must be a list")
    return SourceMap(
        schema_version=SOURCE_MAP_SCHEMA_VERSION,
        snapshot_manifest_schema_version=SNAPSHOT_MANIFEST_SCHEMA_VERSION,
        allowed_migration_modes=frozenset(modes),
        sources=tuple(sources),
        migration_units=tuple(units),
    )
