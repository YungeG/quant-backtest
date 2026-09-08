"""Runnable successor authority for the accepted China A-share no-trade case."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from crypto_quant_domain import TimeInForce, canonical_bytes, canonical_sha256
from crypto_quant_market_data import MarketBundleCapability
from crypto_quant_trading import AccountRiskPolicy, ProfileComponentRef, ProfilePortType

from .cn_a_share_fixed_singleton_no_trade_profile_v1 import (
    CnAShareFixedSingletonNoTradeAuthorityV1,
    _FixedCase,
    _GenericProofAcceptance,
    _ProviderEvidenceIdentity,
    _TargetCommitment,
    create_cn_a_share_fixed_singleton_no_trade_authority_v1,
    validate_cn_a_share_fixed_singleton_no_trade_target_stream_v1,
)
from .execution import NextEligibleBarOpenModel, NoEligibleBarAction
from .financial_dispatch import (
    FinancialDispatcherSpec,
    default_cash_financial_dispatcher_spec,
)
from .ports import SimulationComponentRef, SimulationPortSpec, SimulationPortType
from .resolution import (
    ArtifactInstallMode,
    BuildArtifactManifest,
    BuildArtifactRef,
    BuildArtifactRole,
    ExecutionAccountProfileRegistration,
    MarketSemanticsProfileRegistration,
    RequestedResultGrade,
    SimulationProfileRegistration,
    SourceTreeState,
    StrategyFamily,
)
from .run_end import MarkToMarketCloseoutPolicy
from .target_stream import TARGET_STREAM_CAPABILITY, PrecomputedTargetStream

_AUTHORITY_ID = "cn-a-share-fixed-singleton-no-trade-profile-build-authority-v2"
_MARKET_KEY = "equity.cn_a_share.fixed-singleton-no-trade.market.v2"
_SIMULATION_KEY = "backtest.cn_a_share.fixed-singleton-no-trade.simulation.v2"
_BUILD_KEY = "cn-a-share-fixed-singleton-no-trade-build-v2"
_ENGINE_KIND = "fixed_singleton_no_trade"
_PREDECESSOR_CANDIDATE_COMMIT = "c52c8913ef680b34c1edecf46b1892b268e013e0"
_PREDECESSOR_GOVERNANCE_COMMIT = "0c0a7df5b1f4b6d83928fec0b19d60696ff20d72"
_PREDECESSOR_AUTHORITY_HASH = (
    "sha256:a0f0fb905dbc34d877c39130bf615f2f5d725b97aa618ed97bffdd1a12bce654"
)
_PREDECESSOR_DECISION_FILE_HASH = (
    "sha256:0a22eb7368eb0838d772efbcd6fc08cf48d333783d3ae881a12ba304f25ae1ca"
)
_PREDECESSOR_TARGET_HASH = (
    "sha256:8e4bdddbd91e1bafd65363e133d382673df88e4dc4061d1f0dd776a42afc6cee"
)
_PREDECESSOR_BUILD_HASH = (
    "sha256:a6a73cb72a9ad4cf98bca789c19a6a261f00dc4b1e538478a0ca9674137ab516"
)
_DAILY_CAPABILITY = MarketBundleCapability("tushare_cn_a_share.daily-publications", 1)
_BAR_OPEN_CAPABILITY = MarketBundleCapability("bar_open", 1)
_EXECUTION_COMPONENT_HASH = (
    "sha256:d69d6d96c9081f730db6ff8cdd02431d4babdef2e3967f0094971e73aedf30fe"
)


class _ApplicabilityDisposition(str, Enum):
    ACTIVE_FIXED_CASE_AUTHORITY = "active_fixed_case_authority"
    INERT_BY_ZERO_TARGET_AND_ZERO_ORDER_CAPACITY = (
        "inert_by_zero_target_and_zero_order_capacity"
    )
    INERT_BY_ZERO_ORDER_CAPACITY = "inert_by_zero_order_capacity"
    INERT_BY_ZERO_EXPOSURE = "inert_by_zero_exposure"


@dataclass(frozen=True, slots=True)
class _PredecessorBinding:
    candidate_commit: str
    governance_commit: str
    authority_hash: str
    decision_file_hash: str
    target_stream_digest: str
    build_manifest_hash: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_fixed_singleton_authority_predecessor_v1",
            **{name: getattr(self, name) for name in self.__dataclass_fields__},
        }


@dataclass(frozen=True, slots=True)
class _ComponentApplicability:
    component_ref: ProfileComponentRef | SimulationComponentRef
    disposition: _ApplicabilityDisposition
    predecessor_component_ref: ProfileComponentRef | SimulationComponentRef | None
    justification: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "fixed_case_component_applicability_v2",
            "component_ref": self.component_ref,
            "disposition": self.disposition.value,
            "predecessor_component_ref": self.predecessor_component_ref,
            "justification": self.justification,
        }


@dataclass(frozen=True, slots=True)
class _FixedMarketProfileV2:
    semantic_source_hash: str
    applicability_hash: str
    financial_dispatcher_spec: FinancialDispatcherSpec
    component_manifest: tuple[ProfileComponentRef, ...]
    profile_key: str = _MARKET_KEY
    profile_version: int = 2

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_fixed_singleton_market_profile_v2",
            **{name: getattr(self, name) for name in self.__dataclass_fields__},
        }


def _execution_model_body(model: NextEligibleBarOpenModel) -> dict[str, object]:
    if type(model) is not NextEligibleBarOpenModel:
        raise TypeError("execution_model must be exact NextEligibleBarOpenModel")
    return {
        "type": "next_eligible_bar_open_model",
        "component_ref": model.component_ref,
        "applicability": model.applicability,
        "spec": model.spec(),
    }


def _closeout_policy_body(policy: MarkToMarketCloseoutPolicy) -> dict[str, object]:
    if type(policy) is not MarkToMarketCloseoutPolicy:
        raise TypeError("closeout_policy must be exact MarkToMarketCloseoutPolicy")
    return {
        "type": "mark_to_market_closeout_policy",
        "component_ref": policy.component_ref,
        "spec": policy.spec(),
    }


@dataclass(frozen=True, slots=True)
class _FixedSimulationProfileV2:
    semantic_source_hash: str
    applicability_hash: str
    target_stream_digest: str
    execution_model: NextEligibleBarOpenModel
    execution_spec: SimulationPortSpec
    closeout_policy: MarkToMarketCloseoutPolicy
    closeout_spec: SimulationPortSpec
    component_manifest: tuple[SimulationComponentRef, ...]
    profile_key: str = _SIMULATION_KEY
    profile_version: int = 2

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_fixed_singleton_simulation_profile_v2",
            "semantic_source_hash": self.semantic_source_hash,
            "applicability_hash": self.applicability_hash,
            "target_stream_digest": self.target_stream_digest,
            "execution_model": _execution_model_body(self.execution_model),
            "execution_spec": self.execution_spec,
            "closeout_policy": _closeout_policy_body(self.closeout_policy),
            "closeout_spec": self.closeout_spec,
            "component_manifest": self.component_manifest,
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
        }


@dataclass(frozen=True, slots=True)
class _AuthorityValues:
    predecessor: _PredecessorBinding
    case: _FixedCase
    source_identities: tuple[_ProviderEvidenceIdentity, ...]
    generic_proof_acceptance: _GenericProofAcceptance
    target_commitment: _TargetCommitment
    component_applicability: tuple[_ComponentApplicability, ...]
    account_risk_policy: AccountRiskPolicy
    execution_model: NextEligibleBarOpenModel
    execution_spec: SimulationPortSpec
    closeout_policy: MarkToMarketCloseoutPolicy
    closeout_spec: SimulationPortSpec
    financial_dispatcher_spec: FinancialDispatcherSpec
    market_registration: MarketSemanticsProfileRegistration
    simulation_registration: SimulationProfileRegistration
    execution_account_registration: ExecutionAccountProfileRegistration
    build_manifest: BuildArtifactManifest
    nonclaims: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _CnAShareFixedSingletonNoTradeAuthorityV2:
    predecessor: _PredecessorBinding
    case: _FixedCase
    source_identities: tuple[_ProviderEvidenceIdentity, ...]
    generic_proof_acceptance: _GenericProofAcceptance
    target_commitment: _TargetCommitment
    component_applicability: tuple[_ComponentApplicability, ...]
    account_risk_policy: AccountRiskPolicy
    execution_model: NextEligibleBarOpenModel
    execution_spec: SimulationPortSpec
    closeout_policy: MarkToMarketCloseoutPolicy
    closeout_spec: SimulationPortSpec
    financial_dispatcher_spec: FinancialDispatcherSpec
    market_registration: MarketSemanticsProfileRegistration
    simulation_registration: SimulationProfileRegistration
    execution_account_registration: ExecutionAccountProfileRegistration
    build_manifest: BuildArtifactManifest
    nonclaims: tuple[str, ...]
    limitations: tuple[str, ...]
    decision_grade_eligible: bool
    deployment_authorized: bool
    supersedes_authority_hash: str
    authority_hash: str
    schema_version: int = 2
    authority_id: str = _AUTHORITY_ID

    def __post_init__(self) -> None:
        self._validate_self()

    def validate_target_stream(self, target_stream: PrecomputedTargetStream) -> None:
        self._validate_self()
        validate_cn_a_share_fixed_singleton_no_trade_target_stream_v1(target_stream)
        if target_stream != self.target_commitment.stream or canonical_bytes(
            target_stream
        ) != canonical_bytes(self.target_commitment.stream):
            raise ValueError("target_stream does not match immutable v1 commitment")

    def _identity_body(self) -> dict[str, object]:
        return {
            "type": "cn_a_share_fixed_singleton_no_trade_profile_build_authority_v2",
            "schema_version": self.schema_version,
            "authority_id": self.authority_id,
            "predecessor": self.predecessor,
            "case": self.case,
            "source_identities": self.source_identities,
            "generic_proof_acceptance": self.generic_proof_acceptance,
            "target_commitment": self.target_commitment,
            "component_applicability": self.component_applicability,
            "actual_runtime_components": {
                "execution_model": _execution_model_body(self.execution_model),
                "execution_spec": self.execution_spec,
                "closeout_policy": _closeout_policy_body(self.closeout_policy),
                "closeout_spec": self.closeout_spec,
                "financial_dispatcher_spec": self.financial_dispatcher_spec,
            },
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
        if type(self) is not _CnAShareFixedSingletonNoTradeAuthorityV2:
            raise TypeError("authority must be exact authority type")
        expected = _make_values()
        expected_fields = (
            expected.predecessor,
            expected.case,
            expected.source_identities,
            expected.generic_proof_acceptance,
            expected.target_commitment,
            expected.component_applicability,
            expected.account_risk_policy,
            expected.execution_model,
            expected.execution_spec,
            expected.closeout_policy,
            expected.closeout_spec,
            expected.financial_dispatcher_spec,
            expected.market_registration,
            expected.simulation_registration,
            expected.execution_account_registration,
            expected.build_manifest,
            expected.nonclaims,
            (),
            True,
            False,
            _PREDECESSOR_AUTHORITY_HASH,
            2,
            _AUTHORITY_ID,
        )
        actual_fields = (
            self.predecessor,
            self.case,
            self.source_identities,
            self.generic_proof_acceptance,
            self.target_commitment,
            self.component_applicability,
            self.account_risk_policy,
            self.execution_model,
            self.execution_spec,
            self.closeout_policy,
            self.closeout_spec,
            self.financial_dispatcher_spec,
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
        expected_body = _identity_body_from_values(expected)
        if self.authority_hash != canonical_sha256(expected_body):
            raise ValueError("authority_hash does not match exact reconstruction")
        if canonical_bytes(self._identity_body()) != canonical_bytes(expected_body):
            raise ValueError(
                "authority canonical body does not match exact reconstruction"
            )

    def to_canonical_dict(self) -> dict[str, object]:
        self._validate_self()
        return {**self._identity_body(), "authority_hash": self.authority_hash}


def _predecessor(
    authority: CnAShareFixedSingletonNoTradeAuthorityV1,
) -> _PredecessorBinding:
    if authority.authority_hash != _PREDECESSOR_AUTHORITY_HASH:
        raise ValueError("accepted v1 authority hash mismatch")
    if authority.target_commitment.target_stream_digest != _PREDECESSOR_TARGET_HASH:
        raise ValueError("accepted v1 target digest mismatch")
    if authority.build_manifest.manifest_hash != _PREDECESSOR_BUILD_HASH:
        raise ValueError("accepted v1 Build hash mismatch")
    return _PredecessorBinding(
        _PREDECESSOR_CANDIDATE_COMMIT,
        _PREDECESSOR_GOVERNANCE_COMMIT,
        _PREDECESSOR_AUTHORITY_HASH,
        _PREDECESSOR_DECISION_FILE_HASH,
        _PREDECESSOR_TARGET_HASH,
        _PREDECESSOR_BUILD_HASH,
    )


def _execution_model() -> NextEligibleBarOpenModel:
    model = NextEligibleBarOpenModel.create(
        actions=(
            (TimeInForce.DAY, NoEligibleBarAction.EXPIRE),
            (TimeInForce.GTC, NoEligibleBarAction.KEEP_ACTIVE),
            (TimeInForce.IOC, NoEligibleBarAction.EXPIRE),
            (TimeInForce.FOK, NoEligibleBarAction.EXPIRE),
            (TimeInForce.GTX, NoEligibleBarAction.KEEP_ACTIVE),
        )
    )
    if model.component_ref.component_digest != _EXECUTION_COMPONENT_HASH:
        raise ValueError("exact NextEligibleBarOpenModel digest mismatch")
    if tuple(
        (value.capability_key, value.minimum_version)
        for value in model.spec().required_capabilities
    ) != (("bar_open", 1),):
        raise ValueError("exact NextEligibleBarOpenModel must require bar_open@1")
    return model


def _semantic_source_hash(
    predecessor: _PredecessorBinding,
    authority: CnAShareFixedSingletonNoTradeAuthorityV1,
    execution_model: NextEligibleBarOpenModel,
    closeout_policy: MarkToMarketCloseoutPolicy,
    dispatcher: FinancialDispatcherSpec,
) -> str:
    return canonical_sha256(
        {
            "type": "cn_a_share_fixed_singleton_profile_semantic_sources_v2",
            "predecessor": predecessor,
            "case": authority.case,
            "source_identities": authority.source_identities,
            "generic_proof_acceptance": authority.generic_proof_acceptance,
            "target_stream_digest": authority.target_commitment.target_stream_digest,
            "execution_model": _execution_model_body(execution_model),
            "execution_spec": execution_model.spec(),
            "closeout_policy": _closeout_policy_body(closeout_policy),
            "closeout_spec": closeout_policy.spec(),
            "financial_dispatcher_spec": dispatcher,
        }
    )


def _component_values(
    authority: CnAShareFixedSingletonNoTradeAuthorityV1,
    execution_model: NextEligibleBarOpenModel,
    closeout_policy: MarkToMarketCloseoutPolicy,
    dispatcher: FinancialDispatcherSpec,
) -> tuple[
    tuple[ProfileComponentRef, ...],
    tuple[SimulationComponentRef, ...],
    tuple[_ComponentApplicability, ...],
]:
    old_profile = {
        value.port_type: value
        for value in authority.market_registration.component_manifest
    }
    old_simulation = {
        value.port_type: value
        for value in authority.simulation_registration.component_manifest
    }
    actual_profile = {
        dispatcher.position_accounting_component.port_type: dispatcher.position_accounting_component,
        dispatcher.financing_component.port_type: dispatcher.financing_component,
        dispatcher.margin_component.port_type: dispatcher.margin_component,
    }
    actual_simulation = {
        execution_model.component_ref.port_type: execution_model.component_ref,
        closeout_policy.component_ref.port_type: closeout_policy.component_ref,
        dispatcher.liquidation_audit_component.port_type: dispatcher.liquidation_audit_component,
    }
    profile = tuple(
        sorted(
            (actual_profile.get(port, old_profile[port]) for port in ProfilePortType),
            key=lambda value: value.port_type.value,
        )
    )
    simulation = tuple(
        sorted(
            (
                actual_simulation.get(port, old_simulation[port])
                for port in SimulationPortType
            ),
            key=lambda value: value.port_type.value,
        )
    )
    actual_ports = set(actual_profile) | set(actual_simulation)
    applicability: list[_ComponentApplicability] = []
    for ref in (*profile, *simulation):
        port = ref.port_type
        predecessor_ref = (
            old_profile[port]
            if port in actual_profile
            else old_simulation[port]
            if port in actual_simulation
            else None
        )
        if port in {
            SimulationPortType.EXECUTION_MODEL,
            SimulationPortType.SLIPPAGE_MODEL,
            SimulationPortType.LATENCY_MODEL,
            SimulationPortType.LIQUIDITY_MODEL,
        }:
            disposition = (
                _ApplicabilityDisposition.INERT_BY_ZERO_TARGET_AND_ZERO_ORDER_CAPACITY
            )
        elif port in {
            ProfilePortType.ORDER_RULE_MODEL,
            ProfilePortType.FEE_ASSESSMENT_POLICY,
            ProfilePortType.TAX_POLICY,
            ProfilePortType.SETTLEMENT_MODEL,
            ProfilePortType.POSITION_ACCOUNTING_MODEL,
        }:
            disposition = _ApplicabilityDisposition.INERT_BY_ZERO_ORDER_CAPACITY
        elif port in {
            ProfilePortType.FINANCING_MODEL,
            ProfilePortType.MARGIN_MODEL,
            ProfilePortType.LIQUIDATION_RULES,
            ProfilePortType.CORPORATE_ACTION_MODEL,
            ProfilePortType.CURRENCY_VALUATION_POLICY,
            SimulationPortType.LIQUIDATION_AUDIT_MODEL,
            SimulationPortType.CLOSEOUT_POLICY,
        }:
            disposition = _ApplicabilityDisposition.INERT_BY_ZERO_EXPOSURE
        else:
            disposition = _ApplicabilityDisposition.ACTIVE_FIXED_CASE_AUTHORITY
        if port in actual_ports:
            reason = (
                "replaces the v1 semantic-generated ref with the exact Runtime component "
                f"required by no-trade composition; fixed-case disposition remains {disposition.value}"
            )
        elif disposition is _ApplicabilityDisposition.ACTIVE_FIXED_CASE_AUTHORITY:
            reason = (
                "unchanged exact v1 fixed xshe:000001 July-2026 component authority"
            )
        else:
            reason = f"unchanged exact v1 inert component ref; disposition remains {disposition.value}"
        applicability.append(
            _ComponentApplicability(ref, disposition, predecessor_ref, reason)
        )
    return (
        profile,
        simulation,
        tuple(
            sorted(
                applicability,
                key=lambda value: (
                    value.component_ref.port_type.value,
                    type(value.component_ref).__name__,
                ),
            )
        ),
    )


def _build_manifest(
    predecessor: CnAShareFixedSingletonNoTradeAuthorityV1,
    market: MarketSemanticsProfileRegistration,
    simulation: SimulationProfileRegistration,
) -> BuildArtifactManifest:
    retained = tuple(
        artifact
        for artifact in predecessor.build_manifest.artifacts
        if artifact.role is not BuildArtifactRole.PROFILE_COMPONENT
        or artifact.artifact_key
        == predecessor.execution_account_registration.profile_key
    )
    replacements = (
        BuildArtifactRef(
            BuildArtifactRole.PROFILE_COMPONENT,
            market.profile_key,
            str(market.profile_version),
            ArtifactInstallMode.WHEEL,
            SourceTreeState.CLEAN,
            market.profile_digest,
            None,
        ),
        BuildArtifactRef(
            BuildArtifactRole.PROFILE_COMPONENT,
            simulation.profile_key,
            str(simulation.profile_version),
            ArtifactInstallMode.WHEEL,
            SourceTreeState.CLEAN,
            simulation.profile_digest,
            None,
        ),
    )
    return BuildArtifactManifest(
        1,
        _BUILD_KEY,
        (*retained, *replacements),
        predecessor.build_manifest.dependency_lock_hash,
        predecessor.build_manifest.runtime_libraries,
        predecessor.build_manifest.container_image_digest,
        predecessor.build_manifest.provenance,
    )


def _make_values() -> _AuthorityValues:
    v1 = create_cn_a_share_fixed_singleton_no_trade_authority_v1()
    predecessor = _predecessor(v1)
    execution_model = _execution_model()
    execution_spec = execution_model.spec()
    closeout_policy = MarkToMarketCloseoutPolicy()
    closeout_spec = closeout_policy.spec()
    dispatcher = default_cash_financial_dispatcher_spec()
    profile_components, simulation_components, applicability = _component_values(
        v1, execution_model, closeout_policy, dispatcher
    )
    semantic_source_hash = _semantic_source_hash(
        predecessor, v1, execution_model, closeout_policy, dispatcher
    )
    applicability_hash = canonical_sha256(applicability)
    market_profile = _FixedMarketProfileV2(
        semantic_source_hash,
        applicability_hash,
        dispatcher,
        profile_components,
    )
    simulation_profile = _FixedSimulationProfileV2(
        semantic_source_hash,
        applicability_hash,
        v1.target_commitment.target_stream_digest,
        execution_model,
        execution_spec,
        closeout_policy,
        closeout_spec,
        simulation_components,
    )
    market = MarketSemanticsProfileRegistration(
        _MARKET_KEY,
        2,
        market_profile.profile_digest,
        market_profile,
        "xshe",
        (_DAILY_CAPABILITY,),
        market_profile.component_manifest,
        RequestedResultGrade.DECISION_GRADE,
        (),
        True,
    )
    simulation = SimulationProfileRegistration(
        _SIMULATION_KEY,
        2,
        simulation_profile.profile_digest,
        simulation_profile,
        _ENGINE_KIND,
        (StrategyFamily.PRECOMPUTED_TARGET,),
        (_BAR_OPEN_CAPABILITY, TARGET_STREAM_CAPABILITY),
        simulation_profile.component_manifest,
        RequestedResultGrade.DECISION_GRADE,
        (),
        True,
    )
    build = _build_manifest(v1, market, simulation)
    return _AuthorityValues(
        predecessor,
        v1.case,
        v1.source_identities,
        v1.generic_proof_acceptance,
        v1.target_commitment,
        applicability,
        v1.account_risk_policy,
        execution_model,
        execution_spec,
        closeout_policy,
        closeout_spec,
        dispatcher,
        market,
        simulation,
        v1.execution_account_registration,
        build,
        v1.nonclaims,
    )


def _identity_body_from_values(values: _AuthorityValues) -> dict[str, object]:
    return {
        "type": "cn_a_share_fixed_singleton_no_trade_profile_build_authority_v2",
        "schema_version": 2,
        "authority_id": _AUTHORITY_ID,
        "predecessor": values.predecessor,
        "case": values.case,
        "source_identities": values.source_identities,
        "generic_proof_acceptance": values.generic_proof_acceptance,
        "target_commitment": values.target_commitment,
        "component_applicability": values.component_applicability,
        "actual_runtime_components": {
            "execution_model": _execution_model_body(values.execution_model),
            "execution_spec": values.execution_spec,
            "closeout_policy": _closeout_policy_body(values.closeout_policy),
            "closeout_spec": values.closeout_spec,
            "financial_dispatcher_spec": values.financial_dispatcher_spec,
        },
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
        "supersedes_authority_hash": _PREDECESSOR_AUTHORITY_HASH,
    }


def create_cn_a_share_fixed_singleton_no_trade_authority_v2() -> (
    _CnAShareFixedSingletonNoTradeAuthorityV2
):
    values = _make_values()
    return _CnAShareFixedSingletonNoTradeAuthorityV2(
        values.predecessor,
        values.case,
        values.source_identities,
        values.generic_proof_acceptance,
        values.target_commitment,
        values.component_applicability,
        values.account_risk_policy,
        values.execution_model,
        values.execution_spec,
        values.closeout_policy,
        values.closeout_spec,
        values.financial_dispatcher_spec,
        values.market_registration,
        values.simulation_registration,
        values.execution_account_registration,
        values.build_manifest,
        values.nonclaims,
        (),
        True,
        False,
        _PREDECESSOR_AUTHORITY_HASH,
        canonical_sha256(_identity_body_from_values(values)),
    )


def validate_cn_a_share_fixed_singleton_no_trade_target_stream_v2(
    target_stream: PrecomputedTargetStream,
) -> None:
    validate_cn_a_share_fixed_singleton_no_trade_target_stream_v1(target_stream)


CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V2 = (
    create_cn_a_share_fixed_singleton_no_trade_authority_v2()
)


__all__ = [
    "CN_A_SHARE_FIXED_SINGLETON_NO_TRADE_AUTHORITY_V2",
    "create_cn_a_share_fixed_singleton_no_trade_authority_v2",
    "validate_cn_a_share_fixed_singleton_no_trade_target_stream_v2",
]
