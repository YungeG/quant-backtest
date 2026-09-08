from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Price,
    PricePurpose,
    Scale,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import (
    MarkObservation,
    MarkResolutionFailureCode,
    MarkResolutionOutcome,
    MarkResolver,
    ResolvedMark,
    StaleMarkPolicy,
)


INSTRUMENT = InstrumentId(VenueId("synthetic"), "asset-1")
OTHER_INSTRUMENT = InstrumentId(VenueId("synthetic"), "asset-2")
USD = CurrencyId("USD")


def policy(
    purpose: PricePurpose = PricePurpose.VALUATION,
    *,
    max_age: int = 20,
    allow_forward_fill: bool = True,
) -> StaleMarkPolicy:
    return StaleMarkPolicy(
        policy_key=f"marks.{purpose.value}.v1",
        policy_version=1,
        price_purpose=purpose,
        max_age_nanoseconds=max_age,
        allow_forward_fill=allow_forward_fill,
    )


def observation(
    event: str,
    *,
    instrument: InstrumentId = INSTRUMENT,
    purpose: PricePurpose = PricePurpose.VALUATION,
    observed_at: int = 100,
    available_at: int | None = None,
    units: int = 12_345,
    revision: str = "revision:1",
) -> MarkObservation:
    return MarkObservation(
        instrument_id=instrument,
        quote_currency_id=USD,
        price_purpose=purpose,
        price=Price(units, Scale(2), str(instrument), str(USD)),
        observed_at=UtcInstant(observed_at),
        available_at=UtcInstant(
            observed_at if available_at is None else available_at
        ),
        stream_id=f"stream:{purpose.value}",
        source_event_id=f"event:{event}",
        revision_id=revision,
    )


def test_observation_and_policy_are_typed_immutable_canonical_facts() -> None:
    mark = observation("one")
    stale_policy = policy()

    assert mark.observation_hash == canonical_sha256(mark)
    assert stale_policy.policy_hash == canonical_sha256(stale_policy)
    assert mark.to_canonical_dict()["source_event_id"] == "event:one"

    with pytest.raises(FrozenInstanceError):
        cast(Any, mark).revision_id = "revision:2"
    with pytest.raises(ValueError, match="available_at"):
        replace(mark, available_at=UtcInstant(99))
    with pytest.raises(ValueError, match="instrument identity"):
        replace(mark, price=Price(1, Scale(2), str(OTHER_INSTRUMENT), "USD"))
    with pytest.raises(ValueError, match="currency identity"):
        replace(mark, price=Price(1, Scale(2), str(INSTRUMENT), "EUR"))
    with pytest.raises(ValueError, match="NFC"):
        replace(mark, revision_id="revision:e\u0301")
    with pytest.raises(ValueError, match="max_age_nanoseconds"):
        replace(stale_policy, max_age_nanoseconds=-1)


def test_exact_resolution_is_order_independent_and_preserves_provenance() -> None:
    older = observation("older", observed_at=90, available_at=95, units=12_000)
    latest = observation("latest", observed_at=100, available_at=101, units=12_500)
    resolver = MarkResolver()

    forward = resolver.resolve(
        (older, latest),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(101),
        stale_policy=policy(),
    )
    reverse = resolver.resolve(
        (latest, older),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(101),
        stale_policy=policy(),
    )

    assert forward == reverse
    assert isinstance(forward.resolved_mark, ResolvedMark)
    assert forward.failure is None
    assert forward.resolved_mark.source_event_id == "event:latest"
    assert forward.resolved_mark.revision_id == "revision:1"
    assert forward.resolved_mark.observed_at == UtcInstant(100)
    assert forward.resolved_mark.available_at == UtcInstant(101)
    assert forward.resolved_mark.resolved_at == UtcInstant(101)
    assert forward.resolved_mark.age_nanoseconds == 1
    assert forward.resolved_mark.mark_id.startswith("sha256:")


def test_purpose_isolation_never_uses_execution_as_valuation_fallback() -> None:
    execution = observation("execution", purpose=PricePurpose.EXECUTION_REFERENCE)
    resolver = MarkResolver()

    outcome = resolver.resolve(
        (execution,),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(100),
        stale_policy=policy(),
    )

    assert outcome.resolved_mark is None
    assert outcome.failure is not None
    assert outcome.failure.code is MarkResolutionFailureCode.PRICE_PURPOSE_UNAVAILABLE
    assert outcome.failure.candidate_count == 0


def test_forward_fill_and_max_age_are_explicit_policy_checks() -> None:
    mark = observation("one", observed_at=100)
    resolver = MarkResolver()

    allowed = resolver.resolve(
        (mark,),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(110),
        stale_policy=policy(max_age=10, allow_forward_fill=True),
    )
    assert allowed.resolved_mark is not None
    assert allowed.resolved_mark.age_nanoseconds == 10

    for stale_policy in (
        policy(max_age=9, allow_forward_fill=True),
        policy(max_age=10, allow_forward_fill=False),
    ):
        rejected = resolver.resolve(
            (mark,),
            instrument_id=INSTRUMENT,
            price_purpose=PricePurpose.VALUATION,
            requested_at=UtcInstant(110),
            stale_policy=stale_policy,
        )
        assert rejected.resolved_mark is None
        assert rejected.failure is not None
        assert rejected.failure.code is MarkResolutionFailureCode.STALE_MARK
        assert rejected.failure.selected_observed_at == UtcInstant(100)
        assert rejected.failure.candidate_observation_hashes == (
            mark.observation_hash,
        )


def test_missing_future_and_policy_purpose_fail_closed() -> None:
    future = observation("future", observed_at=110, available_at=120)
    resolver = MarkResolver()

    missing = resolver.resolve(
        (future,),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(100),
        stale_policy=policy(),
    )
    assert missing.failure is not None
    assert missing.failure.code is MarkResolutionFailureCode.MISSING_MARK

    wrong_policy = resolver.resolve(
        (observation("now"),),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(100),
        stale_policy=policy(PricePurpose.MARGIN),
    )
    assert wrong_policy.failure is not None
    assert wrong_policy.failure.code is MarkResolutionFailureCode.PRICE_PURPOSE_UNAVAILABLE

    no_instrument = resolver.resolve(
        (observation("other", instrument=OTHER_INSTRUMENT),),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(100),
        stale_policy=policy(),
    )
    assert no_instrument.failure is not None
    assert no_instrument.failure.code is MarkResolutionFailureCode.MISSING_MARK


def test_multiple_latest_revisions_are_ambiguous_not_guessed() -> None:
    observations = (
        observation("one", revision="revision:1"),
        observation("one", revision="revision:2"),
        observation("older", observed_at=90),
    )

    outcome = MarkResolver().resolve(
        observations,
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(100),
        stale_policy=policy(),
    )

    assert outcome.resolved_mark is None
    assert outcome.failure is not None
    assert outcome.failure.code is MarkResolutionFailureCode.AMBIGUOUS_MARK
    assert outcome.failure.candidate_count == 2
    assert outcome.failure.candidate_observation_hashes == tuple(
        sorted(value.observation_hash for value in observations[:2])
    )
    assert outcome.failure.selected_observed_at == UtcInstant(100)


def test_outcome_requires_exactly_one_resolved_mark_or_failure() -> None:
    resolved = MarkResolver().resolve(
        (observation("one"),),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(100),
        stale_policy=policy(),
    ).resolved_mark
    assert resolved is not None

    with pytest.raises(ValueError, match="exactly one"):
        MarkResolutionOutcome(resolved_mark=None, failure=None)
    failure = MarkResolver().resolve(
        (),
        instrument_id=INSTRUMENT,
        price_purpose=PricePurpose.VALUATION,
        requested_at=UtcInstant(100),
        stale_policy=policy(),
    ).failure
    assert failure is not None
    with pytest.raises(ValueError, match="exactly one"):
        MarkResolutionOutcome(resolved_mark=resolved, failure=failure)
