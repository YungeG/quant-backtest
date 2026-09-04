"""Generic market and account semantics ports shared by backtest and live runtimes."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
import re
from typing import Generic, Never, Protocol, TypeVar, runtime_checkable
import unicodedata

from crypto_quant_domain import canonical_sha256


_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


class ProfilePortType(Enum):
    """Stable identities for market/account semantics component seams."""

    SESSION_MODEL = "session_model"
    INSTRUMENT_MODEL = "instrument_model"
    ORDER_RULE_MODEL = "order_rule_model"
    FEE_ASSESSMENT_POLICY = "fee_assessment_policy"
    TAX_POLICY = "tax_policy"
    SETTLEMENT_MODEL = "settlement_model"
    POSITION_ACCOUNTING_MODEL = "position_accounting_model"
    FINANCING_MODEL = "financing_model"
    MARGIN_MODEL = "margin_model"
    LIQUIDATION_RULES = "liquidation_rules"
    CORPORATE_ACTION_MODEL = "corporate_action_model"
    CURRENCY_VALUATION_POLICY = "currency_valuation_policy"


@runtime_checkable
class ProfilePortContract(Protocol):
    """Canonical immutable request, result, or failure accepted by a profile port."""

    @abstractmethod
    def to_canonical_dict(self) -> dict[str, object]:
        raise TypeError("ProfilePortContract has no implementation")


@dataclass(frozen=True)
class ProfileComponentRef:
    """Versioned content identity of one profile component implementation."""

    port_type: ProfilePortType
    component_key: str
    component_version: int
    component_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.port_type, ProfilePortType):
            raise TypeError("port_type must be ProfilePortType")
        if type(self.component_key) is not str:
            raise TypeError("component_key must be str")
        if (
            not self.component_key
            or self.component_key.strip() != self.component_key
            or unicodedata.normalize("NFC", self.component_key) != self.component_key
        ):
            raise ValueError("component_key must be non-empty canonical text")
        if type(self.component_version) is not int:
            raise TypeError("component_version must be int")
        if self.component_version <= 0:
            raise ValueError("component_version must be positive")
        if type(self.component_digest) is not str:
            raise TypeError("component_digest must be str")
        if _SHA256_PATTERN.fullmatch(self.component_digest) is None:
            raise ValueError("component_digest must be a canonical sha256 identity")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "profile_component_ref",
            "port_type": self.port_type.value,
            "component_key": self.component_key,
            "component_version": self.component_version,
            "component_digest": self.component_digest,
        }


_ResultT_co = TypeVar("_ResultT_co", bound=ProfilePortContract, covariant=True)
_FailureT_co = TypeVar("_FailureT_co", bound=ProfilePortContract, covariant=True)
_ResultValueT = TypeVar("_ResultValueT", bound=ProfilePortContract)
_FailureValueT = TypeVar("_FailureValueT", bound=ProfilePortContract)


@dataclass(frozen=True)
class ProfilePortOutcome(Generic[_ResultT_co, _FailureT_co]):
    """Deterministic exactly-one result/failure returned by every profile port."""

    component_ref: ProfileComponentRef
    input_hash: str
    result: _ResultT_co | None
    failure: _FailureT_co | None

    def __post_init__(self) -> None:
        if not isinstance(self.component_ref, ProfileComponentRef):
            raise TypeError("component_ref must be ProfileComponentRef")
        if type(self.input_hash) is not str or _SHA256_PATTERN.fullmatch(
            self.input_hash
        ) is None:
            raise ValueError("input_hash must be a canonical sha256 identity")
        if (self.result is None) == (self.failure is None):
            raise ValueError("ProfilePortOutcome requires exactly one result or failure")
        value = self.result if self.result is not None else self.failure
        if not isinstance(value, ProfilePortContract):
            raise TypeError("result/failure must satisfy ProfilePortContract")
        canonical_sha256(value)

    @classmethod
    def for_result(
        cls,
        component_ref: ProfileComponentRef,
        request: ProfilePortContract,
        result: _ResultValueT,
    ) -> ProfilePortOutcome[_ResultValueT, Never]:
        if not isinstance(request, ProfilePortContract):
            raise TypeError("request must satisfy ProfilePortContract")
        if not isinstance(result, ProfilePortContract):
            raise TypeError("result must satisfy ProfilePortContract")
        return ProfilePortOutcome(
            component_ref=component_ref,
            input_hash=canonical_sha256(request),
            result=result,
            failure=None,
        )

    @classmethod
    def for_failure(
        cls,
        component_ref: ProfileComponentRef,
        request: ProfilePortContract,
        failure: _FailureValueT,
    ) -> ProfilePortOutcome[Never, _FailureValueT]:
        if not isinstance(request, ProfilePortContract):
            raise TypeError("request must satisfy ProfilePortContract")
        if not isinstance(failure, ProfilePortContract):
            raise TypeError("failure must satisfy ProfilePortContract")
        return ProfilePortOutcome(
            component_ref=component_ref,
            input_hash=canonical_sha256(request),
            result=None,
            failure=failure,
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "profile_port_outcome",
            "component_ref": self.component_ref.to_canonical_dict(),
            "input_hash": self.input_hash,
            "result": (
                self.result.to_canonical_dict() if self.result is not None else None
            ),
            "failure": (
                self.failure.to_canonical_dict() if self.failure is not None else None
            ),
        }


_RequestT_contra = TypeVar(
    "_RequestT_contra", bound=ProfilePortContract, contravariant=True
)


class _ProfilePort(Protocol):
    @property
    @abstractmethod
    def component_ref(self) -> ProfileComponentRef:
        raise TypeError("Profile port has no component_ref implementation")


@runtime_checkable
class SessionModel(
    _ProfilePort, Protocol[_RequestT_contra, _ResultT_co, _FailureT_co]
):
    @abstractmethod
    def resolve_session(
        self, request: _RequestT_contra, /
    ) -> ProfilePortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("SessionModel has no implementation")


@runtime_checkable
class InstrumentModel(
    _ProfilePort, Protocol[_RequestT_contra, _ResultT_co, _FailureT_co]
):
    @abstractmethod
    def resolve_instrument(
        self, request: _RequestT_contra, /
    ) -> ProfilePortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("InstrumentModel has no implementation")


@runtime_checkable
class OrderRuleModel(
    _ProfilePort, Protocol[_RequestT_contra, _ResultT_co, _FailureT_co]
):
    @abstractmethod
    def resolve_order_rules(
        self, request: _RequestT_contra, /
    ) -> ProfilePortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("OrderRuleModel has no implementation")


@runtime_checkable
class FeeAssessmentPolicy(
    _ProfilePort, Protocol[_RequestT_contra, _ResultT_co, _FailureT_co]
):
    @abstractmethod
    def assess_fees(
        self, request: _RequestT_contra, /
    ) -> ProfilePortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("FeeAssessmentPolicy has no implementation")


@runtime_checkable
class TaxPolicy(
    _ProfilePort, Protocol[_RequestT_contra, _ResultT_co, _FailureT_co]
):
    @abstractmethod
    def assess_taxes(
        self, request: _RequestT_contra, /
    ) -> ProfilePortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("TaxPolicy has no implementation")


@runtime_checkable
class SettlementModel(
    _ProfilePort, Protocol[_RequestT_contra, _ResultT_co, _FailureT_co]
):
    @abstractmethod
    def resolve_settlement(
        self, request: _RequestT_contra, /
    ) -> ProfilePortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("SettlementModel has no implementation")


@runtime_checkable
class PositionAccountingModel(
    _ProfilePort, Protocol[_RequestT_contra, _ResultT_co, _FailureT_co]
):
    @abstractmethod
    def translate_position_fact(
        self, request: _RequestT_contra, /
    ) -> ProfilePortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("PositionAccountingModel has no implementation")


@runtime_checkable
class FinancingModel(
    _ProfilePort, Protocol[_RequestT_contra, _ResultT_co, _FailureT_co]
):
    @abstractmethod
    def assess_financing(
        self, request: _RequestT_contra, /
    ) -> ProfilePortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("FinancingModel has no implementation")


@runtime_checkable
class MarginModel(
    _ProfilePort, Protocol[_RequestT_contra, _ResultT_co, _FailureT_co]
):
    @abstractmethod
    def evaluate_margin(
        self, request: _RequestT_contra, /
    ) -> ProfilePortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("MarginModel has no implementation")


@runtime_checkable
class LiquidationRules(
    _ProfilePort, Protocol[_RequestT_contra, _ResultT_co, _FailureT_co]
):
    @abstractmethod
    def evaluate_liquidation(
        self, request: _RequestT_contra, /
    ) -> ProfilePortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("LiquidationRules has no implementation")


@runtime_checkable
class CorporateActionModel(
    _ProfilePort, Protocol[_RequestT_contra, _ResultT_co, _FailureT_co]
):
    @abstractmethod
    def apply_corporate_action(
        self, request: _RequestT_contra, /
    ) -> ProfilePortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("CorporateActionModel has no implementation")


@runtime_checkable
class CurrencyValuationPolicy(
    _ProfilePort, Protocol[_RequestT_contra, _ResultT_co, _FailureT_co]
):
    @abstractmethod
    def select_valuation_path(
        self, request: _RequestT_contra, /
    ) -> ProfilePortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("CurrencyValuationPolicy has no implementation")
