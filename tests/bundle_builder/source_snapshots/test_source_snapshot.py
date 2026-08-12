from __future__ import annotations

from dataclasses import replace

import pytest

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotFailureCode,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)


def test_freeze_source_snapshot_is_atomic_and_content_addressed() -> None:
    outcome = freeze_source_snapshot(
        members=(
            RawSourceMember("empty.dat", b"", "0644", 11, None),
            RawSourceMember(
                "bin/run.sh",
                b"#!/bin/sh\necho fixture\n",
                "0755",
                12,
                "sha256:6ecf06f6dbbab6a920b5b208bc7c4069ca266b150d6c00533a00b5975a8417ca",
            ),
            RawSourceMember("data/alpha.txt", b"alpha\n", "0644", 10, None),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="fixture.vendor",
            source_key="fixture.source",
            license_ref="license.fixture",
            retention_policy_ref="retention.fixture",
        ),
    )

    assert outcome.failure is None
    assert outcome.snapshot is not None
    assert outcome.snapshot.snapshot_id.startswith("sha256:")
    assert outcome.snapshot.member_bytes("empty.dat") == b""
    assert outcome.snapshot.member_bytes("data/alpha.txt") == b"alpha\n"
    assert outcome.snapshot.decision_grade_eligible is False
    assert outcome.snapshot.deployment_authorized is False


def _provenance() -> SourceSnapshotProvenance:
    return SourceSnapshotProvenance(
        vendor_key="fixture.vendor",
        source_key="fixture.source",
        license_ref="license.fixture",
        retention_policy_ref="retention.fixture",
    )


def _members() -> tuple[RawSourceMember, ...]:
    return (
        RawSourceMember("empty.dat", b"", "0644", 11, None),
        RawSourceMember("data/alpha.txt", b"alpha\n", "0644", 10, None),
    )


def test_content_identity_ignores_input_order_and_provenance() -> None:
    first = freeze_source_snapshot(members=_members(), provenance=_provenance()).snapshot
    reversed_result = freeze_source_snapshot(
        members=tuple(reversed(_members())), provenance=_provenance()
    ).snapshot
    changed_provenance = freeze_source_snapshot(
        members=tuple(replace(item, acquired_at_epoch_nanoseconds=99) for item in _members()),
        provenance=replace(_provenance(), license_ref="license.changed"),
    ).snapshot
    assert first is not None and reversed_result is not None and changed_provenance is not None

    assert first.snapshot_id == reversed_result.snapshot_id == changed_provenance.snapshot_id
    assert first.archive_bytes == reversed_result.archive_bytes
    assert first.provenance_hash != changed_provenance.provenance_hash


def test_key_mode_and_bytes_change_content_identity() -> None:
    baseline = freeze_source_snapshot(members=_members(), provenance=_provenance()).snapshot
    changed_key = freeze_source_snapshot(
        members=(replace(_members()[0], member_key="empty2.dat"), _members()[1]),
        provenance=_provenance(),
    ).snapshot
    changed_mode = freeze_source_snapshot(
        members=(replace(_members()[0], mode="0755"), _members()[1]),
        provenance=_provenance(),
    ).snapshot
    changed_bytes = freeze_source_snapshot(
        members=(_members()[0], replace(_members()[1], raw_bytes=b"beta\n")),
        provenance=_provenance(),
    ).snapshot
    assert all(value is not None for value in (baseline, changed_key, changed_mode, changed_bytes))
    assert len({value.snapshot_id for value in (baseline, changed_key, changed_mode, changed_bytes) if value is not None}) == 4


def test_freeze_failure_precedence_and_atomicity() -> None:
    duplicate = freeze_source_snapshot(
        members=(_members()[0], _members()[0]), provenance=_provenance()
    )
    missing = freeze_source_snapshot(
        members=(_members()[0], replace(_members()[1], raw_bytes=None)),
        provenance=_provenance(),
    )
    mismatched = freeze_source_snapshot(
        members=(
            _members()[0],
            replace(_members()[1], declared_sha256="sha256:" + "0" * 64),
        ),
        provenance=_provenance(),
    )

    assert duplicate.failure is not None
    assert duplicate.failure.code is SourceSnapshotFailureCode.DUPLICATE_MEMBER
    assert missing.failure is not None
    assert missing.failure.code is SourceSnapshotFailureCode.ACQUISITION_FAILED
    assert mismatched.failure is not None
    assert mismatched.failure.code is SourceSnapshotFailureCode.DECLARED_SOURCE_HASH_MISMATCH
    assert duplicate.snapshot is missing.snapshot is mismatched.snapshot is None


def test_verify_detects_tampered_content_and_provenance() -> None:
    snapshot = freeze_source_snapshot(members=_members(), provenance=_provenance()).snapshot
    assert snapshot is not None

    archive_failure = verify_source_snapshot(replace(snapshot, archive_bytes=b"not-gzip"))
    id_failure = verify_source_snapshot(replace(snapshot, snapshot_id="sha256:" + "0" * 64))
    tree_failure = verify_source_snapshot(
        replace(snapshot, content_tree_hash="sha256:" + "0" * 64)
    )
    provenance_failure = verify_source_snapshot(
        replace(snapshot, provenance_hash="sha256:" + "0" * 64)
    )

    assert archive_failure.failure is not None
    assert archive_failure.failure.code is SourceSnapshotFailureCode.ARCHIVE_INVALID
    assert id_failure.failure is not None
    assert id_failure.failure.code is SourceSnapshotFailureCode.SNAPSHOT_ID_MISMATCH
    assert tree_failure.failure is not None
    assert tree_failure.failure.code is SourceSnapshotFailureCode.CONTENT_TREE_HASH_MISMATCH
    assert provenance_failure.failure is not None
    assert provenance_failure.failure.code is SourceSnapshotFailureCode.PROVENANCE_HASH_MISMATCH


def test_member_and_provenance_inputs_fail_closed() -> None:
    with pytest.raises(ValueError, match="portable ASCII"):
        replace(_members()[0], member_key="../escape")
    with pytest.raises(ValueError, match="portable ASCII"):
        replace(_members()[0], member_key=".hidden")
    with pytest.raises(ValueError, match="mode"):
        replace(_members()[0], mode="0600")
    with pytest.raises(TypeError, match="integer"):
        replace(_members()[0], acquired_at_epoch_nanoseconds=True)
    with pytest.raises(ValueError, match="reference"):
        replace(_provenance(), vendor_key="https://vendor.example")


def test_member_access_is_verified_and_non_revealing() -> None:
    snapshot = freeze_source_snapshot(members=_members(), provenance=_provenance()).snapshot
    assert snapshot is not None
    assert snapshot.member_bytes("empty.dat") == b""
    with pytest.raises(ValueError, match="source snapshot member unavailable"):
        snapshot.member_bytes("missing.dat")
    tampered = replace(snapshot, archive_bytes=b"bad")
    with pytest.raises(ValueError, match="source snapshot member unavailable"):
        tampered.member_bytes("empty.dat")
