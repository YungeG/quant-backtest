from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import cast

from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)

from .source_snapshots import SourceSnapshot, verify_source_snapshot
from .tushare_cn_a_share_daily_source_bounded_v2 import (
    TushareCnAShareDailySourceBoundedObservationReportV2,
)

_SCHEMA_VERSION = 1
_PROVIDER_KEY = "tushare.pro"
_DATASETS = ("dividend",)
_INSTRUMENT = InstrumentId(VenueId("xshe"), "000001")
_VENUE_CALENDAR = "XSHE"
_PROVIDER_EXCHANGE = "SZSE"
_COVERAGE_START = UtcInstant(1_783_267_200_000_000_000)
_COVERAGE_END_EXCLUSIVE = UtcInstant(1_785_427_200_000_000_000)
_MEMBER_KEY = "response/dividend.json"
_SOURCE_KEY = "tushare.pro.g12k.fixed_instrument_dividend.000001.sz.20260706.20260730"
_FIELDS = (
    "ts_code",
    "end_date",
    "ann_date",
    "div_proc",
    "stk_div",
    "stk_bo_rate",
    "stk_co_rate",
    "cash_div",
    "cash_div_tax",
    "record_date",
    "ex_date",
    "pay_date",
    "div_listdate",
    "imp_ann_date",
    "base_date",
    "base_share",
)
_RELEVANCE_FIELDS = (
    "ann_date",
    "record_date",
    "ex_date",
    "pay_date",
    "div_listdate",
    "imp_ann_date",
)
_DATE_INDICES = (1, 2, 9, 10, 11, 12, 13, 14)
_NUMERIC_INDICES = (4, 5, 6, 7, 8, 15)
_REQUEST_SCOPE_HASH = (
    "sha256:5738442bf477fc2f60542fa4b0ddee7be8d737d068077eefaa63d72489935ed7"
)
_CATALOG_CANONICAL_FILE_SHA256 = (
    "sha256:d71ca8ed8977bf5fa0aa7cd1ab11fb85abcd5382f42c7e2bb2243d5b5290e456"
)
_CATALOG_PUBLICATION_HASH = (
    "sha256:d6bada1c3a9aef99ddaab718e77e2f9329b1da5821a9136f62585d2e3bb1c59b"
)
_CATALOG_SOURCE_HASH = (
    "sha256:59d3267cbf79d4721357d5959f3e848d7a3c250802fe055b4cd40e0aa0a0b8f5"
)
_INSTRUMENT_CATALOG_HASH = (
    "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc"
)
_G12I_CANONICAL_FILE_SHA256 = (
    "sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6"
)
_G12I_REPORT_HASH = (
    "sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029"
)
_G12I_RECEIPT_SHA256 = (
    "sha256:95ba0d8e28414aa997e232c90eee03318f13f2c9041b36f4da046bbc5b2fb623"
)
_G12I_SNAPSHOT_ID = (
    "sha256:9f1915e302e1a1f5b74a2cdccb54c08676642da3b48642eb9bbf728dc4c98f2e"
)
_G12I_SNAPSHOT_CONTENT_TREE_HASH = (
    "sha256:ef44ecd44476dcd3d1cd69f82305df29d186c82350c45f427b5bf008b62d57af"
)
_G12I_PROVENANCE_HASH = (
    "sha256:4dba800ca4688504c804009bcb21a4698cc431761be6847a81bfeef02a0e05e4"
)
_G12I_MANIFEST_CONTENT_HASH = (
    "sha256:87e1209b5510e9d5489d414e63c1008117282a57e1d05555113103222f06a505"
)
_G12I_BUNDLE_REF_MANIFEST_HASH = (
    "sha256:d9f73a48eeb8b92600cd7fdd9017ba8b0536654cb466ce57c8bc6695f10271df"
)
_G12I_STREAM_CONTENT_HASH = (
    "sha256:da735d4545e458f8bb1432008b89e45b7c820812f0fed91ebc6610721ad491a1"
)
_G12I_OBSERVED_DATES = (
    "20260706",
    "20260707",
    "20260708",
    "20260709",
    "20260710",
    "20260713",
    "20260714",
    "20260715",
    "20260716",
    "20260717",
    "20260720",
    "20260721",
    "20260722",
    "20260723",
    "20260724",
    "20260727",
    "20260728",
    "20260729",
    "20260730",
)
_G12I_EVENT_HASHES = (
    "sha256:2cec41bfe1d766422f35775163d132de63830d91af511830849255a80b30cfe0",
    "sha256:e490329a4c53c6e4bf2c601292d2bafd38f9ff6deaac7591bcf7ece16259df03",
    "sha256:ba785b15c8de8cfb88af252ac69b0bdf908c3e857762fbb2d0406ecdf795a981",
    "sha256:2599f9b8bc06ab0721f5fec93420d8184344b82fdc317bf6280aff482152e7ff",
    "sha256:6fd28561578cfaad903178f5ff81b24a6beb6a44a6b66b3176e4e6213cb506d8",
    "sha256:7a0ba4ae64b8f8ebc481ce4f696f3141ade9049efec0829dbf4fa0002488b558",
    "sha256:694faea1bc49d81937b18bcc009bd914c306638d6155ff01388468d5dbfb7917",
    "sha256:8dad04b9a3fc4c8e6b3b15bad66327c19de858baa307c0f2938931185800e1b0",
    "sha256:4d1dcff1609326d7958719b0f8ba5e00bcc15c5898350685f9036630ed811bd1",
    "sha256:6c02d071cfdee10079274c9c6fcdcdd33a73af50d38a7dedcd3e5b08b4a0cd18",
    "sha256:f3e30d0cc2d4097ba3ed8fe87a902055753e12707e9bea6d4ecd9657cd270172",
    "sha256:263ad147cbb51142f45ec244dfa12af8513829be24a707a74cad09906855d003",
    "sha256:98a6c55bc42b178482625eec8dd8ec774f06e2b019b0dbc7ec31c9c7c2616f71",
    "sha256:31102dbaab5653ad78a430f2890a739dbf10b84b2531ba9f4d1d530bbfce75dc",
    "sha256:f4d067480c920169754bfcbc8a5ade48368d4eed97776d1513ba1ae6947c1ce9",
    "sha256:6caa4852a99ab8f6e32743e01f013d3216db140ce9c42950827cfd9a4250a23c",
    "sha256:f04029ea0a17ed715df0d842f0079d84a1b227ab2fe8e769df7ebf8ae3665def",
    "sha256:74cdf0ce0401c36aaeaa97e2b6b5fe0cee4861c41a80cba1f5639e64b828e44b",
    "sha256:98c41ec26cd76f73e66c8ba20a8a3b410940c01eeb886eec6f9034687e4fb5d5",
)
_G12I_NO_SESSION_DATES = (
    "20260711",
    "20260712",
    "20260718",
    "20260719",
    "20260725",
    "20260726",
)
_LIMITATIONS = (
    "permanent_provider_checksum_unavailable",
    "future_revision_finality_unknown",
    "provider_correction_lineage_unavailable",
    "provider_completeness_unknown",
    "g12i_daily_presence_is_not_listing_membership",
    "historical_listing_authority_unavailable",
    "listing_membership_continuity_unavailable",
    "whole_universe_completeness_unavailable",
    "survivorship_safety_unavailable",
    "corporate_action_lifecycle_closure_unavailable",
    "zero_target_dividend_rows_is_not_absence_authority",
    "bak_basic_unavailable_to_observed_credential_code_40203",
)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_DATE = re.compile(r"[0-9]{8}\Z")
_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z")
_RECEIPT_KEYS = {
    "type",
    "schema_version",
    "request",
    "request_scope_hash",
    "provider_requests",
    "acquired_at_epoch_nanoseconds",
    "snapshot",
    "provider_declared_sha256",
    "provider_revision_id",
    "decision_grade_eligible",
    "deployment_authorized",
}
_PROVIDER_REQUEST_KEYS = {
    "api_name",
    "params",
    "fields",
    "member_key",
    "attempts",
    "response_received_at_epoch_nanoseconds",
    "response_byte_count",
    "response_sha256",
    "returned_row_count",
    "observed_envelope",
    "declared_sha256",
    "provider_revision_id",
}
_RESPONSE_KEYS = {"request_id", "code", "data", "msg", "detail"}
_RESPONSE_DATA_KEYS = {"fields", "items", "has_more", "count"}
_FORBIDDEN_CREDENTIAL_MARKERS = (
    b"tushare_token",
    b'"token"',
    b"authorization",
    b"api_key",
)


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _text(name: str, value: object, *, nonempty: bool = True) -> str:
    if (
        type(value) is not str
        or (nonempty and not value)
        or value != value.strip()
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be canonical text")
    value.encode("utf-8")
    return value


def _hash(name: str, value: object) -> str:
    result = _text(name, value)
    if _HASH.fullmatch(result) is None:
        raise ValueError(f"{name} must be canonical sha256")
    return result


def _instant(name: str, value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError(f"{name} must be exact UtcInstant")
    instant = cast(UtcInstant, value)
    if type(instant.epoch_nanoseconds) is not int:
        raise TypeError(f"{name} must be exact UtcInstant")
    return UtcInstant(instant.epoch_nanoseconds)


def _instrument(value: object) -> InstrumentId:
    if type(value) is not InstrumentId:
        raise TypeError("instrument_id must be exact InstrumentId")
    instrument = cast(InstrumentId, value)
    if type(instrument.venue) is not VenueId:
        raise TypeError("instrument_id must be exact InstrumentId")
    return InstrumentId(VenueId(instrument.venue.value), instrument.stable_key)


def _strings(name: str, value: object) -> tuple[str, ...]:
    if type(value) is not tuple or any(type(item) is not str for item in value):
        raise TypeError(f"{name} must be tuple[str, ...]")
    return tuple(_text(f"{name} item", item) for item in value)


def _hashes(name: str, value: object) -> tuple[str, ...]:
    return tuple(_hash(f"{name} item", item) for item in _strings(name, value))


def _source_rows(name: str, value: object) -> tuple[tuple[str | None, ...], ...]:
    if type(value) is not tuple or any(type(row) is not tuple for row in value):
        raise TypeError(f"{name} must be tuple[tuple[str | None, ...], ...]")
    rows = cast(tuple[tuple[object, ...], ...], value)
    if any(
        len(row) != len(_FIELDS)
        or any(item is not None and type(item) is not str for item in row)
        for row in rows
    ):
        raise TypeError(f"{name} row shape mismatch")
    return cast(tuple[tuple[str | None, ...], ...], rows)


def _source_row_bytes(row: tuple[str | None, ...]) -> bytes:
    values: list[bytes] = []
    for index, value in enumerate(row):
        if value is None:
            values.append(b"null")
        elif index in _NUMERIC_INDICES:
            values.append(value.encode("ascii"))
        else:
            values.append(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    return b"[" + b",".join(values) + b"]"


def _replay_source_rows(
    rows: tuple[tuple[str | None, ...], ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    fields = json.dumps(
        list(_FIELDS), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    hashes: list[str] = []
    selected: list[str] = []
    relevance_indices = tuple(_FIELDS.index(name) for name in _RELEVANCE_FIELDS)
    for row in rows:
        if (
            row[0] != "000001.SZ"
            or type(row[3]) is not str
            or any(not _canonical_date(row[index]) for index in _DATE_INDICES)
        ):
            raise ValueError("source row primitive mismatch")
        for index in _NUMERIC_INDICES:
            value = row[index]
            if value is None:
                continue
            if _NUMBER.fullmatch(value) is None:
                raise ValueError("source row numeric lexeme mismatch")
            try:
                if not math.isfinite(float(value)):
                    raise ValueError("source row numeric lexeme is non-finite")
            except (OverflowError, ValueError) as error:
                raise ValueError("source row numeric lexeme mismatch") from error
        row_hash = _digest(
            b'{"fields":' + fields + b',"row":' + _source_row_bytes(row) + b"}"
        )
        hashes.append(row_hash)
        if any(
            type(row[index]) is str and "20260706" <= row[index] < "20260731"
            for index in relevance_indices
        ):
            selected.append(row_hash)
    return tuple(hashes), tuple(selected)


def _integers(name: str, value: object) -> tuple[int, ...]:
    if type(value) is not tuple or any(type(item) is not int for item in value):
        raise TypeError(f"{name} must be tuple[int, ...]")
    if any(item < 0 for item in value):
        raise ValueError(f"{name} must be nonnegative")
    return value


class _FailureCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    EVIDENCE_INVALID = "evidence_invalid"
    REQUEST_SCOPE_MISMATCH = "request_scope_mismatch"
    RESPONSE_SCHEMA_MISMATCH = "response_schema_mismatch"
    RESPONSE_PAGE_INCOMPLETE = "response_page_incomplete"
    SOURCE_REFERENCE_MISMATCH = "source_reference_mismatch"
    PREDECESSOR_INVALID = "predecessor_invalid"
    CORRECTION_EDGE_INVALID = "correction_edge_invalid"
    REPORT_BINDING_MISMATCH = "report_binding_mismatch"


@dataclass(frozen=True, slots=True)
class _Failure:
    code: _FailureCode
    member_key: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not _FailureCode:
            raise TypeError("code must be exact G12K failure code")
        if self.member_key is not None:
            _text("member_key", self.member_key)

    def _body(self) -> dict[str, object]:
        return {
            "type": "g12k_fixed_instrument_source_bounded_observation_failure",
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
class G12KFixedInstrumentSourceBoundedObservationReportV1:
    provider_key: str
    datasets: tuple[str, ...]
    instrument_id: InstrumentId
    catalog_artifact_canonical_file_sha256: str
    catalog_publication_hash: str
    catalog_source_hash: str
    instrument_catalog_hash: str
    venue_calendar: str
    provider_exchange: str
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    g12i_report_canonical_file_sha256: str
    g12i_report_hash: str
    g12i_snapshot_id: str
    g12i_manifest_content_hash: str
    g12i_bundle_ref_manifest_hash: str
    g12i_stream_content_hash: str
    observed_daily_provider_dates: tuple[str, ...]
    observed_daily_event_hashes: tuple[str, ...]
    no_session_provider_dates: tuple[str, ...]
    suspended_provider_dates: tuple[str, ...]
    acquisition_request_scope_hash: str
    acquisition_receipt_sha256: str
    snapshot_id: str
    snapshot_content_tree_hash: str
    provenance_hash: str
    member_keys: tuple[str, ...]
    member_content_hashes: tuple[str, ...]
    member_acquired_at_epoch_nanoseconds: tuple[int, ...]
    dividend_response_has_more: bool
    dividend_response_count_metadata: int
    dividend_source_rows: tuple[tuple[str | None, ...], ...]
    dividend_source_row_hashes: tuple[str, ...]
    target_relevance_fields: tuple[str, ...]
    target_relevant_row_hashes: tuple[str, ...]
    observed_at: UtcInstant
    supersedes_report_hash: str | None
    limitations: tuple[str, ...]
    availability_closure_complete: bool
    revision_closure_complete: bool
    provider_authority_qualified: bool
    provider_revision_completeness_qualified: bool
    historical_listing_status_qualified: bool
    listing_membership_continuity_qualified: bool
    whole_universe_complete: bool
    survivorship_bias_safe: bool
    corporate_action_lifecycle_qualified: bool
    decision_grade_eligible: bool
    profile_qualified: bool
    live_eligible: bool
    deployment_authorized: bool
    report_hash: str = field(init=False)

    def __post_init__(self) -> None:
        if self.provider_key != _PROVIDER_KEY or self.datasets != _DATASETS:
            raise ValueError("report provider/dataset scope mismatch")
        if _instrument(self.instrument_id) != _INSTRUMENT:
            raise ValueError("report instrument scope mismatch")
        fixed_hashes = {
            "catalog_artifact_canonical_file_sha256": _CATALOG_CANONICAL_FILE_SHA256,
            "catalog_publication_hash": _CATALOG_PUBLICATION_HASH,
            "catalog_source_hash": _CATALOG_SOURCE_HASH,
            "instrument_catalog_hash": _INSTRUMENT_CATALOG_HASH,
            "g12i_report_canonical_file_sha256": _G12I_CANONICAL_FILE_SHA256,
            "g12i_report_hash": _G12I_REPORT_HASH,
            "g12i_snapshot_id": _G12I_SNAPSHOT_ID,
            "g12i_manifest_content_hash": _G12I_MANIFEST_CONTENT_HASH,
            "g12i_bundle_ref_manifest_hash": _G12I_BUNDLE_REF_MANIFEST_HASH,
            "g12i_stream_content_hash": _G12I_STREAM_CONTENT_HASH,
            "acquisition_request_scope_hash": _REQUEST_SCOPE_HASH,
        }
        if any(
            _hash(name, getattr(self, name)) != expected
            for name, expected in fixed_hashes.items()
        ):
            raise ValueError("report accepted source identity mismatch")
        for name in (
            "acquisition_receipt_sha256",
            "snapshot_id",
            "snapshot_content_tree_hash",
            "provenance_hash",
        ):
            _hash(name, getattr(self, name))
        if (
            self.venue_calendar != _VENUE_CALENDAR
            or self.provider_exchange != _PROVIDER_EXCHANGE
            or _instant("coverage_start", self.coverage_start) != _COVERAGE_START
            or _instant("coverage_end_exclusive", self.coverage_end_exclusive)
            != _COVERAGE_END_EXCLUSIVE
        ):
            raise ValueError("report calendar/time scope mismatch")
        if (
            _strings(
                "observed_daily_provider_dates",
                self.observed_daily_provider_dates,
            )
            != _G12I_OBSERVED_DATES
            or _hashes(
                "observed_daily_event_hashes",
                self.observed_daily_event_hashes,
            )
            != _G12I_EVENT_HASHES
            or _strings("no_session_provider_dates", self.no_session_provider_dates)
            != _G12I_NO_SESSION_DATES
            or self.suspended_provider_dates != ()
        ):
            raise ValueError("report accepted G12I observation mismatch")
        member_keys = _strings("member_keys", self.member_keys)
        member_hashes = _hashes("member_content_hashes", self.member_content_hashes)
        member_times = _integers(
            "member_acquired_at_epoch_nanoseconds",
            self.member_acquired_at_epoch_nanoseconds,
        )
        if (
            member_keys != (_MEMBER_KEY,)
            or len(member_hashes) != 1
            or len(member_times) != 1
        ):
            raise ValueError("report member binding mismatch")
        if type(self.dividend_response_has_more) is not bool:
            raise TypeError("dividend_response_has_more must be exact bool")
        if self.dividend_response_has_more:
            raise ValueError("dividend response must be terminal")
        if (
            type(self.dividend_response_count_metadata) is not int
            or self.dividend_response_count_metadata < 0
        ):
            raise ValueError("dividend response count metadata mismatch")
        source_rows = _source_rows("dividend_source_rows", self.dividend_source_rows)
        replayed_hashes, replayed_targets = _replay_source_rows(source_rows)
        source_row_hashes = _hashes(
            "dividend_source_row_hashes", self.dividend_source_row_hashes
        )
        target_row_hashes = _hashes(
            "target_relevant_row_hashes", self.target_relevant_row_hashes
        )
        if (
            self.target_relevance_fields != _RELEVANCE_FIELDS
            or source_row_hashes != replayed_hashes
            or target_row_hashes != replayed_targets
        ):
            raise ValueError("report deterministic row binding mismatch")
        observed_at = _instant("observed_at", self.observed_at)
        if observed_at.epoch_nanoseconds != max(
            1_787_292_861_381_694_496,
            *member_times,
        ):
            raise ValueError("report observation time mismatch")
        if self.supersedes_report_hash is not None:
            _hash("supersedes_report_hash", self.supersedes_report_hash)
        if self.limitations != _LIMITATIONS:
            raise ValueError("report limitations mismatch")
        flags = (
            self.availability_closure_complete,
            self.revision_closure_complete,
            self.provider_authority_qualified,
            self.provider_revision_completeness_qualified,
            self.historical_listing_status_qualified,
            self.listing_membership_continuity_qualified,
            self.whole_universe_complete,
            self.survivorship_bias_safe,
            self.corporate_action_lifecycle_qualified,
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
            "type": "g12k_fixed_instrument_source_bounded_observation_report",
            "schema_version": _SCHEMA_VERSION,
            "provider_key": self.provider_key,
            "datasets": self.datasets,
            "instrument_id": self.instrument_id,
            "catalog_artifact_canonical_file_sha256": self.catalog_artifact_canonical_file_sha256,
            "catalog_publication_hash": self.catalog_publication_hash,
            "catalog_source_hash": self.catalog_source_hash,
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "venue_calendar": self.venue_calendar,
            "provider_exchange": self.provider_exchange,
            "coverage_start": self.coverage_start,
            "coverage_end_exclusive": self.coverage_end_exclusive,
            "g12i_report_canonical_file_sha256": self.g12i_report_canonical_file_sha256,
            "g12i_report_hash": self.g12i_report_hash,
            "g12i_snapshot_id": self.g12i_snapshot_id,
            "g12i_manifest_content_hash": self.g12i_manifest_content_hash,
            "g12i_bundle_ref_manifest_hash": self.g12i_bundle_ref_manifest_hash,
            "g12i_stream_content_hash": self.g12i_stream_content_hash,
            "observed_daily_provider_dates": self.observed_daily_provider_dates,
            "observed_daily_event_hashes": self.observed_daily_event_hashes,
            "no_session_provider_dates": self.no_session_provider_dates,
            "suspended_provider_dates": self.suspended_provider_dates,
            "acquisition_request_scope_hash": self.acquisition_request_scope_hash,
            "acquisition_receipt_sha256": self.acquisition_receipt_sha256,
            "snapshot_id": self.snapshot_id,
            "snapshot_content_tree_hash": self.snapshot_content_tree_hash,
            "provenance_hash": self.provenance_hash,
            "member_keys": self.member_keys,
            "member_content_hashes": self.member_content_hashes,
            "member_acquired_at_epoch_nanoseconds": self.member_acquired_at_epoch_nanoseconds,
            "dividend_response_has_more": self.dividend_response_has_more,
            "dividend_response_count_metadata": self.dividend_response_count_metadata,
            "dividend_source_rows": self.dividend_source_rows,
            "dividend_source_row_hashes": self.dividend_source_row_hashes,
            "target_relevance_fields": self.target_relevance_fields,
            "target_relevant_row_hashes": self.target_relevant_row_hashes,
            "observed_at": self.observed_at,
            "supersedes_report_hash": self.supersedes_report_hash,
            "limitations": self.limitations,
            "availability_closure_complete": self.availability_closure_complete,
            "revision_closure_complete": self.revision_closure_complete,
            "provider_authority_qualified": self.provider_authority_qualified,
            "provider_revision_completeness_qualified": self.provider_revision_completeness_qualified,
            "historical_listing_status_qualified": self.historical_listing_status_qualified,
            "listing_membership_continuity_qualified": self.listing_membership_continuity_qualified,
            "whole_universe_complete": self.whole_universe_complete,
            "survivorship_bias_safe": self.survivorship_bias_safe,
            "corporate_action_lifecycle_qualified": self.corporate_action_lifecycle_qualified,
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
    ) -> G12KFixedInstrumentSourceBoundedObservationReportV1:
        if type(value) is not dict:
            raise TypeError("report canonical value must be exact dict")
        body = cast(dict[str, object], value)
        expected_keys = {"type", "schema_version", *cls.__dataclass_fields__.keys()}
        if set(body) != expected_keys:
            raise ValueError("report canonical keys mismatch")
        if (
            body["type"] != "g12k_fixed_instrument_source_bounded_observation_report"
            or body["schema_version"] != _SCHEMA_VERSION
        ):
            raise ValueError("report canonical schema mismatch")

        def instant(name: str) -> UtcInstant:
            item = body[name]
            if (
                type(item) is not dict
                or set(item) != {"type", "epoch_nanoseconds"}
                or item["type"] != "utc_instant"
                or type(item["epoch_nanoseconds"]) is not int
            ):
                raise ValueError(f"report canonical {name} mismatch")
            return UtcInstant(item["epoch_nanoseconds"])

        instrument = body["instrument_id"]
        if (
            type(instrument) is not dict
            or set(instrument) != {"type", "venue", "stable_key"}
            or instrument["type"] != "instrument_id"
            or type(instrument["venue"]) is not str
            or type(instrument["stable_key"]) is not str
        ):
            raise ValueError("report canonical instrument mismatch")

        def sequence(name: str) -> tuple[object, ...]:
            item = body[name]
            if type(item) is not list:
                raise TypeError(f"report canonical {name} must be exact list")
            return tuple(item)

        def rows(name: str) -> tuple[tuple[str | None, ...], ...]:
            item = body[name]
            if type(item) is not list or any(type(row) is not list for row in item):
                raise TypeError(f"report canonical {name} must be exact nested lists")
            return tuple(tuple(cast(list[str | None], row)) for row in item)

        report = cls(
            provider_key=cast(str, body["provider_key"]),
            datasets=cast(tuple[str, ...], sequence("datasets")),
            instrument_id=InstrumentId(
                VenueId(instrument["venue"]), instrument["stable_key"]
            ),
            catalog_artifact_canonical_file_sha256=cast(
                str, body["catalog_artifact_canonical_file_sha256"]
            ),
            catalog_publication_hash=cast(str, body["catalog_publication_hash"]),
            catalog_source_hash=cast(str, body["catalog_source_hash"]),
            instrument_catalog_hash=cast(str, body["instrument_catalog_hash"]),
            venue_calendar=cast(str, body["venue_calendar"]),
            provider_exchange=cast(str, body["provider_exchange"]),
            coverage_start=instant("coverage_start"),
            coverage_end_exclusive=instant("coverage_end_exclusive"),
            g12i_report_canonical_file_sha256=cast(
                str, body["g12i_report_canonical_file_sha256"]
            ),
            g12i_report_hash=cast(str, body["g12i_report_hash"]),
            g12i_snapshot_id=cast(str, body["g12i_snapshot_id"]),
            g12i_manifest_content_hash=cast(str, body["g12i_manifest_content_hash"]),
            g12i_bundle_ref_manifest_hash=cast(
                str, body["g12i_bundle_ref_manifest_hash"]
            ),
            g12i_stream_content_hash=cast(str, body["g12i_stream_content_hash"]),
            observed_daily_provider_dates=cast(
                tuple[str, ...], sequence("observed_daily_provider_dates")
            ),
            observed_daily_event_hashes=cast(
                tuple[str, ...], sequence("observed_daily_event_hashes")
            ),
            no_session_provider_dates=cast(
                tuple[str, ...], sequence("no_session_provider_dates")
            ),
            suspended_provider_dates=cast(
                tuple[str, ...], sequence("suspended_provider_dates")
            ),
            acquisition_request_scope_hash=cast(
                str, body["acquisition_request_scope_hash"]
            ),
            acquisition_receipt_sha256=cast(str, body["acquisition_receipt_sha256"]),
            snapshot_id=cast(str, body["snapshot_id"]),
            snapshot_content_tree_hash=cast(str, body["snapshot_content_tree_hash"]),
            provenance_hash=cast(str, body["provenance_hash"]),
            member_keys=cast(tuple[str, ...], sequence("member_keys")),
            member_content_hashes=cast(
                tuple[str, ...], sequence("member_content_hashes")
            ),
            member_acquired_at_epoch_nanoseconds=cast(
                tuple[int, ...],
                sequence("member_acquired_at_epoch_nanoseconds"),
            ),
            dividend_response_has_more=cast(bool, body["dividend_response_has_more"]),
            dividend_response_count_metadata=cast(
                int, body["dividend_response_count_metadata"]
            ),
            dividend_source_rows=rows("dividend_source_rows"),
            dividend_source_row_hashes=cast(
                tuple[str, ...], sequence("dividend_source_row_hashes")
            ),
            target_relevance_fields=cast(
                tuple[str, ...], sequence("target_relevance_fields")
            ),
            target_relevant_row_hashes=cast(
                tuple[str, ...], sequence("target_relevant_row_hashes")
            ),
            observed_at=instant("observed_at"),
            supersedes_report_hash=cast(str | None, body["supersedes_report_hash"]),
            limitations=cast(tuple[str, ...], sequence("limitations")),
            availability_closure_complete=cast(
                bool, body["availability_closure_complete"]
            ),
            revision_closure_complete=cast(bool, body["revision_closure_complete"]),
            provider_authority_qualified=cast(
                bool, body["provider_authority_qualified"]
            ),
            provider_revision_completeness_qualified=cast(
                bool, body["provider_revision_completeness_qualified"]
            ),
            historical_listing_status_qualified=cast(
                bool, body["historical_listing_status_qualified"]
            ),
            listing_membership_continuity_qualified=cast(
                bool, body["listing_membership_continuity_qualified"]
            ),
            whole_universe_complete=cast(bool, body["whole_universe_complete"]),
            survivorship_bias_safe=cast(bool, body["survivorship_bias_safe"]),
            corporate_action_lifecycle_qualified=cast(
                bool, body["corporate_action_lifecycle_qualified"]
            ),
            decision_grade_eligible=cast(bool, body["decision_grade_eligible"]),
            profile_qualified=cast(bool, body["profile_qualified"]),
            live_eligible=cast(bool, body["live_eligible"]),
            deployment_authorized=cast(bool, body["deployment_authorized"]),
        )
        if body["report_hash"] != report.report_hash:
            raise ValueError("report hash mismatch")
        if canonical_bytes(body) != canonical_bytes(report.to_canonical_dict()):
            raise ValueError("report canonical reconstruction mismatch")
        return report


@dataclass(frozen=True, slots=True)
class G12KFixedInstrumentSourceBoundedObservationOutcomeV1:
    report: G12KFixedInstrumentSourceBoundedObservationReportV1 | None = None
    failure: _Failure | None = None

    def __post_init__(self) -> None:
        if (self.report is None) == (self.failure is None):
            raise ValueError("outcome requires exactly one report or failure")
        if self.report is not None:
            trusted = _reconstruct_report(self.report)
            if trusted is None:
                raise ValueError("outcome report authority is invalid")
            object.__setattr__(self, "report", trusted)
        if self.failure is not None and type(self.failure) is not _Failure:
            raise TypeError("failure must be exact G12K failure")


@dataclass(frozen=True, slots=True)
class _JsonNumber:
    lexeme: str

    def __post_init__(self) -> None:
        if type(self.lexeme) is not str or _NUMBER.fullmatch(self.lexeme) is None:
            raise ValueError("invalid JSON number")


@dataclass(frozen=True, slots=True)
class _Response:
    rows: tuple[tuple[object, ...], ...]
    has_more: bool
    count: int


def _failed(
    code: _FailureCode, member_key: str | None = None
) -> G12KFixedInstrumentSourceBoundedObservationOutcomeV1:
    return G12KFixedInstrumentSourceBoundedObservationOutcomeV1(
        failure=_Failure(code, member_key)
    )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_constant(_: str) -> object:
    raise ValueError("non-finite JSON constant")


def _parse_canonical_mapping(source: bytes, name: str) -> dict[str, object]:
    try:
        parsed = json.loads(
            source.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"{name} must be valid unique-key JSON") from error
    if type(parsed) is not dict or source != canonical_bytes(parsed) + b"\n":
        raise ValueError(f"{name} must be canonical unique-key JSON")
    return parsed


def _parse_response(source: bytes) -> object:
    try:
        return json.loads(
            source.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_int=_JsonNumber,
            parse_float=_JsonNumber,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("response must be valid unique-key JSON") from error


def _reconstruct_report(
    value: object,
) -> G12KFixedInstrumentSourceBoundedObservationReportV1 | None:
    if type(value) is not G12KFixedInstrumentSourceBoundedObservationReportV1:
        return None
    try:
        parsed = json.loads(canonical_bytes(value.to_canonical_dict()))
        return G12KFixedInstrumentSourceBoundedObservationReportV1.from_canonical_dict(
            parsed
        )
    except Exception:  # noqa: BLE001 -- hostile constructor bypass is rejected.
        return None


def _g12i_report(
    source: bytes,
) -> TushareCnAShareDailySourceBoundedObservationReportV2:
    body = _parse_canonical_mapping(source, "G12I report")
    try:
        report = (
            TushareCnAShareDailySourceBoundedObservationReportV2.from_canonical_dict(
                body
            )
        )
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("G12I report reconstruction failed") from error
    if canonical_bytes(report.to_canonical_dict()) + b"\n" != source:
        raise ValueError("G12I report reconstruction mismatch")
    return report


def _catalog(value: InstrumentCatalog) -> InstrumentCatalog | None:
    try:
        if (
            type(value.currencies) is not tuple
            or type(value.instruments) is not tuple
            or type(value.symbol_timelines) is not tuple
            or len(value.currencies) != 1
            or len(value.instruments) != 1
            or value.symbol_timelines
        ):
            return None
        currency = value.currencies[0]
        definition = value.instruments[0]
        if (
            type(currency) is not CurrencyId
            or currency.value != "CNY"
            or type(definition) is not InstrumentDefinition
            or _instrument(definition.instrument_id) != _INSTRUMENT
            or type(definition.instrument_type) is not InstrumentType
            or definition.instrument_type is not InstrumentType.EQUITY
            or definition.base_currency is not None
            or type(definition.quote_currency) is not CurrencyId
            or definition.quote_currency.value != "CNY"
            or type(definition.settlement_currency) is not CurrencyId
            or definition.settlement_currency.value != "CNY"
        ):
            return None
        trusted_currency = CurrencyId("CNY")
        trusted = InstrumentCatalog(
            currencies=(trusted_currency,),
            instruments=(
                InstrumentDefinition(
                    _INSTRUMENT,
                    InstrumentType.EQUITY,
                    None,
                    trusted_currency,
                    trusted_currency,
                ),
            ),
            symbol_timelines=(),
        )
        if (
            canonical_bytes(value) != canonical_bytes(trusted)
            or canonical_sha256(trusted) != _INSTRUMENT_CATALOG_HASH
        ):
            return None
        return trusted
    except Exception:  # noqa: BLE001 -- hostile catalog objects fail closed.
        return None


def _receipt(source: bytes) -> dict[str, object]:
    receipt = _parse_canonical_mapping(source, "receipt")
    if (
        set(receipt) != _RECEIPT_KEYS
        or receipt["type"]
        != "tushare_g12k_fixed_instrument_source_bounded_acquisition_receipt"
        or receipt["schema_version"] != 1
        or type(receipt["request"]) is not dict
        or type(receipt["provider_requests"]) is not list
        or len(receipt["provider_requests"]) != 1
        or type(receipt["acquired_at_epoch_nanoseconds"]) is not int
        or receipt["acquired_at_epoch_nanoseconds"] < 0
        or type(receipt["snapshot"]) is not dict
        or receipt["provider_declared_sha256"] is not None
        or receipt["provider_revision_id"] is not None
        or type(receipt["decision_grade_eligible"]) is not bool
        or receipt["decision_grade_eligible"]
        or type(receipt["deployment_authorized"]) is not bool
        or receipt["deployment_authorized"]
    ):
        raise ValueError("receipt nominal mapping mismatch")
    request = receipt["provider_requests"][0]
    if type(request) is not dict or set(request) != _PROVIDER_REQUEST_KEYS:
        raise ValueError("provider request nominal mapping mismatch")
    envelope = request["observed_envelope"]
    if (
        type(request["api_name"]) is not str
        or type(request["params"]) is not dict
        or any(type(key) is not str for key in request["params"])
        or type(request["fields"]) is not str
        or type(request["member_key"]) is not str
        or type(request["attempts"]) is not int
        or request["attempts"] <= 0
        or type(request["response_received_at_epoch_nanoseconds"]) is not int
        or request["response_received_at_epoch_nanoseconds"] < 0
        or type(request["response_byte_count"]) is not int
        or request["response_byte_count"] < 0
        or type(request["returned_row_count"]) is not int
        or request["returned_row_count"] < 0
        or type(envelope) is not dict
        or set(envelope) != {"has_more", "count"}
        or type(envelope["has_more"]) is not bool
        or type(envelope["count"]) is not int
        or envelope["count"] < 0
        or request["declared_sha256"] is not None
        or request["provider_revision_id"] is not None
    ):
        raise ValueError("provider request primitive mismatch")
    _text("api_name", request["api_name"])
    _text("fields", request["fields"])
    _text("member_key", request["member_key"])
    _hash("response_sha256", request["response_sha256"])
    _hash("request_scope_hash", receipt["request_scope_hash"])
    return receipt


def _evidence(
    receipt_bytes: bytes, snapshot: SourceSnapshot
) -> tuple[dict[str, object], SourceSnapshot, bytes] | None:
    try:
        receipt = _receipt(receipt_bytes)
        verified = verify_source_snapshot(snapshot)
        if verified.snapshot is None:
            return None
        trusted = verified.snapshot
        if receipt["snapshot"] != trusted.to_canonical_dict():
            return None
        requests = cast(list[dict[str, object]], receipt["provider_requests"])
        request = requests[0]
        if len(trusted.members) != 1:
            return None
        member = trusted.members[0]
        raw = trusted.member_bytes(member.member_key)
        if (
            receipt["acquired_at_epoch_nanoseconds"]
            != request["response_received_at_epoch_nanoseconds"]
            or request["response_received_at_epoch_nanoseconds"]
            != member.acquired_at_epoch_nanoseconds
            or request["response_byte_count"] != member.byte_count
            or request["response_sha256"] != member.content_hash
            or _digest(raw) != member.content_hash
            or any(
                marker in receipt_bytes.lower() or marker in raw.lower()
                for marker in _FORBIDDEN_CREDENTIAL_MARKERS
            )
        ):
            return None
        return receipt, trusted, raw
    except Exception:  # noqa: BLE001 -- evidence failures expose no raw data.
        return None


def _request_scope(receipt: dict[str, object], snapshot: SourceSnapshot) -> bool:
    request = cast(dict[str, object], receipt["request"])
    provider_request = cast(list[dict[str, object]], receipt["provider_requests"])[0]
    expected_request = {
        "type": "tushare_g12k_fixed_instrument_source_bounded_request",
        "schema_version": 1,
        "ts_code": "000001.SZ",
        "coverage_start_date": "20260706",
        "coverage_end_date_exclusive": "20260731",
    }
    expected_provenance = {
        "vendor_key": _PROVIDER_KEY,
        "source_key": _SOURCE_KEY,
        "license_ref": "tushare.pro.terms",
        "retention_policy_ref": "backtest.acquisition.candidate",
    }
    coordinates = (
        provider_request["api_name"],
        provider_request["params"],
        provider_request["fields"],
        provider_request["member_key"],
    )
    expected_coordinates = (
        "dividend",
        {"ts_code": "000001.SZ"},
        ",".join(_FIELDS),
        _MEMBER_KEY,
    )
    preimage = {
        "type": "g12k_fixed_instrument_acquisition_request_scope",
        "schema_version": 1,
        "provider_key": snapshot.provenance.vendor_key,
        "api_name": provider_request["api_name"],
        "params": provider_request["params"],
        "fields": tuple(cast(str, provider_request["fields"]).split(",")),
        "member_key": provider_request["member_key"],
        "instrument_id": _INSTRUMENT,
        "instrument_catalog_hash": _INSTRUMENT_CATALOG_HASH,
        "venue_calendar": _VENUE_CALENDAR,
        "provider_exchange": _PROVIDER_EXCHANGE,
        "coverage_start": _COVERAGE_START,
        "coverage_end_exclusive": _COVERAGE_END_EXCLUSIVE,
    }
    try:
        preimage_hash = canonical_sha256(preimage)
    except (TypeError, ValueError):
        return False
    return (
        request == expected_request
        and snapshot.provenance.to_canonical_dict() == expected_provenance
        and coordinates == expected_coordinates
        and receipt["request_scope_hash"] == preimage_hash == _REQUEST_SCOPE_HASH
        and snapshot.members[0].member_key == _MEMBER_KEY
    )


def _number_integer(value: object) -> int | None:
    if type(value) is not _JsonNumber or any(
        marker in value.lexeme.lower() for marker in (".", "e")
    ):
        return None
    try:
        return int(value.lexeme)
    except ValueError:
        return None


def _canonical_date(value: object) -> bool:
    if value is None:
        return True
    if type(value) is not str or _DATE.fullmatch(value) is None:
        return False
    try:
        date.fromisoformat(f"{value[:4]}-{value[4:6]}-{value[6:]}")
    except ValueError:
        return False
    return True


def _response(source: bytes) -> _Response:
    parsed = _parse_response(source)
    if type(parsed) is not dict or set(parsed) != _RESPONSE_KEYS:
        raise ValueError("response envelope mismatch")
    data = parsed["data"]
    code = _number_integer(parsed["code"])
    if (
        type(parsed["request_id"]) is not str
        or not parsed["request_id"]
        or parsed["request_id"] != parsed["request_id"].strip()
        or code != 0
        or parsed["msg"] != ""
        or type(parsed["detail"]) is not str
        or type(data) is not dict
        or set(data) != _RESPONSE_DATA_KEYS
        or type(data["fields"]) is not list
        or tuple(data["fields"]) != _FIELDS
        or any(type(item) is not str for item in data["fields"])
        or type(data["items"]) is not list
        or type(data["has_more"]) is not bool
    ):
        raise ValueError("response schema mismatch")
    count = _number_integer(data["count"])
    if count is None or count < 0:
        raise ValueError("response count mismatch")
    rows: list[tuple[object, ...]] = []
    for source_row in data["items"]:
        if type(source_row) is not list or len(source_row) != len(_FIELDS):
            raise ValueError("response row shape mismatch")
        row = tuple(source_row)
        if (
            row[0] != "000001.SZ"
            or type(row[3]) is not str
            or any(
                not _canonical_date(row[index])
                for index in (1, 2, 9, 10, 11, 12, 13, 14)
            )
            or any(
                row[index] is not None and type(row[index]) is not _JsonNumber
                for index in (4, 5, 6, 7, 8, 15)
            )
        ):
            raise ValueError("response row primitive mismatch")
        for item in row:
            if type(item) is _JsonNumber:
                try:
                    if not math.isfinite(float(item.lexeme)):
                        raise ValueError("response numeric value is non-finite")
                except (OverflowError, ValueError) as error:
                    raise ValueError("response numeric value is invalid") from error
            elif item is not None and type(item) is not str:
                raise ValueError("response row primitive mismatch")
        rows.append(row)
    return _Response(tuple(rows), data["has_more"], count)


def _row_bindings(
    response: _Response,
) -> tuple[
    tuple[tuple[str | None, ...], ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    source_rows = tuple(
        tuple(value.lexeme if type(value) is _JsonNumber else value for value in row)
        for row in response.rows
    )
    trusted_rows = _source_rows("dividend_source_rows", source_rows)
    source_hashes, target_hashes = _replay_source_rows(trusted_rows)
    return trusted_rows, source_hashes, target_hashes


def _g12i_matches(
    source: bytes, report: TushareCnAShareDailySourceBoundedObservationReportV2
) -> bool:
    return (
        _digest(source) == _G12I_CANONICAL_FILE_SHA256
        and report.report_hash == _G12I_REPORT_HASH
        and report.acquisition_receipt_sha256 == _G12I_RECEIPT_SHA256
        and report.snapshot_id == _G12I_SNAPSHOT_ID
        and report.snapshot_content_tree_hash == _G12I_SNAPSHOT_CONTENT_TREE_HASH
        and report.provenance_hash == _G12I_PROVENANCE_HASH
        and report.manifest_content_hash == _G12I_MANIFEST_CONTENT_HASH
        and report.bundle_ref.manifest_hash == _G12I_BUNDLE_REF_MANIFEST_HASH
        and report.stream_content_hash == _G12I_STREAM_CONTENT_HASH
        and report.published_provider_dates == _G12I_OBSERVED_DATES
        and report.published_event_hashes == _G12I_EVENT_HASHES
        and report.no_session_provider_dates == _G12I_NO_SESSION_DATES
        and report.suspended_provider_dates == ()
        and report.provider_key == _PROVIDER_KEY
        and report.instrument_id == _INSTRUMENT
        and report.coverage_start == _COVERAGE_START
        and report.coverage_end_exclusive == _COVERAGE_END_EXCLUSIVE
    )


def _build_report(
    *,
    g12i_report: TushareCnAShareDailySourceBoundedObservationReportV2,
    receipt_bytes: bytes,
    snapshot: SourceSnapshot,
    response: _Response,
    source_rows: tuple[tuple[str | None, ...], ...],
    source_row_hashes: tuple[str, ...],
    target_row_hashes: tuple[str, ...],
    supersedes_report_hash: str | None,
) -> G12KFixedInstrumentSourceBoundedObservationReportV1:
    member = snapshot.members[0]
    return G12KFixedInstrumentSourceBoundedObservationReportV1(
        provider_key=_PROVIDER_KEY,
        datasets=_DATASETS,
        instrument_id=_INSTRUMENT,
        catalog_artifact_canonical_file_sha256=_CATALOG_CANONICAL_FILE_SHA256,
        catalog_publication_hash=_CATALOG_PUBLICATION_HASH,
        catalog_source_hash=_CATALOG_SOURCE_HASH,
        instrument_catalog_hash=_INSTRUMENT_CATALOG_HASH,
        venue_calendar=_VENUE_CALENDAR,
        provider_exchange=_PROVIDER_EXCHANGE,
        coverage_start=_COVERAGE_START,
        coverage_end_exclusive=_COVERAGE_END_EXCLUSIVE,
        g12i_report_canonical_file_sha256=_G12I_CANONICAL_FILE_SHA256,
        g12i_report_hash=g12i_report.report_hash,
        g12i_snapshot_id=g12i_report.snapshot_id,
        g12i_manifest_content_hash=g12i_report.manifest_content_hash,
        g12i_bundle_ref_manifest_hash=g12i_report.bundle_ref.manifest_hash,
        g12i_stream_content_hash=g12i_report.stream_content_hash,
        observed_daily_provider_dates=g12i_report.published_provider_dates,
        observed_daily_event_hashes=g12i_report.published_event_hashes,
        no_session_provider_dates=g12i_report.no_session_provider_dates,
        suspended_provider_dates=g12i_report.suspended_provider_dates,
        acquisition_request_scope_hash=_REQUEST_SCOPE_HASH,
        acquisition_receipt_sha256=_digest(receipt_bytes),
        snapshot_id=snapshot.snapshot_id,
        snapshot_content_tree_hash=snapshot.content_tree_hash,
        provenance_hash=snapshot.provenance_hash,
        member_keys=(member.member_key,),
        member_content_hashes=(member.content_hash,),
        member_acquired_at_epoch_nanoseconds=(member.acquired_at_epoch_nanoseconds,),
        dividend_response_has_more=response.has_more,
        dividend_response_count_metadata=response.count,
        dividend_source_rows=source_rows,
        dividend_source_row_hashes=source_row_hashes,
        target_relevance_fields=_RELEVANCE_FIELDS,
        target_relevant_row_hashes=target_row_hashes,
        observed_at=UtcInstant(
            max(
                g12i_report.observed_at.epoch_nanoseconds,
                member.acquired_at_epoch_nanoseconds,
            )
        ),
        supersedes_report_hash=supersedes_report_hash,
        limitations=_LIMITATIONS,
        availability_closure_complete=False,
        revision_closure_complete=False,
        provider_authority_qualified=False,
        provider_revision_completeness_qualified=False,
        historical_listing_status_qualified=False,
        listing_membership_continuity_qualified=False,
        whole_universe_complete=False,
        survivorship_bias_safe=False,
        corporate_action_lifecycle_qualified=False,
        decision_grade_eligible=False,
        profile_qualified=False,
        live_eligible=False,
        deployment_authorized=False,
    )


def _predecessor(
    *,
    report: G12KFixedInstrumentSourceBoundedObservationReportV1,
    receipt_bytes: bytes,
    snapshot: SourceSnapshot,
    g12i_report: TushareCnAShareDailySourceBoundedObservationReportV2,
) -> G12KFixedInstrumentSourceBoundedObservationReportV1 | None:
    trusted_report = _reconstruct_report(report)
    evidence = _evidence(receipt_bytes, snapshot)
    if trusted_report is None or evidence is None:
        return None
    receipt, trusted_snapshot, response_bytes = evidence
    if not _request_scope(receipt, trusted_snapshot):
        return None
    try:
        response = _response(response_bytes)
    except (AttributeError, TypeError, ValueError):
        return None
    provider_request = cast(list[dict[str, object]], receipt["provider_requests"])[0]
    if (
        response.has_more
        or provider_request["returned_row_count"] != len(response.rows)
        or provider_request["observed_envelope"]
        != {"has_more": response.has_more, "count": response.count}
    ):
        return None
    source_rows, source_hashes, target_hashes = _row_bindings(response)
    try:
        expected = _build_report(
            g12i_report=g12i_report,
            receipt_bytes=receipt_bytes,
            snapshot=trusted_snapshot,
            response=response,
            source_rows=source_rows,
            source_row_hashes=source_hashes,
            target_row_hashes=target_hashes,
            supersedes_report_hash=trusted_report.supersedes_report_hash,
        )
        rebuilt = _reconstruct_report(expected)
    except (AttributeError, TypeError, ValueError):
        return None
    if rebuilt is None or canonical_bytes(rebuilt) != canonical_bytes(trusted_report):
        return None
    return trusted_report


def observe_g12k_tushare_fixed_instrument_source_bounded_v1(
    *,
    g12i_report_bytes: bytes,
    acquisition_receipt_bytes: bytes,
    snapshot: SourceSnapshot,
    instrument_catalog: InstrumentCatalog,
    supersedes_report: G12KFixedInstrumentSourceBoundedObservationReportV1
    | None = None,
    supersedes_acquisition_receipt_bytes: bytes | None = None,
    supersedes_snapshot: SourceSnapshot | None = None,
) -> G12KFixedInstrumentSourceBoundedObservationOutcomeV1:
    if (
        type(g12i_report_bytes) is not bytes
        or type(acquisition_receipt_bytes) is not bytes
        or type(snapshot) is not SourceSnapshot
        or type(instrument_catalog) is not InstrumentCatalog
        or (
            supersedes_report is not None
            and type(supersedes_report)
            is not G12KFixedInstrumentSourceBoundedObservationReportV1
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

    try:
        g12i_report = _g12i_report(g12i_report_bytes)
    except (AttributeError, TypeError, ValueError):
        return _failed(_FailureCode.EVIDENCE_INVALID)
    evidence = _evidence(acquisition_receipt_bytes, snapshot)
    if evidence is None:
        return _failed(_FailureCode.EVIDENCE_INVALID)
    receipt, snapshot, response_bytes = evidence
    trusted_catalog = _catalog(instrument_catalog)
    response: _Response | None = None
    response_invalid = False
    try:
        response = _response(response_bytes)
    except (AttributeError, TypeError, ValueError):
        response_invalid = True
    if response is not None:
        provider_request = cast(list[dict[str, object]], receipt["provider_requests"])[
            0
        ]
        if provider_request["returned_row_count"] != len(
            response.rows
        ) or provider_request["observed_envelope"] != {
            "has_more": response.has_more,
            "count": response.count,
        }:
            return _failed(_FailureCode.EVIDENCE_INVALID, _MEMBER_KEY)

    if not _request_scope(receipt, snapshot):
        return _failed(_FailureCode.REQUEST_SCOPE_MISMATCH, _MEMBER_KEY)
    if response_invalid or response is None:
        return _failed(_FailureCode.RESPONSE_SCHEMA_MISMATCH, _MEMBER_KEY)
    if response.has_more:
        return _failed(_FailureCode.RESPONSE_PAGE_INCOMPLETE, _MEMBER_KEY)
    if not _g12i_matches(g12i_report_bytes, g12i_report) or trusted_catalog is None:
        return _failed(_FailureCode.SOURCE_REFERENCE_MISMATCH)

    predecessor_inputs = (
        supersedes_report is not None,
        supersedes_acquisition_receipt_bytes is not None,
        supersedes_snapshot is not None,
    )
    if any(predecessor_inputs) and not all(predecessor_inputs):
        return _failed(_FailureCode.PREDECESSOR_INVALID)

    trusted_predecessor = None
    if supersedes_report is not None:
        trusted_predecessor = _predecessor(
            report=supersedes_report,
            receipt_bytes=cast(bytes, supersedes_acquisition_receipt_bytes),
            snapshot=cast(SourceSnapshot, supersedes_snapshot),
            g12i_report=g12i_report,
        )
        if trusted_predecessor is None:
            return _failed(_FailureCode.PREDECESSOR_INVALID)

    source_rows, source_row_hashes, target_row_hashes = _row_bindings(response)
    observed_at = max(
        g12i_report.observed_at.epoch_nanoseconds,
        snapshot.members[0].acquired_at_epoch_nanoseconds,
    )
    supersedes_hash = None
    if trusted_predecessor is not None:
        same_scope = (
            trusted_predecessor.provider_key == _PROVIDER_KEY
            and trusted_predecessor.datasets == _DATASETS
            and trusted_predecessor.instrument_id == _INSTRUMENT
            and trusted_predecessor.instrument_catalog_hash == _INSTRUMENT_CATALOG_HASH
            and trusted_predecessor.coverage_start == _COVERAGE_START
            and trusted_predecessor.coverage_end_exclusive == _COVERAGE_END_EXCLUSIVE
            and trusted_predecessor.g12i_report_hash == _G12I_REPORT_HASH
        )
        if (
            not same_scope
            or trusted_predecessor.snapshot_id == snapshot.snapshot_id
            or observed_at <= trusted_predecessor.observed_at.epoch_nanoseconds
        ):
            return _failed(_FailureCode.CORRECTION_EDGE_INVALID)
        supersedes_hash = trusted_predecessor.report_hash

    try:
        report = _build_report(
            g12i_report=g12i_report,
            receipt_bytes=acquisition_receipt_bytes,
            snapshot=snapshot,
            response=response,
            source_rows=source_rows,
            source_row_hashes=source_row_hashes,
            target_row_hashes=target_row_hashes,
            supersedes_report_hash=supersedes_hash,
        )
        trusted_report = _reconstruct_report(report)
        if trusted_report is None or canonical_bytes(trusted_report) != canonical_bytes(
            report
        ):
            raise ValueError("completed report reconstruction mismatch")
    except (AttributeError, TypeError, ValueError):
        return _failed(_FailureCode.REPORT_BINDING_MISMATCH)
    return G12KFixedInstrumentSourceBoundedObservationOutcomeV1(report=trusted_report)
