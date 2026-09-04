"""Streaming boundary index for exact KORU aggregate-trade captures."""

from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import tarfile
from collections import OrderedDict
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from zipfile import BadZipFile, ZipFile

from crypto_quant_domain import (
    ArtifactEnvelope,
    ArtifactRef,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketEvent

from .binance_usdm_koru_aggtrades_source_bounded_v1 import (
    _CSV_HEADER,
    _DECIMAL,
    _MAX_ATTEMPTS,
    _RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY,
    _RETAINED_COVERAGE_END_MS,
    _RETAINED_DERIVED_CSV_MEMBER_KEY,
    _RETAINED_EXECUTION_MANIFEST_MEMBER_KEY,
    _RETAINED_RAW_PATH_PREFIX,
    BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1,
    BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
    BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1,
    _availability_authority_bytes,
    _event_from_row,
    _exact_mapping,
    _execution_manifest,
    _is_csv_header_like,
    _iso_milliseconds,
    _json_object,
    _manifest_file,
    _manifest_files,
    _NormalizationError,
    _page_from_manifest_entry,
    _parse_row,
    _ParsedRow,
    _provenance,
    _retained_member_keys,
    _sha256,
    _snapshot_member,
    _trusted_authority,
    _trusted_capture,
    build_binance_usdm_koru_aggregate_trades_retained_rest_evidence_v1,
)
from .binance_usdm_koru_aggtrades_source_bounded_v1 import (
    _trusted_request as _trusted_source_request,
)
from .raw_blob_snapshots import RawBlobSnapshotView
from .source_snapshots import (
    SourceSnapshot,
    _content_tree_hash,
    _provenance_hash,
)

_SCHEMA_VERSION = 1
_DAY_NS = 86_400_000_000_000
_EPOCH_DATE = date(1970, 1, 1)
_HASH_PREFIX = "sha256:"
_MISSING_REASON = "no_aggregate_trade_before_cutoff"


def _hash(name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 71
        or not value.startswith(_HASH_PREFIX)
        or any(character not in "0123456789abcdef" for character in value[7:])
    ):
        raise ValueError(f"{name} must be a canonical sha256 digest")
    return value


def _utc_date(instant: UtcInstant) -> str:
    return (
        _EPOCH_DATE + timedelta(days=instant.epoch_nanoseconds // _DAY_NS)
    ).isoformat()


def _requested_dates(start: UtcInstant, end: UtcInstant) -> tuple[str, ...]:
    first = start.epoch_nanoseconds // _DAY_NS
    last = (end.epoch_nanoseconds - 1) // _DAY_NS
    return tuple(
        (_EPOCH_DATE + timedelta(days=day)).isoformat()
        for day in range(first, last + 1)
    )


def _retained_manifest(
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
) -> dict[str, object]:
    return _execution_manifest(
        _archive_member_bytes(
            capture.snapshot, _RETAINED_EXECUTION_MANIFEST_MEMBER_KEY
        )
    )


def _retained_manifest_metadata_matches(
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
) -> bool:
    request = capture.request
    authority = _trusted_authority(request.authority)
    if authority is None:
        return False
    try:
        manifest = _retained_manifest(capture)
        if not _exact_mapping(
            manifest.get("holdout_protection"),
            {
                "full_2026_08_24_daily_archive_downloaded": False,
                "policy": "No request, retained row, or archive may address this instant or later",
                "rest_end_time_inclusive": _RETAINED_COVERAGE_END_MS - 1,
                "start_utc_inclusive": "2026-08-24T11:00:00.000Z",
            },
        ) or manifest.get("missing_intervals") != [
            {
                "dataset": "aggTrades",
                "end_utc_exclusive": "2026-08-24T06:34:20.640Z",
                "reason": "Binance public aggTrades REST rejected older requests with code -4166; no archive or alternate feed was used for 2026-08-24",
                "start_utc_inclusive": "2026-08-24T00:00:00.000Z",
            }
        ]:
            return False
        if manifest.get("generated_at_basis") != (
            "frozen base manifest generated_at_utc used as a deterministic offline regeneration marker"
        ):
            return False
        files = _manifest_files(manifest)
        page_entries = [
            entry
            for entry in files
            if type(entry.get("path")) is str
            and str(entry["path"]).startswith(_RETAINED_RAW_PATH_PREFIX)
            and entry.get("status") == "canonical_rest_response"
        ]
        pages = tuple(_page_from_manifest_entry(entry, None) for entry in page_entries)
        if pages != authority.pages:
            return False
        derived_path = _RETAINED_RAW_PATH_PREFIX + authority.derived_csv_member_name
        archive_name = authority.derived_csv_member_name.removesuffix(".csv") + ".zip"
        derived = _manifest_file(files, derived_path, "rest_derived_standard_schema")
        archive = _manifest_file(
            files,
            _RETAINED_RAW_PATH_PREFIX + archive_name,
            "rest_derived_standard_schema",
        )
        checksum = _manifest_file(
            files,
            _RETAINED_RAW_PATH_PREFIX + archive_name + ".CHECKSUM",
            "locally_generated_checksum",
        )
        by_key = {member.member_key: member for member in capture.snapshot.members}
        archive_key = "derived/" + request.archive_name
        checksum_key = "derived/" + request.checksum_name
        availability_bytes = _archive_member_bytes(
            capture.snapshot, _RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY
        )
        derived_bytes = _archive_member_bytes(
            capture.snapshot, _RETAINED_DERIVED_CSV_MEMBER_KEY
        )
        archive_bytes = _archive_member_bytes(capture.snapshot, archive_key)
        checksum_bytes = _archive_member_bytes(capture.snapshot, checksum_key)
        expected_archive, expected_checksum = (
            build_binance_usdm_koru_aggregate_trades_retained_rest_evidence_v1(
                authority, derived_bytes
            )
        )
        if (
            _sha256(availability_bytes)
            != by_key[_RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY].content_hash
            or availability_bytes != _availability_authority_bytes()
            or authority.execution_manifest_file_sha256
            != by_key[_RETAINED_EXECUTION_MANIFEST_MEMBER_KEY].content_hash
            or authority.execution_manifest_identity != manifest["manifest_sha256"]
            or authority.execution_manifest_generated_at_epoch_nanoseconds
            != _iso_milliseconds(manifest.get("generated_at_utc")) * 1_000_000
            or derived["sha256"] != authority.derived_csv_sha256
            or derived["sha256"]
            != by_key[_RETAINED_DERIVED_CSV_MEMBER_KEY].content_hash
            or derived["size_bytes"]
            != by_key[_RETAINED_DERIVED_CSV_MEMBER_KEY].byte_count
            or archive["sha256"] != request.expected_archive_sha256
            or archive["sha256"] != by_key[archive_key].content_hash
            or archive["size_bytes"] != by_key[archive_key].byte_count
            or checksum["sha256"] != request.expected_checksum_sha256
            or checksum["sha256"] != by_key[checksum_key].content_hash
            or checksum["size_bytes"] != by_key[checksum_key].byte_count
            or archive_bytes != expected_archive
            or checksum_bytes != expected_checksum
        ):
            return False
        if any(
            entry["sha256"] != page.content_sha256
            or entry["row_count"] != page.row_count
            or entry["size_bytes"]
            != by_key["retained/raw/" + page.member_name].byte_count
            or page.content_sha256
            != by_key["retained/raw/" + page.member_name].content_hash
            for entry, page in zip(page_entries, pages, strict=True)
        ):
            return False
        row_count = sum(page.row_count for page in pages)
        return all(
            entry["row_count"] == row_count
            for entry in (derived, archive, checksum)
        )
    except (
        AttributeError,
        KeyError,
        OSError,
        RuntimeError,
        StopIteration,
        TypeError,
        ValueError,
    ):
        return False


def _snapshot_metadata_matches_retained_request(
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
) -> bool:
    request = capture.request
    snapshot = capture.snapshot
    expected_keys = _retained_member_keys(request)
    if (
        type(snapshot) is not SourceSnapshot
        or tuple(member.member_key for member in snapshot.members) != expected_keys
        or snapshot.provenance != _provenance(request)
        or snapshot.decision_grade_eligible
        or snapshot.deployment_authorized
        or any(
            member.acquired_at_epoch_nanoseconds
            != request.acquired_at_epoch_nanoseconds
            or member.mode != "0644"
            or member.content_hash != member.declared_sha256
            for member in snapshot.members
        )
        or _sha256(snapshot.archive_bytes) != snapshot.snapshot_id
        or _content_tree_hash(snapshot.members) != snapshot.content_tree_hash
        or _provenance_hash(
            snapshot.snapshot_id, snapshot.provenance, snapshot.members
        )
        != snapshot.provenance_hash
    ):
        return False
    by_key = {member.member_key: member for member in snapshot.members}
    try:
        with tarfile.open(
            fileobj=io.BytesIO(snapshot.archive_bytes), mode="r:gz"
        ) as archive:
            members = archive.getmembers()
            if (
                tuple(member.name for member in members) != expected_keys
                or any(
                    not member.isfile()
                    or member.mode != 0o644
                    or member.mtime != 0
                    or member.uid != 0
                    or member.gid != 0
                    or member.uname != ""
                    or member.gname != ""
                    for member in members
                )
            ):
                return False
            for tar_member in members:
                stream = archive.extractfile(tar_member)
                if stream is None:
                    return False
                digest = hashlib.sha256()
                byte_count = 0
                while chunk := stream.read(1024 * 1024):
                    digest.update(chunk)
                    byte_count += len(chunk)
                evidence = by_key[tar_member.name]
                if (
                    _HASH_PREFIX + digest.hexdigest() != evidence.content_hash
                    or byte_count != evidence.byte_count
                ):
                    return False
    except (KeyError, OSError, tarfile.TarError, ValueError):
        return False
    return _retained_manifest_metadata_matches(capture)


def _trusted_capture_for_boundary(
    value: object,
) -> BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1 | None:
    if type(value) is not BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1:
        return None
    try:
        if value.request.authority is None:
            return _trusted_capture(value)
        trusted_request = _trusted_source_request(value.request)
        if (
            trusted_request is None
            or type(value.archive_attempts) is not int
            or not 1 <= value.archive_attempts <= _MAX_ATTEMPTS
            or type(value.checksum_attempts) is not int
            or not 1 <= value.checksum_attempts <= _MAX_ATTEMPTS
            or type(value.decision_grade_eligible) is not bool
            or value.decision_grade_eligible
            or type(value.deployment_authorized) is not bool
            or value.deployment_authorized
            or not _snapshot_metadata_matches_retained_request(value)
        ):
            return None
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        return None
    return value


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruExecutionBoundaryV1:
    boundary: UtcInstant
    cutoff: UtcInstant

    def __post_init__(self) -> None:
        if (
            type(self.boundary) is not UtcInstant
            or type(self.cutoff) is not UtcInstant
            or self.boundary >= self.cutoff
        ):
            raise ValueError("execution boundary must bind boundary < cutoff")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_execution_boundary_v1",
            "schema_version": _SCHEMA_VERSION,
            "boundary": self.boundary,
            "cutoff": self.cutoff,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1:
    captures: tuple[BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1, ...]
    timeline_window_start: UtcInstant
    timeline_window_end_exclusive: UtcInstant
    boundaries: tuple[BinanceUsdmKoruExecutionBoundaryV1, ...]

    def __post_init__(self) -> None:
        if (
            type(self.timeline_window_start) is not UtcInstant
            or type(self.timeline_window_end_exclusive) is not UtcInstant
            or self.timeline_window_start >= self.timeline_window_end_exclusive
        ):
            raise ValueError("timeline window must be a nonempty half-open interval")
        if (
            type(self.captures) is not tuple
            or not self.captures
            or any(
                type(capture)
                is not BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1
                for capture in self.captures
            )
        ):
            raise TypeError("captures must be an exact nonempty capture tuple")
        expected_dates = _requested_dates(
            self.timeline_window_start, self.timeline_window_end_exclusive
        )
        if (
            tuple(capture.request.utc_date for capture in self.captures)
            != expected_dates
        ):
            raise ValueError("captures must exact-cover timeline UTC dates in order")
        if any(
            _trusted_capture_for_boundary(capture) is None
            for capture in self.captures
        ):
            raise ValueError("captures must replay exact official or retained evidence")
        if type(self.boundaries) is not tuple or any(
            type(boundary) is not BinanceUsdmKoruExecutionBoundaryV1
            for boundary in self.boundaries
        ):
            raise TypeError("boundaries must be an exact boundary tuple")
        boundary_values = tuple(
            boundary.boundary.epoch_nanoseconds for boundary in self.boundaries
        )
        if boundary_values != tuple(sorted(set(boundary_values))):
            raise ValueError("boundaries must be sorted and unique")
        if any(
            boundary.boundary < self.timeline_window_start
            or boundary.boundary >= self.timeline_window_end_exclusive
            or boundary.cutoff > self.timeline_window_end_exclusive
            for boundary in self.boundaries
        ):
            raise ValueError("boundaries must stay inside the timeline window")

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_aggregate_trade_boundary_index_request_v1",
            "schema_version": _SCHEMA_VERSION,
            "captures": [capture.to_canonical_dict() for capture in self.captures],
            "timeline_window_start": self.timeline_window_start,
            "timeline_window_end_exclusive": self.timeline_window_end_exclusive,
            "boundaries": [
                boundary.to_canonical_dict() for boundary in self.boundaries
            ],
        }


def _trusted_request(
    value: object,
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1 | None:
    if type(value) is not BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1(
            value.captures,
            value.timeline_window_start,
            value.timeline_window_end_exclusive,
            value.boundaries,
        )
        if canonical_bytes(rebuilt.to_canonical_dict()) != canonical_bytes(
            value.to_canonical_dict()
        ):
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruSelectedAggregateTradeLineageV1:
    boundary: UtcInstant
    cutoff: UtcInstant
    source_event: MarketEvent
    source_event_hash: str
    utc_date: str
    csv_row_ordinal: int
    csv_row_hash: str
    aggregate_trade_id: int
    first_trade_id: int
    last_trade_id: int
    transaction_time_milliseconds: int
    price: str
    source_snapshot_id: str
    source_snapshot_hash: str
    source_provenance_hash: str
    source_member_key: str
    source_member_hash: str
    archive_member_key: str
    archive_member_hash: str
    request_hash: str
    capture_hash: str
    lineage_hash: str = field(init=False)

    def __post_init__(self) -> None:
        payload = (
            self.source_event.payload if type(self.source_event) is MarketEvent else {}
        )
        if (
            type(self.boundary) is not UtcInstant
            or type(self.cutoff) is not UtcInstant
            or type(self.source_event) is not MarketEvent
            or not self.boundary <= self.source_event.event_time < self.cutoff
            or type(self.utc_date) is not str
            or self.utc_date != _utc_date(self.source_event.event_time)
            or type(self.csv_row_ordinal) is not int
            or self.csv_row_ordinal <= 0
            or type(self.aggregate_trade_id) is not int
            or type(self.first_trade_id) is not int
            or type(self.last_trade_id) is not int
            or not 0 <= self.first_trade_id <= self.last_trade_id
            or type(self.transaction_time_milliseconds) is not int
            or self.transaction_time_milliseconds < 0
            or self.source_event.event_time.epoch_nanoseconds
            != self.transaction_time_milliseconds * 1_000_000
            or type(self.price) is not str
            or not self.price
            or payload.get("aggregate_trade_id") != self.aggregate_trade_id
            or payload.get("first_trade_id") != self.first_trade_id
            or payload.get("last_trade_id") != self.last_trade_id
            or payload.get("transaction_time_milliseconds")
            != self.transaction_time_milliseconds
            or payload.get("price") != self.price
            or payload.get("source_record_hash") != self.csv_row_hash
            or payload.get("source_snapshot_id") != self.source_snapshot_id
            or payload.get("source_snapshot_hash") != self.source_snapshot_hash
            or payload.get("source_provenance_hash") != self.source_provenance_hash
            or payload.get("source_member_key") != self.source_member_key
            or payload.get("source_member_hash") != self.source_member_hash
            or payload.get("archive_member_key") != self.archive_member_key
            or payload.get("archive_member_hash") != self.archive_member_hash
            or payload.get("request_hash") != self.request_hash
            or payload.get("capture_hash") != self.capture_hash
        ):
            raise ValueError("selected aggregate-trade lineage binding mismatch")
        for name in (
            "source_event_hash",
            "csv_row_hash",
            "source_snapshot_hash",
            "source_provenance_hash",
            "source_member_hash",
            "archive_member_hash",
            "request_hash",
            "capture_hash",
        ):
            _hash(name, getattr(self, name))
        if self.source_event_hash != self.source_event.event_hash:
            raise ValueError("selected source event hash mismatch")
        for name in (
            "source_snapshot_id",
            "source_member_key",
            "archive_member_key",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value or value != value.strip():
                raise ValueError(f"{name} must be canonical text")
        object.__setattr__(self, "lineage_hash", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_selected_aggregate_trade_lineage_v1",
            "schema_version": _SCHEMA_VERSION,
            "boundary": self.boundary,
            "cutoff": self.cutoff,
            "source_event": self.source_event,
            "source_event_hash": self.source_event_hash,
            "utc_date": self.utc_date,
            "csv_row_ordinal": self.csv_row_ordinal,
            "csv_row_hash": self.csv_row_hash,
            "aggregate_trade_id": self.aggregate_trade_id,
            "first_trade_id": self.first_trade_id,
            "last_trade_id": self.last_trade_id,
            "transaction_time_milliseconds": self.transaction_time_milliseconds,
            "price": self.price,
            "source_snapshot_id": self.source_snapshot_id,
            "source_snapshot_hash": self.source_snapshot_hash,
            "source_provenance_hash": self.source_provenance_hash,
            "source_member_key": self.source_member_key,
            "source_member_hash": self.source_member_hash,
            "archive_member_key": self.archive_member_key,
            "archive_member_hash": self.archive_member_hash,
            "request_hash": self.request_hash,
            "capture_hash": self.capture_hash,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "lineage_hash": self.lineage_hash}


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruMissingAggregateTradeBoundaryV1:
    boundary: UtcInstant
    cutoff: UtcInstant
    reason: str = _MISSING_REASON
    missing_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.boundary) is not UtcInstant
            or type(self.cutoff) is not UtcInstant
            or self.boundary >= self.cutoff
            or self.reason != _MISSING_REASON
        ):
            raise ValueError("missing aggregate-trade boundary binding mismatch")
        object.__setattr__(self, "missing_hash", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_missing_aggregate_trade_boundary_v1",
            "schema_version": _SCHEMA_VERSION,
            "boundary": self.boundary,
            "cutoff": self.cutoff,
            "reason": self.reason,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "missing_hash": self.missing_hash}


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1:
    previous_aggregate_trade_id: int
    current_aggregate_trade_id: int
    previous_transaction_time_milliseconds: int
    current_transaction_time_milliseconds: int
    missing_first_aggregate_trade_id: int
    missing_last_aggregate_trade_id: int
    missing_aggregate_trade_count: int
    declared_missing_interval_start: UtcInstant
    declared_missing_interval_end_exclusive: UtcInstant
    retained_authority_hash: str
    gap_hash: str = field(init=False)

    def __post_init__(self) -> None:
        values = (
            self.previous_aggregate_trade_id,
            self.current_aggregate_trade_id,
            self.previous_transaction_time_milliseconds,
            self.current_transaction_time_milliseconds,
            self.missing_first_aggregate_trade_id,
            self.missing_last_aggregate_trade_id,
            self.missing_aggregate_trade_count,
        )
        if any(type(value) is not int for value in values) or any(
            value < 0
            for value in (
                self.previous_aggregate_trade_id,
                self.current_aggregate_trade_id,
                self.previous_transaction_time_milliseconds,
                self.current_transaction_time_milliseconds,
                self.missing_aggregate_trade_count,
            )
        ):
            raise ValueError("aggregate-ID coverage gap values must be exact integers")
        if (
            self.current_aggregate_trade_id
            <= self.previous_aggregate_trade_id + 1
            or self.missing_first_aggregate_trade_id
            != self.previous_aggregate_trade_id + 1
            or self.missing_last_aggregate_trade_id
            != self.current_aggregate_trade_id - 1
            or self.missing_aggregate_trade_count <= 0
            or self.missing_aggregate_trade_count
            != self.current_aggregate_trade_id
            - self.previous_aggregate_trade_id
            - 1
            or type(self.declared_missing_interval_start) is not UtcInstant
            or type(self.declared_missing_interval_end_exclusive) is not UtcInstant
            or self.declared_missing_interval_start
            >= self.declared_missing_interval_end_exclusive
            or self.previous_transaction_time_milliseconds * 1_000_000
            >= self.declared_missing_interval_start.epoch_nanoseconds
            or self.current_transaction_time_milliseconds * 1_000_000
            < self.declared_missing_interval_end_exclusive.epoch_nanoseconds
        ):
            raise ValueError("aggregate-ID gap must bind the exact declared prefix")
        _hash("retained_authority_hash", self.retained_authority_hash)
        object.__setattr__(self, "gap_hash", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_aggregate_id_coverage_gap_evidence_v1",
            "schema_version": _SCHEMA_VERSION,
            "previous_aggregate_trade_id": self.previous_aggregate_trade_id,
            "current_aggregate_trade_id": self.current_aggregate_trade_id,
            "previous_transaction_time_milliseconds": self.previous_transaction_time_milliseconds,
            "current_transaction_time_milliseconds": self.current_transaction_time_milliseconds,
            "missing_first_aggregate_trade_id": self.missing_first_aggregate_trade_id,
            "missing_last_aggregate_trade_id": self.missing_last_aggregate_trade_id,
            "missing_aggregate_trade_count": self.missing_aggregate_trade_count,
            "declared_missing_interval_start": self.declared_missing_interval_start,
            "declared_missing_interval_end_exclusive": self.declared_missing_interval_end_exclusive,
            "retained_authority_hash": self.retained_authority_hash,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "gap_hash": self.gap_hash}


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruRawIdGapStreamEvidenceV1:
    gap_count: int
    missing_id_count: int
    chain_digest: str
    first_gap_hash: str | None
    last_gap_hash: str | None

    def __post_init__(self) -> None:
        if (
            type(self.gap_count) is not int
            or self.gap_count < 0
            or type(self.missing_id_count) is not int
            or self.missing_id_count < 0
            or (self.gap_count == 0)
            != (self.first_gap_hash is None and self.last_gap_hash is None)
        ):
            raise ValueError("raw-ID gap stream counts and bounds must be exact")
        _hash("chain_digest", self.chain_digest)
        if self.first_gap_hash is not None:
            _hash("first_gap_hash", self.first_gap_hash)
        if self.last_gap_hash is not None:
            _hash("last_gap_hash", self.last_gap_hash)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_raw_id_gap_stream_evidence_v1",
            "schema_version": _SCHEMA_VERSION,
            "gap_count": self.gap_count,
            "missing_id_count": self.missing_id_count,
            "chain_digest": self.chain_digest,
            "first_gap_hash": self.first_gap_hash,
            "last_gap_hash": self.last_gap_hash,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2:
    request: BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1
    selected_source_events: tuple[MarketEvent, ...]
    selected_lineage: tuple[BinanceUsdmKoruSelectedAggregateTradeLineageV1, ...]
    missing_boundaries: tuple[BinanceUsdmKoruMissingAggregateTradeBoundaryV1, ...]
    intra_day_raw_id_gap_stream: BinanceUsdmKoruRawIdGapStreamEvidenceV1
    cross_date_raw_id_gap_stream: BinanceUsdmKoruRawIdGapStreamEvidenceV1
    aggregate_id_coverage_gaps: tuple[
        BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1, ...
    ]
    streamed_row_count: int
    streamed_reconstruction_digest: str
    result_digest: str = field(init=False)
    development_only: bool = True
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if (
            type(self.request)
            is not BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1
        ):
            raise TypeError("boundary-index result request must be exact")
        if (
            type(self.selected_source_events) is not tuple
            or any(
                type(event) is not MarketEvent for event in self.selected_source_events
            )
            or len({event.event_id for event in self.selected_source_events})
            != len(self.selected_source_events)
            or type(self.selected_lineage) is not tuple
            or any(
                type(lineage) is not BinanceUsdmKoruSelectedAggregateTradeLineageV1
                for lineage in self.selected_lineage
            )
            or type(self.missing_boundaries) is not tuple
            or any(
                type(missing) is not BinanceUsdmKoruMissingAggregateTradeBoundaryV1
                for missing in self.missing_boundaries
            )
        ):
            raise ValueError("boundary-index selections must be exact immutable tuples")
        selected_by_id = {
            event.event_id: event for event in self.selected_source_events
        }
        if {lineage.source_event.event_id for lineage in self.selected_lineage} != set(
            selected_by_id
        ) or any(
            canonical_bytes(
                selected_by_id[lineage.source_event.event_id].to_canonical_dict()
            )
            != canonical_bytes(lineage.source_event.to_canonical_dict())
            for lineage in self.selected_lineage
        ):
            raise ValueError("selected source events must exact-cover selected lineage")
        resolved = tuple(
            sorted(
                (
                    *(
                        (
                            lineage.boundary.epoch_nanoseconds,
                            lineage.cutoff.epoch_nanoseconds,
                        )
                        for lineage in self.selected_lineage
                    ),
                    *(
                        (
                            missing.boundary.epoch_nanoseconds,
                            missing.cutoff.epoch_nanoseconds,
                        )
                        for missing in self.missing_boundaries
                    ),
                )
            )
        )
        expected = tuple(
            (
                boundary.boundary.epoch_nanoseconds,
                boundary.cutoff.epoch_nanoseconds,
            )
            for boundary in self.request.boundaries
        )
        if resolved != expected or len(resolved) != len(set(resolved)):
            raise ValueError("lineage and missing evidence must exact-cover boundaries")
        if (
            type(self.intra_day_raw_id_gap_stream)
            is not BinanceUsdmKoruRawIdGapStreamEvidenceV1
            or type(self.cross_date_raw_id_gap_stream)
            is not BinanceUsdmKoruRawIdGapStreamEvidenceV1
            or type(self.aggregate_id_coverage_gaps) is not tuple
            or any(
                type(gap) is not BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1
                for gap in self.aggregate_id_coverage_gaps
            )
            or len(self.aggregate_id_coverage_gaps) > len(self.request.captures) - 1
        ):
            raise TypeError("gap evidence must use exact bounded representations")
        if type(self.streamed_row_count) is not int or self.streamed_row_count <= 0:
            raise ValueError("streamed row count must be positive")
        _hash("streamed_reconstruction_digest", self.streamed_reconstruction_digest)
        if (
            type(self.development_only) is not bool
            or not self.development_only
            or type(self.decision_grade_eligible) is not bool
            or self.decision_grade_eligible
            or type(self.deployment_authorized) is not bool
            or self.deployment_authorized
        ):
            raise ValueError("boundary index must remain development-only")
        object.__setattr__(self, "result_digest", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_aggregate_trade_boundary_index_result_v2",
            "schema_version": 2,
            "request": self.request,
            "request_hash": self.request.request_hash,
            "selected_source_events": self.selected_source_events,
            "selected_lineage": self.selected_lineage,
            "missing_boundaries": self.missing_boundaries,
            "intra_day_raw_id_gap_stream": self.intra_day_raw_id_gap_stream,
            "cross_date_raw_id_gap_stream": self.cross_date_raw_id_gap_stream,
            "aggregate_id_coverage_gaps": self.aggregate_id_coverage_gaps,
            "streamed_row_count": self.streamed_row_count,
            "streamed_reconstruction_digest": self.streamed_reconstruction_digest,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


_MAX_CERTIFIED_RESULTS = 8
_CERTIFIED_RESULTS: OrderedDict[
    int,
    tuple[BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2, str, str],
] = OrderedDict()


def _result_fingerprint(
    value: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2,
) -> str:
    return canonical_sha256(
        {
            "result": value.to_canonical_dict(),
            "capture_archive_hashes": tuple(
                _sha256(capture.snapshot.archive_bytes)
                for capture in value.request.captures
            ),
        }
    )


def _certify_result(
    value: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2,
) -> None:
    key = id(value)
    _CERTIFIED_RESULTS[key] = (
        value,
        value.result_digest,
        _result_fingerprint(value),
    )
    _CERTIFIED_RESULTS.move_to_end(key)
    while len(_CERTIFIED_RESULTS) > _MAX_CERTIFIED_RESULTS:
        _CERTIFIED_RESULTS.popitem(last=False)


class BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1(str, Enum):
    REQUEST_INVALID = "request_invalid"
    CAPTURE_INVALID = "capture_invalid"
    BOUNDARY_INVALID = "boundary_invalid"
    SOURCE_INVALID = "source_invalid"
    DATA_GAP_DETECTED = "data_gap_detected"


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV1:
    code: BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1
    subject: str | None = None

    def __post_init__(self) -> None:
        if (
            type(self.code)
            is not BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1
        ):
            raise TypeError("boundary-index failure code must be exact")
        if self.subject is not None and (
            type(self.subject) is not str
            or not self.subject
            or self.subject != self.subject.strip()
        ):
            raise ValueError("failure subject must be canonical text or None")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_aggregate_trade_boundary_index_failure_v1",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV1:
    result: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2 | None = None
    failure: BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV1 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("boundary-index outcome must contain exactly one branch")
        if self.result is not None and _trusted_result(self.result) is None:
            raise ValueError("boundary-index outcome result must replay exactly")
        if (
            self.failure is not None
            and type(self.failure)
            is not BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV1
        ):
            raise TypeError("boundary-index outcome failure must be exact")


class _BoundaryIndexError(ValueError):
    def __init__(
        self,
        code: BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1,
        subject: str,
    ) -> None:
        super().__init__(subject)
        self.code = code
        self.subject = subject


def _archive_member_bytes(snapshot: SourceSnapshot, member_key: str) -> bytes:
    try:
        with tarfile.open(
            fileobj=io.BytesIO(snapshot.archive_bytes), mode="r:gz"
        ) as snapshot_archive:
            member = snapshot_archive.extractfile(member_key)
            if member is None:
                raise ValueError("archive member unavailable")
            return member.read()
    except (KeyError, OSError, tarfile.TarError, ValueError) as error:
        raise _BoundaryIndexError(
            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
            member_key,
        ) from error


def _archive_bytes(
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
    archive_key: str,
) -> bytes:
    return _archive_member_bytes(capture.snapshot, archive_key)


def _source_member_hash(zip_file: ZipFile, csv_name: str) -> str:
    digest = hashlib.sha256()
    try:
        with zip_file.open(csv_name) as member:
            while chunk := member.read(1024 * 1024):
                digest.update(chunk)
    except (KeyError, OSError, RuntimeError, ValueError) as error:
        raise _BoundaryIndexError(
            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
            csv_name,
        ) from error
    return _HASH_PREFIX + digest.hexdigest()


def _gap(
    previous: _ParsedRow, current: _ParsedRow
) -> BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1:
    return BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1(
        previous_aggregate_trade_id=previous.aggregate_trade_id,
        current_aggregate_trade_id=current.aggregate_trade_id,
        previous_last_trade_id=previous.last_trade_id,
        current_first_trade_id=current.first_trade_id,
        missing_first_trade_id=previous.last_trade_id + 1,
        missing_last_trade_id=current.first_trade_id - 1,
        missing_trade_count=current.first_trade_id - previous.last_trade_id - 1,
        previous_transaction_time_milliseconds=previous.transaction_time_milliseconds,
        current_transaction_time_milliseconds=current.transaction_time_milliseconds,
    )


class _GapStreamAccumulator:
    def __init__(self, scope: str, request_hash: str) -> None:
        self._scope = scope
        self.gap_count = 0
        self.missing_id_count = 0
        self.first_gap_hash: str | None = None
        self.last_gap_hash: str | None = None
        self.chain_digest = canonical_sha256(
            {
                "type": "binance_usdm_koru_raw_id_gap_stream_genesis_v1",
                "schema_version": _SCHEMA_VERSION,
                "scope": scope,
                "request_hash": request_hash,
            }
        )

    def add(self, gap: BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1) -> None:
        self.gap_count += 1
        self.missing_id_count += gap.missing_trade_count
        if self.first_gap_hash is None:
            self.first_gap_hash = gap.gap_hash
        self.last_gap_hash = gap.gap_hash
        self.chain_digest = canonical_sha256(
            {
                "type": "binance_usdm_koru_raw_id_gap_stream_link_v1",
                "schema_version": _SCHEMA_VERSION,
                "scope": self._scope,
                "previous_digest": self.chain_digest,
                "gap_ordinal": self.gap_count,
                "gap": gap,
            }
        )

    def evidence(self) -> BinanceUsdmKoruRawIdGapStreamEvidenceV1:
        return BinanceUsdmKoruRawIdGapStreamEvidenceV1(
            self.gap_count,
            self.missing_id_count,
            self.chain_digest,
            self.first_gap_hash,
            self.last_gap_hash,
        )


def _aggregate_coverage_gap(
    previous: _ParsedRow,
    current: _ParsedRow,
    authority_hash: str,
    missing_start: UtcInstant,
    missing_end: UtcInstant,
) -> BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1:
    return BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1(
        previous_aggregate_trade_id=previous.aggregate_trade_id,
        current_aggregate_trade_id=current.aggregate_trade_id,
        previous_transaction_time_milliseconds=previous.transaction_time_milliseconds,
        current_transaction_time_milliseconds=current.transaction_time_milliseconds,
        missing_first_aggregate_trade_id=previous.aggregate_trade_id + 1,
        missing_last_aggregate_trade_id=current.aggregate_trade_id - 1,
        missing_aggregate_trade_count=(
            current.aggregate_trade_id - previous.aggregate_trade_id - 1
        ),
        declared_missing_interval_start=missing_start,
        declared_missing_interval_end_exclusive=missing_end,
        retained_authority_hash=authority_hash,
    )


def _retained_raw_rows(
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
) -> Iterator[tuple[str, ...]]:
    authority = capture.request.authority
    if authority is None:
        raise ValueError("retained authority required")
    expected_keys = ("T", "a", "f", "l", "m", "nq", "p", "q")
    row_number = 0
    with tarfile.open(
        fileobj=io.BytesIO(capture.snapshot.archive_bytes), mode="r:gz"
    ) as archive:
        for page in authority.pages:
            member = archive.extractfile("retained/raw/" + page.member_name)
            if member is None:
                raise ValueError("retained page unavailable")
            raw_bytes = member.read()
            if _sha256(raw_bytes) != page.content_sha256:
                raise ValueError("retained page hash mismatch")
            try:
                values = json.loads(raw_bytes, object_pairs_hook=_json_object)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                raise ValueError("retained page must be exact JSON") from error
            if (
                type(values) is not list
                or not values
                or len(values) != page.row_count
                or len(values) > 1000
                or json.dumps(
                    values,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
                != raw_bytes
            ):
                raise ValueError("retained page JSON must be exact and page-bounded")
            first_id: int | None = None
            for item in values:
                row_number += 1
                if type(item) is not dict or tuple(item) != expected_keys:
                    raise ValueError("retained aggTrade JSON schema mismatch")
                if (
                    type(item["a"]) is not int
                    or type(item["f"]) is not int
                    or type(item["l"]) is not int
                    or type(item["T"]) is not int
                    or type(item["m"]) is not bool
                    or type(item["nq"]) is not str
                    or type(item["p"]) is not str
                    or type(item["q"]) is not str
                    or _DECIMAL.fullmatch(item["nq"]) is None
                ):
                    raise ValueError("retained aggTrade JSON value mismatch")
                exact_row = (
                    str(item["a"]),
                    item["p"],
                    item["q"],
                    str(item["f"]),
                    str(item["l"]),
                    str(item["T"]),
                    "true" if item["m"] else "false",
                )
                parsed = _parse_row(list(exact_row), row_number)
                if not (
                    page.request_start_time_milliseconds
                    <= parsed.transaction_time_milliseconds
                    <= page.request_end_time_milliseconds
                ):
                    raise ValueError("retained row falls outside request window")
                if first_id is None:
                    first_id = parsed.aggregate_trade_id
                yield exact_row
            if page.from_aggregate_trade_id is not None and (
                first_id != page.from_aggregate_trade_id
            ):
                raise ValueError("retained page fromId mismatch")


def _retained_dataset_matches(
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
    first: _ParsedRow,
    last: _ParsedRow,
    row_count: int,
) -> bool:
    manifest = _retained_manifest(capture)
    datasets = manifest.get("datasets")
    if type(datasets) is not dict:
        return False
    aggregate_trades = datasets.get("aggTrades")
    if type(aggregate_trades) is not dict:
        return False
    dataset = aggregate_trades.get("rest_2026_08_24")

    def utc_text(milliseconds: int) -> str:
        return datetime.fromtimestamp(milliseconds / 1000, tz=UTC).strftime(
            "%Y-%m-%dT%H:%M:%S.%fZ"
        )[:-4] + "Z"

    return _exact_mapping(
        dataset,
        {
            "covered_end_utc_exclusive": "2026-08-24T11:00:00.000Z",
            "covered_start_utc_inclusive": "2026-08-24T06:34:20.640Z",
            "max_aggregate_trade_id": last.aggregate_trade_id,
            "max_raw_trade_id": last.last_trade_id,
            "max_time_ms": last.transaction_time_milliseconds,
            "max_time_utc": utc_text(last.transaction_time_milliseconds),
            "min_aggregate_trade_id": first.aggregate_trade_id,
            "min_raw_trade_id": first.first_trade_id,
            "min_time_ms": first.transaction_time_milliseconds,
            "min_time_utc": utc_text(first.transaction_time_milliseconds),
            "provenance": "REST-derived; not an official archive",
            "row_count": row_count,
        },
    )


def _lineage(
    boundary: BinanceUsdmKoruExecutionBoundaryV1,
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
    row: _ParsedRow,
    row_ordinal: int,
    source_member_hash: str,
    event: MarketEvent,
) -> BinanceUsdmKoruSelectedAggregateTradeLineageV1:
    request = capture.request
    prefix = "derived/" if request.authority is not None else "archive/"
    archive_key = prefix + request.archive_name
    archive_member = _snapshot_member(capture.snapshot, archive_key)
    return BinanceUsdmKoruSelectedAggregateTradeLineageV1(
        boundary=boundary.boundary,
        cutoff=boundary.cutoff,
        source_event=event,
        source_event_hash=event.event_hash,
        utc_date=request.utc_date,
        csv_row_ordinal=row_ordinal,
        csv_row_hash=canonical_sha256(row.exact_row),
        aggregate_trade_id=row.aggregate_trade_id,
        first_trade_id=row.first_trade_id,
        last_trade_id=row.last_trade_id,
        transaction_time_milliseconds=row.transaction_time_milliseconds,
        price=row.price,
        source_snapshot_id=capture.snapshot.snapshot_id,
        source_snapshot_hash=canonical_sha256(capture.snapshot.to_canonical_dict()),
        source_provenance_hash=capture.snapshot.provenance_hash,
        source_member_key=request.csv_name,
        source_member_hash=source_member_hash,
        archive_member_key=archive_key,
        archive_member_hash=archive_member.content_hash,
        request_hash=request.request_hash,
        capture_hash=capture.capture_hash,
    )


def _missing(
    boundary: BinanceUsdmKoruExecutionBoundaryV1,
) -> BinanceUsdmKoruMissingAggregateTradeBoundaryV1:
    return BinanceUsdmKoruMissingAggregateTradeBoundaryV1(
        boundary.boundary, boundary.cutoff
    )


def _normalization_error(error: _NormalizationError) -> _BoundaryIndexError:
    code = (
        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.DATA_GAP_DETECTED
        if error.code
        is BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.DATA_GAP_DETECTED
        else BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID
    )
    subject = error.subject
    if error.row_number is not None:
        subject += f":row-{error.row_number}"
    return _BoundaryIndexError(code, subject)


def _build(
    request: BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1,
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2:
    resolutions: list[
        BinanceUsdmKoruSelectedAggregateTradeLineageV1
        | BinanceUsdmKoruMissingAggregateTradeBoundaryV1
        | None
    ] = [None] * len(request.boundaries)
    selected_events: dict[str, MarketEvent] = {}
    intra_day_gaps = _GapStreamAccumulator("intra_day", request.request_hash)
    cross_date_gaps = _GapStreamAccumulator("cross_date", request.request_hash)
    aggregate_coverage_gaps: list[
        BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1
    ] = []
    previous: _ParsedRow | None = None
    previous_date: str | None = None
    streamed_row_count = 0
    next_boundary = 0
    chain = canonical_sha256(
        {
            "type": "binance_usdm_koru_aggregate_trade_streamed_reconstruction_genesis_v1",
            "schema_version": _SCHEMA_VERSION,
            "request_hash": request.request_hash,
        }
    )

    for capture in request.captures:
        source_request = capture.request
        authority = source_request.authority
        if authority is not None:
            missing_start = authority.declared_missing_prefix_start
            missing_end = authority.declared_missing_prefix_end_exclusive
            for index, boundary in enumerate(request.boundaries):
                if missing_start <= boundary.boundary < missing_end:
                    resolutions[index] = _missing(boundary)
        prefix = "derived/" if authority is not None else "archive/"
        archive_key = prefix + source_request.archive_name
        archive = _archive_bytes(capture, archive_key)
        raw_rows = iter(_retained_raw_rows(capture)) if authority is not None else None
        capture_first: _ParsedRow | None = None
        capture_last: _ParsedRow | None = None
        archive_member = _snapshot_member(capture.snapshot, archive_key)
        if _sha256(archive) != archive_member.content_hash:
            raise _BoundaryIndexError(
                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                archive_key,
            )
        try:
            with ZipFile(io.BytesIO(archive)) as zip_file:
                if zip_file.namelist() != [source_request.csv_name]:
                    raise _BoundaryIndexError(
                        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                        "zip_member",
                    )
                source_member_hash = _source_member_hash(
                    zip_file, source_request.csv_name
                )
                if (
                    authority is not None
                    and source_member_hash != authority.derived_csv_sha256
                ):
                    raise _BoundaryIndexError(
                        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                        "derived_csv_hash",
                    )
                snapshot_hash = canonical_sha256(capture.snapshot.to_canonical_dict())
                row_ordinal = 0
                coverage_start = (
                    authority.selected_coverage_start.epoch_nanoseconds // 1_000_000
                    if authority is not None
                    else (
                        date.fromisoformat(source_request.utc_date) - _EPOCH_DATE
                    ).days
                    * (_DAY_NS // 1_000_000)
                )
                coverage_end = (
                    authority.selected_coverage_end_exclusive.epoch_nanoseconds
                    // 1_000_000
                    if authority is not None
                    else coverage_start + _DAY_NS // 1_000_000
                )
                with zip_file.open(source_request.csv_name) as binary_member:  # noqa: SIM117
                    with io.TextIOWrapper(
                        binary_member, encoding="utf-8", errors="strict", newline=""
                    ) as text_member:
                        header_pending = True
                        try:
                            for line in text_member:
                                if not line.endswith("\n") or "\r" in line:
                                    raise _BoundaryIndexError(
                                        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                                        "csv_encoding",
                                    )
                                try:
                                    values = next(csv.reader((line,), strict=True))
                                except csv.Error as error:
                                    raise _BoundaryIndexError(
                                        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                                        "csv",
                                    ) from error
                                if line != ",".join(values) + "\n":
                                    raise _BoundaryIndexError(
                                        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                                        "csv_grammar",
                                    )
                                if header_pending:
                                    header_pending = False
                                    if tuple(values) == _CSV_HEADER:
                                        continue
                                    if authority is not None or _is_csv_header_like(
                                        tuple(values), _CSV_HEADER
                                    ):
                                        raise _BoundaryIndexError(
                                            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                                            "csv_header",
                                        )
                                row_ordinal += 1
                                if raw_rows is not None:
                                    try:
                                        raw_values = next(raw_rows)
                                    except StopIteration as error:
                                        raise _BoundaryIndexError(
                                            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                                            f"raw_page_row_count:row-{row_ordinal}",
                                        ) from error
                                    if tuple(values) != raw_values:
                                        raise _BoundaryIndexError(
                                            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                                            f"derived_raw_row_mismatch:row-{row_ordinal}",
                                        )
                                try:
                                    current = _parse_row(values, row_ordinal)
                                except _NormalizationError as error:
                                    raise _normalization_error(error) from error
                                if not (
                                    coverage_start
                                    <= current.transaction_time_milliseconds
                                    < coverage_end
                                ):
                                    raise _BoundaryIndexError(
                                        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.DATA_GAP_DETECTED,
                                        f"transaction_time_window:row-{row_ordinal}",
                                    )
                                if capture_first is None:
                                    capture_first = current
                                capture_last = current
                                if previous is not None:
                                    aggregate_contiguous = (
                                        current.aggregate_trade_id
                                        == previous.aggregate_trade_id + 1
                                    )
                                    if not aggregate_contiguous:
                                        if (
                                            current.aggregate_trade_id
                                            > previous.aggregate_trade_id + 1
                                            and row_ordinal == 1
                                            and authority is not None
                                            and previous_date != source_request.utc_date
                                        ):
                                            try:
                                                aggregate_coverage_gaps.append(
                                                    _aggregate_coverage_gap(
                                                        previous,
                                                        current,
                                                        authority.authority_hash,
                                                        authority.declared_missing_prefix_start,
                                                        authority.declared_missing_prefix_end_exclusive,
                                                    )
                                                )
                                            except (TypeError, ValueError) as error:
                                                raise _BoundaryIndexError(
                                                    BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.DATA_GAP_DETECTED,
                                                    f"aggregate_trade_id_contiguity:row-{row_ordinal}",
                                                ) from error
                                        else:
                                            raise _BoundaryIndexError(
                                                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.DATA_GAP_DETECTED,
                                                f"aggregate_trade_id_contiguity:row-{row_ordinal}",
                                            )
                                    if current.first_trade_id <= previous.last_trade_id:
                                        raise _BoundaryIndexError(
                                            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.DATA_GAP_DETECTED,
                                            f"raw_trade_id_overlap:row-{row_ordinal}",
                                        )
                                    if (
                                        current.transaction_time_milliseconds
                                        < previous.transaction_time_milliseconds
                                    ):
                                        raise _BoundaryIndexError(
                                            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                                            f"transaction_time_order:row-{row_ordinal}",
                                        )
                                    if (
                                        aggregate_contiguous
                                        and current.first_trade_id
                                        > previous.last_trade_id + 1
                                    ):
                                        gaps = (
                                            intra_day_gaps
                                            if previous_date == source_request.utc_date
                                            else cross_date_gaps
                                        )
                                        gaps.add(_gap(previous, current))
                                streamed_row_count += 1
                                row_hash = canonical_sha256(current.exact_row)
                                chain = canonical_sha256(
                                    {
                                        "type": "binance_usdm_koru_aggregate_trade_streamed_reconstruction_link_v1",
                                        "schema_version": _SCHEMA_VERSION,
                                        "previous_digest": chain,
                                        "streamed_row_ordinal": streamed_row_count,
                                        "csv_row_ordinal": row_ordinal,
                                        "csv_row_hash": row_hash,
                                        "utc_date": source_request.utc_date,
                                        "source_member_hash": source_member_hash,
                                        "source_snapshot_hash": snapshot_hash,
                                        "source_request_hash": source_request.request_hash,
                                        "source_capture_hash": capture.capture_hash,
                                    }
                                )
                                event_time = (
                                    current.transaction_time_milliseconds * 1_000_000
                                )
                                while (
                                    next_boundary < len(request.boundaries)
                                    and request.boundaries[
                                        next_boundary
                                    ].boundary.epoch_nanoseconds
                                    <= event_time
                                ):
                                    boundary = request.boundaries[next_boundary]
                                    if resolutions[next_boundary] is None:
                                        if (
                                            event_time
                                            < boundary.cutoff.epoch_nanoseconds
                                        ):
                                            try:
                                                event = _event_from_row(
                                                    capture,
                                                    current,
                                                    row_ordinal - 1,
                                                    source_member_hash,
                                                )
                                                selected_events.setdefault(
                                                    event.event_id, event
                                                )
                                                resolutions[next_boundary] = _lineage(
                                                    boundary,
                                                    capture,
                                                    current,
                                                    row_ordinal,
                                                    source_member_hash,
                                                    event,
                                                )
                                            except (TypeError, ValueError) as error:
                                                raise _BoundaryIndexError(
                                                    BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                                                    "market_event",
                                                ) from error
                                        else:
                                            resolutions[next_boundary] = _missing(
                                                boundary
                                            )
                                    next_boundary += 1
                                previous = current
                                previous_date = source_request.utc_date
                        except UnicodeDecodeError as error:
                            raise _BoundaryIndexError(
                                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                                "csv_encoding",
                            ) from error
                        if header_pending or row_ordinal == 0:
                            raise _BoundaryIndexError(
                                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.DATA_GAP_DETECTED,
                                f"row_count:{source_request.utc_date}",
                            )
                        if raw_rows is not None:
                            if next(raw_rows, None) is not None:
                                raise _BoundaryIndexError(
                                    BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                                    "raw_page_row_count",
                                )
                            if (
                                capture_first is None
                                or capture_last is None
                                or not _retained_dataset_matches(
                                    capture, capture_first, capture_last, row_ordinal
                                )
                            ):
                                raise _BoundaryIndexError(
                                    BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                                    "retained_dataset",
                                )
        except _BoundaryIndexError:
            raise
        except (
            BadZipFile,
            KeyError,
            NotImplementedError,
            OSError,
            RuntimeError,
            ValueError,
        ) as error:
            raise _BoundaryIndexError(
                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                source_request.archive_name,
            ) from error

    for index, boundary in enumerate(request.boundaries):
        if resolutions[index] is None:
            resolutions[index] = _missing(boundary)
    selected_lineage = tuple(
        value
        for value in resolutions
        if type(value) is BinanceUsdmKoruSelectedAggregateTradeLineageV1
    )
    missing_boundaries = tuple(
        value
        for value in resolutions
        if type(value) is BinanceUsdmKoruMissingAggregateTradeBoundaryV1
    )
    return BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2(
        request=request,
        selected_source_events=tuple(selected_events.values()),
        selected_lineage=selected_lineage,
        missing_boundaries=missing_boundaries,
        intra_day_raw_id_gap_stream=intra_day_gaps.evidence(),
        cross_date_raw_id_gap_stream=cross_date_gaps.evidence(),
        aggregate_id_coverage_gaps=tuple(aggregate_coverage_gaps),
        streamed_row_count=streamed_row_count,
        streamed_reconstruction_digest=chain,
    )


def _request_failure(
    value: object,
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV1 | None:
    if type(value) is not BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1:
        return BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV1(
            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.REQUEST_INVALID,
            "request",
        )
    try:
        if (
            type(value.timeline_window_start) is not UtcInstant
            or type(value.timeline_window_end_exclusive) is not UtcInstant
            or value.timeline_window_start >= value.timeline_window_end_exclusive
            or type(value.captures) is not tuple
            or not value.captures
            or tuple(capture.request.utc_date for capture in value.captures)
            != _requested_dates(
                value.timeline_window_start, value.timeline_window_end_exclusive
            )
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV1(
            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.REQUEST_INVALID,
            "request",
        )
    if any(
        _trusted_capture_for_boundary(capture) is None
        for capture in value.captures
    ):
        return BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV1(
            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.CAPTURE_INVALID,
            "captures",
        )
    try:
        boundary_values = tuple(
            boundary.boundary.epoch_nanoseconds for boundary in value.boundaries
        )
        if (
            type(value.boundaries) is not tuple
            or any(
                type(boundary) is not BinanceUsdmKoruExecutionBoundaryV1
                or boundary.boundary >= boundary.cutoff
                or boundary.boundary < value.timeline_window_start
                or boundary.boundary >= value.timeline_window_end_exclusive
                or boundary.cutoff > value.timeline_window_end_exclusive
                for boundary in value.boundaries
            )
            or boundary_values != tuple(sorted(set(boundary_values)))
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV1(
            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.BOUNDARY_INVALID,
            "boundaries",
        )
    if _trusted_request(value) is None:
        return BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV1(
            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.REQUEST_INVALID,
            "request",
        )
    return None


def build_binance_usdm_koru_aggregate_trade_boundary_index_v1(
    request: BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV1,
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV1:
    failure = _request_failure(request)
    if failure is not None:
        return BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV1(failure=failure)
    trusted = _trusted_request(request)
    if trusted is None:
        raise AssertionError("validated boundary-index request must replay")
    try:
        result = _build(trusted)
        _certify_result(result)
        return BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV1(result=result)
    except _BoundaryIndexError as error:
        return BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV1(
            failure=BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV1(
                error.code, error.subject
            )
        )
    except (AttributeError, TypeError, ValueError):
        return BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV1(
            failure=BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV1(
                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1.SOURCE_INVALID,
                "result",
            )
        )


def _trusted_result(
    value: object,
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2 | None:
    if type(value) is not BinanceUsdmKoruAggregateTradeBoundaryIndexResultV2:
        return None
    certified = _CERTIFIED_RESULTS.get(id(value))
    if certified is not None:
        try:
            matches = (
                certified[0] is value
                and certified[1] == value.result_digest
                and certified[2] == _result_fingerprint(value)
            )
        except (AttributeError, TypeError, ValueError):
            matches = False
        if matches:
            _CERTIFIED_RESULTS.move_to_end(id(value))
            return value
        _CERTIFIED_RESULTS.pop(id(value), None)
    try:
        trusted_request = _trusted_request(value.request)
        if trusted_request is None:
            return None
        replay = _build(trusted_request)
        if canonical_bytes(replay.to_canonical_dict()) != canonical_bytes(
            value.to_canonical_dict()
        ):
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return replay


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3:
    """One-pass KORU aggregate-trade boundary-index request."""

    captures: tuple[BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1, ...]
    timeline_window_start: UtcInstant
    timeline_window_end_exclusive: UtcInstant
    boundaries: tuple[BinanceUsdmKoruExecutionBoundaryV1, ...]

    def __post_init__(self) -> None:
        if (
            type(self.timeline_window_start) is not UtcInstant
            or type(self.timeline_window_end_exclusive) is not UtcInstant
            or self.timeline_window_start >= self.timeline_window_end_exclusive
        ):
            raise ValueError("timeline window must be a nonempty half-open interval")
        if (
            type(self.captures) is not tuple
            or not self.captures
            or any(
                type(capture)
                is not BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1
                for capture in self.captures
            )
        ):
            raise TypeError("captures must be an exact nonempty capture tuple")
        if tuple(capture.request.utc_date for capture in self.captures) != _requested_dates(
            self.timeline_window_start, self.timeline_window_end_exclusive
        ):
            raise ValueError("captures must exact-cover timeline UTC dates in order")
        if any(_trusted_capture_for_boundary(capture) is None for capture in self.captures):
            raise ValueError("captures must replay exact official or retained evidence")
        if type(self.boundaries) is not tuple or any(
            type(boundary) is not BinanceUsdmKoruExecutionBoundaryV1
            for boundary in self.boundaries
        ):
            raise TypeError("boundaries must be an exact boundary tuple")
        boundary_values = tuple(
            boundary.boundary.epoch_nanoseconds for boundary in self.boundaries
        )
        if boundary_values != tuple(sorted(set(boundary_values))):
            raise ValueError("boundaries must be sorted and unique")
        if any(
            boundary.boundary < self.timeline_window_start
            or boundary.boundary >= self.timeline_window_end_exclusive
            or boundary.cutoff > self.timeline_window_end_exclusive
            for boundary in self.boundaries
        ):
            raise ValueError("boundaries must stay inside the timeline window")

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_aggregate_trade_boundary_index_request_v3",
            "schema_version": 3,
            "captures": [capture.to_canonical_dict() for capture in self.captures],
            "timeline_window_start": self.timeline_window_start,
            "timeline_window_end_exclusive": self.timeline_window_end_exclusive,
            "boundaries": [
                boundary.to_canonical_dict() for boundary in self.boundaries
            ],
        }


def _trusted_request_v3(
    value: object,
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3 | None:
    if type(value) is not BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3:
        return None
    try:
        rebuilt = BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3(
            value.captures,
            value.timeline_window_start,
            value.timeline_window_end_exclusive,
            value.boundaries,
        )
        if canonical_bytes(rebuilt.to_canonical_dict()) != canonical_bytes(
            value.to_canonical_dict()
        ):
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradeCaptureFinalEvidenceV3:
    capture_ordinal: int
    utc_date: str
    source_member_hash: str
    final_row_chain_digest: str
    source_snapshot_hash: str
    source_request_hash: str
    source_capture_hash: str
    selected_boundary_indexes: tuple[int, ...]
    missing_boundary_indexes: tuple[int, ...]
    capture_final_digest: str = field(init=False)

    def __post_init__(self) -> None:
        if (
            type(self.capture_ordinal) is not int
            or self.capture_ordinal <= 0
            or type(self.utc_date) is not str
            or not self.utc_date
            or type(self.selected_boundary_indexes) is not tuple
            or type(self.missing_boundary_indexes) is not tuple
            or any(type(index) is not int or index < 0 for index in self.selected_boundary_indexes)
            or any(type(index) is not int or index < 0 for index in self.missing_boundary_indexes)
            or self.selected_boundary_indexes != tuple(sorted(set(self.selected_boundary_indexes)))
            or self.missing_boundary_indexes != tuple(sorted(set(self.missing_boundary_indexes)))
            or set(self.selected_boundary_indexes) & set(self.missing_boundary_indexes)
        ):
            raise ValueError("capture-final boundary indexes must be exact and disjoint")
        for name in (
            "source_member_hash",
            "final_row_chain_digest",
            "source_snapshot_hash",
            "source_request_hash",
            "source_capture_hash",
        ):
            _hash(name, getattr(self, name))
        object.__setattr__(self, "capture_final_digest", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_aggregate_trade_capture_final_evidence_v3",
            "schema_version": 3,
            "capture_ordinal": self.capture_ordinal,
            "utc_date": self.utc_date,
            "source_member_hash": self.source_member_hash,
            "final_row_chain_digest": self.final_row_chain_digest,
            "source_snapshot_hash": self.source_snapshot_hash,
            "source_request_hash": self.source_request_hash,
            "source_capture_hash": self.source_capture_hash,
            "selected_boundary_indexes": self.selected_boundary_indexes,
            "missing_boundary_indexes": self.missing_boundary_indexes,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "capture_final_digest": self.capture_final_digest}


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3:
    request: BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3
    selected_source_events: tuple[MarketEvent, ...]
    selected_lineage: tuple[BinanceUsdmKoruSelectedAggregateTradeLineageV1, ...]
    missing_boundaries: tuple[BinanceUsdmKoruMissingAggregateTradeBoundaryV1, ...]
    intra_day_raw_id_gap_stream: BinanceUsdmKoruRawIdGapStreamEvidenceV1
    cross_date_raw_id_gap_stream: BinanceUsdmKoruRawIdGapStreamEvidenceV1
    aggregate_id_coverage_gaps: tuple[BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1, ...]
    streamed_row_count: int
    streamed_reconstruction_digest: str
    capture_final_evidence: tuple[BinanceUsdmKoruAggregateTradeCaptureFinalEvidenceV3, ...]
    result_digest: str = field(init=False)
    development_only: bool = True
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if type(self.request) is not BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3:
            raise TypeError("boundary-index result request must be exact")
        if (
            type(self.selected_source_events) is not tuple
            or any(type(event) is not MarketEvent for event in self.selected_source_events)
            or len({event.event_id for event in self.selected_source_events})
            != len(self.selected_source_events)
            or type(self.selected_lineage) is not tuple
            or any(type(lineage) is not BinanceUsdmKoruSelectedAggregateTradeLineageV1 for lineage in self.selected_lineage)
            or type(self.missing_boundaries) is not tuple
            or any(type(missing) is not BinanceUsdmKoruMissingAggregateTradeBoundaryV1 for missing in self.missing_boundaries)
        ):
            raise ValueError("boundary-index selections must be exact immutable tuples")
        selected_by_id = {event.event_id: event for event in self.selected_source_events}
        if {lineage.source_event.event_id for lineage in self.selected_lineage} != set(selected_by_id) or any(
            canonical_bytes(selected_by_id[lineage.source_event.event_id].to_canonical_dict())
            != canonical_bytes(lineage.source_event.to_canonical_dict())
            for lineage in self.selected_lineage
        ):
            raise ValueError("selected source events must exact-cover selected lineage")
        resolved = tuple(
            sorted(
                (
                    *((lineage.boundary.epoch_nanoseconds, lineage.cutoff.epoch_nanoseconds) for lineage in self.selected_lineage),
                    *((missing.boundary.epoch_nanoseconds, missing.cutoff.epoch_nanoseconds) for missing in self.missing_boundaries),
                )
            )
        )
        expected = tuple(
            (boundary.boundary.epoch_nanoseconds, boundary.cutoff.epoch_nanoseconds)
            for boundary in self.request.boundaries
        )
        if resolved != expected or len(resolved) != len(set(resolved)):
            raise ValueError("lineage and missing evidence must exact-cover boundaries")
        if (
            type(self.intra_day_raw_id_gap_stream) is not BinanceUsdmKoruRawIdGapStreamEvidenceV1
            or type(self.cross_date_raw_id_gap_stream) is not BinanceUsdmKoruRawIdGapStreamEvidenceV1
            or type(self.aggregate_id_coverage_gaps) is not tuple
            or any(type(gap) is not BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1 for gap in self.aggregate_id_coverage_gaps)
            or len(self.aggregate_id_coverage_gaps) > len(self.request.captures) - 1
            or type(self.streamed_row_count) is not int
            or self.streamed_row_count <= 0
            or type(self.capture_final_evidence) is not tuple
            or len(self.capture_final_evidence) != len(self.request.captures)
            or any(type(final) is not BinanceUsdmKoruAggregateTradeCaptureFinalEvidenceV3 for final in self.capture_final_evidence)
            or tuple(final.capture_ordinal for final in self.capture_final_evidence) != tuple(range(1, len(self.request.captures) + 1))
            or tuple(final.utc_date for final in self.capture_final_evidence) != tuple(capture.request.utc_date for capture in self.request.captures)
            or any(index >= len(self.request.boundaries) for final in self.capture_final_evidence for index in (*final.selected_boundary_indexes, *final.missing_boundary_indexes))
        ):
            raise ValueError("V3 stream evidence must be exact and bounded")
        _hash("streamed_reconstruction_digest", self.streamed_reconstruction_digest)
        if (
            type(self.development_only) is not bool
            or not self.development_only
            or type(self.decision_grade_eligible) is not bool
            or self.decision_grade_eligible
            or type(self.deployment_authorized) is not bool
            or self.deployment_authorized
        ):
            raise ValueError("boundary index must remain development-only")
        object.__setattr__(self, "result_digest", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_aggregate_trade_boundary_index_result_v3",
            "schema_version": 3,
            "request": self.request,
            "request_hash": self.request.request_hash,
            "selected_source_events": self.selected_source_events,
            "selected_lineage": self.selected_lineage,
            "missing_boundaries": self.missing_boundaries,
            "intra_day_raw_id_gap_stream": self.intra_day_raw_id_gap_stream,
            "cross_date_raw_id_gap_stream": self.cross_date_raw_id_gap_stream,
            "aggregate_id_coverage_gaps": self.aggregate_id_coverage_gaps,
            "streamed_row_count": self.streamed_row_count,
            "streamed_reconstruction_digest": self.streamed_reconstruction_digest,
            "capture_final_evidence": self.capture_final_evidence,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "result_digest": self.result_digest}


class BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3(str, Enum):
    REQUEST_INVALID = "request_invalid"
    CAPTURE_INVALID = "capture_invalid"
    BOUNDARY_INVALID = "boundary_invalid"
    SOURCE_INVALID = "source_invalid"
    DATA_GAP_DETECTED = "data_gap_detected"


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV3:
    code: BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3
    subject: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3:
            raise TypeError("boundary-index failure code must be exact")
        if self.subject is not None and (
            type(self.subject) is not str or not self.subject or self.subject != self.subject.strip()
        ):
            raise ValueError("failure subject must be canonical text or None")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_aggregate_trade_boundary_index_failure_v3",
            "schema_version": 3,
            "code": self.code.value,
            "subject": self.subject,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV3:
    result: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3 | None = None
    failure: BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV3 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("boundary-index outcome must contain exactly one branch")
        if self.result is not None and _trusted_result_v3(self.result) is None:
            raise ValueError("boundary-index outcome result must replay exactly")
        if self.failure is not None and type(self.failure) is not BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV3:
            raise TypeError("boundary-index outcome failure must be exact")


class _V3BoundaryIndexError(ValueError):
    def __init__(
        self,
        code: BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3,
        subject: str,
    ) -> None:
        super().__init__(subject)
        self.code = code
        self.subject = subject


@dataclass(frozen=True, slots=True)
class _V3SelectedCandidate:
    boundary_index: int
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1
    row: _ParsedRow
    csv_row_ordinal: int


def _v3_failure_code(
    code: BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV1,
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3:
    return BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3(code.value)


def _build_v3(
    request: BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3,
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3:
    resolutions: list[BinanceUsdmKoruSelectedAggregateTradeLineageV1 | BinanceUsdmKoruMissingAggregateTradeBoundaryV1 | None] = [None] * len(request.boundaries)
    selected_events: dict[str, MarketEvent] = {}
    intra_day_gaps = _GapStreamAccumulator("intra_day", request.request_hash)
    cross_date_gaps = _GapStreamAccumulator("cross_date", request.request_hash)
    aggregate_coverage_gaps: list[BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1] = []
    capture_finals: list[BinanceUsdmKoruAggregateTradeCaptureFinalEvidenceV3] = []
    previous: _ParsedRow | None = None
    previous_date: str | None = None
    streamed_row_count = 0
    next_boundary = 0
    prefix_boundary = 0
    chain = canonical_sha256(
        {
            "type": "binance_usdm_koru_aggregate_trade_streamed_reconstruction_genesis_v3",
            "schema_version": 3,
            "request_hash": request.request_hash,
        }
    )

    for capture_index, capture in enumerate(request.captures, start=1):
        source_request = capture.request
        authority = source_request.authority
        resolved_indexes: set[int] = set()
        if authority is not None:
            missing_start = authority.declared_missing_prefix_start
            missing_end = authority.declared_missing_prefix_end_exclusive
            while (
                prefix_boundary < len(request.boundaries)
                and request.boundaries[prefix_boundary].boundary < missing_end
            ):
                boundary = request.boundaries[prefix_boundary]
                if missing_start <= boundary.boundary and resolutions[prefix_boundary] is None:
                    resolutions[prefix_boundary] = _missing(boundary)
                    resolved_indexes.add(prefix_boundary)
                prefix_boundary += 1
        prefix = "derived/" if authority is not None else "archive/"
        archive_key = prefix + source_request.archive_name
        try:
            archive = _archive_bytes(capture, archive_key)
        except _BoundaryIndexError as error:
            raise _V3BoundaryIndexError(_v3_failure_code(error.code), error.subject) from error
        raw_rows = iter(_retained_raw_rows(capture)) if authority is not None else None
        capture_first: _ParsedRow | None = None
        capture_last: _ParsedRow | None = None
        archive_member = _snapshot_member(capture.snapshot, archive_key)
        if _sha256(archive) != archive_member.content_hash:
            raise _V3BoundaryIndexError(
                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                archive_key,
            )
        candidates: list[_V3SelectedCandidate] = []
        try:
            with ZipFile(io.BytesIO(archive)) as zip_file:
                if zip_file.namelist() != [source_request.csv_name]:
                    raise _V3BoundaryIndexError(
                        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                        "zip_member",
                    )
                snapshot_hash = canonical_sha256(capture.snapshot.to_canonical_dict())
                coverage_start = (
                    authority.selected_coverage_start.epoch_nanoseconds // 1_000_000
                    if authority is not None
                    else (date.fromisoformat(source_request.utc_date) - _EPOCH_DATE).days * (_DAY_NS // 1_000_000)
                )
                coverage_end = (
                    authority.selected_coverage_end_exclusive.epoch_nanoseconds // 1_000_000
                    if authority is not None
                    else coverage_start + _DAY_NS // 1_000_000
                )
                row_ordinal = 0
                header_pending = True
                member_digest = hashlib.sha256()
                with zip_file.open(source_request.csv_name) as binary_member:
                    for binary_line in binary_member:
                        member_digest.update(binary_line)
                        try:
                            line = binary_line.decode("utf-8", errors="strict")
                        except UnicodeDecodeError as error:
                            raise _V3BoundaryIndexError(
                                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                                "csv_encoding",
                            ) from error
                        if not line.endswith("\n") or "\r" in line:
                            raise _V3BoundaryIndexError(
                                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                                "csv_encoding",
                            )
                        try:
                            values = next(csv.reader((line,), strict=True))
                        except csv.Error as error:
                            raise _V3BoundaryIndexError(
                                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                                "csv",
                            ) from error
                        if line != ",".join(values) + "\n":
                            raise _V3BoundaryIndexError(
                                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                                "csv_grammar",
                            )
                        if header_pending:
                            header_pending = False
                            if tuple(values) == _CSV_HEADER:
                                continue
                            if authority is not None or _is_csv_header_like(tuple(values), _CSV_HEADER):
                                raise _V3BoundaryIndexError(
                                    BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                                    "csv_header",
                                )
                        row_ordinal += 1
                        if raw_rows is not None:
                            try:
                                raw_values = next(raw_rows)
                            except StopIteration as error:
                                raise _V3BoundaryIndexError(
                                    BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                                    f"raw_page_row_count:row-{row_ordinal}",
                                ) from error
                            if tuple(values) != raw_values:
                                raise _V3BoundaryIndexError(
                                    BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                                    f"derived_raw_row_mismatch:row-{row_ordinal}",
                                )
                        try:
                            current = _parse_row(values, row_ordinal)
                        except _NormalizationError as error:
                            normalized = _normalization_error(error)
                            raise _V3BoundaryIndexError(
                                _v3_failure_code(normalized.code), normalized.subject
                            ) from error
                        if not coverage_start <= current.transaction_time_milliseconds < coverage_end:
                            raise _V3BoundaryIndexError(
                                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.DATA_GAP_DETECTED,
                                f"transaction_time_window:row-{row_ordinal}",
                            )
                        if capture_first is None:
                            capture_first = current
                        capture_last = current
                        if previous is not None:
                            aggregate_contiguous = current.aggregate_trade_id == previous.aggregate_trade_id + 1
                            if not aggregate_contiguous:
                                if (
                                    current.aggregate_trade_id > previous.aggregate_trade_id + 1
                                    and row_ordinal == 1
                                    and authority is not None
                                    and previous_date != source_request.utc_date
                                ):
                                    try:
                                        aggregate_coverage_gaps.append(_aggregate_coverage_gap(
                                            previous,
                                            current,
                                            authority.authority_hash,
                                            authority.declared_missing_prefix_start,
                                            authority.declared_missing_prefix_end_exclusive,
                                        ))
                                    except (TypeError, ValueError) as error:
                                        raise _V3BoundaryIndexError(
                                            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.DATA_GAP_DETECTED,
                                            f"aggregate_trade_id_contiguity:row-{row_ordinal}",
                                        ) from error
                                else:
                                    raise _V3BoundaryIndexError(
                                        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.DATA_GAP_DETECTED,
                                        f"aggregate_trade_id_contiguity:row-{row_ordinal}",
                                    )
                            if current.first_trade_id <= previous.last_trade_id:
                                raise _V3BoundaryIndexError(
                                    BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.DATA_GAP_DETECTED,
                                    f"raw_trade_id_overlap:row-{row_ordinal}",
                                )
                            if current.transaction_time_milliseconds < previous.transaction_time_milliseconds:
                                raise _V3BoundaryIndexError(
                                    BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                                    f"transaction_time_order:row-{row_ordinal}",
                                )
                            if aggregate_contiguous and current.first_trade_id > previous.last_trade_id + 1:
                                (intra_day_gaps if previous_date == source_request.utc_date else cross_date_gaps).add(_gap(previous, current))
                        streamed_row_count += 1
                        chain = canonical_sha256(
                            {
                                "type": "binance_usdm_koru_aggregate_trade_streamed_reconstruction_row_link_v3",
                                "schema_version": 3,
                                "previous_digest": chain,
                                "streamed_row_ordinal": streamed_row_count,
                                "csv_row_ordinal": row_ordinal,
                                "csv_row_hash": canonical_sha256(current.exact_row),
                                "utc_date": source_request.utc_date,
                                "source_snapshot_hash": snapshot_hash,
                                "source_request_hash": source_request.request_hash,
                                "source_capture_hash": capture.capture_hash,
                            }
                        )
                        event_time = current.transaction_time_milliseconds * 1_000_000
                        while (
                            next_boundary < len(request.boundaries)
                            and request.boundaries[next_boundary].boundary.epoch_nanoseconds <= event_time
                        ):
                            boundary = request.boundaries[next_boundary]
                            if resolutions[next_boundary] is None:
                                if event_time < boundary.cutoff.epoch_nanoseconds:
                                    candidates.append(_V3SelectedCandidate(
                                        next_boundary, capture, current, row_ordinal
                                    ))
                                else:
                                    resolutions[next_boundary] = _missing(boundary)
                                    resolved_indexes.add(next_boundary)
                            next_boundary += 1
                        previous = current
                        previous_date = source_request.utc_date
                if header_pending or row_ordinal == 0:
                    raise _V3BoundaryIndexError(
                        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.DATA_GAP_DETECTED,
                        f"row_count:{source_request.utc_date}",
                    )
                source_member_hash = _HASH_PREFIX + member_digest.hexdigest()
                if authority is not None and source_member_hash != authority.derived_csv_sha256:
                    raise _V3BoundaryIndexError(
                        BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                        "derived_csv_hash",
                    )
                if raw_rows is not None:
                    if next(raw_rows, None) is not None:
                        raise _V3BoundaryIndexError(
                            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                            "raw_page_row_count",
                        )
                    if (
                        capture_first is None
                        or capture_last is None
                        or not _retained_dataset_matches(capture, capture_first, capture_last, row_ordinal)
                    ):
                        raise _V3BoundaryIndexError(
                            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                            "retained_dataset",
                        )
        except _V3BoundaryIndexError:
            raise
        except (BadZipFile, KeyError, NotImplementedError, OSError, RuntimeError, ValueError) as error:
            raise _V3BoundaryIndexError(
                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                source_request.archive_name,
            ) from error
        for candidate in candidates:
            try:
                event = _event_from_row(
                    candidate.capture,
                    candidate.row,
                    candidate.csv_row_ordinal - 1,
                    source_member_hash,
                )
                selected_events.setdefault(event.event_id, event)
                resolutions[candidate.boundary_index] = _lineage(
                    request.boundaries[candidate.boundary_index],
                    candidate.capture,
                    candidate.row,
                    candidate.csv_row_ordinal,
                    source_member_hash,
                    event,
                )
                resolved_indexes.add(candidate.boundary_index)
            except (TypeError, ValueError) as error:
                raise _V3BoundaryIndexError(
                    BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                    "market_event",
                ) from error
        if capture_index == len(request.captures):
            for index, boundary in enumerate(request.boundaries):
                if resolutions[index] is None:
                    resolutions[index] = _missing(boundary)
                    resolved_indexes.add(index)
        final_row_chain_digest = chain
        final = BinanceUsdmKoruAggregateTradeCaptureFinalEvidenceV3(
            capture_index,
            source_request.utc_date,
            source_member_hash,
            final_row_chain_digest,
            snapshot_hash,
            source_request.request_hash,
            capture.capture_hash,
            tuple(sorted(
                index for index in resolved_indexes
                if type(resolutions[index]) is BinanceUsdmKoruSelectedAggregateTradeLineageV1
            )),
            tuple(sorted(
                index for index in resolved_indexes
                if type(resolutions[index]) is BinanceUsdmKoruMissingAggregateTradeBoundaryV1
            )),
        )
        capture_finals.append(final)
        chain = canonical_sha256(
            {
                "type": "binance_usdm_koru_aggregate_trade_streamed_reconstruction_capture_final_link_v3",
                "schema_version": 3,
                "previous_digest": final_row_chain_digest,
                "capture_final": final,
            }
        )

    selected_lineage = tuple(
        value for value in resolutions
        if type(value) is BinanceUsdmKoruSelectedAggregateTradeLineageV1
    )
    missing_boundaries = tuple(
        value for value in resolutions
        if type(value) is BinanceUsdmKoruMissingAggregateTradeBoundaryV1
    )
    return BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3(
        request=request,
        selected_source_events=tuple(selected_events.values()),
        selected_lineage=selected_lineage,
        missing_boundaries=missing_boundaries,
        intra_day_raw_id_gap_stream=intra_day_gaps.evidence(),
        cross_date_raw_id_gap_stream=cross_date_gaps.evidence(),
        aggregate_id_coverage_gaps=tuple(aggregate_coverage_gaps),
        streamed_row_count=streamed_row_count,
        streamed_reconstruction_digest=chain,
        capture_final_evidence=tuple(capture_finals),
    )


def _request_failure_v3(
    value: object,
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV3 | None:
    if type(value) is not BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3:
        return BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV3(
            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.REQUEST_INVALID,
            "request",
        )
    try:
        if (
            type(value.timeline_window_start) is not UtcInstant
            or type(value.timeline_window_end_exclusive) is not UtcInstant
            or value.timeline_window_start >= value.timeline_window_end_exclusive
            or type(value.captures) is not tuple
            or not value.captures
            or tuple(capture.request.utc_date for capture in value.captures)
            != _requested_dates(value.timeline_window_start, value.timeline_window_end_exclusive)
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV3(
            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.REQUEST_INVALID,
            "request",
        )
    if any(_trusted_capture_for_boundary(capture) is None for capture in value.captures):
        return BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV3(
            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.CAPTURE_INVALID,
            "captures",
        )
    try:
        boundary_values = tuple(boundary.boundary.epoch_nanoseconds for boundary in value.boundaries)
        if (
            type(value.boundaries) is not tuple
            or any(
                type(boundary) is not BinanceUsdmKoruExecutionBoundaryV1
                or boundary.boundary >= boundary.cutoff
                or boundary.boundary < value.timeline_window_start
                or boundary.boundary >= value.timeline_window_end_exclusive
                or boundary.cutoff > value.timeline_window_end_exclusive
                for boundary in value.boundaries
            )
            or boundary_values != tuple(sorted(set(boundary_values)))
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV3(
            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.BOUNDARY_INVALID,
            "boundaries",
        )
    if _trusted_request_v3(value) is None:
        return BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV3(
            BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.REQUEST_INVALID,
            "request",
        )
    return None


_MAX_CERTIFIED_RESULTS_V3 = 8
_CERTIFIED_RESULTS_V3: OrderedDict[
    int, tuple[BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3, str, str]
] = OrderedDict()


def _result_fingerprint_v3(
    value: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3,
) -> str:
    return canonical_sha256(
        {
            "result": value.to_canonical_dict(),
            "capture_archive_hashes": tuple(
                _sha256(capture.snapshot.archive_bytes)
                for capture in value.request.captures
            ),
        }
    )


def _certify_result_v3(value: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3) -> None:
    key = id(value)
    _CERTIFIED_RESULTS_V3[key] = (
        value,
        value.result_digest,
        _result_fingerprint_v3(value),
    )
    _CERTIFIED_RESULTS_V3.move_to_end(key)
    while len(_CERTIFIED_RESULTS_V3) > _MAX_CERTIFIED_RESULTS_V3:
        _CERTIFIED_RESULTS_V3.popitem(last=False)


def build_binance_usdm_koru_aggregate_trade_boundary_index_v3(
    request: BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3,
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV3:
    failure = _request_failure_v3(request)
    if failure is not None:
        return BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV3(failure=failure)
    trusted = _trusted_request_v3(request)
    if trusted is None:
        raise AssertionError("validated boundary-index request must replay")
    try:
        result = _build_v3(trusted)
        _certify_result_v3(result)
        return BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV3(result=result)
    except _V3BoundaryIndexError as error:
        return BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV3(
            failure=BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV3(error.code, error.subject)
        )
    except (AttributeError, TypeError, ValueError):
        return BinanceUsdmKoruAggregateTradeBoundaryIndexOutcomeV3(
            failure=BinanceUsdmKoruAggregateTradeBoundaryIndexFailureV3(
                BinanceUsdmKoruAggregateTradeBoundaryIndexFailureCodeV3.SOURCE_INVALID,
                "result",
            )
        )


def _trusted_result_v3(
    value: object,
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3 | None:
    if type(value) is not BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3:
        return None
    certified = _CERTIFIED_RESULTS_V3.get(id(value))
    if certified is not None:
        try:
            matches = (
                certified[0] is value
                and certified[1] == value.result_digest
                and certified[2] == _result_fingerprint_v3(value)
            )
        except (AttributeError, TypeError, ValueError):
            matches = False
        if matches:
            _CERTIFIED_RESULTS_V3.move_to_end(id(value))
            return value
        _CERTIFIED_RESULTS_V3.pop(id(value), None)
    try:
        trusted_request = _trusted_request_v3(value.request)
        if trusted_request is None:
            return None
        replay = _build_v3(trusted_request)
        if canonical_bytes(replay.to_canonical_dict()) != canonical_bytes(value.to_canonical_dict()):
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return replay

KORU_AGGREGATE_TRADE_BOUNDARY_INDEX_AUTHORITY_ARTIFACT_TYPE_V3 = (
    "binance_usdm_koru_aggregate_trade_boundary_index_authority_v3"
)
KORU_AGGREGATE_TRADE_BOUNDARY_INDEX_AUTHORITY_SCHEMA_VERSION_V3 = 3
_BOUNDARY_AUTHORITY_PAYLOAD_FIELDS_V3 = frozenset(
    {
        "type",
        "schema_version",
        "builder",
        "raw_snapshot_authority_identity",
        "raw_snapshot_id",
        "boundary_index_identity",
        "capture_bindings",
        "boundary_index_result",
    }
)


def _authority_registry_v3() -> dict[str, type[object]]:
    """Whitelist only value models needed to reconstruct a V3 boundary result."""
    from crypto_quant_domain import artifacts, instruments, time
    from crypto_quant_domain.numeric import scales
    from crypto_quant_market_data import bundles

    from . import binance_usdm_koru_aggtrades_source_bounded_v1, source_snapshots

    registry: dict[str, type[object]] = {}
    for module in (
        artifacts,
        instruments,
        time,
        scales,
        bundles,
        binance_usdm_koru_aggtrades_source_bounded_v1,
        source_snapshots,
    ):
        for value in vars(module).values():
            if (
                isinstance(value, type)
                and value.__module__ == module.__name__
                and (is_dataclass(value) or issubclass(value, Enum))
            ):
                registry[f"{value.__module__}.{value.__qualname__}"] = value
    for value in (
        BinanceUsdmKoruAggregateTradeBoundaryIndexRequestV3,
        BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3,
        BinanceUsdmKoruAggregateTradeCaptureFinalEvidenceV3,
        BinanceUsdmKoruExecutionBoundaryV1,
        BinanceUsdmKoruSelectedAggregateTradeLineageV1,
        BinanceUsdmKoruMissingAggregateTradeBoundaryV1,
        BinanceUsdmKoruRawIdGapStreamEvidenceV1,
        BinanceUsdmKoruAggregateIdCoverageGapEvidenceV1,
    ):
        registry[f"{__name__}.{value.__qualname__}"] = value
    return registry


def _authority_encode_v3(value: object) -> dict[str, object]:
    registry = _authority_registry_v3()

    def encode(item: object) -> dict[str, object]:
        if item is None or type(item) in (bool, int, str):
            return {"kind": "scalar", "value": item}
        if type(item) is bytes:
            return {"kind": "bytes", "base64": base64.b64encode(item).decode("ascii")}
        if isinstance(item, Enum):
            type_id = f"{type(item).__module__}.{type(item).__qualname__}"
            if registry.get(type_id) is not type(item):
                raise TypeError("boundary authority contains an unsupported enum")
            return {"kind": "enum", "type": type_id, "value": item.value}
        if type(item) is tuple:
            return {"kind": "tuple", "items": [encode(child) for child in item]}
        if isinstance(item, Mapping):
            keys = tuple(sorted(item))
            if any(type(key) is not str for key in keys):
                raise TypeError("boundary authority mappings must use string keys")
            return {
                "kind": "mapping",
                "items": [[key, encode(item[key])] for key in keys],
            }
        if is_dataclass(item) and not isinstance(item, type):
            type_id = f"{type(item).__module__}.{type(item).__qualname__}"
            if registry.get(type_id) is not type(item):
                raise TypeError("boundary authority contains an unsupported model")
            return {
                "kind": "model",
                "type": type_id,
                "fields": [
                    [model_field.name, encode(getattr(item, model_field.name))]
                    for model_field in fields(item)
                    if model_field.init
                ],
            }
        raise TypeError("boundary authority contains an unsupported value")

    return encode(value)


def _authority_decode_v3(value: object) -> object:
    registry = _authority_registry_v3()

    def exact(node: object, keys: frozenset[str]) -> dict[str, object]:
        if type(node) is not dict or set(node) != keys:
            raise ValueError("boundary authority serialization schema mismatch")
        return node

    def decode(item: object) -> object:
        if type(item) is not dict or type(item.get("kind")) is not str:
            raise ValueError("boundary authority serialization schema mismatch")
        kind = item["kind"]
        expected_keys = {
            "scalar": frozenset({"kind", "value"}),
            "bytes": frozenset({"kind", "base64"}),
            "enum": frozenset({"kind", "type", "value"}),
            "tuple": frozenset({"kind", "items"}),
            "mapping": frozenset({"kind", "items"}),
            "model": frozenset({"kind", "type", "fields"}),
        }.get(kind)
        if expected_keys is None:
            raise ValueError("boundary authority serialization schema mismatch")
        node = exact(item, expected_keys)
        if kind == "scalar":
            if node["value"] is None or type(node["value"]) in (bool, int, str):
                return node["value"]
        elif kind == "bytes":
            encoded = node["base64"]
            if type(encoded) is str:
                try:
                    decoded_bytes = base64.b64decode(encoded, validate=True)
                except ValueError as error:
                    raise ValueError("boundary authority bytes are invalid") from error
                if base64.b64encode(decoded_bytes).decode("ascii") == encoded:
                    return decoded_bytes
        elif kind == "enum":
            type_id, enum_value = node["type"], node["value"]
            enum_type = registry.get(type_id) if type(type_id) is str else None
            if enum_type is not None and issubclass(enum_type, Enum):
                return enum_type(enum_value)
        elif kind == "tuple" and type(node["items"]) is list:
            return tuple(decode(child) for child in node["items"])
        elif kind == "mapping" and type(node["items"]) is list:
            decoded: dict[str, object] = {}
            previous = ""
            for entry in node["items"]:
                if (
                    type(entry) is not list
                    or len(entry) != 2
                    or type(entry[0]) is not str
                    or entry[0] <= previous
                ):
                    raise ValueError("boundary authority mapping order is invalid")
                previous = entry[0]
                decoded[entry[0]] = decode(entry[1])
            return decoded
        elif kind == "model":
            type_id, model_fields = node["type"], node["fields"]
            model_type = registry.get(type_id) if type(type_id) is str else None
            if (
                model_type is not None
                and is_dataclass(model_type)
                and type(model_fields) is list
            ):
                expected = tuple(
                    model_field.name
                    for model_field in fields(model_type)
                    if model_field.init
                )
                if (
                    len(model_fields) == len(expected)
                    and all(
                        type(entry) is list
                        and len(entry) == 2
                        and type(entry[0]) is str
                        for entry in model_fields
                    )
                    and tuple(entry[0] for entry in model_fields) == expected
                ):
                    return model_type(
                        **{entry[0]: decode(entry[1]) for entry in model_fields}
                    )
        raise ValueError("boundary authority serialization value is invalid")

    return decode(value)


def _canonical_authority_mapping_v3(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"{name} must be a non-empty canonical object")
    try:
        decoded = json.loads(canonical_bytes(value).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{name} must be canonical JSON") from error
    if type(decoded) is not dict or canonical_bytes(decoded) != canonical_bytes(value):
        raise ValueError(f"{name} must be a canonical object")
    return decoded


def _raw_member_bindings_v3(
    result: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3,
    raw_snapshot_view: RawBlobSnapshotView,
) -> tuple[dict[str, object], ...]:
    if type(raw_snapshot_view) is not RawBlobSnapshotView:
        raise TypeError("raw_snapshot_view must be a RawBlobSnapshotView")
    raw_members = raw_snapshot_view.manifest.members
    bindings: list[dict[str, object]] = []
    for ordinal, capture in enumerate(result.request.captures, start=1):
        source_members: list[dict[str, object]] = []
        for source_member in capture.snapshot.members:
            matches = tuple(
                raw_member
                for raw_member in raw_members
                if (
                    raw_member.raw_blob_ref.content_hash == source_member.content_hash
                    and raw_member.raw_blob_ref.byte_count == source_member.byte_count
                    and raw_member.mode == source_member.mode
                )
            )
            if len(matches) != 1:
                raise ValueError("raw snapshot must bind each source member exactly once")
            raw_member = matches[0]
            source_members.append(
                {
                    "source_member_key": source_member.member_key,
                    "source_member_hash": source_member.content_hash,
                    "source_member_byte_count": source_member.byte_count,
                    "raw_snapshot_member_key": raw_member.member_key,
                    "raw_blob_ref": raw_member.raw_blob_ref.to_canonical_dict(),
                }
            )
        retained_pages: list[dict[str, object]] = []
        authority = capture.request.authority
        if authority is not None:
            source_by_key = {item["source_member_key"]: item for item in source_members}
            for page in authority.pages:
                source = source_by_key.get("retained/raw/" + page.member_name)
                if source is None or source["source_member_hash"] != page.content_sha256:
                    raise ValueError("retained raw page does not bind its source member")
                retained_pages.append(
                    {
                        "member_name": page.member_name,
                        "content_sha256": page.content_sha256,
                        "raw_snapshot_member_key": source["raw_snapshot_member_key"],
                    }
                )
        bindings.append(
            {
                "capture_ordinal": ordinal,
                "utc_date": capture.request.utc_date,
                "capture_hash": capture.capture_hash,
                "source_snapshot_id": capture.snapshot.snapshot_id,
                "source_snapshot_hash": canonical_sha256(capture.snapshot.to_canonical_dict()),
                "source_members": source_members,
                "retained_raw_pages": retained_pages,
            }
        )
    return tuple(bindings)


def _boundary_index_identity_v3(
    result: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3,
) -> dict[str, object]:
    value = {
        "request_hash": result.request.request_hash,
        "result_digest": result.result_digest,
        "ordered_boundaries": [
            boundary.to_canonical_dict() for boundary in result.request.boundaries
        ],
        "selected_lineage": [
            lineage.to_canonical_dict() for lineage in result.selected_lineage
        ],
        "missing_boundaries": [
            missing.to_canonical_dict() for missing in result.missing_boundaries
        ],
        "intra_day_raw_id_gap_stream": result.intra_day_raw_id_gap_stream.to_canonical_dict(),
        "cross_date_raw_id_gap_stream": result.cross_date_raw_id_gap_stream.to_canonical_dict(),
        "aggregate_id_coverage_gaps": [
            gap.to_canonical_dict() for gap in result.aggregate_id_coverage_gaps
        ],
        "streamed_reconstruction_digest": result.streamed_reconstruction_digest,
        "capture_final_evidence": [
            final.to_canonical_dict() for final in result.capture_final_evidence
        ],
    }
    return json.loads(canonical_bytes(value).decode("utf-8"))


def _boundary_authority_payload_v3(
    result: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3,
    raw_snapshot_view: RawBlobSnapshotView,
    raw_snapshot_authority_identity: Mapping[str, object],
) -> dict[str, object]:
    trusted = _trusted_result_v3(result)
    if trusted is None:
        raise ValueError("result must be an exact canonical V3 boundary result")
    raw_identity = _canonical_authority_mapping_v3(
        raw_snapshot_authority_identity, "raw_snapshot_authority_identity"
    )
    return {
        "type": KORU_AGGREGATE_TRADE_BOUNDARY_INDEX_AUTHORITY_ARTIFACT_TYPE_V3,
        "schema_version": KORU_AGGREGATE_TRADE_BOUNDARY_INDEX_AUTHORITY_SCHEMA_VERSION_V3,
        "builder": {
            "id": "binance_usdm_koru_aggregate_trade_boundary_index_v3",
            "result_type": "binance_usdm_koru_aggregate_trade_boundary_index_result_v3",
            "result_schema_version": 3,
        },
        "raw_snapshot_authority_identity": raw_identity,
        "raw_snapshot_id": raw_snapshot_view.manifest.snapshot_id,
        "boundary_index_identity": _boundary_index_identity_v3(trusted),
        "capture_bindings": list(_raw_member_bindings_v3(trusted, raw_snapshot_view)),
        "boundary_index_result": _authority_encode_v3(trusted),
    }


def create_binance_usdm_koru_aggregate_trade_boundary_index_authority_v3(
    result: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3,
    raw_snapshot_view: RawBlobSnapshotView,
    raw_snapshot_authority_identity: Mapping[str, object],
) -> tuple[ArtifactEnvelope, ArtifactRef]:
    """Create a V3 boundary authority; Foundation publication belongs to Research."""
    envelope = ArtifactEnvelope.create(
        KORU_AGGREGATE_TRADE_BOUNDARY_INDEX_AUTHORITY_ARTIFACT_TYPE_V3,
        KORU_AGGREGATE_TRADE_BOUNDARY_INDEX_AUTHORITY_SCHEMA_VERSION_V3,
        _boundary_authority_payload_v3(
            result, raw_snapshot_view, raw_snapshot_authority_identity
        ),
    )
    ref = ArtifactRef.from_envelope(envelope)
    if ref.content_hash == result.result_digest:
        raise ValueError("authority artifact identity must differ from result digest")
    return envelope, ref


def serialize_binance_usdm_koru_aggregate_trade_boundary_index_authority_v3(
    result: BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3,
    raw_snapshot_view: RawBlobSnapshotView,
    raw_snapshot_authority_identity: Mapping[str, object],
) -> bytes:
    envelope, _ = create_binance_usdm_koru_aggregate_trade_boundary_index_authority_v3(
        result, raw_snapshot_view, raw_snapshot_authority_identity
    )
    return canonical_bytes(envelope)


def _boundary_authority_envelope_from_bytes_v3(source: bytes) -> ArtifactEnvelope:
    if type(source) is not bytes:
        raise TypeError("boundary authority envelope must be bytes")
    try:
        value = json.loads(source.decode("utf-8"))
        envelope = ArtifactEnvelope(
            value["artifact_type"],
            value["schema_version"],
            value["payload"],
            value["content_hash"],
        )
    except (KeyError, TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("boundary authority envelope is invalid") from error
    if (
        type(value) is not dict
        or set(value) != {"artifact_type", "schema_version", "payload", "content_hash"}
        or canonical_bytes(envelope) != source
    ):
        raise ValueError("boundary authority envelope must use exact canonical bytes")
    return envelope


def open_binance_usdm_koru_aggregate_trade_boundary_index_authority_v3(
    source: bytes,
    artifact_ref: ArtifactRef,
    raw_snapshot_view: RawBlobSnapshotView,
    raw_snapshot_authority_identity: Mapping[str, object],
) -> BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3:
    """Open published V3 bytes from bound raw blobs without aggregate-row replay."""
    if type(artifact_ref) is not ArtifactRef:
        raise TypeError("artifact_ref must be an ArtifactRef")
    envelope = _boundary_authority_envelope_from_bytes_v3(source)
    if (
        envelope.artifact_type
        != KORU_AGGREGATE_TRADE_BOUNDARY_INDEX_AUTHORITY_ARTIFACT_TYPE_V3
        or envelope.schema_version
        != KORU_AGGREGATE_TRADE_BOUNDARY_INDEX_AUTHORITY_SCHEMA_VERSION_V3
        or ArtifactRef.from_envelope(envelope) != artifact_ref
    ):
        raise ValueError("boundary authority envelope/ref schema is unsupported")
    try:
        payload = json.loads(canonical_bytes(envelope.payload).decode("utf-8"))
    except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("boundary authority payload schema is invalid") from error
    if type(payload) is not dict or set(payload) != _BOUNDARY_AUTHORITY_PAYLOAD_FIELDS_V3:
        raise ValueError("boundary authority payload schema is invalid")
    if (
        payload["type"] != KORU_AGGREGATE_TRADE_BOUNDARY_INDEX_AUTHORITY_ARTIFACT_TYPE_V3
        or payload["schema_version"] != KORU_AGGREGATE_TRADE_BOUNDARY_INDEX_AUTHORITY_SCHEMA_VERSION_V3
        or payload["builder"]
        != {
            "id": "binance_usdm_koru_aggregate_trade_boundary_index_v3",
            "result_type": "binance_usdm_koru_aggregate_trade_boundary_index_result_v3",
            "result_schema_version": 3,
        }
        or payload["raw_snapshot_id"] != raw_snapshot_view.manifest.snapshot_id
        or _canonical_authority_mapping_v3(
            payload["raw_snapshot_authority_identity"],
            "raw_snapshot_authority_identity",
        )
        != _canonical_authority_mapping_v3(
            raw_snapshot_authority_identity,
            "raw_snapshot_authority_identity",
        )
        or type(payload["capture_bindings"]) is not list
        or type(payload["boundary_index_identity"]) is not dict
    ):
        raise ValueError("boundary authority identity binding is invalid")
    try:
        rebuilt = _authority_decode_v3(payload["boundary_index_result"])
    except (IndexError, RecursionError, TypeError, ValueError) as error:
        raise ValueError("boundary authority cannot reconstruct typed result") from error
    if type(rebuilt) is not BinanceUsdmKoruAggregateTradeBoundaryIndexResultV3:
        raise ValueError("boundary authority result type is invalid")
    if (
        _boundary_index_identity_v3(rebuilt) != payload["boundary_index_identity"]
        or list(_raw_member_bindings_v3(rebuilt, raw_snapshot_view))
        != payload["capture_bindings"]
    ):
        raise ValueError("boundary authority evidence or raw bindings are invalid")
    # Do not call _trusted_result_v3 here: reopening must never replay aggregate rows.
    return rebuilt
