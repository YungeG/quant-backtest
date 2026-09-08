from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import DomainIdKind, OrderSide, canonical_bytes
from crypto_quant_trading import (
    FeeAssessmentEngine,
    FeeChargedJournalTranslator,
    FinalFeeAssessmentResult,
)

from ._fixtures import (
    assessment_time,
    cash_key,
    domain_id,
    fill_basis,
    order_basis,
    recorded_at,
    rule_set,
    session_basis,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/final-fee-assessment-v1.json"


def canonical_json(value: object) -> object:
    try:
        return json.loads(canonical_bytes(value).decode("utf-8"))
    except (TypeError, ValueError, UnicodeError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid canonical final Fee evidence: {error}")


def test_final_fee_assessment_matches_the_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen final Fee fixture: {error}")

    engine = FeeAssessmentEngine()
    fill_outcome = engine.assess(
        basis=fill_basis(side=OrderSide.SELL),
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "5"),
        assessment_time=assessment_time(),
    )
    order_outcome = engine.assess(
        basis=order_basis(),
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "6"),
        assessment_time=assessment_time(),
    )
    session_outcome = engine.assess(
        basis=session_basis(),
        rule_set=rule_set(),
        fee_assessment_id=domain_id(DomainIdKind.FEE, "7"),
        assessment_time=assessment_time(),
    )
    assert order_outcome.result is not None
    journal_outcome = FeeChargedJournalTranslator().translate(
        result=order_outcome.result,
        cash_key=cash_key(),
        journal_entry_id=domain_id(DomainIdKind.JOURNAL, "e"),
        recorded_at=recorded_at(),
    )

    assert fill_outcome.result is not None
    assert session_outcome.result is not None
    assert journal_outcome.result is not None

    def summarize(
        result: FinalFeeAssessmentResult, outcome_hash: str
    ) -> dict[str, object]:
        return {
            "basis_hash": result.basis.basis_hash,
            "rule_set_hash": result.rule_set.rule_set_hash,
            "lines": [canonical_json(line) for line in result.lines],
            "minimum_adjustments": [
                canonical_json(value) for value in result.minimum_adjustments
            ],
            "assessment": canonical_json(result.assessment),
            "result_hash": result.result_hash,
            "outcome_hash": outcome_hash,
        }

    actual = {
        "fixture_id": "final-fee-assessment-v1",
        "fill": summarize(fill_outcome.result, fill_outcome.outcome_hash),
        "order": summarize(order_outcome.result, order_outcome.outcome_hash),
        "session": summarize(session_outcome.result, session_outcome.outcome_hash),
        "fee_charged_journal": {
            "journal_entry": canonical_json(journal_outcome.result.journal_entry),
            "result_hash": journal_outcome.result.result_hash,
            "outcome_hash": journal_outcome.outcome_hash,
        },
    }
    assert actual == expected
