"""Pure direct-successor binding for July-2026 Tushare listing presence."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

import crypto_quant_domain as domain

from .g12m_tushare_listing_presence_binding_v1 import G12MTushareListingPresenceBindingV1
from .integrity import ResultGrade
from .resolution import RequestedResultGrade

_PREDECESSOR_HASH = "sha256:ab9b0b750e55e34ff6e8fe5fb9e388143b83aa5140357061dfc7fe4c11ee6f8c"
_BASE_ASSESSMENT_HASH = "sha256:31f29b9ab70e7c8da267b6c17dcbe294503088850c894b066116313233dca8bb"
_SEMANTIC_RUN_ID = "run_1eebd60b81376e15fbe4b2496ed359ab24ed644c7416812d09eb3fb715f581a9"
_JULY_FILE_HASH = "sha256:36b38ec4367a4c9945c4ee8caee9b31eeb57bf73f6c10ed93526d0306d281e6c"
_JULY_REPORT_HASH = "sha256:4c829bf707bf0876ada550ad44682d0fc362025379afe233b98e9d7751e22052"
_JULY_SNAPSHOT_ID = "sha256:3b8b35744bd14974e71ca7de4fe00d229290061df38b29cedf0f5d2eb3ca378c"
_JULY_REQUEST_SCOPE_HASH = "sha256:388fa357808ab359366b9ac1dad808ea53b01be07d1b83a80d798a1b75268cce"
_CATALOG_HASH = "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc"
_G12I_REPORT_HASH = "sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029"
_LISTING_REPORT_HASH = "sha256:6d120c94b8d08fa00389d91894bc17d18ad4a6e0c1f9c42b859e7f1e26cc41c8"
_DATES = (
    "20260706", "20260707", "20260708", "20260709", "20260710",
    "20260713", "20260714", "20260715", "20260716", "20260717",
    "20260720", "20260721", "20260722", "20260723", "20260724",
    "20260727", "20260728", "20260729", "20260730",
)
_OBSERVED_AT = 1787543480633962555
_SOURCE_RECORD_HASHES = (
    "sha256:e88b6b2d1e682968fbdc4be2bde38aa606325d0c7a7edce19b981d652bb7be10",
    "sha256:11708340c571327a66161b748e7e270d95c1f3c2d8c6ddc68571e0d45d4392be",
    "sha256:0e9fe3dcd9256fa0483c14f98dd32274433c04c7b2da0c9238cd62edb42b95f2",
    "sha256:63724b4790174868e55f0e0318beabc39e06311cecfba95c7226fa60b3652a2a",
    "sha256:b4cbe6f1b246b7e0bde1e801c183854c5d4086e514f912d9b795cd63bf68850e",
    "sha256:eacf31f3f7df9595e965be2c6f63b95a6620cdd53465c6cec7e2419c55988b6e",
    "sha256:4a77b60f58298c1bb77a2ea663b9e4a4fb8fa55e0869c3c3c4bfd8b1b44bef71",
    "sha256:faa7f9d72a291370dcb3de6f6d2440eb6f8c5ee99cbf479982c532bcc2198e94",
    "sha256:21b4631d781df17297147d702a780f678db24a87610b51a932b50979aa0f9906",
    "sha256:e4550ce6f0979357193292837c673eda507f5392b7efb1e410556ab70ae5ec49",
    "sha256:7cd18eaac13ee95569a726cca34ae3fb39461d4696ab6259db35c28c43077083",
    "sha256:b935b41a6b823bf8b50bd68d59f0173096076d973a97d50f3be6e96a04fd89f8",
    "sha256:186acd98035af6a24fdb342f3e22080fa075e02669745465039a9e40d81a03c2",
    "sha256:7af31558c9d1f0d5b71b91260181dde22b0974598b6b7f7a399442a3522f9bce",
    "sha256:1e0aede174fedcefadc65abeaf8faebd51d709cbb3109ff46b731a9070255ed9",
    "sha256:c0f320b23993d14726b47ebaf32822a6abe00e5b75f160902ba9c718de03fe3c",
    "sha256:b023b4ac3f4237f5533f26d46a898bf9dbd18ee19a770e749bfdbdf30b16287c",
    "sha256:f439cea20ecfb087b6f5963297e7accdcb7b7ad4a04a7828bd060fdc22b391be",
    "sha256:9acf64d212e21c8634c8e47e935730034889344b998add97b88f074a3d3a4738",
)
_LIMITATIONS = (
    "authoritative_absence_unavailable",
    "base_assessment_grade_unchanged",
    "listing_between_observed_dates_unavailable",
    "post_assessment_observation_not_causal_run_input",
    "provider_completeness_unknown",
    "provider_revision_finality_unknown",
    "survivorship_safety_unavailable",
)
_NONCLAIMS = (
    "deployment_not_authorized",
    "grade_upgrade_not_claimed",
    "listing_continuity_not_claimed",
    "live_eligibility_not_claimed",
)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise ValueError("duplicate JSON object key")
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
    value = json.loads(source, object_pairs_hook=_pairs, parse_float=_reject_number, parse_constant=_reject_number)
    if type(value) is not dict or not _deep_exact(value) or source != domain.canonical_bytes(value):
        raise ValueError("report bytes must be one canonical exact object")
    return value


def _sha256(source: bytes) -> str:
    return "sha256:" + hashlib.sha256(source).hexdigest()


def _semantic_hash(value: dict[str, Any]) -> str:
    body = dict(value)
    claimed = body.pop("report_hash", None)
    if type(claimed) is not str or _HASH.fullmatch(claimed) is None or domain.canonical_sha256(body) != claimed:
        raise ValueError("report semantic hash mismatch")
    return claimed


def _subjects(*values: str) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


class G12MTushareJulyListingPresenceBindingFailureCodeV2(str, Enum):
    INVALID_EXACT_INPUT_TYPE = "INVALID_EXACT_INPUT_TYPE"
    PREDECESSOR_BINDING_MISMATCH = "PREDECESSOR_BINDING_MISMATCH"
    MALFORMED_OR_NONCANONICAL_JULY_REPORT = "MALFORMED_OR_NONCANONICAL_JULY_REPORT"
    JULY_REPORT_IDENTITY_MISMATCH = "JULY_REPORT_IDENTITY_MISMATCH"
    BINDING_TIME_INVALID = "BINDING_TIME_INVALID"
    BINDING_RECONSTRUCTION_MISMATCH = "BINDING_RECONSTRUCTION_MISMATCH"


@dataclass(frozen=True, slots=True)
class G12MTushareJulyListingPresenceBindingFailureV2:
    code: G12MTushareJulyListingPresenceBindingFailureCodeV2
    subject_identities: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self) is not G12MTushareJulyListingPresenceBindingFailureV2:
            raise TypeError("failure must be exact July binding failure v2")
        if type(self.code) is not G12MTushareJulyListingPresenceBindingFailureCodeV2:
            raise TypeError("code must be exact July binding failure code v2")
        if (
            type(self.subject_identities) is not tuple
            or any(type(value) is not str or _HASH.fullmatch(value) is None for value in self.subject_identities)
            or self.subject_identities != tuple(sorted(set(self.subject_identities)))
        ):
            raise ValueError("subjects must be sorted unique hashes")

    def to_canonical_dict(self) -> dict[str, object]:
        return {"code": self.code.value, "subject_identities": self.subject_identities}


@dataclass(frozen=True, slots=True)
class G12MTushareJulyListingPresenceBindingV2:
    supersedes_binding_hash: str
    base_assessment_hash: str
    semantic_run_id: str
    base_requested_grade: RequestedResultGrade
    base_result_grade: ResultGrade
    predecessor_listing_report_hash: str
    july_report_file_hash: str
    july_report_hash: str
    july_snapshot_id: str
    july_request_scope_hash: str
    g12i_report_hash: str
    instrument_catalog_hash: str
    trade_dates: tuple[str, ...]
    source_record_hashes: tuple[str, ...]
    july_observed_at: domain.UtcInstant
    bound_at: domain.UtcInstant
    limitations: tuple[str, ...]
    nonclaims: tuple[str, ...]
    live_eligible: bool
    deployment_authorized: bool
    binding_hash: str

    def __post_init__(self) -> None:
        if type(self) is not G12MTushareJulyListingPresenceBindingV2:
            raise TypeError("binding must be exact July listing binding v2")
        expected = {
            "supersedes_binding_hash": _PREDECESSOR_HASH,
            "base_assessment_hash": _BASE_ASSESSMENT_HASH,
            "semantic_run_id": _SEMANTIC_RUN_ID,
            "predecessor_listing_report_hash": _LISTING_REPORT_HASH,
            "july_report_file_hash": _JULY_FILE_HASH,
            "july_report_hash": _JULY_REPORT_HASH,
            "july_snapshot_id": _JULY_SNAPSHOT_ID,
            "july_request_scope_hash": _JULY_REQUEST_SCOPE_HASH,
            "g12i_report_hash": _G12I_REPORT_HASH,
            "instrument_catalog_hash": _CATALOG_HASH,
        }
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("binding fixed identity mismatch")
        for name in (
            "supersedes_binding_hash", "base_assessment_hash", "predecessor_listing_report_hash",
            "july_report_file_hash", "july_report_hash", "july_snapshot_id",
            "july_request_scope_hash", "g12i_report_hash", "instrument_catalog_hash",
            "binding_hash",
        ):
            value = getattr(self, name)
            if type(value) is not str or _HASH.fullmatch(value) is None:
                raise ValueError(f"{name} must be canonical sha256")
        if (
            type(self.base_requested_grade) is not RequestedResultGrade
            or type(self.base_result_grade) is not ResultGrade
            or self.base_requested_grade.value != "decision_grade"
            or self.base_result_grade.value != "decision_grade"
            or self.trade_dates != _DATES
            or type(self.source_record_hashes) is not tuple
            or self.source_record_hashes != _SOURCE_RECORD_HASHES
            or type(self.july_observed_at) is not domain.UtcInstant
            or self.july_observed_at.epoch_nanoseconds != _OBSERVED_AT
            or type(self.bound_at) is not domain.UtcInstant
            or self.bound_at.epoch_nanoseconds < _OBSERVED_AT
            or self.limitations != _LIMITATIONS
            or self.nonclaims != _NONCLAIMS
            or type(self.live_eligible) is not bool or self.live_eligible
            or type(self.deployment_authorized) is not bool or self.deployment_authorized
        ):
            raise ValueError("binding grades, rows, time, or nonclaims mismatch")
        if self.binding_hash != domain.canonical_sha256(self._body()):
            raise ValueError("binding hash mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": "g12m_tushare_july_listing_presence_binding_v2",
            "schema_version": 2,
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
class G12MTushareJulyListingPresenceBindingOutcomeV2:
    binding: G12MTushareJulyListingPresenceBindingV2 | None
    failure: G12MTushareJulyListingPresenceBindingFailureV2 | None

    def __post_init__(self) -> None:
        if type(self) is not G12MTushareJulyListingPresenceBindingOutcomeV2:
            raise TypeError("outcome must be exact July binding outcome v2")
        if (self.binding is None) == (self.failure is None):
            raise ValueError("outcome must carry exactly one value")
        if self.binding is not None:
            if type(self.binding) is not G12MTushareJulyListingPresenceBindingV2:
                raise TypeError("binding must be exact")
            self.binding.__post_init__()
        if self.failure is not None:
            if type(self.failure) is not G12MTushareJulyListingPresenceBindingFailureV2:
                raise TypeError("failure must be exact")
            self.failure.__post_init__()


def _failure(code: G12MTushareJulyListingPresenceBindingFailureCodeV2, *subjects: str) -> G12MTushareJulyListingPresenceBindingOutcomeV2:
    return G12MTushareJulyListingPresenceBindingOutcomeV2(
        None,
        G12MTushareJulyListingPresenceBindingFailureV2(code, _subjects(*subjects)),
    )


def _july_identity(report: dict[str, Any]) -> bool:
    try:
        flags = (
            report["revision_closure_complete"], report["provider_completeness_qualified"],
            report["absence_authority"], report["historical_listing_lifecycle_qualified"],
            report["decision_grade_eligible"], report["live_eligible"], report["deployment_authorized"],
        )
        rows = report["source_rows"]
        return (
            report["type"] == "tushare_cn_a_share_july_listing_presence_report_v1"
            and type(report["schema_version"]) is int and report["schema_version"] == 1
            and report["provider_key"] == "tushare.pro"
            and report["transport_proxy_key"] == "xiaodefa.approved-tushare-proxy.v1"
            and report["trade_dates"] == list(_DATES)
            and report["snapshot_id"] == _JULY_SNAPSHOT_ID
            and report["request_scope_hash"] == _JULY_REQUEST_SCOPE_HASH
            and report["g12i_report_hash"] == _G12I_REPORT_HASH
            and report["listing_report_hash"] == _LISTING_REPORT_HASH
            and report["instrument_catalog_hash"] == _CATALOG_HASH
            and type(rows) is list and len(rows) == 19
            and rows == [[date, "000001.SZ", "平安银行", "19910403"] for date in _DATES]
            and report["source_record_hashes"] == list(_SOURCE_RECORD_HASHES)
            and report["observed_at"] == {"type": "utc_instant", "epoch_nanoseconds": _OBSERVED_AT}
            and report["supersedes_report_hash"] is None
            and all(type(value) is bool and not value for value in flags)
        )
    except (KeyError, TypeError, ValueError):
        return False


def bind_g12m_tushare_july_listing_presence_v2(
    *,
    predecessor_binding: G12MTushareListingPresenceBindingV1,
    july_report_bytes: bytes,
    bound_at: domain.UtcInstant,
) -> G12MTushareJulyListingPresenceBindingOutcomeV2:
    if (
        type(predecessor_binding) is not G12MTushareListingPresenceBindingV1
        or type(july_report_bytes) is not bytes
        or type(bound_at) is not domain.UtcInstant
    ):
        return _failure(G12MTushareJulyListingPresenceBindingFailureCodeV2.INVALID_EXACT_INPUT_TYPE)
    try:
        predecessor_binding.__post_init__()
        if predecessor_binding.binding_hash != _PREDECESSOR_HASH:
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return _failure(
            G12MTushareJulyListingPresenceBindingFailureCodeV2.PREDECESSOR_BINDING_MISMATCH,
            _PREDECESSOR_HASH,
        )
    july_file_hash = _sha256(july_report_bytes)
    try:
        report = _decode(july_report_bytes)
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        return _failure(
            G12MTushareJulyListingPresenceBindingFailureCodeV2.MALFORMED_OR_NONCANONICAL_JULY_REPORT,
            july_file_hash,
        )
    try:
        report_hash = _semantic_hash(report)
        if july_file_hash != _JULY_FILE_HASH or report_hash != _JULY_REPORT_HASH or not _july_identity(report):
            raise ValueError
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failure(
            G12MTushareJulyListingPresenceBindingFailureCodeV2.JULY_REPORT_IDENTITY_MISMATCH,
            _JULY_FILE_HASH,
            _JULY_REPORT_HASH,
            july_file_hash,
        )
    try:
        trusted_bound_at = domain.UtcInstant(bound_at.epoch_nanoseconds)
        if trusted_bound_at != bound_at or trusted_bound_at.epoch_nanoseconds < _OBSERVED_AT:
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return _failure(
            G12MTushareJulyListingPresenceBindingFailureCodeV2.BINDING_TIME_INVALID,
            _JULY_REPORT_HASH,
        )
    values: dict[str, object] = {
        "supersedes_binding_hash": predecessor_binding.binding_hash,
        "base_assessment_hash": predecessor_binding.base_assessment_hash,
        "semantic_run_id": predecessor_binding.semantic_run_id,
        "base_requested_grade": predecessor_binding.base_requested_grade,
        "base_result_grade": predecessor_binding.base_result_grade,
        "predecessor_listing_report_hash": predecessor_binding.listing_report_hash,
        "july_report_file_hash": july_file_hash,
        "july_report_hash": cast(str, report["report_hash"]),
        "july_snapshot_id": cast(str, report["snapshot_id"]),
        "july_request_scope_hash": cast(str, report["request_scope_hash"]),
        "g12i_report_hash": cast(str, report["g12i_report_hash"]),
        "instrument_catalog_hash": cast(str, report["instrument_catalog_hash"]),
        "trade_dates": _DATES,
        "source_record_hashes": tuple(cast(list[str], report["source_record_hashes"])),
        "july_observed_at": domain.UtcInstant(_OBSERVED_AT),
        "bound_at": trusted_bound_at,
        "limitations": _LIMITATIONS,
        "nonclaims": _NONCLAIMS,
        "live_eligible": False,
        "deployment_authorized": False,
    }
    body = {
        "type": "g12m_tushare_july_listing_presence_binding_v2",
        "schema_version": 2,
        **values,
        "base_requested_grade": predecessor_binding.base_requested_grade.value,
        "base_result_grade": predecessor_binding.base_result_grade.value,
    }
    try:
        binding = G12MTushareJulyListingPresenceBindingV2(
            **cast(Any, values),
            binding_hash=domain.canonical_sha256(body),
        )
        binding.__post_init__()
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failure(
            G12MTushareJulyListingPresenceBindingFailureCodeV2.BINDING_RECONSTRUCTION_MISMATCH,
            _PREDECESSOR_HASH,
            _JULY_REPORT_HASH,
        )
    return G12MTushareJulyListingPresenceBindingOutcomeV2(binding, None)
