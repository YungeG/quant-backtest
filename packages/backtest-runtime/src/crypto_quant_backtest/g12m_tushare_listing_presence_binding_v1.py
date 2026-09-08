"""Pure post-assessment binding for accepted G12M and G12L Tushare evidence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

import crypto_quant_domain as domain

from .g12m_tushare_fixed_singleton_assessment_v2 import (
    TushareFixedSingletonSourceBoundedAssessmentV2,
)
from .integrity import ResultGrade
from .resolution import RequestedResultGrade

_BASE_ASSESSMENT_HASH = (
    "sha256:31f29b9ab70e7c8da267b6c17dcbe294503088850c894b066116313233dca8bb"
)
_SEMANTIC_RUN_ID = "run_1eebd60b81376e15fbe4b2496ed359ab24ed644c7416812d09eb3fb715f581a9"
_LISTING_FILE_HASH = (
    "sha256:24122b0a68c87f7bdc5723640724733a2d1f25a7c1b62b0f02eb17bdad2d0205"
)
_LISTING_REPORT_HASH = (
    "sha256:6d120c94b8d08fa00389d91894bc17d18ad4a6e0c1f9c42b859e7f1e26cc41c8"
)
_LISTING_SNAPSHOT_ID = (
    "sha256:3144690c004ea0b8a727d33943e47c00cecd257bf8c142f15982d70f745c25e8"
)
_LISTING_REQUEST_SCOPE_HASH = (
    "sha256:aaa6995714b99510137c667783d272010c848c40aa2ac4a359b6de04a4ac3dd0"
)
_CATALOG_HASH = (
    "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc"
)
_INSTRUMENT = domain.InstrumentId(domain.VenueId("xshe"), "000001")
_TRADE_DATE = "20240102"
_CURRENT_NAME = "平安银行"
_LIST_DATE = "19910403"
_INTERVAL_START = "20120802"
_LISTING_OBSERVED_AT = 1787533249650679470
_STOCK_ROW = [
    "000001.SZ",
    "000001",
    _CURRENT_NAME,
    "主板",
    "SZSE",
    "L",
    _LIST_DATE,
    None,
]
_BAK_ROW = [_TRADE_DATE, "000001.SZ", _CURRENT_NAME, _LIST_DATE]
_TARGET_NAME_ROW = [
    "000001.SZ",
    _CURRENT_NAME,
    _INTERVAL_START,
    None,
    "20120120",
    "其他",
]
_SOURCE_RECORD_HASHES = [
    "sha256:18722c9d539a8667e3bd564f85e48bfbf3a6bff8dfaf039490f48fa5bc90b013",
    "sha256:0bf486b238cbad164cd155eef1efd42ba1fe575292f17b2b17158107d1989aef",
    "sha256:a750331702f2b51eea6a3f2dae698e4763b69fe2c207af3198b44baa1b5ac9aa",
    "sha256:e3ffa5cbb7795afd9f385c8285ffccbc6d3f1b5d038fb728081b30d063624786",
    "sha256:d7020c52ad3b0b2330eb95ff4fa3e9ddd5ce853c4ca1b12f30544c545ade4da8",
    "sha256:62b399b30e706acb2018a9b0fe05658852cf4c8d83f9cdf044b444ff0c03e795",
]
_REPORT_LIMITATIONS = [
    "permanent_provider_checksum_unavailable",
    "future_revision_finality_unknown",
    "provider_correction_lineage_unavailable",
    "provider_completeness_unknown",
    "historical_listing_lifecycle_unavailable",
    "authoritative_absence_unavailable",
    "survivorship_safety_unavailable",
    "corporate_action_lifecycle_closure_unavailable",
    "single_instrument_single_date_scope",
    "approved_proxy_transport_is_not_provider_completeness",
]
_LIMITATIONS = (
    "authoritative_absence_unavailable",
    "base_assessment_grade_unchanged",
    "historical_listing_lifecycle_unavailable",
    "listing_continuity_to_july_2026_execution_window_unavailable",
    "listing_presence_observed_only_for_20240102",
    "post_assessment_observation_not_causal_run_input",
    "provider_completeness_unknown",
    "survivorship_safety_unavailable",
)
_NONCLAIMS = (
    "deployment_not_authorized",
    "grade_upgrade_not_claimed",
    "listing_continuity_not_claimed",
    "live_eligibility_not_claimed",
    "provider_finality_not_claimed",
)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REPORT_KEYS = {
    "absence_authority",
    "acquisition_receipt_sha256",
    "bak_basic_rows",
    "corporate_action_lifecycle_qualified",
    "datasets",
    "decision_grade_eligible",
    "deployment_authorized",
    "historical_listing_lifecycle_qualified",
    "instrument_catalog_hash",
    "instrument_id",
    "limitations",
    "live_eligible",
    "member_acquired_at_epoch_nanoseconds",
    "member_content_hashes",
    "member_keys",
    "namechange_rows",
    "observed_at",
    "provenance_hash",
    "provider_completeness_qualified",
    "provider_key",
    "report_hash",
    "request_scope_hash",
    "revision_closure_complete",
    "schema_version",
    "snapshot_content_tree_hash",
    "snapshot_id",
    "source_record_hashes",
    "stock_basic_rows",
    "supersedes_report_hash",
    "target_name_interval_index",
    "trade_date",
    "transport_proxy_key",
    "type",
}


class _DuplicateKey(ValueError):
    pass


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _reject_number(value: str) -> object:
    raise ValueError(f"unsupported JSON number: {value}")


def _deep_exact(value: object) -> bool:
    if value is None or type(value) in (str, int, bool):
        return True
    if type(value) is list:
        return all(_deep_exact(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and _deep_exact(item) for key, item in value.items())
    return False


def _decode(source: bytes) -> dict[str, Any]:
    value = json.loads(
        source,
        object_pairs_hook=_pairs,
        parse_float=_reject_number,
        parse_constant=_reject_number,
    )
    if type(value) is not dict or not _deep_exact(value):
        raise ValueError("canonical JSON must be one exact object")
    if source != domain.canonical_bytes(value):
        raise ValueError("source bytes are not canonical")
    return value


def _sha256(source: bytes) -> str:
    return "sha256:" + hashlib.sha256(source).hexdigest()


def _semantic_hash(value: dict[str, Any]) -> str:
    body = dict(value)
    claimed = body.pop("report_hash", None)
    if type(claimed) is not str or _HASH.fullmatch(claimed) is None:
        raise ValueError("report hash must be canonical")
    if domain.canonical_sha256(body) != claimed:
        raise ValueError("report hash mismatch")
    return claimed


def _subjects(*values: str) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


class G12MTushareListingPresenceBindingFailureCodeV1(str, Enum):
    INVALID_EXACT_INPUT_TYPE = "INVALID_EXACT_INPUT_TYPE"
    BASE_ASSESSMENT_MISMATCH = "BASE_ASSESSMENT_MISMATCH"
    MALFORMED_OR_NONCANONICAL_LISTING_REPORT = (
        "MALFORMED_OR_NONCANONICAL_LISTING_REPORT"
    )
    LISTING_REPORT_IDENTITY_MISMATCH = "LISTING_REPORT_IDENTITY_MISMATCH"
    BINDING_TIME_INVALID = "BINDING_TIME_INVALID"
    DIRECT_PREDECESSOR_INVALID = "DIRECT_PREDECESSOR_INVALID"
    BINDING_RECONSTRUCTION_MISMATCH = "BINDING_RECONSTRUCTION_MISMATCH"


@dataclass(frozen=True, slots=True)
class G12MTushareListingPresenceBindingFailureV1:
    code: G12MTushareListingPresenceBindingFailureCodeV1
    subject_identities: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self) is not G12MTushareListingPresenceBindingFailureV1:
            raise TypeError("failure must be exact listing presence binding failure v1")
        if type(self.code) is not G12MTushareListingPresenceBindingFailureCodeV1:
            raise TypeError("code must be exact listing presence binding failure code v1")
        if (
            type(self.subject_identities) is not tuple
            or any(
                type(value) is not str or _HASH.fullmatch(value) is None
                for value in self.subject_identities
            )
            or self.subject_identities != tuple(sorted(set(self.subject_identities)))
        ):
            raise ValueError("subject identities must be sorted unique hashes")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "subject_identities": self.subject_identities,
        }


@dataclass(frozen=True, slots=True)
class G12MTushareListingPresenceBindingV1:
    base_assessment_hash: str
    semantic_run_id: str
    base_requested_grade: RequestedResultGrade
    base_result_grade: ResultGrade
    listing_report_file_hash: str
    listing_report_hash: str
    listing_snapshot_id: str
    listing_request_scope_hash: str
    instrument_catalog_hash: str
    instrument_id: domain.InstrumentId
    trade_date: str
    current_name: str
    list_date: str
    target_name_interval_start: str
    target_name_interval_end: None
    listing_observed_at: domain.UtcInstant
    bound_at: domain.UtcInstant
    supersedes_binding_hash: None
    limitations: tuple[str, ...]
    nonclaims: tuple[str, ...]
    live_eligible: bool
    deployment_authorized: bool
    binding_hash: str

    def __post_init__(self) -> None:
        if type(self) is not G12MTushareListingPresenceBindingV1:
            raise TypeError("binding must be exact listing presence binding v1")
        expected = {
            "base_assessment_hash": _BASE_ASSESSMENT_HASH,
            "semantic_run_id": _SEMANTIC_RUN_ID,
            "listing_report_file_hash": _LISTING_FILE_HASH,
            "listing_report_hash": _LISTING_REPORT_HASH,
            "listing_snapshot_id": _LISTING_SNAPSHOT_ID,
            "listing_request_scope_hash": _LISTING_REQUEST_SCOPE_HASH,
            "instrument_catalog_hash": _CATALOG_HASH,
            "trade_date": _TRADE_DATE,
            "current_name": _CURRENT_NAME,
            "list_date": _LIST_DATE,
            "target_name_interval_start": _INTERVAL_START,
        }
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("binding fixed identity mismatch")
        if (
            type(self.base_requested_grade) is not RequestedResultGrade
            or type(self.base_result_grade) is not ResultGrade
            or self.base_requested_grade.value != "decision_grade"
            or self.base_result_grade.value != "decision_grade"
            or type(self.instrument_id) is not domain.InstrumentId
            or self.instrument_id != _INSTRUMENT
            or self.target_name_interval_end is not None
            or type(self.listing_observed_at) is not domain.UtcInstant
            or self.listing_observed_at.epoch_nanoseconds != _LISTING_OBSERVED_AT
            or type(self.bound_at) is not domain.UtcInstant
            or self.bound_at.epoch_nanoseconds < _LISTING_OBSERVED_AT
            or self.supersedes_binding_hash is not None
            or self.limitations != _LIMITATIONS
            or self.nonclaims != _NONCLAIMS
            or type(self.live_eligible) is not bool
            or self.live_eligible
            or type(self.deployment_authorized) is not bool
            or self.deployment_authorized
        ):
            raise ValueError("binding grade, time, predecessor, or nonclaim mismatch")
        if type(self.binding_hash) is not str or _HASH.fullmatch(self.binding_hash) is None:
            raise ValueError("binding_hash must be canonical sha256")
        if self.binding_hash != domain.canonical_sha256(self._body()):
            raise ValueError("binding_hash does not bind body")

    def _body(self) -> dict[str, object]:
        return {
            "type": "g12m_tushare_listing_presence_binding_v1",
            "schema_version": 1,
            **{
                name: getattr(self, name)
                for name in self.__dataclass_fields__
                if name not in {"binding_hash", "base_requested_grade", "base_result_grade"}
            },
            "base_requested_grade": self.base_requested_grade.value,
            "base_result_grade": self.base_result_grade.value,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "binding_hash": self.binding_hash}


@dataclass(frozen=True, slots=True)
class G12MTushareListingPresenceBindingOutcomeV1:
    binding: G12MTushareListingPresenceBindingV1 | None
    failure: G12MTushareListingPresenceBindingFailureV1 | None

    def __post_init__(self) -> None:
        if type(self) is not G12MTushareListingPresenceBindingOutcomeV1:
            raise TypeError("outcome must be exact listing presence binding outcome v1")
        if (self.binding is None) == (self.failure is None):
            raise ValueError("outcome must carry exactly one binding or failure")
        if self.binding is not None:
            if type(self.binding) is not G12MTushareListingPresenceBindingV1:
                raise TypeError("binding must be exact listing presence binding v1")
            self.binding.__post_init__()
        if self.failure is not None:
            if type(self.failure) is not G12MTushareListingPresenceBindingFailureV1:
                raise TypeError("failure must be exact listing presence binding failure v1")
            self.failure.__post_init__()

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "binding": None if self.binding is None else self.binding.to_canonical_dict(),
            "failure": None if self.failure is None else self.failure.to_canonical_dict(),
        }


def _failure(
    code: G12MTushareListingPresenceBindingFailureCodeV1,
    *subjects: str,
) -> G12MTushareListingPresenceBindingOutcomeV1:
    return G12MTushareListingPresenceBindingOutcomeV1(
        None,
        G12MTushareListingPresenceBindingFailureV1(code, _subjects(*subjects)),
    )


def _listing_identity(report: dict[str, Any]) -> bool:
    try:
        instrument = report["instrument_id"]
        observed_at = report["observed_at"]
        flags = (
            report["revision_closure_complete"],
            report["provider_completeness_qualified"],
            report["absence_authority"],
            report["historical_listing_lifecycle_qualified"],
            report["corporate_action_lifecycle_qualified"],
            report["decision_grade_eligible"],
            report["live_eligible"],
            report["deployment_authorized"],
        )
        return (
            set(report) == _REPORT_KEYS
            and report["type"]
            == "tushare_cn_a_share_listing_source_bounded_observation_report_v2"
            and type(report["schema_version"]) is int
            and report["schema_version"] == 2
            and report["provider_key"] == "tushare.pro"
            and report["transport_proxy_key"]
            == "xiaodefa.approved-tushare-proxy.v1"
            and report["datasets"] == ["stock_basic", "bak_basic", "namechange"]
            and type(instrument) is dict
            and instrument
            == {"type": "instrument_id", "venue": "xshe", "stable_key": "000001"}
            and report["trade_date"] == _TRADE_DATE
            and report["request_scope_hash"] == _LISTING_REQUEST_SCOPE_HASH
            and report["snapshot_id"] == _LISTING_SNAPSHOT_ID
            and report["instrument_catalog_hash"] == _CATALOG_HASH
            and report["stock_basic_rows"] == [_STOCK_ROW]
            and report["bak_basic_rows"] == [_BAK_ROW]
            and type(report["namechange_rows"]) is list
            and len(report["namechange_rows"]) == 4
            and report["namechange_rows"][0] == _TARGET_NAME_ROW
            and report["target_name_interval_index"] == 0
            and report["source_record_hashes"] == _SOURCE_RECORD_HASHES
            and type(observed_at) is dict
            and observed_at
            == {"type": "utc_instant", "epoch_nanoseconds": _LISTING_OBSERVED_AT}
            and report["supersedes_report_hash"] is None
            and report["limitations"] == _REPORT_LIMITATIONS
            and all(type(value) is bool and not value for value in flags)
        )
    except (KeyError, TypeError, ValueError):
        return False


def bind_g12m_tushare_listing_presence_v1(
    *,
    base_assessment: TushareFixedSingletonSourceBoundedAssessmentV2,
    listing_report_bytes: bytes,
    bound_at: domain.UtcInstant,
    predecessor_binding: G12MTushareListingPresenceBindingV1 | None = None,
) -> G12MTushareListingPresenceBindingOutcomeV1:
    """Bind accepted post-assessment listing evidence without changing Run grade."""

    if (
        type(base_assessment) is not TushareFixedSingletonSourceBoundedAssessmentV2
        or type(listing_report_bytes) is not bytes
        or type(bound_at) is not domain.UtcInstant
        or (
            predecessor_binding is not None
            and type(predecessor_binding) is not G12MTushareListingPresenceBindingV1
        )
    ):
        return _failure(
            G12MTushareListingPresenceBindingFailureCodeV1.INVALID_EXACT_INPUT_TYPE
        )

    try:
        base_assessment.__post_init__()
        if (
            base_assessment.assessment_hash != _BASE_ASSESSMENT_HASH
            or base_assessment.semantic_run_id != _SEMANTIC_RUN_ID
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return _failure(
            G12MTushareListingPresenceBindingFailureCodeV1.BASE_ASSESSMENT_MISMATCH,
            _BASE_ASSESSMENT_HASH,
        )

    listing_file_hash = _sha256(listing_report_bytes)
    try:
        report = _decode(listing_report_bytes)
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        return _failure(
            G12MTushareListingPresenceBindingFailureCodeV1.MALFORMED_OR_NONCANONICAL_LISTING_REPORT,
            listing_file_hash,
        )

    try:
        report_hash = _semantic_hash(report)
        if (
            listing_file_hash != _LISTING_FILE_HASH
            or report_hash != _LISTING_REPORT_HASH
            or not _listing_identity(report)
        ):
            raise ValueError
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failure(
            G12MTushareListingPresenceBindingFailureCodeV1.LISTING_REPORT_IDENTITY_MISMATCH,
            _LISTING_FILE_HASH,
            _LISTING_REPORT_HASH,
            listing_file_hash,
        )

    try:
        trusted_bound_at = domain.UtcInstant(bound_at.epoch_nanoseconds)
        if trusted_bound_at != bound_at or trusted_bound_at.epoch_nanoseconds < max(
            base_assessment.assessed_at.epoch_nanoseconds,
            _LISTING_OBSERVED_AT,
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return _failure(
            G12MTushareListingPresenceBindingFailureCodeV1.BINDING_TIME_INVALID,
            _BASE_ASSESSMENT_HASH,
            _LISTING_REPORT_HASH,
        )
    if predecessor_binding is not None:
        try:
            predecessor_binding.__post_init__()
            predecessor_subject = predecessor_binding.binding_hash
        except (AttributeError, TypeError, ValueError):
            predecessor_subject = _LISTING_REPORT_HASH
        return _failure(
            G12MTushareListingPresenceBindingFailureCodeV1.DIRECT_PREDECESSOR_INVALID,
            predecessor_subject,
        )

    values: dict[str, object] = {
        "base_assessment_hash": base_assessment.assessment_hash,
        "semantic_run_id": base_assessment.semantic_run_id,
        "base_requested_grade": base_assessment.requested_grade,
        "base_result_grade": base_assessment.result_grade,
        "listing_report_file_hash": listing_file_hash,
        "listing_report_hash": cast(str, report["report_hash"]),
        "listing_snapshot_id": cast(str, report["snapshot_id"]),
        "listing_request_scope_hash": cast(str, report["request_scope_hash"]),
        "instrument_catalog_hash": cast(str, report["instrument_catalog_hash"]),
        "instrument_id": _INSTRUMENT,
        "trade_date": _TRADE_DATE,
        "current_name": _CURRENT_NAME,
        "list_date": _LIST_DATE,
        "target_name_interval_start": _INTERVAL_START,
        "target_name_interval_end": None,
        "listing_observed_at": domain.UtcInstant(_LISTING_OBSERVED_AT),
        "bound_at": trusted_bound_at,
        "supersedes_binding_hash": None,
        "limitations": _LIMITATIONS,
        "nonclaims": _NONCLAIMS,
        "live_eligible": False,
        "deployment_authorized": False,
    }
    body = {
        "type": "g12m_tushare_listing_presence_binding_v1",
        "schema_version": 1,
        **values,
        "base_requested_grade": base_assessment.requested_grade.value,
        "base_result_grade": base_assessment.result_grade.value,
    }
    try:
        binding = G12MTushareListingPresenceBindingV1(
            **cast(Any, values),
            binding_hash=domain.canonical_sha256(body),
        )
        binding.__post_init__()
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failure(
            G12MTushareListingPresenceBindingFailureCodeV1.BINDING_RECONSTRUCTION_MISMATCH,
            _BASE_ASSESSMENT_HASH,
            _LISTING_REPORT_HASH,
        )
    return G12MTushareListingPresenceBindingOutcomeV1(binding, None)
