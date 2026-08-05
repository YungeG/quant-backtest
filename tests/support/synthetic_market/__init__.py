"""Development-only synthetic cash profile and fixed offline factories."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import ClassVar
import unicodedata

from crypto_quant_backtest import (
    DeterministicBpsSlippageModel,
    DeterministicTimeline,
    MarkToMarketCloseoutPolicy,
    NextEligibleBarOpenModel,
    PrecomputedTargetStream,
    ResolvedExecutionCase,
    SimulationComponentRef,
    SimulationPortOutcome,
    SimulationPortSpec,
    SimulationPortType,
)
from crypto_quant_domain import (
    ProfileComponentFailure,
    ProfileComponentFailureCode,
    canonical_sha256,
)
from crypto_quant_market_data import InMemoryMarketBundleReader, InputValidationFailure
from crypto_quant_trading import (
    ProfileComponentRef,
    ProfilePortOutcome,
    ProfilePortType,
)
from tests.runtime.engine import _fixtures as engine_fixtures


SYNTHETIC_PROFILE_KEY = "synthetic.cash.development.v1"
SYNTHETIC_PROFILE_LIMITATION = "synthetic_market_profile"


def _text(name: str, value: object) -> str:
    if type(value) is not str:
        raise TypeError(f"{name} must be str")
    if (
        not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{name} must be nonempty canonical text")
    return value


@dataclass(frozen=True, slots=True)
class SyntheticPortRequest:
    """Canonical request used to prove every development-only port is callable."""

    operation_key: str
    subject_key: str

    def __post_init__(self) -> None:
        _text("operation_key", self.operation_key)
        _text("subject_key", self.subject_key)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_port_request",
            "operation_key": self.operation_key,
            "subject_key": self.subject_key,
        }


@dataclass(frozen=True, slots=True)
class SyntheticPortDecision:
    """Explicit fixed result; never an implicit no-op/default."""

    port_key: str
    operation_key: str
    decision_key: str
    limitation: str

    def __post_init__(self) -> None:
        _text("port_key", self.port_key)
        _text("operation_key", self.operation_key)
        _text("decision_key", self.decision_key)
        _text("limitation", self.limitation)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_port_decision",
            "port_key": self.port_key,
            "operation_key": self.operation_key,
            "decision_key": self.decision_key,
            "limitation": self.limitation,
        }


@dataclass(frozen=True, slots=True)
class SyntheticSimulationApplicability:
    port_type: SimulationPortType
    limitation: str = SYNTHETIC_PROFILE_LIMITATION

    def __post_init__(self) -> None:
        if not isinstance(self.port_type, SimulationPortType):
            raise TypeError("port_type must be SimulationPortType")
        _text("limitation", self.limitation)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_simulation_applicability",
            "port_type": self.port_type.value,
            "limitation": self.limitation,
        }


@dataclass(frozen=True, slots=True)
class _SyntheticKernelComponent:
    component_ref: ProfileComponentRef

    @classmethod
    def create(cls, port_type: ProfilePortType) -> _SyntheticKernelComponent:
        config = {
            "type": "synthetic_kernel_component_config",
            "profile_key": SYNTHETIC_PROFILE_KEY,
            "port_type": port_type.value,
            "decision_key": "fixed_offline_fixture_semantics",
            "limitation": SYNTHETIC_PROFILE_LIMITATION,
        }
        return cls(
            ProfileComponentRef(
                port_type=port_type,
                component_key=f"{SYNTHETIC_PROFILE_KEY}.{port_type.value}",
                component_version=1,
                component_digest=canonical_sha256(config),
            )
        )

    def _resolve(
        self,
        expected_port: ProfilePortType,
        operation_key: str,
        request: SyntheticPortRequest,
    ) -> ProfilePortOutcome[SyntheticPortDecision, ProfileComponentFailure]:
        if not isinstance(request, SyntheticPortRequest):
            raise TypeError("request must be SyntheticPortRequest")
        if self.component_ref.port_type is not expected_port:
            return ProfilePortOutcome.for_failure(
                self.component_ref,
                request,
                ProfileComponentFailure(
                    ProfileComponentFailureCode.COMPONENT_INCOMPATIBLE,
                    expected_port.value,
                ),
            )
        return ProfilePortOutcome.for_result(
            self.component_ref,
            request,
            SyntheticPortDecision(
                port_key=expected_port.value,
                operation_key=operation_key,
                decision_key="fixed_offline_fixture_semantics",
                limitation=SYNTHETIC_PROFILE_LIMITATION,
            ),
        )

    def resolve_session(self, request: SyntheticPortRequest, /):
        return self._resolve(ProfilePortType.SESSION_MODEL, "resolve_session", request)

    def resolve_instrument(self, request: SyntheticPortRequest, /):
        return self._resolve(
            ProfilePortType.INSTRUMENT_MODEL, "resolve_instrument", request
        )

    def resolve_order_rules(self, request: SyntheticPortRequest, /):
        return self._resolve(
            ProfilePortType.ORDER_RULE_MODEL, "resolve_order_rules", request
        )

    def assess_fees(self, request: SyntheticPortRequest, /):
        return self._resolve(
            ProfilePortType.FEE_ASSESSMENT_POLICY, "assess_fees", request
        )

    def assess_taxes(self, request: SyntheticPortRequest, /):
        return self._resolve(ProfilePortType.TAX_POLICY, "assess_taxes", request)

    def resolve_settlement(self, request: SyntheticPortRequest, /):
        return self._resolve(
            ProfilePortType.SETTLEMENT_MODEL, "resolve_settlement", request
        )

    def translate_position_fact(self, request: SyntheticPortRequest, /):
        return self._resolve(
            ProfilePortType.POSITION_ACCOUNTING_MODEL,
            "translate_position_fact",
            request,
        )

    def assess_financing(self, request: SyntheticPortRequest, /):
        return self._resolve(
            ProfilePortType.FINANCING_MODEL, "assess_financing", request
        )

    def evaluate_margin(self, request: SyntheticPortRequest, /):
        return self._resolve(ProfilePortType.MARGIN_MODEL, "evaluate_margin", request)

    def evaluate_liquidation(self, request: SyntheticPortRequest, /):
        return self._resolve(
            ProfilePortType.LIQUIDATION_RULES, "evaluate_liquidation", request
        )

    def apply_corporate_action(self, request: SyntheticPortRequest, /):
        return self._resolve(
            ProfilePortType.CORPORATE_ACTION_MODEL,
            "apply_corporate_action",
            request,
        )

    def select_valuation_path(self, request: SyntheticPortRequest, /):
        return self._resolve(
            ProfilePortType.CURRENCY_VALUATION_POLICY,
            "select_valuation_path",
            request,
        )


@dataclass(frozen=True, slots=True)
class _SyntheticSimulationComponent:
    component_ref: SimulationComponentRef
    applicability: SyntheticSimulationApplicability

    @classmethod
    def create(
        cls, port_type: SimulationPortType
    ) -> _SyntheticSimulationComponent:
        applicability = SyntheticSimulationApplicability(port_type)
        config = {
            "type": "synthetic_simulation_component_config",
            "profile_key": SYNTHETIC_PROFILE_KEY,
            "applicability": applicability,
            "decision_key": "fixed_offline_fixture_semantics",
        }
        return cls(
            SimulationComponentRef(
                port_type=port_type,
                component_key=f"{SYNTHETIC_PROFILE_KEY}.{port_type.value}",
                component_version=1,
                component_digest=canonical_sha256(config),
            ),
            applicability,
        )

    def spec(self) -> SimulationPortSpec:
        return SimulationPortSpec(self.component_ref, (), self.applicability)

    def _resolve(
        self,
        expected_port: SimulationPortType,
        operation_key: str,
        request: SyntheticPortRequest,
    ) -> SimulationPortOutcome[SyntheticPortDecision, ProfileComponentFailure]:
        if not isinstance(request, SyntheticPortRequest):
            raise TypeError("request must be SyntheticPortRequest")
        if self.component_ref.port_type is not expected_port:
            return SimulationPortOutcome.for_failure(
                self.component_ref,
                request,
                ProfileComponentFailure(
                    ProfileComponentFailureCode.COMPONENT_INCOMPATIBLE,
                    expected_port.value,
                ),
            )
        return SimulationPortOutcome.for_result(
            self.component_ref,
            request,
            SyntheticPortDecision(
                port_key=expected_port.value,
                operation_key=operation_key,
                decision_key="fixed_offline_fixture_semantics",
                limitation=SYNTHETIC_PROFILE_LIMITATION,
            ),
        )

    def resolve_latency(self, request: SyntheticPortRequest, /):
        return self._resolve(
            SimulationPortType.LATENCY_MODEL, "resolve_latency", request
        )

    def evaluate_liquidity(self, request: SyntheticPortRequest, /):
        return self._resolve(
            SimulationPortType.LIQUIDITY_MODEL, "evaluate_liquidity", request
        )

    def audit_liquidation(self, request: SyntheticPortRequest, /):
        return self._resolve(
            SimulationPortType.LIQUIDATION_AUDIT_MODEL,
            "audit_liquidation",
            request,
        )


@dataclass(frozen=True, slots=True)
class SyntheticMarketSemanticsProfile:
    session_model: _SyntheticKernelComponent
    instrument_model: _SyntheticKernelComponent
    order_rule_model: _SyntheticKernelComponent
    fee_assessment_policy: _SyntheticKernelComponent
    tax_policy: _SyntheticKernelComponent
    settlement_model: _SyntheticKernelComponent
    position_accounting_model: _SyntheticKernelComponent
    financing_model: _SyntheticKernelComponent
    margin_model: _SyntheticKernelComponent
    liquidation_rules: _SyntheticKernelComponent
    corporate_action_model: _SyntheticKernelComponent
    currency_valuation_policy: _SyntheticKernelComponent

    @classmethod
    def _create(cls) -> SyntheticMarketSemanticsProfile:
        components = {
            port_type: _SyntheticKernelComponent.create(port_type)
            for port_type in ProfilePortType
        }
        return cls(
            session_model=components[ProfilePortType.SESSION_MODEL],
            instrument_model=components[ProfilePortType.INSTRUMENT_MODEL],
            order_rule_model=components[ProfilePortType.ORDER_RULE_MODEL],
            fee_assessment_policy=components[
                ProfilePortType.FEE_ASSESSMENT_POLICY
            ],
            tax_policy=components[ProfilePortType.TAX_POLICY],
            settlement_model=components[ProfilePortType.SETTLEMENT_MODEL],
            position_accounting_model=components[
                ProfilePortType.POSITION_ACCOUNTING_MODEL
            ],
            financing_model=components[ProfilePortType.FINANCING_MODEL],
            margin_model=components[ProfilePortType.MARGIN_MODEL],
            liquidation_rules=components[ProfilePortType.LIQUIDATION_RULES],
            corporate_action_model=components[
                ProfilePortType.CORPORATE_ACTION_MODEL
            ],
            currency_valuation_policy=components[
                ProfilePortType.CURRENCY_VALUATION_POLICY
            ],
        )

    @property
    def component_manifest(self) -> tuple[ProfileComponentRef, ...]:
        components = (
            self.session_model,
            self.instrument_model,
            self.order_rule_model,
            self.fee_assessment_policy,
            self.tax_policy,
            self.settlement_model,
            self.position_accounting_model,
            self.financing_model,
            self.margin_model,
            self.liquidation_rules,
            self.corporate_action_model,
            self.currency_valuation_policy,
        )
        return tuple(
            sorted(
                (component.component_ref for component in components),
                key=lambda ref: ref.port_type.value,
            )
        )

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_market_semantics_profile",
            "profile_key": f"{SYNTHETIC_PROFILE_KEY}.market",
            "profile_version": 1,
            "components": self.component_manifest,
            "limitation": SYNTHETIC_PROFILE_LIMITATION,
        }


@dataclass(frozen=True, slots=True)
class SyntheticSimulationProfile:
    execution_model: NextEligibleBarOpenModel
    slippage_model: DeterministicBpsSlippageModel
    latency_model: _SyntheticSimulationComponent
    liquidity_model: _SyntheticSimulationComponent
    liquidation_audit_model: _SyntheticSimulationComponent
    closeout_policy: MarkToMarketCloseoutPolicy

    @classmethod
    def _create(cls) -> SyntheticSimulationProfile:
        return cls(
            execution_model=engine_fixtures.execution_model(),
            slippage_model=engine_fixtures.slippage_model(),
            latency_model=_SyntheticSimulationComponent.create(
                SimulationPortType.LATENCY_MODEL
            ),
            liquidity_model=_SyntheticSimulationComponent.create(
                SimulationPortType.LIQUIDITY_MODEL
            ),
            liquidation_audit_model=_SyntheticSimulationComponent.create(
                SimulationPortType.LIQUIDATION_AUDIT_MODEL
            ),
            closeout_policy=MarkToMarketCloseoutPolicy(),
        )

    @property
    def component_manifest(self) -> tuple[SimulationComponentRef, ...]:
        refs = (
            self.execution_model.spec().component_ref,
            self.slippage_model.spec().component_ref,
            self.latency_model.spec().component_ref,
            self.liquidity_model.spec().component_ref,
            self.liquidation_audit_model.spec().component_ref,
            self.closeout_policy.spec().component_ref,
        )
        return tuple(sorted(refs, key=lambda ref: ref.port_type.value))

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_simulation_profile",
            "profile_key": f"{SYNTHETIC_PROFILE_KEY}.simulation",
            "profile_version": 1,
            "components": self.component_manifest,
            "component_specs": (
                self.execution_model.spec(),
                self.slippage_model.spec(),
                self.latency_model.spec(),
                self.liquidity_model.spec(),
                self.liquidation_audit_model.spec(),
                self.closeout_policy.spec(),
            ),
            "limitation": SYNTHETIC_PROFILE_LIMITATION,
        }


@dataclass(frozen=True, slots=True)
class SyntheticExecutionAccountProfile:
    account_id: str = engine_fixtures.ACCOUNT
    venue_id: str = engine_fixtures.VENUE.value
    account_type: str = "cash"
    margin_mode: str = "not_applicable"
    account_fee_schedule_key: str = "synthetic.cash.fee_schedule.development.v1"
    cost_basis_policy_key: str = "fifo.synthetic.development.v1"

    def __post_init__(self) -> None:
        for name in (
            "account_id",
            "venue_id",
            "account_type",
            "margin_mode",
            "account_fee_schedule_key",
            "cost_basis_policy_key",
        ):
            _text(name, getattr(self, name))

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_execution_account_profile",
            "profile_key": f"{SYNTHETIC_PROFILE_KEY}.account",
            "profile_version": 1,
            "account_id": self.account_id,
            "venue_id": self.venue_id,
            "account_type": self.account_type,
            "margin_mode": self.margin_mode,
            "account_fee_schedule_key": self.account_fee_schedule_key,
            "cost_basis_policy_key": self.cost_basis_policy_key,
            "limitation": SYNTHETIC_PROFILE_LIMITATION,
        }


@dataclass(frozen=True, slots=True)
class SyntheticCashDevelopmentProfile:
    market_semantics: SyntheticMarketSemanticsProfile
    simulation: SyntheticSimulationProfile
    execution_account: SyntheticExecutionAccountProfile
    profile_key: str = SYNTHETIC_PROFILE_KEY
    profile_version: int = 1
    grade: str = "development"
    limitations: tuple[str, ...] = (SYNTHETIC_PROFILE_LIMITATION,)
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if self.profile_key != SYNTHETIC_PROFILE_KEY:
            raise ValueError("profile_key must be the synthetic development profile")
        if self.profile_version != 1:
            raise ValueError("profile_version must be 1")
        if self.grade != "development":
            raise ValueError("synthetic profile grade must be development")
        if self.limitations != (SYNTHETIC_PROFILE_LIMITATION,):
            raise ValueError("synthetic profile limitation must be explicit")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("synthetic profile cannot authorize decision-grade/deployment")

    @classmethod
    def _create(cls) -> SyntheticCashDevelopmentProfile:
        return cls(
            market_semantics=SyntheticMarketSemanticsProfile._create(),
            simulation=SyntheticSimulationProfile._create(),
            execution_account=SyntheticExecutionAccountProfile(),
        )

    @property
    def profile_digest(self) -> str:
        return canonical_sha256(self)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_cash_development_profile",
            "profile_key": self.profile_key,
            "profile_version": self.profile_version,
            "grade": self.grade,
            "limitations": self.limitations,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
            "market_semantics": self.market_semantics,
            "simulation": self.simulation,
            "execution_account": self.execution_account,
        }


class SyntheticProfileLookupFailureCode(str, Enum):
    PROFILE_NOT_FOUND = "profile_not_found"
    DEVELOPMENT_PROFILE_NOT_ALLOWED = "development_profile_not_allowed"


@dataclass(frozen=True, slots=True)
class SyntheticProfileLookupFailure:
    code: SyntheticProfileLookupFailureCode
    profile_key: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, SyntheticProfileLookupFailureCode):
            raise TypeError("code must be SyntheticProfileLookupFailureCode")
        _text("profile_key", self.profile_key)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_profile_lookup_failure",
            "code": self.code.value,
            "profile_key": self.profile_key,
        }


@dataclass(frozen=True, slots=True)
class SyntheticProfileLookupResult:
    profile: SyntheticCashDevelopmentProfile | None
    failure: SyntheticProfileLookupFailure | None

    def __post_init__(self) -> None:
        if (self.profile is None) == (self.failure is None):
            raise ValueError("lookup requires exactly one profile or failure")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "synthetic_profile_lookup_result",
            "profile": self.profile,
            "failure": self.failure,
        }


@dataclass(frozen=True, slots=True)
class TestProfileRegistry:
    """Test-only registry; development profiles require explicit opt-in."""

    __test__: ClassVar[bool] = False
    allow_development_profiles: bool = False

    def __post_init__(self) -> None:
        if type(self.allow_development_profiles) is not bool:
            raise TypeError("allow_development_profiles must be bool")

    def lookup(self, profile_key: str) -> SyntheticProfileLookupResult:
        _text("profile_key", profile_key)
        if profile_key != SYNTHETIC_PROFILE_KEY:
            return SyntheticProfileLookupResult(
                profile=None,
                failure=SyntheticProfileLookupFailure(
                    SyntheticProfileLookupFailureCode.PROFILE_NOT_FOUND,
                    profile_key,
                ),
            )
        if not self.allow_development_profiles:
            return SyntheticProfileLookupResult(
                profile=None,
                failure=SyntheticProfileLookupFailure(
                    SyntheticProfileLookupFailureCode.DEVELOPMENT_PROFILE_NOT_ALLOWED,
                    profile_key,
                ),
            )
        return SyntheticProfileLookupResult(
            profile=SyntheticCashDevelopmentProfile._create(),
            failure=None,
        )


def _require_profile(
    profile: SyntheticCashDevelopmentProfile,
) -> SyntheticCashDevelopmentProfile:
    if not isinstance(profile, SyntheticCashDevelopmentProfile):
        raise TypeError("profile must be SyntheticCashDevelopmentProfile")
    if (
        profile.profile_key != SYNTHETIC_PROFILE_KEY
        or profile.grade != "development"
        or profile.decision_grade_eligible
        or profile.deployment_authorized
    ):
        raise ValueError("profile is not the authorized synthetic development profile")
    return profile


def build_synthetic_bundle(
    profile: SyntheticCashDevelopmentProfile,
) -> InMemoryMarketBundleReader:
    _require_profile(profile)
    return engine_fixtures.reader()


def build_synthetic_target_stream(
    profile: SyntheticCashDevelopmentProfile,
) -> PrecomputedTargetStream:
    _require_profile(profile)
    return PrecomputedTargetStream("targets", (engine_fixtures.target_event(),))


def build_synthetic_execution_case(
    profile: SyntheticCashDevelopmentProfile,
    *,
    timeline_batch_size: int,
) -> ResolvedExecutionCase:
    resolved = _require_profile(profile)
    base = engine_fixtures.execution_case(batch_size=timeline_batch_size)
    timeline = DeterministicTimeline.open(
        reader=build_synthetic_bundle(resolved),
        stream_keys=base.timeline.stream_keys,
        window=base.timeline.window,
    )
    if isinstance(timeline, InputValidationFailure):
        raise AssertionError("fixed synthetic bundle failed Timeline validation")
    bar_executions = tuple(
        replace(plan, slippage_model=resolved.simulation.slippage_model)
        for plan in base.bar_executions
    )
    return replace(
        base,
        case_key=f"{SYNTHETIC_PROFILE_KEY}.engine.cash.v1",
        timeline=timeline,
        target_stream=build_synthetic_target_stream(resolved),
        bar_executions=bar_executions,
        execution_model=resolved.simulation.execution_model,
        closeout_policy=resolved.simulation.closeout_policy,
    )


__all__ = [
    "SYNTHETIC_PROFILE_KEY",
    "SYNTHETIC_PROFILE_LIMITATION",
    "SyntheticCashDevelopmentProfile",
    "SyntheticExecutionAccountProfile",
    "SyntheticMarketSemanticsProfile",
    "SyntheticPortDecision",
    "SyntheticPortRequest",
    "SyntheticProfileLookupFailure",
    "SyntheticProfileLookupFailureCode",
    "SyntheticProfileLookupResult",
    "SyntheticSimulationProfile",
    "TestProfileRegistry",
    "build_synthetic_bundle",
    "build_synthetic_execution_case",
    "build_synthetic_target_stream",
]
