from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from crypto_quant_backtest.cn_a_share_dividend_profile_v2 import (
    compose_tushare_000703_dividend_profile_v2,
)
from crypto_quant_backtest.cn_a_share_dividend_runtime_v2 import (
    CnAShareDividendCashEntitlementV2,
    CnAShareDividendCashPaymentV2,
    CnAShareDividendFinancialDispatcherV2,
    build_tushare_000703_dividend_scheduled_events_v2,
)
from crypto_quant_backtest.financial_dispatch import (
    FinancialDispatchFailureCode,
    FinancialStateView,
)
from crypto_quant_bundle_builder.tushare_000703_dividend_action_set_v2 import (
    map_tushare_000703_dividend_action_set_v2,
)
from crypto_quant_domain import (
    CashBalance,
    CashBalanceKey,
    CurrencyId,
    InstrumentId,
    Money,
    PositionBalance,
    PositionBalanceKey,
    Quantity,
    Scale,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    AccountingJournal,
    LedgerBalanceRegistration,
    LedgerSchema,
    LedgerState,
    ReservationCommitment,
    ResourceReservationState,
)


ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence/tushare-000703-dividend-authority-v1"
ACCOUNT = "account:000703-development"
INSTRUMENT = InstrumentId(VenueId("xshe"), "000703")
CASH_KEY = CashBalanceKey(ACCOUNT, VenueId("xshe"), CurrencyId("CNY"))
POSITION_KEY = PositionBalanceKey(ACCOUNT, VenueId("xshe"), INSTRUMENT)


def _profile():
    action_set = map_tushare_000703_dividend_action_set_v2(
        (EVIDENCE / "acquisition-receipt.json").read_bytes(),
        (EVIDENCE / "response/dividend.json").read_bytes(),
        INSTRUMENT,
    )
    return compose_tushare_000703_dividend_profile_v2(
        json.loads(canonical_bytes(action_set)), ACCOUNT
    )


def _ledger(quantity: int, scale: Scale = Scale(0)) -> LedgerState:
    schema = LedgerSchema(
        (
            LedgerBalanceRegistration(CASH_KEY, Scale(2)),
            LedgerBalanceRegistration(POSITION_KEY, scale),
        )
    )
    positions = ()
    if quantity:
        positions = (
            PositionBalance(
                POSITION_KEY,
                Quantity(quantity, scale, str(INSTRUMENT)),
                (),
            ),
        )
    return LedgerState(
        schema=schema,
        cursor=AccountingJournal.empty().cursor_at(0),
        cash_balances=(CashBalance(CASH_KEY, Money(0, Scale(2), "CNY")),),
        position_balances=positions,
        realized_pnl=(),
        fees=(),
        financing=(),
    )


def _state(quantity: int, artifacts=(), scale: Scale = Scale(0)) -> FinancialStateView:
    return FinancialStateView(
        journal=AccountingJournal.empty(),
        ledger_state=_ledger(quantity, scale),
        reservation_state=ResourceReservationState(
            ACCOUNT, (), (), ReservationCommitment.empty()
        ),
        position_lot_books=(),
        artifacts=artifacts,
    )


def test_canonical_events_project_register_then_pay_cash_from_ledger() -> None:
    profile = _profile()
    dispatcher = CnAShareDividendFinancialDispatcherV2(profile)
    events = build_tushare_000703_dividend_scheduled_events_v2(profile)
    assert len(events) == len(profile.actions) * 3
    record, entitlement, payment = events[:3]
    assert (record.event_at.phase.rank, entitlement.event_at.phase.rank, payment.event_at.phase.rank) == (100, 105, 110)
    assert record.event_at.instant < entitlement.event_at.instant <= payment.event_at.instant
    for event in events:
        assert event.payload.development_only is True
        assert event.payload.decision_grade_eligible is False
        assert event.payload.live_eligible is False
        assert event.payload.deployment_authorized is False

    record_outcome = dispatcher.dispatch_scheduled_event(record, _state(1_200))
    assert record_outcome.result is not None
    [register_artifact] = record_outcome.result.artifacts
    assert register_artifact.payload.snapshot.registered_quantity.units == 1_200
    entitlement_outcome = dispatcher.dispatch_scheduled_event(
        entitlement,
        _state(1_200, record_outcome.result.artifacts),
    )
    assert entitlement_outcome.result is not None
    [entitlement_artifact] = entitlement_outcome.result.artifacts
    assert type(entitlement_artifact.payload) is CnAShareDividendCashEntitlementV2
    assert entitlement_artifact.payload.gross_cash == Money(12_000, Scale(2), "CNY")
    assert entitlement_artifact.payload.development_only is True
    assert entitlement_artifact.payload.decision_grade_eligible is False
    assert entitlement_artifact.payload.live_eligible is False
    assert entitlement_artifact.payload.deployment_authorized is False

    payment_outcome = dispatcher.dispatch_scheduled_event(
        payment,
        _state(1_200, record_outcome.result.artifacts + entitlement_outcome.result.artifacts),
    )
    assert payment_outcome.result is not None
    [cash_entry] = payment_outcome.result.journal_entries
    [cash_artifact] = payment_outcome.result.artifacts
    assert cash_entry.balance_changes[0].key == CASH_KEY
    assert cash_entry.balance_changes[0].value == Money(12_000, Scale(2), "CNY")
    assert type(cash_artifact.payload) is CnAShareDividendCashPaymentV2
    assert cash_artifact.payload.net_cash == Money(12_000, Scale(2), "CNY")
    assert cash_artifact.payload.entitlement_hash == entitlement_artifact.payload.entitlement_hash
    assert cash_artifact.payload.development_only is True
    assert cash_artifact.payload.decision_grade_eligible is False
    assert cash_artifact.payload.live_eligible is False
    assert cash_artifact.payload.deployment_authorized is False
    assert register_artifact.payload.development_only is True
    assert register_artifact.payload.decision_grade_eligible is False
    assert register_artifact.payload.live_eligible is False
    assert register_artifact.payload.deployment_authorized is False


def test_zero_registered_position_produces_zero_cash_without_journal_entry() -> None:
    profile = _profile()
    dispatcher = CnAShareDividendFinancialDispatcherV2(profile)
    record, entitlement, payment = build_tushare_000703_dividend_scheduled_events_v2(profile)[:3]
    register = dispatcher.dispatch_scheduled_event(record, _state(0))
    assert register.result is not None
    entitled = dispatcher.dispatch_scheduled_event(
        entitlement, _state(0, register.result.artifacts)
    )
    assert entitled.result is not None
    payment_outcome = dispatcher.dispatch_scheduled_event(
        payment, _state(0, register.result.artifacts + entitled.result.artifacts)
    )
    assert payment_outcome.result is not None
    assert not payment_outcome.result.journal_entries
    [artifact] = payment_outcome.result.artifacts
    assert artifact.payload.net_cash == Money(0, Scale(2), "CNY")


def test_all_actions_are_ordered_and_dispatch_once_from_their_register() -> None:
    profile = _profile()
    dispatcher = CnAShareDividendFinancialDispatcherV2(profile)
    events = build_tushare_000703_dividend_scheduled_events_v2(profile)
    action_ids = tuple(action.action_id for action in profile.actions)
    record_ids = tuple(
        event.payload.action_id
        for event in events
        if event.payload.__class__.__name__ == "CnAShareDividendRecordEventV2"
    )
    assert record_ids == action_ids

    quantities = (100, 200, 0)
    artifacts = ()
    paid = []
    for event in events:
        quantity = quantities[event.payload.action_index]
        outcome = dispatcher.dispatch_scheduled_event(event, _state(quantity, artifacts))
        assert outcome.result is not None
        artifacts += outcome.result.artifacts
        paid.extend(entry.balance_changes[0].value for entry in outcome.result.journal_entries)

    assert paid == [Money(1_000, Scale(2), "CNY"), Money(1_000, Scale(2), "CNY")]
    assert tuple(artifact.role for artifact in artifacts) == tuple(
        role
        for action_id in action_ids
        for role in (
            f"tushare_dividend_register:{action_id}",
            f"tushare_dividend_entitlement:{action_id}",
            f"tushare_dividend_cash_payment:{action_id}",
        )
    )


def test_duplicate_delivery_fails_closed() -> None:
    profile = _profile()
    dispatcher = CnAShareDividendFinancialDispatcherV2(profile)
    record = build_tushare_000703_dividend_scheduled_events_v2(profile)[0]
    first = dispatcher.dispatch_scheduled_event(record, _state(1))
    assert first.result is not None
    duplicate = dispatcher.dispatch_scheduled_event(record, _state(1, first.result.artifacts))
    assert duplicate.failure is not None
    assert duplicate.failure.code is FinancialDispatchFailureCode.ARTIFACT_COVERAGE_MISMATCH


@pytest.mark.parametrize(
    ("quantity", "scale"),
    ((120_000, Scale(2)), (-1, Scale(0))),
)
def test_nonintegral_or_negative_ledger_quantity_fails_closed(
    quantity: int, scale: Scale
) -> None:
    profile = _profile()
    dispatcher = CnAShareDividendFinancialDispatcherV2(profile)
    record, entitlement = build_tushare_000703_dividend_scheduled_events_v2(profile)[:2]
    register = dispatcher.dispatch_scheduled_event(record, _state(quantity, scale=scale))
    assert register.result is not None
    entitlement_outcome = dispatcher.dispatch_scheduled_event(
        entitlement,
        _state(quantity, register.result.artifacts, scale),
    )
    assert entitlement_outcome.failure is not None
    assert entitlement_outcome.failure.code is FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE


def test_missing_register_artifact_or_event_tampering_fails_closed() -> None:
    profile = _profile()
    dispatcher = CnAShareDividendFinancialDispatcherV2(profile)
    record, entitlement, payment = build_tushare_000703_dividend_scheduled_events_v2(profile)[:3]
    missing = dispatcher.dispatch_scheduled_event(entitlement, _state(1))
    assert missing.failure is not None
    assert missing.failure.code is FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE

    record_outcome = dispatcher.dispatch_scheduled_event(record, _state(1))
    assert record_outcome.result is not None
    missing_entitlement = dispatcher.dispatch_scheduled_event(
        payment, _state(1, record_outcome.result.artifacts)
    )
    assert missing_entitlement.failure is not None
    assert missing_entitlement.failure.code is FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE

    assert record_outcome.result is not None
    forged_artifact = replace(
        record_outcome.result.artifacts[0],
        component_digest="sha256:" + "f" * 64,
    )
    forged = dispatcher.dispatch_scheduled_event(entitlement, _state(1, (forged_artifact,)))
    assert forged.failure is not None
    assert forged.failure.code is FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE

    entitled = dispatcher.dispatch_scheduled_event(
        entitlement, _state(1, record_outcome.result.artifacts)
    )
    assert entitled.result is not None
    forged_payload = replace(
        entitled.result.artifacts[0].payload,
        gross_cash=Money(99, Scale(2), "CNY"),
    )
    forged_entitlement = replace(
        entitled.result.artifacts[0],
        result_hash=canonical_sha256(forged_payload),
        payload=forged_payload,
    )
    forged_payment = dispatcher.dispatch_scheduled_event(
        payment,
        _state(1, record_outcome.result.artifacts + (forged_entitlement,)),
    )
    assert forged_payment.failure is not None
    assert forged_payment.failure.code is FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE

    forged_record = replace(
        record_outcome.result.artifacts[0],
        source_event_id="forged.record.event",
    )
    tampered_record_payment = dispatcher.dispatch_scheduled_event(
        payment,
        _state(1, (forged_record,) + entitled.result.artifacts),
    )
    assert tampered_record_payment.failure is not None
    assert (
        tampered_record_payment.failure.code
        is FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE
    )

    forged_record_time = replace(
        record_outcome.result.artifacts[0],
        occurred_at=entitlement.event_at,
    )
    tampered_timestamp_payment = dispatcher.dispatch_scheduled_event(
        payment,
        _state(1, (forged_record_time,) + entitled.result.artifacts),
    )
    assert tampered_timestamp_payment.failure is not None
    assert (
        tampered_timestamp_payment.failure.code
        is FinancialDispatchFailureCode.PROFILE_COMPONENT_FAILURE
    )

    tampered = dispatcher.dispatch_scheduled_event(
        record.__class__(
            record.event_id,
            record.event_at,
            "forged.operation",
            record.component_keys,
            record.identity_bindings,
            record.payload,
            record.semantic_payload,
            record.expected_artifact_roles,
        ),
        _state(1),
    )
    assert tampered.failure is not None
    assert tampered.failure.code is FinancialDispatchFailureCode.EVENT_PLAN_MISMATCH
