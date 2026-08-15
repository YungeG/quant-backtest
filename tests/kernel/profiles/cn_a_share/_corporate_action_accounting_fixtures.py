from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from crypto_quant_domain import (
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    Money,
    PositionBalanceKey,
    PositionLot,
    Price,
    QuantizationPolicy,
    Quantity,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashPaymentEvidence,
    CnAShareCashPaymentRequest,
    CnAShareCorporateActionDeliveryStatus,
    CnAShareCorporateActionEntitlement,
    CnAShareCorporateActionSourceRef,
    CnAShareCorporateActionTaxDisposition,
    CnAShareShareDeliveryEvidence,
    CnAShareShareDeliveryRequest,
)
from tests.kernel.profiles.cn_a_share._corporate_action_fixtures import entitlement_case

CNY_SCALE = Scale(2)
SHARE_SCALE = Scale(0)
UNIT_COST_SCALE = Scale(4)
PAYMENT_PHASE = TimelinePhase(110, "corporate_action_payment")
LISTING_PHASE = TimelinePhase(120, "corporate_action_listing")
DELIVERY_SOURCE = CnAShareCorporateActionSourceRef(
    "development.cn-a-share.delivery.v1", "sha256:" + "d" * 64
)
UNIT_COST_POLICY = QuantizationPolicy(
    "cn-a-share-corporate-action-unit-cost-v1",
    UNIT_COST_SCALE,
    RoundingPolicy.HALF_EVEN,
)


def journal_id(digit: str) -> DomainId:
    return DomainId(DomainIdKind.JOURNAL, f"jnl_{digit * 64}")


def local_boundary(value, phase: TimelinePhase) -> SimulationInstant:
    instant = UtcInstant.from_datetime(
        datetime(
            value.year,
            value.month,
            value.day,
            9,
            30,
            tzinfo=ZoneInfo("Asia/Shanghai"),
        )
    )
    return SimulationInstant(instant, phase, SourceSequence(0))


def recorded_after(trigger: SimulationInstant) -> SimulationInstant:
    return SimulationInstant(
        trigger.instant,
        TimelinePhase(130, "corporate_action_accounting"),
        SourceSequence(0),
    )


def entitlement(venue: str = "xshe", *, registered_units: int | None = None) -> CnAShareCorporateActionEntitlement:
    if registered_units is None:
        registered_units = 700 if venue == "xshe" else 1_000
    case = entitlement_case(venue, registered_units=registered_units)
    outcome = case.model.apply_corporate_action(case.query)
    assert outcome.result is not None
    return outcome.result


def payment_trigger(value: CnAShareCorporateActionEntitlement) -> SimulationInstant:
    announcement = value.query.announcement
    assert announcement is not None and announcement.payment_date is not None
    return local_boundary(announcement.payment_date.value, PAYMENT_PHASE)


def listing_trigger(value: CnAShareCorporateActionEntitlement) -> SimulationInstant:
    announcement = value.query.announcement
    assert announcement is not None and announcement.listing_date is not None
    return local_boundary(announcement.listing_date.value, LISTING_PHASE)


def cash_evidence(value: CnAShareCorporateActionEntitlement | None = None) -> CnAShareCashPaymentEvidence:
    value = entitlement() if value is None else value
    announcement = value.query.announcement
    assert announcement is not None
    trigger = payment_trigger(value)
    return CnAShareCashPaymentEvidence(
        evidence_id=f"evidence-{announcement.corporate_action_id.lower()}-cash",
        source_ref=DELIVERY_SOURCE,
        entitlement_hash=value.entitlement_hash,
        corporate_action_id=announcement.corporate_action_id,
        event_id=value.event_id,
        event_hash=value.event_hash,
        status=CnAShareCorporateActionDeliveryStatus.CONFIRMED,
        trigger_at=trigger,
        available_at=trigger,
        gross_cash=value.gross_cash,
        withholding=Money(0, CNY_SCALE, "CNY"),
        net_cash=value.gross_cash,
        tax_disposition=CnAShareCorporateActionTaxDisposition.NOT_APPLICABLE,
        tradable=True,
        withdrawable=True,
        margin_eligible=True,
    )


def cash_request(
    value: CnAShareCorporateActionEntitlement | None = None,
    *,
    digit: str = "8",
) -> CnAShareCashPaymentRequest:
    value = entitlement() if value is None else value
    evidence = cash_evidence(value)
    return CnAShareCashPaymentRequest(
        entitlement=value,
        evidence=evidence,
        cash_key=CashBalanceKey(
            value.account_id,
            value.position_key.venue_id,
            CurrencyId("CNY"),
        ),
        journal_entry_id=journal_id(digit),
        recorded_at=recorded_after(evidence.trigger_at),
    )


def exact_lot(value: CnAShareCorporateActionEntitlement | None = None) -> PositionLot:
    value = entitlement() if value is None else value
    instrument = str(value.position_key.instrument_id)
    return PositionLot(
        lot_id="lot-xshe-exact-basis-001",
        position_key=value.position_key,
        source_id="fill-xshe-current-500",
        quantity=Quantity(500, SHARE_SCALE, instrument),
        unit_cost=Price(150_000, UNIT_COST_SCALE, instrument, "CNY"),
        allocated_fees=(Money(250, CNY_SCALE, "CNY"),),
        opened_at=UtcInstant(value.eligibility_instant.instant.epoch_nanoseconds - 1),
        total_cost_basis=Money(750_000, CNY_SCALE, "CNY"),
    )


def share_evidence(value: CnAShareCorporateActionEntitlement | None = None) -> CnAShareShareDeliveryEvidence:
    value = entitlement() if value is None else value
    announcement = value.query.announcement
    assert announcement is not None
    trigger = listing_trigger(value)
    return CnAShareShareDeliveryEvidence(
        evidence_id=f"evidence-{announcement.corporate_action_id.lower()}-shares",
        source_ref=DELIVERY_SOURCE,
        entitlement_hash=value.entitlement_hash,
        corporate_action_id=announcement.corporate_action_id,
        event_id=value.event_id,
        event_hash=value.event_hash,
        status=CnAShareCorporateActionDeliveryStatus.CONFIRMED,
        trigger_at=trigger,
        available_at=trigger,
        delivered_bonus_quantity=value.bonus_quantity,
        delivered_capitalization_quantity=value.capitalization_quantity,
        withholding=Money(0, CNY_SCALE, "CNY"),
        tax_disposition=CnAShareCorporateActionTaxDisposition.NOT_APPLICABLE,
        sellable=True,
    )


def share_request(
    value: CnAShareCorporateActionEntitlement | None = None,
    *,
    digit: str = "7",
) -> CnAShareShareDeliveryRequest:
    value = entitlement() if value is None else value
    evidence = share_evidence(value)
    return CnAShareShareDeliveryRequest(
        entitlement=value,
        evidence=evidence,
        open_lots=(exact_lot(value),),
        unit_cost_quantization=UNIT_COST_POLICY,
        journal_entry_id=journal_id(digit),
        recorded_at=recorded_after(evidence.trigger_at),
    )


def with_cash_evidence(request: CnAShareCashPaymentRequest, **changes: object) -> CnAShareCashPaymentRequest:
    return replace(request, evidence=replace(request.evidence, **changes))


def with_share_evidence(request: CnAShareShareDeliveryRequest, **changes: object) -> CnAShareShareDeliveryRequest:
    return replace(request, evidence=replace(request.evidence, **changes))
