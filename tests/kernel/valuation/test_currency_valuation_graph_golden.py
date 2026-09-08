from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from crypto_quant_domain import (
    CurrencyId,
    InstrumentId,
    Price,
    PricePurpose,
    ProfileComponentFailure,
    Scale,
    UtcInstant,
    VenueId,
    canonical_bytes,
    canonical_sha256,
)
from crypto_quant_trading import (
    CurrencyValuationEdge,
    CurrencyValuationGraph,
    CurrencyValuationPathRequest,
    CurrencyValuationPathSelection,
    MarkObservation,
    MarkResolver,
    ProfileComponentRef,
    ProfilePortOutcome,
    ProfilePortType,
    StaleMarkPolicy,
)


ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = ROOT / "tests/fixtures/kernel/currency-valuation-graph-v1.json"
BTC = CurrencyId("BTC")
EUR = CurrencyId("EUR")
USD = CurrencyId("USD")
USDT = CurrencyId("USDT")
VALUATION_AT = UtcInstant(100)


def edge(
    source: CurrencyId,
    target: CurrencyId,
    pair: str,
    units: int,
) -> CurrencyValuationEdge:
    instrument = InstrumentId(VenueId("synthetic"), pair)
    observation = MarkObservation(
        instrument_id=instrument,
        quote_currency_id=target,
        price_purpose=PricePurpose.VALUATION,
        price=Price(units, Scale(4), str(instrument), str(target)),
        observed_at=UtcInstant(99),
        available_at=VALUATION_AT,
        stream_id=f"stream:{pair}:valuation",
        source_event_id=f"event:{pair}:100",
        revision_id="revision:1",
    )
    stale_policy = StaleMarkPolicy(
        policy_key="marks.valuation.v1",
        policy_version=1,
        price_purpose=PricePurpose.VALUATION,
        max_age_nanoseconds=10,
        allow_forward_fill=True,
    )
    resolved = MarkResolver().resolve(
        (observation,),
        instrument_id=instrument,
        price_purpose=PricePurpose.VALUATION,
        requested_at=VALUATION_AT,
        stale_policy=stale_policy,
    ).resolved_mark
    assert resolved is not None
    return CurrencyValuationEdge(source, resolved)


class DirectPathPolicy:
    component_ref = ProfileComponentRef(
        port_type=ProfilePortType.CURRENCY_VALUATION_POLICY,
        component_key="fixture.currency-path.direct.v1",
        component_version=1,
        component_digest="sha256:" + "ab" * 32,
    )

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


def test_currency_valuation_graph_matches_frozen_golden() -> None:
    try:
        expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        pytest.fail(f"invalid frozen currency-valuation fixture: {error}")

    graph = CurrencyValuationGraph(
        valuation_at=VALUATION_AT,
        price_purpose=PricePurpose.VALUATION,
        edges=(
            edge(BTC, USD, "BTC-USD", 60_000_0000),
            edge(BTC, EUR, "BTC-EUR", 55_000_0000),
            edge(EUR, USD, "EUR-USD", 1_0900),
        ),
    )
    identity = graph.resolve(USD, USD)
    missing = graph.resolve(USDT, USD)
    ambiguous = graph.resolve(BTC, USD)
    selected = graph.resolve(BTC, USD, policy=DirectPathPolicy())

    try:
        actual = {
            "fixture_id": "currency-valuation-graph-v1",
            "graph": json.loads(canonical_bytes(graph)),
            "graph_hash": graph.graph_hash,
            "path_hashes": [path.path_hash for path in graph.paths(BTC, USD)],
            "identity": json.loads(canonical_bytes(identity)),
            "missing": json.loads(canonical_bytes(missing)),
            "ambiguous": json.loads(canonical_bytes(ambiguous)),
            "selected": json.loads(canonical_bytes(selected)),
            "selected_hash": canonical_sha256(selected),
        }
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        pytest.fail(f"currency-valuation evidence was not canonical: {error}")

    assert actual == expected
