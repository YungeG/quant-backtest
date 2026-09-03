from __future__ import annotations

from pathlib import Path

import pytest
from crypto_quant_bundle_builder import (
    RawBlobSnapshotManifest,
    RawBlobSnapshotMember,
    RawBlobSnapshotSourceMember,
    RawBlobSnapshotView,
    create_raw_blob_snapshot_manifest,
)
from crypto_quant_domain import RawBlobRef


class _Reader:
    def __init__(self, paths: dict[RawBlobRef, Path]) -> None:
        self.paths = paths

    def raw_blob_path(self, *, ref: RawBlobRef) -> Path:
        return self.paths[ref]


def _sources() -> tuple[RawBlobSnapshotSourceMember, ...]:
    return (
        RawBlobSnapshotSourceMember("data/b.txt", b"beta", "0644"),
        RawBlobSnapshotSourceMember("data/a.txt", b"alpha", "0755"),
    )


def _manifest() -> RawBlobSnapshotManifest:
    return create_raw_blob_snapshot_manifest(
        members=_sources(),
        provenance={"source": "fixture", "retention": "test"},
    )


def test_manifest_is_sorted_and_content_addressed_without_provenance_identity() -> None:
    first = _manifest()
    changed_provenance = create_raw_blob_snapshot_manifest(
        members=tuple(reversed(_sources())),
        provenance={"source": "fixture", "retention": "changed"},
    )
    changed_content = create_raw_blob_snapshot_manifest(
        members=(
            RawBlobSnapshotSourceMember("data/b.txt", b"BETA", "0644"),
            RawBlobSnapshotSourceMember("data/a.txt", b"alpha", "0755"),
        ),
        provenance={"source": "fixture", "retention": "test"},
    )

    assert tuple(member.member_key for member in first.members) == (
        "data/a.txt",
        "data/b.txt",
    )
    assert first.snapshot_id == first.content_tree_hash
    assert first.snapshot_id == changed_provenance.snapshot_id
    assert first.provenance_hash != changed_provenance.provenance_hash
    assert first.content_tree_hash != changed_content.content_tree_hash
    assert RawBlobSnapshotManifest.from_envelope(first.envelope) == first
    with pytest.raises(ValueError, match="sorted"):
        RawBlobSnapshotManifest(
            first.snapshot_id,
            tuple(reversed(first.members)),
            first.content_tree_hash,
            first.provenance,
            first.provenance_hash,
        )
    with pytest.raises(ValueError, match="content_tree_hash"):
        RawBlobSnapshotManifest(
            first.snapshot_id,
            first.members,
            "sha256:" + "0" * 64,
            first.provenance,
            first.provenance_hash,
        )


def test_view_rechecks_all_members_and_rejects_tampering_missing_and_unsafe_names(
    tmp_path: Path,
) -> None:
    manifest = _manifest()
    paths: dict[RawBlobRef, Path] = {}
    sources = sorted(_sources(), key=lambda item: item.member_key)
    for member, source in zip(manifest.members, sources):
        path = tmp_path / member.member_key.replace("/", "-")
        path.write_bytes(source.raw_bytes)
        paths[member.raw_blob_ref] = path
    reader = _Reader(paths)

    view = RawBlobSnapshotView.open(manifest, reader)
    assert view.member_bytes("data/a.txt") == b"alpha"
    assert view.member_path("data/b.txt") == paths[manifest.members[1].raw_blob_ref]

    paths[manifest.members[0].raw_blob_ref].write_bytes(b"ALPHA")
    with pytest.raises(ValueError, match="unavailable"):
        view.member_bytes("data/a.txt")
    paths[manifest.members[0].raw_blob_ref].unlink()
    with pytest.raises(ValueError, match="unavailable"):
        RawBlobSnapshotView.open(manifest, reader)
    paths[manifest.members[0].raw_blob_ref].write_bytes(b"alpha")
    unsafe = paths[manifest.members[1].raw_blob_ref]
    unsafe_target = tmp_path / "matching-raw-blob"
    unsafe_target.write_bytes(b"beta")
    unsafe.unlink()
    unsafe.symlink_to(unsafe_target)
    with pytest.raises(ValueError, match="unavailable"):
        RawBlobSnapshotView.open(manifest, reader)
    with pytest.raises(ValueError, match="member_key"):
        RawBlobSnapshotMember("../escape", manifest.members[1].raw_blob_ref, "0644")
