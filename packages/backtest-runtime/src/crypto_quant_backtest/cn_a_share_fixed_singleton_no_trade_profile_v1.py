"""Exact production authority for one China A-share zero-target no-trade case."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    OrderSide,
    PositionEffect,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent
from crypto_quant_trading import (
    AccountRiskPolicy,
    FeeReserveFundingSource,
    ProfileComponentRef,
    ProfilePortType,
)

from .ports import SimulationComponentRef, SimulationPortType
from .resolution import (
    ArtifactInstallMode,
    BuildArtifactManifest,
    BuildArtifactRef,
    BuildArtifactRole,
    BuildProvenance,
    ExecutionAccountProfileRegistration,
    MarketSemanticsProfileRegistration,
    RequestedResultGrade,
    RuntimeLibraryRef,
    SimulationProfileRegistration,
    SourceTreeState,
    StrategyFamily,
)
from .target_stream import (
    TARGET_STREAM_CAPABILITY,
    TARGET_STREAM_EVENT_TYPE,
    PrecomputedTargetStream,
)

_AUTHORITY_ID = "cn-a-share-fixed-singleton-no-trade-profile-build-authority-v1"
_MARKET_KEY = "equity.cn_a_share.fixed-singleton-no-trade.market.v1"
_SIMULATION_KEY = "backtest.cn_a_share.fixed-singleton-no-trade.simulation.v1"
_ACCOUNT_KEY = "account.cn_a_share.fixed-singleton-no-trade.cash.v1"
_ACCOUNT_ID = "cn-a-share-fixed-singleton-no-trade"
_ENGINE_KIND = "fixed_singleton_no_trade"
_INSTRUMENT = InstrumentId(VenueId("xshe"), "000001")
_CNY = CurrencyId("CNY")
_LATEST_ACCEPTED_MEMBER_ACQUIRED_AT_NS = 1_787_292_861_381_694_496
_DECISION_NS = _LATEST_ACCEPTED_MEMBER_ACQUIRED_AT_NS + 1
_GENERIC_CANDIDATE_COMMIT_NS = 1_787_391_728_000_000_000
_DECISION_PHASE = TimelinePhase(30, "strategy_decision")
_DAILY_CAPABILITY = MarketBundleCapability("tushare_cn_a_share.daily-publications", 1)
_G12I_REPORT = "sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029"
_G12I_FILE = "sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6"
_G12I_ASSESSMENT_NS = 1_787_292_861_381_694_496
_G12K_REPORT = "sha256:5a49065d87286a9673893337328ddbbab9a19cd3addf178bf96033b9b1babfd7"
_G12K_FILE = "sha256:a386f4281374d1449c0b5ba4371b9e9d2de5b236bc8fc5b5cdd8de5e43c65956"
_G12K_ASSESSMENT_NS = 1_787_299_622_295_499_670
_G07_CONTRACT = "sha256:30a2f6127969a58c946e8fde6369515aa236f7bac89c4e039ea35e7fce4f8be7"
_G07_GOLDEN = "sha256:33f262070a59ce52a350b99dcffdd9548a0643755690beeda9afffbada20aad7"
_G07_BACKTEST_GOVERNANCE = "606b7e866673f3a5eb71a69196687dd653561b42"
_G07_PLATFORM_CONSUMER = "5948dd62f50d197f3e35d499a8e44e04b2257981"
_G07_GITLINK_CANDIDATE = "cebb9b033b7eeffbbff712715fc017708ac5a247"
_DEPENDENCY_LOCK_HASH = "sha256:a97b6708411bcec45f23504cc41b3a2b54c80d9272a6deb3f2800be891e9b41d"
_PYTHON_BINARY_HASH = "sha256:4703a3d15898c0b5d81c3f939e93bdd8ca6116342093fb160ab1e01860dd7d8b"


class _ApplicabilityDisposition(str, Enum):
    ACTIVE_FIXED_CASE_AUTHORITY = "active_fixed_case_authority"
    INERT_BY_ZERO_TARGET_AND_ZERO_ORDER_CAPACITY = (
        "inert_by_zero_target_and_zero_order_capacity"
    )
    INERT_BY_ZERO_ORDER_CAPACITY = "inert_by_zero_order_capacity"
    INERT_BY_ZERO_EXPOSURE = "inert_by_zero_exposure"


@dataclass(frozen=True, slots=True)
class _FixedCase:
    instrument_id: InstrumentId
    dynamic_selector: bool
    accepted_scope_start: str
    accepted_scope_end_exclusive: str
    latest_accepted_member_acquired_at: UtcInstant
    decision_time: UtcInstant
    decision_phase: TimelinePhase
    target_value: str
    initial_exposure: str
    final_exposure: str
    target_event_count: int
    order_count: int
    fill_count: int
    fee_count: int
    settlement_count: int
    lot_count: int
    corporate_action_dispatch_count: int

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_fixed_singleton_no_trade_case_v1", **{name: getattr(self, name) for name in self.__dataclass_fields__}}


@dataclass(frozen=True, slots=True)
class _ProviderEvidenceIdentity:
    evidence_key: str
    report_hash: str
    canonical_file_hash: str
    assessment_time: UtcInstant
    role: str
    false_qualification_flags: tuple[str, ...]

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "accepted_provider_evidence_identity", **{name: getattr(self, name) for name in self.__dataclass_fields__}}


@dataclass(frozen=True, slots=True)
class _GenericProofAcceptance:
    contract_hash: str
    deterministic_verification_golden_hash: str
    backtest_governance_commit: str
    platform_consumer_commit: str
    platform_gitlink_candidate_commit: str
    accepted_scope: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "generic_durable_rebuild_proof_acceptance", **{name: getattr(self, name) for name in self.__dataclass_fields__}}


@dataclass(frozen=True, slots=True)
class _ComponentApplicability:
    component_ref: ProfileComponentRef | SimulationComponentRef
    disposition: _ApplicabilityDisposition
    justification: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "fixed_case_component_applicability",
            "component_ref": self.component_ref,
            "disposition": self.disposition.value,
            "justification": self.justification,
        }


@dataclass(frozen=True, slots=True)
class _TargetCommitment:
    stream: PrecomputedTargetStream
    event_count: int
    singleton_instrument_id: InstrumentId
    target_value: str
    event_hash: str
    payload_hash: str
    candidate_hash: str
    evidence_hash: str
    target_stream_digest: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "fixed_singleton_target_commitment_v1", **{name: getattr(self, name) for name in self.__dataclass_fields__}}


@dataclass(frozen=True, slots=True)
class _FixedMarketProfile:
    semantic_source_hash: str
    applicability_hash: str
    component_manifest: tuple[ProfileComponentRef, ...]
    profile_key: str = _MARKET_KEY
    profile_version: int = 1

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_fixed_singleton_market_profile_v1", **{name: getattr(self, name) for name in self.__dataclass_fields__}}


@dataclass(frozen=True, slots=True)
class _FixedSimulationProfile:
    semantic_source_hash: str
    applicability_hash: str
    target_stream_digest: str
    component_manifest: tuple[SimulationComponentRef, ...]
    profile_key: str = _SIMULATION_KEY
    profile_version: int = 1

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_fixed_singleton_simulation_profile_v1", **{name: getattr(self, name) for name in self.__dataclass_fields__}}


@dataclass(frozen=True, slots=True)
class _FixedExecutionAccountProfile:
    semantic_source_hash: str
    account_risk_policy: AccountRiskPolicy
    account_id: str = _ACCOUNT_ID
    venue_id: str = "xshe"
    account_type: str = "equity"
    margin_mode: str = "cash_only"
    profile_key: str = _ACCOUNT_KEY
    profile_version: int = 1

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_fixed_singleton_execution_account_profile_v1", **{name: getattr(self, name) for name in self.__dataclass_fields__}}


@dataclass(frozen=True, slots=True)
class _AuthorityValues:
    case: _FixedCase
    source_identities: tuple[_ProviderEvidenceIdentity, ...]
    generic_proof_acceptance: _GenericProofAcceptance
    target_commitment: _TargetCommitment
    component_applicability: tuple[_ComponentApplicability, ...]
    account_risk_policy: AccountRiskPolicy
    market_registration: MarketSemanticsProfileRegistration
    simulation_registration: SimulationProfileRegistration
    execution_account_registration: ExecutionAccountProfileRegistration
    build_manifest: BuildArtifactManifest
    nonclaims: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CnAShareFixedSingletonNoTradeAuthorityV1:
    """Closed immutable Profile/Build authority for exactly one no-trade case."""

    case: _FixedCase
    source_identities: tuple[_ProviderEvidenceIdentity, ...]
    generic_proof_acceptance: _GenericProofAcceptance
    target_commitment: _TargetCommitment
    component_applicability: tuple[_ComponentApplicability, ...]
    account_risk_policy: AccountRiskPolicy
    market_registration: MarketSemanticsProfileRegistration
    simulation_registration: SimulationProfileRegistration
    execution_account_registration: ExecutionAccountProfileRegistration
    build_manifest: BuildArtifactManifest
    nonclaims: tuple[str, ...]
    limitations: tuple[str, ...]
    decision_grade_eligible: bool
    deployment_authorized: bool
    supersedes_authority_hash: str | None
    authority_hash: str
    schema_version: int = 1
    authority_id: str = _AUTHORITY_ID

    def __post_init__(self) -> None:
        self._validate_self()

    def validate_target_stream(self, target_stream: PrecomputedTargetStream) -> None:
        self._validate_self()
        if type(target_stream) is not PrecomputedTargetStream:
            raise TypeError("target_stream must be exact PrecomputedTargetStream")
        expected = self.target_commitment.stream
        if (
            target_stream != expected
            or canonical_bytes(target_stream) != canonical_bytes(expected)
            or target_stream.target_stream_digest
            != self.target_commitment.target_stream_digest
        ):
            raise ValueError("target_stream does not match fixed singleton commitment")

    def _identity_body(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_fixed_singleton_no_trade_profile_build_authority_v1",
            "schema_version": self.schema_version,
            "authority_id": self.authority_id,
            "case": self.case,
            "source_identities": self.source_identities,
            "generic_proof_acceptance": self.generic_proof_acceptance,
            "target_commitment": self.target_commitment,
            "component_applicability": self.component_applicability,
            "account_risk_policy": self.account_risk_policy,
            "profile_registrations": (
                self.market_registration,
                self.simulation_registration,
                self.execution_account_registration,
            ),
            "build_manifest": self.build_manifest,
            "nonclaims": self.nonclaims,
            "limitations": self.limitations,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
            "supersedes_authority_hash": self.supersedes_authority_hash,
        }

    def _validate_self(self) -> None:
        if type(self) is not CnAShareFixedSingletonNoTradeAuthorityV1:
            raise TypeError("authority must be exact authority type")
        expected = _make_values()
        expected_fields = (
            expected.case,
            expected.source_identities,
            expected.generic_proof_acceptance,
            expected.target_commitment,
            expected.component_applicability,
            expected.account_risk_policy,
            expected.market_registration,
            expected.simulation_registration,
            expected.execution_account_registration,
            expected.build_manifest,
            expected.nonclaims,
            (),
            True,
            False,
            None,
            1,
            _AUTHORITY_ID,
        )
        actual_fields = (
            self.case,
            self.source_identities,
            self.generic_proof_acceptance,
            self.target_commitment,
            self.component_applicability,
            self.account_risk_policy,
            self.market_registration,
            self.simulation_registration,
            self.execution_account_registration,
            self.build_manifest,
            self.nonclaims,
            self.limitations,
            self.decision_grade_eligible,
            self.deployment_authorized,
            self.supersedes_authority_hash,
            self.schema_version,
            self.authority_id,
        )
        for actual, wanted in zip(actual_fields, expected_fields, strict=True):
            if type(actual) is not type(wanted) or actual != wanted:
                raise ValueError("authority fields do not match exact reconstruction")
        expected_hash = canonical_sha256(_identity_body_from_values(expected))
        if self.authority_hash != expected_hash:
            raise ValueError("authority_hash does not match exact reconstruction")
        if canonical_bytes(self._identity_body()) != canonical_bytes(
            _identity_body_from_values(expected)
        ):
            raise ValueError("authority canonical body does not match exact reconstruction")

    def to_canonical_dict(self) -> dict[str, object]:
        self._validate_self()
        return {**self._identity_body(), "authority_hash": self.authority_hash}


def _provider_identities() -> tuple[_ProviderEvidenceIdentity, ...]:
    return (
        _ProviderEvidenceIdentity(
            "g12i_tushare_cn_a_share_daily_source_bounded_v2",
            _G12I_REPORT,
            _G12I_FILE,
            UtcInstant(_G12I_ASSESSMENT_NS),
            "accepted_provider_evidence_only",
            (
                "corporate_actions_qualified",
                "decision_grade_eligible",
                "deployment_authorized",
                "historical_listing_status_qualified",
                "provider_qualified",
            ),
        ),
        _ProviderEvidenceIdentity(
            "g12k_tushare_fixed_instrument_source_bounded_v1",
            _G12K_REPORT,
            _G12K_FILE,
            UtcInstant(_G12K_ASSESSMENT_NS),
            "accepted_provider_evidence_only",
            (
                "corporate_action_lifecycle_qualified",
                "decision_grade_eligible",
                "deployment_authorized",
                "historical_listing_status_qualified",
                "listing_membership_continuity_qualified",
                "live_eligible",
                "profile_qualified",
                "provider_authority_qualified",
                "provider_revision_completeness_qualified",
            ),
        ),
    )


def _fixed_case() -> _FixedCase:
    return _FixedCase(
        _INSTRUMENT,
        False,
        "2026-07-06",
        "2026-07-31",
        UtcInstant(_LATEST_ACCEPTED_MEMBER_ACQUIRED_AT_NS),
        UtcInstant(_DECISION_NS),
        _DECISION_PHASE,
        "0",
        "0",
        "0",
        1,
        0,
        0,
        0,
        0,
        0,
        0,
    )


def _generic_proof() -> _GenericProofAcceptance:
    return _GenericProofAcceptance(
        _G07_CONTRACT,
        _G07_GOLDEN,
        _G07_BACKTEST_GOVERNANCE,
        _G07_PLATFORM_CONSUMER,
        _G07_GITLINK_CANDIDATE,
        "same-accepted-build immutable-local-input deterministic rebuild proof v2",
    )


def _target_stream(source_identities: tuple[_ProviderEvidenceIdentity, ...]) -> PrecomputedTargetStream:
    decision_time = UtcInstant(_DECISION_NS)
    evidence = {
        "g12i_report_hash": _G12I_REPORT,
        "g12i_canonical_file_hash": _G12I_FILE,
        "g12i_assessment_time": _G12I_ASSESSMENT_NS,
        "generic_proof_golden_hash": _G07_GOLDEN,
        "provider_evidence_sets_profile_grade": False,
    }
    candidate = {
        "schema_version": 1,
        "strategy_id": "cn-a-share-fixed-singleton-zero-target-v1",
        "sleeve_id": "cn-a-share-fixed-singleton.primary",
        "decision_time": _DECISION_NS,
        "observed_through": _LATEST_ACCEPTED_MEMBER_ACQUIRED_AT_NS,
        "effective_time": _DECISION_NS,
        "expires_at": _DECISION_NS + 1,
        "targets": [
            {
                "instrument_id": {"venue": "xshe", "stable_key": "000001"},
                "value": "0",
            }
        ],
        "confidence": "1",
        "reason": "exact accepted fixed-singleton no-trade authority",
        "evidence": evidence,
    }
    source_hash = canonical_sha256(
        {
            "type": "fixed_singleton_zero_target_source_v1",
            "decision_available_source_identity": source_identities[0],
            "decision_time": decision_time,
            "candidate": candidate,
        }
    )
    event = MarketEvent(
        event_id="cn-a-share-fixed-singleton-zero-target-v1",
        stream_key="cn-a-share-fixed-singleton-zero-target-v1",
        event_type=TARGET_STREAM_EVENT_TYPE,
        capability=TARGET_STREAM_CAPABILITY,
        instrument_id=None,
        event_time=decision_time,
        available_time=decision_time,
        phase=_DECISION_PHASE,
        source_sequence=SourceSequence(1),
        revision_id="initial",
        supersedes_revision_id=None,
        source_key="cn-a-share-fixed-singleton-no-trade-authority-v1",
        source_hash=source_hash,
        payload={"schema_version": 1, "candidate": candidate},
    )
    return PrecomputedTargetStream(event.stream_key, (event,))


def _target_commitment(
    source_identities: tuple[_ProviderEvidenceIdentity, ...],
) -> _TargetCommitment:
    stream = _target_stream(source_identities)
    event = stream.events[0]
    candidate = event.payload["candidate"]
    if not isinstance(candidate, Mapping):
        raise TypeError("exact target candidate must be a mapping")
    evidence = candidate["evidence"]
    if not isinstance(evidence, Mapping):
        raise TypeError("exact target evidence must be a mapping")
    return _TargetCommitment(
        stream,
        1,
        _INSTRUMENT,
        "0",
        event.event_hash,
        canonical_sha256(event.payload),
        canonical_sha256(candidate),
        canonical_sha256(evidence),
        stream.target_stream_digest,
    )


def _semantic_source_hash(
    case: _FixedCase,
    sources: tuple[_ProviderEvidenceIdentity, ...],
    proof: _GenericProofAcceptance,
    target: _TargetCommitment,
) -> str:
    return canonical_sha256(
        {
            "type": "cn_a_share_fixed_singleton_profile_semantic_sources_v1",
            "case": case,
            "source_identities": sources,
            "generic_proof_acceptance": proof,
            "target_stream_digest": target.target_stream_digest,
        }
    )


def _profile_component(
    port: ProfilePortType, key: str, semantic_source_hash: str
) -> ProfileComponentRef:
    return ProfileComponentRef(
        port,
        key,
        1,
        canonical_sha256(
            {
                "type": "cn_a_share_fixed_singleton_profile_component_identity_v1",
                "port_type": port.value,
                "component_key": key,
                "semantic_source_hash": semantic_source_hash,
            }
        ),
    )


def _simulation_component(
    port: SimulationPortType, key: str, semantic_source_hash: str
) -> SimulationComponentRef:
    return SimulationComponentRef(
        port,
        key,
        1,
        canonical_sha256(
            {
                "type": "cn_a_share_fixed_singleton_simulation_component_identity_v1",
                "port_type": port.value,
                "component_key": key,
                "semantic_source_hash": semantic_source_hash,
            }
        ),
    )


def _component_values(
    semantic_source_hash: str,
) -> tuple[
    tuple[ProfileComponentRef, ...],
    tuple[SimulationComponentRef, ...],
    tuple[_ComponentApplicability, ...],
]:
    profile_keys = {
        ProfilePortType.SESSION_MODEL: "equity.cn_a_share.fixed-july-2026-session.v1",
        ProfilePortType.INSTRUMENT_MODEL: "equity.cn_a_share.fixed-xshe-000001.v1",
        ProfilePortType.ORDER_RULE_MODEL: "equity.cn_a_share.cash.order-rules.v1",
        ProfilePortType.FEE_ASSESSMENT_POLICY: "equity.cn_a_share.cash.market-fees.route-product.v2",
        ProfilePortType.TAX_POLICY: "equity.cn_a_share.cash.stamp-duty.route-product.v2",
        ProfilePortType.SETTLEMENT_MODEL: "equity.cn_a_share.cash.settlement.v1",
        ProfilePortType.POSITION_ACCOUNTING_MODEL: "cash.instrument.position-accounting.v1",
        ProfilePortType.FINANCING_MODEL: "cash.no-financing.v1",
        ProfilePortType.MARGIN_MODEL: "cash.no-margin.v1",
        ProfilePortType.LIQUIDATION_RULES: "equity.cn_a_share.cash.liquidation-not-applicable.v1",
        ProfilePortType.CORPORATE_ACTION_MODEL: "equity.cn_a_share.corporate-action.inert-zero-exposure.v1",
        ProfilePortType.CURRENCY_VALUATION_POLICY: "equity.cn_a_share.cny-identity-valuation.v1",
    }
    simulation_keys = {
        SimulationPortType.EXECUTION_MODEL: "next_eligible_bar_open.v1",
        SimulationPortType.SLIPPAGE_MODEL: "zero_slippage.development.v1",
        SimulationPortType.LATENCY_MODEL: "latency.zero.development.v1",
        SimulationPortType.LIQUIDITY_MODEL: "liquidity.next-bar-full-fill.development.v1",
        SimulationPortType.LIQUIDATION_AUDIT_MODEL: "cash.no-liquidation-audit.v1",
        SimulationPortType.CLOSEOUT_POLICY: "mark_to_market.v1",
    }
    profile = tuple(
        sorted(
            (
                _profile_component(port, profile_keys[port], semantic_source_hash)
                for port in ProfilePortType
            ),
            key=lambda value: value.port_type.value,
        )
    )
    simulation = tuple(
        sorted(
            (
                _simulation_component(port, simulation_keys[port], semantic_source_hash)
                for port in SimulationPortType
            ),
            key=lambda value: value.port_type.value,
        )
    )
    zero_order = {
        ProfilePortType.ORDER_RULE_MODEL,
        ProfilePortType.FEE_ASSESSMENT_POLICY,
        ProfilePortType.TAX_POLICY,
        ProfilePortType.SETTLEMENT_MODEL,
        ProfilePortType.POSITION_ACCOUNTING_MODEL,
    }
    zero_exposure = {
        ProfilePortType.FINANCING_MODEL,
        ProfilePortType.MARGIN_MODEL,
        ProfilePortType.LIQUIDATION_RULES,
        ProfilePortType.CORPORATE_ACTION_MODEL,
        ProfilePortType.CURRENCY_VALUATION_POLICY,
    }
    applicability: list[_ComponentApplicability] = []
    for ref in profile:
        if ref.port_type in zero_order:
            disposition = _ApplicabilityDisposition.INERT_BY_ZERO_ORDER_CAPACITY
            reason = "zero order capacity prevents every trade, fee, tax, settlement, and lot mutation"
        elif ref.port_type in zero_exposure:
            disposition = _ApplicabilityDisposition.INERT_BY_ZERO_EXPOSURE
            reason = "zero initial and final exposure makes this component unreachable"
        else:
            disposition = _ApplicabilityDisposition.ACTIVE_FIXED_CASE_AUTHORITY
            reason = "exact fixed xshe:000001 July-2026 identity and accepted daily scope"
        applicability.append(_ComponentApplicability(ref, disposition, reason))
    for ref in simulation:
        if ref.port_type in {
            SimulationPortType.EXECUTION_MODEL,
            SimulationPortType.SLIPPAGE_MODEL,
            SimulationPortType.LATENCY_MODEL,
            SimulationPortType.LIQUIDITY_MODEL,
        }:
            disposition = (
                _ApplicabilityDisposition.INERT_BY_ZERO_TARGET_AND_ZERO_ORDER_CAPACITY
            )
            reason = "the exact zero target fails before translation and zero order capacity independently rejects admission"
        else:
            disposition = _ApplicabilityDisposition.INERT_BY_ZERO_EXPOSURE
            reason = "zero exposure makes liquidation audit and closeout unreachable"
        applicability.append(_ComponentApplicability(ref, disposition, reason))
    return profile, simulation, tuple(
        sorted(
            applicability,
            key=lambda value: (
                value.component_ref.port_type.value,
                type(value.component_ref).__name__,
            ),
        )
    )


def _account_risk_policy() -> AccountRiskPolicy:
    return AccountRiskPolicy.create(
        policy_key="equity.cn_a_share.fixed-singleton.zero-order-capacity.risk.v1",
        policy_version=1,
        account_id=_ACCOUNT_ID,
        venue_id=VenueId("xshe"),
        allowed_sides=(OrderSide.BUY, OrderSide.SELL),
        allowed_position_effects=(PositionEffect.OPEN, PositionEffect.CLOSE),
        allowed_reduce_only_values=(False, True),
        fee_reserve_funding_source=FeeReserveFundingSource.TRADABLE_CASH,
        order_capacity_limit=0,
        exposure_capacity_limits=(),
    )


def _source_snapshot_hash(role: BuildArtifactRole, artifact_key: str) -> str:
    return canonical_sha256(
        {
            "type": "cn_a_share_fixed_singleton_source_snapshot_preimage_v1",
            "generic_backtest_candidate_commit": _G07_GITLINK_CANDIDATE,
            "role": role.value,
            "artifact_key": artifact_key,
            "scope": "tracked source required by the exact generic candidate role",
        }
    )


def _build_manifest(
    target_digest: str,
    registrations: tuple[
        MarketSemanticsProfileRegistration,
        SimulationProfileRegistration,
        ExecutionAccountProfileRegistration,
    ],
) -> BuildArtifactManifest:
    core = (
        (BuildArtifactRole.TRADING_DOMAIN, "crypto-quant-domain"),
        (BuildArtifactRole.TRADING_KERNEL, "crypto-quant-trading"),
        (BuildArtifactRole.MARKET_DATA_CONTRACTS, "crypto-quant-market-data"),
        (BuildArtifactRole.BACKTEST_RUNTIME, "crypto-quant-backtest"),
    )
    artifacts = [
        BuildArtifactRef(
            BuildArtifactRole.DECISION_SOURCE,
            "cn-a-share-fixed-singleton-zero-target-v1",
            "1",
            ArtifactInstallMode.WHEEL,
            SourceTreeState.CLEAN,
            target_digest,
            None,
        )
    ]
    artifacts.extend(
        BuildArtifactRef(
            role,
            key,
            _G07_GITLINK_CANDIDATE,
            ArtifactInstallMode.WHEEL,
            SourceTreeState.CLEAN,
            None,
            _source_snapshot_hash(role, key),
        )
        for role, key in core
    )
    artifacts.extend(
        BuildArtifactRef(
            BuildArtifactRole.PROFILE_COMPONENT,
            registration.profile_key,
            str(registration.profile_version),
            ArtifactInstallMode.WHEEL,
            SourceTreeState.CLEAN,
            registration.profile_digest,
            None,
        )
        for registration in registrations
    )
    return BuildArtifactManifest(
        1,
        "cn-a-share-fixed-singleton-no-trade-build-v1",
        tuple(artifacts),
        _DEPENDENCY_LOCK_HASH,
        (RuntimeLibraryRef("cpython", "3.13.5", _PYTHON_BINARY_HASH),),
        None,
        BuildProvenance(
            _G07_GITLINK_CANDIDATE,
            "not-recorded-by-authority",
            "immutable-source-snapshots",
            UtcInstant(_GENERIC_CANDIDATE_COMMIT_NS),
        ),
    )


def _make_values() -> _AuthorityValues:
    case = _fixed_case()
    sources = _provider_identities()
    proof = _generic_proof()
    target = _target_commitment(sources)
    semantic_source_hash = _semantic_source_hash(case, sources, proof, target)
    profile_components, simulation_components, applicability = _component_values(
        semantic_source_hash
    )
    applicability_hash = canonical_sha256(applicability)
    risk = _account_risk_policy()
    market = _FixedMarketProfile(
        semantic_source_hash, applicability_hash, profile_components
    )
    simulation = _FixedSimulationProfile(
        semantic_source_hash,
        applicability_hash,
        target.target_stream_digest,
        simulation_components,
    )
    account = _FixedExecutionAccountProfile(semantic_source_hash, risk)
    market_registration = MarketSemanticsProfileRegistration(
        _MARKET_KEY,
        1,
        market.profile_digest,
        market,
        "xshe",
        (_DAILY_CAPABILITY,),
        market.component_manifest,
        RequestedResultGrade.DECISION_GRADE,
        (),
        True,
    )
    simulation_registration = SimulationProfileRegistration(
        _SIMULATION_KEY,
        1,
        simulation.profile_digest,
        simulation,
        _ENGINE_KIND,
        (StrategyFamily.PRECOMPUTED_TARGET,),
        (TARGET_STREAM_CAPABILITY,),
        simulation.component_manifest,
        RequestedResultGrade.DECISION_GRADE,
        (),
        True,
    )
    account_registration = ExecutionAccountProfileRegistration(
        _ACCOUNT_KEY,
        1,
        account.profile_digest,
        account,
        _ACCOUNT_ID,
        "xshe",
        "equity",
        "cash_only",
        (_CNY,),
        RequestedResultGrade.DECISION_GRADE,
        (),
        True,
    )
    registrations = (
        market_registration,
        simulation_registration,
        account_registration,
    )
    build = _build_manifest(target.target_stream_digest, registrations)
    nonclaims = (
        "does_not_authorize_deployment_live_or_operations",
        "does_not_mint_g12m_qualification_or_result_grade",
        "does_not_claim_historical_provider_availability_or_future_revision_finality",
        "does_not_claim_provider_completeness",
        "does_not_claim_strict_g12h_official_legal_tax_or_compliance_closure",
        "does_not_claim_historical_listing_membership_or_corporate_action_lifecycle",
        "does_not_claim_retained_wheel_bytes",
        "provider_evidence_does_not_set_profile_or_build_grade",
    )
    return _AuthorityValues(
        case,
        sources,
        proof,
        target,
        applicability,
        risk,
        market_registration,
        simulation_registration,
        account_registration,
        build,
        nonclaims,
    )


def _identity_body_from_values(values: _AuthorityValues) -> dict[str, object]:
    return {
        "type": "cn_a_share_fixed_singleton_no_trade_profile_build_authority_v1",
        "schema_version": 1,
        "authority_id": _AUTHORITY_ID,
        "case": values.case,
        "source_identities": values.source_identities,
        "generic_proof_acceptance": values.generic_proof_acceptance,
        "target_commitment": values.target_commitment,
        "component_applicability": values.component_applicability,
        "account_risk_policy": values.account_risk_policy,
        "profile_registrations": (
            values.market_registration,
            values.simulation_registration,
            values.execution_account_registration,
        ),
        "build_manifest": values.build_manifest,
        "nonclaims": values.nonclaims,
        "limitations": (),
        "decision_grade_eligible": True,
        "deployment_authorized": False,
        "supersedes_authority_hash": None,
    }


def create_cn_a_share_fixed_singleton_no_trade_authority_v1() -> (
    CnAShareFixedSingletonNoTradeAuthorityV1
):
    values = _make_values()
    return CnAShareFixedSingletonNoTradeAuthorityV1(
        values.case,
        values.source_identities,
        values.generic_proof_acceptance,
        values.target_commitment,
        values.component_applicability,
        values.account_risk_policy,
        values.market_registration,
        values.simulation_registration,
        values.execution_account_registration,
        values.build_manifest,
        values.nonclaims,
        (),
        True,
        False,
        None,
        canonical_sha256(_identity_body_from_values(values)),
    )


def validate_cn_a_share_fixed_singleton_no_trade_target_stream_v1(
    target_stream: PrecomputedTargetStream,
) -> None:
    CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1.validate_target_stream(
        target_stream
    )


CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1 = (
    create_cn_a_share_fixed_singleton_no_trade_authority_v1()
)


__all__ = [
    "CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V1",
    "CnAShareFixedSingletonNoTradeAuthorityV1",
    "create_cn_a_share_fixed_singleton_no_trade_authority_v1",
    "validate_cn_a_share_fixed_singleton_no_trade_target_stream_v1",
]
