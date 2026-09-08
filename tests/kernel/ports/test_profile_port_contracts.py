from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import crypto_quant_domain
import crypto_quant_trading
import pytest

from crypto_quant_domain import (
    CanonicalizationError,
    InstrumentId,
    SessionId,
    TradingDate,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    CorporateActionModel,
    CurrencyValuationPolicy,
    FeeAssessmentPolicy,
    FinancingModel,
    InstrumentModel,
    LiquidationRules,
    MarginModel,
    OrderRuleModel,
    PositionAccountingModel,
    ProfileComponentRef,
    ProfilePortContract,
    ProfilePortOutcome,
    ProfilePortType,
    SessionModel,
    SettlementModel,
    TaxPolicy,
)


@dataclass(frozen=True)
class SessionQuery:
    instant: UtcInstant
    instrument_id: InstrumentId

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "session_query",
            "instant": self.instant,
            "instrument_id": self.instrument_id,
        }


@dataclass(frozen=True)
class SessionResolution:
    session_id: SessionId
    trading_date: TradingDate

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "session_resolution",
            "session_id": self.session_id,
            "trading_date": self.trading_date,
        }


@dataclass(frozen=True)
class SessionFailure:
    failure_kind: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "session_failure", "failure_kind": self.failure_kind}


@dataclass(frozen=True)
class NoncanonicalResult:
    value: float

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "noncanonical_result", "value": self.value}


PORT_METHODS = (
    (ProfilePortType.SESSION_MODEL, SessionModel, "resolve_session"),
    (ProfilePortType.INSTRUMENT_MODEL, InstrumentModel, "resolve_instrument"),
    (ProfilePortType.ORDER_RULE_MODEL, OrderRuleModel, "resolve_order_rules"),
    (ProfilePortType.FEE_ASSESSMENT_POLICY, FeeAssessmentPolicy, "assess_fees"),
    (ProfilePortType.TAX_POLICY, TaxPolicy, "assess_taxes"),
    (ProfilePortType.SETTLEMENT_MODEL, SettlementModel, "resolve_settlement"),
    (
        ProfilePortType.POSITION_ACCOUNTING_MODEL,
        PositionAccountingModel,
        "translate_position_fact",
    ),
    (ProfilePortType.FINANCING_MODEL, FinancingModel, "assess_financing"),
    (ProfilePortType.MARGIN_MODEL, MarginModel, "evaluate_margin"),
    (
        ProfilePortType.LIQUIDATION_RULES,
        LiquidationRules,
        "evaluate_liquidation",
    ),
    (
        ProfilePortType.CORPORATE_ACTION_MODEL,
        CorporateActionModel,
        "apply_corporate_action",
    ),
    (
        ProfilePortType.CURRENCY_VALUATION_POLICY,
        CurrencyValuationPolicy,
        "select_valuation_path",
    ),
)


def component_ref(port_type: ProfilePortType) -> ProfileComponentRef:
    return ProfileComponentRef(
        port_type=port_type,
        component_key=f"test.{port_type.value}.v1",
        component_version=1,
        component_digest="sha256:" + "ab" * 32,
    )


def query() -> SessionQuery:
    return SessionQuery(
        instant=UtcInstant(1_700_000_000_000_000_000),
        instrument_id=InstrumentId(VenueId("test-venue"), "asset-1"),
    )


def resolution() -> SessionResolution:
    return SessionResolution(
        session_id=SessionId("test-venue", "2023-11-15.regular"),
        trading_date=TradingDate("test-venue", date(2023, 11, 15)),
    )


def test_domain_and_kernel_publish_pep561_type_information() -> None:
    for module in (crypto_quant_domain, crypto_quant_trading):
        module_file = module.__file__
        assert module_file is not None
        package_root = Path(module_file).resolve().parent
        assert (package_root / "py.typed").is_file()


def test_component_ref_is_typed_versioned_and_canonical() -> None:
    reference = component_ref(ProfilePortType.SESSION_MODEL)

    assert reference.to_canonical_dict() == {
        "type": "profile_component_ref",
        "port_type": "session_model",
        "component_key": "test.session_model.v1",
        "component_version": 1,
        "component_digest": "sha256:" + "ab" * 32,
    }
    assert canonical_bytes(reference) == canonical_bytes(reference)

    with pytest.raises(FrozenInstanceError):
        reference.component_version = 2  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("port_type", "session_model", TypeError),
        ("component_key", "", ValueError),
        ("component_key", "e\u0301", ValueError),
        ("component_version", 0, ValueError),
        ("component_version", True, TypeError),
        ("component_digest", "ab" * 32, ValueError),
    ],
)
def test_component_ref_rejects_invalid_identity(
    field: str, value: object, error: type[Exception]
) -> None:
    values: dict[str, object] = {
        "port_type": ProfilePortType.SESSION_MODEL,
        "component_key": "test.session.v1",
        "component_version": 1,
        "component_digest": "sha256:" + "ab" * 32,
    }
    values[field] = value

    with pytest.raises(error):
        ProfileComponentRef(**values)  # type: ignore[arg-type]


def test_outcome_records_exact_input_and_exactly_one_branch() -> None:
    request = query()
    reference = component_ref(ProfilePortType.SESSION_MODEL)
    success = ProfilePortOutcome.for_result(reference, request, resolution())
    failure = ProfilePortOutcome.for_failure(
        reference, request, SessionFailure("no_session")
    )

    assert success.input_hash == canonical_sha256(request)
    assert success.result == resolution()
    assert success.failure is None
    assert failure.result is None
    assert failure.failure == SessionFailure("no_session")
    assert canonical_bytes(success) == canonical_bytes(
        ProfilePortOutcome.for_result(reference, request, resolution())
    )

    with pytest.raises(ValueError, match="exactly one"):
        ProfilePortOutcome(
            component_ref=reference,
            input_hash=canonical_sha256(request),
            result=resolution(),
            failure=SessionFailure("no_session"),
        )
    with pytest.raises(ValueError, match="exactly one"):
        ProfilePortOutcome[SessionResolution, SessionFailure](
            component_ref=reference,
            input_hash=canonical_sha256(request),
            result=None,
            failure=None,
        )
    with pytest.raises(ValueError, match="input_hash"):
        ProfilePortOutcome(
            component_ref=reference,
            input_hash="bad",
            result=resolution(),
            failure=None,
        )
    with pytest.raises(TypeError, match="ProfilePortContract"):
        ProfilePortOutcome(
            component_ref=reference,
            input_hash=canonical_sha256(request),
            result=object(),  # type: ignore[arg-type]
            failure=None,
        )
    with pytest.raises(CanonicalizationError):
        ProfilePortOutcome(
            component_ref=reference,
            input_hash=canonical_sha256(request),
            result=NoncanonicalResult(1.5),
            failure=None,
        )


def test_all_ports_are_distinct_runtime_protocols_without_defaults() -> None:
    request = query()
    result = resolution()

    for port_type, protocol, method_name in PORT_METHODS:
        reference = component_ref(port_type)
        outcome = ProfilePortOutcome.for_result(reference, request, result)
        adapter = SimpleNamespace(component_ref=reference)
        setattr(adapter, method_name, lambda value, outcome=outcome: outcome)

        assert getattr(protocol, "_is_protocol", False)
        assert isinstance(adapter, protocol)
        assert getattr(adapter, method_name)(request) == outcome
        assert not isinstance(SimpleNamespace(component_ref=reference), protocol)


def test_test_adapter_is_deterministic_and_uses_domain_typed_contracts() -> None:
    request = query()
    reference = component_ref(ProfilePortType.SESSION_MODEL)

    class TestSessionAdapter:
        component_ref = reference

        def resolve_session(
            self, value: SessionQuery, /
        ) -> ProfilePortOutcome[SessionResolution, SessionFailure]:
            return ProfilePortOutcome.for_result(
                self.component_ref, value, resolution()
            )

    adapter = TestSessionAdapter()
    assert isinstance(request, ProfilePortContract)
    assert isinstance(resolution(), ProfilePortContract)
    assert isinstance(adapter, SessionModel)
    assert canonical_bytes(adapter.resolve_session(request)) == canonical_bytes(
        adapter.resolve_session(request)
    )
