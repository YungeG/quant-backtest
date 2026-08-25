from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import UtcInstant, canonical_sha256

from .gree_2023_financial_statement_normalization_v1 import (
    Gree2023FinancialStatementKind,
    Gree2023FinancialStatementObservationSetV1,
)

_SCHEMA_VERSION = 1
_POLICY_KEY = "qb-fin-select-01.gree-fixed-current-consolidated.v1"
_INSTRUMENT = "xshe:000651"
_PERIOD = "20231231"
_OBSERVATION_SET_HASH = "sha256:632206f85bcff71dbcccfd20a3593e14fb895b33bd138ac25bbf9b947e4a4a7c"
_REVISION_IDS = (
    "sha256:8957590f45f32ed9b285e940f2fa0c0524cb28377e86c745ab39aa3875ba63e8",
    "sha256:3e64ee623ca3676f1ec10daf56588dceabdd77a41ba0419d4c9010241313f45d",
    "sha256:71f4428e79d3bd7638cc9c1d98c1471f9802e9a90d25f7fa06b739bc57f0f986",
)
_AVAILABLE_AT = UtcInstant(1_714_959_000_000_000_000)
_REPORT_HASH = "sha256:32ebc475a2291ce4f1b5c1a9f9da55227e03192f07e75041e976c29d213ec8aa"
_CONFIRMATION_HASH = "sha256:a78a67865a7ea989c4fd8b053fad1aa75f36d22c10d14387800ff16b698dbc60"
_SOURCE_FAMILY_HASH = "sha256:0d94a3298739339e6b54315f3193eba722604f0c354246abf06046c10dc6b6b9"


class Gree2023FinancialTrioSelectionFailureCode(str, Enum):
    INPUT_MISMATCH = "INPUT_MISMATCH"
    OBSERVATION_SET_MISMATCH = "OBSERVATION_SET_MISMATCH"
    NOT_VISIBLE = "NOT_VISIBLE"
    RESULT_RECONSTRUCTION_MISMATCH = "RESULT_RECONSTRUCTION_MISMATCH"


@dataclass(frozen=True, slots=True)
class Gree2023FinancialTrioSelectionFailure:
    code: Gree2023FinancialTrioSelectionFailureCode

    def __post_init__(self) -> None:
        if type(self.code) is not Gree2023FinancialTrioSelectionFailureCode:
            raise TypeError("code must be exact trio selection failure code")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._body())

    def _body(self) -> dict[str, object]:
        return {
            "type": "gree_2023_financial_trio_selection_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "failure_hash": self.failure_hash}


def _reconstruct_instant(value: object) -> UtcInstant | None:
    if type(value) is not UtcInstant:
        return None
    try:
        rebuilt = UtcInstant(value.epoch_nanoseconds)
        return rebuilt if rebuilt.to_canonical_dict() == value.to_canonical_dict() else None
    except (AttributeError, TypeError, ValueError):
        return None


def _reconstruct_observation_set(
    value: object,
) -> Gree2023FinancialStatementObservationSetV1 | None:
    if type(value) is not Gree2023FinancialStatementObservationSetV1:
        return None
    try:
        rebuilt = Gree2023FinancialStatementObservationSetV1(
            **{
                name: getattr(value, name)
                for name in Gree2023FinancialStatementObservationSetV1.__dataclass_fields__
            }
        )
        return rebuilt if rebuilt.to_canonical_dict() == value.to_canonical_dict() else None
    except (AttributeError, TypeError, ValueError):
        return None


def _request_body(
    decision_instant: UtcInstant,
    observation_set: Gree2023FinancialStatementObservationSetV1,
) -> dict[str, object]:
    return {
        "type": "gree_2023_financial_statement_trio_selection_request",
        "schema_version": _SCHEMA_VERSION,
        "policy_key": _POLICY_KEY,
        "decision_instant": decision_instant,
        "instrument_id": _INSTRUMENT,
        "report_period_end": _PERIOD,
        "required_statement_kinds": tuple(kind.value for kind in Gree2023FinancialStatementKind),
        "observation_set_hash": observation_set.observation_set_hash,
        "source_bounded_only": True,
    }


def _source_family_hash(observation_set: Gree2023FinancialStatementObservationSetV1) -> str:
    first = observation_set.revisions[0]
    return canonical_sha256(
        {
            "source_snapshot_id": observation_set.source_snapshot_id,
            "source_content_tree_hash": first.source_content_tree_hash,
            "source_provenance_hash": first.source_provenance_hash,
        }
    )


def _observation_set_matches(
    observation_set: Gree2023FinancialStatementObservationSetV1,
) -> bool:
    revisions = observation_set.revisions
    return (
        observation_set.observation_set_hash == _OBSERVATION_SET_HASH
        and tuple(value.revision_id for value in revisions) == _REVISION_IDS
        and tuple(value.statement_kind for value in revisions)
        == tuple(Gree2023FinancialStatementKind)
        and all(
            value.instrument_id == _INSTRUMENT
            and value.report_period_end == _PERIOD
            and value.period_kind == "ANNUAL"
            and value.presentation_basis == "CURRENT_CONSOLIDATED"
            and value.provider_revision_id is None
            and value.supersedes_revision_id is None
            and value.source_bounded is True
            and value.revision_closure_complete is False
            and value.decision_grade_eligible is False
            and value.deployment_authorized is False
            and value.available_at_utc == _AVAILABLE_AT
            and value.official_document_hash == _REPORT_HASH
            and value.publication_confirmation_hash == _CONFIRMATION_HASH
            for value in revisions
        )
        and len({value.consolidation_scope for value in revisions}) == 1
        and len({value.accounting_currency for value in revisions}) == 1
        and len({value.accounting_unit for value in revisions}) == 1
        and len({value.source_content_tree_hash for value in revisions}) == 1
        and len({value.source_provenance_hash for value in revisions}) == 1
        and _source_family_hash(observation_set) == _SOURCE_FAMILY_HASH
    )


@dataclass(frozen=True, slots=True)
class Gree2023FinancialStatementTrioSelectionV1:
    schema_version: int
    policy_key: str
    request_hash: str
    decision_instant: UtcInstant
    instrument_id: str
    report_period_end: str
    observation_set: Gree2023FinancialStatementObservationSetV1
    chosen_revision_ids: tuple[str, ...]
    visible_candidate_revision_ids: tuple[str, ...]
    rejected_pre_adjustment_revision_ids: tuple[str, ...]
    maximum_available_at: UtcInstant
    official_document_hash: str
    publication_confirmation_hash: str
    source_snapshot_family_hash: str
    source_bounded: bool
    revision_closure_complete: bool
    decision_grade_eligible: bool
    deployment_authorized: bool
    selection_hash: str

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != _SCHEMA_VERSION:
            raise ValueError("schema_version mismatch")
        if type(self.decision_instant) is not UtcInstant:
            raise TypeError("decision_instant must be exact UtcInstant")
        observation_set = _reconstruct_observation_set(self.observation_set)
        if observation_set is None or not _observation_set_matches(observation_set):
            raise ValueError("observation_set mismatch")
        object.__setattr__(self, "observation_set", observation_set)
        expected_request_hash = canonical_sha256(_request_body(self.decision_instant, observation_set))
        expected = (
            (self.policy_key, _POLICY_KEY),
            (self.request_hash, expected_request_hash),
            (self.instrument_id, _INSTRUMENT),
            (self.report_period_end, _PERIOD),
            (self.chosen_revision_ids, _REVISION_IDS),
            (self.visible_candidate_revision_ids, _REVISION_IDS),
            (self.rejected_pre_adjustment_revision_ids, ()),
            (self.maximum_available_at, _AVAILABLE_AT),
            (self.official_document_hash, _REPORT_HASH),
            (self.publication_confirmation_hash, _CONFIRMATION_HASH),
            (self.source_snapshot_family_hash, _SOURCE_FAMILY_HASH),
        )
        if any(value != required or type(value) is not type(required) for value, required in expected):
            raise ValueError("selection evidence mismatch")
        if self.decision_instant < self.maximum_available_at:
            raise ValueError("selection is not visible")
        if type(self.source_bounded) is not bool or not self.source_bounded:
            raise TypeError("source_bounded must be exact true")
        if any(
            type(value) is not bool or value
            for value in (
                self.revision_closure_complete,
                self.decision_grade_eligible,
                self.deployment_authorized,
            )
        ):
            raise TypeError("qualification flags must be exact false")
        expected_hash = canonical_sha256(self._body())
        if type(self.selection_hash) is not str:
            raise TypeError("selection_hash must be exact str")
        if self.selection_hash == "":
            object.__setattr__(self, "selection_hash", expected_hash)
        elif self.selection_hash != expected_hash:
            raise ValueError("selection_hash mismatch")

    def _body(self) -> dict[str, object]:
        return {
            "type": "gree_2023_financial_statement_trio_selection",
            "schema_version": self.schema_version,
            "policy_key": self.policy_key,
            "request_hash": self.request_hash,
            "decision_instant": self.decision_instant,
            "instrument_id": self.instrument_id,
            "report_period_end": self.report_period_end,
            "observation_set": self.observation_set.to_canonical_dict(),
            "chosen_revision_ids": self.chosen_revision_ids,
            "visible_candidate_revision_ids": self.visible_candidate_revision_ids,
            "rejected_pre_adjustment_revision_ids": self.rejected_pre_adjustment_revision_ids,
            "maximum_available_at": self.maximum_available_at,
            "official_document_hash": self.official_document_hash,
            "publication_confirmation_hash": self.publication_confirmation_hash,
            "source_snapshot_family_hash": self.source_snapshot_family_hash,
            "source_bounded": self.source_bounded,
            "revision_closure_complete": self.revision_closure_complete,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "selection_hash": self.selection_hash}


def _reconstruct_selection(
    value: object,
) -> Gree2023FinancialStatementTrioSelectionV1 | None:
    if type(value) is not Gree2023FinancialStatementTrioSelectionV1:
        return None
    try:
        rebuilt = Gree2023FinancialStatementTrioSelectionV1(
            **{
                name: getattr(value, name)
                for name in Gree2023FinancialStatementTrioSelectionV1.__dataclass_fields__
            }
        )
        return rebuilt if rebuilt.to_canonical_dict() == value.to_canonical_dict() else None
    except (AttributeError, TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class Gree2023FinancialTrioSelectionOutcome:
    selection: Gree2023FinancialStatementTrioSelectionV1 | None
    failure: Gree2023FinancialTrioSelectionFailure | None

    def __post_init__(self) -> None:
        if (self.selection is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one selection or failure")
        if self.selection is not None:
            trusted = _reconstruct_selection(self.selection)
            if trusted is None:
                raise ValueError("outcome selection reconstruction mismatch")
            object.__setattr__(self, "selection", trusted)
        if self.failure is not None:
            if type(self.failure) is not Gree2023FinancialTrioSelectionFailure:
                raise TypeError("failure must be exact trio selection failure")
            object.__setattr__(
                self,
                "failure",
                Gree2023FinancialTrioSelectionFailure(self.failure.code),
            )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "gree_2023_financial_trio_selection_outcome",
            "schema_version": _SCHEMA_VERSION,
            "selection": None if self.selection is None else self.selection.to_canonical_dict(),
            "failure": None if self.failure is None else self.failure.to_canonical_dict(),
        }


def _failed(
    code: Gree2023FinancialTrioSelectionFailureCode,
) -> Gree2023FinancialTrioSelectionOutcome:
    return Gree2023FinancialTrioSelectionOutcome(
        None,
        Gree2023FinancialTrioSelectionFailure(code),
    )


def _build_selection(
    observation_set: Gree2023FinancialStatementObservationSetV1,
    decision_instant: UtcInstant,
) -> Gree2023FinancialStatementTrioSelectionV1:
    return Gree2023FinancialStatementTrioSelectionV1(
        schema_version=_SCHEMA_VERSION,
        policy_key=_POLICY_KEY,
        request_hash=canonical_sha256(_request_body(decision_instant, observation_set)),
        decision_instant=decision_instant,
        instrument_id=_INSTRUMENT,
        report_period_end=_PERIOD,
        observation_set=observation_set,
        chosen_revision_ids=_REVISION_IDS,
        visible_candidate_revision_ids=_REVISION_IDS,
        rejected_pre_adjustment_revision_ids=(),
        maximum_available_at=_AVAILABLE_AT,
        official_document_hash=_REPORT_HASH,
        publication_confirmation_hash=_CONFIRMATION_HASH,
        source_snapshot_family_hash=_SOURCE_FAMILY_HASH,
        source_bounded=True,
        revision_closure_complete=False,
        decision_grade_eligible=False,
        deployment_authorized=False,
        selection_hash="",
    )


def select_gree_2023_financial_statement_trio_v1(
    observation_set: Gree2023FinancialStatementObservationSetV1,
    decision_instant: UtcInstant,
) -> Gree2023FinancialTrioSelectionOutcome:
    trusted_instant = _reconstruct_instant(decision_instant)
    if (
        type(observation_set) is not Gree2023FinancialStatementObservationSetV1
        or trusted_instant is None
    ):
        return _failed(Gree2023FinancialTrioSelectionFailureCode.INPUT_MISMATCH)
    trusted = _reconstruct_observation_set(observation_set)
    if trusted is None or not _observation_set_matches(trusted):
        return _failed(Gree2023FinancialTrioSelectionFailureCode.OBSERVATION_SET_MISMATCH)
    if trusted_instant < trusted.available_at_utc:
        return _failed(Gree2023FinancialTrioSelectionFailureCode.NOT_VISIBLE)
    try:
        selection = _build_selection(trusted, trusted_instant)
        rebuilt = _reconstruct_selection(selection)
        if rebuilt is None:
            raise ValueError("selection reconstruction mismatch")
        return Gree2023FinancialTrioSelectionOutcome(rebuilt, None)
    except (AttributeError, TypeError, ValueError):
        return _failed(Gree2023FinancialTrioSelectionFailureCode.RESULT_RECONSTRUCTION_MISMATCH)
