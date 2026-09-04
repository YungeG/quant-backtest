from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    Money,
    Quantity,
    Scale,
    canonical_sha256,
)
from crypto_quant_trading.profiles.cn_a_share import (
    CnAShareCorporateActionDeliveryStatus,
    CnAShareCorporateActionTranslationFailureCode,
    translate_corporate_action_cash_payment,
    translate_corporate_action_share_delivery,
)
from tests.kernel.profiles.cn_a_share._corporate_action_accounting_fixtures import (
    cash_request,
    entitlement,
    share_request,
    with_cash_evidence,
)

ROOT = Path(__file__).resolve().parents[4]
FIXTURE = ROOT / "tests/fixtures/kernel/profiles/cn_a_share/corporate-action-accounting-v1.json"


def _read_fixture() -> dict[str, object]:
    value = json.loads(FIXTURE.read_bytes())
    assert isinstance(value, dict)
    return value


def test_static_accounting_control_matches_xshe_xshg_and_qualification_golden() -> None:
    xshe = entitlement()
    xshg = entitlement("xshg")
    cash = cash_request()
    share = share_request()
    cash_success = translate_corporate_action_cash_payment(cash)
    share_success = translate_corporate_action_share_delivery(share)
    failure_outcome = translate_corporate_action_cash_payment(
        with_cash_evidence(
            cash,
            gross_cash=Money(6_999, Scale(2), "CNY"),
            net_cash=Money(6_999, Scale(2), "CNY"),
        )
    )
    multi_defect = replace(
        with_cash_evidence(
            cash,
            entitlement_hash="sha256:" + "0" * 64,
            status=CnAShareCorporateActionDeliveryStatus.CANCELLED,
        ),
        journal_entry_id=DomainId(DomainIdKind.FILL, "fil_" + "2" * 64),
    )
    multi_outcome = translate_corporate_action_cash_payment(multi_defect)
    assert cash_success.journal_entry is not None
    assert share_success.journal_entry is not None
    assert failure_outcome.failure is not None
    assert multi_outcome.failure is not None
    actual = {
        "fixture_id": "cn-a-share-corporate-action-accounting-v1",
        "qualification": {
            "allowed_grade": "development",
            "decision_grade_eligible": False,
            "profile_qualified": False,
            "deployment_authorized": False,
        },
        "controls": {
            "CA-XSHE-001": {
                "payment": xshe.gross_cash,
                "delivery": Quantity(
                    xshe.bonus_quantity.units + xshe.capitalization_quantity.units,
                    Scale(0),
                    str(xshe.position_key.instrument_id),
                ),
                "lot_quantity": share_request().open_lots[0].quantity,
                "record_entitlement": xshe.registered_quantity.units,
                "entitlement_hash": xshe.entitlement_hash,
            },
            "CA-XSHG-001": {
                "payment": xshg.gross_cash,
                "entitlement_hash": xshg.entitlement_hash,
            },
            "multi_defect_first_failure": multi_outcome.failure.code.name,
            "xor_rejection": True,
            "unchanged_raw_prices": True,
        },
        "hashes": {
            "cash_evidence": cash.evidence.evidence_hash,
            "share_evidence": share.evidence.evidence_hash,
            "cash_request": cash.request_hash,
            "share_request": share.request_hash,
            "failure": failure_outcome.failure.failure_hash,
            "cash_outcome": cash_success.outcome_hash,
            "share_outcome": share_success.outcome_hash,
        },
    }
    from crypto_quant_domain import canonical_bytes

    assert json.loads(canonical_bytes(actual)) == _read_fixture()


def test_all_new_values_have_frozen_v1_type_literals_key_order_and_content_hashes() -> None:
    cash = cash_request()
    cash_success = translate_corporate_action_cash_payment(cash)
    share = share_request()
    share_success = translate_corporate_action_share_delivery(share)
    failure_outcome = translate_corporate_action_cash_payment(
        with_cash_evidence(cash, gross_cash=Money(6_999, Scale(2), "CNY"), net_cash=Money(6_999, Scale(2), "CNY"))
    )
    assert cash_success.journal_entry is not None
    assert share_success.journal_entry is not None
    assert failure_outcome.failure is not None
    assert failure_outcome.failure.code is CnAShareCorporateActionTranslationFailureCode.DELIVERED_VALUE_MISMATCH

    fixture_hashes = _read_fixture()["hashes"]
    assert isinstance(fixture_hashes, dict)
    values = (
        (cash.evidence, "cn_a_share_cash_payment_evidence", "evidence_hash", "cash_evidence"),
        (share.evidence, "cn_a_share_share_delivery_evidence", "evidence_hash", "share_evidence"),
        (cash, "cn_a_share_cash_payment_request", "request_hash", "cash_request"),
        (share, "cn_a_share_share_delivery_request", "request_hash", "share_request"),
        (
            failure_outcome.failure,
            "cn_a_share_corporate_action_translation_failure",
            "failure_hash",
            "failure",
        ),
        (cash_success, "cn_a_share_cash_payment_outcome", "outcome_hash", "cash_outcome"),
        (share_success, "cn_a_share_share_delivery_outcome", "outcome_hash", "share_outcome"),
    )
    for value, type_literal, hash_name, fixture_key in values:
        canonical = value.to_canonical_dict()
        assert tuple(canonical)[:2] == ("type", "schema_version")
        assert canonical["type"] == type_literal
        assert canonical["schema_version"] == 1
        assert getattr(value, hash_name) == canonical_sha256(value)
        assert getattr(value, hash_name) == fixture_hashes[fixture_key]

    assert tuple(cash.evidence.to_canonical_dict()) == (
        "type", "schema_version", "evidence_id", "source_ref", "entitlement_hash",
        "corporate_action_id", "event_id", "event_hash", "status", "trigger_at",
        "available_at", "gross_cash", "withholding", "net_cash", "tax_disposition",
        "tradable", "withdrawable", "margin_eligible",
    )
    assert tuple(share.evidence.to_canonical_dict()) == (
        "type", "schema_version", "evidence_id", "source_ref", "entitlement_hash",
        "corporate_action_id", "event_id", "event_hash", "status", "trigger_at",
        "available_at", "delivered_bonus_quantity", "delivered_capitalization_quantity",
        "withholding", "tax_disposition", "sellable",
    )
    assert tuple(cash.to_canonical_dict()) == (
        "type", "schema_version", "entitlement", "evidence", "cash_key",
        "journal_entry_id", "recorded_at",
    )
    assert tuple(share.to_canonical_dict()) == (
        "type", "schema_version", "entitlement", "evidence", "open_lots",
        "unit_cost_quantization", "journal_entry_id", "recorded_at",
    )
    assert tuple(failure_outcome.failure.to_canonical_dict()) == (
        "type", "schema_version", "code", "subject_ids",
    )
    assert tuple(cash_success.to_canonical_dict()) == (
        "type", "schema_version", "request", "journal_entry", "failure",
    )
    assert tuple(share_success.to_canonical_dict()) == (
        "type", "schema_version", "request", "journal_entry", "failure",
    )
