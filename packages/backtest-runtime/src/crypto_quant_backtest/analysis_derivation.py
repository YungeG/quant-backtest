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
    VerifiedBacktestAnalysis,
)
from .verified_publications import VerifiedCompletedPublication

__all__ = ["derive_backtest_analysis"]

_EXTERNAL_CASH_FLOW_TYPES = frozenset(
    {
        AccountingEntryType.CAPITAL_DEPOSITED,
        AccountingEntryType.CAPITAL_WITHDRAWN,
        AccountingEntryType.CAPITAL_TRANSFERRED,
    }
)
_QUANTUM = Decimal("0.000000000000000001")


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


def _simple_period_return(completed: VerifiedCompletedPublication) -> str | None:
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


def derive_backtest_analysis(
    completed: VerifiedCompletedPublication,
    metric_profile_ref: ArtifactRef,
    metric_profile: BacktestMetricProfile,
) -> VerifiedBacktestAnalysis:
    if type(completed) is not VerifiedCompletedPublication:
        raise TypeError("completed must be exact VerifiedCompletedPublication")
    if type(metric_profile_ref) is not ArtifactRef:
        raise TypeError("metric_profile_ref must be exact ArtifactRef")
    if type(metric_profile) is not BacktestMetricProfile:
        raise TypeError("metric_profile must be exact BacktestMetricProfile")
    profile_envelope = ArtifactEnvelope.create(
        "backtest_metric_profile", 1, metric_profile
    )
    if metric_profile_ref != ArtifactRef.from_envelope(profile_envelope):
        raise ValueError("metric_profile_ref does not bind metric_profile")

    analysis = BacktestAnalysis(
        metric_profile_ref=metric_profile_ref,
        source_publication_ref=completed.source_publication_ref,
        source_execution_result_hash=completed.source_execution_result_hash,
        simple_period_return=_simple_period_return(completed),
        trade_count=len(completed.execution_summary.fills),
        result_grade=completed.result_grade,
    )
    envelope = ArtifactEnvelope.create("backtest_analysis", 1, analysis)
    return VerifiedBacktestAnalysis(
        AnalysisArtifactRef(ArtifactRef.from_envelope(envelope)), analysis
    )
