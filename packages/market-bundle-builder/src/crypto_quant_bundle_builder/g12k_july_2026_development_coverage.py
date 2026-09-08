from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import ClassVar, cast

from crypto_quant_domain import (
    CurrencyId,
    InstrumentCatalog,
    InstrumentDefinition,
    InstrumentId,
    InstrumentType,
    SimulationInstant,
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
    MarketEvent,
)

from .bundle_validation import validate_market_bundle_v1
from .coverage_declarations import RevisionTerminalLineage
from .g12b_universe_corporate_action_payloads import (
    G12BCorporateActionLifecycleRevisionPayloadV1,
    G12BCorporateActionStatusV1,
    G12BListingMembershipRevisionPayloadV1,
    _reconstruct_corporate_action_lifecycle_revision_payload_v1,
    _reconstruct_listing_membership_revision_payload_v1,
)

_TARGET_START = UtcInstant(1_783_267_200_000_000_000)
_TARGET_END_EXCLUSIVE = UtcInstant(1_785_427_200_000_000_000)
_LOCAL_START = date(2026, 7, 6)
_LOCAL_END_EXCLUSIVE = date(2026, 7, 31)
_INSTRUMENT_ID = InstrumentId(VenueId("xshe"), "xshe.corporate-action.stable")
_CNY = CurrencyId("CNY")
_INSTRUMENT_DEFINITION = InstrumentDefinition(
    _INSTRUMENT_ID,
    InstrumentType.EQUITY,
    None,
    _CNY,
    _CNY,
)
_CATALOG = InstrumentCatalog((_CNY,), (_INSTRUMENT_DEFINITION,), ())
_CATALOG_HASH = (
    "sha256:954cac9b51cdfae55bcf0f5dd6fbcbda5c7c353baca43fd00fcddeb6c34104bb"
)
_UNIVERSE_KEY = "equity.cn_a_share.xshe.corporate-action-development.v1"
_UNIVERSE_CONTEXT = _UNIVERSE_KEY + "|point_in_time|xshe:xshe.corporate-action.stable"
_ACTION_CONTEXT = (
    "cn-a-share-record-register-entitlement-v1|CN.XSHE|"
    "xshe:xshe.corporate-action.stable"
)
_UNIVERSE_STREAM = "g12k.universe.listing-membership"
_ACTION_STREAM = "g12k.corporate-actions.lifecycle"
_UNIVERSE_EVENT_TYPE = "listing_membership_revision"
_ACTION_EVENT_TYPE = "corporate_action_lifecycle_revision"
_UNIVERSE_CAPABILITY = MarketBundleCapability("universe", 1)
_ACTION_CAPABILITY = MarketBundleCapability("corporate_actions", 1)


def _text(name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{name} must be canonical non-empty text")
    canonical_bytes(value)
    return value


def _hash(name: str, value: object) -> str:
    text = _text(name, value)
    if (
        len(text) != 71
        or not text.startswith("sha256:")
        or any(character not in "0123456789abcdef" for character in text[7:])
    ):
        raise ValueError(f"{name} must be a canonical sha256 hash")
    return text


def _exact_tuple(
    name: str, value: object, item_type: type[object]
) -> tuple[object, ...]:
    if type(value) is not tuple or any(type(item) is not item_type for item in value):
        raise TypeError(f"{name} must be an exact tuple of {item_type.__name__}")
    return cast(tuple[object, ...], value)


def _utc(name: str, value: object) -> UtcInstant:
    if type(value) is not UtcInstant:
        raise TypeError(f"{name} must be UtcInstant")
    return value


def _simulation(name: str, value: object) -> SimulationInstant:
    if type(value) is not SimulationInstant:
        raise TypeError(f"{name} must be SimulationInstant")
    if (
        type(value.instant) is not UtcInstant
        or type(value.phase) is not TimelinePhase
        or type(value.source_sequence) is not SourceSequence
    ):
        raise TypeError(f"{name} must contain exact SimulationInstant values")
    return value


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        raise TypeError("value must be a canonical mapping")
    return cast(Mapping[str, object], value)


def _keys(value: Mapping[str, object], expected: set[str]) -> None:
    if set(value) != expected:
        raise ValueError("canonical mapping keys mismatch")


def _int(value: object) -> int:
    if type(value) is not int:
        raise TypeError("value must be an exact integer")
    return value


def _utc_from_mapping(value: object) -> UtcInstant:
    body = _mapping(value)
    _keys(body, {"type", "epoch_nanoseconds"})
    if body["type"] != "utc_instant":
        raise ValueError("UtcInstant type mismatch")
    return UtcInstant(_int(body["epoch_nanoseconds"]))


def _simulation_from_mapping(value: object) -> SimulationInstant:
    body = _mapping(value)
    _keys(body, {"type", "instant", "phase", "source_sequence"})
    if body["type"] != "simulation_instant":
        raise ValueError("SimulationInstant type mismatch")
    phase = _mapping(body["phase"])
    _keys(phase, {"type", "rank", "code"})
    if phase["type"] != "timeline_phase":
        raise ValueError("TimelinePhase type mismatch")
    sequence = _mapping(body["source_sequence"])
    _keys(sequence, {"type", "value"})
    if sequence["type"] != "source_sequence":
        raise ValueError("SourceSequence type mismatch")
    return SimulationInstant(
        _utc_from_mapping(body["instant"]),
        TimelinePhase(_int(phase["rank"]), _text("phase code", phase["code"])),
        SourceSequence(_int(sequence["value"])),
    )


def _date(value: str | None) -> date | None:
    if value is None:
        return None
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("date must be canonical ISO YYYY-MM-DD")
    return parsed


def _currency_from_mapping(value: object) -> CurrencyId:
    body = _mapping(value)
    _keys(body, {"type", "value"})
    if body["type"] != "currency_id":
        raise ValueError("CurrencyId type mismatch")
    return CurrencyId(_text("currency", body["value"]))


def _instrument_id_from_mapping(value: object) -> InstrumentId:
    body = _mapping(value)
    _keys(body, {"type", "venue", "stable_key"})
    if body["type"] != "instrument_id":
        raise ValueError("InstrumentId type mismatch")
    return InstrumentId(
        VenueId(_text("venue", body["venue"])),
        _text("stable_key", body["stable_key"]),
    )


def _instrument_definition_from_mapping(value: object) -> InstrumentDefinition:
    body = _mapping(value)
    _keys(
        body,
        {
            "type",
            "instrument_id",
            "instrument_type",
            "base_currency",
            "quote_currency",
            "settlement_currency",
        },
    )
    if body["type"] != "instrument_definition":
        raise ValueError("InstrumentDefinition type mismatch")
    base = body["base_currency"]
    return InstrumentDefinition(
        instrument_id=_instrument_id_from_mapping(body["instrument_id"]),
        instrument_type=InstrumentType(
            _text("instrument_type", body["instrument_type"])
        ),
        base_currency=None if base is None else _currency_from_mapping(base),
        quote_currency=_currency_from_mapping(body["quote_currency"]),
        settlement_currency=_currency_from_mapping(body["settlement_currency"]),
    )


def _instrument_catalog_from_mapping(value: object) -> InstrumentCatalog:
    body = _mapping(value)
    _keys(body, {"type", "currencies", "instruments", "symbol_timelines"})
    if body["type"] != "instrument_catalog":
        raise ValueError("InstrumentCatalog type mismatch")
    currencies = body["currencies"]
    instruments = body["instruments"]
    symbol_timelines = body["symbol_timelines"]
    if (
        type(currencies) is not list
        or type(instruments) is not list
        or type(symbol_timelines) is not list
        or symbol_timelines
    ):
        raise TypeError("catalog collections must be exact canonical lists")
    catalog = InstrumentCatalog(
        tuple(_currency_from_mapping(item) for item in currencies),
        tuple(_instrument_definition_from_mapping(item) for item in instruments),
        (),
    )
    if dict(body) != catalog.to_canonical_dict():
        raise ValueError("catalog canonical reconstruction mismatch")
    return catalog


def _deep_catalog(value: InstrumentCatalog) -> InstrumentCatalog:
    rebuilt = _instrument_catalog_from_mapping(value.to_canonical_dict())
    if rebuilt != value:
        raise ValueError("catalog contains non-canonical domain values")
    return rebuilt


class G12KCoverageScopeV1(str, Enum):
    UNIVERSE = "universe"
    CORPORATE_ACTIONS = "corporate_actions"


@dataclass(frozen=True, slots=True)
class G12KRevisionClosureDeclarationV1:
    type: ClassVar[str] = "g12k_revision_closure_declaration"
    schema_version: ClassVar[int] = 1

    scope: G12KCoverageScopeV1
    context_key: str
    target_start: UtcInstant
    target_end_exclusive: UtcInstant
    causal_visibility_limit: SimulationInstant
    event_hashes: tuple[str, ...]
    terminals: tuple[RevisionTerminalLineage, ...]
    source_key: str
    source_hash: str

    def __post_init__(self) -> None:
        if type(self) is not G12KRevisionClosureDeclarationV1:
            raise TypeError("declaration must be exact concrete type")
        if type(self.scope) is not G12KCoverageScopeV1:
            raise TypeError("scope must be G12KCoverageScopeV1")
        _text("context_key", self.context_key)
        start = _utc("target_start", self.target_start)
        end = _utc("target_end_exclusive", self.target_end_exclusive)
        if end <= start:
            raise ValueError("target interval must be non-empty")
        _simulation("causal_visibility_limit", self.causal_visibility_limit)
        hashes = cast(
            tuple[str, ...], _exact_tuple("event_hashes", self.event_hashes, str)
        )
        for value in hashes:
            _hash("event_hash", value)
        if hashes != tuple(sorted(set(hashes))):
            raise ValueError("event_hashes must be sorted and unique")
        terminals = cast(
            tuple[RevisionTerminalLineage, ...],
            _exact_tuple("terminals", self.terminals, RevisionTerminalLineage),
        )
        keys = tuple(item.logical_lineage_key for item in terminals)
        if keys != tuple(sorted(set(keys))):
            raise ValueError("terminals must be sorted by unique lineage key")
        if bool(hashes) != bool(terminals):
            raise ValueError(
                "event hashes and terminals must both be empty or non-empty"
            )
        _text("source_key", self.source_key)
        _hash("source_hash", self.source_hash)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "scope": self.scope.value,
            "context_key": self.context_key,
            "target_start": self.target_start.to_canonical_dict(),
            "target_end_exclusive": self.target_end_exclusive.to_canonical_dict(),
            "causal_visibility_limit": self.causal_visibility_limit.to_canonical_dict(),
            "event_hashes": list(self.event_hashes),
            "terminals": [item.to_canonical_dict() for item in self.terminals],
            "source_key": self.source_key,
            "source_hash": self.source_hash,
        }

    @property
    def declaration_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "declaration_hash": self.declaration_hash}


@dataclass(frozen=True, slots=True)
class UniverseCoverageReport:
    type: ClassVar[str] = "universe_coverage_report"
    schema_version: ClassVar[int] = 1

    manifest_content_hash: str
    instrument_catalog_hash: str
    closure_declaration_hash: str
    target_start: UtcInstant
    target_end_exclusive: UtcInstant
    decision_instant: SimulationInstant
    effective_at: UtcInstant
    relevant_event_hashes: tuple[str, ...]
    terminal_event_hashes: tuple[str, ...]
    member_instrument_ids: tuple[InstrumentId, ...]
    declared_revision_closure_complete: bool = field(default=True, init=False)
    provider_authority_qualified: bool = field(default=False, init=False)
    provider_revision_completeness_qualified: bool = field(default=False, init=False)
    historical_authority_qualified: bool = field(default=False, init=False)
    survivorship_bias_safe: bool = field(default=False, init=False)
    decision_grade_eligible: bool = field(default=False, init=False)
    profile_qualified: bool = field(default=False, init=False)
    live_eligible: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if type(self) is not UniverseCoverageReport:
            raise TypeError("report must be exact concrete type")
        for name in (
            "manifest_content_hash",
            "instrument_catalog_hash",
            "closure_declaration_hash",
        ):
            _hash(name, getattr(self, name))
        _utc("target_start", self.target_start)
        _utc("target_end_exclusive", self.target_end_exclusive)
        _simulation("decision_instant", self.decision_instant)
        _utc("effective_at", self.effective_at)
        if (
            self.instrument_catalog_hash != _CATALOG_HASH
            or self.target_start != _TARGET_START
            or self.target_end_exclusive != _TARGET_END_EXCLUSIVE
            or self.effective_at != _TARGET_START
        ):
            raise ValueError("universe report fixed target binding mismatch")
        _canonical_hash_tuple("relevant_event_hashes", self.relevant_event_hashes)
        _canonical_hash_tuple("terminal_event_hashes", self.terminal_event_hashes)
        ids = cast(
            tuple[InstrumentId, ...],
            _exact_tuple(
                "member_instrument_ids", self.member_instrument_ids, InstrumentId
            ),
        )
        if ids != tuple(sorted(set(ids), key=str)):
            raise ValueError(
                "member InstrumentIds must be canonically ordered and unique"
            )
        _qualification(self)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "manifest_content_hash": self.manifest_content_hash,
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "closure_declaration_hash": self.closure_declaration_hash,
            "target_start": self.target_start.to_canonical_dict(),
            "target_end_exclusive": self.target_end_exclusive.to_canonical_dict(),
            "decision_instant": self.decision_instant.to_canonical_dict(),
            "effective_at": self.effective_at.to_canonical_dict(),
            "relevant_event_hashes": list(self.relevant_event_hashes),
            "terminal_event_hashes": list(self.terminal_event_hashes),
            "member_instrument_ids": [
                item.to_canonical_dict() for item in self.member_instrument_ids
            ],
            "declared_revision_closure_complete": self.declared_revision_closure_complete,
            "provider_authority_qualified": self.provider_authority_qualified,
            "provider_revision_completeness_qualified": self.provider_revision_completeness_qualified,
            "historical_authority_qualified": self.historical_authority_qualified,
            "survivorship_bias_safe": self.survivorship_bias_safe,
            "decision_grade_eligible": self.decision_grade_eligible,
            "profile_qualified": self.profile_qualified,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def report_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        self._validate()
        return {**self._canonical_body(), "report_hash": self.report_hash}


@dataclass(frozen=True, slots=True)
class CorporateActionCoverageReport:
    type: ClassVar[str] = "corporate_action_coverage_report"
    schema_version: ClassVar[int] = 1

    manifest_content_hash: str
    instrument_catalog_hash: str
    closure_declaration_hash: str
    target_start: UtcInstant
    target_end_exclusive: UtcInstant
    relevant_event_hashes: tuple[str, ...]
    terminal_event_hashes: tuple[str, ...]
    active_corporate_action_ids: tuple[str, ...]
    cancelled_corporate_action_ids: tuple[str, ...]
    declared_revision_closure_complete: bool = field(default=True, init=False)
    provider_authority_qualified: bool = field(default=False, init=False)
    provider_revision_completeness_qualified: bool = field(default=False, init=False)
    historical_authority_qualified: bool = field(default=False, init=False)
    survivorship_bias_safe: bool = field(default=False, init=False)
    decision_grade_eligible: bool = field(default=False, init=False)
    profile_qualified: bool = field(default=False, init=False)
    live_eligible: bool = field(default=False, init=False)
    deployment_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if type(self) is not CorporateActionCoverageReport:
            raise TypeError("report must be exact concrete type")
        for name in (
            "manifest_content_hash",
            "instrument_catalog_hash",
            "closure_declaration_hash",
        ):
            _hash(name, getattr(self, name))
        _utc("target_start", self.target_start)
        _utc("target_end_exclusive", self.target_end_exclusive)
        if (
            self.instrument_catalog_hash != _CATALOG_HASH
            or self.target_start != _TARGET_START
            or self.target_end_exclusive != _TARGET_END_EXCLUSIVE
        ):
            raise ValueError("corporate-action report fixed target binding mismatch")
        _canonical_hash_tuple("relevant_event_hashes", self.relevant_event_hashes)
        _canonical_hash_tuple("terminal_event_hashes", self.terminal_event_hashes)
        for name in (
            "active_corporate_action_ids",
            "cancelled_corporate_action_ids",
        ):
            values = cast(tuple[str, ...], _exact_tuple(name, getattr(self, name), str))
            for value in values:
                _text(name, value)
            if values != tuple(sorted(set(values))):
                raise ValueError(f"{name} must be canonically ordered and unique")
        if set(self.active_corporate_action_ids) & set(
            self.cancelled_corporate_action_ids
        ):
            raise ValueError("action IDs cannot be both active and cancelled")
        _qualification(self)

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "manifest_content_hash": self.manifest_content_hash,
            "instrument_catalog_hash": self.instrument_catalog_hash,
            "closure_declaration_hash": self.closure_declaration_hash,
            "target_start": self.target_start.to_canonical_dict(),
            "target_end_exclusive": self.target_end_exclusive.to_canonical_dict(),
            "relevant_event_hashes": list(self.relevant_event_hashes),
            "terminal_event_hashes": list(self.terminal_event_hashes),
            "active_corporate_action_ids": list(self.active_corporate_action_ids),
            "cancelled_corporate_action_ids": list(self.cancelled_corporate_action_ids),
            "declared_revision_closure_complete": self.declared_revision_closure_complete,
            "provider_authority_qualified": self.provider_authority_qualified,
            "provider_revision_completeness_qualified": self.provider_revision_completeness_qualified,
            "historical_authority_qualified": self.historical_authority_qualified,
            "survivorship_bias_safe": self.survivorship_bias_safe,
            "decision_grade_eligible": self.decision_grade_eligible,
            "profile_qualified": self.profile_qualified,
            "live_eligible": self.live_eligible,
            "deployment_authorized": self.deployment_authorized,
        }

    @property
    def report_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        self._validate()
        return {**self._canonical_body(), "report_hash": self.report_hash}


def _canonical_hash_tuple(name: str, value: object) -> None:
    values = cast(tuple[str, ...], _exact_tuple(name, value, str))
    for item in values:
        _hash(name, item)
    if values != tuple(sorted(set(values))):
        raise ValueError(f"{name} must be canonically ordered and unique")


def _qualification(value: object) -> None:
    expected = {
        "declared_revision_closure_complete": True,
        "provider_authority_qualified": False,
        "provider_revision_completeness_qualified": False,
        "historical_authority_qualified": False,
        "survivorship_bias_safe": False,
        "decision_grade_eligible": False,
        "profile_qualified": False,
        "live_eligible": False,
        "deployment_authorized": False,
    }
    if any(getattr(value, name) is not frozen for name, frozen in expected.items()):
        raise ValueError("coverage qualification must remain frozen development-only")


class G12KJuly2026DevelopmentCoverageFailureCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    G12C_VALIDATION_FAILED = "g12c_validation_failed"
    BUNDLE_MANIFEST_MISMATCH = "bundle_manifest_mismatch"
    CATALOG_EVENT_BINDING_MISMATCH = "catalog_event_binding_mismatch"
    EVENT_CONTRACT_MISMATCH = "event_contract_mismatch"
    CLOSURE_MISMATCH = "closure_mismatch"
    COVERAGE_SEMANTICS_MISMATCH = "coverage_semantics_mismatch"


@dataclass(frozen=True, slots=True)
class G12KJuly2026DevelopmentCoverageFailure:
    type: ClassVar[str] = "g12k_july_2026_development_coverage_failure"
    schema_version: ClassVar[int] = 1

    code: G12KJuly2026DevelopmentCoverageFailureCode
    scope: G12KCoverageScopeV1 | None
    logical_lineage_key: str | None

    def __post_init__(self) -> None:
        if type(self) is not G12KJuly2026DevelopmentCoverageFailure:
            raise TypeError("failure must be exact concrete type")
        if type(self.code) is not G12KJuly2026DevelopmentCoverageFailureCode:
            raise TypeError("code must be exact failure code")
        if self.scope is not None and type(self.scope) is not G12KCoverageScopeV1:
            raise TypeError("scope must be G12KCoverageScopeV1 or None")
        if self.logical_lineage_key is not None:
            _text("logical_lineage_key", self.logical_lineage_key)
            if self.scope is None:
                raise ValueError("lineage attribution requires scope")
        if self.code in {
            G12KJuly2026DevelopmentCoverageFailureCode.INVALID_INPUT,
            G12KJuly2026DevelopmentCoverageFailureCode.G12C_VALIDATION_FAILED,
            G12KJuly2026DevelopmentCoverageFailureCode.BUNDLE_MANIFEST_MISMATCH,
            G12KJuly2026DevelopmentCoverageFailureCode.CATALOG_EVENT_BINDING_MISMATCH,
        } and (self.scope is not None or self.logical_lineage_key is not None):
            raise ValueError("top-level failure cannot carry scope attribution")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "code": self.code.value,
            "scope": None if self.scope is None else self.scope.value,
            "logical_lineage_key": self.logical_lineage_key,
        }

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "failure_hash": self.failure_hash}


@dataclass(frozen=True, slots=True)
class G12KJuly2026DevelopmentCoverageOutcome:
    type: ClassVar[str] = "g12k_july_2026_development_coverage_outcome"
    schema_version: ClassVar[int] = 1

    universe_report: UniverseCoverageReport | None
    corporate_action_report: CorporateActionCoverageReport | None
    failure: G12KJuly2026DevelopmentCoverageFailure | None

    def __post_init__(self) -> None:
        if type(self) is not G12KJuly2026DevelopmentCoverageOutcome:
            raise TypeError("outcome must be exact concrete type")
        success = (
            self.universe_report is not None
            and self.corporate_action_report is not None
        )
        failed = self.failure is not None
        if success == failed or (not success and not failed):
            raise ValueError("outcome must contain both reports or exactly one failure")
        if success:
            if type(self.universe_report) is not UniverseCoverageReport:
                raise TypeError("universe_report must be exact report type")
            if type(self.corporate_action_report) is not CorporateActionCoverageReport:
                raise TypeError("corporate_action_report must be exact report type")
        elif (
            self.universe_report is not None or self.corporate_action_report is not None
        ):
            raise ValueError("failure outcome cannot contain a partial report")
        if failed and type(self.failure) is not G12KJuly2026DevelopmentCoverageFailure:
            raise TypeError("failure must be exact failure type")

    def _canonical_body(self) -> dict[str, object]:
        return {
            "type": self.type,
            "schema_version": self.schema_version,
            "universe_report": (
                None
                if self.universe_report is None
                else self.universe_report.to_canonical_dict()
            ),
            "corporate_action_report": (
                None
                if self.corporate_action_report is None
                else self.corporate_action_report.to_canonical_dict()
            ),
            "failure": None
            if self.failure is None
            else self.failure.to_canonical_dict(),
        }

    @property
    def outcome_hash(self) -> str:
        return canonical_sha256(self._canonical_body())

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._canonical_body(), "outcome_hash": self.outcome_hash}


def _terminal_from_mapping(value: object) -> RevisionTerminalLineage:
    body = _mapping(value)
    _keys(
        body, {"type", "schema_version", "logical_lineage_key", "terminal_event_hash"}
    )
    if body["type"] != "revision_terminal_lineage" or body["schema_version"] != 1:
        raise ValueError("terminal identity mismatch")
    terminal = RevisionTerminalLineage(
        _text("logical_lineage_key", body["logical_lineage_key"]),
        _hash("terminal_event_hash", body["terminal_event_hash"]),
    )
    if dict(body) != terminal.to_canonical_dict():
        raise ValueError("terminal reconstruction mismatch")
    return terminal


def _closure_from_mapping(value: object) -> G12KRevisionClosureDeclarationV1:
    body = _mapping(value)
    _keys(
        body,
        {
            "type",
            "schema_version",
            "scope",
            "context_key",
            "target_start",
            "target_end_exclusive",
            "causal_visibility_limit",
            "event_hashes",
            "terminals",
            "source_key",
            "source_hash",
            "declaration_hash",
        },
    )
    if (
        body["type"] != G12KRevisionClosureDeclarationV1.type
        or body["schema_version"] != 1
    ):
        raise ValueError("closure identity mismatch")
    event_hashes_raw = body["event_hashes"]
    terminals_raw = body["terminals"]
    if type(event_hashes_raw) is not list or type(terminals_raw) is not list:
        raise TypeError("closure arrays must be exact lists")
    closure = G12KRevisionClosureDeclarationV1(
        scope=G12KCoverageScopeV1(_text("scope", body["scope"])),
        context_key=_text("context_key", body["context_key"]),
        target_start=_utc_from_mapping(body["target_start"]),
        target_end_exclusive=_utc_from_mapping(body["target_end_exclusive"]),
        causal_visibility_limit=_simulation_from_mapping(
            body["causal_visibility_limit"]
        ),
        event_hashes=tuple(_hash("event_hash", item) for item in event_hashes_raw),
        terminals=tuple(_terminal_from_mapping(item) for item in terminals_raw),
        source_key=_text("source_key", body["source_key"]),
        source_hash=_hash("source_hash", body["source_hash"]),
    )
    if (
        body["declaration_hash"] != closure.declaration_hash
        or dict(body) != closure.to_canonical_dict()
    ):
        raise ValueError("closure canonical reconstruction mismatch")
    return closure


def _deep_closure(
    value: G12KRevisionClosureDeclarationV1,
) -> G12KRevisionClosureDeclarationV1:
    return _closure_from_mapping(value.to_canonical_dict())


def _failed(
    code: G12KJuly2026DevelopmentCoverageFailureCode,
    scope: G12KCoverageScopeV1 | None = None,
    lineage: str | None = None,
) -> G12KJuly2026DevelopmentCoverageOutcome:
    return G12KJuly2026DevelopmentCoverageOutcome(
        None,
        None,
        G12KJuly2026DevelopmentCoverageFailure(code, scope, lineage),
    )


def _reconstruct_event_payload(
    event: MarketEvent,
    scope: G12KCoverageScopeV1,
) -> (
    G12BListingMembershipRevisionPayloadV1
    | G12BCorporateActionLifecycleRevisionPayloadV1
):
    if scope is G12KCoverageScopeV1.UNIVERSE:
        return _reconstruct_listing_membership_revision_payload_v1(event.payload)
    return _reconstruct_corporate_action_lifecycle_revision_payload_v1(event.payload)


def _lineage_key(
    payload: G12BListingMembershipRevisionPayloadV1
    | G12BCorporateActionLifecycleRevisionPayloadV1,
) -> str:
    if isinstance(payload, G12BListingMembershipRevisionPayloadV1):
        return payload.membership_key
    return payload.corporate_action_id


def _event_classification_matches(
    event: MarketEvent,
    scope: G12KCoverageScopeV1,
    payload: G12BListingMembershipRevisionPayloadV1
    | G12BCorporateActionLifecycleRevisionPayloadV1,
) -> bool:
    if scope is G12KCoverageScopeV1.UNIVERSE:
        return (
            event.event_type == _UNIVERSE_EVENT_TYPE
            and event.capability == _UNIVERSE_CAPABILITY
            and isinstance(payload, G12BListingMembershipRevisionPayloadV1)
            and payload.universe_key == _UNIVERSE_KEY
        )
    return (
        event.event_type == _ACTION_EVENT_TYPE
        and event.capability == _ACTION_CAPABILITY
        and isinstance(payload, G12BCorporateActionLifecycleRevisionPayloadV1)
    )


def _lineages(
    events: tuple[MarketEvent, ...],
    payloads: dict[
        str,
        G12BListingMembershipRevisionPayloadV1
        | G12BCorporateActionLifecycleRevisionPayloadV1,
    ],
    closure: G12KRevisionClosureDeclarationV1,
) -> tuple[dict[str, tuple[MarketEvent, ...]], str | None]:
    grouped: dict[str, list[MarketEvent]] = {}
    revision_keys: dict[str, list[str]] = {}
    for event in events:
        payload = payloads[event.event_hash]
        key = (
            payload.membership_key
            if isinstance(payload, G12BListingMembershipRevisionPayloadV1)
            else payload.corporate_action_id
        )
        grouped.setdefault(key, []).append(event)
        revision_keys.setdefault(event.revision_id, []).append(key)
    duplicate_revision_keys = sorted(
        key for keys in revision_keys.values() if len(keys) > 1 for key in set(keys)
    )
    if duplicate_revision_keys:
        return {}, duplicate_revision_keys[0]
    terminal_map = {
        item.logical_lineage_key: item.terminal_event_hash for item in closure.terminals
    }
    if set(grouped) != set(terminal_map):
        differing = sorted(set(grouped) ^ set(terminal_map))
        return {}, differing[0] if differing else None
    ordered: dict[str, tuple[MarketEvent, ...]] = {}
    for key in sorted(grouped):
        values = tuple(sorted(grouped[key], key=lambda item: item.event_hash))
        if any(
            event.timeline_instant > closure.causal_visibility_limit for event in values
        ):
            return {}, key
        if len({event.revision_id for event in values}) != len(values):
            return {}, key
        by_revision = {event.revision_id: event for event in values}
        roots = [event for event in values if event.supersedes_revision_id is None]
        if len(roots) != 1:
            return {}, key
        children: dict[str, list[MarketEvent]] = {}
        for event in values:
            parent_id = event.supersedes_revision_id
            if parent_id is None:
                continue
            parent = by_revision.get(parent_id)
            if parent is None:
                return {}, key
            if event.timeline_instant <= parent.timeline_instant:
                return {}, key
            children.setdefault(parent_id, []).append(event)
            if len(children[parent_id]) > 1:
                return {}, key
        chain: list[MarketEvent] = []
        current = roots[0]
        seen: set[str] = set()
        while current.revision_id not in seen:
            seen.add(current.revision_id)
            chain.append(current)
            next_values = children.get(current.revision_id, [])
            if not next_values:
                break
            current = next_values[0]
        if len(chain) != len(values) or chain[-1].event_hash != terminal_map[key]:
            return {}, key
        first_payload = payloads[chain[0].event_hash]
        identity = (
            (
                first_payload.universe_key,
                first_payload.membership_key,
                chain[0].instrument_id,
            )
            if isinstance(first_payload, G12BListingMembershipRevisionPayloadV1)
            else (
                first_payload.corporate_action_id,
                first_payload.calendar_id,
                chain[0].instrument_id,
            )
        )
        for event in chain[1:]:
            payload = payloads[event.event_hash]
            candidate_identity = (
                (payload.universe_key, payload.membership_key, event.instrument_id)
                if isinstance(payload, G12BListingMembershipRevisionPayloadV1)
                else (
                    payload.corporate_action_id,
                    payload.calendar_id,
                    event.instrument_id,
                )
            )
            if candidate_identity != identity:
                return {}, key
        ordered[key] = tuple(chain)
    return ordered, None


def _valid_membership(payload: G12BListingMembershipRevisionPayloadV1) -> bool:
    if payload.delisted_at is not None and payload.delisted_at <= payload.listed_at:
        return False
    if payload.member_until is not None and payload.member_until <= payload.member_from:
        return False
    if payload.member_from < payload.listed_at:
        return False
    return not (
        payload.delisted_at is not None
        and (payload.member_until is None or payload.member_until > payload.delisted_at)
    )


def _contains(start: UtcInstant, end: UtcInstant | None, instant: UtcInstant) -> bool:
    return start <= instant and (end is None or instant < end)


def _valid_distribution_group(
    values: tuple[int | None, int | None, str | None],
    *,
    exact_scale: int | None,
    exact_identity: str,
) -> tuple[bool, bool]:
    if all(value is None for value in values):
        return True, False
    units, scale, identity = values
    if units is None or scale is None or identity is None:
        return False, False
    scale_valid = scale == exact_scale if exact_scale is not None else 0 <= scale <= 18
    return units > 0 and scale_valid and identity == exact_identity, True


def _valid_action(
    payload: G12BCorporateActionLifecycleRevisionPayloadV1, *, terminal: bool
) -> bool:
    if payload.calendar_id != "CN.XSHE":
        return False
    try:
        dates = tuple(
            _date(value)
            for value in (
                payload.record_date,
                payload.ex_date,
                payload.payment_date,
                payload.listing_date,
            )
        )
    except ValueError:
        return False
    record, ex, payment, listing = dates
    cash_valid, cash = _valid_distribution_group(
        (
            payload.cash_per_share_units,
            payload.cash_per_share_scale,
            payload.cash_currency,
        ),
        exact_scale=2,
        exact_identity="CNY",
    )
    bonus_valid, bonus = _valid_distribution_group(
        (
            payload.bonus_rate_units,
            payload.bonus_rate_scale,
            payload.bonus_rate_basis,
        ),
        exact_scale=None,
        exact_identity="shares_per_share",
    )
    capitalization_valid, capitalization = _valid_distribution_group(
        (
            payload.capitalization_rate_units,
            payload.capitalization_rate_scale,
            payload.capitalization_rate_basis,
        ),
        exact_scale=None,
        exact_identity="shares_per_share",
    )
    if not (cash_valid and bonus_valid and capitalization_valid):
        return False
    if payload.status is G12BCorporateActionStatusV1.CANCELLED:
        return (
            terminal
            and all(value is None for value in dates)
            and not (cash or bonus or capitalization)
        )
    if payload.status is G12BCorporateActionStatusV1.PLAN_ONLY:
        return not terminal
    if record is None or ex is None or not (cash or bonus or capitalization):
        return False
    if cash and payment is None:
        return False
    return not ((bonus or capitalization) and listing is None)


def analyze_g12k_july_2026_development_coverage_v1(
    *,
    manifest: MarketBundleManifest,
    instrument_catalog: InstrumentCatalog,
    events: tuple[MarketEvent, ...],
    universe_closure: G12KRevisionClosureDeclarationV1,
    corporate_action_closure: G12KRevisionClosureDeclarationV1,
) -> G12KJuly2026DevelopmentCoverageOutcome:
    if (
        type(manifest) is not MarketBundleManifest
        or type(instrument_catalog) is not InstrumentCatalog
        or type(events) is not tuple
        or any(type(event) is not MarketEvent for event in events)
        or type(universe_closure) is not G12KRevisionClosureDeclarationV1
        or type(corporate_action_closure) is not G12KRevisionClosureDeclarationV1
    ):
        return _failed(G12KJuly2026DevelopmentCoverageFailureCode.INVALID_INPUT)

    validation = validate_market_bundle_v1(
        bundle_key=manifest.bundle_key,
        schema_version=manifest.schema_version,
        coverage_start=manifest.coverage_start,
        coverage_end_exclusive=manifest.coverage_end_exclusive,
        instrument_catalog_hash=manifest.instrument_catalog_hash,
        events=events,
    )
    if validation.failure is not None:
        return _failed(
            G12KJuly2026DevelopmentCoverageFailureCode.G12C_VALIDATION_FAILED
        )
    if (
        validation.manifest != manifest
        or manifest.coverage_start != _TARGET_START
        or manifest.coverage_end_exclusive != _TARGET_END_EXCLUSIVE
    ):
        return _failed(
            G12KJuly2026DevelopmentCoverageFailureCode.BUNDLE_MANIFEST_MISMATCH
        )

    try:
        rebuilt_catalog = _deep_catalog(instrument_catalog)
        if (
            rebuilt_catalog != _CATALOG
            or canonical_sha256(rebuilt_catalog) != _CATALOG_HASH
            or manifest.instrument_catalog_hash != _CATALOG_HASH
            or any(event.instrument_id != _INSTRUMENT_ID for event in events)
        ):
            raise ValueError("catalog or Event binding mismatch")
    except (AttributeError, LookupError, TypeError, ValueError):
        return _failed(
            G12KJuly2026DevelopmentCoverageFailureCode.CATALOG_EVENT_BINDING_MISMATCH
        )

    if any(
        event.stream_key not in {_UNIVERSE_STREAM, _ACTION_STREAM} for event in events
    ):
        return _failed(
            G12KJuly2026DevelopmentCoverageFailureCode.EVENT_CONTRACT_MISMATCH
        )

    candidates = {
        G12KCoverageScopeV1.UNIVERSE: tuple(
            sorted(
                (event for event in events if event.stream_key == _UNIVERSE_STREAM),
                key=lambda item: item.event_hash,
            )
        ),
        G12KCoverageScopeV1.CORPORATE_ACTIONS: tuple(
            sorted(
                (event for event in events if event.stream_key == _ACTION_STREAM),
                key=lambda item: item.event_hash,
            )
        ),
    }
    payloads: dict[
        G12KCoverageScopeV1,
        dict[
            str,
            G12BListingMembershipRevisionPayloadV1
            | G12BCorporateActionLifecycleRevisionPayloadV1,
        ],
    ] = {
        G12KCoverageScopeV1.UNIVERSE: {},
        G12KCoverageScopeV1.CORPORATE_ACTIONS: {},
    }
    event_failures: list[
        tuple[int, bool, str, str, G12KCoverageScopeV1 | None, str | None]
    ] = []
    for scope_rank, scope in enumerate(
        (G12KCoverageScopeV1.UNIVERSE, G12KCoverageScopeV1.CORPORATE_ACTIONS)
    ):
        for event in candidates[scope]:
            try:
                payload = _reconstruct_event_payload(event, scope)
            except (AttributeError, TypeError, ValueError):
                event_failures.append(
                    (scope_rank, True, "", event.event_hash, scope, None)
                )
                continue
            lineage = _lineage_key(payload)
            if not _event_classification_matches(event, scope, payload):
                event_failures.append(
                    (scope_rank, False, lineage, event.event_hash, scope, lineage)
                )
                continue
            payloads[scope][event.event_hash] = payload
    if event_failures:
        _, _, _, _, failing_scope, failing_lineage = min(event_failures)
        return _failed(
            G12KJuly2026DevelopmentCoverageFailureCode.EVENT_CONTRACT_MISMATCH,
            failing_scope,
            failing_lineage,
        )

    closures: dict[G12KCoverageScopeV1, G12KRevisionClosureDeclarationV1] = {}
    for scope, supplied, context in (
        (G12KCoverageScopeV1.UNIVERSE, universe_closure, _UNIVERSE_CONTEXT),
        (
            G12KCoverageScopeV1.CORPORATE_ACTIONS,
            corporate_action_closure,
            _ACTION_CONTEXT,
        ),
    ):
        try:
            closure = _deep_closure(supplied)
            if (
                closure != supplied
                or closure.scope is not scope
                or closure.context_key != context
                or closure.target_start != _TARGET_START
                or closure.target_end_exclusive != _TARGET_END_EXCLUSIVE
                or closure.event_hashes
                != tuple(event.event_hash for event in candidates[scope])
            ):
                raise ValueError("closure mismatch")
        except (TypeError, ValueError, AttributeError):
            return _failed(
                G12KJuly2026DevelopmentCoverageFailureCode.CLOSURE_MISMATCH, scope
            )
        closures[scope] = closure

    chains: dict[G12KCoverageScopeV1, dict[str, tuple[MarketEvent, ...]]] = {}
    for scope in (G12KCoverageScopeV1.UNIVERSE, G12KCoverageScopeV1.CORPORATE_ACTIONS):
        built, failing_lineage = _lineages(
            candidates[scope], payloads[scope], closures[scope]
        )
        if failing_lineage is not None:
            return _failed(
                G12KJuly2026DevelopmentCoverageFailureCode.CLOSURE_MISMATCH,
                scope,
                failing_lineage,
            )
        chains[scope] = built

    universe_relevant: list[str] = []
    universe_terminals: list[str] = []
    members: list[InstrumentId] = []
    for key, chain in chains[G12KCoverageScopeV1.UNIVERSE].items():
        for event in chain:
            lineage_payload = cast(
                G12BListingMembershipRevisionPayloadV1,
                payloads[G12KCoverageScopeV1.UNIVERSE][event.event_hash],
            )
            if not _valid_membership(lineage_payload):
                return _failed(
                    G12KJuly2026DevelopmentCoverageFailureCode.COVERAGE_SEMANTICS_MISMATCH,
                    G12KCoverageScopeV1.UNIVERSE,
                    key,
                )
        terminal = chain[-1]
        payload = cast(
            G12BListingMembershipRevisionPayloadV1,
            payloads[G12KCoverageScopeV1.UNIVERSE][terminal.event_hash],
        )
        universe_terminals.append(terminal.event_hash)
        if _contains(
            payload.listed_at, payload.delisted_at, _TARGET_START
        ) and _contains(payload.member_from, payload.member_until, _TARGET_START):
            universe_relevant.extend(event.event_hash for event in chain)
            members.append(cast(InstrumentId, terminal.instrument_id))
    if len(set(members)) != len(members):
        return _failed(
            G12KJuly2026DevelopmentCoverageFailureCode.COVERAGE_SEMANTICS_MISMATCH,
            G12KCoverageScopeV1.UNIVERSE,
        )

    action_relevant: list[str] = []
    action_terminals: list[str] = []
    active: list[str] = []
    cancelled: list[str] = []
    for key, chain in chains[G12KCoverageScopeV1.CORPORATE_ACTIONS].items():
        for index, event in enumerate(chain):
            payload = cast(
                G12BCorporateActionLifecycleRevisionPayloadV1,
                payloads[G12KCoverageScopeV1.CORPORATE_ACTIONS][event.event_hash],
            )
            if not _valid_action(payload, terminal=index == len(chain) - 1):
                return _failed(
                    G12KJuly2026DevelopmentCoverageFailureCode.COVERAGE_SEMANTICS_MISMATCH,
                    G12KCoverageScopeV1.CORPORATE_ACTIONS,
                    key,
                )
        terminal = chain[-1]
        terminal_payload = cast(
            G12BCorporateActionLifecycleRevisionPayloadV1,
            payloads[G12KCoverageScopeV1.CORPORATE_ACTIONS][terminal.event_hash],
        )
        relevance: date | None
        if terminal_payload.status is G12BCorporateActionStatusV1.FINAL_IMPLEMENTATION:
            relevance = _date(terminal_payload.record_date)
        elif terminal_payload.status is G12BCorporateActionStatusV1.CANCELLED:
            relevance = next(
                (
                    _date(
                        cast(
                            G12BCorporateActionLifecycleRevisionPayloadV1,
                            payloads[G12KCoverageScopeV1.CORPORATE_ACTIONS][
                                event.event_hash
                            ],
                        ).record_date
                    )
                    for event in reversed(chain[:-1])
                    if cast(
                        G12BCorporateActionLifecycleRevisionPayloadV1,
                        payloads[G12KCoverageScopeV1.CORPORATE_ACTIONS][
                            event.event_hash
                        ],
                    ).record_date
                    is not None
                ),
                None,
            )
            if relevance is None:
                return _failed(
                    G12KJuly2026DevelopmentCoverageFailureCode.COVERAGE_SEMANTICS_MISMATCH,
                    G12KCoverageScopeV1.CORPORATE_ACTIONS,
                    key,
                )
        else:
            return _failed(
                G12KJuly2026DevelopmentCoverageFailureCode.COVERAGE_SEMANTICS_MISMATCH,
                G12KCoverageScopeV1.CORPORATE_ACTIONS,
                key,
            )
        action_terminals.append(terminal.event_hash)
        if relevance is not None and _LOCAL_START <= relevance < _LOCAL_END_EXCLUSIVE:
            action_relevant.extend(event.event_hash for event in chain)
            if (
                terminal_payload.status
                is G12BCorporateActionStatusV1.FINAL_IMPLEMENTATION
            ):
                active.append(terminal_payload.corporate_action_id)
            else:
                cancelled.append(terminal_payload.corporate_action_id)
    if len(set(active + cancelled)) != len(active + cancelled):
        return _failed(
            G12KJuly2026DevelopmentCoverageFailureCode.COVERAGE_SEMANTICS_MISMATCH,
            G12KCoverageScopeV1.CORPORATE_ACTIONS,
        )

    universe_report = UniverseCoverageReport(
        manifest.content_hash,
        _CATALOG_HASH,
        closures[G12KCoverageScopeV1.UNIVERSE].declaration_hash,
        _TARGET_START,
        _TARGET_END_EXCLUSIVE,
        closures[G12KCoverageScopeV1.UNIVERSE].causal_visibility_limit,
        _TARGET_START,
        tuple(sorted(universe_relevant)),
        tuple(sorted(universe_terminals)),
        tuple(sorted(members, key=str)),
    )
    action_report = CorporateActionCoverageReport(
        manifest.content_hash,
        _CATALOG_HASH,
        closures[G12KCoverageScopeV1.CORPORATE_ACTIONS].declaration_hash,
        _TARGET_START,
        _TARGET_END_EXCLUSIVE,
        tuple(sorted(action_relevant)),
        tuple(sorted(action_terminals)),
        tuple(sorted(active)),
        tuple(sorted(cancelled)),
    )
    return G12KJuly2026DevelopmentCoverageOutcome(
        universe_report,
        action_report,
        None,
    )
