"""Backtest-only simulation profile ports."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
import re
from typing import Generic, Never, Protocol, TypeVar, runtime_checkable
import unicodedata

from crypto_quant_domain import canonical_sha256


_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


def _require_canonical_text(value: object, field_name: str) -> str:
    if type(value) is not str:
        raise TypeError(f"{field_name} must be str")
    if (
        not value
        or value.strip() != value
        or unicodedata.normalize("NFC", value) != value
    ):
        raise ValueError(f"{field_name} must be non-empty canonical text")
    return value


class SimulationPortType(Enum):
    """Stable identities for backtest-only simulation component seams."""

    EXECUTION_MODEL = "execution_model"
    SLIPPAGE_MODEL = "slippage_model"
    LATENCY_MODEL = "latency_model"
    LIQUIDITY_MODEL = "liquidity_model"
    LIQUIDATION_AUDIT_MODEL = "liquidation_audit_model"
    CLOSEOUT_POLICY = "closeout_policy"


@runtime_checkable
class SimulationPortContract(Protocol):
    """Canonical immutable request, result, failure, or applicability value."""

    @abstractmethod
    def to_canonical_dict(self) -> dict[str, object]:
        raise TypeError("SimulationPortContract has no implementation")


@dataclass(frozen=True)
class SimulationComponentRef:
    """Versioned content identity of one simulation component implementation."""

    port_type: SimulationPortType
    component_key: str
    component_version: int
    component_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.port_type, SimulationPortType):
            raise TypeError("port_type must be SimulationPortType")
        _require_canonical_text(self.component_key, "component_key")
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
            "type": "simulation_component_ref",
            "port_type": self.port_type.value,
            "component_key": self.component_key,
            "component_version": self.component_version,
            "component_digest": self.component_digest,
        }


@dataclass(frozen=True)
class SimulationCapabilityRequirement:
    """Minimum version of one immutable MarketBundle capability."""

    capability_key: str
    minimum_version: int

    def __post_init__(self) -> None:
        _require_canonical_text(self.capability_key, "capability_key")
        if type(self.minimum_version) is not int:
            raise TypeError("minimum_version must be int")
        if self.minimum_version <= 0:
            raise ValueError("minimum_version must be positive")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "simulation_capability_requirement",
            "capability_key": self.capability_key,
            "minimum_version": self.minimum_version,
        }


@dataclass(frozen=True)
class SimulationPortSpec:
    """Identity, capability requirements, and applicability of one model."""

    component_ref: SimulationComponentRef
    required_capabilities: tuple[SimulationCapabilityRequirement, ...]
    applicability: SimulationPortContract

    def __post_init__(self) -> None:
        if not isinstance(self.component_ref, SimulationComponentRef):
            raise TypeError("component_ref must be SimulationComponentRef")
        if type(self.required_capabilities) is not tuple:
            raise TypeError("required_capabilities must be tuple")
        if not all(
            isinstance(value, SimulationCapabilityRequirement)
            for value in self.required_capabilities
        ):
            raise TypeError(
                "required_capabilities must contain SimulationCapabilityRequirement"
            )
        capability_keys = [
            requirement.capability_key for requirement in self.required_capabilities
        ]
        if len(capability_keys) != len(set(capability_keys)):
            raise ValueError("duplicate capability requirement")
        object.__setattr__(
            self,
            "required_capabilities",
            tuple(
                sorted(
                    self.required_capabilities,
                    key=lambda value: (
                        value.capability_key,
                        value.minimum_version,
                    ),
                )
            ),
        )
        if not isinstance(self.applicability, SimulationPortContract):
            raise TypeError("applicability must satisfy SimulationPortContract")
        canonical_sha256(self.applicability)

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "simulation_port_spec",
            "component_ref": self.component_ref.to_canonical_dict(),
            "required_capabilities": [
                value.to_canonical_dict() for value in self.required_capabilities
            ],
            "applicability": self.applicability.to_canonical_dict(),
        }


_ResultT_co = TypeVar("_ResultT_co", bound=SimulationPortContract, covariant=True)
_FailureT_co = TypeVar("_FailureT_co", bound=SimulationPortContract, covariant=True)
_ResultValueT = TypeVar("_ResultValueT", bound=SimulationPortContract)
_FailureValueT = TypeVar("_FailureValueT", bound=SimulationPortContract)


@dataclass(frozen=True)
class SimulationPortOutcome(Generic[_ResultT_co, _FailureT_co]):
    """Deterministic exactly-one result/failure returned by a simulation port."""

    component_ref: SimulationComponentRef
    input_hash: str
    result: _ResultT_co | None
    failure: _FailureT_co | None

    def __post_init__(self) -> None:
        if not isinstance(self.component_ref, SimulationComponentRef):
            raise TypeError("component_ref must be SimulationComponentRef")
        if type(self.input_hash) is not str or _SHA256_PATTERN.fullmatch(
            self.input_hash
        ) is None:
            raise ValueError("input_hash must be a canonical sha256 identity")
        if (self.result is None) == (self.failure is None):
            raise ValueError("SimulationPortOutcome requires exactly one result or failure")
        value = self.result if self.result is not None else self.failure
        if not isinstance(value, SimulationPortContract):
            raise TypeError("result/failure must satisfy SimulationPortContract")
        canonical_sha256(value)

    @classmethod
    def for_result(
        cls,
        component_ref: SimulationComponentRef,
        request: SimulationPortContract,
        result: _ResultValueT,
    ) -> SimulationPortOutcome[_ResultValueT, Never]:
        if not isinstance(request, SimulationPortContract):
            raise TypeError("request must satisfy SimulationPortContract")
        if not isinstance(result, SimulationPortContract):
            raise TypeError("result must satisfy SimulationPortContract")
        return SimulationPortOutcome(
            component_ref=component_ref,
            input_hash=canonical_sha256(request),
            result=result,
            failure=None,
        )

    @classmethod
    def for_failure(
        cls,
        component_ref: SimulationComponentRef,
        request: SimulationPortContract,
        failure: _FailureValueT,
    ) -> SimulationPortOutcome[Never, _FailureValueT]:
        if not isinstance(request, SimulationPortContract):
            raise TypeError("request must satisfy SimulationPortContract")
        if not isinstance(failure, SimulationPortContract):
            raise TypeError("failure must satisfy SimulationPortContract")
        return SimulationPortOutcome(
            component_ref=component_ref,
            input_hash=canonical_sha256(request),
            result=None,
            failure=failure,
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "simulation_port_outcome",
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
    "_RequestT_contra", bound=SimulationPortContract, contravariant=True
)


class _SimulationPort(Protocol):
    @property
    @abstractmethod
    def spec(self) -> SimulationPortSpec:
        raise TypeError("Simulation port has no spec implementation")


@runtime_checkable
class ExecutionModel(
    _SimulationPort,
    Protocol[_RequestT_contra, _ResultT_co, _FailureT_co],
):
    @abstractmethod
    def simulate_execution(
        self, request: _RequestT_contra, /
    ) -> SimulationPortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("ExecutionModel has no implementation")


@runtime_checkable
class SlippageModel(
    _SimulationPort,
    Protocol[_RequestT_contra, _ResultT_co, _FailureT_co],
):
    @abstractmethod
    def decide_slippage(
        self, request: _RequestT_contra, /
    ) -> SimulationPortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("SlippageModel has no implementation")


@runtime_checkable
class LatencyModel(
    _SimulationPort,
    Protocol[_RequestT_contra, _ResultT_co, _FailureT_co],
):
    @abstractmethod
    def resolve_latency(
        self, request: _RequestT_contra, /
    ) -> SimulationPortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("LatencyModel has no implementation")


@runtime_checkable
class LiquidityModel(
    _SimulationPort,
    Protocol[_RequestT_contra, _ResultT_co, _FailureT_co],
):
    @abstractmethod
    def evaluate_liquidity(
        self, request: _RequestT_contra, /
    ) -> SimulationPortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("LiquidityModel has no implementation")


@runtime_checkable
class LiquidationAuditModel(
    _SimulationPort,
    Protocol[_RequestT_contra, _ResultT_co, _FailureT_co],
):
    @abstractmethod
    def audit_liquidation(
        self, request: _RequestT_contra, /
    ) -> SimulationPortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("LiquidationAuditModel has no implementation")


@runtime_checkable
class CloseoutPolicy(
    _SimulationPort,
    Protocol[_RequestT_contra, _ResultT_co, _FailureT_co],
):
    @abstractmethod
    def resolve_closeout(
        self, request: _RequestT_contra, /
    ) -> SimulationPortOutcome[_ResultT_co, _FailureT_co]:
        raise TypeError("CloseoutPolicy has no implementation")
