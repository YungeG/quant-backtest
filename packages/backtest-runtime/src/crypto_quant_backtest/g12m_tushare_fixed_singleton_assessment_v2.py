"""Pure G12M Tushare fixed-singleton source-to-Run assessment v2."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

import crypto_quant_domain as domain
from crypto_quant_market_data import MarketBundleRef

from .analysis import AnalysisArtifactRefV2
from .g12m_tushare_fixed_singleton_route_v2 import (
    _G12MTushareFixedSingletonRouteResultV2,
)
from .integrity import ResultGrade
from .publication_refs import BacktestCanonicalPublicationRefV2
from .resolution import RequestedResultGrade
from .verified_publications import _VerifiedCompletedEvidenceV3

_DECISION_FILE_HASH = (
    "sha256:920bd2b2b10108ef4cbcb631215b571a0198e55e526de1147e56b49d67b71ff6"
)
_DECISION_HASH = (
    "sha256:7e8ca1ebf63aeb4f5f36ab72073d258db64083028e6e2f4c1662941bd46c7d62"
)
_PREDECESSOR_HASH = (
    "sha256:a7a6fff66a34f20031178d82fd7da424799ecbc2b3e2c887bdd149e98cc826bb"
)
_G12I_FILE_HASH = (
    "sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6"
)
_G12I_REPORT_HASH = (
    "sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029"
)
_G12K_FILE_HASH = (
    "sha256:a386f4281374d1449c0b5ba4371b9e9d2de5b236bc8fc5b5cdd8de5e43c65956"
)
_G12K_REPORT_HASH = (
    "sha256:5a49065d87286a9673893337328ddbbab9a19cd3addf178bf96033b9b1babfd7"
)
_AUTHORITY_HASH = (
    "sha256:3d19c05e552aa61a7f1ff33bc2451d2d0cc13e0d3ee30acde46462bdfa65becf"
)
_BUILD_HASH = (
    "sha256:26048a80c045b8c49ab4f09936ab6ea3ef31acd767d54365caa20c8e457f7f45"
)
_PROFILE_DIGESTS = (
    "sha256:52b02b86b4fb6ea0b481d1184f68148d8b3d074b93e332ca582cd417072c8fd1",
    "sha256:a1f0e4dd163deebf7dd8cf10e199078b6ad1c68bf0467b1f7f449e3423114875",
    "sha256:bac4efa7e4874d3ab915ae6d775c3213db29c12c992663e065dc363ac8c78406",
)
_BUNDLE_MANIFEST_HASH = (
    "sha256:2ea4d3c58076312ff86ee175fac2f1173fb28f01e4e4d31ca372ca0d345e750b"
)
_BUNDLE_CONTENT_HASH = (
    "sha256:a0b6319c07aaa810ba490924f2267ebb93f72d5037432b30dd6a0a5bbb3fb8ff"
)
_TARGET_STREAM_DIGEST = (
    "sha256:8e4bdddbd91e1bafd65363e133d382673df88e4dc4061d1f0dd776a42afc6cee"
)
_DECISION_TIME = 1787292861381694497
_ASSESSMENT_FLOOR = 1787299622295499670
_DISPOSITION = "ZERO_EXPOSURE_NO_ENTITLEMENT_NO_CORPORATE_ACTION_DISPATCH"
_LIMITATIONS = (
    "corporate_action_absence_not_claimed",
    "corporate_action_lifecycle_not_claimed",
    "historical_provider_availability_time_unknown",
    "listing_continuity_and_survivorship_not_claimed",
    "provider_finality_or_completeness_not_claimed",
    "strict_official_legal_tax_closure_not_claimed",
)
_NONCLAIMS = (
    "binance_qualification_not_claimed",
    "deployment_not_authorized",
    "execution_quality_not_claimed",
    "live_eligibility_not_claimed",
    "result_grade_not_minted_or_changed",
)
_HASH = re.compile(r"sha256:[0-9a-f]{64}")


class TushareFixedSingletonAssessmentFailureCodeV2(str, Enum):
    INVALID_EXACT_INPUT_TYPE = "INVALID_EXACT_INPUT_TYPE"
    MALFORMED_OR_NONCANONICAL_BYTES = "MALFORMED_OR_NONCANONICAL_BYTES"
    G12I_RECONSTRUCTION_MISMATCH = "G12I_RECONSTRUCTION_MISMATCH"
    G12K_RECONSTRUCTION_MISMATCH = "G12K_RECONSTRUCTION_MISMATCH"
    SUCCESSOR_AUTHORITY_MISMATCH = "SUCCESSOR_AUTHORITY_MISMATCH"
    BUNDLE_SOURCE_PROJECTION_MEMBERSHIP_MISMATCH = (
        "BUNDLE_SOURCE_PROJECTION_MEMBERSHIP_MISMATCH"
    )
    TARGET_SINGLETON_MISMATCH = "TARGET_SINGLETON_MISMATCH"
    RUN_ATTEMPT_PROOF_MISMATCH = "RUN_ATTEMPT_PROOF_MISMATCH"
    RESOLUTION_INTEGRITY_GRADE_MISMATCH = (
        "RESOLUTION_INTEGRITY_GRADE_MISMATCH"
    )
    TIMELINE_CAUSALITY_MISMATCH = "TIMELINE_CAUSALITY_MISMATCH"
    ACCOUNTING_DISPOSITION_MISMATCH = "ACCOUNTING_DISPOSITION_MISMATCH"
    ASSESSMENT_TIME_INVALID = "ASSESSMENT_TIME_INVALID"
    DIRECT_PREDECESSOR_INVALID = "DIRECT_PREDECESSOR_INVALID"
    ASSESSMENT_RECONSTRUCTION_MISMATCH = "ASSESSMENT_RECONSTRUCTION_MISMATCH"


@dataclass(frozen=True, slots=True)
class TushareFixedSingletonAssessmentFailureV2:
    code: TushareFixedSingletonAssessmentFailureCodeV2
    subject_identities: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self) is not TushareFixedSingletonAssessmentFailureV2:
            raise TypeError("failure must be exact assessment failure v2")
        if type(self.code) is not TushareFixedSingletonAssessmentFailureCodeV2:
            raise TypeError("code must be exact assessment failure code v2")
        if type(self.subject_identities) is not tuple or not all(
            type(value) is str and _HASH.fullmatch(value)
            for value in self.subject_identities
        ):
            raise TypeError("subject identities must be canonical sha256 values")
        if self.subject_identities != tuple(sorted(set(self.subject_identities))):
            raise ValueError("subject identities must be sorted and unique")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "code": self.code.value,
            "subject_identities": self.subject_identities,
        }


@dataclass(frozen=True, slots=True)
class TushareFixedSingletonSourceBoundedAssessmentV2:
    successor_decision_file_hash: str
    successor_decision_hash: str
    successor_decision_predecessor_hash: str
    g12i_canonical_file_hash: str
    g12i_report_hash: str
    g12k_canonical_file_hash: str
    g12k_report_hash: str
    authority_hash: str
    profile_digests: tuple[str, str, str]
    build_manifest_hash: str
    market_bundle_ref: MarketBundleRef
    market_bundle_content_hash: str
    source_event_triples: tuple[tuple[str, str, int], ...]
    projection_event_triples: tuple[tuple[str, str, int], ...]
    target_event_triple: tuple[str, str, int]
    execution_input_ref: domain.ArtifactRef
    execution_input_source_hash: str
    request_hash: str
    resolved_environment_hash: str
    compatibility_report_hash: str
    semantic_run_id: str
    attempt_ids: tuple[str, str]
    attempt_hashes: tuple[str, str]
    execution_result_hash: str
    trace_hash: str
    timeline_event_pairs: tuple[tuple[str, str], ...]
    rebuild_verification_ref: domain.ArtifactRef
    proof_publication_manifest_ref: domain.ArtifactRef
    canonical_publication_ref: BacktestCanonicalPublicationRefV2
    integrity_report_ref: domain.ArtifactRef
    integrity_context_hash: str
    requested_grade: RequestedResultGrade
    result_grade: ResultGrade
    static_verification_hash: str
    metric_profile_ref: domain.ArtifactRef
    analysis_ref: AnalysisArtifactRefV2
    analysis_hash: str
    accounting_disposition: str
    target_effect_count: int
    order_count: int
    fill_count: int
    fee_count: int
    settlement_count: int
    lot_count: int
    exposure_count: int
    entitlement_count: int
    corporate_action_dispatch_count: int
    assessed_at: domain.UtcInstant
    supersedes_assessment_hash: None
    limitations: tuple[str, ...]
    nonclaims: tuple[str, ...]
    live_eligible: bool
    deployment_authorized: bool
    assessment_hash: str

    def __post_init__(self) -> None:
        if type(self) is not TushareFixedSingletonSourceBoundedAssessmentV2:
            raise TypeError("assessment must be exact source-bounded assessment v2")
        expected = {
            "successor_decision_file_hash": _DECISION_FILE_HASH,
            "successor_decision_hash": _DECISION_HASH,
            "successor_decision_predecessor_hash": _PREDECESSOR_HASH,
            "g12i_canonical_file_hash": _G12I_FILE_HASH,
            "g12i_report_hash": _G12I_REPORT_HASH,
            "g12k_canonical_file_hash": _G12K_FILE_HASH,
            "g12k_report_hash": _G12K_REPORT_HASH,
            "authority_hash": _AUTHORITY_HASH,
            "build_manifest_hash": _BUILD_HASH,
            "market_bundle_content_hash": _BUNDLE_CONTENT_HASH,
            "accounting_disposition": _DISPOSITION,
        }
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("assessment fixed identity mismatch")
        if self.profile_digests != _PROFILE_DIGESTS:
            raise ValueError("assessment Profile identity mismatch")
        for name, value, expected_type in (
            ("market_bundle_ref", self.market_bundle_ref, MarketBundleRef),
            ("execution_input_ref", self.execution_input_ref, domain.ArtifactRef),
            (
                "rebuild_verification_ref",
                self.rebuild_verification_ref,
                domain.ArtifactRef,
            ),
            (
                "proof_publication_manifest_ref",
                self.proof_publication_manifest_ref,
                domain.ArtifactRef,
            ),
            (
                "canonical_publication_ref",
                self.canonical_publication_ref,
                BacktestCanonicalPublicationRefV2,
            ),
            ("integrity_report_ref", self.integrity_report_ref, domain.ArtifactRef),
            ("requested_grade", self.requested_grade, RequestedResultGrade),
            ("result_grade", self.result_grade, ResultGrade),
            ("metric_profile_ref", self.metric_profile_ref, domain.ArtifactRef),
            ("analysis_ref", self.analysis_ref, AnalysisArtifactRefV2),
        ):
            if type(value) is not expected_type:
                raise TypeError(f"{name} must be exact {expected_type.__name__}")
        if (
            type(self.source_event_triples) is not tuple
            or len(self.source_event_triples) != 19
            or type(self.projection_event_triples) is not tuple
            or len(self.projection_event_triples) != 19
            or type(self.target_event_triple) is not tuple
            or len(self.target_event_triple) != 3
            or type(self.timeline_event_pairs) is not tuple
            or len(self.timeline_event_pairs) != 39
        ):
            raise ValueError("assessment Event membership mismatch")
        for triples in (self.source_event_triples, self.projection_event_triples):
            if not all(
                type(value) is tuple
                and len(value) == 3
                and type(value[0]) is str
                and type(value[1]) is str
                and _HASH.fullmatch(value[1])
                and type(value[2]) is int
                for value in triples
            ):
                raise TypeError("assessment Event triples must be exact")
        if (
            type(self.attempt_ids) is not tuple
            or len(self.attempt_ids) != 2
            or not all(type(value) is str for value in self.attempt_ids)
            or type(self.attempt_hashes) is not tuple
            or len(self.attempt_hashes) != 2
            or not all(
                type(value) is str and _HASH.fullmatch(value)
                for value in self.attempt_hashes
            )
        ):
            raise TypeError("assessment Attempt identities must be exact")
        for name in (
            "execution_input_source_hash",
            "request_hash",
            "resolved_environment_hash",
            "compatibility_report_hash",
            "execution_result_hash",
            "trace_hash",
            "integrity_context_hash",
            "static_verification_hash",
            "analysis_hash",
            "assessment_hash",
        ):
            value = getattr(self, name)
            if type(value) is not str or _HASH.fullmatch(value) is None:
                raise ValueError(f"{name} must be canonical sha256")
        counts = (
            self.target_effect_count,
            self.order_count,
            self.fill_count,
            self.fee_count,
            self.settlement_count,
            self.lot_count,
            self.exposure_count,
            self.entitlement_count,
            self.corporate_action_dispatch_count,
        )
        if any(type(value) is not int or value != 0 for value in counts):
            raise ValueError("assessment accounting counts must be exact zero")
        if (
            type(self.assessed_at) is not domain.UtcInstant
            or self.assessed_at.epoch_nanoseconds < _ASSESSMENT_FLOOR
            or self.supersedes_assessment_hash is not None
            or self.limitations != _LIMITATIONS
            or self.nonclaims != _NONCLAIMS
            or type(self.live_eligible) is not bool
            or self.live_eligible
            or type(self.deployment_authorized) is not bool
            or self.deployment_authorized
        ):
            raise ValueError("assessment time, predecessor, or nonclaim mismatch")
        if self.assessment_hash != domain.canonical_sha256(self._body()):
            raise ValueError("assessment_hash does not bind assessment body")

    def _body(self) -> dict[str, object]:
        return {
            "type": "g12m_tushare_fixed_singleton_source_bounded_assessment_v2",
            "schema_version": 2,
            **{
                name: getattr(self, name)
                for name in self.__dataclass_fields__
                if name != "assessment_hash"
            },
            "requested_grade": self.requested_grade.value,
            "result_grade": self.result_grade.value,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "assessment_hash": self.assessment_hash}


@dataclass(frozen=True, slots=True)
class TushareFixedSingletonAssessmentOutcomeV2:
    assessment: TushareFixedSingletonSourceBoundedAssessmentV2 | None
    failure: TushareFixedSingletonAssessmentFailureV2 | None

    def __post_init__(self) -> None:
        if type(self) is not TushareFixedSingletonAssessmentOutcomeV2:
            raise TypeError("outcome must be exact assessment outcome v2")
        if (self.assessment is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one assessment or failure")
        if self.assessment is not None:
            if type(self.assessment) is not TushareFixedSingletonSourceBoundedAssessmentV2:
                raise TypeError("outcome assessment must be exact")
            self.assessment.__post_init__()
        if self.failure is not None:
            if type(self.failure) is not TushareFixedSingletonAssessmentFailureV2:
                raise TypeError("outcome failure must be exact")
            self.failure.__post_init__()

    def to_canonical_dict(self) -> dict[str, object]:
        return {"assessment": self.assessment, "failure": self.failure}


class _DuplicateKey(ValueError):
    pass


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise _DuplicateKey(key)
        result[key] = value
    return result


def _reject_number(value: str) -> None:
    raise ValueError(value)


def _deep_exact(value: object) -> bool:
    if value is None or type(value) in (str, int, bool):
        return True
    if type(value) is list:
        return all(_deep_exact(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and _deep_exact(item) for key, item in value.items())
    return False


def _decode(source: bytes, *, trailing_newline: bool) -> dict[str, Any]:
    value = json.loads(
        source,
        object_pairs_hook=_pairs,
        parse_float=_reject_number,
        parse_constant=_reject_number,
    )
    if type(value) is not dict or not _deep_exact(value):
        raise ValueError("canonical JSON must be one exact object")
    expected = domain.canonical_bytes(value) + (b"\n" if trailing_newline else b"")
    if source != expected:
        raise ValueError("source bytes are not canonical")
    return value


def _sha256(source: bytes) -> str:
    return "sha256:" + hashlib.sha256(source).hexdigest()


def _semantic_hash(value: dict[str, Any], hash_key: str) -> str:
    body = dict(value)
    claimed = body.pop(hash_key, None)
    computed = domain.canonical_sha256(body)
    if claimed != computed:
        raise ValueError("embedded semantic hash mismatch")
    return computed


def _subjects(*values: object) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                value
                for value in values
                if type(value) is str and _HASH.fullmatch(value) is not None
            }
        )
    )


def _safe_hash_attr(value: object, name: str, fallback: str) -> str:
    try:
        candidate = getattr(value, name)
    except (AttributeError, TypeError):
        return fallback
    return (
        candidate
        if type(candidate) is str and _HASH.fullmatch(candidate) is not None
        else fallback
    )


def _failure(
    code: TushareFixedSingletonAssessmentFailureCodeV2,
    *subjects: object,
) -> TushareFixedSingletonAssessmentOutcomeV2:
    return TushareFixedSingletonAssessmentOutcomeV2(
        None,
        TushareFixedSingletonAssessmentFailureV2(code, _subjects(*subjects)),
    )


def assess_g12m_tushare_fixed_singleton_v2(
    *,
    successor_decision_bytes: bytes,
    g12i_report_bytes: bytes,
    g12k_report_bytes: bytes,
    route_result: _G12MTushareFixedSingletonRouteResultV2,
    assessed_at: domain.UtcInstant,
    predecessor_assessment: TushareFixedSingletonSourceBoundedAssessmentV2 | None = None,
) -> TushareFixedSingletonAssessmentOutcomeV2:
    """Assess exact already-materialized authority, source, and verified Run values."""

    if (
        type(successor_decision_bytes) is not bytes
        or type(g12i_report_bytes) is not bytes
        or type(g12k_report_bytes) is not bytes
        or type(route_result) is not _G12MTushareFixedSingletonRouteResultV2
        or type(assessed_at) is not domain.UtcInstant
        or (
            predecessor_assessment is not None
            and type(predecessor_assessment)
            is not TushareFixedSingletonSourceBoundedAssessmentV2
        )
    ):
        return _failure(TushareFixedSingletonAssessmentFailureCodeV2.INVALID_EXACT_INPUT_TYPE)

    route_subject = _safe_hash_attr(route_result, "route_hash", _AUTHORITY_HASH)
    source_subjects = (
        _sha256(successor_decision_bytes),
        _sha256(g12i_report_bytes),
        _sha256(g12k_report_bytes),
    )
    try:
        decision = _decode(successor_decision_bytes, trailing_newline=False)
        g12i = _decode(g12i_report_bytes, trailing_newline=True)
        g12k = _decode(g12k_report_bytes, trailing_newline=True)
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError):
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.MALFORMED_OR_NONCANONICAL_BYTES,
            *source_subjects,
        )

    try:
        if (
            _sha256(g12i_report_bytes) != _G12I_FILE_HASH
            or _semantic_hash(g12i, "report_hash") != _G12I_REPORT_HASH
            or g12i.get("type")
            != "tushare_cn_a_share_daily_source_bounded_observation_report"
            or g12i.get("schema_version") != 2
            or g12i.get("supersedes_report_hash") is not None
            or g12i.get("observed_at", {}).get("epoch_nanoseconds")
            != 1787292861381694496
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.G12I_RECONSTRUCTION_MISMATCH,
            _G12I_FILE_HASH,
            _G12I_REPORT_HASH,
            source_subjects[1],
        )

    try:
        if (
            _sha256(g12k_report_bytes) != _G12K_FILE_HASH
            or _semantic_hash(g12k, "report_hash") != _G12K_REPORT_HASH
            or g12k.get("type")
            != "g12k_fixed_instrument_source_bounded_observation_report"
            or g12k.get("schema_version") != 1
            or g12k.get("supersedes_report_hash") is not None
            or g12k.get("observed_at", {}).get("epoch_nanoseconds")
            != _ASSESSMENT_FLOOR
            or g12k.get("g12i_report_canonical_file_sha256") != _G12I_FILE_HASH
            or g12k.get("g12i_report_hash") != _G12I_REPORT_HASH
            or g12k.get("g12i_snapshot_id") != g12i.get("snapshot_id")
            or g12k.get("g12i_manifest_content_hash")
            != g12i.get("manifest_content_hash")
            or g12k.get("g12i_bundle_ref_manifest_hash")
            != g12i.get("bundle_ref", {}).get("manifest_hash")
            or g12k.get("g12i_stream_content_hash") != g12i.get("stream_content_hash")
            or g12k.get("observed_daily_event_hashes")
            != g12i.get("published_event_hashes")
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.G12K_RECONSTRUCTION_MISMATCH,
            _G12K_FILE_HASH,
            _G12K_REPORT_HASH,
            source_subjects[2],
        )

    try:
        decision_hash = _semantic_hash(decision, "decision_hash")
        authority = decision["runnable_profile_build_authority"]
        if (
            _sha256(successor_decision_bytes) != _DECISION_FILE_HASH
            or decision_hash != _DECISION_HASH
            or decision.get("decision_code") != "H1"
            or decision.get("decision") != "EXACT_PREREQUISITES_ACCEPTED"
            or decision.get("supersedes_decision_hash") != _PREDECESSOR_HASH
            or decision.get("historical_predecessor", {}).get(
                "semantic_decision_hash"
            )
            != _PREDECESSOR_HASH
            or authority.get("authority_hash") != _AUTHORITY_HASH
            or authority.get("build_manifest_hash") != _BUILD_HASH
            or route_result.authority_hash != _AUTHORITY_HASH
            or route_result.build_manifest_hash != _BUILD_HASH
            or route_result.profile_digests != _PROFILE_DIGESTS
        ):
            raise ValueError
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.SUCCESSOR_AUTHORITY_MISMATCH,
            _DECISION_FILE_HASH,
            _DECISION_HASH,
            _AUTHORITY_HASH,
            route_subject,
        )

    try:
        sources = route_result.source_events
        projections = route_result.projection_events
        manifest = route_result.market_bundle_manifest
        if (
            route_result.market_bundle_ref.manifest_hash != _BUNDLE_MANIFEST_HASH
            or manifest.content_hash != _BUNDLE_CONTENT_HASH
            or len(sources) != 19
            or len(projections) != 19
            or tuple(value.event_hash for value in sources)
            != tuple(g12i["published_event_hashes"])
            or any(
                type(value).__name__ != "MarketEvent"
                or value.stream_key
                != "tushare_cn_a_share.daily.publication.xshe.000001.v1"
                for value in sources
            )
            or any(
                type(value).__name__ != "MarketEvent"
                or value.stream_key
                != "g12m.tushare.fixed-singleton.bar-open.v2"
                for value in projections
            )
            or len({value.event_hash for value in (*sources, *projections)}) != 38
        ):
            raise ValueError
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.BUNDLE_SOURCE_PROJECTION_MEMBERSHIP_MISMATCH,
            _BUNDLE_MANIFEST_HASH,
            _G12I_REPORT_HASH,
            route_subject,
        )

    try:
        target = route_result.target_stream.events
        request = route_result.execution_request
        if (
            route_result.target_stream.target_stream_digest != _TARGET_STREAM_DIGEST
            or len(target) != 1
            or target[0].event_id != "cn-a-share-fixed-singleton-zero-target-v1"
            or target[0].instrument_id is not None
            or target[0].event_time.epoch_nanoseconds != _DECISION_TIME
            or target[0].available_time.epoch_nanoseconds != _DECISION_TIME
            or request.schema_version != 4
            or request.request.experiment_id
            != "g12m-tushare-fixed-singleton-route-v2"
            or request.request.target_stream_digest != _TARGET_STREAM_DIGEST
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.TARGET_SINGLETON_MISMATCH,
            _TARGET_STREAM_DIGEST,
            route_subject,
        )

    try:
        rich = route_result.completed_evidence
        completed = route_result.completed
        if (
            type(rich) is not _VerifiedCompletedEvidenceV3
            or rich.completed != completed
            or len(rich.ready_attempts) != 2
            or len(rich.attempt_hashes) != 2
            or len(rich.finalized_attempts) != 2
            or len(rich.evidence_manifests) != 2
            or tuple(value.attempt for value in rich.ready_attempts)
            != (rich.first_attempt, rich.retry_attempt)
            or tuple(value.attempt for value in rich.attempt_hashes)
            != (rich.first_attempt, rich.retry_attempt)
            or tuple(value.attempt for value in rich.finalized_attempts)
            != (rich.first_attempt, rich.retry_attempt)
            or any(
                value.execution_result_hash != completed.source_execution_result_hash
                for value in rich.attempt_hashes
            )
            or rich.execution_result_hash != completed.source_execution_result_hash
            or rich.rebuild_verification.ref != completed.rebuild_verification_ref
            or rich.proof_publication_manifest.ref
            != completed.proof_publication_manifest_ref
            or rich.canonical_root.ref
            != route_result.publication_ref.artifact_ref
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.RUN_ATTEMPT_PROOF_MISMATCH,
            route_subject,
        )

    try:
        resolved = rich.resolved_request
        requested_grade = resolved.request.result_grade_requested
        result_grade = rich.integrity.result_grade
        if (
            resolved.request != request.request
            or not resolved.environment.compatibility_report.compatible
            or resolved.environment.deployment_authorized
            or requested_grade.value != "decision_grade"
            or result_grade is not completed.result_grade
            or result_grade is not route_result.analysis.result_grade
            or result_grade.value != "decision_grade"
            or rich.integrity.issue_codes
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.RESOLUTION_INTEGRITY_GRADE_MISMATCH,
            route_subject,
        )

    try:
        engine = rich.attempt_hashes[0].engine_result
        timeline_entries = tuple(
            value
            for value in engine.trace.entries
            if value.stage.value == "timeline_event"
        )
        expected_events = tuple(
            sorted(
                (*sources, *projections, target[0]),
                key=lambda value: (value.ordering_key, value.event_id),
            )
        )
        timeline_pairs = tuple(
            (value.subject_id, value.evidence_hash) for value in timeline_entries
        )
        if (
            len(timeline_entries) != 39
            or timeline_pairs
            != tuple((value.event_id, value.event_hash) for value in expected_events)
            or any(
                value.timeline_instant.instant.epoch_nanoseconds >= _DECISION_TIME
                for value in (*sources, *projections)
            )
            or target[0].timeline_instant.instant.epoch_nanoseconds != _DECISION_TIME
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.TIMELINE_CAUSALITY_MISMATCH,
            rich.trace_hash,
            route_subject,
        )

    try:
        starting = completed.starting_snapshot
        ending = engine.final_portfolio_snapshot
        financial = completed.engine_context.financial_state
        settlement = financial.settlement_book
        target_effect_count = sum(
            target_value.approved_notional.units != 0
            or target_value.source_target.target_notional.units != 0
            for batch in engine.approved_targets
            for target_value in batch.targets
        )
        counts = (
            target_effect_count,
            sum(len(value.planned_orders) for value in engine.order_plans),
            len(engine.fills),
            len(engine.fee_assessments),
            len(settlement.obligations) + len(settlement.events),
            len(financial.lot_books),
            len(starting.positions) + len(ending.positions),
            0,
            0,
        )
        if (
            any(counts)
            or tuple(value.role for value in engine.financial_artifacts)
            != ("final_snapshot",)
            or engine.order_streams
            or engine.slippage_decisions
            or starting.cash != ending.cash
            or starting.positions != ending.positions
            or starting.realized_pnl != ending.realized_pnl
            or starting.unrealized_pnl != ending.unrealized_pnl
            or starting.fees != ending.fees
            or starting.financing != ending.financing
            or starting.equity != ending.equity
            or ending.valuation_marks
            or len(engine.final_journal.entries)
            != completed.initial_journal_entry_count
            or engine.final_journal != financial.journal
        ):
            raise ValueError
    except (AttributeError, TypeError, ValueError):
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.ACCOUNTING_DISPOSITION_MISMATCH,
            completed.source_execution_result_hash,
            route_subject,
        )

    if assessed_at.epoch_nanoseconds < _ASSESSMENT_FLOOR:
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.ASSESSMENT_TIME_INVALID,
            _G12K_REPORT_HASH,
        )

    if predecessor_assessment is not None:
        predecessor_subject = _safe_hash_attr(
            predecessor_assessment,
            "assessment_hash",
            _DECISION_HASH,
        )
        try:
            predecessor_assessment.__post_init__()
        except (AttributeError, TypeError, ValueError):
            return _failure(
                TushareFixedSingletonAssessmentFailureCodeV2.DIRECT_PREDECESSOR_INVALID,
                predecessor_subject,
            )
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.DIRECT_PREDECESSOR_INVALID,
            predecessor_subject,
        )

    try:
        route_result.__post_init__()
        rich._validate_self()
        source_triples = tuple(
            (
                value.event_id,
                value.event_hash,
                value.timeline_instant.instant.epoch_nanoseconds,
            )
            for value in sources
        )
        projection_triples = tuple(
            (
                value.event_id,
                value.event_hash,
                value.timeline_instant.instant.epoch_nanoseconds,
            )
            for value in projections
        )
        target_triple = (
            target[0].event_id,
            target[0].event_hash,
            target[0].timeline_instant.instant.epoch_nanoseconds,
        )
        values: dict[str, object] = {
            "successor_decision_file_hash": _DECISION_FILE_HASH,
            "successor_decision_hash": _DECISION_HASH,
            "successor_decision_predecessor_hash": _PREDECESSOR_HASH,
            "g12i_canonical_file_hash": _G12I_FILE_HASH,
            "g12i_report_hash": _G12I_REPORT_HASH,
            "g12k_canonical_file_hash": _G12K_FILE_HASH,
            "g12k_report_hash": _G12K_REPORT_HASH,
            "authority_hash": route_result.authority_hash,
            "profile_digests": route_result.profile_digests,
            "build_manifest_hash": route_result.build_manifest_hash,
            "market_bundle_ref": route_result.market_bundle_ref,
            "market_bundle_content_hash": manifest.content_hash,
            "source_event_triples": source_triples,
            "projection_event_triples": projection_triples,
            "target_event_triple": target_triple,
            "execution_input_ref": request.execution_input_bundle_ref,
            "execution_input_source_hash": route_result.execution_input_source_hash,
            "request_hash": domain.canonical_sha256(resolved.request),
            "resolved_environment_hash": domain.canonical_sha256(resolved.environment),
            "compatibility_report_hash": domain.canonical_sha256(
                resolved.environment.compatibility_report
            ),
            "semantic_run_id": completed.semantic_run_id,
            "attempt_ids": (
                rich.first_attempt.attempt_id,
                rich.retry_attempt.attempt_id,
            ),
            "attempt_hashes": tuple(
                domain.canonical_sha256(value) for value in rich.attempt_hashes
            ),
            "execution_result_hash": completed.source_execution_result_hash,
            "trace_hash": rich.trace_hash,
            "timeline_event_pairs": timeline_pairs,
            "rebuild_verification_ref": completed.rebuild_verification_ref,
            "proof_publication_manifest_ref": completed.proof_publication_manifest_ref,
            "canonical_publication_ref": route_result.publication_ref,
            "integrity_report_ref": rich.integrity.artifact.ref,
            "integrity_context_hash": rich.integrity.context_hash,
            "requested_grade": requested_grade,
            "result_grade": result_grade,
            "static_verification_hash": rich.static_verification_hash,
            "metric_profile_ref": route_result.metric_profile_ref,
            "analysis_ref": route_result.analysis_ref,
            "analysis_hash": domain.canonical_sha256(route_result.analysis),
            "accounting_disposition": _DISPOSITION,
            "target_effect_count": counts[0],
            "order_count": counts[1],
            "fill_count": counts[2],
            "fee_count": counts[3],
            "settlement_count": counts[4],
            "lot_count": counts[5],
            "exposure_count": counts[6],
            "entitlement_count": counts[7],
            "corporate_action_dispatch_count": counts[8],
            "assessed_at": assessed_at,
            "supersedes_assessment_hash": None,
            "limitations": _LIMITATIONS,
            "nonclaims": _NONCLAIMS,
            "live_eligible": False,
            "deployment_authorized": False,
        }
        body = {
            "type": "g12m_tushare_fixed_singleton_source_bounded_assessment_v2",
            "schema_version": 2,
            **values,
            "requested_grade": requested_grade.value,
            "result_grade": result_grade.value,
        }
        assessment = TushareFixedSingletonSourceBoundedAssessmentV2(
            **cast(Any, values),
            assessment_hash=domain.canonical_sha256(body),
        )
        assessment.__post_init__()
    except (AttributeError, KeyError, TypeError, ValueError):
        return _failure(
            TushareFixedSingletonAssessmentFailureCodeV2.ASSESSMENT_RECONSTRUCTION_MISMATCH,
            route_subject,
        )
    return TushareFixedSingletonAssessmentOutcomeV2(assessment, None)
