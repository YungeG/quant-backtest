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
from .synthetic_jsonl import (
    SyntheticJsonlV1Config,
    SyntheticJsonlV1NormalizationFailure,
    SyntheticJsonlV1NormalizationFailureCode,
    SyntheticJsonlV1NormalizationOutcome,
    SyntheticJsonlV1NormalizationResult,
    SyntheticJsonlV1RecordLocator,
    SyntheticJsonlV1SourceTrace,
    normalize_synthetic_jsonl_v1,
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
    "SyntheticJsonlV1Config",
    "SyntheticJsonlV1NormalizationFailure",
    "SyntheticJsonlV1NormalizationFailureCode",
    "SyntheticJsonlV1NormalizationOutcome",
    "SyntheticJsonlV1NormalizationResult",
    "SyntheticJsonlV1RecordLocator",
    "SyntheticJsonlV1SourceTrace",
    "freeze_source_snapshot",
    "normalize_synthetic_jsonl_v1",
    "verify_source_snapshot",
]
