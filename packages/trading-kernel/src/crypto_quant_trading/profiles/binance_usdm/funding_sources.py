from __future__ import annotations

import hashlib
import re
from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum
from threading import Lock
from typing import ClassVar

from crypto_quant_domain import (
    InstrumentId,
    Price,
    PricePurpose,
    Rate,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    canonical_bytes,
    canonical_sha256,
)

from crypto_quant_trading.derivatives import LinearPerpetualContract
from crypto_quant_trading.funding import (
    FundingSlotId,
    LinearFundingPublicationStatus,
    LinearFundingRatePublicationCandidate,
)
from crypto_quant_trading.funding_accounting import (
    LinearFundingApplicationKey,
    LinearFundingMarkEvidence,
    LinearFundingSettlementEvidence,
)
from crypto_quant_trading.marks import MarkObservation, MarkResolver, StaleMarkPolicy

from .instrument_metadata import BinanceUsdmInstrumentMetadataResolution

_SCHEMA_VERSION = 1
_V1_MODEL_KEY = "crypto.binance_usdm.funding-sources.v1"
_V1_MODEL_VERSION = 1
_V2_MODEL_KEY = "crypto.binance_usdm.funding-sources.v2"
_V2_MODEL_VERSION = 2
_SOURCE_KIND = "funding_rate_history"
_RATE_BASIS = "funding_fraction_of_notional"
_SETTLEMENT_PHASE = TimelinePhase(110, "funding_settlement")
_SETTLEMENT_SEQUENCE = SourceSequence(0)
_MARK_POLICY = StaleMarkPolicy(
    policy_key="binance.usdm.funding-history-associated-mark.v1",
    policy_version=1,
    price_purpose=PricePurpose.FUNDING,
    max_age_nanoseconds=0,
    allow_forward_fill=False,
)
_LIMITATIONS = (
    "development_grade_archive_completeness_unproven",
    "regular_rate_type_only",
    "root_source_revision_only",
    "account_funding_fee_parity_unproven",
)
_SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
_POSITIVE_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.([0-9]{1,18}))?")
_SIGNED_DECIMAL = re.compile(r"(-?)(?:0|[1-9][0-9]*)(?:\.([0-9]{1,18}))?")


@dataclass(frozen=True, slots=True)
class _FundingSourceModelSpec:
    model_key: str
    model_version: int
    mark_scale_policy: str
    preserve_raw_mark_scale: bool


_V1_MODEL = _FundingSourceModelSpec(
    _V1_MODEL_KEY,
    _V1_MODEL_VERSION,
    "exact_contract_price_scale",
    False,
)
_V2_MODEL = _FundingSourceModelSpec(
    _V2_MODEL_KEY,
    _V2_MODEL_VERSION,
    "independent_exact_raw_mark_scale",
    True,
)


class BinanceUsdmFundingSourceFailureCode(str, Enum):
    INSTRUMENT_METADATA_MISMATCH = "instrument_metadata_mismatch"
    CONTRACT_CONTEXT_MISMATCH = "contract_context_mismatch"
    APPLICATION_KEY_MISMATCH = "application_key_mismatch"
    MISSING_FUNDING_SOURCE_RECORDS = "missing_funding_source_records"
    SOURCE_NOT_AVAILABLE = "source_not_available"
    MISSING_FUNDING_COVERAGE = "missing_funding_coverage"
    OVERLAPPING_FUNDING_COVERAGE = "overlapping_funding_coverage"
    MISSING_RATE_TYPE = "missing_rate_type"
    UNSUPPORTED_RATE_TYPE = "unsupported_rate_type"
    MISSING_FUNDING_RATE = "missing_funding_rate"
    MISSING_FUNDING_MARK = "missing_funding_mark"
    INVALID_DECIMAL_FIELD = "invalid_decimal_field"
    INVALID_SOURCE_TIMING = "invalid_source_timing"
    UNSUPPORTED_SOURCE_REVISION = "unsupported_source_revision"
    SOURCE_IDENTITY_CONFLICT = "source_identity_conflict"
    MARK_SCALE_MISMATCH = "mark_scale_mismatch"


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value:
        raise TypeError(f"{name} must be exact non-empty string")
    return value


def _sha256(name: str, value: object) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return value


def _simulation(name: str, value: object) -> SimulationInstant:
    if type(value) is not SimulationInstant:
        raise TypeError(f"{name} must be exact SimulationInstant")
    return value


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingSourceRef:
    source_kind: str
    source_key: str
    source_hash: str
    archive_key: str
    revision_id: str
    supersedes_revision_id: str | None

    def __post_init__(self) -> None:
        _text("source_kind", self.source_kind)
        if self.source_kind != _SOURCE_KIND:
            raise ValueError("source_kind must be funding_rate_history")
        _text("source_key", self.source_key)
        _sha256("source_hash", self.source_hash)
        _text("archive_key", self.archive_key)
        _text("revision_id", self.revision_id)
        if self.supersedes_revision_id is not None:
            _text("supersedes_revision_id", self.supersedes_revision_id)

    @property
    def source_ref_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_source_ref",
            "schema_version": _SCHEMA_VERSION,
            "source_kind": self.source_kind,
            "source_key": self.source_key,
            "source_hash": self.source_hash,
            "archive_key": self.archive_key,
            "revision_id": self.revision_id,
            "supersedes_revision_id": self.supersedes_revision_id,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingRateRecord:
    instrument_id: InstrumentId
    funding_time_milliseconds: int
    funding_rate: str | None
    mark_price: str | None
    rate_type: str | None
    archive_available_at: SimulationInstant
    event_id: str
    revision_id: str
    source_ref: BinanceUsdmFundingSourceRef

    def __post_init__(self) -> None:
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.funding_time_milliseconds) is not int:
            raise TypeError("funding_time_milliseconds must be exact integer")
        if self.funding_time_milliseconds < 0:
            raise ValueError("funding_time_milliseconds must be nonnegative")
        for name, value in (
            ("funding_rate", self.funding_rate),
            ("mark_price", self.mark_price),
            ("rate_type", self.rate_type),
        ):
            if value is not None and type(value) is not str:
                raise TypeError(f"{name} must be exact string or None")
        _simulation("archive_available_at", self.archive_available_at)
        _text("event_id", self.event_id)
        _text("revision_id", self.revision_id)
        if type(self.source_ref) is not BinanceUsdmFundingSourceRef:
            raise TypeError("source_ref must be exact BinanceUsdmFundingSourceRef")
        if self.revision_id != self.source_ref.revision_id:
            raise ValueError("record revision must match source revision")

    @property
    def funding_time(self) -> UtcInstant:
        return UtcInstant(self.funding_time_milliseconds * 1_000_000)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "instrument_id": self.instrument_id,
            "funding_time_milliseconds": self.funding_time_milliseconds,
            "funding_rate": self.funding_rate,
            "mark_price": self.mark_price,
            "rate_type": self.rate_type,
            "archive_available_at": self.archive_available_at,
            "event_id": self.event_id,
            "revision_id": self.revision_id,
            "source_ref": self.source_ref,
        }

    @property
    def event_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_rate_record",
            "schema_version": _SCHEMA_VERSION,
            **self._canonical_body(),
            "event_hash": self.event_hash,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingCoverage:
    coverage_id: str
    instrument_id: InstrumentId
    coverage_from: UtcInstant
    coverage_to_exclusive: UtcInstant
    stream_key: str
    stream_version: int
    source_ref: BinanceUsdmFundingSourceRef

    def __post_init__(self) -> None:
        _text("coverage_id", self.coverage_id)
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.coverage_from) is not UtcInstant or type(
            self.coverage_to_exclusive
        ) is not UtcInstant:
            raise TypeError("coverage bounds must be exact UtcInstant")
        if self.coverage_to_exclusive <= self.coverage_from:
            raise ValueError("funding coverage must be finite and non-empty")
        _text("stream_key", self.stream_key)
        if type(self.stream_version) is not int or self.stream_version <= 0:
            raise ValueError("stream_version must be a positive integer")
        if type(self.source_ref) is not BinanceUsdmFundingSourceRef:
            raise TypeError("source_ref must be exact BinanceUsdmFundingSourceRef")

    def contains(self, instant: UtcInstant) -> bool:
        return self.coverage_from <= instant < self.coverage_to_exclusive

    @property
    def coverage_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_coverage",
            "schema_version": _SCHEMA_VERSION,
            "coverage_id": self.coverage_id,
            "instrument_id": self.instrument_id,
            "coverage_from": self.coverage_from,
            "coverage_to_exclusive": self.coverage_to_exclusive,
            "stream_key": self.stream_key,
            "stream_version": self.stream_version,
            "source_ref": self.source_ref,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmHistoricalFundingBook:
    funding_book_key: str
    funding_book_version: int
    instrument_id: InstrumentId
    coverages: tuple[BinanceUsdmFundingCoverage, ...]
    records: tuple[BinanceUsdmFundingRateRecord, ...]

    def __post_init__(self) -> None:
        _text("funding_book_key", self.funding_book_key)
        if type(self.funding_book_version) is not int or self.funding_book_version <= 0:
            raise ValueError("funding_book_version must be a positive integer")
        if type(self.instrument_id) is not InstrumentId:
            raise TypeError("instrument_id must be exact InstrumentId")
        if type(self.coverages) is not tuple or not all(
            type(value) is BinanceUsdmFundingCoverage for value in self.coverages
        ):
            raise TypeError("coverages must be a tuple of exact funding coverages")
        if type(self.records) is not tuple or not all(
            type(value) is BinanceUsdmFundingRateRecord for value in self.records
        ):
            raise TypeError("records must be a tuple of exact funding records")
        object.__setattr__(
            self,
            "coverages",
            tuple(
                sorted(
                    self.coverages,
                    key=lambda value: (
                        value.coverage_from,
                        value.coverage_to_exclusive,
                        value.coverage_id,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "records",
            tuple(
                sorted(
                    self.records,
                    key=lambda value: (
                        value.funding_time_milliseconds,
                        value.rate_type or "",
                        value.event_id,
                        value.revision_id,
                    ),
                )
            ),
        )

    @property
    def funding_book_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_historical_funding_book",
            "schema_version": _SCHEMA_VERSION,
            "funding_book_key": self.funding_book_key,
            "funding_book_version": self.funding_book_version,
            "instrument_id": self.instrument_id,
            "coverages": list(self.coverages),
            "records": list(self.records),
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingSourceQuery:
    instrument_resolution: BinanceUsdmInstrumentMetadataResolution
    contract: LinearPerpetualContract
    application_key: LinearFundingApplicationKey
    funding_book: BinanceUsdmHistoricalFundingBook
    target_funding_time: UtcInstant
    captured_at: SimulationInstant

    def __post_init__(self) -> None:
        if type(self.instrument_resolution) is not BinanceUsdmInstrumentMetadataResolution:
            raise TypeError(
                "instrument_resolution must be exact BinanceUsdmInstrumentMetadataResolution"
            )
        if type(self.contract) is not LinearPerpetualContract:
            raise TypeError("contract must be exact LinearPerpetualContract")
        if type(self.application_key) is not LinearFundingApplicationKey:
            raise TypeError("application_key must be exact LinearFundingApplicationKey")
        if type(self.funding_book) is not BinanceUsdmHistoricalFundingBook:
            raise TypeError("funding_book must be exact BinanceUsdmHistoricalFundingBook")
        if type(self.target_funding_time) is not UtcInstant:
            raise TypeError("target_funding_time must be exact UtcInstant")
        if self.target_funding_time.epoch_nanoseconds % 1_000_000:
            raise ValueError("target_funding_time must be millisecond aligned")
        _simulation("captured_at", self.captured_at)

    @property
    def query_hash(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_source_query",
            "schema_version": _SCHEMA_VERSION,
            "instrument_resolution": self.instrument_resolution,
            "contract": self.contract,
            "application_key": self.application_key,
            "funding_book": self.funding_book,
            "target_funding_time": self.target_funding_time,
            "captured_at": self.captured_at,
        }


@dataclass(frozen=True, slots=True)
class _DecimalValue:
    units: int
    places: int


def _decimal(value: str, *, signed: bool) -> _DecimalValue | None:
    pattern = _SIGNED_DECIMAL if signed else _POSITIVE_DECIMAL
    match = pattern.fullmatch(value)
    if match is None:
        return None
    negative = signed and value.startswith("-")
    body = value[1:] if negative else value
    whole, dot, fraction = body.partition(".")
    places = len(fraction) if dot else 0
    try:
        units = int(whole + fraction)
    except ValueError:
        return None
    if negative:
        units = -units
    if negative and units == 0:
        return None
    return _DecimalValue(units, places)


def _settlement_instant(target: UtcInstant) -> SimulationInstant:
    return SimulationInstant(target, _SETTLEMENT_PHASE, _SETTLEMENT_SEQUENCE)


def _model_digest(spec: _FundingSourceModelSpec = _V1_MODEL) -> str:
    return canonical_sha256(
        {
            "type": "binance_usdm_funding_source_model",
            "schema_version": _SCHEMA_VERSION,
            "model_key": spec.model_key,
            "model_version": spec.model_version,
            "source_kind": _SOURCE_KIND,
            "slot_key": "instrument_id+funding_time",
            "supported_rate_type": "Regular",
            "unsupported_rate_type": "Special",
            "publication_status": LinearFundingPublicationStatus.FINAL_RATE.value,
            "settlement_phase": _SETTLEMENT_PHASE,
            "settlement_sequence": _SETTLEMENT_SEQUENCE,
            "rate_mapping": "fundingRate_direct_fraction_of_notional",
            "mark_mapping": "same_row_markPrice_at_fundingTime",
            "mark_policy": _MARK_POLICY,
            "revision_policy": "one_visible_root_row_per_regular_slot",
            "decimal_policy": "ascii_ordinary_decimal_max_18_places",
            "mark_scale_policy": spec.mark_scale_policy,
            "allowed_grade": "development",
            "limitations": list(_LIMITATIONS),
        }
    )


def _model_spec(
    model_key: str, model_version: int, model_digest: str
) -> _FundingSourceModelSpec:
    for spec in (_V1_MODEL, _V2_MODEL):
        if (
            model_key == spec.model_key
            and model_version == spec.model_version
            and model_digest == _model_digest(spec)
        ):
            return spec
    raise ValueError("funding source model identity is unsupported")


def _expected_slot(query: BinanceUsdmFundingSourceQuery) -> FundingSlotId:
    return FundingSlotId.derive(
        query.instrument_resolution.instrument.instrument_id,
        query.target_funding_time,
    )


def _target_records(
    query: BinanceUsdmFundingSourceQuery,
) -> tuple[BinanceUsdmFundingRateRecord, ...]:
    target_ms = query.target_funding_time.epoch_nanoseconds // 1_000_000
    return tuple(
        value
        for value in query.funding_book.records
        if value.funding_time_milliseconds == target_ms
    )


def _visible_target_records(
    query: BinanceUsdmFundingSourceQuery,
) -> tuple[BinanceUsdmFundingRateRecord, ...]:
    return tuple(
        value
        for value in _target_records(query)
        if value.archive_available_at <= query.captured_at
    )


def _target_coverages(
    query: BinanceUsdmFundingSourceQuery,
) -> tuple[BinanceUsdmFundingCoverage, ...]:
    return tuple(
        value
        for value in query.funding_book.coverages
        if value.contains(query.target_funding_time)
    )


def _instrument_mismatch(query: BinanceUsdmFundingSourceQuery) -> bool:
    resolution = query.instrument_resolution
    instrument_id = resolution.instrument.instrument_id
    if (
        query.funding_book.instrument_id != instrument_id
        or resolution.query.effective_at != query.target_funding_time
        or not resolution.listing_interval.contains(query.target_funding_time)
        or resolution.query.captured_at > query.captured_at.instant
    ):
        return True
    return any(
        value.instrument_id != instrument_id
        for value in query.funding_book.coverages
    ) or any(
        value.instrument_id != instrument_id for value in query.funding_book.records
    )


def _contract_mismatch(query: BinanceUsdmFundingSourceQuery) -> bool:
    resolution = query.instrument_resolution
    return (
        query.contract.instrument != resolution.instrument
        or query.contract.contract_multiplier
        != resolution.contract_metadata.contract_multiplier
    )


def _coverage_failure(
    query: BinanceUsdmFundingSourceQuery,
) -> BinanceUsdmFundingSourceFailureCode | None:
    coverages = _target_coverages(query)
    if not coverages:
        return BinanceUsdmFundingSourceFailureCode.MISSING_FUNDING_COVERAGE
    if len(coverages) != 1:
        return BinanceUsdmFundingSourceFailureCode.OVERLAPPING_FUNDING_COVERAGE
    return None


def _decimal_failure(
    records: tuple[BinanceUsdmFundingRateRecord, ...],
) -> bool:
    return any(
        value.funding_rate is not None
        and _decimal(value.funding_rate, signed=True) is None
        or value.mark_price is not None
        and (
            (_decimal(value.mark_price, signed=False) is None)
            or (_decimal(value.mark_price, signed=False) or _DecimalValue(0, 0)).units
            <= 0
        )
        for value in records
    )


def _timing_failure(
    query: BinanceUsdmFundingSourceQuery,
    records: tuple[BinanceUsdmFundingRateRecord, ...],
) -> bool:
    return any(
        value.funding_time != query.target_funding_time
        or value.archive_available_at.instant < query.target_funding_time
        for value in records
    )


def _identity_conflict(records: tuple[BinanceUsdmFundingRateRecord, ...]) -> bool:
    if len(records) != 1:
        return True
    natural = {
        (value.instrument_id, value.funding_time_milliseconds, value.rate_type)
        for value in records
    }
    event_ids = {value.event_id for value in records}
    revisions = {value.revision_id for value in records}
    return len(natural) != len(records) or len(event_ids) != len(records) or len(
        revisions
    ) != len(records)


def _mark_units(value: _DecimalValue, target_scale: Scale) -> int | None:
    difference = target_scale.places - value.places
    if difference >= 0:
        return value.units * 10**difference
    divisor = 10 ** (-difference)
    if value.units % divisor:
        return None
    return value.units // divisor


def _first_failure(
    query: BinanceUsdmFundingSourceQuery,
    spec: _FundingSourceModelSpec = _V1_MODEL,
) -> BinanceUsdmFundingSourceFailureCode | None:
    if _instrument_mismatch(query):
        return BinanceUsdmFundingSourceFailureCode.INSTRUMENT_METADATA_MISMATCH
    if _contract_mismatch(query):
        return BinanceUsdmFundingSourceFailureCode.CONTRACT_CONTEXT_MISMATCH
    if query.application_key.funding_slot_id != _expected_slot(query):
        return BinanceUsdmFundingSourceFailureCode.APPLICATION_KEY_MISMATCH
    target_records = _target_records(query)
    if not target_records:
        return BinanceUsdmFundingSourceFailureCode.MISSING_FUNDING_SOURCE_RECORDS
    records = _visible_target_records(query)
    if not records:
        return BinanceUsdmFundingSourceFailureCode.SOURCE_NOT_AVAILABLE
    coverage = _coverage_failure(query)
    if coverage is not None:
        return coverage
    if any(value.rate_type is None for value in records):
        return BinanceUsdmFundingSourceFailureCode.MISSING_RATE_TYPE
    if any(value.rate_type != "Regular" for value in records):
        return BinanceUsdmFundingSourceFailureCode.UNSUPPORTED_RATE_TYPE
    if any(value.funding_rate is None for value in records):
        return BinanceUsdmFundingSourceFailureCode.MISSING_FUNDING_RATE
    if any(value.mark_price is None for value in records):
        return BinanceUsdmFundingSourceFailureCode.MISSING_FUNDING_MARK
    if _decimal_failure(records):
        return BinanceUsdmFundingSourceFailureCode.INVALID_DECIMAL_FIELD
    if _timing_failure(query, records):
        return BinanceUsdmFundingSourceFailureCode.INVALID_SOURCE_TIMING
    if any(value.source_ref.supersedes_revision_id is not None for value in records):
        return BinanceUsdmFundingSourceFailureCode.UNSUPPORTED_SOURCE_REVISION
    if _identity_conflict(records):
        return BinanceUsdmFundingSourceFailureCode.SOURCE_IDENTITY_CONFLICT
    mark = _decimal(records[0].mark_price or "", signed=False)
    if mark is None or (
        not spec.preserve_raw_mark_scale
        and _mark_units(mark, query.contract.price_scale) is None
    ):
        return BinanceUsdmFundingSourceFailureCode.MARK_SCALE_MISMATCH
    return None


@dataclass(frozen=True, slots=True)
class _ResolutionValues:
    selected_record: BinanceUsdmFundingRateRecord
    source_coverage: BinanceUsdmFundingCoverage
    slot_id: FundingSlotId
    publication: LinearFundingRatePublicationCandidate
    mark_observation: MarkObservation
    funding_mark_evidence: LinearFundingMarkEvidence
    settlement_evidence: LinearFundingSettlementEvidence


def _resolution_values(
    query: BinanceUsdmFundingSourceQuery,
    spec: _FundingSourceModelSpec = _V1_MODEL,
) -> _ResolutionValues:
    record = _visible_target_records(query)[0]
    coverage = _target_coverages(query)[0]
    rate_value = _decimal(record.funding_rate or "", signed=True)
    mark_value = _decimal(record.mark_price or "", signed=False)
    if rate_value is None or mark_value is None:
        raise ValueError("funding resolution requires validated decimals")
    mark_units = (
        mark_value.units
        if spec.preserve_raw_mark_scale
        else _mark_units(mark_value, query.contract.price_scale)
    )
    if mark_units is None:
        raise ValueError("funding resolution requires exact mark scale")
    mark_scale = (
        Scale(mark_value.places)
        if spec.preserve_raw_mark_scale
        else query.contract.price_scale
    )
    slot = _expected_slot(query)
    settlement_at = _settlement_instant(query.target_funding_time)
    rate = Rate(rate_value.units, Scale(rate_value.places), _RATE_BASIS)
    publication = LinearFundingRatePublicationCandidate(
        slot_id=slot,
        status=LinearFundingPublicationStatus.FINAL_RATE,
        published_rate=rate,
        event_id=record.event_id,
        event_hash=record.event_hash,
        event_time=query.target_funding_time,
        publication_available_at=settlement_at,
        revision_id=record.revision_id,
        supersedes_revision_id=None,
        source_key=record.source_ref.source_key,
        source_hash=record.source_ref.source_hash,
    )
    observation = MarkObservation(
        instrument_id=slot.instrument_id,
        quote_currency_id=query.contract.instrument.quote_currency,
        price_purpose=PricePurpose.FUNDING,
        price=Price(
            mark_units,
            mark_scale,
            str(slot.instrument_id),
            query.contract.instrument.quote_currency.value,
        ),
        observed_at=query.target_funding_time,
        available_at=query.target_funding_time,
        stream_id=f"binance-usdm-funding-history-mark-v1:{slot.instrument_id}",
        source_event_id=record.event_id,
        revision_id=record.revision_id,
    )
    mark_outcome = MarkResolver().resolve(
        (observation,),
        instrument_id=slot.instrument_id,
        price_purpose=PricePurpose.FUNDING,
        requested_at=query.target_funding_time,
        stale_policy=_MARK_POLICY,
    )
    if mark_outcome.resolved_mark is None:
        raise ValueError("validated funding mark must resolve")
    mark_evidence = LinearFundingMarkEvidence(mark_outcome.resolved_mark, _MARK_POLICY)
    settlement = LinearFundingSettlementEvidence(
        application_key=query.application_key,
        effective_time=query.target_funding_time,
        applied_at=settlement_at,
        applied_rate=rate,
        event_id=record.event_id,
        event_hash=record.event_hash,
        revision_id=record.revision_id,
        supersedes_revision_id=None,
        source_key=record.source_ref.source_key,
        source_hash=record.source_ref.source_hash,
    )
    return _ResolutionValues(
        selected_record=record,
        source_coverage=coverage,
        slot_id=slot,
        publication=publication,
        mark_observation=observation,
        funding_mark_evidence=mark_evidence,
        settlement_evidence=settlement,
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingSourceResolution:
    model_key: str
    model_version: int
    model_digest: str
    query: BinanceUsdmFundingSourceQuery
    query_hash: str
    selected_record: BinanceUsdmFundingRateRecord
    source_coverage: BinanceUsdmFundingCoverage
    slot_id: FundingSlotId
    publication: LinearFundingRatePublicationCandidate
    mark_observation: MarkObservation
    funding_mark_evidence: LinearFundingMarkEvidence
    settlement_evidence: LinearFundingSettlementEvidence
    limitations: tuple[str, ...]
    decision_grade_eligible: bool

    def __post_init__(self) -> None:
        if type(self.query) is not BinanceUsdmFundingSourceQuery:
            raise TypeError("query must be exact BinanceUsdmFundingSourceQuery")
        try:
            spec = _model_spec(self.model_key, self.model_version, self.model_digest)
        except ValueError:
            raise ValueError(
                "resolution fields do not match funding source authority"
            ) from None
        values = _resolution_values(self.query, spec)
        expected = (
            spec.model_key,
            spec.model_version,
            _model_digest(spec),
            self.query.query_hash,
            values.selected_record,
            values.source_coverage,
            values.slot_id,
            values.publication,
            values.mark_observation,
            values.funding_mark_evidence,
            values.settlement_evidence,
            _LIMITATIONS,
            False,
        )
        actual = (
            self.model_key,
            self.model_version,
            self.model_digest,
            self.query_hash,
            self.selected_record,
            self.source_coverage,
            self.slot_id,
            self.publication,
            self.mark_observation,
            self.funding_mark_evidence,
            self.settlement_evidence,
            self.limitations,
            self.decision_grade_eligible,
        )
        if actual != expected:
            raise ValueError("resolution fields do not match funding source authority")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "model_key": self.model_key,
            "model_version": self.model_version,
            "model_digest": self.model_digest,
            "query": self.query,
            "query_hash": self.query_hash,
            "selected_record": self.selected_record,
            "source_coverage": self.source_coverage,
            "slot_id": self.slot_id,
            "publication": self.publication,
            "mark_observation": self.mark_observation,
            "funding_mark_evidence": self.funding_mark_evidence,
            "settlement_evidence": self.settlement_evidence,
            "limitations": list(self.limitations),
            "decision_grade_eligible": self.decision_grade_eligible,
        }

    @property
    def resolution_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_source_resolution",
            "schema_version": _SCHEMA_VERSION,
            **self._canonical_body(),
            "resolution_hash": self.resolution_hash,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingSourceFailure:
    model_key: str
    model_version: int
    model_digest: str
    query: BinanceUsdmFundingSourceQuery
    query_hash: str
    code: BinanceUsdmFundingSourceFailureCode
    subject_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.query) is not BinanceUsdmFundingSourceQuery:
            raise TypeError("query must be exact BinanceUsdmFundingSourceQuery")
        if type(self.code) is not BinanceUsdmFundingSourceFailureCode:
            raise TypeError("code must be exact BinanceUsdmFundingSourceFailureCode")
        try:
            spec = _model_spec(self.model_key, self.model_version, self.model_digest)
        except ValueError:
            raise ValueError(
                "failure fields do not match funding source authority"
            ) from None
        if (
            self.query_hash != self.query.query_hash
            or self.code is not _first_failure(self.query, spec)
        ):
            raise ValueError("failure fields do not match funding source authority")
        expected_subjects = (
            self.code.value,
            self.query.application_key.value,
            str(_expected_slot(self.query).instrument_id),
            str(self.query.target_funding_time.epoch_nanoseconds),
            self.query.funding_book.funding_book_hash,
        )
        if self.subject_ids != expected_subjects:
            raise ValueError("failure subject_ids do not match funding source authority")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "model_key": self.model_key,
            "model_version": self.model_version,
            "model_digest": self.model_digest,
            "query": self.query,
            "query_hash": self.query_hash,
            "code": self.code.value,
            "subject_ids": list(self.subject_ids),
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_source_failure",
            "schema_version": _SCHEMA_VERSION,
            **self._canonical_body(),
            "failure_hash": self.failure_hash,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingSourceOutcome:
    model_digest: str
    query_hash: str
    result: BinanceUsdmFundingSourceResolution | None
    failure: BinanceUsdmFundingSourceFailure | None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("funding source outcome requires exactly one result or failure")
        authority = self.result if self.result is not None else self.failure
        if authority is None:
            raise ValueError("funding source outcome authority is missing")
        if authority.model_digest != self.model_digest:
            raise ValueError("outcome model digest does not match authority")
        if self.query_hash != authority.query_hash:
            raise ValueError("outcome query hash does not match authority")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "model_digest": self.model_digest,
            "query_hash": self.query_hash,
            "result": self.result,
            "failure": self.failure,
        }

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_source_outcome",
            "schema_version": _SCHEMA_VERSION,
            **self._canonical_body(),
            "outcome_hash": self.outcome_hash,
        }


def _resolve_funding_source(
    query: BinanceUsdmFundingSourceQuery,
    spec: _FundingSourceModelSpec,
) -> BinanceUsdmFundingSourceOutcome:
    if type(query) is not BinanceUsdmFundingSourceQuery:
        raise TypeError("query must be exact BinanceUsdmFundingSourceQuery")
    digest = _model_digest(spec)
    code = _first_failure(query, spec)
    if code is not None:
        failure = BinanceUsdmFundingSourceFailure(
            model_key=spec.model_key,
            model_version=spec.model_version,
            model_digest=digest,
            query=query,
            query_hash=query.query_hash,
            code=code,
            subject_ids=(
                code.value,
                query.application_key.value,
                str(_expected_slot(query).instrument_id),
                str(query.target_funding_time.epoch_nanoseconds),
                query.funding_book.funding_book_hash,
            ),
        )
        return BinanceUsdmFundingSourceOutcome(
            model_digest=digest,
            query_hash=query.query_hash,
            result=None,
            failure=failure,
        )
    values = _resolution_values(query, spec)
    result = BinanceUsdmFundingSourceResolution(
        model_key=spec.model_key,
        model_version=spec.model_version,
        model_digest=digest,
        query=query,
        query_hash=query.query_hash,
        selected_record=values.selected_record,
        source_coverage=values.source_coverage,
        slot_id=values.slot_id,
        publication=values.publication,
        mark_observation=values.mark_observation,
        funding_mark_evidence=values.funding_mark_evidence,
        settlement_evidence=values.settlement_evidence,
        limitations=_LIMITATIONS,
        decision_grade_eligible=False,
    )
    return BinanceUsdmFundingSourceOutcome(
        model_digest=digest,
        query_hash=query.query_hash,
        result=result,
        failure=None,
    )


class BinanceUsdmFundingSourceModel:
    @property
    def model_digest(self) -> str:
        return _model_digest(_V1_MODEL)

    def resolve_funding_source(
        self,
        query: BinanceUsdmFundingSourceQuery,
        /,
    ) -> BinanceUsdmFundingSourceOutcome:
        return _resolve_funding_source(query, _V1_MODEL)


class BinanceUsdmFundingSourceModelV2:
    _CACHE_CAPACITY: ClassVar[int] = 256
    _successful_resolution_cache: ClassVar[
        OrderedDict[tuple[str, bytes], BinanceUsdmFundingSourceOutcome]
    ] = OrderedDict()
    _cache_lock: ClassVar[Lock] = Lock()
    _cache_hits: ClassVar[int] = 0
    _cache_misses: ClassVar[int] = 0

    @property
    def model_digest(self) -> str:
        return _model_digest(_V2_MODEL)

    @classmethod
    def _reset_cache_for_test(cls) -> None:
        with cls._cache_lock:
            cls._successful_resolution_cache.clear()
            cls._cache_hits = 0
            cls._cache_misses = 0

    @classmethod
    def _cache_stats_for_test(cls) -> tuple[int, int, int]:
        with cls._cache_lock:
            return (
                len(cls._successful_resolution_cache),
                cls._cache_hits,
                cls._cache_misses,
            )

    def resolve_funding_source(
        self,
        query: BinanceUsdmFundingSourceQuery,
        /,
    ) -> BinanceUsdmFundingSourceOutcome:
        if type(query) is not BinanceUsdmFundingSourceQuery:
            return _resolve_funding_source(query, _V2_MODEL)
        canonical_query = canonical_bytes(query)
        cache_key = (
            f"sha256:{hashlib.sha256(canonical_query).hexdigest()}",
            canonical_query,
        )
        with self._cache_lock:
            cached = self._successful_resolution_cache.get(cache_key)
            if cached is not None:
                self._successful_resolution_cache.move_to_end(cache_key)
                type(self)._cache_hits += 1
                return cached
            type(self)._cache_misses += 1
        outcome = _resolve_funding_source(query, _V2_MODEL)
        if outcome.result is not None:
            with self._cache_lock:
                self._successful_resolution_cache[cache_key] = outcome
                self._successful_resolution_cache.move_to_end(cache_key)
                if len(self._successful_resolution_cache) > self._CACHE_CAPACITY:
                    self._successful_resolution_cache.popitem(last=False)
        return outcome
