from __future__ import annotations

import inspect

import pytest

from crypto_quant_domain import (
    DomainId,
    DomainIdKind,
    IdentityManifest,
    IdentityNamespace,
    derive_domain_id,
)


def test_same_semantic_inputs_reproduce_the_same_id() -> None:
    namespace = IdentityNamespace(value="backtest", version="1")
    key = b'{"instrument":"BTC-USDT","side":"buy"}'

    first = derive_domain_id(
        namespace=namespace,
        kind=DomainIdKind.ORDER,
        semantic_run_id="semantic-run-1",
        semantic_key=key,
        ordinal=0,
    )
    second = derive_domain_id(
        namespace=namespace,
        kind=DomainIdKind.ORDER,
        semantic_run_id="semantic-run-1",
        semantic_key=key,
        ordinal=0,
    )

    assert first == second
    assert first.kind is DomainIdKind.ORDER


def test_ordinal_prevents_identical_fill_economics_from_colliding() -> None:
    namespace = IdentityNamespace(value="backtest", version="1")
    key = b'{"order":"ord-1","price":100,"quantity":1}'

    first = derive_domain_id(
        namespace=namespace,
        kind=DomainIdKind.FILL,
        semantic_run_id="semantic-run-1",
        semantic_key=key,
        ordinal=0,
    )
    second = derive_domain_id(
        namespace=namespace,
        kind=DomainIdKind.FILL,
        semantic_run_id="semantic-run-1",
        semantic_key=key,
        ordinal=1,
    )

    assert first != second


def test_attempt_identity_cannot_enter_the_derivation_interface() -> None:
    assert "attempt" not in inspect.signature(derive_domain_id).parameters
    with pytest.raises(TypeError):
        derive_domain_id(  # type: ignore[call-arg]
            namespace=IdentityNamespace("backtest", "1"),
            kind=DomainIdKind.ORDER,
            semantic_run_id="semantic-run-1",
            semantic_key=b"key",
            ordinal=0,
            attempt_id="attempt-1",
        )


def test_namespace_version_changes_id_and_manifest() -> None:
    key = b"economic-key"
    first_namespace = IdentityNamespace("backtest", "1")
    second_namespace = IdentityNamespace("backtest", "2")

    first = derive_domain_id(
        namespace=first_namespace,
        kind=DomainIdKind.ORDER,
        semantic_run_id="semantic-run-1",
        semantic_key=key,
        ordinal=0,
    )
    second = derive_domain_id(
        namespace=second_namespace,
        kind=DomainIdKind.ORDER,
        semantic_run_id="semantic-run-1",
        semantic_key=key,
        ordinal=0,
    )

    assert first != second
    assert IdentityManifest(first_namespace).to_canonical_dict() != (
        IdentityManifest(second_namespace).to_canonical_dict()
    )


def test_identity_inputs_validate_fail_closed() -> None:
    namespace = IdentityNamespace("backtest", "1")
    with pytest.raises(ValueError, match="canonical"):
        IdentityNamespace(" backtest", "1")
    with pytest.raises(ValueError, match="semantic_run_id"):
        derive_domain_id(
            namespace=namespace,
            kind=DomainIdKind.ORDER,
            semantic_run_id=" run",
            semantic_key=b"key",
            ordinal=0,
        )
    with pytest.raises(ValueError, match="semantic_key"):
        derive_domain_id(
            namespace=namespace,
            kind=DomainIdKind.ORDER,
            semantic_run_id="run",
            semantic_key=b"",
            ordinal=0,
        )
    with pytest.raises(ValueError, match="ordinal"):
        derive_domain_id(
            namespace=namespace,
            kind=DomainIdKind.ORDER,
            semantic_run_id="run",
            semantic_key=b"key",
            ordinal=-1,
        )
    with pytest.raises(ValueError, match="DomainId"):
        DomainId(DomainIdKind.ORDER, "ord_not-a-digest")
