"""Versioned CN portfolio close NAV analysis; old analysis schemas stay frozen.

Values are declarations, not evidence. Only the source-bound Runtime and the
Repository's cold verification can admit a stored analysis. No OOS authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import json
import re
from typing import Any
from zoneinfo import ZoneInfo

import crypto_quant_domain as d
import crypto_quant_trading as t
from crypto_quant_trading.profiles.cn_a_share import CnAShareCalendarDayKind

from .analysis_derivation import _calculate_simple_period_return
from .artifact_envelope_reader import ArtifactEnvelopeReader
from .artifact_envelope_publisher import ArtifactEnvelopePublisher
from .integrity import ResultGrade
from .publication_refs import BacktestCanonicalPublicationRef

_PROFILE_TYPE = "cn_a_share_portfolio_economic_daily_nav_metric_profile"
_ANALYSIS_TYPE = "cn_a_share_portfolio_economic_daily_nav_analysis"
_ZONE = ZoneInfo("Asia/Shanghai")
_CENT = d.Scale(2)
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_QUANTUM = Decimal("0.000000000000000001")


def _hash(value: object) -> None:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError("NAV source hash must be canonical sha256")


def _money(value: object) -> None:
    if type(value) is not d.Money or value.currency != "CNY" or value.scale != _CENT:
        raise ValueError("NAV requires exact CNY-cent money")


def _ref(value: object, artifact_type: str, version: int) -> None:
    if type(value) is not d.ArtifactRef or (value.artifact_type, value.schema_version) != (artifact_type, version):
        raise TypeError("NAV source requires exact " + artifact_type + "@" + str(version))


@dataclass(frozen=True, slots=True)
class CnASharePortfolioEconomicDailyNavMetricProfileV1:
    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": _PROFILE_TYPE, "schema_version": 1,
                "profile_key": "cn.shared-cny.economic-close.return-maxdd.fill-count.v1",
                "reporting_currency": "CNY", "equity_scale": 2,
                "drawdown_sampling": "initial_peak_and_every_frozen_trading_close",
                "close_time": "15:00:00 Asia/Shanghai",
                "external_cash_flows": "reject_except_net_zero_modeled_venue_transfers",
                "rounding": "half_even_18_decimal_places", "accepted_grade": "development",
                "validation_eligible": False, "deployment_authorized": False}


_PROFILE = CnASharePortfolioEconomicDailyNavMetricProfileV1()
_PROFILE_ENVELOPE = d.ArtifactEnvelope.create(_PROFILE_TYPE, 1, _PROFILE)
_PROFILE_REF = d.ArtifactRef.from_envelope(_PROFILE_ENVELOPE)


@dataclass(frozen=True, slots=True)
class CnASharePortfolioEconomicDailyNavPointV1:
    trade_date: str
    occurred_at: d.SimulationInstant
    equity: d.Money
    snapshot_hash: str
    journal_prefix_hash: str
    mark_batch_hash: str
    native_fact_hash: str
    economic_projection_hash: str
    dividend_state_hash: str
    gross_receivable: d.Money
    tax_liability: d.Money

    def __post_init__(self) -> None:
        if type(self.trade_date) is not str or date.fromisoformat(self.trade_date).isoformat() != self.trade_date:
            raise ValueError("NAV date must be canonical ISO date")
        if type(self.occurred_at) is not d.SimulationInstant:
            raise TypeError("NAV observation requires the full SimulationInstant")
        local = self.occurred_at.instant.to_datetime().astimezone(_ZONE)
        if (local.date().isoformat() != self.trade_date or local.time() != time(15)
                or self.occurred_at.instant.epoch_nanoseconds % 1_000_000_000):
            raise ValueError("NAV observation must be at the exact declared trading close")
        _money(self.equity)
        for amount in (self.gross_receivable, self.tax_liability):
            _money(amount)
            if amount.units < 0:
                raise ValueError("economic NAV receivable/liability cannot be negative")
        if self.occurred_at.phase.rank != 160 or self.occurred_at.phase.code != "cn_economic_native" or self.occurred_at.source_sequence.value != 0:
            raise ValueError("economic NAV requires exact close160 clock")
        for value in (self.snapshot_hash, self.journal_prefix_hash, self.mark_batch_hash, self.native_fact_hash, self.economic_projection_hash, self.dividend_state_hash):
            _hash(value)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_economic_daily_nav_point", "schema_version": 1,
                "trade_date": self.trade_date, "occurred_at": self.occurred_at, "equity": self.equity,
                "snapshot_hash": self.snapshot_hash, "journal_prefix_hash": self.journal_prefix_hash,
                "mark_batch_hash": self.mark_batch_hash, "native_fact_hash": self.native_fact_hash,
                "economic_projection_hash": self.economic_projection_hash, "dividend_state_hash": self.dividend_state_hash,
                "gross_receivable": self.gross_receivable, "tax_liability": self.tax_liability}


from .cn_a_share_portfolio_daily_nav_analysis_v1 import _calculate_close_nav_metrics_v1


def _metrics(initial, points):
    return _calculate_close_nav_metrics_v1(initial, tuple(point.equity for point in points))


@dataclass(frozen=True, slots=True)
class CnASharePortfolioEconomicDailyNavAnalysisV1:
    metric_profile_ref: d.ArtifactRef
    source_publication_ref: BacktestCanonicalPublicationRef
    execution_input_ref: d.ArtifactRef
    definition_ref: d.ArtifactRef
    action_set_ref: d.ArtifactRef
    engine_result_ref: d.ArtifactRef
    source_execution_result_hash: str
    starting_snapshot_hash: str
    starting_economic_projection_hash: str
    initial_equity: d.Money
    points: tuple[CnASharePortfolioEconomicDailyNavPointV1, ...]
    trade_count: int
    result_grade: ResultGrade
    simple_period_return: str = field(init=False)
    maximum_drawdown: str = field(init=False)

    def __post_init__(self) -> None:
        _ref(self.metric_profile_ref, _PROFILE_TYPE, 1)
        if self.metric_profile_ref != _PROFILE_REF:
            raise ValueError("NAV metric profile is not the accepted exact version")
        if type(self.source_publication_ref) is not BacktestCanonicalPublicationRef:
            raise TypeError("NAV requires exact standard canonical publication ref")
        for value, name, version in ((self.execution_input_ref, "backtest_execution_input_bundle", 9),
                (self.definition_ref, "backtest_profile_portfolio_definition", 2),
                (self.action_set_ref, "cn_a_share_cash_dividend_action_set", 1),
                (self.engine_result_ref, "engine_execution_result", 1)):
            _ref(value, name, version)
        _hash(self.source_execution_result_hash)
        _hash(self.starting_snapshot_hash)
        _hash(self.starting_economic_projection_hash)
        _money(self.initial_equity)
        if self.initial_equity.units <= 0:
            raise ValueError("economic NAV initial equity must be positive")
        if (type(self.points) is not tuple or not 0 < len(self.points) <= 4096
                or any(type(p) is not CnASharePortfolioEconomicDailyNavPointV1 for p in self.points)):
            raise ValueError("NAV needs a bounded exact close series")
        days = tuple(p.trade_date for p in self.points)
        if days != tuple(sorted(set(days))):
            raise ValueError("NAV dates must be strictly increasing and unique")
        if type(self.trade_count) is not int or self.trade_count < 0:
            raise ValueError("NAV fill count must be a nonnegative integer")
        if type(self.result_grade) is not ResultGrade or self.result_grade is not ResultGrade.DEVELOPMENT:
            raise ValueError("NAV v1 accepts development only, never upgrades a grade")
        returned, maximum = _metrics(self.initial_equity, self.points)
        object.__setattr__(self, "simple_period_return", returned)
        object.__setattr__(self, "maximum_drawdown", maximum)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": _ANALYSIS_TYPE, "schema_version": 1,
                "metric_profile_ref": self.metric_profile_ref, "source_publication_ref": self.source_publication_ref,
                "execution_input_ref": self.execution_input_ref, "definition_ref": self.definition_ref,
                "action_set_ref": self.action_set_ref, "engine_result_ref": self.engine_result_ref, "source_execution_result_hash": self.source_execution_result_hash,
                "starting_snapshot_hash": self.starting_snapshot_hash, "starting_economic_projection_hash": self.starting_economic_projection_hash, "initial_equity": self.initial_equity,
                "points": self.points, "trade_count": self.trade_count, "result_grade": self.result_grade.value,
                "simple_period_return": self.simple_period_return, "maximum_drawdown": self.maximum_drawdown,
                "source_qualification_verified": False, "formal_publication_eligible": False,
                "validation_eligible": False, "deployment_authorized": False,
                "provider_availability_verified": False, "account_fees_verified": False, "trade_authorized": False}


@dataclass(frozen=True, slots=True)
class CnASharePortfolioEconomicDailyNavAnalysisRefV1:
    artifact_ref: d.ArtifactRef

    def __post_init__(self) -> None:
        _ref(self.artifact_ref, _ANALYSIS_TYPE, 1)

    def to_canonical_dict(self) -> dict[str, object]:
        return {"type": "cn_a_share_portfolio_economic_daily_nav_analysis_ref", "schema_version": 1,
                "artifact_ref": self.artifact_ref}


def _map(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or any(type(k) is not str for k in value):
        raise TypeError("NAV source requires a canonical mapping")
    return value


def _seq(value: object) -> tuple[Any, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError("NAV source requires a canonical sequence")
    return tuple(value)


def _wire_ref(value: object) -> d.ArtifactRef:
    from .target_repository import _artifact_ref
    return _artifact_ref(value)


def _read_envelope(reader: ArtifactEnvelopeReader, ref: d.ArtifactRef) -> d.ArtifactEnvelope:
    read = reader.read(ref=ref)
    if (type(read) is not d.ArtifactReadResult or type(read.envelope) is not d.ArtifactEnvelope
            or d.ArtifactRef.from_envelope(read.envelope) != ref
            or read.source_bytes != d.canonical_bytes(read.envelope)
            or read.source_hash != d.canonical_sha256(read.envelope)):
        raise ValueError("NAV retained source byte/ref binding mismatch")
    return read.envelope


def _raw(envelope: d.ArtifactEnvelope) -> Mapping[str, Any]:
    return _map(json.loads(d.canonical_bytes(envelope.payload)))


def _read_nav_profile(value: object) -> CnASharePortfolioEconomicDailyNavMetricProfileV1:
    if d.canonical_bytes(value) != d.canonical_bytes(_PROFILE):
        raise ValueError("NAV profile payload is not the accepted exact version")
    return _PROFILE


def _read_nav_analysis(value: object) -> CnASharePortfolioEconomicDailyNavAnalysisV1:
    from .execution_inputs import _read_money, _read_simulation_instant
    raw = _map(value)
    publication = _map(raw["source_publication_ref"])
    if set(publication) != {"type", "artifact_ref"} or publication["type"] != "backtest_canonical_publication_ref":
        raise ValueError("NAV publication must be the exact nominal canonical ref")
    points = []
    for item in _seq(raw["points"]):
        row = _map(item)
        point = CnASharePortfolioEconomicDailyNavPointV1(row["trade_date"], _read_simulation_instant(row["occurred_at"]),
            _read_money(row["equity"]), row["snapshot_hash"], row["journal_prefix_hash"],
            row["mark_batch_hash"], row["native_fact_hash"], row["economic_projection_hash"], row["dividend_state_hash"],
            _read_money(row["gross_receivable"]), _read_money(row["tax_liability"]))
        if d.canonical_bytes(point) != d.canonical_bytes(row):
            raise ValueError("NAV point must reconstruct exact canonical fields")
        points.append(point)
    result = CnASharePortfolioEconomicDailyNavAnalysisV1(_wire_ref(raw["metric_profile_ref"]),
        BacktestCanonicalPublicationRef(_wire_ref(publication["artifact_ref"])),
        _wire_ref(raw["execution_input_ref"]), _wire_ref(raw["definition_ref"]), _wire_ref(raw["action_set_ref"]), _wire_ref(raw["engine_result_ref"]),
        raw["source_execution_result_hash"], raw["starting_snapshot_hash"], raw["starting_economic_projection_hash"], _read_money(raw["initial_equity"]),
        tuple(points), raw["trade_count"], ResultGrade(raw["result_grade"]))
    if d.canonical_bytes(result) != d.canonical_bytes(raw):
        raise ValueError("NAV analysis fields, metrics or qualification claims do not reconstruct")
    return result




def _build_economic_nav_v1(*, reader, publication_ref, market_reader):
    from .cn_a_share_portfolio_economic_result_v1 import _load_verified_economic_completed_v1
    from .execution_inputs import _read_money, _read_simulation_instant
    completed, case, actual_input_ref, engine_ref, engine, definition_ref, action_ref = _load_verified_economic_completed_v1(
        reader=reader, publication_ref=publication_ref, market_reader=market_reader)
    points = []
    artifacts = sorted((a for a in engine.payload["financial_artifacts"] if a["role"] == "economic_daily_projection"),
        key=lambda a:_read_simulation_instant(a["occurred_at"]))
    for artifact in artifacts:
        fact = artifact["payload"]["payload"]
        checkpoint = fact["checkpoint"]
        projection = checkpoint["economic_projection"]
        at = _read_simulation_instant(artifact["occurred_at"])
        points.append(CnASharePortfolioEconomicDailyNavPointV1(at.instant.to_datetime().astimezone(_ZONE).date().isoformat(),
            at, _read_money(projection["snapshot"]["equity"]), d.canonical_sha256(projection["snapshot"]), checkpoint["journal_hash"],
            d.canonical_sha256(fact["marks"]), d.canonical_sha256(artifact), d.canonical_sha256(projection),
            d.canonical_sha256(checkpoint["dividend_state"]), _read_money(projection["gross_receivable"]), _read_money(projection["tax_liability"])))
    initial = case.execution_case_plan.initial_economic_projection
    if not points or points[-1].equity != completed.execution_summary.final_portfolio_snapshot.equity:
        raise ValueError("economic NAV final close/economic final equity mismatch")
    return CnASharePortfolioEconomicDailyNavAnalysisV1(_PROFILE_REF, publication_ref, actual_input_ref, definition_ref,
        action_ref, engine_ref, completed.source_execution_result_hash, d.canonical_sha256(initial.snapshot),
        initial.projection_hash, initial.snapshot.equity, tuple(points), len(completed.execution_summary.fills), completed.result_grade)


class CnASharePortfolioEconomicDailyNavAnalysisRuntimeV1:
    def __init__(self, *, reader: ArtifactEnvelopeReader, publisher: ArtifactEnvelopePublisher, market_reader):
        from crypto_quant_market_data import MarketBundleReader
        if not callable(getattr(reader, "read", None)) or not callable(getattr(publisher, "put", None)) or not isinstance(market_reader, MarketBundleReader):
            raise TypeError("economic NAV requires explicit artifact and MarketBundle readers")
        self._reader, self._publisher, self._market_reader = reader, publisher, market_reader

    def publish_metric_profile(self):
        from .cash_development_provider import _publish, _verify_published
        ref = _publish(self._publisher, _PROFILE_ENVELOPE)
        if ref != _PROFILE_REF:
            raise ValueError("economic NAV publisher returned wrong profile ref")
        _verify_published(self._reader, ref, _PROFILE_ENVELOPE)
        return ref

    def derive(self, *, publication_ref: BacktestCanonicalPublicationRef, metric_profile_ref: d.ArtifactRef):
        from .cash_development_provider import _publish, _verify_published
        if type(publication_ref) is not BacktestCanonicalPublicationRef:
            raise TypeError("economic NAV requires a completed canonical publication")
        _ref(metric_profile_ref, _PROFILE_TYPE, 1)
        if metric_profile_ref != _PROFILE_REF:
            raise ValueError("economic NAV profile identity mismatch")
        _read_nav_profile(_read_envelope(self._reader, metric_profile_ref).payload)
        value = _build_economic_nav_v1(reader=self._reader, publication_ref=publication_ref, market_reader=self._market_reader)
        envelope = d.ArtifactEnvelope.create(_ANALYSIS_TYPE, 1, value)
        ref = _publish(self._publisher, envelope)
        _verify_published(self._reader, ref, envelope)
        return CnASharePortfolioEconomicDailyNavAnalysisRefV1(ref)
