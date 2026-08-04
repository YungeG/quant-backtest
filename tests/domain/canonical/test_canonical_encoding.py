from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from crypto_quant_domain import (
    CanonicalEnvelope,
    CanonicalSchema,
    CanonicalizationError,
    Money,
    Scale,
    canonical_bytes,
    canonical_sha256,
)


def test_mapping_insertion_order_does_not_change_bytes_or_hash() -> None:
    first = {"beta": 2, "alpha": {"z": 3, "a": 1}}
    second = {"alpha": {"a": 1, "z": 3}, "beta": 2}

    assert canonical_bytes(first) == canonical_bytes(second)
    assert canonical_sha256(first) == canonical_sha256(second)


def test_domain_objects_are_encoded_only_through_canonical_dictionary() -> None:
    envelope = CanonicalEnvelope(
        schema=CanonicalSchema("money", 1),
        payload=Money(units=123, scale=Scale(2), currency="USD"),
    )

    assert canonical_bytes(envelope) == (
        b'{"payload":{"currency":"USD","scale":2,"type":"money",'
        b'"units":123},"schema":{"name":"money","version":1}}'
    )


@pytest.mark.parametrize(
    "value, reason",
    [
        (1.0, "float"),
        (Decimal("1.0"), "Decimal"),
        (datetime(2024, 1, 1, tzinfo=timezone.utc), "datetime"),
        (date(2024, 1, 1), "date"),
        (b"bytes", "bytes"),
        ({1, 2}, "set"),
        ({1: "non-string-key"}, "mapping key"),
        ("e\u0301", "NFC"),
    ],
)
def test_forbidden_canonical_values_fail_closed(value: object, reason: str) -> None:
    with pytest.raises(CanonicalizationError, match=reason):
        canonical_bytes({"value": value})


def test_unknown_object_is_rejected() -> None:
    with pytest.raises(CanonicalizationError, match="unsupported"):
        canonical_bytes({"value": object()})


def test_schema_identity_is_strict_and_changes_hash() -> None:
    payload = {"value": 1}
    first = CanonicalEnvelope(CanonicalSchema("example", 1), payload)
    second = CanonicalEnvelope(CanonicalSchema("example", 2), payload)

    assert canonical_sha256(first) != canonical_sha256(second)
    with pytest.raises(ValueError, match="schema name"):
        CanonicalSchema("Example", 1)
    with pytest.raises(ValueError, match="version"):
        CanonicalSchema("example", 0)
