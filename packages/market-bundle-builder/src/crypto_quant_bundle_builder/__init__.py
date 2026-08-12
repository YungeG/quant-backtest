"""Offline immutable market-bundle builder."""

from .source_snapshots import (
    RawSourceMember,
    SourceSnapshot,
    SourceSnapshotFailure,
    SourceSnapshotFailureCode,
    SourceSnapshotMember,
    SourceSnapshotOutcome,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

__version__ = "0.1.0"

__all__ = [
    "RawSourceMember",
    "SourceSnapshot",
    "SourceSnapshotFailure",
    "SourceSnapshotFailureCode",
    "SourceSnapshotMember",
    "SourceSnapshotOutcome",
    "SourceSnapshotProvenance",
    "freeze_source_snapshot",
    "verify_source_snapshot",
]
