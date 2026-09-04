from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto_quant_domain import UtcInstant
from crypto_quant_trading import OrderTranslator

from ._fixtures import approval, mapping, order


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/kernel/order-translation-v1.json"


def test_order_translation_matches_the_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen Order Translation fixture: {error}")

    subject = order()
    result = OrderTranslator().translate(
        subject,
        approval(subject),
        mapping(),
        UtcInstant(110),
    )
    assert result.executable_spec is not None

    actual = {
        "fixture_id": "order-translation-v1",
        "mapping": {
            "config_hash": result.executable_spec.translation_mapping.config_hash,
            "mapping_hash": result.executable_spec.translation_mapping_hash,
        },
        "spec": {
            "spec_id": result.executable_spec.spec_id,
            "spec_hash": result.executable_spec.spec_hash,
            "source_intent_hash": result.executable_spec.source_intent_hash,
            "capability_decision_id": result.executable_spec.capability_decision_id,
            "capability_decision_hash": result.executable_spec.capability_decision_hash,
        },
        "report": {
            "report_id": result.report.report_id,
            "status": result.report.status.value,
            "field_mappings": [
                {
                    "canonical_field": value.canonical_field,
                    "canonical_value": value.canonical_value,
                    "target_field": value.target_field,
                    "target_value": value.target_value,
                }
                for value in result.report.field_mappings
            ],
        },
        "result_hash": result.result_hash,
    }
    assert actual == expected
