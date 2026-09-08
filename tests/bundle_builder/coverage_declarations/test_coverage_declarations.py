from __future__ import annotations

import json
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from typing import cast

import pytest
from crypto_quant_bundle_builder import (
    AvailabilityClosureDeclaration,
    AvailabilitySpan,
    BuilderStaleMarkPolicy,
    MarketAvailabilityReason,
    PricePurposeRequirement,
    RevisionClosureDeclaration,
    RevisionTerminalLineage,
)
from crypto_quant_domain import (
    InstrumentId,
    PricePurpose,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability

FIXTURE = (
    Path(__file__).resolve().parents[2]
    / "fixtures/market_data/coverage-declarations-v1.json"
)
HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64


def policy(
    purpose: PricePurpose = PricePurpose.VALUATION,
    *,
    allow_forward_fill: bool = True,
) -> BuilderStaleMarkPolicy:
    return BuilderStaleMarkPolicy(
        policy_key=f"test.{purpose.value}.v1",
        policy_version=1,
        price_purpose=purpose,
        max_age_nanoseconds=1_000,
        allow_forward_fill=allow_forward_fill,
    )


def requirement(
    purpose: PricePurpose = PricePurpose.VALUATION,
    *,
    stale_policy: BuilderStaleMarkPolicy | None = None,
) -> PricePurposeRequirement:
    return PricePurposeRequirement(
        requirement_key="test.price-purpose.v1",
        requirement_version=1,
        scope_key="test.scope.v1",
        instrument_id=InstrumentId(VenueId("test"), "asset"),
        price_purpose=purpose,
        stream_key="bars.explicit",
        event_type="bar",
        capability=MarketBundleCapability("price_bars", 1),
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        stale_policy=policy(purpose) if stale_policy is None else stale_policy,
        source_key="test.coverage-authority.v1",
        source_hash=HASH_A,
    )


def availability() -> AvailabilityClosureDeclaration:
    return AvailabilityClosureDeclaration(
        closure_scope_key=("bars.explicit", "test:asset", "valuation"),
        coverage_start=UtcInstant(0),
        coverage_end_exclusive=UtcInstant(1_000),
        spans=(
            AvailabilitySpan(
                UtcInstant(0),
                UtcInstant(600),
                MarketAvailabilityReason.NO_TRADES,
            ),
            AvailabilitySpan(
                UtcInstant(600),
                UtcInstant(1_000),
                MarketAvailabilityReason.NO_SESSION,
            ),
        ),
        source_key="test.calendar-provider-claim.v1",
        source_hash=HASH_A,
        bar_aggregation_manifest_hash=HASH_B,
    )


def revision() -> RevisionClosureDeclaration:
    return RevisionClosureDeclaration(
        closure_scope_key=("bars.explicit", "test:asset", "valuation"),
        causal_visibility_limit=UtcInstant(1_000),
        terminals=(
            RevisionTerminalLineage("lineage-a", HASH_A),
            RevisionTerminalLineage("lineage-b", HASH_B),
        ),
        source_key="test.terminal-set-claim.v1",
        source_hash=HASH_A,
    )


def test_static_schema_v1_fixture_and_hashes_are_exact() -> None:
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    actual = {
        "fixture_id": "coverage-declarations-v1",
        "price_purpose_requirement": requirement().to_canonical_dict(),
        "availability_closure": availability().to_canonical_dict(),
        "revision_closure": revision().to_canonical_dict(),
    }

    assert actual == expected
    assert requirement().requirement_hash == canonical_sha256(
        requirement()._canonical_body()
    )
    assert availability().declaration_hash == canonical_sha256(
        availability()._canonical_body()
    )
    assert revision().declaration_hash == canonical_sha256(revision()._canonical_body())


def test_policy_rejects_type_forgery_and_is_frozen_slotted() -> None:
    with pytest.raises(ValueError, match="positive integer"):
        replace(policy(), policy_version=True)
    with pytest.raises(TypeError, match="PricePurpose"):
        replace(policy(), price_purpose=cast(PricePurpose, "valuation"))
    with pytest.raises(TypeError, match="integer"):
        replace(policy(), max_age_nanoseconds=cast(int, 1.0))
    with pytest.raises(TypeError, match="bool"):
        replace(policy(), allow_forward_fill=cast(bool, 1))
    with pytest.raises(FrozenInstanceError):
        policy().policy_key = "forged"  # type: ignore[misc]
    assert not hasattr(policy(), "__dict__")


def test_requirement_rejects_purpose_mismatch_and_forward_fill_boundary() -> None:
    with pytest.raises(ValueError, match="purpose must match"):
        requirement(PricePurpose.MARGIN, stale_policy=policy())

    for purpose in (
        PricePurpose.EXECUTION_REFERENCE,
        PricePurpose.LIQUIDATION,
    ):
        with pytest.raises(ValueError, match="cannot allow forward fill"):
            requirement(purpose, stale_policy=policy(purpose))
        assert (
            requirement(
                purpose,
                stale_policy=policy(purpose, allow_forward_fill=False),
            ).price_purpose
            is purpose
        )


def test_requirement_rejects_interval_type_hash_and_qualification_forgery() -> None:
    with pytest.raises(ValueError, match="non-empty half-open"):
        replace(requirement(), coverage_end_exclusive=UtcInstant(0))
    with pytest.raises(TypeError, match="instrument_id"):
        replace(requirement(), instrument_id=cast(InstrumentId, "test:asset"))
    with pytest.raises(TypeError, match="capability"):
        replace(
            requirement(),
            capability=cast(MarketBundleCapability, ("price_bars", 1)),
        )
    with pytest.raises(TypeError, match="stale_policy"):
        replace(requirement(), stale_policy=cast(BuilderStaleMarkPolicy, {}))
    with pytest.raises(ValueError, match="sha256"):
        replace(requirement(), source_hash="unsafe")
    forged = requirement()
    object.__setattr__(forged, "decision_grade_eligible", True)
    with pytest.raises(ValueError, match="development-only"):
        forged.__post_init__()


def test_availability_requires_exact_ordered_coverage_and_explicit_empty_scope() -> (
    None
):
    value = availability()
    with pytest.raises(TypeError, match="MarketAvailabilityReason"):
        replace(value.spans[0], reason=cast(MarketAvailabilityReason, "NO_TRADES"))
    with pytest.raises(TypeError, match="tuple of AvailabilitySpan"):
        replace(value, spans=cast(tuple[AvailabilitySpan, ...], (value.spans[0], {})))
    with pytest.raises(TypeError, match="3-tuple"):
        replace(
            value,
            closure_scope_key=cast(tuple[str, str, str], ("stream", "instrument")),
        )
    with pytest.raises(ValueError, match="non-overlapping"):
        replace(
            value,
            spans=(
                value.spans[0],
                replace(value.spans[1], start=UtcInstant(500)),
            ),
        )
    with pytest.raises(ValueError, match="without gaps"):
        replace(
            value,
            spans=(
                value.spans[0],
                replace(value.spans[1], start=UtcInstant(700)),
            ),
        )
    empty = replace(
        value,
        coverage_end_exclusive=value.coverage_start,
        spans=(),
    )
    assert empty.spans == ()
    with pytest.raises(ValueError, match="empty coverage"):
        replace(empty, spans=(value.spans[0],))


def test_revision_closure_requires_unique_ordered_lineages_and_allows_empty_scope() -> (
    None
):
    value = revision()
    with pytest.raises(ValueError, match="sha256"):
        replace(value.terminals[0], terminal_event_hash="unsafe")
    with pytest.raises(TypeError, match="tuple of RevisionTerminalLineage"):
        replace(
            value,
            terminals=cast(
                tuple[RevisionTerminalLineage, ...],
                (value.terminals[0], {}),
            ),
        )
    with pytest.raises(ValueError, match="canonical order"):
        replace(value, terminals=tuple(reversed(value.terminals)))
    with pytest.raises(ValueError, match="duplicate logical lineage"):
        replace(
            value,
            terminals=(
                value.terminals[0],
                replace(value.terminals[1], logical_lineage_key="lineage-a"),
            ),
        )
    assert replace(value, terminals=()).terminals == ()
