from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from crypto_quant_domain import (
    AccountingEntryType,
    ArtifactEnvelope,
    ArtifactRef,
    Money,
)

from .analysis import (
    AnalysisArtifactRef,
    BacktestAnalysis,
    BacktestMetricProfile,
)
from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .verified_publications import VerifiedCompletedPublication, VerifiedCompletedPublicationV2

__all__ = ["BacktestAnalysisRuntime"]

_EXTERNAL_CASH_FLOW_TYPES = frozenset(
    {
        AccountingEntryType.CAPITAL_DEPOSITED,
        AccountingEntryType.CAPITAL_WITHDRAWN,
        AccountingEntryType.CAPITAL_TRANSFERRED,
    }
)
_QUANTUM = Decimal("0.000000000000000001")
_PROFILE = BacktestMetricProfile("simple_period_return.fill_count.v1", 1)
_PROFILE_REF = ArtifactRef.from_envelope(
    ArtifactEnvelope.create("backtest_metric_profile", 1, _PROFILE)
)


def _money_decimal(value: Money) -> Decimal:
    return Decimal(value.units).scaleb(-value.scale.places)


def _calculate_simple_period_return(
    starting: Money,
    ending: Money,
    external_changes: tuple[Money, ...],
) -> str | None:
    values = (starting, ending, *external_changes)
    maximum_digits = max(len(str(abs(value.units))) for value in values)
    maximum_scale = max(value.scale.places for value in values)
    with localcontext() as context:
        context.prec = maximum_digits + maximum_scale + len(str(len(values))) + 40
        context.rounding = ROUND_HALF_EVEN
        non_reporting: dict[str, Decimal] = {}
        net_external_cash_flow = Decimal(0)
        for change in external_changes:
            amount = _money_decimal(change)
            if change.currency == starting.currency:
                net_external_cash_flow += amount
            else:
                non_reporting[change.currency] = (
                    non_reporting.get(change.currency, Decimal(0)) + amount
                )
        if ending.currency != starting.currency or any(
            value != 0 for value in non_reporting.values()
        ):
            return None
        denominator = _money_decimal(starting)
        if denominator <= 0:
            return None
        value = (
            _money_decimal(ending) - denominator - net_external_cash_flow
        ) / denominator
        rounded = value.quantize(_QUANTUM, rounding=ROUND_HALF_EVEN)

    text = format(rounded, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


def _simple_period_return(completed: VerifiedCompletedPublication | VerifiedCompletedPublicationV2) -> str | None:
    journal_entries = completed.execution_summary.final_journal.entries[
        completed.initial_journal_entry_count :
    ]
    external_changes = tuple(
        change.value
        for entry in journal_entries
        if entry.entry_type in _EXTERNAL_CASH_FLOW_TYPES
        for change in entry.balance_changes
    )
    if not all(type(value) is Money for value in external_changes):
        return None
    return _calculate_simple_period_return(
        completed.starting_snapshot.equity,
        completed.execution_summary.final_portfolio_snapshot.equity,
        external_changes,
    )


class BacktestAnalysisRuntime:
    def __init__(self, publisher: ArtifactEnvelopePublisher) -> None:
        if not callable(getattr(publisher, "put", None)):
            raise TypeError("publisher must provide put")
        self._publisher = publisher

    def derive(
        self,
        completed: VerifiedCompletedPublication | VerifiedCompletedPublicationV2,
        metric_profile_ref: ArtifactRef,
    ) -> AnalysisArtifactRef:
        if type(completed) is not VerifiedCompletedPublication and type(completed) is not VerifiedCompletedPublicationV2:
            raise TypeError("completed must be exact VerifiedCompletedPublication or VerifiedCompletedPublicationV2")
        if type(metric_profile_ref) is not ArtifactRef:
            raise TypeError("metric_profile_ref must be exact ArtifactRef")
        if metric_profile_ref != _PROFILE_REF:
            raise ValueError("metric_profile_ref does not bind accepted metric profile")

        analysis = BacktestAnalysis(
            metric_profile_ref=metric_profile_ref,
            source_publication_ref=completed.source_publication_ref,
            source_execution_result_hash=completed.source_execution_result_hash,
            simple_period_return=_simple_period_return(completed),
            trade_count=len(completed.execution_summary.fills),
            result_grade=completed.result_grade,
        )
        envelope = ArtifactEnvelope.create("backtest_analysis", 1, analysis)
        expected_ref = ArtifactRef.from_envelope(envelope)
        stored_ref = self._publisher.put(envelope=envelope)
        if type(stored_ref) is not ArtifactRef:
            raise TypeError("publisher.put must return exact ArtifactRef")
        if stored_ref != expected_ref:
            raise ValueError("publisher.put returned ref does not bind envelope")
        return AnalysisArtifactRef(stored_ref)
