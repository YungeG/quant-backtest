from __future__ import annotations

from crypto_quant_backtest import (
    BarDefinitionRef,
    NamedBarWindowQuery,
    NamedBarWindowResult,
    NamedBarWindowView,
    PointInTimeObservationQueryResult,
)
from crypto_quant_domain import UtcInstant

from tests.runtime.observations._causality_fixtures import (
    DECISION_AT_CORRECTION,
    point_in_time_view,
    run_query,
)
from tests.runtime.observations._fixtures import query


def backing_result() -> PointInTimeObservationQueryResult:
    result = run_query(point_in_time_view(DECISION_AT_CORRECTION), query()).result
    assert result is not None
    return result


def named_query(
    *,
    lookback_count: int = 3,
    end_at_or_before: UtcInstant | None = None,
    bar_definition: BarDefinitionRef | None = None,
) -> NamedBarWindowQuery:
    return NamedBarWindowQuery(
        observation_query=query(),
        bar_definition=(
            BarDefinitionRef(
                key="bars.1m.session",
                version=1,
                definition_hash="sha256:" + "b" * 64,
            )
            if bar_definition is None
            else bar_definition
        ),
        decision_instant=DECISION_AT_CORRECTION,
        lookback_count=lookback_count,
        end_at_or_before=end_at_or_before,
    )


def window(view_value: NamedBarWindowView) -> NamedBarWindowResult:
    window_method = getattr(view_value, "window")
    return window_method()
