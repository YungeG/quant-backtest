from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    DomainIdKind,
    IdentityNamespace,
    derive_domain_id,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "tests/fixtures/domain/deterministic-domain-ids-v1.json"


def load_fixture() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))


@pytest.mark.parametrize("case", load_fixture()["cases"], ids=lambda case: case["kind"])
def test_domain_id_matches_controlled_golden(case: dict[str, Any]) -> None:
    fixture = load_fixture()
    namespace = IdentityNamespace(
        value=fixture["namespace"], version=fixture["namespace_version"]
    )

    actual = derive_domain_id(
        namespace=namespace,
        kind=DomainIdKind(case["kind"]),
        semantic_run_id=fixture["semantic_run_id"],
        semantic_key=case["semantic_key_utf8"].encode("utf-8"),
        ordinal=case["ordinal"],
    )

    assert actual.value == case["expected"]


def test_fixture_algorithm_is_the_authoritative_v1_algorithm() -> None:
    fixture = load_fixture()
    assert fixture["algorithm"] == "sha256-length-prefixed-v1"
