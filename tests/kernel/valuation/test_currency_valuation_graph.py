from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Any, cast

import pytest

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Price,
    PricePurpose,
    ProfileComponentFailure,
    ProfileComponentFailureCode,
    Scale,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_trading import (
    CurrencyValuationEdge,
    CurrencyValuationFailureCode,
    CurrencyValuationGraph,
    CurrencyValuationOutcome,
    CurrencyValuationPathRequest,
    CurrencyValuationPathSelection,
    MarkObservation,
    MarkResolver,
    ProfileComponentRef,
    ProfilePortOutcome,
    ProfilePortType,
    StaleMarkPolicy,
)


BTC = CurrencyId("BTC")
EUR = CurrencyId("EUR")
USD = CurrencyId("USD")
USDT = CurrencyId("USDT")
VALUATION_AT = UtcInstant(100)


def resolved_mark(
    pair: str,
    quote: CurrencyId,
    *,
    units: int,
    purpose: PricePurpose = PricePurpose.VALUATION,
    resolved_at: int = 100,
):
    instrument = InstrumentId(VenueId("synthetic"), pair)
    observation = MarkObservation(
        instrument_id=instrument,
        quote_currency_id=quote,
        price_purpose=purpose,
        price=Price(units, Scale(4), str(instrument), str(quote)),
        observed_at=UtcInstant(resolved_at - 1),
        available_at=UtcInstant(resolved_at),
        stream_id=f"stream:{pair}:{purpose.value}",
        source_event_id=f"event:{pair}:{resolved_at}",
        revision_id="revision:1",
    )
    policy = StaleMarkPolicy(
        policy_key=f"marks.{purpose.value}.v1",
        policy_version=1,
        price_purpose=purpose,
        max_age_nanoseconds=10,
        allow_forward_fill=True,
    )
    outcome = MarkResolver().resolve(
        (observation,),
        instrument_id=instrument,
        price_purpose=purpose,
        requested_at=UtcInstant(resolved_at),
        stale_policy=policy,
    )
    assert outcome.resolved_mark is not None
    return outcome.resolved_mark


def edge(
    source: CurrencyId,
    target: CurrencyId,
    pair: str,
    *,
    units: int,
) -> CurrencyValuationEdge:
    return CurrencyValuationEdge(
        source_currency_id=source,
        resolved_mark=resolved_mark(pair, target, units=units),
    )


def policy_ref(
    port_type: ProfilePortType = ProfilePortType.CURRENCY_VALUATION_POLICY,
) -> ProfileComponentRef:
    return ProfileComponentRef(
        port_type=port_type,
        component_key="test.currency-path.shortest.v1",
        component_version=1,
        component_digest="sha256:" + "ab" * 32,
    )


class ShortestPathPolicy:
    component_ref = policy_ref()

    def select_valuation_path(
        self, request: CurrencyValuationPathRequest, /
    ) -> ProfilePortOutcome[CurrencyValuationPathSelection, ProfileComponentFailure]:
        selected = min(request.candidate_paths, key=lambda path: len(path.edges))
        return cast(
            ProfilePortOutcome[
                CurrencyValuationPathSelection, ProfileComponentFailure
            ],
            ProfilePortOutcome.for_result(
                self.component_ref,
                request,
                CurrencyValuationPathSelection(selected.path_hash),
            ),
        )


class RejectingPolicy:
    component_ref = policy_ref()

    def select_valuation_path(
        self, request: CurrencyValuationPathRequest, /
    ) -> ProfilePortOutcome[CurrencyValuationPathSelection, ProfileComponentFailure]:
        return cast(
            ProfilePortOutcome[
                CurrencyValuationPathSelection, ProfileComponentFailure
            ],
            ProfilePortOutcome.for_failure(
                self.component_ref,
                request,
                ProfileComponentFailure(
                    ProfileComponentFailureCode.UNSUPPORTED_SEMANTICS,
                    "currency-path-selection",
                ),
            ),
        )


class FixedOutcomePolicy:
    def __init__(
        self,
        component_ref: ProfileComponentRef,
        outcome: ProfilePortOutcome[Any, Any],
    ) -> None:
        self.component_ref = component_ref
        self._outcome = outcome

    def select_valuation_path(
        self, request: CurrencyValuationPathRequest, /
    ) -> ProfilePortOutcome[Any, Any]:
        return self._outcome


def multipath_edges() -> tuple[CurrencyValuationEdge, ...]:
    return (
        edge(BTC, USD, "BTC-USD", units=60_000_0000),
        edge(BTC, EUR, "BTC-EUR", units=55_000_0000),
        edge(EUR, USD, "EUR-USD", units=1_0900),
    )


def test_edges_and_graph_are_immutable_point_in_time_canonical_values() -> None:
    direct, via_eur, eur_usd = multipath_edges()
    graph = CurrencyValuationGraph(
        valuation_at=VALUATION_AT,
        price_purpose=PricePurpose.VALUATION,
        edges=(eur_usd, direct, via_eur),
    )
    reversed_graph = CurrencyValuationGraph(
        valuation_at=VALUATION_AT,
        price_purpose=PricePurpose.VALUATION,
        edges=(via_eur, direct, eur_usd),
    )

    assert graph == reversed_graph
    assert graph.graph_hash == canonical_sha256(graph)
    assert direct.target_currency_id == USD
    assert direct.edge_id.startswith("sha256:")
    assert graph.edges == tuple(sorted(graph.edges, key=lambda value: value.edge_id))

    with pytest.raises(FrozenInstanceError):
        cast(Any, direct).source_currency_id = EUR
    with pytest.raises(ValueError, match="different currencies"):
        CurrencyValuationEdge(USD, direct.resolved_mark)
    with pytest.raises(ValueError, match="positive"):
        CurrencyValuationEdge(
            BTC,
            replace(direct.resolved_mark, price=replace(direct.resolved_mark.price, units=0)),
        )
    with pytest.raises(ValueError, match="valuation_at"):
        CurrencyValuationGraph(
            valuation_at=UtcInstant(101),
            price_purpose=PricePurpose.VALUATION,
            edges=(direct,),
        )
    with pytest.raises(ValueError, match="price_purpose"):
        CurrencyValuationGraph(
            valuation_at=VALUATION_AT,
            price_purpose=PricePurpose.MARGIN,
            edges=(direct,),
        )
    with pytest.raises(ValueError, match="duplicate"):
        CurrencyValuationGraph(
            valuation_at=VALUATION_AT,
            price_purpose=PricePurpose.VALUATION,
            edges=(direct, direct),
        )


def test_reporting_currency_uses_an_explicit_identity_path() -> None:
    graph = CurrencyValuationGraph(
        valuation_at=VALUATION_AT,
        price_purpose=PricePurpose.VALUATION,
        edges=(),
    )

    outcome = graph.resolve(USD, USD)

    assert outcome.failure is None
    assert outcome.resolution is not None
    assert outcome.resolution.path.source_currency_id == USD
    assert outcome.resolution.path.reporting_currency_id == USD
    assert outcome.resolution.path.edges == ()
    assert outcome.resolution.path.is_identity
    assert outcome.resolution.policy_outcome is None


def test_unique_path_is_order_independent_and_preserves_mark_provenance() -> None:
    btc_eur = edge(BTC, EUR, "BTC-EUR", units=55_000_0000)
    eur_usd = edge(EUR, USD, "EUR-USD", units=1_0900)

    forward = CurrencyValuationGraph(
        VALUATION_AT, PricePurpose.VALUATION, (btc_eur, eur_usd)
    ).resolve(BTC, USD)
    reverse = CurrencyValuationGraph(
        VALUATION_AT, PricePurpose.VALUATION, (eur_usd, btc_eur)
    ).resolve(BTC, USD)

    assert forward == reverse
    assert forward.resolution is not None
    source_currencies = tuple(
        value.source_currency_id for value in forward.resolution.path.edges
    )
    target_currencies = tuple(
        value.target_currency_id for value in forward.resolution.path.edges
    )
    source_events = tuple(
        value.resolved_mark.source_event_id for value in forward.resolution.path.edges
    )
    expected_sources = (BTC, EUR)
    expected_targets = (EUR, USD)
    expected_events = ("event:BTC-EUR:100", "event:EUR-USD:100")
    assert source_currencies == expected_sources
    assert target_currencies == expected_targets
    assert source_events == expected_events


def test_missing_path_fails_closed_without_an_implicit_stablecoin_peg() -> None:
    outcome = CurrencyValuationGraph(
        VALUATION_AT,
        PricePurpose.VALUATION,
        (),
    ).resolve(USDT, USD)

    assert outcome.resolution is None
    assert outcome.failure is not None
    assert outcome.failure.code is CurrencyValuationFailureCode.MISSING_PATH
    assert outcome.failure.candidate_path_hashes == ()


def test_multiple_paths_require_an_explicit_versioned_policy() -> None:
    graph = CurrencyValuationGraph(
        VALUATION_AT,
        PricePurpose.VALUATION,
        multipath_edges(),
    )

    ambiguous = graph.resolve(BTC, USD)
    selected = graph.resolve(BTC, USD, policy=ShortestPathPolicy())

    assert ambiguous.failure is not None
    assert ambiguous.failure.code is CurrencyValuationFailureCode.NON_UNIQUE_PATH
    assert len(ambiguous.failure.candidate_path_hashes) == 2
    assert selected.failure is None
    assert selected.resolution is not None
    assert len(selected.resolution.path.edges) == 1
    assert selected.resolution.policy_request is not None
    assert selected.resolution.policy_outcome is not None
    assert selected.resolution.policy_outcome.component_ref == policy_ref()
    assert selected.resolution.policy_outcome.input_hash == canonical_sha256(
        selected.resolution.policy_request
    )


def test_policy_failure_and_invalid_outcomes_are_structured_failures() -> None:
    graph = CurrencyValuationGraph(
        VALUATION_AT,
        PricePurpose.VALUATION,
        multipath_edges(),
    )
    request = CurrencyValuationPathRequest(
        graph_hash=graph.graph_hash,
        source_currency_id=BTC,
        reporting_currency_id=USD,
        valuation_at=VALUATION_AT,
        price_purpose=PricePurpose.VALUATION,
        candidate_paths=graph.paths(BTC, USD),
    )

    rejected = graph.resolve(BTC, USD, policy=RejectingPolicy())
    assert rejected.failure is not None
    assert rejected.failure.code is CurrencyValuationFailureCode.POLICY_REJECTED
    assert rejected.failure.policy_outcome is not None

    unknown = ProfilePortOutcome.for_result(
        policy_ref(),
        request,
        CurrencyValuationPathSelection("sha256:" + "cd" * 32),
    )
    invalid_selection = graph.resolve(
        BTC,
        USD,
        policy=FixedOutcomePolicy(policy_ref(), unknown),
    )
    assert invalid_selection.failure is not None
    assert (
        invalid_selection.failure.code
        is CurrencyValuationFailureCode.INVALID_POLICY_OUTCOME
    )

    valid_selection = CurrencyValuationPathSelection(
        request.candidate_paths[0].path_hash
    )
    wrong_input: ProfilePortOutcome[
        CurrencyValuationPathSelection, ProfileComponentFailure
    ] = ProfilePortOutcome(
        component_ref=policy_ref(),
        input_hash="sha256:" + "ef" * 32,
        result=valid_selection,
        failure=None,
    )
    invalid_hash = graph.resolve(
        BTC,
        USD,
        policy=FixedOutcomePolicy(policy_ref(), wrong_input),
    )
    assert invalid_hash.failure is not None
    assert (
        invalid_hash.failure.code
        is CurrencyValuationFailureCode.INVALID_POLICY_OUTCOME
    )

    wrong_ref = policy_ref(ProfilePortType.SESSION_MODEL)
    wrong_port = ProfilePortOutcome.for_result(wrong_ref, request, valid_selection)
    invalid_port = graph.resolve(
        BTC,
        USD,
        policy=FixedOutcomePolicy(wrong_ref, wrong_port),
    )
    assert invalid_port.failure is not None
    assert (
        invalid_port.failure.code
        is CurrencyValuationFailureCode.INVALID_POLICY_OUTCOME
    )


def test_cycles_do_not_create_repeated_currency_paths() -> None:
    usd_eur = edge(USD, EUR, "USD-EUR", units=9174)
    eur_usd = edge(EUR, USD, "EUR-USD", units=1_0900)
    usd_btc = edge(USD, BTC, "USD-BTC", units=1)
    graph = CurrencyValuationGraph(
        VALUATION_AT,
        PricePurpose.VALUATION,
        (usd_eur, eur_usd, usd_btc),
    )

    paths = graph.paths(USD, BTC)

    source_currencies = tuple(value.source_currency_id for value in paths[0].edges)
    expected_sources = (USD,)
    assert len(paths) == 1
    assert source_currencies == expected_sources


def test_outcome_requires_exactly_one_resolution_or_failure() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        CurrencyValuationOutcome(resolution=None, failure=None)
