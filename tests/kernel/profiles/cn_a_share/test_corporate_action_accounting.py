from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    AccountingEntryType,
    CashBalanceKey,
    CurrencyId,
    DomainId,
    DomainIdKind,
    InstrumentId,
    Money,
    PositionBalanceKey,
    Price,
    QuantizationPolicy,
    Quantity,
    RoundingPolicy,
    Scale,
    SimulationInstant,
    SourceSequence,
    TimelinePhase,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCashPaymentEvidence,
    CnAShareCashPaymentOutcome,
    CnAShareCashPaymentRequest,
    CnAShareCorporateActionDeliveryStatus,
    CnAShareCorporateActionTaxDisposition,
    CnAShareCorporateActionTranslationFailure,
    CnAShareCorporateActionTranslationFailureCode,
    CnAShareShareDeliveryEvidence,
    CnAShareShareDeliveryOutcome,
    CnAShareShareDeliveryRequest,
    translate_corporate_action_cash_payment,
    translate_corporate_action_share_delivery,
)
from tests.kernel.profiles.cn_a_share._corporate_action_accounting_fixtures import (
    CNY_SCALE,
    LISTING_PHASE,
    PAYMENT_PHASE,
    SHARE_SCALE,
    UNIT_COST_POLICY,
    UNIT_COST_SCALE,
    cash_evidence,
    cash_request,
    entitlement,
    exact_lot,
    journal_id,
    listing_trigger,
    payment_trigger,
    share_evidence,
    share_request,
    with_cash_evidence,
    with_share_evidence,
)

FAILURE_VALUES = (
    "context_mismatch",
    "entitlement_evidence_mismatch",
    "unsupported_action_scope",
    "unsupported_delivery_status",
    "unsupported_tax_disposition",
    "nonzero_withholding",
    "unsupported_availability",
    "trigger_mismatch",
    "evidence_not_available",
    "unsupported_fractional_share",
    "delivered_value_mismatch",
    "early_invocation",
    "eligible_lot_cardinality_mismatch",
    "lot_state_mismatch",
    "exact_cost_basis_mismatch",
    "unit_cost_quantization_mismatch",
)


def _failure_code(outcome: Any) -> CnAShareCorporateActionTranslationFailureCode:
    assert outcome.journal_entry is None
    assert outcome.failure is not None
    return outcome.failure.code


def test_public_enums_and_concrete_seam_are_exact() -> None:
    assert tuple(value.value for value in CnAShareCorporateActionTaxDisposition) == (
        "not_applicable",
        "applied",
        "deferred_unsupported",
    )
    assert tuple(value.value for value in CnAShareCorporateActionDeliveryStatus) == (
        "confirmed",
        "suspended",
        "cancelled",
    )
    assert tuple(value.value for value in CnAShareCorporateActionTranslationFailureCode) == FAILURE_VALUES
    assert [field.name for field in fields(CnAShareCashPaymentEvidence)] == [
        "evidence_id",
        "source_ref",
        "entitlement_hash",
        "corporate_action_id",
        "event_id",
        "event_hash",
        "status",
        "trigger_at",
        "available_at",
        "gross_cash",
        "withholding",
        "net_cash",
        "tax_disposition",
        "tradable",
        "withdrawable",
        "margin_eligible",
    ]
    assert [field.name for field in fields(CnAShareShareDeliveryEvidence)] == [
        "evidence_id",
        "source_ref",
        "entitlement_hash",
        "corporate_action_id",
        "event_id",
        "event_hash",
        "status",
        "trigger_at",
        "available_at",
        "delivered_bonus_quantity",
        "delivered_capitalization_quantity",
        "withholding",
        "tax_disposition",
        "sellable",
    ]
    assert [field.name for field in fields(CnAShareCashPaymentOutcome)] == [
        "request",
        "journal_entry",
        "failure",
    ]
    assert [field.name for field in fields(CnAShareShareDeliveryOutcome)] == [
        "request",
        "journal_entry",
        "failure",
    ]


def test_evidence_and_requests_are_frozen_slotted_and_semantic_defects_construct() -> None:
    cash = cash_evidence()
    share = share_evidence()
    requests = (cash_request(), share_request())
    for value in (cash, share, *requests):
        assert type(value).__slots__
    for value in (cash, share):
        with pytest.raises(FrozenInstanceError):
            cast(Any, value).evidence_id = "forged"
    for value in requests:
        with pytest.raises(FrozenInstanceError):
            cast(Any, value).recorded_at = value.recorded_at

    # Business defects are translator outcomes, not constructor errors.
    replace(cash, status=CnAShareCorporateActionDeliveryStatus.SUSPENDED)
    replace(cash, withholding=Money(1, CNY_SCALE, "CNY"), tradable=False)
    replace(share, status=CnAShareCorporateActionDeliveryStatus.CANCELLED)
    replace(share, withholding=Money(1, CNY_SCALE, "CNY"), sellable=False)

    with pytest.raises((TypeError, ValueError)):
        replace(cash, evidence_id=" noncanonical")
    with pytest.raises((TypeError, ValueError)):
        cast(Any, CnAShareCashPaymentEvidence)(evidence_id=1)


def test_cash_payment_success_has_one_exact_payment_journal_effect() -> None:
    request = cash_request()
    outcome = translate_corporate_action_cash_payment(request)

    assert outcome.request is request
    assert outcome.failure is None
    entry = outcome.journal_entry
    assert entry is not None
    assert entry.journal_entry_id == journal_id("8")
    assert entry.entry_type is AccountingEntryType.CORPORATE_ACTION_CASH_PAID
    assert entry.account_id == request.entitlement.account_id
    assert entry.venue_id == request.entitlement.position_key.venue_id
    assert entry.effective_time == request.evidence.trigger_at.instant
    assert entry.recorded_at == request.recorded_at
    assert entry.source_ids == (
        request.evidence.corporate_action_id,
        request.entitlement.entitlement_hash,
        request.evidence.event_id,
        request.evidence.event_hash,
        request.evidence.evidence_id,
        request.evidence.evidence_hash,
    )
    assert len(entry.balance_changes) == 1
    assert entry.balance_changes[0].key == request.cash_key
    assert entry.balance_changes[0].value == Money(7_000, CNY_SCALE, "CNY")
    assert entry.position_lot_changes == ()
    assert entry.realized_pnl == entry.fees == entry.financing == ()
    assert not hasattr(outcome, "settlement")
    assert not hasattr(outcome, "availability")


def test_xshg_cny_200_cash_payment_is_supported() -> None:
    request = cash_request(entitlement("xshg"))
    outcome = translate_corporate_action_cash_payment(request)
    assert outcome.failure is None
    assert outcome.journal_entry is not None
    assert outcome.journal_entry.balance_changes[0].value == Money(20_000, CNY_SCALE, "CNY")


def test_share_delivery_rejects_xshg_and_zero_xshe_share_scope() -> None:
    for value in (entitlement("xshg"), entitlement(registered_units=0)):
        outcome = translate_corporate_action_share_delivery(share_request(value))
        assert (
            _failure_code(outcome)
            is CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_ACTION_SCOPE
        )


def test_share_delivery_conserves_exact_basis_and_adjusts_current_500_not_record_700() -> None:
    request = share_request()
    old = request.open_lots[0]
    assert request.entitlement.registered_quantity.units == 700
    assert old.quantity.units == 500

    outcome = translate_corporate_action_share_delivery(request)
    assert outcome.request is request
    assert outcome.failure is None
    entry = outcome.journal_entry
    assert entry is not None
    assert entry.entry_type is AccountingEntryType.CORPORATE_ACTION_POSITION_ADJUSTED
    assert entry.effective_time == request.evidence.trigger_at.instant
    assert entry.source_ids == (
        request.evidence.corporate_action_id,
        request.entitlement.entitlement_hash,
        request.evidence.event_id,
        request.evidence.event_hash,
        request.evidence.evidence_id,
        request.evidence.evidence_hash,
    )
    assert len(entry.balance_changes) == 1
    assert entry.balance_changes[0].key == request.entitlement.position_key
    assert entry.balance_changes[0].value == Quantity(
        210, SHARE_SCALE, str(request.entitlement.position_key.instrument_id)
    )
    assert len(entry.position_lot_changes) == 1
    change = entry.position_lot_changes[0]
    assert change.before is old
    assert change.after is not None
    adjusted = change.after
    assert adjusted.lot_id == old.lot_id
    assert adjusted.source_id == old.source_id
    assert adjusted.position_key == old.position_key
    assert adjusted.opened_at == old.opened_at
    assert adjusted.allocated_fees == old.allocated_fees
    assert adjusted.quantity.units == 710
    assert adjusted.total_cost_basis == Money(750_000, CNY_SCALE, "CNY")
    assert adjusted.unit_cost == Price(
        105_634,
        UNIT_COST_SCALE,
        str(request.entitlement.position_key.instrument_id),
        "CNY",
    )
    assert entry.realized_pnl == entry.fees == entry.financing == ()
    assert not hasattr(outcome, "open_lots")


def test_exact_payment_and_listing_boundaries_and_available_equals_trigger() -> None:
    cash = cash_request()
    share = share_request()
    assert cash.evidence.trigger_at == payment_trigger(cash.entitlement)
    assert cash.evidence.trigger_at.phase == PAYMENT_PHASE
    assert cash.evidence.trigger_at.source_sequence == SourceSequence(0)
    assert cash.evidence.available_at == cash.evidence.trigger_at
    assert share.evidence.trigger_at == listing_trigger(share.entitlement)
    assert share.evidence.trigger_at.phase == LISTING_PHASE
    assert share.evidence.trigger_at.source_sequence == SourceSequence(0)
    assert share.evidence.available_at == share.evidence.trigger_at

    for request, translator in (
        (cash, translate_corporate_action_cash_payment),
        (share, translate_corporate_action_share_delivery),
    ):
        wrong = replace(
            request.evidence.trigger_at,
            source_sequence=SourceSequence(1),
        )
        defective = replace(
            request,
            evidence=replace(request.evidence, trigger_at=wrong, available_at=wrong),
        )
        assert _failure_code(translator(defective)) is CnAShareCorporateActionTranslationFailureCode.TRIGGER_MISMATCH


def _failure_controls() -> tuple[tuple[CnAShareCorporateActionTranslationFailureCode, Any], ...]:
    cash = cash_request()
    share = share_request()
    zero = cash_request(entitlement(registered_units=0))
    other_instrument = InstrumentId(VenueId("xshe"), "xshe.other.stable")
    other_key = PositionBalanceKey(cash.entitlement.account_id, VenueId("xshe"), other_instrument)
    old = share.open_lots[0]
    wrong_lot = replace(
        old,
        position_key=other_key,
        quantity=Quantity(old.quantity.units, SHARE_SCALE, str(other_instrument)),
        unit_cost=Price(old.unit_cost.units, UNIT_COST_SCALE, str(other_instrument), "CNY"),
    )
    wrong_trigger = replace(cash.evidence.trigger_at, phase=TimelinePhase(111, "wrong_payment"))
    late_available = replace(cash.evidence.trigger_at, source_sequence=SourceSequence(1))
    early = replace(cash.evidence.trigger_at, phase=TimelinePhase(109, "before_payment"))
    fractional = Quantity(700, Scale(1), str(share.entitlement.position_key.instrument_id))
    return (
        (
            CnAShareCorporateActionTranslationFailureCode.CONTEXT_MISMATCH,
            translate_corporate_action_cash_payment(
                replace(cash, journal_entry_id=DomainId(DomainIdKind.FILL, "fil_" + "1" * 64))
            ),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.ENTITLEMENT_EVIDENCE_MISMATCH,
            translate_corporate_action_cash_payment(
                with_cash_evidence(cash, entitlement_hash="sha256:" + "0" * 64)
            ),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_ACTION_SCOPE,
            translate_corporate_action_cash_payment(zero),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_DELIVERY_STATUS,
            translate_corporate_action_cash_payment(
                with_cash_evidence(cash, status=CnAShareCorporateActionDeliveryStatus.SUSPENDED)
            ),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_TAX_DISPOSITION,
            translate_corporate_action_cash_payment(
                with_cash_evidence(cash, tax_disposition=CnAShareCorporateActionTaxDisposition.APPLIED)
            ),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.NONZERO_WITHHOLDING,
            translate_corporate_action_cash_payment(
                with_cash_evidence(cash, withholding=Money(1, CNY_SCALE, "CNY"))
            ),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_AVAILABILITY,
            translate_corporate_action_cash_payment(with_cash_evidence(cash, tradable=False)),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.TRIGGER_MISMATCH,
            translate_corporate_action_cash_payment(
                with_cash_evidence(cash, trigger_at=wrong_trigger, available_at=wrong_trigger)
            ),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.EVIDENCE_NOT_AVAILABLE,
            translate_corporate_action_cash_payment(with_cash_evidence(cash, available_at=late_available)),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.UNSUPPORTED_FRACTIONAL_SHARE,
            translate_corporate_action_share_delivery(
                with_share_evidence(share, delivered_bonus_quantity=fractional)
            ),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.DELIVERED_VALUE_MISMATCH,
            translate_corporate_action_cash_payment(
                with_cash_evidence(cash, gross_cash=Money(6_999, CNY_SCALE, "CNY"), net_cash=Money(6_999, CNY_SCALE, "CNY"))
            ),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.EARLY_INVOCATION,
            translate_corporate_action_cash_payment(replace(cash, recorded_at=early)),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.ELIGIBLE_LOT_CARDINALITY_MISMATCH,
            translate_corporate_action_share_delivery(replace(share, open_lots=())),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.LOT_STATE_MISMATCH,
            translate_corporate_action_share_delivery(replace(share, open_lots=(wrong_lot,))),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.EXACT_COST_BASIS_MISMATCH,
            translate_corporate_action_share_delivery(
                replace(share, open_lots=(replace(old, total_cost_basis=Money(0, CNY_SCALE, "CNY")),))
            ),
        ),
        (
            CnAShareCorporateActionTranslationFailureCode.UNIT_COST_QUANTIZATION_MISMATCH,
            translate_corporate_action_share_delivery(
                replace(
                    share,
                    unit_cost_quantization=QuantizationPolicy(
                        "wrong-target-scale", Scale(3), RoundingPolicy.HALF_EVEN
                    ),
                )
            ),
        ),
    )


def test_all_16_failures_are_reachable_in_frozen_precedence_order_without_partial_output() -> None:
    controls = _failure_controls()
    assert tuple(code.value for code, _ in controls) == FAILURE_VALUES
    for expected, outcome in controls:
        assert _failure_code(outcome) is expected
        assert outcome.failure is not None
        request = outcome.request
        leg = (
            "cash_payment"
            if isinstance(request, CnAShareCashPaymentRequest)
            else "share_delivery"
        )
        evidence = request.evidence
        assert outcome.failure.subject_ids == (
            expected.value,
            leg,
            evidence.corporate_action_id,
            request.entitlement.entitlement_hash,
            evidence.evidence_id,
            evidence.evidence_hash,
            request.entitlement.account_id,
            str(request.entitlement.position_key.instrument_id),
            str(request.journal_entry_id),
        )


def test_multi_defect_precedence_and_intrinsic_defect_are_retry_stable() -> None:
    cash = cash_request()
    multi = replace(
        with_cash_evidence(
            cash,
            entitlement_hash="sha256:" + "0" * 64,
            status=CnAShareCorporateActionDeliveryStatus.CANCELLED,
            withholding=Money(1, CNY_SCALE, "CNY"),
            tradable=False,
        ),
        journal_entry_id=DomainId(DomainIdKind.FILL, "fil_" + "2" * 64),
    )
    assert _failure_code(translate_corporate_action_cash_payment(multi)) is CnAShareCorporateActionTranslationFailureCode.CONTEXT_MISMATCH

    mismatch = with_cash_evidence(
        cash,
        gross_cash=Money(6_999, CNY_SCALE, "CNY"),
        net_cash=Money(6_999, CNY_SCALE, "CNY"),
    )
    early = replace(
        mismatch,
        recorded_at=replace(mismatch.evidence.trigger_at, phase=TimelinePhase(109, "early")),
    )
    assert _failure_code(translate_corporate_action_cash_payment(mismatch)) is CnAShareCorporateActionTranslationFailureCode.DELIVERED_VALUE_MISMATCH
    assert _failure_code(translate_corporate_action_cash_payment(early)) is CnAShareCorporateActionTranslationFailureCode.DELIVERED_VALUE_MISMATCH


def test_lot_cardinality_is_absolute_and_never_filters_candidates() -> None:
    request = share_request()
    bad = replace(request.open_lots[0], source_id="unrelated-but-well-formed")
    outcome = translate_corporate_action_share_delivery(
        replace(request, open_lots=(request.open_lots[0], bad))
    )
    assert _failure_code(outcome) is CnAShareCorporateActionTranslationFailureCode.ELIGIBLE_LOT_CARDINALITY_MISMATCH


def test_context_identity_and_source_collisions_fail_before_economic_guards() -> None:
    cash = cash_request()
    wrong_cash_key = CashBalanceKey(
        cash.entitlement.account_id,
        cash.entitlement.position_key.venue_id,
        CurrencyId("USD"),
    )
    assert _failure_code(
        translate_corporate_action_cash_payment(replace(cash, cash_key=wrong_cash_key))
    ) is CnAShareCorporateActionTranslationFailureCode.CONTEXT_MISMATCH
    assert _failure_code(
        translate_corporate_action_cash_payment(
            with_cash_evidence(cash, withholding=Money(0, Scale(3), "CNY"))
        )
    ) is CnAShareCorporateActionTranslationFailureCode.CONTEXT_MISMATCH
    assert _failure_code(
        translate_corporate_action_cash_payment(
            with_cash_evidence(
                cash,
                gross_cash=Money(7_000, Scale(3), "CNY"),
                net_cash=Money(7_000, Scale(3), "CNY"),
            )
        )
    ) is CnAShareCorporateActionTranslationFailureCode.CONTEXT_MISMATCH

    share = share_request()
    assert _failure_code(
        translate_corporate_action_share_delivery(
            with_share_evidence(share, withholding=Money(0, CNY_SCALE, "USD"))
        )
    ) is CnAShareCorporateActionTranslationFailureCode.CONTEXT_MISMATCH
    other_instrument = "xshe:xshe.other.stable"
    assert _failure_code(
        translate_corporate_action_share_delivery(
            with_share_evidence(
                share,
                delivered_bonus_quantity=Quantity(
                    share.evidence.delivered_bonus_quantity.units,
                    SHARE_SCALE,
                    other_instrument,
                ),
            )
        )
    ) is CnAShareCorporateActionTranslationFailureCode.CONTEXT_MISMATCH
    assert _failure_code(
        translate_corporate_action_cash_payment(
            with_cash_evidence(
                cash,
                evidence_id=cash.evidence.corporate_action_id,
            )
        )
    ) is CnAShareCorporateActionTranslationFailureCode.ENTITLEMENT_EVIDENCE_MISMATCH


def test_share_lot_scale_fails_but_rounded_unit_cost_does_not_override_exact_basis() -> None:
    request = share_request()
    old = request.open_lots[0]
    scaled = replace(
        old,
        quantity=Quantity(
            old.quantity.units * 10,
            Scale(1),
            old.quantity.instrument_id,
        ),
    )
    assert _failure_code(
        translate_corporate_action_share_delivery(
            replace(request, open_lots=(scaled,))
        )
    ) is CnAShareCorporateActionTranslationFailureCode.LOT_STATE_MISMATCH

    assert old.unit_cost is not None
    rounded = replace(
        old,
        unit_cost=replace(old.unit_cost, units=old.unit_cost.units - 1),
    )
    outcome = translate_corporate_action_share_delivery(
        replace(request, open_lots=(rounded,))
    )
    assert outcome.failure is None
    assert outcome.journal_entry is not None
    change = outcome.journal_entry.position_lot_changes[0]
    assert change.after is not None
    assert change.after.total_cost_basis == rounded.total_cost_basis

    assert _failure_code(
        translate_corporate_action_share_delivery(
            replace(request, open_lots=(replace(old, unit_cost=None),))
        )
    ) is CnAShareCorporateActionTranslationFailureCode.LOT_STATE_MISMATCH
    for basis in (None, Money(1, Scale(3), "CNY")):
        assert _failure_code(
            translate_corporate_action_share_delivery(
                replace(request, open_lots=(replace(old, total_cost_basis=basis),))
            )
        ) is CnAShareCorporateActionTranslationFailureCode.EXACT_COST_BASIS_MISMATCH

    tiny_basis = replace(old, total_cost_basis=Money(1, CNY_SCALE, "CNY"))
    assert _failure_code(
        translate_corporate_action_share_delivery(
            replace(request, open_lots=(tiny_basis,))
        )
    ) is CnAShareCorporateActionTranslationFailureCode.UNIT_COST_QUANTIZATION_MISMATCH


def test_failure_values_reject_code_and_leg_identity_forgery() -> None:
    failure = translate_corporate_action_cash_payment(
        with_cash_evidence(
            cash_request(),
            status=CnAShareCorporateActionDeliveryStatus.CANCELLED,
        )
    ).failure
    assert failure is not None
    with pytest.raises(ValueError):
        replace(failure, subject_ids=("context_mismatch", *failure.subject_ids[1:]))
    with pytest.raises(ValueError):
        replace(
            failure,
            subject_ids=(failure.subject_ids[0], "unknown_leg", *failure.subject_ids[2:]),
        )


def test_outcomes_enforce_strict_xor_and_reject_forgery() -> None:
    cash = cash_request()
    valid = translate_corporate_action_cash_payment(cash)
    assert valid.journal_entry is not None
    failure_outcome = translate_corporate_action_cash_payment(
        with_cash_evidence(cash, status=CnAShareCorporateActionDeliveryStatus.CANCELLED)
    )
    assert failure_outcome.failure is not None

    with pytest.raises(ValueError):
        CnAShareCashPaymentOutcome(cash, None, None)
    with pytest.raises(ValueError):
        CnAShareCashPaymentOutcome(cash, valid.journal_entry, failure_outcome.failure)
    with pytest.raises(ValueError):
        CnAShareCashPaymentOutcome(cash, replace(valid.journal_entry, source_ids=("forged",)), None)
    with pytest.raises(ValueError):
        CnAShareCashPaymentOutcome(cash, None, replace(failure_outcome.failure, code=CnAShareCorporateActionTranslationFailureCode.CONTEXT_MISMATCH))

    share = share_request()
    valid_share = translate_corporate_action_share_delivery(share)
    assert valid_share.journal_entry is not None
    failed_share = translate_corporate_action_share_delivery(
        with_share_evidence(
            share,
            status=CnAShareCorporateActionDeliveryStatus.CANCELLED,
        )
    )
    assert failed_share.failure is not None
    with pytest.raises(ValueError):
        CnAShareShareDeliveryOutcome(share, None, None)
    with pytest.raises(ValueError):
        CnAShareShareDeliveryOutcome(
            share,
            valid_share.journal_entry,
            failed_share.failure,
        )
    with pytest.raises(ValueError):
        CnAShareShareDeliveryOutcome(
            share,
            replace(valid_share.journal_entry, source_ids=("forged",)),
            None,
        )
    with pytest.raises(ValueError):
        CnAShareShareDeliveryOutcome(
            share,
            None,
            replace(
                failed_share.failure,
                code=CnAShareCorporateActionTranslationFailureCode.CONTEXT_MISMATCH,
            ),
        )


def test_translation_is_pure_and_does_not_mutate_entitlement_lot_or_raw_prices() -> None:
    request = share_request()
    raw_prices = (
        Price(1_250, Scale(2), str(request.entitlement.position_key.instrument_id), "CNY"),
        Price(1_275, Scale(2), str(request.entitlement.position_key.instrument_id), "CNY"),
    )
    before = (
        request.entitlement.entitlement_hash,
        canonical_sha256(request.open_lots),
        canonical_sha256(raw_prices),
        canonical_sha256(request),
    )
    translate_corporate_action_share_delivery(request)
    after = (
        request.entitlement.entitlement_hash,
        canonical_sha256(request.open_lots),
        canonical_sha256(raw_prices),
        canonical_sha256(request),
    )
    assert after == before
