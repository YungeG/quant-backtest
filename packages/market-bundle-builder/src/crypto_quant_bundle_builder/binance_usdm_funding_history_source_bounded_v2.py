from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, localcontext
from enum import Enum
from typing import cast

from crypto_quant_domain import (
    InstrumentId,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import (
    MarketBundleCapability,
    MarketBundleManifest,
    MarketBundleRef,
    MarketEvent,
)

from .bundle_validation import validate_market_bundle_v1
from .source_snapshots import (
    RawSourceMember,
    SourceSnapshot,
    SourceSnapshotMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

_SCHEMA_VERSION = 2
_PROVIDER_KEY = "binance.fapi"
_DATASETS = ("fundingRate",)
_INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "btc-usdt-perpetual")
_MEMBER_KEY = "response/funding-history.json"
_SOURCE_KEY = "binance.fapi.funding_rate_history.btcusdt.1704067200000.1704153599999"
_COVERAGE_START = UtcInstant(1_704_067_200_000_000_000)
_COVERAGE_END_EXCLUSIVE = UtcInstant(1_704_153_600_000_000_000)
_FUNDING_TIMES = (1_704_067_200_000, 1_704_096_000_000, 1_704_124_800_000)
_REQUEST = {
    "type": "binance_usdm_funding_history_acquisition_request",
    "schema_version": 1,
    "symbol": "BTCUSDT",
    "start_time_milliseconds": 1_704_067_200_000,
    "end_time_milliseconds": 1_704_153_599_999,
    "limit": 100,
    "url": (
        "https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&"
        "startTime=1704067200000&endTime=1704153599999&limit=100"
    ),
}
_REQUEST_SCOPE_HASH = canonical_sha256(_REQUEST)
_RESPONSE_FIELDS = ("symbol", "fundingTime", "fundingRate", "markPrice", "rateType")
_RATE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,18})?\Z")
_MARK = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,18})?\Z")
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SCALE = 8
_STREAM_KEY = "binance_usdm.funding_history.publications.btcusdt.v2"
_EVENT_TYPE = "binance_usdm_funding_history_publication.v2"
_CAPABILITY = MarketBundleCapability("binance_usdm.funding-publications", 2)
_PHASE = TimelinePhase(0, "market_data")
_BUNDLE_KEY = "binance-usdm-funding-history-btcusdt-2024-01-01-source-bounded-v2"
_CATALOG_HASH = "sha256:" + "0" * 64
_LIMITATIONS = (
    "permanent_provider_checksum_unavailable",
    "future_revision_finality_unknown",
    "provider_correction_lineage_unavailable",
    "provider_completeness_unknown",
    "current_api_capture_is_not_immutable_publication",
    "local_observation_time_is_late_for_event_time",
    "single_symbol_single_day_scope",
    "instrument_catalog_authority_unavailable",
)
_RECEIPT_KEYS = {
    "acquired_at_epoch_nanoseconds",
    "attempts",
    "decision_grade_eligible",
    "deployment_authorized",
    "missing_mark_price_count",
    "record_count",
    "request",
    "response_sha256",
    "schema_version",
    "snapshot",
    "type",
}
_REQUEST_KEYS = {
    "end_time_milliseconds",
    "limit",
    "schema_version",
    "start_time_milliseconds",
    "symbol",
    "type",
    "url",
}

_SourceRow = tuple[str, int, str, str, str]


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _exact_int(name: str, value: object, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an exact integer")
    return value


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _reject_constant(_: str) -> object:
    raise ValueError("non-finite JSON constant")


def _json(value: bytes) -> object:
    return json.loads(
        value.decode("utf-8"),
        parse_constant=_reject_constant,
        object_pairs_hook=_unique_object,
    )


def _reconstruct_snapshot(value: object) -> SourceSnapshot | None:
    if type(value) is not SourceSnapshot:
        return None
    try:
        provenance = SourceSnapshotProvenance(
            value.provenance.vendor_key,
            value.provenance.source_key,
            value.provenance.license_ref,
            value.provenance.retention_policy_ref,
        )
        members = tuple(
            SourceSnapshotMember(
                member.member_key,
                member.content_hash,
                member.byte_count,
                member.mode,
                member.acquired_at_epoch_nanoseconds,
                member.declared_sha256,
            )
            for member in value.members
        )
        rebuilt = SourceSnapshot(
            value.snapshot_id,
            value.archive_bytes,
            value.content_tree_hash,
            members,
            provenance,
            value.provenance_hash,
            value.decision_grade_eligible,
            value.deployment_authorized,
        )
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt if rebuilt == value else None


class _FailureCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    EVIDENCE_INVALID = "evidence_invalid"
    REQUEST_SCOPE_MISMATCH = "request_scope_mismatch"
    RESPONSE_SCHEMA_MISMATCH = "response_schema_mismatch"
    RESPONSE_SCOPE_MISMATCH = "response_scope_mismatch"
    NORMALIZATION_FAILED = "normalization_failed"
    LOOKAHEAD_VIOLATION = "lookahead_violation"
    PUBLICATION_FAILED = "publication_failed"
    PREDECESSOR_INVALID = "predecessor_invalid"
    CORRECTION_EDGE_INVALID = "correction_edge_invalid"
    REPORT_BINDING_MISMATCH = "report_binding_mismatch"


@dataclass(frozen=True, slots=True)
class _Failure:
    code: _FailureCode
    member_key: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not _FailureCode:
            raise TypeError("code must be exact failure code")
        if self.member_key is not None and self.member_key != _MEMBER_KEY:
            raise ValueError("member_key must be the declared response member")

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_history_source_bounded_observation_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "member_key": self.member_key,
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "failure_hash": self.failure_hash}


@dataclass(frozen=True, slots=True)
class _ParsedResponse:
    rows: tuple[tuple[str, int, str, str, str], ...]


@dataclass(frozen=True, slots=True)
class _NormalizedRow:
    source_row: _SourceRow
    source_record_hash: str
    funding_rate: str
    funding_rate_units: int
    mark_price: str
    mark_price_units: int


@dataclass(frozen=True, slots=True)
class _BuiltPublication:
    events: tuple[MarketEvent, ...]
    stream_payload: bytes
    manifest: MarketBundleManifest
    bundle_ref: MarketBundleRef


def _source_record_hash(row: _SourceRow) -> str:
    return canonical_sha256({"fields": _RESPONSE_FIELDS, "row": row})


def _response_bytes(rows: tuple[_SourceRow, ...]) -> bytes:
    return json.dumps(
        [dict(zip(_RESPONSE_FIELDS, row, strict=True)) for row in rows],
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _decimal_units(lexeme: str, *, positive: bool) -> tuple[str, int]:
    try:
        with localcontext() as context:
            context.prec = 100
            scaled = Decimal(lexeme) * Decimal(10**_SCALE)
            integral = scaled.to_integral_value()
    except (InvalidOperation, ValueError) as error:
        raise ValueError("decimal normalization failed") from error
    if scaled != integral:
        raise ValueError("decimal cannot be represented at exact scale")
    units = int(integral)
    if positive and units <= 0:
        raise ValueError("positive decimal must remain positive")
    absolute = abs(units)
    normalized = f"{absolute // 10**_SCALE}.{absolute % 10**_SCALE:08d}"
    return ("-" if units < 0 else "") + normalized, units


def _normalize(rows: tuple[_SourceRow, ...]) -> tuple[_NormalizedRow, ...]:
    return tuple(
        _NormalizedRow(
            row,
            _source_record_hash(row),
            *_decimal_units(row[2], positive=False),
            *_decimal_units(row[3], positive=True),
        )
        for row in rows
    )


def _event(
    row: _NormalizedRow,
    *,
    row_index: int,
    snapshot_id: str,
    response_hash: str,
    observed_at: UtcInstant,
) -> MarketEvent:
    source = row.source_row
    identity = {
        "type": "binance_usdm_funding_history_event_identity",
        "schema_version": _SCHEMA_VERSION,
        "snapshot_id": snapshot_id,
        "funding_time_milliseconds": source[1],
        "source_record_hash": row.source_record_hash,
    }
    return MarketEvent(
        event_id="binance-usdm-funding-history-v2:" + canonical_sha256(identity),
        stream_key=_STREAM_KEY,
        event_type=_EVENT_TYPE,
        capability=_CAPABILITY,
        instrument_id=_INSTRUMENT,
        event_time=UtcInstant(source[1] * 1_000_000),
        available_time=observed_at,
        phase=_PHASE,
        source_sequence=SourceSequence(row_index),
        revision_id=response_hash,
        supersedes_revision_id=None,
        source_key=_SOURCE_KEY,
        source_hash=response_hash,
        payload={
            "funding_purpose": "funding",
            "funding_time_milliseconds": source[1],
            "raw_funding_rate": source[2],
            "funding_rate": row.funding_rate,
            "funding_rate_units": row.funding_rate_units,
            "funding_rate_scale": _SCALE,
            "raw_mark_price": source[3],
            "mark_price": row.mark_price,
            "mark_price_units": row.mark_price_units,
            "mark_price_scale": _SCALE,
            "rate_type": source[4],
            "source_record_hash": row.source_record_hash,
        },
    )


def _events(
    rows: tuple[_NormalizedRow, ...],
    *,
    snapshot_id: str,
    response_hash: str,
    observed_at: UtcInstant,
) -> tuple[MarketEvent, ...]:
    return tuple(
        _event(
            row,
            row_index=index,
            snapshot_id=snapshot_id,
            response_hash=response_hash,
            observed_at=observed_at,
        )
        for index, row in enumerate(rows)
    )


def _publication(events: tuple[MarketEvent, ...]) -> _BuiltPublication | None:
    try:
        stream_payload = canonical_bytes(events)
        if _digest(stream_payload) != canonical_sha256(events):
            return None
        outcome = validate_market_bundle_v1(
            bundle_key=_BUNDLE_KEY,
            schema_version=1,
            coverage_start=_COVERAGE_START,
            coverage_end_exclusive=_COVERAGE_END_EXCLUSIVE,
            instrument_catalog_hash=_CATALOG_HASH,
            events=events,
        )
        if outcome.failure is not None or outcome.manifest is None:
            return None
        manifest = outcome.manifest
        if (
            len(manifest.streams) != 1
            or manifest.streams[0].stream_key != _STREAM_KEY
            or manifest.streams[0].event_type != _EVENT_TYPE
            or manifest.streams[0].capability != _CAPABILITY
            or manifest.streams[0].event_count != len(events)
            or manifest.streams[0].content_hash != canonical_sha256(events)
        ):
            return None
        bundle_ref = MarketBundleRef.from_manifest(manifest)
        replay = validate_market_bundle_v1(
            bundle_key=_BUNDLE_KEY,
            schema_version=1,
            coverage_start=_COVERAGE_START,
            coverage_end_exclusive=_COVERAGE_END_EXCLUSIVE,
            instrument_catalog_hash=_CATALOG_HASH,
            events=events,
        )
        if (
            replay.failure is not None
            or replay.manifest is None
            or canonical_bytes(replay.manifest) != canonical_bytes(manifest)
            or MarketBundleRef.from_manifest(replay.manifest) != bundle_ref
        ):
            return None
        return _BuiltPublication(events, stream_payload, manifest, bundle_ref)
    except (AttributeError, TypeError, ValueError):
        return None


def _replay_publication(
    source_rows: tuple[_SourceRow, ...],
    *,
    snapshot_id: str,
    response_hash: str,
    observed_at: UtcInstant,
) -> _BuiltPublication:
    normalized = _normalize(source_rows)
    if observed_at.epoch_nanoseconds <= max(row[1] * 1_000_000 for row in source_rows):
        raise ValueError("report lookahead binding mismatch")
    publication = _publication(
        _events(
            normalized,
            snapshot_id=snapshot_id,
            response_hash=response_hash,
            observed_at=observed_at,
        )
    )
    if publication is None:
        raise ValueError("report publication binding mismatch")
    return publication


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingHistorySourceBoundedObservationReportV2:
    provider_key: str
    datasets: tuple[str, ...]
    instrument_id: InstrumentId
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    request_scope_hash: str
    acquisition_receipt_sha256: str
    snapshot_id: str
    snapshot_content_tree_hash: str
    provenance_hash: str
    member_keys: tuple[str, ...]
    member_content_hashes: tuple[str, ...]
    member_acquired_at_epoch_nanoseconds: tuple[int, ...]
    response_record_count: int
    missing_mark_price_count: int
    source_rows: tuple[_SourceRow, ...]
    source_record_hashes: tuple[str, ...]
    bundle_ref: MarketBundleRef
    manifest_content_hash: str
    stream_content_hash: str
    published_event_hashes: tuple[str, ...]
    observed_at: UtcInstant
    supersedes_report_hash: str | None
    limitations: tuple[str, ...]
    availability_closure_complete: bool
    revision_closure_complete: bool
    provider_authority_qualified: bool
    provider_revision_completeness_qualified: bool
    instrument_catalog_qualified: bool
    decision_grade_eligible: bool
    profile_qualified: bool
    live_eligible: bool
    deployment_authorized: bool
    report_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if self.provider_key != _PROVIDER_KEY or self.datasets != _DATASETS:
            raise ValueError("report provider scope mismatch")
        if (
            type(self.instrument_id) is not InstrumentId
            or self.instrument_id != _INSTRUMENT
        ):
            raise ValueError("report instrument scope mismatch")
        if (
            type(self.coverage_start) is not UtcInstant
            or self.coverage_start != _COVERAGE_START
            or type(self.coverage_end_exclusive) is not UtcInstant
            or self.coverage_end_exclusive != _COVERAGE_END_EXCLUSIVE
        ):
            raise ValueError("report coverage scope mismatch")
        for name in (
            "request_scope_hash",
            "acquisition_receipt_sha256",
            "snapshot_id",
            "snapshot_content_tree_hash",
            "provenance_hash",
            "manifest_content_hash",
            "stream_content_hash",
        ):
            _hash(name, getattr(self, name))
        if self.request_scope_hash != _REQUEST_SCOPE_HASH:
            raise ValueError("report request scope mismatch")
        if (
            type(self.member_keys) is not tuple
            or self.member_keys != (_MEMBER_KEY,)
            or type(self.member_content_hashes) is not tuple
            or len(self.member_content_hashes) != 1
            or type(self.member_acquired_at_epoch_nanoseconds) is not tuple
            or len(self.member_acquired_at_epoch_nanoseconds) != 1
        ):
            raise ValueError("report member binding mismatch")
        response_hash = _hash("member_content_hash", self.member_content_hashes[0])
        acquired_at = _exact_int(
            "member acquired time", self.member_acquired_at_epoch_nanoseconds[0]
        )
        if (
            type(self.observed_at) is not UtcInstant
            or UtcInstant(acquired_at) != self.observed_at
        ):
            raise ValueError("report observation time mismatch")
        if (
            type(self.response_record_count) is not int
            or self.response_record_count != len(_FUNDING_TIMES)
            or type(self.missing_mark_price_count) is not int
            or self.missing_mark_price_count != 0
        ):
            raise ValueError("report response count mismatch")
        rows = _source_rows("source_rows", self.source_rows)
        if tuple(row[1] for row in rows) != _FUNDING_TIMES:
            raise ValueError("report source row scope mismatch")
        hashes = _hash_tuple("source_record_hashes", self.source_record_hashes)
        if hashes != tuple(_source_record_hash(row) for row in rows):
            raise ValueError("report source row hash mismatch")
        raw_response = _response_bytes(rows)
        if _digest(raw_response) != response_hash:
            raise ValueError("report raw response binding mismatch")
        frozen_snapshot = freeze_source_snapshot(
            members=(
                RawSourceMember(
                    _MEMBER_KEY,
                    raw_response,
                    "0644",
                    acquired_at,
                    None,
                ),
            ),
            provenance=SourceSnapshotProvenance(
                vendor_key=_PROVIDER_KEY,
                source_key=_SOURCE_KEY,
                license_ref="binance.api.terms",
                retention_policy_ref="backtest.acquisition.candidate",
            ),
        ).snapshot
        if (
            frozen_snapshot is None
            or frozen_snapshot.snapshot_id != self.snapshot_id
            or frozen_snapshot.content_tree_hash != self.snapshot_content_tree_hash
            or frozen_snapshot.provenance_hash != self.provenance_hash
        ):
            raise ValueError("report SourceSnapshot binding mismatch")
        publication = _replay_publication(
            rows,
            snapshot_id=self.snapshot_id,
            response_hash=response_hash,
            observed_at=self.observed_at,
        )
        event_hashes = _hash_tuple(
            "published_event_hashes", self.published_event_hashes
        )
        if event_hashes != tuple(event.event_hash for event in publication.events):
            raise ValueError("report Event hash mismatch")
        if type(self.bundle_ref) is not MarketBundleRef:
            raise TypeError("bundle_ref must be exact MarketBundleRef")
        rebuilt_ref = MarketBundleRef(
            self.bundle_ref.bundle_key, self.bundle_ref.manifest_hash
        )
        if (
            rebuilt_ref != self.bundle_ref
            or rebuilt_ref != publication.bundle_ref
            or self.manifest_content_hash != publication.manifest.content_hash
            or self.stream_content_hash != publication.manifest.streams[0].content_hash
        ):
            raise ValueError("report manifest binding mismatch")
        if self.supersedes_report_hash is not None:
            _hash("supersedes_report_hash", self.supersedes_report_hash)
        if self.limitations != _LIMITATIONS:
            raise ValueError("report limitations mismatch")
        flags = (
            self.availability_closure_complete,
            self.revision_closure_complete,
            self.provider_authority_qualified,
            self.provider_revision_completeness_qualified,
            self.instrument_catalog_qualified,
            self.decision_grade_eligible,
            self.profile_qualified,
            self.live_eligible,
            self.deployment_authorized,
        )
        if any(type(value) is not bool for value in flags) or any(flags):
            raise ValueError("report qualification flags must remain false")
        object.__setattr__(self, "report_hash", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_history_source_bounded_observation_report",
            "schema_version": _SCHEMA_VERSION,
            "provider_key": self.provider_key,
            "datasets": self.datasets,
            "instrument_id": self.instrument_id,
            "coverage_start": self.coverage_start,
            "coverage_end_exclusive": self.coverage_end_exclusive,
            "request_scope_hash": self.request_scope_hash,
            "acquisition_receipt_sha256": self.acquisition_receipt_sha256,
            "snapshot_id": self.snapshot_id,
            "snapshot_content_tree_hash": self.snapshot_content_tree_hash,
            "provenance_hash": self.provenance_hash,
            "member_keys": self.member_keys,
            "member_content_hashes": self.member_content_hashes,
            "member_acquired_at_epoch_nanoseconds": self.member_acquired_at_epoch_nanoseconds,
            "response_record_count": self.response_record_count,
            "missing_mark_price_count": self.missing_mark_price_count,
            "source_rows": self.source_rows,
            "source_record_hashes": self.source_record_hashes,
            "bundle_ref": self.bundle_ref,
            "manifest_content_hash": self.manifest_content_hash,
            "stream_content_hash": self.stream_content_hash,
            "published_event_hashes": self.published_event_hashes,
            "observed_at": self.observed_at,
            "supersedes_report_hash": self.supersedes_report_hash,
            "limitations": self.limitations,
            "availability_closure_complete": self.availability_closure_complete,
            "revision_closure_complete": self.revision_closure_complete,
            "provider_authority_qualified": self.provider_authority_qualified,
            "provider_revision_completeness_qualified": self.provider_revision_completeness_qualified,
            "instrument_catalog_qualified": self.instrument_catalog_qualified,
            "decision_grade_eligible": self.decision_grade_eligible,
            "profile_qualified": self.profile_qualified,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "report_hash": self.report_hash}

    @classmethod
    def from_canonical_dict(
        cls, value: Mapping[str, object]
    ) -> BinanceUsdmFundingHistorySourceBoundedObservationReportV2:
        if type(value) is not dict:
            raise TypeError("report canonical value must be exact dict")
        body = cast(dict[str, object], value)
        if set(body) != {"type", "schema_version", *cls.__dataclass_fields__.keys()}:
            raise ValueError("report canonical keys mismatch")
        if (
            body["type"]
            != "binance_usdm_funding_history_source_bounded_observation_report"
            or type(body["schema_version"]) is not int
            or body["schema_version"] != _SCHEMA_VERSION
        ):
            raise ValueError("report canonical schema mismatch")

        def exact_string(name: str) -> str:
            item = body[name]
            if type(item) is not str:
                raise ValueError(f"report canonical {name} mismatch")
            return item

        def exact_bool(name: str) -> bool:
            item = body[name]
            if type(item) is not bool:
                raise ValueError(f"report canonical {name} mismatch")
            return item

        def string_list(name: str) -> tuple[str, ...]:
            item = body[name]
            if type(item) is not list or any(type(child) is not str for child in item):
                raise ValueError(f"report canonical {name} mismatch")
            return tuple(cast(list[str], item))

        def integer_list(name: str) -> tuple[int, ...]:
            item = body[name]
            if type(item) is not list or any(type(child) is not int for child in item):
                raise ValueError(f"report canonical {name} mismatch")
            return tuple(cast(list[int], item))

        def instant(name: str) -> UtcInstant:
            item = body[name]
            if (
                type(item) is not dict
                or set(item) != {"type", "epoch_nanoseconds"}
                or item["type"] != "utc_instant"
                or type(item["epoch_nanoseconds"]) is not int
            ):
                raise ValueError(f"report canonical {name} mismatch")
            return UtcInstant(cast(int, item["epoch_nanoseconds"]))

        instrument = body["instrument_id"]
        bundle_ref = body["bundle_ref"]
        if (
            type(instrument) is not dict
            or set(instrument) != {"type", "venue", "stable_key"}
            or instrument["type"] != "instrument_id"
            or type(instrument["venue"]) is not str
            or type(instrument["stable_key"]) is not str
            or type(bundle_ref) is not dict
            or set(bundle_ref) != {"type", "bundle_key", "manifest_hash"}
            or bundle_ref["type"] != "market_bundle_ref"
            or type(bundle_ref["bundle_key"]) is not str
            or type(bundle_ref["manifest_hash"]) is not str
        ):
            raise ValueError("report canonical nested identity mismatch")
        source_rows_value = body["source_rows"]
        if type(source_rows_value) is not list:
            raise ValueError("report canonical source_rows mismatch")
        source_rows: list[_SourceRow] = []
        for row in source_rows_value:
            if (
                type(row) is not list
                or len(row) != len(_RESPONSE_FIELDS)
                or type(row[0]) is not str
                or type(row[1]) is not int
                or type(row[2]) is not str
                or type(row[3]) is not str
                or type(row[4]) is not str
            ):
                raise ValueError("report canonical source row mismatch")
            source_rows.append((row[0], row[1], row[2], row[3], row[4]))
        supersedes = body["supersedes_report_hash"]
        if supersedes is not None and type(supersedes) is not str:
            raise ValueError("report canonical supersedes hash mismatch")
        response_count = body["response_record_count"]
        missing_count = body["missing_mark_price_count"]
        if type(response_count) is not int or type(missing_count) is not int:
            raise ValueError("report canonical response count mismatch")
        report_hash = exact_string("report_hash")
        report = cls(
            provider_key=exact_string("provider_key"),
            datasets=string_list("datasets"),
            instrument_id=InstrumentId(
                VenueId(cast(str, instrument["venue"])),
                cast(str, instrument["stable_key"]),
            ),
            coverage_start=instant("coverage_start"),
            coverage_end_exclusive=instant("coverage_end_exclusive"),
            request_scope_hash=exact_string("request_scope_hash"),
            acquisition_receipt_sha256=exact_string("acquisition_receipt_sha256"),
            snapshot_id=exact_string("snapshot_id"),
            snapshot_content_tree_hash=exact_string("snapshot_content_tree_hash"),
            provenance_hash=exact_string("provenance_hash"),
            member_keys=string_list("member_keys"),
            member_content_hashes=string_list("member_content_hashes"),
            member_acquired_at_epoch_nanoseconds=integer_list(
                "member_acquired_at_epoch_nanoseconds"
            ),
            response_record_count=response_count,
            missing_mark_price_count=missing_count,
            source_rows=tuple(source_rows),
            source_record_hashes=string_list("source_record_hashes"),
            bundle_ref=MarketBundleRef(
                cast(str, bundle_ref["bundle_key"]),
                cast(str, bundle_ref["manifest_hash"]),
            ),
            manifest_content_hash=exact_string("manifest_content_hash"),
            stream_content_hash=exact_string("stream_content_hash"),
            published_event_hashes=string_list("published_event_hashes"),
            observed_at=instant("observed_at"),
            supersedes_report_hash=cast(str | None, supersedes),
            limitations=string_list("limitations"),
            availability_closure_complete=exact_bool("availability_closure_complete"),
            revision_closure_complete=exact_bool("revision_closure_complete"),
            provider_authority_qualified=exact_bool("provider_authority_qualified"),
            provider_revision_completeness_qualified=exact_bool(
                "provider_revision_completeness_qualified"
            ),
            instrument_catalog_qualified=exact_bool("instrument_catalog_qualified"),
            decision_grade_eligible=exact_bool("decision_grade_eligible"),
            profile_qualified=exact_bool("profile_qualified"),
            live_eligible=exact_bool("live_eligible"),
            deployment_authorized=exact_bool("deployment_authorized"),
        )
        if report_hash != report.report_hash:
            raise ValueError("report hash mismatch")
        if canonical_bytes(body) != canonical_bytes(report.to_canonical_dict()):
            raise ValueError("report canonical reconstruction mismatch")
        return report


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingHistorySourceBoundedObservationOutcomeV2:
    report: BinanceUsdmFundingHistorySourceBoundedObservationReportV2 | None = None
    failure: _Failure | None = None

    def __post_init__(self) -> None:
        if (self.report is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one report or failure")
        if self.report is not None:
            rebuilt = _reconstruct_report(self.report)
            if rebuilt is None:
                raise ValueError("outcome report authority is invalid")
            object.__setattr__(self, "report", rebuilt)
        if self.failure is not None and type(self.failure) is not _Failure:
            raise TypeError("failure must be exact provider failure")


def _string_tuple(name: str, value: object) -> tuple[str, ...]:
    if type(value) is not tuple or any(type(item) is not str for item in value):
        raise ValueError(f"{name} must be exact tuple[str, ...]")
    return value


def _hash_tuple(name: str, value: object) -> tuple[str, ...]:
    return tuple(_hash(f"{name} item", item) for item in _string_tuple(name, value))


def _source_rows(name: str, value: object) -> tuple[_SourceRow, ...]:
    if type(value) is not tuple or len(value) != len(_FUNDING_TIMES):
        raise ValueError(f"{name} must contain the exact source rows")
    rows: list[_SourceRow] = []
    for item in value:
        if (
            type(item) is not tuple
            or len(item) != len(_RESPONSE_FIELDS)
            or type(item[0]) is not str
            or type(item[1]) is not int
            or type(item[2]) is not str
            or type(item[3]) is not str
            or type(item[4]) is not str
        ):
            raise ValueError(f"{name} row primitive mismatch")
        row = cast(_SourceRow, item)
        if (
            row[0] != "BTCUSDT"
            or row[4] != "Regular"
            or len(row[2]) > 64
            or _RATE.fullmatch(row[2]) is None
            or (row[2].startswith("-") and Decimal(row[2]) == 0)
            or len(row[3]) > 64
            or _MARK.fullmatch(row[3]) is None
        ):
            raise ValueError(f"{name} row scope mismatch")
        rows.append(row)
    return tuple(rows)


def _reconstruct_report(
    value: object,
) -> BinanceUsdmFundingHistorySourceBoundedObservationReportV2 | None:
    if type(value) is not BinanceUsdmFundingHistorySourceBoundedObservationReportV2:
        return None
    try:
        parsed = json.loads(canonical_bytes(value.to_canonical_dict()))
        return BinanceUsdmFundingHistorySourceBoundedObservationReportV2.from_canonical_dict(
            parsed
        )
    except (AttributeError, TypeError, ValueError):
        return None


def _failed(
    code: _FailureCode, member_key: str | None = None
) -> BinanceUsdmFundingHistorySourceBoundedObservationOutcomeV2:
    return BinanceUsdmFundingHistorySourceBoundedObservationOutcomeV2(
        failure=_Failure(code, member_key)
    )


def _receipt(receipt_bytes: bytes) -> dict[str, object]:
    parsed = _json(receipt_bytes)
    if (
        type(parsed) is not dict
        or receipt_bytes != canonical_bytes(parsed) + b"\n"
        or set(parsed) != _RECEIPT_KEYS
    ):
        raise ValueError("receipt must be exact canonical JSON")
    return parsed


def _evidence(
    receipt_bytes: bytes, snapshot: SourceSnapshot
) -> tuple[dict[str, object], SourceSnapshot, bytes] | None:
    try:
        receipt = _receipt(receipt_bytes)
        if (
            receipt["type"] != "binance_usdm_funding_history_acquisition_receipt"
            or type(receipt["schema_version"]) is not int
            or receipt["schema_version"] != 1
            or type(receipt["request"]) is not dict
            or set(cast(dict[str, object], receipt["request"])) != _REQUEST_KEYS
            or type(receipt["acquired_at_epoch_nanoseconds"]) is not int
            or receipt["acquired_at_epoch_nanoseconds"] < 0
            or type(receipt["attempts"]) is not int
            or receipt["attempts"] <= 0
            or type(receipt["record_count"]) is not int
            or receipt["record_count"] < 0
            or type(receipt["missing_mark_price_count"]) is not int
            or receipt["missing_mark_price_count"] < 0
            or type(receipt["decision_grade_eligible"]) is not bool
            or receipt["decision_grade_eligible"]
            or type(receipt["deployment_authorized"]) is not bool
            or receipt["deployment_authorized"]
            or type(receipt["snapshot"]) is not dict
        ):
            return None
        request = cast(dict[str, object], receipt["request"])
        if (
            type(request["type"]) is not str
            or type(request["schema_version"]) is not int
            or type(request["symbol"]) is not str
            or type(request["start_time_milliseconds"]) is not int
            or type(request["end_time_milliseconds"]) is not int
            or type(request["limit"]) is not int
            or type(request["url"]) is not str
        ):
            return None
        response_hash = _hash("response_sha256", receipt["response_sha256"])
        rebuilt = _reconstruct_snapshot(snapshot)
        if rebuilt is None or verify_source_snapshot(rebuilt).snapshot is None:
            return None
        if receipt["snapshot"] != rebuilt.to_canonical_dict():
            return None
        if (
            len(rebuilt.members) != 1
            or rebuilt.members[0].member_key != _MEMBER_KEY
            or rebuilt.members[0].mode != "0644"
            or rebuilt.members[0].declared_sha256 is not None
        ):
            return None
        member = rebuilt.members[0]
        raw = rebuilt.member_bytes(_MEMBER_KEY)
        if (
            member.content_hash != response_hash
            or member.content_hash != _digest(raw)
            or member.byte_count != len(raw)
            or member.acquired_at_epoch_nanoseconds
            != receipt["acquired_at_epoch_nanoseconds"]
        ):
            return None
        try:
            shallow = _json(raw)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
            shallow = None
        if type(shallow) is list:
            if receipt["record_count"] != len(shallow):
                return None
            if all(type(item) is dict and "markPrice" in item for item in shallow):
                missing = sum(item["markPrice"] == "" for item in shallow)
                if receipt["missing_mark_price_count"] != missing:
                    return None
        return receipt, rebuilt, raw
    except Exception:  # noqa: BLE001 -- trust-boundary failures are redacted.
        return None


def _request_scope(receipt: dict[str, object], snapshot: SourceSnapshot) -> bool:
    return receipt[
        "request"
    ] == _REQUEST and snapshot.provenance.to_canonical_dict() == {
        "vendor_key": _PROVIDER_KEY,
        "source_key": _SOURCE_KEY,
        "license_ref": "binance.api.terms",
        "retention_policy_ref": "backtest.acquisition.candidate",
    }


def _response(raw: bytes) -> _ParsedResponse:
    try:
        parsed = _json(raw)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as error:
        raise ValueError("response must be valid unique-key JSON") from error
    try:
        compact = json.dumps(
            parsed,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("response must be compact JSON") from error
    if type(parsed) is not list or raw != compact or b"\r" in raw:
        raise ValueError("response envelope mismatch")
    rows: list[tuple[str, int, str, str, str]] = []
    for item in parsed:
        if type(item) is not dict or tuple(item) != _RESPONSE_FIELDS:
            raise ValueError("response row shape mismatch")
        symbol = item["symbol"]
        funding_time = item["fundingTime"]
        funding_rate = item["fundingRate"]
        mark_price = item["markPrice"]
        rate_type = item["rateType"]
        if (
            type(symbol) is not str
            or type(funding_time) is not int
            or type(funding_rate) is not str
            or type(mark_price) is not str
            or type(rate_type) is not str
            or len(funding_rate) > 64
            or _RATE.fullmatch(funding_rate) is None
            or (funding_rate.startswith("-") and Decimal(funding_rate) == 0)
            or (
                mark_price != ""
                and (len(mark_price) > 64 or _MARK.fullmatch(mark_price) is None)
            )
        ):
            raise ValueError("response row primitive mismatch")
        rows.append((symbol, funding_time, funding_rate, mark_price, rate_type))
    return _ParsedResponse(tuple(rows))


def _response_scope(receipt: dict[str, object], response: _ParsedResponse) -> bool:
    rows = response.rows
    return (
        len(rows) == len(_FUNDING_TIMES)
        and len(rows) < cast(int, cast(dict[str, object], receipt["request"])["limit"])
        and tuple(row[0] for row in rows) == ("BTCUSDT",) * len(_FUNDING_TIMES)
        and tuple(row[1] for row in rows) == _FUNDING_TIMES
        and all(row[3] != "" for row in rows)
        and tuple(row[4] for row in rows) == ("Regular",) * len(_FUNDING_TIMES)
        and receipt["record_count"] == len(rows)
        and receipt["missing_mark_price_count"] == 0
    )


def _build_report(
    *,
    receipt_bytes: bytes,
    receipt: dict[str, object],
    snapshot: SourceSnapshot,
    rows: tuple[_NormalizedRow, ...],
    publication: _BuiltPublication,
    supersedes_report_hash: str | None,
) -> BinanceUsdmFundingHistorySourceBoundedObservationReportV2:
    member = snapshot.members[0]
    return BinanceUsdmFundingHistorySourceBoundedObservationReportV2(
        provider_key=_PROVIDER_KEY,
        datasets=_DATASETS,
        instrument_id=_INSTRUMENT,
        coverage_start=_COVERAGE_START,
        coverage_end_exclusive=_COVERAGE_END_EXCLUSIVE,
        request_scope_hash=_REQUEST_SCOPE_HASH,
        acquisition_receipt_sha256=_digest(receipt_bytes),
        snapshot_id=snapshot.snapshot_id,
        snapshot_content_tree_hash=snapshot.content_tree_hash,
        provenance_hash=snapshot.provenance_hash,
        member_keys=(member.member_key,),
        member_content_hashes=(member.content_hash,),
        member_acquired_at_epoch_nanoseconds=(member.acquired_at_epoch_nanoseconds,),
        response_record_count=cast(int, receipt["record_count"]),
        missing_mark_price_count=cast(int, receipt["missing_mark_price_count"]),
        source_rows=tuple(row.source_row for row in rows),
        source_record_hashes=tuple(row.source_record_hash for row in rows),
        bundle_ref=publication.bundle_ref,
        manifest_content_hash=publication.manifest.content_hash,
        stream_content_hash=publication.manifest.streams[0].content_hash,
        published_event_hashes=tuple(event.event_hash for event in publication.events),
        observed_at=UtcInstant(cast(int, receipt["acquired_at_epoch_nanoseconds"])),
        supersedes_report_hash=supersedes_report_hash,
        limitations=_LIMITATIONS,
        availability_closure_complete=False,
        revision_closure_complete=False,
        provider_authority_qualified=False,
        provider_revision_completeness_qualified=False,
        instrument_catalog_qualified=False,
        decision_grade_eligible=False,
        profile_qualified=False,
        live_eligible=False,
        deployment_authorized=False,
    )


def _replay_predecessor(
    receipt_bytes: bytes,
    snapshot: SourceSnapshot,
    report: BinanceUsdmFundingHistorySourceBoundedObservationReportV2,
) -> BinanceUsdmFundingHistorySourceBoundedObservationReportV2 | None:
    trusted = _reconstruct_report(report)
    if trusted is None:
        return None
    evidence = _evidence(receipt_bytes, snapshot)
    if evidence is None:
        return None
    receipt, snapshot, raw = evidence
    if not _request_scope(receipt, snapshot):
        return None
    try:
        response = _response(raw)
        if not _response_scope(receipt, response):
            return None
        rows = _normalize(response.rows)
    except (AttributeError, InvalidOperation, TypeError, ValueError):
        return None
    observed_at = UtcInstant(cast(int, receipt["acquired_at_epoch_nanoseconds"]))
    if observed_at.epoch_nanoseconds <= max(
        row.source_row[1] * 1_000_000 for row in rows
    ):
        return None
    try:
        publication = _publication(
            _events(
                rows,
                snapshot_id=snapshot.snapshot_id,
                response_hash=snapshot.members[0].content_hash,
                observed_at=observed_at,
            )
        )
        if publication is None:
            return None
        rebuilt = _build_report(
            receipt_bytes=receipt_bytes,
            receipt=receipt,
            snapshot=snapshot,
            rows=rows,
            publication=publication,
            supersedes_report_hash=trusted.supersedes_report_hash,
        )
        replayed = _reconstruct_report(rebuilt)
    except (AttributeError, TypeError, ValueError):
        return None
    if replayed is None or canonical_bytes(
        replayed.to_canonical_dict()
    ) != canonical_bytes(trusted.to_canonical_dict()):
        return None
    return trusted


def observe_binance_usdm_funding_history_source_bounded_v2(
    *,
    acquisition_receipt_bytes: bytes,
    snapshot: SourceSnapshot,
    supersedes_report: BinanceUsdmFundingHistorySourceBoundedObservationReportV2
    | None = None,
    supersedes_acquisition_receipt_bytes: bytes | None = None,
    supersedes_snapshot: SourceSnapshot | None = None,
) -> BinanceUsdmFundingHistorySourceBoundedObservationOutcomeV2:
    if (
        type(acquisition_receipt_bytes) is not bytes
        or type(snapshot) is not SourceSnapshot
        or (
            supersedes_report is not None
            and type(supersedes_report)
            is not BinanceUsdmFundingHistorySourceBoundedObservationReportV2
        )
        or (
            supersedes_acquisition_receipt_bytes is not None
            and type(supersedes_acquisition_receipt_bytes) is not bytes
        )
        or (
            supersedes_snapshot is not None
            and type(supersedes_snapshot) is not SourceSnapshot
        )
    ):
        return _failed(_FailureCode.INVALID_INPUT)

    evidence = _evidence(acquisition_receipt_bytes, snapshot)
    if evidence is None:
        return _failed(_FailureCode.EVIDENCE_INVALID, _MEMBER_KEY)
    receipt, snapshot, raw = evidence
    if not _request_scope(receipt, snapshot):
        return _failed(_FailureCode.REQUEST_SCOPE_MISMATCH)
    try:
        response = _response(raw)
    except (AttributeError, InvalidOperation, TypeError, ValueError):
        return _failed(_FailureCode.RESPONSE_SCHEMA_MISMATCH, _MEMBER_KEY)
    if not _response_scope(receipt, response):
        return _failed(_FailureCode.RESPONSE_SCOPE_MISMATCH, _MEMBER_KEY)
    try:
        rows = _normalize(response.rows)
    except (InvalidOperation, TypeError, ValueError):
        return _failed(_FailureCode.NORMALIZATION_FAILED, _MEMBER_KEY)

    observed_at = UtcInstant(cast(int, receipt["acquired_at_epoch_nanoseconds"]))
    if observed_at.epoch_nanoseconds <= max(
        row.source_row[1] * 1_000_000 for row in rows
    ):
        return _failed(_FailureCode.LOOKAHEAD_VIOLATION, _MEMBER_KEY)
    try:
        events = _events(
            rows,
            snapshot_id=snapshot.snapshot_id,
            response_hash=snapshot.members[0].content_hash,
            observed_at=observed_at,
        )
        publication = _publication(events)
    except (AttributeError, TypeError, ValueError):
        publication = None
    if publication is None:
        return _failed(_FailureCode.PUBLICATION_FAILED, _MEMBER_KEY)

    predecessor_values = (
        supersedes_report,
        supersedes_acquisition_receipt_bytes,
        supersedes_snapshot,
    )
    present = tuple(value is not None for value in predecessor_values)
    predecessor = None
    if any(present):
        if not all(present):
            return _failed(_FailureCode.PREDECESSOR_INVALID)
        predecessor = _replay_predecessor(
            cast(bytes, supersedes_acquisition_receipt_bytes),
            cast(SourceSnapshot, supersedes_snapshot),
            cast(
                BinanceUsdmFundingHistorySourceBoundedObservationReportV2,
                supersedes_report,
            ),
        )
        if predecessor is None:
            return _failed(_FailureCode.PREDECESSOR_INVALID)
        if (
            predecessor.provider_key != _PROVIDER_KEY
            or predecessor.datasets != _DATASETS
            or predecessor.instrument_id != _INSTRUMENT
            or predecessor.coverage_start != _COVERAGE_START
            or predecessor.coverage_end_exclusive != _COVERAGE_END_EXCLUSIVE
            or predecessor.request_scope_hash != _REQUEST_SCOPE_HASH
            or predecessor.snapshot_id == snapshot.snapshot_id
            or predecessor.observed_at.epoch_nanoseconds
            >= observed_at.epoch_nanoseconds
        ):
            return _failed(_FailureCode.CORRECTION_EDGE_INVALID)

    try:
        report = _build_report(
            receipt_bytes=acquisition_receipt_bytes,
            receipt=receipt,
            snapshot=snapshot,
            rows=rows,
            publication=publication,
            supersedes_report_hash=(
                None if predecessor is None else predecessor.report_hash
            ),
        )
        trusted_report = _reconstruct_report(report)
        if trusted_report is None or canonical_bytes(
            trusted_report.to_canonical_dict()
        ) != canonical_bytes(report.to_canonical_dict()):
            raise ValueError("report reconstruction mismatch")
    except (AttributeError, TypeError, ValueError):
        return _failed(_FailureCode.REPORT_BINDING_MISMATCH)
    return BinanceUsdmFundingHistorySourceBoundedObservationOutcomeV2(
        report=trusted_report
    )
