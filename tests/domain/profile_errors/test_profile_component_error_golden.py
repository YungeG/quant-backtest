from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from crypto_quant_domain import (
    ProfileComponentFailure,
    ProfileComponentFailureCode,
    canonical_sha256,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/domain/profile-component-errors-v1.json"


def load_fixture() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))


def build_failures() -> dict[str, ProfileComponentFailure]:
    subjects = {
        "profile_lookup_failed": "market-semantics:cn-a-share.v1",
        "component_incompatible": "position_accounting_model",
        "capability_missing": "prices.execution_reference",
        "applicability_violation": "bar.execution-model.applicability",
        "unsupported_semantics": "order.execution-style.trailing-stop",
    }
    return {
        code.value: ProfileComponentFailure(code, subjects[code.value])
        for code in ProfileComponentFailureCode
    }


def test_profile_component_failure_catalog_matches_golden_fixture() -> None:
    fixture = load_fixture()
    failures = build_failures()

    assert [code.value for code in ProfileComponentFailureCode] == fixture[
        "reason_codes"
    ]
    assert {
        key: failure.to_canonical_dict() for key, failure in failures.items()
    } == fixture["examples"]
    assert {
        key: canonical_sha256(failure) for key, failure in failures.items()
    } == fixture["expected_sha256"]
