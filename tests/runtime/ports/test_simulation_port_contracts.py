from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
from pathlib import Path
from types import SimpleNamespace

import crypto_quant_backtest
import pytest

from crypto_quant_domain import (
    CanonicalizationError,
    InstrumentId,
    Quantity,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import ProfilePortType
from crypto_quant_backtest import (
    CloseoutPolicy,
    ExecutionModel,
    LatencyModel,
    LiquidationAuditModel,
    LiquidityModel,
    SimulationCapabilityRequirement,
    SimulationComponentRef,
    SimulationPortContract,
    SimulationPortOutcome,
    SimulationPortSpec,
    SimulationPortType,
    SlippageModel,
)


@dataclass(frozen=True)
class SimulationQuery:
    instant: SimulationInstant
    instrument_id: InstrumentId
    quantity: Quantity

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "simulation_query",
            "instant": self.instant,
            "instrument_id": self.instrument_id,
            "quantity": self.quantity,
        }


@dataclass(frozen=True)
class SimulationDecision:
    decision: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "simulation_decision", "decision": self.decision}


@dataclass(frozen=True)
class SimulationFailure:
    failure_kind: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "simulation_failure", "failure_kind": self.failure_kind}


@dataclass(frozen=True)
class ApplicabilityEnvelope:
    engine_kind: str
    order_family: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "test_applicability_envelope",
            "engine_kind": self.engine_kind,
            "order_family": self.order_family,
        }


@dataclass(frozen=True)
class NoncanonicalApplicability:
    participation: float

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "noncanonical_applicability",
            "participation": self.participation,
        }


PORT_METHODS = (
    (SimulationPortType.EXECUTION_MODEL, ExecutionModel, "simulate_execution"),
    (SimulationPortType.SLIPPAGE_MODEL, SlippageModel, "decide_slippage"),
    (SimulationPortType.LATENCY_MODEL, LatencyModel, "resolve_latency"),
    (SimulationPortType.LIQUIDITY_MODEL, LiquidityModel, "evaluate_liquidity"),
    (
        SimulationPortType.LIQUIDATION_AUDIT_MODEL,
        LiquidationAuditModel,
        "audit_liquidation",
    ),
    (SimulationPortType.CLOSEOUT_POLICY, CloseoutPolicy, "resolve_closeout"),
)


def component_ref(port_type: SimulationPortType) -> SimulationComponentRef:
    return SimulationComponentRef(
        port_type=port_type,
        component_key=f"test.{port_type.value}.v1",
        component_version=1,
        component_digest="sha256:" + "cd" * 32,
    )


def applicability() -> ApplicabilityEnvelope:
    return ApplicabilityEnvelope(
        engine_kind="bar",
        order_family="portfolio_rebalance",
    )


def spec(port_type: SimulationPortType) -> SimulationPortSpec:
    return SimulationPortSpec(
        component_ref=component_ref(port_type),
        required_capabilities=(
            SimulationCapabilityRequirement("bars.ohlcv", 2),
            SimulationCapabilityRequirement("prices.execution_reference", 1),
        ),
        applicability=applicability(),
    )


def query() -> SimulationQuery:
    return SimulationQuery(
        instant=SimulationInstant(
            instant=UtcInstant(1_700_000_000_000_000_000),
            phase=TimelinePhase(3, "match_resting"),
            source_sequence=SourceSequence(7),
        ),
        instrument_id=InstrumentId(VenueId("test-venue"), "asset-1"),
        quantity=Quantity(25, Scale(1), "test-venue:asset-1"),
    )


def test_runtime_publishes_pep561_type_information() -> None:
    module_file = crypto_quant_backtest.__file__
    assert module_file is not None
    assert (Path(module_file).resolve().parent / "py.typed").is_file()


def test_simulation_component_identity_is_separate_and_canonical() -> None:
    reference = component_ref(SimulationPortType.EXECUTION_MODEL)

    assert reference.to_canonical_dict() == {
        "type": "simulation_component_ref",
        "port_type": "execution_model",
        "component_key": "test.execution_model.v1",
        "component_version": 1,
        "component_digest": "sha256:" + "cd" * 32,
    }
    assert set(value.value for value in SimulationPortType).isdisjoint(
        value.value for value in ProfilePortType
    )
    with pytest.raises(TypeError, match="SimulationPortType"):
        SimulationComponentRef(
            port_type=ProfilePortType.SESSION_MODEL,  # type: ignore[arg-type]
            component_key="test.execution.v1",
            component_version=1,
            component_digest="sha256:" + "cd" * 32,
        )
    with pytest.raises(FrozenInstanceError):
        reference.component_version = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("port_type", "execution_model", TypeError),
        ("component_key", "", ValueError),
        ("component_key", "e\u0301", ValueError),
        ("component_version", 0, ValueError),
        ("component_version", True, TypeError),
        ("component_digest", "cd" * 32, ValueError),
    ],
)
def test_component_ref_rejects_invalid_identity(
    field: str, value: object, error: type[Exception]
) -> None:
    values: dict[str, object] = {
        "port_type": SimulationPortType.EXECUTION_MODEL,
        "component_key": "test.execution.v1",
        "component_version": 1,
        "component_digest": "sha256:" + "cd" * 32,
    }
    values[field] = value

    with pytest.raises(error):
        SimulationComponentRef(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("capability_key", "", ValueError),
        ("capability_key", " bars.ohlcv", ValueError),
        ("capability_key", "e\u0301", ValueError),
        ("minimum_version", 0, ValueError),
        ("minimum_version", True, TypeError),
    ],
)
def test_capability_requirement_rejects_invalid_values(
    field: str, value: object, error: type[Exception]
) -> None:
    values: dict[str, object] = {
        "capability_key": "bars.ohlcv",
        "minimum_version": 1,
    }
    values[field] = value

    with pytest.raises(error):
        SimulationCapabilityRequirement(**values)  # type: ignore[arg-type]


def test_spec_canonicalizes_capabilities_and_requires_typed_applicability() -> None:
    reference = component_ref(SimulationPortType.EXECUTION_MODEL)
    capability_a = SimulationCapabilityRequirement("prices.execution_reference", 1)
    capability_b = SimulationCapabilityRequirement("bars.ohlcv", 2)
    value = SimulationPortSpec(
        component_ref=reference,
        required_capabilities=(capability_a, capability_b),
        applicability=applicability(),
    )

    assert list(value.required_capabilities) == [capability_b, capability_a]
    assert value.to_canonical_dict() == {
        "type": "simulation_port_spec",
        "component_ref": reference.to_canonical_dict(),
        "required_capabilities": [
            capability_b.to_canonical_dict(),
            capability_a.to_canonical_dict(),
        ],
        "applicability": applicability().to_canonical_dict(),
    }
    empty_spec = SimulationPortSpec(
        component_ref=reference,
        required_capabilities=(),
        applicability=applicability(),
    )
    assert not empty_spec.required_capabilities

    with pytest.raises(ValueError, match="duplicate capability"):
        SimulationPortSpec(
            component_ref=reference,
            required_capabilities=(capability_b, capability_b),
            applicability=applicability(),
        )
    with pytest.raises(TypeError, match="tuple"):
        SimulationPortSpec(
            component_ref=reference,
            required_capabilities=[capability_b],  # type: ignore[arg-type]
            applicability=applicability(),
        )
    with pytest.raises(TypeError, match="SimulationPortContract"):
        SimulationPortSpec(
            component_ref=reference,
            required_capabilities=(),
            applicability=object(),  # type: ignore[arg-type]
        )
    with pytest.raises(CanonicalizationError):
        SimulationPortSpec(
            component_ref=reference,
            required_capabilities=(),
            applicability=NoncanonicalApplicability(0.5),
        )


def test_outcome_records_exact_input_and_exactly_one_branch() -> None:
    request = query()
    reference = component_ref(SimulationPortType.EXECUTION_MODEL)
    result = SimulationDecision("eligible")
    failure = SimulationFailure("capability_missing")
    success = SimulationPortOutcome.for_result(reference, request, result)
    rejected = SimulationPortOutcome.for_failure(reference, request, failure)

    assert success.input_hash == canonical_sha256(request)
    assert success.result == result
    assert success.failure is None
    assert rejected.result is None
    assert rejected.failure == failure
    assert canonical_bytes(success) == canonical_bytes(
        SimulationPortOutcome.for_result(reference, request, result)
    )

    with pytest.raises(ValueError, match="exactly one"):
        SimulationPortOutcome(
            component_ref=reference,
            input_hash=canonical_sha256(request),
            result=result,
            failure=failure,
        )
    with pytest.raises(ValueError, match="exactly one"):
        SimulationPortOutcome[SimulationDecision, SimulationFailure](
            component_ref=reference,
            input_hash=canonical_sha256(request),
            result=None,
            failure=None,
        )
    with pytest.raises(ValueError, match="input_hash"):
        SimulationPortOutcome(
            component_ref=reference,
            input_hash="bad",
            result=result,
            failure=None,
        )


def test_all_simulation_ports_are_distinct_protocols_without_defaults() -> None:
    request = query()
    result = SimulationDecision("eligible")

    for port_type, protocol, method_name in PORT_METHODS:
        port_spec = spec(port_type)
        outcome = SimulationPortOutcome.for_result(
            port_spec.component_ref, request, result
        )
        adapter = SimpleNamespace(spec=port_spec)
        setattr(adapter, method_name, lambda value, outcome=outcome: outcome)

        assert getattr(protocol, "_is_protocol", False)
        assert isinstance(adapter, protocol)
        assert getattr(adapter, method_name)(request) == outcome
        assert not isinstance(SimpleNamespace(spec=port_spec), protocol)


def test_test_adapter_is_deterministic_and_uses_typed_contracts() -> None:
    request = query()
    execution_spec = spec(SimulationPortType.EXECUTION_MODEL)

    class TestExecutionAdapter:
        spec = execution_spec

        def simulate_execution(
            self, value: SimulationQuery, /
        ) -> SimulationPortOutcome[SimulationDecision, SimulationFailure]:
            return SimulationPortOutcome.for_result(
                self.spec.component_ref,
                value,
                SimulationDecision("eligible"),
            )

    adapter = TestExecutionAdapter()
    assert isinstance(request, SimulationPortContract)
    assert isinstance(applicability(), SimulationPortContract)
    assert isinstance(adapter, ExecutionModel)
    assert canonical_bytes(adapter.simulate_execution(request)) == canonical_bytes(
        adapter.simulate_execution(request)
    )
