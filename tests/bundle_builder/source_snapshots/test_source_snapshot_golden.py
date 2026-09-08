from __future__ import annotations

import json
from pathlib import Path

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotFailureCode,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests/fixtures/market_data/source-snapshots"
ARCHIVE = FIXTURES / "source-snapshot-v1.tar.gz"
EXPECTED = FIXTURES / "source-snapshot-v1.expected.json"


def _outcome():
    return freeze_source_snapshot(
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
            "fixture.vendor",
            "fixture.source",
            "license.fixture",
            "retention.fixture",
        ),
    )


def _payload() -> dict[str, object]:
    outcome = _outcome()
    assert outcome.snapshot is not None
    snapshot = outcome.snapshot
    reversed_snapshot = freeze_source_snapshot(
        members=tuple(
            reversed(
                (
                    RawSourceMember("empty.dat", b"", "0644", 11, None),
                    RawSourceMember(
                        "bin/run.sh",
                        b"#!/bin/sh\necho fixture\n",
                        "0755",
                        12,
                        "sha256:6ecf06f6dbbab6a920b5b208bc7c4069ca266b150d6c00533a00b5975a8417ca",
                    ),
                    RawSourceMember("data/alpha.txt", b"alpha\n", "0644", 10, None),
                )
            )
        ),
        provenance=snapshot.provenance,
    ).snapshot
    assert reversed_snapshot is not None
    failed = freeze_source_snapshot(
        members=(RawSourceMember("missing.dat", None, "0644", 1, None),),
        provenance=snapshot.provenance,
    )
    assert failed.failure is not None
    return {
        "schema_version": 1,
        "fixture_id": "source-snapshot-v1",
        "snapshot": snapshot.to_canonical_dict(),
        "archive_size": len(snapshot.archive_bytes),
        "member_bytes": {
            member.member_key: snapshot.member_bytes(member.member_key).hex()
            for member in snapshot.members
        },
        "repeat_parity": {
            "snapshot_id_matches": snapshot.snapshot_id
            == reversed_snapshot.snapshot_id,
            "archive_bytes_match": snapshot.archive_bytes
            == reversed_snapshot.archive_bytes,
            "provenance_hash_matches": snapshot.provenance_hash
            == reversed_snapshot.provenance_hash,
        },
        "failure_control": {
            "code": failed.failure.code.value,
            "expected": SourceSnapshotFailureCode.ACQUISITION_FAILED.value,
            "member_key": failed.failure.member_key,
            "failure_hash": failed.failure.failure_hash,
        },
        "limitations": [
            "synthetic-secret-free-fixture",
            "no-network-or-filesystem-acquisition",
            "no-normalization",
            "no-durable-publication",
            "no-retention-or-retrieval-proof",
            "no-decision-grade-or-deployment-authorization",
        ],
    }


def test_source_snapshot_matches_static_golden() -> None:
    outcome = _outcome()
    assert outcome.snapshot is not None
    try:
        expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
        archive = ARCHIVE.read_bytes()
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid G12A golden fixture: {error}") from error
    assert archive == outcome.snapshot.archive_bytes
    assert _payload() == expected
