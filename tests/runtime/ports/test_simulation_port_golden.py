from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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
)
from crypto_quant_backtest import (
    SimulationCapabilityRequirement,
    SimulationComponentRef,
    SimulationPortOutcome,
    SimulationPortSpec,
    SimulationPortType,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/runtime/simulation-profile-ports-v1.json"


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


def test_simulation_profile_port_contracts_match_golden_fixture() -> None:
    try:
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AssertionError(f"invalid golden fixture: {FIXTURE}") from error

    request = SimulationQuery(
        instant=SimulationInstant(
            instant=UtcInstant(1_700_000_000_000_000_000),
            phase=TimelinePhase(3, "match_resting"),
            source_sequence=SourceSequence(7),
        ),
        instrument_id=InstrumentId(VenueId("test-venue"), "asset-1"),
        quantity=Quantity(25, Scale(1), "test-venue:asset-1"),
    )
    reference = SimulationComponentRef(
        port_type=SimulationPortType.EXECUTION_MODEL,
        component_key="test.execution_model.v1",
        component_version=1,
        component_digest="sha256:" + "cd" * 32,
    )
    port_spec = SimulationPortSpec(
        component_ref=reference,
        required_capabilities=(
            SimulationCapabilityRequirement("prices.execution_reference", 1),
            SimulationCapabilityRequirement("bars.ohlcv", 2),
        ),
        applicability=ApplicabilityEnvelope(
            engine_kind="bar",
            order_family="portfolio_rebalance",
        ),
    )

    assert fixture["fixture_id"] == "simulation-profile-ports-v1"
    assert fixture["port_types"] == [value.value for value in SimulationPortType]
    try:
        actual_spec = json.loads(canonical_bytes(port_spec))
        actual_success = json.loads(
            canonical_bytes(
                SimulationPortOutcome.for_result(
                    reference, request, SimulationDecision("eligible")
                )
            )
        )
        actual_failure = json.loads(
            canonical_bytes(
                SimulationPortOutcome.for_failure(
                    reference,
                    request,
                    SimulationFailure("capability_missing"),
                )
            )
        )
    except (CanonicalizationError, json.JSONDecodeError) as error:
        raise AssertionError("simulation port contract is not canonical JSON") from error

    assert actual_spec == fixture["port_spec"]
    assert actual_success == fixture["success_outcome"]
    assert actual_failure == fixture["failure_outcome"]
