from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict, cast

import pytest

from crypto_quant_domain import Money, RoundingPolicy, Scale


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/domain/numeric-boundaries-v1.json"


class RescaleCase(TypedDict):
    id: str
    units: int
    source_scale: int
    target_scale: int
    rounding: str
    expected_units: int


def load_cases() -> list[RescaleCase]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert payload["fixture_id"] == "numeric-boundaries-v1"
    assert payload["schema_version"] == 1
    return cast(list[RescaleCase], payload["rescale_cases"])


@pytest.mark.parametrize("case", load_cases(), ids=lambda case: str(case["id"]))
def test_rescale_obeys_explicit_rounding_fixture(case: RescaleCase) -> None:
    value = Money(
        units=case["units"],
        scale=Scale(case["source_scale"]),
        currency="USD",
    )

    actual = value.rescale(
        Scale(case["target_scale"]),
        RoundingPolicy(str(case["rounding"])),
    )

    assert actual.units == case["expected_units"]


def test_rescale_requires_a_rounding_policy_even_when_increasing_scale() -> None:
    value = Money(units=1, scale=Scale(0), currency="USD")

    with pytest.raises(TypeError):
        value.rescale(Scale(2))  # type: ignore[call-arg]
